"""Local AI Connect — enrollment, machine credentials and approval state.

The administrator mints a one-time code in the dashboard. The connector
presents it once, together with a `hello` frame, and receives a per-machine
credential it stores at ``~/.config/geekcubo/connector.json`` (mode 0600).
From then on the credential authenticates every reconnect.

Codes and credentials are stored as SHA-256 hashes; the plaintext exists only
in the response that created it (for a code) or in the `hello_ok` that issued
it (for a credential). A database dump therefore yields neither a usable code
nor a machine credential.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.local_connect import LocalEnrollment, LocalMachine, LocalSettings

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REVOKED = "revoked"

_CODE_PREFIX = "lcenr"
_CRED_PREFIX = "lc"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC for comparisons."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def machine_online(machine: LocalMachine, *, grace_seconds: int = 90) -> bool:
    last = _aware(machine.last_seen_at)
    if last is None:
        return False
    return (_now() - last).total_seconds() <= grace_seconds


# ── settings ───────────────────────────────────────────────────────────────


async def get_settings_row(db: AsyncSession, workspace_id: str) -> LocalSettings:
    """Write-path accessor: inserts the defaults row if the workspace has none."""
    from app.local_connect.catalog import load_local_settings

    return await load_local_settings(db, workspace_id)


# ── enrollment codes ───────────────────────────────────────────────────────


async def create_enrollment(
    db: AsyncSession,
    *,
    display_name: str | None,
    ttl_minutes: int,
) -> tuple[LocalEnrollment, str]:
    """Mint a one-time code. Returns the row and the plaintext code."""
    code = f"{_CODE_PREFIX}-{secrets.token_urlsafe(24)}"
    row = LocalEnrollment(
        code_hash=_hash(code),
        code_prefix=f"{_CODE_PREFIX}-...{code[-4:]}",
        display_name=(display_name or "").strip() or None,
        expires_at=_now() + timedelta(minutes=max(1, int(ttl_minutes))),
    )
    db.add(row)
    await db.flush()
    return row, code


async def consume_enrollment(
    db: AsyncSession, code: str
) -> tuple[LocalEnrollment | None, str | None]:
    """Validate and burn a code. Returns `(row, error)`.

    On success the row is marked consumed but not yet bound to a machine; the
    caller creates the machine and sets ``machine_id``.
    """
    digest = _hash((code or "").strip())
    row = (
        await db.execute(select(LocalEnrollment).where(LocalEnrollment.code_hash == digest))
    ).scalar_one_or_none()
    if row is None or row.is_deleted:
        return None, "enrollment code not recognized"
    if row.consumed_at is not None:
        return None, "enrollment code has already been used"
    expires = _aware(row.expires_at)
    if expires is None or expires <= _now():
        return None, "enrollment code has expired"
    row.consumed_at = _now()
    await db.flush()
    return row, None


# ── machines ───────────────────────────────────────────────────────────────


async def create_machine(
    db: AsyncSession,
    *,
    display_name: str,
    enrollment: LocalEnrollment | None = None,
    hostname: str | None = None,
    platform: str | None = None,
    agent_version: str | None = None,
    adapters: list[str] | None = None,
) -> tuple[LocalMachine, str]:
    """Create a pending machine and its credential. Returns `(row, credential)`."""
    credential = f"{_CRED_PREFIX}-{secrets.token_urlsafe(32)}"
    machine = LocalMachine(
        display_name=display_name.strip()[:120] or "Local machine",
        status=STATUS_PENDING,
        credential_hash=_hash(credential),
        credential_prefix=f"{_CRED_PREFIX}-...{credential[-4:]}",
        hostname=(hostname or None),
        platform=(platform or None),
        agent_version=(agent_version or None),
        adapters_json=json.dumps(sorted(adapters)) if adapters else None,
    )
    db.add(machine)
    await db.flush()
    if enrollment is not None:
        enrollment.machine_id = machine.id
    return machine, credential


async def find_machine_by_credential(db: AsyncSession, credential: str) -> LocalMachine | None:
    digest = _hash((credential or "").strip())
    machine = (
        await db.execute(select(LocalMachine).where(LocalMachine.credential_hash == digest))
    ).scalar_one_or_none()
    if machine is None or machine.is_deleted or machine.status == STATUS_REVOKED:
        return None
    return machine


async def rotate_credential(db: AsyncSession, machine_id: str) -> str | None:
    machine = await db.get(LocalMachine, machine_id)
    if machine is None or machine.is_deleted:
        return None
    credential = f"{_CRED_PREFIX}-{secrets.token_urlsafe(32)}"
    machine.credential_hash = _hash(credential)
    machine.credential_prefix = f"{_CRED_PREFIX}-...{credential[-4:]}"
    await db.flush()
    return credential


async def approve_machine(db: AsyncSession, machine_id: str) -> LocalMachine | None:
    machine = await db.get(LocalMachine, machine_id)
    if machine is None or machine.is_deleted:
        return None
    machine.status = STATUS_APPROVED
    machine.approved_at = _now()
    await db.flush()
    return machine


async def revoke_machine(db: AsyncSession, machine_id: str) -> LocalMachine | None:
    machine = await db.get(LocalMachine, machine_id)
    if machine is None or machine.is_deleted:
        return None
    machine.status = STATUS_REVOKED
    machine.revoked_at = _now()
    await db.flush()
    return machine


async def touch_machine(
    db: AsyncSession,
    machine: LocalMachine,
    *,
    agent_version: str | None = None,
    adapters: list[str] | None = None,
) -> None:
    machine.last_seen_at = _now()
    if agent_version:
        machine.agent_version = agent_version[:40]
    if adapters:
        machine.adapters_json = json.dumps(sorted(set(adapters)))
    await db.flush()


async def delete_machine(db: AsyncSession, machine_id: str) -> bool:
    machine = await db.get(LocalMachine, machine_id)
    if machine is None or machine.is_deleted:
        return False
    machine.is_deleted = 1
    machine.status = STATUS_REVOKED
    machine.revoked_at = _now()
    await db.flush()
    return True
