"""POST /v1/chat/completions — the proxy endpoint, slimmed for lite.

Supports both blocking and streaming. The streaming path returns an SSE
response in OpenAI's `text/event-stream` format with a terminal
`data: [DONE]` sentinel, exactly matching what the OpenAI SDK expects.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterable, Callable

import anyio
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import prompt_cache, reasoning, router_cache
from app.auto_routing import (
    _VERSION_SUFFIX_RE,
    canonical_model_base,
    choose_auto_model,
    required_capabilities,
)
from app.config import get_settings
from app.deps import get_db, get_key_context
from app.protocols.sse import AdapterError
from app.quality_scores import resolve_model_metrics
from app.schemas import ChatCompletionRequest
from packages.auth.types import KeyContext
from packages.db.models.request_log import RequestLog
from packages.litellm_adapter.catalog import CATALOG_BY_ID
from packages.litellm_adapter.deployment_attribution import (
    hidden_params_of,
    match_served_deployment,
)
from packages.litellm_adapter.types import UpstreamProviderError

logger = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["Chat Completions"])

# Relays the engine's translated error type (rate_limit_error,
# model_not_found, ...) on engine-raised HTTPExceptions so the
# native-protocol routes can re-render the failure in their own
# status/error taxonomy.
ERROR_TYPE_HEADER = "x-geek-error-type"

# Delays (seconds) between successive attempts to commit a streaming
# RequestLog row; attempts = len + 1. That row is the only record of a
# stream's tokens and cost, so a commit that fails outright is retried on
# a fresh session before the row is given up on — bounded, because the
# retries hold the (already [DONE]) stream open. Tests shrink this.
_LOG_COMMIT_BACKOFF_S: tuple[float, ...] = (0.1, 0.4)


def _chunk_to_dict(chunk) -> dict:
    """Normalize a litellm chunk (Pydantic model or dict) into a plain dict.

    Returns an empty dict for None chunks — some LiteLLM stream wrappers
    yield None as a heartbeat/keepalive signal, and crashing on those
    would kill the stream for a non-event. Other unexpected types fall
    through to dict() which will raise TypeError if the object is not
    iterable, surfacing the bug rather than silently swallowing it.
    """
    if chunk is None:
        return {}
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "model_dump"):
        return chunk.model_dump(exclude_none=True)
    return dict(chunk)


def _served_same_group_as_requested(
    *, requested_group: str, served_model: str | None, client
) -> bool:
    """Return True iff the response's served model is in the same model_group
    (model_name in our deployment taxonomy) as the requested primary.

    LiteLLM frequently rewrites or expands model names in the response:
      - prefixed form: requested "gpt-4o-mini", response.model = "openai/gpt-4o-mini"
      - dated alias:   requested "gpt-4o", response.model = "gpt-4o-2024-08-06"
      - bare provider model: requested "claude-3-5-sonnet-latest",
                             response.model = "claude-3-5-sonnet-20241022"

    Strict string equality would treat these as different models and disable
    the prompt cache for almost all real traffic. Canonicalize via four
    progressively-stricter passes:

    1. Exact / prefix-stripped equality — handles "openai/gpt-4o-mini" vs "gpt-4o-mini".
    2. Version-suffix variant — served = requested + "-" + (date | build | vN).
       Catches OpenAI's "gpt-4o-2024-08-06" for "gpt-4o" without falsely
       matching "gpt-4o-mini" for "gpt-4o" (mini is not a date pattern).
    3. Deployment lookup — authoritative for the configured Router. If the
       served name maps to a different deployment's model_name, real cascade.
    4. Catalog lookup — if the bare name is a known distinct catalog entry,
       treat as cascade. Otherwise (unknown rendering), permit caching.
    """
    if not served_model:
        return True
    if served_model == requested_group:
        return True
    bare = served_model.split("/", 1)[-1] if "/" in served_model else served_model
    if bare == requested_group:
        return True

    # Pass 2: version-suffix variant (must run BEFORE deployment/catalog
    # lookups, because dated variants like "gpt-4o-2024-08-06" are also
    # in CATALOG_BY_ID as their own entries — those passes would falsely
    # flag them as a different group).
    if bare.startswith(requested_group + "-"):
        suffix = bare[len(requested_group) + 1:]
        if _VERSION_SUFFIX_RE.match(suffix):
            return True

    # Pass 3: deployment lookup. Authoritative — these are the model_groups
    # we actually configured for this Router.
    deployments = getattr(client, "_deployments", []) or []
    for d in deployments:
        if served_model in (d.litellm_model, d.model_name) or bare == d.model_name:
            return d.model_name == requested_group

    # Pass 4: catalog lookup. If the bare name is itself a recognized
    # catalog model distinct from the requested group, treat as cascade.
    # Imported lazily so the catalog isn't a hard dependency for this fn.
    from packages.litellm_adapter.catalog import CATALOG_BY_ID
    if bare in CATALOG_BY_ID and bare != requested_group:
        return False

    # Bare name doesn't resemble any known model — likely a provider-side
    # normalization we don't recognize. Permit caching to avoid disabling
    # the cache wholesale for unfamiliar response shapes.
    return True


def _geek_response_headers(
    *,
    resolved_model: str,
    requested_model: str,
    strategy: str,
    cache_status: str | None = None,
    auto_plan=None,
    reasoning_requested: str | None = None,
    reasoning_effective: str | None = None,
) -> dict[str, str]:
    """Shared x-geek-* response headers."""
    headers = {
        "x-geek-resolved-model": resolved_model,
        "x-geek-requested-model": requested_model,
        "x-geek-routing-strategy": strategy,
    }
    if cache_status is not None:
        headers["x-geek-cache"] = cache_status
    if auto_plan is not None:
        # Why this model: strategy, effective strategy, tier, candidate count.
        headers.update(auto_plan.headers())
    # An explicit effort is always reported back — including when it was
    # downgraded — so a client can tell what actually happened. Requests
    # without reasoning add nothing here.
    headers.update(
        reasoning.describe(
            requested=reasoning_requested,
            effective=reasoning_effective,
            model_id=resolved_model,
        )
    )
    return headers


def _local_runtime_of(client, model_name: str) -> tuple[str | None, tuple[str, ...] | None]:
    """(adapter, reported `think` values) behind a Local AI Connect model.

    Only local deployments have them; everything else returns (None, None).
    """
    for d in getattr(client, "_deployments", []) or []:
        if d.model_name == model_name and d.custom_llm_provider == "geekcubo_local":
            return getattr(d, "local_adapter", None), getattr(d, "local_thinking", None)
    return None, None


def _reasoning_provider_of(client, model_name: str, fallback: str | None) -> str | None:
    """The provider id whose reasoning interface this deployment speaks.

    Custom providers and local models each have their own translation, and
    getting this wrong is what made the old pipeline drop the parameter.
    """
    for d in getattr(client, "_deployments", []) or []:
        if d.model_name == model_name:
            if d.custom_llm_provider == "geekcubo_local":
                return "geekcubo_local"
            if d.custom_llm_provider == "openai" and d.operator_priced:
                return d.provider
            return d.provider or fallback
    return fallback


def _reasoning_params_by_model(
    *,
    client,
    models: list[str],
    effort: str,
    max_tokens: int | None,
    skip_untranslatable: bool = False,
    messages: list[dict] | None = None,
    endpoint_levels: dict[str, tuple[str, ...] | None] | None = None,
) -> dict[str, dict]:
    """Translate the effort into each model's own provider parameters.

    Pinned (`skip_untranslatable=False`): the single model must honour the
    level, else `ReasoningError` propagates and the caller answers with a
    4xx compatibility error rather than an outage.

    Auto (`skip_untranslatable=True`): a candidate that cannot express the
    level — an Unknown model ranked first that turns out unable to take it,
    or a thinking budget that does not fit `max_tokens` — is left out, and
    the next candidate becomes the primary. Only when no candidate can be
    translated does the first error propagate. The cascade never reaches a
    model that would drop or misinterpret the setting.
    """
    out: dict[str, dict] = {}
    first_error: reasoning.ReasoningError | None = None
    for model_name in models:
        adapter, thinking = _local_runtime_of(client, model_name)
        try:
            out[model_name] = reasoning.provider_params(
                model_id=model_name,
                provider=_reasoning_provider_of(client, model_name, None),
                effort=effort,
                max_tokens=max_tokens,
                local_adapter=adapter,
                local_thinking=thinking,
                messages=messages,
                endpoint_levels=(endpoint_levels or {}).get(model_name),
            )
        except reasoning.ReasoningError as exc:
            if not skip_untranslatable:
                raise
            first_error = first_error or exc
            logger.info("reasoning_candidate_excluded", model=model_name, effort=effort)
    if not out and first_error is not None:
        raise first_error
    return out


async def _custom_endpoint_levels(db) -> dict[str, tuple[str, ...] | None]:
    """Reasoning evidence each custom-provider deployment carries itself.

    Read from the cached custom-provider views (no extra query per request).
    Models with no evidence are absent, so they translate as Unknown.
    """
    from app.custom_providers import load_custom_providers, namespaced_model_id

    out: dict[str, tuple[str, ...] | None] = {}
    for prov in await load_custom_providers(db):
        for m in prov.models:
            if m.reasoning_levels is not None:
                out[namespaced_model_id(prov.slug, m.id)] = m.reasoning_levels
    return out


def _reasoning_error_response(exc) -> HTTPException:
    """A compatibility error, never a provider outage.

    400 with a stable `x-geek-error-type` so the native Anthropic/Gemini
    surfaces render it in their own taxonomy instead of collapsing it to a
    generic upstream failure.
    """
    logger.warning("reasoning_request_rejected", error_type=exc.error_type)
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message,
        headers={ERROR_TYPE_HEADER: exc.error_type},
    )


async def _build_log_row(
    *,
    body: ChatCompletionRequest,
    kc: KeyContext,
    response: dict,
    status_code: int,
    error_type: str | None,
    started_perf: float,
    strategy: str,
    requested_model: str,
    actual_resolved: str | None = None,
    auto_plan=None,
    attempts: list[dict] | None = None,
    request_source: str | None = None,
    trace_id: str | None = None,
) -> RequestLog:
    """Persist what the client asked for vs. what actually served the request.

    `requested_model` is the value the client sent (e.g. "auto" or a pinned
    model name) — captured before any auto-resolution so the log preserves
    user intent. `actual_resolved` is the model that ultimately served the
    response, which may differ from the auto-resolved primary if LiteLLM
    Router cascaded to a fallback after a 404 / cooldown.
    """
    latency_ms = int((time.perf_counter() - started_perf) * 1000)
    meta = response.get("_geekcubo_meta", {}) or {}
    usage = response.get("usage", {}) or {}
    resolved = actual_resolved or response.get("model") or requested_model
    input_t = usage.get("prompt_tokens", 0) or 0
    output_t = usage.get("completion_tokens", 0) or 0
    served_candidate = _served_candidate(auto_plan, resolved) if auto_plan else None
    # Failed upstream attempts: from the adapter on success (meta), or passed
    # explicitly on the error path.
    failed = attempts if attempts is not None else (meta.get("attempts") or [])
    succeeded = status_code < 400
    attempt_count = len(failed) + (1 if succeeded else 0)
    attempt_errors = (
        ",".join(str(a.get("error_type") or "error") for a in failed)[:255] or None
    )
    if auto_plan is not None:
        from app import auto_planner

        auto_planner.record_outcome(
            auto_plan.conversation_key,
            status_code=status_code,
            served_model=served_candidate,
            escalated=auto_plan.escalated,
        )
    cost_microcents, cost_source, cost_snapshot = _cost_with_provenance(
        meta=meta,
        usage=usage,
        resolved=resolved,
        requested_model=requested_model,
        input_tokens=input_t,
        output_tokens=output_t,
    )
    return RequestLog(
        workspace_id=str(kc.workspace_id),
        api_key_id=str(kc.key_id),
        request_source=request_source,
        trace_id=trace_id or str(uuid.uuid4()),
        model_requested=requested_model,
        model_resolved=resolved,
        provider=meta.get("provider", "unknown"),
        routing_strategy=strategy,
        fallback_level=0,
        input_tokens=input_t,
        output_tokens=output_t,
        cost_microcents=cost_microcents,
        cost_source=cost_source,
        pricing_snapshot_json=cost_snapshot,
        latency_ms=meta.get("latency_ms", latency_ms),
        status_code=status_code,
        error_type=error_type,
        is_streaming=body.stream,
        routed_model=(auto_plan.candidates[0] if auto_plan and auto_plan.candidates else None),
        routing_tier=(auto_plan.tier if auto_plan else None),
        routing_reason=(auto_plan.reason[:255] if auto_plan and auto_plan.reason else None),
        candidate_count=(auto_plan.candidate_count if auto_plan else None),
        escalated=(auto_plan.escalated if auto_plan else None),
        fallback_used=(
            # Recorded attempts are authoritative, with a name heuristic for
            # cases where the served candidate differs from the primary.
            (bool(failed) and succeeded)
            or bool(served_candidate and auto_plan.candidates
                    and served_candidate != auto_plan.candidates[0])
        ) if auto_plan else None,
        attempt_count=attempt_count or None,
        attempt_errors=attempt_errors,
    )


def _cost_with_provenance(
    *,
    meta: dict,
    usage: dict,
    resolved: str,
    requested_model: str,
    input_tokens: int,
    output_tokens: int,
) -> tuple[int, str, str]:
    """Cost plus an immutable snapshot of the rates used for this request.

    Provider/catalog prices change; the row records what was applied at the
    time. Reference vendor prices never appear as confirmed custom billing.
    """
    if "operator_price" in meta:
        price = meta.get("operator_price")
        if price is None:
            cost = 0
            source = "unknown"
            rates = None
        else:
            cost = _operator_cost_microcents(price, input_tokens, output_tokens)
            source = "custom"
            rates = {"input_per_token": price[0], "output_per_token": price[1]}
        snapshot = {
            "source": source,
            "served_deployment": meta.get("served_deployment"),
            "rates": rates,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_microcents": cost,
        }
        return cost, source, json.dumps(snapshot, separators=(",", ":"))

    upstream_cost = usage.get("cost_usd") or meta.get("cost_usd")
    if upstream_cost is not None:
        cost = _compute_cost_microcents(
            litellm_cost_usd=upstream_cost,
            model_id=resolved,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fallback_model=requested_model,
        )
        source = "upstream_litellm" if cost > 0 else "unknown"
    else:
        cost = _compute_cost_microcents(
            litellm_cost_usd=None,
            model_id=resolved,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fallback_model=requested_model,
        )
        source = "catalog_estimate" if cost > 0 else "unknown"
    snapshot = {
        "source": source,
        "model": resolved,
        "upstream_cost_usd": upstream_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_microcents": cost,
    }
    return cost, source, json.dumps(snapshot, separators=(",", ":"))


def _served_candidate(auto_plan, served: str | None) -> str | None:
    """Map the upstream's served model id back to the planned candidate.

    Custom upstreams report the bare wire id (`gpt-6-astra`) while candidates
    are namespaced (`apixo/gpt-6-astra`); dated aliases add a suffix. Best
    effort, used only for decision records and stickiness.
    """
    if not served or not auto_plan or not auto_plan.candidates:
        return None
    for cand in auto_plan.candidates:
        if served == cand or cand.endswith("/" + served):
            return cand
    for cand in auto_plan.candidates:
        bare = cand.split("/", 1)[-1]
        if served.startswith(bare) or bare.startswith(served):
            return cand
    return None


def _operator_cost_microcents(
    price: list[float] | None, input_tokens: int, output_tokens: int
) -> int:
    """Cost of a call served by an operator-priced (custom) deployment.

    `price` is `[input_per_token, output_per_token]` in USD, or None when the
    operator configured no price. None returns 0, and the analytics layer
    reports it as UNKNOWN cost. It is never filled in from a catalog or from
    the model name the upstream echoed.
    """
    if not price or input_tokens < 0 or output_tokens < 0:
        return 0
    usd = input_tokens * price[0] + output_tokens * price[1]
    return max(0, int(round(usd * 1_000_000)))


def _compute_cost_microcents(
    *,
    litellm_cost_usd: float | None,
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
    fallback_model: str | None = None,
) -> int:
    """Cost in microcents (1 USD = 1,000,000).

    Two-tier strategy:

      Tier 1 — `litellm_cost_usd` from the response's _geekcubo_meta. This is
      LiteLLM's own `_hidden_params.response_cost`, computed in the adapter
      at the moment LiteLLM Router knew which provider it actually called.
      Authoritative because it includes:
        - Anthropic prompt caching (cache_creation = 1.25x base,
          cache_read = 0.1x base)
        - OpenAI o1/o3 reasoning tokens (priced separately from output)
        - Audio input/output token pricing
        - Provider-specific aliasing — no name-matching guesswork needed
      We do NOT call `litellm.completion_cost(response)` here: that helper
      tries to re-derive the provider from the response dict and fails on
      Anthropic/Gemini bare names ("Provider NOT provided" or
      "model isn't mapped"), so reverse-lookup is unreliable.

      Tier 2 — `tokens × catalog price` fallback. Used when LiteLLM didn't
      attach a cost (cache hit served from our prompt cache, exception
      paths where `_geekcubo_meta` is absent, custom upstreams). Walks four
      catalog id shapes: as-is, prefix-stripped, version-suffix-stripped,
      then the original requested model id.

    Returns 0 only when both tiers miss. Negative tokens / negative cost
    are clamped to 0 (defensive against malformed upstream usage data).
    """
    if input_tokens < 0 or output_tokens < 0:
        return 0

    # Tier 1: LiteLLM's authoritative number, plumbed through _geekcubo_meta.
    if litellm_cost_usd is not None and litellm_cost_usd > 0:
        return max(0, int(litellm_cost_usd * 1_000_000))

    # Tier 2: catalog × tokens fallback.
    m = _lookup_priced_model(model_id) or _lookup_priced_model(fallback_model)
    if m is None:
        return 0
    cost_usd = (
        input_tokens * m.input_cost_per_token
        + output_tokens * m.output_cost_per_token
    )
    return max(0, int(cost_usd * 1_000_000))


def _lookup_priced_model(model_id: str | None):
    """Try four id-shape variants, return the first catalog hit or None.

    Order:
      1. as-is
      2. provider-prefix stripped ("openai/gpt-4o" -> "gpt-4o")
      3. version-suffix stripped (handles "claude-3-5-sonnet-20241022" ->
         "claude-3-5-sonnet" when the response was a dated alias and only
         the base form is in our catalog)
    """
    if not model_id:
        return None
    m = CATALOG_BY_ID.get(model_id)
    if m is not None:
        return m
    bare = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    if bare != model_id:
        m = CATALOG_BY_ID.get(bare)
        if m is not None:
            return m
    base = canonical_model_base(bare)
    if base != bare:
        return CATALOG_BY_ID.get(base)
    return None


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    kc: KeyContext = Depends(get_key_context),
    db: AsyncSession = Depends(get_db),
):
    return await execute_chat(body, kc, db, routing_hints=routing_hints_from(request))


def routing_hints_from(request: Request) -> dict[str, str]:
    """Optional client routing signals (all advisory, all bounded by policy).

    * `x-geek-conversation-id` — stable conversation identity for stickiness
      and escalation strikes (otherwise derived from the opening messages).
    * `x-geek-escalate: true` — explicit escalation request; honoured only
      when the admin set escalation mode to `manual` or `auto`.
    """
    hints: dict[str, str] = {}
    try:
        headers = request.headers
        cid = headers.get("x-geek-conversation-id", "")
        esc = headers.get("x-geek-escalate", "")
    except Exception:
        return hints
    # Hints are advisory: anything that is not a plain string is ignored
    # rather than allowed to break the inference path.
    if isinstance(cid, str) and cid.strip():
        hints["conversation_id"] = cid.strip()[:200]
    if isinstance(esc, str) and esc.strip().lower() in ("1", "true", "yes"):
        hints["escalate"] = "1"
    return hints


async def _lookup_profile(db: AsyncSession, kc: KeyContext, slug: str):
    """Return the live routing profile named `slug`, or None.

    Defensive: any failure (a mocked session in tests, a database without
    the table yet) means "not a profile", never a broken inference path.
    """
    # Only a real session can hold profiles; mocked sessions in unit tests
    # (and any non-SQLAlchemy stand-in) are simply "not a profile".
    if not isinstance(db, AsyncSession):
        return None
    try:
        from app.routing_profiles import find_profile

        row = await find_profile(db, str(kc.workspace_id), slug)
    except Exception:
        return None
    from packages.db.models.routing_profile import RoutingProfile

    return row if isinstance(row, RoutingProfile) else None


async def execute_chat(
    body: ChatCompletionRequest,
    kc: KeyContext,
    db: AsyncSession,
    *,
    log_status: Callable[[int, str | None], int] | None = None,
    routing_hints: dict[str, str] | None = None,
    request_source: str | None = None,
    trace_id: str | None = None,
) -> JSONResponse | StreamingResponse:
    """Protocol-agnostic chat engine — the full pipeline behind
    POST /v1/chat/completions (allowlist → auto-resolution → prompt cache →
    LiteLLM Router → RequestLog writeback), reusable by native-protocol
    adapters (Anthropic /v1/messages, Gemini /v1beta) with a translated body.

    Returns OpenAI-wire-format results: JSONResponse for blocking requests,
    StreamingResponse emitting `data: {json}\\n\\n` frames with a terminal
    `data: [DONE]` for streaming. Raises HTTPException on pre-stream errors.

    `log_status(engine_status, error_type)` lets a native-protocol caller
    record in the RequestLog the status IT will deliver for an upstream
    failure (e.g. 404 for model_not_found where this engine says 422), on
    both the blocking and the streaming path, so the persisted outcome
    matches what went over the wire.
    """
    # Capture client intent before any mutation so the request log and the
    # `x-geek-requested-model` header always reflect what the user asked for,
    # not the post-resolution primary.
    requested_model = body.model
    # `None` means "provider default" and is never coerced to a level: a
    # request that omits reasoning must behave exactly as it did before this
    # pipeline understood the field at all.
    reasoning_requested = body.reasoning_effort
    reasoning_effective = reasoning_requested
    trace_id = trace_id or str(uuid.uuid4())
    was_auto = body.model == "auto"
    # Routing hints come from request headers (conversation id, manual
    # escalation). Native adapters pass them through the same way.
    routing_hints = routing_hints or {}
    auto_plan = None

    # A custom routing profile is addressed by its slug (`model="economy"`)
    # and routes exactly like `auto`, but with its own strategy, policy and
    # model/provider/cost restrictions. Profile slugs never contain "/", so
    # canonical `provider/model` requests skip this lookup entirely.
    profile = None
    if not was_auto and isinstance(body.model, str) and "/" not in body.model:
        profile = await _lookup_profile(db, kc, body.model)
        if profile is not None:
            if not profile.is_enabled:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Routing profile '{profile.slug}' is disabled. Enable it "
                        "under Routing Profiles or use model='auto'."
                    ),
                    headers={
                        ERROR_TYPE_HEADER: "model_not_found",
                        "x-geek-routing-diagnosis": "profile_disabled",
                    },
                )
            was_auto = True

    # Allowlist enforcement is split: pinned requests check up front, auto
    # requests defer to after resolution (since "auto" itself is never in
    # an allowlist literal). Without this exemption, every key with an
    # allowlist would be locked out of `model="auto"`.
    #
    # `is not None` (not truthiness): an explicit empty list means "deny
    # everything" — the operator's intent is to lock the key down. Falsy
    # check would let an empty allowlist mean "no restriction", which
    # silently inverts the operator's security posture.
    if not was_auto and kc.model_allowlist is not None and body.model not in kc.model_allowlist:
        raise HTTPException(
            status_code=403,
            detail=f"Model '{body.model}' is not allowed for this API key",
        )

    client = await router_cache.get_router(db)

    # Optional short aliases ("gpt-6-astra" -> "apixo/gpt-6-astra") resolve
    # only when unambiguous, and only for pinned requests: "auto" is not a
    # model id and never aliases. This runs after the allowlist check above
    # on purpose: an API key restricted to canonical ids must not gain access
    # to other models by using a bare name.
    if not was_auto:
        from app.model_aliases import (
            AliasError,
            alias_candidates,
            needs_resolution,
            resolve_alias,
        )

        alias_deployable = {
            d.model_name for d in getattr(client, "_deployments", []) or []
        }
        if needs_resolution(body.model, alias_deployable):
            # Only consult the catalog when a bare id actually matches a
            # deployed model — every canonical request skips this entirely.
            from app.custom_providers import merged_catalog_by_id

            alias_known = set(
                (await merged_catalog_by_id(db, eligible_only=False)).keys()
            )
            matches = alias_candidates(body.model, alias_deployable)
            if len(matches) > 1 and body.model not in alias_known:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Model '{body.model}' is ambiguous: it matches "
                        + ", ".join(matches)
                        + ". Use the full namespaced id."
                    ),
                )
            try:
                canonical = resolve_alias(
                    body.model, deployable=alias_deployable, known_ids=alias_known
                )
            except AliasError as alias_err:
                raise HTTPException(
                    status_code=alias_err.status_code, detail=alias_err.message
                ) from alias_err
            if canonical != body.model:
                body.model = canonical

    raw_strategy = getattr(client, "strategy", None)
    strategy = raw_strategy if isinstance(raw_strategy, str) and raw_strategy else "balanced"
    raw_preferred = getattr(client, "preferred_models", None)
    preferred_models = raw_preferred if isinstance(raw_preferred, list) else []
    profile_ext_cfg: dict | None = None
    if profile is not None:
        from app.routing_profiles import profile_ext

        strategy = profile.strategy or "balanced"
        profile_ext_cfg = profile_ext(profile.policy)
        pm = profile_ext_cfg.get("preferred_model")
        preferred_models = [pm] if pm else []

    # Resolve `model="auto"` BEFORE building the request kwargs so the router
    # sees a real model. `candidates` is the top-N list from auto-routing;
    # candidates[0] becomes the primary and candidates[1:] are passed to
    # LiteLLM Router as fallbacks for automatic cascade on 404 / cooldown.
    resolved_model = body.model
    candidates: list[str] = []
    if was_auto:
        body_dict = body.model_dump(exclude_none=True)
        needs = required_capabilities(body_dict)
        deployable = {
            d.model_name for d in getattr(client, "_deployments", []) or []
        }
        if not deployable:
            # A registered-but-disabled provider produces zero deployments,
            # which lands here rather than at the capability check. Say why
            # instead of the bare "configure a key" line, which sends the
            # operator looking for a missing key that is already there.
            from app.custom_providers import (
                explain_auto_exclusions,
                load_custom_providers,
            )

            custom_views = await load_custom_providers(db)
            exclusions = explain_auto_exclusions(
                custom_views, needs=needs, deployable=deployable
            )
            detail = (
                "model='auto' requires at least one provider with a "
                "configured key or an approved Local AI Connect machine "
                "advertising an enabled model. No deployable provider found."
            )
            if exclusions:
                detail += (
                    " Registered custom models were excluded: "
                    + " | ".join(exclusions)
                )
            raise HTTPException(
                status_code=422,
                detail=detail,
                # Same operator-side, permanent condition the pinned-model
                # path reports as no_providers_configured. Without the
                # type the native surfaces would collapse this 422 to a
                # client-blaming 400 while the pinned path renders 403.
                headers={ERROR_TYPE_HEADER: "no_providers_configured"},
            )
        # `quality`, `balanced`, `fastest` all want AA-derived metrics.
        # `resolve_model_metrics` does the AA fetch + merges manual
        # overrides for the quality axis (TPS / TTFT have no override
        # concept) and is cached at the resolver layer for 60s, so the
        # default `balanced` strategy doesn't pay a DB hit per request.
        # Skipped for `cheapest` / None where the metrics aren't used.
        quality_scores: dict[str, float] | None = None
        tps_scores: dict[str, float] | None = None
        ttft_scores: dict[str, float] | None = None
        if strategy in ("quality", "balanced", "fastest", "adaptive", "adaptive_gated"):
            metrics = await resolve_model_metrics(
                db=db, workspace_id=str(kc.workspace_id),
            )
            quality_scores = metrics.quality_scores
            tps_scores = metrics.tps_scores
            ttft_scores = metrics.ttft_scores

        # The candidate set is the merged catalog (built-in + namespaced
        # custom providers marked eligible for auto-routing). The planner
        # applies the admin's routing policy around the existing ranker
        # (choose_auto_model); with the default policy it returns exactly
        # what choose_auto_model alone would. The key's allowlist is passed
        # in so it filters BEFORE the top-N cut.
        from app import auto_planner
        from app.custom_providers import (
            explain_auto_exclusions,
            load_custom_providers,
            merged_catalog,
        )
        from app.local_connect.catalog import (
            LOCAL_SLUG,
            machine_id_of_model_id,
        )
        from app.routing_policy import allows_reference_estimates, default_policy

        auto_catalog = await merged_catalog(db, eligible_only=True)
        raw_policy = getattr(client, "routing_policy", None)
        policy = raw_policy if isinstance(raw_policy, dict) else default_policy()

        # Local AI Connect scope: the policy can switch local models out of
        # Auto entirely, or narrow them to a specific set of machines. Applied
        # to the planner's input so no candidate (primary or fallback) can
        # escape it. Cloud models are never filtered by this block.
        local_policy = policy.get("local") or {}
        if not local_policy.get("enabled", True):
            auto_catalog = [m for m in auto_catalog if m.provider != LOCAL_SLUG]
        elif local_policy.get("machines"):
            allowed_machines = set(local_policy["machines"])
            auto_catalog = [
                m for m in auto_catalog
                if m.provider != LOCAL_SLUG
                or machine_id_of_model_id(m.id) in allowed_machines
            ]
        profile_filter_notes: list[str] = []
        if profile is not None:
            from app.routing_policy import PolicyError, normalize_policy
            from app.routing_profiles import apply_profile_filter

            try:
                policy = normalize_policy(profile.policy)
            except PolicyError:
                policy = default_policy()
            # Filtering the planner's INPUT means primary and every fallback
            # already satisfy the profile: a fallback cannot escape it.
            # Scoped to deployable models first: the merged catalog also holds
            # every built-in model with no key, which would make the
            # emptiness check below pass vacuously and inflate the counts.
            auto_catalog, profile_filter_notes = apply_profile_filter(
                [m for m in auto_catalog if m.id in deployable],
                profile_ext_cfg or {},
                allow_estimates=allows_reference_estimates(policy),
            )
            if not auto_catalog:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Routing profile '{profile.slug}' has no eligible model: "
                        + ("; ".join(profile_filter_notes) or "no Auto-eligible models")
                        + ". Widen its provider/model restrictions or cost ceiling."
                    ),
                    headers={
                        ERROR_TYPE_HEADER: "no_capable_provider",
                        "x-geek-routing-diagnosis": "profile_restriction",
                    },
                )
        evidence = (
            await auto_planner.load_evidence(db)
            if strategy in ("adaptive", "adaptive_gated") else {}
        )
        try:
            auto_plan = auto_planner.plan_auto(
                body=body_dict,
                needs=needs,
                deployable=deployable,
                catalog=auto_catalog,
                strategy=strategy,
                preferred_models=preferred_models,
                allowlist=kc.model_allowlist,
                quality_scores=quality_scores,
                tps_scores=tps_scores,
                ttft_scores=ttft_scores,
                policy=policy,
                evidence=evidence,
                hints=routing_hints,
                reasoning_effort=reasoning_requested,
            )
            candidates = auto_plan.candidates
            # The planner may have reduced the effort under the optional
            # downgrade policy; carry the effective level forward so the
            # provider gets the level the model can actually honour.
            reasoning_effective = auto_plan.reasoning_effective
            if profile is not None:
                auto_plan.profile = profile.slug
                auto_plan.notes.extend(profile_filter_notes)
        except auto_planner.AutoRoutingError as routing_err:
            # Empty result has distinct causes — distinguish them so the
            # operator can debug the right thing:
            #   - 403: capable models exist but none are in this key's allowlist
            #   - 422: categorised (providers, eligibility, capability,
            #          context, pool) with the setting to change.
            if routing_err.category == auto_planner.REASONING:
                # Deterministic capability problem, not a provider outage and
                # not an allowlist problem: say exactly what cannot be honoured.
                raise HTTPException(
                    status_code=422,
                    detail=routing_err.message,
                    headers={
                        ERROR_TYPE_HEADER: "unsupported_reasoning_effort",
                        "x-geek-routing-diagnosis": routing_err.category,
                    },
                ) from routing_err
            # Use `is not None` to honor explicit empty allowlist (deny-all).
            if kc.model_allowlist is not None:
                any_capable, _ = choose_auto_model(
                    needs=needs,
                    deployable=deployable,
                    candidates=auto_catalog,
                    strategy="cheapest",
                    allowlist=None,
                    top_n=1,
                    allow_estimates=allows_reference_estimates(policy),
                )
                if any_capable:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"No deployable model in this key's allowlist "
                            f"{kc.model_allowlist} satisfies the requested "
                            f"capabilities ({sorted(needs) or 'none'})."
                        ),
                        headers={"x-geek-routing-diagnosis": auto_planner.NOT_ALLOWED},
                    ) from routing_err

            custom_views = await load_custom_providers(db)
            if routing_err.message:
                # The planner already knows the precise cause (pool,
                # escalation target) — it is the actionable answer.
                category, detail = routing_err.category, routing_err.message
            else:
                full_catalog = await merged_catalog(db, eligible_only=False)
                category, detail = auto_planner.diagnose_empty(
                    needs=needs,
                    deployable=deployable,
                    full_catalog=full_catalog,
                    auto_catalog=auto_catalog,
                    custom_views=custom_views,
                    allowlist=kc.model_allowlist,
                    body=body_dict,
                    allow_estimates=allows_reference_estimates(policy),
                )
            # Explain *which* eligibility gate excluded the operator's own
            # custom models, per model.
            exclusions = explain_auto_exclusions(
                custom_views, needs=needs, deployable=deployable,
                allow_estimates=allows_reference_estimates(policy),
            )
            if exclusions:
                detail += (
                    " Registered custom models were excluded: "
                    + " | ".join(exclusions)
                )
            raise HTTPException(
                status_code=422,
                detail=detail,
                # Operator-side and permanent. The legacy type lets the native
                # surfaces render it as 403 permission_error /
                # PERMISSION_DENIED instead of collapsing the 422 to a
                # client-blaming 400; the finer category rides alongside.
                headers={
                    ERROR_TYPE_HEADER: auto_planner.error_type_for(category),
                    "x-geek-routing-diagnosis": category,
                },
            ) from routing_err

        resolved_model = candidates[0]
        body.model = candidates[0]  # mutate for downstream completion call

    started_perf = time.perf_counter()
    # Failed upstream attempts, filled by the error arm below. Defined before
    # the try so the log row can always reference it.
    failed_attempts: list[dict] = []
    completion_kwargs = body.model_dump(exclude_none=True)

    # Replace the neutral `reasoning_effort` field with the parameter the
    # selected model's provider actually accepts. This happens for the pinned
    # path AND the auto path (whose effort may have been downgraded), and
    # before the cache key is built, so the key describes the real request.
    # Each Auto candidate is translated separately (a Gemini fallback must not
    # inherit an Anthropic `thinking` block); a fallback that cannot honour
    # the effort is left out of the cascade rather than called without it.
    reasoning_params: dict[str, dict] | None = None
    if reasoning_effective is not None:
        completion_kwargs.pop("reasoning_effort", None)
        try:
            reasoning_params = _reasoning_params_by_model(
                client=client,
                models=candidates if was_auto and candidates else [body.model],
                effort=reasoning_effective,
                max_tokens=completion_kwargs.get("max_tokens"),
                skip_untranslatable=bool(was_auto and candidates),
                messages=completion_kwargs.get("messages"),
                endpoint_levels=await _custom_endpoint_levels(db),
            )
            if was_auto and candidates:
                # Promote the first candidate that can carry the effort, so
                # the cascade, the cache key and the response headers all
                # describe the model that is actually tried first.
                skipped = [m for m in candidates if m not in reasoning_params]
                candidates = [m for m in candidates if m in reasoning_params]
                if skipped and auto_plan is not None:
                    auto_plan.candidates = list(candidates)
                    auto_plan.notes.append(
                        f"reasoning_effort={reasoning_effective}: skipped "
                        + ", ".join(skipped)
                        + " (cannot express this level)"
                    )
                resolved_model = candidates[0]
                body.model = candidates[0]
                completion_kwargs["model"] = candidates[0]
        except reasoning.ReasoningError as exc:
            # A model that cannot honour the level is a client-side
            # compatibility problem. Report it as such, and log the attempt so
            # the request does not vanish from analytics.
            error = _reasoning_error_response(exc)
            log = await _build_log_row(
                body=body, kc=kc, response={},
                status_code=error.status_code, error_type=exc.error_type,
                started_perf=started_perf,
                strategy=strategy,
                requested_model=requested_model,
                actual_resolved=resolved_model,
                auto_plan=auto_plan,
                request_source=request_source,
                trace_id=trace_id,
            )
            db.add(log)
            try:
                await db.commit()
            except Exception as commit_err:
                logger.warning("request_log_commit_failed", error=str(commit_err))
            raise error from exc

    # Build the LiteLLM fallbacks argument from the auto candidate list.
    # Format: [{primary_model_name: [fallback_1, fallback_2, ...]}]
    # LiteLLM's async_function_with_fallbacks reads this from kwargs and
    # cascades automatically when the primary deployment fails or is in
    # cooldown — no explicit retry loop needed in this handler.
    fallbacks_arg: list | None = None
    if was_auto and len(candidates) > 1:
        fallback_chain = list(candidates[1:])
        # Local AI Connect: `no_cloud_fallback` keeps a locally-routed request
        # on the operator's hardware. Cloud candidates are dropped from the
        # cascade so a privacy-sensitive prompt never silently leaves the
        # machine; another local candidate still gets the request.
        raw_policy = getattr(client, "routing_policy", None)
        local_policy = (
            raw_policy.get("local") if isinstance(raw_policy, dict) else None
        ) or {}
        if local_policy.get("no_cloud_fallback") and str(candidates[0]).startswith("local/"):
            fallback_chain = [m for m in fallback_chain if str(m).startswith("local/")]
        if fallback_chain:
            fallbacks_arg = [{candidates[0]: fallback_chain}]

    # On the auto path, set num_retries=0 so a dead primary cascades to the
    # next fallback immediately. Default num_retries (configured on Router)
    # would retry the primary 2x before cascading, adding 30-90s of latency
    # before the user sees a working response.
    settings = get_settings()
    per_call_kwargs: dict = {}
    if was_auto:
        per_call_kwargs["num_retries"] = settings.router_num_retries_auto
    if profile_ext_cfg and profile_ext_cfg.get("timeout_seconds"):
        per_call_kwargs["timeout"] = profile_ext_cfg["timeout_seconds"]
    if reasoning_params is not None:
        per_call_kwargs["model_params"] = reasoning_params

    # ── Prompt cache (blocking deterministic requests only) ────────────
    cache_status = "BYPASS"
    cache_hit_response: dict | None = None
    cache_lookup_key: str | None = None
    if not body.stream and prompt_cache.is_cacheable(completion_kwargs):
        cache_lookup_key = prompt_cache.cache_key(
            model=body.model,
            messages=completion_kwargs["messages"],
            temperature=completion_kwargs.get("temperature"),
            tools=completion_kwargs.get("tools"),
            response_format=completion_kwargs.get("response_format"),
            seed=completion_kwargs.get("seed"),
            max_tokens=completion_kwargs.get("max_tokens"),
            max_completion_tokens=completion_kwargs.get("max_completion_tokens"),
            stop=completion_kwargs.get("stop"),
            tool_choice=completion_kwargs.get("tool_choice"),
            top_p=completion_kwargs.get("top_p"),
            n=completion_kwargs.get("n"),
            presence_penalty=completion_kwargs.get("presence_penalty"),
            frequency_penalty=completion_kwargs.get("frequency_penalty"),
            logit_bias=completion_kwargs.get("logit_bias"),
            # Reasoning changes the answer, so it must change the key: a
            # `high` request must never be served a cached `low` response,
            # and a downgraded request must not reuse the requested level's
            # entry. Requests without effort pass None and keep their keys.
            reasoning_effort=reasoning_requested,
            reasoning_effective=reasoning_effective,
        )
        cached = await prompt_cache.get_backend().get(cache_lookup_key)
        if cached is not None:
            cache_status = "HIT"
            cache_hit_response = cached
        else:
            cache_status = "MISS"

    if cache_hit_response is not None:
        # Cache hit: served by us, no upstream call. Provider tagged "cache",
        # cost is zero so the savings dashboard stays accurate. We use the
        # resolved primary as the served model — cache lookup is keyed on
        # the same model so there's no cascade ambiguity here.
        cached_model = cache_hit_response.get("model", resolved_model)
        log = await _build_log_row(
            body=body, kc=kc,
            response={
                "model": cached_model,
                "usage": cache_hit_response.get("usage", {}),
                "_geekcubo_meta": {"provider": "cache", "latency_ms": 0},
            },
            status_code=200, error_type=None, started_perf=started_perf,
            strategy=strategy,
            requested_model=requested_model,
            actual_resolved=cached_model,
            auto_plan=auto_plan,
            request_source=request_source,
            trace_id=trace_id,
        )
        log.cost_microcents = 0
        db.add(log)
        try:
            await db.commit()
        except Exception as commit_err:
            logger.warning("request_log_commit_failed", error=str(commit_err))
        return JSONResponse(
            content=cache_hit_response,
            headers=_geek_response_headers(
                resolved_model=cached_model,
                requested_model=requested_model,
                strategy=strategy,
                cache_status="HIT",
                auto_plan=auto_plan,
                reasoning_requested=reasoning_requested,
                reasoning_effective=reasoning_effective,
            ),
        )

    # ── Streaming path ─────────────────────────────────────────────────
    # NOTE: LiteLLM Router can fall back to a different model only BEFORE the
    # first chunk is emitted (or via MidStreamFallbackError, which only some
    # providers raise). Once any byte of the SSE stream is sent to the client,
    # mid-flight cascade is impossible — we have to surface the error and let
    # the client decide what to do.
    if body.stream:
        # Auto-inject `stream_options.include_usage=True` if the client
        # didn't set it. Without this, OpenAI/LiteLLM streaming responses
        # omit the `usage` field entirely — chunks have no token counts,
        # so our log row gets input=0, output=0 and the cost calculation
        # rounds to zero. Almost no client knows to opt-in to this flag,
        # which would silently zero out streaming spend in the dashboard.
        # Honor an explicit `include_usage=False` from the client if they
        # really want to disable it (e.g. wire-format compatibility tests).
        existing_so = completion_kwargs.get("stream_options") or {}
        if "include_usage" not in existing_so:
            completion_kwargs["stream_options"] = {**existing_so, "include_usage": True}

        async def _log_pre_stream_failure(status: int, err_type: str | None) -> None:
            """Persist a row for a stream that failed BEFORE its first chunk.

            The mid-stream path logs from `_finalize` and the blocking path
            from its `finally`, but this failure happens between them: the
            client is rendered a real 404/429/403/503 and nothing recorded
            it, so the same upstream failure was accounted for when
            stream=false and vanished when stream=true.
            """
            if log_status is not None and err_type is not None:
                status = log_status(status, err_type)
            log = await _build_log_row(
                body=body, kc=kc, response={},
                status_code=status, error_type=err_type,
                started_perf=started_perf,
                strategy=strategy,
                requested_model=requested_model,
                actual_resolved=resolved_model,
                auto_plan=auto_plan,
                request_source=request_source,
            trace_id=trace_id,
                )
            db.add(log)
            try:
                await db.commit()
            except Exception as commit_err:
                # Roll back so the request-scoped session is not left in a
                # dirty state. Without this, the next DB operation on the
                # same session (e.g. the streaming _finalize or the
                # blocking path's own commit) fails with InvalidRequestError
                # because the pending INSERT is still attached.
                try:
                    await db.rollback()
                except Exception:
                    pass
                logger.warning("request_log_commit_failed", error=str(commit_err))

        try:
            stream_obj = await client.acompletion(
                **completion_kwargs,
                fallbacks=fallbacks_arg,
                **per_call_kwargs,
            )
        except HTTPException:
            raise
        except UpstreamProviderError as exc:
            logger.warning("chat_completion_upstream_error", error_type=exc.error_type)
            await _log_pre_stream_failure(exc.http_status, exc.error_type)
            raise HTTPException(
                status_code=exc.http_status,
                detail="Upstream provider error",
                # The generic HTTP status alone loses the translated type
                # (e.g. model_not_found is 422 here but 404 on the
                # Anthropic/Gemini surfaces).
                headers={ERROR_TYPE_HEADER: exc.error_type},
            ) from exc
        except Exception as exc:
            logger.warning("chat_completion_upstream_error", error_type=type(exc).__name__)
            await _log_pre_stream_failure(503, type(exc).__name__)
            raise HTTPException(status_code=503, detail="Upstream provider error") from exc

        async def sse() -> AsyncGenerator[str, None]:
            """Drain the chunk stream → emit SSE → write RequestLog when done."""
            agg_usage: dict = {}
            agg_provider = "unknown"
            agg_latency = 0
            # The first chunk's `model` field tells us what LiteLLM actually
            # served (could be a cascaded fallback, not the resolved primary).
            agg_model: str | None = None
            status_code = 200
            error_type: str | None = None
            log_written = False

            async def _finalize() -> None:
                """Write the request log row exactly once.

                Called from two places: the cancel branch (so the row lands
                even if the [DONE] yield fails against a disconnected
                client), and the `finally` block (the normal path). The
                `log_written` guard makes the second call a no-op when the
                cancel path already ran.
                """
                nonlocal log_written, agg_provider
                if log_written:
                    return
                # Real LiteLLM stream chunks don't carry _geekcubo_meta (the
                # adapter only injects it on non-stream responses, since
                # wrapping every chunk would be wasteful). Look up provider
                # attribution from the served model name against the active
                # deployments — same lookup the non-stream adapter does.
                if agg_provider == "unknown" and agg_model:
                    deployments = getattr(client, "_deployments", []) or []
                    served = match_served_deployment(
                        deployments,
                        hidden=hidden_params_of(stream_obj),
                        served_model=agg_model,
                    )
                    if served is not None:
                        agg_provider = served.provider
                    else:
                        # Unambiguous name match only.
                        bare_served = (
                            agg_model.split("/", 1)[-1] if "/" in agg_model else agg_model
                        )
                        for d in deployments:
                            if agg_model in (d.litellm_model, d.model_name) or bare_served == d.model_name:
                                agg_provider = d.provider
                                break
                synthetic = {
                    "model": agg_model or resolved_model,
                    "usage": agg_usage,
                    "_geekcubo_meta": {"provider": agg_provider},
                }
                # Operator-priced (custom) deployments are costed from their
                # configured price on streams too; previously a stream had no
                # cost source for them and billable traffic logged as $0.
                from packages.litellm_adapter.deployment_attribution import operator_price_meta

                synthetic["_geekcubo_meta"].update(
                    operator_price_meta(
                        match_served_deployment(
                            getattr(client, "_deployments", []) or [],
                            hidden=hidden_params_of(stream_obj),
                            served_model=agg_model or resolved_model,
                        )
                    )
                )
                if agg_latency:
                    # Real LiteLLM chunks carry no _geekcubo_meta, so this is
                    # normally absent — leaving the key out lets
                    # _build_log_row fall back to the measured wall-clock
                    # latency instead of persisting a constant 0.
                    synthetic["_geekcubo_meta"]["latency_ms"] = agg_latency
                from sqlalchemy import select

                from packages.db import session as session_mod

                # The row's VALUES are computed exactly once — latency is
                # measured here, before any commit attempt, so retry
                # backoff never inflates it — and every attempt inserts a
                # fresh ORM object carrying the same id/trace_id. (Fresh,
                # because an object left over from a failed flush carries
                # session state that makes a second session treat it as
                # an UPDATE, not an INSERT.)
                # Same correction the blocking path applies: on a native
                # surface the delivered status differs from the engine's
                # generic one (the Gemini aggregate stream renders a real
                # 404/429/403 from the error chunk; the SSE surfaces report
                # the same class in their in-band error frame), so the row
                # must not say 503 for a response the client saw as 404.
                row_status = status_code
                if log_status is not None and error_type is not None:
                    row_status = log_status(status_code, error_type)
                # Failover attempts made before the stream was accepted. The
                # adapter tags them onto the stream wrapper (streams carry no
                # _geekcubo_meta); without this the row claimed one clean
                # attempt even when the primary had failed.
                stream_attempts = getattr(stream_obj, "_geek_attempts", None)
                template = await _build_log_row(
                    body=body, kc=kc, response=synthetic,
                    status_code=row_status, error_type=error_type,
                    started_perf=started_perf,
                    strategy=strategy,
                    requested_model=requested_model,
                    actual_resolved=agg_model,
                    auto_plan=auto_plan,
                    attempts=(
                        list(stream_attempts)
                        if isinstance(stream_attempts, list) and stream_attempts
                        else None
                    ),
                    request_source=request_source,
                    trace_id=trace_id,
                )
                row_values = {
                    c.key: getattr(template, c.key)
                    for c in RequestLog.__table__.columns
                    if getattr(template, c.key) is not None
                }
                row_values.setdefault("id", str(uuid.uuid4()))

                async def _already_persisted(s) -> bool:
                    return (await s.scalar(
                        select(RequestLog.id).where(RequestLog.trace_id == row_values["trace_id"])
                    )) is not None

                async def _commit_row(*, retry: bool) -> None:
                    """INSERT + COMMIT the row on a session of its own.

                    Only a failing `commit()` propagates; a failure while
                    closing the session AFTER the commit returned is
                    swallowed — the row is already in. A retry is
                    idempotent: it first looks the trace_id up, so a COMMIT
                    that landed but whose ack was lost on the wire
                    (PostgreSQL, connection dropped mid-ack) is not
                    inserted a second time — and the shared primary key
                    would reject a duplicate anyway.
                    """
                    log = RequestLog(**row_values)
                    if session_mod._session_factory is None:
                        # Test-only fallback (the app always installs a
                        # factory): the request-scoped session has to be
                        # rolled back before a retry can reuse it.
                        if retry and await _already_persisted(db):
                            return
                        db.add(log)
                        try:
                            await db.commit()
                        except Exception:
                            try:
                                await db.rollback()
                            except Exception:
                                pass
                            raise
                        return
                    s = session_mod._session_factory()
                    try:
                        if retry and await _already_persisted(s):
                            return
                        s.add(log)
                        await s.commit()
                    finally:
                        try:
                            await s.close()
                        except Exception as close_err:
                            logger.debug(
                                "request_log_session_close_failed", error=str(close_err),
                            )

                # At-most-once across the two call sites: mark BEFORE the
                # first attempt so the other _finalize never re-runs this
                # sequence. Retries live HERE, bounded by
                # _LOG_COMMIT_BACKOFF_S and only for a commit that failed
                # outright — this row is the only record of a stream's
                # tokens and cost, so a transient DB hiccup at request end
                # must not silently zero that spend. Durability against a
                # close/cancel landing mid-commit (e.g. a disconnect
                # delivered during the protocol adapters' post-[DONE]
                # drain) comes from running each attempt in its own task:
                # cancellation aimed at THIS task can't abort the INSERT.
                log_written = True
                attempts = len(_LOG_COMMIT_BACKOFF_S) + 1
                for attempt in range(1, attempts + 1):
                    commit_task = asyncio.ensure_future(_commit_row(retry=attempt > 1))
                    try:
                        await asyncio.shield(commit_task)
                        return
                    except Exception as commit_err:
                        if attempt < attempts:
                            logger.info(
                                "request_log_commit_retry",
                                error=str(commit_err), attempt=attempt,
                            )
                            try:
                                await asyncio.sleep(_LOG_COMMIT_BACKOFF_S[attempt - 1])
                            except BaseException:
                                # Cancelled during the backoff: nothing is
                                # in flight, the row is given up on — say
                                # so, then propagate like the arm below.
                                logger.warning(
                                    "request_log_commit_failed",
                                    error=str(commit_err), attempts=attempt,
                                )
                                raise
                            continue
                        logger.warning(
                            "request_log_commit_failed",
                            error=str(commit_err), attempts=attempt,
                        )
                    except BaseException:
                        # CancelledError aimed at us, not at the commit —
                        # wait the in-flight attempt out so a row about to
                        # land isn't dropped, then let the cancellation
                        # propagate (no further attempts: we are being torn
                        # down).
                        try:
                            await commit_task
                        except Exception as commit_err:
                            logger.warning(
                                "request_log_commit_failed",
                                error=str(commit_err), attempts=attempt,
                            )
                        except BaseException:
                            pass
                        raise

            last_d: dict = {}
            try:
                async for chunk in _aiter(stream_obj):
                    d = _chunk_to_dict(chunk)
                    # Hoist internal metadata onto the request log without
                    # leaking it into the SSE stream.
                    if "_geekcubo_meta" in d:
                        meta = d.pop("_geekcubo_meta") or {}
                        agg_provider = meta.get("provider", agg_provider)
                        agg_latency = meta.get("latency_ms", agg_latency)
                    if "usage" in d and d["usage"]:
                        agg_usage = d["usage"]
                    if d.get("model"):
                        agg_model = d["model"]
                    last_d = d
                    yield f"data: {json.dumps(d, separators=(',', ':'))}\n\n"
                # A trailing frame that already carries `usage` is the usage
                # frame, whether or not `choices` is empty. LiteLLM's
                # include_usage chunk uses
                # `choices: [{"index": 0, "delta": {}}]` rather than `[]`,
                # and some providers attach usage to the finish_reason
                # chunk. Requiring empty choices synthesized a second copy
                # of that usage, and clients that sum `usage` across frames
                # double-counted tokens. Synthesize only when usage was
                # aggregated from an earlier chunk and the stream did not
                # end with it.
                last_had_usage = bool(last_d.get("usage"))
                if agg_usage and not last_had_usage:
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "id": last_d.get("id", ""),
                                "object": last_d.get("object", "chat.completion.chunk"),
                                "created": last_d.get("created", int(time.time())),
                                "model": agg_model or resolved_model,
                                "choices": [],
                                "usage": agg_usage,
                            },
                            separators=(',', ':'),
                        )
                        + "\n\n"
                    )
                yield "data: [DONE]\n\n"
            except (asyncio.CancelledError, GeneratorExit):
                # Client closed the connection (Ctrl+C, tab closed, browser
                # navigated away, proxy timeout, ...). Two distinct signals
                # land here depending on which side noticed first:
                #   - CancelledError: asyncio task running the generator was
                #     cancelled (Starlette saw the disconnect first).
                #   - GeneratorExit: Starlette called aclose() on us during
                #     its own cleanup pass.
                # Either way the consumer is gone — no point yielding more
                # frames, and we MUST stop pulling chunks from upstream so
                # LiteLLM doesn't keep burning tokens on a response nobody
                # will read.
                error_type = "client_disconnect"
                # 499 Client Closed Request — nginx convention, widely
                # understood in analytics pipelines for "user bailed".
                status_code = 499
                logger.info(
                    "chat_completion_stream_client_disconnect",
                    served_model=agg_model,
                )
                # Cleanup MUST actually complete before we unwind, not just
                # be scheduled. `asyncio.shield()` here would NOT wait — the
                # outer await re-raises CancelledError immediately under
                # Starlette's anyio task group cancellation, leaving the
                # inner aclose/finalize racing FastAPI's request-scoped
                # session teardown.
                #
                # `anyio.CancelScope(shield=True)` is the right primitive:
                # awaits inside the shielded scope ignore outer cancellation
                # and run to completion. The scope exits normally and we
                # re-raise the original CancelledError below.
                aclose = getattr(stream_obj, "aclose", None)
                with anyio.CancelScope(shield=True):
                    if aclose is not None:
                        try:
                            await aclose()
                        except Exception:
                            pass
                    try:
                        await _finalize()
                    except Exception:
                        pass
                # Re-raise so asyncio/Starlette see proper cancel propagation.
                raise
            except AdapterError:
                # The protocol adapter downstream of us failed and threw
                # this in rather than closing us: our own fault, not the
                # caller's. Without this branch the close would be
                # indistinguishable from a disconnect and every adapter bug
                # would be filed as 499/client_disconnect.
                error_type = "adapter_error"
                status_code = 500
                logger.warning(
                    "chat_completion_stream_adapter_error", served_model=agg_model,
                )
                aclose = getattr(stream_obj, "aclose", None)
                with anyio.CancelScope(shield=True):
                    if aclose is not None:
                        try:
                            await aclose()
                        except Exception:
                            pass
                return
            except Exception as exc:
                # Translate the underlying LiteLLM exception so the request
                # log records the meaningful error_type (rate_limit_error,
                # model_not_found, ...) instead of just the raw class name.
                # The HTTP status is already 200 because headers were sent
                # before the first chunk; the SSE error frame carries the
                # type string for clients that parse it.
                from packages.litellm_adapter.client import _translate_error
                try:
                    translated = _translate_error(exc)
                except Exception:
                    translated = None
                if isinstance(translated, UpstreamProviderError):
                    error_type = translated.error_type
                    sse_error_type = translated.error_type
                else:
                    error_type = type(exc).__name__
                    sse_error_type = "upstream_error"
                # Mid-stream the response status is locked to 200 (headers
                # already flushed). Record 503 in the log to flag the
                # underlying upstream failure for analytics.
                status_code = 503
                logger.warning(
                    "chat_completion_stream_error",
                    error=str(exc), error_type=error_type,
                )
                err_body = {
                    "error": {
                        "message": f"Upstream provider error: {exc}",
                        "type": sse_error_type,
                    }
                }
                yield f"data: {json.dumps(err_body)}\n\n"
                # Not handling GeneratorExit here, so yielding the sentinel
                # is legal; clients reading until [DONE] still get it after
                # an upstream error.
                yield "data: [DONE]\n\n"
            finally:
                # Same shielding reason as the cancel branch: ensure the
                # log write actually completes before we unwind, even if
                # we're inside a cancelled scope. The cancel branch may
                # have already run _finalize and set log_written=True; the
                # `if log_written: return` guard inside makes this call a
                # cheap no-op in that case.
                with anyio.CancelScope(shield=True):
                    try:
                        await _finalize()
                    except Exception:
                        pass

        return StreamingResponse(
            sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                # Headers are sent before the first chunk, so we can only
                # promise the resolved primary here. The actual served model
                # ends up in each chunk's `model` field — clients reading the
                # stream get authoritative info from there.
                **_geek_response_headers(
                    resolved_model=resolved_model,
                    requested_model=requested_model,
                    strategy=strategy,
                    auto_plan=auto_plan,
                    reasoning_requested=reasoning_requested,
                    reasoning_effective=reasoning_effective,
                ),
            },
        )

    # ── Blocking path ──────────────────────────────────────────────────
    status_code = 200
    error_type: str | None = None
    response: dict = {}
    actual_resolved: str | None = None
    try:
        response = await client.acompletion(
            **completion_kwargs,
            fallbacks=fallbacks_arg,
            **per_call_kwargs,
        )
        # The response.model field is what LiteLLM ultimately served — could
        # be the resolved primary, or a cascaded fallback if the primary 404'd.
        if isinstance(response, dict):
            actual_resolved = response.get("model") or resolved_model
    except HTTPException as exc:
        # Defensive only: record the outcome so this arm can't leave the
        # handler-local status_code at its initial 200, which would make the
        # finally write a success-shaped row (cost ~0, no error_type) for a
        # failed request. Unreachable today: the adapter blanket-translates
        # every exception into UpstreamProviderError (packages/litellm_adapter/
        # client.py, acompletion), so nothing in this try raises HTTPException.
        # Kept because the sibling arms already record their status and this one
        # would silently mis-log the first time that stops holding.
        status_code = exc.status_code
        raise
    except UpstreamProviderError as exc:
        status_code = exc.http_status
        error_type = exc.error_type
        failed_attempts = list(getattr(exc, "attempts", []) or [])
        _attempts = failed_attempts
        logger.warning("chat_completion_upstream_error", error=str(exc), error_type=exc.error_type)
        detail = f"Upstream provider error: {exc}"
        err_headers = {ERROR_TYPE_HEADER: exc.error_type}
        tried = [a.get("model") for a in failed_attempts if a.get("model")]
        if auto_plan is not None and len(tried) < len(candidates) and tried:
            # Stopped early: the failure type is not one another model can
            # fix (auth, permission, invalid request). Say so, rather than
            # claiming every candidate was tried.
            detail = (
                f"{exc.error_type} from {tried[-1]}; not retried on other "
                f"candidates because this failure type is not recoverable by "
                f"switching models. Last error: {exc}"
            )
            err_headers["x-geek-routing-diagnosis"] = "non_retryable_failure"
        elif auto_plan is not None and len(candidates) > 1:
            detail = (
                f"All {len(tried) or len(candidates)} Auto candidates failed "
                f"({', '.join(tried or candidates)}). Last error: {exc}"
            )
            err_headers["x-geek-routing-diagnosis"] = "candidates_exhausted"
        elif auto_plan is not None:
            err_headers["x-geek-routing-diagnosis"] = "upstream_unavailable"
        raise HTTPException(
            status_code=exc.http_status,
            detail=detail,
            # See the streaming-path twin: lets the native routes map the
            # translated type to their surface's status/error taxonomy.
            headers=err_headers,
        ) from exc
    except Exception as exc:
        status_code = 503
        error_type = type(exc).__name__
        logger.warning("chat_completion_upstream_error", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Upstream provider error") from exc
    finally:
        if log_status is not None and error_type is not None:
            status_code = log_status(status_code, error_type)
        log = await _build_log_row(
            body=body, kc=kc, response=response if isinstance(response, dict) else {},
            status_code=status_code, error_type=error_type,
            started_perf=started_perf,
            strategy=strategy,
            requested_model=requested_model,
            # On failure actual_resolved is None — fall back to the resolved
            # primary so the log row records what we tried, not "auto" (which
            # _build_log_row would otherwise default to via requested_model).
            actual_resolved=actual_resolved or resolved_model,
            auto_plan=auto_plan,
            # Prefer the adapter's record (success path carries it in meta,
            # error path in exc.attempts); _build_log_row falls back to meta.
            attempts=failed_attempts or None,
            request_source=request_source,
            trace_id=trace_id,
        )
        db.add(log)
        try:
            await db.commit()
        except Exception as commit_err:
            logger.warning("request_log_commit_failed", error=str(commit_err))

    if isinstance(response, dict) and "_geekcubo_meta" in response:
        response = {k: v for k, v in response.items() if k != "_geekcubo_meta"}

    # Write to cache on MISS only when the served model is in the same
    # model_group as the resolved primary. If LiteLLM Router cascaded to a
    # different group (fallback), the response is from a DIFFERENT model
    # than the cache key implies, and caching it would poison future
    # requests for the primary. Equivalent names within the same group
    # (prefix, dated alias) ARE safe to cache — see the helper for details.
    cache_safe_to_write = (
        cache_status == "MISS"
        and cache_lookup_key is not None
        and isinstance(response, dict)
        and _served_same_group_as_requested(
            requested_group=resolved_model,
            served_model=actual_resolved,
            client=client,
        )
    )
    if cache_safe_to_write:
        try:
            await prompt_cache.get_backend().set(cache_lookup_key, response, ttl=3600)
        except Exception as exc:
            logger.warning("prompt_cache_set_failed", error=str(exc))

    return JSONResponse(
        content=response,
        headers=_geek_response_headers(
            # actual_resolved reflects post-cascade truth (might differ from
            # the primary if Router fell back). Falls back to resolved_model
            # if the response shape is unexpected.
            resolved_model=actual_resolved or resolved_model,
            requested_model=requested_model,
            strategy=strategy,
            cache_status=cache_status,
            auto_plan=auto_plan,
            reasoning_requested=reasoning_requested,
            reasoning_effective=reasoning_effective,
        ),
    )


def _aiter(obj):
    """Coerce a thing into an async iterator.

    LiteLLM's `acompletion(stream=True)` returns a `CustomStreamWrapper`
    that's already async-iterable. Test mocks may return a plain async
    generator. Accept both.
    """
    if hasattr(obj, "__aiter__"):
        return obj.__aiter__()
    if isinstance(obj, AsyncIterable):
        return obj.__aiter__()
    raise TypeError(f"Streaming router returned non-iterable: {type(obj).__name__}")
