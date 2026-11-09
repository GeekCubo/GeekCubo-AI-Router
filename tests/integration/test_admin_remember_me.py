"""Administrator "Remember me for 14 days" sessions.

Same harness as test_admin_auth.py: a real FastAPI app over a real SQLite
file, so middleware, cookies, CSRF and the DB row are exercised together.
Time is moved by rewriting the session row (created_at / last_seen_at /
expires_at), never by trusting anything the client sends.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from packages.auth.sessions import REMEMBER_TTL, SESSION_TTL
from packages.db.models.admin import AdminSession
from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account
from tests.integration.test_admin_auth import auth_app  # noqa: F401  (fixture)

COOKIE = "geekcubo_admin_session"
NEW_PASSWORD = "an entirely different passphrase"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class _Login:
    """`async with _Login(app, remember=...) as (client, response):`"""

    def __init__(self, app, *, remember=None):
        self.app, self.remember = app, remember

    async def __aenter__(self):
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://t")
        await self.client.__aenter__()
        body = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        if self.remember is not None:
            body["remember"] = self.remember
        r = await self.client.post("/api/auth/login", json=body)
        assert r.status_code == 200, r.text
        self.client.headers["x-csrf-token"] = r.json()["csrf_token"]
        return self.client, r

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)


def _session_cookie_header(response) -> str:
    return next(c for c in response.headers.get_list("set-cookie") if c.startswith(COOKIE + "="))


def _max_age(cookie_header: str) -> int:
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.lower().startswith("max-age="):
            return int(part.split("=", 1)[1])
    raise AssertionError(f"no Max-Age in {cookie_header!r}")


async def _rows(factory):
    async with factory() as s:
        return (await s.execute(select(AdminSession).order_by(AdminSession.created_at))).scalars().all()


async def _shift(factory, **values):
    async with factory() as s:
        await s.execute(update(AdminSession).values(**values))
        await s.commit()


@pytest.fixture
async def admin(auth_app):  # noqa: F811
    app, factory = auth_app
    await create_admin_account(factory)
    return app, factory


# ── normal login is unchanged ──────────────────────────────────────────────


async def test_default_login_keeps_the_normal_policy(admin):
    app, factory = admin
    # The "remember" field is omitted entirely, as older dashboards send it.
    async with _Login(app) as (client, r):
        assert r.json()["persistent"] is False
        (row,) = await _rows(factory)
        assert row.persistent is False
        lifetime = _utc(row.expires_at) - _utc(row.created_at)
        assert abs(lifetime - SESSION_TTL) < timedelta(minutes=1)
        assert _max_age(_session_cookie_header(r)) == 12 * 60 * 60


async def test_unchecked_box_is_a_normal_session(admin):
    app, factory = admin
    async with _Login(app, remember=False) as (client, r):
        assert r.json()["persistent"] is False
        assert (await _rows(factory))[0].persistent is False


async def test_normal_session_still_ends_after_60_idle_minutes(admin):
    app, factory = admin
    async with _Login(app, remember=False) as (client, _):
        await _shift(factory, last_seen_at=_now() - timedelta(minutes=61))
        assert (await client.get("/api/auth/me")).status_code == 401


# ── remembered login ───────────────────────────────────────────────────────


async def test_remembered_login_lasts_14_days_server_side_and_in_the_cookie(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, r):
        body = r.json()
        assert body["persistent"] is True
        (row,) = await _rows(factory)
        assert row.persistent is True
        lifetime = _utc(row.expires_at) - _utc(row.created_at)
        assert abs(lifetime - REMEMBER_TTL) < timedelta(minutes=1)

        cookie = _session_cookie_header(r)
        # Cookie lifetime matches the server record (persistent, not a
        # browser-session cookie) and is never longer than 14 days.
        assert 14 * 86400 - 120 <= _max_age(cookie) <= 14 * 86400
        assert "httponly" in cookie.lower()
        assert "samesite=lax" in cookie.lower()

        me = (await client.get("/api/auth/me")).json()
        assert me["persistent"] is True


async def test_remembered_session_survives_long_inactivity(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        # Three days without any request: a normal session would be long dead.
        await _shift(
            factory,
            created_at=_now() - timedelta(days=3),
            last_seen_at=_now() - timedelta(days=3),
        )
        assert (await client.get("/api/auth/me")).status_code == 200


async def test_remembered_session_survives_a_browser_restart(admin):
    """A new browser process has no in-memory state, only the stored cookie."""
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        cookie = client.cookies[COOKIE]
    await _shift(factory, last_seen_at=_now() - timedelta(hours=10))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as fresh:
        fresh.cookies.set(COOKIE, cookie)
        r = await fresh.get("/api/auth/me")
        assert r.status_code == 200
        # The CSRF token comes back from /me, so writes work after a restart too.
        fresh.headers["x-csrf-token"] = r.json()["csrf_token"]
        assert (await fresh.post("/v1/keys", json={"name": "after-restart"})).status_code in (200, 201)


async def test_remembered_session_ends_at_14_days_and_activity_does_not_extend_it(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        (row,) = await _rows(factory)
        original_expiry = _utc(row.expires_at)
        # Constant activity does not move the hard expiry.
        for _ in range(3):
            assert (await client.get("/api/auth/me")).status_code == 200
        (row,) = await _rows(factory)
        assert _utc(row.expires_at) == original_expiry

        # 14 days after sign-in it is over, even with activity a second ago.
        await _shift(
            factory,
            expires_at=_now() - timedelta(seconds=1),
            last_seen_at=_now(),
        )
        assert (await client.get("/api/auth/me")).status_code == 401


async def test_remembered_session_cannot_outlive_14_days_from_creation(admin):
    """Defence in depth: a tampered expires_at does not extend the lifetime."""
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        await _shift(
            factory,
            created_at=_now() - REMEMBER_TTL - timedelta(minutes=1),
            expires_at=_now() + timedelta(days=30),
            last_seen_at=_now(),
        )
        assert (await client.get("/api/auth/me")).status_code == 401


async def test_remembered_session_survives_server_restart(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        cookie = client.cookies[COOKIE]

    from app.main import create_app

    restarted = create_app()  # new process state; same database
    async with AsyncClient(transport=ASGITransport(app=restarted), base_url="http://t") as c:
        c.cookies.set(COOKIE, cookie)
        r = await c.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["persistent"] is True


# ── revocation applies to remembered sessions ──────────────────────────────


async def test_logout_ends_a_remembered_session(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        cookie = client.cookies[COOKIE]
        assert (await client.post("/api/auth/logout")).status_code == 204
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        c.cookies.set(COOKIE, cookie)  # replaying the old cookie must fail
        assert (await c.get("/api/auth/me")).status_code == 401


async def test_password_change_revokes_other_remembered_sessions(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (remembered, _), _Login(app, remember=False) as (current, _):
        r = await current.post("/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        })
        assert r.status_code == 200, r.text
        assert (await remembered.get("/api/auth/me")).status_code == 401
        assert (await current.get("/api/auth/me")).status_code == 200


async def test_cli_password_reset_revokes_remembered_sessions(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        from packages.auth import admin_accounts

        async with factory() as s:
            await admin_accounts.reset_password_locally(s, username=None, new_password=NEW_PASSWORD)
        assert (await client.get("/api/auth/me")).status_code == 401


async def test_revoke_other_sessions_includes_remembered_ones(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (remembered, _), _Login(app) as (current, _):
        r = await current.post("/api/auth/sessions/revoke-others")
        assert r.status_code == 200 and r.json()["revoked"] == 1
        assert (await remembered.get("/api/auth/me")).status_code == 401


async def test_cli_revoke_sessions_ends_remembered_sessions(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, _):
        from packages.auth.sessions import revoke_all_sessions

        rows = await _rows(factory)
        async with factory() as s:
            await revoke_all_sessions(s, rows[0].admin_id)
        assert (await client.get("/api/auth/me")).status_code == 401


# ── CSRF and token exposure ────────────────────────────────────────────────


async def test_remembered_session_still_requires_csrf(admin):
    app, _ = admin
    async with _Login(app, remember=True) as (client, _):
        client.headers.pop("x-csrf-token")
        r = await client.post("/v1/keys", json={"name": "no-csrf"})
        assert r.status_code == 403
        client.headers["x-csrf-token"] = "forged"
        assert (await client.post("/v1/keys", json={"name": "bad-csrf"})).status_code == 403


async def test_session_listing_shows_type_and_expiry_but_never_tokens(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (remembered, _), _Login(app) as (normal, _):
        secret = remembered.cookies[COOKIE]
        r = await normal.get("/api/auth/sessions")
        assert r.status_code == 200
        sessions = r.json()["sessions"]
        assert sorted(s["persistent"] for s in sessions) == [False, True]
        for s in sessions:
            assert s["expires_at"]
            assert "token" not in " ".join(s.keys())
        text = r.text
        assert secret not in text
        rows = await _rows(factory)
        for row in rows:
            assert row.token_hash not in text
            assert row.token_hash != secret


async def test_remember_flag_is_stored_only_as_a_hash_backed_row(admin):
    app, factory = admin
    async with _Login(app, remember=True) as (client, r):
        raw = client.cookies[COOKIE]
        assert raw not in r.text  # never in the JSON body
        (row,) = await _rows(factory)
        assert row.token_hash != raw and len(row.token_hash) == 64


async def test_remember_requires_a_valid_password(admin):
    app, _ = admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "wrong password", "remember": True,
        })
        assert r.status_code == 401
        assert COOKIE not in c.cookies


async def test_remember_rejects_non_boolean_values(admin):
    app, _ = admin
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "remember": {"days": 365},
        })
        assert r.status_code == 422


# ── upgrade path ───────────────────────────────────────────────────────────


async def test_upgrade_adds_the_column_and_keeps_existing_sessions(admin):
    """A database from before this change has no `persistent` column. The
    startup migration adds it; sessions issued before the upgrade stay valid
    under the normal policy."""
    app, factory = admin
    async with _Login(app) as (client, _):
        cookie = client.cookies[COOKIE]

    from sqlalchemy import inspect, text

    from packages.db.migrate import ensure_auth_columns, find_schema_drift

    engine = factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE admin_sessions DROP COLUMN persistent"))
        cols = await conn.run_sync(lambda c: {x["name"] for x in inspect(c).get_columns("admin_sessions")})
        assert "persistent" not in cols

    await ensure_auth_columns(engine)
    await ensure_auth_columns(engine)  # idempotent
    assert "admin_sessions" not in await find_schema_drift(engine)

    (row,) = await _rows(factory)
    assert row.persistent is False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        c.cookies.set(COOKIE, cookie)
        r = await c.get("/api/auth/me")
        assert r.status_code == 200 and r.json()["persistent"] is False
