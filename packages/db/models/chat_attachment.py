"""Dashboard chat — uploaded attachments.

One row per uploaded file. The bytes live on disk under `storage_name` (a
UUID-based relative path); this table holds the metadata, the detection
verdict and the extracted text so a conversation can be replayed without
re-parsing the original file.

Attachments are scoped to the workspace and optionally bound to a
conversation and message once the operator actually sends them. Files that
were uploaded but never sent are cleaned up by the retention sweep.

Soft delete only, matching the rest of the chat tables; the file on disk is
removed best-effort when the row is deleted.
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ChatAttachment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "chat_attachments"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # NULL until the operator sends the attachment with a message.
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Coarse classification used by the UI and the routing decision:
    # image | document | spreadsheet | text | code | archive | video | audio
    kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default="text")
    mime: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # UUID-based path relative to the configured attachment directory.
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ok | unsupported | failed | pending
    extraction_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_chars: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # JSON blob: dimensions, page count, video duration, extracted frame paths,
    # archive entry list, truncation flags, etc.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
