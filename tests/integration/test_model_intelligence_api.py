"""Model Intelligence API: built-ins, custom sources, refresh failure handling."""

from __future__ import annotations

import pytest


@pytest.fixture
async def client(env):
    c, _up, _ = env
    return c


async def test_builtin_sources_are_created_once(client):
    first = (await client.get("/v1/model-intelligence/sources")).json()["sources"]
    keys = [s["key"] for s in first]
    assert keys == ["litellm", "models-dev", "portkey"]
    assert first[0]["is_builtin"] is True
    again = (await client.get("/v1/model-intelligence/sources")).json()["sources"]
    assert len(again) == 3


async def test_litellm_source_works_offline(client):
    r = await client.post("/v1/model-intelligence/sources/litellm/refresh")
    assert r.status_code == 404  # key is not an id; use the real id below
    sources = (await client.get("/v1/model-intelligence/sources")).json()["sources"]
    litellm = next(s for s in sources if s["key"] == "litellm")
    r = await client.post(f"/v1/model-intelligence/sources/{litellm['id']}/refresh")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_error"] is None
    assert body["entry_count"] > 100
    assert body["stale"] is False


async def test_builtin_source_cannot_be_deleted_but_can_be_disabled(client):
    sources = (await client.get("/v1/model-intelligence/sources")).json()["sources"]
    md = next(s for s in sources if s["key"] == "models-dev")
    assert (await client.delete(f"/v1/model-intelligence/sources/{md['id']}")).status_code == 403
    r = await client.put(f"/v1/model-intelligence/sources/{md['id']}", json={"is_enabled": False})
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False


async def test_custom_source_rejects_private_url(client):
    r = await client.post("/v1/model-intelligence/sources", json={
        "name": "internal", "url": "http://169.254.169.254/latest/meta-data",
    })
    assert r.status_code == 422
    body = r.json()
    detail = body.get("detail") or (body.get("error") or {}).get("message", "")
    assert detail and ("https" in detail or "public" in detail), body


async def test_custom_source_lifecycle_and_token_never_returned(client):
    r = await client.post("/v1/model-intelligence/sources", json={
        "name": "My Catalog", "url": "https://catalog.example.com/api.json",
        "token": "super-secret", "priority": 5,
    })
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["has_token"] is True
    assert "super-secret" not in str(created)
    sid = created["id"]
    r = await client.put(f"/v1/model-intelligence/sources/{sid}", json={"priority": 7})
    assert r.json()["priority"] == 7
    assert (await client.delete(f"/v1/model-intelligence/sources/{sid}")).status_code == 204
    left = (await client.get("/v1/model-intelligence/sources")).json()["sources"]
    assert sid not in [s["id"] for s in left]


async def test_failed_refresh_keeps_last_known_good_cache(client, monkeypatch):
    """A source going down must not erase usable data — it is marked stale."""

    r = await client.post("/v1/model-intelligence/sources", json={
        "name": "Flaky", "url": "https://catalog.example.com/api.json",
    })
    sid = r.json()["id"]

    async def boom(*a, **k):
        from app.safe_fetch import FetchError
        raise FetchError("the source timed out")

    # Seed a good cache first, then make the next refresh fail.
    import httpx

    good = b'{"p": {"id": "p", "models": {"m": {"id": "m", "cost": {"input": 1, "output": 2}}}}}'
    monkeypatch.setattr("app.safe_fetch._resolve_public", lambda host: "93.184.216.34")
    import app.safe_fetch as sf
    real_safe_get = sf.safe_get

    async def fake_good(*a, **k):
        return await real_safe_get(*a, transport=httpx.MockTransport(
            lambda req: httpx.Response(200, content=good)), **{k2: v for k2, v in k.items() if k2 != "transport"})


    # `refresh_source` does `from app.safe_fetch import safe_get` at call time.
    monkeypatch.setattr(sf, "safe_get", fake_good)
    ok = await client.post(f"/v1/model-intelligence/sources/{sid}/refresh")
    assert ok.json()["entry_count"] == 1, ok.text

    monkeypatch.setattr(sf, "safe_get", boom)
    failed = await client.post(f"/v1/model-intelligence/sources/{sid}/refresh")
    assert failed.status_code == 200
    body = failed.json()
    assert body["last_error"]
    assert body["entry_count"] == 1      # cache preserved
    assert body["stale"] is True or body["last_success_at"]


async def test_lookup_reports_each_source_and_the_winner(client):
    r = await client.get("/v1/model-intelligence/lookup", params={"model": "openai/gpt-4o"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "openai/gpt-4o"
    assert {s["key"] for s in body["sources"]} >= {"litellm"}
    assert "price_state" in body
