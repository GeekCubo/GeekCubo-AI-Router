"""Dashboard Chat — the native chat surface on the admin session.

The Chat tab is a first-party browser client over the SAME inference engine
that serves `/v1/chat/completions`: it calls `execute_chat()` directly, so
routing, fallbacks, prompt cache, cost provenance and the request log are
identical to SDK traffic. Nothing here starts a second inference path.

Auth follows the console's own rules: routes live under `/api/`, which the
policy classifies as ADMIN (session cookie + CSRF). The administrator's
session must never become a portable inference credential, so no API key is
minted or exposed — a synthetic KeyContext scoped to the workspace drives the
engine, and every request it logs carries
`requests_log.request_source = "dashboard_chat"` so Analytics can tell chat
traffic from SDK traffic without double counting anything.

Persistence is optional (`chat_settings.save_history`). When enabled,
conversations and messages land in `chat_conversations` / `chat_messages`;
retention_days prunes stale conversations, and clearing history is an
explicit, confirmed action.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Literal

import anyio
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app._time_util import iso_utc
from app.attachments import service as attachment_service
from app.attachments.types import IMAGE_TOKEN_COST
from app.deps import AdminContext, get_admin_context, get_db
from packages.auth.types import KeyContext
from packages.db.models.chat_attachment import ChatAttachment
from packages.db.models.chat_conversation import (
    ChatConversation,
    ChatMessage,
    ChatSettings,
)
from packages.db.models.request_log import RequestLog

logger = logging.getLogger("geekcubo.dashboard_chat")

router = APIRouter(prefix="/api/chat", tags=["dashboard-chat"])

REQUEST_SOURCE = "dashboard_chat"

SUPPORTED_ROLES = ("user", "assistant")


async def _next_seq(db: AsyncSession, conversation_id: str) -> int:
    """Next per-conversation turn number."""
    row = await db.execute(
        select(func.coalesce(func.max(ChatMessage.seq), 0)).where(
            ChatMessage.conversation_id == conversation_id
        )
    )
    return int(row.scalar_one()) + 1

FONT_SIZES = ("small", "medium", "large")


# ── settings ───────────────────────────────────────────────────────────────


CLEARABLE_FIELDS = (
    "default_model", "default_profile", "system_prompt",
    "temperature", "max_tokens", "retention_days",
)


class ChatSettingsBody(BaseModel):
    default_model: str | None = Field(None, max_length=200)
    default_profile: str | None = Field(None, max_length=80)
    system_prompt: str | None = Field(None, max_length=8000)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=200_000)
    save_history: bool | None = None
    retention_days: int | None = Field(None, ge=1, le=3650)
    font_size: str | None = None
    enter_to_send: bool | None = None
    privacy_notice_ack: bool | None = None
    # Explicit clear list: an omitted field means "leave unchanged", a present
    # non-null value means "set", and naming the field here means "clear the
    # override and inherit the built-in default".
    clear: list[str] = Field(default_factory=list, max_length=16)


async def _load_settings(db: AsyncSession, workspace_id: str) -> ChatSettings:
    row = (
        await db.execute(
            select(ChatSettings).where(ChatSettings.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = ChatSettings(workspace_id=workspace_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _settings_out(row: ChatSettings) -> dict:
    return {
        "default_model": row.default_model or "auto",
        "default_profile": row.default_profile,
        "system_prompt": row.system_prompt,
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "save_history": bool(row.save_history),
        "retention_days": row.retention_days,
        "font_size": row.font_size or "medium",
        "enter_to_send": bool(row.enter_to_send),
        "privacy_notice_ack": bool(row.privacy_notice_ack),
    }


@router.get("/settings")
async def get_chat_settings(
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return _settings_out(await _load_settings(db, ac.workspace_id))


@router.put("/settings")
async def put_chat_settings(
    body: ChatSettingsBody = Body(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert the operator's chat settings. Unknown fields are ignored, so a
    stale client cannot resurrect a newer field back to its old value."""
    row = await _load_settings(db, ac.workspace_id)
    data = body.model_dump(exclude_unset=True, exclude_none=False)
    clear = set(data.pop("clear", []) or [])
    unknown_clear = clear - set(CLEARABLE_FIELDS)
    if unknown_clear:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot clear: {', '.join(sorted(unknown_clear))}.",
        )
    if data.get("font_size") is not None and data["font_size"] not in FONT_SIZES:
        raise HTTPException(status_code=422, detail="font_size must be small, medium or large.")
    if data.get("retention_days") == 0:
        data["retention_days"] = None
    for field, value in data.items():
        if field in clear:
            continue
        if value is not None or field in ("retention_days", "system_prompt", "default_profile"):
            setattr(row, field, value)
    for field in clear:
        setattr(row, field, None)
    await db.commit()
    await db.refresh(row)
    return _settings_out(row)


# ── conversations CRUD ─────────────────────────────────────────────────────


async def _purge_stale_conversations(db: AsyncSession, workspace_id: str, days: int) -> int:
    """Soft-delete conversations idle longer than the retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = (
        await db.execute(
            select(ChatConversation.id).where(
                ChatConversation.workspace_id == workspace_id,
                ChatConversation.is_deleted == 0,
                func.coalesce(ChatConversation.last_message_at, ChatConversation.updated_at) < cutoff,
            )
        )
    ).scalars().all()
    if not stale:
        return 0
    await db.execute(
        update(ChatConversation)
        .where(ChatConversation.id.in_(stale))
        .values(is_deleted=1)
    )
    await db.execute(
        update(ChatMessage)
        .where(ChatMessage.conversation_id.in_(stale))
        .values(is_deleted=1)
    )
    await _purge_conversation_attachments(db, list(stale))
    await db.commit()
    return len(stale)


class ConversationCreateBody(BaseModel):
    title: str | None = Field(None, max_length=200)
    model: str | None = Field(None, max_length=200)


@router.get("/conversations")
async def list_conversations(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await _load_settings(db, ac.workspace_id)
    if settings.retention_days:
        await _purge_stale_conversations(db, ac.workspace_id, settings.retention_days)
    base = select(ChatConversation).where(
        ChatConversation.workspace_id == ac.workspace_id,
        ChatConversation.is_deleted == 0,
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base
            .order_by(ChatConversation.last_message_at.desc().nullslast(), ChatConversation.created_at.desc())
            .offset(offset).limit(limit)
        )
    ).scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "model": r.selected_model,
            "created_at": iso_utc(r.created_at),
            "updated_at": iso_utc(r.updated_at),
            "last_message_at": iso_utc(r.last_message_at) if r.last_message_at else None,
        }
        for r in rows
    ]
    return {"total": total, "offset": offset, "limit": limit, "conversations": items}


@router.post("/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreateBody = Body(default=ConversationCreateBody()),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await _load_settings(db, ac.workspace_id)
    if settings.retention_days:
        await _purge_stale_conversations(db, ac.workspace_id, settings.retention_days)
    row = ChatConversation(
        workspace_id=ac.workspace_id,
        title=(body.title or "")[:200],
        selected_model=(body.model or "")[:200],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _conversation_out(row)


async def _get_live_conversation(
    db: AsyncSession, workspace_id: str, conversation_id: str
) -> ChatConversation:
    row = (
        await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.workspace_id == workspace_id,
                ChatConversation.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return row


def _conversation_out(row: ChatConversation) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "model": row.selected_model,
        "system_prompt": row.system_prompt,
        "reasoning_effort": getattr(row, "reasoning_effort", None),
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
        "last_message_at": iso_utc(row.last_message_at) if row.last_message_at else None,
    }


def _message_out(row: ChatMessage) -> dict:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "model_requested": row.model_requested,
        "model_resolved": row.model_resolved,
        "provider": row.provider,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cost_microcents": row.cost_microcents,
        "cost_source": row.cost_source,
        "error_type": row.error_type,
        "trace_id": row.trace_id,
        "created_at": iso_utc(row.created_at),
        "search_backend": row.search_backend,
        "search_query": row.search_query,
        "citations": json.loads(row.citations_json) if row.citations_json else None,
        "attachments": json.loads(row.attachments_json) if row.attachments_json else None,
        "mode": row.chat_mode or "normal",
        "knowledge": json.loads(row.knowledge_json) if row.knowledge_json else None,
        "reasoning_requested": getattr(row, "reasoning_requested", None),
        "reasoning_effective": getattr(row, "reasoning_effective", None),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    limit: int = Query(300, ge=1, le=1000),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The conversation plus its messages, oldest first, bounded so a very
    long history cannot blow the browser tab."""
    row = await _get_live_conversation(db, ac.workspace_id, conversation_id)
    msgs = (
        await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == row.id,
                ChatMessage.is_deleted == 0,
            )
            .order_by(ChatMessage.seq.desc(), ChatMessage.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    msgs.reverse()  # oldest-first for rendering
    return {"conversation": _conversation_out(row), "messages": [_message_out(m) for m in msgs]}


_REASONING_DEFAULT = "default"


def _reasoning_field(value: Any) -> str | None:
    """Validate a Chat reasoning selection.

    `"default"` (or an empty value) is the Default choice — no parameter is
    sent. Anything else must be a normalized level; an unknown value is a
    422, never silently ignored.
    """
    from app.reasoning import ReasoningError, normalize_effort

    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() == _REASONING_DEFAULT:
        return _REASONING_DEFAULT
    try:
        return normalize_effort(value) or _REASONING_DEFAULT
    except ReasoningError as exc:
        raise ValueError(exc.message) from exc


def _effort_or_none(value: str | None) -> str | None:
    return None if value in (None, _REASONING_DEFAULT) else value


class ConversationPatchBody(BaseModel):
    title: str | None = Field(None, max_length=200)
    model: str | None = Field(None, max_length=200)
    system_prompt: str | None = Field(None, max_length=8000)
    # "default" clears the selection; omitted leaves it unchanged.
    reasoning_effort: str | None = Field(None, max_length=20)

    @field_validator("reasoning_effort")
    @classmethod
    def _check_reasoning(cls, value: Any) -> str | None:
        return _reasoning_field(value)


@router.patch("/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    body: ConversationPatchBody = Body(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _get_live_conversation(db, ac.workspace_id, conversation_id)
    if body.title is not None:
        row.title = body.title[:200]
    if body.model is not None:
        row.selected_model = body.model[:200]
    if body.system_prompt is not None:
        row.system_prompt = body.system_prompt or None
    if body.reasoning_effort is not None:
        row.reasoning_effort = _effort_or_none(body.reasoning_effort)
    await db.commit()
    await db.refresh(row)
    return _conversation_out(row)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete one conversation. The UI confirms before calling; the backend
    soft-deletes so backups still hold the data."""
    row = await _get_live_conversation(db, ac.workspace_id, conversation_id)
    row.is_deleted = 1
    await db.execute(
        update(ChatMessage).where(ChatMessage.conversation_id == row.id).values(is_deleted=1)
    )
    await _purge_conversation_attachments(db, [row.id])
    await db.commit()


class ClearHistoryBody(BaseModel):
    confirm: bool = False


@router.post("/history/clear", status_code=200)
async def clear_history(
    body: ClearHistoryBody = Body(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete every conversation. Requires an explicit client-side confirmation,
    mirrored here by `confirm: true` so a stray call cannot wipe history."""
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Set confirm=true to clear history.")
    rows = (
        await db.execute(
            select(ChatConversation).where(
                ChatConversation.workspace_id == ac.workspace_id,
                ChatConversation.is_deleted == 0,
            )
        )
    ).scalars().all()
    ids = [r.id for r in rows]
    if ids:
        await db.execute(
            update(ChatConversation).where(ChatConversation.id.in_(ids)).values(is_deleted=1)
        )
        await db.execute(
            update(ChatMessage).where(ChatMessage.conversation_id.in_(ids)).values(is_deleted=1)
        )
        await _purge_conversation_attachments(db, ids)
        await db.commit()
    return {"cleared": len(ids)}


# ── completion ─────────────────────────────────────────────────────────────


class SendMessageBody(BaseModel):
    content: str = Field(..., max_length=200_000)
    # Uploaded attachment ids (from POST /api/chat/attachments). A message
    # may consist of attachments alone, so `content` can be empty when at
    # least one id is present.
    attachment_ids: list[str] = Field(default_factory=list, max_length=8)
    model: str | None = Field(None, max_length=200)
    stream: bool = True
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=200_000)
    # Explicit per-message retrieval request. Requires search mode manual/auto
    # in Settings → Chat → Web Search; otherwise it is rejected, not ignored.
    web_search: bool = False
    # "normal" (default) or "knowledge" (Ask GeekCubo: answer from the
    # bundled GeekCubo documentation). Per message, never sticky server-side.
    mode: Literal["normal", "knowledge"] = "normal"
    # Reasoning effort for this message: a level, or "default" for no
    # parameter. Omitted = the conversation's stored choice. The choice is
    # remembered on the conversation so regenerate and reload reuse it.
    reasoning_effort: str | None = Field(None, max_length=20)

    @field_validator("reasoning_effort")
    @classmethod
    def _check_reasoning(cls, value: Any) -> str | None:
        return _reasoning_field(value)


class RegenerateBody(BaseModel):
    """Regenerate sends the SAME stored question again — no `content`.

    The mode comes from the stored question, not from the request, so a
    regenerated answer is produced the same way as the original.
    """
    model: str | None = Field(None, max_length=200)
    stream: bool = True
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=200_000)
    # Omitted = regenerate with the effort the original question used.
    reasoning_effort: str | None = Field(None, max_length=20)

    @field_validator("reasoning_effort")
    @classmethod
    def _check_reasoning(cls, value: Any) -> str | None:
        return _reasoning_field(value)


def _dashboard_key_context(ac: AdminContext) -> KeyContext:
    """A synthetic KeyContext for engine calls made by the administrator.

    `key_id` is a stable tag (not a real API-key row) so the request log can
    carry it; allowlist/budget are None because the administrator is
    unrestricted by definition.
    """
    return KeyContext(
        key_id="dashboard",
        workspace_id=ac.workspace_id,
        name="Dashboard Chat",
        key_type="dashboard",
    )


# Chat history is loaded from the DB up to a generous row cap; how much of it
# is actually SENT to the model is decided per request by the token-aware
# budget trimmer below, using the resolved model's context limit.
HISTORY_LOAD_LIMIT = 500
DEFAULT_CONTEXT_FALLBACK_TOKENS = 16384
CONTEXT_SAFETY_MARGIN = 1.20
CHARS_PER_TOKEN = 4.0
TOKEN_OVERHEAD_PER_MESSAGE = 8


def estimate_tokens(content: str | list[dict] | None) -> int:
    """Conservative token estimate without a tokenizer dependency.

    A real tokenizer is used only if the model registry ships one; otherwise
    this chars/4 heuristic (widely documented for English/code-heavy chat) is
    deliberately pessimistic because the safety margin above shrinks the
    effective budget. Never under-reserve.

    Multimodal content parts are summed: text parts by length, image parts at
    a fixed pessimistic per-image cost so an attachment-heavy turn cannot
    silently overrun the window.
    """
    if not content:
        return 0
    if isinstance(content, list):
        total = 0
        for part in content:
            if not isinstance(part, dict):
                total += 1
                continue
            ptype = part.get("type")
            if ptype in ("image_url", "image", "input_image"):
                total += IMAGE_TOKEN_COST
            else:
                text = part.get("text")
                if isinstance(text, str) and text:
                    total += max(1, int(len(text) / CHARS_PER_TOKEN) + 1)
                else:
                    total += 1
        return total
    return max(1, int(len(content) / CHARS_PER_TOKEN) + 1)


class ContextBudgetError(Exception):
    pass


@dataclass
class HistoryWindow:
    messages: list[dict]
    omitted_count: int
    estimated_tokens: int
    budget_tokens: int
    budget_source: str  # "model" | "fallback"


async def _model_context_window(db: AsyncSession | None, model: str) -> int | None:
    """The model's input window from the same catalog the router uses.

    Custom and Local AI Connect models carry `context_length` on their merged
    catalog entry. Built-in entries leave it unset, so the bundled LiteLLM
    metadata (`max_input_tokens`) the catalog is generated from is consulted
    under the entry's LiteLLM id, then under the raw id.
    """
    if db is not None:
        from app.custom_providers import merged_catalog_by_id

        entry = (await merged_catalog_by_id(db, eligible_only=False)).get(model)
    else:
        from packages.litellm_adapter.catalog import CATALOG_BY_ID

        entry = CATALOG_BY_ID.get(model)
    ctx = getattr(entry, "context_length", None)
    if isinstance(ctx, int) and ctx > 0:
        return ctx
    import litellm

    cost_map = getattr(litellm, "model_cost", None) or {}
    keys = [model]
    if entry is not None:
        keys.insert(0, f"{entry.litellm_prefix}{entry.id}")
    for key in keys:
        meta = cost_map.get(key)
        value = meta.get("max_input_tokens") if isinstance(meta, dict) else None
        if isinstance(value, int) and value > 0:
            return value
    return None


async def _context_budget_for(
    model: str | None, db: AsyncSession | None = None
) -> tuple[int, str]:
    """Effective context budget in tokens for the resolved (or requested) model."""
    if model and model != "auto":
        try:
            window = await _model_context_window(db, model)
        except Exception:
            window = None
        if window:
            return window, "model"
    return DEFAULT_CONTEXT_FALLBACK_TOKENS, "fallback"


async def _trim_history_to_budget(
    conversation_model: str | None,
    history: list[dict],
    system_prompt: str | None,
    max_output: int | None,
    explicit_context_tokens: int | None,
    *,
    db: AsyncSession | None = None,
) -> HistoryWindow:
    """Select a token-bounded history window, newest-first eviction.

    Rules: preserve the latest user message and system instructions; evict
    from the OLDEST end so message pairs stay intact as much as possible
    (chat protocol pairs start at user turns); never claim omitted messages
    were sent — the omission count is surfaced to the client.
    """
    budget, source = (
        await _context_budget_for(conversation_model, db)
        if db is not None
        else await _context_budget_for(conversation_model)
    )
    if explicit_context_tokens:
        budget = min(budget, explicit_context_tokens)
    budget = int(budget / CONTEXT_SAFETY_MARGIN)
    reserve_output = max_output if max_output else 2048
    budget -= reserve_output

    sys_tokens = estimate_tokens(system_prompt) if system_prompt else 0
    budget -= sys_tokens
    if budget <= 0:
        raise ContextBudgetError("system prompt plus reserved output exceeds the context budget")

    costs = [estimate_tokens(m.get("content")) + TOKEN_OVERHEAD_PER_MESSAGE for m in history]
    total = sum(costs)
    if total <= budget:
        return HistoryWindow(list(history), 0, total + sys_tokens, budget + reserve_output + sys_tokens, source)

    # Drop from the oldest end; align to a user-role boundary so we never
    # start the window mid-pair with a dangling assistant reply.
    start = 0
    while total > budget and start < len(history) - 1:
        total -= costs[start]
        start += 1
    while start < len(history) - 1 and history[start].get("role") != "user":
        total -= costs[start]
        start += 1
    if start >= len(history) or total > budget:
        raise ContextBudgetError("the latest message alone does not fit the context budget")
    window = history[start:]
    return HistoryWindow(window, start, total + sys_tokens, budget + reserve_output + sys_tokens, source)



def _attachment_refs(row: ChatMessage) -> list[dict]:
    if not row.attachments_json:
        return []
    try:
        data = json.loads(row.attachments_json)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _model_accepts_images(db: AsyncSession, model: str | None) -> bool:
    """Whether the selected model can be sent image parts.

    Auto and profile requests are resolved later by the engine, which already
    requires vision when image parts are present — so they always accept
    them. A pinned model is checked against the catalog; an unknown pinned id
    is treated as text-only (the safe default) rather than risking an
    upstream rejection.
    """
    if not model or model == "auto" or "/" not in model:
        # "auto", a profile slug, or an unknown alias: the engine's own
        # capability gate decides.
        return True
    from app.custom_providers import merged_catalog_by_id

    try:
        catalog = await merged_catalog_by_id(db, eligible_only=False)
    except Exception:
        return False
    entry = catalog.get(model)
    return bool(entry and entry.supports_vision)


async def _purge_conversation_attachments(
    db: AsyncSession, conversation_ids: list[str]
) -> None:
    """Mark attachments deleted and remove their files from disk."""
    if not conversation_ids:
        return
    rows = (
        await db.execute(
            select(ChatAttachment).where(
                ChatAttachment.conversation_id.in_(conversation_ids),
                ChatAttachment.is_deleted == 0,
            )
        )
    ).scalars().all()
    for row in rows:
        attachment_service.storage.delete(row.storage_name)
        row.is_deleted = 1


def _attachment_marker(refs: list[dict]) -> str:
    names = [str(ref.get("name") or "file") for ref in refs]
    return "[attached: " + ", ".join(names) + "]"


async def _attachment_rows(db: AsyncSession, refs: list[dict]) -> list[ChatAttachment]:
    ids = [str(ref.get("id")) for ref in refs if ref.get("id")]
    if not ids:
        return []
    rows = (
        await db.execute(
            select(ChatAttachment).where(
                ChatAttachment.id.in_(ids),
                ChatAttachment.is_deleted == 0,
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    return [by_id[i] for i in ids if i in by_id]


async def _history_messages(
    db: AsyncSession,
    conversation: ChatConversation,
    *,
    multimodal_last_user: bool = False,
    allow_images: bool = True,
) -> list[dict]:
    """Replay history for the engine.

    Older turns carry a textual `[attached: ...]` marker instead of the
    original image bytes: re-sending every historical image would multiply
    cost and latency without helping the current turn. With
    `multimodal_last_user`, the newest user message is rebuilt with its real
    content parts (used by regenerate, where the question is already stored).
    """
    rows = (
        await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation.id,
                ChatMessage.is_deleted == 0,
            )
            .order_by(ChatMessage.seq.desc(), ChatMessage.created_at.desc())
            .limit(HISTORY_LOAD_LIMIT)
        )
    ).scalars().all()
    rows.reverse()
    live = [r for r in rows if r.role in SUPPORTED_ROLES]
    last_user_index = None
    if multimodal_last_user:
        for index in range(len(live) - 1, -1, -1):
            if live[index].role == "user":
                last_user_index = index
                break
    out: list[dict] = []
    for index, row in enumerate(live):
        refs = _attachment_refs(row)
        if row.role == "user" and refs:
            if index == last_user_index:
                rows_for_msg = await _attachment_rows(db, refs)
                content, _notices = attachment_service.build_user_content(
                    row.content, rows_for_msg, allow_images=allow_images
                )
                out.append({"role": "user", "content": content})
                continue
            content = (row.content + "\n\n" + _attachment_marker(refs)).strip()
            out.append({"role": "user", "content": content})
            continue
        out.append({"role": row.role, "content": row.content})
    return out


class CompletionResult:
    """What the caller needs after the engine responded (or was cut off)."""

    def __init__(self) -> None:
        self.content = ""
        self.model_resolved: str | None = None
        self.provider: str | None = None
        self.trace_id: str | None = None
        self.usage: dict = {}
        self.error_type: str | None = None
        self.reasoning_requested: str | None = None
        self.reasoning_effective: str | None = None


def _parse_sse_frame(payload: str, out: CompletionResult) -> None:
    """Accumulate one OpenAI SSE data frame into `out`."""
    if payload == "[DONE]":
        return
    try:
        obj = json.loads(payload)
    except ValueError:
        return
    if isinstance(obj.get("error"), dict):
        err = obj["error"]
        out.error_type = str(err.get("type") or "upstream_error")
        return
    choices = obj.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, str) and piece:
            out.content += piece
    if obj.get("model"):
        out.model_resolved = str(obj["model"])
    if isinstance(obj.get("usage"), dict):
        out.usage = obj["usage"]


def _window_payload(window: HistoryWindow) -> dict:
    """Public shape of the context window, mirrored by the response headers."""
    return {
        "estimated_tokens": window.estimated_tokens,
        "budget_tokens": window.budget_tokens,
        "omitted_count": window.omitted_count,
        "budget_source": window.budget_source,
    }

def _attachment_headers(notices: list[str]) -> dict[str, str]:
    """Surface attachment degradation on the streaming path.

    The SSE body belongs to the provider and cannot carry GeekCubo metadata,
    so a "this model cannot read images" notice rides on a header that the UI
    renders as a banner. Notices are UTF-8 safe; headers are latin-1, so any
    non-encodable text is dropped rather than raising.

    Keep in sync with `Access-Control-Expose-Headers` in `_context_headers`.
    """
    if not notices:
        return {}
    try:
        joined = " | ".join(notices)
        joined.encode("latin-1")
    except UnicodeEncodeError:
        return {}
    return {
        "x-geek-attachment-notes": joined,
        "Access-Control-Expose-Headers": (
            "x-geek-context-tokens, x-geek-context-budget, "
            "x-geek-context-omitted, x-geek-context-source, "
            "x-geek-attachment-notes"
        ),
    }


def _context_headers(window: HistoryWindow | None) -> dict[str, str]:
    """Describe the selected history window so the UI can report trimming.

    The chat body is provider SSE and cannot carry GeekCubo metadata, so the
    window facts ride on response headers instead. Omitted messages are real
    (they were not sent upstream) and the operator deserves to see that.
    """
    if window is None:
        return {}
    return {
        "x-geek-context-tokens": str(window.estimated_tokens),
        "x-geek-context-budget": str(window.budget_tokens),
        "x-geek-context-omitted": str(window.omitted_count),
        "x-geek-context-source": window.budget_source,
        "Access-Control-Expose-Headers": (
            "x-geek-context-tokens, x-geek-context-budget, "
            "x-geek-context-omitted, x-geek-context-source"
        ),
    }

async def _proxy_engine_stream(
    inner: StreamingResponse,
    *,
    on_done: "Any",
    trace_id: str,
    extra_headers: dict[str, str] | None = None,
) -> StreamingResponse:
    """Relay the engine's [OI] SSE frames to the browser, accumulate the
    assistant text + usage, and persist the message when the stream ends —
    success, upstream error, or client abort (partial text is kept)."""

    async def relay() -> AsyncIterator[Any]:
        out = CompletionResult()
        buffer = b""
        done = False
        try:
            async for chunk in inner.body_iterator:
                data = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8")
                buffer += data
                while True:
                    sep = buffer.find(b"\n\n")
                    if sep < 0:
                        break
                    frame = buffer[:sep]
                    buffer = buffer[sep + 2:]
                    line = frame.decode("utf-8", "replace")
                    if line.startswith("data: "):
                        if line[6:] == "[DONE]":
                            done = True
                        else:
                            _parse_sse_frame(line[6:], out)
                yield data
        finally:
            if not done and out.error_type is None and out.content:
                # The client vanished mid-stream; keep the partial answer.
                out.error_type = "aborted"
            # A browser abort (Stop button, closed tab) reaches us as
            # cancellation of this generator's task. Unshielded, the first
            # await below would be cancelled too and the partial answer would
            # be lost. Shield both steps, exactly as the engine's sse() does:
            # close the engine stream first so it records its own 499 row and
            # stops pulling upstream tokens, then persist the message.
            with anyio.CancelScope(shield=True):
                aclose = getattr(inner.body_iterator, "aclose", None)
                if aclose is not None:
                    try:
                        await aclose()
                    except Exception:
                        logger.debug("chat_engine_stream_close_failed", exc_info=True)
                try:
                    out.trace_id = trace_id
                    await on_done(out)
                except Exception:
                    logger.warning("chat_message_persist_failed", exc_info=True)

    headers = dict(inner.headers or {})
    if extra_headers:
        headers.update(extra_headers)
    return StreamingResponse(
        relay(),
        media_type=inner.media_type,
        headers=headers,
    )


async def _latest_dashboard_log(db: AsyncSession, workspace_id: str, trace_id: str | None):
    return (
        await db.execute(
            select(RequestLog)
            .where(
                RequestLog.request_source == REQUEST_SOURCE,
                RequestLog.workspace_id == workspace_id,
                RequestLog.trace_id == trace_id,
            )
            .order_by(RequestLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _persist_assistant_message(
    db: AsyncSession,
    *,
    conversation_id: str,
    workspace_id: str,
    result: CompletionResult,
    requested_model: str,
    search_state: dict | None = None,
    knowledge_state: dict | None = None,
) -> dict:
    """Write the assistant row after the engine call finished.

    The engine may leave the shared session with an uncommitted log write
    (aborted client, upstream error), so roll back first — the user's row and
    the engine's committed work are already durable. The conversation's
    `last_message_at` goes through an UPDATE statement, because the rollback
    expired the ORM instance and attribute access would try sync IO.
    """
    try:
        await db.rollback()
    except Exception:
        pass
    usage = result.usage or {}
    # Cost/auth provenance comes from the engine's own RequestLog row —
    # captured at request time, so it matches Analytics exactly.
    log_row = await _latest_dashboard_log(db, workspace_id, result.trace_id)
    provider = (
        result.provider
        if result.provider and result.provider != "unknown"
        else (log_row.provider if log_row else None)
    )
    trace_id = result.trace_id or (log_row.trace_id if log_row else None)
    cost_microcents = log_row.cost_microcents if log_row else None
    cost_source = log_row.cost_source if log_row else None
    input_tokens = int(usage.get("prompt_tokens") or 0) or (
        log_row.input_tokens if log_row else None
    )
    output_tokens = int(usage.get("completion_tokens") or 0) or (
        log_row.output_tokens if log_row else None
    )
    row = ChatMessage(
        conversation_id=conversation_id,
        seq=await _next_seq(db, conversation_id),
        role="assistant",
        content=result.content,
        model_requested=requested_model or None,
        model_resolved=result.model_resolved,
        provider=provider,
        trace_id=trace_id,
        input_tokens=input_tokens or None,
        output_tokens=output_tokens or None,
        cost_microcents=cost_microcents or None,
        cost_source=cost_source,
        error_type=result.error_type,
        search_backend=(search_state or {}).get("backend"),
        search_query=(search_state or {}).get("query"),
        citations_json=(
            json.dumps(search_state["citations"])
            if (search_state or {}).get("citations") else None
        ),
        chat_mode="knowledge" if knowledge_state else None,
        knowledge_json=json.dumps(knowledge_state, separators=(",", ":")) if knowledge_state else None,
        reasoning_requested=result.reasoning_requested,
        reasoning_effective=result.reasoning_effective,
    )
    db.add(row)
    await db.execute(
        update(ChatConversation)
        .where(ChatConversation.id == conversation_id)
        .values(last_message_at=datetime.now(timezone.utc))
    )
    try:
        await db.commit()
        await db.refresh(row)
        return _message_out(row)
    except Exception:
        logger.warning("chat_message_persist_failed", exc_info=True)
        await db.rollback()
        return _message_out(row)


async def _run_engine(
    *,
    db: AsyncSession,
    ac: AdminContext,
    model: str,
    messages: list[dict],
    stream: bool,
    temperature: float | None,
    max_tokens: int | None,
    trace_id: str,
    reasoning_effort: str | None = None,
):
    """Build the OpenAI request and run the shared engine.

    Returns (response, body_used). Raises HTTPException on pre-stream errors.
    """
    from app.routes.chat import ChatCompletionRequest, execute_chat

    payload: dict = {"model": model, "messages": messages, "stream": stream}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if reasoning_effort is not None:
        # Same field an API client sends; the engine validates it against the
        # selected model (or the Auto pool) and translates it per provider.
        payload["reasoning_effort"] = reasoning_effort
    engine_body = ChatCompletionRequest(**payload)
    return await execute_chat(
        engine_body,
        _dashboard_key_context(ac),
        db,
        request_source=REQUEST_SOURCE,
        trace_id=trace_id,
    )


def _conversation_effort(body_value: str | None, conversation: ChatConversation) -> str | None:
    """The effort to send: this request's choice, else the conversation's.

    Mirrors model selection — the request wins, the conversation's stored
    selection is the fallback. Default (None) sends no parameter at all.
    """
    if body_value is not None:
        return _effort_or_none(body_value)
    return getattr(conversation, "reasoning_effort", None)


def _reasoning_from_headers(response: Any, out: CompletionResult) -> None:
    """Copy the engine's requested/effective effort onto the result."""
    headers = getattr(response, "headers", None) or {}
    out.reasoning_requested = headers.get("x-geek-reasoning-requested")
    out.reasoning_effective = headers.get("x-geek-reasoning-effective")


def _blocking_result(response: JSONResponse) -> CompletionResult:
    out = CompletionResult()
    data = json.loads(response.body)
    if isinstance(data.get("error"), dict):
        out.error_type = str(data["error"].get("type") or "upstream_error")
        return out
    choices = data.get("choices") or []
    if choices:
        out.content = str(choices[0].get("message", {}).get("content") or "")
    out.model_resolved = data.get("model")
    out.usage = data.get("usage") or {}
    meta = data.get("_geekcubo_meta") or {}
    out.provider = meta.get("provider")
    out.trace_id = meta.get("trace_id")
    return out


# ── Ask GeekCubo ────────────────────────────────────────────────────────────

def _join_system(system_prompt: str | None, knowledge_block: str | None) -> str | None:
    """Combined system text, for context-budget accounting only."""
    parts = [p for p in (system_prompt, knowledge_block) if p]
    return "\n\n".join(parts) if parts else None


def _system_messages(system_prompt: str | None, knowledge_block: str | None) -> list[dict]:
    """The operator's system prompt first, the documentation block as its own
    separate system message, so retrieved text never merges into (or
    impersonates) the operator's instructions."""
    out: list[dict] = []
    if system_prompt:
        out.append({"role": "system", "content": system_prompt})
    if knowledge_block:
        guide, separator, excerpts = knowledge_block.partition("<geekcubo_documentation>")
        out.append({"role": "system", "content": guide})
        if separator:
            # Retrieved document text never receives system-level authority.
            out.append({"role": "user", "content": separator + excerpts})
    return out


async def _previous_knowledge_question(
    db: AsyncSession, conversation_id: str, *, before_seq: int | None = None
) -> str | None:
    """The most recent earlier question asked in Ask GeekCubo mode, if any."""
    q = select(ChatMessage.content).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.is_deleted == 0,
        ChatMessage.role == "user",
        ChatMessage.chat_mode == "knowledge",
    )
    if before_seq is not None:
        q = q.where(ChatMessage.seq < before_seq)
    return (await db.execute(q.order_by(ChatMessage.seq.desc()).limit(1))).scalar_one_or_none()


async def _knowledge_for(question: str, previous_question: str | None) -> tuple[dict, str | None]:
    """Run retrieval for one Ask GeekCubo turn (off the event loop)."""
    import asyncio

    from app.knowledge_chat import build_context, knowledge_enabled

    if not knowledge_enabled():
        raise HTTPException(
            status_code=422,
            detail="Ask GeekCubo is turned off on this server (KNOWLEDGE_ENABLED=false).",
        )
    ctx = await asyncio.to_thread(build_context, question, previous_question)
    if not ctx.available:
        # Never let a plain answer pass as documentation-grounded.
        raise HTTPException(
            status_code=503,
            detail=f"Ask GeekCubo is unavailable: {ctx.error} Switch to Normal Chat to continue.",
        )
    state = {
        "docs_version": ctx.docs_version,
        "query": ctx.query,
        "sources": ctx.sources,
        "matched": bool(ctx.sources),
    }
    return state, ctx.system_block


def _knowledge_headers(state: dict) -> dict[str, str]:
    import base64

    return {
        "x-geek-knowledge-sources": str(len(state.get("sources") or [])),
        "x-geek-knowledge-version": str(state.get("docs_version") or ""),
        "x-geek-knowledge-context": base64.b64encode(
            json.dumps(state, ensure_ascii=True, separators=(",", ":")).encode()
        ).decode(),
    }


@router.get("/knowledge/status")
async def knowledge_status(_ac: AdminContext = Depends(get_admin_context)) -> dict:
    """Whether Ask GeekCubo can be offered, and which docs it answers from."""
    import asyncio

    from app.knowledge_chat import knowledge_enabled
    from geekcubo_knowledge.service import KnowledgeUnavailable, get_service

    if not knowledge_enabled():
        return {"enabled": False, "available": False, "reason": "disabled"}
    try:
        v = await asyncio.to_thread(lambda: get_service().version())
    except KnowledgeUnavailable as err:
        return {"enabled": True, "available": False, "reason": str(err)}
    return {"enabled": True, "available": True, **v}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessageBody = Body(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
):
    """Append the user's message and stream (or return) the assistant reply.

    Streaming proxies the engine's own OpenAI SSE frames unmodified, so the
    browser parses exactly what an SDK would. Usage arrives on the final
    chunk because the engine auto-injects `stream_options.include_usage`.
    """
    conversation = await _get_live_conversation(db, ac.workspace_id, conversation_id)
    settings = await _load_settings(db, ac.workspace_id)
    model = body.model or conversation.selected_model or settings.default_model or "auto"
    reasoning_effort = _conversation_effort(body.reasoning_effort, conversation)

    from app.routes.chat_attachments import attachments_by_ids

    attachment_rows = await attachments_by_ids(db, ac.workspace_id, body.attachment_ids)
    if not body.content.strip() and not attachment_rows:
        raise HTTPException(status_code=422, detail="Write a message or attach a file.")
    attachment_refs = attachment_service.display_refs(attachment_rows)

    # System prompt: the conversation override wins over the global one.
    system_prompt = conversation.system_prompt if conversation.system_prompt is not None else settings.system_prompt
    eff_max = body.max_tokens if body.max_tokens else settings.max_tokens

    # Optional web search: explicitly requested on this message. Server-side
    # retrieval works for any model — the context block is injected as an
    # extra system message, so models without tool calling can still answer
    # with citations.
    search_state: dict = {"ran": False, "citations": None, "backend": None, "query": None}
    if body.web_search:
        from app.routes.chat_search import load_search_settings
        from app.web_search import SearchError, citations_payload, render_context_block, run_search

        search_row = await load_search_settings(db, ac.workspace_id)
        if search_row.mode == "off" or not search_row.backend:
            raise HTTPException(
                status_code=422,
                detail="Web search is off. Enable it in Settings → Chat → Web Search.",
            )
        used = (
            await db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.conversation_id == conversation.id,
                    ChatMessage.search_backend.is_not(None),
                )
            )
        ).scalar_one()
        if used >= search_row.max_searches_per_conversation:
            raise HTTPException(
                status_code=422,
                detail=f"Search limit reached for this conversation ({search_row.max_searches_per_conversation}).",
            )
        try:
            cfg = {
                "backend": search_row.backend,
                "service_url": search_row.service_url,
            }
            if search_row.encrypted_api_key is not None:
                from packages.auth.encryption import decrypt_credential

                cfg["api_key"] = decrypt_credential(search_row.encrypted_api_key)
            outcome = await run_search(
                body.content, cfg,
                max_results=search_row.max_results,
                max_page_fetches=search_row.max_page_fetches,
                timeout_s=search_row.timeout_s,
            )
        except SearchError as err:
            raise HTTPException(status_code=422, detail=f"Search failed: {err.message}") from err
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(
                status_code=422, detail="Search failed: the backend is unavailable."
            ) from err
        search_state.update(
            ran=True,
            citations=citations_payload(outcome),
            backend=outcome.backend,
            query=outcome.query,
        )
        system_prompt = (system_prompt + "\n\n" if system_prompt else "") + render_context_block(outcome)

    knowledge_state: dict | None = None
    knowledge_block: str | None = None
    if body.mode == "knowledge":
        knowledge_state, knowledge_block = await _knowledge_for(
            body.content, await _previous_knowledge_question(db, conversation.id)
        )

    accepts_images = await _model_accepts_images(db, model)
    if attachment_service.has_image_parts(attachment_rows) and not accepts_images:
        # Rejecting is kinder than silently dropping the picture: the engine
        # would otherwise answer a question about an image it never saw.
        raise HTTPException(
            status_code=422,
            detail=(
                f"The selected model '{model}' does not support image input. "
                "Switch to a vision-capable model, use 'auto', or remove the image."
            ),
            headers={"x-geek-routing-diagnosis": "no_vision"},
        )
    user_content, attachment_notices = attachment_service.build_user_content(
        body.content, attachment_rows, allow_images=accepts_images
    )

    history = await _history_messages(db, conversation)
    history.append({"role": "user", "content": user_content})
    try:
        window = await _trim_history_to_budget(
            model, history, _join_system(system_prompt, knowledge_block), eff_max, None, db=db
        )
    except ContextBudgetError as err:
        raise HTTPException(status_code=422, detail=f"Context budget: {err}.") from err
    engine_messages = _system_messages(system_prompt, knowledge_block)
    engine_messages.extend(window.messages)
    window_headers = _context_headers(window)
    if knowledge_state is not None:
        window_headers.update(_knowledge_headers(knowledge_state))
    if attachment_notices:
        for key, value in _attachment_headers(attachment_notices).items():
            window_headers[key] = value

    # The user's message is committed BEFORE the engine runs, so a failed or
    # aborted completion still shows the question and offers retry.
    user_row = None
    if settings.save_history:
        # `attachments_json` is the display list; the stored content is the
        # plain text plus file-extraction blocks (classic string content) so
        # replay works for any model regardless of vision support.
        stored_content = user_content if isinstance(user_content, str) else (
            "\n\n".join(
                str(part.get("text"))
                for part in user_content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        )
        user_row = ChatMessage(
            conversation_id=conversation.id,
            seq=await _next_seq(db, conversation.id),
            role="user",
            content=stored_content,
            chat_mode="knowledge" if knowledge_state is not None else None,
            reasoning_requested=reasoning_effort,
            attachments_json=(
                json.dumps(attachment_refs, separators=(",", ":"))
                if attachment_refs else None
            ),
        )
        db.add(user_row)
        if not conversation.title:
            # Auto-title from the first exchange; PATCH can rename later.
            title_source = body.content or ", ".join(
                ref.get("name", "") for ref in attachment_refs
            )
            conversation.title = " ".join(title_source.split())[:60]
        if body.reasoning_effort is not None:
            # Remember the selection like the model choice: regenerate and a
            # reload use it without the browser having to resend it.
            conversation.reasoning_effort = _effort_or_none(body.reasoning_effort)
        conversation.last_message_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user_row)
        for attachment in attachment_rows:
            attachment.conversation_id = conversation.id
            attachment.message_id = user_row.id
        if attachment_rows:
            await db.commit()
        await attachment_service.purge_orphan_attachments(db)

    requested_model = model
    trace_id = str(uuid.uuid4())
    try:
        response = await _run_engine(
            db=db, ac=ac, model=model, messages=engine_messages,
            trace_id=trace_id,
            stream=body.stream,
            temperature=body.temperature if body.temperature is not None else settings.temperature,
            max_tokens=body.max_tokens if body.max_tokens else settings.max_tokens,
            reasoning_effort=reasoning_effort,
        )
    except HTTPException as err:
        # Pre-stream failure (no candidates, upstream 4xx/5xx). Surface the
        # engine's own detail; the user message is already persisted.
        await db.rollback()
        return JSONResponse(
            status_code=err.status_code,
            content={"error": {
                "message": err.detail,
                "type": "engine_error",
                # The engine's own classification (e.g.
                # unsupported_reasoning_effort) so the UI can act on it.
                "code": (err.headers or {}).get("x-geek-error-type"),
            }},
        )

    if not settings.save_history:
        if isinstance(response, StreamingResponse):
            headers = dict(response.headers or {})
            headers.update(window_headers)
            return StreamingResponse(
                response.body_iterator, media_type=response.media_type, headers=headers
            )
        for key, value in window_headers.items():
            if key != "Access-Control-Expose-Headers":
                response.headers[key] = value
        return response

    conversation_id = conversation.id
    if isinstance(response, StreamingResponse):
        async def _on_done(result: CompletionResult) -> None:
            _reasoning_from_headers(response, result)
            await _persist_assistant_message(
                db, conversation_id=conversation_id, workspace_id=ac.workspace_id,
                result=result, requested_model=requested_model,
                search_state=search_state, knowledge_state=knowledge_state,
            )

        return await _proxy_engine_stream(
            response, on_done=_on_done, trace_id=trace_id, extra_headers=window_headers
        )

    result = _blocking_result(response)
    result.trace_id = trace_id
    _reasoning_from_headers(response, result)
    message = await _persist_assistant_message(
        db, conversation_id=conversation_id, workspace_id=ac.workspace_id,
        result=result, requested_model=requested_model,
        search_state=search_state, knowledge_state=knowledge_state,
    )
    return JSONResponse(
        status_code=response.status_code,
        content={
            "message": message,
            "context": _window_payload(window),
            "attachment_notices": attachment_notices or None,
        },
        headers=window_headers,
    )


@router.post("/conversations/{conversation_id}/regenerate")
async def regenerate_message(
    conversation_id: str,
    body: RegenerateBody = Body(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Re-run the last exchange.

    Deletes trailing assistant message(s) after the final user message, then
    runs the engine again over the remaining history. No new user row is
    written — the question is already stored.
    """
    conversation = await _get_live_conversation(db, ac.workspace_id, conversation_id)
    settings = await _load_settings(db, ac.workspace_id)
    model = body.model or conversation.selected_model or settings.default_model or "auto"

    if not settings.save_history:
        raise HTTPException(status_code=409, detail="History is off; nothing to regenerate.")

    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id, ChatMessage.is_deleted == 0)
            .order_by(ChatMessage.seq.desc(), ChatMessage.created_at.desc())
            .limit(60)
        )
    ).scalars().all()
    # Rows arrive newest-first; soft-delete leading assistant rows up to the
    # most recent user message.
    last_user = None
    for row in rows:
        if row.role == "user":
            last_user = row
            break
        row.is_deleted = 1
    await db.commit()

    # Regenerate with the effort the stored question used unless the request
    # names one; NULL on the stored row (Default, or a pre-feature message)
    # means no parameter, exactly as the original was sent.
    if body.reasoning_effort is not None:
        reasoning_effort = _effort_or_none(body.reasoning_effort)
    else:
        reasoning_effort = getattr(last_user, "reasoning_requested", None)

    # Regenerate in the same mode as the stored question.
    knowledge_state: dict | None = None
    knowledge_block: str | None = None
    if last_user is not None and last_user.chat_mode == "knowledge":
        knowledge_state, knowledge_block = await _knowledge_for(
            last_user.content,
            await _previous_knowledge_question(db, conversation.id, before_seq=last_user.seq),
        )

    system_prompt = conversation.system_prompt if conversation.system_prompt is not None else settings.system_prompt
    eff_max = body.max_tokens if body.max_tokens else settings.max_tokens
    try:
        window = await _trim_history_to_budget(
            model,
            await _history_messages(
                db, conversation,
                multimodal_last_user=True,
                allow_images=await _model_accepts_images(db, model),
            ),
            _join_system(system_prompt, knowledge_block), eff_max, None, db=db,
        )
    except ContextBudgetError as err:
        raise HTTPException(status_code=422, detail=f"Context budget: {err}.") from err
    engine_messages = _system_messages(system_prompt, knowledge_block)
    engine_messages.extend(window.messages)
    if not any(m["role"] == "user" for m in engine_messages):
        raise HTTPException(status_code=409, detail="No user message to regenerate from.")

    window_headers = _context_headers(window)
    if knowledge_state is not None:
        window_headers.update(_knowledge_headers(knowledge_state))

    requested_model = model
    trace_id = str(uuid.uuid4())
    try:
        response = await _run_engine(
            db=db, ac=ac, model=model, messages=engine_messages,
            trace_id=trace_id,
            stream=body.stream,
            temperature=body.temperature if body.temperature is not None else settings.temperature,
            max_tokens=body.max_tokens if body.max_tokens else settings.max_tokens,
            reasoning_effort=reasoning_effort,
        )
    except HTTPException as err:
        await db.rollback()
        return JSONResponse(
            status_code=err.status_code,
            content={"error": {
                "message": err.detail,
                "type": "engine_error",
                # The engine's own classification (e.g.
                # unsupported_reasoning_effort) so the UI can act on it.
                "code": (err.headers or {}).get("x-geek-error-type"),
            }},
        )

    if not isinstance(response, StreamingResponse):
        result = _blocking_result(response)
        result.trace_id = trace_id
        _reasoning_from_headers(response, result)

        message = await _persist_assistant_message(
            db, conversation_id=conversation.id, workspace_id=ac.workspace_id,
            result=result, requested_model=requested_model,
            knowledge_state=knowledge_state,
        )
        return JSONResponse(
            status_code=response.status_code,
            content={"message": message},
            headers=window_headers,
        )

    conversation_id = conversation.id

    async def _on_done(result: CompletionResult) -> None:
        _reasoning_from_headers(response, result)
        await _persist_assistant_message(
            db, conversation_id=conversation_id, workspace_id=ac.workspace_id,
            result=result, requested_model=requested_model,
            knowledge_state=knowledge_state,
        )

    return await _proxy_engine_stream(
        response, on_done=_on_done, trace_id=trace_id, extra_headers=window_headers
    )
