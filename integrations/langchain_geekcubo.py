"""LangChain LLM wrapper for GeekCubo.

GeekCubo speaks the OpenAI Chat Completions protocol, so we subclass `ChatOpenAI`
with sensible defaults pointing at the local server. Use `model="auto"` to let
GeekCubo pick a capable model for each call according to your routing strategy.

Install:
    pip install langchain-openai

Usage:
    from langchain_geekcubo import GeekCubo

    llm = GeekCubo(model="auto", api_key="sk-geek-...")
    print(llm.invoke("Hello in haiku form"))
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_openai import ChatOpenAI
except ImportError as exc:
    raise ImportError(
        "langchain-openai is required: `pip install langchain-openai`"
    ) from exc


class GeekCubo(ChatOpenAI):
    """Drop-in `ChatOpenAI` that talks to a local GeekCubo by default.

    Override `base_url` to point at a remote GeekCubo instance.
    """

    def __init__(
        self,
        *,
        model: str = "auto",
        api_key: str,
        base_url: str = "http://127.0.0.1:8787/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
