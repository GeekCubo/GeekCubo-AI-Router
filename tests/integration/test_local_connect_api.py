"""Local AI Connect — administrator API and the agent WebSocket, end to end.

Uses the real app, a real SQLite file and a real ASGI WebSocket round-trip
(the connector socket is driven in-process so the test shares the app's event
loop and session factory). This is the suite that proves a machine can enrol
with a one-time code, be approved, publish a model catalog, and then serve a
chat request — and that revoking it closes the door.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse

import pytest

from tests.authkit import dual_client

# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
async def lc(tmp_sqlite_url, monkeypatch, isolated_env):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app import cache_invalidation_bus, router_cache
    from app.local_connect import hub
    from packages.db import session as session_mod
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory
    router_cache.invalidate_router()
    hub.reset()

    from app.seed import seed_initial_state

    async with factory() as s:
        seed = await seed_initial_state(s)

    from app.main import create_app

    app = create_app()
    client = await dual_client(app, factory, seed.api_key)
    try:
        yield {"client": client, "app": app, "factory": factory}
    finally:
        await client.aclose()
        hub.reset()
        router_cache.invalidate_router()
        await cache_invalidation_bus.stop_invalidation_listener()
        # Do not dispose inside a still-running loop's fixtures; engine cleanup
        # happens via the temp DB unlink in tmp_sqlite_url.
        await engine.dispose()
        session_mod._session_factory = None


# ── minimal in-process ASGI WebSocket client ───────────────────────────────


class ASGIWebSocket:
    """Drive a Starlette WebSocket endpoint over raw ASGI messages."""

    def __init__(self, app, path: str, *, headers: list[tuple[bytes, bytes]] | None = None):
        self._app = app
        self._path = path
        self._headers = headers or []
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def connect(self) -> "ASGIWebSocket":
        parsed = urllib.parse.urlsplit(self._path)
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": parsed.path,
            "raw_path": parsed.path.encode(),
            "query_string": parsed.query.encode(),
            "root_path": "",
            "headers": self._headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "subprotocols": [],
            "state": {},
        }

        async def receive():
            return await self._to_app.get()

        async def send(message):
            await self._from_app.put(message)

        self._task = asyncio.create_task(self._app(scope, receive, send))
        await self._to_app.put({"type": "websocket.connect"})
        message = await self._receive()
        assert message["type"] == "websocket.accept", message
        return self

    async def _receive(self, timeout: float = 5.0) -> dict:
        message = await asyncio.wait_for(self._from_app.get(), timeout=timeout)
        return message

    async def send_json(self, payload: dict) -> None:
        await self._to_app.put(
            {"type": "websocket.receive", "text": json.dumps(payload)}
        )

    async def receive_json(self, timeout: float = 5.0) -> dict:
        message = await self._receive(timeout=timeout)
        if message["type"] == "websocket.close":
            return {"type": "close", "code": message.get("code")}
        return json.loads(message["text"])

    async def close(self) -> None:
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()


def _bearer_headers(credential: str) -> list[tuple[bytes, bytes]]:
    return [(b"authorization", f"Bearer {credential}".encode())]


async def _mint_code(client, *, display_name="Studio"):
    r = await client.post("/api/local-connect/enrollments", json={"display_name": display_name})
    assert r.status_code == 201, r.text
    return r.json()


async def _enroll(app, code, *, display_name="Studio", adapters=("ollama",)):
    """Open a fresh connector socket and complete the enrollment handshake."""
    ws = await ASGIWebSocket(app, "/api/local-connect/agent").connect()
    await ws.send_json(
        {
            "type": "hello",
            "protocol_version": 1,
            "display_name": display_name,
            "hostname": "studio.local",
            "platform": "linux",
            "agent_version": "0.1.0",
            "adapters": list(adapters),
            "enrollment_code": code,
        }
    )
    hello = await ws.receive_json()
    assert hello["type"] == "hello_ok", hello
    assert hello["credential"].startswith("lc-")
    return ws, hello


async def _approve(client, machine_id):
    r = await client.post(f"/api/local-connect/machines/{machine_id}/approve")
    assert r.status_code == 200, r.text
    return r.json()


async def _reconnect(app, credential):
    ws = await ASGIWebSocket(
        app, "/api/local-connect/agent", headers=_bearer_headers(credential)
    ).connect()
    hello = await ws.receive_json()
    assert hello["type"] == "hello_ok", hello
    return ws, hello


# ── admin REST ─────────────────────────────────────────────────────────────


async def test_overview_starts_empty(lc):
    r = await lc["client"].get("/api/local-connect/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"] == {
        "machines": 0,
        "approved": 0,
        "pending": 0,
        "online": 0,
        "models": 0,
    }
    assert body["settings"] == {
        "enabled": True,
        "eligible_for_auto": True,
        "no_cloud_fallback": False,
    }
    assert body["machines"] == []
    assert "geekcubo_connector enroll" in body["install_command"]


async def test_settings_round_trip(lc):
    client = lc["client"]
    r = await client.put(
        "/api/local-connect/settings",
        json={"enabled": False, "eligible_for_auto": False, "no_cloud_fallback": True},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "enabled": False,
        "eligible_for_auto": False,
        "no_cloud_fallback": True,
    }
    again = (await client.get("/api/local-connect/settings")).json()
    assert again["no_cloud_fallback"] is True

    # A second PUT with only one field leaves the others intact.
    await client.put("/api/local-connect/settings", json={"enabled": True})
    final = (await client.get("/api/local-connect/settings")).json()
    assert final == {
        "enabled": True,
        "eligible_for_auto": False,
        "no_cloud_fallback": True,
    }


async def test_enrollment_minting_and_listing(lc):
    client = lc["client"]
    created = await _mint_code(client)
    assert created["code"].startswith("lcenr-")
    assert created["code_prefix"].endswith(created["code"][-4:])
    assert created["display_name"] == "Studio"

    listed = (await client.get("/api/local-connect/enrollments")).json()["enrollments"]
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["consumed_at"] is None

    deleted = await client.delete(f"/api/local-connect/enrollments/{created['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/local-connect/enrollments")).json()["enrollments"] == []


async def test_service_files_and_install_command(lc):
    client = lc["client"]
    files = (await client.get("/api/local-connect/service-files")).json()["files"]
    assert set(files) == {"systemd", "launchd", "windows"}
    assert "geekcubo-connector run" in files["systemd"]
    assert "com.geekcubo.connector" in files["launchd"]

    cmd = (await client.get("/api/local-connect/install-command")).json()
    assert cmd["command"].startswith("python -m geekcubo_connector enroll")


async def test_delete_unknown_enrollment_is_404(lc):
    r = await lc["client"].delete("/api/local-connect/enrollments/nope")
    assert r.status_code == 404


# ── enrollment over the WebSocket ──────────────────────────────────────────


async def test_first_connect_burns_code_and_issues_credential(lc):
    client = lc["client"]
    created = await _mint_code(client)

    ws, hello = await _enroll(lc["app"], created["code"])
    try:
        assert hello["status"] == "pending"
        machine_id = hello["machine_id"]

        machines = (await client.get("/api/local-connect/machines")).json()["machines"]
        assert len(machines) == 1
        machine = machines[0]
        assert machine["id"] == machine_id
        assert machine["status"] == "pending"
        assert machine["online"] is True
        assert machine["adapters"] == ["ollama"]
        assert machine["hostname"] == "studio.local"
    finally:
        await ws.close()

    # The code cannot be used a second time.
    ws2 = await ASGIWebSocket(lc["app"], "/api/local-connect/agent").connect()
    await ws2.send_json({"type": "hello", "enrollment_code": created["code"]})
    rejected = await ws2.receive_json()
    assert rejected["type"] == "hello_error"
    assert rejected["code"] == "enrollment_failed"
    await ws2.close()


async def test_hello_without_code_is_rejected(lc):
    ws = await ASGIWebSocket(lc["app"], "/api/local-connect/agent").connect()
    await ws.send_json({"type": "hello"})
    rejected = await ws.receive_json()
    assert rejected["type"] == "hello_error"
    assert "enrollment" in rejected["code"]
    await ws.close()


async def test_non_hello_first_frame_is_a_protocol_error(lc):
    ws = await ASGIWebSocket(lc["app"], "/api/local-connect/agent").connect()
    await ws.send_json({"type": "chunk", "request_id": "x"})
    rejected = await ws.receive_json()
    assert rejected["type"] == "hello_error"
    assert rejected["code"] == "protocol"
    await ws.close()


async def test_url_credentials_are_rejected(lc):
    ws = await ASGIWebSocket(
        lc["app"], "/api/local-connect/agent?credential=lc-test"
    ).connect()
    rejected = await ws.receive_json()
    assert rejected["code"] == "unauthorized"
    assert "Authorization header" in rejected["message"]
    assert (await ws.receive_json())["code"] == 4401
    await ws.close()


@pytest.mark.parametrize("frame", [[], None, "hello", 1])
async def test_non_object_hello_is_rejected(lc, frame):
    ws = await ASGIWebSocket(lc["app"], "/api/local-connect/agent").connect()
    await ws.send_json(frame)
    rejected = await ws.receive_json()
    assert rejected["code"] == "protocol"
    await ws.close()


async def test_unknown_credential_is_rejected(lc):
    ws = await ASGIWebSocket(
        lc["app"], "/api/local-connect/agent", headers=_bearer_headers("lc-nope")
    ).connect()
    rejected = await ws.receive_json()
    assert rejected["type"] == "hello_error"
    assert rejected["code"] == "unauthorized"
    await ws.close()


async def test_disabled_feature_rejects_connection(lc, monkeypatch):
    from app import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("LOCAL_CONNECT_ENABLED", "false")
    cfg.get_settings.cache_clear()
    try:
        ws = await ASGIWebSocket(lc["app"], "/api/local-connect/agent").connect()
        rejected = await ws.receive_json()
        assert rejected["type"] == "hello_error"
        assert rejected["code"] == "disabled"
        await ws.close()
    finally:
        monkeypatch.delenv("LOCAL_CONNECT_ENABLED", raising=False)
        cfg.get_settings.cache_clear()


# ── approval lifecycle ─────────────────────────────────────────────────────


async def test_approved_machine_publishes_models_and_chats(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    try:
        await _approve(client, machine_id)

        # The connector publishes its catalog.
        await ws.send_json(
            {
                "type": "models",
                "adapters": ["ollama"],
                "models": [
                    {
                        "model_key": "llama3.1:8b",
                        "display_name": "Llama 3.1 8B",
                        "adapter": "ollama",
                        "context_length": 131072,
                        "supports_tools": True,
                    }
                ],
            }
        )

        # Poll until the catalog row lands (the models frame is async).
        models: list = []
        for _ in range(100):
            machines = (await client.get("/api/local-connect/machines")).json()["machines"]
            models = machines[0]["models"]
            if models:
                break
            await asyncio.sleep(0.02)
        assert models and models[0]["model_key"] == "llama3.1:8b"
        assert models[0]["routing_id"] == f"local/{machine_id}/llama3.1:8b"

        # The approved model is deployed in the router and the merged catalog.
        from app.local_connect import deployments

        async with lc["factory"]() as db:
            views = await deployments.load_local_deployments(db)
        assert [v.model_name for v in views] == [f"local/{machine_id}/llama3.1:8b"]

        from app.custom_providers import merged_catalog

        async with lc["factory"]() as db:
            ids = {m.id for m in await merged_catalog(db, eligible_only=False)}
        assert f"local/{machine_id}/llama3.1:8b" in ids

        # A chat dispatched over the socket streams back.
        from app.local_connect import dispatcher

        target = dispatcher.ChatTarget(
            machine_id=machine_id, model_key="llama3.1:8b", adapter="ollama"
        )
        pending = asyncio.create_task(
            dispatcher.dispatch_chat(target, messages=[{"role": "user", "content": "hi"}])
        )
        frame = await ws.receive_json()
        assert frame["type"] == "chat"
        assert frame["model"] == "llama3.1:8b"
        request_id = frame["request_id"]
        await ws.send_json({"type": "chunk", "request_id": request_id, "delta": "Hello "})
        await ws.send_json({"type": "chunk", "request_id": request_id, "delta": "local"})
        await ws.send_json(
            {"type": "done", "request_id": request_id, "usage": {"completion_tokens": 2}}
        )
        result = await pending
        assert result["text"] == "Hello local"
    finally:
        await ws.close()


async def test_pending_machine_cannot_be_auto_eligible_model(lc):
    """A pending machine's models never enter the catalog even if reported."""
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    try:
        await ws.send_json(
            {
                "type": "models",
                "models": [{"model_key": "early", "adapter": "ollama"}],
            }
        )
        for _ in range(100):
            from app.local_connect import catalog

            async with lc["factory"]() as db:
                entries = await catalog.local_catalog_entries(db, eligible_only=False)
            if entries:
                break
            await asyncio.sleep(0.02)
        assert entries == []
    finally:
        await ws.close()


async def test_revoke_closes_socket_and_blocks_credential(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    credential = hello["credential"]
    await _approve(client, machine_id)

    r = await client.post(f"/api/local-connect/machines/{machine_id}/revoke")
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"

    # The server closed the live socket with the rejected code.
    closed = await ws.receive_json(timeout=2)
    assert closed["type"] == "close"
    assert closed["code"] == 4403
    await ws.close()

    # The old credential no longer authenticates.
    ws2 = await ASGIWebSocket(
        lc["app"], "/api/local-connect/agent", headers=_bearer_headers(credential)
    ).connect()
    rejected = await ws2.receive_json()
    assert rejected["type"] == "hello_error"
    assert rejected["code"] == "unauthorized"
    await ws2.close()


async def test_rotate_issues_new_credential_and_invalidates_old(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    await _approve(client, machine_id)

    rotated = (await client.post(f"/api/local-connect/machines/{machine_id}/rotate")).json()
    assert rotated["credential"].startswith("lc-")
    assert rotated["reconnect_required"] is True
    await ws.close()

    new_ws, new_hello = await _reconnect(lc["app"], rotated["credential"])
    try:
        assert new_hello["machine_id"] == machine_id
    finally:
        await new_ws.close()


async def test_machine_patch_renames_and_toggles_auto(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    try:
        r = await client.patch(
            f"/api/local-connect/machines/{machine_id}",
            json={"display_name": "Renamed", "eligible_for_auto": False},
        )
        assert r.status_code == 200, r.text
        assert r.json()["display_name"] == "Renamed"
        assert r.json()["eligible_for_auto"] is False

        empty = await client.patch(
            f"/api/local-connect/machines/{machine_id}", json={"display_name": "  "}
        )
        assert empty.status_code == 422
    finally:
        await ws.close()


async def test_model_toggle_and_delete_machine(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    await _approve(client, machine_id)
    try:
        await ws.send_json(
            {"type": "models", "models": [{"model_key": "m1", "adapter": "ollama"}]}
        )
        models: list = []
        for _ in range(100):
            machines = (await client.get("/api/local-connect/machines")).json()["machines"]
            models = machines[0]["models"]
            if models:
                break
            await asyncio.sleep(0.02)
        model_pk = models[0]["id"]

        off = await client.patch(
            f"/api/local-connect/machines/{machine_id}/models/{model_pk}",
            json={"is_enabled": False},
        )
        assert off.status_code == 200
        assert off.json()["is_enabled"] is False

        from app.local_connect import deployments

        async with lc["factory"]() as db:
            assert await deployments.load_local_deployments(db) == []

        deleted = await client.delete(f"/api/local-connect/machines/{machine_id}")
        assert deleted.status_code == 204
        assert (await client.get("/api/local-connect/machines")).json()["machines"] == []
    finally:
        await ws.close()


async def test_discover_round_trips_models_frame(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    await _approve(client, machine_id)
    try:
        pending = asyncio.create_task(client.post(f"/api/local-connect/machines/{machine_id}/discover"))
        frame = await ws.receive_json()
        assert frame["type"] == "discover"
        await ws.send_json(
            {
                "type": "models",
                "request_id": frame["request_id"],
                "models": [{"model_key": "rediscovered", "adapter": "ollama"}],
            }
        )
        r = await pending
        assert r.status_code == 200, r.text
        keys = [m["model_key"] for m in r.json()["models"]]
        assert keys == ["rediscovered"]
    finally:
        await ws.close()


async def test_discover_offline_machine_is_409(lc):
    client = lc["client"]
    created = await _mint_code(client)
    ws, hello = await _enroll(lc["app"], created["code"])
    machine_id = hello["machine_id"]
    await ws.close()
    # Give the handler a moment to unregister.
    for _ in range(100):
        machines = (await client.get("/api/local-connect/machines")).json()["machines"]
        if machines and machines[0]["online"] is False:
            break
        await asyncio.sleep(0.02)

    r = await client.post(f"/api/local-connect/machines/{machine_id}/discover")
    assert r.status_code == 409, r.text
    assert r.json()["error"]["message"]["code"] == "local_offline"


async def test_unknown_machine_actions_are_404(lc):
    client = lc["client"]
    assert (await client.post("/api/local-connect/machines/x/approve")).status_code == 404
    assert (await client.post("/api/local-connect/machines/x/revoke")).status_code == 404
    assert (await client.post("/api/local-connect/machines/x/rotate")).status_code == 404
    assert (await client.delete("/api/local-connect/machines/x")).status_code == 404
