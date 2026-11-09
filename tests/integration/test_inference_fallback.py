"""Inference fallback: which failures fail over, which never do, and how
every attempt is accounted for.

A scripted mock upstream answers each model with a configured status, so
fallback behaviour is measured against real HTTP responses. No live providers.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.integration.test_routing_integration import _models, _provider  # noqa: F401


class ScriptedUpstream:
    """OpenAI-compatible upstream with per-model scripted responses.

    `script[model] = status` (200 success, 4xx/5xx error, "timeout" sleeps
    past the client timeout). `calls` records every model attempted, in order.
    """

    def __init__(self) -> None:
        self.script: dict[str, object] = {}
        self.calls: list[str] = []
        self.stream = False
        self._server: ThreadingHTTPServer | None = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        parent = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status: int, payload: dict, ctype="application/json"):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send(200, {"object": "list", "data": []})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                model = body.get("model", "")
                parent.calls.append(model)
                outcome = parent.script.get(model, 200)
                if outcome == "timeout":
                    time.sleep(3)
                    self._send(200, {})
                    return
                if outcome != 200:
                    self._send(int(outcome), {"error": {"message": f"scripted {outcome}", "type": "x"}})
                    return
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for chunk in (
                        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": model,
                         "choices": [{"index": 0, "delta": {"role": "assistant", "content": "ok"}, "finish_reason": None}]},
                        {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": model,
                         "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}},
                    ):
                        self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                self._send(200, {
                    "id": "c", "object": "chat.completion", "created": 1, "model": model,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
                })

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()


@pytest.fixture
def upstream():
    u = ScriptedUpstream()
    u.start()
    try:
        yield u
    finally:
        u.stop()




async def _setup(c, up, specs=(("primary", 1.0), ("backup", 2.0), ("third", 3.0))):
    prov = await _provider(c, up)
    await _models(c, prov["id"], [(m, True, price, 128000) for m, price in specs])
    # cheapest strategy => deterministic order: primary, backup, third.
    await c.put("/v1/routing", json={"strategy": "cheapest"})


async def _auto(c, stream=False):
    return await c.post("/v1/chat/completions", json={
        "model": "auto", "stream": stream,
        "messages": [{"role": "user", "content": "hi"}],
    })


async def test_successful_primary_makes_one_attempt(env):
    c, up, _ = env
    await _setup(c, up)
    r = await _auto(c)
    assert r.status_code == 200
    assert up.calls == ["primary"]


@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_retryable_failure_fails_over(env, status):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = status
    r = await _auto(c)
    assert r.status_code == 200, r.text
    assert up.calls[0] == "primary"
    assert "backup" in up.calls


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_non_retryable_failure_never_fails_over(env, status):
    """Auth failures and invalid requests are not fixed by asking a different
    model; retrying would hide a real problem and could double-bill."""
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = status
    r = await _auto(c)
    assert r.status_code >= 400
    assert up.calls == ["primary"], up.calls


async def test_attempts_are_bounded(env):
    c, up, _ = env
    await _setup(c, up)
    await c.put("/v1/routing", json={"policy": {"fallback": {"enabled": True, "max_attempts": 2}}})
    for m in ("primary", "backup", "third"):
        up.script[m] = 503
    r = await _auto(c)
    assert r.status_code >= 500
    assert len(up.calls) <= 2, up.calls


async def test_fallback_disabled_means_single_attempt(env):
    c, up, _ = env
    await _setup(c, up)
    await c.put("/v1/routing", json={"policy": {"fallback": {"enabled": False}}})
    up.script["primary"] = 503
    r = await _auto(c)
    assert r.status_code >= 500
    assert up.calls == ["primary"], up.calls


async def test_pinned_model_does_not_fail_over(env):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 503
    r = await c.post("/v1/chat/completions", json={
        "model": "apixo/primary", "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code >= 500
    assert set(up.calls) == {"primary"}, up.calls


async def test_streaming_fails_over_before_first_byte(env):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 503
    r = await _auto(c, stream=True)
    assert r.status_code == 200
    assert "data: [DONE]" in r.text
    assert "backup" in up.calls


async def test_fallback_is_recorded_with_the_serving_model(env):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 503
    await _auto(c)
    row = (await c.get("/v1/analytics/recent")).json()["items"][0]
    assert row["fallback_used"] is True
    assert row["routed_model"] == "apixo/primary"
    # Billed at the model that served (backup, $2/1M): 7 tokens => 14 microcents.
    assert 13 <= row["cost_microcents"] <= 14, row


async def test_failed_attempts_are_persisted(env):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 503
    await _auto(c)
    row = (await c.get("/v1/analytics/recent")).json()["items"][0]
    assert row["attempt_count"] == 2
    assert "upstream_error" in (row["attempt_errors"] or "")


async def test_streaming_failover_attempts_are_persisted(env):
    """Same accounting as the blocking path: a stream that failed over before
    its first byte records the failed attempt, not a clean single attempt."""
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 503
    r = await _auto(c, stream=True)
    assert r.status_code == 200
    row = (await c.get("/v1/analytics/recent")).json()["items"][0]
    assert row["attempt_count"] == 2, row
    assert "upstream_error" in (row["attempt_errors"] or ""), row
    assert row["fallback_used"] is True, row


async def test_non_retryable_error_says_so_instead_of_claiming_all_failed(env):
    c, up, _ = env
    await _setup(c, up)
    up.script["primary"] = 401
    r = await _auto(c)
    assert r.status_code >= 400
    assert r.headers["x-geek-routing-diagnosis"] == "non_retryable_failure"
    body = r.json()
    detail = body.get("detail") or (body.get("error") or {}).get("message", "")
    assert detail
    assert "All 3" not in detail
    assert "auth" in detail.lower() or "not recoverable" in detail.lower()
