"""GeekCubo Knowledge: indexing, retrieval, safety and the bundled index.

Builds throwaway indexes from small fixture trees, and checks the real bundled
index is current with the documentation in this repository.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from geekcubo_knowledge import index as idx
from geekcubo_knowledge import service as svc_mod
from geekcubo_knowledge.service import DocNotFound, KnowledgeService, KnowledgeUnavailable
from geekcubo_knowledge.sources import ALLOWED_PATHS, DOC_SOURCES

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "# GeekCubo\n\nIntro text.\n\n## Optional web search\n\n"
        "Enable SearXNG with the search profile:\n\n"
        "```bash\ndocker compose --profile search up -d\n```\n\nThen set the URL.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "security.md").write_text(
        "# Security\n\n## Encryption at rest\n\nThe pepper is `API_KEY_PEPPER` and the key is "
        "`CREDENTIAL_ENCRYPTION_KEY`.\n\n## Encryption at rest\n\nA second section with the same heading.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "routing.md").write_text(
        "# Routing\n\n## Strategies\n\n**Balanced** strategy weighs quality score against blended price.\n\n"
        "## Diagnosis\n\nRead the `x-geek-routing-diagnosis` header and call /v1/chat/completions.\n\n"
        "## Policies\n\n" + ("Fallback order and retry limits apply to every request. " * 12) + "\n",
        encoding="utf-8",
    )
    # Files that exist but are NOT on the allowlist must never be indexed.
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-real-secret-value-123\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n\nprivate-operator-note-xyz\n", encoding="utf-8")
    (tmp_path / "docs" / "private-notes.md").write_text("# Notes\n\nprivate-notes-marker\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname="geekcubo"\nversion="9.8.7"\n', encoding="utf-8")
    return tmp_path


@pytest.fixture
def built(tree: Path, tmp_path: Path, monkeypatch) -> KnowledgeService:
    monkeypatch.setattr("geekcubo_knowledge.__version__", "9.8.7")
    out = tmp_path / "out" / "knowledge.sqlite3"
    idx.build_index(tree, out)
    return KnowledgeService(out)


# ── indexing ────────────────────────────────────────────────────────────────

def test_only_allowlisted_documents_are_indexed(built: KnowledgeService):
    con = sqlite3.connect(built.index_path)
    paths = {r[0] for r in con.execute("SELECT DISTINCT path FROM sections")}
    dump = "\n".join(con.iterdump())
    con.close()
    assert paths <= ALLOWED_PATHS
    assert paths == {"README.md", "docs/security.md", "docs/routing.md"}
    for marker in ("sk-real-secret-value-123", "private-operator-note-xyz", "private-notes-marker"):
        assert marker not in dump


def test_allowlist_never_names_private_files():
    for path, _title in DOC_SOURCES:
        assert path.endswith(".md")
        assert not path.startswith((".", "/")) and ".." not in path
        assert Path(path).name not in {"AGENTS.md", ".env"}


def test_headings_breadcrumbs_and_stable_ids(built: KnowledgeService):
    hit = built.search("Balanced strategy", 3)[0]
    assert hit.id == "docs/routing.md#strategies"
    assert hit.breadcrumb == "Routing › Strategies"
    assert hit.reference == "Routing → Strategies"
    # A repeated heading gets a distinct, stable id.
    con = sqlite3.connect(built.index_path)
    ids = [r[0] for r in con.execute("SELECT id FROM sections WHERE path='docs/security.md' ORDER BY ordinal")]
    con.close()
    assert "docs/security.md#encryption-at-rest" in ids and "docs/security.md#encryption-at-rest~2" in ids


def test_code_examples_stay_with_their_explanation(built: KnowledgeService):
    doc = built.read("README.md#optional-web-search")
    assert "Enable SearXNG with the search profile" in doc["content"]
    assert "docker compose --profile search up -d" in doc["content"]
    assert built.search("profile search up", 3)[0].id == "README.md#optional-web-search"


@pytest.mark.parametrize("query,expected", [
    ("API_KEY_PEPPER", "docs/security.md#encryption-at-rest"),
    ("CREDENTIAL_ENCRYPTION_KEY", "docs/security.md#encryption-at-rest"),
    ("x-geek-routing-diagnosis", "docs/routing.md#diagnosis"),
    ("/v1/chat/completions", "docs/routing.md#diagnosis"),
])
def test_exact_identifiers_match(built: KnowledgeService, query, expected):
    assert built.search(query, 3)[0].id == expected


def test_version_metadata(built: KnowledgeService):
    v = built.version()
    assert v["docs_version"] == "9.8.7"
    assert v["schema_version"] == idx.SCHEMA_VERSION
    assert v["document_count"] == 3 and v["section_count"] > 3
    assert v["source"] == "bundled documentation package"


def test_build_is_deterministic(tree: Path, tmp_path: Path):
    a, b = tmp_path / "a.sqlite3", tmp_path / "b.sqlite3"
    ma, mb = idx.build_index(tree, a), idx.build_index(tree, b)
    assert ma == mb
    rows = lambda p: sqlite3.connect(p).execute("SELECT * FROM sections ORDER BY rowid").fetchall()  # noqa: E731
    assert rows(a) == rows(b)


def test_rebuild_reflects_changed_docs(tree: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr("geekcubo_knowledge.__version__", "9.8.7")
    out = tmp_path / "k.sqlite3"
    idx.build_index(tree, out)
    before = KnowledgeService(out).version()["docs_sha256"]
    (tree / "docs" / "routing.md").write_text("# Routing\n\n## Strategies\n\nNewly documented zebrafish.\n")
    idx.build_index(tree, out)
    fresh = KnowledgeService(out)
    assert fresh.version()["docs_sha256"] != before
    assert fresh.search("zebrafish", 1)[0].id == "docs/routing.md#strategies"


# ── retrieval limits and refusal ────────────────────────────────────────────

def test_results_and_excerpts_are_bounded(built: KnowledgeService):
    assert len(built.search("encryption security routing searxng", 50)) <= svc_mod.MAX_RESULTS
    for hit in built.search("encryption", 10):
        assert len(hit.excerpt) <= svc_mod.MAX_EXCERPT_CHARS + 4
    long_query = "routing " * 400
    assert built.search(long_query, 3)  # truncated, still works


def test_empty_and_noise_queries(built: KnowledgeService):
    with pytest.raises(ValueError):
        built.search("   ", 3)
    assert built.search("the and of how do i", 3) == []
    # FTS syntax in user input is inert, not an error or an injection.
    assert isinstance(built.search('NEAR("x" "y") OR body:* "', 3), list)


@pytest.mark.parametrize("bad", [
    "../.env", "/etc/passwd", ".env", "docs/../.env", "AGENTS.md", "docs/private-notes.md",
    "README.md#does-not-exist", "file:///etc/passwd", "README.md\x00", "x" * 400, "",
])
def test_read_refuses_anything_not_indexed(built: KnowledgeService, bad):
    with pytest.raises(DocNotFound):
        built.read(bad)


def test_read_whole_document_and_truncation(built: KnowledgeService):
    doc = built.read("docs/security.md")
    assert doc["title"] == "Security and API keys" and doc["sections"]
    small = built.read("docs/routing.md", max_chars=200)
    assert small["truncated"] is True and len(small["content"]) <= 200


def test_ranking_ties_are_deterministic(built: KnowledgeService):
    a = [h.id for h in built.search("encryption", 5)]
    b = [h.id for h in built.search("encryption", 5)]
    assert a == b


# ── missing / corrupt / incompatible index ──────────────────────────────────

def test_missing_index_is_reported_not_crashing(tmp_path: Path):
    s = KnowledgeService(tmp_path / "nope.sqlite3")
    assert s.available() is False
    with pytest.raises(KnowledgeUnavailable):
        s.search("routing", 3)


def test_corrupt_index(tmp_path: Path):
    bad = tmp_path / "k.sqlite3"
    bad.write_bytes(b"this is not a database" * 100)
    s = KnowledgeService(bad)
    assert s.available() is False
    with pytest.raises(KnowledgeUnavailable):
        s.version()


def test_unsupported_schema_version(built: KnowledgeService, tmp_path: Path):
    copy = tmp_path / "old.sqlite3"
    copy.write_bytes(built.index_path.read_bytes())
    con = sqlite3.connect(copy)
    con.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    con.commit()
    con.close()
    with pytest.raises(KnowledgeUnavailable, match="schema"):
        KnowledgeService(copy).version()


def test_index_is_opened_read_only(built: KnowledgeService):
    built.version()
    with pytest.raises(sqlite3.OperationalError):
        built._con.execute("DELETE FROM sections")


def test_version_mismatch_is_rejected(built, monkeypatch):
    monkeypatch.setattr("geekcubo_knowledge.__version__", "99.0.0")
    with pytest.raises(KnowledgeUnavailable, match="version"):
        KnowledgeService(built.index_path).version()


def test_allowlisted_symlink_cannot_include_private_content(tree, tmp_path):
    private = tmp_path / "private.txt"
    private.write_text("private-secret-marker")
    (tree / "README.md").unlink()
    (tree / "README.md").symlink_to(private)
    assert "README.md" not in {p for p, _, _ in idx.read_sources(tree)}


# ── the bundled index ───────────────────────────────────────────────────────

def test_bundled_index_is_current_with_the_repository_docs():
    """Fails when docs change without `python -m geekcubo_knowledge build`."""
    from geekcubo_knowledge.__main__ import main

    assert main(["check"]) == 0


@pytest.mark.parametrize("question,acceptable", [
    ("How do I configure GeekCubo with OpenCode?", {"docs/integrations.md#opencode", "README.md#connect-opencode-and-other-tools"}),
    ("What does the Balanced routing strategy do?", {"docs/routing.md#strategies", "README.md#automatic-routing"}),
    ("How do I enable SearXNG?", {"README.md#optional-web-search", "DEPLOYMENT.md#optional-native-chat-web-search",
                                  "docs/chat.md#web-search-optional-off-by-default"}),
    ("What is the difference between a GeekCubo API key and an upstream provider key?", {"docs/security.md#which-key-goes-where"}),
    ("How do I update GeekCubo without deleting my existing data?", {"DEPLOYMENT.md#upgrading-an-existing-install-do-not-lose-data"}),
])
def test_bundled_index_answers_the_reference_questions(question, acceptable):
    hits = KnowledgeService(svc_mod.default_index_path()).search(question, 3)
    assert acceptable & {h.id for h in hits}, [h.id for h in hits]


@pytest.mark.parametrize("question", ["What is the capital of Australia's best pizza topping?", "tell me a joke"])
def test_bundled_index_returns_nothing_for_unrelated_questions(question):
    assert KnowledgeService(svc_mod.default_index_path()).search(question, 3) == []
