"""Native-Chat web search settings (Settings → Chat → Web Search).

Administrator-session only. Search credentials are encrypted at rest and the
saved key is never returned in full after entry (masked preview only).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_admin_context, get_db
from app.web_search import (
    BACKENDS,
    MAX_PAGE_FETCHES_HARD,
    MAX_RESULTS_HARD,
    MODES,
    SearchError,
    run_search,
)
from packages.auth.encryption import (
    credential_is_decryptable,
    decrypt_credential,
    encrypt_credential,
)
from packages.db.models.chat_search_settings import ChatSearchSettings

router = APIRouter(prefix="/api/chat/search-settings", tags=["chat search"])


class SearchSettingsBody(BaseModel):
    mode: str | None = None                      # off | manual | auto
    backend: str | None = None                   # searxng | brave | tavily
    service_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, max_length=500)   # write-only
    clear_api_key: bool = False
    max_searches_per_conversation: int | None = Field(None, ge=1, le=20)
    max_results: int | None = Field(None, ge=1, le=MAX_RESULTS_HARD)
    max_page_fetches: int | None = Field(None, ge=0, le=MAX_PAGE_FETCHES_HARD)
    timeout_s: int | None = Field(None, ge=3, le=60)


async def load_search_settings(db: AsyncSession, workspace_id: str) -> ChatSearchSettings:
    row = (
        await db.execute(
            select(ChatSearchSettings).where(ChatSearchSettings.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = ChatSearchSettings(workspace_id=workspace_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _settings_out(row: ChatSearchSettings) -> dict:
    has_key = row.encrypted_api_key is not None
    key_state = "unset"
    if has_key:
        key_state = "set" if credential_is_decryptable(row.encrypted_api_key) else "undecryptable"
    return {
        "mode": row.mode,
        "backend": row.backend,
        "service_url": row.service_url,
        "api_key_state": key_state,      # never the key itself
        "max_searches_per_conversation": row.max_searches_per_conversation,
        "max_results": row.max_results,
        "max_page_fetches": row.max_page_fetches,
        "timeout_s": row.timeout_s,
        "last_status": row.last_status,
        "last_error_code": row.last_error_code,
        "last_error_detail": row.last_error_detail,
        "backends": list(BACKENDS),
        "modes": list(MODES),
    }


async def load_search_config(db: AsyncSession, workspace_id: str) -> dict:
    """Runtime config for a search invocation: decrypted key included."""
    row = await load_search_settings(db, workspace_id)
    cfg: dict = {"mode": row.mode, "backend": row.backend, "service_url": row.service_url}
    if row.encrypted_api_key is not None:
        try:
            cfg["api_key"] = decrypt_credential(row.encrypted_api_key)
        except Exception as exc:
            raise SearchError("undecryptable", "The saved search API key cannot be decrypted.") from exc
    cfg.update(
        max_results=row.max_results,
        max_page_fetches=row.max_page_fetches,
        timeout_s=row.timeout_s,
    )
    return cfg


@router.get("")
async def get_search_settings(
    ac=Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return _settings_out(await load_search_settings(db, ac.workspace_id))


@router.put("")
async def put_search_settings(
    body: SearchSettingsBody,
    ac=Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await load_search_settings(db, ac.workspace_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("mode") is not None and data["mode"] not in MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {list(MODES)}.")
    # "auto" is a reserved value: no automatic search planner exists, so
    # accepting it would store a mode that behaves like neither Off nor a
    # real Auto. Refuse switching INTO it; a row that already holds it can
    # still be re-saved unchanged, so existing data is never rewritten.
    if data.get("mode") == "auto" and row.mode != "auto":
        raise HTTPException(
            status_code=422,
            detail="Auto search mode is reserved and not implemented yet. Use 'off' or 'manual'.",
        )
    if data.get("backend") is not None and data["backend"] not in BACKENDS:
        raise HTTPException(status_code=422, detail=f"backend must be one of {list(BACKENDS)}.")
    api_key = data.pop("api_key", None)
    clear_key = data.pop("clear_api_key", False)
    for field, value in data.items():
        if value is not None:
            setattr(row, field, value)
    if clear_key:
        row.encrypted_api_key = None
    elif api_key:
        row.encrypted_api_key = encrypt_credential(api_key.strip())
    # A mode other than off needs a configured backend.
    if row.mode != "off" and not row.backend:
        raise HTTPException(status_code=422, detail="Choose a search backend before enabling search.")
    if (row.backend or data.get("backend")) in ("brave", "tavily") and row.mode != "off":
        if row.encrypted_api_key is None and not api_key:
            raise HTTPException(status_code=422, detail="This backend needs an API key before search can be enabled.")
    if row.mode != "off" and (row.backend or data.get("backend")) == "searxng" and not row.service_url:
        raise HTTPException(status_code=422, detail="SearXNG needs a service URL before search can be enabled.")
    await db.commit()
    return _settings_out(row)


@router.post("/test")
async def test_search_connection(
    ac=Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Probe the configured backend with a harmless query; record the outcome."""
    row = await load_search_settings(db, ac.workspace_id)
    if not row.backend:
        raise HTTPException(status_code=422, detail="No search backend is configured.")
    try:
        cfg = await load_search_config(db, ac.workspace_id)
        outcome = await run_search(
            "geekcubo connection test", cfg,
            max_results=1, max_page_fetches=0, timeout_s=cfg["timeout_s"],
        )
        row.last_status = "connected"
        row.last_error_code = None
        row.last_error_detail = None
        row.last_test_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True, "results": len(outcome.results), "took_ms": outcome.took_ms}
    except SearchError as err:
        row.last_status = "unavailable"
        row.last_error_code = err.code
        row.last_error_detail = err.message
        row.last_test_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": False, "error": err.message, "code": err.code}
