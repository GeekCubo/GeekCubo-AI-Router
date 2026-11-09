"""Analytics routes — recent requests, spend, latency, savings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app._time_util import iso_utc
from app.deps import get_admin_context, get_db
from packages.db.models.request_log import RequestLog

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((len(s) - 1) * pct))))
    return s[idx]


@router.get("/recent")
async def recent_requests(
    limit: int = Query(100, ge=1, le=1000),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(RequestLog)
            .where(RequestLog.is_deleted == 0)
            .order_by(desc(RequestLog.created_at))
            .limit(limit)
        )
    ).scalars().all()

    items = [
        {
            "trace_id": r.trace_id,
            "model_requested": r.model_requested,
            "model_resolved": r.model_resolved,
            "provider": r.provider,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_microcents": r.cost_microcents,
            "latency_ms": r.latency_ms,
            "status_code": r.status_code,
            "error_type": r.error_type,
            "created_at": iso_utc(r.created_at),
            # Auto decision record (None for pinned requests / older rows).
            "routing_strategy": r.routing_strategy,
            "routed_model": r.routed_model,
            "routing_tier": r.routing_tier,
            "routing_reason": r.routing_reason,
            "candidate_count": r.candidate_count,
            "escalated": r.escalated,
            "fallback_used": r.fallback_used,
            "attempt_count": r.attempt_count,
            "attempt_errors": r.attempt_errors,
            # Explicit, so a paid request with no known price is never shown
            # as $0: successful, consumed tokens, but no cost recorded.
            "cost_unknown": bool(
                r.status_code < 400
                and (r.cost_microcents or 0) == 0
                and ((r.input_tokens or 0) + (r.output_tokens or 0)) > 0
                and r.provider != "cache"
            ),
        }
        for r in rows
    ]
    return {"count": len(items), "items": items}


@router.get("/routing")
async def routing_breakdown(
    days: int = Query(7, ge=1, le=90),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Routing observability from the request log — no invented numbers.

    Every figure is a count or sum over recorded rows in the window. Costs
    include only rows with a recorded cost; rows that consumed tokens but
    recorded none are counted separately as `unknown_cost_requests`.
    """
    from sqlalchemy import case

    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = (RequestLog.created_at >= since, RequestLog.is_deleted == 0)
    is_auto = RequestLog.model_requested == "auto"

    totals = (await db.execute(
        select(
            func.count().label("n"),
            func.sum(case((is_auto, 1), else_=0)).label("auto"),
            func.sum(case((RequestLog.fallback_used.is_(True), 1), else_=0)).label("fallback"),
            func.sum(case((RequestLog.escalated.is_(True), 1), else_=0)).label("escalated"),
            func.sum(case((RequestLog.status_code >= 400, 1), else_=0)).label("errors"),
            func.sum(case((
                (RequestLog.status_code < 400)
                & (RequestLog.cost_microcents == 0)
                & ((RequestLog.input_tokens + RequestLog.output_tokens) > 0)
                & (RequestLog.provider != "cache"),
                1), else_=0)).label("unknown_cost"),
            func.sum(RequestLog.cost_microcents).label("cost"),
        ).where(*base)
    )).one()

    def _group(col):
        return select(
            col.label("key"),
            func.count().label("n"),
            func.sum(RequestLog.cost_microcents).label("cost"),
            func.avg(RequestLog.latency_ms).label("lat"),
        ).where(*base).group_by(col)

    by_strategy = [
        {"strategy": r.key, "requests": int(r.n), "cost_microcents": int(r.cost or 0)}
        for r in (await db.execute(_group(RequestLog.routing_strategy).where(is_auto))).all()
    ]
    by_tier = [
        {"tier": r.key or "untiered", "requests": int(r.n),
         "cost_microcents": int(r.cost or 0), "avg_latency_ms": int(r.lat or 0)}
        for r in (await db.execute(_group(RequestLog.routing_tier).where(is_auto))).all()
    ]
    model_col = func.coalesce(RequestLog.routed_model, RequestLog.model_resolved)
    by_model = sorted(
        (
            {"model": r.key, "requests": int(r.n), "cost_microcents": int(r.cost or 0),
             "avg_latency_ms": int(r.lat or 0)}
            for r in (await db.execute(_group(model_col))).all()
        ),
        key=lambda x: -x["requests"],
    )[:25]

    day_col = func.date(RequestLog.created_at)
    timeline = [
        {"day": str(r.day), "requests": int(r.n), "auto": int(r.auto or 0),
         "errors": int(r.errors or 0)}
        for r in (await db.execute(
            select(
                day_col.label("day"),
                func.count().label("n"),
                func.sum(case((is_auto, 1), else_=0)).label("auto"),
                func.sum(case((RequestLog.status_code >= 400, 1), else_=0)).label("errors"),
            ).where(*base).group_by(day_col).order_by(day_col)
        )).all()
    ]

    # Requests that asked for tools but failed upstream — the capability
    # failures worth surfacing. Recorded via error_type on the row.
    tool_failures = (await db.execute(
        select(func.count()).where(
            *base,
            RequestLog.status_code >= 400,
            RequestLog.routing_reason.like("%tools%"),
        )
    )).scalar_one()

    # Requests by routing id: "auto", a profile slug, or a pinned model id.
    # Read from model_requested, which preserves what the client sent.
    by_requested = sorted(
        (
            {"requested": r.key, "requests": int(r.n),
             "cost_microcents": int(r.cost or 0), "avg_latency_ms": int(r.lat or 0)}
            for r in (await db.execute(
                _group(RequestLog.model_requested).where(
                    func.length(RequestLog.model_requested) < 80
                )
            )).all()
        ),
        key=lambda x: -x["requests"],
    )[:25]

    # Fallback success: of the requests that needed a fallback attempt, how
    # many still succeeded. Both numbers come from recorded attempts.
    fb = (await db.execute(
        select(
            func.count().label("n"),
            func.sum(case((RequestLog.status_code < 400, 1), else_=0)).label("ok"),
            func.sum(RequestLog.attempt_count).label("attempts"),
            func.avg(RequestLog.attempt_count).label("avg_attempts"),
        ).where(*base, RequestLog.attempt_count > 0)
    )).one()
    fallback_stats = {
        "requests_with_attempts": int(fb.n or 0),
        "succeeded": int(fb.ok or 0),
        "success_rate": (round(int(fb.ok or 0) / int(fb.n), 3) if fb.n else None),
        "total_attempts": int(fb.attempts or 0),
        "avg_attempts": round(float(fb.avg_attempts), 2) if fb.avg_attempts else None,
    }

    # Errors grouped by cause, from the recorded error_type.
    by_error = sorted(
        (
            {"error_type": r.key or "unknown", "requests": int(r.n)}
            for r in (await db.execute(
                select(func.count().label("n"), RequestLog.error_type.label("key"))
                .where(*base, RequestLog.status_code >= 400)
                .group_by(RequestLog.error_type)
            )).all()
        ),
        key=lambda x: -x["requests"],
    )[:15]

    return {
        "days": days,
        "requests": int(totals.n or 0),
        "auto_requests": int(totals.auto or 0),
        "fallback_requests": int(totals.fallback or 0),
        "escalated_requests": int(totals.escalated or 0),
        "error_requests": int(totals.errors or 0),
        "unknown_cost_requests": int(totals.unknown_cost or 0),
        "tool_route_failures": int(tool_failures or 0),
        "cost_microcents": int(totals.cost or 0),
        "by_strategy": by_strategy,
        "by_tier": by_tier,
        "by_model": by_model,
        "by_requested": by_requested,
        "by_error": by_error,
        "fallback_stats": fallback_stats,
        "timeline": timeline,
    }


@router.get("/baseline-comparison")
async def baseline_comparison(
    baseline: str = Query(..., min_length=1, max_length=200),
    days: int = Query(30, ge=1, le=90),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actual routed cost vs. the same measured tokens at `baseline`'s price.

    An ESTIMATE: it re-prices this installation's recorded token counts at the
    baseline model's configured price. It is not an invoice, and it cannot
    account for a baseline model's prompt caching, batch discounts, reasoning
    tokens or negotiated rates. Only models with a configured or catalog price
    can be used as a baseline, and the two numbers are labelled as such.
    """
    from app.custom_providers import merged_catalog_by_id

    catalog = await merged_catalog_by_id(db, eligible_only=False)
    model = catalog.get(baseline)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown model '{baseline}'")
    in_price = getattr(model, "input_cost_per_token", 0.0) or 0.0
    out_price = getattr(model, "output_cost_per_token", 0.0) or 0.0
    if not in_price and not out_price:
        raise HTTPException(
            status_code=422,
            detail=f"'{baseline}' has no configured price, so it cannot be a baseline",
        )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    row = (await db.execute(
        select(
            func.count().label("n"),
            func.sum(RequestLog.input_tokens).label("tin"),
            func.sum(RequestLog.output_tokens).label("tout"),
            func.sum(RequestLog.cost_microcents).label("actual"),
        ).where(
            RequestLog.created_at >= since,
            RequestLog.is_deleted == 0,
            RequestLog.status_code < 400,
            RequestLog.provider != "cache",
        )
    )).one()
    tin = int(row.tin or 0)
    tout = int(row.tout or 0)
    estimated_usd = tin * in_price + tout * out_price
    estimated_microcents = int(round(estimated_usd * 1_000_000))
    actual = int(row.actual or 0)
    return {
        "baseline_model": baseline,
        "days": days,
        "requests": int(row.n or 0),
        "input_tokens": tin,
        "output_tokens": tout,
        "actual_microcents": actual,
        "baseline_estimated_microcents": estimated_microcents,
        "difference_microcents": estimated_microcents - actual,
        "is_estimate": True,
        "note": (
            "Estimate only: recorded token counts re-priced at the baseline "
            "model's configured rates. Ignores caching, batch discounts, "
            "reasoning tokens and any negotiated pricing."
        ),
    }


@router.get("/spend")
async def spend_by_model(
    days: int = Query(7, ge=1, le=365),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                RequestLog.model_resolved,
                func.sum(RequestLog.cost_microcents).label("cost"),
                func.count().label("count"),
            )
            .where(RequestLog.is_deleted == 0, RequestLog.created_at >= cutoff)
            .group_by(RequestLog.model_resolved)
            .order_by(desc("cost"))
        )
    ).all()

    by_model = [
        {"model": model, "cost_microcents": int(cost or 0), "request_count": count}
        for model, cost, count in rows
    ]
    total = sum(row["cost_microcents"] for row in by_model)
    return {"total_microcents": total, "by_model": by_model, "days": days}


@router.get("/latency")
async def latency_by_provider(
    days: int = Query(7, ge=1, le=365),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(RequestLog.provider, RequestLog.latency_ms)
            .where(RequestLog.is_deleted == 0, RequestLog.created_at >= cutoff)
        )
    ).all()

    bucket: dict[str, list[int]] = {}
    for prov, lat in rows:
        bucket.setdefault(prov, []).append(int(lat))

    result = [
        {
            "provider": prov,
            "request_count": len(samples),
            "p50_ms": _percentile(samples, 0.5),
            "p99_ms": _percentile(samples, 0.99),
        }
        for prov, samples in bucket.items()
    ]
    result.sort(key=lambda r: -r["request_count"])
    return {"by_provider": result, "days": days}


@router.get("/savings")
async def savings_vs_baseline(
    days: int = Query(7, ge=1, le=365),
    baseline: str = Query("gpt-4o"),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What would these requests have cost on `baseline` instead?

    Powers the dashboard's "you saved $X by routing" tile. The baseline
    must be a known catalog model (default: gpt-4o).

    """
    from packages.litellm_adapter.catalog import CATALOG_BY_ID

    baseline_model = CATALOG_BY_ID.get(baseline)
    if baseline_model is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown baseline model: {baseline}",
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                RequestLog.input_tokens,
                RequestLog.output_tokens,
                RequestLog.cost_microcents,
                RequestLog.provider,
            )
            .where(
                RequestLog.is_deleted == 0,
                RequestLog.created_at >= cutoff,
                RequestLog.status_code < 400,
            )
        )
    ).all()

    # A request that consumed tokens but recorded no cost has an UNKNOWN
    # price, not a zero one. Counting it as free would claim savings with no
    # valid comparison, so it is excluded from both sides and reported.
    def _unknown(i, o, c, p) -> bool:
        return (c or 0) == 0 and ((i or 0) + (o or 0)) > 0 and p != "cache"

    unknown_count = sum(1 for r in rows if _unknown(*r))
    rows = [r for r in rows if not _unknown(*r)]

    actual_microcents = sum(int(c or 0) for _i, _o, c, _p in rows)
    # Per-token pricing in litellm is USD/token; convert to microcents
    # (1 USD = 1,000,000 microcents).
    baseline_microcents = sum(
        int(
            (i or 0) * baseline_model.input_cost_per_token * 1_000_000
            + (o or 0) * baseline_model.output_cost_per_token * 1_000_000
        )
        for i, o, _c, _p in rows
    )
    saved = max(0, baseline_microcents - actual_microcents)
    pct = (
        round(100 * saved / baseline_microcents, 1)
        if baseline_microcents
        else 0
    )

    return {
        "baseline_model": baseline,
        "request_count": len(rows),
        "actual_microcents": actual_microcents,
        "baseline_microcents": baseline_microcents,
        "saved_microcents": saved,
        "savings_percent": pct,
        "unknown_cost_requests_excluded": unknown_count,
        "days": days,
    }
