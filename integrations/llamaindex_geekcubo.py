"""LlamaIndex LLM wrapper for GeekCubo.

Install:
    pip install llama-index-llms-openai-like

Usage:
    from llamaindex_geekcubo import GeekCubo

    llm = GeekCubo(model="auto", api_key="sk-geek-...")
    print(llm.complete("Hello!"))
"""

from __future__ import annotations

from typing import Any

try:
    from llama_index.llms.openai_like import OpenAILike
except ImportError as exc:
    raise ImportError(
        "llama-index-llms-openai-like is required: "
        "`pip install llama-index-llms-openai-like`"
    ) from exc


class GeekCubo(OpenAILike):
    """`OpenAILike` configured for a local GeekCubo by default."""

    def __init__(
        self,
        *,
        model: str = "auto",
        api_key: str,
        api_base: str = "http://127.0.0.1:8787/v1",
        is_chat_model: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            api_base=api_base,
            is_chat_model=is_chat_model,
            **kwargs,
        )
