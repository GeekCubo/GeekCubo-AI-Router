"""Tests for /v1/models, /v1/keys (rotate / allowlist), /v1/routing (strategy)."""

from __future__ import annotations

import pytest

from tests.authkit import SignedInClient


@pytest.fixture
async def lite_client(tmp_sqlite_url, monkeypatch):
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

    from app.main import create_app
    app = create_app()

    from httpx import ASGITransport

    async with SignedInClient(
transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {seed.api_key}"},
    ) as c:
        yield c, seed.api_key

    await engine.dispose()
    session_mod._session_factory = None


# ── /v1/models ────────────────────────────────────────────────────────

async def test_models_returns_openai_format_listing(lite_client):
    client, _ = lite_client
    r = await client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0
    sample = body["data"][0]
    assert sample["object"] == "model"
    assert "id" in sample
    assert "owned_by" in sample


async def test_models_returns_anthropic_format_for_anthropic_clients(lite_client):
    """The native /v1/messages surface lives on the same base URL, so
    `client.models.list()` from the Anthropic SDK hits this path too. It
    always sends `anthropic-version` (no OpenAI client does), which is
    what selects the Anthropic envelope."""
    client, _ = lite_client
    r = await client.get("/v1/models", headers={"anthropic-version": "2023-06-01"})
    assert r.status_code == 200
    body = r.json()
    assert "object" not in body  # not the OpenAI envelope
    assert body["has_more"] is False
    assert body["first_id"] == body["data"][0]["id"]
    assert body["last_id"] == body["data"][-1]["id"]
    sample = body["data"][0]
    assert sample["type"] == "model"
    assert sample["id"] and sample["display_name"]
    # RFC 3339, per ModelInfo.created_at
    assert sample["created_at"].endswith("Z")


async def test_models_without_anthropic_header_stays_openai_shaped(lite_client):
    """Regression guard: adding the Anthropic envelope must not change the
    default shape every OpenAI client depends on."""
    client, _ = lite_client
    r = await client.get("/v1/models", headers={"user-agent": "openai-python/1.0"})
    assert r.json()["object"] == "list"


# ── /v1/keys ──────────────────────────────────────────────────────────

async def test_list_keys_shows_seeded_key(lite_client):
    client, _ = lite_client
    r = await client.get("/v1/keys")
    assert r.status_code == 200
    body = r.json()
    assert len(body["keys"]) == 1
    assert body["keys"][0]["name"] == "default"
    assert "key_hash" not in body["keys"][0]
    # Seeded key is unrestricted — null, not [].
    assert body["keys"][0]["model_allowlist"] is None


async def test_create_new_key_returns_plaintext_once(lite_client):
    client, _ = lite_client
    r = await client.post("/v1/keys", json={"name": "ci-runner"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["api_key"].startswith("sk-geek-")
    assert body["name"] == "ci-runner"
    assert body["model_allowlist"] is None

    listing = await client.get("/v1/keys")
    names = {k["name"] for k in listing.json()["keys"]}
    assert names == {"default", "ci-runner"}


async def test_list_keys_newest_first(lite_client):
    """Keys are ordered created_at DESC, id DESC — newest at the top."""
    import asyncio

    client, _ = lite_client
    # The seed creates "default" first; each new key must appear above it.
    # SQLite's CURRENT_TIMESTAMP has second precision, so a same-second tie is
    # broken by id (a random UUID), not chronology — space the inserts out to
    # keep the timestamp ordering deterministic.
    await asyncio.sleep(1.1)
    await client.post("/v1/keys", json={"name": "older"})
    await asyncio.sleep(1.1)
    await client.post("/v1/keys", json={"name": "newer"})

    names = [k["name"] for k in (await client.get("/v1/keys")).json()["keys"]]
    # "newer" was created last, so it must lead; "default" is oldest and last.
    assert names[0] == "newer", names
    assert names[-1] == "default", names
    # created_at must be non-increasing down the list.
    times = [k["created_at"] for k in (await client.get("/v1/keys")).json()["keys"]]
    assert times == sorted(times, reverse=True), times


async def test_create_key_with_allowlist(lite_client):
    client, _ = lite_client
    r = await client.post(
        "/v1/keys",
        json={"name": "scoped", "model_allowlist": ["gpt-4o-mini"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["model_allowlist"] == ["gpt-4o-mini"]

    listing = await client.get("/v1/keys")
    scoped = next(k for k in listing.json()["keys"] if k["name"] == "scoped")
    assert scoped["model_allowlist"] == ["gpt-4o-mini"]


async def test_create_key_empty_allowlist_is_deny_all(lite_client):
    """[] is stored as [] (deny everything), not coerced to null."""
    client, _ = lite_client
    r = await client.post("/v1/keys", json={"name": "locked", "model_allowlist": []})
    assert r.status_code == 201, r.text
    assert r.json()["model_allowlist"] == []

    listing = await client.get("/v1/keys")
    locked = next(k for k in listing.json()["keys"] if k["name"] == "locked")
    assert locked["model_allowlist"] == []


async def test_create_key_rejects_unknown_model_ids(lite_client):
    client, _ = lite_client
    r = await client.post(
        "/v1/keys",
        json={
            "name": "typo",
            "model_allowlist": ["gpt-4o-mni", "also-fake", "gpt-4o-mini"],
        },
    )
    assert r.status_code == 422, r.text
    assert "gpt-4o-mni" in r.text
    assert "also-fake" in r.text
    listing = await client.get("/v1/keys")
    names = {k["name"] for k in listing.json()["keys"]}
    assert "typo" not in names


async def test_put_key_updates_allowlist(lite_client):
    client, _ = lite_client
    created = (await client.post("/v1/keys", json={"name": "mutable"})).json()
    r = await client.put(
        f"/v1/keys/{created['id']}",
        json={"model_allowlist": ["gpt-4o-mini"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["model_allowlist"] == ["gpt-4o-mini"]

    listing = await client.get("/v1/keys")
    row = next(k for k in listing.json()["keys"] if k["id"] == created["id"])
    assert row["model_allowlist"] == ["gpt-4o-mini"]


async def test_put_key_empty_allowlist_is_deny_all(lite_client):
    client, _ = lite_client
    created = (
        await client.post(
            "/v1/keys",
            json={"name": "lockable", "model_allowlist": ["gpt-4o-mini"]},
        )
    ).json()
    r = await client.put(f"/v1/keys/{created['id']}", json={"model_allowlist": []})
    assert r.status_code == 200, r.text
    assert r.json()["model_allowlist"] == []


async def test_put_key_null_allowlist_clears_restriction(lite_client):
    client, _ = lite_client
    created = (
        await client.post(
            "/v1/keys",
            json={"name": "clearable", "model_allowlist": ["gpt-4o-mini"]},
        )
    ).json()
    r = await client.put(
        f"/v1/keys/{created['id']}",
        json={"model_allowlist": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["model_allowlist"] is None


async def test_put_key_rejects_unknown_model_ids(lite_client):
    client, _ = lite_client
    created = (
        await client.post(
            "/v1/keys",
            json={"name": "stable", "model_allowlist": ["gpt-4o-mini"]},
        )
    ).json()
    r = await client.put(
        f"/v1/keys/{created['id']}",
        json={"model_allowlist": ["not-a-real-model"]},
    )
    assert r.status_code == 422, r.text
    assert "not-a-real-model" in r.text
    listing = await client.get("/v1/keys")
    row = next(k for k in listing.json()["keys"] if k["id"] == created["id"])
    assert row["model_allowlist"] == ["gpt-4o-mini"]


async def test_put_key_missing_returns_404(lite_client):
    client, _ = lite_client
    r = await client.put(
        "/v1/keys/does-not-exist",
        json={"model_allowlist": ["gpt-4o-mini"]},
    )
    assert r.status_code == 404


async def test_revoke_key_blocks_reauth(lite_client):
    client, _ = lite_client
    created = (await client.post("/v1/keys", json={"name": "to-revoke"})).json()
    new_key = created["api_key"]
    new_id = created["id"]

    r = await client.delete(f"/v1/keys/{new_id}")
    assert r.status_code == 204

    from httpx import AsyncClient
    transport = client._transport
    async with AsyncClient(transport=transport, base_url="http://t",
                           headers={"Authorization": f"Bearer {new_key}"}) as fresh:
        r2 = await fresh.get("/v1/models")
    assert r2.status_code == 401
    assert r2.json()["error"]["message"] == "API key revoked"


# ── key management is administrator-only ─────────────────────────────
# These replace the pre-Phase-2 "restricted key may / may not manage keys"
# matrix. That matrix existed because an sk-geek-* key could call /v1/keys at
# all, so every subset/escalation edge case needed its own guard. Now no
# inference key reaches these routes, restricted or not — the whole class of
# escalation is closed at the boundary rather than case by case.


async def test_no_inference_key_can_manage_keys(lite_client):
    from httpx import AsyncClient

    client, root_key = lite_client
    created = (
        await client.post(
            "/v1/keys", json={"name": "scoped", "model_allowlist": ["gpt-4o-mini"]}
        )
    ).json()
    target = created["id"]

    for key in (root_key, created["api_key"]):
        async with AsyncClient(
            transport=client._transport, base_url="http://t",
            headers={"Authorization": f"Bearer {key}"},
        ) as k:
            assert (await k.get("/v1/keys")).status_code == 401
            assert (await k.post("/v1/keys", json={"name": "escape"})).status_code == 401
            assert (
                await k.put(f"/v1/keys/{target}", json={"model_allowlist": None})
            ).status_code == 401
            assert (await k.delete(f"/v1/keys/{target}")).status_code == 401
            assert (
                await k.post(f"/v1/keys/{target}/rotate", json={})
            ).status_code == 401

    # Nothing changed: still restricted, still active, nothing minted.
    keys = (await client.get("/v1/keys")).json()["keys"]
    assert {k["name"] for k in keys} == {"default", "scoped"}
    row = next(k for k in keys if k["id"] == target)
    assert row["model_allowlist"] == ["gpt-4o-mini"]
    assert row["is_active"] is True


async def test_restricted_key_still_enforced_on_inference(lite_client):
    """The allowlist itself is unchanged: a restricted key is still limited on
    the inference surface (it just can no longer edit its own restriction)."""
    from httpx import AsyncClient

    client, _ = lite_client
    created = (
        await client.post("/v1/keys", json={"name": "locked", "model_allowlist": []})
    ).json()
    async with AsyncClient(
        transport=client._transport, base_url="http://t",
        headers={"Authorization": f"Bearer {created['api_key']}"},
    ) as k:
        r = await k.post("/v1/chat/completions", json={
            "model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 403, r.text


async def test_rename_does_not_touch_allowlist(lite_client):
    client, _ = lite_client
    created = (
        await client.post(
            "/v1/keys", json={"name": "before", "model_allowlist": ["gpt-4o-mini"]}
        )
    ).json()
    r = await client.put(f"/v1/keys/{created['id']}", json={"name": "after"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "after"
    assert r.json()["model_allowlist"] == ["gpt-4o-mini"]


async def test_rename_rejects_blank_name(lite_client):
    client, _ = lite_client
    created = (await client.post("/v1/keys", json={"name": "x"})).json()
    r = await client.put(f"/v1/keys/{created['id']}", json={"name": "   "})
    assert r.status_code == 422


async def test_rotate_keeps_original_working_by_default(lite_client):
    from httpx import AsyncClient

    client, _ = lite_client
    created = (
        await client.post(
            "/v1/keys", json={"name": "svc", "model_allowlist": ["gpt-4o-mini"]}
        )
    ).json()
    r = await client.post(f"/v1/keys/{created['id']}/rotate", json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["api_key"].startswith("sk-geek-")
    assert body["api_key"] != created["api_key"]
    # Same scope carried over to the replacement.
    assert body["model_allowlist"] == ["gpt-4o-mini"]
    assert body["original"]["is_active"] is True

    for secret in (created["api_key"], body["api_key"]):
        async with AsyncClient(
            transport=client._transport, base_url="http://t",
            headers={"Authorization": f"Bearer {secret}"},
        ) as k:
            assert (await k.get("/v1/models")).status_code == 200


async def test_rotate_with_revoke_original_cuts_over(lite_client):
    from httpx import AsyncClient

    client, _ = lite_client
    created = (await client.post("/v1/keys", json={"name": "svc"})).json()
    r = await client.post(
        f"/v1/keys/{created['id']}/rotate", json={"revoke_original": True}
    )
    assert r.status_code == 201
    assert r.json()["original"]["is_active"] is False
    async with AsyncClient(
        transport=client._transport, base_url="http://t",
        headers={"Authorization": f"Bearer {created['api_key']}"},
    ) as k:
        assert (await k.get("/v1/models")).status_code == 401


async def test_plaintext_key_never_appears_in_listing(lite_client):
    client, _ = lite_client
    created = (await client.post("/v1/keys", json={"name": "secret"})).json()
    listing = await client.get("/v1/keys")
    assert created["api_key"] not in listing.text
    assert "key_hash" not in listing.text


async def test_expiring_key_stops_working_after_expiry(lite_client, tmp_sqlite_url):
    """Expiry is enforced per request — no sweep job, no grace window."""
    from datetime import datetime, timedelta, timezone

    from httpx import AsyncClient
    from sqlalchemy import update

    from packages.db import session as session_mod
    from packages.db.models.api_key import ApiKey

    client, _ = lite_client
    created = (
        await client.post("/v1/keys", json={"name": "temp", "expires_in_days": 1})
    ).json()
    assert created["expires_at"] is not None

    headers = {"Authorization": f"Bearer {created['api_key']}"}
    async with AsyncClient(
        transport=client._transport, base_url="http://t", headers=headers
    ) as k:
        assert (await k.get("/v1/models")).status_code == 200

    async with session_mod._session_factory() as s:
        await s.execute(
            update(ApiKey)
            .where(ApiKey.id == created["id"])
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await s.commit()

    async with AsyncClient(
        transport=client._transport, base_url="http://t", headers=headers
    ) as k:
        r = await k.get("/v1/models")
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "API key expired"
    listed = next(
        k for k in (await client.get("/v1/keys")).json()["keys"]
        if k["id"] == created["id"]
    )
    assert listed["expired"] is True


# ── /v1/routing ───────────────────────────────────────────────────────

async def test_get_routing_returns_default_strategy(lite_client):
    client, _ = lite_client
    r = await client.get("/v1/routing")
    assert r.status_code == 200
    body = r.json()
    assert body["strategy"] == "balanced"


async def test_put_routing_updates_strategy(lite_client):
    client, _ = lite_client
    r = await client.put("/v1/routing", json={"strategy": "cheapest"})
    assert r.status_code == 200
    assert r.json()["strategy"] == "cheapest"

    fetched = await client.get("/v1/routing")
    assert fetched.json()["strategy"] == "cheapest"


async def test_put_routing_rejects_unknown_strategy(lite_client):
    client, _ = lite_client
    r = await client.put("/v1/routing", json={"strategy": "magic-sauce"})
    assert r.status_code == 422


async def test_put_routing_invalidates_cached_router(lite_client, monkeypatch):
    """Changing the strategy must drop the cached client so the next request
    rebuilds it with the new `routing_strategy`."""
    client, _ = lite_client
    from app import router_cache

    sentinel = object()
    router_cache._cached_client = sentinel
    assert router_cache._cached_client is sentinel

    r = await client.put("/v1/routing", json={"strategy": "cheapest"})
    assert r.status_code == 200
    assert router_cache._cached_client is None
