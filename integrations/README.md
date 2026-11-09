# Integrations

Drop-in configs that plug existing AI dev tools into a local GeekCubo
instance. All of these route via the standard OpenAI-compatible base URL —
nothing custom, nothing magic.

| Tool | File | What it gives you |
|---|---|---|
| **Continue.dev** | [`continue.json`](./continue.json) | Sidebar code chat / autocomplete / edit, routed through GeekCubo |
| **Aider** | [`aider.md`](./aider.md) | CLI pair programmer with GeekCubo as the LLM backend |
| **LangChain (Python)** | [`langchain_geekcubo.py`](./langchain_geekcubo.py) | Drop-in `GeekCubo()` LLM class |
| **LlamaIndex (Python)** | [`llamaindex_geekcubo.py`](./llamaindex_geekcubo.py) | Drop-in `GeekCubo()` LLM class |
| **Vercel AI SDK** | [`vercel_ai.ts`](./vercel_ai.ts) | OpenAI-provider config pointing at GeekCubo |
| **OpenAI Python SDK** | (any) | Just set `base_url=http://127.0.0.1:8787/v1` |
| **Cursor** | [`cursor.md`](./cursor.md) | Custom OpenAI-compatible model config |

The pattern is the same everywhere: **point the OpenAI base URL at `http://127.0.0.1:8787/v1` (the Docker Compose default) and use an `sk-geek-*` key from Settings → API Keys.** You get `model="auto"` routing, inference fallback, and the local cost dashboard for free.

These files are examples: they are syntax-checked but not run against every
tool version. **Settings → Connect a tool** in the dashboard generates the same
configuration with your real base URL and routing ids.

## Why GeekCubo for these tools?

- **One key for everything** — your tool ships an "OpenAI key" config; you drop in a `sk-geek-*` and reach every model your configured providers serve.
- **Cost guardrails** — see exactly what your editor / agent is spending in the local dashboard.
- **Auto-routing** — `model="auto"` picks a capable model per request using the strategy you choose (Balanced, Cheapest, Quality First, Adaptive or Adaptive-Gated). With Adaptive-Gated, tool calls and long prompts go to your *Hard* pool and simple requests to your *Mundane* pool.
- **Failover** — if a provider is rate-limited or down, Auto retries the next capable candidate from your other configured providers.
