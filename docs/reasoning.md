# Reasoning effort

[← Back to the README](../README.md)

GeekCubo accepts one normalized reasoning setting and translates it into the
parameter each upstream model actually understands. An explicit setting is
either honoured, visibly downgraded (only when your routing policy allows it),
or rejected with a client error. It is never silently dropped.

## Levels

`reasoning_effort` takes one of:

| Level | Meaning |
|---|---|
| *(omitted)* | **Default**: no parameter is sent and the model uses its own default. This is not the same as any level. |
| `none` | Reasoning switched off, where the model allows it |
| `minimal` | The lowest non-zero effort (e.g. GPT-5) |
| `low`, `medium`, `high` | The common graded levels |
| `xhigh` | Extra high (e.g. GPT-5.2, newer Claude) |
| `max` | Maximum (newer Claude adaptive thinking) |

Values are case-insensitive. An empty string or `null` means Default. Any
other value returns **422**.

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $GEEKCUBO_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"o3","reasoning_effort":"high","messages":[{"role":"user","content":"hi"}]}'
```

## What the response tells you

When a request sets an effort, the response carries:

- `x-geek-reasoning-requested`: the level you asked for
- `x-geek-reasoning-effective`: the level actually sent upstream
- `x-geek-reasoning-downgraded: true`: only when the two differ

A request without an effort adds none of these, and it behaves exactly as it
did before this feature.

## Capability: Supported, Unsupported, Unknown

Each model's supported levels come from LiteLLM's model metadata plus what a
local runtime reports:

- **Confirmed levels.** For OpenAI-style models, a model counts only if
  LiteLLM marks it `supports_reasoning`. `low`/`medium`/`high` are then
  available. `none`, `minimal`, `xhigh` and `max` each need their own explicit
  flag. Examples: o3 offers low/medium/high; gpt-5 adds minimal; gpt-5.1 adds
  none; gpt-5.2 adds xhigh.
- **Only levels that reach the provider as asked.** Every advertised level is
  checked against what LiteLLM actually sends. Two levels that would become
  the same request are offered as one, under the name the request really
  carries. Examples: Gemini 3 Pro offers low/medium/high, because LiteLLM
  sends `thinkingLevel: low` for none, minimal and low alike. Mistral Medium 3
  offers none/high.
- **Confirmed unsupported.** The model is catalogued and either has no
  reasoning control (e.g. gpt-4o), or LiteLLM accepts the effort but sends
  nothing for it (Magistral, which only gets a fixed system prompt). Sending
  an effort to it returns **400 `unsupported_reasoning_effort`**.
- **Unknown.** Nothing is known: custom-provider models without evidence,
  models LiteLLM does not catalogue, LM Studio models. These are **attempted
  with the effort preserved**. If the provider rejects the parameter, the
  client gets a 400 compatibility error, never a 503.

### Custom providers and gateways: evidence per endpoint

A model name says nothing about what a particular endpoint does with the
field. Live testing found a gateway serving `gpt-6.1-sol` that accepts **any**
`reasoning_effort`, including an invalid value, and returns identical
reasoning usage. So for custom providers GeekCubo **never borrows a
capability by model name**. Abliterated, uncensored or fine-tuned variants are
treated the same way: as separate deployments with no inherited capability.

Evidence for a custom model, in priority order:

1. **Administrator override**: `PATCH /v1/custom-providers/{id}/models/{row}`
   with `{"reasoning_levels": ["low", "high"]}` (`[]` = no effort control) or
   `{"clear_reasoning": true}`.
2. **Verification**: in the dashboard, **Providers → Manage Models → Actions →
   Verify reasoning** (API:
   `POST /v1/custom-providers/{id}/models/{row}/verify-reasoning`). A
   confirmation explains that it sends real requests using the provider's
   stored key, which may cost credits.
   - It runs only when an administrator asks, never automatically.
   - It costs at most four tiny completions (default, `low`, `high`, one
     invalid value), with no retries and a one-minute cooldown per model.
   - A result is stored only when it is conclusive:
     - the endpoint rejects the invalid value, or
     - reasoning usage clearly follows the level, or
     - everything is accepted with no difference (recorded as "field
       ignored", so the setting is then refused instead of silently dropped).
   - Rate limits, outages and ambiguous signals record nothing.
   - Results expire after 30 days, and stop applying if the model id or the
     provider URL changes.
3. Otherwise **Unknown**.

The model list returns `reasoning_levels`, `reasoning_source`
(`administrator_override`, `verified` or `unknown`) and the last
`reasoning_observation`.

In the dashboard, the result appears in the model's detail row, and **Details**
always shows the current reasoning status:

| Status | Meaning |
|---|---|
| Verified support: low, high | The levels shown are honoured; others are refused for this model |
| Field ignored / Verified unsupported | Requests with an effort are refused instead of silently ignored |
| Inconclusive | The provider gave no usable evidence; nothing is stored and the model stays Unknown |
| Provider unavailable | A rate limit, outage or capacity error; nothing is stored |
| Verification failed | The request could not be completed (for example, the cooldown is active) |
| Verification expired | The last result is older than 30 days and no longer applies |
| Not yet verified | No override and no verification: Unknown |
| Override: … | An administrator set the levels; this always wins |

The evidence lists the exact model, the provider, each request sent (level,
HTTP status, reported reasoning usage), the basis for the conclusion, when it
was verified and when it expires. Built-in providers keep using LiteLLM's metadata, as
described above.

`GET /api/routing/models` publishes `reasoning_levels` per model: a list when
confirmed (an empty list means no effort control) or `null` when Unknown. It
also publishes `auto_reasoning_levels`, the levels at least one Auto-eligible
model confirms.

## Provider translation

| Provider | What is sent |
|---|---|
| OpenAI, Groq, xAI, OpenRouter, other OpenAI-style providers and custom providers | `reasoning_effort` |
| Anthropic, newer models with adaptive thinking | `thinking: {type: adaptive}` + `output_config.effort` in low/medium/high, plus `xhigh`/`max` only where the model's metadata flags them (claude-opus-4-6 has `max` but not `xhigh`). `minimal` is not offered. `none` → `thinking: {type: disabled}`, except on always-on models (Fable/Mythos 5), which cannot turn thinking off and so do not offer `none`. |
| Anthropic, older extended thinking | `thinking: {type: enabled, budget_tokens}` with low 1024 / medium 2048 / high 4096 / xhigh 8192 / max 16384. The budget must be below `max_tokens`; otherwise the request returns 400 instead of being trimmed. |
| Gemini | `reasoning_effort`, which LiteLLM turns into a thinking budget (2.5) or a thinking level (3). `xhigh`/`max` are not available. Gemini 2.5 Pro cannot switch thinking off, so `none` is not offered there. Gemini 3 Pro offers low/medium/high. Gemini 3 Flash also offers a real `minimal`. |
| DeepSeek (on/off thinking) | `none` → disabled, `high` → enabled. No graded levels are offered. |
| Ollama (Local AI Connect) | `think`: a named level when the model reports levels (gpt-oss: low/medium/high), otherwise `true`/`false`. A model that reports nothing accepts only `none` and `high`. In Auto, such a model is skipped for any other level and the next candidate serves the request. |
| LM Studio / other OpenAI-compatible local servers | `reasoning_effort`, allowed for that single call only. These models stay Unknown because the runtime does not report support. |

The global LiteLLM `drop_params` option stays **off**: no parameter is ever
removed quietly.

## Auto routing

Auto keeps a single mixed pool. Reasoning is one more eligibility check next
to tools, vision and JSON:

1. With no effort requested, routing is unchanged.
2. With an effort, models **confirmed** unable to honour it are removed.
   Confirmed and Unknown models stay, and the strategy ranks them as usual.
   Every candidate is translated for its own provider. One that cannot
   express the level is skipped rather than called without it, even when it
   ranked first: for example, an Ollama model that reported no levels, or a
   Claude thinking budget that does not fit `max_tokens`. The next candidate
   becomes the primary, and the routing notes name the skipped model. Only
   when no candidate can express the level does the request fail with 400.
   A pinned model is strict: if it cannot express the level, the result is
   400.
4. If a provider refuses the level at request time, the request moves on to
   the next candidate with the same level. When none is left, the result is
   400 `unsupported_reasoning_effort`, never a retryable 503.
3. If every eligible model is confirmed incompatible:
   - **Strict** (default): the request fails with 422
     `x-geek-routing-diagnosis: reasoning_mismatch`.
   - **Downgrade allowed**: Auto uses the highest level *below* the request
     that some model supports, never below the policy's `min_effort` (default
     `low`). It never lands on `none`/`minimal` and never upgrades. The
     headers show requested vs effective.

Policy (`PUT /v1/routing`, or the routing policy editor):

```json
{"policy": {"reasoning": {"allow_downgrade": true, "min_effort": "low"}}}
```

The prompt cache keys on both the requested and the effective level, so
different levels, and downgraded results, never share an entry.

## Native Anthropic and Gemini endpoints

- `POST /v1/messages`: `thinking` (`enabled` + `budget_tokens`, `adaptive`,
  `disabled`) and `output_config.effort` map to a level. Budgets map
  approximately: ≤1024 low, ≤2048 medium, ≤4096 high, ≤8192 xhigh, above that
  max. An unknown `thinking.type` returns 400.
- **Thinking continuity (tool loops).** With thinking on, Anthropic requires
  the assistant turn that made a tool call to come back with its signed
  thinking blocks, unchanged. `/v1/messages` therefore returns signed
  `thinking` and `redacted_thinking` blocks (streaming and non-streaming).
  When the client sends them back, they reach the Anthropic model first and
  unchanged. Unsigned blocks are not carried. The blocks are forwarded only
  to an Anthropic model with thinking on; they never reach another provider,
  and they never appear in Native Chat history, request logs or analytics.
  If a tool-loop turn arrives without them while thinking is on, the request
  returns 400 `invalid_request_error` explaining what is missing, rather than
  silently running the turn without thinking. Choosing `none` (thinking
  disabled) needs no blocks.
- `POST /v1beta/models/{model}:generateContent`: `thinkingConfig.thinkingLevel`
  maps directly. For `thinkingBudget`, `0` → none, `-1` → model default,
  positive → nearest level. `includeThoughts` alone sets nothing. Invalid
  values return 400.

Compatibility errors come back in each protocol's own format as an
invalid-request (400) error, never as a retryable server error.

## Native Chat

A compact **Reasoning** selector sits next to the model picker:

- **Default** is always available and sends nothing.
- For a pinned model, only its confirmed levels are listed. For an Unknown
  model, every level is listed under *Support not confirmed*. For a model with
  no effort control, the selector is disabled.
- **Auto** lists the levels its pool can satisfy.
- When you switch model and the chosen level is not available, it resets to
  Default with a notice.
- The choice is saved per conversation and reused by Regenerate. Each
  assistant message shows the effective level, plus the requested one when
  Auto downgraded it.

The dashboard Chat API takes the same field:
`POST /api/chat/conversations/{id}/messages` and `…/regenerate` accept
`"reasoning_effort"` (a level, or `"default"`).
`PATCH /api/chat/conversations/{id}` stores it.

## Live verification (November 2026)

Minimal paid calls through the configured OpenAI-compatible gateway (Apixo),
direct and through GeekCubo. "Usage" is the provider-reported reasoning-token
count. The gateway's behaviour is what was measured; it is not a claim about
each model vendor's own API.

| Family | Model (gateway id) | Default | Levels sent | Observed | GeekCubo result |
|---|---|---|---|---|---|
| GPT | `gpt-6.1-sol` | 0 reasoning tokens | low, high, invalid | All accepted, including an invalid value; usage identical | Verification records "field ignored"; `reasoning_effort` is then refused with 400 |
| Claude | `claude-haiku-5-5` | no reasoning fields | low, high, minimal | All accepted; no reasoning usage reported | Unknown (no evidence either way) |
| Grok | `grok-4.7` | 86 | low 34, high 106 | Usage follows the level | Forwarded as `reasoning_effort`; headers report requested = effective |
| DeepSeek | `deepseek-v4.1-flash` | none | high 19, none 0 | `none` disables, `high` enables | Same through GeekCubo (high 14, none 0) |
| GLM | `glm-5.3-flash` | 43 | high 45, none 45 | `none` ignored: still reasons | Unknown; an administrator can set `[]` or verify |
| Kimi | `kimi-k3` | 52 | high 17, none 1 | `none` nearly disables | GeekCubo call returned a transient 503 (reported as such) |
| Qwen | `qwen3-abliterated` | 503 at capacity | not tested | n/a | Untested |
| Gemma | `gemma-4-31b-abliterated` | none | high | Accepted; no reasoning usage | Unknown |
| Gemini | `gemini-4-argon` | none | low, high | `high` produced reasoning text | Unknown |
| DeepSeek (abliterated) | `deepseek-v4.1-flash-1017-abliterated` | 0 | high 0 | Gateway served a different id; no reasoning | Unknown, treated separately from the base model |

## Limitations

- Built-in capability depends on LiteLLM's metadata. Models it does not flag
  (for example grok-3-mini at the time of writing) are Unknown, not
  Supported.
- Custom and gateway models are Unknown until an administrator sets or
  verifies them. Verification needs a measurable signal (reasoning usage or a
  validation error); gateways that report neither stay Unknown.
- The Gemini 2.5 Pro "cannot switch thinking off" rule and the Anthropic
  thinking-continuity requirement follow the providers' documentation. They
  are verified against LiteLLM's request bodies, not against live provider
  calls.
- OpenAI-format clients (`/v1/chat/completions`) receive Claude's thinking as
  LiteLLM's `thinking_blocks` / `reasoning_content` fields. To continue a
  Claude tool loop with thinking on, they must send `thinking_blocks` back on
  the assistant turn; otherwise they get the compatibility error above.
- The Gemini endpoint does not carry Gemini thought signatures between turns
  (a pre-existing limitation, unrelated to reasoning effort).
- Budget ↔ level mapping for Anthropic/Gemini budget interfaces is
  approximate.
- Reasoning text is never shown as ordinary assistant text, and Native Chat
  does not keep it.
