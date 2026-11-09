"""Administrator identity and browser-session models.

Three tables, all additive — an upgrade from an existing Lite install only
creates them, never rewrites `api_keys` / `provider_keys` / `custom_providers`.

`AdminAccount` is a hard singleton (`singleton` is UNIQUE and always 1). That
constraint, not application logic, is what makes concurrent first-run setup
requests unable to create two administrators: the loser's INSERT violates the
unique index and its transaction rolls back.

`AdminSession` holds only a SHA-256 *hash* of the opaque cookie value, so a
stolen SQLite file cannot be replayed as a live session. Sessions are
server-side revocable (row deleted/revoked), which is what makes "log out all
other devices" and password-change invalidation real rather than advisory.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class AdminAccount(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """The single local administrator."""

    __tablename__ = "admin_accounts"

    # UNIQUE + always 1 => at most one non-deleted administrator, enforced by
    # the database rather than by a check-then-insert race in the API.
    singleton: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, default=1, server_default="1"
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # Argon2id PHC string ($argon2id$v=19$m=...$salt$hash). Never a plaintext
    # or a fast unsalted digest.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when an operator recovers the password through the local CLI. Shown
    # in Security so a surprise reset is visible rather than silent.
    password_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AdminSession(Base, UUIDMixin, TimestampMixin):
    """A server-side browser session for the administrator."""

    __tablename__ = "admin_sessions"

    admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_accounts.id"), nullable=False, index=True
    )
    # SHA-256 of the cookie secret. The plaintext cookie value exists only in
    # the Set-Cookie response and the operator's browser.
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    # Double-submit CSRF token echoed back in the X-CSRF-Token header. Kept
    # server-side so a forged cookie cannot invent a matching pair.
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "Remember me": a fixed 14-day lifetime from sign-in with no idle limit.
    # False (the default, and every row created before this column existed)
    # keeps the normal 12-hour / 60-minute-idle policy.
    persistent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class SetupToken(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """One-time token authorizing first-run administrator creation.

    Required because the dashboard may be reached through a Docker port
    mapping: the request then arrives from the bridge gateway, so "is the peer
    loopback?" cannot distinguish the operator from anything else behind the
    same NAT. The token is generated when no administrator exists, printed to
    the server log (the same channel that used to carry the first-run
    sk-geek-* key), and consumable exactly once.
    """

    __tablename__ = "admin_setup_tokens"

    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
