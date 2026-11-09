"""Custom OpenAI-compatible providers — third-party aggregators behind an
OpenAI-format API (Apixo, Venice, OpenRouter, ...).

A custom provider is stored separately from the built-in `provider_keys` table
because it carries more than a single credential: a base URL, an enabled state,
an auto-routing eligibility flag, and a set of models with capabilities and
pricing. The built-in table's single-row-per-provider invariant and env-key
fallback semantics must not be disturbed by this feature.

Model ids are namespaced at the routing layer (`{slug}/{model_id}`) so two
aggregators that both expose `gpt-4o` never collide. The `slug` is the
provider identifier (e.g. `apixo`) and is unique.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class CustomProvider(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "custom_providers"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_custom_providers_slug"),
    )

    # Provider identifier used for model namespacing (`{slug}/{model_id}`).
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    # Human-facing display name (e.g. "Apixo").
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Upstream OpenAI-compatible base URL, e.g. `https://api.example.com/v1`.
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # API key, AES-256-GCM sealed via packages.auth.encryption. Never returned
    # in plaintext by the API.
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Operator explicitly certifies that capabilities + pricing are configured
    # well enough for `model="auto"` to consider this provider's models.
    eligible_for_auto: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Last time `GET /models` was fetched successfully for this provider.
    # Surfaced in the dashboard so the operator knows how stale the catalog is.
    last_models_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CustomProviderModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "custom_provider_models"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "model_id", name="uq_custom_provider_models_provider_model"
        ),
    )

    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("custom_providers.id"), nullable=False, index=True
    )
    # Upstream wire model id (what is sent to the provider), e.g. `gpt-4o`.
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_tools: Mapped[bool] = mapped_column(Boolean, server_default="false")
    supports_vision: Mapped[bool] = mapped_column(Boolean, server_default="false")
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, server_default="false")
    supports_json_schema: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Confirmed custom-provider rates. These are what the provider actually
    # bills and the only rates used for spend accounting. Reference rates are
    # stored separately and never substituted here.
    input_cost_per_token: Mapped[float] = mapped_column(Float, server_default="0")
    output_cost_per_token: Mapped[float] = mapped_column(Float, server_default="0")
    # Reference (original vendor) rates. Estimates only: never treated as
    # confirmed custom-provider billing. NULL means unknown.
    reference_input_cost_per_token: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_output_cost_per_token: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_cache_read_cost_per_token: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_cache_write_cost_per_token: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # JSON provenance: identity match, capability tri-states/overrides, context
    # and reference-price source, custom cache rates, manual-field flags.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Disabled models stay registered (with their configuration) but are not
    # deployed or eligible for Auto until re-enabled.
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
