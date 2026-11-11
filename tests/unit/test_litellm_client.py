"""Unit tests for GeekCuboLLMClient — focused on the stream/non-stream branch.

Round 5 of /codex review caught a real production bug: the adapter always
called `model_dump()` on the LiteLLM response, but `stream=True` returns a
`CustomStreamWrapper` (an async iterable), not a response object with
`model_dump`. Streaming through the production adapter would either crash
or return garbage. Integration tests had been mocking `client.acompletion`
directly so the real adapter path was untested.

These tests pin the contract: stream=True returns the raw wrapper for the
caller to iterate; stream=False returns a dict with `_geekcubo_meta` injected.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeChunkAsyncIter:
    """Stand-in for litellm's CustomStreamWrapper — async iterable of chunks."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


@pytest.fixture
def fake_router_with_stream(monkeypatch):
    """Build an GeekCuboLLMClient whose Router is mocked to return a stream
    wrapper for stream=True and a ModelResponse-like object for stream=False.
    """
    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    deployments = [
        ProviderDeployment(
            model_name="gpt-4o-mini",
            litellm_model="openai/gpt-4o-mini",
            api_key="sk-test",
            provider="openai",
        )
    ]

    # Patch the Router class so __init__ doesn't try to talk to upstream.
    fake_router = MagicMock()

    class _ResponseModel:
        def __init__(self, model: str):
            self.model = model

        def model_dump(self):
            return {"model": self.model, "choices": [], "usage": {}}

    async def _acompletion(**kwargs):
        if kwargs.get("stream"):
            return _FakeChunkAsyncIter([
                {"id": "x", "model": "gpt-4o-mini",
                 "choices": [{"delta": {"content": "hi"}}]},
                {"id": "x", "model": "gpt-4o-mini",
                 "choices": [{"delta": {}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
            ])
        return _ResponseModel("gpt-4o-mini")

    fake_router.acompletion = AsyncMock(side_effect=_acompletion)
    # The adapter imports Router inside __init__, so patch the source
    # symbol on the litellm package before construction.
    import litellm
    monkeypatch.setattr(litellm, "Router", lambda **_: fake_router)

    client = GeekCuboLLMClient(deployments=deployments, strategy="balanced")
    return client


async def test_acompletion_stream_returns_async_iterable_not_dict(fake_router_with_stream):
    """Production bug from round-5 review: passing stream=True must not
    eagerly coerce the wrapper to a dict. The caller (chat.py SSE path)
    needs to `async for` over it."""
    result = await fake_router_with_stream.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    # Result must be async-iterable.
    assert hasattr(result, "__aiter__"), (
        f"stream=True must return an async iterable, got {type(result).__name__}"
    )
    # Drain it.
    chunks = []
    async for c in result:
        chunks.append(c)
    assert len(chunks) == 2


async def test_acompletion_forwards_parallel_tool_calls_false(fake_router_with_stream):
    """Issue #124: `parallel_tool_calls=False` must reach LiteLLM Router
    kwargs as False, not be dropped as a falsy value."""
    await fake_router_with_stream.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
        parallel_tool_calls=False,
    )
    call = fake_router_with_stream._router.acompletion.await_args
    assert call.kwargs["parallel_tool_calls"] is False


async def test_acompletion_forwards_json_schema_response_format(fake_router_with_stream):
    """Issue #132: LangChain json_schema `response_format` must reach the
    LiteLLM Router kwargs intact (strict + nested schema)."""
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "MovieReview",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    }
    await fake_router_with_stream.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        response_format=response_format,
    )
    call = fake_router_with_stream._router.acompletion.await_args
    assert call.kwargs["response_format"] == response_format


async def test_openai_deployments_advertise_response_schema(monkeypatch):
    """LiteLLM uses model_info.supports_response_schema to decide whether
    to pass json_schema through or re-wrap it. OpenAI-compatible
    deployments must advertise support so LangChain structured output
    is not rewritten into an invalid schema."""
    import litellm

    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    captured: dict = {}

    def _router(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(litellm, "Router", _router)

    GeekCuboLLMClient(
        deployments=[
            ProviderDeployment(
                model_name="gpt-4o-mini",
                litellm_model="openai/gpt-4o-mini",
                api_key="sk-test",
                provider="openai",
            ),
            ProviderDeployment(
                model_name="claude-3-5-sonnet-latest",
                litellm_model="anthropic/claude-3-5-sonnet-latest",
                api_key="sk-test",
                provider="anthropic",
            ),
        ]
    )
    by_name = {e["model_name"]: e for e in captured["model_list"]}
    assert by_name["gpt-4o-mini"]["model_info"]["supports_response_schema"] is True
    assert "supports_response_schema" not in (by_name["claude-3-5-sonnet-latest"].get("model_info") or {})


async def test_acompletion_non_stream_returns_dict_with_geekcubo_meta(fake_router_with_stream):
    """Non-stream path must keep returning a dict with the _geekcubo_meta
    injection — that's the contract the existing chat.py blocking path
    and request_log writer rely on."""
    result = await fake_router_with_stream.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert isinstance(result, dict)
    assert result.get("model") == "gpt-4o-mini"
    assert "_geekcubo_meta" in result
    assert result["_geekcubo_meta"].get("provider") == "openai"


async def test_acompletion_propagates_litellm_hidden_params_into_geekcubo_meta(monkeypatch):
    """LiteLLM stashes per-call cost on `_hidden_params.response_cost` and
    the actual provider on `_hidden_params.custom_llm_provider`. The
    adapter MUST extract these BEFORE `model_dump()` strips them, then
    surface them on _geekcubo_meta. Otherwise downstream cost tracking falls
    back to the (much less accurate) catalog calculation for every request.
    """
    from unittest.mock import AsyncMock, MagicMock

    import litellm

    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    class _ResponseModel:
        def __init__(self):
            self.model = "claude-3-5-sonnet-20241022"
            # LiteLLM populates this in `_response_cost_calculator` —
            # value is USD (float).
            self._hidden_params = {
                "response_cost": 0.000_750,
                "custom_llm_provider": "anthropic",
                "litellm_call_id": "test-id",
            }

        def model_dump(self):
            # Pydantic strips _-prefixed attrs by default. This mirrors
            # what real LiteLLM ModelResponse.model_dump() does.
            return {
                "model": self.model,
                "choices": [],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }

    fake_router = MagicMock()

    async def _acompletion(**kwargs):
        return _ResponseModel()

    fake_router.acompletion = AsyncMock(side_effect=_acompletion)
    monkeypatch.setattr(litellm, "Router", lambda **_: fake_router)

    client = GeekCuboLLMClient(
        deployments=[
            ProviderDeployment(
                model_name="claude-3-5-sonnet-20241022",
                litellm_model="anthropic/claude-3-5-sonnet-20241022",
                api_key="sk-test", provider="anthropic",
            )
        ],
        strategy="balanced",
    )
    result = await client.acompletion(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "hi"}],
    )
    meta = result.get("_geekcubo_meta") or {}
    assert meta.get("cost_usd") == 0.000_750, (
        "_hidden_params.response_cost must survive into _geekcubo_meta — "
        "downstream cost calculation reads it from there"
    )
    assert meta.get("provider") == "anthropic", (
        "_hidden_params.custom_llm_provider should win over the "
        "deployment-loop fallback (more reliable on aliased model names)"
    )


async def test_acompletion_geekcubo_meta_cost_none_when_litellm_omits_it(monkeypatch):
    """When the response object has no `_hidden_params` (very old LiteLLM,
    custom upstream wrappers), `cost_usd` must be None on the meta — that's
    the signal for downstream code to fall back to catalog pricing."""
    from unittest.mock import AsyncMock, MagicMock

    import litellm

    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    class _BareResponse:
        model = "gpt-4o-mini"
        # Deliberately no _hidden_params.

        def model_dump(self):
            return {"model": self.model, "choices": [], "usage": {}}

    fake_router = MagicMock()
    fake_router.acompletion = AsyncMock(side_effect=lambda **_: _BareResponse())
    monkeypatch.setattr(litellm, "Router", lambda **_: fake_router)

    client = GeekCuboLLMClient(
        deployments=[
            ProviderDeployment(
                model_name="gpt-4o-mini", litellm_model="openai/gpt-4o-mini",
                api_key="sk-test", provider="openai",
            )
        ],
        strategy="balanced",
    )
    result = await client.acompletion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert result["_geekcubo_meta"]["cost_usd"] is None
    # Provider attribution falls back to deployment-loop lookup.
    assert result["_geekcubo_meta"]["provider"] == "openai"


async def test_acompletion_stream_raises_no_providers_when_router_is_none():
    """No-key configurations short-circuit before LiteLLM gets called.
    Stream requests must hit the same guard as non-stream ones."""
    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import UpstreamProviderError

    # Empty deployments → self._router is None.
    client = GeekCuboLLMClient(deployments=[])
    with pytest.raises(UpstreamProviderError):
        await client.acompletion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )


# ── reasoning effort: per-model params, error mapping, retry ─────────────


def _two_model_client(monkeypatch, side_effect):
    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    deployments = [
        ProviderDeployment(model_name=n, litellm_model=f"openai/{n}",
                           api_key="sk-test", provider="openai")
        for n in ("o3", "gpt-5", "gpt-4o")
    ]
    fake_router = MagicMock()
    fake_router.acompletion = AsyncMock(side_effect=side_effect)
    import litellm
    monkeypatch.setattr(litellm, "Router", lambda **_: fake_router)
    return GeekCuboLLMClient(deployments=deployments, strategy="balanced"), fake_router


def _ok(model):
    resp = MagicMock()
    resp.model_dump.return_value = {"model": model, "choices": [], "usage": {}}
    resp._hidden_params = {}
    return resp


async def test_model_params_merged_per_attempt_and_chain_filtered(monkeypatch):
    import litellm

    async def _side(**kw):
        if kw["model"] == "o3":
            raise litellm.InternalServerError("boom", llm_provider="openai", model="o3")
        return _ok(kw["model"])

    client, router = _two_model_client(monkeypatch, _side)
    await client.acompletion(
        model="o3",
        messages=[{"role": "user", "content": "hi"}],
        fallbacks=[{"o3": ["gpt-4o", "gpt-5"]}],
        model_params={"o3": {"reasoning_effort": "high"},
                      "gpt-5": {"reasoning_effort": "low"}},
    )
    calls = [c.kwargs for c in router.acompletion.await_args_list]
    # gpt-4o is absent from model_params, so it is never attempted.
    assert [c["model"] for c in calls] == ["o3", "gpt-5"]
    assert calls[0]["reasoning_effort"] == "high"
    # The fallback gets its own translation, not the primary's.
    assert calls[1]["reasoning_effort"] == "low"


async def test_no_model_params_keeps_original_chain(monkeypatch):
    client, router = _two_model_client(monkeypatch, lambda **kw: _ok(kw["model"]))
    await client.acompletion(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
    call = router.acompletion.await_args.kwargs
    assert "reasoning_effort" not in call and "model_params" not in call


def test_unsupported_reasoning_maps_to_400_not_503():
    import litellm

    from packages.litellm_adapter.client import _translate_error

    exc = litellm.UnsupportedParamsError(
        message="openai does not support parameters: ['reasoning_effort']",
        llm_provider="openai", model="gpt-4o",
    )
    err = _translate_error(exc)
    assert err.http_status == 400
    assert err.error_type == "unsupported_reasoning_effort"

    other = litellm.UnsupportedParamsError(
        message="does not support parameters: ['logit_bias']",
        llm_provider="openai", model="x",
    )
    assert _translate_error(other).error_type == "unsupported_parameter"


def test_provider_400_naming_reasoning_is_a_compat_error():
    import litellm

    from packages.litellm_adapter.client import _translate_error, is_retryable

    exc = litellm.BadRequestError(
        message="Unsupported parameter: 'reasoning_effort' is not supported with this model.",
        llm_provider="openai", model="gpt-4o",
    )
    err = _translate_error(exc)
    assert (err.http_status, err.error_type) == (400, "unsupported_reasoning_effort")
    # Model-specific refusal: the next candidate may accept it.
    assert is_retryable(exc)


def test_unrelated_bad_request_is_unchanged():
    import litellm

    from packages.litellm_adapter.client import is_retryable

    exc = litellm.BadRequestError(
        message="messages: field required", llm_provider="openai", model="x"
    )
    assert not is_retryable(exc)


def test_local_runtime_refusing_think_is_a_compat_error():
    from packages.litellm_adapter.client import _translate_error

    exc = Exception('"qwen2" does not support thinking')
    exc.geek_local_code = "local_upstream_error"
    exc.geek_local_status = 502
    err = _translate_error(exc)
    assert (err.http_status, err.error_type) == (400, "unsupported_reasoning_effort")
