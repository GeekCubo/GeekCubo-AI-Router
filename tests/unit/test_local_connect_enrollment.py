"""Local AI Connect — enrollment, credentials, approval and liveness.

A machine is only trustworthy through two one-time secrets: the enrollment
code (minted by an administrator, burned on first use) and the per-machine
credential (issued once, stored hashed). These tests pin the lifecycle and the
negative cases that keep a leaked database row from impersonating a machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.local_connect import enrollment


async def _seed_workspace(db):
    from app.seed import seed_initial_state

    await seed_initial_state(db)


# ── enrollment codes ───────────────────────────────────────────────────────


async def test_enrollment_code_is_burned_once(db_session):
    await _seed_workspace(db_session)
    row, code = await enrollment.create_enrollment(
        db_session, display_name="Studio", ttl_minutes=30
    )
    assert code.startswith("lcenr-")
    assert row.code_prefix.endswith(code[-4:])

    consumed, error = await enrollment.consume_enrollment(db_session, code)
    assert error is None
    assert consumed is not None
    assert consumed.consumed_at is not None

    again, error = await enrollment.consume_enrollment(db_session, code)
    assert again is None
    assert "already been used" in error


async def test_unknown_enrollment_code_is_rejected(db_session):
    await _seed_workspace(db_session)
    row, error = await enrollment.consume_enrollment(db_session, "lcenr-not-a-real-code")
    assert row is None
    assert "not recognized" in error


async def test_expired_enrollment_code_is_rejected(db_session):
    await _seed_workspace(db_session)
    row, code = await enrollment.create_enrollment(
        db_session, display_name=None, ttl_minutes=60
    )
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()

    consumed, error = await enrollment.consume_enrollment(db_session, code)
    assert consumed is None
    assert "expired" in error


# ── machine credential lifecycle ───────────────────────────────────────────


async def test_machine_starts_pending_and_credential_authenticates(db_session):
    await _seed_workspace(db_session)
    enrollment_row, code = await enrollment.create_enrollment(
        db_session, display_name="Studio", ttl_minutes=30
    )
    consumed, _ = await enrollment.consume_enrollment(db_session, code)
    machine, credential = await enrollment.create_machine(
        db_session,
        display_name="Studio",
        enrollment=consumed,
        hostname="studio.local",
        platform="darwin",
        agent_version="0.1.0",
        adapters=["ollama", "lmstudio"],
    )

    assert credential.startswith("lc-")
    assert machine.status == enrollment.STATUS_PENDING
    assert consumed.machine_id == machine.id

    found = await enrollment.find_machine_by_credential(db_session, credential)
    assert found is not None
    assert found.id == machine.id

    # The stored material is a hash, never the plaintext credential.
    assert credential not in (machine.credential_hash, machine.credential_prefix)


async def test_unknown_credential_is_rejected(db_session):
    await _seed_workspace(db_session)
    assert await enrollment.find_machine_by_credential(db_session, "lc-nope") is None


async def test_rotate_invalidates_previous_credential(db_session):
    await _seed_workspace(db_session)
    machine, credential = await enrollment.create_machine(
        db_session, display_name="Box", adapters=["ollama"]
    )
    new_credential = await enrollment.rotate_credential(db_session, machine.id)
    assert new_credential is not None
    assert new_credential != credential

    assert await enrollment.find_machine_by_credential(db_session, credential) is None
    assert (
        await enrollment.find_machine_by_credential(db_session, new_credential)
    ).id == machine.id


async def test_revoke_blocks_credential_and_delete_is_soft(db_session):
    await _seed_workspace(db_session)
    machine, credential = await enrollment.create_machine(
        db_session, display_name="Box", adapters=[]
    )
    await enrollment.approve_machine(db_session, machine.id)
    assert machine.status == enrollment.STATUS_APPROVED

    await enrollment.revoke_machine(db_session, machine.id)
    assert machine.status == enrollment.STATUS_REVOKED
    assert await enrollment.find_machine_by_credential(db_session, credential) is None

    deleted = await enrollment.delete_machine(db_session, machine.id)
    assert deleted is True
    assert machine.is_deleted == 1
    assert await enrollment.delete_machine(db_session, machine.id) is False


async def test_approve_unknown_machine_returns_none(db_session):
    await _seed_workspace(db_session)
    assert await enrollment.approve_machine(db_session, "does-not-exist") is None
    assert await enrollment.revoke_machine(db_session, "does-not-exist") is None


# ── liveness ───────────────────────────────────────────────────────────────


def test_machine_online_respects_grace_window():
    from packages.db.models.local_connect import LocalMachine

    machine = LocalMachine(display_name="x", credential_hash="h", credential_prefix="lc-")

    machine.last_seen_at = None
    assert enrollment.machine_online(machine) is False

    machine.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert enrollment.machine_online(machine) is True

    machine.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=100)
    assert enrollment.machine_online(machine) is False


def test_machine_online_treats_naive_datetime_as_utc():
    """SQLite returns naive datetimes; they must not be treated as local time."""
    from packages.db.models.local_connect import LocalMachine

    machine = LocalMachine(display_name="x", credential_hash="h", credential_prefix="lc-")
    naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
    machine.last_seen_at = naive
    assert enrollment.machine_online(machine) is True


async def test_touch_machine_updates_liveness_and_adapters(db_session):
    await _seed_workspace(db_session)
    machine, _ = await enrollment.create_machine(db_session, display_name="Box", adapters=[])
    await enrollment.touch_machine(
        db_session, machine, agent_version="0.2.0", adapters=["ollama", "vllm"]
    )
    assert machine.last_seen_at is not None
    assert machine.agent_version == "0.2.0"
    assert machine.adapters_json == '["ollama", "vllm"]'
