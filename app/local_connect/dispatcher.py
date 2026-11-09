"""Route a chat request to a local machine over its agent WebSocket.

The LiteLLM custom provider handler calls into this module. A request is
written to the machine's socket as a `chat` frame; the endpoint's reader loop
pushes the machine's `chunk` / `done` / `error` frames back into a queue this
module awaits.

Failures are raised as LiteLLM-compatible exceptions so the existing error
translation in `client.py` maps them onto HTTP statuses the chat route already
understands:
  * machine offline          -> 503 (`local_offline`)
  * machine pending approval -> 503 (`local_not_approved`)
  * connector-reported error -> 502 (`local_upstream_error`)
  * request cancelled        -> `asyncio.CancelledError` propagation
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.local_connect import hub, protocol

REQUEST_TIMEOUT_S = 300


class LocalConnectError(Exception):
    """Base for local dispatch failures that the router translates."""

    def __init__(self, message: str, *, code: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class LocalOffline(LocalConnectError):
    def __init__(self, machine_id: str) -> None:
        super().__init__(
            f"Local machine {machine_id} is not connected. Start the connector "
            "on that machine or pick another model.",
            code="local_offline",
            http_status=503,
        )


class LocalNotApproved(LocalConnectError):
    def __init__(self, machine_id: str) -> None:
        super().__init__(
            f"Local machine {machine_id} is waiting for administrator approval.",
            code="local_not_approved",
            http_status=503,
        )


class LocalUpstreamError(LocalConnectError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="local_upstream_error", http_status=502)


@dataclass
class ChatTarget:
    machine_id: str
    model_key: str
    adapter: str


async def stream_chat(
    target: ChatTarget,
    *,
    messages: list[dict],
    params: dict | None = None,
) -> AsyncIterator[dict]:
    """Yield connector frames (`chunk`, `done`) until the request finishes.

    Raises `LocalConnectError` subclasses on transport failure. Cancelling the
    consumer sends a `cancel` frame so the adapter stops generating.
    """
    connection = hub.get(target.machine_id)
    if connection is None:
        raise LocalOffline(target.machine_id)
    request_id = uuid.uuid4().hex
    queue = connection.open_request(request_id)
    try:
        await connection.send_json(
            protocol.chat(
                request_id=request_id,
                model=target.model_key,
                adapter=target.adapter,
                messages=messages,
                params=params or {},
            )
        )
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=REQUEST_TIMEOUT_S)
            except asyncio.TimeoutError as exc:
                raise LocalUpstreamError(
                    f"Local machine {target.machine_id} did not respond within "
                    f"{REQUEST_TIMEOUT_S}s."
                ) from exc
            frame_type = frame.get("type")
            if frame_type == "chunk":
                yield frame
            elif frame_type == "done":
                yield frame
                return
            elif frame_type == "error":
                raise LocalUpstreamError(
                    frame.get("message") or "the local connector reported an error"
                )
    except asyncio.CancelledError:
        try:
            await connection.send_json(protocol.cancel(request_id=request_id))
        except Exception:
            pass
        raise
    finally:
        connection.close_request(request_id)


async def dispatch_chat(
    target: ChatTarget,
    *,
    messages: list[dict],
    params: dict | None = None,
) -> dict:
    """Non-streaming convenience wrapper: collect the full text + usage."""
    text_parts: list[str] = []
    usage: dict | None = None
    model = None
    async for frame in stream_chat(target, messages=messages, params=params):
        if frame.get("type") == "chunk":
            text_parts.append(frame.get("delta") or "")
            if frame.get("usage"):
                usage = frame["usage"]
        elif frame.get("type") == "done":
            if frame.get("usage"):
                usage = frame["usage"]
            model = frame.get("model")
    return {
        "text": "".join(text_parts),
        "usage": usage or {},
        "model": model or target.model_key,
    }


async def discover(machine_id: str, *, timeout: float = 20.0) -> list[dict]:
    """Ask a machine to re-scan its adapters and return the model list."""
    connection = hub.get(machine_id)
    if connection is None:
        raise LocalOffline(machine_id)
    request_id = uuid.uuid4().hex
    queue = connection.open_request(request_id)
    try:
        await connection.send_json(protocol.discover(request_id=request_id))
        while True:
            frame = await asyncio.wait_for(queue.get(), timeout=timeout)
            frame_type = frame.get("type")
            if frame_type == "models":
                return list(frame.get("models") or [])
            if frame_type == "error":
                raise LocalUpstreamError(
                    frame.get("message") or "the local connector reported an error"
                )
            if frame_type == "done":
                return []
    except asyncio.TimeoutError as exc:
        raise LocalUpstreamError(
            f"Local machine {machine_id} did not answer discovery within {int(timeout)}s."
        ) from exc
    finally:
        connection.close_request(request_id)


