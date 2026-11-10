# API endpoints and features

[← Back to the README](../README.md)

Every HTTP surface GeekCubo exposes, which credential each one accepts, the built-in model catalog, the prompt cache and the savings report.

## Endpoints

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + cross-provider prompt cache
- `POST /v1/messages` — **Anthropic Messages API ingress** (Claude Code / Anthropic SDKs connect directly; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **Gemini API ingress** (google-genai SDK connects directly; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, routing profiles and the model catalog (built-in from `litellm.model_cost`, plus custom and local models)
- `GET/PUT/DELETE /v1/providers/{provider}` — set / list / revoke encrypted provider keys (`decryptable` flags rows that no longer open after a `CREDENTIAL_ENCRYPTION_KEY` rotation)
- `/v1/custom-providers` — custom OpenAI-compatible providers, model discovery (`POST …/fetch-models`), registration and per-model metadata
- `GET/PUT /v1/routing` — change strategy (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; legacy `fastest`) and policy; `/v1/routing-profiles` — named Auto profiles
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — local analytics, no telemetry leaves the box
- `GET/POST/PUT/DELETE /v1/keys/...` — list / create / rename / rotate / revoke API keys
- `/api/auth/*` — administrator setup, login/logout, password change and session management (HttpOnly session cookie + CSRF token)
- Everything under `/v1/providers`, `/v1/custom-providers`, `/v1/routing`, `/v1/routing-profiles`, `/v1/model-intelligence`, `/v1/analytics`, `/v1/quality`, `/v1/keys` and `/api/` requires the administrator session (plus `X-CSRF-Token` on changes); `sk-geek-*` keys authenticate only `/v1/chat/completions`, `/v1/messages`, `/v1beta/models/*` and `GET /v1/models`
- Single-page dashboard at `/` (administrator sign-in) with a built-in **Chat** tab: talk to your deployed models in the browser; requests route, cache and cost-track exactly like SDK traffic, chat history lives only in your local database with a per-install retention setting, context trimming is reported per turn, optional web search (SearXNG, Brave or Tavily) adds citations, and attachments (images, PDF/DOCX, spreadsheets, text/code, archives, video/audio) are extracted safely and sent through the same pipeline
- `POST /api/chat/conversations/{id}/messages` accepts `"mode": "knowledge"` (Ask GeekCubo: answer from the bundled documentation; the reply's `knowledge.sources` lists the sections used) or `"normal"` (default); `GET /api/chat/knowledge/status` reports whether the documentation index is available and its version
- `POST /api/chat/attachments` — upload/extract/delete chat attachments; `GET /api/chat/attachments/limits` reports the server-enforced limits so the UI matches them
- `/api/local-connect/*` — **Local AI Connect**: enrollment codes, machine approval/revocation/rotation, model toggles, service-file generation, and the outbound agent WebSocket at `/api/local-connect/agent` (`local/<machine>/<model>` routing ids; no tool calls over the connector)
- Dashboard extras: strict provider pricing (estimate-backed decisions are opt-in), quality manual scores (single + bulk, with optional notes), and per-model metadata-resolve previews with source attribution
- SQLite by default; Postgres opt-in via `DATABASE_URL` (install the `postgres` extra); Redis optional
- Runs as **one server process**. Setting `REDIS_URL` moves the prompt cache to Redis and broadcasts config-cache invalidation, but it does not make other in-process state shared: Local AI Connect connections, Auto conversation state (stickiness, escalation) and Adaptive's evidence cache stay per process. Multi-worker or multi-replica deployment is not supported.

## Rotating `CREDENTIAL_ENCRYPTION_KEY`

See [Controlled key rotation](security.md#controlled-key-rotation). The short version: set `CREDENTIAL_ENCRYPTION_PREVIOUS_KEY` to the old value, restart (startup re-encrypts), verify, then remove the previous key.

## Cross-provider prompt cache

Deterministic, non-streaming requests (an explicit `temperature: 0`, or a pinned `seed`) are served from cache on repeat — works across **every** provider, not just Anthropic. Backend is Redis when `REDIS_URL` is set, in-process LRU otherwise. Cache hits return instantly with `x-geek-cache: HIT` and cost $0. A response served by a fallback model is not cached under the primary model's key.

```bash
$ curl ... -d '{"model":"auto","messages":[...], "temperature": 0}' -i
HTTP/1.1 200 OK
x-geek-cache: MISS
x-geek-resolved-model: gpt-4o-mini

$ curl ...  # same payload again
HTTP/1.1 200 OK
x-geek-cache: HIT          ← served from cache, no upstream call
```

## Savings widget

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` reports what your traffic would have cost on the baseline model versus what it actually cost, using the baseline's list price. Requests with an unknown price are not counted as savings. The dashboard shows it as a tile.

## Model catalog

The built-in catalog (several hundred chat models for the supported providers) is loaded at startup from the copy of [LiteLLM's community-maintained pricing database](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) bundled with the installed LiteLLM version — no model list to maintain manually. Each entry exposes:

- `id` (e.g. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mapped to your configured keys)
- Capability flags: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema` (Supported, Unsupported or Unknown)
- Per-token input/output list price (used by cost-aware strategies, the savings widget and spend accounting)

Built-in models become deployable when you add a key for their provider (`openai`, `anthropic`, `google`, `groq`, `together`, `fireworks`, `xai`, `deepseek`). Anything else is added as a [custom provider](model-intelligence.md) or through [Local AI Connect](local-ai-connect.md).

`GET /v1/models` returns `auto`, your enabled routing profiles and the full catalog (built-in, custom and local models, including built-in models whose provider has no key yet) in OpenAI format, or in Anthropic format when the request carries `anthropic-version`.
