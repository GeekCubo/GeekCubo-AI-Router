# Connecting tools and SDKs

[← Back to the README](../README.md)

How clients connect to GeekCubo: Connect a tool, OpenCode, Claude Code, Cursor, the native Anthropic and Gemini endpoints, streaming and the example configs in `integrations/`.

## Connect a tool

**Settings → Connect a tool** is the authoritative place for client-specific
configuration. It generates ready-to-paste configuration for OpenCode, Claude
Code, Cursor, Continue, Cline, Kilo Code, any generic OpenAI-compatible client,
cURL and the Python/TypeScript SDKs, using your installation's base URL and
routing ids:

- **Local (this host)** — the loopback endpoint, for clients running on the
  GeekCubo host itself (for example `http://127.0.0.1:8787/v1`).
- **Remote (public URL)** — the address set in `PUBLIC_BASE_URL` (for example
  `https://api.example.com/v1`). It is the default when configured and can be
  edited. A URL for that host is never generated with `http://` when the
  configured address is `https://`.

No secret is ever embedded: keys are referenced through the client-side
`GEEKCUBO_API_KEY` variable (see [Which key goes where](security.md#which-key-goes-where)).
That name is a convention the generated files wire in explicitly; no client
looks for it on its own. The files follow each tool's documented format. The
OpenCode configs were run against OpenCode 2.2.6; the others are not tested
against every tool version, so check the tool's own documentation if a field
has moved.

## Claude Code

Claude Code works because GeekCubo serves the Anthropic Messages API
(`POST /v1/messages`, streaming, tool use, `count_tokens`):

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"   # no /v1
export ANTHROPIC_AUTH_TOKEN="$GEEKCUBO_API_KEY"      # sent as Authorization: Bearer
export ANTHROPIC_MODEL="auto"                         # or a routing-profile id
claude
```

`ANTHROPIC_API_KEY` (sent as `x-api-key`) works as well; GeekCubo accepts
either header.

## Cursor and other limits

Cursor is supported for **chat models only** through its OpenAI-compatible
override; Cursor's own Tab completion and background agents keep
using Cursor's models. Anthropic-hosted extras outside the Messages API (for
example server-side web search tools) are not available and fail as ordinary
unsupported-tool responses.

## OpenCode

OpenCode 2.x reads a custom OpenAI-compatible provider from `opencode.json(c)`
([documentation](https://opencode.ai/docs/providers#custom)). Put your
GeekCubo key in the environment OpenCode starts from, then save:

```bash
export GEEKCUBO_API_KEY="sk-geek-..."
```

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "providers": {
    "geek": {
      "name": "GeekCubo",
      "env": ["GEEKCUBO_API_KEY"],
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": { "baseURL": "https://api.example.com/v1" },
      "models": { "auto": { "name": "GeekCubo auto" } }
    }
  }
}
```

Use your own endpoint: `https://<your-host>/v1` for a remote GeekCubo, or
`http://127.0.0.1:8787/v1` on the GeekCubo host. Select the model as
`geek/auto` (OpenCode's provider prefix plus the value GeekCubo receives).

OpenCode 1.x used a different, now deprecated schema (`provider` / `npm` /
`options` with `"apiKey": "{env:GEEKCUBO_API_KEY}"`). **Settings → Connect a
tool → OpenCode → Format** generates either one with your real base URL; do
not merge the two shapes in one file.

Both formats were verified with OpenCode 2.2.6 for text generation (streamed
chat completions). Agentic tool calling additionally depends on the model
GeekCubo routes to; a successful text request does not prove it.

### Documentation lookup tools (MCP)

Separately from the provider above, OpenCode can search GeekCubo's
documentation through the local, read-only `geekcubo-mcp` server. It needs no
GeekCubo server and no key, and works with whatever model OpenCode uses:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "geekcubo-knowledge": { "type": "local", "command": ["geekcubo-mcp", "serve"] }
    }
  }
}
```

Installation and the full tool reference: [GeekCubo Knowledge](geekcubo-knowledge.md#geekcubo-mcp-for-opencode-and-other-mcp-clients).

## Native protocol endpoints (Anthropic + Gemini)

GeekCubo speaks three inbound protocols against one routing pipeline. Clients
that only talk Anthropic or Gemini wire formats connect directly — no OpenAI SDK
required. Claude Code setup is shown [above](#claude-code); the Gemini
SDK works the same way:

```python
# google-genai SDK, pointed at GeekCubo (no /v1 in the base URL)
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Requests are translated at the edge into the same internal pipeline, so
`model="auto"`, the cross-provider prompt cache (shared across protocols),
routing strategies, and the analytics dashboard all work identically. Guides:
[integrations/claude-code.md](../integrations/claude-code.md),
[integrations/gemini-sdk.md](../integrations/gemini-sdk.md).

## Streaming

OpenAI-compatible SSE format with the standard `data: ... \n\n` framing and a terminal `[DONE]` sentinel — drop-in for any SDK that already streams from OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Example configs in `integrations/`

Example configs for [Claude Code](../integrations/claude-code.md), [Gemini SDK](../integrations/gemini-sdk.md), [Continue.dev](../integrations/continue.json), [Aider](../integrations/aider.md), [Cursor](../integrations/cursor.md), [LangChain](../integrations/langchain_geekcubo.py), [LlamaIndex](../integrations/llamaindex_geekcubo.py), [Vercel AI SDK](../integrations/vercel_ai.ts), and any tool that speaks the OpenAI Chat Completions protocol — plus native Anthropic and Gemini wire formats. See [`integrations/`](../integrations/). They use the Docker base URL `http://127.0.0.1:8787`; the JSON, Python and TypeScript files are syntax-checked, but they have not been run against every tool version.
