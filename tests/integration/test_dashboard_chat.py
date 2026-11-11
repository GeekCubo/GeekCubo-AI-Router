"""Dashboard Chat integration tests.

The Chat tab calls `execute_chat()` on the admin session, so these tests run
the REAL engine — routing, logging, prompt cache, cost provenance — with
LiteLLM (the network boundary) mocked per the no-mock-of-layer-under-test
rule. Persistence goes to real SQLite.

What the tests must prove:
  - Streaming: the browser receives the engine's OpenAI SSE frames
    unmodified, `[DONE]` included, and the assistant row lands AFTER the
    stream finishes (success AND upstream-error variants).
  - `requests_log.request_source` is "dashboard_chat" so Analytics can tell
    chat traffic from SDK traffic WITHOUT double counting.
  - `save_history=false` turns persistence off entirely (engine passthrough).
  - Retention pruning, clear-with-confirm, regenerate, settings round-trip.
"""

from __future__ import annotations

import copy
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from tests.authkit import SignedInClient

BLOCKING_RETURN = {
    "id": "chatcmpl-dash-1",
    "model": "gpt-4o-mini",
    "object": "chat.completion",
    "created": int(time.time()),
    "choices": [{
        "index": 0,
        "message": {"role": "assistant", "content": "Hello world"},
        "finish_reason": "stop",
    }],
    "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    "_geekcubo_meta": {"provider": "openai", "latency_ms": 12},
}

STREAM_CHUNKS = [
    {
        "id": "chatcmpl-dash-1",
        "object": "chat.completion.chunk",
        "model": "gpt-4o-mini",
        "created": int(time.time()),
        "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}],
    },
    {
        "id": "chatcmpl-dash-1",
        "object": "chat.completion.chunk",
        "model": "gpt-4o-mini",
        "created": int(time.time()),
        "choices": [{"index": 0, "delta": {"content": " world"}, "finish_reason": None}],
    },
    {
        "id": "chatcmpl-dash-1",
        "object": "chat.completion.chunk",
        "model": "gpt-4o-mini",
        "created": int(time.time()),
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        "_geekcubo_meta": {"provider": "openai", "latency_ms": 12},
    },
]


async def _stream_iter(chunks):
    for chunk in chunks:
        yield chunk


def _png_bytes(width: int = 24, height: int = 16) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (20, 140, 60)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def dash_env(tmp_sqlite_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")

    from app import config as cfg
    cfg.get_settings.cache_clear()

    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db import session as session_mod
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory

    from app.seed import seed_initial_state
    async with factory() as s:
        await seed_initial_state(s)

    from app import router_cache
    router_cache.invalidate_router()

    fake_client = AsyncMock()

    async def _acompletion_router(**kwargs):
        if kwargs.get("stream"):
            return _stream_iter(copy.deepcopy(STREAM_CHUNKS))
        return copy.deepcopy(BLOCKING_RETURN)

    fake_client.acompletion = AsyncMock(side_effect=_acompletion_router)

    async def _fake_get_router(_session):
        return fake_client

    monkeypatch.setattr(router_cache, "get_router", _fake_get_router)

    monkeypatch.setenv("ATTACHMENT_DIR", str(tempfile.mkdtemp(prefix="attach-")))
    cfg.get_settings.cache_clear()

    from app.main import create_app
    app = create_app()

    from httpx import ASGITransport

    async with SignedInClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, fake_client, factory

    await engine.dispose()
    session_mod._session_factory = None


async def _sse_frames(text: str) -> list[object]:
    out: list[object] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        if payload.strip() == "[DONE]":
            out.append("[DONE]")
        else:
            out.append(json.loads(payload))
    return out


# ── settings ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("stream", [False, True])
async def test_chat_provenance_uses_exact_request_trace(dash_env, stream):
    from sqlalchemy import select

    from app.routes.dashboard_chat import _latest_dashboard_log
    from packages.db.models.request_log import RequestLog

    client, _, factory = dash_env
    conversation = (await client.post("/api/chat/conversations", json={})).json()
    for content in ("first", "second"):
        response = await client.post(
            f"/api/chat/conversations/{conversation['id']}/messages",
            json={"content": content, "model": "gpt-4o-mini", "stream": stream},
        )
        assert response.status_code == 200
    messages = (await client.get(
        f"/api/chat/conversations/{conversation['id']}"
    )).json()["messages"]
    assistants = [message for message in messages if message["role"] == "assistant"]
    assert len(assistants) == 2
    assert assistants[0]["trace_id"] != assistants[1]["trace_id"]
    async with factory() as session:
        logs = (await session.execute(select(RequestLog))).scalars().all()
        assert len(logs) == 2
        first = next(log for log in logs if log.trace_id == assistants[0]["trace_id"])
        selected = await _latest_dashboard_log(session, first.workspace_id, first.trace_id)
        assert selected.id == first.id
        assert await _latest_dashboard_log(session, first.workspace_id, "missing-trace") is None
        assert await _latest_dashboard_log(session, "other-workspace", first.trace_id) is None


async def test_settings_roundtrip(dash_env):
    client, _, _ = dash_env
    r = await client.get("/api/chat/settings")
    assert r.status_code == 200, r.text
    defaults = r.json()
    assert defaults["default_model"] == "auto"
    assert defaults["save_history"] is True

    r = await client.put(
        "/api/chat/settings",
        json={"default_model": "gpt-4o-mini", "save_history": True,
              "temperature": 0.4, "retention_days": 14},
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["default_model"] == "gpt-4o-mini"
    assert got["temperature"] == 0.4
    assert got["retention_days"] == 14

    r = await client.put("/api/chat/settings", json={"font_size": "giant"})
    assert r.status_code == 422


# ── conversations ──────────────────────────────────────────────────────────


async def test_create_list_get_rename_delete(dash_env):
    client, _, _ = dash_env
    r = await client.post("/api/chat/conversations", json={})
    assert r.status_code == 201, r.text
    convo = r.json()

    r = await client.get("/api/chat/conversations")
    items = r.json()["conversations"]
    assert [c["id"] for c in items] == [convo["id"]]
    assert items[0]["title"] == ""

    r = await client.patch(f"/api/chat/conversations/{convo['id']}",
                           json={"title": "Weekly report"})
    assert r.json()["title"] == "Weekly report"

    r = await client.delete(f"/api/chat/conversations/{convo['id']}")
    assert r.status_code == 204
    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    assert r.status_code == 404
    r = await client.get("/api/chat/conversations")
    assert r.json()["conversations"] == []


# ── send message (blocking) ────────────────────────────────────────────────


async def test_blocking_send_persists_rows_and_logs_source(dash_env):
    client, _, factory = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi there", "model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()["message"]
    assert body["role"] == "assistant"
    assert body["content"] == "Hello world"
    assert body["model_resolved"] == "gpt-4o-mini"
    assert body["input_tokens"] == 4
    assert body["output_tokens"] == 2
    # The selected history window is described out-of-band on the response.
    assert int(r.headers["x-geek-context-budget"]) > 0
    assert r.headers["x-geek-context-omitted"] == "0"
    assert r.headers["x-geek-context-source"] in ("model", "fallback")
    assert r.json()["context"]["budget_tokens"] == int(r.headers["x-geek-context-budget"])

    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    # Auto-title from the first exchange.
    assert r.json()["conversation"]["title"] == "hi there"

    # The engine's request log marks chat traffic distinctly from SDK calls.
    from sqlalchemy import select

    from packages.db.models.request_log import RequestLog

    async with factory() as s:
        rows = (await s.execute(select(RequestLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].request_source == "dashboard_chat"


async def test_send_message_without_history(dash_env):
    client, _, _ = dash_env
    await client.put("/api/chat/settings", json={"save_history": False})
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 200
    # Raw engine body passes through, nothing persisted.
    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    assert r.json()["messages"] == []


# ── send message (streaming) ───────────────────────────────────────────────


async def test_stream_send_relays_frames_and_persists_after_done(dash_env):
    client, _, factory = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": True},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert int(r.headers["x-geek-context-budget"]) > 0
    assert r.headers["x-geek-context-omitted"] == "0"
    frames = await _sse_frames(r.text)
    # The engine's frames reach the browser unmodified, [DONE] included.
    assert frames[-1] == "[DONE]"
    deltas = [f["choices"][0]["delta"].get("content", "")
              for f in frames[:-1] if f.get("choices")]
    assert "".join(deltas) == "Hello world"
    usage_frames = [f for f in frames[:-1] if f.get("usage")]
    assert usage_frames, "usage chunk must reach the browser"

    # Persistence happens after the stream, not before.
    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[-1]["content"] == "Hello world"
    assert msgs[-1]["input_tokens"] == 4
    assert msgs[-1]["output_tokens"] == 2
    # Provenance (provider / trace / cost) mirrors the engine's RequestLog row.
    assert msgs[-1]["provider"] == "openai"
    # The fixture meta carries no litellm cost, so the engine falls
    # back to its catalog estimate — same provenance Analytics records.
    assert msgs[-1]["cost_source"] == "catalog_estimate"
    assert (msgs[-1]["cost_microcents"] or 0) >= 0


async def test_stream_abort_keeps_partial_answer_and_logs_disconnect(dash_env):
    """Stop / closed tab mid-stream: the partial answer is persisted as
    `aborted` and the engine records a 499 client_disconnect row.

    Regression: the relay's persistence step ran unshielded inside the
    cancelled task, so the first DB await was cancelled and the partial
    answer the UI promises to keep was silently lost.
    """
    import asyncio

    import anyio
    from sqlalchemy import select

    from packages.db.models.chat_conversation import ChatMessage
    from packages.db.models.request_log import RequestLog

    client, fake, factory = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()

    first_chunk_sent = asyncio.Event()

    async def _slow_stream():
        yield copy.deepcopy(STREAM_CHUNKS[0])
        first_chunk_sent.set()
        await asyncio.sleep(30)  # never finishes; the client aborts first
        yield copy.deepcopy(STREAM_CHUNKS[-1])

    fake.acompletion = AsyncMock(side_effect=lambda **kw: _slow_stream())

    app = client._transport.app
    body = json.dumps({"content": "hi", "model": "gpt-4o-mini", "stream": True}).encode()
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "server": ("test", 80),
        "path": f"/api/chat/conversations/{convo['id']}/messages",
        "raw_path": f"/api/chat/conversations/{convo['id']}/messages".encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            *[(k.encode(), v.encode()) for k, v in client.headers.items()
              if k.lower() not in ("host", "content-type", "content-length")],
            (b"cookie", "; ".join(f"{k}={v}" for k, v in client.cookies.items()).encode()),
        ],
    }
    disconnect = asyncio.Event()
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    sent_bodies: list[bytes] = []

    async def send(message):
        if message["type"] == "http.response.body":
            sent_bodies.append(message.get("body", b""))

    async def _abort_after_first_chunk():
        await first_chunk_sent.wait()
        await asyncio.sleep(0.05)
        disconnect.set()

    with anyio.fail_after(10):
        async with anyio.create_task_group() as tg:
            tg.start_soon(_abort_after_first_chunk)
            await app(scope, receive, send)

    assert b"Hello" in b"".join(sent_bodies)

    async with factory() as s:
        msgs = (await s.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == convo["id"])
            .order_by(ChatMessage.seq)
        )).scalars().all()
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[-1].content == "Hello"
        assert msgs[-1].error_type == "aborted"

        log = (await s.execute(
            select(RequestLog).where(RequestLog.request_source == "dashboard_chat")
        )).scalars().all()
        assert [(r.status_code, r.error_type) for r in log] == [(499, "client_disconnect")]


async def test_stream_send_upstream_error_persists_nothing(dash_env):
    client, fake, _ = dash_env
    fake.acompletion = AsyncMock(side_effect=RuntimeError("provider down"))
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 503, r.text
    assert r.json()["error"]["type"] == "engine_error"

    # The user row stays (retry-friendly); no assistant row.
    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    assert [m["role"] for m in r.json()["messages"]] == ["user"]


# ── regenerate ─────────────────────────────────────────────────────────────


async def test_regenerate_with_history_off_preserves_existing_messages(dash_env):
    client, fake, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    path = f"/api/chat/conversations/{convo['id']}"
    response = await client.post(
        f"{path}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )
    assert response.status_code == 200
    before = (await client.get(path)).json()["messages"]
    await client.put("/api/chat/settings", json={"save_history": False})
    fake.acompletion.reset_mock()
    response = await client.post(
        f"{path}/regenerate", json={"model": "gpt-4o-mini", "stream": False},
    )
    assert response.status_code == 409
    assert (await client.get(path)).json()["messages"] == before
    fake.acompletion.assert_not_called()


async def test_regenerate_replaces_trailing_assistant(dash_env):
    client, fake, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )

    fake.acompletion = AsyncMock(return_value={
        **BLOCKING_RETURN,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Better answer"},
                     "finish_reason": "stop"}],
    })

    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/regenerate",
        json={"model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["content"] == "Better answer"

    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    roles = [m["role"] for m in r.json()["messages"]]
    assert roles == ["user", "assistant"]


# ── history management ─────────────────────────────────────────────────────


async def test_clear_history_requires_confirm(dash_env):
    client, _, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )

    r = await client.post("/api/chat/history/clear", json={})
    assert r.status_code == 422
    r = await client.post("/api/chat/history/clear", json={"confirm": True})
    assert r.status_code == 200, r.text
    assert r.json()["cleared"] == 1
    r = await client.get("/api/chat/conversations")
    assert r.json()["conversations"] == []


async def test_retention_prunes_stale_conversations(dash_env):
    client, _, factory = dash_env
    await client.put("/api/chat/settings", json={"retention_days": 7})
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "old chat", "stream": False},
    )

    from sqlalchemy import update

    from packages.db.models.chat_conversation import ChatConversation

    stale = datetime.now(timezone.utc) - timedelta(days=30)
    async with factory() as s:
        await s.execute(
            update(ChatConversation)
            .where(ChatConversation.id == convo["id"])
            .values(last_message_at=stale)
        )
        await s.commit()

    r = await client.get("/api/chat/conversations")
    assert r.json()["conversations"] == []
    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    assert r.status_code == 404


async def test_send_message_unknown_conversation(dash_env):
    client, _, _ = dash_env
    r = await client.post(
        "/api/chat/conversations/nope/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 404


async def test_send_message_forwards_engine_params(dash_env):
    client, fake, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False, "temperature": 0.3, "max_tokens": 99},
    )
    call = fake.acompletion.await_args
    assert call.kwargs["temperature"] == 0.3
    assert call.kwargs["max_tokens"] == 99
    # History + this message reach the engine in order.
    roles = [m["role"] for m in call.kwargs["messages"]]
    assert roles == ["user"]


async def test_settings_clear_and_roundtrip(dash_env):
    """Set -> clear -> reload: overrides actually revert to the default."""
    client, _, _ = dash_env
    r = await client.put("/api/chat/settings", json={"temperature": 0.7, "max_tokens": 500})
    assert r.status_code == 200, r.text
    assert r.json()["temperature"] == 0.7
    assert r.json()["max_tokens"] == 500

    r = await client.put("/api/chat/settings", json={"clear": ["temperature", "max_tokens"]})
    assert r.status_code == 200, r.text
    assert r.json()["temperature"] is None
    assert r.json()["max_tokens"] is None

    # Reload persists the clear.
    r = await client.get("/api/chat/settings")
    assert r.json()["temperature"] is None
    assert r.json()["max_tokens"] is None

    # Omitting a field leaves it unchanged.
    r = await client.put("/api/chat/settings", json={"save_history": True})
    assert r.json()["max_tokens"] is None

    # Unknown clear targets are rejected.
    r = await client.put("/api/chat/settings", json={"clear": ["nope"]})
    assert r.status_code == 422

    # Validation ranges still apply.
    r = await client.put("/api/chat/settings", json={"temperature": 9.9})
    assert r.status_code == 422


# ── attachments ────────────────────────────────────────────────────────────


async def _upload(client, name: str, data: bytes, mime: str = "text/plain") -> dict:
    r = await client.post(
        "/api/chat/attachments",
        files={"file": (name, data, mime)},
    )
    assert r.status_code == 201, r.text
    return r.json()["attachment"]


async def test_attachment_limits_are_published(dash_env):
    client, _, _ = dash_env
    r = await client.get("/api/chat/attachments/limits")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["max_mb"] >= 1
    assert body["max_per_message"] == 8


async def test_upload_extracts_and_serves_original_bytes(dash_env):
    client, _, _ = dash_env
    att = await _upload(client, "notes.txt", b"alpha beta gamma")
    assert att["kind"] == "text"
    assert att["filename"] == "notes.txt"
    assert att["extraction_state"] == "ok"
    assert att["extracted_chars"] == len("alpha beta gamma")

    r = await client.get(f"/api/chat/attachments/{att['id']}")
    assert r.json()["attachment"]["id"] == att["id"]

    r = await client.get(f"/api/chat/attachments/{att['id']}/content")
    assert r.status_code == 200
    assert r.content == b"alpha beta gamma"
    assert "attachment;" in r.headers["content-disposition"]
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_non_ascii_filename_downloads_instead_of_500(dash_env):
    """Regression: a non-Latin-1 filename crashed the header encoder (500)."""
    from urllib.parse import quote

    from app.routes.chat_attachments import _content_disposition

    client, _, _ = dash_env
    att = await _upload(client, "季度报告.txt", b"quarterly numbers")
    r = await client.get(f"/api/chat/attachments/{att['id']}/content")
    assert r.status_code == 200, r.text
    assert r.content == b"quarterly numbers"
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment;")
    assert 'filename="____.txt"' in cd
    assert "filename*=UTF-8''" + quote("季度报告.txt", safe="") in cd

    # Quotes, backslashes and control characters never reach the header raw.
    tricky = _content_disposition('a"b\\c\r\nd.txt')
    assert 'filename="a_b_c__d.txt"' in tricky
    assert "\r" not in tricky and "\n" not in tricky
    assert _content_disposition(None).startswith('attachment; filename="attachment"')


async def test_stale_unbound_upload_is_purged_even_with_history_off(dash_env):
    """With history off, sent uploads are never bound to a message; the
    orphan sweep used to run only on the history-on send path, so their
    bytes stayed on disk forever."""
    from sqlalchemy import select, update

    from app.attachments import storage
    from packages.db.models.chat_attachment import ChatAttachment

    client, _, factory = dash_env
    await client.put("/api/chat/settings", json={"save_history": False})
    old = await _upload(client, "old.txt", b"stale bytes")
    async with factory() as s:
        row = (await s.execute(
            select(ChatAttachment).where(ChatAttachment.id == old["id"])
        )).scalar_one()
        old_path = storage.path_for(row.storage_name)
        await s.execute(
            update(ChatAttachment)
            .where(ChatAttachment.id == old["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=2))
        )
        await s.commit()
    assert old_path.exists()

    fresh = await _upload(client, "fresh.txt", b"draft in progress")

    assert not old_path.exists()
    assert (await client.get(f"/api/chat/attachments/{old['id']}")).status_code == 404
    # A recent unbound upload (a draft) is never touched.
    assert (await client.get(f"/api/chat/attachments/{fresh['id']}")).status_code == 200


async def test_upload_rejects_unsafe_and_oversized_files(dash_env, monkeypatch):
    client, _, _ = dash_env
    r = await client.post(
        "/api/chat/attachments",
        files={"file": ("tool.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert r.status_code == 422

    from app import config as cfg

    monkeypatch.setattr(cfg.get_settings(), "attachment_max_mb", 1)
    r = await client.post(
        "/api/chat/attachments",
        files={"file": ("big.txt", b"a" * (1024 * 1024 + 10), "text/plain")},
    )
    assert r.status_code == 413


async def test_text_attachment_is_sent_to_the_model_and_displayed(dash_env):
    client, fake, factory = dash_env
    att = await _upload(client, "brief.md", b"# Brief\nThe client wants blue.")
    convo = (await client.post("/api/chat/conversations", json={})).json()

    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={
            "content": "summarise the attached brief",
            "attachment_ids": [att["id"]],
            "model": "gpt-4o-mini",
            "stream": False,
        },
    )
    assert r.status_code == 200, r.text

    sent = fake.acompletion.await_args.kwargs["messages"]
    user_msg = [m for m in sent if m["role"] == "user"][-1]
    assert isinstance(user_msg["content"], str)
    assert "[attached file: brief.md" in user_msg["content"]
    assert "The client wants blue." in user_msg["content"]

    r = await client.get(f"/api/chat/conversations/{convo['id']}")
    user_row = [m for m in r.json()["messages"] if m["role"] == "user"][0]
    assert user_row["attachments"][0]["name"] == "brief.md"

    from sqlalchemy import select

    from packages.db.models.chat_attachment import ChatAttachment

    async with factory() as s:
        row = (await s.execute(select(ChatAttachment))).scalar_one()
        assert row.message_id == user_row["id"]
        assert row.conversation_id == convo["id"]


async def test_attachment_only_message_is_allowed(dash_env):
    client, _, _ = dash_env
    att = await _upload(client, "a.txt", b"just a file")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "  ", "attachment_ids": [att["id"]],
              "model": "gpt-4o-mini", "stream": False},
    )
    assert r.status_code == 200, r.text


async def test_empty_message_without_attachments_is_rejected(dash_env):
    client, _, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "   ", "stream": False},
    )
    assert r.status_code == 422


async def test_unknown_attachment_is_rejected(dash_env):
    client, _, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "attachment_ids": ["missing-id"], "stream": False},
    )
    assert r.status_code == 422


async def test_image_is_rejected_for_a_text_only_model(dash_env):
    client, fake, _ = dash_env
    att = await _upload(client, "chart.png", _png_bytes(), "image/png")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "describe it", "attachment_ids": [att["id"]],
              "model": "deepseek/deepseek-v3", "stream": False},
    )
    assert r.status_code == 422
    assert "vision" in r.json()["error"]["message"].lower()
    # Nothing was sent upstream: the model never sees a message it cannot read.
    fake.acompletion.assert_not_awaited()


async def test_image_is_sent_as_parts_for_a_vision_model(dash_env):
    client, fake, _ = dash_env
    att = await _upload(client, "chart.png", _png_bytes(), "image/png")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "describe it", "attachment_ids": [att["id"]],
              "model": "gpt-4o", "stream": False},
    )
    assert r.status_code == 200, r.text
    sent = fake.acompletion.await_args.kwargs["messages"]
    user_msg = [m for m in sent if m["role"] == "user"][-1]
    assert isinstance(user_msg["content"], list)
    assert any(p.get("type") == "image_url" for p in user_msg["content"])
    image_part = [p for p in user_msg["content"] if p["type"] == "image_url"][0]
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


async def test_thumbnail_is_available_for_images(dash_env):
    client, _, _ = dash_env
    att = await _upload(client, "chart.png", _png_bytes(), "image/png")
    r = await client.get(f"/api/chat/attachments/{att['id']}/thumbnail")
    assert r.status_code == 200
    assert r.json()["thumbnail"].startswith("data:image/jpeg;base64,")


async def test_unsent_attachment_can_be_deleted_but_a_sent_one_cannot(dash_env):
    client, _, _ = dash_env
    pending = await _upload(client, "draft.txt", b"draft")
    r = await client.delete(f"/api/chat/attachments/{pending['id']}")
    assert r.status_code == 204
    r = await client.get(f"/api/chat/attachments/{pending['id']}")
    assert r.status_code == 404

    sent = await _upload(client, "kept.txt", b"kept")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "attachment_ids": [sent["id"]], "stream": False},
    )
    r = await client.delete(f"/api/chat/attachments/{sent['id']}")
    assert r.status_code == 409


async def test_deleting_a_conversation_marks_its_attachments(dash_env):
    client, _, factory = dash_env
    att = await _upload(client, "gone.txt", b"gone soon")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "attachment_ids": [att["id"]], "stream": False},
    )
    r = await client.delete(f"/api/chat/conversations/{convo['id']}")
    assert r.status_code == 204

    from sqlalchemy import select

    from packages.db.models.chat_attachment import ChatAttachment

    async with factory() as s:
        row = (await s.execute(select(ChatAttachment))).scalar_one()
        assert row.is_deleted == 1

    from app.attachments import storage

    assert not storage.path_for(row.storage_name).exists()


async def test_attachment_bytes_are_not_re_read_for_old_turns(dash_env):
    """Only the newest user turn keeps its image parts; older turns degrade
    to a text marker so replay cannot multiply image cost."""
    client, fake, _ = dash_env
    first = await _upload(client, "one.png", _png_bytes(), "image/png")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "first", "attachment_ids": [first["id"]],
              "model": "gpt-4o", "stream": False},
    )
    second = await _upload(client, "two.png", _png_bytes(), "image/png")
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "second", "attachment_ids": [second["id"]],
              "model": "gpt-4o", "stream": False},
    )
    sent = fake.acompletion.await_args.kwargs["messages"]
    users = [m for m in sent if m["role"] == "user"]
    assert len(users) == 2
    assert isinstance(users[0]["content"], str)
    assert "[attached: one.png]" in users[0]["content"]
    assert isinstance(users[1]["content"], list)


async def test_regenerate_resends_the_attached_image(dash_env):
    client, fake, _ = dash_env
    att = await _upload(client, "pic.png", _png_bytes(), "image/png")
    convo = (await client.post("/api/chat/conversations", json={})).json()
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "describe", "attachment_ids": [att["id"]],
              "model": "gpt-4o", "stream": False},
    )
    fake.acompletion = AsyncMock(return_value={
        **BLOCKING_RETURN,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Again"},
                     "finish_reason": "stop"}],
    })
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/regenerate",
        json={"model": "gpt-4o", "stream": False},
    )
    assert r.status_code == 200, r.text
    sent = fake.acompletion.await_args.kwargs["messages"]
    user_msg = [m for m in sent if m["role"] == "user"][-1]
    assert isinstance(user_msg["content"], list)
    assert any(p.get("type") == "image_url" for p in user_msg["content"])


async def test_stored_attachment_files_are_not_publicly_reachable(dash_env):
    """Uploaded bytes are only served by the admin-authenticated attachment
    routes: no static mount maps the attachment directory, and an anonymous
    client cannot fetch them through the API."""
    from httpx import AsyncClient
    from sqlalchemy import select

    from app.attachments import storage
    from packages.db.models.chat_attachment import ChatAttachment

    client, _, factory = dash_env
    secret = b"confidential attachment body"
    att = await _upload(client, "secret.txt", secret)
    async with factory() as s:
        row = (await s.execute(select(ChatAttachment))).scalar_one()
    storage_name = row.storage_name
    assert storage.path_for(storage_name).read_bytes() == secret

    for path in (
        f"/static/{storage_name}",
        f"/static/attachments/{storage_name}",
        f"/attachments/{storage_name}",
        f"/static/../attachments/{storage_name}",
        f"/{storage_name}",
    ):
        r = await client.get(path)
        assert secret not in r.content, path

    anon = AsyncClient(transport=client._transport, base_url="http://test")
    async with anon:
        for path in (
            f"/api/chat/attachments/{att['id']}",
            f"/api/chat/attachments/{att['id']}/content",
            f"/api/chat/attachments/{att['id']}/thumbnail",
        ):
            r = await anon.get(path)
            assert r.status_code in (401, 403), (path, r.status_code)
            assert secret not in r.content


# ── reasoning effort ───────────────────────────────────────────────────────


def _deploy_o3(fake):
    from packages.litellm_adapter.types import ProviderDeployment

    fake._deployments = [
        ProviderDeployment(model_name=n, litellm_model=f"openai/{n}",
                           api_key="sk-test", provider="openai")
        for n in ("o3", "gpt-4o-mini")
    ]


async def test_reasoning_patch_sets_and_default_clears(dash_env):
    client, _, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    assert convo["reasoning_effort"] is None
    url = f"/api/chat/conversations/{convo['id']}"
    assert (await client.patch(url, json={"reasoning_effort": "High"})).json()["reasoning_effort"] == "high"
    # Omitted leaves it unchanged.
    assert (await client.patch(url, json={"title": "x"})).json()["reasoning_effort"] == "high"
    assert (await client.patch(url, json={"reasoning_effort": "default"})).json()["reasoning_effort"] is None
    r = await client.patch(url, json={"reasoning_effort": "turbo"})
    assert r.status_code == 422


async def test_send_persists_requested_and_effective_and_regenerate_reuses(dash_env):
    client, fake, _ = dash_env
    _deploy_o3(fake)
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "o3", "stream": False, "reasoning_effort": "low"},
    )
    assert r.status_code == 200, r.text
    assert fake.acompletion.await_args.kwargs["model_params"] == {"o3": {"reasoning_effort": "low"}}
    msg = r.json()["message"]
    assert msg["reasoning_requested"] == "low"
    assert msg["reasoning_effective"] == "low"

    data = (await client.get(f"/api/chat/conversations/{convo['id']}")).json()
    assert data["conversation"]["reasoning_effort"] == "low"
    assert data["messages"][0]["reasoning_requested"] == "low"

    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/regenerate",
        json={"model": "o3", "stream": False},
    )
    assert r.status_code == 200, r.text
    assert fake.acompletion.await_args.kwargs["model_params"] == {"o3": {"reasoning_effort": "low"}}

    # The sticky conversation value is used when the message omits it.
    await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "again", "model": "o3", "stream": False},
    )
    assert fake.acompletion.await_args.kwargs["model_params"] == {"o3": {"reasoning_effort": "low"}}


async def test_default_reasoning_sends_no_parameter(dash_env):
    client, fake, _ = dash_env
    _deploy_o3(fake)
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "o3", "stream": False, "reasoning_effort": "default"},
    )
    assert r.status_code == 200, r.text
    kwargs = fake.acompletion.await_args.kwargs
    assert "model_params" not in kwargs and "reasoning_effort" not in kwargs
    assert r.json()["message"]["reasoning_effective"] is None


async def test_unsupported_reasoning_returns_compat_error_code(dash_env):
    client, fake, _ = dash_env
    _deploy_o3(fake)
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "model": "gpt-4o-mini", "stream": False, "reasoning_effort": "high"},
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "unsupported_reasoning_effort"
    fake.acompletion.assert_not_awaited()


async def test_invalid_reasoning_on_send_is_422(dash_env):
    client, _, _ = dash_env
    convo = (await client.post("/api/chat/conversations", json={})).json()
    r = await client.post(
        f"/api/chat/conversations/{convo['id']}/messages",
        json={"content": "hi", "stream": False, "reasoning_effort": "ultra"},
    )
    assert r.status_code == 422
