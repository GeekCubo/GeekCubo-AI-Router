"""Adapter interface and shared HTTP helpers.

An *adapter* knows how to talk to one local inference server on this machine.
Each adapter can:

* ``available()``  — report whether the server is reachable right now;
* ``list_models()`` — return catalog entries (see :class:`ModelEntry`);
* ``stream_chat()`` — yield text deltas for a chat request.

The connector multiplexes adapters behind one WebSocket. Adapters never know
about WebSockets; they speak HTTP to localhost and yield plain dicts.

Every network call is bounded by a short timeout so a hung local server cannot
stall the connector's receive loop.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from typing import AsyncIterator

import httpx

# Local servers answer fast or not at all; a discovery probe must not hang.
PROBE_TIMEOUT_S = 3.0
# Chat is long-running; per-read timeout is generous but bounded.
CHAT_READ_TIMEOUT_S = 300.0


@dataclass
class ModelEntry:
    """One model a machine can serve.

    The server stores this verbatim (minus ``extra``) and exposes it to routing
    as ``local/<machine>/<model_key>``.
    """

    model_key: str
    display_name: str
    adapter: str
    family: str | None = None
    parameter_count: str | None = None
    quantization: str | None = None
    context_length: int | None = None
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    metadata: dict = field(default_factory=dict)

    def to_wire(self) -> dict:
        data = asdict(self)
        # Drop empty optional fields so the server stores a compact row.
        return {k: v for k, v in data.items() if v not in (None, "", {})}


class AdapterError(Exception):
    """Raised when an adapter cannot satisfy a request."""


class BaseAdapter(abc.ABC):
    name: str = "custom"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or self.default_base_url()).rstrip("/")
        self.api_key = api_key

    @classmethod
    @abc.abstractmethod
    def default_base_url(cls) -> str:
        """The endpoint this adapter talks to when the operator configures none."""

    def _client(self, *, timeout: float = PROBE_TIMEOUT_S) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=timeout
        )

    async def available(self) -> bool:
        """Return True if the server answers a cheap liveness probe."""
        try:
            async with self._client() as client:
                await self._probe(client)
            return True
        except Exception:
            return False

    async def _probe(self, client: httpx.AsyncClient) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def list_models(self) -> list[ModelEntry]:
        """Enumerate servable models. Empty list if the server has none."""

    @abc.abstractmethod
    async def stream_chat(
        self,
        *,
        model_key: str,
        messages: list[dict],
        params: dict,
    ) -> AsyncIterator[dict]:
        """Yield ``{"delta": str}`` frames, then ``{"done": True, "usage": {...}}``.

        Implementations must raise :class:`AdapterError` on transport or
        protocol failure so the connector can report a clean ``error`` frame.
        """
