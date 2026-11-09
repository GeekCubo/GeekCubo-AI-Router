"""Browser session storage: create, validate, renew, revoke.

Design notes that matter for correctness:

* The cookie carries a 256-bit random secret; the database stores only its
  SHA-256 hash. A leaked database dump therefore cannot be replayed as a live
  session, and lookups stay O(1) on an indexed column.
* CSRF uses a per-session random token returned in the `me` payload and
  required in `X-CSRF-Token` on state-changing requests. It is stored
  server-side, so an attacker who can set cookies still cannot guess it, and
  it is never readable by cross-origin script.
* Two independent clocks: an absolute `expires_at` (session lifetime) and an
  idle window (`last_seen_at`). Both are enforced server-side; the client's
  copy is advisory only.
* Everything is server-side revocable — logout, password change and "revoke
  other sessions" delete rows rather than hoping the client forgets a cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.admin import AdminAccount, AdminSession

SESSION_COOKIE_NAME = "geekcubo_admin_session"
CSRF_HEADER_NAME = "x-csrf-token"

# Absolute session lifetime. Long enough for a working day of dashboard use,
# short enough that an abandoned browser does not stay authenticated forever.
SESSION_TTL = timedelta(hours=12)
# Idle window: a session untouched for this long is dead even if its absolute
# expiry has not arrived.
SESSION_IDLE_TTL = timedelta(minutes=60)
# "Remember me for 14 days": a hard limit measured from sign-in. Activity never
# extends it (expires_at is written once, at creation), and there is no idle
# limit, so closing the browser or leaving the dashboard alone does not end it.
# Revocation (logout, password change/reset, "log out other sessions", CLI)
# applies exactly as for normal sessions.
REMEMBER_TTL = timedelta(days=14)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes for tz-aware columns; normalize."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_session_token(raw: str) -> str:
    """SHA-256 of the cookie secret (fast is fine: the secret is 256-bit)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_secret() -> str:
    return secrets.token_urlsafe(32)


@dataclass
class SessionIssued:
    raw_token: str
    csrf_token: str
    expires_at: datetime
    persistent: bool = False


@dataclass
class SessionRecord:
    session_id: str
    admin_id: str
    username: str
    csrf_token: str
    expires_at: datetime
    last_seen_at: datetime
    persistent: bool = False


async def create_session(
    db: AsyncSession,
    admin: AdminAccount,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    persistent: bool = False,
) -> SessionIssued:
    """Mint a new session row and return the plaintext cookie secret once."""
    raw_token = _new_secret()
    csrf_token = _new_secret()
    now = _now()
    persistent = bool(persistent)
    expires_at = now + (REMEMBER_TTL if persistent else SESSION_TTL)
    db.add(
        AdminSession(
            admin_id=admin.id,
            token_hash=hash_session_token(raw_token),
            csrf_token=csrf_token,
            expires_at=expires_at,
            last_seen_at=now,
            ip_address=(ip_address or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
            persistent=persistent,
        )
    )
    await db.commit()
    return SessionIssued(
        raw_token=raw_token, csrf_token=csrf_token, expires_at=expires_at, persistent=persistent
    )


async def load_session(
    db: AsyncSession,
    raw_token: str,
    *,
    touch: bool = True,
) -> SessionRecord | None:
    """Resolve a cookie secret to a live session, enforcing both TTLs.

    Expired/idle sessions are revoked on sight so a stale cookie cannot be
    resurrected by a clock skew on a later request.
    """
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    row = (
        await db.execute(
            select(AdminSession, AdminAccount)
            .join(AdminAccount, AdminSession.admin_id == AdminAccount.id)
            .where(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
                AdminAccount.is_deleted == 0,
            )
        )
    ).first()
    if row is None:
        return None
    session, admin = row
    now = _now()
    expires_at = _as_utc(session.expires_at)
    last_seen = _as_utc(session.last_seen_at)
    persistent = bool(session.persistent)
    if expires_at is None or expires_at <= now:
        await revoke_session(db, session.id)
        return None
    # Defence in depth: a remembered session can never outlive REMEMBER_TTL
    # from its creation, whatever expires_at says.
    created = _as_utc(session.created_at)
    if persistent and created is not None and now - created > REMEMBER_TTL:
        await revoke_session(db, session.id)
        return None
    if not persistent and (last_seen is None or (now - last_seen) > SESSION_IDLE_TTL):
        await revoke_session(db, session.id)
        return None

    if touch:
        # Slide the idle window. Cheap single-row update on an indexed PK.
        await db.execute(
            update(AdminSession)
            .where(AdminSession.id == session.id)
            .values(last_seen_at=now)
        )
        await db.commit()

    return SessionRecord(
        session_id=session.id,
        admin_id=admin.id,
        username=admin.username,
        csrf_token=session.csrf_token,
        expires_at=expires_at,
        last_seen_at=last_seen or now,
        persistent=persistent,
    )


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(AdminSession)
        .where(AdminSession.id == session_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.commit()


async def revoke_session_by_token(db: AsyncSession, raw_token: str) -> None:
    if not raw_token:
        return
    await db.execute(
        update(AdminSession)
        .where(
            AdminSession.token_hash == hash_session_token(raw_token),
            AdminSession.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    await db.commit()


async def revoke_all_sessions(
    db: AsyncSession, admin_id: str, *, except_session_id: str | None = None
) -> int:
    """Revoke every live session for `admin_id`. Returns the count revoked."""
    stmt = (
        update(AdminSession)
        .where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if except_session_id:
        stmt = stmt.where(AdminSession.id != except_session_id)
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)


def csrf_token_matches(expected: str, provided: str | None) -> bool:
    """Constant-time CSRF comparison. Missing token never matches."""
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


async def purge_expired_sessions(db: AsyncSession, *, older_than_days: int = 7) -> int:
    """Delete long-dead rows so the table does not grow without bound."""
    cutoff = _now() - timedelta(days=older_than_days)
    result = await db.execute(
        delete(AdminSession).where(
            (AdminSession.expires_at < cutoff) | (AdminSession.revoked_at < cutoff)
        )
    )
    await db.commit()
    return int(result.rowcount or 0)
