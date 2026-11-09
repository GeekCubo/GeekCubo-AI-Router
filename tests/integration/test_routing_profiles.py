"""Routing profiles: CRUD, identifier rules, and inference through a profile.

Real app + real SQLite + a local mock OpenAI-compatible upstream. No real
provider keys (`isolated_env`), no billable requests.
"""

from __future__ import annotations

import pytest

from tests.integration.test_routing_integration import (
    TOOLS,
    _models,
    _provider,
)


async def _create(c, **kw):
    body = {"display_name": kw.pop("display_name", "Economy"), **kw}
    return await c.post("/v1/routing-profiles", json=body)


async def _chat(c, model, *, tools=False, stream=False, headers=None):
    payload = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
    if tools:
        payload["tools"] = TOOLS
    if stream:
        payload["stream"] = True
    return await c.post("/v1/chat/completions", json=payload, headers=headers or {})


# ── listing / built-in auto ───────────────────────────────────────────────


async def test_auto_is_always_listed_first_and_builtin(env):
    c, _up, _ = env
    r = await c.get("/v1/routing-profiles")
    assert r.status_code == 200
    first = r.json()["profiles"][0]
    assert first["slug"] == "auto"
    assert first["is_builtin"] is True


async def test_auto_cannot_be_deleted_or_edited(env):
    c, _up, _ = env
    assert (await c.delete("/v1/routing-profiles/auto")).status_code == 403
    r = await c.put("/v1/routing-profiles/auto", json={"display_name": "x"})
    assert r.status_code == 403


# ── create / identifier rules ─────────────────────────────────────────────


async def test_create_derives_a_stable_slug(env):
    c, _up, _ = env
    r = await _create(c, display_name="My Custom")
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "my-custom"


async def test_duplicate_slug_is_rejected(env):
    c, _up, _ = env
    assert (await _create(c, display_name="Economy")).status_code == 201
    r = await _create(c, display_name="Economy again", slug="economy")
    assert r.status_code == 409


@pytest.mark.parametrize("slug", ["auto", "models", "geek", "Bad Slug", "-x", "x-", "a/b"])
async def test_reserved_or_malformed_slugs_are_rejected(env, slug):
    c, _up, _ = env
    r = await _create(c, display_name="X", slug=slug)
    assert r.status_code == 422, (slug, r.text)


async def test_slug_cannot_shadow_a_registered_model(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    # The canonical id is "apixo/gpt-4o"; a profile claiming it is ambiguous.
    r = await _create(c, display_name="X", slug="apixo-gpt-4o")
    assert r.status_code == 201  # different identifier, fine
    from app.routing_profiles import ProfileError, normalize_slug

    # A slash can never be a slug, so canonical ids are structurally safe.
    with pytest.raises(ProfileError):
        normalize_slug("apixo/gpt-4o")


async def test_rename_display_name_keeps_slug(env):
    c, _up, _ = env
    pid = (await _create(c, display_name="Economy")).json()["id"]
    r = await c.put(f"/v1/routing-profiles/{pid}", json={"display_name": "Budget"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Budget"
    assert r.json()["slug"] == "economy"


async def test_slug_change_requires_confirmation_and_tombstones_old(env):
    c, _up, _ = env
    pid = (await _create(c, display_name="Economy")).json()["id"]
    r = await c.put(f"/v1/routing-profiles/{pid}", json={"slug": "budget"})
    assert r.status_code == 409
    r = await c.put(
        f"/v1/routing-profiles/{pid}",
        json={"slug": "budget", "confirm_slug_change": True},
    )
    assert r.status_code == 200
    assert r.json()["slug"] == "budget"
    # The old slug is tombstoned, not silently reusable.
    assert (await _create(c, display_name="Economy")).status_code == 409


# ── delete / tombstone ────────────────────────────────────────────────────


async def test_delete_tombstones_and_reassigns_default(env):
    c, _up, _ = env
    pid = (await _create(c, display_name="Economy")).json()["id"]
    assert (await c.post(f"/v1/routing-profiles/{pid}/default")).status_code == 200
    r = await c.delete(f"/v1/routing-profiles/{pid}")
    assert r.status_code == 200
    assert r.json()["default_reassigned_to"] == "auto"
    # Deleted id is not silently reused...
    assert (await _create(c, display_name="Economy")).status_code == 409
    # ...unless the admin takes it over deliberately.
    r = await _create(c, display_name="Economy", allow_slug_reuse=True)
    assert r.status_code == 201


async def test_delete_never_touches_providers_or_models(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    pid = (await _create(c, display_name="Economy")).json()["id"]
    await c.delete(f"/v1/routing-profiles/{pid}")
    listed = (await c.get("/v1/custom-providers")).json()
    providers = listed["providers"] if isinstance(listed, dict) else listed
    assert len(providers) == 1
    assert len(providers[0]["models"]) == 1


# ── duplicate / default / export / import ─────────────────────────────────


async def test_duplicate_copies_configuration(env):
    c, _up, _ = env
    pid = (await _create(c, display_name="Coding", strategy="quality")).json()["id"]
    r = await c.post(f"/v1/routing-profiles/{pid}/duplicate", json={})
    assert r.status_code == 201, r.text
    assert r.json()["strategy"] == "quality"
    assert r.json()["slug"] == "coding-copy"


async def test_only_one_default_at_a_time(env):
    c, _up, _ = env
    a = (await _create(c, display_name="A")).json()["id"]
    b = (await _create(c, display_name="B")).json()["id"]
    await c.post(f"/v1/routing-profiles/{a}/default")
    await c.post(f"/v1/routing-profiles/{b}/default")
    profiles = (await c.get("/v1/routing-profiles")).json()["profiles"]
    defaults = [p["slug"] for p in profiles if p["is_default"]]
    assert defaults == ["b"]


async def test_export_import_roundtrip_reports_unknown_models(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    pid = (await _create(
        c, display_name="Coding",
        policy={"pools": {"hard": ["apixo/gpt-4o"]}},
    )).json()["id"]
    exported = (await c.get(f"/v1/routing-profiles/{pid}/export")).json()
    assert exported["geekcubo_routing_profile"] == 1
    # Exports never carry credentials.
    assert "sk-test" not in str(exported)

    exported["slug"] = "coding-2"
    exported["policy"]["pools"]["mundane"] = ["nowhere/ghost"]
    r = await c.post("/v1/routing-profiles/import", json=exported)
    assert r.status_code == 201, r.text
    assert r.json()["unknown_models"] == ["nowhere/ghost"]


async def test_import_rejects_non_profile_json(env):
    c, _up, _ = env
    r = await c.post("/v1/routing-profiles/import", json={"slug": "x"})
    assert r.status_code == 422


# ── inference through a profile ───────────────────────────────────────────


async def test_profile_slug_routes_like_auto(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    assert (await _create(c, display_name="Economy", strategy="cheapest")).status_code == 201

    r = await _chat(c, "economy")
    assert r.status_code == 200, r.text
    assert r.headers["x-geek-routing-profile"] == "economy"
    assert r.headers["x-geek-routing-strategy"] == "cheapest"
    assert up.requests[-1]["body"]["model"] == "gpt-4o"


async def test_plain_auto_is_unaffected_by_profiles(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    await _create(c, display_name="Economy", strategy="cheapest")
    r = await _chat(c, "auto")
    assert r.status_code == 200
    assert r.headers["x-geek-routing-profile"] == "auto"
    assert r.headers["x-geek-routing-strategy"] == "balanced"


async def test_canonical_model_id_still_works(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    await _create(c, display_name="Economy")
    r = await _chat(c, "apixo/gpt-4o")
    assert r.status_code == 200, r.text
    assert "x-geek-routing-profile" not in r.headers


async def test_profile_model_restriction_is_enforced(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [
        ("cheap", True, 0.1, 128000),
        ("pricey", True, 9.0, 128000),
    ])
    await _create(
        c, display_name="Premium", strategy="cheapest",
        profile={"models": ["apixo/pricey"]},
    )
    r = await _chat(c, "premium")
    assert r.status_code == 200, r.text
    # Cheapest would pick "cheap" — the profile restriction must win.
    assert up.requests[-1]["body"]["model"] == "pricey"


async def test_fallback_never_escapes_profile_restriction(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [
        ("a", True, 0.1, 128000),
        ("b", True, 0.2, 128000),
        ("outside", True, 0.01, 128000),
    ])
    await _create(
        c, display_name="Restricted",
        profile={"models": ["apixo/a", "apixo/b"]},
    )
    r = await _chat(c, "restricted")
    assert r.status_code == 200
    cands = int(r.headers["x-geek-routing-candidates"])
    # Only the two allowed models are candidates (primary + fallback).
    assert cands == 2


async def test_cost_ceiling_excludes_expensive_and_unpriced(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [
        ("cheap", True, 0.5, 128000),     # blended $1.00/1M
        ("pricey", True, 50.0, 128000),   # blended $100/1M
    ])
    await _create(
        c, display_name="Budget",
        # $5 per 1M tokens, blended, in micro-dollars.
        profile={"max_cost_per_million_micros": 5_000_000},
    )
    r = await _chat(c, "budget")
    assert r.status_code == 200, r.text
    assert up.requests[-1]["body"]["model"] == "cheap"
    assert r.headers["x-geek-routing-candidates"] == "1"


async def test_profile_with_no_eligible_model_explains_why(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("pricey", True, 50.0, 128000)])
    await _create(
        c, display_name="Budget",
        profile={"max_cost_per_million_micros": 1_000_000},
    )
    r = await _chat(c, "budget")
    assert r.status_code == 422
    assert r.headers["x-geek-routing-diagnosis"] == "profile_restriction"
    assert "cost ceiling" in r.text


async def test_disabled_profile_returns_clear_404(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    pid = (await _create(c, display_name="Economy")).json()["id"]
    await c.put(f"/v1/routing-profiles/{pid}", json={"is_enabled": False})
    r = await _chat(c, "economy")
    assert r.status_code == 404
    assert r.headers["x-geek-routing-diagnosis"] == "profile_disabled"


async def test_profile_still_enforces_capabilities(env):
    c, up, _ = env
    prov = await _provider(c, up)
    # Only model has no tool support.
    await _models(c, prov["id"], [("no-tools", False, 1.0, 128000)])
    await _create(c, display_name="Economy")
    r = await _chat(c, "economy", tools=True)
    assert r.status_code == 422, r.text


async def test_profile_streaming_works(env):
    c, up, _ = env
    up.stream = True
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    await _create(c, display_name="Economy")
    r = await _chat(c, "economy", stream=True)
    assert r.status_code == 200
    assert "data: [DONE]" in r.text
    assert r.headers["x-geek-routing-profile"] == "economy"


async def test_profile_usage_is_recorded_under_its_slug(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    await _create(c, display_name="Economy")
    await _chat(c, "economy")
    profiles = (await c.get("/v1/routing-profiles")).json()["profiles"]
    eco = next(p for p in profiles if p["slug"] == "economy")
    assert eco["requests_30d"] == 1
    assert eco["last_used_at"]


async def test_allowlisted_key_cannot_use_profile_to_widen_access(env):
    """A key restricted to one model may use a profile, but the profile can
    only ever route it to models in that allowlist."""
    c, up, factory = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [
        ("a", True, 0.1, 128000),
        ("b", True, 0.2, 128000),
    ])
    await _create(c, display_name="Economy", strategy="cheapest")
    r = await c.post("/v1/keys", json={"name": "narrow", "model_allowlist": ["apixo/b"]})
    assert r.status_code in (200, 201), r.text
    key = r.json().get("key") or r.json().get("api_key") or r.json().get("plaintext")
    assert key
    up.requests.clear()
    r = await c.post(
        "/v1/chat/completions",
        json={"model": "economy", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert r.status_code == 200, r.text
    # Cheapest would pick "a"; the key's allowlist must still win.
    assert up.requests[-1]["body"]["model"] == "b"


# ── regressions: profile restrictions must never be silently dropped ──────


async def test_restrictions_are_reported_back_not_shown_as_default(env):
    c, _up, _ = env
    r = await _create(
        c, display_name="Budget",
        profile={"max_cost_per_million_micros": 5_000_000, "timeout_seconds": 30},
    )
    ext = r.json()["profile"]
    assert ext["max_cost_per_million_micros"] == 5_000_000
    assert ext["timeout_seconds"] == 30


async def test_policy_only_update_keeps_restrictions(env):
    c, _up, _ = env
    pid = (await _create(
        c, display_name="Budget", profile={"max_cost_per_million_micros": 5_000_000},
    )).json()["id"]
    r = await c.put(
        f"/v1/routing-profiles/{pid}",
        json={"policy": {"fallback": {"max_attempts": 2}}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile"]["max_cost_per_million_micros"] == 5_000_000
    assert r.json()["policy"]["fallback"]["max_attempts"] == 2


async def test_duplicate_keeps_restrictions(env):
    c, _up, _ = env
    pid = (await _create(
        c, display_name="Budget", profile={"models": ["apixo/x"]},
    )).json()["id"]
    r = await c.post(f"/v1/routing-profiles/{pid}/duplicate", json={})
    assert r.json()["profile"]["models"] == ["apixo/x"]


async def test_export_import_keeps_pools_and_restrictions(env):
    c, up, _ = env
    prov = await _provider(c, up)
    await _models(c, prov["id"], [("gpt-4o", True, 1.0, 128000)])
    pid = (await _create(
        c, display_name="Coding",
        policy={"pools": {"hard": ["apixo/gpt-4o"]}},
        profile={"max_cost_per_million_micros": 9_000_000},
    )).json()["id"]
    exported = (await c.get(f"/v1/routing-profiles/{pid}/export")).json()
    exported["slug"] = "coding-imported"
    r = await c.post("/v1/routing-profiles/import", json=exported)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["policy"]["pools"]["hard"] == ["apixo/gpt-4o"]
    assert body["profile"]["max_cost_per_million_micros"] == 9_000_000


async def test_models_endpoint_lists_auto_and_enabled_profiles(env):
    c, _up, _ = env
    await _create(c, display_name="Economy")
    pid = (await _create(c, display_name="Hidden")).json()["id"]
    await c.put(f"/v1/routing-profiles/{pid}", json={"is_enabled": False})
    ids = [m["id"] for m in (await c.get("/v1/models")).json()["data"]]
    assert ids[0] == "auto"
    assert "economy" in ids
    assert "hidden" not in ids  # disabled profiles are not advertised
