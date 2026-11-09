"""Request log — append-only log of every chat completion."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, UUIDMixin


class RequestLog(Base, UUIDMixin, SoftDeleteMixin):
    __tablename__ = "requests_log"
    __table_args__ = (
        Index("ix_requests_log_ws_created", "workspace_id", "created_at"),
        Index("ix_requests_log_api_key_spend", "api_key_id", "is_deleted"),
    )

    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    api_key_id: Mapped[str] = mapped_column(String(36), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_requested: Mapped[str] = mapped_column(String(100), nullable=False)
    model_resolved: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    routing_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    fallback_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_microcents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    # Immutable pricing provenance captured at request time. Refreshing or
    # editing a catalog/provider price must never rewrite what this call was
    # estimated to cost. `cost_source` is custom, upstream_litellm,
    # catalog_estimate or unknown.
    cost_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pricing_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_streaming: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Auto-routing decision record. All nullable: pinned requests and every
    # row written before this release leave them empty.
    routed_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    routing_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    routing_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    escalated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fallback_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Where the request came from: NULL/"api" for SDK and CLI traffic,
    # "dashboard_chat" for the dashboard's native Chat tab. Lets Analytics
    # attribute rows without double counting: every request logs once, here.
    request_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Inference fallback record: total upstream attempts for this request and
    # the error types of the ones that failed (e.g. "rate_limit_error,
    # upstream_error"). Failed attempts return no usage, so they carry no
    # billable tokens; the cost on this row is the serving attempt's.
    attempt_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    attempt_errors: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
