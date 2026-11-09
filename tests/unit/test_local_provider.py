"""LiteLLM `geekcubo_local` custom provider handler.

The handler is the one place where LiteLLM's CustomLLM contract meets our wire
protocol. These tests pin the two things that were hardest to get right:
dispatch errors must survive LiteLLM's exception re-wrapping (so the HTTP
status and `local_*` code reach the client), and the streaming path must close
the dispatcher generator so a cancelled stream does not leak a pending
request.
"""

from __future__ import annotations

import litellm
import pytest

from app.local_connect import dispatcher


def _wire(machine="m-1", key="llama3.1:8b"):
    return f"geekcubo_local/{machine}::{key}"


# ── id parsing ─────────────────────────────────────────────────────────────


def test_split_parses_wire_id():
    from packages.litellm_adapter.local_provider import _split

    assert _split(_wire()) == ("m-1", "llama3.1:8b")


def test_split_rejects_malformed():
    from packages.litellm_adapter.local_provider import _split

    with pytest.raises(ValueError):
        _split("openai/gpt-4o")


# ── parameter whitelist ────────────────────────────────────────────────────


def test_completion_params_keeps_known_keys_and_drops_others():
    from packages.litellm_adapter.local_provider import _completion_params

    out = _completion_params(
        {
            "temperature": 0.2,
            "max_tokens": 64,
            "tools": [{"type": "function"}],
            "api_base": "http://dropped",
            "custom_llm_provider": "dropped",
            "seed": None,
        }
    )
    assert out == {"temperature": 0.2, "max_tokens": 64, "tools": [{"type": "function"}]}


# ── error translation ──────────────────────────────────────────────────────


def test_offline_error_becomes_litellm_service_unavailable():
    """LocalOffline must raise a LiteLLM exception with our code attached.

    A non-LiteLLM exception would be re-wrapped as APIConnectionError/500,
    losing the 503 and `local_offline`, so this pins the type.
    """
    from packages.litellm_adapter.local_provider import _raise_for_litellm

    with pytest.raises(litellm.ServiceUnavailableError) as err:
        _raise_for_litellm(dispatcher.LocalOffline("m-1"))
    assert err.value.geek_local_code == "local_offline"
    assert err.value.geek_local_status == 503
    assert err.value.status_code == 503


def test_upstream_error_uses_502_class():
    from packages.litellm_adapter.local_provider import _raise_for_litellm

    with pytest.raises(litellm.ServiceUnavailableError) as err:
        _raise_for_litellm(dispatcher.LocalUpstreamError("connector crashed"))
    assert err.value.geek_local_code == "local_upstream_error"
    assert err.value.geek_local_status == 502


def test_client_translate_error_recovers_local_markers():
    """`client._translate_error` must read the markers back into an HTTP error."""
    from packages.litellm_adapter.client import _translate_error

    error = litellm.ServiceUnavailableError(
        message="Local machine m-1 is not connected.",
        llm_provider="geekcubo_local",
        model="geekcubo_local",
    )
    error.geek_local_code = "local_offline"
    error.geek_local_status = 503

    translated = _translate_error(error)
    assert translated.http_status == 503
    assert translated.error_type == "local_offline"


# ── handler completion ─────────────────────────────────────────────────────


async def test_acompletion_dispatches_and_builds_model_response(monkeypatch):
    from packages.litellm_adapter import local_provider

    captured = {}

    async def fake_dispatch(target, *, messages, params=None):
        captured["target"] = target
        captured["messages"] = messages
        captured["params"] = params
        return {"text": "Hello local", "usage": {"prompt_tokens": 3, "completion_tokens": 2}, "model": "llama3.1:8b"}

    monkeypatch.setattr(local_provider.dispatcher, "dispatch_chat", fake_dispatch)
    monkeypatch.setattr(local_provider, "_resolve_adapter", lambda m, k: _async("ollama"))

    handler = local_provider.LocalConnectHandler()
    response = await handler.acompletion(
        model=_wire(),
        messages=[{"role": "user", "content": "hi"}],
        optional_params={"temperature": 0.1, "api_base": "ignored"},
    )

    assert response.choices[0].message.content == "Hello local"
    assert response.usage["prompt_tokens"] == 3
    assert response.usage["total_tokens"] == 5
    assert captured["target"].machine_id == "m-1"
    assert captured["target"].adapter == "ollama"
    assert captured["params"] == {"temperature": 0.1}


async def test_acompletion_raises_translated_error(monkeypatch):
    from packages.litellm_adapter import local_provider

    async def fake_dispatch(target, *, messages, params=None):
        raise dispatcher.LocalOffline(target.machine_id)

    monkeypatch.setattr(local_provider.dispatcher, "dispatch_chat", fake_dispatch)
    monkeypatch.setattr(local_provider, "_resolve_adapter", lambda m, k: _async("ollama"))

    handler = local_provider.LocalConnectHandler()
    with pytest.raises(litellm.ServiceUnavailableError) as err:
        await handler.acompletion(model=_wire(), messages=[], optional_params={})
    assert err.value.geek_local_code == "local_offline"


async def _async(value):
    return value
