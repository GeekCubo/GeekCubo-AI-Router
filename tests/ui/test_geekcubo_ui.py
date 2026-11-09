"""Browser-level coverage for GeekCubo 1.0's new surfaces.

Covers the three things this release adds to the dashboard that a unit test
cannot verify: the light/dark theme (persistence + no flash + contrast), the
redesigned Routing page (strategy cards, pools, policy form, dry-run), and
the routing analytics panel.

Skips cleanly when Playwright or a Chromium build is unavailable (see
conftest.py).
"""

from __future__ import annotations

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("geekcubo-ui"))
    try:
        yield server
    finally:
        stop_server(server)


@pytest.fixture
def context(browser):
    ctx = browser.new_context()
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    p = context.new_page()
    yield p
    p.close()


def _signed_in(page, live_server, path: str = "/") -> None:
    sign_in(page, live_server.base_url, path=path)
    page.wait_for_function(
        "() => document.querySelector('#custom-providers-card') !== null"
        " || document.querySelector('#app-shell') !== null",
        timeout=15_000,
    )


def _effective_theme(page) -> str:
    return page.evaluate("() => document.documentElement.getAttribute('data-theme')")


# ─────────────────────────── theme ───────────────────────────

def test_theme_toggle_switches_and_persists_across_reload(page, live_server):
    _signed_in(page, live_server)
    start = _effective_theme(page)
    assert start in ("light", "dark")

    # Explicit choice: pick the opposite of whatever we resolved to.
    target = "dark" if start == "light" else "light"
    page.click(f'[data-theme-choice="{target}"]')
    page.wait_for_function(
        "(t) => document.documentElement.getAttribute('data-theme') === t",
        arg=target, timeout=5_000,
    )
    assert page.locator(f'[data-theme-choice="{target}"]').get_attribute("aria-checked") == "true"

    # The choice must survive a reload, and be restored *before* first paint
    # by the inline head script (no light flash on a dark-themed install).
    page.reload(wait_until="domcontentloaded")
    assert _effective_theme(page) == target
    assert page.evaluate("() => localStorage.getItem('geekcubo-theme')") == target


def test_theme_choice_is_applied_before_paint(page, live_server):
    """The inline script in <head> sets data-theme before the body renders."""
    _signed_in(page, live_server)
    page.evaluate("() => localStorage.setItem('geekcubo-theme', 'dark')")
    page.goto(f"{live_server.base_url}/", wait_until="domcontentloaded")
    assert _effective_theme(page) == "dark"
    # Body background must already be the dark canvas, not the light one.
    bg = page.evaluate(
        "() => getComputedStyle(document.body).backgroundColor"
    )
    assert bg not in ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_body_text_meets_contrast_in_both_themes(page, live_server, theme):
    _signed_in(page, live_server)
    page.evaluate("(t) => localStorage.setItem('geekcubo-theme', t)", theme)
    page.reload(wait_until="domcontentloaded")
    ratio = page.evaluate(
        """() => {
          const parse = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = (rgb) => {
            const [r, g, b] = rgb.map((v) => {
              v /= 255;
              return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
            });
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
          };
          const l1 = lum(parse(getComputedStyle(document.body).color));
          const l2 = lum(parse(getComputedStyle(document.body).backgroundColor));
          const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
          return (hi + 0.05) / (lo + 0.05);
        }"""
    )
    assert ratio >= 4.5, f"body contrast {ratio:.2f} below 4.5 in {theme}"


# ─────────────────────────── routing page ───────────────────────────

def test_routing_page_renders_strategies_and_pools(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#panel-routing:not([hidden])", timeout=10_000)

    cards = page.locator(".strategy-card")
    assert cards.count() >= 5
    # Exactly one strategy is selected at a time, and it is reflected in the
    # underlying radio group for keyboard/screen-reader users.
    assert page.locator(".strategy-card.selected").count() == 1

    for pool in ("mundane", "hard", "fallback"):
        assert page.locator(f'[data-pool-chips="{pool}"]').count() == 1

    page.wait_for_function(
        "() => { const t = document.querySelector('#pool-count').textContent;"
        " return t && !t.includes('…'); }",
        timeout=15_000,
    )
    assert "model" in page.locator("#pool-count").inner_text().lower()


def test_selecting_a_strategy_persists_it(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#panel-routing:not([hidden])", timeout=10_000)

    target = page.locator('.strategy-card[data-value="cheapest"]')
    target.click()
    page.wait_for_function(
        "() => document.querySelector('.strategy-card[data-value=\"cheapest\"]')"
        ".classList.contains('selected')",
        timeout=10_000,
    )
    status, body = live_server.admin("GET", "/v1/routing")
    assert status == 200
    assert body["strategy"] == "cheapest"

    # Restore so the module-scoped server stays in a known state.
    live_server.admin("PUT", "/v1/routing", {"strategy": "balanced"})


def test_routing_policy_form_saves(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#panel-routing:not([hidden])", timeout=10_000)

    page.wait_for_selector("#routing-policy-card:not([hidden])", timeout=10_000)
    page.fill("#pol-fallback-max", "3")
    page.click("#pol-save")
    page.wait_for_function(
        "() => document.querySelector('#pol-status').textContent.trim().length > 0",
        timeout=10_000,
    )
    assert "saved" in page.locator("#pol-status").inner_text().lower()

    status, body = live_server.admin("GET", "/v1/routing")
    assert status == 200
    assert body["policy"]["fallback"]["max_attempts"] == 3

    live_server.admin("PUT", "/v1/routing", {"policy": body["policy"]})


def test_escalation_fields_disable_when_mode_is_off(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#routing-policy-card:not([hidden])", timeout=10_000)

    page.select_option("#pol-esc-mode", "off")
    assert page.locator("#pol-esc-threshold").is_disabled()
    page.select_option("#pol-esc-mode", "auto")
    assert page.locator("#pol-esc-threshold").is_enabled()
    page.select_option("#pol-esc-mode", "off")


def test_explain_dry_run_reports_a_decision(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#routing-explain-card:not([hidden])", timeout=10_000)

    page.click("#explain-form button[type=submit]")
    page.wait_for_function(
        "() => { const el = document.querySelector('#explain-result');"
        " return el && !el.textContent.includes('Evaluating'); }",
        timeout=15_000,
    )
    text = page.locator("#explain-result").inner_text().lower()
    # Either a candidate was picked or a diagnosis was named — never blank.
    assert "selected" in text or "candidate" in text or "diagnosis" in text


# ─────────────────────────── analytics ───────────────────────────

def test_routing_analytics_panel_renders_kpis(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="analytics"]')
    page.wait_for_selector("#panel-analytics:not([hidden])", timeout=10_000)
    page.wait_for_selector("#ra-kpis .ra-kpi", timeout=15_000)
    assert page.locator("#ra-kpis .ra-kpi").count() >= 4
    # Empty state is a valid state — but the summary must always be filled in.
    assert page.locator("#ra-summary").inner_text().strip()


def test_recent_requests_table_has_routing_column(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="analytics"]')
    page.wait_for_selector("#panel-analytics:not([hidden])", timeout=10_000)
    header = page.locator("#recent-table thead").inner_text().lower()
    assert "routing" in header


# ─────────────────────────── accessibility / responsiveness ───────────────────────────

def test_pool_toggles_expose_a11y_state(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#pool-models-table tbody tr", timeout=15_000)
    for btn in page.locator("[data-pool-toggle]").all()[:6]:
        state = btn.get_attribute("aria-pressed")
        assert state in ("true", "false")


@pytest.mark.parametrize("width", [390, 768, 1440])
def test_routing_page_does_not_overflow(page, live_server, width):
    page.set_viewport_size({"width": width, "height": 900})
    _signed_in(page, live_server)
    page.click('[data-tab="routing"]')
    page.wait_for_selector("#panel-routing:not([hidden])", timeout=10_000)
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 2, f"horizontal overflow of {overflow}px at {width}px"


# ─────────────────────────── routing profiles ───────────────────────────

def test_profiles_page_lists_auto_and_created_profiles(page, live_server):
    live_server.admin("POST", "/v1/routing-profiles", {"display_name": "Economy", "strategy": "cheapest"})
    _signed_in(page, live_server)
    page.click('[data-tab="profiles"]')
    page.wait_for_selector("#panel-profiles:not([hidden])", timeout=10_000)
    page.wait_for_selector(".profile-row", timeout=15_000)
    rows = page.locator(".profile-row")
    assert rows.count() >= 2
    text = page.inner_text("#profile-list")
    assert "auto" in text.lower()
    assert "economy" in text.lower()


def test_profile_editor_creates_a_profile(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="profiles"]')
    page.wait_for_selector("#panel-profiles:not([hidden])", timeout=10_000)
    page.click("#profile-new-btn")
    page.wait_for_selector("#profile-dialog[open]", timeout=10_000)
    page.fill("#pf-name", "My Custom")
    page.select_option("#pf-strategy", "quality")
    # Slug is derived from the name as the operator types.
    assert page.input_value("#pf-slug") == "my-custom"
    page.click("#pf-save")
    page.wait_for_function(
        "() => [...document.querySelectorAll('.profile-slug')].some(e => e.textContent === 'my-custom')",
        timeout=15_000,
    )
    status, body = live_server.admin("GET", "/v1/routing-profiles")
    assert any(p["slug"] == "my-custom" and p["strategy"] == "quality" for p in body["profiles"])


def test_profile_delete_requires_confirmation(page, live_server):
    live_server.admin("POST", "/v1/routing-profiles", {"display_name": "Temp Profile"})
    _signed_in(page, live_server)
    page.click('[data-tab="profiles"]')
    page.wait_for_selector(".profile-row", timeout=15_000)
    row = page.locator('.profile-row:has(.profile-slug:text-is("temp-profile"))')
    row.locator(".cp-menu > summary").click()
    row.locator('[data-pa="delete"]').click()
    page.wait_for_selector("#profile-delete-dialog[open]", timeout=10_000)
    assert "temp-profile" in page.inner_text("#pd-body")
    page.click("#pd-confirm")
    page.wait_for_function(
        "() => ![...document.querySelectorAll('.profile-slug')].some(e => e.textContent === 'temp-profile')",
        timeout=15_000,
    )


# ─────────────────────────── integrations ───────────────────────────

def test_integrations_generates_opencode_config_without_secrets(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="integrations"]')
    page.wait_for_selector("#panel-integrations:not([hidden])", timeout=10_000)
    page.wait_for_function(
        "() => document.querySelector('#int-code')?.textContent.includes('providers')",
        timeout=15_000,
    )
    code = page.inner_text("#int-code")
    assert '"geek"' in code
    assert "{env:GEEKCUBO_API_KEY}" in code
    assert "sk-" not in code.replace("sk-geek-...", "")


def test_integrations_lists_every_supported_tool(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="integrations"]')
    page.wait_for_selector("#int-apps .int-app", timeout=15_000)
    apps = page.locator("#int-apps .int-app")
    assert apps.count() >= 9
    assert "claude code" in page.inner_text("#int-apps").lower()


def test_claude_code_generator_emits_anthropic_env(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="integrations"]')
    page.wait_for_selector("#int-apps .int-app", timeout=15_000)
    page.click('[data-int-app="claude-code"]')
    page.wait_for_function(
        "() => document.querySelector('#int-code')?.textContent.includes('ANTHROPIC_BASE_URL')",
        timeout=15_000,
    )
    code = page.inner_text("#int-code")
    assert "ANTHROPIC_AUTH_TOKEN" in code
    # Base URL must not carry /v1 — Claude Code appends /v1/messages itself.
    line = next(ln for ln in code.splitlines() if "ANTHROPIC_BASE_URL" in ln)
    assert not line.rstrip('"').endswith("/v1")


# ─────────────────────────── model intelligence ───────────────────────────

def test_intelligence_lists_three_builtin_sources(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="intelligence"]')
    page.wait_for_selector("#panel-intelligence:not([hidden])", timeout=10_000)
    page.wait_for_selector(".mi-row", timeout=15_000)
    text = page.inner_text("#mi-list").lower()
    assert "litellm" in text
    assert "models.dev" in text
    assert "portkey" in text


def test_intelligence_rejects_an_internal_url(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="intelligence"]')
    page.wait_for_selector(".mi-row", timeout=15_000)
    page.click("#mi-add-btn")
    page.fill("#mi-name", "internal")
    page.fill("#mi-url", "http://169.254.169.254/latest/meta-data")
    page.click("#mi-form button[type=submit]")
    page.wait_for_selector("#mi-error:not([hidden])", timeout=10_000)
    assert page.inner_text("#mi-error")


def test_intelligence_price_lookup_shows_sources(page, live_server):
    _signed_in(page, live_server)
    page.click('[data-tab="intelligence"]')
    page.wait_for_selector(".mi-row", timeout=15_000)
    page.fill("#mi-lookup-id", "openai/gpt-4o")
    page.click("#mi-lookup-form button[type=submit]")
    page.wait_for_selector("#mi-lookup-result .explain-result", timeout=15_000)
    text = page.inner_text("#mi-lookup-result").lower()
    assert "input" in text and "source" in text


# ─────────────────────────── readability guard ───────────────────────────

def test_no_user_visible_text_is_below_12px(page, live_server):
    """Regression guard for the readability pass: 12px is the floor."""
    _signed_in(page, live_server)
    for tab in ("providers", "routing", "profiles", "integrations", "intelligence", "analytics"):
        page.click(f'[data-tab="{tab}"]')
        page.wait_for_timeout(600)
        smallest = page.evaluate(
            """() => {
              let min = 99;
              const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
              while (w.nextNode()) {
                const t = w.currentNode;
                if (!t.textContent.trim()) continue;
                const el = t.parentElement;
                if (!el || el.closest('.sr-only,[aria-hidden="true"]')) continue;
                const cs = getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) continue;
                min = Math.min(min, parseFloat(cs.fontSize));
              }
              return min;
            }"""
        )
        assert smallest >= 12, f"{tab} renders text at {smallest}px"
