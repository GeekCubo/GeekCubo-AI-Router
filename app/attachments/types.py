"""Native Chat attachments — shared types and limits.

The constants here are the single source of truth for what the upload
endpoint accepts and how much work the extractors are allowed to do. They
are deliberately conservative: every limit exists to stop a hostile or
merely huge file from consuming the process, and every extractor stops at
its cap instead of raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Coarse buckets the UI renders and the router uses to decide whether a
# request needs a vision-capable model.
KIND_IMAGE = "image"
KIND_DOCUMENT = "document"
KIND_SPREADSHEET = "spreadsheet"
KIND_TEXT = "text"
KIND_CODE = "code"
KIND_ARCHIVE = "archive"
KIND_VIDEO = "video"
KIND_AUDIO = "audio"

KINDS = (
    KIND_IMAGE,
    KIND_DOCUMENT,
    KIND_SPREADSHEET,
    KIND_TEXT,
    KIND_CODE,
    KIND_ARCHIVE,
    KIND_VIDEO,
    KIND_AUDIO,
)

# Extraction states stored on ChatAttachment.extraction_state.
STATE_PENDING = "pending"
STATE_OK = "ok"
STATE_UNSUPPORTED = "unsupported"
STATE_FAILED = "failed"

# ── upload limits ──────────────────────────────────────────────────────────
DEFAULT_MAX_UPLOAD_MB = 25
MAX_ATTACHMENTS_PER_MESSAGE = 8
# Hard ceiling regardless of configuration; a larger file is rejected rather
# than read into memory.
ABSOLUTE_MAX_UPLOAD_MB = 200

# ── extraction limits ──────────────────────────────────────────────────────
# Characters of text any single file may contribute to the model context.
MAX_EXTRACTED_CHARS = 200_000
# Text files larger than this are read only up to the cap above.
MAX_TEXT_READ_BYTES = 4 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_DOCX_PARAGRAPHS = 20_000
MAX_SHEET_ROWS = 5_000
MAX_SHEET_COLS = 64
MAX_SHEETS = 20
# ZIP files are never extracted to disk; we list entries and read a bounded
# amount of their text content.
MAX_ZIP_ENTRIES = 500
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_TEXT_BYTES = 512 * 1024

# Image handling.
IMAGE_MAX_DIMENSION = 1568
IMAGE_THUMBNAIL_DIMENSION = 320
IMAGE_JPEG_QUALITY = 82
# Rough token cost charged per image part during context budgeting. Vision
# models bill a tile grid; this is a deliberately pessimistic constant.
IMAGE_TOKEN_COST = 1000

# Video frame extraction (requires ffmpeg/ffprobe; degrades gracefully).
VIDEO_MAX_FRAMES = 4
VIDEO_FRAME_DIMENSION = 1024

# Audio is metadata-only until a transcription backend is configured.
AUDIO_TRANSCRIBE_NOTE = (
    "Audio file attached. Automatic transcription is not enabled on this "
    "server, so the model cannot hear the audio; its metadata is included."
)


@dataclass
class ExtractionResult:
    """What an extractor produced for one file.

    `text` is the context the model may read. `image_data_urls` are rendered
    image parts (the original image, video frames). `metadata` is JSON-safe
    and stored on the attachment row for display.
    """

    state: str = STATE_OK
    text: str = ""
    image_data_urls: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: str | None = None
    truncated: bool = False


@dataclass
class DetectedFile:
    kind: str
    mime: str
    # Extension used for display; lower-case, no dot ("pdf").
    ext: str
