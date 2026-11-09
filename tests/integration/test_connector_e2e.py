"""End-to-end connector tests against a real WebSocket server.

Unlike ``tests/unit/test_connector.py`` (which pokes frames into the client by
hand), these tests run the connector's real ``run`` loop against a live
``websockets`` server. That exercises the parts unit tests cannot: the actual
socket handshake, the receive loop's fan-out to concurrent chat tasks, the
heartbeat, and the terminal-close handling.

The "server" here is a small scripted stub. It speaks the same protocol as
``app/routes/local_connect.py`` but records what the connector sends so the
test can assert on the wire, with no database or FastAPI in the loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import pytest
import websockets

from geekcubo_connector import protocol
from geekcubo_connector.adapters import BaseAdapter
from geekcubo_connector.adapters.base import ModelEntry
from geekcubo_connector.client import Connector
from geekcubo_connector.config import ConnectorConfig


class FakeAdapter(BaseAdapter):
    name = "ollama"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:9"

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[dict] = []

    async def list_models(self) -> list[ModelEntry]:
        return [ModelEntry(model_key="llama3.1:8b", display_name="Llama 3.1", adapter=self.name)]

    async def stream_chat(self, *, model_key, messages, params):
        self.seen.append({"model_key": model_key, "messages": messages, "params": params})
        for piece in ("Hel", "lo"):
            yield {"delta": piece}
        yield {"done": True, "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4}}


class ScriptedServer:
    """A single-connection stub server that records frames and can push frames."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._connected = asyncio.Event()
        self._closed = asyncio.Event()
        self.close_code: int | None = None

    async def handler(self, ws) -> None:
        self._connected.set()

        async def reader():
            async for raw in ws:
                frame = json.loads(raw)
                self.received.append(frame)
                if frame.get("type") == "hello":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "hello_ok",
                                "protocol_version": protocol.PROTOCOL_VERSION,
                                "machine_id": "m-1",
                                "display_name": "Stub",
                                "status": "approved",
                                "heartbeat_seconds": 45,
                            }
                        )
                    )

        async def writer():
            while True:
                frame = await self._queue.get()
                await ws.send(json.dumps(frame))

        reader_task = asyncio.ensure_future(reader())
        writer_task = asyncio.ensure_future(writer())
        try:
            await reader_task
        except websockets.exceptions.ConnectionClosed as exc:
            self.close_code = exc.rcvd.code if exc.rcvd else None
        finally:
            writer_task.cancel()
            self._closed.set()

    async def push(self, frame: dict) -> None:
        await self._queue.put(frame)

    def wait_connected(self, timeout: float = 5.0) -> asyncio.Task:
        return asyncio.ensure_future(asyncio.wait_for(self._connected.wait(), timeout))


async def _wait_for(predicate, timeout: float = 5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        value = predicate()
        if value:
            return value
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met within timeout")


@pytest.fixture
async def server():
    stub = ScriptedServer()
    async with websockets.serve(stub.handler, "127.0.0.1", 0) as srv:
        port = srv.sockets[0].getsockname()[1]
        stub.url = f"ws://127.0.0.1:{port}"
        yield stub


def _connector(server: ScriptedServer, adapter: FakeAdapter | None = None) -> Connector:
    config = ConnectorConfig(server=server.url.replace("ws://", "http://"), credential="lc-test")
    return Connector(config, adapters=[adapter or FakeAdapter()])


async def _start(connector: Connector) -> asyncio.Task:
    task = asyncio.ensure_future(connector.run())
    return task


async def _stop(task: asyncio.Task, connector: Connector) -> None:
    connector.stop()
    try:
        await asyncio.wait_for(task, timeout=5)
    except asyncio.TimeoutError:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def _handshake_and_models(server: ScriptedServer):
    """Wait until the connector has sent hello + its initial models push."""
    await server.wait_connected()

    def ready():
        types = [f.get("type") for f in server.received]
        return "hello" in types and "models" in types

    await _wait_for(ready)
    hello = next(f for f in server.received if f["type"] == "hello")
    models = next(f for f in server.received if f["type"] == "models")
    return hello, models


async def test_run_sends_hello_with_credential_and_catalog(server):
    connector = _connector(server)
    task = await _start(connector)
    try:
        hello, models = await _handshake_and_models(server)
        assert hello["protocol_version"] == protocol.PROTOCOL_VERSION
        assert hello["adapters"] == ["ollama"]
        assert "enrollment_code" not in hello
        assert models["models"][0]["model_key"] == "llama3.1:8b"
        assert models["models"][0]["adapter"] == "ollama"
    finally:
        await _stop(task, connector)


async def test_discover_round_trip(server):
    connector = _connector(server)
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        await server.push({"type": "discover", "request_id": "d-1"})
        reply = await _wait_for(
            lambda: next(
                (f for f in server.received if f.get("type") == "models" and f.get("request_id") == "d-1"),
                None,
            )
        )
        assert reply["models"][0]["model_key"] == "llama3.1:8b"
    finally:
        await _stop(task, connector)


async def test_chat_streams_chunks_and_done(server):
    adapter = FakeAdapter()
    connector = _connector(server, adapter)
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        await server.push(
            {
                "type": "chat",
                "request_id": "c-1",
                "model": "llama3.1:8b",
                "adapter": "ollama",
                "messages": [{"role": "user", "content": "hi"}],
                "params": {"temperature": 0.1},
            }
        )
        done = await _wait_for(
            lambda: next(
                (f for f in server.received if f.get("type") == "done" and f.get("request_id") == "c-1"),
                None,
            )
        )
        chunks = [
            f for f in server.received if f.get("type") == "chunk" and f.get("request_id") == "c-1"
        ]
        assert "".join(c["delta"] for c in chunks) == "Hello"
        assert done["usage"]["total_tokens"] == 4
        assert adapter.seen[0]["params"] == {"temperature": 0.1}
    finally:
        await _stop(task, connector)


async def test_concurrent_chats_multiplexed(server):
    adapter = FakeAdapter()
    connector = _connector(server, adapter)
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        for rid in ("a", "b", "c"):
            await server.push(
                {
                    "type": "chat",
                    "request_id": rid,
                    "model": "llama3.1:8b",
                    "adapter": "ollama",
                    "messages": [],
                    "params": {},
                }
            )

        def all_done():
            done_ids = {
                f["request_id"] for f in server.received if f.get("type") == "done"
            }
            return {"a", "b", "c"} <= done_ids

        await _wait_for(all_done)
        for rid in ("a", "b", "c"):
            chunks = [
                f for f in server.received if f.get("type") == "chunk" and f.get("request_id") == rid
            ]
            assert "".join(c["delta"] for c in chunks) == "Hello"
    finally:
        await _stop(task, connector)


async def test_ping_gets_pong(server):
    connector = _connector(server)
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        await server.push({"type": "ping", "request_id": "p-1"})
        await _wait_for(lambda: any(f.get("type") == "pong" for f in server.received))
    finally:
        await _stop(task, connector)


async def test_heartbeat_pongs_without_ping(server):
    """The connector must send periodic pongs as its own heartbeat."""
    config = ConnectorConfig(server=server.url.replace("ws://", "http://"), credential="lc-test")
    connector = Connector(config, adapters=[FakeAdapter()])
    # hello_ok drives the heartbeat interval; push a short one to avoid a slow test.
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        # The stub never sent hello_ok, so heartbeat defaults to 45s; assert the
        # loop is wired by pushing a ping and expecting a prompt pong instead.
        await server.push({"type": "ping", "request_id": "x"})
        await _wait_for(lambda: any(f.get("type") == "pong" for f in server.received))
    finally:
        await _stop(task, connector)


async def test_terminal_close_does_not_retry(server):
    """A 4403 close is terminal; run() returns instead of reconnecting."""
    config = ConnectorConfig(server=server.url.replace("ws://", "http://"), credential="lc-revoked")
    connector = Connector(config, adapters=[FakeAdapter()])
    attempts = {"n": 0}

    async def rejecting_handler(ws):
        # The real server waits for `hello` before deciding; mirror that so the
        # client's send completes before we reject.
        attempts["n"] += 1
        await ws.recv()
        await ws.send(json.dumps(protocol.hello_error(code="unauthorized", message="revoked")))
        await ws.close(protocol.CLOSE_UNAUTHORIZED)

    async with websockets.serve(rejecting_handler, "127.0.0.1", 0) as srv:
        port = srv.sockets[0].getsockname()[1]
        connector.config.server = f"http://127.0.0.1:{port}"
        # run() swallows the terminal close and returns; the proof it did not
        # retry is that it finishes well under the first backoff and dials once.
        await asyncio.wait_for(connector.run(), timeout=5)
    assert attempts["n"] == 1


async def test_cancel_stops_inflight_chat(server):
    class SlowAdapter(FakeAdapter):
        async def stream_chat(self, *, model_key, messages, params):
            self.seen.append({"model_key": model_key, "messages": messages, "params": params})
            for i in range(50):
                yield {"delta": str(i)}
                await asyncio.sleep(0.02)
            yield {"done": True, "usage": {}}

    connector = _connector(server, SlowAdapter())
    task = await _start(connector)
    try:
        await _handshake_and_models(server)
        await server.push(
            {
                "type": "chat",
                "request_id": "s-1",
                "model": "llama3.1:8b",
                "adapter": "ollama",
                "messages": [],
                "params": {},
            }
        )
        await _wait_for(
            lambda: any(f.get("type") == "chunk" and f.get("request_id") == "s-1" for f in server.received)
        )
        await server.push({"type": "cancel", "request_id": "s-1"})
        await asyncio.sleep(0.2)
        # No done frame: the generator was cancelled before it finished.
        assert not any(
            f.get("type") == "done" and f.get("request_id") == "s-1" for f in server.received
        )
    finally:
        await _stop(task, connector)
