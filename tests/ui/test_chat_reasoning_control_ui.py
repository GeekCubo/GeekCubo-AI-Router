"""Chat header: the reasoning selector is a labelled, readable control that
never overlaps the other header controls. Real server, real browser."""

from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")


from tests.ui.test_custom_provider_ui import (  # noqa: E402,F401  (fixtures)
    live_server,
    mock_upstream,
)


@pytest.mark.parametrize("theme,width,height", [
    ("light", 1440, 900), ("dark", 1440, 900), ("light", 768, 1024), ("dark", 390, 844)])
def test_reasoning_selector_is_labelled_and_unobstructed(browser, live_server, theme, width, height):  # noqa: F811
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


@pytest.fixture
def mixed_pool(live_server, mock_upstream):  # noqa: F811
    """One Auto-eligible provider: a model confirmed for low/high and one
    with unknown reasoning support (the production situation)."""
    st, prov = live_server.admin("POST", "/v1/custom-providers", {
        "display_name": "Mixpool", "base_url": mock_upstream.base_url,
        "api_key": "sk-test-mixpool-0000", "eligible_for_auto": True,
    })
    assert st == 201, prov
    entries = [
        {"model_id": mid, "display_name": mid, "context_length": 128_000,
         "input_cost_per_million": 1, "output_cost_per_million": 2}
        for mid in ("confirmed-model", "unknown-model")
    ]
    st, _ = live_server.admin("PUT", f"/v1/custom-providers/{prov['id']}/models", entries)
    assert st == 200
    st, provs = live_server.admin("GET", "/v1/custom-providers")
    plist = provs if isinstance(provs, list) else provs.get("providers", [])
    p = next(x for x in plist if x["id"] == prov["id"])
    mid = next(m["id"] for m in p["models"] if m["model_id"] == "confirmed-model")
    st, body = live_server.admin("PATCH", f"/v1/custom-providers/{prov['id']}/models/{mid}",
                                 {"reasoning_levels": ["low", "high"]})
    assert st == 200, body
    yield p["slug"]
    live_server.admin("DELETE", f"/v1/custom-providers/{prov['id']}")


def _options(page):
    return page.evaluate("""() => [...document.querySelectorAll('#ch-reasoning option')].map((o) =>
      [o.value, o.parentElement.tagName === 'OPTGROUP'])""")


def test_reasoning_selector_opens_and_selects_with_mixed_auto_pool(browser, live_server, mixed_pool):  # noqa: F811
    from tests.ui.conftest import sign_in

    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors: list[str] = []
    chat_posts: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda q: chat_posts.append(q.url)
            if q.method == "POST" and "/completions" in q.url else None)
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    sel = page.locator("#ch-reasoning")
    page.wait_for_function("() => document.querySelectorAll('#ch-reasoning option').length > 1", timeout=15_000)

    # Auto: enabled; confirmed levels plain, the rest offered as unverified.
    assert sel.is_enabled()
    opts = dict(_options(page))
    assert opts["default"] is False and opts["low"] is False and opts["high"] is False
    assert opts["medium"] is True and opts["xhigh"] is True
    # Keyboard and pointer both reach it, and a level can be chosen and undone.
    sel.focus()
    assert page.evaluate("() => document.activeElement.id") == "ch-reasoning"
    sel.select_option("high")
    assert page.evaluate("() => chState.reasoning") == "high"
    assert sel.evaluate("e => e.options[e.selectedIndex].text") == "Reasoning: High"
    sel.select_option("default")
    assert page.evaluate("() => chState.reasoning") == "default"

    # Pinned confirmed model: only its levels, none unverified.
    page.evaluate(f"""() => {{ const s = chModelSelect(); s.value = '{mixed_pool}/confirmed-model';
      document.querySelector('#ch-model').dispatchEvent(new Event('change')); }}""")
    assert [v for v, _ in _options(page)] == ["default", "low", "high"]
    # Pinned unknown model: every level, all labelled unverified.
    page.evaluate(f"""() => {{ const s = chModelSelect(); s.value = '{mixed_pool}/unknown-model';
      document.querySelector('#ch-model').dispatchEvent(new Event('change')); }}""")
    opts = _options(page)
    assert opts[0] == ["default", False] and len(opts) == 8 and all(g for _, g in opts[1:])
    assert sel.is_enabled()
    assert chat_posts == [] and errors == []
    ctx.close()
