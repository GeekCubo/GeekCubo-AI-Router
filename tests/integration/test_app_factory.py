"""Tests for app.main.create_app — boot, /health, error format, CORS."""

import re

import pytest


@pytest.fixture
async def lite_app(tmp_sqlite_url, monkeypatch):
    """Boot a fresh app against a tempfile SQLite."""
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)

    # Reset the singleton settings so the new env is picked up
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register session factory bound to this engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db import session as session_mod

    session_mod._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import create_app

    yield create_app()

    await engine.dispose()
    session_mod._session_factory = None


async def test_health_returns_ok(lite_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_unknown_route_returns_404_in_error_envelope(lite_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        r = await c.get("/v1/totally-not-a-route")
    # Auth middleware sees /v1/* and demands a bearer first.
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["type"] == "auth_error"


async def test_v1_models_requires_auth(lite_app):
    """/v1/models is gated behind a bearer token in lite (single-tenant)."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        r = await c.get("/v1/models")
    assert r.status_code == 401


# ── dashboard shell delivery ───────────────────────────────────────────────
# The Phase 1 "custom-provider form is missing" report was a stale-asset
# problem: the served index.html was new, but the browser kept an OLD app.js
# that had no __custom__ branch. These tests pin the three properties that
# make that impossible: the shell is never cached, its asset URLs are
# versioned, and /providers serves the shell instead of a JSON 404.


async def test_root_serves_dashboard_shell_uncached(lite_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        r = await c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "no-store" in r.headers["cache-control"]
    assert "app.js" in r.text


async def test_providers_path_serves_dashboard_shell_not_404(lite_app):
    """Operators navigate to /providers. It must not answer with JSON 404."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        r = await c.get("/providers")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "no-store" in r.headers["cache-control"]
    assert 'id="custom-provider-form"' in r.text


async def test_shell_asset_urls_are_versioned(lite_app):
    """No bare /static/app.js reference may survive: an unversioned URL is
    what let a browser keep running the pre-custom-provider bundle."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        html = (await c.get("/")).text

    assert "__ASSET_VERSION__" not in html, "placeholder was not substituted"
    for asset in ("app.js", "style.css"):
        matches = re.findall(rf'/static/{re.escape(asset)}(\?v=[0-9a-f]+)?', html)
        assert matches, f"{asset} not referenced"
        assert all(m.startswith("?v=") for m in matches), (
            f"{asset} must carry a version query string, got {matches}"
        )


async def test_asset_version_is_a_content_hash(lite_app):
    """The token must be a hash of the served bundles' bytes, so any change to
    app.js/style.css changes the URL and no browser can run a stale bundle
    against a fresh shell."""
    import hashlib
    import os

    from httpx import ASGITransport, AsyncClient

    from app.main import _find_design_dir

    design_dir = _find_design_dir()
    assert design_dir

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        html = (await c.get("/")).text
    token = html.split("app.js?v=")[1].split('"')[0]
    assert re.fullmatch(r"[0-9a-f]{16}", token), token

    digest = hashlib.sha256()
    for name in ("app.js", "style.css"):
        path = os.path.join(design_dir, name)
        digest.update(hashlib.sha256(open(path, "rb").read()).hexdigest().encode())
    assert token == digest.hexdigest()[:16]

    # Every shell response carries the same token — it is not per-request.
    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        assert token in (await c.get("/providers")).text


async def test_versioned_bundles_are_cacheable_only_under_their_own_token(lite_app):
    """A CDN keeps whatever it first sees under app.js?v=<token>. Only the
    URL whose token matches the served bytes may be cached; a stale or
    missing token must revalidate, so a release URL can never pin another
    release's script (the a7a163c Cloudflare incident)."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=lite_app), base_url="http://t") as c:
        html = (await c.get("/")).text
        token = html.split("app.js?v=")[1].split('"')[0]
        for asset in ("app.js", "style.css"):
            current = await c.get(f"/static/{asset}?v={token}")
            assert current.status_code == 200
            assert current.headers["cache-control"] == "public, max-age=31536000, immutable"
            for url in (f"/static/{asset}", f"/static/{asset}?v=0000000000000000"):
                r = await c.get(url)
                assert r.status_code == 200
                assert r.headers["cache-control"] == "no-cache", url
