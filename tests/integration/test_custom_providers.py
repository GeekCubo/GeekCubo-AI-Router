"""Integration tests for custom OpenAI-compatible providers.

Covers CRUD, credential encryption, model registration, base-URL SSRF
guards, credential non-leakage, built-in provider regression, and — via a
mock upstream — real routing, streaming, tool calls, `model="auto"` selection,
and usage accounting against a custom base URL.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# ── mock OpenAI-compatible upstream ─────────────────────────────────────────


class _MockUpstream:
    def __init__(self):
        self.requests: list[dict] = []
        self.stream = False
        self.with_tool_calls = False
        self.model = "gpt-4o"
        self.models_payload: dict | list | str = {
            "object": "list",
            "data": [
                {"id": "gpt-4o", "object": "model", "owned_by": "apixo"},
                {"id": "gpt-4o-mini", "object": "model", "owned_by": "apixo"},
            ],
        }
        self.models_status = 200
        self.redirect_to: str | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _body(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                return json.loads(raw) if raw else None

            def _send(self, status, ctype, data: bytes):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                parent.requests.append({
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "body": None,
                })
                if parent.redirect_to:
                    self.send_response(302)
                    self.send_header("Location", parent.redirect_to)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                payload = parent.models_payload
                if isinstance(payload, (dict, list)):
                    payload = json.dumps(payload)
                data = payload.encode() if isinstance(payload, str) else payload
                self.send_response(parent.models_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                parent.requests.append({
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "body": self._body(),
                })
                if parent.stream:
                    self._sse()
                else:
                    self._json()

            def _message(self) -> dict:
                msg = {"role": "assistant", "content": "hi there"}
                if parent.with_tool_calls:
                    msg["tool_calls"] = [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city":"SF"}'},
                    }]
                return msg

            def _json(self):
                payload = {
                    "id": "chatcmpl-x", "object": "chat.completion", "created": 123,
                    "model": parent.model,
                    "choices": [{"index": 0, "message": self._message(), "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
                }
                self._send(200, "application/json", json.dumps(payload).encode())

            def _sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chunks = [
                    {"id": "chatcmpl-x", "object": "chat.completion.chunk", "created": 123,
                     "model": parent.model,
                     "choices": [{"index": 0, "delta": {"role": "assistant", "content": "hi"}, "finish_reason": None}]},
                    {"id": "chatcmpl-x", "object": "chat.completion.chunk", "created": 123,
                     "model": parent.model,
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}},
                ]
                for c in chunks:
                    self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode())
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


@pytest.fixture
def mock_upstream():
    m = _MockUpstream()
    m.start()
    try:
        yield m
    finally:
        m.stop()


# ── fixtures ────────────────────────────────────────────────────────────────


def _build_app(tmp_sqlite_url, monkeypatch, *, allow_local_hosts: str | None = None):
    monkeypatch.setenv("DATABASE_URL", tmp_sqlite_url)
    if allow_local_hosts is not None:
        monkeypatch.setenv("CUSTOM_PROVIDER_ALLOWED_LOCAL_HOSTS", allow_local_hosts)

    from app import config as cfg
    cfg.get_settings.cache_clear()

    from packages.db.engine import build_engine

    engine = build_engine(tmp_sqlite_url)
    return engine, cfg


@pytest.fixture
async def custom_client(tmp_sqlite_url, monkeypatch, isolated_env):
    """Authed app client for CRUD / security tests (no mock upstream)."""
    engine, _ = _build_app(tmp_sqlite_url, monkeypatch)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from packages.db import session as session_mod
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory

    from app.seed import seed_initial_state
    async with factory() as s:
        seed = await seed_initial_state(s)

    from app.main import create_app
    app = create_app()

    from tests.authkit import dual_client
    c = await dual_client(app, factory, seed.api_key)
    try:
        yield c
    finally:
        await c.aclose()

    await engine.dispose()
    session_mod._session_factory = None


@pytest.fixture
async def routed_client(tmp_sqlite_url, monkeypatch, mock_upstream, isolated_env):
    """Authed app client with a real mock upstream wired as a custom provider."""
    engine, cfg = _build_app(
        tmp_sqlite_url, monkeypatch,
        allow_local_hosts=f"127.0.0.1:{mock_upstream.port}",
    )
    cfg.get_settings.cache_clear()

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from packages.db import session as session_mod
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session_mod._session_factory = factory

    from app.seed import seed_initial_state
    async with factory() as s:
        seed = await seed_initial_state(s)

    from app import router_cache
    router_cache.invalidate_router()

    from app.main import create_app
    app = create_app()

    from tests.authkit import dual_client
    c = await dual_client(app, factory, seed.api_key)
    try:
        yield c, seed.api_key, mock_upstream, cfg
    finally:
        await c.aclose()

    await engine.dispose()
    session_mod._session_factory = None
    router_cache.invalidate_router()


async def _create_apixo(client, base_url: str, *, eligible: bool | None = None, key: str = "sk-apixo-secret-1234567890"):
    payload = {"display_name": "Apixo", "base_url": base_url, "api_key": key}
    if eligible is not None:
        payload["eligible_for_auto"] = eligible
    r = await client.post("/v1/custom-providers", json=payload)
    return r


async def _add_model(client, provider_id: str, *, model_id: str = "gpt-4o"):
    return await client.put(f"/v1/custom-providers/{provider_id}/models", json=[{
        "model_id": model_id, "display_name": "GPT-4o",
        "context_length": 128000,
        "supports_tools": True, "supports_vision": True, "supports_json_mode": True,
        "input_cost_per_million": 1.0, "output_cost_per_million": 2.0,
    }])


# ── CRUD + encryption + no-leak ─────────────────────────────────────────────


async def test_create_requires_https_public_base_url(custom_client):
    for url in (
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://192.168.1.5/v1",
        "http://8.8.8.8/v1",
        "ftp://8.8.8.8/v1",
        "https://user:pass@8.8.8.8/v1",
    ):
        r = await _create_apixo(custom_client, url)
        assert r.status_code == 422, f"{url} should be rejected: {r.text}"


async def test_create_and_list(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "apixo"
    assert body["display_name"] == "Apixo"
    assert body["base_url"] == "https://8.8.8.8/v1"
    assert body["key_prefix"] == "sk-apixo...7890"
    assert body["is_enabled"] is True
    assert body["eligible_for_auto"] is True
    assert "encrypted_key" not in body
    assert "api_key" not in body

    listing = await custom_client.get("/v1/custom-providers")
    assert listing.status_code == 200
    rows = listing.json()["providers"]
    assert len(rows) == 1
    assert rows[0]["slug"] == "apixo"
    assert rows[0]["eligible_for_auto"] is True


@pytest.mark.parametrize("eligible", [False, True])
async def test_saved_auto_preference_survives_unrelated_updates(custom_client, eligible):
    created = await _create_apixo(custom_client, "https://8.8.8.8/v1", eligible=eligible)
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["eligible_for_auto"] is eligible

    for update in (
        {"display_name": "Renamed"},
        {"api_key": "sk-replacement-1234567890"},
        {"api_key": "[REDACTED]"},
        {"is_enabled": False},
        {"is_enabled": True},
    ):
        saved = await custom_client.put(f"/v1/custom-providers/{pid}", json=update)
        assert saved.status_code == 200, saved.text
        assert saved.json()["eligible_for_auto"] is eligible

    listing = await custom_client.get("/v1/custom-providers")
    assert listing.json()["providers"][0]["eligible_for_auto"] is eligible


async def test_explicit_auto_opt_out_persists(custom_client):
    created = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = created.json()["id"]
    saved = await custom_client.put(
        f"/v1/custom-providers/{pid}", json={"eligible_for_auto": False}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["eligible_for_auto"] is False
    saved = await custom_client.put(f"/v1/custom-providers/{pid}", json={"display_name": "Renamed"})
    assert saved.json()["eligible_for_auto"] is False
    listing = await custom_client.get("/v1/custom-providers")
    assert listing.json()["providers"][0]["eligible_for_auto"] is False


async def test_credential_never_leaks(custom_client):
    await _create_apixo(custom_client, "https://8.8.8.8/v1")
    r = await custom_client.get("/v1/custom-providers")
    assert "sk-apixo-secret-1234567890" not in r.text
    assert "sk-apixo-secret" not in r.text


async def test_credential_encrypted_at_rest(custom_client, tmp_sqlite_url):
    await _create_apixo(custom_client, "https://8.8.8.8/v1")

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.auth.encryption import decrypt_credential
    from packages.db.engine import build_engine
    from packages.db.models.custom_provider import CustomProvider

    engine = build_engine(tmp_sqlite_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        rows = (await s.execute(select(CustomProvider))).scalars().all()
    await engine.dispose()

    assert len(rows) == 1
    blob = rows[0].encrypted_key
    assert b"sk-apixo-secret-1234567890" not in blob
    assert decrypt_credential(blob) == "sk-apixo-secret-1234567890"


async def test_duplicate_slug_rejected(custom_client):
    await _create_apixo(custom_client, "https://8.8.8.8/v1")
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    assert r.status_code == 409, r.text


async def test_update_and_delete(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]

    upd = await custom_client.put(f"/v1/custom-providers/{pid}", json={"is_enabled": False})
    assert upd.status_code == 200, upd.text
    assert upd.json()["is_enabled"] is False

    # placeholder api_key must be a no-op (no overwrite)
    upd2 = await custom_client.put(f"/v1/custom-providers/{pid}", json={"api_key": "[REDACTED]"})
    assert upd2.status_code == 200
    assert upd2.json()["key_prefix"] == "sk-apixo...7890"

    d = await custom_client.delete(f"/v1/custom-providers/{pid}")
    assert d.status_code == 204
    listing = await custom_client.get("/v1/custom-providers")
    assert listing.json()["providers"] == []


async def test_model_registration_and_listing(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]

    add = await _add_model(custom_client, pid)
    assert add.status_code == 200, add.text
    models = add.json()["models"]
    assert len(models) == 1
    assert models[0]["model_id"] == "gpt-4o"
    assert models[0]["supports_tools"] is True
    assert models[0]["input_cost_per_token"] == pytest.approx(1e-6)


async def test_custom_model_appears_in_v1_models_when_enabled(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]
    await _add_model(custom_client, pid)

    listing = await custom_client.get("/v1/models")
    ids = [m["id"] for m in listing.json()["data"]]
    assert "apixo/gpt-4o" in ids
    owned = next(m for m in listing.json()["data"] if m["id"] == "apixo/gpt-4o")
    assert owned["owned_by"] == "apixo"


async def test_custom_model_usable_in_key_allowlist(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]
    await _add_model(custom_client, pid)

    r = await custom_client.post("/v1/keys", json={"name": "k", "model_allowlist": ["apixo/gpt-4o"]})
    assert r.status_code == 201, r.text

    bad = await custom_client.post("/v1/keys", json={"name": "k2", "model_allowlist": ["apixo/nope"]})
    assert bad.status_code == 422


async def test_builtin_provider_regression(custom_client, monkeypatch):
    """Adding custom providers must not disturb the built-in provider key path."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    from app import config as cfg
    cfg.get_settings.cache_clear()

    r = await custom_client.put("/v1/providers/openai", json={"api_key": "sk-db-openai"})
    assert r.status_code == 200, r.text

    await _create_apixo(custom_client, "https://8.8.8.8/v1")

    listing = await custom_client.get("/v1/providers")
    provs = {p["provider"]: p for p in listing.json()["providers"]}
    assert provs["openai"]["source"] == "db"
    assert provs["openai"]["key_prefix"] == "sk...ai"  # masked, no leak

    models = await custom_client.get("/v1/models")
    ids = [m["id"] for m in models.json()["data"]]
    assert "gpt-4o" in ids  # built-in catalog still present

    from app.custom_providers import merged_catalog_by_id
    from packages.db import session as session_mod

    async with session_mod._session_factory() as db:
        auto_catalog = await merged_catalog_by_id(db)
    assert "gpt-4o" in auto_catalog


# ── routing / streaming / tool calls against the mock upstream ──────────────


async def test_pinned_custom_model_routes_to_configured_url(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await _add_model(client, pid)

    resp = await client.post("/v1/chat/completions", json={
        "model": "apixo/gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "hi there"
    assert body["model"] == "gpt-4o"

    assert len(upstream.requests) == 1
    req = upstream.requests[0]
    assert req["path"] == "/v1/chat/completions"
    # Credential went to OUR configured URL, not OpenAI, and with our key.
    assert req["auth"] == "Bearer sk-apixo-secret-1234567890"
    assert req["body"]["model"] == "gpt-4o"


async def test_custom_model_streaming(routed_client):
    client, _key, upstream, _cfg = routed_client
    upstream.stream = True
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await _add_model(client, pid)

    async with client.stream("POST", "/v1/chat/completions", json={
        "model": "apixo/gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = "".join([chunk async for chunk in resp.aiter_text()])
    assert "[DONE]" in text
    assert "hi" in text


async def test_custom_model_tool_calls(routed_client):
    client, _key, upstream, _cfg = routed_client
    upstream.with_tool_calls = True
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await _add_model(client, pid)

    resp = await client.post("/v1/chat/completions", json={
        "model": "apixo/gpt-4o",
        "messages": [{"role": "user", "content": "what is the weather?"}],
        "tools": [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {}}}}],
        "tool_choice": "auto",
    })
    assert resp.status_code == 200, resp.text
    msg = resp.json()["choices"][0]["message"]
    assert "tool_calls" in msg
    assert msg["tool_calls"][0]["function"]["name"] == "get_weather"

    req = upstream.requests[0]["body"]
    assert req.get("tools") is not None


async def test_auto_routing_uses_eligible_custom_model(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url, eligible=True)
    pid = r.json()["id"]
    await _add_model(client, pid)

    resp = await client.post("/v1/chat/completions", json={
        "model": "auto",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}],
    })
    assert resp.status_code == 200, resp.text
    assert resp.headers["x-geek-requested-model"] == "auto"
    # The eligible custom model was selected: the mock upstream (not any
    # other provider) actually served the request with the wire model id.
    assert len(upstream.requests) >= 1
    assert upstream.requests[0]["body"]["model"] == "gpt-4o"
    assert "gpt-4o" in resp.headers["x-geek-resolved-model"]


async def test_auto_routing_ignores_not_eligible_custom_model(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url, eligible=False)
    pid = r.json()["id"]
    await _add_model(client, pid)

    resp = await client.post("/v1/chat/completions", json={
        "model": "auto",
        "messages": [{"role": "user", "content": "hi"}],
    })
    # No other deployable provider → auto finds nothing capable.
    assert resp.status_code in (422, 403), resp.text
    assert not upstream.requests  # never reached the custom provider via auto


async def test_usage_accounting(routed_client, tmp_sqlite_url):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await _add_model(client, pid)

    await client.post("/v1/chat/completions", json={
        "model": "apixo/gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
    })

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from packages.db.engine import build_engine
    from packages.db.models.request_log import RequestLog

    engine = build_engine(tmp_sqlite_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        rows = (await s.execute(select(RequestLog))).scalars().all()
    await engine.dispose()

    assert len(rows) == 1
    log = rows[0]
    assert log.model_requested == "apixo/gpt-4o"
    assert log.provider == "apixo"
    assert log.input_tokens == 4
    assert log.output_tokens == 3
    # Operator pricing: 4 * $1/1M + 3 * $2/1M = $10e-6 = 10 microcents.
    assert log.cost_microcents == 10


async def test_saved_connection_test_reports_models_without_leaking_key(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    t = await client.post(f"/v1/custom-providers/{pid}/test", json={})
    assert t.status_code == 200, t.text
    body = t.json()
    assert body["ok"] is True
    assert "gpt-4o" in body.get("models", [])
    assert "sk-apixo-secret" not in t.text


# ── model discovery (Fetch Available Models) ────────────────────────────────


async def test_fetch_models_returns_parsed_catalog(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    ids = {m["id"] for m in body["models"]}
    assert ids == {"gpt-4o", "gpt-4o-mini"}
    assert body["registered_model_ids"] == []
    assert body["fetched_at"] is not None
    assert "sk-apixo-secret" not in resp.text

    # last_models_fetched_at is now stamped on the provider listing
    listing = await client.get("/v1/custom-providers")
    row = listing.json()["providers"][0]
    assert row["last_models_fetched_at"] is not None


async def test_fetch_models_preserves_existing_config_on_add(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    # Register one model manually with explicit pricing/caps.
    await client.put(f"/v1/custom-providers/{pid}/models", json=[{
        "model_id": "gpt-4o", "display_name": "GPT-4o",
        "context_length": 128000, "supports_tools": True,
        "input_cost_per_million": 1.0, "output_cost_per_million": 2.0,
    }])

    # Add the OTHER discovered model via the additive endpoint.
    resp = await client.post(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": "gpt-4o-mini", "display_name": "gpt-4o-mini"},
    ])
    assert resp.status_code == 200, resp.text
    assert resp.json()["added"] == 1

    listing = await client.get("/v1/custom-providers")
    models = {m["model_id"]: m for m in listing.json()["providers"][0]["models"]}
    assert set(models) == {"gpt-4o", "gpt-4o-mini"}
    # Existing model's config was untouched.
    assert models["gpt-4o"]["supports_tools"] is True
    assert models["gpt-4o"]["input_cost_per_token"] == pytest.approx(1e-6)
    # Newly discovered model has unknown (zero) pricing + no invented caps.
    assert models["gpt-4o-mini"]["supports_tools"] is False
    assert models["gpt-4o-mini"]["input_cost_per_token"] == 0


async def test_add_models_is_idempotent_no_duplicates(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    first = await client.post(f"/v1/custom-providers/{pid}/models", json=[{"model_id": "gpt-4o"}])
    assert first.json()["added"] == 1
    second = await client.post(f"/v1/custom-providers/{pid}/models", json=[{"model_id": "gpt-4o"}])
    assert second.json()["added"] == 0

    listing = await client.get("/v1/custom-providers")
    assert len(listing.json()["providers"][0]["models"]) == 1


async def test_fetch_models_empty_catalog_is_clear_error(routed_client):
    client, _key, upstream, _cfg = routed_client
    upstream.models_payload = {"object": "list", "data": []}
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error_type"] == "malformed_response"
    assert "empty" in body["error"]


async def test_fetch_models_malformed_response(routed_client):
    client, _key, upstream, _cfg = routed_client
    upstream.models_payload = "not-json"
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    body = resp.json()
    assert body["ok"] is False
    assert body["error_type"] == "malformed_response"


async def test_fetch_models_unauthorized_error(routed_client):
    client, _key, upstream, _cfg = routed_client
    upstream.models_status = 401
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    body = resp.json()
    assert body["ok"] is False
    assert body["error_type"] == "auth_error"


async def test_fetch_models_refuses_redirect_to_private(routed_client):
    client, _key, upstream, _cfg = routed_client
    # The upstream redirects to a private address; discovery must refuse to
    # follow it (credential never forwarded to the redirect target).
    upstream.redirect_to = "http://169.254.169.254/latest"
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    body = resp.json()
    assert body["ok"] is False
    assert body["error_type"] == "redirect_unsafe"


async def _seed_catalog(entries: dict[str, dict]) -> None:
    """Insert a litellm catalog source so discovery previews resolve offline."""
    from app.seed import DEFAULT_WORKSPACE_ID
    from packages.db import session as session_mod
    from packages.db.models.metadata_source import MetadataSource

    async with session_mod._session_factory() as s:
        s.add(MetadataSource(
            workspace_id=DEFAULT_WORKSPACE_ID,
            key="litellm",
            name="LiteLLM",
            kind="litellm",
            is_builtin=True,
            is_enabled=True,
            priority=1,
            cache=entries,
            entry_count=len(entries),
        ))
        await s.commit()


def _catalog_entry(*, context=128000, tools=True, inp=2.5, outp=10.0):
    return {
        "price_state": "priced",
        "input_per_million": inp, "output_per_million": outp,
        "cache_read_per_million": None, "cache_write_per_million": None,
        "context": context, "tools": tools, "vision": True,
        "json_mode": None, "json_schema": True,
    }


async def test_fetch_models_previews_catalog_resolution(routed_client):
    client, _key, upstream, _cfg = routed_client
    await _seed_catalog({
        "openai/gpt-4o": _catalog_entry(),
        "azure/gpt-4o": _catalog_entry(inp=3.0),
        "openai/gpt-4o-mini": _catalog_entry(),
    })
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/fetch-models", json={"force": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    previews = {m["id"]: m["preview"] for m in body["models"]}

    # gpt-4o exists under two vendors → ambiguous, no guess.
    assert previews["gpt-4o"]["status"] == "ambiguous"
    assert previews["gpt-4o"]["catalog_key"] is None
    assert set(previews["gpt-4o"]["candidates"]) == {"openai/gpt-4o", "azure/gpt-4o"}
    # gpt-4o-mini has one bare match → resolved with inherited metadata.
    assert previews["gpt-4o-mini"]["status"] == "resolved"
    assert previews["gpt-4o-mini"]["catalog_key"] == "openai/gpt-4o-mini"
    assert body["preview_summary"] == {"resolved": 1, "ambiguous": 1}


async def test_registering_with_catalog_key_resolves_ambiguous_id(routed_client):
    client, _key, upstream, _cfg = routed_client
    await _seed_catalog({
        "openai/gpt-4o": _catalog_entry(inp=2.5),
        "azure/gpt-4o": _catalog_entry(inp=3.0),
    })
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": "gpt-4o", "display_name": "gpt-4o", "catalog_key": "azure/gpt-4o"},
    ])
    assert resp.status_code == 200, resp.text

    listing = await client.get("/v1/custom-providers")
    model = next(
        m for m in listing.json()["providers"][0]["models"] if m["model_id"] == "gpt-4o"
    )
    assert model["catalog_key"] == "azure/gpt-4o"
    assert model["match_status"] == "resolved"
    assert model["context_length"] == 128000
    assert model["reference_input_cost_per_million"] == pytest.approx(3.0)
    # Reference pricing never becomes a confirmed custom price.
    assert model["price_state"] == "unknown"


async def test_add_selected_resolves_each_field_independently_and_persists(routed_client):
    client, _key, upstream, _cfg = routed_client
    entry = _catalog_entry(context=64000, tools=True)
    entry.update({"price_state": "unknown", "input_per_million": None,
                  "output_per_million": None, "json_mode": None, "json_schema": False})
    await _seed_catalog({
        "apixo/vis-tool": entry,
        "openai/gpt-4o": _catalog_entry(),
        "azure/gpt-4o": _catalog_entry(inp=3.0),
    })
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    resp = await client.post(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": "vis-tool"}, {"model_id": "gpt-4o"},
    ])
    assert resp.status_code == 200, resp.text

    listing = await client.get("/v1/custom-providers")
    models = {m["model_id"]: m for m in listing.json()["providers"][0]["models"]}
    vt = models["vis-tool"]
    assert vt["capabilities"] == {"tools": "supported", "vision": "supported", "json_mode": "unknown", "json_schema": "unsupported"}
    assert (vt["supports_tools"], vt["supports_vision"], vt["supports_json_mode"], vt["supports_json_schema"]) == (True, True, False, False)
    assert vt["capability_sources"] == {"tools": "litellm", "vision": "litellm", "json_mode": None, "json_schema": "litellm"}
    assert vt["context_length"] == 64000
    assert vt["reference_input_cost_per_million"] is None
    assert vt["price_state"] == "unknown"

    amb = models["gpt-4o"]
    assert amb["match_status"] == "ambiguous"
    assert amb["capabilities"] == {"tools": "unknown", "vision": "unknown", "json_mode": "unknown", "json_schema": "unknown"}
    assert not (amb["supports_tools"] or amb["supports_vision"] or amb["supports_json_mode"] or amb["supports_json_schema"])
    assert amb["context_length"] is None
    assert amb["reference_input_cost_per_million"] is None


async def test_capability_overrides_survive_bulk_resolve(routed_client):
    client, _key, upstream, _cfg = routed_client
    await _seed_catalog({"apixo/m1": _catalog_entry()})
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await client.post(f"/v1/custom-providers/{pid}/models", json=[{"model_id": "m1"}])
    listing = await client.get("/v1/custom-providers")
    row_id = listing.json()["providers"][0]["models"][0]["id"]

    patch = await client.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={
        "capabilities": {"tools": "unknown", "vision": "unsupported"},
    })
    assert patch.status_code == 200, patch.text
    bulk = await client.post(f"/v1/custom-providers/{pid}/models/bulk", json={
        "action": "resolve_metadata", "model_ids": [row_id],
    })
    assert bulk.status_code == 200, bulk.text

    model = (await client.get("/v1/custom-providers")).json()["providers"][0]["models"][0]
    assert model["capabilities"] == {"tools": "unknown", "vision": "unsupported", "json_mode": "unknown", "json_schema": "supported"}
    assert model["capability_sources"]["tools"] == "administrator_override"
    # Catalog structured-output evidence maps to JSON Schema; JSON mode has
    # no source here and stays unknown.
    assert model["capability_sources"]["json_schema"] == "litellm"
    assert model["supports_tools"] is False and model["supports_vision"] is False


async def test_registered_model_exposes_match_status(routed_client):
    client, _key, upstream, _cfg = routed_client
    await _seed_catalog({})  # explicit empty catalog suppresses the bundled fallback
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]

    await client.put(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": "gpt-4o", "display_name": "GPT-4o"},
    ])
    listing = await client.get("/v1/custom-providers")
    model = listing.json()["providers"][0]["models"][0]
    # No catalog entry → unmatched, not silently "resolved".
    assert model["match_status"] == "unmatched"


# ── namespacing across multiple aggregators ─────────────────────────────────


async def test_two_providers_same_model_id_are_namespaced(routed_client):
    client, _key, upstream, _cfg = routed_client
    a = await _create_apixo(client, upstream.base_url)
    pid_a = a.json()["id"]
    await _add_model(client, pid_a)

    # Second provider, same upstream model id "gpt-4o".
    b = await client.post("/v1/custom-providers", json={
        "display_name": "Other", "base_url": upstream.base_url,
        "api_key": "sk-other-1234567890", "eligible_for_auto": False,
    })
    pid_b = b.json()["id"]
    await client.put(f"/v1/custom-providers/{pid_b}/models", json=[{
        "model_id": "gpt-4o", "display_name": "GPT-4o (Other)",
        "input_cost_per_million": 3.0, "output_cost_per_million": 4.0,
    }])

    listing = await client.get("/v1/models")
    ids = [m["id"] for m in listing.json()["data"]]
    assert "apixo/gpt-4o" in ids
    assert "other/gpt-4o" in ids

    # Pinning either namespaced id routes to the configured URL (both mock).
    for name in ("apixo/gpt-4o", "other/gpt-4o"):
        resp = await client.post("/v1/chat/completions", json={
            "model": name, "messages": [{"role": "user", "content": "hi"}],
        })
        assert resp.status_code == 200, f"{name}: {resp.text}"


async def test_disable_provider_removes_models_from_listing(routed_client):
    client, _key, upstream, _cfg = routed_client
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await _add_model(client, pid)

    await client.put(f"/v1/custom-providers/{pid}", json={"is_enabled": False})

    listing = await client.get("/v1/models")
    ids = [m["id"] for m in listing.json()["data"]]
    assert "apixo/gpt-4o" not in ids


# ── metadata / pricing / bulk model administration ──────────────────────────


async def test_model_metadata_patch_and_bulk_actions(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]
    created = await _add_model(custom_client, pid)
    model = created.json()["models"][0]
    row_id = model["id"]
    assert model["price_state"] == "custom"
    assert model["input_cost_per_million"] == 1.0
    assert model["output_cost_per_million"] == 2.0
    assert model["capabilities"]["tools"] == "supported"

    patch = await custom_client.patch(
        f"/v1/custom-providers/{pid}/models/{row_id}",
        json={
            "catalog_key": "openai/gpt-4o",
            "capabilities": {"vision": "unsupported", "json_mode": "unknown"},
            "reference_input_cost_per_million": 2.5,
            "reference_output_cost_per_million": 10.0,
            "context_length": 64000,
            "is_enabled": False,
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["catalog_key"] == "openai/gpt-4o"
    assert body["reference_input_cost_per_million"] == 2.5
    assert body["capabilities"]["vision"] == "unsupported"
    assert body["capabilities"]["json_mode"] == "unknown"
    assert body["context_length"] == 64000
    assert body["is_enabled"] is False

    bulk = await custom_client.post(
        f"/v1/custom-providers/{pid}/models/bulk",
        json={"action": "enable", "model_ids": [row_id]},
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json() == {"updated": 1, "action": "enable"}

    bulk = await custom_client.post(
        f"/v1/custom-providers/{pid}/models/bulk",
        json={
            "action": "restore_metadata",
            "model_ids": [row_id],
            "capabilities": {"tools": "unknown", "vision": "supported"},
        },
    )
    assert bulk.status_code == 200, bulk.text
    listing = await custom_client.get("/v1/custom-providers")
    model = listing.json()["providers"][0]["models"][0]
    assert model["is_enabled"] is True
    assert model["capabilities"]["tools"] == "unknown"
    assert model["capabilities"]["vision"] == "supported"
    # Vendor reference pricing is an estimate and never overwrites the
    # confirmed custom-provider rate.
    assert model["price_state"] == "custom"
    assert model["input_cost_per_million"] == 1.0

    bulk = await custom_client.post(
        f"/v1/custom-providers/{pid}/models/bulk",
        json={"action": "remove", "model_ids": [row_id]},
    )
    assert bulk.status_code == 200, bulk.text
    listing = await custom_client.get("/v1/custom-providers")
    assert listing.json()["providers"][0]["models"] == []


async def test_full_model_set_preserves_manual_reference_and_enabled_state(custom_client):
    r = await _create_apixo(custom_client, "https://8.8.8.8/v1")
    pid = r.json()["id"]
    created = await _add_model(custom_client, pid)
    model = created.json()["models"][0]
    row_id = model["id"]

    await custom_client.patch(
        f"/v1/custom-providers/{pid}/models/{row_id}",
        json={
            "reference_input_cost_per_million": 4.0,
            "reference_output_cost_per_million": 8.0,
            "is_enabled": False,
        },
    )

    saved = await custom_client.put(
        f"/v1/custom-providers/{pid}/models",
        json=[{
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 2.0,
        }],
    )
    assert saved.status_code == 200, saved.text
    model = saved.json()["models"][0]
    assert model["id"] == row_id
    assert model["is_enabled"] is False
    assert model["reference_input_cost_per_million"] == 4.0
    assert model["reference_output_cost_per_million"] == 8.0


async def test_diff_save_and_clear_preserve_other_overrides(custom_client, monkeypatch):
    from app import model_metadata as mm

    async def sources(_db):
        return [{"key": "mock", "entries": {"vendor/gpt-4o": {
            "context": 128000, "tools": True, "input_per_million": 2.5,
            "output_per_million": 10, "price_state": "reference",
        }}}]

    monkeypatch.setattr(mm, "load_enabled_sources", sources)
    pid = (await _create_apixo(custom_client, "https://8.8.8.8/v1")).json()["id"]
    model = (await _add_model(custom_client, pid)).json()["models"][0]
    url = f"/v1/custom-providers/{pid}/models/{model['id']}"
    overrides = {
        "capabilities": {"tools": "unknown", "vision": "unsupported"},
        "context_length": 64000,
        "reference_input_cost_per_million": 4,
        "reference_output_cost_per_million": 8,
    }
    before = (await custom_client.patch(url, json=overrides)).json()
    saved = await custom_client.patch(url, json={"display_name": "Renamed"})
    assert saved.status_code == 200
    assert saved.json()["metadata"] == before["metadata"]
    assert saved.json()["input_cost_per_million"] == before["input_cost_per_million"]
    cleared = (await custom_client.patch(url, json={"clear_context": True})).json()
    assert cleared["context_length"] == 128000
    assert cleared["metadata"]["context"]["manual"] is False
    assert cleared["metadata"]["reference"] == before["metadata"]["reference"]
    assert cleared["capability_sources"] == before["capability_sources"]
    await custom_client.patch(url, json={"context_length": 32000})
    cleared = (await custom_client.patch(url, json={"clear_reference_price": True})).json()
    assert cleared["reference_input_cost_per_million"] == 2.5
    assert cleared["reference_price_state"] == "reference"
    assert cleared["context_length"] == 32000
    assert cleared["metadata"]["context"]["manual"] is True
    assert cleared["capability_sources"] == before["capability_sources"]
    assert cleared["input_cost_per_million"] == before["input_cost_per_million"]


async def test_bulk_resolve_statuses_and_override_provenance(custom_client, monkeypatch):
    from app import model_metadata as mm

    async def sources(_db):
        return [{"key": "mock", "entries": {
            "vendor/known": {"context": 128000, "tools": True},
            "vendor/shared": {"tools": True},
            "other/shared": {"tools": False},
        }}]

    monkeypatch.setattr(mm, "load_enabled_sources", sources)
    pid = (await _create_apixo(custom_client, "https://8.8.8.8/v1")).json()["id"]
    response = await custom_client.post(f"/v1/custom-providers/{pid}/models", json=[
        {"model_id": mid} for mid in ("known", "shared", "missing", "broken")
    ])
    models = {m["model_id"]: m for m in response.json()["provider"]["models"]}
    for mid in ("known", "shared", "missing"):
        response = await custom_client.patch(
            f"/v1/custom-providers/{pid}/models/{models[mid]['id']}",
            json={"context_length": 42, "capabilities": {"tools": "unknown"},
                  "reference_input_cost_per_million": 7, "custom_input_cost_per_million": 3},
        )
        models[mid] = response.json()
    resolve = mm.resolve_one

    def resolve_mock(slug, model, sources):
        if model.model_id == "broken":
            model.context_length = 999
            raise ValueError("mock failure")
        return resolve(slug, model, sources)

    monkeypatch.setattr(mm, "resolve_one", resolve_mock)
    response = await custom_client.post(f"/v1/custom-providers/{pid}/models/bulk", json={
        "action": "resolve_metadata", "model_ids": [m["id"] for m in models.values()],
    })
    assert response.status_code == 200, response.text
    assert response.json()["summary"] == dict(resolved=1, ambiguous=1, unmatched=1, failed=1)
    results = {r["id"]: r for r in response.json()["results"]}
    assert results[models["shared"]["id"]]["candidates"] == ["other/shared", "vendor/shared"]
    listing = (await custom_client.get("/v1/custom-providers")).json()["providers"][0]["models"]
    for m in listing:
        if m["model_id"] == "broken":
            assert m["context_length"] is None
            continue
        before = models[m["model_id"]]
        for key in ("manual", "reference", "context", "capabilities", "custom"):
            assert m["metadata"][key] == before["metadata"][key]
        assert m["input_cost_per_million"] == 3
        if m["model_id"] == "shared":
            assert m["catalog_key"] is None


async def test_catalog_state_clears_capability_override(routed_client):
    client, _key, upstream, _cfg = routed_client
    await _seed_catalog({"apixo/m1": _catalog_entry()})
    r = await _create_apixo(client, upstream.base_url)
    pid = r.json()["id"]
    await client.post(f"/v1/custom-providers/{pid}/models", json=[{"model_id": "m1"}])
    row_id = (await client.get("/v1/custom-providers")).json()["providers"][0]["models"][0]["id"]

    await client.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={"capabilities": {"tools": "unsupported"}})
    resp = await client.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={"capabilities": {"tools": "catalog"}})
    assert resp.status_code == 200, resp.text
    model = (await client.get("/v1/custom-providers")).json()["providers"][0]["models"][0]
    assert model["capabilities"]["tools"] == "supported"
    assert model["capability_sources"]["tools"] == "litellm"

    bad = await client.patch(f"/v1/custom-providers/{pid}/models/{row_id}", json={"capabilities": {"tools": "maybe"}})
    assert bad.status_code == 422
