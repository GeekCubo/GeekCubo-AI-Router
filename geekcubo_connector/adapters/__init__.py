"""Concrete OpenAI-compatible adapters and the adapter registry.

These share the streaming implementation in :mod:`.openai_compat`; each only
differs in default endpoint and reporting name so the dashboard can tell an
LM Studio model from a vLLM one.
"""

from __future__ import annotations

from .base import AdapterError, BaseAdapter
from .ollama import OllamaAdapter
from .openai_compat import OpenAICompatibleAdapter


class LMStudioAdapter(OpenAICompatibleAdapter):
    name = "lmstudio"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:1234"


class VLLMAdapter(OpenAICompatibleAdapter):
    name = "vllm"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:8000"


class LlamaCppAdapter(OpenAICompatibleAdapter):
    name = "llamacpp"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:8080"


class CustomAdapter(OpenAICompatibleAdapter):
    """A user-provided OpenAI-compatible endpoint.

    Unlike the others it has no meaningful default; the operator must supply a
    base URL. Kept in the registry so a config can name it explicitly.
    """

    name = "custom"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:8000"


ADAPTER_CLASSES: dict[str, type[BaseAdapter]] = {
    OllamaAdapter.name: OllamaAdapter,
    LMStudioAdapter.name: LMStudioAdapter,
    VLLMAdapter.name: VLLMAdapter,
    LlamaCppAdapter.name: LlamaCppAdapter,
    CustomAdapter.name: CustomAdapter,
}

# Order in which auto-detection probes adapters. Ollama first because it is the
# most common local runtime on developer machines.
PROBE_ORDER: tuple[str, ...] = ("ollama", "lmstudio", "vllm", "llamacpp", "custom")


def build_adapter(
    name: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> BaseAdapter:
    cls = ADAPTER_CLASSES.get(name)
    if cls is None:
        raise AdapterError(f"unknown adapter: {name!r}")
    return cls(base_url=base_url, api_key=api_key)


__all__ = [
    "ADAPTER_CLASSES",
    "PROBE_ORDER",
    "AdapterError",
    "BaseAdapter",
    "CustomAdapter",
    "LlamaCppAdapter",
    "LMStudioAdapter",
    "OllamaAdapter",
    "VLLMAdapter",
    "build_adapter",
]
