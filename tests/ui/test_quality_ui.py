"""Browser-level layout and behavior checks for the Quality page.

Verifies, with real Chrome geometry, that the Artificial Analysis key form and
the manual-override form render as single rows on desktop, wrap without
overlap or overflow on narrow viewports, that the searchable model picker
popup stays bounded, and that table bulk selection drives the bulk endpoint.
"""

from __future__ import annotations

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("geekcubo-quality-ui"))
    try:
        yield server
    finally:
        stop_server(server)


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    p.close()
    ctx.close()


def _open_quality(page, live_server, width: int, height: int = 900) -> None:
    page.set_viewport_size({"width": width, "height": height})
    sign_in(page, live_server.base_url)
    page.click('[data-tab="quality"]')
    page.wait_for_selector("#panel-quality.active, #panel-quality:not([hidden])", timeout=10_000)
    page.wait_for_selector("#q-ov-form .gc-select-input", state="visible", timeout=10_000)


def _boxes(page, selectors):
    return page.evaluate(
        """(sels) => sels.map((s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {sel: s, x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom};
        })""",
        selectors,
    )


def _overlaps(a, b) -> bool:
    return not (a["right"] <= b["x"] + 0.5 or b["right"] <= a["x"] + 0.5
                or a["bottom"] <= b["y"] + 0.5 or b["bottom"] <= a["y"] + 0.5)


def _no_page_overflow(page) -> int:
    return page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )


KEY_ROW = [
    "#quality-key-input",
    "#quality-key-limit",
    '#quality-key-form button[type="submit"]',
    "#quality-key-test",
    "#quality-key-cancel",
]
OV_ROW = [
    "#q-ov-model-picker .gc-select-field",
    "#q-ov-score",
    "#q-ov-note",
    '#q-ov-form button[type="submit"]',
    "#q-ov-clear",
]


def _reveal_key_form(page) -> None:
    page.evaluate("() => { document.querySelector('#quality-key-form').hidden = false; }")


def _show_q_tab(page, name: str) -> None:
    """Select an in-page Quality tab (models | scores | aa)."""
    page.click(f'[data-q-tab="{name}"]')
    page.wait_for_selector(f"#q-pane-{name}:not([hidden])", timeout=5_000)


def _rows_for_tab(page, row):
    """Each form lives in its own tab; select it before measuring."""
    _show_q_tab(page, "aa" if row is KEY_ROW else "models")
    if row is KEY_ROW:
        _reveal_key_form(page)


@pytest.mark.parametrize("width", [1700, 1440, 1280])
def test_quality_forms_are_single_rows_on_desktop(page, live_server, width):
    _open_quality(page, live_server, width)
    for row in (KEY_ROW, OV_ROW):
        _rows_for_tab(page, row)
        boxes = _boxes(page, row)
        assert all(b and b["w"] > 0 for b in boxes), boxes
        centers = [b["y"] + b["h"] / 2 for b in boxes]
        assert max(centers) - min(centers) <= 6, f"not one row at {width}px: {boxes}"
        xs = [b["x"] for b in boxes]
        assert xs == sorted(xs), f"controls out of order at {width}px: {boxes}"
        # Adjacent pairs only — `boxes[1:]` is never shorter than `boxes[:-1]`
        # for a non-empty list, so strict=False keeps the pairing exhaustive
        # without emitting an unused iterator for the 1-box case.
        for a, b in zip(boxes, boxes[1:], strict=False):
            assert not _overlaps(a, b), (a, b)
        heights = [b["h"] for b in boxes]
        assert max(heights) - min(heights) <= 4, f"inconsistent heights: {heights}"
    assert _no_page_overflow(page) <= 2


@pytest.mark.parametrize("width,height", [(1024, 900), (768, 1024), (390, 844)])
def test_quality_forms_wrap_without_overlap_or_overflow(page, live_server, width, height):
    _open_quality(page, live_server, width, height)
    for row in (KEY_ROW, OV_ROW):
        _rows_for_tab(page, row)
        boxes = _boxes(page, row)
        assert all(b and b["w"] > 0 for b in boxes), boxes
        for i, a in enumerate(boxes):
            assert a["right"] <= width + 1, f"{a['sel']} clipped at {width}px"
            for b in boxes[i + 1:]:
                assert not _overlaps(a, b), (a, b)
    assert _no_page_overflow(page) <= 2, f"horizontal overflow at {width}px"


def test_quality_header_is_compact_when_key_missing(page, live_server):
    _open_quality(page, live_server, 1440)
    _show_q_tab(page, "aa")
    card = _boxes(page, ["#quality-connect-card"])[0]
    assert card["h"] < 420, f"connection card too tall: {card['h']}px"


def test_model_picker_popup_is_bounded_and_closes(page, live_server):
    _open_quality(page, live_server, 1280, 700)
    page.click("#q-ov-model-picker .gc-select-input")
    pop = page.locator("#q-ov-model-picker .gc-select-pop")
    pop.wait_for(state="visible")
    box = pop.bounding_box()
    assert box["height"] <= 242, box
    assert box["y"] >= 0 and box["y"] + box["height"] <= 700 + 1, box
    assert page.get_attribute("#q-ov-model-picker .gc-select-input", "aria-expanded") == "true"
    page.keyboard.press("Escape")
    pop.wait_for(state="hidden")
    page.click("#q-ov-model-picker .gc-select-input")
    pop.wait_for(state="visible")
    page.mouse.click(5, 5)
    pop.wait_for(state="hidden")


def test_model_picker_supports_custom_ids_and_chips(page, live_server):
    _open_quality(page, live_server, 1280)
    inp = page.locator("#q-ov-model-picker .gc-select-input")
    inp.click()
    inp.fill("zz-test/never-exists")
    page.keyboard.press("Enter")
    chips = page.locator("#q-ov-model-picker .gc-chip")
    assert chips.count() == 1
    assert "zz-test/never-exists" in chips.first.inner_text()
    page.click("#q-ov-model-picker .gc-chip-x")
    assert chips.count() == 0


def test_bulk_selection_sets_and_clears_overrides(page, live_server):
    _open_quality(page, live_server, 1440)
    page.wait_for_selector("#quality-table tbody .q-row-check", timeout=10_000)
    rows = page.locator("#quality-table tbody .q-row-check")
    if rows.count() < 2:
        pytest.skip("catalog has fewer than two models in this environment")
    assert page.is_disabled("#q-bulk-clear")
    ids = [rows.nth(i).get_attribute("data-id") for i in range(2)]
    rows.nth(0).check()
    rows.nth(1).check()
    assert "2" in page.inner_text("#q-selected-count")
    assert page.evaluate("() => document.querySelector('#q-check-all').indeterminate")
    page.fill("#q-ov-score", "77")
    page.click("#q-bulk-set")
    page.wait_for_function(
        "() => document.querySelectorAll('#quality-table tbody .q-row-check:checked').length === 0",
        timeout=10_000,
    )
    status, body = live_server.admin("GET", "/v1/quality/overrides")
    assert status == 200
    got = {o["model_id"]: o for o in (body.get("overrides") if isinstance(body, dict) else body)}
    for mid in ids:
        assert mid in got and round(got[mid]["score"]) == 77, got

    page.fill("#q-filter", ids[0])
    page.wait_for_function(
        "(id) => [...document.querySelectorAll('#quality-table tbody .q-row-check')]"
        ".every((c) => c.dataset.id.includes(id))",
        arg=ids[0], timeout=5_000,
    )
    page.fill("#q-filter", "")
    for mid in ids:
        page.check(f'#quality-table tbody .q-row-check[data-id="{mid}"]')
    page.once("dialog", lambda d: d.accept())
    page.click("#q-bulk-clear")
    page.wait_for_function(
        "() => document.querySelectorAll('#quality-table tbody .q-row-check:checked').length === 0",
        timeout=10_000,
    )
    status, body = live_server.admin("GET", "/v1/quality/overrides")
    got = {o["model_id"] for o in (body.get("overrides") if isinstance(body, dict) else body)}
    assert not (set(ids) & got)


# ── In-page tabs: Models | Quality scores | Artificial Analysis ───────

import json as _json  # noqa: E402

_KEY_BASE = {
    "configured": True, "origin": "stored", "key_prefix": "aa-k...wxyz", "can_clear": True,
    "endpoint": "https://artificialanalysis.ai/api/v2/language/models/free",
    "free_endpoint": "https://artificialanalysis.ai/api/v2/language/models/free",
    "documented_daily_limit": 100, "recorded_daily_limit": None,
    "connection_status": "key_configured", "last_test_status": None, "last_test_detail": None,
    "last_test_at": None, "last_test_ok_at": None,
    "sync_status": "never_synced", "last_sync_at": None, "last_sync_attempt_at": None,
    "last_sync_raw_count": None, "last_sync_matched_count": None, "tier": None,
    "last_error_code": None, "last_error_detail": None, "last_error_at": None,
}


def _stub_key_status(page, **overrides):
    """Serve a fixed /v1/quality/key body; everything else hits the live server."""
    body = {**_KEY_BASE, **overrides}
    page.route("**/v1/quality/key", lambda route: route.fulfill(
        status=200, content_type="application/json", body=_json.dumps(body))
        if route.request.method == "GET" else route.continue_())
    return body


def _tab_state(page):
    return page.evaluate("""() => ({
        selected: [...document.querySelectorAll('[data-q-tab]')]
            .filter((t) => t.getAttribute('aria-selected') === 'true').map((t) => t.dataset.qTab),
        visible: ['models', 'scores', 'aa'].filter((n) => !document.getElementById('q-pane-' + n).hidden),
        aaDot: document.getElementById('q-tab-aa-dot').dataset.state,
        aaSr: document.getElementById('q-tab-aa-sr').textContent,
        scoresFlag: !document.getElementById('q-tab-scores-flag').hidden,
        scoresSr: document.getElementById('q-tab-scores-sr').textContent,
    })""")


def test_tabs_render_in_order_with_models_default(page, live_server):
    _open_quality(page, live_server, 1440)
    labels = page.eval_on_selector_all('[data-q-tab]', "els => els.map((e) => e.dataset.qTab)")
    assert labels == ["models", "scores", "aa"]
    texts = [page.inner_text(f'[data-q-tab="{n}"] [data-i18n]') for n in labels]
    assert texts == ["Models", "Quality scores", "Artificial Analysis"]
    st = _tab_state(page)
    assert st["selected"] == ["models"] and st["visible"] == ["models"]
    # Only one Quality destination in the sidebar.
    assert page.locator('#tabs [data-tab="quality"]').count() == 1
    assert page.get_attribute("#quality-tabs", "role") == "tablist"
    for n in labels:
        tab = page.locator(f'[data-q-tab="{n}"]')
        assert tab.get_attribute("role") == "tab"
        assert tab.get_attribute("aria-controls") == f"q-pane-{n}"


def test_tab_keyboard_navigation(page, live_server):
    _open_quality(page, live_server, 1280)
    page.focus('[data-q-tab="models"]')
    page.keyboard.press("ArrowRight")
    assert _tab_state(page)["selected"] == ["scores"]
    assert page.evaluate("document.activeElement.dataset.qTab") == "scores"
    page.keyboard.press("End")
    assert _tab_state(page)["selected"] == ["aa"]
    page.keyboard.press("ArrowRight")  # wraps
    assert _tab_state(page)["selected"] == ["models"]
    page.keyboard.press("ArrowLeft")
    assert _tab_state(page)["selected"] == ["aa"]
    page.keyboard.press("Home")
    assert _tab_state(page)["selected"] == ["models"]
    # Roving tabindex: only the selected tab is in the tab order.
    idx = page.eval_on_selector_all('[data-q-tab]', "els => els.map((e) => e.tabIndex)")
    assert idx == [0, -1, -1]


def test_unsaved_inputs_survive_tab_switches(page, live_server):
    _open_quality(page, live_server, 1440)
    page.fill("#q-ov-score", "64")
    page.fill("#q-ov-note", "draft note")
    page.fill("#q-filter", "gpt")
    page.wait_for_selector("#quality-table tbody .q-row-check", timeout=10_000)
    rows = page.locator("#quality-table tbody .q-row-check")
    if rows.count():
        rows.first.check()
    _show_q_tab(page, "aa")
    page.click("#quality-connect-replace")
    page.fill("#quality-key-input", "aa-draft-not-saved-1234")
    _show_q_tab(page, "scores")
    _show_q_tab(page, "models")
    assert page.input_value("#q-ov-score") == "64"
    assert page.input_value("#q-ov-note") == "draft note"
    assert page.input_value("#q-filter") == "gpt"
    if rows.count():
        assert rows.first.is_checked()
    _show_q_tab(page, "aa")
    assert page.input_value("#quality-key-input") == "aa-draft-not-saved-1234"


def test_tab_switching_makes_no_extra_requests(page, live_server):
    _open_quality(page, live_server, 1440)
    page.wait_for_load_state("networkidle")
    calls = []
    page.on("request", lambda r: calls.append(r.url) if "/v1/quality" in r.url else None)
    for name in ("scores", "aa", "models", "aa", "scores"):
        _show_q_tab(page, name)
    page.wait_for_timeout(300)
    assert calls == [], calls


def test_opening_quality_page_fetches_each_endpoint_once(page, live_server):
    page.set_viewport_size({"width": 1440, "height": 900})
    sign_in(page, live_server.base_url)
    calls = []
    page.on("request", lambda r: calls.append(r.url.split("?")[0].split("/v1/quality", 1)[1] or "/")
            if "/v1/quality" in r.url else None)
    page.click('[data-tab="quality"]')
    page.wait_for_selector("#q-ov-form .gc-select-input", state="visible", timeout=10_000)
    page.wait_for_load_state("networkidle")
    assert sorted(calls) == sorted(["/", "/auto-preview", "/key"]), calls


@pytest.mark.parametrize("overrides,dot,sr_contains,flag", [
    ({"configured": False, "origin": "missing", "key_prefix": None, "can_clear": False,
      "connection_status": "not_configured", "sync_status": "not_configured"},
     "not_configured", "Not configured", False),
    ({}, "key_configured", "Key configured", False),
    ({"connection_status": "connected", "last_test_status": "connected",
      "last_test_at": "2026-11-09T10:00:00Z", "last_test_ok_at": "2026-11-09T10:00:00Z"},
     "connected", "Connected", False),
    ({"connection_status": "connection_failed", "last_test_status": "invalid_key",
      "last_test_detail": "Artificial Analysis rejected the API key (HTTP 401).",
      "last_test_at": "2026-11-09T10:00:00Z"},
     "connection_failed", "Connection failed", False),
    ({"connection_status": "connected", "last_test_status": "connected",
      "last_test_at": "2026-11-09T10:00:00Z", "last_test_ok_at": "2026-11-09T10:00:00Z",
      "sync_status": "sync_failed", "last_error_code": "rate_limited",
      "last_error_detail": "Artificial Analysis daily request limit reached (HTTP 429).",
      "last_sync_attempt_at": "2026-11-09T11:00:00Z"},
     "sync_failed", "Sync failed", True),
])
def test_aa_tab_status_indicator(page, live_server, overrides, dot, sr_contains, flag):
    _stub_key_status(page, **overrides)
    _open_quality(page, live_server, 1440)
    page.wait_for_function(
        "(d) => document.getElementById('q-tab-aa-dot').dataset.state === d"
        " && document.getElementById('q-tab-aa-sr').textContent.length > 0", arg=dot, timeout=5_000)
    st = _tab_state(page)
    # Visible while another tab (Models) is selected.
    assert st["selected"] == ["models"]
    assert st["aaDot"] == dot
    assert sr_contains in st["aaSr"]
    assert st["scoresFlag"] is flag
    assert ("Sync failed" in st["scoresSr"]) is flag
    # A stored key alone never claims Connected.
    if dot == "key_configured":
        assert "Connected" not in st["aaSr"]


def test_connected_and_sync_failed_are_both_shown(page, live_server):
    _stub_key_status(page, connection_status="connected", last_test_status="connected",
                     last_test_at="2026-11-09T10:00:00Z", last_test_ok_at="2026-11-09T10:00:00Z",
                     sync_status="sync_failed", last_error_code="endpoint_retired",
                     last_error_detail="The Artificial Analysis endpoint has been retired (HTTP 410).",
                     last_sync_attempt_at="2026-11-09T11:00:00Z", tier="free")
    _open_quality(page, live_server, 1440)
    _show_q_tab(page, "aa")
    assert page.text_content("#quality-connect-status") == "Connected"
    assert "Sync failed" in page.inner_text("#quality-connect-sync")
    assert "retired" in page.inner_text("#quality-connect-error")
    assert "free tier" in page.inner_text("#quality-connect-mask")
    _show_q_tab(page, "scores")
    assert page.is_visible("#q-sync-error")
    assert "Endpoint retired" in page.text_content("#q-sync-error-code")
    # Only the masked key is rendered.
    assert "aa-k...wxyz" in page.text_content("#quality-connect-mask")


def test_no_provider_is_not_reported_as_sync_failure(page, live_server):
    """A fresh install has no provider keys and no AA key: the sync panel must
    not show a sync error, and the Auto-routing notice lives in its own
    collapsible section."""
    _open_quality(page, live_server, 1440)
    _show_q_tab(page, "scores")
    assert page.is_hidden("#q-sync-error")
    assert not _tab_state(page)["scoresFlag"]
    empty = page.inner_text("#q-sync-empty")
    assert "Artificial Analysis" in empty
    # Auto-routing diagnostic is collapsed and outside the sync card.
    assert page.evaluate("document.getElementById('quality-auto-status').open") is False
    assert page.evaluate(
        "!document.getElementById('quality-status-card').contains(document.getElementById('quality-preview'))")
    assert page.is_disabled("#quality-refresh")


def test_empty_sync_state_with_key(page, live_server):
    _stub_key_status(page, sync_status="synced", last_sync_at="2026-11-09T09:00:00Z",
                     last_sync_attempt_at="2026-11-09T09:00:00Z",
                     last_sync_raw_count=0, last_sync_matched_count=0)
    _open_quality(page, live_server, 1440)
    _show_q_tab(page, "scores")
    assert page.inner_text("#q-sync-returned") == "0"
    assert "no models" in page.inner_text("#q-sync-empty")


def test_sync_counts_render(page, live_server):
    _stub_key_status(page, sync_status="synced", last_sync_at="2026-11-09T09:00:00Z",
                     last_sync_attempt_at="2026-11-09T09:00:00Z",
                     last_sync_raw_count=726, last_sync_matched_count=99, tier="free")
    _open_quality(page, live_server, 1440)
    _show_q_tab(page, "scores")
    assert page.inner_text("#q-sync-returned") == "726"
    assert page.inner_text("#q-sync-matched") == "99"
    assert page.inner_text("#q-sync-unmatched") == "627"
    assert page.is_hidden("#q-sync-error")
    assert not page.is_disabled("#quality-refresh")
    # "Where these numbers come from" guidance is kept.
    assert page.locator("#quality-provenance summary").count() == 1


def test_availability_column_does_not_imply_deployable(page, live_server):
    _open_quality(page, live_server, 1440)
    header = page.text_content("#quality-table thead")
    assert "Availability" in header
    page.wait_for_selector("#quality-table tbody .q-row-check", timeout=10_000)
    pills = page.eval_on_selector_all("#quality-table tbody td .pill", "els => els.map((e) => e.textContent)")
    # No provider keys in this test server: nothing may be shown as available.
    assert pills and all(p == "no provider key" for p in pills), pills[:5]


def test_individual_override_and_reset_through_tabs(page, live_server):
    _open_quality(page, live_server, 1440)
    page.wait_for_selector("#quality-table tbody .q-row-check", timeout=10_000)
    first = page.locator("#quality-table tbody .set-override").first
    if not first.count():
        pytest.skip("no unscored rows")
    mid = first.get_attribute("data-id")
    first.click()
    page.fill("#q-ov-score", "71")
    page.fill("#q-ov-note", "ui regression")
    page.click('#q-ov-form button[type="submit"]')
    page.wait_for_function(
        "(id) => [...document.querySelectorAll('.reset-override')].some((b) => b.dataset.id === id)",
        arg=mid, timeout=10_000)
    _show_q_tab(page, "scores")
    assert int(page.inner_text("#q-sync-overrides")) >= 1
    _show_q_tab(page, "models")
    page.once("dialog", lambda d: d.accept())
    page.click(f'.reset-override[data-id="{mid}"]')
    page.wait_for_function(
        "(id) => ![...document.querySelectorAll('.reset-override')].some((b) => b.dataset.id === id)",
        arg=mid, timeout=10_000)
    status, body = live_server.admin("GET", "/v1/quality/overrides")
    assert mid not in {o["model_id"] for o in body["overrides"]}


@pytest.mark.parametrize("width,height", [(390, 844), (768, 1024)])
def test_tabs_fit_on_small_screens(page, live_server, width, height):
    _open_quality(page, live_server, width, height)
    for name in ("models", "scores", "aa"):
        _show_q_tab(page, name)
        assert _no_page_overflow(page) <= 2, f"overflow on {name} at {width}px"
    boxes = _boxes(page, ['[data-q-tab="models"]', '[data-q-tab="scores"]', '[data-q-tab="aa"]'])
    assert all(b["h"] < 60 for b in boxes), boxes
