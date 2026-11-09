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


@pytest.mark.parametrize("width", [1700, 1440, 1280])
def test_quality_forms_are_single_rows_on_desktop(page, live_server, width):
    _open_quality(page, live_server, width)
    _reveal_key_form(page)
    for row in (KEY_ROW, OV_ROW):
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
    _reveal_key_form(page)
    for row in (KEY_ROW, OV_ROW):
        boxes = _boxes(page, row)
        assert all(b and b["w"] > 0 for b in boxes), boxes
        for i, a in enumerate(boxes):
            assert a["right"] <= width + 1, f"{a['sel']} clipped at {width}px"
            for b in boxes[i + 1:]:
                assert not _overlaps(a, b), (a, b)
    assert _no_page_overflow(page) <= 2, f"horizontal overflow at {width}px"


def test_quality_header_is_compact_when_key_missing(page, live_server):
    _open_quality(page, live_server, 1440)
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
