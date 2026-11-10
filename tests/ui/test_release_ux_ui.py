"""Browser-level regression tests for the final release UX pass.

Covers the Analytics tabs (navigation, refresh, mobile layout, metric
labelling), API-key copy/rotate/archive, the compact login form, logout
without a redundant confirmation and the Providers empty-state wording.
Everything runs through real browser interactions against a disposable
server; no provider is called.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.ui.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, boot_server, stop_server

BASE_ORIGIN_PERMS = ["clipboard-read", "clipboard-write"]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("release-ux"))
    _seed_request_logs(server.db_url.split("///", 1)[1])
    try:
        yield server
    finally:
        stop_server(server)


def _seed_request_logs(db_path: str) -> None:
    """Two populations: 4 successes with a recorded attempt, 1 error without."""
    now = datetime.now(timezone.utc)
    rows = [
        ("auto", "demo/model-a", "demo", 200, None, 1, 120_000),
        ("auto", "demo/model-a", "demo", 200, None, 1, 80_000),
        ("demo/model-b", "demo/model-b", "demo", 200, None, 1, 0),
        ("auto", "demo/model-b", "demo", 200, None, 1, 40_000),
        ("demo/model-c", "demo/model-c", "unknown", 503, "upstream_error", None, 0),
    ]
    con = sqlite3.connect(db_path)
    for i, (req, model, prov, status, err, attempts, cost) in enumerate(rows):
        con.execute(
            """insert into requests_log (id, workspace_id, api_key_id, trace_id, model_requested,
            model_resolved, provider, routing_strategy, fallback_level, input_tokens, output_tokens,
            cost_microcents, latency_ms, status_code, error_type, is_streaming, routed_model,
            request_source, attempt_count, created_at, is_deleted)
            values (?,?,?,?,?,?,?,'balanced',0,?,?,?,?,?,?,0,?,'api',?,?,0)""",
            (str(uuid.uuid4()), "default", "dashboard", str(uuid.uuid4()), req, model, prov,
             100 if status < 400 else 0, 20 if status < 400 else 0, cost, 300 + i, status, err,
             model if req == "auto" else None, attempts,
             (now - timedelta(hours=i + 1)).strftime("%Y-%m-%d %H:%M:%S")),
        )
    con.commit()
    con.close()


def _ctx(browser, live_server, width=1440, height=900):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    ctx.grant_permissions(BASE_ORIGIN_PERMS, origin=live_server.base_url)
    return ctx


def _sign_in(pg, live_server, path="/"):
    pg.goto(f"{live_server.base_url}{path}", wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    pg.fill("#login-username", ADMIN_USERNAME)
    pg.fill("#login-password", ADMIN_PASSWORD)
    pg.click("#login-submit")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)


def _visible_pane(pg):
    return pg.evaluate(
        "() => [...document.querySelectorAll('.an-pane')].filter(p => !p.hidden).map(p => p.id)"
    )


# ─────────────────────────── analytics tabs ───────────────────────────

def test_analytics_has_four_tabs_and_switches_without_refetching(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server, "/#analytics")
    pg.wait_for_selector("#ra-kpis .ra-kpi", timeout=15_000)
    labels = [t.strip() for t in pg.locator("#analytics-tabs [role=tab]").all_inner_texts()]
    assert labels == ["Overview", "Routing", "Costs & Performance", "Request History"]
    assert _visible_pane(pg) == ["an-pane-overview"]
    kpis = pg.inner_text("#ra-kpis")
    for label in ("Total requests", "Recorded spending", "Auto-routed requests", "Errors"):
        assert label in kpis

    requests = []
    pg.on("request", lambda r: requests.append(r.url) if "/v1/analytics/" in r.url else None)
    pg.click("#an-tab-routing")
    assert _visible_pane(pg) == ["an-pane-routing"]
    assert pg.get_attribute("#an-tab-routing", "aria-selected") == "true"
    assert "Routing decisions" in pg.inner_text("#an-pane-routing")
    pg.click("#an-tab-history")
    assert _visible_pane(pg) == ["an-pane-history"]
    assert pg.locator("#recent-table tbody tr").count() == 5
    assert "trace" in pg.inner_text("#recent-table thead").lower()
    # Overview, Routing and History share data already loaded: no new fetch.
    assert requests == []

    # Costs loads its own (latency) data the first time only.
    pg.click("#an-tab-costs")
    pg.wait_for_function("() => document.querySelector('#latency-table tbody tr td') !== null")
    assert any("/v1/analytics/latency" in u for u in requests)
    n = len(requests)
    pg.click("#an-tab-overview")
    pg.click("#an-tab-costs")
    pg.wait_for_timeout(300)
    assert len(requests) == n
    assert "Spend by provider" in pg.inner_text("#an-pane-costs")
    ctx.close()


def test_analytics_tab_and_range_survive_a_refresh(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server, "/#analytics")
    pg.click("#an-tab-costs")
    pg.click('#window-seg [data-days="30"]')
    pg.wait_for_function("() => location.search.includes('days=30')")
    assert "atab=costs" in pg.url
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    assert _visible_pane(pg) == ["an-pane-costs"]
    assert pg.get_attribute('#window-seg [data-days="30"]', "class").split().count("active") == 1
    pg.wait_for_function("() => document.querySelector('#ra-summary').innerText.includes('30d')")
    # Switching tabs keeps the range.
    pg.click("#an-tab-routing")
    assert "days=30" in pg.url and "atab=routing" in pg.url
    # Leaving Analytics drops the analytics-only parameters.
    pg.click('#tabs [data-tab="overview"]')
    assert "atab=" not in pg.url and "days=" not in pg.url
    ctx.close()


def test_upstream_attempt_metric_is_labelled_as_a_different_population(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server, "/?atab=routing#analytics")
    pg.wait_for_selector("#ra-fallback .ra-fallback-stats", timeout=15_000)
    stats = pg.inner_text("#ra-fallback")
    assert "100%" in stats and "recorded upstream attempt" in stats
    assert "still succeeded" not in stats
    note = pg.inner_text("#ra-fallback-note")
    assert "4 of 5 requests" in note
    assert "not overall service reliability" in note
    assert "20%" in note  # the real overall error rate, unchanged
    ctx.close()


def test_analytics_mobile_layout_has_no_page_overflow(browser, live_server):
    ctx = _ctx(browser, live_server, 390, 844)
    pg = ctx.new_page()
    _sign_in(pg, live_server, "/#analytics")
    for tab in ("overview", "routing", "costs", "history"):
        pg.click(f"#an-tab-{tab}")
        pg.wait_for_timeout(200)
        overflow = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
        assert overflow <= 1, (tab, overflow)
    # All four tabs are on screen (2×2 grid), none clipped off the edge.
    for box in [b.bounding_box() for b in pg.locator("#analytics-tabs [role=tab]").all()]:
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    # The wide history table scrolls inside its own container.
    wrap = pg.evaluate(
        "() => { const w = document.querySelector('.an-history-wrap');"
        " return [w.scrollWidth, w.clientWidth, getComputedStyle(w).overflowX]; }"
    )
    assert wrap[0] > wrap[1] and wrap[2] == "auto"
    ctx.close()


# ─────────────────────────── API keys ───────────────────────────

def _open_keys(pg, live_server):
    _sign_in(pg, live_server, "/#keys")
    pg.wait_for_selector("#panel-keys.active")


def _create(pg, name):
    pg.fill("#key-name", name)
    pg.click("#key-create-btn")
    pg.wait_for_selector("#new-key-display:not([hidden])", timeout=15_000)
    return pg.inner_text("#new-key-value").strip()


def _hash_only(live_server, secret):
    db = live_server.db_url.split("///", 1)[1]
    con = sqlite3.connect(db)
    rows = con.execute("select * from api_keys").fetchall()
    con.close()
    assert not any(secret in repr(r) for r in rows), "plaintext key found in the database"


def test_create_key_copy_button_beside_the_secret(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _open_keys(pg, live_server)
    secret = _create(pg, "copy-me")
    assert secret.startswith("sk-geek-")
    # Copy control sits on the same row as the secret.
    key_box = pg.locator("#new-key-value").bounding_box()
    btn_box = pg.locator("#new-key-copy").bounding_box()
    assert abs((key_box["y"] + key_box["height"] / 2) - (btn_box["y"] + btn_box["height"] / 2)) < 30
    assert btn_box["x"] > key_box["x"]
    pg.click("#new-key-copy")
    pg.wait_for_function("() => document.querySelector('#new-key-status').dataset.state === 'ok'")
    assert pg.evaluate("navigator.clipboard.readText()") == secret
    assert pg.is_hidden("#new-key-rotate-note")
    _hash_only(live_server, secret)
    pg.click("#new-key-dismiss")
    assert secret not in pg.content()
    ctx.close()


def test_rotate_shows_new_key_with_copy_and_update_warning(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _open_keys(pg, live_server)
    original = _create(pg, "rotate-copy")
    pg.click("#new-key-dismiss")
    pg.once("dialog", lambda d: d.dismiss())  # keep the original working
    pg.locator("#keys-table tbody tr", has_text="rotate-copy").first.locator(".rotate-key").click()
    pg.wait_for_selector("#new-key-display:not([hidden])", timeout=15_000)
    rotated = pg.inner_text("#new-key-value").strip()
    assert rotated.startswith("sk-geek-") and rotated != original
    assert pg.is_visible("#new-key-rotate-note")
    assert "must be updated" in pg.inner_text("#new-key-rotate-note")
    pg.click("#new-key-copy")
    pg.wait_for_function("() => document.querySelector('#new-key-status').dataset.state === 'ok'")
    assert pg.evaluate("navigator.clipboard.readText()") == rotated
    _hash_only(live_server, rotated)
    _hash_only(live_server, original)
    ctx.close()


def test_revoked_keys_are_filtered_and_can_be_archived(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _open_keys(pg, live_server)
    _create(pg, "to-archive")
    pg.click("#new-key-dismiss")
    pg.once("dialog", lambda d: d.accept())
    pg.locator("#keys-table tbody tr", has_text="to-archive").first.locator(".rev-key").click()
    # Default view: active keys only — the revoked key disappears.
    pg.wait_for_function(
        "() => ![...document.querySelectorAll('#keys-table tbody tr')].some(r => r.innerText.includes('to-archive'))",
        timeout=15_000,
    )
    pg.click('[data-key-filter="revoked"]')
    row = pg.locator("#keys-table tbody tr", has_text="to-archive").first
    assert row.locator(".archive-key").count() == 1
    assert row.locator(".rotate-key").count() == 0
    pg.once("dialog", lambda d: d.accept())
    row.locator(".archive-key").click()
    pg.wait_for_function(
        "() => ![...document.querySelectorAll('#keys-table tbody tr')].some(r => r.innerText.includes('to-archive'))",
        timeout=15_000,
    )
    # Soft delete: the row and its revocation survive for audit.
    db = live_server.db_url.split("///", 1)[1]
    con = sqlite3.connect(db)
    r = con.execute("select is_deleted, revoked_at from api_keys where name='to-archive'").fetchone()
    con.close()
    assert r[0] == 1 and r[1] is not None
    ctx.close()


def test_archive_refuses_an_active_key(live_server):
    status, body = live_server.admin("POST", "/v1/keys", {"name": "still-active"})
    assert status == 201
    status, _ = live_server.admin("POST", f"/v1/keys/{body['id']}/archive")
    assert status == 409
    status, listing = live_server.admin("GET", "/v1/keys")
    assert any(k["id"] == body["id"] and k["is_active"] for k in listing["keys"])


# ─────────────────────────── login / logout ───────────────────────────

@pytest.mark.parametrize("width", [1440, 768])
def test_login_desktop_tagline_beside_brand_and_no_hint(browser, live_server, width):
    ctx = _ctx(browser, live_server, width, 900)
    pg = ctx.new_page()
    pg.goto(live_server.base_url, wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    pg.wait_for_timeout(500)  # card entrance animation
    logo = pg.locator(".auth-brand .brand-logo-img:visible").first.bounding_box()
    tag = pg.locator(".auth-tagline").bounding_box()
    assert tag is not None and pg.is_visible(".auth-tagline")
    assert tag["x"] >= logo["x"] + logo["width"]  # beside, not below
    assert tag["y"] < logo["y"] + logo["height"]
    card = pg.locator(".auth-card").bounding_box()
    assert tag["x"] + tag["width"] <= card["x"] + card["width"]
    assert card["width"] <= 421
    assert pg.inner_text("label[for='login-remember']").strip() == "Remember me for 14 days"
    # The explanation stays for screen readers only (sr-only: a 1px clip box).
    hint = pg.locator("#login-remember-hint").bounding_box()
    assert hint is None or (hint["width"] <= 1 and hint["height"] <= 1)
    assert pg.get_attribute("#login-remember", "aria-describedby") == "login-remember-hint"
    assert pg.is_checked("#login-remember") is False
    ctx.close()


def test_login_mobile_hides_tagline_keeps_logo(browser, live_server):
    ctx = _ctx(browser, live_server, 390, 844)
    pg = ctx.new_page()
    pg.goto(live_server.base_url, wait_until="domcontentloaded")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert not pg.is_visible(".auth-tagline")
    assert pg.locator(".auth-brand .brand-logo-img:visible").count() == 1
    assert pg.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 1
    ctx.close()


def test_logout_returns_to_login_without_signed_out_message(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server)
    pg.wait_for_timeout(300)
    pg.click("#account-btn")
    pg.wait_for_selector("#account-dropdown:not([hidden])")
    pg.click("#logout-btn")
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    pg.wait_for_timeout(400)
    assert pg.inner_text("#login-status").strip() == ""
    assert "signed out" not in pg.inner_text("body").lower()
    ctx.close()


def test_expired_session_message_is_still_shown(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server)
    assert live_server.cli("revoke-sessions").returncode == 0
    pg.click('#tabs [data-tab="keys"]')
    pg.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    assert "expired" in pg.inner_text("#login-status").lower()
    ctx.close()


# ─────────────────────────── providers ───────────────────────────

def test_provider_empty_state_names_standard_providers(browser, live_server):
    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _sign_in(pg, live_server, "/#providers")
    pg.wait_for_selector("#providers-empty", state="visible", timeout=15_000)
    text = pg.inner_text("#providers-empty")
    assert "No standard-provider keys configured" in text
    assert "Custom OpenAI-compatible providers" in text
    assert "No provider keys yet" not in pg.inner_text("body")
    ctx.close()



# ─────────────────────── copy a stored key from its row ───────────────────────

def _infer_status(base_url: str, key: str) -> int:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(f"{base_url}/v1/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_acceptance_copy_icon_copies_full_key_after_refresh(browser, live_server, width, height):
    """Create → dismiss → refresh → click the copy icon → use the clipboard value."""
    ctx = _ctx(browser, live_server, width, height)
    pg = ctx.new_page()
    _open_keys(pg, live_server)
    name = f"copy-later-{width}"
    created = _create(pg, name)
    pg.click("#new-key-dismiss")
    assert created not in pg.content()

    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    pg.click('#tabs [data-tab="keys"]')
    row = pg.locator("#keys-table tbody tr", has_text=name).first
    row.wait_for(timeout=15_000)
    assert created not in pg.content()
    # No settings panel, no extra buttons: just the icon next to the prefix.
    assert pg.locator("#key-recovery").count() == 0
    assert row.locator("button", has_text="Copy API key").count() == 0
    assert row.locator("button", has_text="Rotate to enable copying").count() == 0

    pg.evaluate("navigator.clipboard.writeText('sentinel')")
    row.locator(".copy-key").click()
    # wait_for_function does not await an async predicate (a pending Promise
    # is truthy), so poll the asynchronous clipboard explicitly.
    clip = None
    for _ in range(50):
        clip = pg.evaluate("navigator.clipboard.readText()")
        if clip != "sentinel":
            break
        pg.wait_for_timeout(200)

    assert clip == created, "the icon must copy the full usable key, not a masked identifier"
    assert clip.startswith("sk-geek-") and "...." not in clip and len(clip) == 40
    assert _infer_status(live_server.base_url, clip) == 200
    assert clip not in pg.content()

    con = sqlite3.connect(live_server.db_url.split("///", 1)[1])
    dump = "\n".join(con.iterdump())
    con.close()
    assert clip not in dump
    ctx.close()


def test_hash_only_key_icon_explains_instead_of_copying_the_prefix(browser, live_server):
    live_server.admin_login()  # an earlier test revoked every session
    status, legacy = live_server.admin("POST", "/v1/keys", {"name": "legacy-hash-only"})
    assert status == 201
    con = sqlite3.connect(live_server.db_url.split("///", 1)[1])
    con.execute("update api_keys set encrypted_secret=NULL where id=?", (legacy["id"],))
    con.commit()
    con.close()

    ctx = _ctx(browser, live_server)
    pg = ctx.new_page()
    _open_keys(pg, live_server)
    row = pg.locator("#keys-table tbody tr", has_text="legacy-hash-only").first
    row.wait_for(timeout=10_000)
    icon = row.locator(".copy-key")
    assert "is-unavailable" in icon.get_attribute("class")
    assert "Rotate it once" in icon.get_attribute("aria-label")
    pg.evaluate("navigator.clipboard.writeText('sentinel')")
    icon.click(force=True)  # aria-disabled; clicking explains instead of copying
    pg.wait_for_selector("text=Rotate it once to get a copyable key", timeout=5_000)
    assert pg.evaluate("navigator.clipboard.readText()") == "sentinel"
    # Nothing was rotated or revoked automatically.
    assert _infer_status(live_server.base_url, legacy["api_key"]) == 200
    ctx.close()
