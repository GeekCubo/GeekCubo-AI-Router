"""Adapter for any OpenAI-compatible local endpoint.

LM Studio, vLLM, llama.cpp's server and most "OpenAI-compatible" tools expose
``GET /v1/models`` and ``POST /v1/chat/completions`` with SSE streaming. This
one class serves all of them; the concrete subclasses only differ in their
default base URL and display metadata.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import CHAT_READ_TIMEOUT_S, PROBE_TIMEOUT_S, AdapterError, BaseAdapter, ModelEntry


class OpenAICompatibleAdapter(BaseAdapter):
    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:8000"

    async def _probe(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/v1/models")
        response.raise_for_status()

    async def list_models(self) -> list[ModelEntry]:
        try:
            async with self._client() as client:
                response = await client.get("/v1/models")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001 - surfaced as a typed error
            raise AdapterError(f"{self.name}: {exc}") from exc
        entries: list[ModelEntry] = []
        for item in payload.get("data") or []:
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            meta = item.get("meta") or {}
            entries.append(
                ModelEntry(
                    model_key=model_id,
                    display_name=str(item.get("name") or model_id),
                    adapter=self.name,
                    context_length=_as_int(
                        meta.get("n_ctx")
                        or meta.get("context_length")
                        or item.get("context_length")
                    ),
                    metadata=_metadata_from(item),
                )
            )
        return entries

    async def stream_chat(
        self,
        *,
        model_key: str,
        messages: list[dict],
        params: dict,
    ) -> AsyncIterator[dict]:
        body = _completion_body(model_key, messages, params)
        usage: dict | None = None
        try:
            timeout = httpx.Timeout(
                connect=PROBE_TIMEOUT_S, read=CHAT_READ_TIMEOUT_S, write=30.0, pool=PROBE_TIMEOUT_S
            )
            async with self._client(timeout=timeout) as client:
                async with client.stream("POST", "/v1/chat/completions", json=body) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", "replace")
                        raise AdapterError(
                            f"{self.name}: HTTP {response.status_code}: {detail[:400]}"
                        )
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except ValueError:
                            continue
                        if event.get("usage"):
                            usage = _normalise_usage(event["usage"])
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            content = delta.get("content")
                            if content:
                                yield {"delta": content}
                            if choice.get("finish_reason"):
                                yield {"finish_reason": choice["finish_reason"]}
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"{self.name}: {exc}") from exc
        yield {"done": True, "usage": usage or {}}


def _completion_body(model_key: str, messages: list[dict], params: dict) -> dict:
    body: dict = {"model": model_key, "messages": messages, "stream": True}
    # Ask for usage on the final chunk when the server honours it; harmless if
    # it ignores the field.
    body["stream_options"] = {"include_usage": True}
    for key in (
        "temperature",
        "max_tokens",
        "top_p",
        "stop",
        "tools",
        "tool_choice",
        "seed",
        "response_format",
        "presence_penalty",
        "frequency_penalty",
        "parallel_tool_calls",
        # LM Studio and other OpenAI-compatible runtimes take this for the
        # reasoning models they recognise; the server rejects it otherwise.
        "reasoning_effort",
    ):
        if params.get(key) is not None:
            body[key] = params[key]
    return body


def _normalise_usage(raw: dict) -> dict:
    return {
        "prompt_tokens": int(raw.get("prompt_tokens") or 0),
        "completion_tokens": int(raw.get("completion_tokens") or 0),
        "total_tokens": int(
            raw.get("total_tokens")
            or (int(raw.get("prompt_tokens") or 0) + int(raw.get("completion_tokens") or 0))
        ),
    }


def _as_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _metadata_from(item: dict) -> dict:
    """Keep a small, JSON-safe slice of what the server reported."""
    out: dict = {}
    for key in ("object", "owned_by", "created", "arch", "publisher"):
        if key in item:
            out[key] = item[key]
    return out
