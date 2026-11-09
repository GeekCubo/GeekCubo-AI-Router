"""Upgrade path for the JSON mode / JSON Schema capability split.

The defect this guards against: `json_mode` was one tri-state resolved from
catalog structured-output flags (`supports_response_schema`, models.dev
`structured_output`). That flag is Structured-Outputs evidence, so the split
must move catalog-derived JSON state to `json_schema`, return `json_mode` to
unknown, and leave administrator overrides alone. Existing installs keep
stored `metadata_json`, so this needs a migration test on a pre-change
database, not a fresh one.
"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.db.engine import build_engine
from packages.db.migrate import ensure_custom_provider_columns, ensure_json_capability_split
from packages.db.models.base import Base


async def _make_db(tmp_sqlite_url: str):
    import packages.db.models  # noqa: F401  (register every table)
    from packages.db import session as session_mod

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_custom_provider_columns(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory
    return engine, factory


async def _add_provider(factory, slug: str = "apixo") -> str:
    from packages.auth.encryption import encrypt_credential
    from packages.db.models.custom_provider import CustomProvider

    async with factory() as s:
        p = CustomProvider(
            slug=slug, display_name=slug.title(), base_url="https://upstream.test/v1",
            encrypted_key=encrypt_credential("sk-upstream-secret"), key_prefix="sk-up...cret",
        )
        s.add(p)
        await s.commit()
        return p.id


async def _add_model(factory, provider_id: str, *, metadata: dict | None,
                     mode_col: bool = False, schema_col: bool = False,
                     model_id: str = "m1") -> str:
    from packages.db.models.custom_provider import CustomProviderModel

    async with factory() as s:
        m = CustomProviderModel(
            provider_id=provider_id, model_id=model_id, display_name=model_id,
            supports_json_mode=mode_col, supports_json_schema=schema_col,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        s.add(m)
        await s.commit()
        return m.id


async def _get(factory, row_id: str) -> dict:
    from sqlalchemy import text

    from packages.db import session as session_mod

    async with session_mod._session_factory() as s:
        row = (
            await s.execute(text(
                "SELECT metadata_json, supports_json_mode, supports_json_schema "
                "FROM custom_provider_models WHERE id = :id"
            ), {"id": row_id})
        ).one()
    meta = json.loads(row[0]) if row[0] else None
    return {"metadata": meta, "mode_col": bool(row[1]), "schema_col": bool(row[2])}


async def test_catalog_derived_json_state_moves_to_json_schema(tmp_sqlite_url):
    engine, factory = await _make_db(tmp_sqlite_url)
    try:
        pid = await _add_provider(factory)
        row_id = await _add_model(factory, pid, metadata={
            "capabilities": {
                "json_mode": {"state": "supported", "source": "litellm",
                              "stale": False, "override": False},
                "tools": {"state": "supported", "source": "litellm",
                          "stale": False, "override": False},
            },
        }, mode_col=True)
        await ensure_json_capability_split(engine)

        got = await _get(factory, row_id)
        caps = got["metadata"]["capabilities"]
        # Structured-output evidence is JSON-Schema evidence; JSON mode has no
        # source and falls back to unknown.
        assert caps["json_schema"] == {"state": "supported", "source": "litellm",
                                       "stale": False, "override": False}
        assert caps["json_mode"] == {"state": "unknown", "source": None,
                                     "stale": False, "override": False}
        # Non-JSON capabilities are untouched.
        assert caps["tools"]["state"] == "supported"
        assert (got["mode_col"], got["schema_col"]) == (False, True)
    finally:
        from packages.db import session as session_mod

        session_mod._session_factory = None
        await engine.dispose()


async def test_administrator_override_stays_on_json_mode(tmp_sqlite_url):
    engine, factory = await _make_db(tmp_sqlite_url)
    try:
        pid = await _add_provider(factory)
        row_id = await _add_model(factory, pid, metadata={
            "capabilities": {
                "json_mode": {"state": "supported", "source": "administrator_override",
                              "stale": False, "override": True},
            },
        }, mode_col=True)
        await ensure_json_capability_split(engine)

        got = await _get(factory, row_id)
        caps = got["metadata"]["capabilities"]
        assert caps["json_mode"] == {"state": "supported", "source": "administrator_override",
                                     "stale": False, "override": True}
        assert "json_schema" not in caps  # nothing invented
        assert (got["mode_col"], got["schema_col"]) == (True, False)
    finally:
        from packages.db import session as session_mod

        session_mod._session_factory = None
        await engine.dispose()


async def test_rows_without_catalog_json_state_are_untouched(tmp_sqlite_url):
    engine, factory = await _make_db(tmp_sqlite_url)
    try:
        pid = await _add_provider(factory)
        # Column True but never catalog-derived: the operator set it in the
        # UI, so it stays JSON mode — no schema capability is invented.
        bare_col = await _add_model(factory, pid, metadata=None, mode_col=True, model_id="bare")
        # Already-unknown catalog state: nothing to move.
        unknown = await _add_model(factory, pid, metadata={
            "capabilities": {
                "json_mode": {"state": "unknown", "source": None,
                              "stale": False, "override": False},
            },
        }, model_id="unknown")
        # No capabilities at all.
        no_caps = await _add_model(factory, pid, metadata={"custom": {"input_per_million": 1.0}}, model_id="nocaps")
        await ensure_json_capability_split(engine)

        for row_id, expect_schema in ((bare_col, False), (unknown, False), (no_caps, False)):
            got = await _get(factory, row_id)
            assert got["schema_col"] is expect_schema
            if row_id == bare_col:
                assert got["mode_col"] is True
        assert (await _get(factory, unknown))["metadata"]["capabilities"]["json_mode"]["state"] == "unknown"
    finally:
        from packages.db import session as session_mod

        session_mod._session_factory = None
        await engine.dispose()


async def test_json_capability_split_is_idempotent(tmp_sqlite_url):
    engine, factory = await _make_db(tmp_sqlite_url)
    try:
        pid = await _add_provider(factory)
        row_id = await _add_model(factory, pid, metadata={
            "capabilities": {
                "json_mode": {"state": "unsupported", "source": "models-dev",
                              "stale": False, "override": False},
            },
        })
        for _ in range(3):
            await ensure_json_capability_split(engine)
        got = await _get(factory, row_id)
        caps = got["metadata"]["capabilities"]
        assert caps["json_schema"] == {"state": "unsupported", "source": "models-dev",
                                       "stale": False, "override": False}
        assert caps["json_mode"] == {"state": "unknown", "source": None,
                                     "stale": False, "override": False}
        assert (got["mode_col"], got["schema_col"]) == (False, False)
    finally:
        from packages.db import session as session_mod

        session_mod._session_factory = None
        await engine.dispose()
