"""Attachment service — the single place uploads are validated, stored,
extracted and turned into model content parts.

Keeping this out of the route means the chat send path and the tests use the
exact same rules: what an upload accepts, how an attachment becomes a text
block or an image part, and what the "unsupported/degraded" markers look
like.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.attachments import detect as detect_mod
from app.attachments import extract as extract_mod
from app.attachments import storage
from app.attachments.types import (
    ABSOLUTE_MAX_UPLOAD_MB,
    DEFAULT_MAX_UPLOAD_MB,
    KIND_ARCHIVE,
    KIND_AUDIO,
    KIND_CODE,
    KIND_DOCUMENT,
    KIND_IMAGE,
    KIND_SPREADSHEET,
    KIND_TEXT,
    KIND_VIDEO,
    STATE_FAILED,
    STATE_UNSUPPORTED,
    ExtractionResult,
)
from app.config import get_settings
from packages.db.models.chat_attachment import ChatAttachment

logger = logging.getLogger("geekcubo.attachments")

# Kinds whose bytes can be described to a text-only model at all.
TEXTUAL_KINDS = (
    KIND_DOCUMENT, KIND_SPREADSHEET, KIND_TEXT, KIND_CODE, KIND_ARCHIVE,
    KIND_VIDEO, KIND_AUDIO,
)

# Kinds a vision model can receive as an image part.
IMAGE_BEARING_KINDS = (KIND_IMAGE, KIND_VIDEO)


class AttachmentError(ValueError):
    """A user-facing rejection (too large, unsupported, disabled)."""


def max_upload_bytes() -> int:
    settings = get_settings()
    mb = settings.attachment_max_mb or DEFAULT_MAX_UPLOAD_MB
    mb = max(1, min(int(mb), ABSOLUTE_MAX_UPLOAD_MB))
    return mb * 1024 * 1024


def max_upload_mb() -> int:
    return max_upload_bytes() // (1024 * 1024)


def _display_ref(row: ChatAttachment) -> dict:
    return {
        "id": row.id,
        "name": row.filename,
        "kind": row.kind,
        "mime": row.mime,
        "size": row.size_bytes,
        "extraction": row.extraction_state,
        "truncated": bool((_metadata(row)).get("truncated")),
    }


def _metadata(row: ChatAttachment) -> dict:
    if not row.metadata_json:
        return {}
    try:
        data = json.loads(row.metadata_json)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def attachment_payload(row: ChatAttachment, *, include_thumbnail: bool = True) -> dict:
    meta = _metadata(row)
    thumb = meta.get("thumbnail_data_url") if include_thumbnail else None
    return {
        **_display_ref(row),
        "filename": row.filename,
        "extraction_state": row.extraction_state,
        "extracted_chars": row.extracted_chars,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "truncated": bool(meta.get("truncated")),
        "thumbnail": thumb,
        "metadata": {k: v for k, v in meta.items() if k != "thumbnail_data_url"},
    }


async def store_upload(
    db: AsyncSession,
    *,
    workspace_id: str,
    filename: str,
    data: bytes,
    declared_mime: str | None = None,
) -> ChatAttachment:
    """Validate, persist and extract one uploaded file.

    Raises AttachmentError for rejections the operator can act on. An
    extraction failure is not a rejection: the row is stored with
    `extraction_state=failed` so the file shows up with its error.
    """
    settings = get_settings()
    if not settings.attachments_enabled:
        raise AttachmentError("Attachments are disabled on this server.")
    if not data:
        raise AttachmentError("The uploaded file is empty.")
    limit = max_upload_bytes()
    if len(data) > limit:
        raise AttachmentError(
            f"{filename}: file is larger than the {max_upload_mb()} MB limit."
        )
    try:
        detected = detect_mod.detect(filename, data, declared_mime)
    except detect_mod.UnsupportedAttachment as err:
        raise AttachmentError(str(err)) from err

    storage_name = storage.new_storage_name(detected.ext)
    try:
        path = await asyncio.to_thread(storage.write_bytes, storage_name, data)
    except OSError as err:
        raise AttachmentError("Could not store the upload; check disk space.") from err

    # Extraction is CPU-bound parsing plus, for video, ffmpeg subprocesses
    # with multi-second timeouts. On the event loop it froze every
    # concurrent request — live inference streams included — for the
    # duration; a worker thread keeps the server responsive.
    result: ExtractionResult = await asyncio.to_thread(
        extract_mod.extract, detected.kind, detected.ext, path, data
    )
    metadata = dict(result.metadata or {})
    if result.truncated:
        metadata["truncated"] = True

    row = ChatAttachment(
        workspace_id=workspace_id,
        filename=(filename or "file")[:255],
        kind=detected.kind,
        mime=detected.mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_name=storage_name,
        extraction_state=result.state,
        extracted_text=result.text or None,
        extracted_chars=len(result.text or ""),
        error=(result.error or None),
        metadata_json=json.dumps(metadata, separators=(",", ":"), sort_keys=True) if metadata else None,
    )
    # Image/video parts are kept in memory only for the upload response; they
    # are rebuilt from the stored file when a message is sent/replayed.
    row._image_data_urls = list(result.image_data_urls or [])  # type: ignore[attr-defined]
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# Unbound uploads older than this are removed (bytes and row).
ORPHAN_ATTACHMENT_HOURS = 24


async def purge_orphan_attachments(db: AsyncSession) -> int:
    """Drop uploads that were never bound to a stored message.

    A user can upload and then close the tab, and with chat history off a
    sent upload is never bound at all; without this the bytes would live
    forever because nothing references them. Only uploads that are still
    unbound and older than a day are removed, so a draft in progress is safe.
    Runs on every upload, which is the only operation that creates orphans,
    so it applies whether or not history is saved.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_ATTACHMENT_HOURS)
    rows = (
        await db.execute(
            select(ChatAttachment).where(
                ChatAttachment.is_deleted == 0,
                ChatAttachment.message_id.is_(None),
                ChatAttachment.created_at < cutoff,
            )
        )
    ).scalars().all()
    if not rows:
        return 0
    for row in rows:
        storage.delete(row.storage_name)
        row.is_deleted = 1
    await db.commit()
    return len(rows)


async def load_owned(
    db: AsyncSession, *, workspace_id: str, attachment_id: str
) -> ChatAttachment | None:
    return (
        await db.execute(
            select(ChatAttachment).where(
                ChatAttachment.id == attachment_id,
                ChatAttachment.workspace_id == workspace_id,
                ChatAttachment.is_deleted == 0,
            )
        )
    ).scalar_one_or_none()


def _image_parts_for(row: ChatAttachment) -> list[str]:
    """Re-extract the primary image part(s) from disk for sending/replay."""
    if row.kind not in IMAGE_BEARING_KINDS:
        return []
    try:
        data = storage.read_bytes(row.storage_name)
    except storage.StorageError:
        return []
    if row.kind == KIND_IMAGE:
        result = extract_mod.extract(KIND_IMAGE, _ext(row), storage.path_for(row.storage_name), data)
    else:
        result = extract_mod.extract(KIND_VIDEO, _ext(row), storage.path_for(row.storage_name), data)
    return list(result.image_data_urls or [])


def _ext(row: ChatAttachment) -> str:
    name = row.filename or ""
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def text_block(row: ChatAttachment) -> str:
    """The text a model reads for a non-image attachment.

    Delimited so the model can tell file content from the operator's own
    words, and it names the file and says when the content was truncated.
    """
    header = f"[attached file: {row.filename} ({row.kind}, {row.size_bytes} bytes)]"
    notes: list[str] = []
    if row.extraction_state == STATE_UNSUPPORTED:
        notes.append(row.error or "This file type could not be read on this server.")
        return "\n".join([header, *notes]) + "\n[/attached file]"
    if row.extraction_state == STATE_FAILED:
        notes.append(row.error or "The file could not be read.")
        return "\n".join([header, *notes]) + "\n[/attached file]"
    body = row.extracted_text or ""
    if not body.strip():
        notes.append("(no extractable text)")
        body = ""
    meta = _metadata(row)
    if meta.get("truncated"):
        notes.append("(content truncated to fit the context budget)")
    parts = [header]
    if notes:
        parts.extend(notes)
    if body:
        parts.append(body)
    parts.append("[/attached file]")
    return "\n".join(parts)


def build_user_content(
    text: str,
    rows: list[ChatAttachment],
    *,
    allow_images: bool = True,
) -> tuple[str | list[dict], list[str]]:
    """Build an OpenAI message `content` value plus degradation notices.

    Returns the plain string when nothing image-bearing is included, and the
    content-parts list when at least one image part survives. `allow_images`
    is false when the chosen model cannot see images: the caller then decides
    whether to degrade (describe frames/text in words) or reject.
    """
    notices: list[str] = []
    text_chunks: list[str] = [text] if text else []
    image_urls: list[str] = []

    for row in rows:
        if row.kind in IMAGE_BEARING_KINDS and allow_images:
            urls = _image_parts_for(row)
            if urls:
                image_urls.extend(urls)
                continue
            notices.append(f"{row.filename}: the image could not be prepared for this model.")
        if row.kind in (KIND_IMAGE,):
            meta = _metadata(row)
            desc = (
                f"[attached image: {row.filename} "
                f"({meta.get('width', '?')}x{meta.get('height', '?')}); "
                "the selected model cannot view images, so only this description is included]"
            )
            text_chunks.append(desc)
            notices.append(f"{row.filename}: not sent as an image (model has no vision).")
            continue
        text_chunks.append(text_block(row))

    if image_urls:
        parts: list[dict] = []
        combined = "\n\n".join(chunk for chunk in text_chunks if chunk)
        if combined:
            parts.append({"type": "text", "text": combined})
        for url in image_urls:
            parts.append({"type": "image_url", "image_url": {"url": url}})
        return parts, notices
    return "\n\n".join(chunk for chunk in text_chunks if chunk), notices


def has_image_parts(rows: list[ChatAttachment]) -> bool:
    return any(row.kind in IMAGE_BEARING_KINDS for row in rows)


def display_refs(rows: list[ChatAttachment]) -> list[dict]:
    return [_display_ref(row) for row in rows]
