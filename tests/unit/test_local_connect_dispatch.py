"""Local AI Connect — hub, dispatcher and wire protocol.

The hub is the in-memory switchboard between the router and the connector
sockets; the dispatcher is the request/response codec on top of it. These
tests use a fake socket so the whole path is exercised without a network or a
running connector.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.local_connect import dispatcher, hub, protocol


class FakeSocket:
    """Minimal stand-in for a Starlette WebSocket."""

    def __init__(self):
        self.sent: list[dict] = []
        self.closed: list[int] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self, code: int = 1000) -> None:
        self.closed.append(code)


@pytest.fixture(autouse=True)
def _clear_hub():
    hub.reset()
    yield
    hub.reset()


# ── protocol frames ────────────────────────────────────────────────────────


def test_frame_builders_shape():
    assert protocol.chat(request_id="r", model="m", adapter="ollama", messages=[{"role": "user"}])[
        "type"
    ] == "chat"
    assert protocol.chunk(request_id="r", delta="hi") == {
        "type": "chunk",
        "request_id": "r",
        "delta": "hi",
    }
    assert protocol.done(request_id="r", usage={"completion_tokens": 1})["usage"] == {
        "completion_tokens": 1
    }
    assert protocol.error(request_id="r", message="boom")["code"] == "upstream_error"
    assert protocol.cancel(request_id="r")["type"] == "cancel"
    assert protocol.ping(request_id="r")["type"] == "ping"


def test_hello_error_carries_code():
    frame = protocol.hello_error(code="unauthorized", message="nope")
    assert frame == {"type": "hello_error", "code": "unauthorized", "message": "nope"}


# ── hub ────────────────────────────────────────────────────────────────────


async def test_register_and_unregister_round_trip():
    sock = FakeSocket()
    connection = await hub.register("m-1", sock)
    assert hub.get("m-1") is connection
    assert hub.is_online("m-1") is True
    assert hub.online_machine_ids() == {"m-1"}

    await hub.unregister("m-1", connection)
    assert hub.get("m-1") is None
    assert hub.is_online("m-1") is False


async def test_reconnect_supersedes_old_socket():
    first = FakeSocket()
    second = FakeSocket()
    old = await hub.register("m-1", first)
    new = await hub.register("m-1", second)

    assert new is not old
    assert first.closed == [4409]
    assert hub.get("m-1") is new


async def test_reconnect_wakes_waiting_request_with_error():
    old_sock = FakeSocket()
    old = await hub.register("m-1", old_sock)
    queue = old.open_request("r-1")

    await hub.register("m-1", FakeSocket())
    frame = queue.get_nowait()
    assert frame["code"] == "superseded"


async def test_unregister_ignores_stale_connection():
    old = await hub.register("m-1", FakeSocket())
    new = await hub.register("m-1", FakeSocket())
    new_queue = new.open_request("r-new")
    await hub.unregister("m-1", old)
    assert hub.get("m-1") is new
    # The live connection's waiters are untouched by a stale unregister.
    assert new_queue.empty()


async def test_disconnect_fails_inflight_request_immediately(monkeypatch):
    """Regression: a connector that dropped mid-request left the caller
    waiting the full REQUEST_TIMEOUT_S (300 s) for a socket that was gone."""
    monkeypatch.setattr(dispatcher, "REQUEST_TIMEOUT_S", 30)
    connection = await hub.register("m-1", FakeSocket())
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="llama3", adapter="ollama")

    async def consume():
        async for _ in dispatcher.stream_chat(target, messages=[]):
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await hub.unregister("m-1", connection)
    with pytest.raises(dispatcher.LocalUpstreamError, match="disconnected"):
        await asyncio.wait_for(task, timeout=2)


# ── dispatcher: streaming ──────────────────────────────────────────────────


async def test_stream_chat_forwards_chunks_and_done():
    sock = FakeSocket()
    connection = await hub.register("m-1", sock)
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="llama3.1:8b", adapter="ollama")

    agen = dispatcher.stream_chat(target, messages=[{"role": "user", "content": "hi"}])
    first = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)
    # The request frame has been written to the socket by now.
    sent = sock.sent[-1]
    assert sent["type"] == "chat"
    assert sent["model"] == "llama3.1:8b"
    assert sent["adapter"] == "ollama"

    request_id = sent["request_id"]
    connection.push(request_id, protocol.chunk(request_id=request_id, delta="Hel"))
    assert (await first)["delta"] == "Hel"

    second = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)
    connection.push(request_id, protocol.chunk(request_id=request_id, delta="lo"))
    assert (await second)["delta"] == "lo"

    third = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)
    connection.push(
        request_id, protocol.done(request_id=request_id, usage={"completion_tokens": 2})
    )
    done = await third
    assert done["type"] == "done"

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert connection.pending == {}


async def test_stream_chat_raises_offline_when_not_connected():
    target = dispatcher.ChatTarget(machine_id="m-x", model_key="k", adapter="ollama")
    agen = dispatcher.stream_chat(target, messages=[])
    with pytest.raises(dispatcher.LocalOffline) as err:
        await agen.__anext__()
    assert err.value.code == "local_offline"
    assert err.value.http_status == 503


async def test_stream_chat_surfaces_connector_error():
    connection = await hub.register("m-1", FakeSocket())
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="k", adapter="ollama")
    agen = dispatcher.stream_chat(target, messages=[])
    pending = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)

    request_id = next(iter(connection.pending))
    connection.push(request_id, protocol.error(request_id=request_id, message="model crashed"))
    with pytest.raises(dispatcher.LocalUpstreamError):
        await pending
    assert connection.pending == {}


async def test_cancelling_stream_sends_cancel_frame():
    sock = FakeSocket()
    connection = await hub.register("m-1", sock)
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="k", adapter="ollama")
    agen = dispatcher.stream_chat(target, messages=[])
    pending = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0)

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert any(frame["type"] == "cancel" for frame in sock.sent)
    assert connection.pending == {}


async def test_stream_chat_times_out(monkeypatch):
    monkeypatch.setattr(dispatcher, "REQUEST_TIMEOUT_S", 0.01)
    connection = await hub.register("m-1", FakeSocket())
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="k", adapter="ollama")
    agen = dispatcher.stream_chat(target, messages=[])
    with pytest.raises(dispatcher.LocalUpstreamError):
        await agen.__anext__()
    assert connection.pending == {}


# ── dispatcher: non-streaming convenience ──────────────────────────────────


async def test_dispatch_chat_collects_text_and_usage():
    connection = await hub.register("m-1", FakeSocket())
    target = dispatcher.ChatTarget(machine_id="m-1", model_key="k", adapter="ollama")
    pending = asyncio.create_task(dispatcher.dispatch_chat(target, messages=[]))
    await asyncio.sleep(0)

    request_id = next(iter(connection.pending))
    connection.push(request_id, protocol.chunk(request_id=request_id, delta="Hello "))
    connection.push(request_id, protocol.chunk(request_id=request_id, delta="local"))
    connection.push(
        request_id,
        protocol.done(
            request_id=request_id, usage={"completion_tokens": 2}, model="llama3.1:8b"
        ),
    )

    result = await pending
    assert result["text"] == "Hello local"
    assert result["usage"] == {"completion_tokens": 2}
    assert result["model"] == "llama3.1:8b"


# ── dispatcher: discovery ──────────────────────────────────────────────────


async def test_discover_returns_models_frame():
    connection = await hub.register("m-1", FakeSocket())
    pending = asyncio.create_task(dispatcher.discover("m-1"))
    await asyncio.sleep(0)

    request_id = next(iter(connection.pending))
    connection.push(
        request_id,
        {"type": "models", "request_id": request_id, "models": [{"model_key": "a"}]},
    )
    models = await pending
    assert models == [{"model_key": "a"}]


async def test_discover_offline_raises():
    with pytest.raises(dispatcher.LocalOffline):
        await dispatcher.discover("m-missing")


async def test_discover_error_frame_raises():
    connection = await hub.register("m-1", FakeSocket())
    pending = asyncio.create_task(dispatcher.discover("m-1"))
    await asyncio.sleep(0)
    request_id = next(iter(connection.pending))
    connection.push(request_id, protocol.error(request_id=request_id, message="no adapters"))
    with pytest.raises(dispatcher.LocalUpstreamError):
        await pending
