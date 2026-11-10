"""Real browser controls, sources, mode isolation and responsive code blocks."""
import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("knowledge-ui"))
    yield server
    stop_server(server)


@pytest.mark.parametrize("width", [1440, 768, 390])
def test_modes_sources_and_code_fit(browser, live_server, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    sign_in(page, live_server.base_url, path="/#chat")
    page.wait_for_selector("#ch-mode-bar:not([hidden])")
    assert page.get_attribute("#ch-mode-normal", "aria-checked") == "true"
    page.click("#ch-mode-knowledge")
    assert page.get_attribute("#ch-mode-knowledge", "aria-checked") == "true"
    assert page.is_visible("#ch-attach")
    # Render saved provenance through the production renderer. Backend tests
    # independently prove these fields come from actual retrieval.
    page.evaluate(r"""() => {
      chState.messages = [{role:'assistant', mode:'knowledge',
        content:'Example:\n```bash\n' + 'command '.repeat(100) + '\n```',
        knowledge:{docs_version:'0.1.0', sources:[{id:'docs/routing.md#strategies',
          reference:'Routing → Strategies'}]}}];
      chRenderThread();
    }""")
    page.locator(".chat-knowledge-sources summary").click()
    assert "docs/routing.md#strategies" in page.inner_text("#ch-thread")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    bubble = page.locator(".chat-bubble").bounding_box()
    assert bubble["x"] + bubble["width"] <= width + 1
    page.click("#ch-mode-normal")
    assert page.get_attribute("#ch-mode-normal", "aria-checked") == "true"
    assert page.locator(".chat-knowledge-sources").count() == 1
    context.close()
