"""The two credentials must not substitute for each other.

This is the security property Phase 2 exists to establish:

    a dashboard session  -> admin routes only   (never inference)
    an sk-geek-* key     -> inference only      (never admin)

Both directions are asserted against the real app so a future refactor of the
middleware cannot quietly merge them again.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account

ADMIN_ONLY_ROUTES = [
    ("GET", "/v1/providers"),
    ("GET", "/v1/custom-providers"),
    ("GET", "/v1/keys"),
    ("GET", "/v1/routing"),
    ("GET", "/v1/analytics/recent"),
    ("GET", "/v1/analytics/unreachable"),
    ("GET", "/v1/quality"),
    ("GET", "/api/models"),
]

ADMIN_WRITES = [
    ("PUT", "/v1/providers/openai", {"api_key": "sk-should-never-store"}),
    ("POST", "/v1/custom-providers", {
        "display_name": "X", "base_url": "https://api.example.com/v1", "api_key": "k",
    }),
    ("POST", "/v1/keys", {"name": "nope"}),
    ("PUT", "/v1/routing", {"strategy": "cheapest"}),
]

INFERENCE_ROUTES = [
    ("GET", "/v1/models"),
]


@pytest.fixture
async def booted(tmp_sqlite_url, monkeypatch, isolated_env):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
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

    from app.seed import seed_initial_state

    async with factory() as s:
        seed = await seed_initial_state(s)
    await create_admin_account(factory)

    from app.main import create_app

    yield create_app(), factory, seed.api_key

    await engine.dispose()
    session_mod._session_factory = None


@pytest.fixture
async def session_client(booted):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        assert r.status_code == 200
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        yield c


# ── an inference key must not reach the console ────────────────────────────


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ROUTES)
async def test_inference_key_cannot_read_admin_routes(booted, method, path):
    app, _factory, key = booted
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
        headers={"Authorization": f"Bearer {key}"},
    ) as c:
        r = await c.request(method, path)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}: {r.text[:200]}"
    assert "Administrator session" in r.json()["error"]["message"]


@pytest.mark.parametrize("method,path,body", ADMIN_WRITES)
async def test_inference_key_cannot_write_admin_routes(booted, method, path, body):
    app, _factory, key = booted
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
        headers={"Authorization": f"Bearer {key}"},
    ) as c:
        r = await c.request(method, path, json=body)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}: {r.text[:200]}"


async def test_inference_key_writes_have_no_effect(booted):
    app, _factory, key = booted
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
        headers={"Authorization": f"Bearer {key}"},
    ) as c:
        await c.put("/v1/providers/openai", json={"api_key": "sk-smuggled"})
        assert (await c.get("/v1/providers")).status_code == 401

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        providers = (await c.get("/v1/providers")).json()["providers"]
    assert all(p["provider"] != "openai" for p in providers)


# ── a session must not act as an inference credential ──────────────────────


@pytest.mark.parametrize("method,path", INFERENCE_ROUTES)
async def test_session_cookie_cannot_authorize_inference(booted, method, path):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        assert r.status_code == 200
        # The cookie is in the jar; no Authorization header is set.
        resp = await c.request(method, path)
    assert resp.status_code == 401
    assert "dashboard session cannot be used for inference" in resp.json()["error"]["message"]


async def test_session_cookie_cannot_call_chat_completions(booted):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        r = await c.post("/v1/chat/completions", json={
            "model": "auto", "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 401


async def test_session_cookie_cannot_call_native_surfaces(booted):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        anthropic = await c.post("/v1/messages", json={})
        gemini = await c.get("/v1beta/models")
    assert anthropic.status_code == 401
    assert anthropic.json()["type"] == "error"
    assert gemini.status_code == 401
    assert gemini.json()["error"]["status"] == "UNAUTHENTICATED"


async def test_both_credentials_together_still_route_by_class(booted):
    """Holding both is a legitimate browser+key combo; each request still uses
    only the credential its route class allows."""
    app, factory, key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        c.headers["Authorization"] = f"Bearer {key}"
        assert (await c.get("/v1/providers")).status_code == 200   # session
        assert (await c.get("/v1/models")).status_code == 200      # key


async def test_revoked_key_stops_inference_but_not_the_session(booted):
    app, factory, key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        c.headers["Authorization"] = f"Bearer {key}"

        seed_id = (await c.get("/v1/keys")).json()["keys"][0]["id"]
        assert (await c.delete(f"/v1/keys/{seed_id}")).status_code == 204

        # Inference with the dead key now fails...
        assert (await c.get("/v1/models")).status_code == 401
        # ...while the administrator can still sign in and mint a replacement.
        assert (await c.get("/v1/providers")).status_code == 200
        replacement = await c.post("/v1/keys", json={"name": "after-revoke"})
        assert replacement.status_code == 201


async def test_revoking_every_key_leaves_the_console_usable(booted):
    app, factory, key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        for k in (await c.get("/v1/keys")).json()["keys"]:
            if k["is_active"]:
                assert (await c.delete(f"/v1/keys/{k['id']}")).status_code == 204
        assert (await c.get("/v1/keys")).json()["keys"][0]["is_active"] is False
        # Administrator is unaffected and can start over.
        assert (await c.get("/api/auth/me")).status_code == 200
        assert (await c.post("/v1/keys", json={"name": "fresh"})).status_code == 201


# ── unauthenticated access ─────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/v1/providers", "/v1/keys", "/v1/routing",
                                  "/v1/analytics/recent", "/api/models"])
async def test_admin_routes_reject_anonymous(booted, path):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get(path)).status_code == 401


async def test_unknown_v1_path_needs_a_credential(booted):
    """Unknown paths answer 404 (not 401) — but only for authenticated callers."""
    app, _factory, key = booted
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
        headers={"Authorization": f"Bearer {key}"},
    ) as c:
        assert (await c.get("/v1/does-not-exist")).status_code == 404
        assert (await c.get("/v1beta/does-not-exist")).status_code == 404

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as anon:
        assert (await anon.get("/v1/does-not-exist")).status_code == 401


async def test_public_routes_need_nothing(booted):
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        for path in ("/health", "/", "/providers", "/api/auth/status"):
            assert (await c.get(path)).status_code == 200, path


async def test_openapi_is_not_public(booted):
    """The schema enumerates every route and every parameter shape."""
    app, _factory, _key = booted
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/openapi.json")).status_code == 401
        assert (await c.get("/docs")).status_code == 401
