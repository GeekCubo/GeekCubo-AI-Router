# Routing: `model="auto"`, strategies, policies and profiles

[← Back to the README](../README.md)

How GeekCubo chooses a model for every request, what each strategy does, the routing policy (pools, tiers, fallback, escalation, stickiness), routing profiles, and inference fallback.

## How Auto works

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

## Which models Auto may use

Every Auto request filters candidates in this order. A model that fails any step is never selected, not even as a fallback:

1. **Eligible** — a built-in provider with a working key, or a custom provider that is enabled and *Included in Auto*, and the model itself is enabled. Approved Local AI Connect machines take part when their policy allows it.
2. **Confirmed price** — a built-in list price or a custom price you set. An unknown price is never treated as free, and a reference estimate counts only if you enable estimate-based pricing (see [Model Intelligence](model-intelligence.md)).
3. **Capable** — every capability the request needs (Tools, Vision, JSON mode, JSON Schema) is **Supported**. Unknown never satisfies a requirement.
4. **Fits** — the estimated prompt fits the model's known context window. A model whose window is unknown is not excluded on that basis.
5. **Allowed** — the API key's model allowlist and, for a [routing profile](#routing-profiles), the profile's restrictions.

## Strategies

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

## Routing policies

The Routing tab is the source of truth. The same settings are available through the administrator API (`GET`/`PUT /v1/routing`), which requires the dashboard session cookie and, for `PUT`, the `X-CSRF-Token` returned by `POST /api/auth/login`; `sk-geek-*` keys cannot change routing.

| Piece | What it does |
|---|---|
| **Strategies** | `balanced` (default), `cheapest`, `quality`, `adaptive`, `adaptive_gated`; `fastest` is kept for existing configurations. See [Strategies](#strategies). |
| **Tiers** | Under `adaptive_gated`, each request is classified as *mundane* or *hard* from observable signals (tool calls, images, long prompts, many messages, large `max_tokens`); thresholds are configurable. |
| **Pools** | `mundane`, `hard` and `fallback` are explicit model lists, used by `adaptive_gated` and escalation. Other strategies rank every Auto-eligible model. An entry that is no longer a registered model is ignored by routing and flagged on the Routing page. |
| **Fallback** | The ranked candidates are tried in order, up to `max_attempts` (default 5). Every fallback still satisfies the request's capability requirements. |
| **Escalation** | Decided *before* a request starts: after repeated upstream failures (5xx/408/429) in a conversation (`mode: auto`), or when the client sends `x-geek-escalate: 1` (`mode: manual`), the next request uses the `hard` (or `fallback`) pool, capped per conversation. Default `off`; `shadow: true` records the decision without switching. |
| **Stickiness** | Optional per-conversation pinning (default 30 min TTL) so multi-turn chats keep hitting the same model and its prompt cache. |
| **Reasoning** | `reasoning.allow_downgrade` (default `false` = strict) and `reasoning.min_effort` (default `low`). With an explicit `reasoning_effort`, models confirmed unable to honour it are excluded; Unknown models stay eligible. When every model is confirmed incompatible, Auto either fails (`reasoning_mismatch`) or uses the highest supported level below the request. See [Reasoning effort](reasoning.md). |
| **Dry run** | **Test a routing decision** on the Routing page (`GET /api/routing/explain?tools=true&messages=3`) shows the chosen model, the fallbacks, why, and what each filter stage removed. Nothing is sent upstream. |

Response headers on every routed request: `x-geek-resolved-model`, plus `x-geek-routing-strategy`, `x-geek-routing-effective` (what actually ran, e.g. `balanced` while Adaptive collects samples), `x-geek-routing-reason`, `x-geek-routing-candidates`, `x-geek-routing-tier` and `x-geek-routing-escalated`. When no candidate can serve the request, the 422 response carries `x-geek-routing-diagnosis` naming the filter that emptied the pool (`no_auto_eligible_providers`, `no_registered_models`, `capability_mismatch`, `context_mismatch`, `pool_mismatch`, `allowlist_mismatch`, `reasoning_mismatch`, …). Requests with `reasoning_effort` also get `x-geek-reasoning-requested` / `-effective` (and `-downgraded`). Upstream failures after the request started are reported as `candidates_exhausted` or `non_retryable_failure`.

## Using Auto day to day

- **Use Auto:** send `model="auto"` (or a routing-profile id) from an SDK, or choose **Auto (router picks)** in the Chat model menu.
- **Pick a specific model instead:** send its full id (for example `gpt-4o-mini` or `<provider-slug>/<model>`), or choose it in the Chat model menu. A pinned model bypasses Auto ranking and fallback for that request or conversation.
- **Change the strategy:** click a strategy card on the Routing page. It is saved immediately and applies to the next request.
- **Change pools:** use the *Mundane / Hard / Fallback* buttons in the Routing page model table, or remove a chip from a pool.
- **Keep a model out of Auto:** disable the model, choose *Exclude from Auto* on its custom provider (the model stays usable by name), or remove its confirmed price.
- **See why a model was chosen:** use **Test a routing decision**, read the `x-geek-routing-*` headers, or check **Analytics → Recent requests**, which records the routed model and any fallback for every call.
- **No eligible model:** the request fails with a 422 that names the reason instead of guessing a model.

Auto *model routing* is unrelated to the **Auto** web-search mode in Chat settings, which is reserved and not implemented (see [Web search](chat.md#web-search-optional-off-by-default)).

## Advanced Auto in the dashboard

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

## Routing profiles

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
