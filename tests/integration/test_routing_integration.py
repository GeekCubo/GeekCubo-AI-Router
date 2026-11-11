"""End-to-end routing: chat handler + routing API + aliases + diagnostics.

Uses the real app, a real SQLite file, and a local mock OpenAI-compatible
upstream. Real provider keys are stripped (`isolated_env`).
"""

from __future__ import annotations

import pytest

from tests.authkit import dual_client
from tests.integration.test_custom_providers import _MockUpstream

TOOLS = [{"type": "function", "function": {"name": "f",
          "parameters": {"type": "object", "properties": {}}}}]


@pytest.fixture
def upstream():
    u = _MockUpstream()
    u.start()
    try:
        yield u
    finally:
        u.stop()


@pytest.fixture
async def env(tmp_sqlite_url, monkeypatch, isolated_env, upstream):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    monkeypatch.setenv("CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS", f"127.0.0.1:{upstream.port}")
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import auto_planner, router_cache
    from app.custom_providers import invalidate
    from packages.db import session as session_mod
    from packages.db.engine import build_engine
    from packages.db.migrate import ensure_routing_columns
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_routing_columns(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory
    router_cache.invalidate_router()
    invalidate()
    auto_planner.reset_state()

    from app.seed import seed_initial_state

    async with factory() as s:
        seed = await seed_initial_state(s)

    from app.main import create_app

    c = await dual_client(create_app(), factory, seed.api_key)
    try:
        yield c, upstream, factory
    finally:
        await c.aclose()
        router_cache.invalidate_router()
        invalidate()
        auto_planner.reset_state()
    await engine.dispose()
    session_mod._session_factory = None


async def _provider(c, upstream, name="APIXO", *, auto=True):
    r = await c.post("/v1/custom-providers", json={
        "display_name": name, "base_url": upstream.base_url,
        "api_key": "sk-test-key-0000000000", "eligible_for_auto": auto,
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _models(c, pid, specs):
    r = await c.put(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": mid, "display_name": mid, "context_length": ctx,
         "supports_tools": tools, "input_cost_per_million": price,
         "output_cost_per_million": price}
        for mid, tools, price, ctx in specs
    ])
    assert r.status_code == 200, r.text


async def _auto(c, *, tools=True, headers=None):
    payload = {"model": "auto", "messages": [{"role": "user", "content": "hi"}]}
    if tools:
        payload["tools"] = TOOLS
    return await c.post("/v1/chat/completions", json=payload, headers=headers or {})


# ── default policy == previous behaviour ──────────────────────────────────


async def test_default_policy_routes_like_before(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    r = await _auto(c)
    assert r.status_code == 200, r.text
    assert up.requests[0]["body"]["model"] == "gpt-4o"
    assert r.headers["x-geek-routing-strategy"] == "balanced"
    assert r.headers["x-geek-routing-candidates"] == "1"


async def test_routing_get_exposes_policy_and_strategies(env):
    c, _up, _ = env
    r = await c.get("/v1/routing")
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "balanced"
    assert body["policy"]["fallback"]["max_attempts"] == 5
    ids = {s["id"] for s in body["strategies"]}
    assert {"balanced", "cheapest", "quality", "adaptive", "adaptive_gated"} <= ids


async def test_routing_policy_persists_and_rejects_unknown_models(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None), ("cheap-m", True, 0.1, None)])

    bad = await c.put("/v1/routing", json={"policy": {"pools": {"hard": ["no/such-model"]}}})
    assert bad.status_code == 422
    assert "no/such-model" in bad.text

    ok = await c.put("/v1/routing", json={
        "strategy": "adaptive_gated",
        "policy": {"pools": {"mundane": ["apixo/cheap-m"], "hard": ["apixo/gpt-4o"]}},
    })
    assert ok.status_code == 200, ok.text
    again = (await c.get("/v1/routing")).json()
    assert again["strategy"] == "adaptive_gated"
    assert again["policy"]["pools"]["hard"] == ["apixo/gpt-4o"]


async def test_adaptive_gated_routes_tools_to_the_hard_pool(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 5.0, None), ("cheap-m", True, 0.1, None)])
    await c.put("/v1/routing", json={
        "strategy": "adaptive_gated",
        "policy": {"pools": {"mundane": ["apixo/cheap-m"], "hard": ["apixo/gpt-4o"]}},
    })

    hard = await _auto(c, tools=True)
    assert hard.status_code == 200, hard.text
    assert hard.headers["x-geek-routing-tier"] == "hard"
    assert up.requests[-1]["body"]["model"] == "gpt-4o"

    mundane = await _auto(c, tools=False)
    assert mundane.status_code == 200, mundane.text
    assert mundane.headers["x-geek-routing-tier"] == "mundane"
    assert up.requests[-1]["body"]["model"] == "cheap-m"


async def test_pool_mismatch_is_reported_as_such(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("weak", False, 1.0, None), ("gpt-4o", True, 1.0, None)])
    await c.put("/v1/routing", json={
        "strategy": "adaptive_gated",
        "policy": {"pools": {"mundane": ["apixo/weak"], "hard": ["apixo/weak"]},
                   "gated": {"allow_mundane_fallback": False}},
    })
    r = await _auto(c, tools=True)
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "pool_mismatch"


async def test_decision_is_recorded_on_the_request_log(env):
    c, up, factory = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    assert (await _auto(c)).status_code == 200

    from sqlalchemy import select

    from packages.db.models.request_log import RequestLog

    async with factory() as s:
        row = (await s.execute(select(RequestLog).order_by(RequestLog.created_at.desc()))).scalars().first()
    assert row.model_requested == "auto"
    assert row.routed_model == "apixo/gpt-4o"
    assert row.candidate_count == 1
    assert row.escalated is False
    assert row.fallback_used is False


async def test_pinned_requests_carry_no_routing_record(env):
    c, up, factory = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    r = await c.post("/v1/chat/completions", json={
        "model": "apixo/gpt-4o", "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200
    # A pinned request makes no routing decision, so the plan headers that
    # describe one must be absent. `x-geek-routing-strategy` is always present
    # (it reports the configured strategy), so it is not the signal here.
    assert "x-geek-routing-profile" not in r.headers
    assert "x-geek-routing-candidates" not in r.headers

    from sqlalchemy import select

    from packages.db.models.request_log import RequestLog

    async with factory() as s:
        row = (await s.execute(select(RequestLog))).scalars().first()
    assert row.routed_model is None
    assert row.routing_tier is None


# ── diagnostics ───────────────────────────────────────────────────────────


async def test_no_providers_configured(env):
    c, _up, _ = env
    r = await _auto(c)
    assert r.status_code == 422
    assert "x-geek-routing-diagnosis" in r.headers or "No deployable provider" in r.text


async def test_pinned_only_provider_is_diagnosed(env):
    c, up, _ = env
    prov = await _provider(c, up, auto=False)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    r = await _auto(c)
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "no_auto_eligible_providers"
    assert r.json()["error"]["code"] == "no_auto_eligible_providers"
    assert "Enable Auto" in r.text


async def test_native_anthropic_surface_still_maps_the_legacy_error_type(env):
    """The Anthropic adapter maps on x-geek-error-type internally; the new
    categories must keep it on `no_capable_provider` (-> 403 permission_error)."""
    c, up, _ = env
    prov = await _provider(c, up, auto=False)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    r = await c.post("/v1/messages", json={
        "model": "auto", "max_tokens": 16,
        "messages": [{"role": "user", "content": "hi"}],
    }, headers={"anthropic-version": "2023-06-01"})
    assert r.status_code == 403, r.text
    assert r.json()["error"]["type"] == "permission_error"


async def test_capability_mismatch_is_diagnosed(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("plain", False, 1.0, None)])
    r = await _auto(c, tools=True)
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "capability_mismatch"


async def test_unpriced_models_are_diagnosed(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("free", True, 0.0, None)])
    r = await _auto(c)
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "no_registered_models"
    assert "pricing" in r.text


async def test_context_mismatch_is_diagnosed(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("tiny", True, 1.0, 50)])
    r = await c.post("/v1/chat/completions", json={
        "model": "auto",
        "messages": [{"role": "user", "content": "x" * 4000}],
        "tools": TOOLS,
    })
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "context_mismatch"


async def test_diagnosis_never_leaks_the_provider_key(env):
    c, up, _ = env
    prov = await _provider(c, up, auto=False)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    r = await _auto(c)
    assert "sk-test-key-0000000000" not in r.text


async def test_explain_dry_run_reports_stages_without_calling_upstream(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None), ("plain", False, 0.5, None)])
    r = await c.get("/api/routing/explain", params={"tools": "true"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["selected"] == "apixo/gpt-4o"
    stages = {s["stage"]: s["count"] for s in body["stages"]}
    assert stages["auto_eligible_and_deployable"] == 2
    assert stages["capable"] == 1
    assert not up.requests  # dry-run


async def test_explain_requires_admin_session(env):
    c, _up, _ = env
    from httpx import ASGITransport, AsyncClient

    app = c._transport.app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t",
                           headers={"Authorization": c.headers["Authorization"]}) as k:
        assert (await k.get("/api/routing/explain")).status_code == 401


async def test_routing_models_inventory_is_paginated(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(f"m{i}", True, 1.0, None) for i in range(12)])
    r = await c.get("/api/routing/models", params={"scope": "custom", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 12
    assert len(body["models"]) == 5
    first = body["models"][0]
    assert {"id", "provider", "tools", "context_length", "input_per_million",
            "availability", "pools"} <= set(first)
    assert first["availability"] == "auto"
    filtered = await c.get("/api/routing/models", params={"scope": "custom", "q": "m1"})
    assert {m["id"] for m in filtered.json()["models"]} == {"apixo/m1", "apixo/m10", "apixo/m11"}


async def test_unpriced_model_shows_unknown_not_zero(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("free", True, 0.0, None)])
    r = await c.get("/api/routing/models", params={"scope": "custom"})
    m = r.json()["models"][0]
    assert m["input_per_million"] is None
    assert m["availability"] == "unpriced"


# ── aliases ───────────────────────────────────────────────────────────────


async def test_unambiguous_short_alias_resolves(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("geek-only-9", True, 1.0, None)])
    r = await c.post("/v1/chat/completions", json={
        "model": "geek-only-9", "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200, r.text
    assert up.requests[0]["body"]["model"] == "geek-only-9"


async def test_ambiguous_short_alias_is_rejected_with_choices(env):
    c, up, _ = env
    a = await _provider(c, up, "APIXO")
    b = await _provider(c, up, "Other AI")
    await _models(c, a["id"], [("twin-9", True, 1.0, None)])
    await _models(c, b["id"], [("twin-9", True, 1.0, None)])
    r = await c.post("/v1/chat/completions", json={
        "model": "twin-9", "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 409
    assert "apixo/twin-9" in r.text and "other-ai/twin-9" in r.text
    assert not up.requests


async def test_canonical_id_still_works_when_alias_is_ambiguous(env):
    c, up, _ = env
    a = await _provider(c, up, "APIXO")
    b = await _provider(c, up, "Other AI")
    await _models(c, a["id"], [("twin-9", True, 1.0, None)])
    await _models(c, b["id"], [("twin-9", True, 1.0, None)])
    r = await c.post("/v1/chat/completions", json={
        "model": "other-ai/twin-9", "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200, r.text


async def test_alias_does_not_bypass_the_key_allowlist(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("secret-9", True, 1.0, None), ("open-9", True, 1.0, None)])
    key = (await c.post("/v1/keys", json={
        "name": "limited", "model_allowlist": ["apixo/open-9"],
    })).json()["api_key"]

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=c._transport.app), base_url="http://t",
                           headers={"Authorization": f"Bearer {key}"}) as k:
        r = await k.post("/v1/chat/completions", json={
            "model": "secret-9", "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 403
    assert not up.requests


# ── analytics ─────────────────────────────────────────────────────────────


async def test_routing_analytics_counts_recorded_decisions(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None)])
    for _ in range(3):
        assert (await _auto(c)).status_code == 200
    await c.post("/v1/chat/completions", json={
        "model": "apixo/gpt-4o", "messages": [{"role": "user", "content": "x"}],
    })

    r = await c.get("/v1/analytics/routing", params={"days": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requests"] == 4
    assert body["auto_requests"] == 3
    assert {s["strategy"] for s in body["by_strategy"]} == {"balanced"}
    assert any(m["model"] == "apixo/gpt-4o" for m in body["by_model"])
    assert body["timeline"] and body["timeline"][-1]["auto"] == 3


async def test_recent_flags_unknown_cost_instead_of_zero(env):
    c, up, factory = env
    from packages.db.models.request_log import RequestLog

    async with factory() as s:
        s.add(RequestLog(
            workspace_id="default", api_key_id="k", trace_id="t-unknown",
            model_requested="apixo/mystery", model_resolved="mystery",
            provider="apixo", routing_strategy="balanced",
            input_tokens=100, output_tokens=50, cost_microcents=0,
            latency_ms=10, status_code=200,
        ))
        await s.commit()
    recent = (await c.get("/v1/analytics/recent")).json()["items"]
    row = next(i for i in recent if i["trace_id"] == "t-unknown")
    assert row["cost_unknown"] is True
    routing = (await c.get("/v1/analytics/routing")).json()
    assert routing["unknown_cost_requests"] == 1


async def test_routing_analytics_requires_admin(env):
    c, _up, _ = env
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=c._transport.app), base_url="http://t",
                           headers={"Authorization": c.headers["Authorization"]}) as k:
        assert (await k.get("/v1/analytics/routing")).status_code == 401


async def test_explain_simulator_candidates_and_unknown_profile(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, None), ("plain", False, 0.5, None)])
    r = await c.get("/api/routing/explain",
                    params={"tools": "true", "input_tokens": 500, "session_id": "sim-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    by_id = {cand["model"]: cand for cand in body["candidates"]}
    assert by_id["apixo/gpt-4o"]["selected"] is True
    assert any("capability" in reason for reason in by_id["apixo/plain"]["reasons"])
    assert not up.requests

    r = await c.get("/api/routing/explain", params={"profile": "does-not-exist"})
    assert r.status_code == 404


async def test_routing_models_publishes_reasoning_levels(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("plain-model", True, 1.0, None)])
    body = (await c.get("/api/routing/models", params={"scope": "custom"})).json()
    # A custom model with no evidence is Unknown (null), never "unsupported".
    assert body["models"][0]["reasoning_levels"] is None
    assert body["auto_reasoning_levels"] == []
    # ...but Auto still tries any level on it, so the UI must be told.
    assert body["auto_reasoning_unknown"] is True


def test_auto_reasoning_levels_union_in_canonical_order():
    from types import SimpleNamespace

    from app.routes.console import _auto_reasoning_levels

    pool = [
        SimpleNamespace(reasoning_levels=("high", "low")),
        SimpleNamespace(reasoning_levels=None),
        SimpleNamespace(reasoning_levels=("none", "xhigh")),
        SimpleNamespace(reasoning_levels=()),
    ]
    assert _auto_reasoning_levels(pool) == ["none", "low", "high", "xhigh"]
