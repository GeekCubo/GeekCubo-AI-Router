"""Native Ollama adapter.

Ollama exposes ``GET /api/tags`` for the catalog and ``POST /api/chat`` with
NDJSON streaming. We speak its native protocol rather than its OpenAI shim
because ``/api/tags`` returns richer model metadata (family, parameter size,
quantization) that the dashboard surfaces.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import CHAT_READ_TIMEOUT_S, PROBE_TIMEOUT_S, AdapterError, BaseAdapter, ModelEntry


class OllamaAdapter(BaseAdapter):
    name = "ollama"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:11434"

    async def _probe(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/tags")
        response.raise_for_status()

    async def list_models(self) -> list[ModelEntry]:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"ollama: {exc}") from exc
        entries: list[ModelEntry] = []
        for item in payload.get("models") or []:
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name:
                continue
            details = item.get("details") or {}
            capabilities: list = []
            try:
                async with self._client() as client:
                    response = await client.post("/api/show", json={"model": name})
                    response.raise_for_status()
                    reported = response.json().get("capabilities")
                    if isinstance(reported, list):
                        capabilities = reported
            except Exception:
                pass
            entries.append(
                ModelEntry(
                    model_key=name,
                    display_name=name,
                    adapter=self.name,
                    family=details.get("family"),
                    parameter_count=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    context_length=_context_length(item),
                    supports_tools=False,
                    supports_vision="vision" in capabilities,
                    metadata={
                        "size": item.get("size"),
                        "modified_at": item.get("modified_at"),
                        "digest": item.get("digest"),
                    },
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
        usage: dict | None = None
        try:
            body = _chat_body(model_key, messages, params)
            timeout = httpx.Timeout(
                connect=PROBE_TIMEOUT_S, read=CHAT_READ_TIMEOUT_S, write=30.0, pool=PROBE_TIMEOUT_S
            )
            async with self._client(timeout=timeout) as client:
                async with client.stream("POST", "/api/chat", json=body) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", "replace")
                        raise AdapterError(
                            f"ollama: HTTP {response.status_code}: {detail[:400]}"
                        )
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        message = event.get("message") or {}
                        content = message.get("content")
                        if content:
                            yield {"delta": content}
                        if event.get("done"):
                            usage = _normalise_usage(event)
                            if event.get("done_reason"):
                                yield {"finish_reason": _finish_reason(event["done_reason"])}
                            break
        except AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"ollama: {exc}") from exc
        yield {"done": True, "usage": usage or {}}


def _chat_body(model_key: str, messages: list[dict], params: dict) -> dict:
    options: dict = {}
    if params.get("temperature") is not None:
        options["temperature"] = params["temperature"]
    if params.get("top_p") is not None:
        options["top_p"] = params["top_p"]
    if params.get("max_tokens") is not None:
        options["num_predict"] = params["max_tokens"]
    if params.get("stop") is not None:
        options["stop"] = params["stop"]
    if params.get("seed") is not None:
        options["seed"] = params["seed"]
    if params.get("presence_penalty") is not None:
        options["presence_penalty"] = params["presence_penalty"]
    if params.get("frequency_penalty") is not None:
        options["frequency_penalty"] = params["frequency_penalty"]
    body: dict = {"model": model_key, "messages": _ollama_messages(messages), "stream": True}
    if options:
        body["options"] = options
    if params.get("tools"):
        body["tools"] = params["tools"]
    if params.get("response_format", {}).get("type") == "json_object":
        body["format"] = "json"
    return body


def _ollama_messages(messages: list[dict]) -> list[dict]:
    converted: list[dict] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            converted.append(message)
            continue
        text_parts: list[str] = []
        images: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                raise AdapterError("ollama: unsupported message content part")
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
            elif part.get("type") == "image_url":
                image_url = part.get("image_url")
                image_url = image_url.get("url") if isinstance(image_url, dict) else image_url
                if not isinstance(image_url, str) or not image_url.startswith("data:image/"):
                    raise AdapterError("ollama: images must use base64 image data URLs")
                header, separator, encoded = image_url.partition(",")
                if not separator or not header.endswith(";base64") or not encoded:
                    raise AdapterError("ollama: invalid base64 image data URL")
                images.append(encoded)
            else:
                raise AdapterError("ollama: unsupported message content part")
        converted_message = {key: value for key, value in message.items() if key != "content"}
        converted_message["content"] = "".join(text_parts)
        if images:
            converted_message["images"] = images
        converted.append(converted_message)
    return converted


def _context_length(item: dict) -> int | None:
    """Ollama reports the window in a couple of places depending on version."""
    for key in ("context_length", "n_ctx"):
        value = item.get(key)
        if value:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    details = item.get("details") or {}
    value = details.get("context_length")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _normalise_usage(event: dict) -> dict:
    prompt = int(event.get("prompt_eval_count") or 0)
    completion = int(event.get("eval_count") or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _finish_reason(reason: str) -> str:
    return {"length": "length", "stop": "stop"}.get(str(reason), "stop")
