"""Attachment detection by extension + magic bytes.

No `python-magic`/libmagic dependency: the set of accepted types is small
and each has a well-defined signature at a known offset, so a table is
cheaper and portable. The extension decides the coarse kind and the
extractor; the signature check exists to reject a file whose bytes do not
match its claimed type (an executable renamed to `.pdf`, an archive smuggled
in as an image) rather than to discover unknown types.

A mismatch is a rejection, not a silent reclassification: the operator
picked the file, and quietly sending different bytes to the model than the
name suggests is worse than asking them to rename it.
"""

from __future__ import annotations

import io
import zipfile

from app.attachments.types import (
    KIND_ARCHIVE,
    KIND_AUDIO,
    KIND_CODE,
    KIND_DOCUMENT,
    KIND_IMAGE,
    KIND_SPREADSHEET,
    KIND_TEXT,
    KIND_VIDEO,
    DetectedFile,
)


class UnsupportedAttachment(ValueError):
    """Raised when a file is not an accepted type (or lies about its type)."""


# extension -> (kind, canonical mime)
_EXTENSIONS: dict[str, tuple[str, str]] = {
    # images
    "png": (KIND_IMAGE, "image/png"),
    "jpg": (KIND_IMAGE, "image/jpeg"),
    "jpeg": (KIND_IMAGE, "image/jpeg"),
    "gif": (KIND_IMAGE, "image/gif"),
    "webp": (KIND_IMAGE, "image/webp"),
    "bmp": (KIND_IMAGE, "image/bmp"),
    "tif": (KIND_IMAGE, "image/tiff"),
    "tiff": (KIND_IMAGE, "image/tiff"),
    # documents
    "pdf": (KIND_DOCUMENT, "application/pdf"),
    "docx": (KIND_DOCUMENT, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "rtf": (KIND_DOCUMENT, "application/rtf"),
    "txt": (KIND_TEXT, "text/plain"),
    "md": (KIND_TEXT, "text/markdown"),
    "markdown": (KIND_TEXT, "text/markdown"),
    "log": (KIND_TEXT, "text/plain"),
    "text": (KIND_TEXT, "text/plain"),
    # spreadsheets
    "xlsx": (KIND_SPREADSHEET, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "xls": (KIND_SPREADSHEET, "application/vnd.ms-excel"),
    "ods": (KIND_SPREADSHEET, "application/vnd.oasis.opendocument.spreadsheet"),
    "csv": (KIND_SPREADSHEET, "text/csv"),
    "tsv": (KIND_SPREADSHEET, "text/tab-separated-values"),
    # code / structured text
    "json": (KIND_CODE, "application/json"),
    "jsonl": (KIND_CODE, "application/x-ndjson"),
    "yaml": (KIND_CODE, "application/yaml"),
    "yml": (KIND_CODE, "application/yaml"),
    "xml": (KIND_CODE, "application/xml"),
    "html": (KIND_CODE, "text/html"),
    "htm": (KIND_CODE, "text/html"),
    "css": (KIND_CODE, "text/css"),
    "js": (KIND_CODE, "text/javascript"),
    "jsx": (KIND_CODE, "text/javascript"),
    "ts": (KIND_CODE, "text/typescript"),
    "tsx": (KIND_CODE, "text/typescript"),
    "py": (KIND_CODE, "text/x-python"),
    "rb": (KIND_CODE, "text/x-ruby"),
    "go": (KIND_CODE, "text/x-go"),
    "rs": (KIND_CODE, "text/x-rust"),
    "java": (KIND_CODE, "text/x-java"),
    "kt": (KIND_CODE, "text/x-kotlin"),
    "c": (KIND_CODE, "text/x-c"),
    "h": (KIND_CODE, "text/x-c"),
    "cpp": (KIND_CODE, "text/x-c++"),
    "hpp": (KIND_CODE, "text/x-c++"),
    "cs": (KIND_CODE, "text/x-csharp"),
    "php": (KIND_CODE, "text/x-php"),
    "swift": (KIND_CODE, "text/x-swift"),
    "sql": (KIND_CODE, "application/sql"),
    "sh": (KIND_CODE, "application/x-sh"),
    "bash": (KIND_CODE, "application/x-sh"),
    "zsh": (KIND_CODE, "application/x-sh"),
    "ps1": (KIND_CODE, "application/x-powershell"),
    "toml": (KIND_CODE, "application/toml"),
    "ini": (KIND_CODE, "text/plain"),
    "cfg": (KIND_CODE, "text/plain"),
    "conf": (KIND_CODE, "text/plain"),
    "env": (KIND_CODE, "text/plain"),
    "dockerfile": (KIND_CODE, "text/plain"),
    "makefile": (KIND_CODE, "text/plain"),
    "lua": (KIND_CODE, "text/x-lua"),
    "r": (KIND_CODE, "text/x-r"),
    "scala": (KIND_CODE, "text/x-scala"),
    "pl": (KIND_CODE, "text/x-perl"),
    # archives
    "zip": (KIND_ARCHIVE, "application/zip"),
    "tar": (KIND_ARCHIVE, "application/x-tar"),
    "gz": (KIND_ARCHIVE, "application/gzip"),
    "tgz": (KIND_ARCHIVE, "application/gzip"),
    # video
    "mp4": (KIND_VIDEO, "video/mp4"),
    "m4v": (KIND_VIDEO, "video/mp4"),
    "mov": (KIND_VIDEO, "video/quicktime"),
    "webm": (KIND_VIDEO, "video/webm"),
    "mkv": (KIND_VIDEO, "video/x-matroska"),
    # audio
    "mp3": (KIND_AUDIO, "audio/mpeg"),
    "wav": (KIND_AUDIO, "audio/wav"),
    "m4a": (KIND_AUDIO, "audio/mp4"),
    "ogg": (KIND_AUDIO, "audio/ogg"),
    "oga": (KIND_AUDIO, "audio/ogg"),
    "flac": (KIND_AUDIO, "audio/flac"),
    "aac": (KIND_AUDIO, "audio/aac"),
    "opus": (KIND_AUDIO, "audio/opus"),
}

# Signature checks. Each returns True when the bytes look like that family.
# The head is at least 16 bytes; ZIP/Office need the full buffer, so the
# caller passes the whole file for small files and a head for large ones.
def _is_pdf(head: bytes) -> bool:
    return head.startswith(b"%PDF-")


def _is_png(head: bytes) -> bool:
    return head.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(head: bytes) -> bool:
    return head.startswith(b"\xff\xd8\xff")


def _is_gif(head: bytes) -> bool:
    return head.startswith((b"GIF87a", b"GIF89a"))


def _is_webp(head: bytes) -> bool:
    return head.startswith(b"RIFF") and head[8:12] == b"WEBP"


def _is_bmp(head: bytes) -> bool:
    return head.startswith(b"BM")


def _is_tiff(head: bytes) -> bool:
    return head.startswith((b"II*\x00", b"MM\x00*"))


def _is_zip(head: bytes) -> bool:
    return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def _is_ole(head: bytes) -> bool:
    return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _is_rtf(head: bytes) -> bool:
    return head.startswith(b"{\\rtf")


def _is_mp4(head: bytes) -> bool:
    return len(head) >= 12 and head[4:8] == b"ftyp"


def _is_matroska(head: bytes) -> bool:
    return head.startswith(b"\x1a\x45\xdf\xa3")


def _is_ogg(head: bytes) -> bool:
    return head.startswith(b"OggS")


def _is_wav(head: bytes) -> bool:
    return head.startswith(b"RIFF") and head[8:12] == b"WAVE"


def _is_flac(head: bytes) -> bool:
    return head.startswith(b"fLaC")


def _is_mp3(head: bytes) -> bool:
    return head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


def _is_gzip(head: bytes) -> bool:
    return head.startswith(b"\x1f\x8b")


def _is_tar(head: bytes) -> bool:
    # POSIX tar stores "ustar" at offset 257.
    return len(head) >= 262 and head[257:262] == b"ustar"


# Reject types that are well-defined and dangerous regardless of extension.
_BLOCKED_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Windows executable"),
    (b"\x7fELF", "Linux executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O/Java class file"),
    (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
)


def _office_subtype(data: bytes, ext: str) -> str | None:
    """Return 'docx' | 'xlsx' | 'ods' | None for a ZIP payload.

    The extension already chose one; this confirms the archive actually
    contains that document type, so a ZIP renamed to `.docx` is rejected
    instead of being parsed as Word and failing mysteriously.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return None
    if ext == "docx":
        return "docx" if "word/document.xml" in names else None
    if ext == "xlsx":
        return "xlsx" if "xl/workbook.xml" in names else None
    if ext == "ods":
        return "ods" if "content.xml" in names and "mimetype" in names else None
    return None


def detect(filename: str, data: bytes, declared_mime: str | None = None) -> DetectedFile:
    """Classify a file, raising `UnsupportedAttachment` when it is not allowed.

    `data` may be the full payload (preferred) or a head of at least 16 bytes;
    ZIP-based Office detection needs the full payload.
    """
    name = (filename or "").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    # A handful of common extensionless names.
    if not ext:
        lowered = name.lower()
        if lowered in ("dockerfile", "makefile"):
            ext = lowered
    entry = _EXTENSIONS.get(ext)
    if entry is None:
        raise UnsupportedAttachment(
            f"{name or 'file'}: unsupported file type"
            + (f" (.{ext})" if ext else "")
        )
    kind, mime = entry

    head = data[:64]
    for magic, label in _BLOCKED_MAGIC:
        if head.startswith(magic):
            raise UnsupportedAttachment(f"{name}: {label} is not accepted")

    def mismatch(expected: str) -> None:
        raise UnsupportedAttachment(
            f"{name}: contents do not match the {expected} file signature"
        )

    if kind == KIND_IMAGE:
        checks = {
            "png": _is_png, "jpg": _is_jpeg, "jpeg": _is_jpeg, "gif": _is_gif,
            "webp": _is_webp, "bmp": _is_bmp, "tif": _is_tiff, "tiff": _is_tiff,
        }
        if ext in checks and not checks[ext](head):
            mismatch(ext.upper())
    elif ext == "pdf":
        if not _is_pdf(head):
            mismatch("PDF")
    elif ext == "rtf":
        if not _is_rtf(head):
            mismatch("RTF")
    elif ext == "docx" or ext == "xlsx" or ext == "ods":
        if not _is_zip(head):
            mismatch(ext.upper())
        if _office_subtype(data, ext) is None:
            mismatch(ext.upper())
    elif ext == "xls":
        if not _is_ole(head):
            mismatch("Excel 97-2003")
    elif ext == "zip":
        if not _is_zip(head):
            mismatch("ZIP")
    elif ext == "tar":
        if not _is_tar(head):
            mismatch("TAR")
    elif ext in ("gz", "tgz"):
        if not _is_gzip(head):
            mismatch("GZIP")
    elif kind == KIND_VIDEO:
        if ext in ("mp4", "m4v", "mov"):
            if not _is_mp4(head):
                mismatch("MP4/MOV")
        elif ext in ("webm", "mkv"):
            if not _is_matroska(head):
                mismatch("Matroska/WebM")
    elif kind == KIND_AUDIO:
        if ext == "mp3" and not _is_mp3(head):
            mismatch("MP3")
        elif ext == "wav" and not _is_wav(head):
            mismatch("WAV")
        elif ext in ("m4a", "aac") and not (_is_mp4(head) or _is_mp3(head)):
            mismatch("M4A/AAC")
        elif ext in ("ogg", "oga", "opus") and not (_is_ogg(head) or _is_mp3(head)):
            mismatch("OGG/Opus")
        elif ext == "flac" and not _is_flac(head):
            mismatch("FLAC")

    return DetectedFile(kind=kind, mime=mime, ext=ext)
