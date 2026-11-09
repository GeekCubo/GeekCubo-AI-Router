"""Connector runtime: connect, handshake, serve chat, heartbeat, reconnect.

One :class:`Connector` owns a single outbound WebSocket and multiplexes many
concurrent chat requests over it. The server addresses each request with a
``request_id``; the connector fans a ``chat`` frame out to the right adapter and
streams ``chunk`` / ``done`` / ``error`` frames back on the same socket, tagged
with that id. A ``cancel`` frame stops the matching generator.

The receive loop is the single reader of the socket; outbound frames from chat
tasks and heartbeats go through a lock so they never interleave mid-frame.

Reconnection is exponential backoff capped at 30 s. A revoked credential
(the server closes with ``CLOSE_UNAUTHORIZED`` or ``CLOSE_REJECTED``) is
terminal: the connector exits with a clear message instead of retrying forever.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import platform
import socket
import sys
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from . import __version__, protocol
from .adapters import PROBE_ORDER, AdapterError, BaseAdapter, build_adapter
from .config import ConnectorConfig

logger = logging.getLogger("geekcubo.connector")

RECONNECT_MAX_S = 30.0
# The server closes with these codes on a credential it will never accept
# again; retrying cannot help.
TERMINAL_CLOSE_CODES = frozenset({protocol.CLOSE_UNAUTHORIZED, protocol.CLOSE_REJECTED})


def _device_facts() -> dict[str, str]:
    return {
        "hostname": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()}".strip(),
        "agent_version": __version__,
        "python": sys.version.split()[0],
    }


class Connector:
    def __init__(self, config: ConnectorConfig, *, adapters: list[BaseAdapter] | None = None) -> None:
        self.config = config
        self._adapters: list[BaseAdapter] = adapters if adapters is not None else []
        # request_id -> task running the chat; used to honor `cancel`.
        self._inflight: dict[str, asyncio.Task] = {}
        self._send_lock = asyncio.Lock()
        self._ws: Any = None
        self._stop = asyncio.Event()

    # ── adapter selection ──────────────────────────────────────────────

    async def detect_adapters(self) -> list[BaseAdapter]:
        """Probe every adapter and keep the ones that answer.

        An operator can pin a subset via ``config.adapters``; when set we only
        probe those names. Custom base URLs and the shared API key come from
        the config so the same machine can point at non-default ports.
        """
        names = self.config.adapters or list(PROBE_ORDER)
        found: list[BaseAdapter] = []
        for name in names:
            try:
                adapter = build_adapter(
                    name,
                    base_url=self.config.adapter_urls.get(name),
                    api_key=self.config.adapter_api_key,
                )
            except AdapterError:
                logger.warning("unknown adapter configured: %s", name)
                continue
            if await adapter.available():
                found.append(adapter)
                logger.info("adapter available: %s (%s)", adapter.name, adapter.base_url)
            else:
                logger.debug("adapter not available: %s", name)
        return found

    def _adapter_for(self, name: str) -> BaseAdapter | None:
        for adapter in self._adapters:
            if adapter.name == name:
                return adapter
        # Fall back to any adapter when the server names one we did not report;
        # the machine id already pins the model, this only picks a transport.
        return self._adapters[0] if self._adapters else None

    # ── catalog ────────────────────────────────────────────────────────

    async def collect_models(self) -> list[dict]:
        entries: list[dict] = []
        for adapter in self._adapters:
            try:
                models = await adapter.list_models()
            except AdapterError as exc:
                logger.warning("model listing failed for %s: %s", adapter.name, exc)
                continue
            entries.extend(entry.to_wire() for entry in models)
        return entries

    # ── connection lifecycle ───────────────────────────────────────────

    async def run(self) -> None:
        """Connect and serve until stopped or the credential is rejected."""
        if not self._adapters:
            self._adapters = await self.detect_adapters()
        if not self._adapters:
            logger.warning(
                "no local inference adapter answered; the connector will connect "
                "but advertise no models until one starts"
            )
        delay = 1.0
        while not self._stop.is_set():
            try:
                await self._connect_once()
                delay = 1.0
            except _TerminalClose as exc:
                logger.error("%s", exc)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect on anything else
                logger.warning("connection lost: %s", exc)
            if self._stop.is_set():
                return
            logger.info("reconnecting in %.0fs", delay)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, RECONNECT_MAX_S)

    async def enroll(self) -> None:
        """Redeem the configured enrollment code and store the credential.

        Connects with no credential, sends ``hello`` carrying the code, reads
        the ``hello_ok`` that issues the credential, and returns. The caller
        (``run``) then reconnects with the stored credential.
        """
        if not self.config.enrollment_code:
            raise _TerminalClose("an enrollment code is required for `enroll`")
        url = _agent_url(self.config.server)
        async with websockets.connect(url, max_size=None, ping_interval=None) as ws:
            self._ws = ws
            await self._handshake(ws)
            self._ws = None
        if not self.config.credential:
            raise _TerminalClose("the server did not issue a credential; check the enrollment code")

    async def _connect_once(self) -> None:
        url = _agent_url(self.config.server)
        headers = {}
        if self.config.credential:
            headers["Authorization"] = f"Bearer {self.config.credential}"
        logger.info("connecting to %s", url)
        async with websockets.connect(
            url,
            additional_headers=headers,
            max_size=None,
            ping_interval=None,  # we drive our own heartbeat over the protocol
        ) as ws:
            self._ws = ws
            heartbeat = await self._handshake(ws)
            await self._publish_catalog(ws)
            logger.info("registered with server; heartbeat every %ss", heartbeat)
            await self._serve(ws, heartbeat)

    async def _handshake(self, ws: Any) -> int:
        hello = {
            "type": "hello",
            "protocol_version": protocol.PROTOCOL_VERSION,
            "display_name": self.config.display_name,
            "adapters": [a.name for a in self._adapters],
            **_device_facts(),
        }
        if not self.config.credential and self.config.enrollment_code:
            hello["enrollment_code"] = self.config.enrollment_code
        await ws.send(json.dumps(hello))
        raw = await asyncio.wait_for(ws.recv(), timeout=30)
        frame = _decode(raw)
        if frame.get("type") == "hello_error":
            code = frame.get("code") or "error"
            message = frame.get("message") or "handshake rejected"
            raise _TerminalClose(f"server rejected the connector ({code}): {message}")
        if frame.get("type") != "hello_ok":
            raise _TerminalClose(f"unexpected handshake frame: {frame.get('type')!r}")
        # A fresh enrollment issues the credential on hello_ok; persist it so
        # subsequent reconnects authenticate with the machine credential.
        credential = frame.get("credential")
        if credential:
            self.config.credential = credential
            self.config.machine_id = frame.get("machine_id")
            from .config import save_config

            save_config(self.config)
            logger.info("enrollment accepted; credential stored")
        self.config.machine_id = frame.get("machine_id") or self.config.machine_id
        status = frame.get("status")
        if status and status != "approved":
            logger.warning(
                "machine is %r; it will not serve until an administrator approves it",
                status,
            )
        return int(frame.get("heartbeat_seconds") or 45)

    async def _publish_catalog(self, ws: Any) -> None:
        payload = {
            "type": "models",
            "adapters": [a.name for a in self._adapters],
            "models": await self.collect_models(),
        }
        await self._send(ws, payload)

    async def _serve(self, ws: Any, heartbeat: int) -> None:
        blocker = asyncio.ensure_future(self._stop.wait())
        pinger = asyncio.ensure_future(self._heartbeat(ws, heartbeat))
        try:
            while True:
                recv = asyncio.ensure_future(ws.recv())
                done, _ = await asyncio.wait(
                    {recv, blocker}, return_when=asyncio.FIRST_COMPLETED
                )
                if blocker in done:
                    recv.cancel()
                    return
                raw = recv.result()
                await self._on_frame(ws, _decode(raw))
        except ConnectionClosed as exc:
            code = getattr(exc.rcvd, "code", None) if getattr(exc, "rcvd", None) else None
            if code in TERMINAL_CLOSE_CODES:
                raise _TerminalClose(
                    f"server closed the connection with code {code}; re-enroll the machine"
                ) from exc
            raise
        finally:
            pinger.cancel()
            blocker.cancel()
            await self._cancel_all()
            self._ws = None
            # Await the cancelled tasks so they are not left pending; their
            # CancelledError is expected and must not escape shutdown.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await pinger
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await blocker

    async def _heartbeat(self, ws: Any, seconds: int) -> None:
        interval = max(5, int(seconds))
        while True:
            await asyncio.sleep(interval)
            try:
                await self._send(ws, {"type": "pong"})
            except Exception:
                return

    # ── inbound dispatch ──────────────────────────────────────────────

    async def _on_frame(self, ws: Any, frame: dict) -> None:
        frame_type = frame.get("type")
        if frame_type == "ping":
            with contextlib.suppress(Exception):
                await self._send(ws, {"type": "pong"})
            return
        if frame_type == "discover":
            task = asyncio.ensure_future(self._handle_discover(ws, frame))
            task.add_done_callback(_log_task_error)
            return
        if frame_type == "chat":
            request_id = str(frame.get("request_id") or "")
            if not request_id:
                return
            task = asyncio.ensure_future(self._handle_chat(ws, frame))
            task.add_done_callback(_log_task_error)
            self._inflight[request_id] = task
            return
        if frame_type == "cancel":
            await self._cancel(str(frame.get("request_id") or ""))
            return
        # hello_ok / hello_error after handshake and unknown frames are ignored.

    async def _handle_discover(self, ws: Any, frame: dict) -> None:
        request_id = str(frame.get("request_id") or "")
        try:
            models = await self.collect_models()
        except Exception as exc:  # noqa: BLE001
            if request_id:
                await self._send(
                    ws, protocol.error(request_id=request_id, message=str(exc), code="discovery_failed")
                )
            return
        payload: dict = {
            "type": "models",
            "adapters": [a.name for a in self._adapters],
            "models": models,
        }
        if request_id:
            payload["request_id"] = request_id
        await self._send(ws, payload)

    async def _handle_chat(self, ws: Any, frame: dict) -> None:
        request_id = str(frame.get("request_id") or "")
        model_key = str(frame.get("model") or "")
        adapter_name = str(frame.get("adapter") or "")
        messages = list(frame.get("messages") or [])
        params = dict(frame.get("params") or {})
        adapter = self._adapter_for(adapter_name)
        if adapter is None:
            await self._send(
                ws,
                protocol.error(
                    request_id=request_id,
                    message=f"no adapter is running for {adapter_name or 'this machine'}",
                    code="adapter_unavailable",
                ),
            )
            return
        try:
            finish_reason: str | None = None
            async for event in adapter.stream_chat(
                model_key=model_key, messages=messages, params=params
            ):
                if "delta" in event and event["delta"]:
                    await self._send(
                        ws, protocol.chunk(request_id=request_id, delta=event["delta"])
                    )
                if event.get("finish_reason"):
                    finish_reason = event["finish_reason"]
                if event.get("done"):
                    await self._send(
                        ws,
                        protocol.done(
                            request_id=request_id,
                            usage=event.get("usage") or {},
                            model=model_key or None,
                        ),
                    )
                    # A finish_reason that arrived before done is advisory; the
                    # server reads it from the streaming chunk if present.
                    if finish_reason:
                        with contextlib.suppress(Exception):
                            await self._send(
                                ws,
                                protocol.chunk(
                                    request_id=request_id,
                                    delta="",
                                    finish_reason=finish_reason,
                                ),
                            )
                    return
        except AdapterError as exc:
            await self._send(
                ws,
                protocol.error(request_id=request_id, message=str(exc)),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._send(
                ws,
                protocol.error(request_id=request_id, message=f"connector error: {exc}"),
            )
        finally:
            self._inflight.pop(request_id, None)

    async def _cancel(self, request_id: str) -> None:
        task = self._inflight.pop(request_id, None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _cancel_all(self) -> None:
        tasks = list(self._inflight.values())
        self._inflight.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _send(self, ws: Any, payload: dict) -> None:
        async with self._send_lock:
            await ws.send(json.dumps(payload))

    def stop(self) -> None:
        self._stop.set()


class _TerminalClose(Exception):
    """The server will not accept this connector again; do not retry."""


def _decode(raw: Any) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        frame = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return frame if isinstance(frame, dict) else {}


def _agent_url(server: str) -> str:
    base = server.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    elif not base.startswith(("ws://", "wss://")):
        base = "wss://" + base
    return f"{base}/api/local-connect/agent"


def _log_task_error(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background task failed: %s", exc)
