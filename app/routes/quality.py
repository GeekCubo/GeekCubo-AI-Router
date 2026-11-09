"""Quality scoring endpoints — backs the dashboard's Quality page.

Surface area:
  GET    /v1/quality                    — full scored-model table + index status
  POST   /v1/quality/refresh            — force-refresh the AA cache
  GET    /v1/quality/auto-preview       — live preview of which model auto would
                                          pick now under the current strategy
  GET    /v1/quality/overrides          — list manual overrides
  PUT    /v1/quality/overrides/{model_id} — set a manual override
  DELETE /v1/quality/overrides/{model_id} — remove an override (revert to AA)
  GET    /v1/quality/key                — is an AA key configured, and where from
  PUT    /v1/quality/key                — store an AA key (encrypted at rest)
  DELETE /v1/quality/key                — forget the stored key

The dashboard uses these to give the operator transparency over (and
control of) the routing decisions the `quality` strategy makes. AA scores
alone aren't always right for every team — overrides let a developer
encode their own evals on top.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import router_cache
from app._time_util import iso_utc
from app.auto_routing import (
    choose_auto_model,
    litellm_routing_strategy,
)
from app.cache_invalidation_bus import broadcast_metrics_cache_invalidation
from app.config import get_settings
from app.deps import AdminContext, get_admin_context, get_db
from app.quality_scores import (
    fetch_aa_index,
    load_overrides,
    resolve_model_metrics,
)
from packages.db.models.quality_score_override import QualityScoreOverride
from packages.litellm_adapter.catalog import CATALOG, CATALOG_BY_ID

router = APIRouter(prefix="/v1/quality", tags=["quality"])


def _blended_cost(m) -> float:
    """Match auto_routing's blended cost formula (kept private so we don't
    leak the formula into the public surface)."""
    return 0.3 * m.input_cost_per_token + 0.7 * m.output_cost_per_token


def _serialize_aa_index(idx) -> dict[str, Any]:
    """Project a QualityIndex into a JSON-friendly status block.

    `QualityIndex.fetched_at` is per-process monotonic time and is
    re-anchored to "now" whenever the index is loaded from the DB
    snapshot, so it's not a meaningful wall-clock value to surface to
    clients. The dashboard uses `raw_count` / `matched_count` for
    freshness signal; the `source` flag distinguishes live vs stale
    (in-process) vs stale (DB).

    `matched_count` is the union (catalog IDs covered by ANY axis), so
    the dashboard's "X of Y AA models indexed" string still reads as a
    single useful number. `matched_count_breakdown` exposes the per-axis
    counts for callers that want to distinguish quality vs latency
    coverage.
    """
    return {
        "source": idx.source,
        "raw_count": idx.raw_count,
        "matched_count": idx.matched_count,
        "matched_count_breakdown": {
            "quality": idx.matched_count_quality,
            "tps": idx.matched_count_tps,
            "ttft": idx.matched_count_ttft,
        },
        "configured": idx.source != "missing-key",
        # Which AA endpoint these numbers came from, so the page can show a
        # source line that matches what was actually fetched.
        "endpoint": get_settings().artificial_analysis_models_url,
        # AA's own documentation for the free data API: 1,000 requests/day.
        # A key's account page may state a different allowance; see
        # /v1/quality/key for the per-key figure the operator recorded.
        "documented_daily_limit": 1000,
    }


@router.get("")
async def quality_status(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full table of catalog models with their effective quality scores.

    Each row carries:
      - id, provider, blended_cost (per-token, blended 0.3/0.7 in/out)
      - aa_score (from Artificial Analysis, may be None)
      - manual_score (operator override, may be None)
      - effective_score (manual if set, else aa_score, else None)
      - capable_for_chat (always True here — catalog is filtered to chat)
      - deployable (whether a configured provider key covers this model)

    Also includes the AA index status (configured? matched count? source?).
    """
    aa = await fetch_aa_index(db=db, workspace_id=str(kc.workspace_id))
    overrides = await load_overrides(db, str(kc.workspace_id))

    # Build the deployable set from the live router cache.
    client = await router_cache.get_router(db)
    deployable: set[str] = {
        d.model_name for d in getattr(client, "_deployments", []) or []
    }

    rows: list[dict] = []
    for m in CATALOG:
        aa_score = aa.scores.get(m.id)
        manual_score = overrides.get(m.id)
        effective = manual_score if manual_score is not None else aa_score
        rows.append(
            {
                "id": m.id,
                "provider": m.provider,
                "blended_cost": _blended_cost(m),
                "input_cost_per_token": m.input_cost_per_token,
                "output_cost_per_token": m.output_cost_per_token,
                "aa_score": aa_score,
                "manual_score": manual_score,
                "effective_score": effective,
                # Latency metrics from AA — None when AA didn't cover this
                # model on that axis. Dashboard renders "—" for None.
                "tps": aa.tps_scores.get(m.id),
                "ttft": aa.ttft_scores.get(m.id),
                "supports_tools": m.supports_tools,
                "supports_vision": m.supports_vision,
                "supports_json_mode": m.supports_json_mode,
                "supports_json_schema": m.supports_json_schema,
                "deployable": m.id in deployable,
                "deprecation_date": m.deprecation_date,
            }
        )

    # Sort by effective_score desc (None at the bottom), then by cost desc.
    rows.sort(
        key=lambda r: (
            -(r["effective_score"] if r["effective_score"] is not None else -1),
            -r["blended_cost"],
            r["id"],
        )
    )

    return {
        "aa_index": _serialize_aa_index(aa),
        "override_count": len(overrides),
        "models": rows,
        "attribution": {
            "name": "Artificial Analysis",
            "url": "https://artificialanalysis.ai",
            "shown_when": "any AA score appears in routing or the dashboard",
        },
    }


@router.post("/refresh")
async def quality_refresh(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Force a fresh fetch of the AA Intelligence Index.

    Bypasses the 1h cache TTL AND the DB snapshot freshness check.
    Counts against the AA daily request quota (1000/day on the free
    tier) — operators with an outage or a very stale snapshot can use
    this to get back online without waiting for natural expiry.
    On AA success, the new snapshot is also persisted to the DB so the
    next process restart inherits it.

    Also drops the resolver-layer metrics cache so balanced/fastest
    routing sees the fresh values on the very next request, not after
    the 60s TTL.
    """
    aa = await fetch_aa_index(
        db=db, workspace_id=str(kc.workspace_id), force_refresh=True,
    )
    await broadcast_metrics_cache_invalidation()  # global — AA fetch refreshes all workspaces
    return {"aa_index": _serialize_aa_index(aa)}


class AAKeyBody(BaseModel):
    api_key: str = Field(min_length=8, max_length=400)
    # The allowance the operator's AA account reports for this key, in
    # requests per rolling 24h. AA's public docs state 1,000/day for the free
    # data API, but an individual account page can show something else; when
    # the operator records it we display their number instead of ours.
    daily_limit: int | None = Field(default=None, ge=1, le=100000)


def _mask_key(value: str) -> str:
    """Display-safe prefix: never enough of the key to be usable."""
    if len(value) > 12:
        return value[:6] + "..." + value[-4:]
    if len(value) > 4:
        return value[:2] + "..." + value[-2:]
    return "..."


async def _key_row(db: AsyncSession, workspace_id: str):
    from packages.db.models.quality_settings import QualitySettings

    return (
        await db.execute(
            select(QualitySettings).where(QualitySettings.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()


async def _key_status(db: AsyncSession, workspace_id: str) -> dict:
    from packages.litellm_adapter.quality_index import resolve_aa_api_key

    _key, origin = await resolve_aa_api_key(db, workspace_id)
    row = await _key_row(db, workspace_id)
    stored_prefix = row.key_prefix if row is not None else None
    return {
        "configured": origin != "missing",
        # "stored" = saved here and encrypted at rest; "env" = came from
        # ARTIFICIAL_ANALYSIS_API_KEY. The page words these differently.
        "origin": origin,
        "key_prefix": stored_prefix,
        "can_clear": origin == "stored",
        "endpoint": get_settings().artificial_analysis_models_url,
        "documented_daily_limit": 1000,
        "recorded_daily_limit": row.daily_limit if row is not None else None,
        # Connection health, surfaced so the operator can tell at a glance
        # whether the key works, without ever exposing the key itself.
        "connection_status": _derive_connection_status(origin, row),
        "last_sync_at": iso_utc(row.last_sync_at) if row is not None and row.last_sync_at else None,
        "last_error_code": row.last_error_code if row is not None else None,
        "last_error_detail": row.last_error_detail if row is not None else None,
        "last_error_at": iso_utc(row.last_error_at) if row is not None and row.last_error_at else None,
    }


def _derive_connection_status(origin: str, row) -> str:
    """One stable status for the compact connection section.

    Values: "not_configured", "connected", "invalid_key", "rate_limited",
    "connection_failed", "cached". Derived from the persisted last fetch
    result (last_status / last_error_code) and whether a key is present.
    """
    if origin == "missing":
        return "not_configured"
    if row is None:
        # A key exists (env) but has never been recorded here.
        return "connected"
    code = row.last_error_code
    if code:
        return code  # invalid_key | rate_limited | connection_failed
    status = row.last_status
    if status == "live":
        return "connected"
    if status in ("stale-cache", "stale-db"):
        return "cached"
    # A key is configured but has not been fetched yet; nothing wrong to show.
    return "connected"


@router.get("/key")
async def quality_key_status(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Whether an AA key is configured, and where it came from.

    The key itself is never returned -- only a masked prefix.
    """
    return await _key_status(db, str(kc.workspace_id))


@router.put("/key")
async def quality_key_save(
    body: AAKeyBody,
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store an AA key, encrypted at rest, and invalidate cached scores.

    Saved keys take precedence over ARTIFICIAL_ANALYSIS_API_KEY; clearing one
    falls back to the environment value rather than disabling scoring.
    """
    from packages.auth.encryption import encrypt_credential
    from packages.db.models.quality_settings import QualitySettings

    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="API key cannot be empty.")

    workspace_id = str(kc.workspace_id)
    row = await _key_row(db, workspace_id)
    if row is None:
        row = QualitySettings(workspace_id=workspace_id)
        db.add(row)
    row.encrypted_api_key = encrypt_credential(api_key)
    row.key_prefix = _mask_key(api_key)
    row.daily_limit = body.daily_limit
    await db.commit()

    # Scores cached under the old key must not survive the change.
    await broadcast_metrics_cache_invalidation()
    return await _key_status(db, workspace_id)


@router.post("/key/test")
async def quality_key_test(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test the configured AA key against the live endpoint, non-destructively.

    Uses the stored key (or the environment key, if no stored key) exactly as
    routing would. Reports the actual result — connected, invalid key, rate
    limited, connection failed — without modifying the stored credential or the
    cached benchmark snapshot. The key is never echoed.
    """
    from packages.litellm_adapter.quality_index import _classify_fetch_error, _fetch_remote, resolve_aa_api_key

    api_key, origin = await resolve_aa_api_key(db, str(kc.workspace_id))
    if origin == "missing":
        return {
            "configured": False,
            "status": "not_configured",
            "detail": "No Artificial Analysis key is configured.",
        }

    url = get_settings().artificial_analysis_models_url
    try:
        data = await _fetch_remote(url, api_key)
    except Exception as exc:  # noqa: BLE001 — classify, never propagate the raw error
        code, detail = _classify_fetch_error(exc)
        return {"configured": True, "status": code, "detail": detail}

    return {
        "configured": True,
        "status": "connected",
        "detail": f"Connected — {len(data)} model records returned.",
        "model_count": len(data),
    }


@router.delete("/key")
async def quality_key_clear(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Forget the stored key. An environment key, if any, takes over again."""
    workspace_id = str(kc.workspace_id)
    row = await _key_row(db, workspace_id)
    if row is not None:
        row.encrypted_api_key = None
        row.key_prefix = None
        row.daily_limit = None
        await db.commit()
        await broadcast_metrics_cache_invalidation()
    return await _key_status(db, workspace_id)


_VALID_STRATEGIES = {"cheapest", "balanced", "fastest", "quality"}

# Human-readable scoring source per strategy + data-availability state.
# Surfaced verbatim in the dashboard preview ("scoring: ...").
#
# The two fallback labels per strategy distinguish:
#   - "*-cheapest-fallback":         AA data is configured but doesn't cover ANY
#                                     model in this request's eligible set
#                                     (deployable + capability + allowlist).
#                                     Operator likely needs to widen the
#                                     allowlist or add a manual quality override.
#   - "*-no-data-fallback":          AA data is globally unavailable (no key
#                                     configured, AA outage, no overrides).
#                                     Operator should configure AA or accept
#                                     cost-only routing.
# Both fall back to cheapest of the eligible set; differentiating in the UI
# tells the operator which knob to turn.
_SCORING_SOURCE_LABELS = {
    "balanced": "AA quality + catalog cost (50/50 normalized)",
    "balanced-cheapest-fallback": "AA covers no eligible models — fell back to cheapest",
    "balanced-no-data-fallback": "no AA quality data configured — fell back to cheapest",
    "fastest": "AA TPS + AA TTFT (50/50 normalized)",
    "fastest-cheapest-fallback": "AA covers no eligible models on TPS+TTFT — fell back to cheapest",
    "fastest-no-data-fallback": "no AA latency data configured — fell back to cheapest",
    "quality": "AA Intelligence Index + manual overrides",
    "quality-cost-fallback": "no AA quality data — using cost-as-quality proxy (legacy)",
    "cheapest": "blended cost (0.3 input + 0.7 output)",
}


@router.get("/auto-preview")
async def quality_auto_preview(
    needs: str | None = Query(
        None,
        description=(
            "Comma-separated capability requirements: 'tools', 'vision', "
            "'json_mode'. Empty for plain chat."
        ),
    ),
    strategy: str | None = Query(
        None,
        description=(
            "Override the workspace's active strategy for this preview only. "
            "Lets verification curl/tests compare all four strategies "
            "without flipping the persisted routing config. Dashboard does "
            "NOT pass this — it relies on the workspace strategy as the "
            "authoritative source to avoid race conditions during initial load."
        ),
    ),
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Show what model `model='auto'` would resolve to right now under the
    workspace's active strategy (or the `?strategy=` override, if given).

    Returns the same scoring breakdown the ranker computed, so the
    dashboard renders exactly the numbers that drove the decision (no
    DRY drift from re-implementing normalize / weight in the route).
    """
    needs_set: set[str] = (
        {n.strip() for n in needs.split(",") if n.strip()} if needs else set()
    )

    client = await router_cache.get_router(db)
    raw_strategy = getattr(client, "strategy", None)
    workspace_strategy = (
        raw_strategy if isinstance(raw_strategy, str) and raw_strategy else "balanced"
    )
    if strategy and strategy in _VALID_STRATEGIES:
        effective_strategy = strategy
    else:
        effective_strategy = workspace_strategy

    raw_preferred = getattr(client, "preferred_models", None)
    preferred_models = raw_preferred if isinstance(raw_preferred, list) else []

    deployable: set[str] = {
        d.model_name for d in getattr(client, "_deployments", []) or []
    }

    quality_scores: dict[str, float] | None = None
    tps_scores: dict[str, float] | None = None
    ttft_scores: dict[str, float] | None = None
    if effective_strategy in ("quality", "balanced", "fastest"):
        metrics = await resolve_model_metrics(
            db=db, workspace_id=str(kc.workspace_id)
        )
        quality_scores = metrics.quality_scores
        tps_scores = metrics.tps_scores
        ttft_scores = metrics.ttft_scores

    candidates, scoring = choose_auto_model(
        needs=needs_set,
        deployable=deployable,
        candidates=CATALOG,
        strategy=effective_strategy,
        preferred_models=preferred_models,
        allowlist=kc.model_allowlist,
        quality_scores=quality_scores,
        tps_scores=tps_scores,
        ttft_scores=ttft_scores,
    )

    primary = candidates[0] if candidates else None
    primary_model = CATALOG_BY_ID.get(primary) if primary else None
    primary_detail = scoring.get(primary) if primary else None

    # scoring_source: distinguish "ran the strategy as designed" vs
    # "fell back to cheapest because the data wasn't there". Helps the
    # operator interpret a primary that doesn't match their strategy
    # selection (and could indicate a missing AA key vs a too-narrow
    # allowlist that excludes everything AA covers).
    if effective_strategy == "balanced":
        if (primary_detail and primary_detail.breakdown
                and "quality" in primary_detail.breakdown):
            source_key = "balanced"
        elif quality_scores:
            # AA data is configured (and possibly covers OTHER models)
            # but no eligible model in this request has it. Operator
            # likely has an allowlist that excludes covered models.
            source_key = "balanced-cheapest-fallback"
        else:
            source_key = "balanced-no-data-fallback"
    elif effective_strategy == "fastest":
        if (primary_detail and primary_detail.breakdown
                and "tps" in primary_detail.breakdown):
            source_key = "fastest"
        elif tps_scores and ttft_scores:
            source_key = "fastest-cheapest-fallback"
        else:
            source_key = "fastest-no-data-fallback"
    elif effective_strategy == "quality":
        source_key = "quality" if quality_scores else "quality-cost-fallback"
    else:
        source_key = "cheapest"

    # Serialize ScoringDetail for JSON. dataclass with frozen=True doesn't
    # JSON-encode automatically; pull fields explicitly to keep the wire
    # format under our control (no leaky internal types).
    primary_score = primary_detail.primary_score if primary_detail else None
    primary_breakdown = primary_detail.breakdown if primary_detail else None

    return {
        "strategy": effective_strategy,
        "workspace_strategy": workspace_strategy,
        "strategy_overridden": effective_strategy != workspace_strategy,
        "litellm_routing_strategy": litellm_routing_strategy(effective_strategy),
        "needs": sorted(needs_set),
        "preferred_models": preferred_models,
        "deployable_count": len(deployable),
        "primary": primary,
        "primary_score": primary_score,
        "primary_score_breakdown": primary_breakdown,
        "primary_blended_cost": (
            _blended_cost(primary_model) if primary_model else None
        ),
        "fallbacks": candidates[1:] if len(candidates) > 1 else [],
        "fallbacks_count": max(0, len(candidates) - 1),
        "scoring_source": _SCORING_SOURCE_LABELS.get(source_key, source_key),
    }


# ── Manual overrides CRUD ─────────────────────────────────────────────


class OverrideBody(BaseModel):
    """Request shape for PUT /v1/quality/overrides/{model_id}."""

    score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Operator-assigned quality score on the same 0-100 scale "
                    "as AA's Intelligence Index. Higher is better.",
    )
    note: str | None = Field(
        None, max_length=2000,
        description="Free-form rationale for the override; surfaced in the "
                    "dashboard so future operators understand the reasoning.",
    )


def _serialize_override(row: QualityScoreOverride) -> dict:
    return {
        "model_id": row.model_id,
        "score": row.score,
        "note": row.note,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


class BulkOverrideBody(BaseModel):
    """Bulk set/clear of manual scores in one round trip.

    TPS / TTFT / pricing are AA-derived and intentionally unreachable from
    this endpoint: bulk edits touch only the operator's manual scores.
    """

    model_ids: list[str] = Field(
        ..., min_length=1, max_length=500,
        description="Catalog model ids to apply the action to.",
    )
    action: str = Field(
        "set", pattern="^(set|clear)$",
        description="'set' applies `score` to every id; 'clear' removes overrides.",
    )
    score: float | None = Field(
        None, ge=0.0, le=100.0,
        description="Required for action='set'; ignored for 'clear'.",
    )
    note: str | None = Field(None, max_length=2000)


@router.post("/overrides/bulk")
async def bulk_overrides(
    body: BulkOverrideBody = Body(...),
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Apply one score override to many models, or clear many overrides.

    Unknown ids are skipped and reported instead of failing the batch: an
    operator pasting a list shouldn't lose the whole operation to one stale
    id. Same-cache invalidation rules as the single PUT apply.

    Set is implemented as the same merge-then-update retry as the single
    override PUT, batched per id.
    """
    if body.action == "set" and body.score is None:
        raise HTTPException(
            status_code=422,
            detail="action='set' requires a score between 0 and 100.",
        )
    ids: list[str] = list(dict.fromkeys(i.strip() for i in body.model_ids if i.strip()))
    if not ids:
        raise HTTPException(status_code=422, detail="model_ids must not be empty.")
    workspace_id = str(kc.workspace_id)

    unknown = [mid for mid in ids if mid not in CATALOG_BY_ID]
    valid = [mid for mid in ids if mid in CATALOG_BY_ID]

    set_count = cleared = 0
    if body.action == "clear":
        if valid:
            result = await db.execute(
                delete(QualityScoreOverride).where(
                    QualityScoreOverride.workspace_id == workspace_id,
                    QualityScoreOverride.model_id.in_(valid),
                )
            )
            cleared = result.rowcount or 0
            await db.commit()
    else:
        for mid in valid:
            try:
                await db.merge(QualityScoreOverride(
                    workspace_id=workspace_id,
                    model_id=mid,
                    score=body.score,
                    note=body.note,
                ))
                await db.commit()
                set_count += 1
            except IntegrityError:
                # Concurrent writer inserted first; force the UPDATE path.
                await db.rollback()
                await db.execute(
                    update(QualityScoreOverride)
                    .where(
                        QualityScoreOverride.workspace_id == workspace_id,
                        QualityScoreOverride.model_id == mid,
                    )
                    .values(score=body.score, note=body.note)
                )
                await db.commit()
                set_count += 1

    if valid:
        await broadcast_metrics_cache_invalidation(workspace_id)
    return {"set": set_count, "cleared": cleared, "unknown_model_ids": unknown}


@router.get("/overrides")
async def list_overrides(
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(QualityScoreOverride).where(
                QualityScoreOverride.workspace_id == str(kc.workspace_id)
            )
        )
    ).scalars().all()
    return {"overrides": [_serialize_override(r) for r in rows]}


@router.put("/overrides/{model_id}")
async def upsert_override(
    model_id: str,
    body: OverrideBody = Body(...),
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update an override. Idempotent on (workspace, model_id).

    `session.merge()` is select-then-write under the hood, so two
    concurrent PUTs for the same (workspace, model) can both observe
    "row not present" and both attempt INSERT — the loser gets an
    IntegrityError. We retry once: on the retry, the row is guaranteed
    to exist, so merge() takes the UPDATE path and succeeds.

    A single retry is enough because the failure window is bounded by
    the duration of a single SELECT+INSERT — a second concurrent writer
    would have already committed by the time we re-enter.
    """
    if model_id not in CATALOG_BY_ID:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Model '{model_id}' is not in the catalog. Overrides can only "
                "be set for models the router knows about."
            ),
        )

    workspace_id = str(kc.workspace_id)

    async def _do_merge() -> QualityScoreOverride:
        row = await db.merge(QualityScoreOverride(
            workspace_id=workspace_id,
            model_id=model_id,
            score=body.score,
            note=body.note,
        ))
        await db.commit()
        await db.refresh(row)
        return row

    try:
        row = await _do_merge()
    except IntegrityError:
        # Concurrent writer beat us to the INSERT. Roll back the failed
        # transaction, then issue a direct UPDATE — the row is guaranteed
        # to exist now (the other writer committed it). UPDATE is
        # unconditionally safe even if their value is now ours; PUT
        # semantics say last-writer-wins anyway.
        await db.rollback()
        await db.execute(
            update(QualityScoreOverride)
            .where(
                QualityScoreOverride.workspace_id == workspace_id,
                QualityScoreOverride.model_id == model_id,
            )
            .values(score=body.score, note=body.note)
        )
        await db.commit()
        row = (
            await db.execute(
                select(QualityScoreOverride).where(
                    QualityScoreOverride.workspace_id == workspace_id,
                    QualityScoreOverride.model_id == model_id,
                )
            )
        ).scalar_one()
    # Drop the resolver cache so balanced + quality routing see the new
    # override on the very next request (otherwise stale up to 60s TTL).
    await broadcast_metrics_cache_invalidation(workspace_id)
    return _serialize_override(row)


@router.delete("/overrides/{model_id}", status_code=204)
async def delete_override(
    model_id: str,
    kc: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an override. Returns 204 even if the override didn't exist —
    the operator's intent ('no override on this model') is satisfied either
    way, no need to surface the distinction."""
    workspace_id = str(kc.workspace_id)
    await db.execute(
        delete(QualityScoreOverride).where(
            QualityScoreOverride.workspace_id == workspace_id,
            QualityScoreOverride.model_id == model_id,
        )
    )
    await db.commit()
    await broadcast_metrics_cache_invalidation(workspace_id)
