"""Browser-level (Playwright) coverage for Native Chat attachments.

The attachment pipeline is fully covered by backend tests; what those cannot
prove is that the dashboard actually wires the paperclip, drop zone, paste
handler and tray to it. These tests drive the real composer in a real browser:
browse-to-upload, drag/drop overlay, paste, chip removal and the pre-send
restore path. A missing event binding or a stale `app.js` fails here.

Skips cleanly when Playwright or a Chromium build is unavailable.
"""

from __future__ import annotations

import pytest

from tests.ui.conftest import boot_server, sign_in, stop_server

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    server = boot_server(tmp_path_factory.mktemp("chat-attach-ui"))
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


def _open_chat(page, live_server) -> list[str]:
    """Sign in, switch to the Chat tab and wait for attachment limits."""
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    page.wait_for_selector("#ch-attach:not([hidden])", timeout=15_000)
    page.wait_for_function("() => !!chState.attachmentLimits", timeout=15_000)
    return errors


def _upload(page, name: str, body: bytes = b"hello attachment") -> None:
    page.set_input_files(
        "#ch-file-input",
        {"name": name, "mimeType": "text/plain", "buffer": body},
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)


def _chip_text(page) -> str:
    return page.inner_text(".chat-attachment-chip").replace("\n", " | ")


def _drop(page, name: str, body: bytes = b"dropped content") -> None:
    page.evaluate(
        """({name, body}) => {
          const dt = new DataTransfer();
          dt.items.add(new File([body], name, {type: 'text/plain'}));
          document.querySelector('.chat-wrap').dispatchEvent(
            new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}),
          );
        }""",
        {"name": name, "body": body.decode()},
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)


# ─────────────────────────── upload paths ───────────────────────────

def test_paperclip_upload_renders_a_chip(page, live_server):
    errors = _open_chat(page, live_server)
    _upload(page, "notes.txt")

    text = _chip_text(page)
    assert "TXT" in text and "notes.txt" in text
    assert page.evaluate("() => chState.attachments[0].extraction") == "ok"
    assert page.evaluate("() => chState.attachments[0].kind") == "text"
    assert errors == []


def test_tray_sits_above_the_composer(page, live_server):
    _open_chat(page, live_server)
    _upload(page, "layout.txt")

    tray = page.evaluate(
        "() => { const r = document.querySelector('#ch-attachments').getBoundingClientRect();"
        " return [r.top, r.bottom]; }"
    )
    composer = page.evaluate(
        "() => document.querySelector('.chat-composer').getBoundingClientRect().top"
    )
    assert tray[1] <= composer + 1
    assert page.evaluate(
        "() => { const w = document.querySelector('.chat-wrap');"
        " return w.scrollWidth <= w.clientWidth + 1; }"
    )


def test_drag_overlay_toggles_and_drop_uploads(page, live_server):
    _open_chat(page, live_server)

    page.evaluate(
        """() => {
          const dt = new DataTransfer();
          dt.items.add(new File(['x'], 'a.txt', {type: 'text/plain'}));
          document.querySelector('.chat-wrap').dispatchEvent(
            new DragEvent('dragenter', {bubbles: true, dataTransfer: dt}),
          );
        }"""
    )
    page.wait_for_function(
        "() => !document.querySelector('#ch-drop-overlay').hidden", timeout=5_000
    )

    page.evaluate(
        """() => {
          const dt = new DataTransfer();
          dt.items.add(new File(['x'], 'a.txt', {type: 'text/plain'}));
          document.querySelector('.chat-wrap').dispatchEvent(
            new DragEvent('dragleave', {bubbles: true, dataTransfer: dt}),
          );
        }"""
    )
    page.wait_for_function(
        "() => document.querySelector('#ch-drop-overlay').hidden", timeout=5_000
    )

    _drop(page, "drop.txt")
    assert "drop.txt" in _chip_text(page)


def test_pasted_file_uploads(page, live_server):
    _open_chat(page, live_server)
    page.evaluate(
        """() => {
          const dt = new DataTransfer();
          dt.items.add(new File(['pasted'], 'pasted.txt', {type: 'text/plain'}));
          document.querySelector('#ch-input').dispatchEvent(
            new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData: dt}),
          );
        }"""
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
    assert "pasted.txt" in _chip_text(page)


def test_plain_text_paste_is_not_intercepted(page, live_server):
    _open_chat(page, live_server)
    page.fill("#ch-input", "keep me")
    page.evaluate(
        """() => {
          const dt = new DataTransfer();
          dt.setData('text/plain', 'typed');
          document.querySelector('#ch-input').dispatchEvent(
            new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData: dt}),
          );
        }"""
    )
    page.wait_for_timeout(300)
    assert page.evaluate("() => chState.attachments.length") == 0


def test_chip_remove_clears_the_tray(page, live_server):
    _open_chat(page, live_server)
    _upload(page, "remove-me.txt")

    page.click("[data-attachment-remove]")
    page.wait_for_function(
        "() => document.querySelectorAll('.chat-attachment-chip').length === 0",
        timeout=10_000,
    )
    assert page.evaluate("() => chState.attachments.length") == 0
    assert page.evaluate("() => document.querySelector('#ch-attachments').hidden") is True


# ─────────────────────── composer state ───────────────────────

def test_attachment_only_send_is_enabled(page, live_server):
    _open_chat(page, live_server)
    _upload(page, "only.txt")

    assert page.evaluate("() => document.querySelector('#ch-input').value") == ""
    assert page.evaluate("() => !document.querySelector('#ch-send').disabled")


def test_new_chat_clears_pending_attachments(page, live_server):
    _open_chat(page, live_server)
    _upload(page, "pending.txt")

    page.click("#ch-new")
    page.wait_for_function("() => chState.attachments.length === 0", timeout=15_000)


def test_failed_send_restores_pending_attachments(page, live_server):
    """A rejected send must not silently discard the operator's files.

    The server rejects an unknown model before the message is bound, so the
    client-side guard is disabled here to exercise the HTTP error path.
    """
    _open_chat(page, live_server)
    _upload(page, "retry.txt")

    page.evaluate(
        "() => { chState.attachmentLimits = {...chState.attachmentLimits, enabled: true}; }"
    )
    page.evaluate(
        """() => {
          const sel = document.querySelector('#ch-model select');
          if (sel) { sel.insertAdjacentHTML('beforeend',
            '<option value="nope/does-not-exist">nope/does-not-exist</option>');
            sel.value = 'nope/does-not-exist';
            sel.dispatchEvent(new Event('change', {bubbles: true})); }
        }"""
    )
    page.fill("#ch-input", "this send fails")
    page.click("#ch-send")

    page.wait_for_function(
        "() => document.querySelectorAll('.toast.err').length > 0", timeout=25_000
    )
    page.wait_for_function(
        "() => chState.attachments.some((a) => a.name === 'retry.txt')", timeout=25_000
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=10_000)


def test_disabled_server_hides_the_paperclip(page, tmp_path_factory):
    server = boot_server(
        tmp_path_factory.mktemp("chat-attach-off"),
        extra_env={"ATTACHMENTS_ENABLED": "false"},
    )
    try:
        sign_in(page, server.base_url)
        page.evaluate("() => setTab('chat')")
        page.wait_for_function("() => !!chState.attachmentLimits", timeout=15_000)
        assert page.evaluate("() => chState.attachmentLimits.enabled") is False
        assert page.evaluate("() => document.querySelector('#ch-attach').hidden") is True
    finally:
        stop_server(server)


# ───────────── reported regressions: reload, screenshot paste ─────────────

def _png(width: int = 24, height: int = 16) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _visible_box(page, selector: str) -> dict:
    """Rendered geometry + the element actually painted at its centre."""
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return {hidden: el.hidden, display: cs.display, visibility: cs.visibility,
                  w: r.width, h: r.height, inViewport: r.bottom <= innerHeight && r.right <= innerWidth,
                  onTop: !!hit && (hit === el || el.contains(hit))};
        }""",
        selector,
    )


def test_paperclip_visible_after_signing_in_from_a_chat_deep_link(page, live_server):
    """Regression for the reported "no paperclip": opening /#chat while signed
    out (a reload or bookmark) loaded the Chat tab BEFORE authentication. The
    401 on /attachments/limits was cached as `enabled: false`, so the button
    stayed hidden for the rest of the page's life."""
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, live_server.base_url, path="/#chat")
    page.wait_for_selector("#panel-chat.active", timeout=15_000)
    page.wait_for_function("() => chState.attachmentLimits?.enabled === true", timeout=15_000)

    box = _visible_box(page, "#ch-attach")
    assert box["hidden"] is False and box["display"] != "none" and box["visibility"] == "visible"
    assert box["w"] >= 32 and box["h"] >= 32
    assert box["inViewport"] and box["onTop"], box
    assert errors == []


def test_paperclip_visible_after_reload_on_chat(page, live_server):
    sign_in(page, live_server.base_url)
    page.evaluate("() => setTab('chat')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
    page.wait_for_selector("#panel-chat.active", timeout=15_000)
    page.wait_for_function("() => chState.attachmentLimits?.enabled === true", timeout=15_000)
    assert _visible_box(page, "#ch-attach")["onTop"]


def test_paperclip_click_opens_the_file_chooser(page, live_server):
    _open_chat(page, live_server)
    with page.expect_file_chooser(timeout=5_000) as fc:
        page.click("#ch-attach")
    chooser = fc.value
    assert chooser.is_multiple()
    chooser.set_files({"name": "picked.txt", "mimeType": "text/plain", "buffer": b"picked"})
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
    assert "picked.txt" in _chip_text(page)


def test_pasted_screenshot_without_a_filename_becomes_an_image(page, live_server):
    """Screenshot tools put an image on the clipboard with no usable name
    ("" or "blob"). The server classifies by extension, so the paste used to
    be rejected as an unsupported type. It must arrive as an image."""
    _open_chat(page, live_server)
    page.fill("#ch-input", "what is in this picture?")
    page.evaluate(
        """(bytes) => {
          const dt = new DataTransfer();
          dt.items.add(new File([new Uint8Array(bytes)], 'blob', {type: 'image/png'}));
          document.querySelector('#ch-input').dispatchEvent(
            new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData: dt}),
          );
        }""",
        list(_png()),
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
    att = page.evaluate("() => chState.attachments[0]")
    assert att["kind"] == "image", att
    assert att["name"].startswith("pasted-image-") and att["name"].endswith(".png")
    assert page.query_selector(".chat-attachment-thumb") is not None
    # Pasting an image neither submits the message nor eats the typed text.
    assert page.input_value("#ch-input") == "what is in this picture?"
    assert page.evaluate("() => chState.streaming") is None
    assert page.evaluate("() => document.querySelectorAll('.toast.err').length") == 0


def test_unsupported_file_shows_a_clear_error_and_no_chip(page, live_server):
    _open_chat(page, live_server)
    page.set_input_files(
        "#ch-file-input",
        {"name": "tool.exe", "mimeType": "application/octet-stream", "buffer": b"MZ\x90\x00"},
    )
    page.wait_for_function(
        "() => [...document.querySelectorAll('.toast.err')].some(t => t.textContent.includes('tool.exe'))",
        timeout=15_000,
    )
    msg = page.evaluate(
        "() => [...document.querySelectorAll('.toast.err')].map(t => t.textContent).join(' | ')"
    )
    assert "unsupported file type" in msg, msg
    assert page.evaluate("() => chState.attachments.length") == 0
    assert page.evaluate("() => chState.uploading") == 0


def test_unreadable_file_is_marked_on_its_chip(page, live_server):
    """Extraction failures are not rejections: the file stays attachable, so
    the problem must stay visible on the chip, not only in a passing toast."""
    _open_chat(page, live_server)
    page.set_input_files(
        "#ch-file-input",
        {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\nnot really a pdf"},
    )
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
    assert page.evaluate("() => chState.attachments[0].extraction") == "failed"
    assert page.query_selector(".chat-attachment-chip.is-failed .chat-attachment-warn") is not None
    page.wait_for_function(
        "() => [...document.querySelectorAll('.toast')].some(t => t.textContent.includes('broken.pdf'))",
        timeout=10_000,
    )


def test_send_is_disabled_while_an_upload_is_in_flight(page, live_server):
    _open_chat(page, live_server)
    page.route(
        "**/api/chat/attachments",
        lambda route: (page.wait_for_timeout(800), route.continue_()),
    )
    page.set_input_files(
        "#ch-file-input", {"name": "slow.txt", "mimeType": "text/plain", "buffer": b"slow"}
    )
    page.wait_for_selector(".chat-attachment-chip.is-uploading", timeout=5_000)
    assert page.evaluate("() => document.querySelector('#ch-send').disabled") is True
    page.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
    page.wait_for_function("() => !document.querySelector('#ch-send').disabled", timeout=5_000)


def test_composer_is_multiline_and_enter_follows_the_setting(page, live_server):
    _open_chat(page, live_server)
    # Observe sends at the network boundary: any send POSTs a conversation.
    posts: list[str] = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" and "/api/chat/conversations" in r.url else None)

    assert page.evaluate("() => document.querySelector('#ch-input').tagName") == "TEXTAREA"
    page.focus("#ch-input")
    page.keyboard.type("line one")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("line two")
    assert page.input_value("#ch-input") == "line one\nline two"
    # The textarea grows with its content instead of scrolling a single line.
    h1 = page.evaluate("() => document.querySelector('#ch-input').getBoundingClientRect().height")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("line three")
    h2 = page.evaluate("() => document.querySelector('#ch-input').getBoundingClientRect().height")
    assert h2 > h1
    assert posts == []

    # Enter during an IME composition must not send a half-typed message.
    page.evaluate(
        """() => document.querySelector('#ch-input').dispatchEvent(
             new KeyboardEvent('keydown', {key: 'Enter', isComposing: true, bubbles: true, cancelable: true}))"""
    )
    page.wait_for_timeout(300)
    assert posts == []

    # With "Enter sends" switched off, Enter is a newline and Ctrl+Enter sends.
    page.evaluate("() => { chState.settings = {...chState.settings, enter_to_send: false}; }")
    page.keyboard.press("Enter")
    assert page.input_value("#ch-input").endswith("\n")
    assert posts == []
    with page.expect_request(
        lambda r: r.method == "POST" and "/api/chat/conversations" in r.url, timeout=10_000
    ):
        page.keyboard.press("Control+Enter")


def test_composer_controls_fit_on_a_phone(browser, live_server):
    ctx = browser.new_context(viewport={"width": 360, "height": 740}, is_mobile=True)
    pg = ctx.new_page()
    try:
        sign_in(pg, live_server.base_url)
        pg.evaluate("() => setTab('chat')")
        pg.wait_for_function("() => chState.attachmentLimits?.enabled === true", timeout=15_000)
        pg.set_input_files(
            "#ch-file-input",
            {"name": "a-really-long-file-name-that-would-overflow-the-tray-on-a-phone.txt",
             "mimeType": "text/plain", "buffer": b"x"},
        )
        pg.wait_for_selector(".chat-attachment-chip:not(.is-uploading)", timeout=20_000)
        for sel in ("#ch-attach", "#ch-input", "#ch-send"):
            box = _visible_box(pg, sel)
            assert box["inViewport"] and box["onTop"] and box["w"] >= 32, (sel, box)
        assert pg.evaluate(
            "() => { const w = document.querySelector('.chat-main');"
            " return w.scrollWidth <= w.clientWidth + 1; }"
        )
    finally:
        ctx.close()
