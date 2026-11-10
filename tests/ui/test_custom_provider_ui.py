"""Browser-level (Playwright) coverage for the dashboard's custom-provider UI.

Why this file exists: Phase 1 shipped a correct backend and correct *source*
files, but the operator's browser ran a stale ``app.js`` against the new
``index.html``. Selecting "OpenAI Format – Others" therefore rendered no name
or URL field and saving fell through to ``PUT /v1/providers/__custom__``. Every
backend test passed. These tests load the real dashboard in a real browser, so
a UI-wiring regression fails here instead of in front of the owner.

The suite boots ``scripts/start.py`` as a subprocess against a temp SQLite file
(a real socket, so Playwright can drive it) and points a mock OpenAI-compatible
upstream at it for the Fetch Available Models path.

Skips cleanly when Playwright or a Chromium build is unavailable, so the normal
``pytest`` run on a machine without browser binaries still passes.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ── mock OpenAI-compatible upstream ─────────────────────────────────────────


class _MockUpstream:
    """Serves GET /v1/models so "Fetch Available Models" has something real."""

    def __init__(self) -> None:
        self.model_ids = ["apixo-large", "apixo-small", "apixo-vision"]
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status: int, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    self._send(
                        200,
                        {
                            "object": "list",
                            "data": [{"id": m, "object": "model", "owned_by": "apixo"} for m in parent.model_ids],
                        },
                    )
                    return
                self._send(404, {"error": {"message": "not found"}})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                self._send(
                    200,
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    },
                )

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


# ── live server fixture ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mock_upstream():
    upstream = _MockUpstream()
    upstream.start()
    yield upstream
    upstream.stop()


@pytest.fixture(scope="module")
def live_server(tmp_path_factory, mock_upstream):
    from tests.ui.conftest import boot_server, stop_server

    server = boot_server(
        tmp_path_factory.mktemp("ui-server"),
        # Local mock upstream is the only sanctioned non-HTTPS target.
        extra_env={
            "CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS": f"127.0.0.1:{mock_upstream.port}",
        },
    )
    try:
        yield server
    finally:
        stop_server(server)


@pytest.fixture
def page(browser, live_server):
    """A dashboard signed in through the real login form, on Providers."""
    from tests.ui.conftest import sign_in

    context = browser.new_context()
    pg = context.new_page()
    sign_in(pg, live_server.base_url, path="/providers")
    pg.wait_for_selector("#panel-providers.active", timeout=15_000)
    yield pg
    context.close()


@pytest.fixture(autouse=True)
def _clean_custom_providers(live_server):
    """Each UI test starts and ends with no custom providers."""
    yield
    status, body = live_server.admin("GET", "/v1/custom-providers")
    assert status == 200, body
    for p in body.get("providers", []):
        live_server.admin("DELETE", f"/v1/custom-providers/{p['id']}")


def _create_provider_via_ui(page, upstream, name, key="sk-test-abcdefghijkl"):
    page.select_option("#provider-name", "__custom__")
    page.fill("#custom-provider-name", name)
    page.fill("#custom-base-url", upstream.base_url)
    page.fill("#custom-api-key", key)
    page.click("#custom-provider-form button[type=submit]")
    # Wait for THIS provider's row — a bare .cp-row wait returns immediately
    # when an earlier test-created row is still on screen.
    page.wait_for_function(
        """(name) => [...document.querySelectorAll('.cp-row .cp-row-head .name')]"""
        """.some(el => el.textContent === name)""",
        arg=name,
        timeout=15_000,
    )


# ── tests ───────────────────────────────────────────────────────────────────


def _catalog_entry(*, inp=2.5, outp=10.0, context=128000, tools=True) -> dict:
    return {
        "price_state": "priced",
        "input_per_million": inp,
        "output_per_million": outp,
        "cache_read_per_million": None,
        "cache_write_per_million": None,
        "context": context,
        "tools": tools,
        "vision": False,
        "json_mode": None,
        "json_schema": True,
    }


def _seed_catalog(live_server, entries: dict[str, dict]) -> None:
    """Insert a deterministic Model Intelligence catalog into the live DB.

    A row keyed 'litellm' exists, so ``load_enabled_sources`` suppresses the
    bundled catalog fallback and this cache is authoritative.
    """
    import sqlite3
    import uuid
    from datetime import datetime, timezone

    path = live_server.db_url.split("///", 1)[1]
    con = sqlite3.connect(path, timeout=20)
    try:
        con.execute('DELETE FROM metadata_sources WHERE "key" = ?', ("litellm",))
        con.execute(
            'INSERT INTO metadata_sources (workspace_id, "key", name, kind, '
            "is_builtin, is_enabled, priority, sync_interval_hours, cache, "
            "entry_count, last_success_at, id, is_deleted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "default",
                "litellm",
                "Test catalog",
                "litellm",
                0,
                1,
                10,
                24,
                json.dumps(entries),
                len(entries),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
                str(uuid.uuid4()),
                0,
            ),
        )
        con.commit()
    finally:
        con.close()


def _clear_catalog(live_server) -> None:
    import sqlite3

    path = live_server.db_url.split("///", 1)[1]
    con = sqlite3.connect(path, timeout=20)
    try:
        con.execute('DELETE FROM metadata_sources WHERE "key" = ?', ("litellm",))
        con.commit()
    finally:
        con.close()


def test_providers_path_serves_dashboard_and_opens_providers_tab(page):
    """/providers is the URL the owner used; it must serve the shell, not a 404."""
    # setTab() rewrites the fragment, so the path is what matters.
    assert page.url.split("://", 1)[1].split("/", 1)[1].startswith("providers")
    assert page.is_visible("#panel-providers")
    assert page.is_visible("#provider-form")


def test_selecting_openai_format_others_shows_name_url_and_key(page):
    assert page.is_visible("#provider-key"), "built-in key field should show by default"

    page.select_option("#provider-name", "__custom__")

    assert page.is_visible("#custom-provider-form")
    assert page.is_visible("#custom-provider-name")
    assert page.is_visible("#custom-base-url")
    assert page.is_visible("#custom-api-key")
    # The generic key field must be gone — otherwise the two forms compete and
    # the legacy PUT /v1/providers/__custom__ path stays reachable.
    assert not page.is_visible("#provider-key")

    # Dropdown label is part of the contract.
    label = page.eval_on_selector('#provider-name option[value="__custom__"]', "o => o.textContent")
    assert label.strip() == "Others (OpenAI format)"

    page.select_option("#provider-name", "openai")
    assert page.is_visible("#provider-key")
    assert not page.is_visible("#custom-provider-form")


def test_blank_and_malformed_input_is_rejected_without_a_request(page):
    seen: list[str] = []
    page.on(
        "request",
        lambda r: (
            seen.append(f"{r.method} {r.url}") if "/v1/custom-providers" in r.url or "/v1/providers/" in r.url else None
        ),
    )
    page.select_option("#provider-name", "__custom__")

    page.click("#custom-provider-form button[type=submit]")
    page.wait_for_selector("#custom-form-error:not([hidden])")
    assert "Provider Name is required" in page.inner_text("#custom-form-error")

    page.fill("#custom-provider-name", "Apixo")
    page.click("#custom-provider-form button[type=submit]")
    assert "API Base URL is required" in page.inner_text("#custom-form-error")

    page.fill("#custom-base-url", "not-a-url")
    page.fill("#custom-api-key", "sk-test")
    page.click("#custom-provider-form button[type=submit]")
    assert "must be a full URL" in page.inner_text("#custom-form-error")

    page.fill("#custom-base-url", "ftp://api.apixo.example/v1")
    page.click("#custom-provider-form button[type=submit]")
    assert "must start with http" in page.inner_text("#custom-form-error")

    page.fill("#custom-base-url", "https://user:pw@api.apixo.example/v1")
    page.click("#custom-provider-form button[type=submit]")
    assert "must not embed credentials" in page.inner_text("#custom-form-error")

    page.fill("#custom-base-url", "https://api.apixo.example/v1")
    page.fill("#custom-api-key", "")
    page.click("#custom-provider-form button[type=submit]")
    assert "API Key is required" in page.inner_text("#custom-form-error")

    # Nothing above may have reached the API.
    assert seen == [], f"invalid input triggered requests: {seen}"


def test_save_posts_to_custom_provider_endpoint_not_legacy_provider_key(page):
    posts: list[str] = []
    legacy: list[str] = []
    page.on(
        "request",
        lambda r: (
            posts.append(r.url.split("://", 1)[1])
            if r.method == "POST" and r.url.endswith("/v1/custom-providers")
            else (legacy.append(r.url) if "/v1/providers/__custom__" in r.url else None)
        ),
    )

    page.select_option("#provider-name", "__custom__")
    page.fill("#custom-provider-name", "Apixo")
    page.fill("#custom-base-url", "https://example.com/v1")
    assert "apixo" in page.inner_text("#custom-slug-hint")
    page.fill("#custom-api-key", "sk-apixo-ui-test-key-0001")
    page.click("#custom-provider-form button[type=submit]")

    page.wait_for_selector(".cp-row", timeout=15_000)
    assert posts, "expected POST /v1/custom-providers"
    assert legacy == [], f"legacy provider-key path was called: {legacy}"

    # The key must not survive in the form after a successful save.
    assert page.input_value("#custom-api-key") == ""
    assert page.inner_text("#custom-provider-name") == ""

    # ...and must not be exposed in the rendered card.
    card_text = page.inner_text("#custom-providers-card")
    assert "sk-apixo-ui-test-key-0001" not in card_text


def test_saved_provider_renders_management_card(page, mock_upstream):
    _create_provider_via_ui(page, mock_upstream, "Apixo")

    page.wait_for_selector("#custom-providers-card:not([hidden])")
    card = page.inner_text("#custom-providers-card")
    # Status pills are CSS-uppercased, so compare case-insensitively.
    lowered = card.lower()
    assert "Apixo" in card
    assert mock_upstream.base_url in card
    assert "apixo/" in card  # derived slug
    # The card shows the count as a fact ("Models / 0"), not "0 models".
    assert "0 unpriced" not in lowered
    assert "manage models (0)" in lowered
    assert "enabled" in lowered

    # Masked key, never the raw value.
    assert "sk-test-abcdefghijkl" not in card
    assert "sk-tes" in card

    # Edit and "Manage models" stay on the card; the rest live in the More
    # menu so the card does not turn into a wall of buttons.
    assert page.is_visible('.cp-head-actions button:text-is("Edit")')
    assert page.is_visible(".cp-actions button[data-cp-manage]")

    page.locator(".cp-row .cp-menu > summary").first.click()
    for control in (
        "Test connection",
        "Fetch available models",
        "Disable provider",
        "Exclude from Auto",
        "Remove provider",
    ):
        assert page.is_visible(f'.cp-menu-item:text-is("{control}")'), control


def test_multiple_named_providers_coexist_independently(page, mock_upstream):
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    _create_provider_via_ui(page, mock_upstream, "Venice AI")

    names = page.eval_on_selector_all(".cp-row .cp-row-head .name", "els => els.map(e => e.textContent)")
    assert names == ["Apixo", "Venice AI"]

    slugs = page.eval_on_selector_all(".cp-row .cp-slug", "e => e.map(x => x.textContent)")
    assert slugs[0].startswith("apixo/")
    assert slugs[1].startswith("venice-ai/")


def test_fetch_available_models_then_bulk_register(page, live_server, mock_upstream):
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    row = page.locator(".cp-row").first

    row.locator(".cp-menu > summary").click()
    row.locator("[data-cp-fetch]").click()
    row.locator(".cp-fetch-panel .cp-fetch-item").first.wait_for(timeout=15_000)

    items = row.locator(".cp-fetch-item code").all_inner_texts()
    assert items == mock_upstream.model_ids

    # Searchable multi-select: filter, then select-all + bulk add.
    row.locator("[data-fetch-search]").fill("vision")
    assert row.locator(".cp-fetch-item").count() == 1
    row.locator("[data-fetch-search]").fill("")
    row.locator("[data-fetch-selectall]").click()
    row.locator("[data-fetch-add]").click()

    page.wait_for_function(
        "() => document.querySelector('.cp-row [data-cp-model-count]')?.textContent.trim() === '3'",
        timeout=15_000,
    )
    table_rows = row.locator(".cp-models tbody tr").all_inner_texts()
    assert len(table_rows) == 3
    assert any("apixo-large" in t for t in table_rows)


def test_fetch_discovery_shows_catalog_resolution_and_honours_picked_key(page, live_server, mock_upstream):
    """Discovery must tell the operator, before registering, which ids resolve
    to catalog metadata, which are ambiguous, and which have no match — and a
    picked catalog key must be used when the models are added."""
    _seed_catalog(
        live_server,
        {
            # Two vendors expose the same bare id → ambiguous.
            "vendor1/apixo-large": _catalog_entry(),
            "vendor2/apixo-large": _catalog_entry(inp=2.5, outp=10.0),
            # The provider owns its own catalog namespace → exact match.
            "apixo/apixo-small": _catalog_entry(inp=0.4, outp=1.6, context=32000),
            # apixo-vision is deliberately absent → no catalog match.
        },
    )
    try:
        _create_provider_via_ui(page, mock_upstream, "Apixo")
        row = page.locator(".cp-row").first

        row.locator(".cp-menu > summary").click()
        row.locator("[data-cp-fetch]").click()
        row.locator(".cp-fetch-panel .cp-fetch-item").first.wait_for(timeout=15_000)

        summary = row.locator("[data-fetch-summary]")
        summary.wait_for(timeout=15_000)
        # Counts are rendered as status pills (uppercased by CSS).
        summary_text = summary.inner_text().lower()
        assert "1 resolved" in summary_text
        assert "1 ambiguous" in summary_text
        assert "1 unmatched" in summary_text

        large = row.locator(".cp-fetch-item").filter(has_text="apixo-large")
        small = row.locator(".cp-fetch-item").filter(has_text="apixo-small")
        vision = row.locator(".cp-fetch-item").filter(has_text="apixo-vision")
        assert large.locator(".pill").inner_text().strip().lower() == "ambiguous"
        assert small.locator(".pill").inner_text().strip().lower() == "resolved"
        assert vision.locator(".pill").inner_text().strip().lower() == "unmatched"

        # Ambiguous ids offer a searchable candidate picker; unmatched ids with
        # no candidates must not render a useless empty picker.
        assert large.locator('[data-fetch-key="apixo-large"]').count() == 1
        assert vision.locator("[data-fetch-key]").count() == 0

        # The candidate picker filters: a query matching nothing shows the
        # empty state, narrowing to one vendor leaves one option to pick.
        large_picker = large.locator('[data-fetch-key="apixo-large"]')
        large_picker.locator(".gc-select-input").click()
        large_picker.locator(".gc-select-input").fill("nomatch")
        assert large_picker.locator(".gc-select-empty").is_visible()
        large_picker.locator(".gc-select-input").fill("vendor1")
        opts = large_picker.locator(".gc-select-opt")
        assert opts.count() == 1
        assert "vendor1/apixo-large" in opts.first.inner_text()
        opts.first.click()
        assert large_picker.locator(".gc-select-input").input_value() == "vendor1/apixo-large"

        large.locator("[data-fetch-check]").check()
        row.locator("[data-fetch-add]").click()

        page.wait_for_function(
            "() => document.querySelector('.cp-row [data-cp-model-count]')?.textContent.trim() === '1'",
            timeout=15_000,
        )
        # Adding models opens the Manage Models panel itself.
        page.wait_for_selector("[data-cp-manage-panel]:not([hidden]) tr[data-model-row]", timeout=15_000)
        model_row = row.locator("tr[data-model-row]").first
        text = model_row.inner_text()
        # The picked key is what the registered model resolved against.
        assert "resolved" in text.lower()
        assert "vendor1/apixo-large" in text
        assert "128,000" in text
        assert "$2.50 / $10.00" in text

        # Provider card summarises catalog readiness and flags unpriced models
        # (a reference estimate is never a confirmed custom price).
        readiness = row.locator("[data-cp-readiness]")
        readiness.wait_for(timeout=15_000)
        readiness_text = readiness.inner_text().lower()
        assert "1 resolved" in readiness_text
        assert "1 without a confirmed price" in readiness_text
    finally:
        _clear_catalog(live_server)


def test_registered_ambiguous_model_picks_and_clears_catalog_key(page, live_server, mock_upstream):
    """A model registered without a key can be resolved later from its table
    row, and clearing the override returns it to the ambiguous state."""
    _seed_catalog(
        live_server,
        {
            "vendor1/apixo-large": _catalog_entry(inp=2.5, outp=10.0),
            "vendor2/apixo-large": _catalog_entry(inp=3.0, outp=12.0),
        },
    )
    try:
        _create_provider_via_ui(page, mock_upstream, "Apixo")
        row = page.locator(".cp-row").first
        row.locator(".cp-menu > summary").click()
        row.locator("[data-cp-fetch]").click()
        row.locator(".cp-fetch-panel .cp-fetch-item").first.wait_for(timeout=15_000)

        large = row.locator(".cp-fetch-item").filter(has_text="apixo-large")
        large.locator("[data-fetch-check]").check()
        row.locator("[data-fetch-add]").click()

        page.wait_for_selector("[data-cp-manage-panel]:not([hidden]) tr[data-model-row]", timeout=15_000)
        model_row = row.locator("tr[data-model-row]").first
        assert model_row.locator("[data-cp-catalog]").count() == 1
        assert "ambiguous" in model_row.inner_text().lower()

        # Choosing a key on the registered row re-resolves its metadata and
        # refreshes the provider-level readiness line in place.
        model_row.locator("[data-cp-catalog] .gc-select-input").click()
        row.locator('[data-cp-catalog] .gc-select-opt:has-text("vendor2/apixo-large")').first.click()
        page.wait_for_function(
            "() => { const r = document.querySelector("
            "'[data-cp-manage-panel]:not([hidden]) tr[data-model-row]');"
            "return r && r.textContent.includes('vendor2/apixo-large') "
            "&& r.textContent.includes('$3.00 / $12.00'); }",
            timeout=15_000,
        )
        page.wait_for_function(
            "() => document.querySelector('.cp-row [data-cp-readiness]')"
            "?.textContent.toLowerCase().includes('1 resolved')",
            timeout=15_000,
        )
        model_row = row.locator("tr[data-model-row]").first
        text = model_row.inner_text()
        assert "resolved" in text.lower()
        assert "vendor2/apixo-large" in text
        assert "$3.00 / $12.00" in text

        # Clearing the override drops back to the ambiguous picker.
        model_row.locator("[data-cp-catalog-clear]").click()
        page.wait_for_function(
            "() => { const r = document.querySelector("
            "'[data-cp-manage-panel]:not([hidden]) tr[data-model-row]');"
            "return r && !!r.querySelector('[data-cp-catalog]') "
            "&& r.textContent.toLowerCase().includes('ambiguous'); }",
            timeout=15_000,
        )
        page.wait_for_function(
            "() => document.querySelector('.cp-row [data-cp-readiness]')"
            "?.textContent.toLowerCase().includes('1 ambiguous')",
            timeout=15_000,
        )
        model_row = row.locator("tr[data-model-row]").first
        assert model_row.locator("[data-cp-catalog]").count() == 1
        assert "ambiguous" in model_row.inner_text().lower()
    finally:
        _clear_catalog(live_server)


def test_add_selected_populates_catalog_fields_and_provenance_without_guessing(page, live_server, mock_upstream):
    """Deterministic catalog: an exactly-matched id inherits tools/vision/json,
    context and unknown reference pricing on Add Selected, with every field's
    persisted source visible in the row itself. An ambiguous id stays
    ambiguous — the UI must never auto-pick one of its candidates."""
    _seed_catalog(
        live_server,
        {
            "apixo/apixo-small": {
                "price_state": "unknown",
                "input_per_million": None,
                "output_per_million": None,
                "cache_read_per_million": None,
                "cache_write_per_million": None,
                "context": 65536,
                "tools": True,
                "vision": True,
                "json_mode": None,
                "json_schema": False,
            },
            "vendor1/apixo-large": _catalog_entry(inp=2.5, outp=10.0),
            "vendor2/apixo-large": _catalog_entry(inp=3.0, outp=12.0),
        },
    )
    try:
        _create_provider_via_ui(page, mock_upstream, "Apixo")
        row = page.locator(".cp-row").first
        row.locator(".cp-menu > summary").click()
        row.locator("[data-cp-fetch]").click()
        row.locator(".cp-fetch-panel .cp-fetch-item").first.wait_for(timeout=15_000)

        small = row.locator(".cp-fetch-item").filter(has_text="apixo-small")
        large = row.locator(".cp-fetch-item").filter(has_text="apixo-large")
        # Unknown reference prices keep the status at partial, not resolved.
        assert "partial" in small.inner_text().lower()
        assert "ambiguous" in large.inner_text().lower()

        small.locator("[data-fetch-check]").check()
        large.locator("[data-fetch-check]").check()
        row.locator("[data-fetch-add]").click()

        page.wait_for_function(
            "() => document.querySelector('.cp-row [data-cp-model-count]')?.textContent.trim() === '2'",
            timeout=15_000,
        )
        page.wait_for_selector("[data-cp-manage-panel]:not([hidden]) tr[data-model-row]", timeout=15_000)

        small_row = row.locator("tr[data-model-row]").filter(has_text="apixo-small")
        assert row.locator(".cp-detail-row").count() == 0
        small_text = small_row.inner_text().lower()
        assert "partial" in small_text
        assert "resolved" not in small_text
        assert "65,536" in small_text
        assert "unknown" in small_text
        assert small_row.locator('[data-cp-cap="tools"]').input_value() == "supported"
        assert small_row.locator('[data-cp-cap="vision"]').input_value() == "supported"
        # JSON mode and JSON schema are separate selects with separate sources.
        assert small_row.locator('[data-cp-cap="json_mode"]').input_value() == "unknown"
        assert small_row.locator('[data-cp-cap="json_schema"]').input_value() == "unsupported"
        # Persisted provenance is on the row without opening Details.
        assert "via litellm" in small_row.locator('[data-prov="tools"]').inner_text()
        assert "via litellm" in small_row.locator('[data-prov="vision"]').inner_text()
        assert "via litellm" in small_row.locator('[data-prov="json_schema"]').inner_text()
        assert "via litellm" in small_row.locator('[data-prov="context"]').inner_text()
        assert "via apixo/apixo-small" in small_row.locator('[data-prov="reference_input"]').inner_text()
        assert "via unknown" in small_row.locator('[data-prov="custom_input"]').inner_text()

        # Ambiguous registration: no candidate is guessed, no metadata is
        # inherited, and the searchable picker is offered on the table row.
        large_row = row.locator("tr[data-model-row]").filter(has_text="apixo-large")
        large_text = large_row.inner_text().lower()
        assert "ambiguous" in large_text
        assert "vendor1/apixo-large" not in large_text
        assert "$2.50" not in large_row.inner_text()
        assert "128,000" not in large_row.inner_text()
        assert large_row.locator('[data-cp-cap="tools"]').input_value() == "unknown"
        assert large_row.locator('[data-cp-cap="vision"]').input_value() == "unknown"
        assert large_row.locator('[data-cp-cap="json_mode"]').input_value() == "unknown"
        assert large_row.locator('[data-cp-cap="json_schema"]').input_value() == "unknown"

        picker = large_row.locator("[data-cp-catalog]")
        assert picker.count() == 1
        picker.locator(".gc-select-input").click()
        picker.locator(".gc-select-input").fill("vendor2")
        opts = picker.locator(".gc-select-opt")
        assert opts.count() == 1
        assert "vendor2/apixo-large" in opts.first.inner_text()
        opts.first.click()

        page.wait_for_function(
            "() => { const r = document.querySelector("
            "'[data-cp-manage-panel]:not([hidden]) tr[data-model-row]');"
            "return r && r.textContent.includes('vendor2/apixo-large') "
            "&& r.textContent.includes('$3.00 / $12.00'); }",
            timeout=15_000,
        )
        # Row catalog selection refreshes the provider readiness line too.
        readiness = row.locator("[data-cp-readiness]").inner_text().lower()
        assert "1 resolved" in readiness
        assert "1 partial" in readiness
        assert "ambiguous" not in readiness
        picked = row.locator("tr[data-model-row]").filter(has_text="apixo-large")
        assert picked.locator('[data-cp-cap="tools"]').input_value() == "supported"
        assert "via litellm" in picked.locator('[data-prov="reference_input"]').inner_text()
    finally:
        _clear_catalog(live_server)


def test_edit_changes_name_url_and_key_independently(page, mock_upstream):
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    row = page.locator(".cp-row").first

    # Name only — URL and key untouched.
    row.locator("[data-cp-edit]").click()
    row.locator('[data-e="display_name"]').fill("Apixo AI")
    row.locator(".cp-edit button[type=submit]").click()
    page.wait_for_function(
        "() => document.querySelector('.cp-row .cp-row-head .name')?.textContent === 'Apixo AI'",
        timeout=15_000,
    )
    assert mock_upstream.base_url in row.locator(".cp-summary").inner_text()
    assert "sk-tes" in row.locator(".cp-summary").inner_text()

    # URL only — name and key untouched. Stay on the allowlisted mock host:
    # the server's SSRF guard rejects hosts it cannot resolve or that are not
    # explicitly authorized, so an invented public hostname would 422 here.
    new_url = mock_upstream.base_url.replace("/v1", "/v2")
    row.locator("[data-cp-edit]").click()
    row.locator('[data-e="base_url"]').fill(new_url)
    row.locator(".cp-edit button[type=submit]").click()
    page.wait_for_function(
        "(url) => document.querySelector('.cp-row .cp-summary')?.textContent.includes(url)",
        arg=new_url,
        timeout=15_000,
    )
    assert row.locator(".cp-row-head .name").inner_text() == "Apixo AI"

    # Invalid edit is rejected inline and does not change the stored row.
    row.locator("[data-cp-edit]").click()
    row.locator('[data-e="base_url"]').fill("nonsense")
    row.locator(".cp-edit button[type=submit]").click()
    row.locator("[data-cp-edit-error]:not([hidden])").wait_for(timeout=5_000)
    assert "must be a full URL" in row.locator("[data-cp-edit-error]").inner_text()
    assert new_url in row.locator(".cp-summary").inner_text()


def test_manage_models_toggle_and_manual_model_with_pricing(page, mock_upstream):
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    row = page.locator(".cp-row").first
    panel = row.locator("[data-cp-manage-panel]")

    assert not panel.is_visible()
    row.locator("[data-cp-manage]").click()
    assert panel.is_visible()

    row.locator('[data-m="model_id"]').fill("manual-1")
    row.locator('[data-m="display_name"]').fill("Manual One")
    row.locator('[data-m="context_length"]').fill("32000")
    row.locator('[data-m="supports_tools"]').check()
    row.locator('[data-m="input_cost_per_million"]').fill("1.5")
    row.locator('[data-m="output_cost_per_million"]').fill("6")
    row.locator("[data-cp-addbtn]").click()

    page.wait_for_function(
        "() => document.querySelector('.cp-row .cp-models tbody tr') !== null",
        timeout=15_000,
    )
    text = row.locator(".cp-models tbody tr").first.inner_text()
    assert "manual-1" in text
    # The unit lives in the column header ("In /1M" / "Out /1M") so the cell
    # stays narrow; the value itself is still rendered per million tokens.
    assert "$1.50" in text
    assert "$6.00" in text
    # Header text is CSS-uppercased, so compare case-insensitively. The /1M
    # unit lives in the column headers ("Reference In / Out /1M" and
    # "Custom In / Out /1M"), the cell shows the bare dollar value.
    assert "in / out /1m" in row.locator(".cp-models thead").inner_text().lower()


def test_ui_never_writes_a_custom_provider_key_row(page, live_server, mock_upstream):
    """Regression guard for the original bug: no path in the dashboard may
    PUT /v1/providers/__custom__ — the server rejects it outright, but the UI
    must not even try (a stale bundle used to)."""
    attempted: list[str] = []
    page.on(
        "request",
        lambda r: (
            attempted.append(f"{r.method} {r.url}")
            if "__custom__" in r.url and "/v1/custom-providers" not in r.url
            else None
        ),
    )

    _create_provider_via_ui(page, mock_upstream, "Apixo")
    # Also exercise the built-in form with the sentinel selected programmatically.
    page.select_option("#provider-name", "openai")
    page.fill("#provider-key", "sk-should-not-be-stored")
    page.click('#provider-form button[type="submit"]')
    page.wait_for_timeout(1500)

    assert attempted == [], f"legacy __custom__ provider-key writes attempted: {attempted}"

    status, body = live_server.admin("GET", "/v1/providers")
    assert status == 200, body
    assert all(p["provider"] != "__custom__" for p in body["providers"])


def test_auto_toggle_label_states_the_action_not_a_misleading_status(page, mock_upstream):
    """A new provider defaults to Auto, and the menu action matches the pill."""
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    row = page.locator(".cp-row").first
    head = row.locator(".cp-row-head").inner_text().lower()
    assert "auto-eligible" in head

    row.locator(".cp-menu > summary").click()
    toggle = row.locator("[data-cp-auto]")
    assert toggle.inner_text().strip() == "Exclude from Auto"

    toggle.click()
    page.wait_for_function(
        "() => document.querySelector('.cp-row .cp-row-head')?.textContent.toLowerCase().includes('pinned only')",
        timeout=15_000,
    )
    row.locator(".cp-menu > summary").click()
    assert row.locator("[data-cp-auto]").inner_text().strip() == "Include in Auto"


def _register_three_models(page):
    row = page.locator(".cp-row").first
    row.locator(".cp-menu > summary").click()
    row.locator("[data-cp-fetch]").click()
    row.locator(".cp-fetch-panel .cp-fetch-item").first.wait_for(timeout=15_000)
    row.locator("[data-fetch-selectall]").click()
    row.locator("[data-fetch-add]").click()
    page.wait_for_function(
        "() => document.querySelector('.cp-row [data-cp-model-count]')?.textContent.trim() === '3'",
        timeout=15_000,
    )
    return row


def _toolbar_boxes(page):
    return page.evaluate(
        """() => {
          const bar = document.querySelector('.cp-model-bulk');
          const nodes = [
            bar.querySelector('.cp-bulk-select'),
            bar.querySelector('.cp-bulk-count'),
            bar.querySelector('[data-cp-bulk-cap]'),
            bar.querySelector('[data-cp-bulk-state]'),
            bar.querySelector('[data-cp-bulk="restore_metadata"]'),
            bar.querySelector('[data-cp-bulk="enable"]'),
            bar.querySelector('[data-cp-bulk="disable"]'),
            bar.querySelector('[data-cp-bulk="remove"]'),
          ];
          const table = document.querySelector('.cp-models').getBoundingClientRect();
          return {
            boxes: nodes.map((n) => {
              const r = n.getBoundingClientRect();
              return {top: r.top, bottom: r.bottom, left: r.left, right: r.right,
                      center: r.top + r.height / 2, height: r.height, width: r.width};
            }),
            barBottom: bar.getBoundingClientRect().bottom,
            tableTop: table.top,
            viewport: window.innerWidth,
            docWidth: document.documentElement.scrollWidth,
            overflow: [...document.querySelectorAll('body *')]
              .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1
                && (() => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
                  const st = getComputedStyle(a);
                  if (st.overflowX !== 'visible' || st.clip !== 'auto') return false; } return true; })())
              .slice(0, 8)
              .map((e) => `${e.tagName}.${e.className}`),
          };
        }"""
    )


@pytest.mark.parametrize("width", [1700, 1440, 1280])
def test_provider_bulk_toolbar_is_one_aligned_row_on_desktop(page, mock_upstream, width):
    page.set_viewport_size({"width": width, "height": 900})
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    _register_three_models(page)
    data = _toolbar_boxes(page)
    boxes = data["boxes"]
    centers = [b["center"] for b in boxes]
    assert max(centers) - min(centers) <= 3, boxes
    assert all(b["width"] > 0 and b["height"] > 0 for b in boxes), boxes
    lefts = [b["left"] for b in boxes]
    assert lefts == sorted(lefts), boxes
    for left, right in zip(boxes, boxes[1:], strict=False):
        assert left["right"] <= right["left"] + 1, boxes
    heights = [b["height"] for b in boxes[2:]]
    assert max(heights) - min(heights) <= 2, boxes
    assert 0 <= data["tableTop"] - data["barBottom"] <= 16, data
    assert data["docWidth"] <= data["viewport"] + 1, data["overflow"]


def test_provider_bulk_toolbar_selection_state(page, mock_upstream):
    page.set_viewport_size({"width": 1440, "height": 900})
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    row = _register_three_models(page)
    bar = row.locator(".cp-model-bulk")
    assert bar.locator(".cp-bulk-count").inner_text() == "0 selected"
    assert bar.locator('[data-cp-bulk="remove"]').is_disabled()

    row.locator("[data-cp-check]").first.check()
    page.wait_for_function("() => document.querySelector('.cp-bulk-count')?.textContent === '1 selected'")
    assert page.evaluate("() => document.querySelector('[data-cp-check-all-toolbar]').indeterminate")
    bar.locator("[data-cp-check-all-toolbar]").check()
    page.wait_for_function("() => document.querySelector('.cp-bulk-count')?.textContent === '3 selected'")
    assert not bar.locator('[data-cp-bulk="remove"]').is_disabled()


@pytest.mark.parametrize("width,height", [(1024, 900), (768, 1024), (390, 844)])
def test_provider_bulk_toolbar_wraps_without_overlap(page, mock_upstream, width, height):
    page.set_viewport_size({"width": width, "height": height})
    _create_provider_via_ui(page, mock_upstream, "Apixo")
    _register_three_models(page)
    data = _toolbar_boxes(page)
    boxes = data["boxes"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            overlaps = not (
                a["right"] <= b["left"] + 1
                or b["right"] <= a["left"] + 1
                or a["bottom"] <= b["top"] + 1
                or b["bottom"] <= a["top"] + 1
            )
            assert not overlaps, (a, b)
    assert data["docWidth"] <= data["viewport"] + 1, data["overflow"]


_FORM_GEOMETRY = """() => { const f = document.querySelector('#custom-provider-form').getBoundingClientRect();
  return ['#custom-provider-name', '#custom-base-url', '#custom-api-key', '#custom-provider-form button[type=submit]']
    .map(s => { const r = document.querySelector(s).getBoundingClientRect();
      return [Math.round(r.x), Math.round(r.y - f.y), Math.round(r.width), Math.round(r.height)]; })
    .concat([[Math.round(f.height)]]); }"""


@pytest.mark.parametrize("width", [1440, 1280, 1024, 768, 390])
def test_typing_a_provider_name_does_not_move_the_form(browser, live_server, width):
    """Revealing the slug hint while typing must not reflow the fields, and on
    desktop the three fields and Save provider share one row."""
    from tests.ui.conftest import sign_in

    context = browser.new_context(viewport={"width": width, "height": 900})
    pg = context.new_page()
    sign_in(pg, live_server.base_url, path="/providers")
    pg.wait_for_selector("#panel-providers.active", timeout=15_000)
    pg.select_option("#provider-name", "__custom__")
    pg.wait_for_selector("#custom-provider-form:not([hidden])")
    before = pg.evaluate(_FORM_GEOMETRY)
    pg.type("#custom-provider-name", "Orca Router Test With A Much Longer Provider Name")
    assert pg.is_visible("#custom-slug-hint")
    assert pg.evaluate(_FORM_GEOMETRY) == before
    if width >= 1280:
        name, url, key, save = before[:4]
        assert name[1] == url[1] == key[1], "fields should share one row"
        assert save[0] + save[2] <= pg.evaluate(
            "document.querySelector('#custom-provider-form').getBoundingClientRect().right") + 1
        assert abs((save[1] + save[3] / 2) - (name[1] + name[3] / 2)) <= 4, "Save aligns with the inputs"
    pg.fill("#custom-provider-name", "")
    pg.dispatch_event("#custom-provider-name", "input")
    assert pg.evaluate(_FORM_GEOMETRY) == before
    context.close()
