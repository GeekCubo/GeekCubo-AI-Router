"""Unit tests for the Local AI Connect connector package.

Covers the on-disk config, the local adapter HTTP conversation (via an httpx
mock transport, no real server), the WebSocket frame dispatch, and the
protocol copy staying byte-identical to the server's.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import httpx
import pytest

from geekcubo_connector import protocol
from geekcubo_connector.adapters import (
    ADAPTER_CLASSES,
    AdapterError,
    BaseAdapter,
    OllamaAdapter,
    build_adapter,
)
from geekcubo_connector.adapters.base import ModelEntry
from geekcubo_connector.adapters.openai_compat import OpenAICompatibleAdapter
from geekcubo_connector.client import Connector, _agent_url
from geekcubo_connector.config import (
    ConnectorConfig,
    config_path,
    load_config,
    save_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── protocol drift guard ───────────────────────────────────────────────────


def test_vendored_protocol_matches_server():
    server = (REPO_ROOT / "app" / "local_connect" / "protocol.py").read_text(encoding="utf-8")
    vendored = (REPO_ROOT / "geekcubo_connector" / "protocol.py").read_text(encoding="utf-8")
    assert server == vendored, "geekcubo_connector/protocol.py drifted from the server copy"


# ── config ─────────────────────────────────────────────────────────────────


def test_config_round_trip_and_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("GEEKCUBO_CONNECTOR_CONFIG", str(tmp_path / "cfg" / "config.json"))
    config = ConnectorConfig(
        server="https://chat.example.com",
        credential="lc-secret",
        machine_id="m-1",
        display_name="Workstation",
        adapters=["ollama"],
        adapter_urls={"ollama": "http://127.0.0.1:11434"},
    )
    target = save_config(config)
    assert target.exists()
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600

    loaded = load_config()
    assert loaded is not None
    assert loaded.server == "https://chat.example.com"
    assert loaded.credential == "lc-secret"
    assert loaded.adapters == ["ollama"]
    assert loaded.adapter_urls == {"ollama": "http://127.0.0.1:11434"}


def test_load_config_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("GEEKCUBO_CONNECTOR_CONFIG", str(tmp_path / "absent.json"))
    assert load_config() is None
    assert config_path() == tmp_path / "absent.json"


def test_config_rejects_empty_server_on_load(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    target.write_text(json.dumps({"server": "", "credential": "x"}), encoding="utf-8")
    monkeypatch.setenv("GEEKCUBO_CONNECTOR_CONFIG", str(target))
    assert load_config() is None


def test_server_trailing_slash_stripped_on_load(tmp_path, monkeypatch):
    target = tmp_path / "config.json"
    target.write_text(json.dumps({"server": "https://x.example.com/"}), encoding="utf-8")
    monkeypatch.setenv("GEEKCUBO_CONNECTOR_CONFIG", str(target))
    loaded = load_config()
    assert loaded is not None
    assert loaded.server == "https://x.example.com"


# ── URL derivation ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "server,expected",
    [
        ("https://chat.example.com", "wss://chat.example.com/api/local-connect/agent"),
        ("http://127.0.0.1:8080/", "ws://127.0.0.1:8080/api/local-connect/agent"),
        ("chat.example.com", "wss://chat.example.com/api/local-connect/agent"),
        ("ws://host:1", "ws://host:1/api/local-connect/agent"),
    ],
)
def test_agent_url(server, expected):
    assert _agent_url(server) == expected


# ── adapter registry ───────────────────────────────────────────────────────


def test_registry_has_all_protocol_adapters():
    assert set(ADAPTER_CLASSES) == set(protocol.ADAPTERS)


def test_build_unknown_adapter_raises():
    with pytest.raises(AdapterError):
        build_adapter("nope")


def _patch_client(adapter: BaseAdapter, handler) -> None:
    transport = httpx.MockTransport(handler)

    def _client(*, timeout: float = 3.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=adapter.base_url, transport=transport, timeout=timeout)

    adapter._client = _client  # type: ignore[method-assign]


# ── Ollama adapter ─────────────────────────────────────────────────────────


async def test_ollama_available_and_models():
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "llama3.1:8b",
                        "details": {
                            "family": "llama",
                            "parameter_size": "8B",
                            "quantization_level": "Q4_0",
                        },
                        "size": 4_900_000_000,
                    }
                ]
            },
        )

    _patch_client(adapter, handler)
    assert await adapter.available() is True
    models = await adapter.list_models()
    assert len(models) == 1
    entry = models[0]
    assert entry.model_key == "llama3.1:8b"
    assert entry.adapter == "ollama"
    assert entry.family == "llama"
    assert entry.parameter_count == "8B"
    assert entry.quantization == "Q4_0"


@pytest.mark.parametrize("capabilities", [["completion", "vision"], ["completion"], None])
async def test_ollama_vision_requires_reported_capability(capabilities):
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "vision-model"}]})
        assert request.url.path == "/api/show"
        assert json.loads(request.content) == {"model": "vision-model"}
        if capabilities is None:
            return httpx.Response(404)
        return httpx.Response(200, json={"capabilities": capabilities})

    _patch_client(adapter, handler)
    models = await adapter.list_models()
    assert models[0].supports_vision is (capabilities is not None and "vision" in capabilities)
    assert models[0].supports_tools is False


async def test_ollama_stream_chat_converts_openai_images():
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["messages"] == [{
            "role": "user",
            "content": "describe",
            "images": ["aGVsbG8="],
        }]
        return httpx.Response(200, content=b'{"done":true}\n')

    _patch_client(adapter, handler)
    events = [e async for e in adapter.stream_chat(
        model_key="llava", messages=[{"role": "user", "content": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}},
        ]}], params={})]
    assert events[-1]["done"] is True


@pytest.mark.parametrize("url", ["https://example.com/image.png", "data:image/png", "data:image/png;base64,"])
async def test_ollama_rejects_unsupported_images_before_http(url):
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid image content must not reach Ollama")

    _patch_client(adapter, handler)
    with pytest.raises(AdapterError):
        [event async for event in adapter.stream_chat(
            model_key="vision", messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": url}},
            ]}], params={}
        )]


async def test_ollama_stream_chat():
    adapter = OllamaAdapter()
    lines = [
        {"message": {"content": "Hel"}, "done": False},
        {"message": {"content": "lo"}, "done": False},
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 2,
        },
    ]
    body = "\n".join(json.dumps(line) for line in lines) + "\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "llama3.1:8b"
        assert payload["stream"] is True
        return httpx.Response(200, content=body.encode())

    _patch_client(adapter, handler)
    events = [e async for e in adapter.stream_chat(model_key="llama3.1:8b", messages=[{"role": "user", "content": "hi"}], params={"temperature": 0.2})]
    deltas = "".join(e.get("delta", "") for e in events)
    assert deltas == "Hello"
    done = [e for e in events if e.get("done")]
    assert done and done[0]["usage"] == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}


async def test_ollama_http_error_is_adapter_error():
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    _patch_client(adapter, handler)
    with pytest.raises(AdapterError):
        [e async for e in adapter.stream_chat(model_key="m", messages=[], params={})]


async def test_ollama_unavailable_returns_false():
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    _patch_client(adapter, handler)
    assert await adapter.available() is False


# ── OpenAI-compatible adapter ──────────────────────────────────────────────


async def test_openai_compat_models():
    adapter = OpenAICompatibleAdapter(base_url="http://127.0.0.1:1234")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "gemma-2b", "object": "model"}]})

    _patch_client(adapter, handler)
    models = await adapter.list_models()
    assert [m.model_key for m in models] == ["gemma-2b"]
    assert models[0].adapter == "custom"


async def test_openai_compat_stream_chat():
    adapter = OpenAICompatibleAdapter(base_url="http://127.0.0.1:1234")
    events = [
        {"choices": [{"delta": {"content": "He"}}]},
        {"choices": [{"delta": {"content": "y"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}, "choices": []},
    ]
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, content=body.encode())

    _patch_client(adapter, handler)
    out = [
        e
        async for e in adapter.stream_chat(
            model_key="gemma-2b",
            messages=[{"role": "user", "content": "hi"}],
            params={"response_format": {"type": "json_object"}},
        )
    ]
    assert "".join(e.get("delta", "") for e in out) == "Hey"
    done = [e for e in out if e.get("done")]
    assert done and done[0]["usage"]["total_tokens"] == 4


# ── frame dispatch ─────────────────────────────────────────────────────────


class FakeWS:
    def __init__(self, incoming: list | None = None) -> None:
        self.sent: list[dict] = []
        self.incoming = list(incoming or [])

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def recv(self):
        return self.incoming.pop(0)


class FakeAdapter(BaseAdapter):
    name = "fake"

    @classmethod
    def default_base_url(cls) -> str:
        return "http://127.0.0.1:9"

    async def list_models(self) -> list[ModelEntry]:
        return [ModelEntry(model_key="m1", display_name="M1", adapter=self.name)]

    async def stream_chat(self, *, model_key, messages, params):
        yield {"delta": "Hi "}
        yield {"delta": "there"}
        yield {"done": True, "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}


def _connector(adapter: FakeAdapter | None = None) -> Connector:
    config = ConnectorConfig(server="https://x.example.com", credential="lc-x")
    return Connector(config, adapters=[adapter or FakeAdapter()])


async def test_ping_gets_pong():
    conn = _connector()
    ws = FakeWS()
    await conn._on_frame(ws, {"type": "ping", "request_id": "r1"})
    assert ws.sent == [{"type": "pong"}]


async def test_chat_streams_chunks_and_done():
    conn = _connector()
    ws = FakeWS()
    frame = {"type": "chat", "request_id": "r1", "model": "m1", "adapter": "fake", "messages": [], "params": {}}
    await conn._handle_chat(ws, frame)
    types = [f["type"] for f in ws.sent]
    assert types == ["chunk", "chunk", "done"]
    assert ws.sent[0]["request_id"] == "r1"
    assert ws.sent[0]["delta"] == "Hi "
    assert ws.sent[-1]["usage"]["total_tokens"] == 3
    # The completed request is no longer tracked for cancellation.
    assert "r1" not in conn._inflight


async def test_chat_unknown_adapter_reports_error():
    conn = _connector()
    conn._adapters = []  # no adapter available
    ws = FakeWS()
    frame = {"type": "chat", "request_id": "r2", "model": "m1", "adapter": "fake", "messages": []}
    await conn._handle_chat(ws, frame)
    assert ws.sent[0]["type"] == "error"
    assert ws.sent[0]["request_id"] == "r2"


async def test_chat_adapter_error_becomes_error_frame():
    class BoomAdapter(FakeAdapter):
        async def stream_chat(self, *, model_key, messages, params):
            raise AdapterError("ollama exploded")
            yield  # pragma: no cover - marks the generator

    conn = _connector(BoomAdapter())
    ws = FakeWS()
    frame = {"type": "chat", "request_id": "r3", "model": "m1", "adapter": "fake", "messages": []}
    await conn._handle_chat(ws, frame)
    assert ws.sent[0]["type"] == "error"
    assert "exploded" in ws.sent[0]["message"]


async def test_discover_carries_request_id_and_models():
    conn = _connector()
    ws = FakeWS()
    await conn._handle_discover(ws, {"type": "discover", "request_id": "d1"})
    assert ws.sent[0]["type"] == "models"
    assert ws.sent[0]["request_id"] == "d1"
    assert ws.sent[0]["models"][0]["model_key"] == "m1"


async def test_collect_models_aggregates_adapters():
    a = FakeAdapter()
    b = FakeAdapter()
    b.name = "fake2"
    conn = Connector(ConnectorConfig(server="https://x.example.com"), adapters=[a, b])
    models = await conn.collect_models()
    assert {m["adapter"] for m in models} == {"fake", "fake2"}


# ── handshake ──────────────────────────────────────────────────────────────


async def test_handshake_enrollment_persists_credential(monkeypatch):
    saved: dict = {}

    def fake_save(config, path=None):
        saved["credential"] = config.credential
        saved["machine_id"] = config.machine_id
        return path or Path("/dev/null")

    monkeypatch.setattr("geekcubo_connector.config.save_config", fake_save)

    config = ConnectorConfig(server="https://x.example.com", enrollment_code="lcenr-abc")
    conn = Connector(config, adapters=[FakeAdapter()])
    ws = FakeWS(
        incoming=[
            json.dumps(
                {
                    "type": "hello_ok",
                    "machine_id": "m-1",
                    "display_name": "Laptop",
                    "status": "pending",
                    "heartbeat_seconds": 30,
                    "credential": "lc-issued",
                }
            )
        ]
    )
    heartbeat = await conn._handshake(ws)
    assert heartbeat == 30
    assert config.credential == "lc-issued"
    assert config.machine_id == "m-1"
    assert saved["credential"] == "lc-issued"

    hello = ws.sent[0]
    assert hello["type"] == "hello"
    assert hello["enrollment_code"] == "lcenr-abc"
    assert hello["protocol_version"] == protocol.PROTOCOL_VERSION


async def test_handshake_rejection_is_terminal():
    from geekcubo_connector.client import _TerminalClose

    config = ConnectorConfig(server="https://x.example.com", credential="lc-bad")
    conn = Connector(config, adapters=[FakeAdapter()])
    ws = FakeWS(incoming=[json.dumps({"type": "hello_error", "code": "unauthorized", "message": "nope"})])
    with pytest.raises(_TerminalClose):
        await conn._handshake(ws)


# ── reasoning controls ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "show,expected",
    [
        ({"capabilities": ["completion", "thinking"],
          "thinking": {"values": ["low", "medium", "high"]}},
         {"thinking_values": ["low", "medium", "high"]}),
        ({"capabilities": ["completion", "thinking"]}, {"thinking": True}),
        ({"capabilities": ["completion"]}, {"thinking": False}),
        (None, {}),
    ],
)
async def test_ollama_reports_thinking_metadata(show, expected):
    adapter = OllamaAdapter()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "m"}]})
        if show is None:
            return httpx.Response(404)
        return httpx.Response(200, json=show)

    _patch_client(adapter, handler)
    meta = (await adapter.list_models())[0].metadata
    for key in ("thinking", "thinking_values"):
        assert meta.get(key) == expected.get(key)


@pytest.mark.parametrize("think", [True, False, "high"])
def test_ollama_chat_body_forwards_think(think):
    from geekcubo_connector.adapters.ollama import _chat_body

    body = _chat_body("m", [{"role": "user", "content": "hi"}], {"think": think})
    assert body["think"] == think


def test_ollama_chat_body_omits_think_by_default():
    from geekcubo_connector.adapters.ollama import _chat_body

    assert "think" not in _chat_body("m", [{"role": "user", "content": "hi"}], {})


def test_openai_compat_body_forwards_reasoning_effort_only_when_set():
    from geekcubo_connector.adapters.openai_compat import _completion_body

    msgs = [{"role": "user", "content": "hi"}]
    assert _completion_body("m", msgs, {"reasoning_effort": "low"})["reasoning_effort"] == "low"
    assert "reasoning_effort" not in _completion_body("m", msgs, {})


def test_local_provider_forwards_translated_reasoning_params():
    from packages.litellm_adapter.local_provider import _completion_params

    assert _completion_params({"think": "high", "reasoning_effort": None}) == {"think": "high"}
    assert _completion_params({"reasoning_effort": "medium"}) == {"reasoning_effort": "medium"}
    assert "think" not in _completion_params({})
