"""Browser-level checks for sidebar shortcuts and the web-search mode setting.

Sidebar: every number shown next to a nav item must be the key that opens
that item, and items without a shortcut must not show one. The help drawer
must describe the same range.

Web search: "Auto" is reserved (no automatic search planner exists). It must
be visible as unavailable, impossible to pick in the form, and refused by the
API, so it can never be switched on by accident.

Skips cleanly when Playwright or a Chromium build is unavailable.
"""

from __future__ import annotations

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("nav-search-ui"))
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


# ─────────────────────────── sidebar shortcuts ───────────────────────────

def _nav_items(page) -> list[dict]:
    return page.eval_on_selector_all(
        "#tabs .nav-item",
        """els => els.map(e => ({
            tab: e.dataset.tab,
            kbd: e.querySelector('kbd')?.textContent.trim() || null,
            shortcut: e.dataset.shortcut || null,
            aria: e.getAttribute('aria-keyshortcuts'),
        }))""",
    )


def test_every_displayed_number_opens_its_own_item(page, live_server):
    sign_in(page, live_server.base_url)
    items = _nav_items(page)
    shown = [i for i in items if i["kbd"]]
    assert [i["kbd"] for i in shown] == [str(n) for n in range(1, 10)], items

    for item in shown:
        # The visible hint, the data attribute and the accessible shortcut agree.
        assert item["shortcut"] == item["kbd"] == item["aria"], item
        page.focus("body")
        page.keyboard.press(item["kbd"])
        page.wait_for_selector(f"#panel-{item['tab']}.active", timeout=5_000)
        active = page.eval_on_selector("#tabs .nav-item.active", "e => e.dataset.tab")
        assert active == item["tab"], (item, active)


def test_items_without_a_shortcut_show_no_number(page, live_server):
    sign_in(page, live_server.base_url)
    unnumbered = {i["tab"] for i in _nav_items(page) if not i["kbd"]}
    assert unnumbered == {"chat", "local", "intelligence"}
    for item in _nav_items(page):
        if item["tab"] in unnumbered:
            assert item["shortcut"] is None and item["aria"] is None, item


def test_digit_keys_are_ignored_while_typing_or_with_modifiers(page, live_server):
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    page.focus("#ch-input")
    page.keyboard.type("2")
    assert page.eval_on_selector("#tabs .nav-item.active", "e => e.dataset.tab") == "chat"
    assert page.input_value("#ch-input") == "2"

    page.focus("body")
    page.keyboard.press("Alt+3")
    assert page.eval_on_selector("#tabs .nav-item.active", "e => e.dataset.tab") == "chat"


def test_help_drawer_describes_the_real_shortcut_range(page, live_server):
    sign_in(page, live_server.base_url)
    page.focus("body")
    page.keyboard.press("?")
    page.wait_for_selector("#help-drawer:not([hidden])", timeout=5_000)
    first = page.inner_text(".kbd-list li:first-child")
    assert "1" in first and "9" in first, first
    # On Linux/Windows the palette hint names the key that actually works.
    palette_hint = page.inner_text("#open-palette kbd")
    assert palette_hint == "Ctrl K", palette_hint
    page.keyboard.press("Escape")
    page.keyboard.press("Control+k")
    page.wait_for_selector("#palette:not([hidden])", timeout=5_000)


# ─────────────────────────── web search mode ───────────────────────────

def test_auto_search_mode_is_shown_as_unavailable(page, live_server):
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    page.click("#ch-settings")
    page.wait_for_selector("#chat-settings-dialog[open]", timeout=10_000)

    options = page.eval_on_selector_all(
        "#chs-search-mode option",
        "els => els.map(o => ({value: o.value, disabled: o.disabled, text: o.textContent}))",
    )
    by_value = {o["value"]: o for o in options}
    assert set(by_value) == {"off", "manual", "auto"}
    assert by_value["auto"]["disabled"] is True
    assert "reserved" in by_value["auto"]["text"].lower()
    assert by_value["off"]["disabled"] is False and by_value["manual"]["disabled"] is False
    assert page.input_value("#chs-search-mode") == "off"
    help_text = page.inner_text("#chs-search-mode + .field-help").lower()
    assert "not implemented" in help_text

    # A real user cannot reach it: keyboard navigation through the select
    # skips the disabled option.
    page.focus("#chs-search-mode")
    for _ in range(4):
        page.keyboard.press("ArrowDown")
    assert page.input_value("#chs-search-mode") == "manual"

    # Even if a stale or scripted form submitted it, saving does not enable it.
    page.evaluate(
        """() => { const s = document.querySelector('#chs-search-mode');
                   s.querySelector('option[value=auto]').disabled = false; s.value = 'auto'; }"""
    )
    page.click("#chs-save")
    page.wait_for_function(
        "() => [...document.querySelectorAll('.toast.err')].some(t => /reserved/i.test(t.textContent))",
        timeout=10_000,
    )
    page.wait_for_function("() => chState.searchSettings?.mode !== 'auto'", timeout=5_000)


def test_api_refuses_to_enable_auto_search(page, live_server):
    status, _ = live_server.admin(
        "PUT", "/api/chat/search-settings",
        {"backend": "searxng", "service_url": "http://127.0.0.1:9/", "mode": "manual"},
    )
    assert status == 200
    status, body = live_server.admin("PUT", "/api/chat/search-settings", {"mode": "auto"})
    assert status == 422, body
    assert "reserved" in str(body).lower()
    status, body = live_server.admin("GET", "/api/chat/search-settings")
    assert body["mode"] == "manual"

    # Manual mode shows the per-message composer toggle; off hides it.
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    page.wait_for_selector("#ch-search-toggle:not([hidden])", timeout=10_000)
    page.click("#ch-search-toggle")
    assert page.get_attribute("#ch-search-toggle", "aria-pressed") == "true"

    live_server.admin("PUT", "/api/chat/search-settings", {"mode": "off"})
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#panel-chat.active", timeout=15_000)
    page.wait_for_function("() => chState.searchSettings?.mode === 'off'", timeout=10_000)
    assert page.evaluate("() => document.querySelector('#ch-search-toggle').hidden") is True


def test_disabled_server_still_hides_paperclip_explicitly(tmp_path_factory, browser):
    """Counterpart to the reload fix: only an explicit server `enabled:false`
    hides the paperclip, and that still works after a deep-link sign-in."""
    server = boot_server(
        tmp_path_factory.mktemp("nav-attach-off"),
        extra_env={"ATTACHMENTS_ENABLED": "false"},
    )
    ctx = browser.new_context()
    pg = ctx.new_page()
    try:
        sign_in(pg, server.base_url, path="/#chat")
        pg.wait_for_function("() => chState.attachmentLimits?.enabled === false", timeout=15_000)
        assert pg.evaluate("() => document.querySelector('#ch-attach').hidden") is True
    finally:
        ctx.close()
        stop_server(server)
