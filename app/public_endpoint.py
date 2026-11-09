"""The API endpoint clients should use, resolved from trusted configuration.

GeekCubo is self-hosted, so nothing here knows a hostname. The public address
comes only from the operator's configuration (`PUBLIC_BASE_URL`, falling back
to `LOCAL_CONNECT_PUBLIC_URL`). It is never built from the request's Host or
X-Forwarded-* headers: behind a reverse proxy those describe the hop to the
proxy (typically plain http), and from an untrusted client they are whatever
the client chose to send.

The local endpoint is the loopback address. When the dashboard itself was
reached on a loopback address, that exact host and port are used (it is the
address that demonstrably works from this machine); otherwise the documented
default is used: the Compose publish port 8787 inside Docker, or the configured
PORT when running directly.
"""

from __future__ import annotations

import ipaddress
import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request

log = logging.getLogger(__name__)

COMPOSE_PUBLISHED_PORT = 8787
_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
_FORBIDDEN_CHARS = set("\"'`\\ \n\r\t<>{}")


def api_base(url: str) -> str:
    """`url` normalized to end in exactly one `/v1` (no trailing slash)."""
    url = url.strip().rstrip("/")
    while url.endswith("/v1"):
        url = url[: -len("/v1")].rstrip("/")
    return url + "/v1"


def _clean_configured(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
        or any(ch in raw for ch in _FORBIDDEN_CHARS)
    ):
        log.warning("public_base_url_ignored", extra={"reason": "not a plain http(s) URL"})
        return None
    return api_base(raw)


def configured_public_api_base() -> str | None:
    """`https://host[/prefix]/v1` from configuration, or None if unset/invalid."""
    from app.config import get_settings

    settings = get_settings()
    for raw in (
        getattr(settings, "public_base_url", ""),
        getattr(settings, "local_connect_public_url", ""),
    ):
        cleaned = _clean_configured(raw)
        if cleaned:
            return cleaned
    return None


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    host = host.strip("[]").lower()
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _in_docker() -> bool:
    return Path("/.dockerenv").exists()


def local_api_base(request: Request | None = None) -> str:
    """Loopback endpoint for clients running on the GeekCubo host itself."""
    if request is not None:
        host = request.url.hostname
        port = request.url.port
        if is_loopback_host(host) and request.url.scheme in ("http", "https"):
            shown = f"[{host}]" if host and ":" in host else host
            netloc = f"{shown}:{port}" if port else shown
            return f"{request.url.scheme}://{netloc}/v1"
    if _in_docker():
        port = COMPOSE_PUBLISHED_PORT
    else:
        from app.config import get_settings

        port = int(getattr(get_settings(), "port", 8000) or 8000)
    return f"http://127.0.0.1:{port}/v1"


def endpoint_info(request: Request | None = None) -> dict:
    """What the dashboard shows on API Keys and pre-fills in Connect a tool."""
    public = configured_public_api_base()
    local = local_api_base(request)
    return {
        "api_base_url": public or local,
        "kind": "public" if public else "local",
        "public_api_base_url": public,
        "local_api_base_url": local,
        "public_configured": public is not None,
        "insecure_public": bool(public and public.startswith("http://")),
    }


def align_with_public(url: str) -> str:
    """If `url` names the configured public host, use the configured scheme.

    Prevents an `http://` URL for a host that is configured as `https://`
    (for example a remote URL typed or pasted without the scheme upgrade).
    """
    public = configured_public_api_base()
    if not public:
        return url
    p, u = urlparse(public), urlparse(url)
    if (u.hostname or "").lower() == (p.hostname or "").lower() and u.scheme != p.scheme:
        netloc = u.netloc
        # Drop an explicit default port that belonged to the old scheme.
        if u.port in (80, 443):
            netloc = u.hostname or netloc
        return f"{p.scheme}://{netloc}{u.path}"
    return url
