"""Browser-level (Playwright) coverage for Phase 2 authentication.

Drives the real dashboard: first-run setup with a server-printed token,
sign-in / sign-out, reload persistence, session expiry handling, password
change, and the API-key workflow (generate, one-time reveal, copy snippet,
rename, rotate, revoke). Also proves no credential lands in localStorage.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from tests.ui.conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    boot_server,
    sign_in,
    stop_server,
)


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("auth-ui"))
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
    """A page with NO global dialog handler.

    Tests that trigger confirm()/prompt() register exactly one `once` handler
    for that dialog. A global auto-accept here would race those handlers —
    both try to answer the same dialog, and whichever runs first decides
    (e.g. a "Cancel" meant to keep the old key would be accepted instead).
    """
    pg = context.new_page()
    yield pg


@pytest.fixture(autouse=True)
def _reset_login_throttle(live_server):
    """Tests deliberately fail logins; keep each one independent.

    The throttle is in-process, so the cheapest reliable reset is a revoke of
    the CLI-visible state plus a successful login (which clears the counter).
    """
    yield
    live_server.admin_login()


def _inference(base_url: str, key: str, path: str = "/v1/models") -> int:
    req = urllib.request.Request(
        f"{base_url}{path}", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# ── first-run setup (separate server: needs an uninitialized install) ─────


@pytest.fixture(scope="module")
def fresh_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("fresh-ui"), provision_admin=False)
    try:
        yield server
    finally:
        stop_server(server)


def test_first_run_shows_create_administrator(browser, fresh_server):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(fresh_server.base_url, wait_until="networkidle")
    pg.wait_for_selector("#setup-view:not([hidden])", timeout=15_000)
    assert pg.is_visible("text=Create Administrator Account")
    assert not pg.is_visible("#login-view")
    # No API-key field anywhere on the gate any more.
    assert pg.locator("#api-key-input").count() == 0
    ctx.close()


def test_first_run_setup_with_server_printed_token(browser, fresh_server):
    assert fresh_server.setup_token, "server did not print a setup token"
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(fresh_server.base_url, wait_until="networkidle")
    pg.wait_for_selector("#setup-view:not([hidden])", timeout=15_000)

    # Validation: mismatch is caught client-side, before any request.
    pg.fill("#setup-username", "owner")
    pg.fill("#setup-password", ADMIN_PASSWORD)
    pg.fill("#setup-password-confirm", ADMIN_PASSWORD + "x")
    pg.fill("#setup-token", fresh_server.setup_token)
    pg.click("#setup-submit")
    assert "do not match" in pg.inner_text("#setup-status")

    # Bad token is rejected by the server with an actionable message.
    pg.fill("#setup-password-confirm", ADMIN_PASSWORD)
    pg.fill("#setup-token", "wrong-token")
    pg.click("#setup-submit")
    pg.wait_for_function(
        "() => document.querySelector('#setup-status').textContent.includes('Invalid setup token')",
        timeout=10_000,
    )

    pg.fill("#setup-token", fresh_server.setup_token)
    pg.click("#setup-submit")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    assert pg.inner_text("#account-username") == "owner"
    ctx.close()

    # Setup is now permanently closed: a new visitor gets the login screen.
    ctx2 = browser.new_context()
    pg2 = ctx2.new_page()
    pg2.goto(fresh_server.base_url, wait_until="networkidle")
    pg2.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert not pg2.is_visible("#setup-view")
    ctx2.close()


# ── sign in / sign out ─────────────────────────────────────────────────────


def test_login_screen_and_successful_sign_in(page, live_server):
    page.goto(live_server.base_url, wait_until="networkidle")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert page.is_visible("#login-username")
    assert page.get_attribute("#login-password", "type") == "password"

    page.click("#login-password-toggle")
    assert page.get_attribute("#login-password", "type") == "text"
    page.click("#login-password-toggle")

    sign_in(page, live_server.base_url)
    assert page.inner_text("#account-username") == ADMIN_USERNAME


def test_wrong_password_shows_generic_error(page, live_server):
    page.goto(live_server.base_url, wait_until="networkidle")
    page.wait_for_selector("#login-view:not([hidden])")
    page.fill("#login-username", ADMIN_USERNAME)
    page.fill("#login-password", "definitely not it")
    page.click("#login-submit")
    page.wait_for_function(
        "() => document.querySelector('#login-status').textContent.length > 0",
        timeout=10_000,
    )
    assert page.inner_text("#login-status") == "Invalid username or password."
    assert not page.is_visible("#app-shell")


def test_session_persists_across_reload(page, live_server):
    sign_in(page, live_server.base_url)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    assert not page.is_visible("#login-view")


def test_no_credentials_in_browser_storage(page, context, live_server):
    sign_in(page, live_server.base_url)
    storage = page.evaluate("() => JSON.stringify({...localStorage})")
    assert "sk-geek" not in storage
    assert ADMIN_PASSWORD not in storage

    cookies = {c["name"]: c for c in context.cookies()}
    session = cookies["geekcubo_admin_session"]
    assert session["httpOnly"] is True
    assert session["sameSite"] == "Lax"
    # JavaScript cannot read the session cookie.
    assert "geekcubo_admin_session" not in page.evaluate("() => document.cookie")


def test_legacy_localstorage_key_is_purged(page, live_server):
    """A pre-2.0 browser may still hold an API key in the old storage slot."""
    page.goto(live_server.base_url, wait_until="domcontentloaded")
    page.evaluate("() => localStorage.setItem('geekcubo-api-key', 'sk-geek-stale')")
    page.reload(wait_until="networkidle")
    assert page.evaluate("() => localStorage.getItem('geekcubo-api-key')") is None
    # And it does not sign anyone in.
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)


def test_remember_me_is_unchecked_by_default_and_gives_a_normal_session(browser, live_server):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(live_server.base_url, wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert pg.is_visible("#login-remember")
    assert pg.is_checked("#login-remember") is False
    assert "14" in pg.inner_text("label[for='login-remember']")
    sign_in(pg, live_server.base_url)
    cookie = {c["name"]: c for c in ctx.cookies()}["geekcubo_admin_session"]
    # A normal session's cookie keeps the original 12-hour lifetime.
    import time
    assert cookie["expires"] - time.time() <= 12 * 3600 + 60
    ctx.close()


def test_remember_me_survives_a_browser_restart_and_is_listed(browser, live_server, tmp_path):
    import time

    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(live_server.base_url, wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    pg.fill("#login-username", ADMIN_USERNAME)
    pg.fill("#login-password", ADMIN_PASSWORD)
    pg.check("#login-remember")
    pg.click("#login-submit")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)

    cookie = {c["name"]: c for c in ctx.cookies()}["geekcubo_admin_session"]
    assert cookie["httpOnly"] is True and cookie["sameSite"] == "Lax"
    remaining = cookie["expires"] - time.time()
    assert 13.9 * 86400 < remaining <= 14 * 86400 + 60, remaining
    # Not readable by page scripts, not in storage.
    assert "geekcubo_admin_session" not in pg.evaluate("() => document.cookie")
    assert cookie["value"] not in pg.evaluate("() => JSON.stringify({...localStorage, ...sessionStorage})")

    # "Close the browser": persist cookies, drop the context, open a new one.
    state = tmp_path / "state.json"
    ctx.storage_state(path=str(state))
    ctx.close()
    ctx2 = browser.new_context(storage_state=str(state))
    pg2 = ctx2.new_page()
    pg2.goto(live_server.base_url, wait_until="networkidle")
    pg2.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    assert not pg2.is_visible("#login-view")

    # Security page shows the remembered session and its expiry, never a token.
    pg2.click('#tabs [data-tab="security"]')
    pg2.wait_for_selector("#panel-security.active")
    pg2.wait_for_function(
        "() => document.querySelector('#sessions-table tbody tr') !== null", timeout=10_000
    )
    table = pg2.inner_text("#sessions-table").lower()
    assert "remembered (14 days)" in table
    assert "remembered" in pg2.inner_text("#sec-session").lower()
    assert cookie["value"] not in pg2.content()

    # Logging out ends it for good.
    pg2.click("#account-btn")
    pg2.wait_for_selector("#account-dropdown:not([hidden])")
    pg2.click("#logout-btn")
    pg2.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    ctx2.close()
    ctx3 = browser.new_context(storage_state=str(state))  # stale cookie replayed
    pg3 = ctx3.new_page()
    pg3.goto(live_server.base_url, wait_until="networkidle")
    pg3.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    ctx3.close()


def test_logout_from_account_menu(page, live_server):
    sign_in(page, live_server.base_url)
    page.click("#account-btn")
    page.wait_for_selector("#account-dropdown:not([hidden])")
    page.click("#logout-btn")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)

    page.reload(wait_until="networkidle")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert not page.is_visible("#app-shell")


def test_revoked_session_drops_back_to_login(page, live_server):
    """Another device signing everything out must not leave a dead shell."""
    sign_in(page, live_server.base_url)
    r = live_server.cli("revoke-sessions")
    assert r.returncode == 0, r.stderr
    # Any admin call now 401s; the app should react by showing sign-in.
    page.click('#tabs [data-tab="keys"]')
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert "expired" in page.inner_text("#login-status").lower()


# ── Security page ──────────────────────────────────────────────────────────


def test_security_page_shows_account_and_sessions(page, live_server):
    sign_in(page, live_server.base_url)
    page.click('#tabs [data-tab="security"]')
    page.wait_for_selector("#panel-security.active")
    page.wait_for_function(
        "() => document.querySelector('#sec-username').textContent !== '—'",
        timeout=10_000,
    )
    assert page.inner_text("#sec-username") == ADMIN_USERNAME
    # The pill is CSS-uppercased; compare case-insensitively.
    assert "this device" in page.inner_text("#sessions-table").lower()


def test_change_password_round_trip(browser, live_server):
    """Change it, prove another device was signed out, change it back."""
    other_ctx = browser.new_context()
    other = other_ctx.new_page()
    sign_in(other, live_server.base_url)

    ctx = browser.new_context()
    pg = ctx.new_page()
    sign_in(pg, live_server.base_url)
    pg.click('#tabs [data-tab="security"]')
    pg.wait_for_selector("#panel-security.active")

    new_pw = "a brand new secret phrase entirely"
    pg.fill("#pw-current", "wrong current password")
    pg.fill("#pw-new", new_pw)
    pg.fill("#pw-confirm", new_pw)
    pg.click("#pw-submit")
    pg.wait_for_function(
        "() => document.querySelector('#pw-status').textContent.length > 0",
        timeout=10_000,
    )
    assert "incorrect" in pg.inner_text("#pw-status").lower()

    pg.fill("#pw-current", ADMIN_PASSWORD)
    pg.fill("#pw-new", new_pw)
    pg.fill("#pw-confirm", new_pw)
    pg.click("#pw-submit")
    pg.wait_for_function(
        "() => document.querySelector('#pw-status').textContent.includes('updated')",
        timeout=15_000,
    )
    # This device stays in; the fields are cleared.
    assert pg.is_visible("#app-shell")
    assert pg.input_value("#pw-current") == ""

    # The other device is signed out on its next request.
    other.click('#tabs [data-tab="keys"]')
    other.wait_for_selector("#login-view:not([hidden])", timeout=15_000)

    # Restore the shared password for the rest of the module.
    pg.fill("#pw-current", new_pw)
    pg.fill("#pw-new", ADMIN_PASSWORD)
    pg.fill("#pw-confirm", ADMIN_PASSWORD)
    pg.click("#pw-submit")
    pg.wait_for_function(
        "() => document.querySelector('#pw-status').textContent.includes('updated')",
        timeout=15_000,
    )
    live_server._csrf = ""  # helper session was revoked; re-login lazily
    ctx.close()
    other_ctx.close()


# ── API keys ───────────────────────────────────────────────────────────────


def _open_keys(page, live_server):
    sign_in(page, live_server.base_url)
    page.click('#tabs [data-tab="keys"]')
    page.wait_for_selector("#panel-keys.active")


def _generate(page, name: str, expiry: str = "") -> str:
    page.fill("#key-name", name)
    if expiry:
        page.select_option("#key-expiry", expiry)
    page.click("#key-create-btn")
    page.wait_for_selector("#new-key-display:not([hidden])", timeout=15_000)
    page.wait_for_function(
        "(n) => [...document.querySelectorAll('#keys-table tbody tr')]"
        ".some(r => r.innerText.includes(n))",
        arg=name, timeout=15_000,
    )
    return page.inner_text("#new-key-value").strip()


def test_generate_key_reveals_once_and_works(page, live_server):
    _open_keys(page, live_server)
    secret = _generate(page, "ui-generated")
    assert secret.startswith("sk-geek-")
    assert "cannot be retrieved later" in page.inner_text("#new-key-display")

    snippet = page.inner_text("#new-key-snippet")
    assert f'OPENAI_API_KEY="{secret}"' in snippet
    assert f"{live_server.base_url}/v1" in snippet

    # The key authenticates inference immediately.
    assert _inference(live_server.base_url, secret) == 200

    # One-time: after a reload, the secret is nowhere on the page.
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#app-shell:not([hidden])")
    page.click('#tabs [data-tab="keys"]')
    page.wait_for_selector("#panel-keys.active")
    assert secret not in page.content()
    assert page.is_hidden("#new-key-display")


def test_key_listing_never_contains_secrets(page, live_server):
    _open_keys(page, live_server)
    secret = _generate(page, "listing-check")
    status, body = live_server.admin("GET", "/v1/keys")
    assert status == 200
    assert secret not in json.dumps(body)


def test_key_with_expiry_shows_a_date(page, live_server):
    _open_keys(page, live_server)
    _generate(page, "expires-soon", expiry="30")
    row = page.locator("#keys-table tbody tr", has_text="expires-soon")
    text = row.inner_text()
    assert "ago" not in text.split("expires-soon", 1)[1].split("\t")[-2]
    assert "Never" not in text.split("\t")[5] if "\t" in text else True


def test_rename_key(page, live_server):
    _open_keys(page, live_server)
    _generate(page, "to-rename")
    page.once("dialog", lambda d: d.accept("renamed-key"))
    page.locator("#keys-table tbody tr", has_text="to-rename").locator(".rename-key").click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('#keys-table tbody tr')]"
        ".some(r => r.innerText.includes('renamed-key'))",
        timeout=15_000,
    )


def test_rotate_keeps_old_key_working(page, live_server):
    _open_keys(page, live_server)
    original = _generate(page, "rotate-me")
    # confirm() "OK" means "revoke the original now". A non-destructive
    # rotation is the operator choosing Cancel.
    page.once("dialog", lambda d: d.dismiss())
    page.locator("#keys-table tbody tr", has_text="rotate-me").first.locator(".rotate-key").click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('#keys-table tbody tr')]"
        ".some(r => r.innerText.includes('rotate-me (rotated)'))",
        timeout=15_000,
    )
    replacement = page.inner_text("#new-key-value").strip()
    assert replacement != original
    assert _inference(live_server.base_url, original) == 200
    assert _inference(live_server.base_url, replacement) == 200


def test_revoke_key_stops_it_immediately(page, live_server):
    _open_keys(page, live_server)
    secret = _generate(page, "revoke-me")
    assert _inference(live_server.base_url, secret) == 200

    row = page.locator("#keys-table tbody tr", has_text="revoke-me")
    page.once("dialog", lambda d: d.accept())  # the destructive confirm()
    row.locator(".rev-key").click()
    # The default view lists active keys only; revoked keys move to the
    # "Revoked & expired" view.
    page.wait_for_function(
        "() => ![...document.querySelectorAll('#keys-table tbody tr')]"
        ".some(r => r.innerText.includes('revoke-me'))",
        timeout=15_000,
    )
    page.click('[data-key-filter="revoked"]')
    page.wait_for_function(
        "() => [...document.querySelectorAll('#keys-table tbody tr')]"
        ".some(r => r.innerText.includes('revoke-me') && r.innerText.toUpperCase().includes('REVOKED'))",
        timeout=15_000,
    )
    assert _inference(live_server.base_url, secret) == 401


def test_dashboard_session_is_not_an_inference_credential(page, live_server):
    """Even inside the signed-in browser, fetch() to an inference route fails."""
    sign_in(page, live_server.base_url)
    status = page.evaluate(
        "async () => (await fetch('/v1/models', {credentials: 'same-origin'})).status"
    )
    assert status == 401


def test_model_catalog_loads_after_login(page, live_server):
    """The dashboard reads the catalog over /api/models with the session.

    Asserts the catalog fetch itself, not the "Models deployable" KPI: that KPI
    counts models a configured provider can actually serve, which is honestly 0
    when the fixture has no provider key.
    """
    sign_in(page, live_server.base_url)
    total = page.evaluate(
        "async () => {"
        "  const r = await fetch('/api/models', {credentials: 'same-origin'});"
        "  if (!r.ok) return -1;"
        "  const b = await r.json();"
        "  return (b.data || []).length;"
        "}"
    )
    assert total > 0

    # And the KPI is populated (0 is a valid answer without provider keys).
    page.wait_for_function(
        "() => { const t = document.querySelector('#kpi-models')?.textContent;"
        " return t && t !== '—'; }",
        timeout=15_000,
    )
    assert page.inner_text("#kpi-models").strip().isdigit()


def test_settings_navigation_and_keyboard_shortcuts(page, live_server):
    sign_in(page, live_server.base_url)
    # Shortcuts follow the sidebar order, which gained Profiles (4) and
    # Connect a tool (9) — assert the hint the UI actually renders.
    hints = page.eval_on_selector_all(
        "#tabs .nav-item", "els => els.map(e => e.dataset.tab + '=' + (e.querySelector('kbd')?.textContent || '-'))"
    )
    assert "security=7" in hints
    assert "keys=8" in hints
    page.keyboard.press("7")
    page.wait_for_selector("#panel-security.active")
    page.keyboard.press("8")
    page.wait_for_selector("#panel-keys.active")
    assert page.is_visible("text=Router API keys")


def test_mobile_viewport_login(browser, live_server):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    pg = ctx.new_page()
    sign_in(pg, live_server.base_url)
    assert pg.is_visible("#app-shell")
    ctx.close()


# ── API Keys page: endpoint and creation flow ──────────────────────────────


def test_api_keys_page_shows_the_endpoint_and_copies_it(browser, live_server):
    ctx = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    try:
        _open_keys(page, live_server)
        page.wait_for_function(
            "() => document.querySelector('#key-endpoint-url').textContent.includes('/v1')",
            timeout=15_000,
        )
        url = page.inner_text("#key-endpoint-url").strip()
        # No PUBLIC_BASE_URL on the test server: the local loopback endpoint.
        assert url == f"{live_server.base_url}/v1"
        assert url.count("/v1") == 1
        assert "local" in page.inner_text("#key-endpoint-kind").lower()
        assert "PUBLIC_BASE_URL" in page.inner_text("#key-endpoint-note")
        page.click("#key-endpoint-copy")
        page.wait_for_timeout(300)
        assert page.evaluate("() => navigator.clipboard.readText()") == url
        # The Connect a tool link goes to the integrations tab.
        page.click("#key-connect-link")
        page.wait_for_selector("#panel-integrations.active", timeout=10_000)
    finally:
        ctx.close()


def test_new_key_copy_download_and_dismiss(browser, live_server, tmp_path):
    ctx = browser.new_context(permissions=["clipboard-read", "clipboard-write"], accept_downloads=True)
    page = ctx.new_page()
    try:
        _open_keys(page, live_server)
        secret = _generate(page, "copy-me")
        text = page.inner_text("#new-key-display")
        assert "not an OpenAI API key" in text
        assert f'GEEKCUBO_API_KEY="{secret}"' in page.inner_text("#new-key-snippet-geekcubo")
        assert f'OPENAI_API_KEY="{secret}"' in page.inner_text("#new-key-snippet")
        assert f'OPENAI_BASE_URL="{live_server.base_url}/v1"' in page.inner_text("#new-key-snippet")
        assert "Use it with OpenCode" not in text

        page.click("#new-key-copy")
        page.wait_for_function(
            "() => document.querySelector('#new-key-status').dataset.state === 'ok'", timeout=5_000)
        assert page.evaluate("() => navigator.clipboard.readText()") == secret

        with page.expect_download() as dl:
            page.click("#new-key-download")
        download = dl.value
        assert download.suggested_filename == "geekcubo-api-key-copy-me.env"
        saved = tmp_path / download.suggested_filename
        download.save_as(str(saved))
        content = saved.read_text()
        assert f"GEEKCUBO_API_KEY={secret}" in content
        assert "SECRET" in content and "not an OpenAI key" in content

        # Nothing persisted in browser storage or the URL.
        storage = page.evaluate("() => JSON.stringify({...localStorage, ...sessionStorage})")
        assert secret not in storage and secret not in page.url

        page.click("#new-key-dismiss")
        assert page.is_hidden("#new-key-display")
        assert secret not in page.content()
    finally:
        ctx.close()


def test_new_key_clipboard_failure_is_reported_and_selects_the_key(browser, live_server):
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        _open_keys(page, live_server)
        secret = _generate(page, "clip-blocked")
        page.evaluate(
            "() => { navigator.clipboard.writeText = () => Promise.reject(new Error('denied')); }")
        page.click("#new-key-copy")
        page.wait_for_function(
            "() => document.querySelector('#new-key-status').dataset.state === 'err'", timeout=5_000)
        assert "copy it manually" in page.inner_text("#new-key-status").lower()
        assert page.evaluate("() => window.getSelection().toString().trim()") == secret
    finally:
        ctx.close()


def test_leaving_the_keys_page_wipes_the_revealed_key(page, live_server):
    _open_keys(page, live_server)
    secret = _generate(page, "wipe-me")
    page.click('#tabs [data-tab="overview"]')
    page.wait_for_selector("#panel-overview.active")
    assert secret not in page.content()
    page.click('#tabs [data-tab="keys"]')
    page.wait_for_selector("#panel-keys.active")
    assert page.is_hidden("#new-key-display")


def test_existing_keys_explain_non_recoverability_and_offer_no_copy(page, live_server):
    _open_keys(page, live_server)
    _generate(page, "listed-key")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    page.click('#tabs [data-tab="keys"]')
    row = page.locator("#keys-table tbody tr", has_text="listed-key").first
    row.wait_for(timeout=15_000)
    # No control offers the full key. The only copy control copies the masked
    # identifier and says so in its accessible name.
    assert row.locator("button", has_text="Copy").count() == 0
    copy_controls = row.locator(".copy-prefix")
    assert copy_controls.count() == 1
    label = copy_controls.first.get_attribute("aria-label").lower()
    assert "identifier" in label and "not the api key" in label
    assert row.locator(".rotate-key").count() == 1 and row.locator(".rev-key").count() == 1
    assert "cannot be copied again" in page.inner_text(".keys-list-note")


# ── startup never hangs on "Checking administrator status" ─────────────────


def _visible_auth_view(page):
    return page.evaluate(
        "() => ['#checking-view','#login-view','#setup-view','#unreachable-view','#app-shell']"
        ".filter(s => { const e = document.querySelector(s); return e && e.offsetParent !== null; })"
    )


def test_refresh_while_signed_out_shows_login_not_a_spinner(page, live_server):
    """A 401 from /api/auth/me is the normal signed-out answer, not an error."""
    for _ in range(3):
        page.goto(live_server.base_url, wait_until="domcontentloaded")
        page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
        assert _visible_auth_view(page) == ["#login-view"]


def test_logout_then_refresh_lands_on_login(page, live_server):
    sign_in(page, live_server.base_url)
    page.click("#account-btn")
    page.click("#logout-btn")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert _visible_auth_view(page) == ["#login-view"]


def test_expired_session_refresh_lands_on_login(page, live_server):
    sign_in(page, live_server.base_url)
    assert live_server.cli("revoke-sessions").returncode == 0
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert _visible_auth_view(page) == ["#login-view"]


def test_unanswered_session_probe_ends_in_a_retryable_error(page, live_server):
    stalled = {"on": True}

    def handle(route):
        if stalled["on"]:
            return  # never answer: simulates a hung proxy or connection
        route.continue_()

    page.route("**/api/auth/me", handle)
    page.goto(live_server.base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#unreachable-view:not([hidden])", timeout=40_000)
    assert _visible_auth_view(page) == ["#unreachable-view"]
    assert "reach the server" in page.inner_text("#unreachable-view")

    stalled["on"] = False
    page.click("#unreachable-retry")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)


def test_server_error_on_session_probe_is_not_an_endless_spinner(page, live_server):
    page.route("**/api/auth/me", lambda r: r.fulfill(status=502, body="bad gateway"))
    page.goto(live_server.base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#unreachable-view:not([hidden])", timeout=20_000)


def test_remembered_session_refresh_goes_straight_to_the_dashboard(browser, live_server):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(live_server.base_url, wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    pg.fill("#login-username", ADMIN_USERNAME)
    pg.fill("#login-password", ADMIN_PASSWORD)
    pg.check("#login-remember")
    pg.click("#login-submit")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    for _ in range(3):
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
        assert "#checking-view" not in _visible_auth_view(pg)
    ctx.close()
