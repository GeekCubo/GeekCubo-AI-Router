# Claude Code → GeekCubo

GeekCubo serves the Anthropic Messages API natively (`POST /v1/messages`), so
Claude Code and the official `anthropic` SDKs connect without changes.

## Claude Code

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787    # no /v1 suffix
export ANTHROPIC_API_KEY=sk-geek-...               # your GeekCubo key (or ANTHROPIC_AUTH_TOKEN)
# optional: pin the model (any catalog model, or "auto")
# export ANTHROPIC_MODEL=claude-3-5-sonnet-latest

claude
```

Requests route through GeekCubo's normal pipeline: `model="auto"` works, the
prompt cache works, and every request lands in the local dashboard.

## Anthropic Python SDK

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:8787",   # SDK appends /v1/messages itself
    api_key="sk-geek-...",
)
message = client.messages.create(
    model="auto",                        # or any catalog model
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)
print(message.content[0].text)
```

Streaming (`client.messages.stream(...)`) and tool use work as usual.

## Known limitations (v1)

- `thinking` (extended thinking) and `output_config.effort` are mapped to
  GeekCubo's normalized reasoning effort and translated for the model that
  serves the request: adaptive effort or a thinking budget for Claude, the
  native control for other providers. A model that cannot honour it returns a
  400 `invalid_request_error`, never a dropped setting. Budget ↔ level
  mapping is approximate. Signed thinking blocks are returned and accepted
  back, so tool loops with extended thinking keep working against Claude
  models. They are never forwarded to non-Anthropic models. See
  [Reasoning effort](../docs/reasoning.md#native-anthropic-and-gemini-endpoints).
- `top_k` is dropped; `temperature` / `top_p` pass through, and values
  outside the API's own 0–1 range are rejected with a 400 rather than
  forwarded (an upstream rejection would reach you as a retryable 500).
  `max_tokens` must be >= 1, likewise.
- `stop_sequences` beyond the OpenAI wire cap of 4 are truncated to the
  first 4 (a `structlog` warning is emitted).
- Images inside a `tool_result` are forwarded as a user message following
  the tool result, since the internal format's tool messages are
  text-only. Non-text blocks in `system` (which the API itself does not
  allow) are dropped with a warning.
- Streaming `message_start.usage.input_tokens` is the same estimate
  `/v1/messages/count_tokens` returns — the upstream only reports the
  exact count at end-of-stream, where it is sent in `message_delta`.
- Server-side tools (web search, computer use), PDF `document` blocks, and
  the Files API return 400. Custom function tools are fully supported.
- `POST /v1/messages/count_tokens` returns an estimate
  (`litellm.token_counter`, chars/4 fallback), good enough for Claude
  Code's context tracking.
