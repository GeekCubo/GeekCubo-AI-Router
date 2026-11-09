"""Attachment detection: extension allowlist + signature cross-check.

The security property under test is that a file is classified by what it
actually is, not merely by what it is called: a Windows executable renamed
to `.pdf`, a plain ZIP renamed to `.docx`, or an HTML page renamed to `.png`
must all be rejected instead of being handed to an extractor.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from app.attachments import detect


def _zip_with(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, "x")
    return buf.getvalue()


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_plain_types_resolve_to_kind_mime_and_extension():
    got = detect.detect("notes.txt", b"hello")
    assert (got.kind, got.mime, got.ext) == ("text", "text/plain", "txt")

    got = detect.detect("report.PDF", b"%PDF-1.7\n...")
    assert (got.kind, got.mime, got.ext) == ("document", "application/pdf", "pdf")

    got = detect.detect("data.csv", b"a,b\n1,2\n")
    assert got.kind == "spreadsheet"

    got = detect.detect("main.py", b"print(1)\n")
    assert got.kind == "code"


def test_image_signature_is_verified():
    assert detect.detect("pic.png", _png()).mime == "image/png"
    with pytest.raises(detect.UnsupportedAttachment):
        detect.detect("pic.png", b"<html><body>not an image")


def test_executables_are_rejected_whatever_the_extension():
    for magic in (b"MZ\x90\x00", b"\x7fELF\x02\x01", b"\xca\xfe\xba\xbe"):
        with pytest.raises(detect.UnsupportedAttachment) as err:
            detect.detect("invoice.pdf", magic + b"\x00" * 16)
        assert "not accepted" in str(err.value).lower() or "not accepted" in str(err.value)


def test_unknown_extension_is_rejected():
    with pytest.raises(detect.UnsupportedAttachment):
        detect.detect("payload.exe", b"MZ\x90")


def test_zip_renamed_to_docx_is_rejected():
    payload = _zip_with("notes.txt")
    with pytest.raises(detect.UnsupportedAttachment):
        detect.detect("letter.docx", payload)


def test_real_office_container_is_accepted():
    docx = _zip_with("word/document.xml", "[Content_Types].xml")
    assert detect.detect("letter.docx", docx).mime.endswith("wordprocessingml.document")

    xlsx = _zip_with("xl/workbook.xml", "[Content_Types].xml")
    assert detect.detect("book.xlsx", xlsx).kind == "spreadsheet"

    ods = _zip_with("content.xml", "mimetype")
    assert detect.detect("sheet.ods", ods).mime.endswith("opendocument.spreadsheet")


def test_extensionless_well_known_names():
    assert detect.detect("Dockerfile", b"FROM python:3.12\n").kind == "code"
    assert detect.detect("Makefile", b"all:\n\techo hi\n").kind == "code"


def test_media_signatures():
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
    assert detect.detect("clip.mp4", mp4).kind == "video"

    webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 16
    assert detect.detect("clip.webm", webm).kind == "video"

    wav = b"RIFF\x24\x00\x00\x00WAVEfmt "
    assert detect.detect("voice.wav", wav).kind == "audio"

    with pytest.raises(detect.UnsupportedAttachment):
        detect.detect("voice.wav", b"not a wave file")


def test_declared_mime_does_not_override_the_bytes():
    # The browser may claim anything; only the bytes decide acceptance.
    with pytest.raises(detect.UnsupportedAttachment):
        detect.detect("photo.png", b"plain text", "image/png")
