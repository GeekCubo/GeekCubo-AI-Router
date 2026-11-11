"""Custom OpenAI-compatible providers — validation, routing, and catalog merge.

This module is the single home for the reusable "OpenAI Format – Others"
feature. It owns:

  * base-URL validation (HTTPS required for remote hosts, SSRF / private /
    loopback blocking, an explicit local-host allowlist for self-hosted
    proxies);
  * a redirect-safe HTTP client used by the "Test connection" action (no
    blind `follow_redirects` — every hop is re-validated so the credential
    never flows to an unapproved host);
  * the mapping from stored `CustomProvider` rows to `ProviderDeployment`
    entries (namespaced `{slug}/{model_id}` model names, upstream wire id
    sent on the wire, `custom_llm_provider="openai"` + the provider's
    `api_base`);
  * the dynamic catalog merge that lets custom models appear in
    `GET /v1/models`, key allowlists, and `model="auto"` routing — but only
    when the operator has marked the provider `eligible_for_auto` and given
    the model non-zero pricing (unknown capabilities/prices are never
    guessed).

No plaintext credential is ever returned by this module's public helpers.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from packages.auth.encryption import decrypt_credential
from packages.litellm_adapter.catalog import CatalogModel
from packages.litellm_adapter.types import ProviderDeployment


class CustomProviderValidationError(ValueError):
    """Raised when a custom provider base URL fails validation."""


# ── slug / identifier ──────────────────────────────────────────────────────


def normalize_slug(value: str) -> str:
    """Derive a stable, lowercase provider identifier from a display name.

    "Apixo AI" -> "apixo-ai". Letters/digits/dashes/underscores only; runs
    of anything else collapse to a single dash; leading/trailing dashes
    stripped. Raises ValueError when nothing usable remains.
    """
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise ValueError("provider identifier cannot be empty")
    if len(slug) > 50:
        slug = slug[:50].rstrip("-")
    if slug.startswith("-"):
        slug = slug.lstrip("-")
    return slug


# ── SSRF-safe URL validation ───────────────────────────────────────────────


def _allowed_local_hosts_set(raw: str | None) -> set[str]:
    """Parse `host[:port]` entries from the allowlist setting."""
    out: set[str] = set()
    for part in (raw or "").split(","):
        part = part.strip().lower()
        if part:
            out.add(part)
    return out


def _host_is_public(host: str) -> bool:
    """Resolve `host` and require every address to be a global unicast IP.

    A hostname that resolves to any loopback/private/link-local/multicast/
    reserved/CGNAT address is rejected. Resolution failure is a rejection —
    an unverifiable host must not become a credential sink.
    """
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise CustomProviderValidationError(
            f"could not resolve host '{host}': {exc}"
        ) from exc

    addrs: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0] if isinstance(sockaddr, (tuple, list)) else str(sockaddr)
        addrs.add(str(addr))

    if not addrs:
        raise CustomProviderValidationError(f"host '{host}' resolved to no addresses")

    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise CustomProviderValidationError(
                f"host '{host}' resolved to an unparseable address '{addr}'"
            ) from exc
        if not ip.is_global:
            raise CustomProviderValidationError(
                f"host '{host}' resolves to non-public address {addr}; "
                "custom providers must not point at localhost or private "
                "network ranges (SSRF guard)"
            )
    return True


def _parse_port(parsed) -> int | None:
    if parsed.port is not None:
        return parsed.port
    scheme = parsed.scheme.lower()
    if scheme == "https":
        return 443
    if scheme == "http":
        return 80
    return None


def _is_authorized_local(parsed, allowed: set[str]) -> bool:
    """True when `parsed` targets an explicitly-authorized local endpoint."""
    host = (parsed.hostname or "").lower()
    port = _parse_port(parsed)
    if not host:
        return False
    # Exact host match.
    if host in allowed:
        return True
    # host:port match for the default and explicit ports.
    for candidate in (f"{host}:{port}", f"{host}") if port is not None else (host,):
        if candidate in allowed:
            return True
    return False


def validate_base_url(base_url: str, *, allowed_local_hosts: str | None = None) -> str:
    """Validate a custom provider base URL and return it normalized.

    Normalized form has no trailing slash and no fragment/query/userinfo.

    Rules:
      * scheme must be http or https (anything else — file:, ftp:, gopher: —
        is rejected outright);
      * userinfo (embedded credentials) is rejected;
      * remote (non-allowlisted) hosts MUST use https and MUST resolve to a
        global unicast IP only;
      * an http:// or private/loopback host is accepted ONLY when the
        `host` (or `host:port`) is present in the explicit local allowlist.

    Raises `CustomProviderValidationError` with a human-readable reason.
    """
    raw = (base_url or "").strip()
    if not raw:
        raise CustomProviderValidationError("base URL cannot be empty")

    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise CustomProviderValidationError(f"invalid base URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise CustomProviderValidationError(
            f"base URL scheme must be http or https, got '{scheme or '(none)'}'"
        )
    if parsed.username or parsed.password:
        raise CustomProviderValidationError(
            "base URL must not embed credentials (userinfo)"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise CustomProviderValidationError("base URL must include a host")

    allowed = _allowed_local_hosts_set(allowed_local_hosts)

    if _is_authorized_local(parsed, allowed):
        # Explicit operator authorization: http + private IP allowed here.
        pass
    else:
        if scheme != "https":
            raise CustomProviderValidationError(
                "custom provider base URL must use https (http is only allowed "
                "for explicitly authorized local endpoints)"
            )
        _host_is_public(host)

    # Rebuild a clean URL: scheme://netloc + path (path preserved, trailing
    # slash stripped). netloc already excludes userinfo because we rejected it.
    path = parsed.path.rstrip("/")
    return f"{scheme}://{parsed.netloc}{path}"


# ── redirect-safe HTTP for the test-connection action ──────────────────────


def _join_url(base_url: str, location: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base_url, location)


def _request_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _classify_http_error(status: int, body_text: str) -> tuple[str, str]:
    if status in (401, 403):
        return "auth_error", "The provider rejected the API key (unauthorized)."
    if status == 429:
        return "rate_limit_error", "The provider returned 429 (rate limited)."
    if 500 <= status < 600:
        return "server_error", f"The provider returned HTTP {status}."
    snippet = body_text[:200].strip() or "no body"
    return "http_error", f"The provider returned HTTP {status}: {snippet}"


async def _send_test_request(
    client: httpx.AsyncClient,
    url: str,
    *,
    api_key: str,
    allowed_local_hosts: str | None,
    _redirects_left: int = 5,
) -> dict:
    """Send one request, re-validating every redirect hop before following it."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = await client.get(url, headers=headers)
    if resp.is_redirect:
        if _redirects_left <= 0:
            return {
                "ok": False,
                "http_status": resp.status_code,
                "error": "too many redirects",
                "error_type": "redirect_unsafe",
            }
        location = resp.headers.get("location", "")
        if not location:
            return {
                "ok": False,
                "http_status": resp.status_code,
                "error": "redirect response without a location header",
                "error_type": "redirect_unsafe",
            }
        try:
            target = validate_base_url(
                _join_url(str(resp.url), location),
                allowed_local_hosts=allowed_local_hosts,
            )
        except CustomProviderValidationError as exc:
            return {
                "ok": False,
                "http_status": resp.status_code,
                "error": f"refusing unsafe redirect: {exc}",
                "error_type": "redirect_unsafe",
            }
        source = urlparse(str(resp.url))
        destination = urlparse(target)
        next_key = api_key if (source.scheme, source.hostname, source.port) == (
            destination.scheme, destination.hostname, destination.port
        ) else ""
        return await _send_test_request(
            client, target, api_key=next_key,
            allowed_local_hosts=allowed_local_hosts, _redirects_left=_redirects_left - 1,
        )
    if resp.is_success:
        return {
            "ok": True,
            "http_status": resp.status_code,
            "error_type": None,
            "error": None,
            "body": resp.text,
        }
    etype, msg = _classify_http_error(resp.status_code, resp.text)
    return {
        "ok": False,
        "http_status": resp.status_code,
        "error_type": etype,
        "error": msg,
        "body": resp.text,
    }


async def test_connection(
    *,
    base_url: str,
    api_key: str,
    model: str | None = None,
    allowed_local_hosts: str | None = None,
) -> dict:
    """Verify connectivity to a custom provider without exposing the key.

    With `model` set, issues a minimal chat completion and reports the
    resolved upstream model. Without it, issues `GET {base}/models` and
    reports the model ids the upstream advertises.

    Returns a dict safe to serialize to the dashboard: the credential never
    appears, and every error is classified.
    """
    try:
        normalized = validate_base_url(
            base_url, allowed_local_hosts=allowed_local_hosts
        )
    except CustomProviderValidationError as exc:
        return {"ok": False, "error": str(exc), "error_type": "invalid_url"}

    timeout = httpx.Timeout(15.0, connect=10.0)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, timeout=timeout,
        ) as client:
            if model:
                url = _request_url(normalized, "/chat/completions")
                for attempt in ({"max_tokens": 1}, {"max_completion_tokens": 1}):
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": "ping"}],
                            **attempt,
                        },
                    )
                    if resp.is_redirect:
                        location = resp.headers.get("location", "")
                        try:
                            validate_base_url(
                                _join_url(url, location),
                                allowed_local_hosts=allowed_local_hosts,
                            )
                        except CustomProviderValidationError as exc:
                            return {
                                "ok": False, "http_status": resp.status_code,
                                "resolved_model": None,
                                "error": f"refusing unsafe redirect: {exc}",
                                "error_type": "redirect_unsafe",
                            }
                        return {
                            "ok": False, "http_status": resp.status_code,
                            "resolved_model": None,
                            "error": "provider responded with a redirect; check the base URL",
                            "error_type": "redirect_unsafe",
                        }
                    if resp.status_code == 400 and "max_completion_tokens" in resp.text:
                        continue
                    body = resp.json() if _is_json(resp) else {}
                    resolved = body.get("model") if isinstance(body, dict) else None
                    if resp.is_success:
                        return {
                            "ok": True,
                            "http_status": resp.status_code,
                            "resolved_model": resolved or model,
                            "models": None,
                            "error": None,
                            "error_type": None,
                        }
                    etype, msg = _classify_http_error(resp.status_code, resp.text)
                    return {
                        "ok": False, "http_status": resp.status_code,
                        "resolved_model": None, "error": msg, "error_type": etype,
                    }
                return {
                    "ok": False, "http_status": 400,
                    "resolved_model": None,
                    "error": "provider rejected the minimal test completion",
                    "error_type": "http_error",
                }
            else:
                url = _request_url(normalized, "/models")
                result = await _send_test_request(
                    client, url, api_key=api_key, allowed_local_hosts=allowed_local_hosts
                )
                if not result["ok"]:
                    result["resolved_model"] = None
                    result["models"] = None
                    return result
                models = _extract_model_ids(result.get("body", ""))
                return {
                    "ok": True,
                    "http_status": result["http_status"],
                    "resolved_model": None,
                    "models": models,
                    "error": None,
                    "error_type": None,
                }
    except httpx.ConnectError as exc:
        return {"ok": False, "error": f"could not connect: {exc}", "error_type": "connect_error"}
    except httpx.TimeoutException as exc:
        return {"ok": False, "error": f"request timed out: {exc}", "error_type": "timeout"}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"http error: {exc}", "error_type": "connect_error"}


def _is_json(resp: httpx.Response) -> bool:
    return "application/json" in resp.headers.get("content-type", "")


# A level is honoured only if this many reasoning tokens (or that much
# reasoning text) separate it from the request without it. Tiny prompts make
# the signal small, so the probe asks for a little arithmetic.
_PROBE_PROMPT = "What is 17 * 23? Answer with the number only."
_PROBE_MAX_TOKENS = 256
# Low/high bracket the classic ladder; a deliberately invalid value tells an
# endpoint that validates the field from one that ignores it.
_PROBE_LEVELS = ("low", "high")
_PROBE_INVALID = "geekcubo-invalid-level"
# Minimum absolute reasoning-token separation treated as a real difference.
_PROBE_MIN_GAP = 16


def _reasoning_signal(body: dict) -> int | None:
    """Reasoning tokens (or reasoning-text length) in a completion, or None."""
    usage = body.get("usage") if isinstance(body, dict) else None
    details = (usage or {}).get("completion_tokens_details") if isinstance(usage, dict) else None
    if isinstance(details, dict) and isinstance(details.get("reasoning_tokens"), int):
        return details["reasoning_tokens"]
    choices = body.get("choices") if isinstance(body, dict) else None
    msg = (choices[0].get("message") if choices and isinstance(choices[0], dict) else None) or {}
    for key in ("reasoning_content", "reasoning"):
        if isinstance(msg.get(key), str):
            return len(msg[key]) // 4
    return None


async def probe_reasoning(
    *,
    base_url: str,
    api_key: str,
    model: str,
    allowed_local_hosts: str | None = None,
) -> dict:
    """Administrator-triggered, bounded check of `reasoning_effort` on one model.

    At most four tiny completions (default, low, high, one invalid value), no
    retries, short timeouts. Conclusions are drawn only from evidence the
    provider returns:

      * the invalid value is rejected with a 4xx  → the endpoint validates the
        field; levels it accepted are recorded as supported;
      * accepted AND reasoning usage moves with the level → supported;
      * everything accepted with no difference, including the invalid value →
        the endpoint ignores the field: recorded as no effort control;
      * anything else (outage, rate limit, 5xx, ambiguous signal) → no
        conclusion. Transient failures never become a permanent capability.

    The credential is only ever sent to `base_url` and never returned.
    """
    try:
        normalized = validate_base_url(base_url, allowed_local_hosts=allowed_local_hosts)
    except CustomProviderValidationError as exc:
        return {"ok": False, "conclusive": False, "error": str(exc), "error_type": "invalid_url"}
    url = _request_url(normalized, "/chat/completions")
    samples: dict[str, dict] = {}
    timeout = httpx.Timeout(30.0, connect=10.0)
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
            for label in ("default", *_PROBE_LEVELS, "invalid"):
                body = {"model": model, "max_tokens": _PROBE_MAX_TOKENS,
                        "messages": [{"role": "user", "content": _PROBE_PROMPT}]}
                if label != "default":
                    body["reasoning_effort"] = _PROBE_INVALID if label == "invalid" else label
                resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {api_key}"})
                data = resp.json() if _is_json(resp) else {}
                samples[label] = {
                    "status": resp.status_code,
                    "signal": _reasoning_signal(data) if resp.is_success else None,
                }
                if label == "default" and not resp.is_success:
                    break  # the model itself is not answering: no conclusion
    except httpx.HTTPError as exc:
        return {"ok": False, "conclusive": False, "error_type": "connect_error",
                "error": f"probe failed: {type(exc).__name__}", "samples": samples}

    def status(label: str) -> int | None:
        return (samples.get(label) or {}).get("status")

    result: dict = {"ok": True, "conclusive": False, "samples": samples, "levels": None}
    if status("default") != 200:
        result.update(ok=False, error_type="model_unavailable",
                      error=f"default request returned HTTP {status('default')}")
        return result
    if any((status(lv) or 0) >= 500 or status(lv) in (408, 429) for lv in (*_PROBE_LEVELS, "invalid")):
        result.update(error_type="transient", error="transient upstream failure; nothing recorded")
        return result
    accepted = [lv for lv in _PROBE_LEVELS if status(lv) == 200]
    invalid = status("invalid")
    signals = {lv: samples[lv]["signal"] for lv in accepted}
    # Sampling noise moves reasoning usage by a few tokens on its own (a live
    # gateway ignoring the field showed 5 → 6), so only a clear separation
    # counts: high must exceed low by both a ratio and an absolute margin,
    # AND the invalid value must not look like a real level.
    def _clearly_more(a: int | None, b: int | None) -> bool:
        return a is not None and b is not None and a >= max(2 * b, b + _PROBE_MIN_GAP)

    moved = (len(accepted) == 2 and None not in signals.values()
             and _clearly_more(signals["high"], signals["low"])
             and not _clearly_more(samples["invalid"]["signal"], signals["low"]))
    if invalid is not None and 400 <= invalid < 500:
        # Validates the field: what it accepted, it understands.
        result.update(conclusive=True, levels=accepted, basis="invalid value rejected")
    elif invalid == 200 and moved:
        result.update(conclusive=True, levels=accepted, basis="reasoning usage follows the level")
    elif invalid == 200 and len(accepted) == 2 and None not in signals.values() \
            and samples["default"]["signal"] is not None \
            and not _clearly_more(signals["high"], signals["low"]) \
            and not _clearly_more(signals["low"], signals["high"]) \
            and abs(signals["high"] - samples["default"]["signal"]) < _PROBE_MIN_GAP:
        result.update(conclusive=True, levels=[],
                      basis="any value accepted with identical reasoning usage; field ignored")
    else:
        result.update(error_type="inconclusive",
                      error="the provider gave no evidence that the level changes anything")
    return result


def _parse_models_body(body_text: str) -> tuple[list[dict], str | None]:
    """Parse an OpenAI-compatible `GET /models` body.

    Returns `(models, error)`. `models` is a list of `{id, ...metadata}`; a
    non-empty `error` describes a malformed/empty body. Supports:
      - standard envelope  `{"object":"list","data":[{"id":...}, ...]}`
      - string-id entries  `{"data": ["id1", "id2"]}`
      - bare list          `[{"id":...}, ...]` / `["id1", ...]`

    Only the `id` is authoritative. Reliable metadata is passed through
    verbatim; capabilities / pricing / context are NEVER invented.
    """
    import json

    try:
        data = json.loads(body_text)
    except Exception:
        return [], "malformed JSON response"

    raw: list | None = None
    if isinstance(data, dict):
        raw = data.get("data")
    elif isinstance(data, list):
        raw = data
    if not isinstance(raw, list):
        return [], "response is missing a 'data' list"

    out: list[dict] = []
    for item in raw:
        if isinstance(item, str):
            if item.strip():
                out.append({"id": item.strip()})
            continue
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                entry: dict = {"id": model_id.strip()}
                for key in ("object", "owned_by", "created", "root", "display_name"):
                    if isinstance(item.get(key), (str, int, float)) and item.get(key) != "":
                        entry[key] = item[key]
                # Limits the provider itself reports for THIS deployment. Not
                # part of the OpenAI schema, so only a positive integer under
                # a known name is kept; anything else stays unknown.
                for key, aliases in (
                    ("context_window", ("context_window", "context_length", "max_context_length")),
                    ("max_output_tokens", ("max_output_tokens", "max_completion_tokens")),
                ):
                    for alias in aliases:
                        value = item.get(alias)
                        if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 100_000_000:
                            entry[key] = value
                            break
                out.append(entry)
            continue
    if not out:
        return [], "provider returned an empty model list"
    return out, None


def _extract_model_ids(body_text: str) -> list[str]:
    """Best-effort parse of an OpenAI `GET /models` body → list of ids."""
    models, _ = _parse_models_body(body_text)
    return [m["id"] for m in models]


# ── model discovery fetch + cache ───────────────────────────────────────────


# In-process cache of the last successful discovery per provider id, keyed to
# avoid hammering the upstream on repeated clicks/refreshes. Timestamps are
# also persisted on the provider row (`last_models_fetched_at`).
_fetch_cache: dict[str, dict] = {}
_fetch_cache_lock = asyncio.Lock()


def _fetch_cache_get(provider_id: str, max_age_s: float) -> dict | None:
    entry = _fetch_cache.get(provider_id)
    if entry is None:
        return None
    if (time.monotonic() - entry["monotonic"]) > max_age_s:
        return None
    return entry


def cached_discovery(provider_id: str) -> dict | None:
    """Last successful discovery for a provider, regardless of age.

    Used only to carry provider-reported limits onto models the operator
    registers from that list; it never triggers an upstream request.
    """
    return _fetch_cache.get(provider_id)


def invalidate_fetch_cache(provider_id: str | None = None) -> None:
    global _fetch_cache
    if provider_id is None:
        _fetch_cache = {}
    else:
        _fetch_cache.pop(provider_id, None)


async def fetch_models(
    *,
    base_url: str,
    api_key: str,
    allowed_local_hosts: str | None = None,
    provider_id: str | None = None,
    force: bool = False,
    cache_ttl_s: float = 300.0,
) -> dict:
    """Fetch + parse the provider's `GET /models`, caching by provider id.

    Never returns the credential. Every request re-validates the base URL and
    refuses unsafe redirects (see `_send_test_request`). A cached (fresh)
    result is returned instead of re-hitting upstream unless `force` is set.
    """
    import time as _time

    if provider_id is not None and not force:
        cached = _fetch_cache_get(provider_id, cache_ttl_s)
        if cached is not None:
            return {
                "ok": True,
                "cached": True,
                "models": cached["models"],
                "fetched_at": cached["fetched_at"],
                "error": None,
                "error_type": None,
            }

    try:
        normalized = validate_base_url(
            base_url, allowed_local_hosts=allowed_local_hosts
        )
    except CustomProviderValidationError as exc:
        return {"ok": False, "cached": False, "models": [], "error": str(exc), "error_type": "invalid_url"}

    timeout = httpx.Timeout(15.0, connect=10.0)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, timeout=timeout,
        ) as client:
            url = _request_url(normalized, "/models")
            result = await _send_test_request(
                client, url, api_key=api_key, allowed_local_hosts=allowed_local_hosts
            )
            if not result["ok"]:
                return {
                    "ok": False, "cached": False, "models": [],
                    "error": result["error"], "error_type": result["error_type"],
                    "http_status": result.get("http_status"),
                }
            models, parse_error = _parse_models_body(result.get("body", ""))
            if parse_error is not None:
                return {
                    "ok": False, "cached": False, "models": [],
                    "error": parse_error, "error_type": "malformed_response",
                    "http_status": result["http_status"],
                }
            fetched_at = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            if provider_id is not None:
                async with _fetch_cache_lock:
                    _fetch_cache[provider_id] = {
                        "models": models,
                        "fetched_at": fetched_at,
                        "monotonic": _time.monotonic(),
                    }
            return {
                "ok": True, "cached": False, "models": models,
                "fetched_at": fetched_at, "error": None, "error_type": None,
            }
    except httpx.ConnectError as exc:
        return {"ok": False, "cached": False, "models": [], "error": f"could not connect: {exc}", "error_type": "connect_error"}
    except httpx.TimeoutException as exc:
        return {"ok": False, "cached": False, "models": [], "error": f"request timed out: {exc}", "error_type": "timeout"}
    except httpx.HTTPError as exc:
        return {"ok": False, "cached": False, "models": [], "error": f"http error: {exc}", "error_type": "connect_error"}


# ── catalog merge / routing ────────────────────────────────────────────────


def namespaced_model_id(slug: str, model_id: str) -> str:
    return f"{slug}/{model_id}"


def _wire_model_id(model_id: str) -> str:
    """The exact model id sent upstream, minus a redundant openai/ prefix."""
    stripped = model_id.strip()
    if stripped.startswith("openai/"):
        return stripped[len("openai/"):]
    return stripped


@dataclass(frozen=True)
class CustomProviderView:
    slug: str
    display_name: str
    base_url: str
    api_key: str
    is_enabled: bool
    eligible_for_auto: bool
    models: list[CatalogModel]


def providers_to_deployments(providers: list[CustomProviderView]) -> list[ProviderDeployment]:
    """Map stored custom providers to LiteLLM deployments.

    Only enabled providers with a decryptable key and at least one model are
    deployable. Model names are namespaced (`{slug}/{model_id}`) so two
    aggregators exposing the same bare id never collide; the upstream wire id
    is the operator-supplied model id (openai/ prefix normalized away).
    """
    deployments: list[ProviderDeployment] = []
    from app.model_metadata import effective_custom_price

    for prov in providers:
        if not prov.is_enabled:
            continue
        for m in prov.models:
            if getattr(m, "is_enabled", True) is False:
                continue
            custom_in, custom_out, _ = effective_custom_price(m)
            deployments.append(
                ProviderDeployment(
                    model_name=namespaced_model_id(prov.slug, m.id),
                    litellm_model=f"openai/{_wire_model_id(m.id)}",
                    api_key=prov.api_key,
                    api_base=prov.base_url,
                    provider=prov.slug,
                    custom_llm_provider="openai",
                    input_cost_per_token=custom_in or None,
                    output_cost_per_token=custom_out or None,
                    # Pinned so LiteLLM reports exactly which model served the
                    # call. Without it, attribution falls back to the
                    # api_base match, which returns the provider's FIRST
                    # model and bills the wrong price.
                    deployment_id=f"custom::{namespaced_model_id(prov.slug, m.id)}",
                    operator_priced=True,
                )
            )
    return deployments


def custom_catalog_entries(
    providers: list[CustomProviderView], *, eligible_only: bool = True
) -> list[CatalogModel]:
    """Custom models as namespaced `CatalogModel` records.

    `eligible_only=True` keeps only models from providers the operator marked
    `eligible_for_auto` — the set that may participate in `model="auto"`.
    Pinned `{slug}/{model_id}` requests don't need these entries (they route
    straight through the deployment list).
    """
    out: list[CatalogModel] = []
    from app.model_metadata import catalog_support

    for prov in providers:
        if eligible_only and not prov.eligible_for_auto:
            continue
        if not prov.is_enabled:
            continue
        for m in prov.models:
            if getattr(m, "is_enabled", True) is False:
                continue
            model_id = namespaced_model_id(prov.slug, m.id)
            out.append(
                CatalogModel(
                    id=model_id,
                    provider=prov.slug,
                    litellm_prefix="openai/",
                    supports_tools=catalog_support(m, "tools"),
                    supports_vision=catalog_support(m, "vision"),
                    supports_json_mode=catalog_support(m, "json_mode"),
                    supports_json_schema=catalog_support(m, "json_schema"),
                    input_cost_per_token=m.input_cost_per_token,
                    output_cost_per_token=m.output_cost_per_token,
                    context_length=m.context_length,
                    custom_input_cost_per_token=m.custom_input_cost_per_token,
                    custom_output_cost_per_token=m.custom_output_cost_per_token,
                    price_source=getattr(m, "price_source", "catalog"),
                    # Only this endpoint's own evidence (administrator
                    # override or a fresh verification). A gateway serving a
                    # well-known model name may still ignore the field, so a
                    # name match in LiteLLM is never borrowed: without
                    # evidence the model stays Unknown, which Auto still
                    # attempts with the effort preserved.
                    reasoning_levels=m.reasoning_levels,
                )
            )
    return out


def eligible_auto_model_ids(
    providers: list[CustomProviderView], *, allow_estimates: bool = False
) -> set[str]:
    from app.model_metadata import effective_routing_price

    ids: set[str] = set()
    for prov in providers:
        if not prov.is_enabled or not prov.eligible_for_auto:
            continue
        for m in prov.models:
            if getattr(m, "is_enabled", True) is False:
                continue
            in_cost, out_cost, source = effective_routing_price(m)
            if source == "reference" and not allow_estimates:
                continue
            if source != "unknown" and (in_cost > 0 or out_cost > 0):
                ids.add(namespaced_model_id(prov.slug, m.id))
    return ids


# Capability name (as produced by auto_routing.required_capabilities) ->
# CatalogModel flag + the checkbox label the operator sees in the dashboard.
_CAPABILITY_FLAGS: dict[str, tuple[str, str]] = {
    "tools": ("supports_tools", "Tools"),
    "vision": ("supports_vision", "Vision"),
    "json_mode": ("supports_json_mode", "JSON mode"),
    "json_schema": ("supports_json_schema", "JSON schema"),
}


def explain_auto_exclusions(
    providers: list[CustomProviderView],
    *,
    needs: set[str],
    deployable: set[str],
    allow_estimates: bool = False,
) -> list[str]:
    """Why each registered custom model is NOT an Auto candidate.

    Mirrors, in order, the gates a custom model has to pass to be chosen by
    `model="auto"`:

      1. its provider is enabled;
      2. its provider is eligible for Auto (not "pinned only");
      3. it is deployable (enabled provider + decryptable key);
      4. it carries pricing (auto_routing excludes zero-blended-cost
         entries — unpriced stubs are treated as unknown, not free);
      5. it has every capability the request needs.

    Returns one human-readable line per excluded model, or an empty list when
    every custom model would qualify (or none are registered). Read-only: it
    never changes eligibility, it only reports it, so the 422 a caller gets
    from `model="auto"` says *which* setting to change instead of a bare
    "no deployable model".
    """
    lines: list[str] = []
    for prov in providers:
        for m in prov.models:
            public_id = namespaced_model_id(prov.slug, m.id)
            reasons: list[str] = []
            if not prov.is_enabled:
                reasons.append(f"provider '{prov.display_name}' is disabled")
            if not prov.eligible_for_auto:
                reasons.append(
                    f"provider '{prov.display_name}' is pinned-only "
                    "(click 'Enable Auto' on the provider)"
                )
            if prov.is_enabled and public_id not in deployable:
                reasons.append("not deployable (provider API key missing or undecryptable)")
            # Same price gate the ranker uses: only a confirmed custom rate
            # counts as priced unless the policy explicitly allows reference
            # estimates; unknown never does.
            from app.model_metadata import effective_routing_price

            route_in, route_out, price_source = effective_routing_price(m)
            if price_source == "unknown" or (route_in <= 0 and route_out <= 0):
                reasons.append("no pricing configured or resolved (input/output cost per 1M)")
            elif price_source == "reference" and not allow_estimates:
                reasons.append(
                    "only a reference price estimate is available; set a confirmed "
                    "custom price or enable estimate-based pricing in the routing policy"
                )
            for cap, (flag, label) in _CAPABILITY_FLAGS.items():
                if cap not in needs:
                    continue
                # `m` is a CatalogModel here, so the capability is already
                # tri-state: False is reported-unsupported, None is unknown.
                value = getattr(m, flag, None)
                if value is False:
                    reasons.append(f"{label} support not enabled on the model")
                elif value is None:
                    reasons.append(
                        f"{label} support unknown (resolve metadata or set it on the model)"
                    )
            if reasons:
                lines.append(f"{public_id}: {'; '.join(reasons)}")
    return lines


# ── cached provider loader ─────────────────────────────────────────────────


def _models_to_catalog(models: list, base_url: str | None = None) -> list[CatalogModel]:
    out: list[CatalogModel] = []
    from app.model_metadata import (
        catalog_support,
        effective_custom_price,
        effective_routing_price,
        endpoint_reasoning_levels,
    )

    for m in models:
        custom_in, custom_out, _custom_state = effective_custom_price(m)
        route_in, route_out, route_source = effective_routing_price(m)
        reasoning_levels, _source = endpoint_reasoning_levels(m, base_url)
        out.append(
            CatalogModel(
                id=m.model_id,  # bare id here; namespacing applied by callers
                provider="",
                litellm_prefix="openai/",
                supports_tools=catalog_support(m, "tools"),
                supports_vision=catalog_support(m, "vision"),
                supports_json_mode=catalog_support(m, "json_mode"),
                supports_json_schema=catalog_support(m, "json_schema"),
                input_cost_per_token=route_in,
                output_cost_per_token=route_out,
                context_length=int(m.context_length) if m.context_length else None,
                custom_input_cost_per_token=custom_in or 0.0,
                custom_output_cost_per_token=custom_out or 0.0,
                price_source=route_source,
                reasoning_levels=reasoning_levels,
            )
        )
    return out


_custom_cache: list[CustomProviderView] | None = None
_cache_lock = asyncio.Lock()


async def _query_providers(db) -> list[CustomProviderView]:
    from sqlalchemy import select

    from packages.db.models.custom_provider import CustomProvider, CustomProviderModel

    rows = (
        await db.execute(
            select(CustomProvider).where(CustomProvider.is_deleted == 0)
        )
    ).scalars().all()
    model_rows = (
        await db.execute(
            select(CustomProviderModel).where(CustomProviderModel.is_deleted == 0)
        )
    ).scalars().all()

    by_provider: dict[str, list] = {}
    for m in model_rows:
        by_provider.setdefault(m.provider_id, []).append(m)

    out: list[CustomProviderView] = []
    for row in rows:
        try:
            api_key = decrypt_credential(row.encrypted_key)
        except Exception:
            api_key = ""  # undecryptable → skipped at deployment time
        models = _models_to_catalog(by_provider.get(row.id, []), row.base_url)
        out.append(
            CustomProviderView(
                slug=row.slug,
                display_name=row.display_name,
                base_url=row.base_url,
                api_key=api_key,
                is_enabled=bool(row.is_enabled),
                eligible_for_auto=bool(row.eligible_for_auto),
                models=models,
            )
        )
    return out


async def load_custom_providers(db) -> list[CustomProviderView]:
    """Return enabled-and-usable custom provider views, cached in-process.

    The cache is dropped on any provider mutation (via `invalidate`), which
    the CRUD routes call after commit.
    """
    global _custom_cache
    if _custom_cache is not None:
        return _custom_cache
    async with _cache_lock:
        if _custom_cache is not None:
            return _custom_cache
        _custom_cache = await _query_providers(db)
    return _custom_cache


def invalidate() -> None:
    global _custom_cache
    _custom_cache = None


async def merged_catalog(db, *, eligible_only: bool = True) -> list[CatalogModel]:
    """`CATALOG` + namespaced custom models.

    `eligible_only=True` (the auto-routing path) keeps only models from
    providers the operator marked `eligible_for_auto`, plus every local model
    on a machine that is itself auto-eligible (Local AI Connect). Local models
    are appended last so they never displace a cloud model the operator has
    explicitly enabled. `eligible_only=False` (the /v1/models listing and
    key-allowlist paths) keeps every enabled custom model and every enabled
    local model so they can be pinned or allowlisted even when auto-routing
    eligibility isn't configured.
    """
    from app.local_connect.catalog import local_catalog_entries
    from packages.litellm_adapter.catalog import CATALOG

    providers = await load_custom_providers(db)
    entries = list(CATALOG) + custom_catalog_entries(providers, eligible_only=eligible_only)
    entries.extend(await local_catalog_entries(db, eligible_only=eligible_only))
    return entries


async def merged_catalog_by_id(db, *, eligible_only: bool = True) -> dict[str, CatalogModel]:
    catalog = await merged_catalog(db, eligible_only=eligible_only)
    return {m.id: m for m in catalog}
