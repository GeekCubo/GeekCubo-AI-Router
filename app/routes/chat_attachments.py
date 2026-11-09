"""Native Chat attachment upload and retrieval.

Administrator-session routes under `/api/`, so the existing auth policy
classifies them ADMIN (session cookie + CSRF). Files are stored under an
opaque UUID name; the original filename is metadata only.

Upload → extract → return an `attachment` payload. Sending a message with
`attachment_ids` binds the rows to the conversation/message, and the chat
route builds the model content from them.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attachments import service as attachment_service
from app.attachments import storage
from app.attachments.types import MAX_ATTACHMENTS_PER_MESSAGE
from app.deps import AdminContext, get_admin_context, get_db
from packages.db.models.chat_attachment import ChatAttachment

logger = logging.getLogger("geekcubo.chat_attachments")

router = APIRouter(prefix="/api/chat/attachments", tags=["chat attachments"])


@router.get("/limits")
async def attachment_limits(ac: AdminContext = Depends(get_admin_context)) -> dict:
    """What the client may upload, so the UI can enforce it before sending."""
    from app.config import get_settings

    settings = get_settings()
    return {
        "enabled": bool(settings.attachments_enabled),
        "max_mb": attachment_service.max_upload_mb(),
        "max_per_message": MAX_ATTACHMENTS_PER_MESSAGE,
    }


@router.post("", status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    limit = attachment_service.max_upload_bytes()
    # Read with a hard stop: `read()` without a size would buffer an
    # arbitrarily large body before the length check.
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"{file.filename}: file is larger than the "
            f"{attachment_service.max_upload_mb()} MB limit.",
        )
    try:
        row = await attachment_service.store_upload(
            db,
            workspace_id=ac.workspace_id,
            filename=file.filename or "file",
            data=data,
            declared_mime=file.content_type,
        )
    except attachment_service.AttachmentError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    # Housekeeping must never fail an upload that already succeeded.
    payload = {"attachment": attachment_service.attachment_payload(row)}
    try:
        await attachment_service.purge_orphan_attachments(db)
    except Exception:
        logger.warning("orphan_attachment_purge_failed", exc_info=True)
        await db.rollback()
    return payload


async def _owned_or_404(
    db: AsyncSession, workspace_id: str, attachment_id: str
) -> ChatAttachment:
    row = await attachment_service.load_owned(
        db, workspace_id=workspace_id, attachment_id=attachment_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return row


@router.get("/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _owned_or_404(db, ac.workspace_id, attachment_id)
    return {"attachment": attachment_service.attachment_payload(row)}


def _content_disposition(filename: str | None) -> str:
    """`attachment` disposition that survives any original filename.

    HTTP headers are Latin-1, so a raw non-ASCII name (``报告.pdf``) raised
    UnicodeEncodeError and turned the download into a 500. RFC 6266: an
    ASCII-only `filename` fallback plus the exact name as UTF-8 `filename*`.
    Quotes, backslashes and control characters never reach the header.
    """
    from urllib.parse import quote

    name = filename or "attachment"
    fallback = "".join(
        ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in name
    ) or "attachment"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


@router.get("/{attachment_id}/content")
async def get_attachment_content(
    attachment_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve the original bytes. Only the administrator can read them, and
    the response is always an attachment download (never inline render)."""
    row = await _owned_or_404(db, ac.workspace_id, attachment_id)
    try:
        data = storage.read_bytes(row.storage_name)
    except storage.StorageError as err:
        raise HTTPException(status_code=410, detail="The file is no longer on disk.") from err
    return Response(
        content=data,
        media_type=row.mime or "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(row.filename),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=0, no-store",
        },
    )


@router.get("/{attachment_id}/thumbnail")
async def get_attachment_thumbnail(
    attachment_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A small inline preview (data URL) for images and video frames."""
    row = await _owned_or_404(db, ac.workspace_id, attachment_id)
    payload = attachment_service.attachment_payload(row)
    return {"thumbnail": payload.get("thumbnail")}


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await _owned_or_404(db, ac.workspace_id, attachment_id)
    # A sent attachment is part of a message's history; removing the bytes
    # would make replay lie. Only unsent uploads can be deleted outright.
    if row.message_id:
        raise HTTPException(
            status_code=409,
            detail="This attachment was sent in a message and cannot be deleted on its own.",
        )
    row.is_deleted = 1
    await db.commit()
    storage.delete(row.storage_name)


async def attachments_by_ids(
    db: AsyncSession, workspace_id: str, ids: list[str]
) -> list[ChatAttachment]:
    """Fetch attachment rows for a send, preserving the client's order.

    Unknown, foreign or already-bound ids are an error: silently dropping an
    attachment would send the model a different message than the operator
    wrote.
    """
    if not ids:
        return []
    if len(ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_ATTACHMENTS_PER_MESSAGE} attachments per message.",
        )
    rows = (
        await db.execute(
            select(ChatAttachment).where(
                ChatAttachment.id.in_(ids),
                ChatAttachment.workspace_id == workspace_id,
                ChatAttachment.is_deleted == 0,
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    missing = [aid for aid in ids if aid not in by_id]
    if missing:
        raise HTTPException(
            status_code=422, detail="One or more attachments are missing or expired."
        )
    return [by_id[aid] for aid in ids]
