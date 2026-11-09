"""In-memory registry of live agent WebSocket connections.

Single-process deployment (see ``app/cli.py`` — the server runs one uvicorn
worker), so a module-level registry is enough. If workers are ever added, this
must move to a broker and the endpoint must reject multi-worker boot.

Each machine has at most one active connection; a reconnect supersedes the
old socket (which the server closes) so a machine that restarted without a
clean close does not leave a zombie that swallows requests.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol


class _Sendable(Protocol):
    async def send_text(self, data: str) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


@dataclass
class Connection:
    machine_id: str
    websocket: _Sendable
    # request_id -> queue of frames routed to the caller awaiting that request.
    pending: dict[str, asyncio.Queue] = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send_json(self, payload: dict[str, Any]) -> None:
        import json

        async with self.send_lock:
            await self.websocket.send_text(json.dumps(payload))

    def push(self, request_id: str, frame: dict[str, Any]) -> None:
        queue = self.pending.get(request_id)
        if queue is not None:
            queue.put_nowait(frame)

    def open_request(self, request_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.pending[request_id] = queue
        return queue

    def close_request(self, request_id: str) -> None:
        self.pending.pop(request_id, None)

    def fail_pending(self, code: str, message: str) -> None:
        """Wake every waiter on this connection with a terminal error frame,
        so in-flight requests fail fast instead of waiting out the request
        timeout on a socket that will never answer."""
        for queue in list(self.pending.values()):
            queue.put_nowait({"type": "error", "code": code, "message": message})


_connections: dict[str, Connection] = {}
_lock = asyncio.Lock()


async def register(machine_id: str, websocket: _Sendable) -> Connection:
    """Attach `websocket` as the live connection for `machine_id`."""
    async with _lock:
        previous = _connections.get(machine_id)
        connection = Connection(machine_id=machine_id, websocket=websocket)
        _connections[machine_id] = connection
    if previous is not None:
        # Wake any waiter on the old socket so it fails fast instead of
        # waiting out the request timeout on a dead machine.
        previous.fail_pending("superseded", "connection replaced")
        await _safe_close(previous.websocket, 4409)
    return connection


async def unregister(machine_id: str, connection: Connection) -> None:
    async with _lock:
        if _connections.get(machine_id) is connection:
            del _connections[machine_id]
    # The socket is gone: requests still waiting on it can never be answered.
    # Only this connection's own waiters are woken; a newer connection that
    # superseded it keeps its requests.
    connection.fail_pending(
        "disconnected", f"Local machine {machine_id} disconnected mid-request."
    )


def get(machine_id: str) -> Connection | None:
    return _connections.get(machine_id)


def is_online(machine_id: str) -> bool:
    return machine_id in _connections


def online_machine_ids() -> set[str]:
    return set(_connections)


async def _safe_close(websocket: _Sendable, code: int) -> None:
    try:
        await websocket.close(code)
    except Exception:
        pass


def reset() -> None:
    """Drop every connection. Test hook only."""
    _connections.clear()
