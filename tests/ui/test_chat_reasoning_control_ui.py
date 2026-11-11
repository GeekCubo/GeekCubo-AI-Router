"""Chat header: the reasoning selector is a labelled, readable control that
never overlaps the other header controls. Real server, real browser."""

from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    from tests.ui.conftest import boot_server, stop_server

    server = boot_server(tmp_path_factory.mktemp("chat-reasoning"))
    yield server
    stop_server(server)


@pytest.mark.parametrize("theme,width,height", [
    ("light", 1440, 900), ("dark", 1440, 900), ("light", 768, 1024), ("dark", 390, 844)])
def test_reasoning_selector_is_labelled_and_unobstructed(browser, live_server, theme, width, height):
    from tests.ui.conftest import sign_in

    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, live_server.base_url)
    page.evaluate(f"() => applyTheme('{theme}')")
    page.evaluate("() => setTab('chat')")
    sel = page.locator("#ch-reasoning")
    sel.wait_for(state="visible", timeout=15_000)
    shown = sel.evaluate("e => e.options[e.selectedIndex]?.text || ''")
    assert shown.startswith("Reasoning: "), shown
    box = sel.bounding_box()
    assert box["width"] >= 120, box
    # Visible header controls (the sr-only label excluded) must not overlap,
    # and the selector must stay inside the header.
    boxes = page.evaluate("""() => [...document.querySelectorAll('.chat-head-actions > *')]
      .filter((e) => e.offsetParent && !e.classList.contains('sr-only'))
      .map((e) => { const r = e.getBoundingClientRect(); return [r.left, r.right]; })""")
    assert all(a[1] <= b[0] for a, b in zip(boxes, boxes[1:], strict=False)), boxes
    head = page.locator(".chat-head").bounding_box()
    assert box["x"] + box["width"] <= head["x"] + head["width"]
    assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    assert errors == []
    ctx.close()
