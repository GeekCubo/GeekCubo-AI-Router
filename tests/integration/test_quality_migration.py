"""Upgrade path for the Quality settings table.

The defect this guards against: `quality_settings` shipped without
`daily_limit`, and the column was added to the model in a later change.
`Base.metadata.create_all` only creates missing TABLES, never alters existing
ones, so every install that had booted the earlier build kept a table the ORM
could no longer select from. The symptom was a 500 on /v1/quality/key with
"no such column: quality_settings.daily_limit", not a startup failure — which
is exactly why it needs a migration test rather than a fresh-database test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from packages.db.engine import build_engine
from packages.db.migrate import ensure_quality_columns

# The table exactly as it existed before `daily_limit` was introduced.
_STORED_PLAINTEXT = "aa-real-value-before-upgrade-123"

_PRE_CHANGE_SCHEMA = [
    # Same shape as the shipped workspaces table (see test_auth_migration).
    """CREATE TABLE workspaces (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) UNIQUE NOT NULL,
        default_model VARCHAR(100) DEFAULT 'gpt-4o-mini',
        default_routing_strategy VARCHAR(20) DEFAULT 'balanced',
        settings_json JSON DEFAULT '{}',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        is_deleted SMALLINT DEFAULT 0 NOT NULL
    )""",
    """CREATE TABLE quality_settings (
        workspace_id VARCHAR(36) PRIMARY KEY,
        encrypted_api_key BLOB,
        key_prefix VARCHAR(40),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )""",
]


async def _make_pre_change_db(url: str) -> bytes:
    """Build the pre-change schema and return the ciphertext actually stored."""
    from packages.auth.encryption import encrypt_credential

    blob = encrypt_credential(_STORED_PLAINTEXT)
    engine = build_engine(url)
    async with engine.begin() as conn:
        for stmt in _PRE_CHANGE_SCHEMA:
            await conn.execute(text(stmt))
        await conn.execute(text(
            "INSERT INTO workspaces (id, name, slug) VALUES ('default','Default','default')"
        ))
        # A key saved by the earlier build must survive the upgrade untouched.
        await conn.execute(
            text(
                "INSERT INTO quality_settings (workspace_id, encrypted_api_key, key_prefix) "
                "VALUES ('default', :blob, 'aa-...f3a9')"
            ),
            {"blob": blob},
        )
    await engine.dispose()
    return blob


async def test_migration_adds_missing_daily_limit(tmp_sqlite_url):
    await _make_pre_change_db(tmp_sqlite_url)

    engine = build_engine(tmp_sqlite_url)
    async with engine.connect() as conn:
        before = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        }
    assert "daily_limit" not in before

    await ensure_quality_columns(engine)

    async with engine.connect() as conn:
        after = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        }
    assert "daily_limit" in after
    await engine.dispose()


async def test_migration_preserves_the_stored_key(tmp_sqlite_url):
    """Encryption continuity: the ciphertext and mask must be byte-identical."""
    original = await _make_pre_change_db(tmp_sqlite_url)
    engine = build_engine(tmp_sqlite_url)
    await ensure_quality_columns(engine)

    async with engine.connect() as conn:
        row = (
            await conn.execute(text(
                "SELECT encrypted_api_key, key_prefix, daily_limit "
                "FROM quality_settings WHERE workspace_id='default'"
            ))
        ).one()
    assert bytes(row[0]) == original
    # Still decryptable after the schema change — the key itself was not touched.
    from packages.auth.encryption import decrypt_credential

    assert decrypt_credential(bytes(row[0])) == "aa-real-value-before-upgrade-123"
    assert row[1] == "aa-...f3a9"
    # New column defaults to NULL = "limit not recorded", no rewrite.
    assert row[2] is None
    await engine.dispose()


async def test_migration_is_idempotent(tmp_sqlite_url):
    """Repeated startup must not fail or duplicate anything."""
    await _make_pre_change_db(tmp_sqlite_url)
    engine = build_engine(tmp_sqlite_url)
    for _ in range(3):
        await ensure_quality_columns(engine)
    async with engine.connect() as conn:
        cols = [
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        ]
    assert cols.count("daily_limit") == 1
    await engine.dispose()


async def test_migration_is_a_noop_on_a_fresh_database(tmp_sqlite_url):
    """create_all already made the full table; the migration must accept that."""
    import packages.db.models  # noqa: F401
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_quality_columns(engine)
    await ensure_quality_columns(engine)

    async with engine.connect() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        }
    assert "daily_limit" in cols
    await engine.dispose()


async def test_quality_key_endpoint_works_after_upgrade(tmp_sqlite_url, monkeypatch):
    """End to end: the 500 becomes a 200 for an upgraded database."""
    from httpx import ASGITransport, AsyncClient

    await _make_pre_change_db(tmp_sqlite_url)
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker

    import packages.db.models  # noqa: F401
    from packages.auth.encryption import decrypt_credential
    from packages.db import session as session_mod
    from packages.db.migrate import (
        ensure_auth_columns,
        ensure_budget_columns,
        ensure_custom_provider_columns,
    )
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Exactly what the lifespan runs, in order.
    await ensure_budget_columns(engine)
    await ensure_custom_provider_columns(engine)
    await ensure_auth_columns(engine)
    await ensure_quality_columns(engine)
    session_mod._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import create_app

    app = create_app()
    # The endpoint requires an admin session; the point of the test is that the
    # query reaches the database instead of exploding on a missing column.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as c:
        r = await c.get("/v1/quality/key")
    # 401 = auth wall reached, i.e. no schema error. A missing column would be
    # a 500 with an OperationalError in the body.
    assert r.status_code in (200, 401), r.text
    if r.status_code == 500:
        pytest.fail(f"schema error survived migration: {r.text}")

    # And the ORM can now select the full row shape.
    async with engine.connect() as conn:
        row = (
            await conn.execute(text(
                "SELECT encrypted_api_key, daily_limit FROM quality_settings"
            ))
        ).one()
    assert decrypt_credential(bytes(row[0])) == _STORED_PLAINTEXT
    assert row[1] is None
    await engine.dispose()
    session_mod._session_factory = None


async def test_drift_check_names_the_missing_column(tmp_sqlite_url):
    """Before the migrations the checker must name every missing column."""
    from packages.db.migrate import find_schema_drift

    await _make_pre_change_db(tmp_sqlite_url)
    engine = build_engine(tmp_sqlite_url)
    drift = await find_schema_drift(engine)
    missing = drift.get("quality_settings") or []
    # The pre-change schema predates daily_limit AND the connection-health
    # columns; the checker reports the whole gap, not just the first one.
    assert "daily_limit" in missing
    assert {"last_status", "last_sync_at", "last_error_code",
            "last_error_at", "last_error_detail"} <= set(missing)
    await engine.dispose()


async def test_full_startup_sequence_leaves_no_drift(tmp_sqlite_url):
    """After create_all + every migration, no ORM column may be missing."""
    import packages.db.models  # noqa: F401
    from packages.db.migrate import (
        ensure_auth_columns,
        ensure_budget_columns,
        ensure_custom_provider_columns,
        ensure_quality_columns,
        ensure_quality_connection_columns,
        ensure_routing_columns,
        find_schema_drift,
    )
    from packages.db.models.base import Base

    await _make_pre_change_db(tmp_sqlite_url)
    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_budget_columns(engine)
    await ensure_custom_provider_columns(engine)
    await ensure_auth_columns(engine)
    await ensure_routing_columns(engine)
    await ensure_quality_columns(engine)
    await ensure_quality_connection_columns(engine)
    assert await find_schema_drift(engine) == {}

    # SQLite's own integrity check after the ALTERs.
    async with engine.connect() as conn:
        result = (await conn.execute(text("PRAGMA integrity_check"))).scalar_one()
    assert result == "ok"
    await engine.dispose()
