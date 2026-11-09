"""Model metadata sources — configured catalogs and their last-good cache."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class MetadataSource(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "metadata_sources"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # Stable identifier: "litellm", "models-dev", "portkey", or a custom slug.
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # litellm | models_dev | portkey | custom_models_dev
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    # Lower number = consulted first.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    sync_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    # Optional bearer token for a custom source, encrypted at rest. Sent only
    # to this source's own host — never to anything else.
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Last-known-good normalized entries: {"provider/model": {...}}.
    # Kept on failed refreshes so the data stays usable while flagged stale.
    cache: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
