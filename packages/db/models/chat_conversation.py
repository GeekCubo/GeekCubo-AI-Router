"""Dashboard chat — persisted conversations.

The native Chat tab stores its conversations here. One row per conversation:

* the workspace owns it (Lite is single-workspace, the FK keeps the table
  forward-compatible);
* `selected_model` is the model id (a pinned id, "auto", or a profile slug)
  the operator picked for new messages; per-message resolution is stored on
  the messages;
* soft delete only — "Clear history" follows the same soft-delete path other
  modules use, so an accidental click is recoverable from backups.

Messages live in `chat_messages`; the settings that govern retention and
completions live in `chat_settings`.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ChatConversation(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "chat_conversations"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    # Model the operator selected for this conversation ("auto", a pinned id
    # or a routing-profile slug). Empty string = use the chat default.
    selected_model: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    # System prompt override for this conversation; NULL = use settings.
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ChatMessage(Base, UUIDMixin, SoftDeleteMixin):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Monotonic per-conversation turn number, assigned at insert time.
    # created_at has second granularity and row ids are random UUIDs, so
    # neither can reconstruct play order for messages written in the same
    # second — `seq` is the authoritative ordering.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # "user" | "assistant"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Resolution provenance for assistant messages; NULL for user messages.
    model_requested: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_resolved: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Web-search provenance (native Chat only): set when a retrieval ran for
    # this message. citations_json is the normalized [{id,title,url,...}] list.
    search_backend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    search_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "knowledge" when the turn ran in Ask GeekCubo mode (documentation
    # retrieved and injected); NULL for Normal Chat. Stored on both the user
    # and assistant rows so a reload shows which mode produced an answer.
    chat_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Documentation sources actually retrieved for this answer:
    # [{id,title,heading,reference,path}], plus the docs version.
    knowledge_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Same unit as requests_log: microcents. NULL = not known.
    cost_microcents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Server-side error marker for the retry UI; NULL = success.
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # JSON list of {id,name,kind,mime,size} for attachments sent with this
    # message. The bytes + extracted text live in `chat_attachments`; this is
    # the denormalized display copy so rendering a message is one row read.
    attachments_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChatSettings(Base, TimestampMixin):
    __tablename__ = "chat_settings"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), primary_key=True, nullable=False
    )
    # Default model for new conversations ("auto", pinned id or profile slug).
    default_model: Mapped[str] = mapped_column(String(200), nullable=False, server_default="auto")
    # Default routing profile for new conversations; NULL = none.
    default_profile: Mapped[str | None] = mapped_column(String(80), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # False = conversations are ephemeral; nothing is persisted.
    save_history: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Delete conversations whose last activity is older than this many days.
    # NULL = keep forever.
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # UI-only preferences persisted server-side so they follow the browser
    # session onto other machines of the same operator.
    font_size: Mapped[str] = mapped_column(String(10), nullable=False, server_default="medium")
    enter_to_send: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    privacy_notice_ack: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
