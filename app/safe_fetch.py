"""SSRF-hardened outbound GET for metadata catalogs.

Model Intelligence fetches public JSON catalogs (models.dev, Portkey, and
admin-added sources). An admin-supplied URL is an SSRF vector, so every fetch:

* requires https (http only for hosts on an explicit local allowlist);
* rejects embedded credentials, non-default schemes and unresolvable hosts;
* resolves the hostname ONCE, requires every address to be a public unicast
  IP, and then connects to that pinned IP, with the real hostname used for
  SNI and certificate verification. A DNS-rebinding answer cannot swap in an
  internal address between the check and the connection;
* follows redirects manually, re-validating every hop (max 3);
* caps the response size and the total time;
* never sends provider API keys. The only credential a fetch can carry is
  the source's own optional bearer token, and only to that source's host.

Blocked destinations include loopback, RFC 1918 private ranges, link-local
(including the 169.254.169.254 cloud metadata service), CGNAT, multicast and
reserved space, plus anything else that is not a global unicast address.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 32 * 1024 * 1024  # models.dev api.json is ~6 MB today
TIMEOUT_S = 20.0
MAX_REDIRECTS = 3


class FetchError(Exception):
    """A refused or failed fetch. The message is safe to show the admin."""


@dataclass
class FetchResult:
    status: int
    body: bytes
    etag: str | None
    last_modified: str | None
    not_modified: bool = False
    final_url: str = ""


def _allowed_local(raw: str | None) -> set[str]:
    return {h.strip().lower() for h in (raw or "").split(",") if h.strip()}


def _resolve_public(host: str) -> str:
    """Resolve `host` and return one validated public IP to pin the
    connection to. Raises if ANY resolved address is non-public, because a
    mixed answer is a rebinding attempt or a misconfiguration either way."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise FetchError(f"could not resolve host '{host}'") from exc
    addrs = []
    for info in infos:
        addr = str(info[4][0])
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise FetchError(f"host '{host}' resolved to an invalid address") from exc
        if not ip.is_global or ip.is_multicast:
            raise FetchError(
                f"host '{host}' resolves to a non-public address ({addr}); "
                "metadata sources may not point at internal networks"
            )
        addrs.append(addr)
    if not addrs:
        raise FetchError(f"host '{host}' resolved to no addresses")
    return addrs[0]


def validate_source_url(url: str, *, allowed_local_hosts: str | None = None) -> str:
    """Validate a metadata source URL without fetching it. Returns it cleaned."""
    raw = (url or "").strip()
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise FetchError("invalid URL") from exc
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise FetchError("URL must use https")
    if parsed.username or parsed.password:
        raise FetchError("URL must not embed credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise FetchError("URL must include a host")
    netloc_key = f"{host}:{parsed.port}" if parsed.port else host
    local = _allowed_local(allowed_local_hosts)
    if host in local or netloc_key in local:
        return raw
    if scheme != "https":
        raise FetchError("URL must use https")
    # IP literals are checked directly; names are checked at fetch time too.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return raw
    if not ip.is_global or ip.is_multicast:
        raise FetchError(f"{host} is not a public address")
    return raw


async def safe_get(
    url: str,
    *,
    allowed_local_hosts: str | None = None,
    bearer_token: str | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
    max_bytes: int = MAX_BYTES,
    timeout_s: float = TIMEOUT_S,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchResult:
    current = validate_source_url(url, allowed_local_hosts=allowed_local_hosts)
    origin_host = (urlparse(current).hostname or "").lower()
    local = _allowed_local(allowed_local_hosts)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s),
        follow_redirects=False,
        transport=transport,
        trust_env=False,  # never route through an env-configured proxy
    ) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current)
            host = (parsed.hostname or "").lower()
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            key = f"{host}:{parsed.port}" if parsed.port else host
            headers = {"Accept": "application/json", "User-Agent": "GeekCubo-ModelIntelligence/1.0"}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified
            # The source's own token only, and only to its own host: a
            # redirect to another host must not carry it along.
            if bearer_token and host == origin_host:
                headers["Authorization"] = f"Bearer {bearer_token}"

            extensions: dict = {}
            if host in local or key in local:
                target = current
            else:
                pinned = _resolve_public(host)
                ip_host = f"[{pinned}]" if ":" in pinned else pinned
                target = parsed._replace(netloc=f"{ip_host}:{port}").geturl()
                headers["Host"] = host if not parsed.port else f"{host}:{parsed.port}"
                extensions["sni_hostname"] = host

            try:
                req = client.build_request("GET", target, headers=headers, extensions=extensions)
                resp = await client.send(req, stream=True)
            except httpx.TimeoutException as exc:
                raise FetchError("the source timed out") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"could not connect: {type(exc).__name__}") from exc

            try:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location", "")
                    if not location:
                        raise FetchError("redirect without a location")
                    current = validate_source_url(
                        urljoin(current, location), allowed_local_hosts=allowed_local_hosts
                    )
                    continue
                if resp.status_code == 304:
                    return FetchResult(304, b"", etag, last_modified, not_modified=True, final_url=current)
                if resp.status_code >= 400:
                    raise FetchError(f"the source returned HTTP {resp.status_code}")
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise FetchError("the response is larger than the allowed size")
                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise FetchError("the response is larger than the allowed size")
                    chunks.append(chunk)
                return FetchResult(
                    resp.status_code,
                    b"".join(chunks),
                    resp.headers.get("etag"),
                    resp.headers.get("last-modified"),
                    final_url=current,
                )
            finally:
                await resp.aclose()
    raise FetchError("too many redirects")
