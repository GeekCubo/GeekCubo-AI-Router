"""Per-endpoint reasoning capability: administrator override + bounded probe.

A scripted OpenAI-compatible gateway stands in for the operator's endpoint.
It can (a) ignore `reasoning_effort` entirely, accepting any value — the
behaviour observed live on a real gateway — (b) validate it, or (c) fail
transiently. No credentials leave the process; nothing is called upstream.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.integration.test_routing_integration import (  # noqa: F401
    _models,
    _provider,
    env,  # noqa: F401  (fixture)
)


class Gateway:
    def __init__(self, mode: str):
        self.mode = mode
        self.requests: list[dict] = []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self._send(200, {"object": "list", "data": [{"id": "m1"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
                gw.requests.append(body)
                effort = body.get("reasoning_effort")
                if gw.mode == "transient" and effort:
                    return self._send(503, {"error": {"message": "at capacity"}})
                if gw.mode == "validating" and effort not in (None, "low", "medium", "high"):
                    return self._send(400, {"error": {"message": "invalid reasoning_effort"}})
                tokens = {"low": 10, "high": 90}.get(effort, 10) if gw.mode == "validating" else 10
                self._send(200, {
                    "id": "c", "object": "chat.completion", "created": 1, "model": body.get("model"),
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "391"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": tokens + 1,
                              "completion_tokens_details": {"reasoning_tokens": tokens}},
                })

            def _send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def stop(self):
        self._srv.shutdown()


@pytest.fixture
def upstream():
    """Replaces the routing-integration upstream: a scripted gateway."""
    gw = Gateway("ignoring")
    yield gw
    gw.stop()


async def _setup(c, gw):
    prov = await _provider(c, gw)
    await _models(c, prov["id"], [("m1", True, 1.0, None)])
    listed = (await c.get("/v1/custom-providers")).json()
    providers = listed if isinstance(listed, list) else listed.get("providers", listed.get("items", []))
    model = next(m for p in providers if p["id"] == prov["id"] for m in p["models"])
    return prov, model


async def test_new_custom_model_is_unknown_and_effort_is_forwarded(env, upstream):  # noqa: F811
    c, gw, _ = env
    prov, model = await _setup(c, gw)
    assert model["reasoning_levels"] is None and model["reasoning_source"] == "unknown"
    r = await c.post("/v1/chat/completions", json={
        "model": f"{prov['slug']}/m1", "reasoning_effort": "high",
        "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200, r.text
    assert gw.requests[-1]["reasoning_effort"] == "high"


async def test_probe_detects_an_endpoint_that_ignores_the_field(env, upstream):  # noqa: F811
    c, gw, _ = env
    prov, model = await _setup(c, gw)
    r = await c.post(f"/v1/custom-providers/{prov['id']}/models/{model['id']}/verify-reasoning")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["conclusive"] is True and out["levels"] == []
    assert out["model"]["reasoning_levels"] == [] and out["model"]["reasoning_source"] == "verified"
    assert len(gw.requests) == 4  # bounded: default, low, high, invalid
    # Now refused instead of silently ignored.
    r = await c.post("/v1/chat/completions", json={
        "model": f"{prov['slug']}/m1", "reasoning_effort": "high",
        "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 400
    assert r.headers["x-geek-error-type"] == "unsupported_reasoning_effort"
    # A second probe straight away is rate limited (paid calls).
    again = await c.post(f"/v1/custom-providers/{prov['id']}/models/{model['id']}/verify-reasoning")
    assert again.status_code == 429


async def test_probe_records_levels_an_endpoint_validates(env, upstream):  # noqa: F811
    c, gw, _ = env
    gw.mode = "validating"
    prov, model = await _setup(c, gw)
    out = (await c.post(f"/v1/custom-providers/{prov['id']}/models/{model['id']}/verify-reasoning")).json()
    assert out["conclusive"] and out["levels"] == ["low", "high"]
    assert out["model"]["reasoning_levels"] == ["low", "high"]


async def test_transient_failure_records_nothing(env, upstream):  # noqa: F811
    c, gw, _ = env
    gw.mode = "transient"
    prov, model = await _setup(c, gw)
    out = (await c.post(f"/v1/custom-providers/{prov['id']}/models/{model['id']}/verify-reasoning")).json()
    assert out["conclusive"] is False and out["error_type"] == "transient"
    assert out["model"]["reasoning_levels"] is None


async def test_administrator_override_wins_and_can_be_cleared(env, upstream):  # noqa: F811
    c, gw, _ = env
    prov, model = await _setup(c, gw)
    url = f"/v1/custom-providers/{prov['id']}/models/{model['id']}"
    r = await c.patch(url, json={"reasoning_levels": ["high", "low"]})
    assert r.status_code == 200, r.text
    assert r.json()["reasoning_levels"] == ["low", "high"]
    assert r.json()["reasoning_source"] == "administrator_override"
    bad = await c.patch(url, json={"reasoning_levels": ["turbo"]})
    assert bad.status_code == 422
    # Auto and the inventory see the override.
    inv = (await c.get("/api/routing/models", params={"scope": "custom"})).json()
    assert inv["models"][0]["reasoning_levels"] == ["low", "high"]
    r = await c.post("/v1/chat/completions", json={
        "model": f"{prov['slug']}/m1", "reasoning_effort": "medium",
        "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 400
    cleared = await c.patch(url, json={"clear_reasoning": True})
    assert cleared.json()["reasoning_levels"] is None


async def test_default_requests_never_probe(env, upstream):  # noqa: F811
    c, gw, _ = env
    prov, _model = await _setup(c, gw)
    await c.post("/v1/chat/completions", json={
        "model": f"{prov['slug']}/m1", "messages": [{"role": "user", "content": "hi"}]})
    assert len(gw.requests) == 1 and "reasoning_effort" not in gw.requests[0]


async def test_probe_does_not_read_sampling_noise_as_support(env, upstream):  # noqa: F811
    """Live regression: a real gateway ignoring the field returned reasoning
    usage 5/5/6/5 for default/low/high/invalid. A one-token wobble must not
    be recorded as 'reasoning usage follows the level'."""
    c, gw, _ = env
    gw.mode = "noisy"
    original = gw._srv.RequestHandlerClass.do_POST

    def noisy(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        gw.requests.append(body)
        tokens = {"high": 6}.get(body.get("reasoning_effort"), 5)
        self._send(200, {"id": "c", "object": "chat.completion", "created": 1, "model": "m1",
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": "391"},
                                      "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 5, "completion_tokens": tokens,
                                   "completion_tokens_details": {"reasoning_tokens": tokens}}})

    gw._srv.RequestHandlerClass.do_POST = noisy
    try:
        prov, model = await _setup(c, gw)
        out = (await c.post(f"/v1/custom-providers/{prov['id']}/models/{model['id']}/verify-reasoning")).json()
    finally:
        gw._srv.RequestHandlerClass.do_POST = original
    assert out["levels"] != ["low", "high"]
    assert out["conclusive"] is True and out["levels"] == []
