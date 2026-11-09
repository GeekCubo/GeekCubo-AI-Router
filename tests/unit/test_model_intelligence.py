"""Model Intelligence: unit conversion, precedence, fallback and SSRF guards.

No network: parsers are pure and the fetcher is exercised against local
servers with DNS/connection behaviour stubbed where needed.
"""

from __future__ import annotations

import pytest

from app import model_intelligence as mi
from app.safe_fetch import FetchError, safe_get, validate_source_url

# ── unit conversion ───────────────────────────────────────────────────────


def test_portkey_cents_per_token_are_converted_not_reinterpreted():
    """Portkey publishes US CENTS per token. $2.50/1M = 0.00025 cents/token.

    Treating 0.00025 as dollars (or as per-million dollars) understates the
    price by 10,000x — the bug this test exists to prevent.
    """
    entries = mi.parse_portkey("openai", {
        "gpt-4o": {"pricing_config": {"pay_as_you_go": {
            "request_token": {"price": 0.00025},
            "response_token": {"price": 0.001},
        }}},
    })
    e = entries["openai/gpt-4o"]
    assert e["input_per_million"] == pytest.approx(2.5)
    assert e["output_per_million"] == pytest.approx(10.0)


def test_portkey_template_entry_is_ignored():
    """`default` is a zero template. Treating it as a real model would make
    every unknown model look free."""
    entries = mi.parse_portkey("openai", {
        "default": {"pricing_config": {"pay_as_you_go": {"request_token": {"price": 0}}}},
        "gpt-4o": {"pricing_config": {"pay_as_you_go": {"request_token": {"price": 0.00025}}}},
    })
    assert "openai/default" not in entries
    assert "openai/gpt-4o" in entries


def test_portkey_zero_prices_are_unknown_not_free():
    entries = mi.parse_portkey("x", {"m": {"pricing_config": {"pay_as_you_go": {
        "request_token": {"price": 0}, "response_token": {"price": 0}}}}})
    assert entries["x/m"]["price_state"] == "unknown"


def test_models_dev_prices_are_already_per_million():
    entries = mi.parse_models_dev({"openai": {"id": "openai", "models": {
        "gpt-4o": {"id": "gpt-4o", "cost": {"input": 2.5, "output": 10, "cache_read": 1.25},
                   "limit": {"context": 128000}, "tool_call": True,
                   "modalities": {"input": ["text", "image"]}, "structured_output": True},
    }}})
    e = entries["openai/gpt-4o"]
    assert e["input_per_million"] == 2.5
    assert e["output_per_million"] == 10.0
    assert e["cache_read_per_million"] == 1.25
    assert e["context"] == 128000
    assert e["tools"] is True and e["vision"] is True
    # models.dev reports structured outputs, never JSON mode.
    assert e["json_mode"] is None and e["json_schema"] is True


def test_models_dev_explicit_zero_is_free():
    entries = mi.parse_models_dev({"local": {"id": "local", "models": {
        "tiny": {"id": "tiny", "cost": {"input": 0, "output": 0}}}}})
    assert entries["local/tiny"]["price_state"] == "free"


def test_litellm_per_token_is_scaled_to_per_million():
    entries = mi.parse_litellm({
        "gpt-4o": {"litellm_provider": "openai", "input_cost_per_token": 2.5e-06,
                   "output_cost_per_token": 1e-05, "max_input_tokens": 128000,
                   "cache_read_input_token_cost": 1.25e-06},
        "sample_spec": {},
    })
    e = entries["openai/gpt-4o"]
    assert e["input_per_million"] == pytest.approx(2.5)
    assert e["output_per_million"] == pytest.approx(10.0)
    assert e["cache_read_per_million"] == pytest.approx(1.25)


def test_litellm_zero_is_never_reported_as_free():
    """LiteLLM uses 0 for "no price known" in many entries."""
    entries = mi.parse_litellm({
        "mystery": {"litellm_provider": "acme", "input_cost_per_token": 0, "output_cost_per_token": 0},
    })
    assert entries["acme/mystery"]["price_state"] == "unknown"


# ── identity: no fuzzy matching ───────────────────────────────────────────


def test_similar_names_are_not_merged():
    """An aggregator's `apixo/gpt-4o` must never inherit OpenAI's price."""
    sources = [
        {"key": "models-dev", "name": "Models.dev", "stale": False,
         "entries": {"openai/gpt-4o": {"input_per_million": 2.5, "output_per_million": 10.0,
                                       "price_state": "priced"}}},
    ]
    result = mi.resolve("apixo/gpt-4o", configured=None, sources=sources)
    assert result["price_state"] == "unknown"
    assert result["fields"]["input_per_million"]["value"] is None


# ── precedence and field-level fallback ───────────────────────────────────


def _src(key, entries, stale=False):
    return {"key": key, "name": key, "entries": entries, "stale": stale}


def test_operator_configured_price_wins_over_every_catalog():
    sources = [_src("models-dev", {"apixo/m": {"input_per_million": 2.5, "output_per_million": 10.0,
                                               "price_state": "priced"}})]
    r = mi.resolve("apixo/m", configured={"input_per_million": 1.0, "output_per_million": 3.0}, sources=sources)
    assert r["price_state"] == "configured"
    assert r["fields"]["input_per_million"] == {"value": 1.0, "source": "configured", "stale": False}


def test_priority_order_decides_conflicts():
    sources = [
        _src("first", {"p/m": {"input_per_million": 1.0, "output_per_million": 2.0, "price_state": "priced"}}),
        _src("second", {"p/m": {"input_per_million": 9.0, "output_per_million": 9.0, "price_state": "priced"}}),
    ]
    r = mi.resolve("p/m", configured=None, sources=sources)
    assert r["fields"]["input_per_million"]["value"] == 1.0
    assert r["fields"]["input_per_million"]["source"] == "first"


def test_missing_field_falls_through_to_the_next_source():
    sources = [
        _src("first", {"p/m": {"input_per_million": 1.0, "output_per_million": 2.0,
                               "context": None, "price_state": "priced"}}),
        _src("second", {"p/m": {"input_per_million": 9.0, "output_per_million": 9.0,
                                "context": 64000, "price_state": "priced"}}),
    ]
    r = mi.resolve("p/m", configured=None, sources=sources)
    assert r["fields"]["context"] == {"value": 64000, "source": "second", "stale": False}
    assert r["fields"]["input_per_million"]["source"] == "first"


def test_stale_cache_is_flagged_as_cached_not_estimate():
    sources = [_src("models-dev", {"p/m": {"input_per_million": 1.0, "output_per_million": 2.0,
                                          "price_state": "priced"}}, stale=True)]
    r = mi.resolve("p/m", configured=None, sources=sources)
    assert r["price_state"] == "cached"
    assert r["fields"]["input_per_million"]["stale"] is True


def test_all_sources_offline_yields_unknown():
    r = mi.resolve("p/m", configured=None, sources=[])
    assert r["price_state"] == "unknown"


# ── SSRF ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "http://models.dev/api.json",              # plain http
    "file:///etc/passwd",
    "ftp://example.com/x.json",
    "https://user:pw@example.com/api.json",    # embedded credentials
    "https://127.0.0.1/api.json",
    "https://169.254.169.254/latest/meta-data/",
    "https://10.0.0.5/api.json",
    "https://[::1]/api.json",
])
def test_internal_or_unsafe_urls_are_refused(url):
    with pytest.raises(FetchError):
        validate_source_url(url)


def test_https_public_url_is_accepted():
    assert validate_source_url("https://models.dev/api.json") == "https://models.dev/api.json"


def test_explicit_local_allowlist_permits_http():
    assert validate_source_url(
        "http://127.0.0.1:9000/api.json", allowed_local_hosts="127.0.0.1:9000"
    )


async def test_hostname_resolving_to_private_ip_is_refused(monkeypatch):
    """DNS that points at an internal address must be refused, not connected."""
    import socket as _socket

    def fake_getaddrinfo(host, *a, **k):
        return [(2, 1, 6, "", ("10.1.2.3", 0))]

    monkeypatch.setattr(_socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(FetchError) as exc:
        await safe_get("https://intranet.example/api.json")
    assert "non-public" in str(exc.value)


async def test_dns_rebinding_answer_with_mixed_addresses_is_refused(monkeypatch):
    import socket as _socket

    def fake_getaddrinfo(host, *a, **k):
        return [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(_socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(FetchError):
        await safe_get("https://rebind.example/api.json")


async def test_redirect_to_internal_address_is_refused(monkeypatch):
    """A public source redirecting to 169.254.169.254 must not be followed."""
    import httpx

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.safe_fetch._resolve_public", lambda host: "93.184.216.34"
    )
    with pytest.raises(FetchError):
        await safe_get("https://evil.example/api.json", transport=transport)
    assert all("169.254" not in u for u in seen)


async def test_responses_over_the_size_cap_are_refused(monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048)

    monkeypatch.setattr("app.safe_fetch._resolve_public", lambda host: "93.184.216.34")
    with pytest.raises(FetchError):
        await safe_get("https://big.example/api.json", transport=httpx.MockTransport(handler), max_bytes=1024)


async def test_source_token_is_not_sent_to_another_host(monkeypatch):
    """A redirect to a different host must drop the source's bearer token."""
    import httpx

    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.headers.get("host") or str(request.url), request.headers.get("authorization")))
        if len(sent) == 1:
            return httpx.Response(302, headers={"location": "https://other.example/api.json"})
        return httpx.Response(200, content=b'{"p": {"models": {}}}')

    monkeypatch.setattr("app.safe_fetch._resolve_public", lambda host: "93.184.216.34")
    await safe_get("https://origin.example/api.json", bearer_token="secret", transport=httpx.MockTransport(handler))
    assert sent[0][1] == "Bearer secret"
    assert sent[1][1] is None
