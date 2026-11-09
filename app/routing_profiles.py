"""Custom routing profiles — CRUD helpers, slug rules and validation.

A profile is a named Auto configuration that clients select by sending its
slug as `model`. The built-in `auto` profile is NOT stored here: it maps to
`routing_config`, so existing installs and clients keep working untouched.

Design decisions worth knowing:

* **Slug vs display name.** The slug is the wire identifier and is immutable
  after creation unless the caller explicitly confirms the change (and
  accepts that clients using the old slug will break). Display names are
  free-form and can change any time.
* **No ambiguity.** A slug may not collide with `auto`, with a registered
  model id, with another live profile, or with a tombstoned slug (a deleted
  profile's identifier is not silently recycled).
* **Profiles never widen access.** Provider/model allowlists and the cost
  ceiling are enforced by the planner, and fallback candidates are filtered
  through the same restrictions, so a fallback cannot escape a profile.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.routing_policy import PolicyError, normalize_policy
from packages.db.models.routing_profile import RoutingProfile, RoutingProfileTombstone

# Identifiers clients already send, or that GeekCubo exposes as endpoints.
# A profile slug must never shadow one of these.
RESERVED_SLUGS = frozenset(
    {
        "auto",
        "models",
        "chat",
        "completions",
        "messages",
        "embeddings",
        "health",
        "routing",
        "analytics",
        "keys",
        "admin",
        "v1",
        "system",
        "default",
        "none",
        "null",
        "geek",
        "geekcubo",
    }
)

AUTO_SLUG = "auto"
AUTO_LABEL = "Auto"

# Lowercase, digits and single hyphens. No leading/trailing hyphen, max 64.
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")

# Profile-only extensions. These live in `policy["profile"]`, kept separate
# from the shared Auto policy so `normalize_policy` stays the single owner of
# the routing knobs it already validates.
DEFAULT_PROFILE_EXT = {
    # Restrict which providers this profile may use (provider display keys,
    # e.g. "apixo"). Empty = any configured provider.
    "providers": [],
    # Restrict which models this profile may use. Empty = any Auto-eligible.
    "models": [],
    # Hard ceiling on a single model's blended price per 1M tokens, in
    # micro-dollars ($/1M x 1e6). None = no ceiling.
    "max_cost_per_million_micros": None,
    # Upstream request timeout in seconds for this profile. None = global.
    "timeout_seconds": None,
    # Pinned first choice, still subject to the capability + allowlist checks.
    "preferred_model": None,
}


class ProfileError(ValueError):
    """Invalid profile input. Message is safe to show the administrator."""


def normalize_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    if not slug:
        raise ProfileError("API identifier cannot be empty")
    if not SLUG_RE.match(slug):
        raise ProfileError(
            "API identifier must be 1-64 characters: lowercase letters, digits "
            "and hyphens, and cannot start or end with a hyphen"
        )
    if slug in RESERVED_SLUGS:
        raise ProfileError(
            f"'{slug}' is reserved by GeekCubo and cannot be used as a profile identifier"
        )
    return slug


def slugify(name: str) -> str:
    """Derive a slug from a display name. May still be reserved — caller checks."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug[:64].strip("-") or "profile"


def normalize_profile_ext(raw: Any) -> dict[str, Any]:
    out = dict(DEFAULT_PROFILE_EXT)
    if raw is None:
        return out
    if not isinstance(raw, dict):
        raise ProfileError("profile settings must be an object")

    if "providers" in raw:
        out["providers"] = _str_list(raw["providers"], "providers")
    if "models" in raw:
        out["models"] = _str_list(raw["models"], "models")
    if "max_cost_per_million_micros" in raw:
        v = raw["max_cost_per_million_micros"]
        if v is None:
            out["max_cost_per_million_micros"] = None
        else:
            iv = _as_int(v, "max_cost_per_million_micros", 0, 10**12)
            out["max_cost_per_million_micros"] = iv
    if "timeout_seconds" in raw:
        v = raw["timeout_seconds"]
        out["timeout_seconds"] = (
            None if v is None else _as_int(v, "timeout_seconds", 1, 3600)
        )
    if "preferred_model" in raw:
        v = raw["preferred_model"]
        if v is None or (isinstance(v, str) and not v.strip()):
            out["preferred_model"] = None
        elif isinstance(v, str):
            out["preferred_model"] = v.strip()
        else:
            raise ProfileError("preferred_model must be a model id or null")
    return out


def normalize_profile_policy(
    policy: Any, profile: Any = None
) -> dict[str, Any]:
    """Validate a profile's stored policy: shared Auto policy + extensions.

    Explicit arguments on purpose: an earlier version accepted one dict and
    guessed whether it was a `{policy, profile}` wrapper or a policy, and a
    real exported policy was mistaken for the wrapper and reset to defaults.

    `profile=None` keeps whatever extensions `policy` already carries, so a
    policy-only update never silently clears the profile's restrictions.
    """
    if policy is not None and not isinstance(policy, dict):
        raise ProfileError("policy must be an object")
    carried = (policy or {}).get("profile") if isinstance(policy, dict) else None
    try:
        out = normalize_policy(policy)
    except PolicyError as exc:
        raise ProfileError(str(exc)) from exc
    out["profile"] = normalize_profile_ext(profile if profile is not None else carried)
    return out


def profile_ext(policy: dict | None) -> dict[str, Any]:
    raw = ((policy or {}).get("profile")) or {}
    try:
        return normalize_profile_ext(raw)
    except ProfileError:
        # A stored profile that no longer validates must not break routing.
        return dict(DEFAULT_PROFILE_EXT)


def _str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProfileError(f"{name} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ProfileError(f"{name} entries must be strings")
        item = item.strip()
        if item and item not in out:
            out.append(item)
    return out


def _as_int(value: Any, name: str, lo: int, hi: int) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"{name} must be an integer") from exc
    if iv < lo or iv > hi:
        raise ProfileError(f"{name} must be between {lo} and {hi}")
    return iv


# ── lookup ────────────────────────────────────────────────────────────────


async def live_profiles(
    db: AsyncSession, workspace_id: str, *, only_enabled: bool = False
) -> list[RoutingProfile]:
    stmt = select(RoutingProfile).where(
        RoutingProfile.workspace_id == workspace_id,
        RoutingProfile.is_deleted == 0,
    )
    if only_enabled:
        stmt = stmt.where(RoutingProfile.is_enabled.is_(True))
    stmt = stmt.order_by(RoutingProfile.display_name)
    return list((await db.execute(stmt)).scalars().all())


async def find_profile(
    db: AsyncSession, workspace_id: str, slug: str
) -> RoutingProfile | None:
    return (
        await db.execute(
            select(RoutingProfile).where(
                RoutingProfile.workspace_id == workspace_id,
                RoutingProfile.slug == slug,
                RoutingProfile.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()


async def profile_slugs(db: AsyncSession, workspace_id: str) -> set[str]:
    return {p.slug for p in await live_profiles(db, workspace_id)}


async def tombstoned_slugs(db: AsyncSession, workspace_id: str) -> set[str]:
    rows = (
        await db.execute(
            select(RoutingProfileTombstone.slug).where(
                RoutingProfileTombstone.workspace_id == workspace_id
            )
        )
    ).scalars().all()
    return set(rows)


async def default_profile(
    db: AsyncSession, workspace_id: str
) -> RoutingProfile | None:
    return (
        await db.execute(
            select(RoutingProfile).where(
                RoutingProfile.workspace_id == workspace_id,
                RoutingProfile.is_default.is_(True),
                RoutingProfile.is_deleted == 0,
            )
        )
    ).scalars().first()


async def ensure_single_default(
    db: AsyncSession, workspace_id: str, keep_id: str | None
) -> None:
    """Clear is_default on every other profile (only one default at a time)."""
    rows = await live_profiles(db, workspace_id)
    for row in rows:
        should = row.id == keep_id
        if bool(row.is_default) != should:
            row.is_default = should


# ── routing-time enforcement ─────────────────────────────────────────────


def _blended_micros_per_million(model, *, allow_estimates: bool = False) -> int | None:
    """Blended (input + output) price per 1M tokens in micro-dollars.

    None when the model has no confirmed price — "unknown" is not "free", and
    a reference estimate is not a confirmed provider rate, so neither can
    satisfy a strict cost ceiling. Estimates count only when the policy
    explicitly opts in.
    """
    from app.auto_routing import ESTIMATE_PRICE_SOURCES, is_confirmed_price

    if not is_confirmed_price(model) and not (
        allow_estimates and getattr(model, "price_source", "") in ESTIMATE_PRICE_SOURCES
    ):
        return None
    inp = getattr(model, "input_cost_per_token", 0.0) or 0.0
    out = getattr(model, "output_cost_per_token", 0.0) or 0.0
    if not inp and not out:
        return None
    # $/token -> $/1M -> micro-dollars.
    return int(round((inp + out) * 1_000_000 * 1_000_000))


def apply_profile_filter(
    catalog: list, ext: dict[str, Any], *, allow_estimates: bool = False
) -> tuple[list, list[str]]:
    """Restrict the Auto catalog to what a profile allows.

    Applied to the planner's INPUT, so every candidate it returns — primary
    and fallbacks alike — already satisfies the profile. A fallback therefore
    cannot escape the profile's model, provider or cost restrictions.

    Returns `(kept, reasons)` where `reasons` explains each restriction that
    removed something, for diagnostics.
    """
    kept = list(catalog)
    reasons: list[str] = []

    providers = {p.lower() for p in (ext.get("providers") or [])}
    if providers:
        before = len(kept)
        kept = [m for m in kept if (getattr(m, "provider", "") or "").lower() in providers]
        if len(kept) < before:
            reasons.append(f"provider restriction removed {before - len(kept)} model(s)")

    models = set(ext.get("models") or [])
    if models:
        before = len(kept)
        kept = [m for m in kept if m.id in models]
        if len(kept) < before:
            reasons.append(f"model restriction removed {before - len(kept)} model(s)")

    ceiling = ext.get("max_cost_per_million_micros")
    if ceiling is not None:
        before = len(kept)
        kept = [
            m for m in kept
            if (price := _blended_micros_per_million(m, allow_estimates=allow_estimates))
            is not None and price <= ceiling
        ]
        if len(kept) < before:
            reasons.append(
                f"cost ceiling removed {before - len(kept)} model(s) "
                + (
                    "(unpriced models never pass a ceiling; reference estimates "
                    "are allowed by policy)"
                    if allow_estimates
                    else "(only confirmed provider prices satisfy a ceiling; "
                    "unpriced models and reference estimates never pass)"
                )
            )
    return kept, reasons
