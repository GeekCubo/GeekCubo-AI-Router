"""Administrator-session read APIs for the console (and Phase 3 chat).

`GET /v1/models` is an *inference* route: SDKs call it with an sk-geek-* key.
The dashboard is not an SDK and no longer holds such a key — it holds a
session — so it reads the same merged catalog from here instead.

This is also the seam the native chat (Phase 3) will use: it runs inside the
signed-in dashboard, so its model picker and requests authenticate with the
administrator session through `/api/...` rather than by smuggling an inference
key into the browser. Keeping one catalog function (`merged_catalog`) behind
both routes guarantees the picker and the SDK listing never disagree.

Routing helpers live here too because they are admin-only reads:

  GET /api/routing/models   — every routable model with the metadata the
                              pool pickers show (provider, capabilities,
                              context, price, Auto availability, pools)
  GET /api/routing/explain  — dry-run of the Auto decision for a synthetic
                              request: per-stage candidate counts, the
                              tier, the chosen model and why. No upstream
                              call, no request-log row.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_admin_session, get_db
from packages.auth.sessions import SessionRecord

router = APIRouter(prefix="/api", tags=["console"])


@router.get("/models")
async def console_models(
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.custom_providers import merged_catalog

    catalog = await merged_catalog(db, eligible_only=False)
    return {
        "object": "list",
        "data": [
            {
                "id": m.id,
                "object": "model",
                "owned_by": m.provider,
                "provider": m.provider,
            }
            for m in catalog
        ],
    }


async def _routing_context(db: AsyncSession):
    """Shared inputs for the routing inventory and dry-run."""
    from app import router_cache
    from app.custom_providers import load_custom_providers, merged_catalog
    from app.routing_policy import default_policy

    client = await router_cache.get_router(db)
    deployable = {d.model_name for d in getattr(client, "_deployments", []) or []}
    raw_policy = getattr(client, "routing_policy", None)
    policy = raw_policy if isinstance(raw_policy, dict) else default_policy()
    raw_strategy = getattr(client, "strategy", None)
    strategy = raw_strategy if isinstance(raw_strategy, str) and raw_strategy else "balanced"
    raw_preferred = getattr(client, "preferred_models", None)
    preferred = list(raw_preferred) if isinstance(raw_preferred, list) else []
    full = await merged_catalog(db, eligible_only=False)
    auto = await merged_catalog(db, eligible_only=True)
    views = await load_custom_providers(db)
    return client, deployable, policy, strategy, preferred, full, auto, views


@router.get("/routing/models")
async def routing_models(
    q: str = Query("", max_length=200, description="case-insensitive filter"),
    scope: str = Query("routable", pattern="^(routable|custom|all)$"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Paginated model inventory for the Routing page pickers.

    `scope=routable` (default) lists models that can actually be deployed —
    the built-in catalogue alone has hundreds of entries for providers you
    have no key for, which is noise in a pool picker. `custom` limits to
    custom-provider models; `all` is everything in the catalogue.
    """
    from app.auto_routing import is_confirmed_price, is_priced_for_auto
    from app.routing_policy import allows_reference_estimates, pool_membership

    _client, deployable, policy, *_rest, full, auto, views = await _routing_context(db)
    allow_estimates = allows_reference_estimates(policy)
    auto_ids = {m.id for m in auto}
    custom_slugs = {v.slug for v in views}
    pools = pool_membership(policy)

    rows = []
    needle = q.strip().lower()
    for m in full:
        is_custom = m.provider in custom_slugs
        if scope == "routable" and m.id not in deployable:
            continue
        if scope == "custom" and not is_custom:
            continue
        if needle and needle not in m.id.lower() and needle not in (m.provider or "").lower():
            continue
        member_of = sorted(name for name, ids in pools.items() if m.id in ids)
        priced = is_priced_for_auto(m, allow_estimates=allow_estimates)
        if m.id not in deployable:
            availability = "not_deployable"
        elif m.id not in auto_ids:
            availability = "pinned_only"
        elif not priced:
            availability = (
                "estimate_only" if is_priced_for_auto(m, allow_estimates=True) else "unpriced"
            )
        else:
            availability = "auto"
        rows.append({
            "id": m.id,
            "provider": m.provider,
            "custom": is_custom,
            # Tri-state capability evidence: True / False / null (unknown).
            # The dashboard only renders a pill for True; null renders as no
            # pill, never as "unsupported".
            "tools": m.supports_tools,
            "vision": m.supports_vision,
            "json": m.supports_json_mode,
            "json_schema": m.supports_json_schema,
            "context_length": getattr(m, "context_length", None),
            # Per-1M prices; None means unknown (never shown as $0).
            "input_per_million": (m.input_cost_per_token * 1e6) if m.input_cost_per_token else None,
            "output_per_million": (m.output_cost_per_token * 1e6) if m.output_cost_per_token else None,
            "price_source": getattr(m, "price_source", "catalog"),
            "price_confirmed": is_confirmed_price(m),
            "availability": availability,
            "pools": member_of,
        })
    rows.sort(key=lambda r: (not r["custom"], r["availability"] != "auto", r["id"]))
    total = len(rows)
    return {"total": total, "offset": offset, "limit": limit, "models": rows[offset:offset + limit]}


@router.get("/routing/explain")
async def routing_explain(
    tools: bool = False,
    vision: bool = False,
    json_mode: bool = Query(False, alias="json"),
    json_schema: bool = False,
    messages: int = Query(1, ge=1, le=1000),
    prompt_chars: int = Query(200, ge=0, le=10_000_000),
    max_tokens: int = Query(0, ge=0, le=10_000_000),
    escalate: bool = False,
    profile: str | None = Query(None, max_length=80),
    input_tokens: int = Query(0, ge=0, le=10_000_000),
    session_id: str | None = Query(None, max_length=200),
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dry-run the Auto decision for a described request.

    Shows every filtering stage so the admin can see where candidates drop
    out. Uses the live policy and deployments; sends nothing upstream.
    `profile` selects a saved routing profile instead of the global Auto
    config; `session_id` exercises stickiness/escalation state read-only.
    """
    from app import auto_planner
    from app.auto_routing import _model_meets, is_confirmed_price, is_priced_for_auto
    from app.custom_providers import explain_auto_exclusions
    from app.quality_scores import resolve_model_metrics
    from app.routing_policy import (
        PolicyError,
        allows_reference_estimates,
        classify_difficulty,
        default_policy,
        normalize_policy,
    )
    from app.routing_profiles import apply_profile_filter, find_profile

    _client, deployable, policy, strategy, preferred, full, auto, views = await _routing_context(db)
    profile_slug = None
    profile_notes: list[str] = []
    if profile and profile != "auto":
        from app.seed import DEFAULT_WORKSPACE_ID

        prof = await find_profile(db, DEFAULT_WORKSPACE_ID, profile)
        if prof is None:
            raise HTTPException(status_code=404, detail=f"Routing profile '{profile}' not found.")
        try:
            policy = normalize_policy(prof.policy)
        except PolicyError:
            policy = default_policy()
        strategy = prof.strategy or strategy
        profile_slug = prof.slug
        ext = prof.profile if isinstance(prof.profile, dict) else {}
        auto, profile_notes = apply_profile_filter(
            [m for m in auto if m.id in deployable],
            ext,
            allow_estimates=allows_reference_estimates(policy),
        )
    allow_estimates = allows_reference_estimates(policy)

    needs: set[str] = set()
    if tools:
        needs.add("tools")
    if vision:
        needs.add("vision")
    if json_mode:
        needs.add("json_mode")
    if json_schema:
        needs.add("json_schema")
    if input_tokens:
        prompt_chars = max(prompt_chars, input_tokens * 4)
    per = max(1, prompt_chars // max(1, messages))
    body: dict = {
        "messages": [{"role": "user", "content": "x" * per} for _ in range(messages)],
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    stages = []
    deployable_auto = [m for m in auto if m.id in deployable]
    stages.append({"stage": "auto_eligible_and_deployable", "count": len(deployable_auto)})
    priced = [
        m for m in deployable_auto if is_priced_for_auto(m, allow_estimates=allow_estimates)
    ]
    stages.append({"stage": "priced", "count": len(priced)})
    capable = [m for m in priced if _model_meets(m, needs)]
    stages.append({"stage": "capable", "count": len(capable)})
    est = auto_planner.estimate_prompt_tokens(body)
    fits = [m for m in capable if not (m.context_length and est > m.context_length)]
    stages.append({"stage": "fits_context", "count": len(fits)})

    quality_scores = tps = ttft = None
    if strategy in ("quality", "balanced", "fastest", "adaptive", "adaptive_gated"):
        metrics = await resolve_model_metrics(db=db, workspace_id="default")
        quality_scores, tps, ttft = metrics.quality_scores, metrics.tps_scores, metrics.ttft_scores
    evidence = await auto_planner.load_evidence(db) if strategy in ("adaptive", "adaptive_gated") else {}

    difficulty = classify_difficulty(body, needs, policy)
    result: dict = {
        "strategy": strategy,
        "pricing_mode": "estimate_allowed" if allow_estimates else "confirmed_only",
        "needs": sorted(needs),
        "estimated_prompt_tokens": est,
        "difficulty": {"tier": difficulty.tier, "signals": difficulty.signals},
        "stages": stages,
    }
    hints: dict = {}
    if escalate:
        hints["escalate"] = "1"
    if session_id:
        hints["conversation_id"] = session_id
    try:
        plan = auto_planner.plan_auto(
            body=body, needs=needs, deployable=deployable, catalog=auto,
            strategy=strategy, preferred_models=preferred, allowlist=None,
            quality_scores=quality_scores, tps_scores=tps, ttft_scores=ttft,
            policy=policy, evidence=evidence,
            # The dry-run must not mutate real conversation state.
            hints=hints,
        )
        # Per-candidate detail: why each eligible model won or lost.
        candidate_detail = []
        rank = {mid: i for i, mid in enumerate(plan.candidates)}
        seen: set[str] = set()
        for m in auto:
            if m.id in seen or m.id not in deployable:
                continue
            seen.add(m.id)
            entry = {
                "model": m.id,
                "selected": m.id in rank,
                "rank": rank.get(m.id),
                "price_source": "confirmed" if is_confirmed_price(m) else "reference_or_unknown",
            }
            if m.id not in rank:
                reasons = []
                if not _model_meets(m, needs):
                    reasons.append("capability mismatch")
                if not is_priced_for_auto(m, allow_estimates=allow_estimates):
                    reasons.append("strict price unknown")
                if m.context_length and est > m.context_length:
                    reasons.append("insufficient context")
                if not reasons:
                    reasons.append("ranked below the selected candidates")
                entry["reasons"] = reasons
            candidate_detail.append(entry)
        result.update({
            "ok": True,
            "selected": plan.candidates[0],
            "fallbacks": plan.candidates[1:],
            "tier": plan.tier,
            "effective_strategy": plan.effective_strategy,
            "reason": plan.reason,
            "candidate_count": plan.candidate_count,
            "escalated": plan.escalated,
            "sticky": plan.sticky,
            "notes": plan.notes + profile_notes,
            "profile": profile_slug or "auto",
            "candidates": candidate_detail[:100],
            "dry_run": True,
        })
    except auto_planner.AutoRoutingError as err:
        if err.message:
            category, message = err.category, err.message
        else:
            category, message = auto_planner.diagnose_empty(
                needs=needs, deployable=deployable, full_catalog=full,
                auto_catalog=auto, custom_views=views, allowlist=None, body=body,
                allow_estimates=allow_estimates,
            )
        result.update({
            "ok": False,
            "diagnosis": category,
            "message": message,
            "exclusions": explain_auto_exclusions(
                views, needs=needs, deployable=deployable, allow_estimates=allow_estimates,
            ),
        })
    finally:
        # The planner keys state by conversation; the synthetic body's key
        # (or a hypothetical session id) must not linger and influence real
        # traffic.
        key = auto_planner.conversation_key(body, session_id)
        auto_planner._CONVERSATIONS.pop(key, None)
    return result


@router.get("/stats")
async def console_stats(
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Canonical inventory counts, so every page shows the same numbers.

    These were previously derived independently per page, which produced
    contradictions an operator can see: Overview read "0 providers" while the
    Providers page listed an enabled custom provider, because Overview counted
    only built-in `provider_keys` rows and ignored custom providers entirely.

    Definitions, deliberately distinct:

      providers_configured  built-in provider keys (DB or env) that decrypt,
                            PLUS custom providers that are enabled and
                            decryptable. One provider counts once.
      providers_enabled     the subset that is switched on — same rule, since a
                            key that cannot decrypt is not usable.
      models_deployable     models the router can actually serve right now
                            (a usable deployment exists for them).
      models_catalog        every model in the merged catalogue, most of which
                            have no key configured. NOT deployable.
      models_auto_eligible  deployable models that also carry usable pricing,
                            i.e. what model="auto" may choose between.
    """
    from sqlalchemy import select

    from app import router_cache
    from app.auto_routing import is_priced_for_auto
    from app.config import get_settings
    from app.custom_providers import load_custom_providers, merged_catalog
    from app.router_cache import usable_providers_from_db
    from packages.db.models.provider_key import ProviderKey

    rows = (
        await db.execute(select(ProviderKey).where(ProviderKey.is_deleted == 0))
    ).scalars().all()

    builtin = usable_providers_from_db(list(rows))
    builtin |= {
        prov for prov, key in get_settings().env_provider_keys().items() if key
    }

    custom_rows = await load_custom_providers(db)
    custom_enabled = [
        p for p in custom_rows
        if getattr(p, "is_enabled", False) and getattr(p, "decryptable", True)
    ]

    client = await router_cache.get_router(db)
    deployable = {d.model_name for d in getattr(client, "_deployments", []) or []}

    from app.routing_policy import allows_reference_estimates, default_policy

    raw_policy = getattr(client, "routing_policy", None)
    allow_estimates = allows_reference_estimates(
        raw_policy if isinstance(raw_policy, dict) else default_policy()
    )
    catalog = await merged_catalog(db, eligible_only=False)
    auto_eligible = [
        m for m in catalog
        if m.id in deployable and is_priced_for_auto(m, allow_estimates=allow_estimates)
    ]
    estimate_only = [
        m for m in catalog
        if m.id in deployable
        and not is_priced_for_auto(m, allow_estimates=allow_estimates)
        and is_priced_for_auto(m, allow_estimates=True)
    ]

    return {
        "providers_configured": len(builtin) + len(custom_enabled),
        "providers_enabled": len(builtin) + len(custom_enabled),
        "providers_builtin": len(builtin),
        "providers_custom": len(custom_enabled),
        "models_deployable": len(deployable),
        "models_catalog": len(catalog),
        "models_auto_eligible": len(auto_eligible),
        "models_estimate_only": len(estimate_only),
        "pricing_mode": "estimate_allowed" if allow_estimates else "confirmed_only",
    }
