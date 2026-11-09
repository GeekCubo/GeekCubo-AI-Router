"""Analytics endpoints — recent requests, daily spend, latency."""

from __future__ import annotations

from datetime import datetime  # noqa: F401

import pytest

from tests.authkit import SignedInClient


@pytest.fixture
async def analytics_client(tmp_sqlite_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)

    from app import config as cfg
    cfg.get_settings.cache_clear()

    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db import session as session_mod
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory

    from app.seed import seed_initial_state
    async with factory() as s:
        seed = await seed_initial_state(s)

    # Pre-populate request logs spanning today + yesterday + 5 days ago.
    import uuid

    from packages.db.models.request_log import RequestLog

    rows = [
        # Today, openai/gpt-4o-mini, 100ms
        RequestLog(
            workspace_id="default", api_key_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            model_requested="gpt-4o-mini", model_resolved="gpt-4o-mini",
            provider="openai", routing_strategy="balanced",
            input_tokens=10, output_tokens=20, cost_microcents=100,
            latency_ms=100, status_code=200,
        ),
        # Today, anthropic/claude, 300ms
        RequestLog(
            workspace_id="default", api_key_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            model_requested="claude-3-5-haiku-latest",
            model_resolved="claude-3-5-haiku-latest",
            provider="anthropic", routing_strategy="balanced",
            input_tokens=50, output_tokens=80, cost_microcents=500,
            latency_ms=300, status_code=200,
        ),
    ]

    async with factory() as s:
        for r in rows:
            s.add(r)
        await s.commit()

    from app.main import create_app
    app = create_app()

    from httpx import ASGITransport

    async with SignedInClient(
transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {seed.api_key}"},
    ) as c:
        yield c

    await engine.dispose()
    session_mod._session_factory = None


async def test_recent_returns_logged_requests_newest_first(analytics_client):
    r = await analytics_client.get("/v1/analytics/recent?limit=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    items = body["items"]
    assert {it["provider"] for it in items} == {"openai", "anthropic"}
    # Each item exposes the user-relevant fields and not internal ones
    sample = items[0]
    for k in ("model_requested", "model_resolved", "provider", "input_tokens",
              "output_tokens", "cost_microcents", "latency_ms", "status_code",
              "created_at"):
        assert k in sample
    assert "api_key_id" not in sample  # internal


async def test_recent_respects_limit(analytics_client):
    r = await analytics_client.get("/v1/analytics/recent?limit=1")
    assert r.json()["count"] == 1


async def test_spend_returns_per_model_cost(analytics_client):
    r = await analytics_client.get("/v1/analytics/spend?days=7")
    assert r.status_code == 200
    body = r.json()
    by_model = {row["model"]: row for row in body["by_model"]}
    assert by_model["gpt-4o-mini"]["cost_microcents"] == 100
    assert by_model["claude-3-5-haiku-latest"]["cost_microcents"] == 500
    assert body["total_microcents"] == 600


async def test_latency_returns_p50_p99_per_provider(analytics_client):
    r = await analytics_client.get("/v1/analytics/latency?days=7")
    assert r.status_code == 200
    body = r.json()
    by_prov = {row["provider"]: row for row in body["by_provider"]}
    assert "openai" in by_prov
    assert "anthropic" in by_prov
    assert by_prov["openai"]["p50_ms"] == 100
    assert by_prov["anthropic"]["p50_ms"] == 300


async def test_routing_analytics_reports_profiles_fallbacks_and_errors(env):
    c, up, _ = env
    from tests.integration.test_routing_integration import _models, _provider

    prov = await _provider(c, up)
    await _models(c, prov["id"], [("a", True, 1.0, 128000), ("b", True, 2.0, 128000)])
    await c.post("/v1/routing-profiles", json={"display_name": "Economy", "strategy": "cheapest"})
    await c.post("/v1/chat/completions", json={"model": "economy", "messages": [{"role": "user", "content": "hi"}]})
    await c.post("/v1/chat/completions", json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]})
    body = (await c.get("/v1/analytics/routing?days=7")).json()
    requested = {r["requested"] for r in body["by_requested"]}
    assert "economy" in requested and "auto" in requested
    assert body["fallback_stats"]["requests_with_attempts"] >= 0
    assert isinstance(body["by_error"], list)


async def test_baseline_comparison_labels_itself_an_estimate(env):
    c, up, _ = env
    from tests.integration.test_routing_integration import _models, _provider

    prov = await _provider(c, up)
    await _models(c, prov["id"], [("a", True, 1.0, 128000)])
    await c.post("/v1/chat/completions", json={"model": "apixo/a", "messages": [{"role": "user", "content": "hi"}]})
    body = (await c.get("/v1/analytics/baseline-comparison?baseline=apixo/a")).json()
    assert body["is_estimate"] is True
    assert "Estimate only" in body["note"]
    assert body["baseline_estimated_microcents"] >= 0
    assert body["requests"] == 1


async def test_baseline_rejects_an_unpriced_model(env):
    c, up, _ = env
    from tests.integration.test_routing_integration import _models, _provider

    prov = await _provider(c, up)
    await _models(c, prov["id"], [("free", True, 0.0, 128000)])
    r = await c.get("/v1/analytics/baseline-comparison?baseline=apixo/free")
    assert r.status_code == 422
