"""Local AI Connect — machines the operator runs inference on, at home or in the
office, reached through an outbound WebSocket the connector opens to us.

Four tables:

``local_machines``
    One row per enrolled machine. Holds the machine's display name, the
    approval state, the hashed per-machine credential, and liveness hints the
    dashboard shows (last seen, agent version, adapters found). The plaintext
    credential is generated once at enrollment and only ever returned to the
    connector; we keep a SHA-256 hash so a database read cannot impersonate a
    machine.

``local_enrollments``
    One-time enrollment codes. A code is minted by the administrator, handed to
    the connector via the dashboard (or CLI), and consumed exactly once when the
    connector presents it together with its first `hello`. Stored hashed, with
    an expiry, so a leaked database row does not yield a usable code.

``local_models``
    The model catalog a machine advertises. Replaced wholesale on every
    `models` frame: the connector is the source of truth for what its adapters
    can serve. `model_key` is the adapter-local name (``llama3.1:8b``); the
    routing layer exposes it as ``local/<machine>/<model_key>``.

``local_settings``
    Per-workspace preferences for the feature: whether local machines are
    allowed at all, whether Auto may consider them, and whether a request that
    could be served locally may silently fall back to a cloud provider.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class LocalMachine(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "local_machines"

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Operator-visible state: pending -> approved -> (revoked). A pending
    # machine may hold a WebSocket but cannot serve inference.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    # SHA-256 of the per-machine credential. The plaintext is shown once, at
    # enrollment, and never stored.
    credential_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    credential_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    # Free-form labels the operator sets to pick this machine in routing.
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # JSON list of adapter names the connector reported (ollama, lmstudio, ...).
    adapters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether this machine may contribute models to `model="auto"`.
    eligible_for_auto: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LocalEnrollment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "local_enrollments"

    # SHA-256 of the one-time code. The plaintext is shown once in the wizard.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    code_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    # Optional label the operator associates with the code before a machine
    # shows up; copied onto the machine row when the code is consumed.
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when the code is redeemed. A machine is created at the same moment;
    # the FK lets the dashboard show "enrolled by this code".
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    machine_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("local_machines.id"), nullable=True
    )


class LocalModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "local_models"
    __table_args__ = (
        UniqueConstraint("machine_id", "model_key", name="uq_local_models_machine_key"),
    )

    machine_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("local_machines.id"), nullable=False, index=True
    )
    # Adapter-local identifier, e.g. ``llama3.1:8b`` or ``Qwen2.5-7B-Instruct``.
    model_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Which connector adapter serves it (ollama, lmstudio, vllm, llamacpp,
    # custom). Useful for diagnostics; routing only needs the machine id.
    adapter: Mapped[str] = mapped_column(String(30), nullable=False)
    family: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parameter_count: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantization: Mapped[str | None] = mapped_column(String(40), nullable=True)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_tools: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    supports_vision: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Operator override; NULL = whatever the connector reported. A disabled
    # model stays registered but is not deployed.
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # JSON bag for anything the adapter reported that we do not model yet.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rough speed measured by the connector (tokens/second), surfaced in the UI.
    tokens_per_second: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LocalSettings(Base, TimestampMixin):
    __tablename__ = "local_settings"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), primary_key=True, nullable=False
    )
    # Master switch: when false, no local model is deployed or listed.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # When false, local machines never participate in `model="auto"`; they are
    # still reachable by pinning `local/<machine>/<model>`.
    eligible_for_auto: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # When true, a request that the engine would have sent to a local machine
    # must NOT be retried against a cloud provider if the machine is offline or
    # fails. Keeps private prompts on the operator's hardware.
    no_cloud_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
