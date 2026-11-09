"""Integration generator API — configuration for client tools.

Model choices come from this installation's real data (`auto`, enabled
routing profiles, registered models). Output never contains a secret: keys
are referenced through `GEEKCUBO_API_KEY`.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import integrations
from app.deps import get_admin_context, get_db
from app.public_endpoint import align_with_public, endpoint_info
from app.routing_profiles import live_profiles
from app.seed import DEFAULT_WORKSPACE_ID

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _validate_base(url: str) -> str:
    """A user-supplied remote URL becomes text in a config file — it is never
    fetched — but it must still be a clean http(s) URL so we don't emit
    something that breaks the generated file's syntax."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="base_url must be a full http(s) URL")
    if any(ch in url for ch in "\"'`\\ \n\r\t<>{}"):
        raise HTTPException(status_code=422, detail="base_url contains characters that are not allowed")
    url = url.rstrip("/")
    while url.endswith("/v1"):
        url = url[: -len("/v1")].rstrip("/")
    # Never emit http:// for a host the operator configured as https://.
    return align_with_public(url + "/v1")


@router.get("/options")
async def options(
    request: Request,
    _kc = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.custom_providers import merged_catalog

    profiles = await live_profiles(db, DEFAULT_WORKSPACE_ID, only_enabled=True)
    deployable_models = []
    try:
        from app import router_cache

        client = await router_cache.get_router(db)
        deployable = {d.model_name for d in getattr(client, "_deployments", []) or []}
        deployable_models = sorted(
            m.id for m in await merged_catalog(db, eligible_only=False) if m.id in deployable
        )
    except Exception:
        deployable_models = []

    # Trusted configuration only; request Host / X-Forwarded-* never decide
    # what a downloadable config file points at.
    ep = endpoint_info(request)
    return {
        "apps": integrations.catalog(),
        "routing_ids": [{"id": "auto", "label": "auto (built-in)"}] + [
            {"id": p.slug, "label": f"{p.slug} — {p.display_name}"} for p in profiles
        ],
        "models": deployable_models[:500],
        "local_base_url": ep["local_api_base_url"],
        # The configured public endpoint (PUBLIC_BASE_URL), or null when unset.
        "public_base_url": ep["public_api_base_url"],
        "default_endpoint": "remote" if ep["public_configured"] else "local",
        "remote_placeholder": "https://your-geekcubo-host/v1",
        "env_key": integrations.ENV_KEY,
    }


@router.get("/endpoint")
async def endpoint(request: Request, _kc = Depends(get_admin_context)) -> dict:
    """The API base URL clients should use, for Settings -> API Keys.

    Contains no credential. Resolved from configuration (PUBLIC_BASE_URL),
    with the loopback address as the fallback.
    """
    return {**endpoint_info(request), "env_key": integrations.ENV_KEY}


@router.get("/config")
async def config(
    app: str = Query(..., max_length=40),
    model: str = Query("auto", max_length=200),
    base_url: str = Query(..., max_length=500),
    variant: str | None = Query(None, max_length=40),
    _kc = Depends(get_admin_context),
) -> dict:
    if any(ch in model for ch in "\"'`\\ \n\r\t<>{}$"):
        raise HTTPException(status_code=422, detail="model contains characters that are not allowed")
    try:
        result = integrations.build(app, base_url=_validate_base(base_url), model=model, variant=variant)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown application '{app}'") from exc
    return result.as_dict()
