"""`model="auto"` must consider registered custom-provider models.

Regression guard for the live GeekCubo failure: every registered model worked
when pinned, `Tools` and pricing were configured, and Auto still answered

    No deployable model satisfies the requested capabilities (['tools'])

The resolver itself was never broken — the provider was persisted with
`eligible_for_auto = 0` ("pinned only"), so `merged_catalog(eligible_only=True)`
never handed its models to the ranker. Nothing in the error said that, so the
operator had no reason to look at provider eligibility.

These tests pin the whole chain:
  * configured metadata (tools / pricing / enabled) is what Auto reads —
    it never consults LiteLLM's public model registry for the *routing* decision;
  * each eligibility gate really does exclude (so the check stays honest);
  * a configuration change takes effect on the very next request;
  * the failure message names the gate that actually blocked.
"""

from __future__ import annotations

import pytest

from tests.authkit import dual_client
from tests.integration.test_custom_providers import _MockUpstream

TOOLS_PAYLOAD = [{
    "type": "function",
    "function": {"name": "f", "parameters": {"type": "object", "properties": {}}},
}]


@pytest.fixture
def mock_upstream():
    upstream = _MockUpstream()
    # A wire id that LiteLLM's public cost map does NOT contain. Auto must
    # still route to it: the routing decision comes from the operator's
    # configured metadata, not from litellm.model_cost.
    upstream.model = "geekcubo-nova-9"
    upstream.models_payload = {
        "object": "list",
        "data": [{"id": "geekcubo-nova-9", "object": "model", "owned_by": "apixo"}],
    }
    upstream.start()
    try:
        yield upstream
    finally:
        upstream.stop()


@pytest.fixture
async def client(tmp_sqlite_url, monkeypatch, isolated_env, mock_upstream):
    """Signed-in admin client + one registered custom provider.

    `isolated_env` strips developer provider keys, so Auto has exactly one
    family of deployments to choose from and the assertions cannot be
    satisfied by a built-in provider that happens to be configured locally.
    """
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    monkeypatch.setenv(
        "CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS", f"127.0.0.1:{mock_upstream.port}"
    )

    from app import config as cfg

    cfg.get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db import session as session_mod
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory

    from app import router_cache
    from app.seed import seed_initial_state

    router_cache.invalidate_router()

    async with factory() as s:
        seed = await seed_initial_state(s)

    from app.main import create_app

    c = await dual_client(create_app(), factory, seed.api_key)
    try:
        yield c, mock_upstream
    finally:
        await c.aclose()
        router_cache.invalidate_router()
        from app.custom_providers import invalidate

        invalidate()
    await engine.dispose()
    session_mod._session_factory = None


async def _provider(client, upstream, *, eligible: bool, enabled: bool = True):
    r = await client.post("/v1/custom-providers", json={
        "display_name": "APIXO",
        "base_url": upstream.base_url,
        "api_key": "sk-geekcubo-test-key-123456",
        "eligible_for_auto": eligible,
        "is_enabled": enabled,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _model(client, pid, *, model_id="geekcubo-nova-9", tools=True,
                 price=1.0, output_price=None, json_mode=False, json_schema=False):
    r = await client.put(f"/v1/custom-providers/{pid}/models", json=[{
        "model_id": model_id,
        "display_name": model_id,
        "context_length": 200_000,
        "supports_tools": tools,
        "supports_vision": False,
        "supports_json_mode": json_mode,
        "supports_json_schema": json_schema,
        "input_cost_per_million": price,
        "output_cost_per_million": output_price if output_price is not None else price,
    }])
    assert r.status_code == 200, r.text


async def _auto(client, *, tools=True):
    payload = {"model": "auto", "messages": [{"role": "user", "content": "hi"}]}
    if tools:
        payload["tools"] = TOOLS_PAYLOAD
    return await client.post("/v1/chat/completions", json=payload)


# ── the regression itself ──────────────────────────────────────────────────


async def test_pinned_model_works_before_and_after_enabling_auto(client):
    """The model is identical; only provider eligibility changes."""
    c, upstream = client
    pid = await _provider(c, upstream, eligible=False)
    await _model(c, pid)

    pinned = await c.post("/v1/chat/completions", json={
        "model": "apixo/geekcubo-nova-9",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert pinned.status_code == 200, pinned.text
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"

    # Same model, via auto: pinned-only provider is excluded.
    before = await _auto(c)
    assert before.status_code == 422, before.text

    upd = await c.put(f"/v1/custom-providers/{pid}", json={"eligible_for_auto": True})
    assert upd.status_code == 200

    after = await _auto(c)
    assert after.status_code == 200, after.text
    assert after.headers["x-geek-requested-model"] == "auto"
    resolved = after.headers["x-geek-resolved-model"]
    assert "geekcubo-nova-9" in resolved


async def test_auto_selects_a_registered_tool_capable_priced_model(client):
    """Auto must reach a model that exists ONLY in the operator's config.

    The wire id is absent from LiteLLM's public cost map, which is exactly the
    situation that produced `ModelNotMappedError` in production for
    `openai/claude-opus-5-5` and `openai/deepseek-v4-pro-0813`.
    """
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=1.0)

    resp = await _auto(c)
    assert resp.status_code == 200, resp.text
    # The mock upstream (not some built-in provider) served it, with the
    # operator's wire id.
    assert upstream.requests, "auto never reached the custom upstream"
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"


def _rf(fmt: str) -> dict:
    if fmt == "json_object":
        return {"response_format": {"type": "json_object"}}
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": {"type": "object"}},
        },
    }


# ── JSON mode and Structured Outputs are independent filters ───────────────


async def test_auto_selects_json_mode_model_for_json_object_request(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, json_mode=True)

    resp = await c.post("/v1/chat/completions", json={
        "model": "auto", "messages": [{"role": "user", "content": "hi"}],
        **_rf("json_object"),
    })
    assert resp.status_code == 200, resp.text
    assert upstream.requests
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"
    assert upstream.requests[0]["body"]["response_format"] == {"type": "json_object"}


async def test_auto_excludes_a_model_without_json_mode_for_json_object(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, json_mode=False, json_schema=True)

    resp = await c.post("/v1/chat/completions", json={
        "model": "auto", "messages": [{"role": "user", "content": "hi"}],
        **_rf("json_object"),
    })
    assert resp.status_code == 422, resp.text
    assert not upstream.requests
    assert "json_mode" in resp.text


async def test_auto_selects_json_schema_model_for_structured_outputs(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, json_schema=True)

    resp = await c.post("/v1/chat/completions", json={
        "model": "auto", "messages": [{"role": "user", "content": "hi"}],
        **_rf("json_schema"),
    })
    assert resp.status_code == 200, resp.text
    assert upstream.requests
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"
    assert upstream.requests[0]["body"]["response_format"]["type"] == "json_schema"


async def test_auto_excludes_a_model_without_json_schema_for_structured_outputs(client):
    """A `supports_json_mode` flag must NOT satisfy a `json_schema` request —
    the two capabilities filter independently."""
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, json_mode=True, json_schema=False)

    resp = await c.post("/v1/chat/completions", json={
        "model": "auto", "messages": [{"role": "user", "content": "hi"}],
        **_rf("json_schema"),
    })
    assert resp.status_code == 422, resp.text
    assert not upstream.requests
    assert "json_schema" in resp.text


async def test_auto_excludes_a_model_without_tool_support(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=False, price=1.0)

    resp = await _auto(c)
    assert resp.status_code == 422, resp.text
    assert not upstream.requests  # capability check is not bypassed
    # An unchecked registration box leaves the capability Unknown, not
    # Unsupported — the diagnostic must say so.
    assert "Tools support unknown" in resp.text


async def test_auto_excludes_a_disabled_provider(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True, enabled=False)
    await _model(c, pid, tools=True, price=1.0)

    resp = await _auto(c)
    assert resp.status_code == 422, resp.text
    assert not upstream.requests
    # A disabled provider has no deployments at all, so this is reported on
    # the "no deployable provider" path — which must also carry the diagnosis.
    assert "is disabled" in resp.text


async def test_auto_excludes_a_pinned_only_provider(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=False)
    await _model(c, pid, tools=True, price=1.0)

    resp = await _auto(c)
    assert resp.status_code == 422, resp.text
    assert not upstream.requests
    assert "pinned-only" in resp.text
    assert "Enable Auto" in resp.text


async def test_auto_excludes_an_unpriced_model(client):
    """Zero price is treated as "unknown", not "free" — the ranker's savings
    arithmetic depends on it, so it must stay excluded."""
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=0.0)

    resp = await _auto(c)
    assert resp.status_code == 422, resp.text
    assert not upstream.requests
    assert "no pricing configured" in resp.text


async def test_fully_free_model_is_also_excluded(client):
    """Both directions zero -> blended cost 0 -> excluded (unknown, not free)."""
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=1.0, output_price=0.0)
    # An input-only price still blends to > 0, so this one IS eligible; the
    # guard that matters is the total-zero case above. Assert the documented
    # behaviour explicitly so a future "must be non-zero in BOTH" change to
    # the ranker shows up here as a deliberate decision, not a silent drift.
    from app.auto_routing import is_priced_for_auto
    from packages.litellm_adapter.catalog import CatalogModel

    assert is_priced_for_auto(CatalogModel(
        id="x", provider="", litellm_prefix="openai/",
        input_cost_per_token=1e-6, output_cost_per_token=0.0,
    )) is True
    assert is_priced_for_auto(CatalogModel(
        id="y", provider="", litellm_prefix="openai/",
        input_cost_per_token=0.0, output_cost_per_token=0.0,
    )) is False


# ── configuration changes take effect immediately ─────────────────────────


async def test_enabling_tools_takes_effect_on_the_next_request(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=False, price=1.0)

    first = await _auto(c)
    assert first.status_code == 422, first.text

    await _model(c, pid, tools=True, price=1.0)

    second = await _auto(c)
    assert second.status_code == 200, second.text
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"


async def test_setting_pricing_takes_effect_on_the_next_request(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=0.0)
    assert (await _auto(c)).status_code == 422

    await _model(c, pid, tools=True, price=2.5)

    resp = await _auto(c)
    assert resp.status_code == 200, resp.text
    assert upstream.requests


async def test_disabling_auto_takes_effect_on_the_next_request(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=1.0)
    assert (await _auto(c)).status_code == 200

    await c.put(f"/v1/custom-providers/{pid}", json={"eligible_for_auto": False})

    resp = await _auto(c)
    assert resp.status_code == 422, resp.text
    assert "pinned-only" in resp.text


async def test_deleting_a_model_removes_it_from_auto(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=1.0)
    assert (await _auto(c)).status_code == 200

    d = await c.put(f"/v1/custom-providers/{pid}/models", json=[])
    assert d.status_code == 200

    assert (await _auto(c)).status_code == 422


# ── pinned behaviour is unchanged ─────────────────────────────────────────


async def test_pinned_request_ignores_auto_eligibility(client):
    """Pinning works whether or not the provider is Auto-eligible."""
    c, upstream = client
    pid = await _provider(c, upstream, eligible=False)
    await _model(c, pid, tools=False, price=0.0)

    resp = await c.post("/v1/chat/completions", json={
        "model": "apixo/geekcubo-nova-9",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200, resp.text
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"


async def test_pinned_request_keeps_the_namespaced_public_id(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=True)
    await _model(c, pid, tools=True, price=1.0)

    resp = await c.post("/v1/chat/completions", json={
        "model": "apixo/geekcubo-nova-9",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200
    assert resp.headers["x-geek-requested-model"] == "apixo/geekcubo-nova-9"
    # The upstream sees the bare wire id, never the namespaced one.
    assert upstream.requests[0]["body"]["model"] == "geekcubo-nova-9"


# ── the diagnostic itself ─────────────────────────────────────────────────


async def test_exclusion_message_names_every_failing_gate(client):
    c, upstream = client
    pid = await _provider(c, upstream, eligible=False, enabled=True)
    await _model(c, pid, tools=False, price=0.0)

    resp = await _auto(c)
    assert resp.status_code == 422
    msg = resp.json()["error"]["message"]
    assert "apixo/geekcubo-nova-9" in msg
    assert "pinned-only" in msg
    assert "no pricing configured" in msg
    assert "Tools support unknown" in msg


def test_explain_auto_exclusions_matches_the_resolver_gates():
    """Unit-level mirror: the explainer must call each gate the same way
    `choose_auto_model` does."""
    from app.custom_providers import (
        CustomProviderView,
        explain_auto_exclusions,
    )
    from packages.litellm_adapter.catalog import CatalogModel

    def view(*, enabled=True, eligible=True, tools=True, price=1.0):
        return CustomProviderView(
            slug="apixo",
            display_name="APIXO",
            base_url="https://example.invalid/v1",
            api_key="k",
            is_enabled=enabled,
            eligible_for_auto=eligible,
            models=[CatalogModel(
                id="m", provider="", litellm_prefix="openai/",
                supports_tools=tools,
                input_cost_per_token=price, output_cost_per_token=price,
            )],
        )

    # Fully configured + deployable -> no exclusion.
    assert explain_auto_exclusions(
        [view()], needs={"tools"}, deployable={"apixo/m"}
    ) == []

    lines = explain_auto_exclusions(
        [view(eligible=False, tools=False, price=0.0)],
        needs={"tools"}, deployable=set(),
    )
    assert len(lines) == 1
    text = lines[0]
    assert "pinned-only" in text
    assert "not deployable" in text
    assert "no pricing configured" in text
    assert "Tools support not enabled" in text
