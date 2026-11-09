"""Instance settings that are not provided by environment variables.

Today this holds exactly one thing: the Artificial Analysis API key entered
through the Quality page. It exists because asking an operator to edit `.env`
and restart the container just to enable quality routing is a poor trade --
they are already signed in to the dashboard that shows what the key unlocks.

Storage rules, matching provider credentials:

  * the key is encrypted at rest with the same AES-256-GCM helper as
    `provider_keys`, so a stolen SQLite file does not leak it;
  * only a short masked prefix is ever returned to the browser;
  * the row is per-workspace, so a future multi-workspace build does not have
    to reshape the table.

`env` still works and still wins nothing: the stored key takes precedence, so
an operator who saves a new key in the UI is not silently ignored by a stale
`ARTIFICIAL_ANALYSIS_API_KEY` left in the environment.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base


class QualitySettings(Base):
    __tablename__ = "quality_settings"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), primary_key=True, nullable=False
    )
    # Ciphertext from packages.auth.encryption.encrypt_credential. NULL means
    # "no key stored here"; resolution then falls back to the environment.
    encrypted_api_key: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Masked form for display, e.g. "aa-...f3a9". Never the full key.
    key_prefix: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Requests per rolling 24h that this key is allowed, as reported on the
    # operator's own AA account page. NULL means "not recorded" and the UI
    # falls back to AA's documented 1,000/day for the free data API. It is
    # informational: nothing here enforces a limit, AA does.
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ── connection health (surfaced on the Quality page, never the key) ────
    # Last fetch result for the current key: "live" | "stale-cache" |
    # "stale-db" | "error" (mirrors QualityIndex.source). NULL = never fetched.
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Wall-clock time of the last successful AA sync, for the "last synced"
    # display. NULL = never synced successfully.
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Latest fetch failure, classified into a stable machine-readable code:
    # "invalid_key" | "rate_limited" | "connection_failed". NULL = no error.
    # Never contains the key or any provider response body.
    last_error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Short human-readable reason (no secrets, no upstream payload).
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── benchmark synchronization (separate from connection tests) ─────────
    # Time of the most recent sync attempt, successful or not.
    last_sync_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Counts from the most recent successful sync: models returned by AA and
    # how many matched GeekCubo's catalog.
    last_sync_raw_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_sync_matched_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AA tier that served the last successful request ("free" | "pro" | ...).
    last_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ── connection test (POST /v1/quality/key/test) ────────────────────────
    # "connected" or one of the failure codes. Only a real successful test
    # produces "connected"; a stored key alone never does.
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
