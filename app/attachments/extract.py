"""Text and image extraction for chat attachments.

Each extractor is bounded: it stops at the configured caps instead of
raising, records whether it truncated, and never writes user content to
disk (video frames go to a temporary directory that is removed after the
frames are encoded). A failure in one extractor surfaces as
`ExtractionResult(state=STATE_FAILED)` with a human message; the upload
itself still succeeds so the operator can see the file was received.

No optional dependency is imported at module import time: PDF/DOCX/XLSX/
Pillow are imported inside their extractors, so a deployment missing one
degrades that type only.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.attachments.types import (
    AUDIO_TRANSCRIBE_NOTE,
    IMAGE_JPEG_QUALITY,
    IMAGE_MAX_DIMENSION,
    IMAGE_THUMBNAIL_DIMENSION,
    KIND_ARCHIVE,
    KIND_AUDIO,
    KIND_CODE,
    KIND_DOCUMENT,
    KIND_IMAGE,
    KIND_SPREADSHEET,
    KIND_TEXT,
    KIND_VIDEO,
    MAX_DOCX_PARAGRAPHS,
    MAX_EXTRACTED_CHARS,
    MAX_PDF_PAGES,
    MAX_SHEET_COLS,
    MAX_SHEET_ROWS,
    MAX_SHEETS,
    MAX_TEXT_READ_BYTES,
    MAX_ZIP_ENTRIES,
    MAX_ZIP_TEXT_BYTES,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    STATE_FAILED,
    STATE_OK,
    STATE_UNSUPPORTED,
    VIDEO_FRAME_DIMENSION,
    VIDEO_MAX_FRAMES,
    ExtractionResult,
)


def _clip(text: str, limit: int = MAX_EXTRACTED_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _read_text_file(path: Path) -> ExtractionResult:
    with open(path, "rb") as fh:
        raw = fh.read(MAX_TEXT_READ_BYTES)
        extra = fh.read(1)
    text = _decode_text(raw)
    text, truncated = _clip(text)
    return ExtractionResult(
        state=STATE_OK,
        text=text,
        truncated=truncated or bool(extra),
        metadata={"bytes_read": len(raw)},
    )


# ── PDF ────────────────────────────────────────────────────────────────────


def _extract_pdf(path: Path) -> ExtractionResult:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ExtractionResult(
            state=STATE_UNSUPPORTED,
            error="PDF support is not installed on this server.",
            metadata={"pages": None},
        )
    try:
        reader = PdfReader(str(path))
        pages = len(reader.pages)
        chunks: list[str] = []
        total = 0
        truncated = pages > MAX_PDF_PAGES
        for index, page in enumerate(reader.pages[:MAX_PDF_PAGES]):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text:
                chunks.append(f"[page {index + 1}]\n{text}")
                total += len(text)
                if total >= MAX_EXTRACTED_CHARS:
                    truncated = True
                    break
        text, clipped = _clip("\n\n".join(chunks))
        return ExtractionResult(
            state=STATE_OK,
            text=text,
            truncated=truncated or clipped,
            metadata={"pages": pages, "pages_extracted": min(pages, MAX_PDF_PAGES)},
        )
    except Exception as err:  # noqa: BLE001  (report, don't crash the upload)
        return ExtractionResult(
            state=STATE_FAILED,
            error=f"Could not read the PDF: {err}"[:300],
        )


# ── DOCX ───────────────────────────────────────────────────────────────────


def _extract_docx(path: Path) -> ExtractionResult:
    try:
        import docx
    except ImportError:
        return ExtractionResult(
            state=STATE_UNSUPPORTED,
            error="DOCX support is not installed on this server.",
        )
    try:
        document = docx.Document(str(path))
        parts: list[str] = []
        chars = 0
        paragraphs = 0
        truncated = False
        for para in document.paragraphs:
            if paragraphs >= MAX_DOCX_PARAGRAPHS:
                truncated = True
                break
            paragraphs += 1
            text = (para.text or "").strip()
            if text:
                parts.append(text)
                chars += len(text)
                if chars >= MAX_EXTRACTED_CHARS:
                    truncated = True
                    break
        if not truncated:
            for table in document.tables:
                if chars >= MAX_EXTRACTED_CHARS:
                    truncated = True
                    break
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    line = " | ".join(cells)
                    if line.strip(" |"):
                        parts.append(line)
                        chars += len(line)
                        if chars >= MAX_EXTRACTED_CHARS:
                            truncated = True
                            break
        text, clipped = _clip("\n".join(parts))
        return ExtractionResult(
            state=STATE_OK,
            text=text,
            truncated=truncated or clipped,
            metadata={
                "paragraphs": len(document.paragraphs),
                "paragraphs_extracted": paragraphs,
                "tables": len(document.tables),
            },
        )
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(
            state=STATE_FAILED,
            error=f"Could not read the DOCX: {err}"[:300],
        )


# ── spreadsheets ───────────────────────────────────────────────────────────


def _format_sheet(rows: list[list[str]], name: str) -> str:
    lines = [f"[sheet: {name}]"]
    for row in rows:
        cells = [c.replace("\n", " ").strip() for c in row[:MAX_SHEET_COLS]]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_xlsx(path: Path) -> ExtractionResult:
    try:
        import openpyxl
    except ImportError:
        return ExtractionResult(
            state=STATE_UNSUPPORTED,
            error="Spreadsheet support is not installed on this server.",
        )
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Could not read the workbook: {err}"[:300])
    parts: list[str] = []
    chars = 0
    truncated = False
    sheets = 0
    try:
        for name in wb.sheetnames[:MAX_SHEETS]:
            sheets += 1
            ws = wb[name]
            rows: list[list[str]] = []
            for index, row in enumerate(ws.iter_rows(values_only=True)):
                if index >= MAX_SHEET_ROWS:
                    truncated = True
                    break
                rows.append(["" if v is None else str(v) for v in row])
            block = _format_sheet(rows, str(name))
            parts.append(block)
            chars += len(block)
            if chars >= MAX_EXTRACTED_CHARS:
                truncated = True
                break
    finally:
        wb.close()
    if len(wb.sheetnames) > MAX_SHEETS:
        truncated = True
    text, clipped = _clip("\n\n".join(parts))
    return ExtractionResult(
        state=STATE_OK,
        text=text,
        truncated=truncated or clipped,
        metadata={"sheets": len(wb.sheetnames), "sheets_extracted": sheets},
    )


def _extract_xls(path: Path) -> ExtractionResult:
    try:
        import xlrd
    except ImportError:
        return ExtractionResult(
            state=STATE_UNSUPPORTED,
            error="Legacy Excel (.xls) support is not installed on this server.",
        )
    try:
        book = xlrd.open_workbook(str(path))
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Could not read the workbook: {err}"[:300])
    parts: list[str] = []
    chars = 0
    truncated = False
    for name in book.sheet_names()[:MAX_SHEETS]:
        sheet = book.sheet_by_name(name)
        rows: list[list[str]] = []
        for r in range(min(sheet.nrows, MAX_SHEET_ROWS)):
            rows.append([str(sheet.cell_value(r, c)) for c in range(min(sheet.ncols, MAX_SHEET_COLS))])
        if sheet.nrows > MAX_SHEET_ROWS or sheet.ncols > MAX_SHEET_COLS:
            truncated = True
        block = _format_sheet(rows, str(name))
        parts.append(block)
        chars += len(block)
        if chars >= MAX_EXTRACTED_CHARS:
            truncated = True
            break
    text, clipped = _clip("\n\n".join(parts))
    return ExtractionResult(
        state=STATE_OK,
        text=text,
        truncated=truncated or clipped,
        metadata={"sheets": len(book.sheet_names())},
    )


_ODS_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


def _extract_ods(path: Path) -> ExtractionResult:
    """ODS without odfpy: parse content.xml and read cell text."""
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open("content.xml") as fh:
                root = ElementTree.parse(fh).getroot()
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Could not read the spreadsheet: {err}"[:300])
    parts: list[str] = []
    chars = 0
    truncated = False
    tables = root.findall(".//table:table", _ODS_NS)
    for table in tables[:MAX_SHEETS]:
        name = table.get(f"{{{_ODS_NS['table']}}}name", "Sheet")
        rows: list[list[str]] = []
        for row in table.findall("table:table-row", _ODS_NS)[:MAX_SHEET_ROWS]:
            cells: list[str] = []
            for cell in row.findall("table:table-cell", _ODS_NS):
                repeated = cell.get(f"{{{_ODS_NS['table']}}}number-columns-repeated")
                value = "".join(cell.itertext()).strip()
                count = min(int(repeated) if repeated and repeated.isdigit() else 1, MAX_SHEET_COLS)
                cells.extend([value] * count)
            rows.append(cells)
        block = _format_sheet(rows, name)
        parts.append(block)
        chars += len(block)
        if chars >= MAX_EXTRACTED_CHARS:
            truncated = True
            break
    if len(tables) > MAX_SHEETS:
        truncated = True
    text, clipped = _clip("\n\n".join(parts))
    return ExtractionResult(
        state=STATE_OK,
        text=text,
        truncated=truncated or clipped,
        metadata={"sheets": len(tables)},
    )


def _extract_delimited(path: Path, delimiter: str) -> ExtractionResult:
    with open(path, "rb") as fh:
        raw = fh.read(MAX_TEXT_READ_BYTES)
        extra = fh.read(1)
    text = _decode_text(raw)
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error:
        clipped, was_clipped = _clip(text)
        return ExtractionResult(state=STATE_OK, text=clipped, truncated=was_clipped)
    truncated = bool(extra) or len(rows) > MAX_SHEET_ROWS
    body = "\n".join(" | ".join(r[:MAX_SHEET_COLS]) for r in rows[:MAX_SHEET_ROWS])
    body, clipped = _clip(body)
    return ExtractionResult(
        state=STATE_OK,
        text=body,
        truncated=truncated or clipped,
        metadata={"rows": len(rows)},
    )


# ── RTF ────────────────────────────────────────────────────────────────────

_RTF_CONTROL = re.compile(r"\\[a-zA-Z]+-?\d* ?")
_RTF_HEX = re.compile(r"\\'[0-9a-fA-F]{2}")
_RTF_GROUP = re.compile(r"[{}]")


def _extract_rtf(path: Path) -> ExtractionResult:
    with open(path, "rb") as fh:
        raw = fh.read(MAX_TEXT_READ_BYTES)
    source = raw.decode("latin-1", "replace")
    # Drop embedded binary/object groups rather than their textual noise.
    text = re.sub(r"\\\*.*?;", " ", source, flags=re.S)
    text = _RTF_HEX.sub(" ", text)
    text = text.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", "\t")
    text = _RTF_CONTROL.sub(" ", text)
    text = _RTF_GROUP.sub(" ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    text, truncated = _clip(text)
    return ExtractionResult(state=STATE_OK, text=text, truncated=truncated, metadata={})


# ── archives ───────────────────────────────────────────────────────────────


def _safe_zip_member(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return False
    return ".." not in Path(name).parts


def _extract_zip(path: Path) -> ExtractionResult:
    """Never extract to disk. List entries and read a bounded amount of text."""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            total_uncompressed = sum(max(i.file_size, 0) for i in infos)
            listed = infos[:MAX_ZIP_ENTRIES]
            names = [i.filename for i in listed if _safe_zip_member(i.filename)]
            lines = [
                f"Archive contains {len(infos)} entr{'y' if len(infos) == 1 else 'ies'} "
                f"({total_uncompressed} bytes uncompressed).",
                "",
            ]
            lines.extend(f"- {name}" for name in names)
            if len(infos) > MAX_ZIP_ENTRIES:
                lines.append(f"- … {len(infos) - MAX_ZIP_ENTRIES} more entries not listed")
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                return ExtractionResult(
                    state=STATE_OK,
                    text="\n".join(lines),
                    truncated=True,
                    metadata={"entries": len(infos), "listed": len(names), "refused_text": True},
                )
            budget = MAX_ZIP_TEXT_BYTES
            text_parts: list[str] = []
            for info in listed:
                if budget <= 0:
                    break
                if not _safe_zip_member(info.filename) or info.is_dir():
                    continue
                ext = info.filename.rsplit(".", 1)[-1].lower() if "." in info.filename else ""
                if ext not in ("txt", "md", "csv", "tsv", "json", "log", "yml", "yaml", "xml"):
                    continue
                try:
                    with zf.open(info) as fh:
                        chunk = fh.read(min(budget, info.file_size + 1))
                except Exception:
                    continue
                budget -= len(chunk)
                text_parts.append(f"[{info.filename}]\n{_decode_text(chunk)}")
            if text_parts:
                lines.append("")
                lines.extend(text_parts)
            text, clipped = _clip("\n".join(lines))
            return ExtractionResult(
                state=STATE_OK,
                text=text,
                truncated=clipped or len(infos) > MAX_ZIP_ENTRIES or budget <= 0,
                metadata={"entries": len(infos), "listed": len(names)},
            )
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Could not read the archive: {err}"[:300])


def _extract_archive_other(path: Path) -> ExtractionResult:
    """tar/gz: we do not expand them, only report that they are archives."""
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return ExtractionResult(
        state=STATE_OK,
        text=(
            "Archive attached. Compressed archives are listed by name only; "
            "GeekCubo does not expand tar/gzip uploads."
        ),
        metadata={"size_bytes": size},
    )


# ── images ─────────────────────────────────────────────────────────────────


def _image_data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _extract_image(path: Path, original: bytes) -> ExtractionResult:
    try:
        from PIL import Image
    except ImportError:
        return ExtractionResult(
            state=STATE_FAILED,
            error="Image processing support is not installed on this server.",
        )
    try:
        with Image.open(io.BytesIO(original)) as img:
            img.load()
            width, height = img.size
            fmt = (img.format or "").upper()
            # Animated GIFs: keep the first frame for the model.
            if getattr(img, "is_animated", False):
                img.seek(0)
            rgb = img.convert("RGB")
            scaled = rgb.copy()
            scaled.thumbnail((IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION))
            out = io.BytesIO()
            scaled.save(out, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
            primary = out.getvalue()

            thumb_img = rgb.copy()
            thumb_img.thumbnail((IMAGE_THUMBNAIL_DIMENSION, IMAGE_THUMBNAIL_DIMENSION))
            thumb = io.BytesIO()
            thumb_img.save(thumb, format="JPEG", quality=70, optimize=True)

        return ExtractionResult(
            state=STATE_OK,
            text="",
            image_data_urls=[_image_data_url(primary, "image/jpeg")],
            metadata={
                "width": width,
                "height": height,
                "format": fmt,
                "resized": (scaled.size != (width, height)),
                "thumbnail_data_url": _image_data_url(thumb.getvalue(), "image/jpeg"),
            },
        )
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Could not read the image: {err}"[:300])


# ── video / audio (ffmpeg) ─────────────────────────────────────────────────


def _which(name: str) -> str | None:
    return shutil.which(name)


def _ffprobe_metadata(path: Path) -> dict:
    exe = _which("ffprobe")
    if not exe:
        return {}
    try:
        proc = subprocess.run(
            [
                exe, "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path),
            ],
            capture_output=True, timeout=20, check=False,
        )
        if proc.returncode != 0:
            return {}
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception:
        return {}
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    out: dict = {}
    try:
        if fmt.get("duration"):
            out["duration_s"] = round(float(fmt["duration"]), 2)
    except (TypeError, ValueError):
        pass
    if video:
        out["width"] = video.get("width")
        out["height"] = video.get("height")
        out["video_codec"] = video.get("codec_name")
        try:
            out["fps"] = round(float(video.get("avg_frame_rate", "0/1").split("/")[0]) / max(float(video.get("avg_frame_rate", "0/1").split("/")[1] or 1), 1e-9), 2)
        except (ValueError, ZeroDivisionError, IndexError):
            pass
    if audio:
        out["audio_codec"] = audio.get("codec_name")
        out["audio_channels"] = audio.get("channels")
    return out


def _ffmpeg_frames(path: Path, duration_s: float | None) -> list[str]:
    exe = _which("ffmpeg")
    if not exe:
        return []
    tmp = tempfile.mkdtemp(prefix="geekcubo-frames-")
    try:
        urls: list[str] = []
        # Evenly spaced timestamps; ffmpeg seeks before decoding.
        if duration_s and duration_s > 1:
            points = [duration_s * (i + 0.5) / VIDEO_MAX_FRAMES for i in range(VIDEO_MAX_FRAMES)]
        else:
            points = [0.0]
        for index, ts in enumerate(points):
            target = Path(tmp) / f"frame-{index}.jpg"
            try:
                proc = subprocess.run(
                    [
                        exe, "-v", "error", "-ss", f"{ts:.2f}", "-i", str(path),
                        "-frames:v", "1",
                        "-vf", f"scale='min({VIDEO_FRAME_DIMENSION},iw)':-2",
                        str(target),
                    ],
                    capture_output=True, timeout=30, check=False,
                )
            except Exception:
                continue
            if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
                urls.append(_image_data_url(target.read_bytes(), "image/jpeg"))
        return urls
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _extract_video(path: Path) -> ExtractionResult:
    meta = _ffprobe_metadata(path)
    frames = _ffmpeg_frames(path, meta.get("duration_s"))
    meta["frames_extracted"] = len(frames)
    if not frames:
        if not _which("ffmpeg"):
            return ExtractionResult(
                state=STATE_UNSUPPORTED,
                error="Video attached, but this server cannot read it (ffmpeg is not available).",
                metadata=meta,
            )
        return ExtractionResult(
            state=STATE_FAILED,
            error="Video attached, but no frames could be extracted from it.",
            metadata=meta,
        )
    note = (
        f"Video attached ({meta.get('duration_s', 'unknown')}s"
        + (f", {meta.get('width')}x{meta.get('height')}" if meta.get("width") else "")
        + f"). {len(frames)} representative frame(s) are included."
    )
    return ExtractionResult(
        state=STATE_OK,
        text=note,
        image_data_urls=frames,
        metadata=meta,
        truncated=len(frames) < VIDEO_MAX_FRAMES,
    )


def _extract_audio(path: Path) -> ExtractionResult:
    meta = _ffprobe_metadata(path)
    meta["transcribed"] = False
    meta["metadata_only"] = True
    lines = [AUDIO_TRANSCRIBE_NOTE]
    if meta.get("duration_s"):
        lines.append(f"Duration: {meta['duration_s']}s.")
    if meta.get("audio_codec"):
        lines.append(f"Codec: {meta['audio_codec']}.")
    return ExtractionResult(state=STATE_OK, text=" ".join(lines), metadata=meta)


# ── dispatch ───────────────────────────────────────────────────────────────


def extract(kind: str, ext: str, path: Path, data: bytes) -> ExtractionResult:
    """Extract text and/or image parts for a detected file."""
    try:
        if kind == KIND_IMAGE:
            return _extract_image(path, data)
        if kind == KIND_DOCUMENT:
            if ext == "pdf":
                return _extract_pdf(path)
            if ext == "docx":
                return _extract_docx(path)
            if ext == "rtf":
                return _extract_rtf(path)
            return _read_text_file(path)
        if kind == KIND_SPREADSHEET:
            if ext == "xlsx":
                return _extract_xlsx(path)
            if ext == "xls":
                return _extract_xls(path)
            if ext == "ods":
                return _extract_ods(path)
            if ext == "tsv":
                return _extract_delimited(path, "\t")
            return _extract_delimited(path, ",")
        if kind in (KIND_TEXT, KIND_CODE):
            return _read_text_file(path)
        if kind == KIND_ARCHIVE:
            if ext == "zip":
                return _extract_zip(path)
            return _extract_archive_other(path)
        if kind == KIND_VIDEO:
            return _extract_video(path)
        if kind == KIND_AUDIO:
            return _extract_audio(path)
        return ExtractionResult(
            state=STATE_UNSUPPORTED, error="This file type has no extractor."
        )
    except Exception as err:  # noqa: BLE001
        return ExtractionResult(state=STATE_FAILED, error=f"Extraction failed: {err}"[:300])
