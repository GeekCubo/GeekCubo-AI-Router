"""Idempotent startup schema migrations for columns added after the first release.

`Base.metadata.create_all` creates new tables but never alters existing ones, so a
deployment that already ran a release (a SQLite named volume, a fly.io/Postgres
volume) keeps an `api_keys` table without the `spent_microcents` column. After an
upgrade the ORM would then `SELECT` every mapped column and hit "no such column"
on every authenticated request — a 503 for the whole API.

`ensure_budget_columns` runs at boot, after `create_all`, on every start: it
inspects the live schema, only acts where the change is missing, tolerates
another process racing it to the same change, and re-attempts a repair that an
earlier boot applied only halfway.
"""

from __future__ import annotations

import json

from sqlalchemy import BigInteger, inspect, text
from sqlalchemy.exc import DBAPIError

from packages.db.units import MICROCENTS_PER_CENT


def _already_applied(err: DBAPIError) -> bool:
    """Whether a DDL failure means someone else applied the change first."""
    msg = str(err).lower()
    return (
        "already exists" in msg
        or "duplicate column" in msg
        # Concurrent CREATE INDEX on Postgres can lose the race at the catalog
        # insert rather than the IF NOT EXISTS probe, surfacing as a verror on
        # pg_class's unique index instead of the usual "already exists".
        or "pg_class_relname_nsp_index" in msg
    )


async def _apply_ddl(conn, statement: str) -> None:
    """Run one startup DDL statement, tolerating a boot that raced us to it.

    Every worker runs this in its lifespan, so the first boot after an upgrade
    has several processes inspecting a schema none of them has altered yet. Each
    then issues the same statement and all but one fail — "column ... already
    exists" on Postgres, "duplicate column name" on SQLite — which is success
    from here, not a reason to keep the worker from booting. The failure is
    caught inside a SAVEPOINT because on Postgres an error would otherwise abort
    the whole transaction and take the rest of the startup with it.
    """
    try:
        async with conn.begin_nested():
            await conn.execute(text(statement))
    except DBAPIError as err:
        if not _already_applied(err):
            raise


async def ensure_budget_columns(engine) -> None:
    """Make `api_keys.spent_microcents` correct, whatever schema it started from.

    Adds the column when an upgraded volume lacks it, and repairs lifetime spend
    against historical request logs on every boot so the `ALTER` is never mistaken
    for proof that the seed ran. Also widens `budget_limit_cents` to BIGINT on
    Postgres (the column is scaled into microcents for every comparison against
    spend, and an int4 ceiling is about 214,748 dollars of lifetime budget) and
    creates the `ix_requests_log_api_key_spend` index that create_all only builds
    on fresh databases. Each step costs nothing on a database that needs none of
    it — there the repair is a single indexed UPDATE that matches no row.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]: c["type"]
            for c in await conn.run_sync(lambda sync: inspect(sync).get_columns("api_keys"))
        }
        is_postgres = engine.dialect.name == "postgresql"

        # The model declares ix_requests_log_api_key_spend (api_key_id,
        # is_deleted); create_all only builds it on fresh databases, so an
        # upgraded deployment would drift. Built before the seed below, which is
        # a correlated aggregate over requests_log and otherwise full-scans the
        # one table that grows without bound here — once per key, inside the
        # transaction that already holds the api_keys lock. is_deleted has
        # existed since the first release (SoftDeleteMixin), so the index is
        # always creatable.
        idx = {
            i["name"]
            for i in await conn.run_sync(
                lambda sync: inspect(sync).get_indexes("requests_log")
            )
        }
        if "ix_requests_log_api_key_spend" not in idx:
            await _apply_ddl(
                conn,
                "CREATE INDEX IF NOT EXISTS ix_requests_log_api_key_spend "
                "ON requests_log (api_key_id, is_deleted)",
            )

        if "spent_microcents" not in cols:
            await _apply_ddl(
                conn,
                "ALTER TABLE api_keys ADD COLUMN spent_microcents BIGINT "
                "NOT NULL DEFAULT 0",
            )

        # Seed lifetime spend from historical request logs so an existing key's
        # cap is not silently reset to zero (which would re-grant a leaked key
        # a full new budget). Deliberately unfiltered by is_deleted, unlike the
        # analytics reads over the same table: this restores an accrued total,
        # so counting a row a retention job has hidden can only ever make the
        # cap tighter, while honouring the filter would hand a capped key
        # back the spend it was capped for.
        #
        # Not a one-shot `= 0` backfill but a monotonic, cap-clamped repair run
        # every boot: the counter rises to max(current, log total) and is never
        # written past budget_limit_cents scaled to microcents or below its
        # current value. Until #161 wires the per-request charge, request logs
        # are the only recorded spend, so a counter seeded at an earlier boot
        # goes stale as traffic flows and only re-aggregating closes the gap.
        # Afterwards the clamp keeps this a no-op on correct state: a key whose
        # final charge was clamped deliberately under-reports its log total, and
        # raising it back to the SUM would undo the clamp (and overshoot the
        # cap). The strict inequality means a steady-state boot matches no row.
        #
        # It runs beside every ALTER, not only with the column's own, because
        # the ALTER is no record of the seed: on SQLite that DDL is durable the
        # instant it executes while this is DML in the transaction a kill — or
        # the `database is locked` this very aggregate provokes on an upgrade
        # that overlaps the old machine's writes — rolls back, and a gate keyed
        # on the column would then never retry. Capped keys only: an uncapped
        # key is never charged, so its counter stays at zero by design and
        # nothing reads it. The cap is scaled by MICROCENTS_PER_CENT, the same
        # constant the request-path charge uses. GREATEST/LEAST are Postgres;
        # SQLite's scalar MAX/MIN take the same arguments.
        greatest, least = ("GREATEST", "LEAST") if is_postgres else ("MAX", "MIN")
        repaired = (
            f"{least}({greatest}(spent_microcents, ("
            "SELECT CAST(COALESCE(SUM(cost_microcents), 0) AS BIGINT) FROM requests_log "
            "WHERE requests_log.api_key_id = api_keys.id"
            f")), CAST(budget_limit_cents AS BIGINT) * {MICROCENTS_PER_CENT})"
        )
        await conn.execute(
            text(
                f"UPDATE api_keys SET spent_microcents = {repaired} "
                f"WHERE budget_limit_cents IS NOT NULL AND spent_microcents < {repaired}"
            )
        )

        limit_type = cols.get("budget_limit_cents")
        if is_postgres and limit_type is not None and not isinstance(limit_type, BigInteger):
            await _apply_ddl(
                conn, "ALTER TABLE api_keys ALTER COLUMN budget_limit_cents TYPE BIGINT"
            )


async def ensure_custom_provider_columns(engine) -> None:
    """Add columns added to `custom_providers` after its first release.

    `create_all` makes the table on fresh databases but never alters an
    existing one, so a deployment that already ran a release keeps a
    `custom_providers` table without `last_models_fetched_at`. Idempotent and
    additive: each step is a no-op when the column already exists.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]: c["type"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("custom_providers")
            )
        }
        if "last_models_fetched_at" not in cols:
            await _apply_ddl(
                conn,
                "ALTER TABLE custom_providers ADD COLUMN last_models_fetched_at TIMESTAMP",
            )

        model_cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("custom_provider_models")
            )
        }
        additions = {
            "reference_input_cost_per_token": "FLOAT",
            "reference_output_cost_per_token": "FLOAT",
            "reference_cache_read_cost_per_token": "FLOAT",
            "reference_cache_write_cost_per_token": "FLOAT",
            "reference_source": "VARCHAR(80)",
            "metadata_json": "TEXT",
            "is_enabled": "BOOLEAN DEFAULT TRUE",
            "supports_json_schema": "BOOLEAN DEFAULT FALSE",
        }
        for name, ddl_type in additions.items():
            if name not in model_cols:
                await _apply_ddl(
                    conn,
                    f"ALTER TABLE custom_provider_models ADD COLUMN {name} {ddl_type}",
                )


_JSON_CAPABILITY_STATES = {"supported", "unsupported", "unknown"}


async def ensure_json_capability_split(engine) -> None:
    """Split the old single JSON capability into JSON mode and JSON Schema.

    Before the split, one tri-state (`json_mode`) was resolved from catalog
    structured-output flags (`supports_response_schema` / models.dev
    `structured_output`). That flag is evidence about Structured Outputs, so
    catalog-derived states move to `json_schema`; `json_mode` returns to
    unknown because no source reported `json_object` support. Explicit
    administrator overrides stay on JSON mode — that is what the operator
    chose in the UI. Rows without catalog-derived JSON state are untouched,
    and nothing here invents a capability no source reported. Idempotent.
    """
    from sqlalchemy import select

    from packages.db.models.custom_provider import CustomProviderModel

    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                select(
                    CustomProviderModel.id,
                    CustomProviderModel.metadata_json,
                ).where(CustomProviderModel.metadata_json.isnot(None))
            )
        ).all()
    updates: list[tuple[str, bool, bool, str]] = []
    for row_id, raw in rows:
        try:
            meta = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        caps = meta.get("capabilities")
        if not isinstance(caps, dict):
            continue
        old = caps.get("json_mode")
        if not isinstance(old, dict) or old.get("state") not in _JSON_CAPABILITY_STATES:
            continue
        if old.get("source") == "administrator_override" or "json_schema" in caps:
            continue
        moved = {
            "state": old.get("state", "unknown"),
            "source": old.get("source"),
            "stale": bool(old.get("stale")),
            "override": False,
        }
        caps["json_schema"] = moved
        caps["json_mode"] = {"state": "unknown", "source": None, "stale": False, "override": False}
        meta["capabilities"] = caps
        schema_supported = moved["state"] == "supported"
        updates.append((schema_supported, False, json.dumps(meta, separators=(",", ":"), sort_keys=True), row_id))
    if not updates:
        return
    from sqlalchemy import bindparam, update

    async with engine.begin() as conn:
        await conn.execute(
            update(CustomProviderModel)
            .where(CustomProviderModel.id == bindparam("row_id"))
            .values(
                supports_json_schema=bindparam("schema_supported"),
                supports_json_mode=bindparam("mode_supported"),
                metadata_json=bindparam("meta"),
            ),
            [
                {
                    "row_id": row_id,
                    "schema_supported": schema_supported,
                    "mode_supported": mode_supported,
                    "meta": meta,
                }
                for schema_supported, mode_supported, meta, row_id in updates
            ],
        )


async def ensure_auth_columns(engine) -> None:
    """Additive upgrade for the administrator-auth release.

    The three new tables (`admin_accounts`, `admin_sessions`,
    `admin_setup_tokens`) are created by `create_all`, which only ever adds
    missing tables. Changes to existing tables: a nullable
    `api_keys.expires_at` (NULL means "never expires", so every key issued
    before this release keeps working with no data rewrite) and
    `admin_sessions.persistent` (FALSE for every existing session, which keeps
    its original policy). Idempotent — a no-op once the columns exist.

    Nothing here touches `key_hash`, workspace references, allowlists, budgets,
    spend counters, provider credentials or request history.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("api_keys")
            )
        }
        if "expires_at" not in cols:
            await _apply_ddl(
                conn, "ALTER TABLE api_keys ADD COLUMN expires_at TIMESTAMP"
            )
        # Opt-in recoverable keys. NULL for every existing key, which keeps
        # them hash-only exactly as before. BLOB on SQLite, BYTEA on Postgres.
        if "encrypted_secret" not in cols:
            blob = "BYTEA" if conn.dialect.name == "postgresql" else "BLOB"
            await _apply_ddl(
                conn, f"ALTER TABLE api_keys ADD COLUMN encrypted_secret {blob}"
            )

        # "Remember me" sessions. Existing rows default to FALSE, i.e. they keep
        # exactly the policy they were issued under.
        session_cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("admin_sessions")
            )
        }
        if session_cols and "persistent" not in session_cols:
            await _apply_ddl(
                conn,
                "ALTER TABLE admin_sessions ADD COLUMN persistent BOOLEAN NOT NULL DEFAULT FALSE",
            )


async def ensure_routing_columns(engine) -> None:
    """Additive upgrade for the GeekCubo routing release.

    * `routing_config.policy` (JSON, nullable): advanced Auto policy. NULL
      means defaults, which reproduce the previous Auto behaviour exactly.
    * `requests_log` decision columns (all nullable): which candidate Auto
      routed to, the tier/reason, candidate count, escalation and fallback
      flags. Existing rows keep NULLs; nothing is backfilled or rewritten.

    Idempotent: each column is added only when missing.
    """
    json_type = "JSON"
    async with engine.begin() as conn:
        rc_cols = {
            c["name"] for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("routing_config")
            )
        }
        if "policy" not in rc_cols:
            await _apply_ddl(conn, f"ALTER TABLE routing_config ADD COLUMN policy {json_type}")

        rl_cols = {
            c["name"] for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("requests_log")
            )
        }
        additions = {
            "routed_model": "VARCHAR(200)",
            "routing_tier": "VARCHAR(20)",
            "routing_reason": "VARCHAR(255)",
            "candidate_count": "SMALLINT",
            "escalated": "BOOLEAN",
            "fallback_used": "BOOLEAN",
            "attempt_count": "SMALLINT",
            "attempt_errors": "VARCHAR(255)",
            "cost_source": "VARCHAR(30)",
            "pricing_snapshot_json": "TEXT",
        }
        for name, ddl_type in additions.items():
            if name not in rl_cols:
                await _apply_ddl(
                    conn, f"ALTER TABLE requests_log ADD COLUMN {name} {ddl_type}"
                )


async def ensure_quality_columns(engine) -> None:
    """Add columns added to `quality_settings` after it first shipped.

    `create_all` creates the table on a fresh database but never alters an
    existing one, so an install that booted a build where `quality_settings`
    existed without `daily_limit` keeps that narrower table forever. The ORM
    then selects every mapped column and every Quality endpoint fails with
    "no such column: quality_settings.daily_limit" — a 500 on GET
    /v1/quality/key, which is what the dashboard showed.

    Additive and idempotent: the column is nullable with no default, so
    existing rows keep NULL ("limit not recorded") and nothing is rewritten.
    `key_prefix`, `encrypted_api_key` and timestamps are untouched, so stored
    keys and encryption continuity are preserved.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        }
        if "daily_limit" not in cols:
            await _apply_ddl(
                conn, "ALTER TABLE quality_settings ADD COLUMN daily_limit INTEGER"
            )


async def find_schema_drift(engine) -> dict[str, list[str]]:
    """Return {table: [missing columns]} for every ORM column the live DB lacks.

    The `ensure_*` functions above each repair a change someone remembered to
    write a migration for. This catches the ones nobody did: it compares the
    live schema with the ORM after all migrations ran. A non-empty result
    means some endpoint will fail with "no such column" — the exact failure
    mode of quality_settings.daily_limit — so it is reported loudly at boot
    rather than discovered as a 500.
    """
    import packages.db.models  # noqa: F401  (register every table)
    from packages.db.models.base import Base

    def _inspect(sync_conn):
        insp = inspect(sync_conn)
        present_tables = set(insp.get_table_names())
        drift: dict[str, list[str]] = {}
        for table in Base.metadata.sorted_tables:
            if table.name not in present_tables:
                drift[table.name] = ["<table missing>"]
                continue
            live = {c["name"] for c in insp.get_columns(table.name)}
            missing = sorted(c.name for c in table.columns if c.name not in live)
            if missing:
                drift[table.name] = missing
        return drift

    async with engine.connect() as conn:
        return await conn.run_sync(_inspect)


async def ensure_quality_connection_columns(engine) -> None:
    """Add connection-health columns added to `quality_settings` after its key
    storage shipped.

    Same failure mode as `daily_limit`: `create_all` never alters an existing
    table, so an install that booted before the Quality page gained connection
    status would keep a narrower table and 500 on the status endpoint. Each
    column is nullable with no default, added only when missing.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("quality_settings")
            )
        }
        additions = {
            "last_status": "VARCHAR(32)",
            "last_error_code": "VARCHAR(32)",
            "last_error_detail": "TEXT",
            # Sync bookkeeping and connection-test results (separate states).
            "last_sync_raw_count": "INTEGER",
            "last_sync_matched_count": "INTEGER",
            "last_tier": "VARCHAR(32)",
            "last_test_status": "VARCHAR(32)",
            "last_test_detail": "TEXT",
        }
        for name, ddl_type in additions.items():
            if name not in cols:
                await _apply_ddl(
                    conn, f"ALTER TABLE quality_settings ADD COLUMN {name} {ddl_type}"
                )
        for name in ("last_sync_at", "last_error_at", "last_sync_attempt_at",
                     "last_test_at", "last_test_ok_at"):
            if name not in cols:
                await _apply_ddl(
                    conn, f"ALTER TABLE quality_settings ADD COLUMN {name} TIMESTAMP"
                )


async def ensure_chat_columns(engine) -> None:
    """Add columns for the dashboard's native Chat tab.

    `requests_log.request_source` (VARCHAR(20), nullable) marks rows created
    by the dashboard chat so Analytics can distinguish them from SDK/CLI
    traffic. Existing rows keep NULL and are treated as API traffic.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("requests_log")
            )
        }
        if "request_source" not in cols:
            await _apply_ddl(
                conn, "ALTER TABLE requests_log ADD COLUMN request_source VARCHAR(20)"
            )
        message_cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("chat_messages")
            )
        }
        if "seq" not in message_cols:
            await _apply_ddl(
                conn,
                "ALTER TABLE chat_messages ADD COLUMN seq INTEGER NOT NULL DEFAULT 0",
            )


async def ensure_chat_search_columns(engine) -> None:
    """Web-search provenance columns on `chat_messages`.

    `search_backend`/`search_query` record that a retrieval actually happened
    for that message; `citations_json` stores the normalized citation list
    shown next to the assistant reply. NULL = no search ran.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("chat_messages")
            )
        }
        additions = {
            "search_backend": "VARCHAR(20)",
            "search_query": "TEXT",
            "citations_json": "TEXT",
        }
        for name, ddl_type in additions.items():
            if name not in cols:
                await _apply_ddl(
                    conn, f"ALTER TABLE chat_messages ADD COLUMN {name} {ddl_type}"
                )


async def ensure_chat_attachment_columns(engine) -> None:
    """Attachment support on the native chat tables.

    `chat_messages.attachments_json` holds the denormalized display copy of the
    attachments sent with a message. The `chat_attachments` table itself is
    created by `create_all` on fresh databases; this only alters existing
    `chat_messages` tables. Idempotent and additive.
    """
    async with engine.begin() as conn:
        cols = {
            c["name"]
            for c in await conn.run_sync(
                lambda sync: inspect(sync).get_columns("chat_messages")
            )
        }
        if "attachments_json" not in cols:
            await _apply_ddl(
                conn, "ALTER TABLE chat_messages ADD COLUMN attachments_json TEXT"
            )


async def ensure_local_connect_tables(engine) -> None:
    """Local AI Connect tables on databases that predate the feature.

    `create_all` creates ``local_machines`` / ``local_enrollments`` /
    ``local_models`` / ``local_settings`` on a fresh database but an upgraded
    volume already holds a schema snapshot that nothing re-creates tables in.
    Each ``CREATE TABLE ... IF NOT EXISTS`` is additive and costs nothing on a
    database that already has the table, so running this on every boot is safe.
    """
    async with engine.begin() as conn:
        await _apply_ddl(
            conn,
            "CREATE TABLE IF NOT EXISTS local_machines ("
            " id VARCHAR(36) NOT NULL PRIMARY KEY,"
            " display_name VARCHAR(120) NOT NULL,"
            " status VARCHAR(20) NOT NULL DEFAULT 'pending',"
            " credential_hash VARCHAR(64) NOT NULL UNIQUE,"
            " credential_prefix VARCHAR(20) NOT NULL,"
            " hostname VARCHAR(255),"
            " platform VARCHAR(80),"
            " agent_version VARCHAR(40),"
            " adapters_json TEXT,"
            " eligible_for_auto BOOLEAN NOT NULL DEFAULT true,"
            " last_seen_at TIMESTAMP,"
            " approved_at TIMESTAMP,"
            " revoked_at TIMESTAMP,"
            " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " is_deleted SMALLINT NOT NULL DEFAULT 0"
            ")",
        )
        await _apply_ddl(
            conn,
            "CREATE TABLE IF NOT EXISTS local_enrollments ("
            " id VARCHAR(36) NOT NULL PRIMARY KEY,"
            " code_hash VARCHAR(64) NOT NULL UNIQUE,"
            " code_prefix VARCHAR(12) NOT NULL,"
            " display_name VARCHAR(120),"
            " expires_at TIMESTAMP NOT NULL,"
            " consumed_at TIMESTAMP,"
            " machine_id VARCHAR(36),"
            " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " is_deleted SMALLINT NOT NULL DEFAULT 0"
            ")",
        )
        await _apply_ddl(
            conn,
            "CREATE TABLE IF NOT EXISTS local_models ("
            " id VARCHAR(36) NOT NULL PRIMARY KEY,"
            " machine_id VARCHAR(36) NOT NULL,"
            " model_key VARCHAR(200) NOT NULL,"
            " display_name VARCHAR(200) NOT NULL,"
            " adapter VARCHAR(30) NOT NULL,"
            " family VARCHAR(80),"
            " parameter_count VARCHAR(40),"
            " quantization VARCHAR(40),"
            " context_length INTEGER,"
            " supports_tools BOOLEAN DEFAULT false,"
            " supports_vision BOOLEAN DEFAULT false,"
            " supports_json_mode BOOLEAN DEFAULT false,"
            " is_enabled BOOLEAN DEFAULT true,"
            " metadata_json TEXT,"
            " tokens_per_second FLOAT,"
            " last_reported_at TIMESTAMP,"
            " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")",
        )
        await _apply_ddl(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_local_models_machine_id "
            "ON local_models (machine_id)",
        )
        await _apply_ddl(
            conn,
            "CREATE TABLE IF NOT EXISTS local_settings ("
            " workspace_id VARCHAR(36) NOT NULL PRIMARY KEY,"
            " enabled BOOLEAN NOT NULL DEFAULT true,"
            " eligible_for_auto BOOLEAN NOT NULL DEFAULT true,"
            " no_cloud_fallback BOOLEAN NOT NULL DEFAULT false,"
            " created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")",
        )
