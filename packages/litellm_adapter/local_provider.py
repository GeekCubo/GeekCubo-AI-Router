"""LiteLLM CustomLLM handler for Local AI Connect.

Registers a `geekcubo_local` provider with LiteLLM so the Router can carry
`local/<machine>/<model>` entries like any other deployment. The wire model id
is ``geekcubo_local/<machine_id>::<model_key>``; the handler parses that back
into `(machine_id, model_key)` and dispatches over the machine's agent
WebSocket.

Importing this module has a side effect: it appends the handler to
``litellm.custom_provider_map`` exactly once. `client.py` imports it before
constructing a Router so the map is live by the time deployments are resolved.
Keeping this out of `client.py` means the heavy LiteLLM typing imports only
happen for installs that actually use local models.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import litellm
from litellm import CustomLLM
from litellm.types.utils import GenericStreamingChunk, ModelResponse

from app.local_connect import catalog as local_catalog
from app.local_connect import dispatcher

PROVIDER_NAME = local_catalog.LITELLM_PROVIDER


def _split(model: str) -> tuple[str, str]:
    parsed = local_catalog.parse_wire_model_id(model)
    if parsed is None:
        # The Router hands us the full wire id (`provider/...`). A deployment
        # with a malformed id is a configuration bug, not a user error.
        raise ValueError(f"malformed local model id: {model!r}")
    return parsed


async def _resolve_adapter(machine_id: str, model_key: str) -> str:
    """Look up the adapter a model should be sent to.

    The model catalog row records which connector adapter owns the model key,
    so a machine running both Ollama and LM Studio routes to the right one.
    Falls back to `ollama` for a key the server has never seen.
    """
    try:
        from sqlalchemy import select

        from packages.db import session as session_mod
        from packages.db.models.local_connect import LocalModel

        factory = session_mod._session_factory
        if factory is None:
            return "ollama"
        async with factory() as db:
            row = (
                await db.execute(
                    select(LocalModel).where(
                        LocalModel.machine_id == machine_id,
                        LocalModel.model_key == model_key,
                    )
                )
            ).scalar_one_or_none()
            return row.adapter if row is not None else "ollama"
    except Exception:
        return "ollama"


def _raise_for_litellm(exc: dispatcher.LocalConnectError) -> None:
    """Re-raise a dispatch failure as the LiteLLM exception LiteLLM preserves.

    Any other exception raised inside a CustomLLM handler is re-wrapped by
    LiteLLM as a generic ``APIConnectionError`` with status 500, losing both
    our status and our error code. Exceptions that are already LiteLLM types
    pass through untouched, so attach the local code/status to one of those
    and let `client._translate_error` recover them.
    """
    if exc.http_status >= 502:
        error = litellm.ServiceUnavailableError(
            message=str(exc), llm_provider=PROVIDER_NAME, model=PROVIDER_NAME
        )
    else:
        error = litellm.BadRequestError(
            message=str(exc), llm_provider=PROVIDER_NAME, model=PROVIDER_NAME
        )
    # Preserved by LiteLLM's exception pass-through; read in client.py. The
    # marker keeps `_translate_error` from mistaking an unrelated provider's
    # own `code` attribute for a Local AI Connect error code.
    error.geek_local_code = exc.code  # type: ignore[attr-defined]
    error.geek_local_status = exc.http_status  # type: ignore[attr-defined]
    raise error from exc


def _messages_to_frames(messages: list[dict]) -> list[dict]:
    """Pass message content through verbatim; the connector speaks OpenAI."""

    return list(messages or [])


class LocalConnectHandler(CustomLLM):
    """Bridges a LiteLLM Router call onto the connector WebSocket protocol."""

    async def acompletion(self, *args: Any, **kwargs: Any) -> ModelResponse:
        model = kwargs.get("model") or (args[0] if args else "")
        messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
        optional_params = kwargs.get("optional_params") or {}
        machine_id, model_key = _split(str(model))
        adapter = await _resolve_adapter(machine_id, model_key)
        params = _completion_params(optional_params)
        try:
            result = await dispatcher.dispatch_chat(
                dispatcher.ChatTarget(machine_id=machine_id, model_key=model_key, adapter=adapter),
                messages=_messages_to_frames(messages),
                params=params,
            )
        except dispatcher.LocalConnectError as exc:
            _raise_for_litellm(exc)
        usage = result.get("usage") or {}
        return _to_model_response(
            model=str(model),
            text=result.get("text") or "",
            usage=usage,
            finish_reason=params.get("_finish_reason") or "stop",
        )

    async def astreaming(self, *args: Any, **kwargs: Any):
        model = kwargs.get("model") or (args[0] if args else "")
        messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
        optional_params = kwargs.get("optional_params") or {}
        machine_id, model_key = _split(str(model))
        adapter = await _resolve_adapter(machine_id, model_key)
        params = _completion_params(optional_params)
        target = dispatcher.ChatTarget(
            machine_id=machine_id, model_key=model_key, adapter=adapter
        )
        usage: dict | None = None
        finish_reason = "stop"
        stream = dispatcher.stream_chat(
            target, messages=_messages_to_frames(messages), params=params
        )
        frames = stream.__aiter__()
        try:
            while True:
                try:
                    frame = await frames.__anext__()
                except StopAsyncIteration:
                    return
                except dispatcher.LocalConnectError as exc:
                    _raise_for_litellm(exc)
                frame_type = frame.get("type")
                if frame_type == "chunk":
                    if frame.get("usage"):
                        usage = frame["usage"]
                    if frame.get("finish_reason"):
                        finish_reason = frame["finish_reason"]
                    yield GenericStreamingChunk(
                        text=frame.get("delta") or "",
                        is_finished=False,
                        finish_reason="",
                        usage=None,
                        index=0,
                        tool_use=None,
                    )
                elif frame_type == "done":
                    if frame.get("usage"):
                        usage = frame["usage"]
                    yield GenericStreamingChunk(
                        text="",
                        is_finished=True,
                        finish_reason=finish_reason or "stop",
                        usage=usage,
                        index=0,
                        tool_use=None,
                    )
                    return
        finally:
            await stream.aclose()


def _completion_params(optional_params: dict) -> dict:
    out: dict = {}
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
        # Reasoning controls, already translated for the serving runtime by
        # app.reasoning: Ollama takes `think`, OpenAI-compatible servers take
        # `reasoning_effort`. Forwarded verbatim; absent unless requested.
        "think",
        "reasoning_effort",
    ):
        if key in optional_params and optional_params[key] is not None:
            out[key] = optional_params[key]
    return out


def _to_model_response(
    *,
    model: str,
    text: str,
    usage: dict,
    finish_reason: str,
) -> ModelResponse:
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(
        usage.get("completion_tokens") or usage.get("output_tokens") or 0
    )
    response = ModelResponse(
        id=f"local-{uuid.uuid4().hex}",
        model=model,
        created=int(time.time()),
        object="chat.completion",
    )
    response.choices[0].message.content = text
    response.choices[0].finish_reason = finish_reason or "stop"
    response.usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    return response


_handler: LocalConnectHandler | None = None


def register() -> None:
    """Register the provider with LiteLLM once per process."""
    global _handler
    if _handler is not None:
        return
    _handler = LocalConnectHandler()
    providers = getattr(litellm, "custom_provider_map", None) or []
    if not any(entry.get("provider") == PROVIDER_NAME for entry in providers):
        providers.append({"provider": PROVIDER_NAME, "custom_handler": _handler})
    litellm.custom_provider_map = providers
    # LiteLLM resolves a provider string against `provider_list` /
    # `_custom_providers`; the map alone is not enough for the Router's
    # provider detection on a cold process.
    from litellm.utils import custom_llm_setup

    custom_llm_setup()


register()
