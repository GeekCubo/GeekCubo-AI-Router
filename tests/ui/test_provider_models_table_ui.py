"""Providers → Manage Models: compact rows, status icons, Actions menu and the
inline editor that opens directly beneath the selected model.

Real server + real browser. The bulk-action toolbar is asserted unchanged.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.ui.test_custom_provider_ui import (  # noqa: E402,F401  (fixtures)
    _clean_custom_providers,
    live_server,
    mock_upstream,
)

MODELS = [
    ("claude-opus-5-5", 1_000_000, (25, 125)),
    ("gpt-6.1-sol", 1_050_000, None),
    ("deepseek-v4.1-flash-1017-abliterated", 1_048_576, (0.2, 0.2)),
    ("glm-5.3-flash", 1_000_000, (1.6, 1.6)),
    ("kimi-k3", 1_000_000, (0.6, 2.5)),
    ("grok-4.7", 500_000, (3, 15)),
    ("qwen3-abliterated", 32_768, None),
    ("gemma-4-31b-abliterated", 32_768, (0.1, 0.1)),
    ("gemini-4-argon", 128_000, (1.25, 10)),
    ("an-unusually-long-community-model-identifier-q4_k_m-instruct-v2-final", 131_072, None),
    ("o3", 200_000, (2, 8)),
]


@pytest.fixture
def table(browser, live_server, mock_upstream):  # noqa: F811
    from tests.ui.conftest import sign_in

    st, prov = live_server.admin("POST", "/v1/custom-providers", {
        "display_name": "Apixo", "base_url": mock_upstream.base_url,
        "api_key": "sk-test-abcdefghijkl", "eligible_for_auto": True,
    })
    assert st == 201, prov
    entries = []
    for mid, ctx, price in MODELS:
        e = {"model_id": mid, "display_name": mid, "context_length": ctx, "supports_tools": True}
        if price:
            e.update(input_cost_per_million=price[0], output_cost_per_million=price[1])
        entries.append(e)
    st, _ = live_server.admin("PUT", f"/v1/custom-providers/{prov['id']}/models", entries)
    assert st == 200
    st, provs = live_server.admin("GET", "/v1/custom-providers")
    plist = provs if isinstance(provs, list) else provs.get("providers", [])
    p = next(x for x in plist if x["id"] == prov["id"])
    ids = {m["model_id"]: m["id"] for m in p["models"]}
    live_server.admin("PATCH", f"/v1/custom-providers/{prov['id']}/models/{ids['claude-opus-5-5']}",
                      {"capabilities": {"vision": "supported", "json_schema": "unsupported"}})
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # Dialog policy is per test: page.dialog_policy = "accept" | "dismiss".
    page.dialog_policy = "accept"
    page.dialogs = []

    def _on_dialog(d):
        page.dialogs.append(d.message)
        d.accept() if page.dialog_policy == "accept" else d.dismiss()

    page.on("dialog", _on_dialog)
    sign_in(page, live_server.base_url, path="/providers")
    page.wait_for_selector("#panel-providers.active", timeout=15_000)
    page.click(f'[data-cp-manage="{prov["id"]}"]')
    holder = f'[data-cp-models-holder="{prov["id"]}"]'
    page.wait_for_selector(f"{holder} tr[data-model-row]", timeout=15_000)

    def row(mid):
        return page.locator(f'{holder} tr[data-model-row="{ids[mid]}"]')

    yield page, row, holder, ids, prov, live_server
    assert errors == []
    ctx.close()


def _cap(row, key):
    return row.locator(f'[data-cp-cap="{key}"]')


def test_status_icons_render_each_state_with_provenance(table):
    page, row, *_ = table
    r = row("claude-opus-5-5")
    assert _cap(r, "vision").get_attribute("data-cap-state") == "supported"
    assert _cap(r, "json_schema").get_attribute("data-cap-state") == "unsupported"
    assert _cap(r, "json_mode").get_attribute("data-cap-state") == "unknown"
    # No dropdowns and no repeated OVERRIDE/"via …" text in capability cells.
    assert r.locator("select").count() == 0
    assert "override" not in r.inner_text().lower()
    assert "via " not in r.inner_text()
    # Provenance is in the tooltip/accessible name; overrides carry a marker.
    assert _cap(r, "vision").get_attribute("aria-label").startswith("Vision: Supported — Administrator override")
    assert _cap(r, "vision").locator(".cp-ov-dot").count() == 1
    assert _cap(r, "json_mode").locator(".cp-ov-dot").count() == 0
    _cap(r, "vision").hover()
    assert page.locator("#cp-tooltip").inner_text() == "Vision: Supported — Administrator override"


def test_capability_menu_updates_icon_and_use_catalog_clears(table):
    page, row, holder, ids, *_ = table
    btn = _cap(row("o3"), "json_mode")
    btn.focus()
    page.keyboard.press("Enter")
    page.wait_for_selector(".cp-popmenu")
    items = page.locator(".cp-popmenu-item").all_inner_texts()
    assert [i.split("\n")[-1] if "catalog" not in i.lower() else "Use catalog" for i in items][:3] == [
        "Supported", "Unsupported", "Unknown"]
    assert any("Use catalog" in i for i in items)
    page.keyboard.press("Escape")
    assert page.locator(".cp-popmenu").count() == 0
    assert page.evaluate("() => document.activeElement.dataset.cpCap") == "json_mode"

    btn.click()
    page.locator(".cp-popmenu-item", has_text="Unsupported").click()
    sel = f'{holder} tr[data-model-row="{ids["o3"]}"] [data-cp-cap="json_mode"]'
    page.wait_for_function(f"() => document.querySelector('{sel}').dataset.capState === 'unsupported'")
    assert _cap(row("o3"), "json_mode").get_attribute("data-cap-override") == "true"

    _cap(row("o3"), "json_mode").click()
    page.locator(".cp-popmenu-item", has_text="Use catalog").click()
    page.wait_for_function(f"() => document.querySelector('{sel}').dataset.capOverride === 'false'")


def test_compact_context_price_and_catalog_status(table):
    _page, row, *_ = table
    r = row("claude-opus-5-5")
    cells = r.locator(".cp-num .cp-compact")
    assert cells.nth(0).inner_text().startswith("1M")
    assert "1,000,000" in cells.nth(0).get_attribute("data-cp-tip")
    assert cells.nth(2).inner_text().strip() == "$25.00 / $125.00"
    assert "input $25.00" in cells.nth(2).get_attribute("data-cp-tip")
    # A missing price is "unknown", never $0.
    assert row("gpt-6.1-sol").locator(".cp-num .cp-compact").nth(2).inner_text().strip() == "unknown"
    assert "$0" not in row("gpt-6.1-sol").inner_text()
    # Catalog status: a compact icon (no row-height UNMATCHED pill), with the
    # status in its accessible name; the provider summary counts remain.
    badge = row("deepseek-v4.1-flash-1017-abliterated").locator(".match-badge")
    assert badge.get_attribute("data-match") == "unmatched"
    assert "Unmatched" in badge.get_attribute("aria-label")
    assert badge.inner_text().strip() == ""


def test_long_model_id_is_single_line_with_full_id_available(table):
    page, row, *_ = table
    r = row("an-unusually-long-community-model-identifier-q4_k_m-instruct-v2-final")
    code = r.locator(".cp-model-id")
    full = "an-unusually-long-community-model-identifier-q4_k_m-instruct-v2-final"
    assert full in code.inner_text()
    assert full in code.get_attribute("data-cp-tip")
    assert code.evaluate("e => e.scrollWidth > e.clientWidth")  # truncated visually
    heights = [row(m).bounding_box()["height"] for m in ("an-unusually-long-community-model-identifier-q4_k_m-instruct-v2-final", "qwen3-abliterated")]
    assert abs(heights[0] - heights[1]) < 2


def test_edit_opens_directly_beneath_the_selected_row_and_saves_in_place(table):
    page, row, holder, ids, *_ = table
    target = "claude-opus-5-5"
    row(target).locator("[data-cp-actions]").click()
    assert page.locator(".cp-popmenu-item").all_inner_texts() == ["Details", "Edit model", "Verify reasoning", "Remove model"]
    page.locator(".cp-popmenu-item", has_text="Edit model").click()
    page.wait_for_selector(f"{holder} .cp-edit-row")
    assert page.evaluate(
        f"() => document.querySelector('{holder} tr[data-model-row=\"{ids[target]}\"]')"
        ".nextElementSibling.classList.contains('cp-edit-row')"
    )
    assert page.locator(f"{holder} .cp-edit-row").count() == 1
    assert "is-editing" in row(target).get_attribute("class")
    assert page.locator('.cp-inline-editor [data-m="model_id"]').input_value() == target
    # Every field of the previous editor is still editable.
    fields = page.locator(".cp-inline-editor [data-m]").evaluate_all("els => els.map(e => e.dataset.m)")
    assert set(fields) == {
        "model_id", "display_name", "context_length", "input_cost_per_million",
        "output_cost_per_million", "reference_input_cost_per_million",
        "reference_output_cost_per_million", "catalog_key", "supports_tools",
        "supports_vision", "supports_json_mode", "supports_json_schema"}
    assert page.evaluate("() => { const r = document.querySelector('.cp-edit-row').getBoundingClientRect();"
                         " return r.top >= 0 && r.top < innerHeight; }")
    page.fill('.cp-inline-editor [data-m="output_cost_per_million"]', "120")
    y0 = page.evaluate("() => scrollY")
    page.click("[data-cp-inline-save]")
    page.wait_for_selector(".cp-edit-row", state="detached")
    page.wait_for_function(
        f"() => document.querySelector('{holder} tr[data-model-row=\"{ids[target]}\"]').textContent.includes('$120.00')")
    assert abs(page.evaluate("() => scrollY") - y0) < 2


def test_unsaved_changes_prompt_and_cancel_escape(table):
    page, row, holder, *_ = table
    page.dialog_policy = "dismiss"
    prompts = page.dialogs
    row("o3").locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Edit model").click()
    page.fill('.cp-inline-editor [data-m="display_name"]', "changed")
    row("kimi-k3").locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Edit model").click()
    page.wait_for_timeout(200)
    assert prompts and "Discard unsaved changes to o3" in prompts[-1]
    # Dismissed: still editing o3, value preserved.
    assert page.locator('.cp-inline-editor [data-m="model_id"]').input_value() == "o3"
    assert page.locator('.cp-inline-editor [data-m="display_name"]').input_value() == "changed"


def test_cancel_and_escape_close_the_editor(table):
    page, row, holder, *_ = table
    for close in ("cancel", "escape"):
        row("o3").locator("[data-cp-actions]").click()
        page.locator(".cp-popmenu-item", has_text="Edit model").click()
        page.wait_for_selector(".cp-inline-editor")
        if close == "cancel":
            page.click("[data-cp-inline-cancel]")
        else:
            page.focus('.cp-inline-editor [data-m="display_name"]')
            page.keyboard.press("Escape")
        page.wait_for_selector(".cp-edit-row", state="detached")


def test_details_and_remove_from_actions_menu(table):
    page, row, holder, *_ = table
    row("gemini-4-argon").locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Details").click()
    page.wait_for_selector(f"{holder} .cp-detail-row")
    n = page.locator(f"{holder} tr[data-model-row]").count()
    row("qwen3-abliterated").locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Remove model").click()
    assert page.dialogs and "qwen3-abliterated" in page.dialogs[-1]
    page.wait_for_function(f"() => document.querySelectorAll('{holder} tr[data-model-row]').length === {n - 1}")


def test_enabled_is_independent_and_bulk_toolbar_unchanged(table):
    page, row, holder, *_ = table
    box = row("kimi-k3").locator("[data-cp-enable]")
    box.uncheck()
    page.wait_for_function(f"() => !document.querySelector('{holder} [data-cp-enable]:not(:checked)') === false")
    assert _cap(row("kimi-k3"), "tools").get_attribute("data-cap-state") == "supported"
    bulk = page.locator(f"{holder} .cp-model-bulk")
    assert bulk.locator("[data-cp-check-all-toolbar]").count() == 1
    assert bulk.locator("[data-cp-bulk-cap] option").all_inner_texts() == ["Tools", "Vision", "JSON mode", "JSON schema"]
    assert len(bulk.locator("[data-cp-bulk-state] option").all_inner_texts()) == 4
    assert [b.get_attribute("data-cp-bulk") for b in bulk.locator("[data-cp-bulk]").all()] == [
        "restore_metadata", "resolve_metadata", "enable", "disable", "remove"]


def test_menu_is_not_clipped_and_mobile_editor_fits(table):
    page, row, holder, *_ = table
    last = page.locator(f"{holder} tr[data-model-row]").last
    last.locator("[data-cp-actions]").click()
    assert page.evaluate("() => { const r = document.querySelector('.cp-popmenu').getBoundingClientRect();"
                         " return r.top >= 0 && r.bottom <= innerHeight && r.right <= innerWidth; }")
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 390, "height": 844})
    b = page.locator(f"{holder} [data-cp-actions]").first
    assert b.get_attribute("aria-label").startswith("Actions for ")
    b.scroll_into_view_if_needed()
    b.click()
    page.locator(".cp-popmenu-item", has_text="Edit model").click()
    page.wait_for_selector(".cp-inline-editor")
    over = page.evaluate("() => { const f = document.querySelector('.cp-inline-editor');"
                         " const w = f.closest('.cp-models').getBoundingClientRect();"
                         " return [...f.querySelectorAll('input,button')].filter(e => e.getBoundingClientRect().right > w.right + 1).length; }")
    assert over == 0
    assert not page.evaluate("() => document.documentElement.scrollWidth > innerWidth")


def test_verify_reasoning_confirms_shows_evidence_and_keeps_unknown(table):
    """The mock gateway reports no reasoning usage, so verification is
    inconclusive: evidence is shown, nothing is stored, the model stays
    Unknown. Cancelling the confirmation sends nothing."""
    page, row, holder, ids, prov, server = table
    r = row("qwen3-abliterated")
    r.locator("[data-cp-actions]").click()
    items = page.locator(".cp-popmenu-item").all_inner_texts()
    assert any(i.startswith("Verify reasoning") for i in items)
    # Cancel: no request is made.
    page.dialog_policy = "dismiss"
    calls: list[str] = []
    page.on("request", lambda q: calls.append(q.url) if "verify-reasoning" in q.url else None)
    page.locator(".cp-popmenu-item", has_text="Verify reasoning").click()
    assert "real requests" in page.dialogs[-1] and "credits" in page.dialogs[-1]
    page.wait_for_timeout(200)
    assert calls == []
    # Confirm: one verification call, evidence rendered in the row slot.
    page.dialog_policy = "accept"
    r.locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Verify reasoning").click()
    panel = page.locator(f"{holder} .cp-detail-row .cp-rsn-evidence")
    panel.wait_for(timeout=15_000)
    assert len(calls) == 1
    text = page.locator(f"{holder} .cp-detail-row").inner_text()
    assert "Inconclusive" in text
    assert "qwen3-abliterated" in text
    assert "Requests sent" in text and "invalid value" in text
    assert "Not conclusive (nothing stored)" in text
    assert "Unknown (effort is forwarded unchanged)" in text
    st, provs = server.admin("GET", "/v1/custom-providers")
    plist = provs if isinstance(provs, list) else provs.get("providers", [])
    m = next(x for p in plist if p["id"] == prov["id"] for x in p["models"] if x["model_id"] == "qwen3-abliterated")
    assert m["reasoning_levels"] is None and m["reasoning_source"] == "unknown"
    # Cooldown: an immediate second run is refused, not re-sent upstream.
    r.locator("[data-cp-actions]").click()
    page.locator(".cp-popmenu-item", has_text="Verify reasoning").click()
    page.locator(f"{holder} .cp-detail-row .cp-rsn-failed").wait_for(timeout=10_000)
    assert "wait a minute" in page.locator(f"{holder} .cp-detail-row").inner_text()


def test_details_show_reasoning_status_and_override(table):
    page, row, holder, ids, prov, server = table
    server.admin("PATCH", f"/v1/custom-providers/{prov['id']}/models/{ids['grok-4.7']}",
                 {"reasoning_levels": ["low", "high"]})
    page.reload()
    page.wait_for_selector("#panel-providers.active", timeout=15_000)
    page.click(f'[data-cp-manage="{prov["id"]}"]')
    page.wait_for_selector(f"{holder} tr[data-model-row]")
    row("grok-4.7").locator("[data-cp-actions]").click()
    assert any("Override: low, high" in i for i in page.locator(".cp-popmenu-item").all_inner_texts())
    page.locator(".cp-popmenu-item", has_text="Details").click()
    page.locator(f"{holder} .cp-detail-reasoning").wait_for(timeout=15_000)
    assert "Override: low, high" in page.locator(f"{holder} .cp-detail-reasoning").inner_text()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_desktop_columns_are_balanced_with_actions_header(table, theme):
    """The model column no longer takes every spare pixel: data columns get
    room for one-line headers, an Actions header sits above every Actions
    button, and provider-level buttons use the bordered secondary style."""
    page, row, holder, *_ = table
    page.evaluate(f"() => applyTheme('{theme}')")
    heads = page.locator(f"{holder} thead th")
    texts = [h.inner_text().strip() for h in heads.all()]
    assert texts[-1].lower() == "actions"
    widths = page.evaluate(f"""() => {{
      const ths = [...document.querySelectorAll('{holder} thead th')];
      const tbl = document.querySelector('{holder} table').getBoundingClientRect().width;
      return {{ tbl, model: ths[1].getBoundingClientRect().width,
        scroll: document.querySelector('{holder} .table-wrap').scrollWidth - document.querySelector('{holder} .table-wrap').clientWidth,
        tall: ths.slice(2).filter((th) => th.innerText.split("\\n").length > 2).map((th) => th.innerText) }};
    }}""")
    assert widths["model"] < widths["tbl"] * 0.35, widths
    # At desktop width the whole table fits its card; headers wrap at most
    # to two lines.
    assert widths["scroll"] <= 1, widths
    assert widths["tall"] == [], widths
    # Every Actions button sits inside the Actions header's horizontal span.
    head = heads.last.bounding_box()
    for b in page.locator(f"{holder} [data-cp-actions]").all():
        bb = b.bounding_box()
        assert head["x"] - 1 <= bb["x"] and bb["x"] + bb["width"] <= head["x"] + head["width"] + 1
    for sel in ("[data-cp-edit]", ".cp-menu > summary", "[data-cp-manage]"):
        assert "btn-secondary" in page.locator(sel).first.get_attribute("class"), sel
    assert not page.evaluate("() => document.documentElement.scrollWidth > innerWidth")
    page.screenshot(path=f"/tmp/opencode/fix_shots/local-providers-{theme}-1440.png")


def test_tablet_scrolls_inside_table_without_page_overflow(table):
    page, row, holder, *_ = table
    page.set_viewport_size({"width": 768, "height": 1024})
    page.wait_for_timeout(200)
    assert not page.evaluate("() => document.documentElement.scrollWidth > innerWidth")
    wrap = page.locator(f"{holder} .table-wrap")
    assert wrap.evaluate("e => e.scrollWidth > e.clientWidth")


