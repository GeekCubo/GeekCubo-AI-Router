"""Ask GeekCubo in the real Chat UI: layout, scrolling, modes and sources.

A local OpenAI-compatible upstream (a custom provider on 127.0.0.1) streams
slowly, so messages go through the real send path, the real router and SSE.
It records every request, which makes mode isolation observable: a Normal
Chat request must never carry the documentation block.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

MODEL_ID = "ui-stream"
LONG_REPLY = (
    "\n\n".join(f"Paragraph {i}: " + "words " * 30 for i in range(24))
    + "\n\n| Strategy | Ranks by |\n|---|---|\n| Balanced | quality + price |\n| Cheapest | price |"
    + "\n\n```bash\ndocker compose up -d --no-deps api\n```\n\nEND-OF-REPLY"
)


class _Upstream:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _json(self, code, payload):
                raw = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                self._json(200, {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                parent.requests.append(body)
                last = next((m["content"] for m in reversed(body.get("messages", []))
                             if m.get("role") == "user" and isinstance(m.get("content"), str)
                             and "<geekcubo_documentation>" not in m["content"]), "")
                text = LONG_REPLY if "LONG" in last else f"Short reply to: {last[:40]}"
                if not body.get("stream"):
                    self._json(200, {"id": "x", "object": "chat.completion", "model": MODEL_ID,
                                     "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                                  "finish_reason": "stop"}],
                                     "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for i in range(0, len(text), 40):
                    chunk = {"id": "x", "object": "chat.completion.chunk", "model": MODEL_ID,
                             "choices": [{"index": 0, "delta": {"content": text[i:i + 40]}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(0.02)
                end = {"id": "x", "object": "chat.completion.chunk", "model": MODEL_ID,
                       "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}
                self.wfile.write(f"data: {json.dumps(end)}\n\ndata: [DONE]\n\n".encode())
                self.wfile.flush()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="module")
def upstream():
    u = _Upstream()
    yield u
    u.stop()


@pytest.fixture(scope="module")
def live_server(tmp_path_factory, upstream):
    server = boot_server(
        tmp_path_factory.mktemp("knowledge-ui"),
        extra_env={"CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS": f"127.0.0.1:{upstream.port}"},
    )
    status, prov = server.admin("POST", "/v1/custom-providers", {
        "display_name": "UI Stream", "base_url": f"http://127.0.0.1:{upstream.port}/v1",
        "api_key": "sk-ui-stream-not-secret"})
    assert status == 201, prov
    status, _ = server.admin("POST", f"/v1/custom-providers/{prov['id']}/models",
                             [{"model_id": MODEL_ID, "context_length": 32768}])
    assert status == 200
    server.model = f"{prov['slug']}/{MODEL_ID}"
    yield server
    stop_server(server)


def _open_chat(browser, server, width, height, theme="light"):
    context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme)
    page = context.new_page()
    sign_in(page, server.base_url, path="/#chat")
    page.wait_for_selector("#ch-mode-bar:not([hidden])")
    # Pick the model first: a new conversation stores the selected model,
    # and reopening it restores that model.
    page.wait_for_function("document.querySelector('#ch-model').gcSelect")
    page.evaluate(f"document.querySelector('#ch-model').gcSelect.setValue({json.dumps(server.model)})")
    page.evaluate("chNewChat()")
    page.wait_for_function("!!chState.convo")
    return context, page


def _send(page, text):
    n = page.evaluate("chState.messages.length")
    page.fill("#ch-input", text)
    page.press("#ch-input", "Enter")
    # Done when the post-stream refresh has loaded both persisted rows.
    page.wait_for_function(
        f"!chState.streaming && chState.messages.length >= {n + 2}"
        " && chState.messages.at(-1)?.role === 'assistant' && !!chState.messages.at(-1)?.id",
        timeout=30_000)


_GEOMETRY = """() => {
  const t = document.querySelector('#ch-thread'), tr = t.getBoundingClientRect();
  const last = t.lastElementChild.getBoundingClientRect();
  const bar = document.querySelector('#ch-mode-bar').getBoundingClientRect();
  const comp = document.querySelector('.chat-composer').getBoundingClientRect();
  const hint = document.querySelector('.chat-hint').getBoundingClientRect();
  return { gap: t.scrollHeight - t.scrollTop - t.clientHeight, lastBottom: last.bottom, threadBottom: tr.bottom,
           barTop: bar.top, composerTop: comp.top, hintBottom: hint.bottom, vh: innerHeight,
           pageOverflowX: document.documentElement.scrollWidth - innerWidth };
}"""


def _assert_unobstructed(g):
    assert g["gap"] <= 2, f"latest reply not scrolled to the end: {g}"
    assert g["lastBottom"] <= g["threadBottom"] + 1, f"latest reply hidden behind the composer: {g}"
    assert g["barTop"] >= g["threadBottom"] - 1, f"mode bar overlaps the thread: {g}"
    assert g["composerTop"] >= g["barTop"], g
    assert g["hintBottom"] <= g["vh"] + 1, f"composer pushed off screen: {g}"
    assert g["pageOverflowX"] <= 1, g


@pytest.mark.parametrize("width,height", [(1440, 900), (1440, 600), (768, 1024), (768, 600), (390, 844), (390, 600)])
def test_long_streamed_reply_stays_fully_visible_above_the_composer(browser, live_server, width, height):
    context, page = _open_chat(browser, live_server, width, height)
    page.click("#ch-mode-knowledge")
    page.fill("#ch-input", "LONG What does the Balanced routing strategy do?")
    page.press("#ch-input", "Enter")
    # While streaming: the newest text is followed, never under the composer.
    page.wait_for_function("document.querySelector('#ch-thread').innerText.includes('Paragraph 12')", timeout=30_000)
    _assert_unobstructed(page.evaluate(_GEOMETRY))
    page.wait_for_function("!chState.streaming && document.querySelector('#ch-thread').innerText.includes('END-OF-REPLY')",
                           timeout=30_000)
    page.wait_for_function("chState.messages.at(-1)?.role === 'assistant' && !!chState.messages.at(-1)?.id")
    g = page.evaluate(_GEOMETRY)
    _assert_unobstructed(g)
    # A table renders as a table, scrolled inside the bubble if needed.
    assert page.locator(".chat-msg-assistant:last-child table.chat-table").count() == 1
    # Expanding the newest sources keeps them on screen.
    page.locator(".chat-msg-assistant:last-child .chat-knowledge-sources summary").click()
    page.wait_for_timeout(100)
    sources = page.locator(".chat-msg-assistant:last-child .chat-knowledge-sources").bounding_box()
    thread = page.locator("#ch-thread").bounding_box()
    if sources["height"] <= thread["height"]:
        assert sources["y"] >= thread["y"] - 1 and sources["y"] + sources["height"] <= thread["y"] + thread["height"] + 1
    else:  # taller than the visible thread: opens at its start, rest scrolls
        assert thread["y"] - 1 <= sources["y"] <= thread["y"] + 40
    # A multiline draft grows the composer; the thread shrinks, the reply stays pinned.
    page.evaluate("document.querySelector('#ch-thread').scrollTop = 1e9")
    page.fill("#ch-input", "\n".join(f"line {i}" for i in range(12)))
    page.dispatch_event("#ch-input", "input")
    page.wait_for_timeout(100)
    _assert_unobstructed(page.evaluate(_GEOMETRY))
    context.close()


def test_reader_scrolled_up_is_not_yanked_to_the_bottom(browser, live_server):
    context, page = _open_chat(browser, live_server, 1440, 700)
    page.fill("#ch-input", "LONG first")
    page.press("#ch-input", "Enter")
    # Early enough that plenty of the reply is still to come (shared runners
    # can be slow, so the stream must not finish before the gesture).
    page.wait_for_function("document.querySelector('#ch-thread').scrollHeight > document.querySelector('#ch-thread').clientHeight + 200", timeout=30_000)
    # A real wheel gesture, so the browser fires a genuine scroll event.
    box = page.locator("#ch-thread").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -100_000)
    page.wait_for_function("document.querySelector('#ch-thread').scrollTop < 50 && chState.pinned === false",
                           timeout=10_000)
    assert page.evaluate("!!chState.streaming"), "stream ended before the reader scrolled up"
    page.wait_for_function("!chState.streaming", timeout=30_000)
    page.wait_for_timeout(200)
    assert page.evaluate("document.querySelector('#ch-thread').scrollTop") < 50
    context.close()


def test_mode_bar_is_just_the_selector_in_both_modes(browser, live_server):
    context, page = _open_chat(browser, live_server, 1440, 900)
    _send(page, "hello")
    normal_bar = page.locator("#ch-mode-bar").bounding_box()["height"]
    page.click("#ch-mode-knowledge")
    # No explanatory note beside the selector; the version is in the tooltip.
    assert page.locator("#ch-mode-note").count() == 0
    assert "Answers grounded" not in page.inner_text("#ch-mode-bar")
    assert "0.1.0" in page.get_attribute("#ch-mode-knowledge", "title")
    assert page.locator("#ch-mode-bar").bounding_box()["height"] == normal_bar
    page.click("#ch-mode-normal")
    assert page.locator("#ch-mode-bar").bounding_box()["height"] == normal_bar
    # No dead space: the composer sits at the bottom of the chat card.
    gap = page.evaluate("document.querySelector('.chat-wrap').getBoundingClientRect().bottom"
                        " - document.querySelector('.chat-hint').getBoundingClientRect().bottom")
    assert 0 <= gap <= 4
    context.close()


def test_mode_switching_isolation_persistence_and_no_double_send(browser, live_server, upstream):
    context, page = _open_chat(browser, live_server, 1440, 900)
    model_before = page.evaluate("document.querySelector('#ch-model').gcSelect.value")
    _send(page, "plain hello")
    start = len(upstream.requests)
    page.click("#ch-mode-knowledge")
    page.click("#ch-mode-normal")
    page.click("#ch-mode-knowledge")
    assert len(upstream.requests) == start, "switching modes must not send anything"
    assert page.locator(".chat-msg").count() == 2, "switching modes must not drop messages"
    assert page.evaluate("document.querySelector('#ch-model').gcSelect.value") == model_before

    _send(page, "How do I enable SearXNG?")
    ask = upstream.requests[-1]["messages"]
    assert any("<geekcubo_documentation>" in (m.get("content") or "") for m in ask)
    sources = page.locator(".chat-msg-assistant:last-child .chat-knowledge-sources summary")
    assert "documentation sections" in sources.inner_text()

    page.click("#ch-mode-normal")
    _send(page, "and in normal chat?")
    normal = upstream.requests[-1]["messages"]
    assert not any("geekcubo_documentation" in json.dumps(m) or "Ask GeekCubo" in json.dumps(m) for m in normal)
    assert len(upstream.requests) == start + 2, "each send reaches the model exactly once"

    # Reopening restores the mode of the most recent question.
    convo = page.evaluate("chState.convo")
    page.evaluate("chNewChat()")
    page.wait_for_function(f"chState.convo !== {json.dumps(convo)}")
    assert page.evaluate("chState.mode") == "normal", "new conversations start in Normal Chat"
    page.evaluate(f"chOpen({json.dumps(convo)})")
    page.wait_for_function(f"chState.convo === {json.dumps(convo)} && chState.messages.length === 6")
    assert page.evaluate("chState.mode") == "normal"
    page.click("#ch-mode-knowledge")
    _send(page, "How do I enable SearXNG again?")
    page.evaluate("chNewChat()")
    page.wait_for_function(f"chState.convo !== {json.dumps(convo)}")
    page.evaluate(f"chOpen({json.dumps(convo)})")
    page.wait_for_function(f"chState.convo === {json.dumps(convo)} && chState.messages.length === 8")
    assert page.evaluate("chState.mode") == "knowledge"
    assert page.get_attribute("#ch-mode-knowledge", "aria-checked") == "true"
    context.close()


def test_selector_keyboard_and_active_state(browser, live_server):
    for theme in ("light", "dark"):
        context, page = _open_chat(browser, live_server, 1440, 900, theme)
        page.evaluate(f"document.documentElement.setAttribute('data-theme', '{theme}')")
        page.focus("#ch-mode-normal")
        page.keyboard.press("ArrowRight")
        assert page.evaluate("document.activeElement.id") == "ch-mode-knowledge"
        assert page.get_attribute("#ch-mode-knowledge", "aria-checked") == "true"
        assert page.get_attribute("#ch-mode-knowledge", "tabindex") == "0"
        assert page.get_attribute("#ch-mode-normal", "tabindex") == "-1"
        # Active is distinguishable: accent outline and heavier text.
        active, idle = page.evaluate("""() => ['#ch-mode-knowledge', '#ch-mode-normal'].map(s => {
            const c = getComputedStyle(document.querySelector(s)); return [c.boxShadow, c.fontWeight]; })""")
        assert "inset" in active[0] and "inset" not in idle[0]
        assert int(active[1]) > int(idle[1])
        page.keyboard.press("ArrowLeft")
        assert page.evaluate("chState.mode") == "normal"
        context.close()


@pytest.mark.parametrize("width", [1440, 768, 390])
def test_selector_and_sources_fit_every_width(browser, live_server, width):
    context, page = _open_chat(browser, live_server, width, 844)
    for sel in ("#ch-mode-normal", "#ch-mode-knowledge", "#ch-attach", "#ch-send"):
        box = page.locator(sel).bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1, sel
    page.click("#ch-mode-knowledge")
    page.evaluate(r"""() => {
      chState.messages = [{role:'assistant', mode:'knowledge',
        content:'Example:\n```bash\n' + 'command '.repeat(100) + '\n```',
        knowledge:{docs_version:'0.1.0', sources:[{id:'DEPLOYMENT.md#upgrading-an-existing-install-do-not-lose-data',
          reference:'Deployment guide → Upgrading an existing install (do not lose data) and a very long tail'}]}}];
      chRenderThread();
    }""")
    page.locator(".chat-knowledge-sources summary").click()
    assert "DEPLOYMENT.md#upgrading-an-existing-install-do-not-lose-data" in page.inner_text("#ch-thread")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    bubble = page.locator(".chat-bubble").bounding_box()
    assert bubble["x"] + bubble["width"] <= width + 1
    context.close()
