"""Audit trail for copying stored API keys.

Every retrieval attempt of a copyable sk-geek-* key is recorded here. It never
stores a secret: only the key id, the masked prefix, the outcome, the browser
session and the client address. Additive table (created by `create_all`).
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, UUIDMixin


class KeyRecoveryAudit(Base, UUIDMixin):
    __tablename__ = "key_recovery_audit"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    # ok | rate_limited | not_active | not_recoverable | decrypt_failed
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    key_prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
