"""Routing profiles — named Auto configurations exposed as model ids.

`model="auto"` is a built-in profile and never a database row: it keeps
using `routing_config` so an install that never creates a profile behaves
exactly as it did. A custom profile is a row here, and its `slug` is the
value clients send as `model` (e.g. `"economy"`).

Two invariants this table enforces in the application layer:

* A slug is unique among *live* profiles and can never collide with a
  reserved word (`auto`, protocol names) or a registered model id, so
  `model="x"` is never ambiguous.
* Deleting a profile writes a tombstone (`deleted_slugs`) rather than
  freeing the identifier for silent reuse by an unrelated profile.
"""

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class RoutingProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "routing_profiles"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # Stable, client-facing model id. Renaming this breaks clients, so it is
    # only settable at create time unless the caller passes an explicit
    # `confirm_slug_change`.
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400), nullable=True)

    strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="balanced"
    )
    # Full Auto policy (pools, gating, fallback, escalation, stickiness) plus
    # the profile-only extensions held in `app/routing_profiles.py`
    # (provider/model allowlists, max cost, timeout, preferred model).
    policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    # At most one profile is the default new clients are pointed at. It never
    # changes what `model="auto"` does; it only drives the UI and the
    # integration generator.
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )


class RoutingProfileTombstone(Base, UUIDMixin, TimestampMixin):
    """A slug that was used by a profile which has since been deleted.

    Kept so a new profile cannot silently inherit an identifier that old
    clients are still sending — that would route their traffic somewhere
    they never configured. Creating a profile with a tombstoned slug
    requires `allow_reuse=True`.
    """

    __tablename__ = "routing_profile_tombstones"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
