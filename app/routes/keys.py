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

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app._time_util import iso_utc
from app.deps import DEFAULT_WORKSPACE_ID, get_admin_session, get_db
from packages.auth import key_recovery
from packages.auth.hashing import generate_api_key
from packages.auth.sessions import SessionRecord
from packages.db.models.api_key import ApiKey
from packages.db.models.key_recovery import KeyRecoveryAudit

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
        # Whether an encrypted copy exists. Never the copy itself.
        "recoverable": r.encrypted_secret is not None,
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


# ── copyable keys ───────────────────────────────────────────────────────────
#
# New and rotated keys also get an AES-256-GCM copy sealed with the dedicated
# API_KEY_RECOVERY_KEY, so the administrator can copy the full key again later
# from its row. Authentication is unchanged and never reads that copy.
# Retrieval needs an administrator session + CSRF token (middleware, POST),
# is rate limited per session, is never cached, and every attempt is written
# to key_recovery_audit without the secret. Keys created before this existed
# were stored hash-only and cannot be copied.

_RETRIEVE_LIMIT = 30          # retrievals per session...
_RETRIEVE_WINDOW_S = 10 * 60  # ...per 10 minutes
_retrievals: dict[str, deque[float]] = defaultdict(deque)


def reset_recovery_rate_limits() -> None:
    """Test hook."""
    _retrievals.clear()


def _hit(bucket: dict[str, deque[float]], key: str, limit: int, window_s: int) -> bool:
    """Record an event; return False when the window is already full."""
    now = time.monotonic()
    q = bucket[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _peer(request: Request) -> str | None:
    from app.routes.auth import _client_ip

    return (_client_ip(request) or "")[:64] or None


def _seal_if_possible(row: ApiKey, full_key: str) -> None:
    """Store an encrypted copy when a recovery key is configured.

    Without API_KEY_RECOVERY_KEY (for example secrets managed only in .env on
    an install that never set it) the key is simply stored hash-only.
    """
    if key_recovery.recovery_available():
        row.encrypted_secret = key_recovery.seal_api_key(full_key, row.id)


async def _audit(db: AsyncSession, outcome: str, *, record: SessionRecord,
                 request: Request, key: ApiKey) -> None:
    db.add(KeyRecoveryAudit(
        event="retrieve",
        outcome=outcome,
        api_key_id=key.id,
        key_prefix=key.key_prefix,
        session_id=record.session_id,
        ip_address=_peer(request),
    ))
    await db.commit()


@router.post("/{key_id}/reveal")
async def reveal_key(
    key_id: str,
    request: Request,
    response: Response,
    record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the full secret of a copyable key. POST so CSRF applies."""
    _no_store(response)
    row = await _get_key(db, key_id, DEFAULT_WORKSPACE_ID)

    async def deny(status: int, outcome: str, detail: str):
        await _audit(db, outcome, record=record, request=request, key=row)
        raise HTTPException(status_code=status, detail=detail)

    if not _hit(_retrievals, record.session_id, _RETRIEVE_LIMIT, _RETRIEVE_WINDOW_S):
        await deny(429, "rate_limited", "Too many key copies. Wait a few minutes.")
    usable = row.is_active and row.revoked_at is None
    if usable and row.expires_at is not None:
        exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        usable = exp > datetime.now(timezone.utc)
    if not usable:
        await deny(409, "not_active", "This key is revoked or expired.")
    if row.encrypted_secret is None:
        await deny(409, "not_recoverable",
                   "This key was created before keys could be copied, so only its hash "
                   "is stored. Rotate it once to get a copyable key.")
    try:
        secret = key_recovery.open_api_key(row.encrypted_secret, row.id)
    except Exception:
        await deny(500, "decrypt_failed",
                   "The stored copy could not be decrypted. Check API_KEY_RECOVERY_KEY.")
    await _audit(db, "ok", record=record, request=request, key=row)
    return {"id": row.id, "api_key": secret}

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
    await db.flush()  # assigns row.id, which the ciphertext is bound to
    _seal_if_possible(row, full_key)
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
    await db.flush()
    _seal_if_possible(replacement, full_key)
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
    # A revoked key can never be used again, so its recoverable copy has no
    # purpose. Destroy it rather than keep a dead secret around.
    row.encrypted_secret = None
    await db.commit()
    return Response(status_code=204)


@router.post("/{key_id}/archive", status_code=204)
async def archive_key(
    key_id: str,
    _record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Hide a revoked or expired key from key management.

    A soft delete (`is_deleted = 1`): the row, its hash and its revocation
    timestamp stay in the database, so request-log rows that reference the key
    keep their audit trail. The key validator already ignores soft-deleted rows,
    and the key was unusable before this call anyway. Active keys are refused:
    archiving must never be a silent way to revoke a credential.
    """
    row = await _get_key(db, key_id, DEFAULT_WORKSPACE_ID)
    expired = False
    if row.expires_at is not None:
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        expired = expires_at <= datetime.now(timezone.utc)
    revoked = (not row.is_active) or row.revoked_at is not None
    if not (revoked or expired):
        raise HTTPException(
            status_code=409,
            detail="Only revoked or expired keys can be archived. Revoke the key first.",
        )
    row.is_deleted = 1
    row.encrypted_secret = None
    await db.commit()
    return Response(status_code=204)

