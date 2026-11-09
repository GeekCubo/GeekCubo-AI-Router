"""API-key management — administrator-only.

These keys are *inference* credentials: they authenticate SDK traffic against
/v1/chat/completions and friends. Minting or revoking one is an administrative
act, so every route here requires a dashboard session (enforced by the policy
module and, as defence in depth, by `get_admin_session`).

This is a deliberate boundary change from the original design, where holding an
unrestricted inference key was enough to mint sibling keys. That made one
leaked key into permanent, self-renewing access with no way to stop it short of
editing the database. Now key custody belongs to the administrator, and revoking
every key still leaves the operator able to sign in and mint a new one.

Keys are opaque `sk-geek-*` values hashed with the existing scheme; the
listing never shows a credential the middleware would reject.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app._time_util import iso_utc
from app.deps import DEFAULT_WORKSPACE_ID, get_admin_session, get_db
from packages.auth.hashing import generate_api_key
from packages.auth.sessions import SessionRecord
from packages.db.models.api_key import ApiKey

router = APIRouter(prefix="/v1/keys", tags=["keys"])

# `name` is operator-facing; long enough for "github-actions-prod-eu", short
# enough that the list stays readable.
_KEY_NAME_MAX = 255


class CreateKey(BaseModel):
    name: str
    # None (omitted) = unrestricted. [] = deny everything (see UpdateKey).
    model_allowlist: list[str] | None = None
    # Optional lifetime in days. Omitted/None means the key never expires,
    # which is what every pre-existing key already means.
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class UpdateKey(BaseModel):
    # Both optional: a rename and an allowlist change are independent actions.
    name: str | None = None
    # Required so JSON null (clear → unrestricted) is distinct from [].
    # `is not None` semantics: [] is a deny-everything lock, not "no restriction".
    model_allowlist: list[str] | None = None


class RotateKey(BaseModel):
    # Name for the replacement. Defaults to the old key's name + " (rotated)".
    name: str | None = None
    # When True, revoke the original as part of the rotation. Default False so
    # an operator can cut a client over deliberately — the old key keeps
    # working until they explicitly revoke it.
    revoke_original: bool = False


async def _validate_model_allowlist(
    db: AsyncSession, ids: list[str] | None
) -> list[str] | None:
    """Reject unknown catalog ids at write time.

    None stays None (unrestricted). An explicit empty list is valid — it is
    the operator's deny-everything signal, and must not be coerced to None.
    The known-id set is the merged catalog: built-in models plus namespaced
    custom-provider models (`{slug}/{model_id}`).
    """
    if ids is None:
        return None
    from app.custom_providers import merged_catalog_by_id

    known = await merged_catalog_by_id(db, eligible_only=False)
    unknown = sorted({m for m in ids if m not in known})
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown model id(s): {unknown}. "
                "Allowlist entries must match the catalog."
            ),
        )
    return ids


def _clean_name(name: str | None, *, fallback: str = "key") -> str:
    value = (name or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="Key name cannot be empty.")
    if len(value) > _KEY_NAME_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"Key name must be at most {_KEY_NAME_MAX} characters.",
        )
    return value


def _key_public(r: ApiKey) -> dict:
    expires_at = r.expires_at
    expired = False
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        expired = expires_at <= datetime.now(timezone.utc)
    return {
        "id": r.id,
        "name": r.name,
        "key_prefix": r.key_prefix,
        "is_active": r.is_active,
        "model_allowlist": r.model_allowlist,
        "budget_limit_cents": r.budget_limit_cents,
        "spent_microcents": r.spent_microcents,
        "last_used_at": iso_utc(r.last_used_at),
        "revoked_at": iso_utc(r.revoked_at),
        "created_at": iso_utc(r.created_at),
        "expires_at": iso_utc(expires_at),
        "expired": expired,
    }


async def _get_key(db: AsyncSession, key_id: str, workspace_id: str) -> ApiKey:
    row = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.workspace_id == workspace_id,
                ApiKey.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return row


@router.get("")
async def list_keys(
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(ApiKey)
            .where(
                ApiKey.is_deleted == 0,
                # Workspace-scoped, as before Phase 2. Lite only ever creates
                # rows in "default", but a stray foreign row must never be
                # visible or mutable through this API.
                ApiKey.workspace_id == DEFAULT_WORKSPACE_ID,
            )
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        )
    ).scalars().all()
    return {"keys": [_key_public(r) for r in rows]}


def _no_store(response: Response) -> None:
    """Responses carrying a plaintext key must not be cached anywhere."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("", status_code=201)
async def create_key(
    body: CreateKey,
    response: Response,
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _no_store(response)
    name = _clean_name(body.name)
    allowlist = await _validate_model_allowlist(db, body.model_allowlist)
    full_key, key_hash, key_prefix = generate_api_key()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
        if body.expires_in_days
        else None
    )
    row = ApiKey(
        workspace_id=DEFAULT_WORKSPACE_ID,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        model_allowlist=allowlist,
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return {
        **_key_public(row),
        # Plaintext is returned exactly once, only in this response body.
        # No-store keeps it out of browser and intermediary caches.
        "api_key": full_key,
    }


@router.put("/{key_id}")
async def update_key(
    key_id: str,
    body: UpdateKey,
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get_key(db, key_id, DEFAULT_WORKSPACE_ID)
    if body.name is not None:
        row.name = _clean_name(body.name)
    # Explicit `model_allowlist` in the payload is what distinguishes "leave it
    # alone" from "set it to null"; pydantic cannot tell absent from null here,
    # so a rename-only PUT must not wipe an allowlist. Clients that want to
    # clear it send null explicitly (documented behaviour, unchanged).
    if "model_allowlist" in body.model_fields_set:
        row.model_allowlist = await _validate_model_allowlist(db, body.model_allowlist)
    await db.commit()
    await db.refresh(row)
    return _key_public(row)


@router.post("/{key_id}/rotate", status_code=201)
async def rotate_key(
    key_id: str,
    body: RotateKey,
    response: Response,
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mint a replacement key with the same scope; leave the original alone.

    Rotation is explicitly non-destructive by default: the old key keeps
    authenticating until the operator revokes it, so a client can be cut over
    without a window where neither key works.
    """
    _no_store(response)
    original = await _get_key(db, key_id, DEFAULT_WORKSPACE_ID)
    name = _clean_name(body.name or f"{original.name} (rotated)")
    full_key, key_hash, key_prefix = generate_api_key()
    replacement = ApiKey(
        workspace_id=original.workspace_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        model_allowlist=original.model_allowlist,
        budget_limit_cents=original.budget_limit_cents,
        expires_at=original.expires_at,
    )
    db.add(replacement)
    if body.revoke_original:
        original.is_active = False
        original.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(replacement)
    await db.refresh(original)
    return {
        **_key_public(replacement),
        "api_key": full_key,
        "original": _key_public(original),
    }


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: str,
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await _get_key(db, key_id, DEFAULT_WORKSPACE_ID)
    row.is_active = False
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(status_code=204)
