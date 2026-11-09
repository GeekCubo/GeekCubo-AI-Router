# GeekCubo

**One gateway. Every AI model.**
Open-source AI gateway and intelligent LLM router. OpenAI-compatible, BYOK, self-hosted. Streaming and `model="auto"` routing.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./design/brand/geekcubo-logo-dark.png">
  <img src="./design/brand/geekcubo-logo.png" alt="GeekCubo" width="320">
</picture>

[![tests](https://img.shields.io/badge/tests-passing-brightgreen)](#testing)
[![models](https://img.shields.io/badge/models-100%2B-blue)](#model-catalog)
[![license](https://img.shields.io/badge/license-MIT-blue)](#license)

## Languages

- [English](./README.md)
- [日本語](./README.ja.md)
- [中文](./README.zh.md)
- [한국어](./README.ko.md)
- [Deutsch](./README.de.md)
- [Français](./README.fr.md)
- [Español](./README.es.md)
- [Italiano](./README.it.md)
- [Русский](./README.ru.md)
- [Português](./README.pt.md)
- [Tiếng Việt](./README.vi.md)
- [हिन्दी](./README.hi.md)


GeekCubo is a self-hosted, OpenAI-compatible gateway: bring your own provider keys and `model="auto"` picks a capable model for every request according to the routing strategy you choose, with fallback and cost tracking.

> **Where it fits.** LiteLLM is a library you embed; OpenRouter is hosted-only; Ollama is local-only. GeekCubo is the server you run yourself, with the routing, fallback and accounting built in.

## Why GeekCubo exists

Automatic model routing should give developers control, not uncertainty.

The motivation for GeekCubo came from a practical problem: using your own AI provider keys doesn't always make it obvious which provider will handle a request, whether a fallback might use a separately billed service, or why a particular model was selected.

We wanted a self-hosted alternative where routing policies, eligible providers, model capabilities, pricing assumptions, and fallback behavior are visible and configurable.

GeekCubo is built around that principle: **your keys, your infrastructure, your routing decisions.**

There is no mandatory hosted routing wallet. You configure the providers and models available to the router, and you can inspect how automatic routing makes its decisions.

### Open-source origins

GeekCubo builds on [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), an open-source project released under the MIT License. We're grateful to its original developers for providing the foundation on which GeekCubo has evolved.

GeekCubo is independently developed and maintained, with its own features, architecture, and product direction. It is not affiliated with or endorsed by the original OrcaRouter developers.

See [License](#license) for attribution and licensing details.

## 60-second quickstart

GeekCubo is self-hosted and bring-your-own-key. There is no GeekCubo-hosted account and no required subdomain.

**Prerequisites:** Linux, macOS or WSL with Docker Engine 24+ and the Compose v2 plugin (`docker compose version`), plus about 1 GB RAM and 2 GB disk.

### Recommended: the installer

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

The installer checks Docker and Compose, creates `.env` from `.env.example` only when it is missing, validates the Compose file, runs `docker compose up -d --build`, waits for the real `/health` endpoint, and prints the dashboard URL. On a fresh install it also prints the one-time administrator setup token. Rerunning it is safe: it never deletes the data volume or regenerates credentials.

Optional provider keys can be set in `.env` before running it, or added later in the dashboard.

### Manual install

Both methods use the same `docker-compose.yml` and the same application code:

```bash
cp .env.example .env
# optional: OPENAI_API_KEY=sk-...  (or add providers in the dashboard instead)
docker compose up -d --build

# Only while no administrator exists:
docker compose exec api python -m app.admin_cli setup-token
```

Open the dashboard, choose **Create Administrator Account**, and paste that token (details [below](#administrator-account--api-keys)). Then generate an `sk-geek-*` key under **Settings → API Keys**.

Base URL: `http://127.0.0.1:8787/v1`. Use an `sk-geek-*` key from the dashboard (a fresh database also prints a first key to the log, which keeps working for inference).

The bundled Compose file publishes the dashboard on `127.0.0.1:8787` only. That is deliberate: the administrator login must not be exposed directly to the internet. For remote access use an SSH tunnel (`ssh -L 8787:127.0.0.1:8787 <user>@<server>`) or put a TLS reverse proxy in front of it. On a VPS, set `PUBLIC_BASE_URL` in `.env` to your own address — a root domain such as `https://example.com` or a subdomain such as `https://api.example.com`, whichever you use — so the installer displays it; see [Deployment](DEPLOYMENT.md). GeekCubo runs entirely on your infrastructure and never depends on a GeekCubo-operated host.

On first start GeekCubo generates `CREDENTIAL_ENCRYPTION_KEY` and `API_KEY_PEPPER` automatically and stores them next to the database (`.geekcubo-secrets`, mode `0600`). You normally never set or see them — see [Security and encryption](#security-and-encryption).

### Then call it from any OpenAI SDK

Examples below use the local Docker base URL, `http://127.0.0.1:8787/v1`.

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # or "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)
```
</details>

<details>
<summary><b>Node.js</b></summary>

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8787/v1",
  apiKey: "sk-geek-abc123...",
});

const r = await client.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(r.choices[0].message.content);
```
</details>

<details>
<summary><b>curl</b></summary>

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-geek-abc123..." \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```
</details>

Open the dashboard for providers, routing, analytics and settings. It is protected by a local administrator account; your `sk-geek-*` keys never sign you in.

## Administrator account & API keys

The dashboard signs in with a **username and password**. `sk-geek-*` keys are machine credentials for SDKs and CLIs: they cannot open the dashboard or change settings, and a dashboard session cannot be used for `/v1/chat/completions`. Revoking every API key never locks you out of the dashboard.

Examples use the bundled Docker base URL, `http://127.0.0.1:8787`. Substitute the port if you changed the Compose mapping.

### First-time setup

When no administrator exists, the server prints a one-time setup token on start:

```
── Administrator setup required ──
One-time setup token (valid 24h): <token>
```

`./install.sh` retrieves and prints this token for you on a fresh install. For a manual install, use the CLI:

```bash
docker compose exec api python -m app.admin_cli setup-token
```

1. Open the dashboard and choose **Create Administrator Account**.
2. Enter a username, a password (8+ characters; a multi-word passphrase is ideal), the confirmation, and the setup token.

There are no default credentials and no public registration; a remote visitor cannot create the account without the token from the server log. The token is single-use and becomes invalid once the administrator exists. After that, `setup-token` refuses to issue another: it never discloses a token after setup and never regenerates one just because the installer ran again. Treat the token like a password and do not share screenshots or terminal transcripts that contain it. Lost it before setup finished? Generate a new one (the old one stops working), or create the account from the shell instead:

```bash
docker compose exec api python -m app.admin_cli setup-token
docker compose exec api python -m app.admin_cli setup --username <name>   # prompts for the password
```

Normal GeekCubo restarts and updates preserve your database, provider credentials, custom providers and `sk-geek-*` keys. Keep the data volume and encryption secrets together; see [Deployment](DEPLOYMENT.md) for backup and update procedures.

### Sign in, change password, sessions

- Sign in at `/` with your username and password. Sessions are stored server-side, use an HttpOnly cookie, and end after 12 hours or 60 minutes idle.
- **Settings → Security** shows the account, changes the password, and can log out all other sessions. Changing the password signs out every other device; this one stays signed in. API keys are unaffected.

### Forgot the password

Recovery is local-only — no email reset and no HTTP endpoint. Run it where the server runs:

```bash
docker compose exec api python -m app.admin_cli reset-password
```

The new password is read from a hidden prompt (or one line on stdin with `--password-stdin`); there is no `--password` flag. All dashboard sessions are signed out. Provider keys, API keys, models and usage history are not touched.

### Generate an `sk-geek-*` key

**Settings → API Keys** → name the key (optionally an expiry) → **Generate New API Key** → copy it. The secret is shown once and only a hash is stored. **Rotate** creates a replacement with the same restrictions and leaves the old key working until you revoke it; **Revoke** takes effect immediately.

### Use the key with OpenCode

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8787/v1"
export OPENAI_API_KEY="sk-geek-..."
```

For a custom provider in `opencode.json`, OpenCode has used two schemas. The example below is the `provider` / `npm` / `options` form; **Settings → Connect a tool → OpenCode** generates either it or the newer `providers` / `package` / `settings` form with your real base URL. Check OpenCode's documentation for the version you run:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "geek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "GeekCubo",
      "options": { "baseURL": "http://127.0.0.1:8787/v1", "apiKey": "{env:GEEKCUBO_API_KEY}" },
      "models": { "auto": { "name": "GeekCubo auto" } }
    }
  }
}
```

### Rebuild safely and back up

```bash
docker compose build api
docker compose up -d api
docker compose logs -f api
```

Your data lives in the `geekcubo-data` named volume, so a rebuild keeps it. Rerunning `./install.sh` is also safe: it reuses the existing volume, `.env`, administrator account, provider credentials, encryption secrets and `sk-geek-*` keys. Never run `docker compose down -v` — it deletes the volume. To back up, stop the service and copy `/data`. It contains the database (with its SQLite `-wal`/`-shm` files), chat attachments and the automatically generated `.geekcubo-secrets` file holding `CREDENTIAL_ENCRYPTION_KEY`, without which stored provider keys can't be decrypted. If you set the encryption secrets in `.env` instead, back up `.env` as well.

```bash
docker compose stop api
docker compose cp api:/data ./geekcubo-data-backup
docker compose start api
```

Behind a reverse proxy that terminates HTTPS, set `TRUST_PROXY_HEADERS=true` so session cookies get the `Secure` flag. Leave it off for direct localhost use.

### Troubleshooting an install

`./install.sh` re-checks Docker, Compose, `.env`, health and administrator state on every run. To diagnose a failure yourself:

```bash
docker compose ps
docker compose logs --tail=100 api
```

If Docker needs elevated permissions, use `sudo docker compose ps` and `sudo docker compose logs --tail=100 api` instead. Re-running the installer after fixing the problem is safe; it reuses the existing `geekcubo-data` volume, `.env`, administrator account, provider credentials, encryption secrets and API keys. It never runs `docker compose down -v`.

### Security and encryption

On first start GeekCubo provisions two secrets automatically and writes them to a `.geekcubo-secrets` file next to the database (mode `0600`, never committed, never logged):

- `CREDENTIAL_ENCRYPTION_KEY` — the AES-256 key that seals provider and Artificial Analysis credentials at rest.
- `API_KEY_PEPPER` — the pepper for inference-key hashing.

Restarting never regenerates them (the file is reused). If you set either value in `.env`, it takes precedence and is never overwritten. If the database already holds encrypted records but the key is missing (for example, a partial restore), GeekCubo refuses to start rather than inventing a key that could never decrypt them — restore the key from backup.

#### Controlled key rotation

```bash
# 1. In .env, keep the old key and set the new one
#    CREDENTIAL_ENCRYPTION_PREVIOUS_KEY=<old>
#    CREDENTIAL_ENCRYPTION_KEY=<new>
# 2. Restart. Startup re-encrypts stored keys and logs
#    reencrypted_provider_keys / undecryptable_provider_keys.
# 3. Confirm the dashboard shows Enabled, then remove the previous key
#    and restart once more.
```

Rotation covers every field encrypted with the credential key (provider keys, custom-provider keys, the Artificial Analysis key, and custom metadata-source tokens). Re-save any row still marked "Can't decrypt" if a value was already unreadable before the rotation.

## How GeekCubo compares

| | GeekCubo | LiteLLM library | OpenRouter | Ollama |
|---|---|---|---|---|
| Self-hosted server | ✓ | as a library | ✗ | ✓ |
| OpenAI-compatible | ✓ | ✓ | ✓ | ✓ |
| Multi-provider (OpenAI/Anthropic/Google/…) | ✓ | ✓ | ✓ | ✗ |
| Built-in dashboard | ✓ | ✗ | ✓ | ✗ |
| `model="auto"` (policy-based selection) | ✓ | ✗ | ✗ | n/a |
| Streaming | ✓ | ✓ | ✓ | ✓ |
| BYOK | ✓ | ✓ | ✗ | n/a |
| Inference fallback | ✓ | ✗ | n/a | ✗ |
| No Postgres / no Redis required | ✓ | n/a | n/a | ✓ |

## `model="auto"` — the headline feature

Send `model="auto"` and GeekCubo filters the Auto-eligible models down to the ones that can serve the request, ranks them with the strategy you chose in **Routing**, and calls the best one, with a bounded fallback chain behind it. No manual routing rules and no cost-optimization code in your application.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → only models whose Vision capability is Supported are considered;
#   the active strategy ranks them
```

The resolved model is exposed back to callers via the `x-geek-resolved-model` response header so you can log/display what was actually used.

### Which models Auto may use

Every Auto request filters candidates in this order. A model that fails any step is never selected, not even as a fallback:

1. **Eligible** — a built-in provider with a working key, or a custom provider that is enabled and *Included in Auto*, and the model itself is enabled. Approved Local AI Connect machines take part when their policy allows it.
2. **Confirmed price** — a built-in list price or a custom price you set. An unknown price is never treated as free, and a reference estimate counts only if you enable estimate-based pricing (see [Model Intelligence](#model-intelligence)).
3. **Capable** — every capability the request needs (Tools, Vision, JSON mode, JSON Schema) is **Supported**. Unknown never satisfies a requirement.
4. **Fits** — the estimated prompt fits the model's known context window. A model whose window is unknown is not excluded on that basis.
5. **Allowed** — the API key's model allowlist and, for a [routing profile](#routing-profiles), the profile's restrictions.

### Strategies

| Strategy | How it ranks the remaining candidates | When evidence is missing |
|---|---|---|
| **Balanced** (default) | Equal weight on quality score and blended price. With a quality floor set, models below that percentile are removed first. Only models that have a quality score take part. | No score for any candidate: ranks by price and says so in the routing notes. Floor set without scores: the floor is not applied, and that is reported. |
| **Cheapest** | Lowest blended price (30% input, 70% output per token); ties break by model id. | All prices unknown: no candidate, the request fails with a diagnosis. |
| **Quality First** | Highest quality score; manual scores on the Quality page override Artificial Analysis. Unscored models rank after scored ones. | No scores at all: ranks by price as a stand-in (most expensive first) and says so. |
| **Adaptive** | Re-ranks by observed success rate, then latency, from this installation's own request log (last 7 days). | Fewer than 20 requests per model: behaves as Balanced and reports how many samples exist. |
| **Adaptive-Gated** | Classifies the request as *Mundane* or *Hard* (tool calls, images, long prompts, many messages, large `max_tokens`) and ranks only that pool, then applies Adaptive's evidence re-ranking when it exists. | Tier pool has no capable model: the *Fallback* pool, then *Mundane* for hard requests if allowed. Never widens to the whole catalog. |
| **Fastest** (legacy) | Benchmark throughput and first-token latency from Artificial Analysis. Models without both measurements are excluded, never assumed fast. | No benchmarks for any candidate: ranks by price and says so. |

Quality scores come from Artificial Analysis (with an API key) or your own manual scores; GeekCubo does not invent them.

GeekCubo reads Artificial Analysis's supported V2 API: the Free language-models list (`/api/v2/language/models/free`), which accepts any Artificial Analysis key, or the Pro list when `ARTIFICIAL_ANALYSIS_USE_PRO=true`. Free keys are limited to 100 requests per day; a sync uses about four. AA's API terms require attribution wherever its data is shown, so the Quality page credits Artificial Analysis. GeekCubo stores only the per-model numbers it routes on, locally, and does not redistribute AA data. Using it is subject to AA's Terms of Use.

### Routing policies

The Routing tab is the source of truth. The same settings are available through the administrator API (`GET`/`PUT /v1/routing`), which requires the dashboard session cookie and, for `PUT`, the `X-CSRF-Token` returned by `POST /api/auth/login`; `sk-geek-*` keys cannot change routing.

| Piece | What it does |
|---|---|
| **Strategies** | `balanced` (default), `cheapest`, `quality`, `adaptive`, `adaptive_gated`; `fastest` is kept for existing configurations. See [Strategies](#strategies). |
| **Tiers** | Under `adaptive_gated`, each request is classified as *mundane* or *hard* from observable signals (tool calls, images, long prompts, many messages, large `max_tokens`); thresholds are configurable. |
| **Pools** | `mundane`, `hard` and `fallback` are explicit model lists, used by `adaptive_gated` and escalation. Other strategies rank every Auto-eligible model. An entry that is no longer a registered model is ignored by routing and flagged on the Routing page. |
| **Fallback** | The ranked candidates are tried in order, up to `max_attempts` (default 5). Every fallback still satisfies the request's capability requirements. |
| **Escalation** | Decided *before* a request starts: after repeated upstream failures (5xx/408/429) in a conversation (`mode: auto`), or when the client sends `x-geek-escalate: 1` (`mode: manual`), the next request uses the `hard` (or `fallback`) pool, capped per conversation. Default `off`; `shadow: true` records the decision without switching. |
| **Stickiness** | Optional per-conversation pinning (default 30 min TTL) so multi-turn chats keep hitting the same model and its prompt cache. |
| **Dry run** | **Test a routing decision** on the Routing page (`GET /api/routing/explain?tools=true&messages=3`) shows the chosen model, the fallbacks, why, and what each filter stage removed. Nothing is sent upstream. |

Response headers on every routed request: `x-geek-resolved-model`, plus `x-geek-routing-strategy`, `x-geek-routing-effective` (what actually ran, e.g. `balanced` while Adaptive collects samples), `x-geek-routing-reason`, `x-geek-routing-candidates`, `x-geek-routing-tier` and `x-geek-routing-escalated`. When no candidate can serve the request, the 422 response carries `x-geek-routing-diagnosis` naming the filter that emptied the pool (`no_auto_eligible_providers`, `no_registered_models`, `capability_mismatch`, `context_mismatch`, `pool_mismatch`, `allowlist_mismatch`, …). Upstream failures after the request started are reported as `candidates_exhausted` or `non_retryable_failure`.

### Using Auto day to day

- **Use Auto:** send `model="auto"` (or a routing-profile id) from an SDK, or choose **Auto (router picks)** in the Chat model menu.
- **Pick a specific model instead:** send its full id (for example `gpt-4o-mini` or `<provider-slug>/<model>`), or choose it in the Chat model menu. A pinned model bypasses Auto ranking and fallback for that request or conversation.
- **Change the strategy:** click a strategy card on the Routing page. It is saved immediately and applies to the next request.
- **Change pools:** use the *Mundane / Hard / Fallback* buttons in the Routing page model table, or remove a chip from a pool.
- **Keep a model out of Auto:** disable the model, choose *Exclude from Auto* on its custom provider (the model stays usable by name), or remove its confirmed price.
- **See why a model was chosen:** use **Test a routing decision**, read the `x-geek-routing-*` headers, or check **Analytics → Recent requests**, which records the routed model and any fallback for every call.
- **No eligible model:** the request fails with a 422 that names the reason instead of guessing a model.

Auto *model routing* is unrelated to the **Auto** web-search mode in Chat settings, which is reserved and not implemented (see [Web search](#web-search-optional-off-by-default)).

### Advanced Auto in the dashboard

The Routing tab exposes the whole policy, not just the strategy name:

- **Fallback, escalation & continuity** — fallback attempts and retryable
  conditions, escalation mode (`off` / `auto` / `manual`), failures before
  escalating, per-conversation cap, destination pool, shadow mode and the
  stickiness window. Capability requirements are always preserved; a decision
  is made before the request starts, so a model never changes mid-stream.
- **Test a routing decision** — dry-run form (tools, vision, JSON, message
  count, prompt size, escalate). It shows the chosen model, strategy and tier
  and every filter stage that removed candidates. Nothing is sent upstream.
- **Pricing** — whether reference estimates may take part in Auto, Cheapest and
  cost ceilings (off by default).

Both are the same policy the `PUT /v1/routing` API edits, so dashboard changes
and API changes never diverge.

Conversations are identified by the optional `x-geek-conversation-id` header. Without it, escalation and stickiness degrade to per-request behavior — nothing breaks, you just lose continuity.

Model aliases: a bare model name such as `gpt-4o` resolves to `<provider-slug>/gpt-4o` when exactly one deployable model matches. If several match, you get a `409` listing the candidates instead of a silent guess.

### Routing profiles

A profile is a named Auto configuration that clients select by model id:

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $GEEKCUBO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "economy", "messages": [{"role":"user","content":"Explain this code."}]}'
```

`auto` is built in and cannot be edited or deleted. Create any number of
profiles, each with its own strategy, model/provider allowlist, per-1M price
ceiling, timeout, fallback limit, pools and escalation. Every restriction is
enforced on the planner's input, so **a fallback can never escape a profile**.

Profiles are managed on the **Routing profiles** page or through the
administrator API (`/v1/routing-profiles`, session cookie plus `X-CSRF-Token`
for changes). Example request body for a profile with a $5 per 1M token
ceiling:

```json
{
  "display_name": "Economy",
  "strategy": "cheapest",
  "profile": { "max_cost_per_million_micros": 5000000 }
}
```

Identifiers are stable wire values: lowercase, digits and hyphens, unique among
live profiles, never a registered model id, never reservable words like `auto`.
Renaming one requires `confirm_slug_change=true` and leaves a tombstone so a
deleted identifier is never silently reused by a different profile. Profiles can
be duplicated, exported to JSON (no secrets) and imported on another install.
`GET /v1/models` lists `auto` plus every enabled profile, so clients can
discover them.

## Inference fallback

Each Auto request tries its primary, then further candidates in order, up to
`fallback.max_attempts` in total (default 5; the dashboard's new-profile editor
pre-fills 3). Only failures another model can fix cause a failover:

| Failure | Fails over? |
|---|---|
| 429, timeouts, connection errors, 5xx | Yes (bounded backoff on 429) |
| 404 / model-missing on that deployment | Yes |
| Context window exceeded | Yes (another model may be larger) |
| 400, 401, 403, 422, content policy | **No** — reported as `non_retryable_failure` |

Streaming fails over only before the first byte: a second model's output is
never spliced into a stream that already started. Pinned models keep their
existing single-model behaviour. Every attempt is recorded (`attempt_count`,
`attempt_errors`); failed attempts return no usage, so they carry no billable
tokens.

## Model Intelligence

**Settings → Model data** configures where catalog metadata comes from. Three
sources ship built in: LiteLLM's bundled catalog (offline, no network),
[Models.dev](https://models.dev/api.json), and Portkey's per-provider pricing.
Add your own models.dev-compatible HTTPS endpoint if you have an internal
catalog.

Matching is exact-first and never guesses. GeekCubo tries, in order: an exact
`<provider-slug>/<model>` key, the operator-chosen catalog key, an exact
model id that already carries a vendor prefix, and a uniquely matching bare
model id. Prefixes such as `apixo/` are not blindly stripped to manufacture a
match, and no fuzzy or "looks similar" matching is used.

Each discovered or registered model shows one identity status:

| Status | Meaning |
|---|---|
| **Resolved** | Exactly one catalog entry matched, with context, reference prices and tool support known. |
| **Partial** | One entry matched, but at least one of those fields is missing; missing fields stay Unknown. |
| **Ambiguous** | Several catalog entries use the same id (often resellers). Nothing is inherited until you pick the right catalog key. The picker lists the model vendor's own entry first and accepts any exact key you type. |
| **Unmatched** | No catalog entry uses the id, typically a custom, renamed, *abliterated* or *uncensored* variant. Such models never inherit the metadata of a similarly named model. |

Large reseller catalogs make **Ambiguous** common for popular model ids; that
is expected and safe. The counts in **Manage models** and in the discovery list
are filter buttons.

When the provider's own `GET /models` reports `context_window` or
`max_output_tokens` (not part of the OpenAI schema, but some providers include
them), GeekCubo stores those values for that provider's models and shows them
as `via provider_models_endpoint`. They are refreshed whenever you run **Fetch
available models** and never imply capabilities or prices.

### Confirmed custom price vs reference estimate

There are two independent prices for a custom-provider model:

- **Custom price** — the confirmed rate you configured for that provider. It is
  the only rate used for spend accounting, budgets and analytics.
- **Reference price** — a vendor catalog rate shown for comparison. It is
  always labelled as an estimate and never becomes confirmed billing.

Strict pricing is the default. Auto, the **Cheapest** strategy and every
routing-profile cost ceiling compare only confirmed prices: built-in provider
list prices and the custom price you set. A custom model that has only a
reference estimate is reported as `estimate_only` and is not chosen by Auto
until you confirm its price. An unknown price never satisfies a ceiling.

If you prefer to route on estimates, enable it explicitly in the routing
policy:

```json
{ "pricing": { "allow_reference_estimates": true } }
```

With that flag on, reference estimates take part in Auto ranking and cost
ceilings, the routing dry-run reports `pricing_mode: estimate_allowed`, and
each decision that relied on an estimate carries an `estimate-based pricing`
note. Spend accounting still uses only confirmed prices.

`provider_catalog` trust is assigned only when the matched key begins with the
custom provider's own slug (for example `apixo/gpt-4o`). A match against
`openai/gpt-4o` remains a `reference_estimate`. An unknown price is never
treated as zero or free.

Reference precedence, highest first:

1. a reference price you set explicitly on the model,
2. a trusted provider catalog match,
3. another public catalog price (recorded as an estimate),
4. cached catalog data (flagged stale),
5. unknown.

Units are converted per source. Portkey publishes **cents per token**;
`0.00025` becomes **$2.50 / 1M**, and its zero-filled `default` template is
ignored.

### Capabilities and Auto

Metadata is resolved automatically when you **Fetch → Select → Add Selected
Models**. You don't need to open Details first. Tools, Vision, JSON mode,
JSON Schema, context window and reference prices are resolved **field by
field**, each independently. Each
field takes the first enabled source, in priority order, that has an explicit
value for the matched model. A missing price never blocks capabilities: a
model can show Tools and Vision as Supported and JSON Schema as Unsupported while its
price stays Unknown.

JSON mode (OpenAI's `json_object` response format) and JSON Schema (OpenAI's
`json_schema` structured outputs) are two separate capabilities, resolved
independently. Structured-output evidence in the catalog — for example
LiteLLM's `supports_response_schema` — maps only to JSON Schema and is never
treated as evidence of JSON mode.

Each capability has one of three states, **Supported**, **Unsupported** or
**Unknown**, and its source (for example `litellm`, `models-dev` or
`administrator_override`) appears next to it in the model table. A
capability is Supported or Unsupported only when a reliably matched catalog
entry gives an explicit value. Without that evidence it stays Unknown. An
ambiguous model (a bare id listed under several vendors) gets no capabilities,
context or prices until you pick its catalog key from the searchable
candidate list. GeekCubo never borrows another model's metadata.

The context window follows its own precedence: a value you set on the model,
then the limit the provider's `GET /models` reported, then the matched catalog
entry, otherwise Unknown. An unknown window never excludes a model from Auto;
a known window that is too small does.

Any explicit administrator choice is an override and survives catalog
refreshes. That includes choosing **Unknown**. Choose **Use catalog** to drop
the override and return to the resolved value. **Resolve metadata** in the
bulk toolbar re-resolves existing models, and refreshing a Model data source
re-resolves every registered model. Both update catalog-derived values and
leave overrides alone.

Auto routing, Chat and routing profiles all read the same stored
capabilities. A model is chosen for a request that needs a capability only
when that capability is Supported. Unknown is never promoted to Supported,
and GeekCubo does not mark capabilities Supported just so Auto has a
candidate. Neither an unknown price nor a reference estimate meets a price
ceiling unless estimate-based pricing is explicitly enabled.

### Provider-table administration

Inside a custom provider's **Manage models** panel, each row shows the
identity status and matched catalog key, the context window (and the
provider-reported maximum output, when known), reference and confirmed prices,
tri-state capabilities with their source, and an independent Enabled switch.
Disabled models stay registered but are not deployed, listed or Auto-selected.

Selections are independent from discovery and survive table re-renders. The
header checkbox selects the current filtered result set (with an indeterminate
state), and the bulk toolbar can enable, disable, remove or set a capability
across the selected rows. Removal is provider-scoped and asks for confirmation;
it is never performed while a capability save is in flight.

Every request stores immutable cost provenance (`custom`, `upstream_litellm`,
`catalog_estimate` or `unknown`) plus the pricing snapshot used at that moment.
Later catalog refreshes and model edits do not rewrite historical estimates.

Fetching is SSRF-hardened: https only (with an explicit local allowlist
exception), no embedded credentials, DNS resolved once and pinned to the
connection with the hostname preserved for TLS, every redirect re-validated,
32 MB and 20 s caps, and a source's own token is only ever sent to that
source's host. GeekCubo never sends provider keys or prompts to a catalog.

With every source offline, all configured models keep serving.

## Chat in the dashboard

The **Chat** tab talks to your deployed models from the browser. Requests go
through the same routing pipeline as SDK traffic, so `model="auto"`, profiles,
caching and cost tracking behave identically. The model menu offers **Auto
(router picks)**, your routing profiles and every deployable model; the choice
is saved per conversation.

Replies stream as they are generated. **Stop** (the Send button while a reply
is streaming) ends the request upstream; the partial answer is kept and marked
as interrupted, and the request log records it as a client disconnect.

Conversations live in your local database only. History saving and retention
are configurable in **Settings → Chat**. With history off, messages are not
stored (the request log still records usage), and uploaded attachments are
deleted once they are a day old.

### Context budget

Before every request the server loads recent history and trims it to what the
selected model can actually accept. The trim is reported back to the browser in
response headers:

| Header | Meaning |
|---|---|
| `x-geek-context-tokens` | Estimated tokens sent for this turn |
| `x-geek-context-budget` | Token budget used for the model |
| `x-geek-context-omitted` | Older messages dropped to fit |
| `x-geek-context-source` | `model` when the window is known for the selected model, `fallback` (16 384 tokens) otherwise, for example under Auto before a model is chosen |

The chat header shows the same numbers ("Context: 1 204 / 128 000 tokens") and
notes when older messages were omitted, so a truncated answer is never mistaken
for a model failure. Token counts are estimates (about four characters per
token, plus a small per-message overhead) and the budget keeps a safety margin.

### Web search (optional, off by default)

Chat can search the web before answering and cite the pages it used. Configure
it in **Settings → Chat → Web search**:

- **Mode** — `off` (default) or `manual`, which shows a per-message toggle in
  the composer. `auto` is reserved and not implemented; the option is disabled.
- **Backend** — `searxng` (your own or a private instance, URL required),
  `brave` or `tavily` (API key required, stored encrypted and never shown again).
- **Limits** — searches per conversation, results per search, pages fetched per
  search, and a timeout. Hard caps apply server-side.
- **Test connection** runs one real query and reports the result count and
  latency without saving anything.

A search that did not happen is never described as one that did: failures are
reported in the composer, and citations are rendered only for URLs the backend
actually returned. Search-provider keys are stored separately from inference
provider keys.

SearXNG can be run by the installer (Compose profile `search`):

```bash
docker compose --profile search up -d          # start it
docker compose --profile search down           # stop it
```

Then point the backend at `http://searxng:8080/`. Brave and Tavily need no
container — paste the API key in the dashboard.

### Attachments (images, documents, archives, media)

The composer accepts files three ways: the paperclip button, drag-and-drop
onto the conversation, and paste (a pasted image, including a screenshot with
no file name, becomes an attachment; pasted plain text stays native). Each file
appears as a chip with a preview where possible and a remove button; Send waits
until uploads finish. Files are identified by extension and verified by magic
bytes, stored under an opaque UUID name, served back only to the signed-in
administrator, and never executed.

| Kind | Formats | How the model sees it |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Converted to JPEG and sent as image parts to a vision-capable model |
| `document` | PDF, DOCX, RTF | Extracted text, delimited |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Sheet-by-sheet text, bounded |
| `text` / `code` | TXT, MD, JSON, YAML, source files | Raw text, delimited |
| `archive` | ZIP, TAR, GZIP | Entry listing plus bounded reads; never unpacked to disk |
| `video` / `audio` | MP4, WebM, MOV, MKV, MP3, WAV, M4A, OGG, FLAC, … | Video: metadata plus up to four evenly spaced frames (needs `ffmpeg`). Audio: metadata only |

Textual attachments always degrade to a delimited block in the user message,
so any model can read them. Images become real image parts only for the
current turn; in older history they collapse to an `[attached: name]` marker to
keep the context window honest. If you pin a model that cannot accept images,
the send is rejected with a `no_vision` diagnosis rather than silently dropping
the file.

Server-side limits (adjustable through env: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; see `.env.example`):

- Up to 8 attachments per message.
- 25 MB per file by default, clamped to a hard ceiling.
- Unbound uploads are purged after 24 hours.

An unsupported file type is rejected with an error naming the file. A
supported file that cannot be read (for example a damaged PDF) is still
attached, marked with a warning on its chip, and the model is told it could
not be read. Neither blocks the text you typed.
`GET /api/chat/attachments/limits` tells the browser what it may upload, so the
UI enforces the same rules before sending.

Media needs `ffmpeg`/`ffprobe` on `PATH` for video frames; without them a video
still uploads and the model is told it cannot be read. Audio is documented to
the model as metadata only — automatic speech transcription is deliberately not
enabled, and the model is never told it heard something it did not.

## Connect your AI tool

**Settings → Connect a tool** generates ready-to-paste configuration for
OpenCode, Claude Code, Cursor, Continue, Cline, Kilo Code, any generic
OpenAI-compatible client, cURL and the Python/TypeScript SDKs, using your real
base URL and routing ids. No secret is ever embedded: keys are referenced as
`GEEKCUBO_API_KEY`. The generated files are built from each tool's documented
format; they are not tested against every tool version, so check the tool's
own documentation if a field has moved.

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

Cursor is supported for **chat models only** through its OpenAI-compatible
override; Cursor's own Tab completion and background agents keep
using Cursor's models. Anthropic-hosted extras outside the Messages API (for
example server-side web search tools) are not available and fail as ordinary
unsupported-tool responses.

## Local AI Connect

Bring the models already running on your own hardware into the same catalog,
policies and `model="auto"` routing as your cloud providers. The connector is an
outbound-only agent: it dials your GeekCubo instance over WebSocket, advertises
the local models it can see, and answers chat requests. No inbound port, no
tunnel, no VPN and no cloud account in between.

**Local AI → Set up a machine** walks through eight steps: enable the
feature, create a one-time enrollment code, install and enroll the connector,
start it, approve the machine, enable the models you want, and include them in
Auto.

```bash
# On the machine that runs the models (Python 3.11+), from a checkout of this repo
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

The connector probes common local runtimes automatically:

| Adapter | Default base URL | Protocol |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Native `/api/tags`, `/api/show` and `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | OpenAI-compatible `/v1` |
| `vllm` | `http://127.0.0.1:8000` | OpenAI-compatible `/v1` |
| `llamacpp` | `http://127.0.0.1:8080` | OpenAI-compatible `/v1` |
| `custom` | none (set with `--url`) | Any OpenAI-compatible `/v1` server (`--api-key` for a bearer token) |

What each part of the path supports today:

| | Ollama | LM Studio / vLLM / llama.cpp / custom |
|---|---|---|
| Model discovery | ✓ | ✓ |
| Context window | reported by Ollama | when the server reports it |
| Streaming text | ✓ | ✓ |
| Image input | ✓ for models Ollama reports as vision-capable (base64 images) | passed through unchanged; depends on the server |
| Tool calls | ✗ — not returned through the connector | ✗ — not returned through the connector |
| Reconnect | automatic, exponential backoff capped at 30 s | same |

Capabilities are what the *whole path* can deliver, not only what the model
can do: a local model that supports tools on its own is still advertised
without Tools, because the connector does not carry tool calls back yet. Auto
therefore never sends a request that needs tools to a local model.

Use `--adapter` to restrict probing and `--url adapter=URL` to point an adapter
at a non-default port. `python -m geekcubo_connector ...` is equivalent to the
`geekcubo-connector` script. The dashboard offers ready-made systemd, launchd
and Windows service files so the connector restarts with the machine.

Enrollment codes are single-use, expire after 30 minutes by default, and grant
nothing until an administrator approves the machine. Once approved, local models
appear in the catalog as `local/<machine>/<model>` and can be pinned directly or
included in `model="auto"`.

Local routing is governed by the `local` block of the routing policy:

- `enabled` — include approved local models in Auto.
- `no_cloud_fallback` — when Auto picks a local model and that machine is
  offline, fail the request instead of silently retrying on a cloud provider.
- `machines` — restrict Auto to specific machine ids; empty means every
  approved, auto-eligible machine.

Local models are priced at a confirmed zero (they run on your own hardware), so
they always pass Auto's price gate and rank first under **Cheapest**. Keep a
machine or model out of Auto with its *Auto* toggle or the `local` policy below,
and address it directly by its routing id.

Configuration (all optional, see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Master switch; `false` closes the agent endpoint and hides local models. |
| `LOCAL_CONNECT_PUBLIC_URL` | empty | Public base URL written into the generated install command and service files. When empty, they show a `https://your-geekcubo-host` placeholder to replace by hand. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | How often a connected machine reports in (updates its last-seen time). A machine shows as online while its connection is open. |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Lifetime of an enrollment code. |

The agent socket is a WebSocket on `/api/local-connect/agent`, so any reverse
proxy in front of GeekCubo must forward the HTTP `Upgrade` header. The Nginx
vhost generated by `./install.sh` includes the required `map`, and Caddy handles
WebSockets automatically. The in-memory connection hub requires a **single
server process** (the default; `scripts/start.py` and the Docker image run one
worker). Running several workers or replicas is not supported, and a restart
drops live connectors until they reconnect. Machine credentials are bearer secrets: stored hashed server-side,
written `0600` on the model host, and revocable or rotatable from the dashboard
at any time.

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

## Native protocol endpoints (Anthropic + Gemini)

GeekCubo speaks three inbound protocols against one routing pipeline. Clients
that only talk Anthropic or Gemini wire formats connect directly — no OpenAI SDK
required. Claude Code setup is shown [above](#connect-your-ai-tool); the Gemini
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
[integrations/claude-code.md](./integrations/claude-code.md),
[integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Model catalog

The built-in catalog (several hundred chat models for the supported providers) is loaded at startup from the copy of [LiteLLM's community-maintained pricing database](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) bundled with the installed LiteLLM version — no model list to maintain manually. Each entry exposes:

- `id` (e.g. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mapped to your configured keys)
- Capability flags: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema` (Supported, Unsupported or Unknown)
- Per-token input/output list price (used by cost-aware strategies, the savings widget and spend accounting)

Built-in models become deployable when you add a key for their provider (`openai`, `anthropic`, `google`, `groq`, `together`, `fireworks`, `xai`, `deepseek`). Anything else is added as a [custom provider](#model-intelligence) or through [Local AI Connect](#local-ai-connect).

`GET /v1/models` returns `auto`, your enabled routing profiles and the full catalog (built-in, custom and local models, including built-in models whose provider has no key yet) in OpenAI format, or in Anthropic format when the request carries `anthropic-version`.

## Deploy somewhere else

GeekCubo is a single Docker container, so it runs anywhere Docker does. Without
Compose, build the image from a checkout and keep the data on a named volume:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Tagged releases are set up to publish a multi-architecture image to
`ghcr.io/geekcubo/geekcubo-ai-router` through `.github/workflows/release.yml`;
use that image name once a release has been published.

For a full VPS + reverse-proxy walkthrough, see [DEPLOYMENT.md](./DEPLOYMENT.md).

## What's in the box

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
- `POST /api/chat/attachments` — upload/extract/delete chat attachments; `GET /api/chat/attachments/limits` reports the server-enforced limits so the UI matches them
- `/api/local-connect/*` — **Local AI Connect**: enrollment codes, machine approval/revocation/rotation, model toggles, service-file generation, and the outbound agent WebSocket at `/api/local-connect/agent` (`local/<machine>/<model>` routing ids; no tool calls over the connector)
- Dashboard extras: strict provider pricing (estimate-backed decisions are opt-in), quality manual scores (single + bulk, with optional notes), and per-model metadata-resolve previews with source attribution
- SQLite by default; Postgres opt-in via `DATABASE_URL` (install the `postgres` extra); Redis optional
- Runs as **one server process**. Setting `REDIS_URL` moves the prompt cache to Redis and broadcasts config-cache invalidation, but it does not make other in-process state shared: Local AI Connect connections, Auto conversation state (stickiness, escalation) and Adaptive's evidence cache stay per process. Multi-worker or multi-replica deployment is not supported.

### Rotating `CREDENTIAL_ENCRYPTION_KEY`

See [Controlled key rotation](#controlled-key-rotation) under Security and encryption. The short version: set `CREDENTIAL_ENCRYPTION_PREVIOUS_KEY` to the old value, restart (startup re-encrypts), verify, then remove the previous key.

### Cross-provider prompt cache

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

### Savings widget

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` reports what your traffic would have cost on the baseline model versus what it actually cost, using the baseline's list price. Requests with an unknown price are not counted as savings. The dashboard shows it as a tile.

### Integrations

Example configs for [Claude Code](./integrations/claude-code.md), [Gemini SDK](./integrations/gemini-sdk.md), [Continue.dev](./integrations/continue.json), [Aider](./integrations/aider.md), [Cursor](./integrations/cursor.md), [LangChain](./integrations/langchain_geekcubo.py), [LlamaIndex](./integrations/llamaindex_geekcubo.py), [Vercel AI SDK](./integrations/vercel_ai.ts), and any tool that speaks the OpenAI Chat Completions protocol — plus native Anthropic and Gemini wire formats. See [`integrations/`](./integrations/). They use the Docker base URL `http://127.0.0.1:8787`; the JSON, Python and TypeScript files are syntax-checked, but they have not been run against every tool version.

## What's deliberately not

GeekCubo is a **single-workspace**, single-process server. By design, it has no:
- multi-tenancy, RBAC, SSO
- billing, wallets, points, partner program
- multi-user admin console, audit logs, trust & safety (one local administrator account is built in)
- multi-worker, multi-replica or Kubernetes deployment
- email / Slack / webhooks for alerts

## Testing

```bash
pip install -e ".[dev]"
PYTHONPATH=. pytest -q
```

The suite uses local mock upstreams and never calls a paid provider. Browser tests under `tests/ui` need the `ui` extra plus `playwright install chromium`; they otherwise skip. CI also runs `ruff check .`, `node --check design/app.js`, the localization tests (`python -m unittest design.test_i18n_unittest`), `bash -n install.sh`, a package build and a Docker smoke test. See `.github/workflows/ci.yml` for the exact commands.

## Architecture

```
app/
├── main.py               FastAPI factory, startup migrations, SPA mount
├── config.py             Settings (environment / .env)
├── auth_policy.py        Route classes: public, administrator, inference
├── middleware/auth.py    Session-cookie + CSRF and sk-geek-* enforcement
├── secret_provisioning.py  First-run CREDENTIAL_ENCRYPTION_KEY / API_KEY_PEPPER
├── auto_routing.py       Capability gate, price gate, strategy ranking
├── auto_planner.py       Policy: pools, tiers, fallback, escalation, stickiness
├── routing_policy.py     Policy schema and validation
├── routing_profiles.py   Named Auto profiles
├── router_cache.py       Deployments from provider keys, custom providers, local machines
├── custom_providers.py   Custom OpenAI-compatible providers + discovery
├── model_metadata.py     Catalog matching, tri-state capabilities, price provenance
├── model_intelligence.py Metadata-source parsers (LiteLLM, models.dev, Portkey)
├── quality_scores.py     Artificial Analysis scores + manual overrides
├── prompt_cache.py       Cross-provider exact-match cache (Redis or in-memory LRU)
├── web_search.py         Optional SearXNG / Brave / Tavily search
├── safe_fetch.py         SSRF-hardened outbound fetches
├── attachments/          Upload detection, extraction, storage
├── local_connect/        Local AI Connect hub, dispatcher, enrollment, catalog
├── protocols/            Anthropic and Gemini wire-format translation
└── routes/               HTTP routes (chat, dashboard chat, providers, routing, …)

packages/
├── litellm_adapter/      LiteLLM Router wrapper, built-in catalog, local provider
├── auth/                 Password/key hashing, AES-256-GCM, sessions
└── db/                   Models, engine, startup migrations, guards

geekcubo_connector/       Local AI Connect agent (`geekcubo-connector`)
design/                   Dashboard (HTML, CSS, JS; 12 languages)
integrations/             Tool configuration examples
```

## Roadmap

- [x] OpenAI-compatible chat completions
- [x] Streaming (SSE)
- [x] `model="auto"` policy-based routing with selectable strategies
- [x] Inference fallback and escalation
- [x] Encrypted BYOK at rest
- [x] Local analytics dashboard
- [x] CI (GitHub Actions)
- [x] Cross-provider prompt caching
- [x] Continue.dev / Aider / LangChain / Cursor / Vercel AI SDK integrations
- [x] Savings widget (cost of your traffic against a baseline model)
- [x] Local AI Connect (bring your own local models through an outbound agent)
- [ ] Tool calls through Local AI Connect
- [ ] Automatic (per-message) web search
- [ ] Embeddings + image-gen proxy

See [DEMO.md](./DEMO.md) for a scripted failover demo you can record yourself.

## ❤️ Support GeekCubo

GeekCubo is free, open-source, and independently developed. You can support its continued development by exploring services that complement your AI setup.

- [**AI API Providers**](https://geekcubo.com/providers/) — Discover compatible AI model providers.
- [**VPS & Cloud Hosting**](https://geekcubo.com/hosting/) — Explore hosting options for self-hosted deployments.
- [**VPN & Privacy**](https://geekcubo.com/vpn/) — Explore optional privacy and secure networking tools.

**Affiliate disclosure:** Some links may earn us a commission at no additional cost to you. Using them is optional and does not influence GeekCubo's model routing or provider compatibility.

## License

MIT. See [LICENSE](./LICENSE).

GeekCubo is derived from OrcaRouter Lite. The upstream MIT license and its
copyright notice ("Copyright (c) 2026 OrcaRouter contributors") are preserved
in [LICENSE](./LICENSE) and must be kept in copies and substantial portions of
the software.

Third-party assets keep their own licenses: the font outlines used in the logo
(Inter, SIL Open Font License 1.1) are covered by
[design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).
