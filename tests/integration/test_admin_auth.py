"""Administrator authentication: setup, login, sessions, CSRF, recovery.

Everything here runs against a real FastAPI app + real SQLite, so the
middleware, cookie handling, CSRF checks and DB constraints are all exercised
together. Mocks are limited to the outbound-network boundary (unused here).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account


@pytest.fixture
async def auth_app(tmp_sqlite_url, monkeypatch, isolated_env):
    """Booted app over a fresh DB with no administrator yet."""
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

    from app.main import create_app

    app = create_app()

    # Rate limiting is process-global; keep tests independent.
    from app.routes import auth as auth_routes

    auth_routes.reset_rate_limits()

    yield app, factory

    await engine.dispose()
    session_mod._session_factory = None


@pytest.fixture
async def anon(auth_app):
    app, _factory = auth_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


@pytest.fixture
async def setup_token(auth_app):
    app, factory = auth_app
    from packages.auth import admin_accounts

    async with factory() as s:
        issued = await admin_accounts.issue_setup_token(s)
    return issued.raw_token


@pytest.fixture
async def admin_session(auth_app):
    """A client signed in as a freshly created administrator."""
    app, factory = auth_app
    await create_admin_account(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200, r.text
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        yield c


# ── first-run setup ────────────────────────────────────────────────────────


async def test_status_reports_uninitialized(auth_app, anon):
    r = await anon.get("/api/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert body["initialized"] is False
    assert "8" in body["password_policy"]


async def test_setup_requires_a_token(auth_app, anon):
    r = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": "",
    })
    assert r.status_code == 403
    assert "setup token" in r.json()["error"]["message"].lower()


async def test_setup_rejects_unknown_token(auth_app, anon):
    r = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": "not-a-real-token",
    })
    assert r.status_code == 403


async def test_setup_creates_administrator_and_signs_in(auth_app, anon, setup_token):
    r = await anon.post("/api/auth/setup", json={
        "username": "operator", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": setup_token,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "operator"
    assert body["authenticated"] is True
    assert body["csrf_token"]

    # Session cookie is HttpOnly + SameSite, and immediately usable.
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.lower() or "samesite=lax" in cookie.lower()
    me = await anon.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "operator"


async def test_setup_token_is_single_use(auth_app, anon, setup_token):
    first = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": setup_token,
    })
    assert first.status_code == 201

    async with AsyncClient(
        transport=ASGITransport(app=auth_app[0]), base_url="http://t"
    ) as second:
        r = await second.post("/api/auth/setup", json={
            "username": "intruder", "password": ADMIN_PASSWORD,
            "confirm_password": ADMIN_PASSWORD, "setup_token": setup_token,
        })
    assert r.status_code == 403


async def test_setup_disabled_once_initialized(admin_session, setup_token):
    r = await admin_session.post("/api/auth/setup", json={
        "username": "second", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": setup_token,
    })
    assert r.status_code == 403
    assert "already exists" in r.json()["error"]["message"]


async def test_setup_rejects_short_password(auth_app, anon, setup_token):
    r = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": "short12",
        "confirm_password": "short12", "setup_token": setup_token,
    })
    assert r.status_code == 422
    assert "at least 8 characters" in r.json()["error"]["message"]


async def test_setup_accepts_eight_characters_without_composition(auth_app, anon, setup_token):
    """No character-class rules: a plain 8-character password is valid."""
    r = await anon.post("/api/auth/setup", json={
        "username": "operator", "password": "abcd1234",
        "confirm_password": "abcd1234", "setup_token": setup_token,
    })
    assert r.status_code == 201, r.text


async def test_setup_rejects_mismatched_confirmation(auth_app, anon, setup_token):
    r = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD + "x", "setup_token": setup_token,
    })
    assert r.status_code == 422
    assert "do not match" in r.json()["error"]["message"]


async def test_concurrent_setup_creates_exactly_one_administrator(auth_app):
    """Two simultaneous setups with valid tokens: one wins, the other is told
    the installation is already initialized. The UNIQUE singleton is what makes
    this true even if both pass the 'does an admin exist?' check."""
    app, factory = auth_app
    from sqlalchemy import func, select

    from packages.auth import admin_accounts
    from packages.db.models.admin import AdminAccount

    async with factory() as s:
        # Re-issuing invalidates any earlier token, so mint one through the
        # real path and add a second live row explicitly.
        t2 = (await admin_accounts.issue_setup_token(s)).raw_token
        from packages.auth.sessions import hash_session_token
        from packages.db.models.admin import SetupToken

        row = SetupToken(
            token_hash=hash_session_token("explicit-second"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        s.add(row)
        await s.commit()

    async def attempt(token: str, username: str):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/auth/setup", json={
                "username": username, "password": ADMIN_PASSWORD,
                "confirm_password": ADMIN_PASSWORD, "setup_token": token,
            })

    results = await asyncio.gather(
        attempt(t2, "first"),
        attempt("explicit-second", "second"),
        return_exceptions=True,
    )
    codes = sorted(getattr(r, "status_code", 500) for r in results)
    assert codes[0] == 201, results
    assert all(c in (201, 403) for c in codes), codes

    async with factory() as s:
        count = (
            await s.execute(select(func.count()).select_from(AdminAccount))
        ).scalar_one()
    assert count == 1


async def test_setup_token_expires(auth_app, anon):
    app, factory = auth_app
    from packages.auth.sessions import hash_session_token
    from packages.db.models.admin import SetupToken

    async with factory() as s:
        s.add(SetupToken(
            token_hash=hash_session_token("expired-token"),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ))
        await s.commit()

    r = await anon.post("/api/auth/setup", json={
        "username": "admin", "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD, "setup_token": "expired-token",
    })
    assert r.status_code == 403
    assert "expired" in r.json()["error"]["message"]


async def test_issuing_a_new_setup_token_invalidates_the_old(auth_app, setup_token):
    app, factory = auth_app
    from packages.auth import admin_accounts

    async with factory() as s:
        await admin_accounts.issue_setup_token(s)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/setup", json={
            "username": "admin", "password": ADMIN_PASSWORD,
            "confirm_password": ADMIN_PASSWORD, "setup_token": setup_token,
        })
    assert r.status_code == 403


async def test_status_does_not_leak_the_username(auth_app, anon, admin_session):
    r = await anon.get("/api/auth/status")
    body = r.json()
    assert body["initialized"] is True
    assert ADMIN_USERNAME not in str(body)


# ── login / logout ─────────────────────────────────────────────────────────


async def test_login_with_correct_credentials(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    r = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


async def test_login_wrong_password_is_generic(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    r = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": "wrong wrong wrong",
    })
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid username or password."


async def test_login_unknown_user_is_indistinguishable(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    unknown = await anon.post("/api/auth/login", json={
        "username": "no-such-user", "password": ADMIN_PASSWORD,
    })
    wrong = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": "wrong wrong wrong",
    })
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


async def test_login_before_setup_is_generic(auth_app, anon):
    r = await anon.post("/api/auth/login", json={
        "username": "admin", "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid username or password."


async def test_logout_revokes_the_session(auth_app, admin_session):
    assert (await admin_session.get("/api/auth/me")).status_code == 200
    r = await admin_session.post("/api/auth/logout")
    assert r.status_code == 204
    assert (await admin_session.get("/api/auth/me")).status_code == 401


async def test_logout_requires_a_session(auth_app, anon):
    r = await anon.post("/api/auth/logout")
    assert r.status_code == 401


async def test_logout_requires_csrf(admin_session):
    admin_session.headers.pop("x-csrf-token", None)
    r = await admin_session.post("/api/auth/logout")
    assert r.status_code == 403


# ── CSRF ───────────────────────────────────────────────────────────────────


async def test_admin_write_without_csrf_is_refused(admin_session):
    admin_session.headers.pop("x-csrf-token", None)
    r = await admin_session.post("/v1/keys", json={"name": "x"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["error"]["message"]


async def test_admin_write_with_wrong_csrf_is_refused(admin_session):
    admin_session.headers["x-csrf-token"] = "not-the-token"
    r = await admin_session.post("/v1/keys", json={"name": "x"})
    assert r.status_code == 403


async def test_admin_read_does_not_require_csrf(admin_session):
    admin_session.headers.pop("x-csrf-token", None)
    assert (await admin_session.get("/v1/keys")).status_code == 200
    assert (await admin_session.get("/v1/providers")).status_code == 200


async def test_csrf_token_is_bound_to_the_session(auth_app, anon, admin_session):
    """A token from session A must not authorize a request on session B."""
    app, factory = auth_app
    other = (await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })).json()["csrf_token"]

    admin_session.headers["x-csrf-token"] = other
    r = await admin_session.post("/v1/keys", json={"name": "cross"})
    assert r.status_code == 403


# ── session lifecycle ──────────────────────────────────────────────────────


async def test_session_cookie_is_httponly_and_samesite(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    r = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("geekcubo_admin_session="))
    assert "HttpOnly" in session_cookie
    assert "samesite=lax" in session_cookie.lower()


async def test_expired_session_is_rejected(auth_app, admin_session):
    app, factory = auth_app
    from sqlalchemy import update

    from packages.db.models.admin import AdminSession

    async with factory() as s:
        await s.execute(update(AdminSession).values(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        ))
        await s.commit()

    r = await admin_session.get("/api/auth/me")
    assert r.status_code == 401
    assert "expired" in r.json()["error"]["message"].lower()


async def test_idle_session_is_rejected(auth_app, admin_session):
    app, factory = auth_app
    from sqlalchemy import update

    from packages.db.models.admin import AdminSession

    async with factory() as s:
        await s.execute(update(AdminSession).values(
            last_seen_at=datetime.now(timezone.utc) - timedelta(hours=3)
        ))
        await s.commit()

    assert (await admin_session.get("/api/auth/me")).status_code == 401


async def test_revoked_session_is_rejected(auth_app, admin_session):
    app, factory = auth_app
    from sqlalchemy import update

    from packages.db.models.admin import AdminSession

    async with factory() as s:
        await s.execute(update(AdminSession).values(
            revoked_at=datetime.now(timezone.utc)
        ))
        await s.commit()

    assert (await admin_session.get("/api/auth/me")).status_code == 401


async def test_forged_cookie_is_rejected(auth_app, anon):
    anon.cookies.set("geekcubo_admin_session", "made-up-token-value")
    assert (await anon.get("/api/auth/me")).status_code == 401


async def test_session_ids_are_unpredictable(auth_app):
    app, factory = auth_app
    await create_admin_account(factory)
    tokens = set()
    for _ in range(5):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/api/auth/login", json={
                "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
            })
            tokens.add(c.cookies["geekcubo_admin_session"])
            assert r.json()["csrf_token"] not in tokens
    assert len(tokens) == 5
    for tok in tokens:
        assert len(tok) >= 40  # ~256 bits, urlsafe-encoded


async def test_session_stores_only_a_hash(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })
    raw = anon.cookies["geekcubo_admin_session"]

    from sqlalchemy import select

    from packages.db.models.admin import AdminSession

    async with factory() as s:
        rows = (await s.execute(select(AdminSession))).scalars().all()
    assert rows
    for row in rows:
        assert row.token_hash != raw
        assert raw not in (row.token_hash or "")


async def test_session_survives_process_restart(tmp_sqlite_url, monkeypatch, isolated_env):
    """Sessions are rows, not in-memory state: a restart keeps them valid."""
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

    await create_admin_account(factory)

    from app.main import create_app

    app1 = create_app()
    async with AsyncClient(transport=ASGITransport(app=app1), base_url="http://t") as c:
        await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        cookie = c.cookies["geekcubo_admin_session"]

    app2 = create_app()  # "restart"
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://t") as c:
        c.cookies.set("geekcubo_admin_session", cookie)
        r = await c.get("/api/auth/me")
    assert r.status_code == 200
    await engine.dispose()
    session_mod._session_factory = None


# ── password change ────────────────────────────────────────────────────────


async def test_change_password_updates_and_keeps_current_session(auth_app, admin_session):
    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "an entirely different passphrase",
        "confirm_password": "an entirely different passphrase",
    })
    assert r.status_code == 200, r.text
    assert r.json()["revoked_other_sessions"] is True

    # This device stays signed in.
    assert (await admin_session.get("/api/auth/me")).status_code == 200


async def test_change_password_rejects_wrong_current(auth_app, admin_session):
    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": "not the password",
        "new_password": "an entirely different passphrase",
        "confirm_password": "an entirely different passphrase",
    })
    assert r.status_code == 403
    assert "incorrect" in r.json()["error"]["message"].lower()


async def test_change_password_rejects_weak_new_password(admin_session):
    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "short12",
        "confirm_password": "short12",
    })
    assert r.status_code == 422
    assert "at least 8 characters" in r.json()["error"]["message"]


async def test_change_password_rejects_mismatch(admin_session):
    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "an entirely different passphrase",
        "confirm_password": "a different phrase entirely",
    })
    assert r.status_code == 422


async def test_change_password_rejects_reuse(admin_session):
    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD,
    })
    assert r.status_code == 422
    assert "differ" in r.json()["error"]["message"]


async def test_change_password_revokes_other_sessions(auth_app, admin_session):
    app, factory = auth_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as other:
        await other.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        assert (await other.get("/api/auth/me")).status_code == 200

        await admin_session.post("/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "an entirely different passphrase",
            "confirm_password": "an entirely different passphrase",
        })

        assert (await other.get("/api/auth/me")).status_code == 401


async def test_old_password_stops_working_after_change(auth_app, admin_session):
    app, _factory = auth_app
    await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "an entirely different passphrase",
        "confirm_password": "an entirely different passphrase",
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        old = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        new = await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "an entirely different passphrase",
        })
    assert old.status_code == 401
    assert new.status_code == 200


async def test_password_change_does_not_touch_api_keys(auth_app, admin_session):
    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    app, factory = auth_app
    created = (await admin_session.post("/v1/keys", json={"name": "svc"})).json()

    async with factory() as s:
        before = (await s.execute(select(ApiKey))).scalars().all()
        snapshot = [(r.id, r.key_hash, r.is_active) for r in before]

    await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "an entirely different passphrase",
        "confirm_password": "an entirely different passphrase",
    })

    async with factory() as s:
        after = (await s.execute(select(ApiKey))).scalars().all()
        assert [(r.id, r.key_hash, r.is_active) for r in after] == snapshot

    # And the key still authenticates inference.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t",
        headers={"Authorization": f"Bearer {created['api_key']}"},
    ) as k:
        assert (await k.get("/v1/models")).status_code == 200


# ── session management endpoints ───────────────────────────────────────────


async def test_sessions_listing_marks_current(admin_session):
    r = await admin_session.get("/api/auth/sessions")
    assert r.status_code == 200
    body = r.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["current"] is True
    assert body["account"]["username"] == ADMIN_USERNAME


async def test_revoke_others_keeps_current(auth_app, admin_session):
    app, _factory = auth_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as other:
        await other.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
        })
        r = await admin_session.post("/api/auth/sessions/revoke-others")
        assert r.status_code == 200
        assert r.json()["revoked"] == 1
        assert (await other.get("/api/auth/me")).status_code == 401
        assert (await admin_session.get("/api/auth/me")).status_code == 200


async def test_sessions_listing_never_leaks_hashes(admin_session):
    r = await admin_session.get("/api/auth/sessions")
    assert "token_hash" not in r.text
    assert "csrf_token" not in r.text
    assert "password_hash" not in r.text


# ── rate limiting ──────────────────────────────────────────────────────────


async def test_repeated_failures_are_throttled(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)

    codes = []
    for _ in range(10):
        r = await anon.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "wrong wrong wrong",
        })
        codes.append(r.status_code)
    assert 429 in codes, codes

    # Even the CORRECT password is refused while the window is closed: the
    # limit is on the identity, not on the guess.
    blocked = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })
    assert blocked.status_code == 429
    assert "reset-password" in blocked.json()["error"]["message"]


async def test_rate_limit_is_per_username(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    for _ in range(10):
        await anon.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "wrong wrong wrong",
        })
    other = await anon.post("/api/auth/login", json={
        "username": "someone-else", "password": "wrong wrong wrong",
    })
    assert other.status_code == 401  # not throttled by the first identity


async def test_throttle_clears_after_success(auth_app, anon):
    app, factory = auth_app
    await create_admin_account(factory)
    from app.routes import auth as auth_routes

    auth_routes.reset_rate_limits()
    good = await anon.post("/api/auth/login", json={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    })
    assert good.status_code == 200


# ── local recovery ─────────────────────────────────────────────────────────


async def test_cli_reset_password_changes_login_and_revokes_sessions(
    auth_app, admin_session
):
    app, factory = auth_app
    from packages.auth import admin_accounts

    r = await admin_session.post("/api/auth/change-password", json={
        "current_password": ADMIN_PASSWORD,
        "new_password": "an entirely different passphrase",
        "confirm_password": "an entirely different passphrase",
    })
    assert r.status_code == 200

    async with factory() as s:
        await admin_accounts.reset_password_locally(
            s, username=None, new_password="recovered by the operator"
        )

    # Every session is gone, including the one that just changed the password.
    assert (await admin_session.get("/api/auth/me")).status_code == 401

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "an entirely different passphrase",
        })).status_code == 401
        assert (await c.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": "recovered by the operator",
        })).status_code == 200


async def test_cli_reset_marks_the_account(auth_app, admin_session):
    app, factory = auth_app
    from packages.auth import admin_accounts

    async with factory() as s:
        admin = await admin_accounts.reset_password_locally(
            s, username=ADMIN_USERNAME, new_password="recovered by the operator"
        )
        assert admin.password_reset_at is not None


async def test_cli_reset_rejects_wrong_username(auth_app, admin_session):
    app, factory = auth_app
    from packages.auth import admin_accounts

    async with factory() as s:
        with pytest.raises(admin_accounts.SetupError):
            await admin_accounts.reset_password_locally(
                s, username="someone-else", new_password="recovered by the operator"
            )


async def test_cli_reset_does_not_touch_api_keys(auth_app, admin_session):
    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    app, factory = auth_app
    await admin_session.post("/v1/keys", json={"name": "durable"})
    async with factory() as s:
        before = [(r.id, r.key_hash) for r in (await s.execute(select(ApiKey))).scalars()]

    from packages.auth import admin_accounts

    async with factory() as s:
        await admin_accounts.reset_password_locally(
            s, username=None, new_password="recovered by the operator"
        )
        after = [(r.id, r.key_hash) for r in (await s.execute(select(ApiKey))).scalars()]
    assert after == before
