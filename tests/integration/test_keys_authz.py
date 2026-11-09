"""Key-management authorization tests.

History: this file originally proved that a *restricted* sk-geek-* key could
not mint, list or revoke keys, because an unrestricted one could — the whole
escalation class existed because an inference credential could reach
/v1/keys at all.

Phase 2 closes that at the boundary instead of case by case: /v1/keys requires
an administrator *session*, so no sk-geek-* key of any shape can manage keys.
These tests now assert the stronger property, and keep the workspace-scoping
(IDOR) guarantees that still apply to the administrator API.
"""

from contextlib import asynccontextmanager

import pytest


@pytest.fixture
async def seeded_keys(db_session):
    """Seed the workspace root key plus one restricted and one budgeted key.

    Returns (root_full_key, restricted_full_key, budgeted_full_key).
    """
    from app.seed import seed_initial_state
    from packages.auth.hashing import generate_api_key
    from packages.db.models.api_key import ApiKey

    seed = await seed_initial_state(db_session)
    assert seed.api_key is not None

    def _make(**kwargs) -> str:
        full_key, key_hash, key_prefix = generate_api_key()
        row = ApiKey(
            workspace_id="default",
            name=kwargs.pop("name", "test"),
            key_hash=key_hash,
            key_prefix=key_prefix,
            **kwargs,
        )
        db_session.add(row)
        return full_key

    # flush once so all rows land before any request reads them
    restricted = _make(name="restricted", model_allowlist=["gpt-4o-mini"])
    budgeted = _make(name="budgeted", budget_limit_cents=500)
    await db_session.commit()
    return seed.api_key, restricted, budgeted


@pytest.fixture
async def keys_app(db_session, monkeypatch):
    """FastAPI app with auth middleware, the key routes and the auth routes.

    The auth router is mounted too: these clients sign in like a real
    administrator, which is the only way to reach /v1/keys now.
    """
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    from fastapi import FastAPI

    from app.middleware.auth import AuthMiddleware
    from packages.db import session as session_mod

    class _PassthroughFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc):
            return False  # propagate, don't close — fixture owns the session

    monkeypatch.setattr(session_mod, "_session_factory", lambda: _PassthroughFactory())

    from app.routes.auth import router as auth_router
    from app.routes.keys import router as keys_router

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(auth_router)
    app.include_router(keys_router)
    return app


@asynccontextmanager
async def _admin_client(app, db_session):
    """Signed-in administrator client (session cookie + CSRF header).

    A context manager so the AsyncClient is entered exactly once: an httpx
    client cannot be used outside `async with` and then entered again.
    """
    from httpx import ASGITransport, AsyncClient

    from tests.authkit import ADMIN_PASSWORD, ADMIN_USERNAME, create_admin_account

    class _Factory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc):
            return False

    await create_admin_account(_Factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200, r.text
        c.headers["x-csrf-token"] = r.json()["csrf_token"]
        yield c


async def _client(app):
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.parametrize("which", [1, 2], ids=["allowlist-restricted", "budget-restricted"])
async def test_inference_key_cannot_create_keys(keys_app, seeded_keys, db_session, which):
    """No sk-geek-* key — restricted or not — can mint another."""
    _keys, restricted, budgeted = seeded_keys
    caller = (restricted, budgeted)[which - 1]
    async with await _client(keys_app) as c:
        r = await c.post(
            "/v1/keys",
            json={"name": "escalated"},
            headers={"Authorization": f"Bearer {caller}"},
        )
    assert r.status_code == 401
    assert "Administrator session" in r.json()["error"]["message"]

    from sqlalchemy import func, select

    from packages.db.models.api_key import ApiKey

    count = (
        await db_session.execute(select(func.count()).select_from(ApiKey))
    ).scalar_one()
    assert count == 3  # root + restricted + budgeted, nothing new


@pytest.mark.parametrize("which", [1, 2], ids=["allowlist-restricted", "budget-restricted"])
async def test_inference_key_cannot_list_keys(keys_app, seeded_keys, which):
    _keys, restricted, budgeted = seeded_keys
    caller = (restricted, budgeted)[which - 1]
    async with await _client(keys_app) as c:
        r = await c.get("/v1/keys", headers={"Authorization": f"Bearer {caller}"})
    assert r.status_code == 401


async def test_inference_key_cannot_revoke_keys(keys_app, seeded_keys, db_session):
    _root, restricted, _budgeted = seeded_keys
    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    rows = (await db_session.execute(select(ApiKey))).scalars().all()
    target_id = next(r.id for r in rows if r.name == "default")
    async with await _client(keys_app) as c:
        r = await c.delete(
            f"/v1/keys/{target_id}",
            headers={"Authorization": f"Bearer {restricted}"},
        )
    assert r.status_code == 401
    target = next(r for r in rows if r.name == "default")
    assert target.is_active  # untouched


async def test_unrestricted_inference_key_also_cannot_manage(keys_app, seeded_keys):
    """The key that used to hold full management rights (the seeded root) is
    now refused too. Administrative authority belongs to the session."""
    root, _restricted, _budgeted = seeded_keys
    h = {"Authorization": f"Bearer {root}"}
    async with await _client(keys_app) as c:
        assert (await c.get("/v1/keys", headers=h)).status_code == 401
        assert (
            await c.post("/v1/keys", json={"name": "child"}, headers=h)
        ).status_code == 401


async def test_administrator_can_manage_keys(keys_app, seeded_keys, db_session):
    async with _admin_client(keys_app, db_session) as c:
        listed = await c.get("/v1/keys")
        assert listed.status_code == 200

        created = await c.post("/v1/keys", json={"name": "child"})
        assert created.status_code == 201, created.text
        child_id = created.json()["id"]

        revoked = await c.delete(f"/v1/keys/{child_id}")
        assert revoked.status_code == 204


async def test_administrator_write_requires_csrf(keys_app, seeded_keys, db_session):
    """A session cookie alone is not enough for a state-changing call."""
    async with _admin_client(keys_app, db_session) as c:
        c.headers.pop("x-csrf-token", None)
        r = await c.post("/v1/keys", json={"name": "no-csrf"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["error"]["message"]


async def test_create_key_accepts_restrictions(keys_app, seeded_keys, db_session):
    async with _admin_client(keys_app, db_session) as c:
        r = await c.post(
            "/v1/keys",
            json={"name": "team-a", "model_allowlist": ["gpt-4o-mini"]},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["model_allowlist"] == ["gpt-4o-mini"]

    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.id == body["id"]))
    ).scalar_one()
    assert row.model_allowlist == ["gpt-4o-mini"]


# ── Workspace scoping (IDOR regression tests) ────────────────────────────


async def _make_foreign_workspace_key(db_session) -> tuple[str, str]:
    """A key belonging to a different workspace; returns (id, name)."""
    from packages.auth.hashing import generate_api_key
    from packages.db.models.api_key import ApiKey
    from packages.db.models.workspace import Workspace

    db_session.add(Workspace(id="ws-other", name="Other", slug="other"))
    await db_session.flush()

    full_key, key_hash, key_prefix = generate_api_key()
    row = ApiKey(
        workspace_id="ws-other",
        name="foreign-key",
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db_session.add(row)
    await db_session.commit()
    return row.id, full_key


async def test_list_keys_hides_other_workspaces(keys_app, seeded_keys, db_session):
    root, *_ = seeded_keys
    foreign_id, _foreign_key = await _make_foreign_workspace_key(db_session)

    async with _admin_client(keys_app, db_session) as c:
        r = await c.get("/v1/keys")

    assert r.status_code == 200
    listed_ids = {k["id"] for k in r.json()["keys"]}
    assert foreign_id not in listed_ids


async def test_revoke_rejects_other_workspaces_key(keys_app, seeded_keys, db_session):
    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    root, *_ = seeded_keys
    foreign_id, _foreign_key = await _make_foreign_workspace_key(db_session)

    async with _admin_client(keys_app, db_session) as c:
        r = await c.delete(f"/v1/keys/{foreign_id}")

    assert r.status_code == 404
    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.id == foreign_id))
    ).scalar_one()
    assert row.is_active  # untouched
