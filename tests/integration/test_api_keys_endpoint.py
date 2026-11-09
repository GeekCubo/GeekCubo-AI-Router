"""Settings -> API Keys backend: endpoint route, key lifecycle, non-recoverability.

Real app + real SQLite (same harness as test_admin_auth.py).
"""

from __future__ import annotations

import re

import pytest
from httpx import ASGITransport, AsyncClient

from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account
from tests.integration.test_admin_auth import auth_app  # noqa: F401  (fixture)

KEY_RE = re.compile(r"sk-geek-[0-9a-f]{32}")


@pytest.fixture
async def admin(auth_app):  # noqa: F811
    app, factory = auth_app
    await create_admin_account(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8787") as c:
        r = await c.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        yield c


async def test_endpoint_route_requires_an_admin_session(auth_app):  # noqa: F811
    app, _ = auth_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/integrations/endpoint")).status_code == 401


async def test_endpoint_route_rejects_an_inference_key(auth_app, admin):  # noqa: F811
    app, _ = auth_app
    key = (await admin.post("/v1/keys", json={"name": "probe"})).json()["api_key"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/integrations/endpoint", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code in (401, 403)


async def test_endpoint_route_local_fallback(admin, monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    r = await admin.get("/api/integrations/endpoint")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "local"
    assert body["api_base_url"] == "http://127.0.0.1:8787/v1"
    assert body["env_key"] == "GEEKCUBO_API_KEY"
    assert not KEY_RE.search(r.text)


async def test_endpoint_route_public_https(admin, monkeypatch):
    from app import config as cfg

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.example.com/v1/")
    cfg.get_settings.cache_clear()
    try:
        r = await admin.get("/api/integrations/endpoint", headers={"x-forwarded-proto": "http",
                                                                  "x-forwarded-host": "evil.example"})
        body = r.json()
        assert body["kind"] == "public"
        assert body["api_base_url"] == "https://api.example.com/v1"
        assert body["local_api_base_url"].startswith("http://127.0.0.1")
        opts = (await admin.get("/api/integrations/options")).json()
        assert opts["public_base_url"] == "https://api.example.com/v1"
        assert opts["default_endpoint"] == "remote"
        # Connect a tool upgrades an http:// URL for the configured https host.
        cfg_r = await admin.get("/api/integrations/config", params={
            "app": "opencode", "model": "auto", "base_url": "http://api.example.com/v1"})
        assert cfg_r.status_code == 200
        assert '"baseURL": "https://api.example.com/v1"' in cfg_r.json()["code"]
    finally:
        cfg.get_settings.cache_clear()


async def test_created_and_rotated_keys_are_not_cacheable_and_shown_once(admin):
    r = await admin.post("/v1/keys", json={"name": "laptop"})
    assert r.status_code == 201
    assert r.headers["cache-control"] == "no-store"
    secret = r.json()["api_key"]
    assert KEY_RE.fullmatch(secret)
    key_id = r.json()["id"]

    rot = await admin.post(f"/v1/keys/{key_id}/rotate", json={"revoke_original": False})
    assert rot.status_code == 201 and rot.headers["cache-control"] == "no-store"
    replacement = rot.json()["api_key"]
    assert replacement != secret

    listing = await admin.get("/v1/keys")
    assert secret not in listing.text and replacement not in listing.text
    assert not KEY_RE.search(listing.text)
    for k in listing.json()["keys"]:
        assert "api_key" not in k and "key_hash" not in k
        assert k["key_prefix"].startswith("sk-geek-....")
        for field in ("created_at", "expires_at", "last_used_at"):
            assert field in k


async def test_no_endpoint_returns_an_existing_full_key(admin):
    """Non-recoverability: after creation, nothing returns the plaintext."""
    secret = (await admin.post("/v1/keys", json={"name": "once"})).json()["api_key"]
    key_id = (await admin.get("/v1/keys")).json()["keys"][0]["id"]
    for path in ("/v1/keys", "/api/integrations/endpoint", "/api/integrations/options"):
        r = await admin.get(path)
        assert secret not in r.text, path
    r = await admin.put(f"/v1/keys/{key_id}", json={"name": "renamed"})
    assert r.status_code == 200 and secret not in r.text
    # There is no "reveal" route.
    assert (await admin.get(f"/v1/keys/{key_id}")).status_code in (404, 405)


async def test_revoke_still_works_and_stops_the_key(auth_app, admin):  # noqa: F811
    app, _ = auth_app
    r = (await admin.post("/v1/keys", json={"name": "temp"})).json()
    secret, key_id = r["api_key"], r["id"]
    assert (await admin.delete(f"/v1/keys/{key_id}")).status_code == 204
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/v1/models", headers={"Authorization": f"Bearer {secret}"})
        assert resp.status_code == 401
