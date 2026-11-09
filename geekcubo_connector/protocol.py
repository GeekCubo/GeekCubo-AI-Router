"""Wire protocol shared by the server and the Local AI Connect connector.

One JSON object per WebSocket text frame, discriminated by `type`. The
connector always opens the socket OUTBOUND to the GeekCubo instance, so the
operator needs no port forwarding, tunnel or VPN: any machine that can reach
the dashboard over HTTPS can serve local models.

Handshake
---------
1. Connector connects to ``GET {base}/api/local-connect/agent`` with the
   per-machine credential in an ``Authorization: Bearer`` header.
2. Connector sends ``hello`` with its identity + adapters.
3. Server replies ``hello_ok`` (registered) or ``hello_error`` (rejected) and
   closes on error. A machine in ``pending`` state connects but is told it
   cannot serve until an administrator approves it.

Request/response
----------------
Server -> connector: ``discover``, ``chat``, ``cancel``, ``ping``.
Connector -> server: ``models``, ``chunk``, ``done``, ``error``, ``pong``.
Every request carries a ``request_id`` echoed on its responses so a single
socket can multiplex concurrent chats from many dashboard users.

This module holds only constants and frame constructors so it can be
vendored into the connector package unchanged.
"""

from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = 1

# Frame types, server -> connector.
SERVER_FRAMES = frozenset({"hello_ok", "hello_error", "discover", "chat", "cancel", "ping"})
# Frame types, connector -> server.
CONNECTOR_FRAMES = frozenset({"hello", "models", "chunk", "done", "error", "pong"})

# Adapters a connector may speak. The connector reports which are reachable;
# the server never assumes one is present.
ADAPTERS = ("ollama", "lmstudio", "vllm", "llamacpp", "custom")

# WebSocket close codes (4000-4999 is the application-private range).
CLOSE_UNAUTHORIZED = 4401
CLOSE_REJECTED = 4403
CLOSE_PROTOCOL = 4400
CLOSE_DISABLED = 4404


def hello_ok(
    *,
    machine_id: str,
    display_name: str,
    status: str,
    heartbeat_seconds: int,
) -> dict[str, Any]:
    return {
        "type": "hello_ok",
        "protocol_version": PROTOCOL_VERSION,
        "machine_id": machine_id,
        "display_name": display_name,
        "status": status,
        "heartbeat_seconds": heartbeat_seconds,
    }


def hello_error(*, code: str, message: str) -> dict[str, Any]:
    return {"type": "hello_error", "code": code, "message": message}


def discover(*, request_id: str) -> dict[str, Any]:
    return {"type": "discover", "request_id": request_id}


def chat(
    *,
    request_id: str,
    model: str,
    adapter: str,
    messages: list[dict],
    params: dict | None = None,
) -> dict[str, Any]:
    return {
        "type": "chat",
        "request_id": request_id,
        "model": model,
        "adapter": adapter,
        "messages": messages,
        "params": params or {},
    }


def cancel(*, request_id: str) -> dict[str, Any]:
    return {"type": "cancel", "request_id": request_id}


def ping(*, request_id: str) -> dict[str, Any]:
    return {"type": "ping", "request_id": request_id}


def chunk(
    *,
    request_id: str,
    delta: str = "",
    finish_reason: str | None = None,
    usage: dict | None = None,
) -> dict[str, Any]:
    frame: dict[str, Any] = {"type": "chunk", "request_id": request_id, "delta": delta}
    if finish_reason is not None:
        frame["finish_reason"] = finish_reason
    if usage is not None:
        frame["usage"] = usage
    return frame


def done(*, request_id: str, usage: dict | None = None, model: str | None = None) -> dict[str, Any]:
    frame: dict[str, Any] = {"type": "done", "request_id": request_id}
    if usage is not None:
        frame["usage"] = usage
    if model is not None:
        frame["model"] = model
    return frame


def error(*, request_id: str, message: str, code: str = "upstream_error") -> dict[str, Any]:
    return {"type": "error", "request_id": request_id, "code": code, "message": message}
