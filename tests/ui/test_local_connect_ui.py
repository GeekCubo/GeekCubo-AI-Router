"""Browser-level (Playwright) coverage for the Local AI Connect dashboard.

The REST surface and the connector are covered by backend tests. What those
cannot prove is that the dashboard actually wires the panel, settings form,
enrollment list, machine cards and the eight-step wizard to the API. These
tests drive the real page in a real browser against a real server process, with
a fake connector speaking the wire protocol over a real WebSocket so the
machine cards render live data.

Skips cleanly when Playwright or a Chromium build is unavailable.
"""

from __future__ import annotations

import json
import threading

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

pytest.importorskip("playwright.sync_api")

MACHINE_MODELS = [
    {
        "model_key": "llama3.1:8b",
        "display_name": "Llama 3.1 8B",
        "adapter": "ollama",
        "family": "llama",
        "parameter_count": "8B",
        "quantization": "Q4_K_M",
        "context_length": 131072,
        "supports_tools": True,
        "supports_vision": False,
        "supports_json_mode": True,
        "tokens_per_second": 42.5,
    },
    {
        "model_key": "qwen2.5-vl:7b",
        "display_name": "Qwen2.5 VL 7B",
        "adapter": "ollama",
        "context_length": 32768,
        "supports_vision": True,
    },
]

class FakeConnector:
    """A real WebSocket client that speaks the connector wire protocol.

    Runs its receive loop on a daemon thread so the machine stays online for
    the duration of a test and answers server-initiated frames the way the
    real connector does.
    """

    def __init__(self, base_url: str, enrollment_code: str, *,
                 display_name: str = "Studio box", hostname: str = "studio",
                 platform: str = "Linux", adapters: list[str] | None = None) -> None:
        from websockets.sync.client import connect

        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self._connect = connect
        self._ws = None
        self.hello_ok: dict = {}
        self.machine_id: str = ""
        self.credential: str = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        ws = connect(
            f"{self.ws_url}/api/local-connect/agent",
            additional_headers=None,
            proxy=None,
            open_timeout=15,
            max_size=None,
        )
        self._ws = ws
        ws.send(json.dumps({
            "type": "hello",
            "display_name": display_name,
            "hostname": hostname,
            "platform": platform,
            "agent_version": "0.1.0",
            "adapters": adapters or ["ollama"],
            "enrollment_code": enrollment_code,
        }))
        first = json.loads(ws.recv(timeout=15))
        assert first.get("type") == "hello_ok", first
        self.hello_ok = first
        self.machine_id = first["machine_id"]
        self.credential = first.get("credential") or ""
        ws.send(json.dumps({"type": "models", "models": MACHINE_MODELS,
                            "adapters": adapters or ["ollama"]}))

    def start(self) -> "FakeConnector":
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _loop(self) -> None:
        assert self._ws is not None
        try:
            while not self._stop.is_set():
                try:
                    raw = self._ws.recv(timeout=1)
                except TimeoutError:
                    continue
                except Exception:
                    return
                try:
                    frame = json.loads(raw)
                except ValueError:
                    continue
                kind = frame.get("type")
                if kind == "ping":
                    self._ws.send(json.dumps({"type": "pong",
                                              "request_id": frame.get("request_id")}))
                elif kind == "discover":
                    self._ws.send(json.dumps({
                        "type": "models",
                        "models": MACHINE_MODELS,
                        "adapters": ["ollama"],
                        "request_id": frame.get("request_id"),
                    }))
                elif kind == "chat":
                    rid = frame.get("request_id")
                    self._ws.send(json.dumps({"type": "chunk", "request_id": rid,
                                              "delta": "hi"}))
                    self._ws.send(json.dumps({"type": "done", "request_id": rid}))
        finally:
            try:
                self._ws.close()
            except Exception:
                pass

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        try:
            self._ws.close()
        except Exception:
            pass

@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(
        tmp_path_factory.mktemp("local-connect-ui"),
        extra_env={"LOCAL_CONNECT_PUBLIC_URL": "https://ai.example.test"},
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
    p.close()
    ctx.close()

@pytest.fixture
def connector(live_server):
    created: list[FakeConnector] = []

    def _make() -> FakeConnector:
        status, body = live_server.admin("POST", "/api/local-connect/enrollments", {})
        assert status == 201, body
        c = FakeConnector(live_server.base_url, body["code"]).start()
        created.append(c)
        return c

    yield _make
    for c in created:
        c.close()

def _open_local(page, server) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, server.base_url)
    page.click('[data-tab="local"]')
    page.wait_for_selector("#panel-local.active", timeout=10_000)
    page.wait_for_selector("#local-kpis .local-kpi", timeout=15_000)
    return errors

def _refresh(page) -> None:
    page.click("#local-refresh")
    page.wait_for_function(
        "() => state.local.overview && state.local.overview.counts", timeout=15_000
    )

def _boxes(page, selectors):
    return page.evaluate(
        """(sels) => sels.map((s) => {
            const el = document.querySelector(s);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {sel: s, x: r.x, y: r.y, w: r.width, h: r.height,
                    right: r.right, bottom: r.bottom};
        })""",
        selectors,
    )

def _no_page_overflow(page) -> int:
    return page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )

def test_panel_renders_kpis_and_install_command(page, live_server):
    errors = _open_local(page, live_server)
    assert page.evaluate("() => document.querySelectorAll('#local-kpis .local-kpi').length") == 4
    assert page.inner_text("#local-install-command").startswith("python -m geekcubo_connector enroll")
    assert "https://ai.example.test" in page.inner_text("#local-install-command")
    assert page.evaluate("() => document.querySelector('#local-feature-off').hidden") is True
    assert page.evaluate("() => document.querySelector('#local-url-missing').hidden") is True
    assert errors == []

def test_settings_toggle_persists(page, live_server):
    _open_local(page, live_server)
    page.uncheck("#local-set-auto")
    page.click('#local-settings-form button[type="submit"]')
    page.wait_for_function(
        "() => document.querySelector('#local-settings-status').textContent.trim().length > 0",
        timeout=10_000,
    )
    status, body = live_server.admin("GET", "/api/local-connect/settings")
    assert status == 200 and body["eligible_for_auto"] is False
    _refresh(page)
    assert page.is_checked("#local-set-auto") is False
    page.check("#local-set-auto")
    page.click('#local-settings-form button[type="submit"]')
    page.wait_for_function(
        "() => state.local.overview.settings.eligible_for_auto === true", timeout=10_000
    )

def test_enrollment_created_in_wizard_appears_in_list(page, live_server):
    _open_local(page, live_server)
    page.click("#local-wizard-open")
    page.wait_for_selector("#local-wizard[open]", timeout=10_000)
    assert page.evaluate("() => state.local.wizardStep") == 1
    page.fill("#local-wizard-name", "Workshop box")
    page.click("#local-wizard-next")
    page.wait_for_function("() => !!state.local.wizardCode", timeout=10_000)
    code = page.evaluate("() => state.local.wizardCode.code")
    assert code.startswith("lcenr-")
    page.click("#local-wizard-next")
    page.wait_for_function("() => state.local.wizardStep === 2", timeout=10_000)
    body = page.inner_text("#local-step-body")
    assert code in body
    assert "python -m geekcubo_connector enroll" in body
    page.click('[data-local-wizard-close] >> nth=0')
    page.wait_for_selector("#local-wizard", state="hidden", timeout=10_000)
    _refresh(page)
    assert page.evaluate("() => state.local.enrollments.length") >= 1
    assert code[-4:] in page.inner_text("#local-enrollments")

def test_wizard_steps_are_numbered_and_linear(page, live_server):
    _open_local(page, live_server)
    page.click("#local-wizard-open")
    page.wait_for_selector("#local-wizard[open]", timeout=10_000)
    assert page.evaluate("() => document.querySelectorAll('#local-steps .local-step').length") == 8
    assert page.evaluate(
        "() => document.querySelectorAll('#local-steps .local-step.active').length"
    ) == 1
    step = page.evaluate("() => state.local.wizardStep")
    if step > 0:
        page.click("#local-wizard-back")
        page.wait_for_function(f"() => state.local.wizardStep === {step - 1}", timeout=10_000)
    assert page.evaluate("() => document.querySelector('#local-wizard-back').hidden") is (step - 1 == 0)
    page.click('[data-local-wizard-close] >> nth=0')

def test_machine_card_renders_models_and_toggle(page, live_server, connector):
    c = connector()
    _open_local(page, live_server)
    page.wait_for_selector(f'.local-machine[data-machine-id="{c.machine_id}"]', timeout=20_000)
    card = page.locator(f'.local-machine[data-machine-id="{c.machine_id}"]')
    assert "Studio box" in card.inner_text()
    rows = card.locator("tbody tr")
    assert rows.count() == 2
    assert "llama3.1:8b" in card.inner_text()
    first_toggle = card.locator("input[data-local-toggle-model]").first
    assert first_toggle.is_checked()
    first_toggle.uncheck()
    page.wait_for_function(
        """(mid) => {
            const ov = state.local.overview;
            const m = (ov.machines || []).find((x) => x.id === mid);
            const model = (m.models || []).find((x) => x.model_key === 'llama3.1:8b');
            return model && model.is_enabled === false;
        }""",
        arg=c.machine_id,
        timeout=20_000,
    )

def test_pending_machine_can_be_approved_from_card(page, live_server, connector):
    c = connector()
    _open_local(page, live_server)
    page.wait_for_selector(f'.local-machine[data-machine-id="{c.machine_id}"]', timeout=20_000)
    card = page.locator(f'.local-machine[data-machine-id="{c.machine_id}"]')
    page.on("dialog", lambda d: d.accept())
    card.locator('[data-local-action="approve"]').click()
    page.wait_for_function(
        """(mid) => {
            const m = (state.local.overview.machines || []).find((x) => x.id === mid);
            return m && m.status === 'approved';
        }""",
        arg=c.machine_id,
        timeout=20_000,
    )
    assert "approved" in card.inner_text().lower() or card.locator(".pill.ok").count() >= 1

def test_revoke_uses_confirmation(page, live_server, connector):
    c = connector()
    status, _ = live_server.admin("POST", f"/api/local-connect/machines/{c.machine_id}/approve")
    assert status == 200
    _open_local(page, live_server)
    page.wait_for_selector(f'.local-machine[data-machine-id="{c.machine_id}"]', timeout=20_000)
    page.on("dialog", lambda d: d.accept())
    page.click(f'.local-machine[data-machine-id="{c.machine_id}"] [data-local-action="revoke"]')
    page.wait_for_function(
        """(mid) => {
            const m = (state.local.overview.machines || []).find((x) => x.id === mid);
            return m && m.status === 'revoked';
        }""",
        arg=c.machine_id,
        timeout=20_000,
    )
    status, body = live_server.admin("GET", "/api/local-connect/overview")
    machine = next(m for m in body["machines"] if m["id"] == c.machine_id)
    assert machine["status"] == "revoked"

def test_service_file_switches_between_platforms(page, live_server):
    _open_local(page, live_server)
    page.click("#local-install-card summary")
    page.wait_for_selector("#local-service-file", state="visible", timeout=10_000)
    page.click('#local-service-seg [data-local-service="systemd"]')
    assert "[Unit]" in page.inner_text("#local-service-file")
    page.click('#local-service-seg [data-local-service="launchd"]')
    assert "com.geekcubo.connector" in page.inner_text("#local-service-file")
    page.click('#local-service-seg [data-local-service="windows"]')
    assert "New-Service" in page.inner_text("#local-service-file")
    assert page.evaluate(
        "() => document.querySelector('#local-service-seg .seg-btn.active').dataset.localService"
    ) == "windows"

def test_delete_enrollment_from_list(page, live_server):
    status, body = live_server.admin("POST", "/api/local-connect/enrollments",
                                     {"display_name": "throwaway"})
    assert status == 201
    enrollment_id = body["id"]
    _open_local(page, live_server)
    page.wait_for_function(
        "(eid) => state.local.enrollments.some((x) => x.id === eid)",
        arg=enrollment_id,
        timeout=15_000,
    )
    page.on("dialog", lambda d: d.accept())
    page.click(f'[data-local-del-enrollment="{enrollment_id}"]')
    page.wait_for_function(
        "(eid) => !state.local.enrollments.some((x) => x.id === eid)",
        arg=enrollment_id,
        timeout=15_000,
    )

@pytest.mark.parametrize("width,height", [(1440, 900), (768, 1024), (390, 844)])
def test_panel_has_no_horizontal_overflow(page, live_server, width, height):
    page.set_viewport_size({"width": width, "height": height})
    _open_local(page, live_server)
    boxes = _boxes(page, [
        "#local-hero",
        "#local-settings-card",
        "#local-machines-card",
        "#local-enrollments-card",
        "#local-install-card",
    ])
    assert all(b and b["w"] > 0 for b in boxes), boxes
    for b in boxes:
        assert b["right"] <= width + 1, f"{b['sel']} clipped at {width}px: {b}"
    assert _no_page_overflow(page) <= 2, f"horizontal overflow at {width}px"

def test_wizard_fits_narrow_viewport(page, live_server):
    page.set_viewport_size({"width": 390, "height": 844})
    _open_local(page, live_server)
    page.click("#local-wizard-open")
    page.wait_for_selector("#local-wizard[open]", timeout=10_000)
    box = page.locator("#local-wizard").bounding_box()
    assert box is not None and box["width"] <= 390
    assert _no_page_overflow(page) <= 2
    page.click('[data-local-wizard-close] >> nth=0')

def test_feature_disabled_shows_callout_and_disables_settings(page, tmp_path_factory):
    server = boot_server(
        tmp_path_factory.mktemp("local-connect-off"),
        extra_env={"LOCAL_CONNECT_ENABLED": "false"},
    )
    try:
        sign_in(page, server.base_url)
        page.click('[data-tab="local"]')
        page.wait_for_selector("#panel-local.active", timeout=10_000)
        page.wait_for_selector("#local-feature-off:not([hidden])", timeout=15_000)
        assert page.evaluate("() => document.querySelector('#local-set-enabled').disabled") is True
        assert page.evaluate("() => state.local.overview.feature_enabled") is False
    finally:
        stop_server(server)
