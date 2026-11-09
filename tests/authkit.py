"""Shared helpers for administrator-session tests.

Phase 2 moved every management route from "API key" to "administrator
session". Tests that used to send `Authorization: Bearer <seeded key>` to
`/v1/providers`, `/v1/keys`, `/v1/routing`, `/v1/analytics/*`, `/v1/quality*`
and `/v1/custom-providers*` must now sign in instead.

`admin_session()` bootstraps the single account through the real code path
(the same `create_admin` the CLI and the dashboard use) and returns a live
AsyncClient carrying the session cookie. Since the cookie is HttpOnly, httpx
stores and replays it exactly as a browser would — which is also why these
tests double as proof that cookie round-tripping works.

The CSRF token is attached once and reused: the middleware only checks it on
state-changing methods, and it is stable for the life of a session.
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "correct horse battery staple"


async def create_admin_account(factory, *, username: str = ADMIN_USERNAME,
                              password: str = ADMIN_PASSWORD):
    """Create the administrator directly (bypasses the token, which is a UI
    convenience — the CLI `setup` path has its own test)."""
    from packages.auth import admin_accounts

    async with factory() as session:
        existing = await admin_accounts.get_admin(session)
        if existing is not None:
            return existing
        issued = await admin_accounts.issue_setup_token(session)
        return await admin_accounts.create_admin(
            session, username=username, password=password,
            setup_token=issued.raw_token,
        )


async def admin_client(app, *, username: str = ADMIN_USERNAME,
                       password: str = ADMIN_PASSWORD) -> AsyncClient:
    """An AsyncClient signed in as the administrator.

    Returns the client with its session cookie jar populated and the CSRF
    token set on the default headers, so existing test bodies keep working with
    a one-line fixture change.
    """
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://t")
    r = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    if r.status_code != 200:
        await client.aclose()
        raise AssertionError(
            f"admin login failed: {r.status_code} {r.text}"
        )
    token = r.json()["csrf_token"]
    client.headers["x-csrf-token"] = token
    return client


async def signed_in(app, factory, **kwargs) -> AsyncClient:
    """Ensure the admin exists, then return a signed-in client."""
    await create_admin_account(factory, **{
        k: v for k, v in kwargs.items() if k in ("username", "password")
    })
    return await admin_client(
        app,
        username=kwargs.get("username", ADMIN_USERNAME),
        password=kwargs.get("password", ADMIN_PASSWORD),
    )


async def dual_client(app, factory, api_key: str) -> AsyncClient:
    """A client carrying BOTH an admin session and an sk-geek-* bearer key.

    Many integration tests configure something through the console (custom
    providers, routing) and then send inference traffic, using one client. The
    middleware decides which credential applies per route class, so a client
    holding both still exercises the real boundary: admin routes see only the
    cookie, inference routes see only the bearer. Separate tests assert that
    each credential alone is rejected by the other class.
    """
    client = await signed_in(app, factory)
    client.headers["Authorization"] = f"Bearer {api_key}"
    return client


class SignedInClient(AsyncClient):
    """Drop-in for `AsyncClient(transport=ASGITransport(app=app), ...)`.

    Signs in as the administrator on `__aenter__`, so fixtures written as::

        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://t",
                               headers={"Authorization": f"Bearer {key}"}) as c:

    only need the class name swapped. The bearer header is kept: inference
    routes in the same test still authenticate with it, admin routes use the
    session. Uses the process-global session factory the fixture has already
    installed (`packages.db.session._session_factory`).
    """

    async def __aenter__(self):
        await super().__aenter__()
        from packages.db import session as session_mod

        factory = session_mod._session_factory
        if factory is None:  # pragma: no cover - fixture bug
            raise RuntimeError("SignedInClient needs session_mod._session_factory set")
        await create_admin_account(factory)
        r = await self.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
        if r.status_code != 200:
            raise AssertionError(f"admin login failed: {r.status_code} {r.text}")
        self.headers["x-csrf-token"] = r.json()["csrf_token"]
        return self
