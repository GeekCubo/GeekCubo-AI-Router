"""Browser coverage for the Auto-routing acceptance fixes.

Drives the real Routing page and the real Providers → Manage models table:
  * the "Allow reference estimates" checkbox actually persists;
  * pool entries that are no longer registered are marked, can be removed,
    and no longer block saving the policy;
  * the concise "How Auto routing works" help is present and accurate;
  * the registered-model table filters by catalog-match status with
    keyboard-operable, labelled controls.

Skips cleanly when Playwright or a Chromium build is unavailable.
"""

from __future__ import annotations

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server
from tests.ui.test_custom_provider_ui import _MockUpstream

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def upstream():
    u = _MockUpstream()
    u.start()
    yield u
    u.stop()


@pytest.fixture(scope="module")
def live_server(tmp_path_factory, upstream):
    server = boot_server(
        tmp_path_factory.mktemp("routing-acceptance-ui"),
        extra_env={"CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS": f"127.0.0.1:{upstream.port}"},
    )
    try:
        yield server
    finally:
        stop_server(server)


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    ctx.close()


def _provider_with_models(live_server, upstream, models):
    status, prov = live_server.admin("POST", "/v1/custom-providers", {
        "display_name": "Apixo", "base_url": upstream.base_url,
        "api_key": "sk-test-abcdefghijkl", "eligible_for_auto": True,
    })
    assert status == 201, prov
    status, body = live_server.admin("PUT", f"/v1/custom-providers/{prov['id']}/models", models)
    assert status == 200, body
    return prov


def _cleanup(live_server):
    _, body = live_server.admin("GET", "/v1/custom-providers")
    for p in body.get("providers", []):
        live_server.admin("DELETE", f"/v1/custom-providers/{p['id']}")
    live_server.admin("PUT", "/v1/routing", {"strategy": "balanced", "policy": {}})


def _open_routing(page, live_server):
    sign_in(page, live_server.base_url, path="/#routing")
    page.wait_for_selector("#panel-routing.active", timeout=15_000)
    page.wait_for_function("() => !!state.routing?.policy", timeout=15_000)


def test_reference_estimate_checkbox_persists(page, live_server):
    try:
        _open_routing(page, live_server)
        assert page.is_checked("#pol-allow-estimates") is False
        page.check("#pol-allow-estimates")
        page.click("#pol-save")
        page.wait_for_function(
            "() => /saved/i.test(document.querySelector('#pol-status').textContent)", timeout=10_000
        )
        _, body = live_server.admin("GET", "/v1/routing")
        assert body["policy"]["pricing"]["allow_reference_estimates"] is True
        assert "allow_estimates" not in body["policy"]

        # Survives a reload: the form reads the persisted field back.
        page.reload()
        page.wait_for_selector("#panel-routing.active", timeout=15_000)
        page.wait_for_function("() => !!state.routing?.policy", timeout=15_000)
        assert page.is_checked("#pol-allow-estimates") is True
    finally:
        _cleanup(live_server)


def test_stale_pool_chip_is_marked_removable_and_does_not_block_saving(page, live_server, upstream):
    try:
        _provider_with_models(live_server, upstream, [
            {"model_id": "live", "input_cost_per_million": 1, "output_cost_per_million": 1},
        ])
        status, _ = live_server.admin("PUT", "/v1/routing", {"policy": {"pools": {"mundane": ["apixo/live"]}}})
        assert status == 200
        # Owner's real state: the policy still names models of a provider
        # that no longer exists under that slug.
        import json
        import sqlite3

        con = sqlite3.connect(live_server.db_url.split("///", 1)[1], timeout=20)
        try:
            row = con.execute("SELECT policy FROM routing_config").fetchone()
            policy = json.loads(row[0])
            policy["pools"]["mundane"].append("gone/old-model")
            con.execute("UPDATE routing_config SET policy = ?", (json.dumps(policy),))
            con.commit()
        finally:
            con.close()
        live_server.admin("PUT", "/v1/routing", {"strategy": "balanced"})  # drop router cache

        _open_routing(page, live_server)
        stale = page.locator('[data-pool-chips="mundane"] .model-chip.is-stale')
        stale.wait_for(timeout=10_000)
        assert "gone/old-model" in stale.inner_text()
        assert "not registered" in stale.inner_text().lower()
        assert page.locator('[data-pool-chips="mundane"] .model-chip:not(.is-stale)').count() == 1
        warnings = page.inner_text("#routing-warnings")
        assert "no longer registered" in warnings

        # Saving an unrelated setting works despite the stale entry.
        page.fill("#pol-fallback-max", "4")
        page.click("#pol-save")
        page.wait_for_function(
            "() => /saved/i.test(document.querySelector('#pol-status').textContent)", timeout=10_000
        )

        # Removing the stale chip (keyboard-reachable × button) clears it.
        remove = stale.locator(".chip-x")
        assert "ignored by routing" in remove.get_attribute("aria-label")
        remove.focus()
        page.keyboard.press("Enter")
        page.wait_for_function(
            "() => !document.querySelector('[data-pool-chips=\"mundane\"] .model-chip.is-stale')",
            timeout=10_000,
        )
        _, body = live_server.admin("GET", "/v1/routing")
        assert body["policy"]["pools"]["mundane"] == ["apixo/live"]
        assert body["policy"]["fallback"]["max_attempts"] == 4
        assert body["stale_models"] == []
    finally:
        _cleanup(live_server)


def test_auto_routing_help_explains_the_real_controls(page, live_server):
    _open_routing(page, live_server)
    help_box = page.locator("#routing-howto")
    assert help_box.get_attribute("open") is None  # collapsed: no clutter
    help_box.locator("summary").click()
    text = help_box.inner_text()
    for phrase in ('model="auto"', "Auto (router picks)", "Exclude from Auto",
                   "confirmed", "Test a routing decision", "Stop", "web search"):
        assert phrase in text, phrase
    # The strings it names really exist in the UI.
    assert page.evaluate("() => t('chat.model_auto')") == "Auto (router picks)"


def test_model_table_filters_by_catalog_status(page, live_server, upstream):
    """Two registered models with different identity states; the status
    pills filter the table and are real, labelled buttons."""
    import json
    import sqlite3
    import uuid
    from datetime import datetime, timezone

    con = sqlite3.connect(live_server.db_url.split("///", 1)[1], timeout=20)
    try:
        con.execute('DELETE FROM metadata_sources WHERE "key" = ?', ("litellm",))
        entry = {"price_state": "priced", "input_per_million": 1.0, "output_per_million": 2.0,
                 "cache_read_per_million": None, "cache_write_per_million": None,
                 "context": 8000, "tools": True, "vision": False, "json_mode": None, "json_schema": None}
        con.execute(
            'INSERT INTO metadata_sources (workspace_id, "key", name, kind, is_builtin, is_enabled, '
            "priority, sync_interval_hours, cache, entry_count, last_success_at, id, is_deleted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("default", "litellm", "Test", "litellm", 0, 1, 10, 24,
             json.dumps({"v1/shared": entry, "v2/shared": entry}), 2,
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"), str(uuid.uuid4()), 0),
        )
        con.commit()
    finally:
        con.close()
    try:
        prov = _provider_with_models(live_server, upstream, [
            {"model_id": "shared"}, {"model_id": "custom-only-abliterated"},
        ])
        sign_in(page, live_server.base_url, path="/providers")
        page.wait_for_selector("#panel-providers.active", timeout=15_000)
        row = page.locator(f'.cp-row[data-cp-id="{prov["id"]}"]')
        row.locator("[data-cp-manage]").click()
        row.locator("tr[data-model-row]").first.wait_for(timeout=10_000)
        assert row.locator("tr[data-model-row]").count() == 2

        badges = {
            r.locator("code").first.inner_text(): r.locator(".match-badge").get_attribute("data-match")
            for r in row.locator("tr[data-model-row]").all()
        }
        assert badges == {"apixo/shared": "ambiguous", "apixo/custom-only-abliterated": "unmatched"}
        # The badge's explanation is part of its accessible name.
        label = row.locator('tr[data-model-row] .match-badge[data-match="ambiguous"]').get_attribute("aria-label")
        assert "Ambiguous" in label and "2 catalog entries" in label
        # Ambiguous: no metadata inherited, picker offered.
        amb = row.locator("tr[data-model-row]").filter(has_text="apixo/shared")
        assert amb.locator("[data-cp-catalog]").count() == 1
        assert "Pick 1 of 2" in amb.locator(".match-badge").get_attribute("aria-label")

        btn = row.locator('.cp-match-filter [data-match-filter="unmatched"]')
        assert btn.get_attribute("aria-pressed") == "false"
        btn.focus()
        page.keyboard.press("Enter")
        page.wait_for_function(
            f"() => document.querySelectorAll('.cp-row[data-cp-id=\"{prov['id']}\"] tr[data-model-row]').length === 1",
            timeout=5_000,
        )
        assert "custom-only-abliterated" in row.locator("tr[data-model-row]").inner_text()
        assert row.locator('.cp-match-filter [data-match-filter="unmatched"]').get_attribute("aria-pressed") == "true"

        row.locator('.cp-match-filter button:has-text("Show all")').click()
        page.wait_for_function(
            f"() => document.querySelectorAll('.cp-row[data-cp-id=\"{prov['id']}\"] tr[data-model-row]').length === 2",
            timeout=5_000,
        )
    finally:
        con = sqlite3.connect(live_server.db_url.split("///", 1)[1], timeout=20)
        try:
            con.execute('DELETE FROM metadata_sources WHERE "key" = ?', ("litellm",))
            con.commit()
        finally:
            con.close()
        _cleanup(live_server)
