"""Auto-routing acceptance through the real app.

Real routes, real SQLite, a local mock OpenAI-compatible upstream; no real
provider is contacted. Covers the defects found in the routing acceptance
audit and the selection path from `model="auto"` to the upstream request.
"""

from __future__ import annotations

import pytest

from tests.integration.test_custom_providers import _catalog_entry, _seed_catalog


def _last_model(up) -> str:
    """Model id of the most recent chat completion sent upstream."""
    return [r for r in up.requests if r["body"]][-1]["body"]["model"]
from tests.integration.test_routing_integration import _auto, _models, _provider

# ── persisted policy ───────────────────────────────────────────────────────


async def test_reference_estimate_toggle_is_persisted(env):
    """Regression: the dashboard sent `allow_estimates`, which the policy
    normaliser drops, so the checkbox never changed routing."""
    c, _up, _ = env
    r = await c.put("/v1/routing", json={"policy": {"pricing": {"allow_reference_estimates": True}}})
    assert r.status_code == 200, r.text
    assert r.json()["policy"]["pricing"]["allow_reference_estimates"] is True
    again = await c.get("/v1/routing")
    assert again.json()["policy"]["pricing"]["allow_reference_estimates"] is True


async def test_stale_pool_entry_no_longer_blocks_saving_the_policy(env, tmp_sqlite_url):
    """Regression: a pool entry whose model was removed (or whose provider was
    re-created under a new slug) made EVERY later policy save fail with 422,
    including the save that removes it."""
    c, up, factory = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("live", True, 1.0, None)])
    ok = await c.put("/v1/routing", json={"policy": {"pools": {"mundane": ["apixo/live"]}}})
    assert ok.status_code == 200, ok.text

    # Simulate the owner's state: the stored policy references models that
    # are no longer registered.
    from sqlalchemy import select

    from packages.db.models.routing_config import RoutingConfig

    async with factory() as s:
        row = (await s.execute(select(RoutingConfig))).scalar_one()
        policy = dict(row.policy)
        policy["pools"] = {"mundane": ["apixo/live", "gone/old-model"], "hard": ["gone/other"], "fallback": []}
        row.policy = policy
        await s.commit()

    got = (await c.get("/v1/routing")).json()
    assert got["stale_models"] == ["gone/old-model", "gone/other"]
    assert any("no longer registered" in w for w in got["warnings"])

    # Changing an unrelated field keeps working.
    r = await c.put("/v1/routing", json={"policy": {**got["policy"], "fallback": {"max_attempts": 3}}})
    assert r.status_code == 200, r.text
    # Removing the stale chip works and clears the warning.
    cleaned = {**got["policy"], "pools": {"mundane": ["apixo/live"], "hard": [], "fallback": []}}
    r = await c.put("/v1/routing", json={"policy": cleaned})
    assert r.status_code == 200, r.text
    assert r.json()["stale_models"] == []

    # A NEW unknown id is still rejected.
    bad = await c.put("/v1/routing", json={"policy": {"pools": {"hard": ["no/such-model"]}}})
    assert bad.status_code == 422
    assert "no/such-model" in bad.text


async def test_strategy_change_persists_and_applies_to_the_next_request(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("cheap", True, 0.1, None), ("pricey", True, 9.0, None)])

    await c.put("/v1/routing", json={"strategy": "cheapest"})
    r = await _auto(c)
    assert r.status_code == 200, r.text
    assert _last_model(up) == "cheap"
    assert r.headers["x-geek-routing-strategy"] == "cheapest"

    # Quality First with no scores: price proxy, most expensive first.
    await c.put("/v1/routing", json={"strategy": "quality"})
    assert (await c.get("/v1/routing")).json()["strategy"] == "quality"
    r = await _auto(c)
    assert r.status_code == 200, r.text
    assert _last_model(up) == "pricey"


# ── Cheapest uses effective (override) prices ─────────────────────────────


async def test_cheapest_uses_administrator_price_over_reference(env):
    """Mirrors the owner's DeepSeek model: the catalog reference says $0.30 /
    $1.20, the administrator's confirmed rate is $0.20 / $0.20. Cheapest must
    compare the confirmed rate; the reference never becomes a billing price."""
    c, up, _ = env
    await _seed_catalog({
        "vendor/ds-flash": _catalog_entry(inp=0.3, outp=1.2, context=1_048_576),
        "vendor/other": _catalog_entry(inp=0.25, outp=0.5),
    })
    prov = await _provider(c, up)
    r = await c.put(f"/v1/custom-providers/{prov['id']}/models", json=[
        {"model_id": "ds-flash", "input_cost_per_million": 0.2, "output_cost_per_million": 0.2},
        {"model_id": "other", "input_cost_per_million": 0.25, "output_cost_per_million": 0.5},
    ])
    assert r.status_code == 200, r.text
    models = {m["model_id"]: m for m in r.json()["models"]}
    assert models["ds-flash"]["reference_input_cost_per_million"] == pytest.approx(0.3)
    assert models["ds-flash"]["input_cost_per_million"] == pytest.approx(0.2)

    inv = (await c.get("/api/routing/models?scope=custom")).json()["models"]
    row = next(m for m in inv if m["id"] == "apixo/ds-flash")
    assert (row["input_per_million"], row["output_per_million"]) == (pytest.approx(0.2), pytest.approx(0.2))
    assert row["price_source"] == "custom" and row["availability"] == "auto"

    await c.put("/v1/routing", json={"strategy": "cheapest"})
    r = await _auto(c, tools=False)
    assert r.status_code == 200, r.text
    assert _last_model(up) == "ds-flash"


async def test_model_with_reference_price_only_is_not_auto_eligible(env):
    c, up, _ = env
    await _seed_catalog({"vendor/refonly": _catalog_entry(inp=0.01, outp=0.01)})
    prov = await _provider(c, up)
    r = await c.post(f"/v1/custom-providers/{prov['id']}/models", json=[{"model_id": "refonly"}])
    assert r.status_code == 200, r.text
    inv = (await c.get("/api/routing/models?scope=custom")).json()["models"]
    assert next(m for m in inv if m["id"] == "apixo/refonly")["availability"] == "estimate_only"
    r = await _auto(c, tools=False)
    assert r.status_code == 422
    assert r.headers.get("x-geek-routing-diagnosis") == "no_registered_models"


# ── discovery: provider-reported limits, catalog identity ─────────────────


async def test_discovery_reports_and_registration_stores_provider_limits(env):
    c, up, _ = env
    up.models_payload = {"object": "list", "data": [
        {"id": "big", "object": "model", "owned_by": "apixo", "display_name": "Big",
         "context_window": 1_000_000, "max_output_tokens": 65_536},
        {"id": "plain", "object": "model"},
        {"id": "weird", "context_window": "lots", "max_output_tokens": -1},
    ]}
    prov = await _provider(c, up)
    pid = prov["id"]
    fetched = (await c.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})).json()
    by_id = {m["id"]: m for m in fetched["models"]}
    assert by_id["big"]["context_window"] == 1_000_000
    assert by_id["big"]["max_output_tokens"] == 65_536
    assert "context_window" not in by_id["plain"]
    assert "context_window" not in by_id["weird"] and "max_output_tokens" not in by_id["weird"]
    assert by_id["big"]["preview"]["fields"]["context"] == 1_000_000

    r = await c.post(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": "big"}, {"model_id": "plain"},
    ])
    assert r.status_code == 200, r.text
    models = {m["model_id"]: m for m in r.json()["provider"]["models"]}
    assert models["big"]["context_length"] == 1_000_000
    assert models["big"]["max_output_tokens"] == 65_536
    assert models["big"]["metadata"]["context"]["source"] == "provider_models_endpoint"
    # No report and no catalog: stays unknown, never invented.
    assert models["plain"]["context_length"] is None
    assert models["plain"]["max_output_tokens"] is None
    # Provider limits never imply capabilities or prices.
    assert models["big"]["capabilities"]["tools"] == "unknown"
    assert models["big"]["price_state"] == "unknown"


async def test_administrator_context_beats_provider_report_and_survives_refresh(env):
    c, up, _ = env
    up.models_payload = {"object": "list", "data": [{"id": "big", "context_window": 1_000_000}]}
    prov = await _provider(c, up)
    pid = prov["id"]
    await c.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    r = await c.post(f"/v1/custom-providers/{pid}/models", json=[{"model_id": "big"}])
    row_id = r.json()["provider"]["models"][0]["id"]

    r = await c.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={"context_length": 200_000})
    assert r.json()["context_length"] == 200_000

    up.models_payload = {"object": "list", "data": [{"id": "big", "context_window": 2_000_000}]}
    await c.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    model = (await c.get("/v1/custom-providers")).json()["providers"][0]["models"][0]
    assert model["context_length"] == 200_000
    assert model["metadata"]["context"]["source"] == "administrator"

    # Clearing the override falls back to the provider's latest report.
    r = await c.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={"clear_context": True})
    assert r.json()["context_length"] == 2_000_000


async def test_ambiguous_candidates_put_the_vendor_first_and_are_never_auto_picked(env):
    c, up, _ = env
    resellers = {f"reseller{i:02d}/glm-9": _catalog_entry() for i in range(40)}
    await _seed_catalog({**resellers, "zai/glm-9": _catalog_entry(context=999)})
    up.models_payload = {"object": "list", "data": [{"id": "glm-9"}]}
    prov = await _provider(c, up)
    fetched = (await c.post(f"/v1/custom-providers/{prov['id']}/fetch-models", json={"force": True})).json()
    preview = fetched["models"][0]["preview"]
    assert preview["status"] == "ambiguous"
    assert preview["catalog_key"] is None
    assert preview["candidate_total"] == 41
    assert preview["candidates"][0] == "zai/glm-9"   # previously cut off alphabetically
    assert len(preview["candidates"]) == 25


async def test_abliterated_variant_does_not_inherit_the_base_model(env):
    c, up, _ = env
    await _seed_catalog({"deepseek/ds-v9-flash": _catalog_entry(inp=0.1, outp=0.2)})
    up.models_payload = {"object": "list", "data": [
        {"id": "ds-v9-flash-abliterated"}, {"id": "ds-v9-flash-uncensored"},
    ]}
    prov = await _provider(c, up)
    fetched = (await c.post(f"/v1/custom-providers/{prov['id']}/fetch-models", json={"force": True})).json()
    assert {m["preview"]["status"] for m in fetched["models"]} == {"unmatched"}
    assert all(m["preview"]["candidates"] == [] for m in fetched["models"])


# Fallback after an upstream failure is covered end-to-end with a scripted
# upstream in tests/integration/test_inference_fallback.py.
