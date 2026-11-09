"""Endpoint resolution (API Keys page, Connect a tool) and generated client configs.

The endpoint shown to operators comes only from configuration
(PUBLIC_BASE_URL, then LOCAL_CONNECT_PUBLIC_URL) or the loopback fallback. It
is never taken from the request's Host or X-Forwarded-* headers.
"""

from __future__ import annotations

import json
import re

import pytest
from starlette.requests import Request

from app import integrations, public_endpoint
from app.public_endpoint import align_with_public, api_base, endpoint_info, local_api_base


class _Settings:
    def __init__(self, public="", local_connect="", port=8000):
        self.public_base_url = public
        self.local_connect_public_url = local_connect
        self.port = port


@pytest.fixture
def settings(monkeypatch):
    holder = {"s": _Settings()}
    import app.config as cfg

    monkeypatch.setattr(cfg, "get_settings", lambda: holder["s"])
    monkeypatch.setattr(public_endpoint, "_in_docker", lambda: False)
    return holder


def _request(url: str, headers: dict | None = None) -> Request:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    raw_headers = [(b"host", parts.netloc.encode())]
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode(), v.encode()))
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return Request({
        "type": "http", "method": "GET", "scheme": parts.scheme, "path": parts.path or "/",
        "query_string": b"", "headers": raw_headers, "server": (parts.hostname, port),
        "client": ("203.0.113.9", 50000),
    })


# ── /v1 handling ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ("https://api.example.com", "https://api.example.com/v1"),
    ("https://api.example.com/", "https://api.example.com/v1"),
    ("https://api.example.com/v1", "https://api.example.com/v1"),
    ("https://api.example.com/v1/", "https://api.example.com/v1"),
    ("https://api.example.com/v1/v1", "https://api.example.com/v1"),
    ("https://example.com/geekcubo", "https://example.com/geekcubo/v1"),
])
def test_api_base_has_exactly_one_v1(raw, expected):
    assert api_base(raw) == expected


# ── public endpoint ────────────────────────────────────────────────────────


def test_public_https_endpoint_is_shown_from_configuration(settings):
    settings["s"] = _Settings(public="https://api.example.com/")
    info = endpoint_info(_request("http://10.0.0.5:8000/v1/keys"))
    assert info["api_base_url"] == "https://api.example.com/v1"
    assert info["kind"] == "public"
    assert info["insecure_public"] is False


def test_request_headers_never_decide_the_public_endpoint(settings):
    """Behind a proxy the request is http://app.host; a client can also forge
    Host / X-Forwarded-*. Neither may change what is shown."""
    settings["s"] = _Settings(public="https://api.example.com")
    forged = _request("http://evil.example.net/", {
        "x-forwarded-host": "attacker.example.org",
        "x-forwarded-proto": "http",
    })
    info = endpoint_info(forged)
    assert info["api_base_url"] == "https://api.example.com/v1"
    assert "evil" not in json.dumps(info) and "attacker" not in json.dumps(info)


def test_unconfigured_install_falls_back_to_loopback_not_the_request_host(settings):
    info = endpoint_info(_request("http://app.example.com/v1/keys", {"x-forwarded-proto": "https"}))
    assert info["kind"] == "local"
    assert info["public_api_base_url"] is None
    assert info["api_base_url"] == "http://127.0.0.1:8000/v1"
    assert "app.example.com" not in json.dumps(info)


def test_local_connect_url_is_used_when_public_base_url_is_empty(settings):
    settings["s"] = _Settings(local_connect="https://ai.example.org")
    assert endpoint_info(None)["api_base_url"] == "https://ai.example.org/v1"


@pytest.mark.parametrize("bad", [
    "ftp://api.example.com", "api.example.com", "https://", "https://a b.example.com",
    "https://api.example.com/?x=1", "javascript:alert(1)", "https://api.example.com/\"}",
])
def test_invalid_configured_url_is_ignored(settings, bad):
    settings["s"] = _Settings(public=bad)
    assert endpoint_info(None)["kind"] == "local"


def test_plain_http_public_url_is_flagged(settings):
    settings["s"] = _Settings(public="http://api.example.com")
    info = endpoint_info(None)
    assert info["insecure_public"] is True
    assert info["api_base_url"] == "http://api.example.com/v1"


# ── local endpoint ─────────────────────────────────────────────────────────


def test_local_endpoint_uses_the_loopback_address_the_dashboard_was_opened_on(settings):
    assert local_api_base(_request("http://127.0.0.1:8787/")) == "http://127.0.0.1:8787/v1"
    assert local_api_base(_request("http://localhost:9000/")) == "http://localhost:9000/v1"


def test_local_endpoint_ignores_non_loopback_hosts(settings):
    settings["s"] = _Settings(port=8123)
    assert local_api_base(_request("http://app.example.com/")) == "http://127.0.0.1:8123/v1"


def test_local_endpoint_in_docker_is_the_compose_port(settings, monkeypatch):
    monkeypatch.setattr(public_endpoint, "_in_docker", lambda: True)
    assert local_api_base(_request("https://app.example.com/")) == "http://127.0.0.1:8787/v1"


# ── Connect a tool: never http:// for an https host ────────────────────────


def test_http_url_for_the_configured_https_host_is_upgraded(settings):
    settings["s"] = _Settings(public="https://app.example.com")
    assert align_with_public("http://app.example.com/v1") == "https://app.example.com/v1"
    assert align_with_public("http://app.example.com:80/v1") == "https://app.example.com/v1"
    # Other hosts and the loopback endpoint are left alone.
    assert align_with_public("http://127.0.0.1:8787/v1") == "http://127.0.0.1:8787/v1"
    assert align_with_public("http://other.example.com/v1") == "http://other.example.com/v1"


def test_validate_base_strips_duplicate_v1_and_upgrades_scheme(settings):
    from app.routes.integrations import _validate_base

    settings["s"] = _Settings(public="https://app.example.com")
    assert _validate_base("http://app.example.com/v1/v1/") == "https://app.example.com/v1"
    assert _validate_base("https://gw.example.com") == "https://gw.example.com/v1"


# ── generated configurations ───────────────────────────────────────────────


def _oc(variant=None, base="https://app.example.com/v1", model="auto"):
    return integrations.build("opencode", base_url=base, model=model, variant=variant)


def test_opencode_current_follows_the_documented_custom_provider_schema():
    cfg = json.loads(_oc().code)
    assert cfg["$schema"] == "https://opencode.ai/config.json"
    assert set(cfg) == {"$schema", "providers"}
    geek = cfg["providers"]["geek"]
    # Only fields the OpenCode 2.x schema defines for a provider.
    assert set(geek) <= {"canonical", "name", "env", "package", "compatibility",
                         "settings", "headers", "body", "models"}
    assert geek["env"] == ["GEEKCUBO_API_KEY"]
    assert geek["package"] == "@opencode/ai/providers/openai-compatible"
    assert geek["settings"] == {"baseURL": "https://app.example.com/v1"}
    assert list(geek["models"]) == ["auto"]


def test_opencode_legacy_uses_provider_npm_options_and_env_reference():
    cfg = json.loads(_oc("legacy").code)
    assert set(cfg) == {"$schema", "provider"}
    geek = cfg["provider"]["geek"]
    assert geek["npm"] == "@ai-sdk/openai-compatible"
    assert geek["options"] == {"baseURL": "https://app.example.com/v1",
                               "apiKey": "{env:GEEKCUBO_API_KEY}"}


def test_opencode_unknown_variant_falls_back_to_current():
    assert "providers" in json.loads(_oc("something-else").code)


@pytest.mark.parametrize("app_id", [a["id"] for a in integrations.catalog()])
def test_every_client_uses_geekcubo_api_key_and_embeds_no_secret(app_id):
    r = integrations.build(app_id, base_url="https://app.example.com/v1", model="auto")
    text = r.code + "\n".join(r.steps) + "\n".join(r.notes)
    # A real key is sk-geek- followed by 32 hex characters; only placeholders allowed.
    assert not re.search(r"sk-geek-[0-9a-f]{8,}", text), app_id
    assert "OPENAI_API_KEY" not in r.code, app_id
    if r.downloadable:
        assert "GEEKCUBO_API_KEY" in r.code, app_id


@pytest.mark.parametrize("app_id", [a["id"] for a in integrations.catalog()])
def test_https_base_url_is_preserved_in_every_generated_config(app_id):
    r = integrations.build(app_id, base_url="https://app.example.com/v1", model="auto")
    blob = r.code + "\n".join(r.steps) + "\n".join(r.notes)
    assert "http://app.example.com" not in blob, app_id
    assert "https://app.example.com" in blob, app_id


def test_claude_code_root_has_no_v1_and_keeps_https():
    r = integrations.build("claude-code", base_url="https://app.example.com/v1", model="auto")
    assert 'ANTHROPIC_BASE_URL="https://app.example.com"' in r.code
    assert "${GEEKCUBO_API_KEY}" in r.code


def test_no_operator_hostname_is_hardcoded_in_generators():
    import inspect

    src = inspect.getsource(integrations) + inspect.getsource(public_endpoint)
    assert "geekcubo.com" not in src
