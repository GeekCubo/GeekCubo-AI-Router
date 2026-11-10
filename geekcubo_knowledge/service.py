"""The one retrieval service behind Ask GeekCubo (native Chat) and the MCP server.

Read-only over a prebuilt SQLite FTS5 index. Callers address documentation
only by section id (``docs/routing.md#strategies``) or by document path from
the allowlist; there is no way to name an arbitrary file.

    svc = KnowledgeService.open_default()
    svc.search("enable searxng", limit=5)
    svc.read("docs/chat.md#web-search-optional-off-by-default")
    svc.version()
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from geekcubo_knowledge.index import INDEX_FILENAME, SCHEMA_VERSION
from geekcubo_knowledge.sources import ALLOWED_PATHS

MAX_QUERY_CHARS = 500
MAX_RESULTS = 10
DEFAULT_RESULTS = 5
MAX_EXCERPT_CHARS = 700
MAX_READ_CHARS = 12_000
MIN_COVERAGE = 0.35  # rarity-weighted share of query terms a section must contain
MIN_SCORE = 3.5      # ...and, unless it contains all of them, this much evidence

# Words that carry no signal in a "how do I…" question. Removing them keeps
# FTS ranking on the terms that matter (searxng, rotate, balanced, …).
_STOPWORDS = frozenset("""
a an and are as at be but by can could do does doing for from how i if in into is it its
me my of on or our should so that the their then there these this to was we what when
where which who why will with would you your yours geekcubo please tell explain about
difference between differences versus vs compare comparison meaning mean means work works
use using used need want get set make way best any some there here also just like does did
""".split())
_TOKEN = re.compile(r"[\w\-]+|/[\w\-/.{}]+", re.UNICODE)
_ID = re.compile(r"^[A-Za-z0-9_./\-]+(#[\w\-~.]+)?$")


class KnowledgeUnavailable(RuntimeError):
    """The index is missing, unreadable or from an unsupported schema."""


class DocNotFound(LookupError):
    """The id does not name an indexed section or allowlisted document."""


@dataclass(frozen=True)
class SearchHit:
    id: str
    path: str
    title: str          # document title, e.g. "Routing"
    heading: str        # section heading
    breadcrumb: str
    excerpt: str
    score: float
    reference: str      # "Routing → Strategies"

    def to_dict(self) -> dict:
        return asdict(self)


def default_index_path() -> Path:
    override = os.environ.get("GEEKCUBO_KNOWLEDGE_INDEX")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "data" / INDEX_FILENAME


def _reference(title: str, heading: str) -> str:
    return f"{title} → {heading}" if heading and heading != title else title


def build_match_query(query: str) -> str | None:
    """Turn free text into a safe FTS5 expression.

    Every term is quoted, so FTS operators in user input (NEAR, AND, column
    filters, quotes) are inert. Terms are OR-ed and ranked by bm25; an exact
    phrase of the whole query is added as a boosted alternative.
    """
    terms: list[str] = []
    for tok in _TOKEN.findall(query or ""):
        t = tok.strip("-/.").lower()
        if len(t) < 2 or t in _STOPWORDS:
            continue
        # A path like /v1/chat/completions: index tokens are its segments.
        for piece in re.split(r"[/.]", t):
            if len(piece) >= 2 and piece not in _STOPWORDS and piece not in terms:
                terms.append(piece)
    if not terms:
        return None
    quoted = [f'"{t}"' for t in terms[:16]]
    expr = " OR ".join(quoted)
    if len(terms) > 1:
        expr = f'("{" ".join(terms[:8])}") OR {expr}'
    return expr


class KnowledgeService:
    def __init__(self, index_path: Path):
        self.index_path = Path(index_path)
        self._lock = threading.Lock()
        self._con: sqlite3.Connection | None = None
        self._meta: dict[str, str] | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    @classmethod
    def open_default(cls) -> KnowledgeService:
        return cls(default_index_path())

    def _connect(self) -> sqlite3.Connection:
        if self._con is not None:
            return self._con
        if not self.index_path.is_file():
            raise KnowledgeUnavailable(
                f"Documentation index not found at {self.index_path.name}. "
                "Rebuild it with `python -m geekcubo_knowledge build`."
            )
        try:
            con = sqlite3.connect(
                f"file:{self.index_path}?mode=ro&immutable=1", uri=True, check_same_thread=False
            )
            meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
            con.execute("SELECT count(*) FROM sections_fts").fetchone()
        except sqlite3.DatabaseError as err:
            raise KnowledgeUnavailable(f"Documentation index is unreadable: {err}") from err
        if meta.get("schema_version") != str(SCHEMA_VERSION):
            con.close()
            raise KnowledgeUnavailable(
                f"Documentation index schema {meta.get('schema_version')!r} is not supported "
                f"(expected {SCHEMA_VERSION}). Rebuild it."
            )
        from geekcubo_knowledge import __version__

        if meta.get("app_version") != __version__:
            con.close()
            raise KnowledgeUnavailable("Documentation version does not match this package. Rebuild the index.")
        self._con, self._meta = con, meta
        return con

    def available(self) -> bool:
        try:
            with self._lock:
                self._connect()
            return True
        except KnowledgeUnavailable:
            return False

    # ── public API ─────────────────────────────────────────────────────────
    def version(self) -> dict:
        with self._lock:
            self._connect()
            meta = dict(self._meta or {})
        return {
            "docs_version": meta.get("app_version", "unknown"),
            "schema_version": int(meta.get("schema_version", 0)),
            "docs_sha256": meta.get("docs_sha256"),
            "document_count": int(meta.get("document_count", 0)),
            "section_count": int(meta.get("section_count", 0)),
            "source": "bundled documentation package",
        }

    def documents(self) -> list[dict]:
        import json

        with self._lock:
            self._connect()
            docs = json.loads((self._meta or {}).get("documents", "[]"))
        return [{"path": p, "title": t} for p, t in docs]

    def search(self, query: str, limit: int = DEFAULT_RESULTS) -> list[SearchHit]:
        query = (query or "").strip()
        if not query:
            raise ValueError("Query is empty.")
        if len(query) > MAX_QUERY_CHARS:
            query = query[:MAX_QUERY_CHARS]
        limit = max(1, min(int(limit or DEFAULT_RESULTS), MAX_RESULTS))
        expr = build_match_query(query)
        if expr is None:
            return []
        terms = [t for t in re.findall(r'"([^"]+)"', expr) if " " not in t]
        with self._lock:
            con = self._connect()
            # Over-fetch, then re-rank in Python: bm25 alone lets frequent,
            # generic words ("configure", "data") outweigh the rare word that
            # names the topic. Two cheap, deterministic signals fix that:
            # coverage (how many distinct query terms the section contains)
            # and a heading match.
            rows = con.execute(
                """
                SELECT s.id, s.path, s.doc_title, s.heading, s.breadcrumb, s.body,
                       bm25(sections_fts, 8.0, 3.0, 1.0) AS score, s.ordinal
                FROM sections_fts JOIN sections s ON s.rowid = sections_fts.rowid
                WHERE sections_fts MATCH ?
                ORDER BY score ASC, s.path ASC, s.ordinal ASC
                LIMIT 60
                """,
                (expr,),
            ).fetchall()
            weights = self._term_weights(con, terms)
        ranked = []
        total_w = sum(weights.values()) or 1.0
        for r in rows:
            head = f"{r[3]} {r[4]}".lower()
            text = f"{head} {r[5].lower()}"
            # Rarity-weighted coverage: "searxng" (in 4 sections) counts far
            # more than "enable" (in 30), so the topic word decides relevance.
            coverage = sum(w for t, w in weights.items() if t in text) / total_w
            in_head = sum(w for t, w in weights.items() if t in head) / total_w * len(weights)
            score = -float(r[6]) * (0.5 + coverage) + 2.0 * in_head
            # Relevance floor: a section that shares only an incidental word
            # with the question ("best", "today") is noise, not an answer.
            # Better to report "not documented" than to ground on it.
            if coverage < MIN_COVERAGE or (coverage < 1.0 and score < MIN_SCORE):
                continue
            ranked.append((score, r))
        ranked.sort(key=lambda x: (-x[0], x[1][1], x[1][7]))
        return [
            SearchHit(
                id=r[0], path=r[1], title=r[2], heading=r[3], breadcrumb=r[4],
                excerpt=_excerpt(r[5], terms, MAX_EXCERPT_CHARS),
                score=round(score, 4),
                reference=_reference(r[2], r[3]),
            )
            for score, r in ranked[:limit]
        ]

    def _term_weights(self, con: sqlite3.Connection, terms: list[str]) -> dict[str, float]:
        """IDF weight per query term (log N/df), from the index itself."""
        import math

        n = con.execute("SELECT count(*) FROM sections").fetchone()[0] or 1
        out: dict[str, float] = {}
        for t in terms:
            df = con.execute(
                "SELECT count(*) FROM sections_fts WHERE sections_fts MATCH ?", (f'"{t}"',)
            ).fetchone()[0]
            out[t] = math.log((n + 1) / (df + 0.5))
        return out

    def read(self, doc_id: str, *, max_chars: int = MAX_READ_CHARS) -> dict:
        """Read one section (``path#anchor``) or a whole document (``path``).

        Only ids present in the index resolve. A path must be on the
        allowlist; nothing touches the filesystem beyond the index file.
        """
        doc_id = (doc_id or "").strip()
        if not doc_id or len(doc_id) > 300 or not _ID.match(doc_id) or ".." in doc_id:
            raise DocNotFound("Invalid document id.")
        max_chars = max(200, min(int(max_chars), MAX_READ_CHARS))
        with self._lock:
            con = self._connect()
            if "#" in doc_id:
                row = con.execute(
                    "SELECT id, path, doc_title, heading, breadcrumb, body FROM sections WHERE id = ?",
                    (doc_id,),
                ).fetchone()
                if row is None:
                    raise DocNotFound(f"No section {doc_id!r} in the installed documentation.")
                rows = [row]
            else:
                if doc_id not in ALLOWED_PATHS:
                    raise DocNotFound(f"{doc_id!r} is not an indexed GeekCubo document.")
                rows = con.execute(
                    "SELECT id, path, doc_title, heading, breadcrumb, body FROM sections "
                    "WHERE path = ? ORDER BY ordinal",
                    (doc_id,),
                ).fetchall()
                if not rows:
                    raise DocNotFound(f"{doc_id!r} is not in the installed documentation.")
        if len(rows) == 1:
            r = rows[0]
            text = r[5]
            heading, breadcrumb = r[3], r[4]
        else:
            text = "\n\n".join(
                (("#" * 2 + " " + r[3] + "\n\n") if r[3] else "") + r[5] for r in rows
            )
            heading, breadcrumb = "", ""
        truncated = len(text) > max_chars
        r0 = rows[0]
        return {
            "id": doc_id,
            "path": r0[1],
            "title": r0[2],
            "heading": heading,
            "breadcrumb": breadcrumb,
            "content": text[:max_chars],
            "truncated": truncated,
            "reference": _reference(r0[2], heading),
            "docs_version": self.version()["docs_version"],
            "sections": [r[0] for r in rows] if len(rows) > 1 else None,
        }


def _excerpt(body: str, terms: list[str], limit: int) -> str:
    """A window of the section around the first matching term."""
    text = body.strip()
    if len(text) <= limit:
        return text
    low = text.lower()
    pos = min((low.find(t) for t in terms if t and low.find(t) >= 0), default=0)
    start = max(0, pos - limit // 4)
    # Do not start inside a code fence marker if avoidable: snap to a line start.
    nl = text.rfind("\n", 0, start)
    if nl != -1 and start - nl < 120:
        start = nl + 1
    chunk = text[start:start + limit]
    return ("… " if start else "") + chunk.rstrip() + (" …" if start + limit < len(text) else "")


_default: KnowledgeService | None = None
_default_lock = threading.Lock()


def get_service() -> KnowledgeService:
    """Process-wide service over the bundled index (opened lazily)."""
    global _default
    with _default_lock:
        if _default is None or _default.index_path != default_index_path():
            _default = KnowledgeService.open_default()
        return _default
