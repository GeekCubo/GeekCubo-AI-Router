"""On-disk storage for chat attachments.

Every file is written under a UUID-based relative name inside a single
configured directory, so the filename from the client never touches the
filesystem — that removes path traversal as a class rather than validating
against it. Reads resolve the same way and refuse any path that escapes the
root after resolution (defence in depth against a corrupted row).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.config import get_settings


class StorageError(RuntimeError):
    pass


def _sqlite_db_path(url: str) -> Path | None:
    prefix = "sqlite"
    if not url.startswith(prefix):
        return None
    # sqlite+aiosqlite:///./geekcubo.db → ./geekcubo.db
    _, _, rest = url.partition(":///")
    if not rest or rest.startswith(":memory:"):
        return None
    return Path(rest)


def attachments_root() -> Path:
    """The attachment directory, created on demand.

    Precedence: explicit `ATTACHMENT_DIR`, then `attachments/` next to the
    SQLite database file (so the Docker volume that holds the DB also holds
    the files), then `./attachments`.
    """
    settings = get_settings()
    configured = (settings.attachment_dir or "").strip()
    if configured:
        root = Path(configured)
    else:
        db_path = _sqlite_db_path(settings.database_url)
        if db_path is not None:
            root = db_path.parent / "attachments"
        else:
            root = Path("./attachments")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_name(storage_name: str) -> str:
    """Reject any storage name that is not a plain relative path component."""
    if not storage_name or storage_name.startswith(("/", "\\")):
        raise StorageError("invalid storage name")
    if ".." in Path(storage_name).parts:
        raise StorageError("invalid storage name")
    return storage_name


def new_storage_name(ext: str) -> str:
    suffix = f".{ext}" if ext else ""
    return f"{uuid.uuid4().hex}{suffix}"


def write_bytes(storage_name: str, data: bytes) -> Path:
    root = attachments_root()
    name = _safe_name(storage_name)
    target = (root / name)
    resolved = target.resolve()
    if root.resolve() not in resolved.parents and resolved.parent != root.resolve():
        raise StorageError("invalid storage name")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp = resolved.with_suffix(resolved.suffix + ".part")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, resolved)
    return resolved


def path_for(storage_name: str) -> Path:
    root = attachments_root()
    name = _safe_name(storage_name)
    resolved = (root / name).resolve()
    if root.resolve() not in resolved.parents and resolved.parent != root.resolve():
        raise StorageError("invalid storage name")
    return resolved


def read_bytes(storage_name: str) -> bytes:
    path = path_for(storage_name)
    try:
        return path.read_bytes()
    except FileNotFoundError as err:
        raise StorageError("attachment file is missing on disk") from err


def delete(storage_name: str) -> None:
    """Best-effort removal; a missing file is not an error."""
    try:
        path = path_for(storage_name)
    except StorageError:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return
