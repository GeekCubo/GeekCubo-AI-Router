"""Overview KPI cards: Routing savings replaced by Requests (7D); spend is
labelled as an estimate. Real server, real browser, light and dark."""

from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    from tests.ui.conftest import boot_server, stop_server

    server = boot_server(tmp_path_factory.mktemp("overview-kpis"))
    yield server
    stop_server(server)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_overview_shows_requests_and_estimated_spend(browser, live_server, theme, tmp_path):
    from tests.ui.conftest import sign_in

    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, live_server.base_url)
    page.evaluate(f"() => applyTheme('{theme}')")
    page.evaluate("() => setTab('overview')")
    page.wait_for_function("() => /\\d/.test(document.querySelector('#kpi-requests')?.textContent || '')",
                           timeout=15_000)
    labels = page.locator(".kpi-grid .kpi-label").all_inner_texts()
    assert [lb.lower() for lb in labels] == [
        "estimated spend (7d)", "requests (7d)", "p50 latency", "models deployable"]
    # No savings claim anywhere on the card grid.
    grid = page.locator(".kpi-grid").inner_text().lower()
    assert "savings" not in grid and "gpt-4o" not in grid
    assert page.locator("#kpi-saved").count() == 0
    # The request count moved out of the spend subtitle into its own card.
    assert "requests" not in page.inner_text("#kpi-spend-sub").lower()
    assert page.inner_text("#kpi-requests").strip() == "0"
    page.locator(".kpi-grid").screenshot(path=str(tmp_path / f"kpis-{theme}.png"))
    assert errors == []
    ctx.close()
