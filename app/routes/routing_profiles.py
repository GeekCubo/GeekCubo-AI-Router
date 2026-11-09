"""Routing profiles API — CRUD, export/import, default selection.

The built-in `auto` profile is represented by `routing_config` and is served
read-only here, so it always appears in listings (first, and undeletable)
without needing a database row that could drift from the real config.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache_invalidation_bus
from app.deps import get_admin_context, get_db
from app.routing_policy import STRATEGY_LABELS, normalize_policy
from app.routing_profiles import (
    AUTO_LABEL,
    AUTO_SLUG,
    ProfileError,
    default_profile,
    ensure_single_default,
    find_profile,
    live_profiles,
    normalize_profile_policy,
    normalize_slug,
    profile_ext,
    slugify,
    tombstoned_slugs,
)
from app.seed import DEFAULT_WORKSPACE_ID
from packages.db.models.request_log import RequestLog
from packages.db.models.routing_config import RoutingConfig
from packages.db.models.routing_profile import RoutingProfile, RoutingProfileTombstone

router = APIRouter(prefix="/v1/routing-profiles", tags=["routing profiles"])

VALID_STRATEGIES = {"balanced", "cheapest", "fastest", "quality", "adaptive", "adaptive_gated"}


class ProfileIn(BaseModel):
    display_name: str
    slug: str | None = None
    description: str | None = None
    strategy: str = "balanced"
    policy: dict | None = None
    profile: dict | None = None
    is_enabled: bool = True
    allow_slug_reuse: bool = False


class ProfilePatch(BaseModel):
    display_name: str | None = None
    description: str | None = None
    strategy: str | None = None
    policy: dict | None = None
    profile: dict | None = None
    is_enabled: bool | None = None
    # Renaming the slug is a breaking change for clients; require explicit
    # confirmation rather than letting it happen as a side effect of a PUT.
    slug: str | None = None
    confirm_slug_change: bool = False


class DuplicateIn(BaseModel):
    display_name: str | None = None
    slug: str | None = None


def _auto_row(payload_routing: RoutingConfig | None) -> dict:
    policy = normalize_policy(payload_routing.policy if payload_routing else None)
    return {
        "id": "auto",
        "slug": AUTO_SLUG,
        "display_name": AUTO_LABEL,
        "description": "Built-in default routing. Cannot be edited or deleted.",
        "strategy": payload_routing.strategy if payload_routing else "balanced",
        "strategy_label": STRATEGY_LABELS.get(
            payload_routing.strategy if payload_routing else "balanced", "Balanced"
        ),
        "policy": policy,
        "profile": profile_ext(policy),
        "is_enabled": True,
        "is_default": False,
        "is_builtin": True,
        "model_count": 0,
        "last_used_at": None,
        "requests_30d": 0,
    }


async def _routing_row(db: AsyncSession) -> RoutingConfig | None:
    return (
        await db.execute(
            select(RoutingConfig).where(
                RoutingConfig.workspace_id == DEFAULT_WORKSPACE_ID,
                RoutingConfig.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()


async def _usage(db: AsyncSession, slugs: list[str]) -> dict[str, tuple[int, str | None]]:
    """Requests in the last 30 days per profile slug, plus the last timestamp.

    Counted from the request log (which records the requested model), so this
    is measured data, never an estimate.
    """
    if not slugs:
        return {}
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        await db.execute(
            select(
                RequestLog.model_requested,
                RequestLog.created_at,
            ).where(
                RequestLog.is_deleted == 0,
                RequestLog.created_at >= since,
                RequestLog.model_requested.in_(slugs),
            )
        )
    ).all()
    out: dict[str, tuple[int, str | None]] = {}
    for model, created in rows:
        n, last = out.get(model, (0, None))
        iso = created.isoformat() if created else None
        out[model] = (n + 1, iso if (iso and (last is None or iso > last)) else last)
    return out


def _profile_out(
    row: RoutingProfile,
    *,
    usage: dict[str, tuple[int, str | None]],
    default_id: str | None,
) -> dict:
    policy = normalize_policy(row.policy)
    # normalize_policy drops keys it does not own, including "profile" — read
    # the extensions from the stored row, or they would always look default.
    ext = profile_ext(row.policy)
    policy["profile"] = ext
    n, last = usage.get(row.slug, (0, None))
    model_count = len(policy["pools"]["mundane"]) + len(policy["pools"]["hard"]) + len(
        policy["fallback"]["models"]
    )
    return {
        "id": row.id,
        "slug": row.slug,
        "display_name": row.display_name,
        "description": row.description,
        "strategy": row.strategy,
        "strategy_label": STRATEGY_LABELS.get(row.strategy, row.strategy.title()),
        "policy": policy,
        "profile": ext,
        "is_enabled": bool(row.is_enabled),
        "is_default": bool(row.is_default) or row.id == default_id,
        "is_builtin": False,
        "model_count": model_count,
        "last_used_at": last,
        "requests_30d": n,
    }


async def _check_slug_available(
    db: AsyncSession,
    slug: str,
    *,
    allow_reuse: bool,
    exclude_id: str | None = None,
) -> None:
    """A slug may not shadow a model id, another profile, or a tombstone."""
    existing = await find_profile(db, DEFAULT_WORKSPACE_ID, slug)
    if existing and existing.id != exclude_id:
        raise HTTPException(
            status_code=409,
            detail=f"A routing profile with identifier '{slug}' already exists",
        )
    if allow_reuse:
        return
    if slug in await tombstoned_slugs(db, DEFAULT_WORKSPACE_ID):
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{slug}' was used by a deleted profile. Clients may still send "
                "it. Pass allow_slug_reuse=true to deliberately take it over."
            ),
        )
    # A profile slug is sent in the same `model` field as a model id, so a
    # collision would make routing ambiguous.
    from app.custom_providers import merged_catalog

    known = {m.id for m in await merged_catalog(db, eligible_only=False)}
    if slug in known:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{slug}' is a registered model id; using it as a profile "
                "identifier would make model routing ambiguous"
            ),
        )


@router.get("")
async def list_profiles(
    q: str = Query("", max_length=200),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = await live_profiles(db, DEFAULT_WORKSPACE_ID)
    usage = await _usage(db, [r.slug for r in rows])
    default = await default_profile(db, DEFAULT_WORKSPACE_ID)
    default_id = default.id if default else None

    items = [_auto_row(await _routing_row(db))]
    items += [
        _profile_out(r, usage=usage, default_id=default_id)
        for r in rows
    ]
    needle = (q or "").strip().lower()
    if needle:
        items = [
            i
            for i in items
            if needle in i["display_name"].lower() or needle in i["slug"].lower()
        ]
    return {
        "profiles": items,
        "count": len(items),
        "strategies": [
            {"id": k, "label": v} for k, v in STRATEGY_LABELS.items()
        ],
        "reserved_slugs": sorted({AUTO_SLUG}),
    }


@router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if profile_id == AUTO_SLUG:
        return _auto_row(await _routing_row(db))
    row = (
        await db.execute(
            select(RoutingProfile).where(
                RoutingProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                RoutingProfile.id == profile_id,
                RoutingProfile.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    usage = await _usage(db, [row.slug])
    default = await default_profile(db, DEFAULT_WORKSPACE_ID)
    return _profile_out(row, usage=usage, default_id=default.id if default else None)


@router.post("", status_code=201)
async def create_profile(
    body: ProfileIn,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    name = (body.display_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="display_name cannot be empty")
    if body.strategy not in VALID_STRATEGIES:
        raise HTTPException(
            status_code=422, detail=f"strategy must be one of {sorted(VALID_STRATEGIES)}"
        )
    try:
        slug = normalize_slug(body.slug or slugify(name))
        policy = normalize_profile_policy(body.policy, body.profile)
    except ProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await _check_slug_available(db, slug, allow_reuse=body.allow_slug_reuse)

    row = RoutingProfile(
        workspace_id=DEFAULT_WORKSPACE_ID,
        slug=slug,
        display_name=name,
        description=(body.description or "").strip() or None,
        strategy=body.strategy,
        policy=policy,
        is_enabled=body.is_enabled,
        is_default=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    return _profile_out(row, usage={}, default_id=None)


@router.put("/{profile_id}")
async def update_profile(
    profile_id: str,
    body: ProfilePatch,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if profile_id == AUTO_SLUG:
        raise HTTPException(
            status_code=403,
            detail=(
                "The built-in 'auto' profile cannot be edited here. Change it "
                "on the Routing page, which owns the default configuration."
            ),
        )
    row = (
        await db.execute(
            select(RoutingProfile).where(
                RoutingProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                RoutingProfile.id == profile_id,
                RoutingProfile.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Routing profile not found")

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")
        row.display_name = name
    if body.description is not None:
        row.description = body.description.strip() or None
    if body.strategy is not None:
        if body.strategy not in VALID_STRATEGIES:
            raise HTTPException(
                status_code=422,
                detail=f"strategy must be one of {sorted(VALID_STRATEGIES)}",
            )
        row.strategy = body.strategy
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.policy is not None or body.profile is not None:
        try:
            base = body.policy if body.policy is not None else (row.policy or {})
            carried = (row.policy or {}).get("profile")
            merged = normalize_profile_policy(
                base, body.profile if body.profile is not None else carried
            )
        except ProfileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.policy = merged
    if body.slug is not None:
        try:
            new_slug = normalize_slug(body.slug)
        except ProfileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if new_slug != row.slug:
            if not body.confirm_slug_change:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Changing the API identifier breaks every client using "
                        f"'{row.slug}'. Resend with confirm_slug_change=true to "
                        "proceed."
                    ),
                )
            await _check_slug_available(db, new_slug, allow_reuse=False, exclude_id=row.id)
            db.add(
                RoutingProfileTombstone(
                    workspace_id=DEFAULT_WORKSPACE_ID,
                    slug=row.slug,
                    display_name=row.display_name,
                )
            )
            row.slug = new_slug

    await db.commit()
    await db.refresh(row)
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    usage = await _usage(db, [row.slug])
    default = await default_profile(db, DEFAULT_WORKSPACE_ID)
    return _profile_out(row, usage=usage, default_id=default.id if default else None)


@router.post("/{profile_id}/duplicate", status_code=201)
async def duplicate_profile(
    profile_id: str,
    body: DuplicateIn,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if profile_id == AUTO_SLUG:
        routing = await _routing_row(db)
        base_strategy = routing.strategy if routing else "balanced"
        base_policy = normalize_policy(routing.policy if routing else None)
        base_name = AUTO_LABEL
        base_desc = None
    else:
        src = (
            await db.execute(
                select(RoutingProfile).where(
                    RoutingProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                    RoutingProfile.id == profile_id,
                    RoutingProfile.is_deleted == 0,
                )
            )
        ).scalar_one_or_none()
        if src is None:
            raise HTTPException(status_code=404, detail="Routing profile not found")
        base_strategy = src.strategy
        base_policy = normalize_profile_policy(src.policy)
        base_name, base_desc = src.display_name, src.description

    name = (body.display_name or f"{base_name} copy").strip()
    try:
        slug = normalize_slug(body.slug or slugify(name))
    except ProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await _check_slug_available(db, slug, allow_reuse=False)

    row = RoutingProfile(
        workspace_id=DEFAULT_WORKSPACE_ID,
        slug=slug,
        display_name=name,
        description=base_desc,
        strategy=base_strategy,
        policy=base_policy,
        is_enabled=True,
        is_default=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    return _profile_out(row, usage={}, default_id=None)


@router.post("/{profile_id}/default")
async def set_default_profile(
    profile_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if profile_id == AUTO_SLUG:
        # auto is the implicit default when no profile claims it.
        await ensure_single_default(db, DEFAULT_WORKSPACE_ID, keep_id=None)
        await db.commit()
        await cache_invalidation_bus.broadcast_router_cache_invalidation()
        return {"is_default": AUTO_SLUG, "slug": AUTO_SLUG}
    row = await find_profile(db, DEFAULT_WORKSPACE_ID, profile_id)
    if row is None:
        row = (
            await db.execute(
                select(RoutingProfile).where(
                    RoutingProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                    RoutingProfile.id == profile_id,
                    RoutingProfile.is_deleted == 0,
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    await ensure_single_default(db, DEFAULT_WORKSPACE_ID, keep_id=row.id)
    await db.commit()
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    return {"is_default": row.id, "slug": row.slug}


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if profile_id == AUTO_SLUG:
        raise HTTPException(
            status_code=403, detail="The built-in 'auto' profile cannot be deleted"
        )
    row = (
        await db.execute(
            select(RoutingProfile).where(
                RoutingProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                RoutingProfile.id == profile_id,
                RoutingProfile.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Routing profile not found")

    was_default = bool(row.is_default)
    # Soft delete + tombstone: providers, credentials, models and the request
    # log are untouched, and the slug is not silently reusable.
    row.is_deleted = 1
    row.is_default = False
    db.add(
        RoutingProfileTombstone(
            workspace_id=DEFAULT_WORKSPACE_ID,
            slug=row.slug,
            display_name=row.display_name,
        )
    )
    await db.commit()
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    return {
        "deleted": row.slug,
        "default_reassigned_to": AUTO_SLUG if was_default else None,
    }


@router.get("/{profile_id}/export")
async def export_profile(
    profile_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Portable JSON. Never contains credentials or provider secrets."""
    data = await get_profile(profile_id, _kc, db)
    return {
        "geekcubo_routing_profile": 1,
        "slug": data["slug"],
        "display_name": data["display_name"],
        "description": data["description"],
        "strategy": data["strategy"],
        "policy": data["policy"],
        "is_enabled": data["is_enabled"],
    }


@router.post("/import", status_code=201)
async def import_profile(
    body: dict,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import a profile exported by another GeekCubo install.

    Model ids in pools are validated against this install's catalog; unknown
    ids are reported rather than silently kept, so an imported profile never
    claims to route to something that does not exist here.
    """
    if not isinstance(body, dict) or "geekcubo_routing_profile" not in body:
        raise HTTPException(
            status_code=422,
            detail="Not a GeekCubo routing profile export (missing geekcubo_routing_profile)",
        )
    strategy = body.get("strategy") or "balanced"
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(status_code=422, detail=f"Unknown strategy '{strategy}'")
    name = (body.get("display_name") or "").strip() or "Imported profile"
    try:
        slug = normalize_slug(body.get("slug") or slugify(name))
        policy = normalize_profile_policy(body.get("policy"))
    except ProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await _check_slug_available(db, slug, allow_reuse=False)

    from app.custom_providers import merged_catalog

    known = {m.id for m in await merged_catalog(db, eligible_only=False)}
    referenced: set[str] = set()
    for ids in policy["pools"].values():
        referenced |= set(ids)
    referenced |= set(policy["fallback"]["models"])
    unknown = sorted(referenced - known)

    row = RoutingProfile(
        workspace_id=DEFAULT_WORKSPACE_ID,
        slug=slug,
        display_name=name,
        description=(body.get("description") or "").strip() or None,
        strategy=strategy,
        policy=policy,
        is_enabled=bool(body.get("is_enabled", True)),
        is_default=False,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
    out = _profile_out(row, usage={}, default_id=None)
    out["unknown_models"] = unknown
    return out
