"""Administrator account lifecycle: bootstrap, verify, change, recover.

Every function here is transactional in the sense that matters: either the
whole state change lands or nothing does. The singleton constraint on
`admin_accounts` is the real guard against two concurrent first-run setups —
the loser's INSERT raises IntegrityError and its transaction rolls back.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth.passwords import (
    PasswordPolicyError,
    burn_verification_time,
    hash_password,
    needs_rehash,
    validate_new_password,
    validate_username,
    verify_password,
)
from packages.auth.sessions import hash_session_token, revoke_all_sessions
from packages.db.models.admin import AdminAccount, SetupToken

SETUP_TOKEN_TTL = timedelta(hours=24)


class SetupError(Exception):
    """First-run setup refused. Message is safe to surface."""


class LoginError(Exception):
    """Credentials rejected. Message is deliberately generic."""


GENERIC_LOGIN_ERROR = "Invalid username or password."


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_admin(db: AsyncSession) -> AdminAccount | None:
    """The single administrator, or None if this install is uninitialized."""
    return (
        await db.execute(
            select(AdminAccount).where(AdminAccount.is_deleted == 0)
        )
    ).scalar_one_or_none()


async def admin_exists(db: AsyncSession) -> bool:
    return await get_admin(db) is not None


@dataclass
class SetupTokenIssued:
    raw_token: str
    expires_at: datetime


async def issue_setup_token(db: AsyncSession) -> SetupTokenIssued:
    """Mint (and persist) a one-time bootstrap token.

    Any previously issued, unconsumed token is invalidated first: if an operator
    re-runs the setup command because they lost the printed value, the old one
    must stop working rather than leave two live bootstrap secrets.
    """
    await db.execute(
        SetupToken.__table__.update()
        .where(SetupToken.consumed_at.is_(None), SetupToken.is_deleted == 0)
        .values(is_deleted=1)
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + SETUP_TOKEN_TTL
    db.add(
        SetupToken(token_hash=hash_session_token(raw_token), expires_at=expires_at)
    )
    await db.commit()
    return SetupTokenIssued(raw_token=raw_token, expires_at=expires_at)


async def consume_setup_token(db: AsyncSession, raw_token: str) -> None:
    """Atomically validate + consume a setup token.

    The UPDATE guards on `consumed_at IS NULL`, so two requests racing with the
    same token cannot both succeed: the second sees rowcount 0.
    """
    if not raw_token:
        raise SetupError("A setup token is required to create the administrator.")
    token_hash = hash_session_token(raw_token.strip())
    row = (
        await db.execute(
            select(SetupToken).where(
                SetupToken.token_hash == token_hash,
                SetupToken.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise SetupError("Invalid setup token.")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        raise SetupError(
            "This setup token has expired. Run `python -m app.admin_cli setup-token` "
            "on the host to generate a new one."
        )
    result = await db.execute(
        SetupToken.__table__.update()
        .where(
            SetupToken.id == row.id,
            SetupToken.consumed_at.is_(None),
            SetupToken.is_deleted == 0,
        )
        .values(consumed_at=_now())
    )
    if int(result.rowcount or 0) != 1:
        raise SetupError("This setup token has already been used.")
    await db.commit()


async def create_admin(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    setup_token: str,
) -> AdminAccount:
    """Create the one administrator. Requires a valid, unused setup token."""
    if await admin_exists(db):
        raise SetupError(
            "An administrator already exists. Sign in with those credentials, "
            "or use `python -m app.admin_cli reset-password` locally if the "
            "password is lost."
        )
    clean_username = validate_username(username)
    validate_new_password(password, username=clean_username)
    await consume_setup_token(db, setup_token)

    admin = AdminAccount(
        singleton=1,
        username=clean_username,
        password_hash=hash_password(password),
        password_changed_at=_now(),
    )
    db.add(admin)
    try:
        await db.commit()
    except IntegrityError as exc:
        # Concurrent setup: another request won the singleton race. Its token
        # was consumed too, so this is a clean "already initialized" error.
        await db.rollback()
        raise SetupError("An administrator already exists.") from exc
    await db.refresh(admin)
    return admin


async def authenticate(
    db: AsyncSession, *, username: str, password: str
) -> AdminAccount:
    """Verify credentials. Always the same failure and the same cost.

    Unknown username still runs a full Argon2 verification so response time
    does not disclose whether the account exists.
    """
    admin = await get_admin(db)
    if admin is None:
        burn_verification_time(password)
        raise LoginError(GENERIC_LOGIN_ERROR)
    if not verify_password(admin.password_hash, password or ""):
        raise LoginError(GENERIC_LOGIN_ERROR)
    if admin.username.strip().lower() != (username or "").strip().lower():
        # Right password, wrong username — still generic, still verified above.
        raise LoginError(GENERIC_LOGIN_ERROR)

    if needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(password)
        await db.commit()

    admin.last_login_at = _now()
    await db.commit()
    await db.refresh(admin)
    return admin


async def change_password(
    db: AsyncSession,
    admin: AdminAccount,
    *,
    current_password: str,
    new_password: str,
    keep_session_id: str | None = None,
) -> None:
    """Verify the current password, then replace it and invalidate sessions.

    `keep_session_id` is the session performing the change. The caller decides
    whether to keep it (we do: the operator stays signed in on this device)
    while every *other* session is revoked.
    """
    if not verify_password(admin.password_hash, current_password or ""):
        raise LoginError("Current password is incorrect.")
    if verify_password(admin.password_hash, new_password or ""):
        raise PasswordPolicyError("New password must differ from the current one.")
    validate_new_password(new_password, username=admin.username)

    admin.password_hash = hash_password(new_password)
    admin.password_changed_at = _now()
    await db.commit()
    await revoke_all_sessions(db, admin.id, except_session_id=keep_session_id)


async def reset_password_locally(
    db: AsyncSession, *, username: str | None, new_password: str
) -> AdminAccount:
    """CLI recovery path. No current password required; revokes all sessions."""
    admin = await get_admin(db)
    if admin is None:
        raise SetupError(
            "No administrator exists yet. Run `python -m app.admin_cli setup` first."
        )
    if username and username.strip().lower() != admin.username.strip().lower():
        raise SetupError(
            f"No administrator named '{username}'. The configured username is "
            f"'{admin.username}'."
        )
    validate_new_password(new_password, username=admin.username)
    admin.password_hash = hash_password(new_password)
    admin.password_changed_at = _now()
    admin.password_reset_at = _now()
    await db.commit()
    await revoke_all_sessions(db, admin.id)
    return admin
