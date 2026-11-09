"""Extractors: bounded everywhere, never fatal, never write user files to disk.

Each test builds a real file of the accepted type, runs the extractor the
upload route would run, and asserts on the model-facing text. Caps are
asserted with `truncated` rather than by inspecting private counters.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.attachments import extract
from app.attachments.types import (
    AUDIO_TRANSCRIBE_NOTE,
    KIND_ARCHIVE,
    KIND_AUDIO,
    KIND_DOCUMENT,
    KIND_IMAGE,
    KIND_SPREADSHEET,
    KIND_TEXT,
    KIND_VIDEO,
    MAX_EXTRACTED_CHARS,
    MAX_SHEET_ROWS,
    STATE_FAILED,
    STATE_OK,
    STATE_UNSUPPORTED,
)


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _png(tmp_path: Path, width: int = 40, height: int = 30) -> Path:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, format="PNG")
    return _write(tmp_path, "pic.png", buf.getvalue())


def test_text_is_decoded_and_latin1_fallback(tmp_path):
    path = _write(tmp_path, "a.txt", "héllo\nwörld".encode("cp1252"))
    result = extract.extract(KIND_TEXT, "txt", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "wörld" in result.text
    assert result.truncated is False


def test_text_is_truncated_at_the_character_cap(tmp_path):
    path = _write(tmp_path, "big.txt", b"a" * (MAX_EXTRACTED_CHARS + 500))
    result = extract.extract(KIND_TEXT, "txt", path, path.read_bytes())
    assert len(result.text) == MAX_EXTRACTED_CHARS
    assert result.truncated is True


def test_csv_becomes_readable_rows_and_respects_row_cap(tmp_path):
    body = "name,qty\n" + "".join(f"item{i},{i}\n" for i in range(MAX_SHEET_ROWS + 10))
    path = _write(tmp_path, "d.csv", body.encode())
    result = extract.extract(KIND_SPREADSHEET, "csv", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "name | qty" in result.text
    assert result.truncated is True


def test_xlsx_cells_are_extracted(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["region", "total"])
    ws.append(["emea", 42])
    path = tmp_path / "b.xlsx"
    wb.save(path)

    result = extract.extract(KIND_SPREADSHEET, "xlsx", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "Sales" in result.text
    assert "emea" in result.text
    assert "42" in result.text


def test_docx_paragraphs_are_extracted(tmp_path):
    import docx

    document = docx.Document()
    document.add_paragraph("Quarterly summary")
    document.add_paragraph("Revenue grew.")
    path = tmp_path / "d.docx"
    document.save(path)

    result = extract.extract(KIND_DOCUMENT, "docx", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "Quarterly summary" in result.text
    assert "Revenue grew." in result.text


def test_pdf_text_is_extracted(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    with open(path, "wb") as fh:
        writer.write(fh)

    result = extract.extract(KIND_DOCUMENT, "pdf", path, path.read_bytes())
    assert result.state == STATE_OK
    assert isinstance(result.text, str)


def test_zip_lists_entries_and_reads_bounded_text(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hello from the archive")
        zf.writestr("image.bin", b"\x00\x01\x02")
    path = _write(tmp_path, "a.zip", buf.getvalue())

    result = extract.extract(KIND_ARCHIVE, "zip", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "readme.txt" in result.text
    assert "hello from the archive" in result.text
    # Binary members are listed but their bytes are not pasted in.
    assert "image.bin" in result.text


def test_zip_slip_member_names_are_not_listed(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0")
        zf.writestr("ok.txt", "fine")
    path = _write(tmp_path, "evil.zip", buf.getvalue())

    result = extract.extract(KIND_ARCHIVE, "zip", path, path.read_bytes())
    assert "passwd" not in result.text
    assert "ok.txt" in result.text
    # Nothing was written to the parent of the temp directory.
    assert not (tmp_path.parent / "etc").exists()


def test_image_is_downscaled_and_thumbnail_kept(tmp_path):
    path = _png(tmp_path, width=4000, height=3000)
    result = extract.extract(KIND_IMAGE, "png", path, path.read_bytes())
    assert result.state == STATE_OK
    assert len(result.image_data_urls) == 1
    assert result.image_data_urls[0].startswith("data:image/jpeg;base64,")
    assert result.metadata["width"] == 4000
    assert result.metadata["resized"] is True
    assert result.metadata["thumbnail_data_url"].startswith("data:image/jpeg;base64,")


def test_image_with_no_pixels_fails_softly(tmp_path):
    path = _write(tmp_path, "broken.png", b"\x89PNG\r\n\x1a\nnot really")
    result = extract.extract(KIND_IMAGE, "png", path, path.read_bytes())
    assert result.state == STATE_FAILED
    assert result.error


def test_extractor_error_never_raises(tmp_path):
    path = _write(tmp_path, "x.docx", b"PK\x03\x04garbage")
    result = extract.extract(KIND_DOCUMENT, "docx", path, path.read_bytes())
    assert result.state in (STATE_FAILED, STATE_OK)
    assert isinstance(result.error, str) or result.text


def test_rtf_is_stripped_to_text(tmp_path):
    rtf = b"{\\rtf1\\ansi Hello \\b bold\\b0  world\\par second line}"
    path = _write(tmp_path, "a.rtf", rtf)
    result = extract.extract(KIND_DOCUMENT, "rtf", path, path.read_bytes())
    assert result.state == STATE_OK
    assert "Hello" in result.text
    assert "second line" in result.text
    assert "\\rtf1" not in result.text


def test_video_without_ffmpeg_is_reported_unsupported(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "_which", lambda name: None)
    path = _write(tmp_path, "clip.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    result = extract.extract(KIND_VIDEO, "mp4", path, path.read_bytes())
    assert result.state == STATE_UNSUPPORTED
    assert "ffmpeg is not available" in result.error
    assert result.image_data_urls == []
    assert result.metadata["frames_extracted"] == 0


def test_video_with_ffmpeg_but_no_frames_is_reported_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "_which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(extract, "_ffprobe_metadata", lambda path: {"duration_s": 3.0})
    monkeypatch.setattr(extract, "_ffmpeg_frames", lambda path, duration: [])
    path = _write(tmp_path, "clip.mp4", b"not really a video")
    result = extract.extract(KIND_VIDEO, "mp4", path, path.read_bytes())
    assert result.state == STATE_FAILED
    assert "no frames" in result.error
    assert result.metadata["duration_s"] == 3.0


def test_video_with_frames_is_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "_ffprobe_metadata", lambda path: {"duration_s": 2.0})
    monkeypatch.setattr(extract, "_ffmpeg_frames", lambda path, duration: ["data:image/jpeg;base64,AAAA"])
    path = _write(tmp_path, "clip.mp4", b"video")
    result = extract.extract(KIND_VIDEO, "mp4", path, path.read_bytes())
    assert result.state == STATE_OK
    assert result.image_data_urls == ["data:image/jpeg;base64,AAAA"]
    assert "1 representative frame(s)" in result.text


def test_audio_is_metadata_only_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "_ffprobe_metadata", lambda path: {"duration_s": 12.5, "audio_codec": "mp3"})
    path = _write(tmp_path, "voice.mp3", b"ID3" + b"\x00" * 32)
    result = extract.extract(KIND_AUDIO, "mp3", path, path.read_bytes())
    assert result.state == STATE_OK
    assert result.text.startswith(AUDIO_TRANSCRIBE_NOTE)
    assert "cannot hear the audio" in result.text
    assert "Duration: 12.5s." in result.text
    assert result.metadata["transcribed"] is False
    assert result.metadata["metadata_only"] is True
    assert result.image_data_urls == []


def test_audio_without_ffprobe_is_still_labelled_metadata_only(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "_which", lambda name: None)
    path = _write(tmp_path, "voice.wav", b"RIFF" + b"\x00" * 40)
    result = extract.extract(KIND_AUDIO, "wav", path, path.read_bytes())
    assert result.state == STATE_OK
    assert result.text == AUDIO_TRANSCRIBE_NOTE
    assert result.metadata == {"transcribed": False, "metadata_only": True}
