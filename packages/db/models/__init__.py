"""ORM models — import all so SQLAlchemy + Alembic see them."""

from packages.db.models.admin import AdminAccount, AdminSession, SetupToken
from packages.db.models.api_key import ApiKey
from packages.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from packages.db.models.chat_attachment import ChatAttachment
from packages.db.models.chat_conversation import ChatConversation, ChatMessage, ChatSettings
from packages.db.models.chat_search_settings import ChatSearchSettings
from packages.db.models.custom_provider import CustomProvider, CustomProviderModel
from packages.db.models.local_connect import (
    LocalEnrollment,
    LocalMachine,
    LocalModel,
    LocalSettings,
)
from packages.db.models.metadata_source import MetadataSource
from packages.db.models.provider_key import ProviderKey
from packages.db.models.quality_score_override import QualityScoreOverride
from packages.db.models.quality_score_snapshot import QualityScoreSnapshot
from packages.db.models.quality_settings import QualitySettings
from packages.db.models.request_log import RequestLog
from packages.db.models.routing_config import RoutingConfig
from packages.db.models.routing_profile import RoutingProfile, RoutingProfileTombstone
from packages.db.models.workspace import Workspace

__all__ = [
    "Base",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDMixin",
    "AdminAccount",
    "AdminSession",
    "SetupToken",
    "ApiKey",
    "ChatAttachment",
    "ChatConversation",
    "ChatMessage",
    "ChatSettings",
    "ChatSearchSettings",
    "LocalMachine",
    "LocalEnrollment",
    "LocalModel",
    "LocalSettings",
    "ProviderKey",
    "MetadataSource",
    "CustomProvider",
    "CustomProviderModel",
    "QualitySettings",
    "QualityScoreOverride",
    "QualityScoreSnapshot",
    "RequestLog",
    "RoutingConfig",
    "RoutingProfile",
    "RoutingProfileTombstone",
    "Workspace",
]
