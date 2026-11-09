"""Token-aware chat history budgeting (no tokenizer dependency)."""
from __future__ import annotations

import pytest

from app.routes.dashboard_chat import (
    ContextBudgetError,
    _trim_history_to_budget,
    estimate_tokens,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _msgs(pairs: int, chars: int = 200):
    out = []
    for _ in range(pairs):
        out.append({"role": "user", "content": "u" * chars})
        out.append({"role": "assistant", "content": "a" * chars})
    return out


async def test_small_history_passes_through_unmodified(monkeypatch):
    monkeypatch.setattr(
        "app.routes.dashboard_chat._context_budget_for", _budget(100_000),
    )
    msgs = _msgs(3)
    w = await _trim_history_to_budget("m", msgs, "sys", 1000, None)
    assert w.messages == msgs
    assert w.omitted_count == 0


async def test_long_history_evicts_oldest_and_counts_omissions(monkeypatch):
    # 4000-token budget minus margin (~3333) minus 512 reserve -> ~2820 tokens
    # for history. Each 200-char message costs ~58 tokens, so ~48 fit of 100.
    monkeypatch.setattr(
        "app.routes.dashboard_chat._context_budget_for", _budget(4000),
    )
    msgs = _msgs(50)
    w = await _trim_history_to_budget("m", msgs, None, 512, None)
    assert w.omitted_count > 0
    assert len(w.messages) < len(msgs)
    assert w.messages == msgs[w.omitted_count:]
    # Window starts on a user turn (no dangling assistant reply).
    assert w.messages[0]["role"] == "user"


async def test_latest_message_too_large_raises(monkeypatch):
    monkeypatch.setattr(
        "app.routes.dashboard_chat._context_budget_for", _budget(2000),
    )
    msgs = [{"role": "user", "content": "x" * 100_000}]
    with pytest.raises(ContextBudgetError):
        await _trim_history_to_budget("m", msgs, None, 512, None)


async def test_system_prompt_is_charged_against_budget(monkeypatch):
    monkeypatch.setattr(
        "app.routes.dashboard_chat._context_budget_for", _budget(4000),
    )
    with pytest.raises(ContextBudgetError):
        await _trim_history_to_budget("m", _msgs(1), "s" * 200_000, 512, None)


async def test_explicit_context_cap_wins(monkeypatch):
    monkeypatch.setattr(
        "app.routes.dashboard_chat._context_budget_for", _budget(1_000_000),
    )
    msgs = _msgs(40)
    w = await _trim_history_to_budget("m", msgs, None, 256, 2000)
    assert w.omitted_count > 0


async def test_unknown_model_uses_fallback_budget():
    msgs = _msgs(2)
    w = await _trim_history_to_budget("totally-unknown-model-xyz", msgs, None, None, None)
    assert w.budget_source == "fallback"
    assert w.omitted_count == 0


async def test_known_builtin_model_uses_its_real_window():
    # Regression: the lookup called model_intelligence.resolve() with the
    # wrong signature, the TypeError was swallowed, and every model got the
    # 16,384-token fallback. A built-in catalog model must report its own
    # window, sourced from the bundled LiteLLM metadata.
    import litellm

    from app.routes.dashboard_chat import (
        DEFAULT_CONTEXT_FALLBACK_TOKENS,
        _context_budget_for,
    )

    expected = litellm.model_cost["gpt-4o"]["max_input_tokens"]
    budget, source = await _context_budget_for("gpt-4o")
    assert source == "model"
    assert budget == expected
    assert budget != DEFAULT_CONTEXT_FALLBACK_TOKENS


async def test_catalog_context_length_wins_over_litellm(monkeypatch):
    import dataclasses

    from app.routes.dashboard_chat import _context_budget_for
    from packages.litellm_adapter import catalog

    entry = catalog.CATALOG_BY_ID["gpt-4o"]
    monkeypatch.setitem(
        catalog.CATALOG_BY_ID, "gpt-4o", dataclasses.replace(entry, context_length=4321),
    )
    assert await _context_budget_for("gpt-4o") == (4321, "model")


async def test_auto_keeps_fallback_budget():
    from app.routes.dashboard_chat import (
        DEFAULT_CONTEXT_FALLBACK_TOKENS,
        _context_budget_for,
    )

    assert await _context_budget_for("auto") == (DEFAULT_CONTEXT_FALLBACK_TOKENS, "fallback")


def test_estimate_tokens_conservative():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("a" * 400) >= 100


def _budget(value):
    async def _inner(model):
        return value, "model"

    return _inner
