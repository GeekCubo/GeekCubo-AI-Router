"""Custom OpenAI-compatible provider CRUD + connection test.

The dashboard's "OpenAI Format – Others" provider option maps to these
endpoints. Built-in provider keys (the `provider_keys` table) are untouched;
custom providers live in their own tables and are namespaced by a unique
`slug` so multiple aggregators and their models never collide.

Credentials are sealed with the same AES-256-GCM mechanism as built-in keys
and are never returned in plaintext. Base URLs are validated against the
SSRF/HTTPS policy in `app.custom_providers` before anything is persisted or
sent upstream.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache_invalidation_bus, custom_providers, model_metadata
from app._time_util import iso_utc
from app.config import get_settings
from app.deps import get_admin_context, get_db
from packages.auth.encryption import credential_is_decryptable, decrypt_credential, encrypt_credential
from packages.db.models.custom_provider import CustomProvider, CustomProviderModel

router = APIRouter(prefix="/v1/custom-providers", tags=["custom-providers"])

DASHBOARD_KEY_PLACEHOLDER = "[REDACTED]"

_RESERVED_SLUGS = {
    "openai", "anthropic", "google", "groq", "together", "fireworks",
    "xai", "deepseek", "auto", "cache", "unknown",
}


def _mask_key(api_key: str) -> str:
    if len(api_key) > 12:
        return api_key[:8] + "..." + api_key[-4:]
    if len(api_key) > 4:
        return api_key[:2] + "..." + api_key[-2:]
    return "..."


# ── request/response schemas ────────────────────────────────────────────────


class ModelIn(BaseModel):
    model_id: str
    display_name: str | None = None
    context_length: int | None = None
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    supports_json_schema: bool = False
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    # Dashboard ergonomics: prices may be given per-million tokens.
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    custom_cache_read_per_million: float | None = None
    custom_cache_write_per_million: float | None = None
    # Optional tri-state capability overrides. Every value, including
    # "unknown", is stored as an administrator decision that refreshes keep.
    capabilities: dict[str, str] | None = None
    # Optional administrator-supplied reference (original vendor) rates.
    reference_input_cost_per_million: float | None = None
    reference_output_cost_per_million: float | None = None
    reference_cache_read_per_million: float | None = None
    reference_cache_write_per_million: float | None = None
    # Administrator-confirmed catalog identity used to resolve metadata.
    catalog_key: str | None = None
    is_enabled: bool | None = None

    def resolved(self) -> dict:
        in_c = self.input_cost_per_token
        if in_c is None and self.input_cost_per_million is not None:
            in_c = self.input_cost_per_million / 1_000_000
        out_c = self.output_cost_per_token
        if out_c is None and self.output_cost_per_million is not None:
            out_c = self.output_cost_per_million / 1_000_000
        custom_price = any(
            value is not None and value > 0
            for value in (
                self.input_cost_per_token,
                self.output_cost_per_token,
                self.input_cost_per_million,
                self.output_cost_per_million,
            )
        )
        return {
            "provided_fields": self.model_fields_set,
            "model_id": self.model_id.strip(),
            "display_name": (self.display_name or self.model_id).strip(),
            "context_length": self.context_length,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_json_mode": self.supports_json_mode,
            "supports_json_schema": self.supports_json_schema,
            "input_cost_per_token": in_c if in_c is not None else 0.0,
            "output_cost_per_token": out_c if out_c is not None else 0.0,
            "custom_price_provided": custom_price,
            "custom_cache_read_per_million": self.custom_cache_read_per_million,
            "custom_cache_write_per_million": self.custom_cache_write_per_million,
            "capabilities": self.capabilities,
            "reference": {
                "input_per_million": self.reference_input_cost_per_million,
                "output_per_million": self.reference_output_cost_per_million,
                "cache_read_per_million": self.reference_cache_read_per_million,
                "cache_write_per_million": self.reference_cache_write_per_million,
            },
            "reference_provided": any(v is not None for v in (
                self.reference_input_cost_per_million,
                self.reference_output_cost_per_million,
                self.reference_cache_read_per_million,
                self.reference_cache_write_per_million,
            )),
            "catalog_key": self.catalog_key.strip() if self.catalog_key else None,
            "is_enabled": self.is_enabled,
        }


class CreateProvider(BaseModel):
    display_name: str
    base_url: str
    api_key: str
    slug: str | None = None
    is_enabled: bool = True
    eligible_for_auto: bool = True


class UpdateProvider(BaseModel):
    display_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_enabled: bool | None = None
    eligible_for_auto: bool | None = None


class TestConnectionIn(BaseModel):
    base_url: str
    api_key: str
    model: str | None = None


def _per_million(value: float | None) -> float | None:
    return None if value is None else float(value) * 1_000_000


def _reasoning_out(m: CustomProviderModel, base_url: str | None = None) -> dict:
    levels, source = model_metadata.endpoint_reasoning_levels(m, base_url)
    return {
        "reasoning_levels": list(levels) if levels is not None else None,
        "reasoning_source": source,
        "reasoning_observation": model_metadata.reasoning_observation_for_endpoint(m, base_url),
    }


def _model_out(m: CustomProviderModel, base_url: str | None = None) -> dict:
    meta = model_metadata.load_metadata(getattr(m, "metadata_json", None))
    identity = meta.get("identity") if isinstance(meta.get("identity"), dict) else {}
    reference = meta.get("reference") if isinstance(meta.get("reference"), dict) else {}
    caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    custom_in, custom_out, custom_state = model_metadata.effective_custom_price(m)
    tools_state = (caps.get("tools") or {}).get("state", "unknown")
    status = model_metadata.match_status(
        identity.get("confidence", "none"),
        {
            "context": m.context_length,
            "input_per_million": m.reference_input_cost_per_token,
            "output_per_million": m.reference_output_cost_per_token,
            "tools": None if tools_state == "unknown" else tools_state,
        },
    )
    return {
        "id": m.id,
        "model_id": m.model_id,
        "display_name": m.display_name,
        "context_length": m.context_length,
        # Provider-reported (GET /models) maximum output tokens; None = unknown.
        "max_output_tokens": model_metadata.provider_report(meta).get("max_output_tokens"),
        "supports_tools": bool(m.supports_tools),
        "supports_vision": bool(m.supports_vision),
        "supports_json_mode": bool(m.supports_json_mode),
        "supports_json_schema": bool(m.supports_json_schema),
        "is_enabled": bool(getattr(m, "is_enabled", True)),
        "input_cost_per_token": float(custom_in or 0.0),
        "output_cost_per_token": float(custom_out or 0.0),
        "input_cost_per_million": _per_million(custom_in),
        "output_cost_per_million": _per_million(custom_out),
        "price_state": custom_state,
        "reference_input_cost_per_million": _per_million(m.reference_input_cost_per_token),
        "reference_output_cost_per_million": _per_million(m.reference_output_cost_per_token),
        "reference_cache_read_cost_per_million": _per_million(m.reference_cache_read_cost_per_token),
        "reference_cache_write_cost_per_million": _per_million(m.reference_cache_write_cost_per_token),
        "reference_source": m.reference_source,
        "reference_trust": reference.get("trust", "unknown"),
        "reference_price_state": reference.get("price_state", "unknown"),
        "reference_stale": bool(reference.get("stale", False)),
        "catalog_key": identity.get("catalog_key"),
        "match_confidence": identity.get("confidence", "none"),
        "match_status": status,
        "match_candidates": identity.get("candidates", []),
        "capabilities": {
            "tools": (caps.get("tools") or {}).get("state", "unknown"),
            "vision": (caps.get("vision") or {}).get("state", "unknown"),
            "json_mode": (caps.get("json_mode") or {}).get("state", "unknown"),
            "json_schema": (caps.get("json_schema") or {}).get("state", "unknown"),
        },
        "capability_sources": {
            key: (caps.get(key) or {}).get("source")
            for key in ("tools", "vision", "json_mode", "json_schema")
        },
        # Endpoint-specific reasoning evidence: levels (list, [] = none, or
        # null = Unknown), where it came from, and the last verification.
        **_reasoning_out(m, base_url),
        "metadata": meta,
    }


def _provider_out(p: CustomProvider, models: list[CustomProviderModel]) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "display_name": p.display_name,
        "base_url": p.base_url,
        "key_prefix": p.key_prefix,
        "is_enabled": bool(p.is_enabled),
        "eligible_for_auto": bool(p.eligible_for_auto),
        "decryptable": credential_is_decryptable(p.encrypted_key),
        "last_models_fetched_at": iso_utc(p.last_models_fetched_at),
        "models": [_model_out(m, p.base_url) for m in models],
    }


async def _load_models(db: AsyncSession, provider_id: str) -> list[CustomProviderModel]:
    return list(
        (
            await db.execute(
                select(CustomProviderModel)
                .where(
                    CustomProviderModel.provider_id == provider_id,
                    CustomProviderModel.is_deleted == 0,
                )
                .order_by(CustomProviderModel.model_id)
            )
        ).scalars().all()
    )


async def _get_provider(db: AsyncSession, provider_id: str) -> CustomProvider:
    row = (
        await db.execute(
            select(CustomProvider).where(
                CustomProvider.id == provider_id,
                CustomProvider.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Custom provider not found")
    return row


def _validate_slug(slug: str) -> str:
    normalized = custom_providers.normalize_slug(slug)
    if normalized in _RESERVED_SLUGS or normalized.startswith("_"):
        raise HTTPException(
            status_code=422,
            detail=f"'{normalized}' is reserved; choose a different provider name",
        )
    return normalized


async def _slug_exists(db: AsyncSession, slug: str, *, exclude_id: str | None = None) -> bool:
    stmt = select(CustomProvider.id).where(
        CustomProvider.slug == slug, CustomProvider.is_deleted == 0
    )
    if exclude_id is not None:
        stmt = stmt.where(CustomProvider.id != exclude_id)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


def _validate_and_normalize_url(base_url: str) -> str:
    try:
        return custom_providers.validate_base_url(
            base_url,
            allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
        )
    except custom_providers.CustomProviderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── routes ──────────────────────────────────────────────────────────────────


@router.get("")
async def list_custom_providers(
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(CustomProvider)
            .where(CustomProvider.is_deleted == 0)
            .order_by(CustomProvider.display_name)
        )
    ).scalars().all()
    out = []
    for p in rows:
        models = await _load_models(db, p.id)
        out.append(_provider_out(p, models))
    return {"providers": out}


@router.post("", status_code=201)
async def create_custom_provider(
    body: CreateProvider,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="display_name cannot be empty")
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="api_key cannot be empty")

    slug = _validate_slug(body.slug or display_name)
    if await _slug_exists(db, slug):
        raise HTTPException(
            status_code=409,
            detail=f"a custom provider with identifier '{slug}' already exists",
        )

    base_url = _validate_and_normalize_url(body.base_url)

    row = CustomProvider(
        slug=slug,
        display_name=display_name,
        base_url=base_url,
        encrypted_key=encrypt_credential(api_key),
        key_prefix=_mask_key(api_key),
        is_enabled=body.is_enabled,
        eligible_for_auto=body.eligible_for_auto,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await _invalidate()
    return _provider_out(row, [])


@router.put("/{provider_id}")
async def update_custom_provider(
    provider_id: str,
    body: UpdateProvider,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get_provider(db, provider_id)

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")
        row.display_name = name

    if body.base_url is not None:
        row.base_url = _validate_and_normalize_url(body.base_url)

    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.eligible_for_auto is not None:
        row.eligible_for_auto = body.eligible_for_auto

    if body.api_key is not None and body.api_key != DASHBOARD_KEY_PLACEHOLDER:
        api_key = body.api_key.strip()
        if not api_key:
            raise HTTPException(status_code=422, detail="api_key cannot be empty")
        row.encrypted_key = encrypt_credential(api_key)
        row.key_prefix = _mask_key(api_key)

    await db.commit()
    await db.refresh(row)
    custom_providers.invalidate_fetch_cache(row.id)
    await _invalidate()
    models = await _load_models(db, row.id)
    return _provider_out(row, models)


@router.delete("/{provider_id}", status_code=204)
async def delete_custom_provider(
    provider_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await _get_provider(db, provider_id)
    await db.execute(
        sql_delete(CustomProviderModel).where(
            CustomProviderModel.provider_id == row.id
        )
    )
    await db.execute(sql_delete(CustomProvider).where(CustomProvider.id == row.id))
    await db.commit()
    custom_providers.invalidate_fetch_cache(row.id)
    await _invalidate()
    return Response(status_code=204)


def _build_model(
    provider_id: str,
    resolved: dict,
    *,
    previous: CustomProviderModel | None = None,
) -> CustomProviderModel:
    meta = model_metadata.load_metadata(previous.metadata_json if previous else None)
    manual = meta.get("manual") if isinstance(meta.get("manual"), dict) else {}
    enabled = resolved.get("is_enabled")
    if enabled is None:
        enabled = bool(previous.is_enabled) if previous else True
    m = CustomProviderModel(
        provider_id=provider_id,
        model_id=resolved["model_id"],
        display_name=resolved["display_name"],
        context_length=(
            previous.context_length
            if previous is not None and manual.get("context")
            else resolved["context_length"]
        ),
        supports_tools=resolved["supports_tools"],
        supports_vision=resolved["supports_vision"],
        supports_json_mode=resolved["supports_json_mode"],
        supports_json_schema=resolved["supports_json_schema"],
        input_cost_per_token=resolved["input_cost_per_token"],
        output_cost_per_token=resolved["output_cost_per_token"],
        reference_input_cost_per_token=previous.reference_input_cost_per_token if previous else None,
        reference_output_cost_per_token=previous.reference_output_cost_per_token if previous else None,
        reference_cache_read_cost_per_token=previous.reference_cache_read_cost_per_token if previous else None,
        reference_cache_write_cost_per_token=previous.reference_cache_write_cost_per_token if previous else None,
        reference_source=previous.reference_source if previous else None,
        is_enabled=enabled,
        metadata_json=previous.metadata_json if previous else None,
    )
    provided = resolved.get("provided_fields", set())
    if previous is not None:
        for field in ("supports_tools", "supports_vision", "supports_json_mode", "supports_json_schema", "context_length"):
            if field not in provided:
                setattr(m, field, getattr(previous, field))
        if not provided.intersection({
            "input_cost_per_token", "output_cost_per_token",
            "input_cost_per_million", "output_cost_per_million",
        }):
            m.input_cost_per_token = previous.input_cost_per_token
            m.output_cost_per_token = previous.output_cost_per_token
    if resolved.get("custom_price_provided"):
        model_metadata.apply_custom_price(
            m,
            input_per_million=resolved["input_cost_per_token"] * 1_000_000,
            output_per_million=resolved["output_cost_per_token"] * 1_000_000,
            cache_read_per_million=resolved.get("custom_cache_read_per_million"),
            cache_write_per_million=resolved.get("custom_cache_write_per_million"),
        )
    if resolved.get("reference_provided"):
        ref = resolved["reference"]
        model_metadata.set_reference_price(
            m,
            input_per_million=ref["input_per_million"],
            output_per_million=ref["output_per_million"],
            cache_read_per_million=ref["cache_read_per_million"],
            cache_write_per_million=ref["cache_write_per_million"],
        )
    if resolved.get("catalog_key"):
        model_metadata.set_alias(m, resolved["catalog_key"])
    for capability, state in (resolved.get("capabilities") or {}).items():
        model_metadata.apply_capability_override(m, capability, state)
    # A checked capability in the registration form is an explicit operator
    # assertion. Unchecked stays unknown so catalog metadata can fill it in.
    for capability, flag in (
        ("tools", "supports_tools"),
        ("vision", "supports_vision"),
        ("json_mode", "supports_json_mode"),
        ("json_schema", "supports_json_schema"),
    ):
        if resolved.get(flag) and capability not in (resolved.get("capabilities") or {}):
            model_metadata.apply_capability_override(m, capability, "supported")
    if resolved.get("context_length") is not None:
        model_metadata.mark_context_manual(m)
    return m


@router.put("/{provider_id}/models")
async def set_models(
    provider_id: str,
    body: list[ModelIn],
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Replace the provider's model set in one call (create/update/remove)."""
    row = await _get_provider(db, provider_id)

    seen: set[str] = set()
    for item in body:
        resolved = item.resolved()
        model_id = resolved["model_id"]
        if not model_id:
            raise HTTPException(status_code=422, detail="model_id cannot be empty")
        if model_id in seen:
            raise HTTPException(status_code=422, detail=f"duplicate model_id '{model_id}'")
        seen.add(model_id)

    previous = {m.model_id: m for m in await _load_models(db, row.id)}
    created: list[CustomProviderModel] = []
    for item in body:
        resolved = item.resolved()
        old = previous.pop(resolved["model_id"], None)
        built = _build_model(row.id, resolved, previous=old)
        if old is None:
            db.add(built)
            m = built
        else:
            # Keep the row UUID stable across full-set saves so dashboard
            # selections and audit references do not silently change.
            for column in CustomProviderModel.__table__.columns:
                if column.name in {"id", "created_at", "updated_at", "is_deleted"}:
                    continue
                setattr(old, column.name, getattr(built, column.name))
            m = old
        created.append(m)

    if previous:
        await db.execute(
            sql_delete(CustomProviderModel).where(
                CustomProviderModel.id.in_([m.id for m in previous.values()])
            )
        )

    await db.flush()
    sources = await model_metadata.load_enabled_sources(db)
    for m in created:
        model_metadata.resolve_one(row.slug, m, sources)
    await db.commit()
    await _invalidate()
    models = await _load_models(db, row.id)
    return _provider_out(row, models)


@router.post("/{provider_id}/models")
async def add_models(
    provider_id: str,
    body: list[ModelIn],
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add models without touching existing ones (idempotent by model_id).

    Used by the "Add Selected Models" discovery workflow: newly-discovered
    models are appended with unknown capabilities/pricing, preserving any
    operator configuration already stored on the provider.
    """
    row = await _get_provider(db, provider_id)
    existing = {m.model_id for m in await _load_models(db, row.id)}
    # Limits the provider reported in the most recent discovery (in-process
    # cache, never re-fetched here). Absent when no discovery ran.
    cached = custom_providers.cached_discovery(row.id)
    reported = {m["id"]: m for m in (cached or {}).get("models") or []}

    added = 0
    for item in body:
        resolved = item.resolved()
        model_id = resolved["model_id"]
        if not model_id:
            raise HTTPException(status_code=422, detail="model_id cannot be empty")
        if model_id in existing:
            continue
        built = _build_model(row.id, resolved)
        if model_id in reported:
            model_metadata.record_provider_report(built, reported[model_id])
        db.add(built)
        existing.add(model_id)
        added += 1

    await db.flush()
    sources = await model_metadata.load_enabled_sources(db)
    for m in await _load_models(db, row.id):
        model_metadata.resolve_one(row.slug, m, sources)
    await db.commit()
    await _invalidate()
    models = await _load_models(db, row.id)
    return {"added": added, "provider": _provider_out(row, models)}


class ModelMetadataIn(BaseModel):
    model_id: str | None = None
    display_name: str | None = None
    catalog_key: str | None = None
    clear_catalog_key: bool = False
    capabilities: dict[str, str] | None = None
    is_enabled: bool | None = None
    custom_input_cost_per_million: float | None = None
    custom_output_cost_per_million: float | None = None
    custom_cache_read_per_million: float | None = None
    custom_cache_write_per_million: float | None = None
    clear_custom_price: bool = False
    reference_input_cost_per_million: float | None = None
    reference_output_cost_per_million: float | None = None
    reference_cache_read_per_million: float | None = None
    reference_cache_write_per_million: float | None = None
    clear_reference_price: bool = False
    context_length: int | None = None
    clear_context: bool = False
    # Administrator reasoning-effort override for THIS deployment: a list of
    # levels it honours (empty = no effort control). Takes precedence over
    # verification results. `clear_reasoning` returns it to evidence/Unknown.
    reasoning_levels: list[str] | None = None
    clear_reasoning: bool = False


class BulkModelIn(BaseModel):
    action: str
    model_ids: list[str]
    capabilities: dict[str, str] | None = None


async def _get_model_row(
    db: AsyncSession, provider_id: str, model_row_id: str
) -> CustomProviderModel:
    row = (
        await db.execute(
            select(CustomProviderModel).where(
                CustomProviderModel.id == model_row_id,
                CustomProviderModel.provider_id == provider_id,
                CustomProviderModel.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return row


@router.patch("/{provider_id}/models/{model_row_id}")
async def update_model_metadata(
    provider_id: str,
    model_row_id: str,
    body: ModelMetadataIn,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    provider = await _get_provider(db, provider_id)
    m = await _get_model_row(db, provider_id, model_row_id)

    alias_changed = False
    if body.model_id is not None and body.model_id.strip() != m.model_id:
        model_id = body.model_id.strip()
        if not model_id:
            raise HTTPException(status_code=422, detail="model_id cannot be empty")
        if any(other.model_id == model_id for other in await _load_models(db, provider_id)):
            raise HTTPException(status_code=422, detail="duplicate model_id")
        m.model_id = model_id
        alias_changed = True
    if body.display_name is not None:
        m.display_name = body.display_name.strip() or m.model_id
    if body.clear_catalog_key:
        model_metadata.set_alias(m, None)
        alias_changed = True
    elif body.catalog_key:
        model_metadata.set_alias(m, body.catalog_key)
        alias_changed = True
    if body.clear_reasoning:
        model_metadata.set_reasoning_override(m, None)
    elif body.reasoning_levels is not None:
        try:
            model_metadata.set_reasoning_override(m, body.reasoning_levels)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    for capability, state in (body.capabilities or {}).items():
        try:
            if state == "catalog":
                model_metadata.clear_capability_override(m, capability)
                alias_changed = True
            else:
                model_metadata.apply_capability_override(m, capability, state)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    if body.clear_custom_price:
        meta = model_metadata.load_metadata(m.metadata_json)
        manual = meta.setdefault("manual", {})
        manual.pop("pricing", None)
        meta.pop("custom", None)
        m.input_cost_per_token = 0.0
        m.output_cost_per_token = 0.0
        m.metadata_json = model_metadata.dump_metadata(meta)
    elif any(value is not None for value in (
        body.custom_input_cost_per_million, body.custom_output_cost_per_million,
        body.custom_cache_read_per_million, body.custom_cache_write_per_million,
    )):
        model_metadata.apply_custom_price(
            m,
            input_per_million=body.custom_input_cost_per_million,
            output_per_million=body.custom_output_cost_per_million,
            cache_read_per_million=body.custom_cache_read_per_million,
            cache_write_per_million=body.custom_cache_write_per_million,
        )

    if body.clear_reference_price:
        meta = model_metadata.load_metadata(m.metadata_json)
        meta.setdefault("manual", {}).pop("reference", None)
        m.metadata_json = model_metadata.dump_metadata(meta)
        model_metadata.resolve_one(provider.slug, m, await model_metadata.load_enabled_sources(db))
    elif any(v is not None for v in (
        body.reference_input_cost_per_million,
        body.reference_output_cost_per_million,
        body.reference_cache_read_per_million,
        body.reference_cache_write_per_million,
    )):
        model_metadata.set_reference_price(
            m,
            input_per_million=body.reference_input_cost_per_million,
            output_per_million=body.reference_output_cost_per_million,
            cache_read_per_million=body.reference_cache_read_per_million,
            cache_write_per_million=body.reference_cache_write_per_million,
        )

    if body.clear_context:
        model_metadata.reset_context_override(m)
        model_metadata.resolve_one(provider.slug, m, await model_metadata.load_enabled_sources(db))
    elif body.context_length is not None:
        if body.context_length < 0:
            raise HTTPException(status_code=422, detail="context_length cannot be negative")
        m.context_length = body.context_length
        model_metadata.mark_context_manual(m)

    if body.is_enabled is not None:
        m.is_enabled = body.is_enabled

    if alias_changed:
        model_metadata.resolve_one(
            provider.slug, m, await model_metadata.load_enabled_sources(db)
        )

    await db.commit()
    custom_providers.invalidate_fetch_cache(provider.id)
    await _invalidate()
    return _model_out(m, provider.base_url)


@router.post("/{provider_id}/models/bulk")
async def bulk_update_models(
    provider_id: str,
    body: BulkModelIn,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Provider-scoped bulk model actions used by the dashboard table.

    Removals are soft deletes. The endpoint is intentionally explicit about
    scope: every id must belong to this provider.
    """
    provider = await _get_provider(db, provider_id)
    if not body.model_ids:
        raise HTTPException(status_code=422, detail="model_ids cannot be empty")
    if body.action not in {"enable", "disable", "remove", "restore_metadata", "resolve_metadata"}:
        raise HTTPException(status_code=422, detail="unsupported bulk action")
    if body.action == "restore_metadata" and not body.capabilities:
        raise HTTPException(status_code=422, detail="capabilities are required")

    rows = []
    for model_row_id in body.model_ids:
        rows.append(await _get_model_row(db, provider_id, model_row_id))

    sources = None
    results = []
    for m in rows:
        if body.action == "resolve_metadata":
            row_id, model_id = m.id, m.model_id
            try:
                if sources is None:
                    sources = await model_metadata.load_enabled_sources(db)
                async with db.begin_nested():
                    meta, resolved = model_metadata.resolve_one(provider.slug, m, sources)
                    identity = meta["identity"]
                    status = "resolved" if resolved is not None else (
                        "ambiguous" if identity["confidence"] == "ambiguous" else "unmatched"
                    )
                results.append({
                    "id": m.id, "model_id": m.model_id, "status": status,
                    "candidates": identity["candidates"],
                })
            except Exception:
                results.append({"id": row_id, "model_id": model_id, "status": "failed", "candidates": []})
        elif body.action == "enable":
            m.is_enabled = True
        elif body.action == "disable":
            m.is_enabled = False
        elif body.action == "remove":
            m.is_deleted = 1
            m.is_enabled = False
        else:
            for capability, state in (body.capabilities or {}).items():
                try:
                    if state == "catalog":
                        model_metadata.clear_capability_override(m, capability)
                    else:
                        model_metadata.apply_capability_override(m, capability, state)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from None
            if sources is None:
                sources = await model_metadata.load_enabled_sources(db)
            model_metadata.resolve_one(provider.slug, m, sources)

    await db.commit()
    custom_providers.invalidate_fetch_cache(provider.id)
    await _invalidate()
    response = {"updated": len(rows), "action": body.action}
    if body.action == "resolve_metadata":
        response["results"] = results
        response["summary"] = {
            status: sum(result["status"] == status for result in results)
            for status in ("resolved", "ambiguous", "unmatched", "failed")
        }
    return response


@router.post("/{provider_id}/fetch-models")
async def fetch_models(
    provider_id: str,
    body: dict | None = None,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Server-side `GET /models` against the provider's base URL + stored key.

    Never exposes the credential. Returns parsed model ids + metadata plus the
    set of already-registered model ids so the dashboard can distinguish new
    from existing entries. A successful fetch stamps `last_models_fetched_at`.
    """
    row = await _get_provider(db, provider_id)
    try:
        api_key = decrypt_credential(row.encrypted_key)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="stored key cannot be decrypted; re-save the API key",
        ) from exc

    body = body or {}
    result = await custom_providers.fetch_models(
        base_url=row.base_url,
        api_key=api_key,
        allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
        provider_id=row.id,
        force=bool(body.get("force")),
    )

    if result["ok"]:
        row.last_models_fetched_at = datetime.now(timezone.utc)
        # Keep registered models' provider-reported limits current. Only the
        # provider's own numbers are stored; administrator values still win.
        reported = {m["id"]: m for m in result.get("models") or []}
        changed = []
        for m in await _load_models(db, row.id):
            entry = reported.get(m.model_id)
            if entry and model_metadata.record_provider_report(m, entry):
                changed.append(m)
        if changed:
            sources = await model_metadata.load_enabled_sources(db)
            for m in changed:
                model_metadata.resolve_one(row.slug, m, sources)
        await db.commit()
        if changed:
            await _invalidate()

    registered = {m.model_id for m in await _load_models(db, row.id)}
    result["registered_model_ids"] = sorted(registered)

    # Preview catalog resolution for each discovered model so the dashboard
    # can show Resolved / Partial / Ambiguous / Unmatched before the operator
    # registers anything. Nothing is persisted here.
    if result.get("models"):
        sources = await model_metadata.load_enabled_sources(db)
        previews = {
            m["id"]: model_metadata.preview_model(row.slug, m["id"], sources)
            for m in result["models"]
        }
        for m in result["models"]:
            # Provider-reported limits outrank a catalog value for context;
            # show the value registration will actually store.
            if isinstance(m.get("context_window"), int):
                previews[m["id"]]["context_source"] = model_metadata.PROVIDER_REPORT_SOURCE
                previews[m["id"]]["fields"] = {
                    **previews[m["id"]].get("fields", {}),
                    "context": m["context_window"],
                }
        for m in result["models"]:
            m["preview"] = previews[m["id"]]
        summary: dict[str, int] = {}
        for preview in previews.values():
            summary[preview["status"]] = summary.get(preview["status"], 0) + 1
        result["preview_summary"] = summary
    return result



@router.delete("/{provider_id}/models/{model_id}", status_code=204)
async def delete_model(
    provider_id: str,
    model_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await _get_provider(db, provider_id)
    await db.execute(
        sql_delete(CustomProviderModel).where(
            CustomProviderModel.provider_id == row.id,
            CustomProviderModel.model_id == model_id,
        )
    )
    await db.commit()
    await _invalidate()
    return Response(status_code=204)


@router.post("/test")
async def test_connection(
    body: TestConnectionIn,
    _kc = Depends(get_admin_context),
) -> dict:
    """Verify connectivity to a base URL without persisting or leaking the key."""
    return await custom_providers.test_connection(
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
    )


@router.post("/{provider_id}/test")
async def test_saved_connection(
    provider_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test a saved provider using its stored key, without exposing it.

    The credential is decrypted server-side and sent only to the validated
    base URL already on record. The response never contains the key.
    """
    row = await _get_provider(db, provider_id)
    try:
        api_key = decrypt_credential(row.encrypted_key)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="stored key cannot be decrypted; re-save the API key",
        ) from exc
    return await custom_providers.test_connection(
        base_url=row.base_url,
        api_key=api_key,
        model=None,
        allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
    )


# One verification per model per window: each probe is a few paid calls.
_PROBE_COOLDOWN_S = 60.0
_last_probe: dict[str, float] = {}


@router.post("/{provider_id}/models/{model_row_id}/verify-reasoning")
async def verify_model_reasoning(
    provider_id: str,
    model_row_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Administrator-triggered reasoning-effort check for one deployment.

    Never runs automatically. Costs at most four tiny completions on the
    operator's own key. Only a conclusive result is stored (with a 30-day
    expiry); an administrator override always takes precedence over it.
    """
    import time

    row = await _get_provider(db, provider_id)
    m = await _get_model_row(db, provider_id, model_row_id)
    now = time.monotonic()
    if now - _last_probe.get(m.id, -1e9) < _PROBE_COOLDOWN_S:
        raise HTTPException(status_code=429, detail="This model was verified moments ago; try again shortly.")
    _last_probe[m.id] = now
    try:
        api_key = decrypt_credential(row.encrypted_key)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="stored key cannot be decrypted; re-save the API key") from exc
    result = await custom_providers.probe_reasoning(
        base_url=row.base_url, api_key=api_key, model=m.model_id,
        allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
    )
    if result.get("conclusive"):
        model_metadata.record_reasoning_observation(m, {
            "levels": result["levels"], "basis": result.get("basis"),
            "base_url": row.base_url, "model_id": m.model_id,
        })
        await db.commit()
        await _invalidate()
    return {**result, "model": _model_out(m, row.base_url)}


async def _invalidate() -> None:
    custom_providers.invalidate()
    await cache_invalidation_bus.broadcast_router_cache_invalidation()
