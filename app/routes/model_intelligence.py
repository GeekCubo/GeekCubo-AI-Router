"""Model Intelligence API — sources, refresh, and price lookup."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import model_intelligence as mi
from app import model_metadata
from app.config import get_settings
from app.deps import get_admin_context, get_db
from app.safe_fetch import FetchError, validate_source_url
from app.seed import DEFAULT_WORKSPACE_ID
from packages.auth.encryption import decrypt_credential, encrypt_credential
from packages.db.models.metadata_source import MetadataSource

router = APIRouter(prefix="/v1/model-intelligence", tags=["model intelligence"])


class SourceIn(BaseModel):
    name: str
    url: str
    priority: int = 100
    sync_interval_hours: int = 24
    token: str | None = None
    is_enabled: bool = True


class SourcePatch(BaseModel):
    name: str | None = None
    url: str | None = None
    priority: int | None = None
    sync_interval_hours: int | None = None
    token: str | None = None
    is_enabled: bool | None = None


async def _rows(db: AsyncSession) -> list[MetadataSource]:
    return list(
        (
            await db.execute(
                select(MetadataSource)
                .where(
                    MetadataSource.workspace_id == DEFAULT_WORKSPACE_ID,
                    MetadataSource.is_deleted == 0,
                )
                .order_by(MetadataSource.priority, MetadataSource.name)
            )
        ).scalars().all()
    )


def _out(row: MetadataSource) -> dict:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "kind": row.kind,
        "url": row.url,
        "is_builtin": bool(row.is_builtin),
        "is_enabled": bool(row.is_enabled),
        "priority": row.priority,
        "sync_interval_hours": row.sync_interval_hours,
        "has_token": bool(row.encrypted_token),
        "entry_count": row.entry_count,
        "last_attempt_at": _iso(row.last_attempt_at),
        "last_success_at": _iso(row.last_success_at),
        "last_error": row.last_error,
        "stale": mi.is_stale(row.last_success_at, row.sync_interval_hours),
        "description": next(
            (b["description"] for b in mi.BUILTIN_SOURCES if b["key"] == row.key), None
        ),
    }


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def ensure_builtin_sources(db: AsyncSession) -> None:
    """Materialize the three default sources once, on first use.

    Idempotent, and never re-enables a source the operator turned off.
    """
    existing = {r.key for r in await _rows(db)}
    added = False
    for spec in mi.BUILTIN_SOURCES:
        if spec["key"] in existing:
            continue
        db.add(
            MetadataSource(
                workspace_id=DEFAULT_WORKSPACE_ID,
                key=spec["key"],
                name=spec["name"],
                kind=spec["kind"],
                url=spec["url"],
                is_builtin=True,
                is_enabled=True,
                priority=spec["priority"],
            )
        )
        added = True
    if added:
        await db.commit()


async def _entries_for(db: AsyncSession, *, refresh: bool = False) -> list[dict]:
    """Enabled sources in priority order with their cached entries."""
    out = []
    for row in await _rows(db):
        if not row.is_enabled:
            continue
        if refresh:
            await refresh_source(db, row)
        out.append({
            "key": row.key,
            "name": row.name,
            "entries": row.cache or {},
            "stale": mi.is_stale(row.last_success_at, row.sync_interval_hours),
        })
    return out


def _load_litellm_entries() -> dict[str, dict]:
    import litellm

    return mi.parse_litellm(getattr(litellm, "model_cost", {}) or {})


async def refresh_source(db: AsyncSession, row: MetadataSource) -> dict:
    """Refresh one source. Never raises: failures are recorded on the row and
    the previous cache is kept so the data stays usable (flagged stale)."""
    from app.safe_fetch import safe_get

    row.last_attempt_at = datetime.now(timezone.utc)
    try:
        if row.kind == "litellm":
            entries = _load_litellm_entries()
        elif row.kind == "portkey":
            entries = await _fetch_portkey(db, row)
        else:
            token = None
            if row.encrypted_token:
                try:
                    token = decrypt_credential(row.encrypted_token)
                except Exception:
                    raise FetchError(
                        "the stored token cannot be decrypted with the current "
                        "CREDENTIAL_ENCRYPTION_KEY; re-save it"
                    ) from None
            result = await safe_get(
                row.url or "",
                allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
                bearer_token=token,
                etag=row.etag,
                last_modified=row.last_modified,
            )
            if result.not_modified:
                row.last_success_at = datetime.now(timezone.utc)
                row.last_error = None
                await db.commit()
                return _out(row)
            data = mi.parse_json_bytes(result.body)
            entries = (
                mi.parse_portkey(_portkey_provider(row), data)
                if row.kind == "portkey"
                else mi.parse_models_dev(data)
            )
            row.etag = result.etag
            row.last_modified = result.last_modified
        if not entries:
            raise FetchError("the source returned no usable models")
        row.cache = entries
        row.entry_count = len(entries)
        row.last_success_at = datetime.now(timezone.utc)
        row.last_error = None
    except (FetchError, ValueError) as exc:
        row.last_error = str(exc)[:500]
    except Exception as exc:  # never break the endpoint on an unexpected parser bug
        row.last_error = f"refresh failed: {type(exc).__name__}: {exc}"[:500]
    await db.commit()
    return _out(row)


def _portkey_provider(row: MetadataSource) -> str:
    return (row.url or "").rsplit("/", 1)[-1].removesuffix(".json")


async def _fetch_portkey(db: AsyncSession, row: MetadataSource) -> dict[str, dict]:
    """Portkey publishes one file per provider; fetch the providers we use.

    Only provider slugs that appear in a registered model id are fetched, so
    enabling this source does not hammer 90 URLs on every refresh.
    """
    from app.custom_providers import merged_catalog
    from app.safe_fetch import safe_get

    catalog = await merged_catalog(db, eligible_only=False)
    providers = sorted({m.provider for m in catalog if m.provider})
    if not providers:
        raise FetchError("no registered models to look up")
    template = row.url or "https://configs.portkey.ai/pricing/{provider}.json"
    merged: dict[str, dict] = {}
    errors: list[str] = []
    for provider in providers:
        url = template.replace("{provider}", provider)
        try:
            result = await safe_get(
                url,
                allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
            )
            merged.update(mi.parse_portkey(provider, mi.parse_json_bytes(result.body)))
        except (FetchError, ValueError) as exc:
            errors.append(f"{provider}: {exc}")
    if not merged:
        raise FetchError(
            "no provider pricing could be fetched"
            + (f" ({'; '.join(errors[:3])})" if errors else "")
        )
    return merged


@router.get("/sources")
async def list_sources(
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await ensure_builtin_sources(db)
    return {"sources": [_out(r) for r in await _rows(db)]}


@router.post("/sources", status_code=201)
async def add_source(
    body: SourceIn,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be empty")
    try:
        url = validate_source_url(
            body.url, allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts
        )
    except FetchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not 1 <= body.priority <= 10_000:
        raise HTTPException(status_code=422, detail="priority must be between 1 and 10000")
    if not 1 <= body.sync_interval_hours <= 720:
        raise HTTPException(status_code=422, detail="sync_interval_hours must be 1-720")

    key = "custom-" + name.lower().replace(" ", "-")[:40]
    if any(r.key == key for r in await _rows(db)):
        raise HTTPException(status_code=409, detail="a source with that name already exists")
    row = MetadataSource(
        workspace_id=DEFAULT_WORKSPACE_ID,
        key=key,
        name=name,
        kind="custom_models_dev",
        url=url,
        is_builtin=False,
        is_enabled=body.is_enabled,
        priority=body.priority,
        sync_interval_hours=body.sync_interval_hours,
        encrypted_token=encrypt_credential(body.token) if body.token else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row)


async def _get(db: AsyncSession, source_id: str) -> MetadataSource:
    row = (
        await db.execute(
            select(MetadataSource).where(
                MetadataSource.workspace_id == DEFAULT_WORKSPACE_ID,
                MetadataSource.id == source_id,
                MetadataSource.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Metadata source not found")
    return row


@router.put("/sources/{source_id}")
async def update_source(
    source_id: str,
    body: SourcePatch,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get(db, source_id)
    if body.name is not None and not row.is_builtin:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="name cannot be empty")
        row.name = name
    if body.url is not None and not row.is_builtin:
        try:
            row.url = validate_source_url(
                body.url,
                allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
            )
        except FetchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row.etag = None
        row.last_modified = None
    if body.priority is not None:
        if not 1 <= body.priority <= 10_000:
            raise HTTPException(status_code=422, detail="priority must be between 1 and 10000")
        row.priority = body.priority
    if body.sync_interval_hours is not None:
        if not 1 <= body.sync_interval_hours <= 720:
            raise HTTPException(status_code=422, detail="sync_interval_hours must be 1-720")
        row.sync_interval_hours = body.sync_interval_hours
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.token is not None:
        if row.is_builtin:
            raise HTTPException(status_code=422, detail="built-in sources take no token")
        row.encrypted_token = encrypt_credential(body.token) if body.token else None
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await _get(db, source_id)
    if row.is_builtin:
        raise HTTPException(
            status_code=403,
            detail="Built-in sources cannot be deleted; disable them instead",
        )
    row.is_deleted = 1
    await db.commit()


@router.post("/sources/{source_id}/refresh")
async def refresh_one(
    source_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get(db, source_id)
    result = await refresh_source(db, row)
    synced = await model_metadata.sync_all_registered(db)
    await db.commit()
    return {**result, "metadata_synced": synced}


@router.post("/sources/{source_id}/test")
async def test_source(
    source_id: str,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Connectivity check that reports the outcome without touching the cache."""
    row = await _get(db, source_id)
    if row.kind == "litellm":
        entries = _load_litellm_entries()
        return {"ok": True, "models": len(entries), "error": None, "source": "bundled"}
    from app.safe_fetch import safe_get

    token = None
    if row.encrypted_token:
        try:
            token = decrypt_credential(row.encrypted_token)
        except Exception:
            return {"ok": False, "models": 0, "error": "stored token cannot be decrypted"}
    try:
        if row.kind == "portkey":
            entries = await _fetch_portkey(db, row)
        else:
            result = await safe_get(
                row.url or "",
                allowed_local_hosts=get_settings().custom_provider_allowed_local_hosts,
                bearer_token=token,
            )
            data = mi.parse_json_bytes(result.body)
            entries = (
                mi.parse_portkey(_portkey_provider(row), data)
                if row.kind == "portkey" else mi.parse_models_dev(data)
            )
        return {"ok": True, "models": len(entries), "error": None, "source": row.url}
    except (FetchError, ValueError) as exc:
        return {"ok": False, "models": 0, "error": str(exc)}


@router.post("/refresh")
async def refresh_all(
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await ensure_builtin_sources(db)
    results = [await refresh_source(db, r) for r in await _rows(db) if r.is_enabled]
    synced = await model_metadata.sync_all_registered(db)
    await db.commit()
    return {"sources": results, "metadata_synced": synced}


@router.get("/lookup")
async def lookup(
    model: str = Query(..., min_length=1, max_length=200),
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What each enabled source reports for one model, and which value wins."""
    await ensure_builtin_sources(db)
    entries = await _entries_for(db, refresh=False)
    configured = None
    try:
        from app.custom_providers import merged_catalog_by_id

        m = (await merged_catalog_by_id(db, eligible_only=False)).get(model)
        if m is not None and (m.input_cost_per_token or m.output_cost_per_token):
            configured = {
                "input_per_million": (m.input_cost_per_token or 0.0) * 1_000_000,
                "output_per_million": (m.output_cost_per_token or 0.0) * 1_000_000,
                "context": getattr(m, "context_length", None),
            }
    except Exception:
        configured = None
    result = mi.resolve(model, configured=configured, sources=entries)
    errors = {r.key: r.last_error for r in await _rows(db)}
    result["sources"] = [
        {
            "key": s["key"],
            "name": s["name"],
            "stale": s["stale"],
            "has_entry": (s.get("entries") or {}).get(model.lower()) is not None,
            "last_error": errors.get(s["key"]),
        }
        for s in entries
    ]
    return result
