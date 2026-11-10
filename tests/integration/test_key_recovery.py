"""Copyable sk-geek-* keys: encrypted storage, retrieval controls and safety.

Real app + real SQLite (same harness as test_api_keys_endpoint.py).
"""

from __future__ import annotations

import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient

from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account
from tests.integration.test_admin_auth import auth_app  # noqa: F401  (fixture)

RECOVERY_KEY = "ab" * 32


@pytest.fixture
async def admin(auth_app, monkeypatch):  # noqa: F811
    monkeypatch.setenv("API_KEY_RECOVERY_KEY", RECOVERY_KEY)
    from app import config as cfg
    from app.routes import keys as keys_routes

    cfg.get_settings.cache_clear()
    keys_routes.reset_recovery_rate_limits()
    app, factory = auth_app
    await create_admin_account(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8787") as c:
        r = await c.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        c.app = app
        yield c
    cfg.get_settings.cache_clear()


async def _infer(app, key: str) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        return (await c.get("/v1/models", headers={"Authorization": f"Bearer {key}"})).status_code


def _db(tmp_sqlite_url: str) -> sqlite3.Connection:
    return sqlite3.connect(tmp_sqlite_url.split("///", 1)[1])


async def test_new_key_is_copyable_later_and_never_stored_in_plaintext(admin, tmp_sqlite_url):
    created = (await admin.post("/v1/keys", json={"name": "opencode"})).json()
    secret = created["api_key"]
    assert created["recoverable"] is True
    listing = await admin.get("/v1/keys")
    assert secret not in listing.text
    assert any(k["id"] == created["id"] and k["recoverable"] for k in listing.json()["keys"])

    r = await admin.post(f"/v1/keys/{created['id']}/reveal")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert r.json()["api_key"] == secret
    assert await _infer(admin.app, r.json()["api_key"]) == 200

    con = _db(tmp_sqlite_url)
    dump = "\n".join(con.iterdump())
    con.close()
    assert secret not in dump
    assert secret.encode().hex() not in dump.lower()


async def test_authentication_stays_hash_based(admin, tmp_sqlite_url):
    created = (await admin.post("/v1/keys", json={"name": "k"})).json()
    con = _db(tmp_sqlite_url)
    con.execute("update api_keys set encrypted_secret=NULL where id=?", (created["id"],))
    con.commit()
    con.close()
    assert await _infer(admin.app, created["api_key"]) == 200


async def test_retrieval_needs_a_session_and_csrf(admin):
    kid = (await admin.post("/v1/keys", json={"name": "k"})).json()["id"]
    csrf = admin.headers.pop("x-csrf-token")
    assert (await admin.post(f"/v1/keys/{kid}/reveal")).status_code == 403
    admin.headers["x-csrf-token"] = csrf
    async with AsyncClient(transport=ASGITransport(app=admin.app), base_url="http://t") as anon:
        assert (await anon.post(f"/v1/keys/{kid}/reveal")).status_code == 401
    secret = (await admin.post(f"/v1/keys/{kid}/reveal")).json()["api_key"]
    async with AsyncClient(transport=ASGITransport(app=admin.app), base_url="http://t") as bearer:
        r = await bearer.post(f"/v1/keys/{kid}/reveal", headers={"Authorization": f"Bearer {secret}"})
        assert r.status_code in (401, 403)


async def test_retrieval_is_rate_limited(admin):
    kid = (await admin.post("/v1/keys", json={"name": "k"})).json()["id"]
    codes = [(await admin.post(f"/v1/keys/{kid}/reveal")).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


async def test_hash_only_key_cannot_be_copied(admin, tmp_sqlite_url):
    created = (await admin.post("/v1/keys", json={"name": "legacy"})).json()
    con = _db(tmp_sqlite_url)
    con.execute("update api_keys set encrypted_secret=NULL where id=?", (created["id"],))
    con.commit()
    con.close()
    r = await admin.post(f"/v1/keys/{created['id']}/reveal")
    assert r.status_code == 409 and "Rotate" in r.text
    assert created["api_key"] not in r.text
    # Rotation (non-destructive by default) yields a copyable replacement.
    rotated = (await admin.post(f"/v1/keys/{created['id']}/rotate", json={})).json()
    assert rotated["recoverable"] is True
    assert await _infer(admin.app, created["api_key"]) == 200
    assert (await admin.post(f"/v1/keys/{rotated['id']}/reveal")).json()["api_key"] == rotated["api_key"]


async def test_revocation_and_archive_destroy_the_copy(admin, tmp_sqlite_url):
    created = (await admin.post("/v1/keys", json={"name": "gone"})).json()
    assert (await admin.delete(f"/v1/keys/{created['id']}")).status_code == 204
    con = _db(tmp_sqlite_url)
    blob = con.execute("select encrypted_secret from api_keys where id=?", (created["id"],)).fetchone()[0]
    con.close()
    assert blob is None
    assert (await admin.post(f"/v1/keys/{created['id']}/reveal")).status_code == 409


async def test_ciphertext_is_bound_to_its_row(admin, tmp_sqlite_url):
    a = (await admin.post("/v1/keys", json={"name": "a"})).json()
    b = (await admin.post("/v1/keys", json={"name": "b"})).json()
    con = _db(tmp_sqlite_url)
    blob = con.execute("select encrypted_secret from api_keys where id=?", (a["id"],)).fetchone()[0]
    con.execute("update api_keys set encrypted_secret=? where id=?", (blob, b["id"]))
    con.commit()
    con.close()
    r = await admin.post(f"/v1/keys/{b['id']}/reveal")
    assert r.status_code == 500 and a["api_key"] not in r.text


async def test_every_retrieval_is_audited_without_the_secret(admin, tmp_sqlite_url):
    created = (await admin.post("/v1/keys", json={"name": "audited"})).json()
    await admin.post(f"/v1/keys/{created['id']}/reveal")
    con = _db(tmp_sqlite_url)
    rows = con.execute("select event, outcome, key_prefix from key_recovery_audit").fetchall()
    allrows = con.execute("select * from key_recovery_audit").fetchall()
    con.close()
    assert ("retrieve", "ok", created["key_prefix"]) in rows
    assert created["api_key"] not in repr(allrows)


async def test_without_a_recovery_key_new_keys_are_hash_only(admin, monkeypatch):
    from app import config as cfg

    monkeypatch.delenv("API_KEY_RECOVERY_KEY", raising=False)
    cfg.get_settings.cache_clear()
    created = (await admin.post("/v1/keys", json={"name": "no-recovery-key"})).json()
    assert created["recoverable"] is False
    assert await _infer(admin.app, created["api_key"]) == 200
