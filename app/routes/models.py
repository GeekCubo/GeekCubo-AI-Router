"""GET /v1/models — model listing.

One path, two protocols. The OpenAI envelope is the default; a request
carrying `anthropic-version` (which the official Anthropic SDK and Claude
Code always send, and no OpenAI client sends) gets the Anthropic envelope
instead, so `client.models.list()` works against the same base URL the
native /v1/messages surface lives on. The Gemini surface has its own
listing at GET /v1beta/models.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_key_context
from packages.auth.types import KeyContext

router = APIRouter(prefix="/v1", tags=["models"])

# Anthropic's ModelInfo.created_at is an RFC 3339 release date. We don't
# track release dates, and the API documents the epoch as the value to
# use when the date is unknown.
_UNKNOWN_RELEASE = "1970-01-01T00:00:00Z"


class _RoutingEntry:
    """A routing id (`auto` or a profile slug) shaped like a catalog model."""

    def __init__(self, slug: str, label: str) -> None:
        self.id = slug
        self.provider = "geekcubo"
        self.label = label


async def _routing_entries(db: AsyncSession, workspace_id: str) -> list[_RoutingEntry]:
    """`auto` plus every enabled routing profile, listed first.

    Clients (OpenCode, Cursor, SDKs) discover selectable ids from this
    endpoint; without these entries a profile works but is invisible.
    Defensive: a failure here must never break the model listing.
    """
    entries = [_RoutingEntry("auto", "GeekCubo Auto")]
    try:
        from app.routing_profiles import live_profiles

        for row in await live_profiles(db, workspace_id, only_enabled=True):
            entries.append(_RoutingEntry(row.slug, f"GeekCubo {row.display_name}"))
    except Exception:
        pass
    return entries


def _anthropic_listing(catalog) -> dict:
    data = [
        {
            "type": "model",
            "id": m.id,
            "display_name": getattr(m, "label", None) or m.id,
            "created_at": _UNKNOWN_RELEASE,
        }
        for m in catalog
    ]
    return {
        "data": data,
        # The whole catalog is returned in one page, so pagination is a
        # constant: nothing follows this page.
        "has_more": False,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
    }


@router.get("/models")
async def list_models(
    request: Request,
    _kc: KeyContext = Depends(get_key_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.custom_providers import merged_catalog

    catalog = await _routing_entries(db, str(_kc.workspace_id)) + list(
        await merged_catalog(db, eligible_only=False)
    )

    if "anthropic-version" in request.headers:
        return _anthropic_listing(catalog)

    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": m.id,
                "object": "model",
                "created": now,
                "owned_by": m.provider,
                "permission": [],
            }
            for m in catalog
        ],
    }
