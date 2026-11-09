"""Quality page: AA key storage and provenance.

Covers the dashboard-saved key (encrypted at rest, masked on read, taking
precedence over the environment) and the status block that tells the page
where its numbers came from.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def client(env):
    c, _up, _ = env
    return c


def _clear_settings_cache() -> None:
    """get_settings is lru_cached, so a monkeypatched env var is invisible
    until the cache is dropped."""
    from app import config as cfg

    cfg.get_settings.cache_clear()


async def test_key_status_reports_missing_when_nothing_configured(client):
    body = (await client.get("/v1/quality/key")).json()
    assert body["configured"] is False
    assert body["origin"] == "missing"
    assert body["key_prefix"] is None
    assert body["can_clear"] is False


async def test_saved_key_is_masked_and_never_echoed(client):
    secret = "aa-test-secret-value-1234567890"
    r = await client.put("/v1/quality/key", json={"api_key": secret, "daily_limit": 100})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["configured"] is True
    assert body["origin"] == "stored"
    assert body["can_clear"] is True
    assert body["recorded_daily_limit"] == 100
    # The full key must not appear anywhere in the response.
    assert secret not in r.text
    assert body["key_prefix"] is not None and "..." in body["key_prefix"]


async def test_saved_key_is_encrypted_at_rest(client, env):
    from sqlalchemy import select

    from packages.db import session as session_mod
    from packages.db.models.quality_settings import QualitySettings

    secret = "aa-plaintext-probe-abcdefghijkl"
    await client.put("/v1/quality/key", json={"api_key": secret})

    async with session_mod._session_factory() as db:
        row = (
            await db.execute(
                select(QualitySettings).where(QualitySettings.workspace_id == "default")
            )
        ).scalar_one()
    assert row.encrypted_api_key is not None
    assert secret.encode() not in row.encrypted_api_key


async def test_saved_key_takes_precedence_over_environment(client, monkeypatch):
    from packages.litellm_adapter.quality_index import resolve_aa_api_key

    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", "from-environment")
    _clear_settings_cache()
    stored = "from-dashboard-value-9999"
    await client.put("/v1/quality/key", json={"api_key": stored})

    from packages.db import session as session_mod

    async with session_mod._session_factory() as db:
        key, origin = await resolve_aa_api_key(db, "default")
    assert origin == "stored"
    assert key == stored


async def test_clearing_falls_back_to_environment(client, monkeypatch):
    from packages.litellm_adapter.quality_index import resolve_aa_api_key

    await client.put("/v1/quality/key", json={"api_key": "stored-then-cleared-1234"})
    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", "env-fallback-key")
    _clear_settings_cache()

    body = (await client.delete("/v1/quality/key")).json()
    assert body["origin"] == "env"
    assert body["can_clear"] is False

    from packages.db import session as session_mod

    async with session_mod._session_factory() as db:
        key, origin = await resolve_aa_api_key(db, "default")
    assert origin == "env"
    assert key == "env-fallback-key"


async def test_rejects_empty_key(client):
    r = await client.put("/v1/quality/key", json={"api_key": ""})
    assert r.status_code == 422


async def test_status_reports_endpoint_and_documented_limit(client):
    body = (await client.get("/v1/quality")).json()
    index = body["aa_index"]
    # The supported Free V2 endpoint, never the retired /api/v2/data/ family.
    assert index["endpoint"] == "https://artificialanalysis.ai/api/v2/language/models/free"
    assert "/api/v2/data/" not in index["endpoint"]
    assert index["documented_daily_limit"] == 100


async def test_key_endpoints_require_admin_session(env):
    """An inference key must not be able to read or write the AA key."""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": "Bearer sk-geek-not-a-real-key"},
    ) as c:
        assert (await c.get("/v1/quality/key")).status_code == 401
        assert (await c.put("/v1/quality/key", json={"api_key": "x" * 20})).status_code == 401


async def test_key_status_includes_connection_health_fields(client):
    body = (await client.get("/v1/quality/key")).json()
    assert body["connection_status"] == "not_configured"
    assert body["last_sync_at"] is None
    assert body["last_error_code"] is None
    assert body["last_error_detail"] is None


async def test_save_then_replace_preserves_only_new_key(client, env):
    from sqlalchemy import select

    from packages.db import session as session_mod
    from packages.db.models.quality_settings import QualitySettings

    first = "aa-first-secret-123456789012"
    second = "aa-second-secret-987654321098"
    assert (await client.put("/v1/quality/key", json={"api_key": first})).status_code == 200
    body = (await client.put("/v1/quality/key", json={"api_key": second})).json()
    assert body["key_prefix"] != first
    # The full new key never appears; the stored ciphertext is not the old key.
    assert first not in body["key_prefix"]

    from packages.auth.encryption import decrypt_credential

    async with session_mod._session_factory() as db:
        row = (await db.execute(select(QualitySettings))).scalar_one()
    assert decrypt_credential(row.encrypted_api_key) == second


async def test_test_connection_reports_not_configured(client):
    r = await client.post("/v1/quality/key/test")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["status"] == "not_configured"


async def test_test_connection_classifies_http_errors(client, env, monkeypatch):
    """A bad key must yield 'invalid_key' without echoing the key or the body."""
    import httpx

    secret = "aa-bad-key-0000111122223333"
    await client.put("/v1/quality/key", json={"api_key": secret})

    # Point the fetch at a fake endpoint and force a 401 by raising from httpx.
    orig = httpx.AsyncClient.get

    async def fake_get(self, url, **kwargs):
        class Resp:
            status_code = 401
            def raise_for_status(self):
                raise httpx.HTTPStatusError("401", request=kwargs, response=self)
        return Resp()

    httpx.AsyncClient.get = fake_get
    try:
        r = await client.post("/v1/quality/key/test")
    finally:
        httpx.AsyncClient.get = orig

    body = r.json()
    assert body["status"] == "invalid_key"
    assert secret not in r.text


async def test_test_connection_does_not_modify_stored_key(client, env, monkeypatch):
    from sqlalchemy import select

    from packages.auth.encryption import decrypt_credential
    from packages.db import session as session_mod
    from packages.db.models.quality_settings import QualitySettings

    secret = "aa-untouched-9999000011112222"
    await client.put("/v1/quality/key", json={"api_key": secret})

    async def bad(self, url, **kwargs):
        raise httpx.ConnectError("boom")
    import httpx
    orig = httpx.AsyncClient.get
    httpx.AsyncClient.get = bad
    try:
        r = await client.post("/v1/quality/key/test")
    finally:
        httpx.AsyncClient.get = orig
    assert r.json()["status"] == "connection_failed"

    async with session_mod._session_factory() as db:
        row = (await db.execute(select(QualitySettings))).scalar_one()
    assert decrypt_credential(row.encrypted_api_key) == secret


async def test_remove_key_clears_credential(client, env):
    from sqlalchemy import select

    from packages.db import session as session_mod
    from packages.db.models.quality_settings import QualitySettings

    await client.put("/v1/quality/key", json={"api_key": "aa-to-be-removed-4444"})
    body = (await client.delete("/v1/quality/key")).json()
    assert body["configured"] is False
    assert body["connection_status"] == "not_configured"

    async with session_mod._session_factory() as db:
        row = (await db.execute(select(QualitySettings))).scalar_one()
    assert row.encrypted_api_key is None
    assert row.key_prefix is None


async def test_error_is_recorded_on_failed_refresh(client, env, monkeypatch):
    """A failed fetch persists last_error_code/detail, never the key."""
    import httpx

    secret = "aa-refresh-fail-555566667777"
    await client.put("/v1/quality/key", json={"api_key": secret})

    orig = httpx.AsyncClient.get
    async def rate_limited(self, url, **kwargs):
        class Resp:
            status_code = 429
            def raise_for_status(self):
                raise httpx.HTTPStatusError("429", request=kwargs, response=self)
        return Resp()
    httpx.AsyncClient.get = rate_limited
    try:
        # Force a fresh fetch through the full quality path.
        await client.post("/v1/quality/refresh")
    finally:
        httpx.AsyncClient.get = orig

    status = (await client.get("/v1/quality/key")).json()
    # A sync failure is reported as sync state; it must not masquerade as a
    # connection-test result (no test has run for this key).
    assert status["sync_status"] == "sync_failed"
    assert status["connection_status"] == "key_configured"
    assert status["last_error_code"] == "rate_limited"
    assert secret not in (status["last_error_detail"] or "")


# ── V2 migration: connection test vs. synchronization ─────────────────

import httpx as _httpx  # noqa: E402

_REAL_ASYNC_CLIENT = _httpx.AsyncClient


def _mock_aa(monkeypatch, handler):
    """Route every httpx.AsyncClient used by the app through a MockTransport."""
    import httpx

    # Always wrap the original class, so calling this twice in one test
    # replaces the mock instead of nesting factories.
    real = _REAL_ASYNC_CLIENT
    seen: list = []

    def _wrapped(request):
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)

    def _factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return seen


def _free_body(n: int = 2, *, total_pages: int = 1):
    from tests.unit.test_aa_v2_api import envelope, free_model

    return envelope(
        [free_model(f"Model {i}", f"model-{i}", 40.0 + i, 50.0, 1.0) for i in range(n)],
        total_pages=total_pages,
    )


async def test_stored_key_alone_is_not_connected(client):
    """Saving a key never claims a verified connection."""
    body = (await client.put("/v1/quality/key", json={"api_key": "aa-untested-key-123456"})).json()
    assert body["connection_status"] == "key_configured"
    assert body["sync_status"] == "never_synced"
    assert body["last_test_at"] is None


async def test_connection_test_uses_free_endpoint_and_records_success(client, monkeypatch):
    import httpx

    secret = "aa-good-key-0000aaaa1111"
    await client.put("/v1/quality/key", json={"api_key": secret})
    seen = _mock_aa(monkeypatch, lambda req: httpx.Response(
        200, json=_free_body(3, total_pages=4), headers={"x-aa-tier": "free"}))

    r = await client.post("/v1/quality/key/test")
    body = r.json()
    assert body["status"] == "connected"
    assert body["tier"] == "free"
    assert body["model_count"] == 3
    assert body["endpoint"].endswith("/api/v2/language/models/free")
    assert secret not in r.text
    # Exactly one request: only the first page is fetched by a test.
    assert len(seen) == 1
    assert str(seen[0].url) == "https://artificialanalysis.ai/api/v2/language/models/free"
    assert seen[0].headers["x-api-key"] == secret

    status = (await client.get("/v1/quality/key")).json()
    assert status["connection_status"] == "connected"
    assert status["last_test_status"] == "connected"
    assert status["last_test_ok_at"] is not None
    assert status["tier"] == "free"
    # A connection test is not a sync.
    assert status["sync_status"] == "never_synced"
    assert status["last_sync_at"] is None


@pytest.mark.parametrize(
    "status_code,expected",
    [(401, "invalid_key"), (403, "insufficient_tier"), (410, "endpoint_retired"),
     (429, "rate_limited"), (503, "server_error")],
)
async def test_connection_test_failure_codes(client, monkeypatch, status_code, expected):
    import httpx

    secret = "aa-failing-key-2222bbbb3333"
    await client.put("/v1/quality/key", json={"api_key": secret})
    _mock_aa(monkeypatch, lambda req: httpx.Response(status_code, json={"error": "upstream says no"}))

    r = await client.post("/v1/quality/key/test")
    body = r.json()
    assert body["status"] == expected
    assert secret not in r.text
    assert "upstream says no" not in r.text

    status = (await client.get("/v1/quality/key")).json()
    assert status["connection_status"] == "connection_failed"
    assert status["last_test_status"] == expected
    assert status["last_test_ok_at"] is None


async def test_connection_test_timeout_and_malformed(client, monkeypatch):
    import httpx

    await client.put("/v1/quality/key", json={"api_key": "aa-flaky-key-44445555"})

    def timeout(req):
        raise httpx.ConnectTimeout("slow", request=req)

    _mock_aa(monkeypatch, timeout)
    assert (await client.post("/v1/quality/key/test")).json()["status"] == "timeout"

    _mock_aa(monkeypatch, lambda req: httpx.Response(200, json={"unexpected": True}))
    assert (await client.post("/v1/quality/key/test")).json()["status"] == "malformed_response"

    _mock_aa(monkeypatch, lambda req: httpx.Response(200, json={"tier": "free", "pagination": {}, "data": []}))
    assert (await client.post("/v1/quality/key/test")).json()["status"] == "no_data"


async def test_sync_failure_does_not_erase_verified_connection(client, monkeypatch):
    """Connected + sync failed are reported side by side."""
    import httpx

    await client.put("/v1/quality/key", json={"api_key": "aa-both-states-6666"})
    _mock_aa(monkeypatch, lambda req: httpx.Response(200, json=_free_body()))
    assert (await client.post("/v1/quality/key/test")).json()["status"] == "connected"

    _mock_aa(monkeypatch, lambda req: httpx.Response(429, json={"error": "quota"}, headers={"retry-after": "60"}))
    await client.post("/v1/quality/refresh")

    status = (await client.get("/v1/quality/key")).json()
    assert status["connection_status"] == "connected"
    assert status["sync_status"] == "sync_failed"
    assert status["last_error_code"] == "rate_limited"
    assert status["last_sync_attempt_at"] is not None


async def test_successful_sync_records_counts_and_tier(client, monkeypatch):
    import httpx

    from packages.litellm_adapter.catalog import CATALOG

    await client.put("/v1/quality/key", json={"api_key": "aa-sync-ok-7777"})
    # Use real catalog ids so matching succeeds.
    real_ids = [m.id for m in CATALOG if "/" not in m.id][:2]
    assert len(real_ids) == 2

    from tests.unit.test_aa_v2_api import envelope, free_model

    payload = envelope(
        [free_model(mid, mid, 50.0, 40.0, 1.0) for mid in real_ids]
        + [free_model("Unknown Vendor X1", "unknown-x1", 30.0, None, None)]
    )
    _mock_aa(monkeypatch, lambda req: httpx.Response(200, json=payload, headers={"x-aa-tier": "free"}))
    r = await client.post("/v1/quality/refresh")
    assert r.status_code == 200
    assert r.json()["aa_index"]["source"] == "live"

    status = (await client.get("/v1/quality/key")).json()
    assert status["sync_status"] == "synced"
    assert status["last_sync_raw_count"] == 3
    assert status["last_sync_matched_count"] >= 2
    assert status["tier"] == "free"
    assert status["last_error_code"] is None
    # Sync never fabricates a connection-test result.
    assert status["connection_status"] == "key_configured"


async def test_replacing_key_resets_connection_test(client, monkeypatch):
    import httpx

    await client.put("/v1/quality/key", json={"api_key": "aa-first-key-8888"})
    _mock_aa(monkeypatch, lambda req: httpx.Response(200, json=_free_body()))
    await client.post("/v1/quality/key/test")
    assert (await client.get("/v1/quality/key")).json()["connection_status"] == "connected"

    body = (await client.put("/v1/quality/key", json={"api_key": "aa-second-key-9999"})).json()
    assert body["connection_status"] == "key_configured"


async def test_manual_overrides_survive_failed_sync(client, monkeypatch):
    """Admin overrides keep precedence regardless of AA availability."""
    import httpx

    from packages.litellm_adapter.catalog import CATALOG

    mid = next(m.id for m in CATALOG if "/" not in m.id)
    assert (await client.put(f"/v1/quality/overrides/{mid}", json={"score": 88, "note": "own evals"})).status_code == 200
    await client.put("/v1/quality/key", json={"api_key": "aa-override-key-1010"})
    _mock_aa(monkeypatch, lambda req: httpx.Response(410, json={"error": "Gone"}))
    await client.post("/v1/quality/refresh")

    body = (await client.get("/v1/quality")).json()
    row = next(r for r in body["models"] if r["id"] == mid)
    assert row["manual_score"] == 88
    assert row["effective_score"] == 88
    overrides = (await client.get("/v1/quality/overrides")).json()["overrides"]
    assert any(o["model_id"] == mid and o["note"] == "own evals" for o in overrides)
    assert (await client.get("/v1/quality/key")).json()["last_error_code"] == "endpoint_retired"
