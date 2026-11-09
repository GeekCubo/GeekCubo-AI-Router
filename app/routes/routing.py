"""Routing configuration — single row for the GeekCubo workspace.

`strategy` + `preferred_models` behave exactly as before. `policy` carries the
advanced Auto configuration (pools, gating, fallback, escalation, stickiness);
omitting it leaves the stored policy untouched, and a NULL policy means
defaults, which reproduce the pre-policy routing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache_invalidation_bus
from app.deps import get_admin_context, get_db
from app.routing_policy import (
    ADAPTIVE_MIN_SAMPLES,
    STRATEGY_LABELS,
    PolicyError,
    normalize_policy,
    pool_membership,
)
from app.seed import DEFAULT_WORKSPACE_ID
from packages.db.models.routing_config import RoutingConfig

router = APIRouter(prefix="/v1/routing", tags=["routing"])

# `fastest` predates the policy work and stays accepted for existing configs.
VALID_STRATEGIES = {"balanced", "cheapest", "fastest", "quality", "adaptive", "adaptive_gated"}


class UpdateRouting(BaseModel):
    strategy: str | None = None
    preferred_models: list[str] | None = None
    policy: dict | None = None

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STRATEGIES:
            raise ValueError(f"strategy must be one of {sorted(VALID_STRATEGIES)}")
        return v


async def _row(db: AsyncSession) -> RoutingConfig:
    row = (
        await db.execute(
            select(RoutingConfig).where(
                RoutingConfig.workspace_id == DEFAULT_WORKSPACE_ID,
                RoutingConfig.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Routing config not found")
    return row


def _referenced_ids(policy: dict) -> set[str]:
    """Every model id a policy names (pools, explicit fallback, overrides)."""
    referenced: set[str] = set()
    for ids in (policy.get("pools") or {}).values():
        referenced |= set(ids or [])
    referenced |= set((policy.get("fallback") or {}).get("models") or [])
    referenced |= {o["model"] for o in policy.get("pool_overrides") or []}
    return referenced


async def _known_ids(db: AsyncSession) -> set[str]:
    from app.custom_providers import merged_catalog

    return {m.id for m in await merged_catalog(db, eligible_only=False)}


async def _warnings(db: AsyncSession, strategy: str, policy: dict) -> list[str]:
    """Configuration problems the admin should see before traffic does."""
    from app.custom_providers import merged_catalog

    eligible = {m.id for m in await merged_catalog(db, eligible_only=True)}
    pools = pool_membership(policy)
    out: list[str] = []
    # Pool entries whose model was removed or renamed (e.g. the provider was
    # re-created under another slug). Routing already ignores them; say so,
    # so the admin can remove them instead of believing the pool is staffed.
    stale = sorted(_referenced_ids(policy) - await _known_ids(db))
    if stale:
        out.append(
            "These pool/fallback entries are no longer registered models and are "
            f"ignored by routing: {', '.join(stale)}. Remove them on the Routing page."
        )
    if strategy == "adaptive_gated":
        for name in ("mundane", "hard"):
            members = pools.get(name) or set()
            if not members:
                out.append(f"The {name} pool is empty; {name} requests will use the fallback pool.")
            elif not members & eligible:
                out.append(
                    f"No model in the {name} pool is Auto-eligible (enable Auto on its provider)."
                )
    esc = policy.get("escalation") or {}
    if esc.get("mode", "off") != "off":
        target = pools.get(esc.get("to_pool", "hard")) or set()
        if not target:
            out.append(
                f"Escalation is on but its target pool '{esc.get('to_pool', 'hard')}' is empty."
            )
    if strategy == "adaptive":
        out.append(
            f"Adaptive re-ranks only after {ADAPTIVE_MIN_SAMPLES} observed requests per "
            "model; until then it routes as Balanced."
        )
    if strategy == "cheapest":
        out.append("Cheapest optimises cost only; output quality may vary.")
    return out


def _payload(
    row: RoutingConfig, policy: dict, warnings: list[str], stale: list[str] | None = None
) -> dict:
    return {
        "strategy": row.strategy,
        "strategy_label": STRATEGY_LABELS.get(row.strategy, row.strategy.title()),
        "preferred_models": row.preferred_models or [],
        "policy": policy,
        "warnings": warnings,
        # Policy entries that no longer name a registered model. Routing
        # ignores them; the dashboard marks them so they can be removed.
        "stale_models": stale or [],
        "strategies": [
            {"id": sid, "label": label} for sid, label in STRATEGY_LABELS.items()
        ],
    }


@router.get("")
async def get_routing(
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _row(db)
    try:
        policy = normalize_policy(row.policy)
    except PolicyError:
        policy = normalize_policy(None)
    return await _respond(db, row, policy)


async def _respond(db: AsyncSession, row: RoutingConfig, policy: dict) -> dict:
    stale = sorted(_referenced_ids(policy) - await _known_ids(db))
    return _payload(row, policy, await _warnings(db, row.strategy, policy), stale)


@router.put("")
async def update_routing(
    body: UpdateRouting,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _row(db)

    if body.strategy is not None:
        row.strategy = body.strategy
    if body.preferred_models is not None:
        row.preferred_models = body.preferred_models

    if body.policy is not None:
        try:
            policy = normalize_policy(body.policy)
        except PolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # Pool/fallback members must be real registered models. Silently
        # keeping an unknown id would look like a configured pool that never
        # routes anything. Only NEWLY introduced ids are checked: an entry
        # already stored whose model was later removed (or whose provider was
        # re-created under a new slug) is reported as a warning instead.
        # Rejecting it here made every later save fail with a 422 — including
        # the save that removes it — which locked the whole policy form.
        try:
            stored = normalize_policy(row.policy)
        except PolicyError:
            stored = normalize_policy(None)
        known = await _known_ids(db)
        unknown = sorted(_referenced_ids(policy) - known - _referenced_ids(stored))
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown model id(s) in routing policy: {unknown}",
            )
        row.policy = policy
    else:
        try:
            policy = normalize_policy(row.policy)
        except PolicyError:
            policy = normalize_policy(None)

    await db.commit()
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    return await _respond(db, row, policy)

