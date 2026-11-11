"""Reasoning effort on the wire: real LiteLLM -> a recording mock upstream.

The route and client tests elsewhere replace the LiteLLM call, so they cannot
see what a provider actually receives. These tests run GeekCubo's translation
through real LiteLLM (1.108.1, local cost map) to a local HTTP server that
records each request body, and assert on that body. No credentials, no egress.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import reasoning as r

_OPENAI_OK = {
    "id": "c1", "object": "chat.completion", "created": 1, "model": "m",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}
_ANTHROPIC_OK = {
    "id": "msg_1", "type": "message", "role": "assistant", "model": "m",
    "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}
_GEMINI_OK = {
    "candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]},
                    "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
}


class Upstream:
    """Records request bodies; answers per protocol, or with a scripted error."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.reject: dict[str, tuple[int, dict]] = {}
        self.anthropic_reply: dict | None = None
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                upstream.requests.append({"path": self.path, "body": body})
                model = str(body.get("model") or "")
                if model in upstream.reject:
                    status, payload = upstream.reject[model]
                elif "/messages" in self.path:
                    status, payload = 200, upstream.anthropic_reply or _ANTHROPIC_OK
                elif "generateContent" in self.path:
                    status, payload = 200, _GEMINI_OK
                else:
                    status, payload = 200, {**_OPENAI_OK, "model": model}
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self._srv.server_address[1]}"
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def last(self) -> dict:
        return self.requests[-1]["body"]

    def close(self) -> None:
        self._srv.shutdown()


@pytest.fixture
def upstream():
    u = Upstream()
    yield u
    u.close()


_API_BASE = {"anthropic": "", "gemini": ""}


async def _send(upstream, litellm_model: str, params: dict, **extra) -> dict:
    """One real LiteLLM call to the mock; returns the recorded request body."""
    import litellm

    provider = litellm_model.split("/", 1)[0]
    base = upstream.base + _API_BASE.get(provider, "/v1")
    before = len(upstream.requests)
    await litellm.acompletion(
        model=litellm_model, api_key="sk-mock", api_base=base,
        messages=extra.pop("messages", [{"role": "user", "content": "hi"}]),
        **params, **extra,
    )
    assert len(upstream.requests) == before + 1, "request never reached the upstream"
    return upstream.last()


def _thinking_config(body: dict) -> dict:
    cfg = (body.get("generationConfig") or {}).get("thinkingConfig") or {}
    return {k: v for k, v in cfg.items() if k != "includeThoughts"}


# ── every advertised level reaches the provider as requested ──────────────

# Built-in models whose levels GeekCubo advertises. Each advertised level is
# sent through real LiteLLM, and the recorded body must carry a control that
# expresses exactly that level — never a silent drop, never another level.
_ADVERTISED = [
    ("openai", "o3", "openai/o3"),
    ("openai", "gpt-5", "openai/gpt-5"),
    ("openai", "gpt-5.2", "openai/gpt-5.2"),
    ("anthropic", "claude-sonnet-4-5", "anthropic/claude-sonnet-4-5"),
    ("anthropic", "claude-opus-4-6", "anthropic/claude-opus-4-6"),
    ("google", "gemini-2.5-pro", "gemini/gemini-2.5-pro"),
    ("google", "gemini-2.5-flash", "gemini/gemini-2.5-flash"),
    ("google", "gemini-3-pro-preview", "gemini/gemini-3-pro-preview"),
    ("deepseek", "deepseek-chat", "deepseek/deepseek-chat"),
    ("mistral", "mistral-medium-3", "mistral/mistral-medium-3"),
]


def _wire_control(body: dict):
    """The reasoning control present in a recorded body, normalized."""
    for key in ("reasoning_effort", "output_config", "thinking"):
        if key in body:
            return key, body[key]
    cfg = _thinking_config(body)
    if cfg:
        return "thinkingConfig", cfg
    return None, None


@pytest.mark.parametrize("provider,model_id,litellm_model", _ADVERTISED)
async def test_each_advertised_level_reaches_the_wire_distinctly(
    upstream, provider, model_id, litellm_model,
):
    levels = r.supported_levels(model_id, provider=provider)
    assert levels, f"{model_id} should have confirmed levels"
    seen = {}
    for level in levels:
        params = r.provider_params(
            model_id=model_id, provider=provider, effort=level, max_tokens=32000,
        )
        body = await _send(upstream, litellm_model, params, max_tokens=32000)
        key, value = _wire_control(body)
        if level == "none" and key is None:
            pytest.fail(f"{model_id}: 'none' sent no control at all")
        assert key is not None, f"{model_id}: {level} was dropped before the wire"
        seen[level] = json.dumps([key, value], sort_keys=True)
    # Two advertised levels must never become the same request.
    assert len(set(seen.values())) == len(seen), seen


@pytest.mark.parametrize("level", ["none", "minimal"])
async def test_gemini_3_pro_does_not_offer_levels_it_would_turn_into_low(upstream, level):
    assert level not in r.supported_levels("gemini-3-pro-preview", provider="google")
    with pytest.raises(r.ReasoningError) as exc:
        r.provider_params(model_id="gemini-3-pro-preview", provider="google", effort=level)
    assert exc.value.error_type == "unsupported_reasoning_effort"


async def test_gemini_3_flash_keeps_a_real_minimal_level(upstream):
    params = r.provider_params(model_id="gemini-3-flash-preview", provider="google", effort="minimal")
    body = await _send(upstream, "gemini/gemini-3-flash-preview", params)
    assert _thinking_config(body) == {"thinkingLevel": "minimal"}


async def test_gemini_2_5_pro_cannot_be_switched_off():
    assert "none" not in r.supported_levels("gemini-2.5-pro", provider="google")
    assert "none" in r.supported_levels("gemini-2.5-flash", provider="google")


@pytest.mark.parametrize("level", ["minimal", "xhigh"])
async def test_adaptive_claude_offers_only_levels_litellm_forwards(level):
    # claude-opus-4-6 flags `max` but not `xhigh`; `minimal` is no adaptive effort.
    assert level not in r.supported_levels("claude-opus-4-6", provider="anthropic")


async def test_adaptive_claude_flagged_levels_reach_the_wire(upstream):
    params = r.provider_params(model_id="claude-opus-4-6", provider="anthropic", effort="max")
    body = await _send(upstream, "anthropic/claude-opus-4-6", params, max_tokens=32000)
    assert body["output_config"] == {"effort": "max"}
    assert body["thinking"]["type"] == "adaptive"


async def test_always_on_claude_does_not_claim_it_can_disable_thinking():
    levels = r.supported_levels("claude-fable-5", provider="anthropic")
    assert "none" not in levels and "high" in levels


async def test_magistral_is_unsupported_not_silently_ignored(upstream):
    # LiteLLM accepts the effort and sends nothing for it (only a fixed
    # system prompt) — so GeekCubo must refuse it rather than report it honoured.
    params_low = await _send(upstream, "mistral/magistral-medium-latest", {"reasoning_effort": "low"})
    params_high = await _send(upstream, "mistral/magistral-medium-latest", {"reasoning_effort": "high"})
    assert "reasoning_effort" not in params_low and params_low == params_high
    assert r.supported_levels("magistral-medium-latest", provider="mistral") == ()
    with pytest.raises(r.ReasoningError):
        r.provider_params(model_id="magistral-medium-latest", provider="mistral", effort="high")


async def test_default_request_sends_no_reasoning_control(upstream):
    body = await _send(upstream, "openai/o3", {})
    assert _wire_control(body) == (None, None)


# ── real client: refusals are 4xx, fallback keeps the effort ──────────────


def _client(upstream, *specs):
    """GeekCuboLLMClient over deployments that all point at the mock."""
    from packages.litellm_adapter.client import GeekCuboLLMClient
    from packages.litellm_adapter.types import ProviderDeployment

    deployments = []
    for name, provider, litellm_model in specs:
        base = upstream.base + _API_BASE.get(litellm_model.split("/", 1)[0], "/v1")
        deployments.append(ProviderDeployment(
            model_name=name, litellm_model=litellm_model, api_key="sk-mock",
            provider=provider, api_base=base,
        ))
    return GeekCuboLLMClient(deployments=deployments, strategy="balanced", num_retries=0)


def _openai_refusal(message: str) -> tuple[int, dict]:
    return 400, {"error": {"message": message, "type": "invalid_request_error",
                           "param": "reasoning_effort", "code": "unsupported_value"}}


# Real-world wordings that previously fell through to 503 upstream_error.
_REFUSALS = [
    "Invalid effort value: 'minimal'. Must be one of: 'high', 'medium', 'low'",
    "effort='xhigh' is not supported by this model.",
    "Argument not supported on this model: reasoningEffort",
    "Budget 0 is invalid. This model only works in thinking mode.",
]


@pytest.mark.parametrize("message", _REFUSALS)
async def test_provider_refusal_of_reasoning_is_400_not_503(upstream, message):
    from packages.litellm_adapter.client import UpstreamProviderError

    client = _client(upstream, ("gpt-5.2", "openai", "openai/gpt-5.2"))
    upstream.reject["gpt-5.2"] = _openai_refusal(message)
    with pytest.raises(UpstreamProviderError) as exc:
        await client.acompletion(
            model="gpt-5.2", messages=[{"role": "user", "content": "hi"}],
            model_params={"gpt-5.2": {"reasoning_effort": "xhigh"}},
        )
    assert exc.value.http_status == 400
    assert exc.value.error_type == "unsupported_reasoning_effort"


async def test_unrelated_400_without_reasoning_keeps_its_classification(upstream):
    from packages.litellm_adapter.client import UpstreamProviderError

    client = _client(upstream, ("o3", "openai", "openai/o3"))
    # Same wording, but no reasoning control was sent: not a reasoning refusal.
    upstream.reject["o3"] = _openai_refusal("Budget 0 is invalid for this account.")
    with pytest.raises(UpstreamProviderError) as exc:
        await client.acompletion(model="o3", messages=[{"role": "user", "content": "hi"}])
    assert exc.value.error_type != "unsupported_reasoning_effort"


async def test_refusal_fails_over_with_the_same_effort(upstream):
    client = _client(upstream, ("gpt-5", "openai", "openai/gpt-5"), ("o3", "openai", "openai/o3"))
    upstream.reject["gpt-5"] = _openai_refusal(_REFUSALS[0])
    await client.acompletion(
        model="gpt-5", messages=[{"role": "user", "content": "hi"}],
        fallbacks=[{"gpt-5": ["o3"]}],
        model_params={"gpt-5": {"reasoning_effort": "high"}, "o3": {"reasoning_effort": "high"}},
    )
    sent = [(q["body"]["model"], q["body"].get("reasoning_effort")) for q in upstream.requests]
    assert sent == [("gpt-5", "high"), ("o3", "high")]


# ── Anthropic thinking continuity across a tool call ─────────────────────

_TOOL = [{"type": "function", "function": {
    "name": "read_file", "parameters": {"type": "object", "properties": {"p": {"type": "string"}}}}}]
_SIGNED = [{"type": "thinking", "thinking": "I should read it.", "signature": "SIG-1"},
           {"type": "redacted_thinking", "data": "RED-1"}]


def _tool_loop(thinking_blocks):
    assistant = {"role": "assistant", "content": None, "tool_calls": [{
        "id": "toolu_1", "type": "function",
        "function": {"name": "read_file", "arguments": "{\"p\": \"a.txt\"}"}}]}
    if thinking_blocks is not None:
        assistant["thinking_blocks"] = thinking_blocks
    return [{"role": "user", "content": "read a.txt"}, assistant,
            {"role": "tool", "tool_call_id": "toolu_1", "content": "hello"}]


@pytest.mark.parametrize("model_id", ["claude-sonnet-4-5", "claude-opus-4-6"])
async def test_signed_thinking_blocks_reach_anthropic_first_and_unchanged(upstream, model_id):
    client = _client(upstream, (model_id, "anthropic", f"anthropic/{model_id}"))
    messages = _tool_loop(_SIGNED)
    params = r.provider_params(model_id=model_id, provider="anthropic", effort="high",
                               max_tokens=32000, messages=messages)
    await client.acompletion(model=model_id, messages=messages, tools=_TOOL,
                             max_tokens=32000, model_params={model_id: params})
    body = upstream.last()
    assert body["thinking"]["type"] in ("enabled", "adaptive")
    assistant = [m for m in body["messages"] if m["role"] == "assistant"][-1]
    assert [b["type"] for b in assistant["content"]] == ["thinking", "redacted_thinking", "tool_use"]
    assert assistant["content"][0]["signature"] == "SIG-1"
    assert assistant["content"][1]["data"] == "RED-1"


async def test_tool_loop_without_signed_blocks_is_a_clear_compat_error():
    with pytest.raises(r.ReasoningError) as exc:
        r.provider_params(model_id="claude-sonnet-4-5", provider="anthropic",
                          effort="high", max_tokens=32000, messages=_tool_loop(None))
    assert exc.value.error_type == "unsupported_reasoning_effort"
    assert "signed thinking blocks" in exc.value.message


async def test_disabling_thinking_needs_no_blocks():
    params = r.provider_params(model_id="claude-sonnet-4-5", provider="anthropic",
                               effort="none", messages=_tool_loop(None))
    assert params == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize("name,provider,litellm_model", [
    ("o3", "openai", "openai/o3"),
    ("deepseek-chat", "deepseek", "deepseek/deepseek-chat"),
    ("grok-4", "xai", "xai/grok-4"),
])
async def test_thinking_blocks_never_reach_a_non_anthropic_model(upstream, name, provider, litellm_model):
    client = _client(upstream, (name, provider, litellm_model))
    await client.acompletion(model=name, messages=_tool_loop(_SIGNED), tools=_TOOL)
    blob = json.dumps(upstream.last())
    assert "thinking_blocks" not in blob and "SIG-1" not in blob and "RED-1" not in blob


async def test_thinking_blocks_dropped_for_anthropic_without_thinking(upstream):
    client = _client(upstream, ("claude-sonnet-4-5", "anthropic", "anthropic/claude-sonnet-4-5"))
    await client.acompletion(model="claude-sonnet-4-5", messages=_tool_loop(_SIGNED),
                             tools=_TOOL, max_tokens=1024)
    assert "SIG-1" not in json.dumps(upstream.last())


# ── route level: real app + real client, Auto skips untranslatable models ─


@pytest.fixture
async def wired_app(tmp_sqlite_url, monkeypatch, isolated_env, upstream):
    """The real app whose router is a real GeekCuboLLMClient on the mock."""
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    from app import config as cfg

    cfg.get_settings.cache_clear()
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import auto_planner, router_cache
    from packages.db import session as session_mod
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory
    auto_planner.reset_state()
    from app.seed import seed_initial_state

    async with factory() as s:
        seed = await seed_initial_state(s)
    holder: dict = {}

    async def _get_router(_session):
        return holder["client"]

    monkeypatch.setattr(router_cache, "get_router", _get_router)
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t",
                           headers={"Authorization": f"Bearer {seed.api_key}"}) as c:
        yield c, holder, monkeypatch
    await engine.dispose()
    session_mod._session_factory = None


def _catalog_entry(mid, provider, levels, price):
    from packages.litellm_adapter.catalog import CatalogModel

    return CatalogModel(id=mid, provider=provider, litellm_prefix="openai/",
                        supports_tools=True, supports_vision=False, supports_json_mode=False,
                        input_cost_per_token=price, output_cost_per_token=price,
                        reasoning_levels=levels, price_source="catalog")


async def test_auto_skips_a_top_ranked_model_that_cannot_take_the_budget(wired_app, upstream):
    """Cheapest ranks the legacy-budget Claude first; `high` needs a 4096
    budget that does not fit max_tokens=2000, so Auto must promote o3 and
    send it `high` — not fail the whole request."""
    c, holder, mp = wired_app
    holder["client"] = _client(
        upstream,
        ("claude-sonnet-4-5", "anthropic", "anthropic/claude-sonnet-4-5"),
        ("o3", "openai", "openai/o3"),
    )
    holder["client"].strategy = "cheapest"
    catalog = [
        _catalog_entry("claude-sonnet-4-5", "anthropic",
                       r.supported_levels("claude-sonnet-4-5", provider="anthropic"), 1e-9),
        _catalog_entry("o3", "openai", ("low", "medium", "high"), 1e-6),
    ]

    async def _merged(_db, eligible_only=True):
        return catalog

    import app.custom_providers as custom_mod

    mp.setattr(custom_mod, "merged_catalog", _merged)
    resp = await c.post("/v1/chat/completions", json={
        "model": "auto", "reasoning_effort": "high", "max_tokens": 2000,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200, resp.text
    assert [q["body"]["model"] for q in upstream.requests] == ["o3"]
    assert upstream.last()["reasoning_effort"] == "high"
    assert resp.headers["x-geek-resolved-model"] == "o3"
    assert resp.headers["x-geek-reasoning-effective"] == "high"


async def test_pinned_untranslatable_model_stays_a_strict_400(wired_app, upstream):
    c, holder, _mp = wired_app
    holder["client"] = _client(upstream, ("claude-sonnet-4-5", "anthropic",
                                          "anthropic/claude-sonnet-4-5"))
    resp = await c.post("/v1/chat/completions", json={
        "model": "claude-sonnet-4-5", "reasoning_effort": "high", "max_tokens": 2000,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 400, resp.text
    assert resp.headers["x-geek-error-type"] == "unsupported_reasoning_effort"
    assert upstream.requests == []


async def test_route_provider_refusal_is_400_with_compat_type(wired_app, upstream):
    c, holder, _mp = wired_app
    holder["client"] = _client(upstream, ("gpt-5.2", "openai", "openai/gpt-5.2"))
    upstream.reject["gpt-5.2"] = _openai_refusal(_REFUSALS[1])
    resp = await c.post("/v1/chat/completions", json={
        "model": "gpt-5.2", "reasoning_effort": "xhigh",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 400, resp.text
    assert resp.headers.get("x-geek-error-type") == "unsupported_reasoning_effort"


async def test_anthropic_surface_round_trips_signed_thinking(wired_app, upstream):
    """Claude Code shape end to end: /v1/messages returns the signed block,
    and sending it back on the tool-result turn reaches Anthropic intact."""
    c, holder, _mp = wired_app
    holder["client"] = _client(upstream, ("claude-sonnet-4-5", "anthropic",
                                          "anthropic/claude-sonnet-4-5"))
    upstream.anthropic_reply = {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-4-5",
        "content": [{"type": "thinking", "thinking": "plan", "signature": "SIG-RT"},
                    {"type": "tool_use", "id": "toolu_9", "name": "read_file", "input": {"p": "a"}}],
        "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    tools = [{"name": "read_file", "input_schema": {"type": "object", "properties": {"p": {"type": "string"}}}}]
    base = {"model": "claude-sonnet-4-5", "max_tokens": 32000, "tools": tools,
            "thinking": {"type": "enabled", "budget_tokens": 4096}}
    first = await c.post("/v1/messages", json={**base, "messages": [
        {"role": "user", "content": "read a"}]})
    assert first.status_code == 200, first.text
    content = first.json()["content"]
    assert content[0] == {"type": "thinking", "thinking": "plan", "signature": "SIG-RT"}

    upstream.anthropic_reply = None
    second = await c.post("/v1/messages", json={**base, "messages": [
        {"role": "user", "content": "read a"},
        {"role": "assistant", "content": content},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_9", "content": "hi"}]},
    ]})
    assert second.status_code == 200, second.text
    sent = upstream.last()
    assistant = [m for m in sent["messages"] if m["role"] == "assistant"][-1]
    assert assistant["content"][0] == {"type": "thinking", "thinking": "plan", "signature": "SIG-RT"}
    assert sent["thinking"] == {"type": "enabled", "budget_tokens": 4096}


async def test_anthropic_surface_missing_thinking_is_invalid_request(wired_app, upstream):
    c, holder, _mp = wired_app
    holder["client"] = _client(upstream, ("claude-sonnet-4-5", "anthropic",
                                          "anthropic/claude-sonnet-4-5"))
    resp = await c.post("/v1/messages", json={
        "model": "claude-sonnet-4-5", "max_tokens": 32000,
        "thinking": {"type": "enabled", "budget_tokens": 4096},
        "tools": [{"name": "read_file", "input_schema": {"type": "object"}}],
        "messages": [
            {"role": "user", "content": "read a"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x"}]},
        ],
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["type"] == "invalid_request_error"
    assert upstream.requests == []


# ── streaming: real LiteLLM Anthropic stream -> /v1/messages SSE events ───

_ANTHROPIC_SSE = [
    ("message_start", {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-4-5",
        "content": [], "stop_reason": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}),
    ("content_block_start", {"type": "content_block_start", "index": 0,
                             "content_block": {"type": "thinking", "thinking": ""}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                             "delta": {"type": "thinking_delta", "thinking": "pl"}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                             "delta": {"type": "thinking_delta", "thinking": "an"}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                             "delta": {"type": "signature_delta", "signature": "SIG-S"}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
    ("content_block_start", {"type": "content_block_start", "index": 1,
                             "content_block": {"type": "redacted_thinking", "data": "RED-S"}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 1}),
    ("content_block_start", {"type": "content_block_start", "index": 2, "content_block": {
        "type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {}}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 2,
                             "delta": {"type": "input_json_delta", "partial_json": "{\"p\":\"a\"}"}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 2}),
    ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use"},
                       "usage": {"output_tokens": 5}}),
    ("message_stop", {"type": "message_stop"}),
]


class _SSEUpstream:
    def __init__(self):
        events = _ANTHROPIC_SSE

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("content-length") or 0))
                data = "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self._srv.server_address[1]}"
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()


async def test_streamed_thinking_is_relayed_as_signed_blocks():
    import litellm

    from app.protocols.anthropic import stream_events
    from app.routes.chat import _chunk_to_dict

    up = _SSEUpstream()
    try:
        stream = await litellm.acompletion(
            model="anthropic/claude-sonnet-4-5", api_key="sk-mock", api_base=up.base,
            messages=[{"role": "user", "content": "hi"}], stream=True, max_tokens=8192,
            thinking={"type": "enabled", "budget_tokens": 1024},
        )

        async def frames():
            async for chunk in stream:
                yield _chunk_to_dict(chunk)

        events = []
        async for raw in stream_events(frames()):
            lines = raw.strip().splitlines()
            events.append((lines[0][7:], json.loads(lines[1][6:])))
    finally:
        up._srv.shutdown()

    starts = [d["content_block"] for e, d in events if e == "content_block_start"]
    assert [b["type"] for b in starts] == ["thinking", "redacted_thinking", "tool_use"]
    assert starts[1]["data"] == "RED-S"
    deltas = [d["delta"] for e, d in events if e == "content_block_delta"]
    assert "".join(x.get("thinking", "") for x in deltas if x["type"] == "thinking_delta") == "plan"
    assert [x["signature"] for x in deltas if x["type"] == "signature_delta"] == ["SIG-S"]
    # Every opened block is closed exactly once, in order.
    opened = [d["index"] for e, d in events if e == "content_block_start"]
    closed = [d["index"] for e, d in events if e == "content_block_stop"]
    assert opened == closed == [0, 1, 2]
    # Hidden reasoning never becomes visible assistant text.
    assert not any(x["type"] == "text_delta" for x in deltas)


def test_auto_skips_unreported_local_ollama_model_for_a_graded_level():
    """An Ollama model that reported no `think` levels is Unknown, so the
    planner keeps it, and its zero price ranks it first. It cannot express
    `medium`; Auto must move on to o3 rather than fail the request. Pinned,
    the same model stays a strict 400."""
    from types import SimpleNamespace

    from app.routes.chat import _reasoning_params_by_model
    from packages.litellm_adapter.types import ProviderDeployment

    local_id = "local/m1/qwen3:8b"
    client = SimpleNamespace(_deployments=[
        ProviderDeployment(model_name=local_id, litellm_model="geekcubo_local/x", api_key="local",
                           provider="local", custom_llm_provider="geekcubo_local",
                           operator_priced=True, local_adapter="ollama"),
        ProviderDeployment(model_name="o3", litellm_model="openai/o3", api_key="k", provider="openai"),
    ])
    out = _reasoning_params_by_model(client=client, models=[local_id, "o3"], effort="medium",
                                     max_tokens=None, skip_untranslatable=True)
    assert out == {"o3": {"reasoning_effort": "medium"}}
    with pytest.raises(r.ReasoningError):
        _reasoning_params_by_model(client=client, models=[local_id], effort="medium", max_tokens=None)
    # A level the boolean switch can express still goes to the local model.
    out = _reasoning_params_by_model(client=client, models=[local_id, "o3"], effort="high",
                                     max_tokens=None, skip_untranslatable=True)
    assert out[local_id] == {"think": True}
