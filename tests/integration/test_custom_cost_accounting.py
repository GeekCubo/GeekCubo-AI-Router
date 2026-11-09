# Accounting for priced custom models: never silently $0, never a foreign price.
from __future__ import annotations

import pytest

from tests.integration.test_routing_integration import (
    _models,
    _provider,
)

# Deliberately absent from LiteLLM's built-in cost map, so any non-zero cost
# can only have come from the price configured on the custom model.
MODEL = "zz-custom-9"


async def _last_row(c):
    return (await c.get("/v1/analytics/recent")).json()["items"][0]


@pytest.mark.parametrize("served", [MODEL, f"openai/{MODEL}", f"apixo/{MODEL}"])
@pytest.mark.parametrize("route", ["pinned", "auto"])
async def test_priced_custom_model_cost_is_recorded(env, served, route):
    c, up, _ = env
    up.model = served  # what the upstream reports in the response `model`
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(MODEL, True, 10.0, 128000)])
    model = f"apixo/{MODEL}" if route == "pinned" else "auto"
    r = await c.post("/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200, r.text
    row = await _last_row(c)
    # 4 input + 3 output tokens at $10/1M = $0.00007 = 70 microcents.
    assert 69 <= row["cost_microcents"] <= 70, row
    assert row["cost_unknown"] is False


@pytest.mark.parametrize("route", ["pinned", "auto"])
async def test_priced_custom_model_streaming_cost_is_recorded(env, route):
    c, up, _ = env
    up.stream = True
    up.model = f"openai/{MODEL}"
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(MODEL, True, 10.0, 128000)])
    model = f"apixo/{MODEL}" if route == "pinned" else "auto"
    r = await c.post("/v1/chat/completions", json={"model": model, "stream": True, "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert "data: [DONE]" in r.text
    row = await _last_row(c)
    assert 69 <= row["cost_microcents"] <= 70, row
    assert row["cost_unknown"] is False


async def test_unpriced_custom_model_is_unknown_not_free(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(MODEL, True, 0.0, 128000)])
    r = await c.post("/v1/chat/completions", json={"model": f"apixo/{MODEL}", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    row = await _last_row(c)
    assert row["cost_microcents"] == 0
    assert row["cost_unknown"] is True


@pytest.mark.parametrize("stream", [False, True])
async def test_each_model_is_billed_at_its_own_price(env, stream):
    """Two models behind ONE base URL, upstream echoing a misleading name.
    Attribution used to fall back to the provider's first model at that URL."""
    c, up, _ = env
    up.stream = stream
    up.model = "gpt-4o"  # echoed name matches neither model
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("cheap-x", True, 1.0, 128000), ("pricey-x", True, 100.0, 128000)])
    r = await c.post("/v1/chat/completions", json={
        "model": "apixo/pricey-x", "stream": stream,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 200
    row = await _last_row(c)
    # 7 tokens at $100/1M = 700 microcents; the cheap model would be 7.
    assert 699 <= row["cost_microcents"] <= 700, row


async def test_analytics_totals_match_recent_rows(env):
    """Dashboard aggregate and per-request rows must report the same money."""
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(MODEL, True, 10.0, 128000)])
    for stream in (False, True):
        up.stream = stream
        await c.post("/v1/chat/completions", json={
            "model": f"apixo/{MODEL}", "stream": stream,
            "messages": [{"role": "user", "content": "hi"}],
        })
    rows = (await c.get("/v1/analytics/recent")).json()["items"]
    spend = (await c.get("/v1/analytics/spend?days=1")).json()
    assert spend["total_microcents"] == sum(r["cost_microcents"] for r in rows)
    assert spend["total_microcents"] >= 138
