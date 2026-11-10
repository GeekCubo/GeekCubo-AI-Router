"""Building the GeekCubo Knowledge index: Markdown sections in SQLite FTS5.

The index is a small SQLite file generated from the allowlisted documents in
`sources.py`. It is built ahead of time (wheel/Docker build, or
`python -m geekcubo_knowledge build`) and only ever read at runtime.

Design choices:

* **Sections, not arbitrary windows.** Each chunk is one Markdown heading and
  its body, with the parent headings kept as a breadcrumb. A section longer
  than the chunk budget is split on paragraph boundaries, never inside a
  fenced code block, so an example stays with the text that explains it.
* **Stable ids.** A section id is ``<path>#<heading-slug>`` (plus ``~2``,
  ``~3`` for repeated headings and ``.p2`` for continuation parts). It only
  changes when the heading changes.
* **Deterministic.** Same inputs → byte-identical rows in the same order; the
  build records a content hash so a stale index is detectable.
* **Exact tokens.** FTS5 ``unicode61`` with ``_`` and ``-`` kept inside
  tokens, so ``API_KEY_PEPPER``, ``x-geek-routing-diagnosis`` and
  ``/v1/chat/completions`` match as written.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from geekcubo_knowledge.sources import DOC_SOURCES

SCHEMA_VERSION = 1
MAX_CHUNK_CHARS = 2400
INDEX_FILENAME = "knowledge.sqlite3"

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Section:
    id: str
    path: str
    doc_title: str
    heading: str          # the section's own heading ("" for a preamble)
    breadcrumb: str       # "Routing › Strategies"
    level: int
    ordinal: int          # position within the document
    body: str


def slugify(text: str) -> str:
    """GitHub-style anchor slug, so ids double as working Markdown anchors."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r" ", "-", text) or "section"


def _clean_heading(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.strip()


def _split_blocks(body: str) -> list[str]:
    """Paragraph blocks; a fenced code block (and the paragraph that
    introduces it) is kept as one unit."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in body.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
            current.append(line)
            continue
        if not in_fence and not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    # Glue a block that ends with ":" (an introduction) to the next block.
    merged: list[str] = []
    for block in blocks:
        if merged and merged[-1].rstrip().endswith(":"):
            merged[-1] = merged[-1] + "\n\n" + block
        else:
            merged.append(block)
    return merged


def _pack(blocks: list[str], limit: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + 2 + len(block) > limit:
            parts.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        parts.append(current)
    return parts


def split_markdown(path: str, text: str, doc_title: str) -> list[Section]:
    """Split one Markdown document into sections with stable ids."""
    lines = text.replace("\r\n", "\n").split("\n")
    raw: list[tuple[int, str, list[str]]] = []  # (level, heading, body lines)
    level, heading, body = 0, "", []
    in_fence = False
    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            raw.append((level, heading, body))
            level, heading, body = len(m.group(1)), _clean_heading(m.group(2)), []
        else:
            body.append(line)
    raw.append((level, heading, body))

    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    ordinal = 0
    for lvl, head, body_lines in raw:
        content = "\n".join(body_lines).strip()
        if lvl:
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, head))
        if not content and not head:
            continue
        crumbs = [h for _, h in stack] if lvl else []
        breadcrumb = " › ".join(crumbs)
        base = slugify(head) if head else "intro"
        seen[base] = seen.get(base, 0) + 1
        anchor = base if seen[base] == 1 else f"{base}~{seen[base]}"
        parts = _pack(_split_blocks(content), MAX_CHUNK_CHARS) if content else [""]
        for i, part in enumerate(parts):
            sid = f"{path}#{anchor}" + (f".p{i + 1}" if i else "")
            sections.append(Section(
                id=sid, path=path, doc_title=doc_title, heading=head,
                breadcrumb=breadcrumb, level=lvl, ordinal=ordinal, body=part,
            ))
            ordinal += 1
    return sections


def read_sources(root: Path) -> list[tuple[str, str, str]]:
    """(path, title, text) for every allowlisted document that exists."""
    out = []
    for rel, title in DOC_SOURCES:
        p = (root / rel)
        if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve()):
            out.append((rel, title, p.read_text(encoding="utf-8")))
    return out


def project_version(root: Path) -> str:
    try:
        import tomllib

        with open(root / "pyproject.toml", "rb") as f:
            return str(tomllib.load(f)["project"]["version"])
    except Exception:
        try:
            from importlib.metadata import version

            return version("geekcubo")
        except Exception:
            return "unknown"


def build_index(root: Path, out_path: Path, *, version: str | None = None) -> dict:
    """Build the index atomically. Returns the metadata written."""
    docs = read_sources(root)
    sections: list[Section] = []
    digest = hashlib.sha256()
    for rel, title, text in docs:
        digest.update(rel.encode() + b"\0" + text.encode("utf-8") + b"\0")
        sections.extend(split_markdown(rel, text, title))
    meta = {
        "schema_version": str(SCHEMA_VERSION),
        "app_version": version or project_version(root),
        "docs_sha256": digest.hexdigest(),
        "document_count": str(len(docs)),
        "section_count": str(len(sections)),
        "documents": json.dumps([[rel, title] for rel, title, _ in docs]),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".knowledge-", suffix=".tmp", dir=out_path.parent)
    os.close(fd)
    try:
        con = sqlite3.connect(tmp)
        con.executescript("""
            PRAGMA journal_mode=DELETE;
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE sections (
                rowid INTEGER PRIMARY KEY,
                id TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                doc_title TEXT NOT NULL,
                heading TEXT NOT NULL,
                breadcrumb TEXT NOT NULL,
                level INTEGER NOT NULL,
                ordinal INTEGER NOT NULL,
                body TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE sections_fts USING fts5(
                heading, breadcrumb, body,
                content='sections', content_rowid='rowid',
                tokenize="unicode61 tokenchars '_-'"
            );
        """)
        for rowid, s in enumerate(sections, start=1):
            con.execute(
                "INSERT INTO sections VALUES (?,?,?,?,?,?,?,?,?)",
                (rowid, s.id, s.path, s.doc_title, s.heading, s.breadcrumb, s.level, s.ordinal, s.body),
            )
        con.execute("INSERT INTO sections_fts(sections_fts) VALUES ('rebuild')")
        con.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
        con.commit()
        con.execute("VACUUM")
        con.close()
        os.chmod(tmp, 0o644)
        os.replace(tmp, out_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return meta
