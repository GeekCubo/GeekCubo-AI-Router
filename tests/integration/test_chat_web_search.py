"""Native-Chat web search: settings, retrieval pipeline, citations, failures."""
# ruff: noqa: F811  (pytest fixture `dash_env` is imported and injected by name)
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


from unittest.mock import AsyncMock, patch

from app.web_search import SearchError, SearchOutcome, SearchResult  # noqa: E402
from tests.integration.test_dashboard_chat import dash_env  # noqa: E402,F401


def _outcome(n=2):
    o = SearchOutcome(backend="searxng", query="q", took_ms=12)
    for i in range(1, n + 1):
        o.results.append(SearchResult(
            title=f"T{i}", url=f"https://example.org/{i}", source="searxng",
            snippet=f"snippet {i}", retrieved_at="2026-01-01T00:00:00+00:00",
            citation_id=f"S{i}",
        ))
    return o


async def _make_conversation(client):
    r = await client.post("/api/chat/conversations", json={})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── settings ────────────────────────────────────────────────────────────────


async def test_search_settings_defaults_and_roundtrip(dash_env):
    client, _, _ = dash_env
    r = await client.get("/api/chat/search-settings")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "off"
    assert body["api_key_state"] == "unset"

    # Enabling without a backend is rejected.
    r = await client.put("/api/chat/search-settings", json={"mode": "manual"})
    assert r.status_code == 422

    # Brave requires a key.
    r = await client.put("/api/chat/search-settings",
                         json={"backend": "brave", "mode": "manual"})
    assert r.status_code == 422

    r = await client.put("/api/chat/search-settings",
                         json={"backend": "brave", "api_key": "brave-test-key",
                               "mode": "manual", "max_results": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key_state"] == "set"
    assert body["max_results"] == 3
    assert "brave-test-key" not in r.text  # the key never comes back

    # Clearing the key while the backend still needs it is rejected.
    r = await client.put("/api/chat/search-settings", json={"clear_api_key": True})
    assert r.status_code == 422
    # Disable first, then the clear goes through.
    r = await client.put("/api/chat/search-settings", json={"mode": "off", "clear_api_key": True})
    assert r.status_code == 200, r.text
    assert r.json()["api_key_state"] == "unset"


async def test_reserved_auto_mode_cannot_be_enabled(dash_env):
    """No automatic search planner exists, so "auto" must not be storable."""
    client, _, _ = dash_env
    r = await client.put("/api/chat/search-settings",
                         json={"backend": "brave", "api_key": "k", "mode": "manual"})
    assert r.status_code == 200, r.text
    r = await client.put("/api/chat/search-settings", json={"mode": "auto"})
    assert r.status_code == 422
    assert "reserved" in r.text.lower()
    r = await client.get("/api/chat/search-settings")
    assert r.json()["mode"] == "manual"
    # Still advertised so the UI can render it as unavailable.
    assert "auto" in r.json()["modes"]


async def test_search_settings_validation(dash_env):
    client, _, _ = dash_env
    r = await client.put("/api/chat/search-settings", json={"mode": "sometimes"})
    assert r.status_code == 422
    r = await client.put("/api/chat/search-settings", json={"backend": "bing"})
    assert r.status_code == 422
    r = await client.put("/api/chat/search-settings", json={"max_results": 999})
    assert r.status_code == 422


# ── test-connection probe ───────────────────────────────────────────────────


async def test_search_test_connection_success_and_failure(dash_env):
    client, _, _ = dash_env
    await client.put("/api/chat/search-settings",
                     json={"backend": "searxng", "service_url": "http://searxng:8080",
                           "mode": "manual"})
    with patch("app.routes.chat_search.run_search", new=AsyncMock(return_value=_outcome(1))):
        r = await client.post("/api/chat/search-settings/test")
        assert r.json()["ok"] is True
    with patch("app.routes.chat_search.run_search",
               new=AsyncMock(side_effect=SearchError("unavailable", "SearXNG is unreachable"))):
        r = await client.post("/api/chat/search-settings/test")
        body = r.json()
        assert body["ok"] is False
        assert body["code"] == "unavailable"
    r = await client.get("/api/chat/search-settings")
    assert r.json()["last_status"] == "unavailable"


# ── message-level search ────────────────────────────────────────────────────


async def test_search_request_rejected_when_disabled(dash_env):
    client, _, _ = dash_env
    cid = await _make_conversation(client)
    r = await client.post(
        f"/api/chat/conversations/{cid}/messages",
        json={"content": "hello", "stream": False, "web_search": True},
    )
    assert r.status_code == 422
    body = r.json()
    assert "Web search is off" in (body.get("detail") or body.get("error", {}).get("message", ""))


async def test_search_message_injects_context_and_stores_citations(dash_env):
    client, fake, _ = dash_env
    await client.put("/api/chat/search-settings",
                     json={"backend": "searxng", "service_url": "http://searxng:8080",
                           "mode": "manual"})
    cid = await _make_conversation(client)
    with patch("app.web_search.run_search", new=AsyncMock(return_value=_outcome(2))):
        r = await client.post(
            f"/api/chat/conversations/{cid}/messages",
            json={"content": "latest news", "model": "gpt-4o-mini", "stream": False, "web_search": True},
        )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["search_backend"] == "searxng"
    assert msg["citations"][0]["url"] == "https://example.org/1"

    # The engine received the injected, clearly-delimited context block.
    sent = fake.acompletion.call_args.kwargs["messages"]
    sys_msgs = [m for m in sent if m["role"] == "system"]
    assert sys_msgs and "[S1]" in sys_msgs[0]["content"]
    assert "untrusted" in sys_msgs[0]["content"]

    # Citations survive a reload.
    r = await client.get(f"/api/chat/conversations/{cid}")
    msgs = [m for m in r.json()["messages"] if m["role"] == "assistant"]
    assert msgs[-1]["citations"][1]["id"] == "S2"


async def test_search_failure_does_not_reach_the_model(dash_env):
    client, fake, _ = dash_env
    await client.put("/api/chat/search-settings",
                     json={"backend": "searxng", "service_url": "http://searxng:8080",
                           "mode": "manual"})
    cid = await _make_conversation(client)
    calls_before = fake.acompletion.call_count
    with patch("app.web_search.run_search",
               new=AsyncMock(side_effect=SearchError("timeout", "SearXNG did not answer in time."))):
        r = await client.post(
            f"/api/chat/conversations/{cid}/messages",
            json={"content": "q", "stream": False, "web_search": True},
        )
    assert r.status_code == 422
    body = r.json()
    assert "Search failed" in (body.get("detail") or body.get("error", {}).get("message", ""))
    assert fake.acompletion.call_count == calls_before  # no inference call


async def test_search_per_conversation_limit(dash_env):
    client, _, _ = dash_env
    await client.put("/api/chat/search-settings",
                     json={"backend": "searxng", "service_url": "http://searxng:8080",
                           "mode": "manual", "max_searches_per_conversation": 1})
    cid = await _make_conversation(client)
    with patch("app.web_search.run_search", new=AsyncMock(return_value=_outcome(1))):
        r1 = await client.post(f"/api/chat/conversations/{cid}/messages",
                               json={"content": "one", "model": "gpt-4o-mini", "stream": False, "web_search": True})
        assert r1.status_code == 200, r1.text
        r2 = await client.post(f"/api/chat/conversations/{cid}/messages",
                               json={"content": "two", "model": "gpt-4o-mini", "stream": False, "web_search": True})
        assert r2.status_code == 422
        body = r2.json()
        assert "Search limit" in (body.get("detail") or body.get("error", {}).get("message", ""))
