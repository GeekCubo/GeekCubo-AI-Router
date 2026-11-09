"""Native-Chat web search settings.

One row per workspace. Search-provider credentials live here (encrypted with
the same key as inference-provider keys) and are kept separate from the
`provider_keys` table: a search key is never usable for inference and vice
versa.

`enabled` off by default: a fresh install has no search dependency at all.
"""

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, TimestampMixin


class ChatSearchSettings(Base, TimestampMixin):
    __tablename__ = "chat_search_settings"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), primary_key=True, nullable=False
    )
    # off | manual | auto
    mode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="off")
    # searxng | brave | tavily; NULL = not configured
    backend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Trusted private service URL for SearXNG (e.g. http://searxng:8080).
    service_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Encrypted Brave/Tavily key; NULL when unset or for SearXNG.
    encrypted_api_key: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    max_searches_per_conversation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    max_results: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    max_page_fetches: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    # Connection probe bookkeeping (same pattern as quality_settings).
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
