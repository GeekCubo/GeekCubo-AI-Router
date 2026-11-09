"""Administrator authentication endpoints.

All of these live under `/api/auth/` and are PUBLIC at the middleware layer —
by definition they are the routes that establish a session. Each one enforces
its own restriction internally:

  status           anonymous; reports only whether setup is complete
  setup            requires a one-time bootstrap token; disabled afterwards
  login            rate limited per (username, client); generic errors
  logout           requires a session, revokes it server-side
  me               requires a session; returns identity + CSRF token
  change-password  requires a session + CSRF; revokes other sessions
  sessions         requires a session; lists/revokes sibling sessions

Session material never appears in a JSON body except the CSRF token (which is
not a bearer credential — it is useless without the HttpOnly cookie).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_admin_session, get_db
from app.security_cookies import clear_session_cookies, set_session_cookies
from packages.auth import admin_accounts
from packages.auth.passwords import (
    PasswordPolicyError,
    password_strength_hint,
    validate_username,
)
from packages.auth.sessions import (
    SessionRecord,
    create_session,
    revoke_all_sessions,
    revoke_session,
)
from packages.db.models.admin import AdminSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── login rate limiting ────────────────────────────────────────────────────
# In-process sliding window. Deliberately per-username + peer, not global: a
# runaway script must not lock the operator out of their own dashboard, and
# Lite is single-tenant so one process sees all attempts. A restart clears it,
# which is acceptable — an attacker cannot restart the server, and a permanent
# lockout would be a denial of service against the operator.
_FAILURE_WINDOW_SECONDS = 15 * 60
_MAX_FAILURES = 8
_LOCKOUT_SECONDS = 5 * 60
_failures: dict[str, deque[float]] = defaultdict(deque)
_locked_until: dict[str, float] = {}


def _rate_key(request: Request, username: str) -> str:
    peer = (request.client.host if request.client else "") or "unknown"
    return f"{(username or '').strip().lower()}|{peer}"


def _check_rate_limit(key: str) -> None:
    now = time.monotonic()
    until = _locked_until.get(key)
    if until and until > now:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many failed sign-in attempts. Wait a few minutes and try "
                "again, or reset the password locally with "
                "`python -m app.admin_cli reset-password`."
            ),
        )
    if until and until <= now:
        _locked_until.pop(key, None)
        _failures.pop(key, None)


def _record_failure(key: str) -> None:
    now = time.monotonic()
    window = _failures[key]
    window.append(now)
    while window and now - window[0] > _FAILURE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _MAX_FAILURES:
        _locked_until[key] = now + _LOCKOUT_SECONDS


def _record_success(key: str) -> None:
    _failures.pop(key, None)
    _locked_until.pop(key, None)


def reset_rate_limits() -> None:
    """Test hook — clears in-process counters."""
    _failures.clear()
    _locked_until.clear()


# ── schemas ────────────────────────────────────────────────────────────────


class SetupIn(BaseModel):
    username: str
    password: str
    confirm_password: str
    setup_token: str


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


def _client_ip(request: Request) -> str | None:
    # X-Forwarded-For is only trusted when a proxy is explicitly declared
    # (see settings.trust_proxy_headers); otherwise the socket peer is used.
    from app.config import get_settings

    settings = get_settings()
    if getattr(settings, "trust_proxy_headers", False):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else None)


def _session_payload(record: SessionRecord) -> dict:
    return {
        "authenticated": True,
        "username": record.username,
        "session_id": record.session_id,
        "csrf_token": record.csrf_token,
        "expires_at": record.expires_at.isoformat(),
        "last_seen_at": record.last_seen_at.isoformat(),
    }


# ── endpoints ──────────────────────────────────────────────────────────────


@router.get("/status")
async def auth_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Anonymous, minimal: does an administrator exist yet?

    Deliberately does not echo the username before login — that would hand an
    anonymous caller half the credentials.
    """
    admin = await admin_accounts.get_admin(db)
    return {
        "initialized": admin is not None,
        "password_policy": password_strength_hint(),
    }


@router.post("/setup", status_code=201)
async def setup_administrator(
    body: SetupIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create the one administrator. Requires a CLI-issued bootstrap token."""
    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    try:
        username = validate_username(body.username)
        admin = await admin_accounts.create_admin(
            db,
            username=username,
            password=body.password,
            setup_token=body.setup_token,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except admin_accounts.SetupError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    issued = await create_session(
        db, admin, ip_address=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    set_session_cookies(response, issued, request)
    return {
        "authenticated": True,
        "username": admin.username,
        "csrf_token": issued.csrf_token,
        "expires_at": issued.expires_at.isoformat(),
    }


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    key = _rate_key(request, body.username)
    _check_rate_limit(key)
    try:
        admin = await admin_accounts.authenticate(
            db, username=body.username, password=body.password
        )
    except admin_accounts.LoginError as exc:
        _record_failure(key)
        # Same status, same message, whether the username exists or not.
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    _record_success(key)
    issued = await create_session(
        db, admin, ip_address=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    set_session_cookies(response, issued, request)
    return {
        "authenticated": True,
        "username": admin.username,
        "csrf_token": issued.csrf_token,
        "expires_at": issued.expires_at.isoformat(),
    }


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await revoke_session(db, record.session_id)
    clear_session_cookies(response)
    response.status_code = 204
    return response


@router.get("/me")
async def me(record: SessionRecord = Depends(get_admin_session)) -> dict:
    return _session_payload(record)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordIn,
    record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=422, detail="New passwords do not match.")
    admin = await admin_accounts.get_admin(db)
    if admin is None:  # pragma: no cover - session without account
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        await admin_accounts.change_password(
            db,
            admin,
            current_password=body.current_password,
            new_password=body.new_password,
            # Keep THIS device signed in; every other session is revoked.
            keep_session_id=record.session_id,
        )
    except admin_accounts.LoginError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "Password updated. Other devices have been signed out.",
        "revoked_other_sessions": True,
    }


@router.get("/sessions")
async def list_sessions(
    record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select


    admin = await admin_accounts.get_admin(db)
    if admin is None:  # pragma: no cover
        raise HTTPException(status_code=401, detail="Authentication required")
    rows = (
        await db.execute(
            select(AdminSession)
            .where(
                AdminSession.admin_id == admin.id,
                AdminSession.revoked_at.is_(None),
            )
            .order_by(AdminSession.last_seen_at.desc())
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    out = []
    for row in rows:
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        last_seen = row.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        out.append({
            "id": row.id,
            "current": row.id == record.session_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_seen_at": last_seen.isoformat(),
            "expires_at": expires.isoformat(),
            "expired": expires <= now,
            "ip_address": row.ip_address,
            # Truncated to a browser family: enough to recognize "that was my
            # laptop", not enough to fingerprint.
            "user_agent": (row.user_agent or "")[:120] or None,
        })
    account = await admin_accounts.get_admin(db)
    return {
        "sessions": out,
        "account": {
            "username": account.username if account else None,
            "password_changed_at": (
                account.password_changed_at.isoformat()
                if account and account.password_changed_at else None
            ),
            "password_reset_at": (
                account.password_reset_at.isoformat()
                if account and account.password_reset_at else None
            ),
            "last_login_at": (
                account.last_login_at.isoformat()
                if account and account.last_login_at else None
            ),
            "created_at": account.created_at.isoformat() if account and account.created_at else None,
        },
    }


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    record: SessionRecord = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    admin = await admin_accounts.get_admin(db)
    if admin is None:  # pragma: no cover
        raise HTTPException(status_code=401, detail="Authentication required")
    revoked = await revoke_all_sessions(db, admin.id, except_session_id=record.session_id)
    return {"ok": True, "revoked": revoked}
