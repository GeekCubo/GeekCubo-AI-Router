"""Upgrade path for the Chat reasoning-effort columns.

Existing installs have chat tables created before the feature; the startup
migration must add the nullable columns (NULL = Default) without touching
existing rows, and be idempotent.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from packages.db.engine import build_engine
from packages.db.migrate import ensure_chat_columns
from packages.db.models.base import Base


async def _columns(engine, table: str) -> set[str]:
    async with engine.connect() as conn:
        return {
            c["name"]
            for c in await conn.run_sync(lambda s: inspect(s).get_columns(table))
        }


async def test_reasoning_columns_added_to_pre_feature_database(tmp_sqlite_url):
    import packages.db.models  # noqa: F401  (register every table)

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Simulate a database created before the feature.
        await conn.execute(text("ALTER TABLE chat_messages DROP COLUMN reasoning_requested"))
        await conn.execute(text("ALTER TABLE chat_messages DROP COLUMN reasoning_effective"))
        await conn.execute(text("ALTER TABLE chat_conversations DROP COLUMN reasoning_effort"))
    assert "reasoning_effort" not in await _columns(engine, "chat_conversations")

    await ensure_chat_columns(engine)
    await ensure_chat_columns(engine)  # idempotent

    assert {"reasoning_requested", "reasoning_effective"} <= await _columns(engine, "chat_messages")
    assert "reasoning_effort" in await _columns(engine, "chat_conversations")
    await engine.dispose()
