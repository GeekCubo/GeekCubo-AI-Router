"""Attachment service: storage names, extraction-to-row round trip, and the
content a model actually receives.

The security property here is that the client's filename never reaches the
filesystem: every file is written under an opaque UUID name and the original
name is metadata only. The behaviour property is that a text-only model still
sees something useful for an image, while a vision model gets the picture.
"""

from __future__ import annotations

import io
import os

import pytest
import pytest_asyncio

from app.attachments import service, storage


@pytest.fixture(autouse=True)
def _attachments_env(tmp_path, monkeypatch):
    """Force a 5 MB ceiling and a per-test storage directory.

    The service reads settings through `app.config.get_settings`, which the
    `isolated_env`-style teardown re-caches; going through the env vars keeps
    the patched instance the single source of truth for this module.
    """
    from app import config as cfg

    monkeypatch.setenv("ATTACHMENT_DIR", str(tmp_path / "attachments"))
    monkeypatch.setenv("ATTACHMENT_MAX_MB", "5")
    monkeypatch.setenv("ATTACHMENTS_ENABLED", "true")
    cfg.get_settings.cache_clear()
    yield
    cfg.get_settings.cache_clear()


@pytest_asyncio.fixture
async def db(db_session):
    return db_session


def _png_bytes(width: int = 20, height: int = 10) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 120, 240)).save(buf, format="PNG")
    return buf.getvalue()


async def test_store_upload_uses_opaque_name_and_extracts(db):
    row = await service.store_upload(
        db, workspace_id="w1", filename="../../etc/красивый.txt", data=b"hello"
    )
    assert row.filename.endswith(".txt")
    assert row.kind == "text"
    assert row.extracted_text == "hello"
    assert row.extraction_state == "ok"
    assert ".." not in row.storage_name
    stored = storage.attachments_root() / row.storage_name
    assert stored.exists()
    # Nothing escaped the attachment root.
    assert not (storage.attachments_root().parent / "etc").exists()


async def test_upload_larger_than_the_limit_is_rejected(db):
    with pytest.raises(service.AttachmentError) as err:
        await service.store_upload(
            db, workspace_id="w1", filename="big.txt", data=b"a" * (6 * 1024 * 1024)
        )
    assert "limit" in str(err.value)


async def test_empty_upload_is_rejected(db):
    with pytest.raises(service.AttachmentError):
        await service.store_upload(db, workspace_id="w1", filename="x.txt", data=b"")


async def test_unsupported_type_is_rejected(db):
    with pytest.raises(service.AttachmentError):
        await service.store_upload(
            db, workspace_id="w1", filename="tool.exe", data=b"MZ\x90\x00"
        )


async def test_disabled_attachments_are_rejected(db, monkeypatch):
    from app import config as cfg


    monkeypatch.setenv("ATTACHMENTS_ENABLED", "false")
    cfg.get_settings.cache_clear()
    with pytest.raises(service.AttachmentError):
        await service.store_upload(db, workspace_id="w1", filename="a.txt", data=b"hi")


async def test_display_refs_do_not_leak_the_storage_name(db):
    row = await service.store_upload(db, workspace_id="w1", filename="a.txt", data=b"x")
    refs = service.display_refs([row])
    assert refs[0]["name"] == "a.txt"
    assert "storage_name" not in refs[0]
    assert "extracted_text" not in refs[0]


async def test_text_attachment_is_built_as_a_delimited_block(db):
    row = await service.store_upload(
        db, workspace_id="w1", filename="plan.md", data=b"# Plan\n- do the thing"
    )
    content, notices = service.build_user_content("summarise this", [row])
    assert isinstance(content, str)
    assert "summarise this" in content
    assert "[attached file: plan.md" in content
    assert "do the thing" in content
    assert content.rstrip().endswith("[/attached file]")
    assert notices == []


async def test_image_becomes_an_image_part_for_vision_models(db):
    row = await service.store_upload(
        db, workspace_id="w1", filename="shot.png", data=_png_bytes()
    )
    content, notices = service.build_user_content("what is this?", [row])
    assert isinstance(content, list)
    kinds = [part["type"] for part in content]
    assert kinds == ["text", "image_url"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert notices == []


async def test_image_degrades_to_a_description_without_vision(db):
    row = await service.store_upload(
        db, workspace_id="w1", filename="shot.png", data=_png_bytes()
    )
    content, notices = service.build_user_content(
        "what is this?", [row], allow_images=False
    )
    assert isinstance(content, str)
    assert "shot.png" in content
    assert "cannot view images" in content
    assert notices and "no vision" in notices[0]


async def test_failed_extraction_still_produces_a_block(db):
    row = await service.store_upload(
        db, workspace_id="w1", filename="broken.pdf", data=b"%PDF-1.4\n garbage"
    )
    content, _ = service.build_user_content("", [row])
    assert isinstance(content, str)
    assert "broken.pdf" in content


async def test_has_image_parts_detects_only_image_bearing_kinds(db):
    text_row = await service.store_upload(
        db, workspace_id="w1", filename="a.txt", data=b"x"
    )
    image_row = await service.store_upload(
        db, workspace_id="w1", filename="b.png", data=_png_bytes()
    )
    assert service.has_image_parts([text_row]) is False
    assert service.has_image_parts([text_row, image_row]) is True


def test_storage_refuses_names_that_escape_the_root():
    root = storage.attachments_root()
    with pytest.raises(storage.StorageError):
        storage.path_for("../escape.txt")
    with pytest.raises(storage.StorageError):
        storage.path_for("/etc/passwd")
    assert os.path.isdir(root)


def test_storage_delete_is_idempotent():
    name = storage.new_storage_name("txt")
    storage.write_bytes(name, b"data")
    path = storage.path_for(name)
    assert path.exists()
    storage.delete(name)
    assert not path.exists()
    storage.delete(name)  # no error the second time


_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


async def test_video_without_ffmpeg_is_stored_unsupported_and_tells_the_model(db, monkeypatch):
    from app.attachments import extract

    monkeypatch.setattr(extract, "_which", lambda name: None)
    row = await service.store_upload(db, workspace_id="w1", filename="clip.mp4", data=_MP4)
    assert row.kind == "video"
    assert row.extraction_state == "unsupported"
    assert "ffmpeg is not available" in row.error
    payload = service.attachment_payload(row)
    assert payload["extraction"] == "unsupported"
    assert "ffmpeg is not available" in payload["error"]
    content, _ = service.build_user_content("what happens here?", [row])
    assert isinstance(content, str)
    assert "clip.mp4" in content
    assert "ffmpeg is not available" in content
    assert "representative frame" not in content


async def test_audio_is_stored_as_metadata_only(db, monkeypatch):
    from app.attachments import extract

    monkeypatch.setattr(extract, "_which", lambda name: None)
    data = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
    row = await service.store_upload(db, workspace_id="w1", filename="voice.mp3", data=data)
    assert row.kind == "audio"
    assert row.extraction_state == "ok"
    payload = service.attachment_payload(row)
    assert payload["metadata"]["transcribed"] is False
    assert payload["metadata"]["metadata_only"] is True
    content, _ = service.build_user_content("summarize", [row])
    assert "Automatic transcription is not enabled" in content
    assert "cannot hear the audio" in content


async def test_extraction_does_not_block_the_event_loop(db, monkeypatch):
    """Regression: extraction (CPU-bound parsing, ffmpeg subprocesses) ran on
    the event loop and froze every concurrent request, live streams included,
    for its full duration."""
    import asyncio
    import time

    from app.attachments import extract
    from app.attachments.types import STATE_OK, ExtractionResult

    def _slow_extract(kind, ext, path, data):
        time.sleep(0.5)  # stands in for a heavy parse
        return ExtractionResult(state=STATE_OK, text="done")

    monkeypatch.setattr(extract, "extract", _slow_extract)

    ticks = 0

    async def _heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.02)
            ticks += 1

    beat = asyncio.create_task(_heartbeat())
    try:
        row = await service.store_upload(db, workspace_id="w1", filename="a.txt", data=b"x")
    finally:
        beat.cancel()
    assert row.extracted_text == "done"
    # A blocked loop would tick at most once or twice during the 0.5 s parse.
    assert ticks >= 10, ticks
