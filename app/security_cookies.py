"""Cookie attribute decisions, in one place.

`Secure` is conditional on purpose. The default deployment binds to
127.0.0.1 and is reached over plain http; a `Secure` cookie would simply not be
stored there and the operator could never sign in. The moment the request is
HTTPS — directly, or via a proxy whose `X-Forwarded-Proto` we are explicitly
told to trust — the flag is set.

`SameSite=Lax` (not Strict): Stripe-style external links and a reload from a
bookmark should land signed-in, while cross-site POSTs still do not carry the
cookie, which is the property that matters for CSRF. The CSRF token adds the
second layer that Lax alone does not give us.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request, Response

from packages.auth.sessions import CSRF_HEADER_NAME, SESSION_COOKIE_NAME

# How long the browser keeps the cookie. Matches the server-side absolute TTL;
# the server is the authority either way (an expired row is rejected on sight).
_BROWSER_MAX_AGE = 12 * 60 * 60


def _cookie_max_age(issued) -> int:
    """Normal sessions keep the 12-hour cookie. A remembered session's cookie
    lives exactly as long as its server-side record (never longer)."""
    if not getattr(issued, "persistent", False):
        return _BROWSER_MAX_AGE
    remaining = (issued.expires_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(remaining))


def request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception:
        return False
    if not getattr(settings, "trust_proxy_headers", False):
        return False
    proto = request.headers.get("x-forwarded-proto", "")
    return proto.split(",")[0].strip().lower() == "https"


def set_session_cookies(response: Response, issued, request: Request) -> None:
    """Attach the HttpOnly session cookie and expose the CSRF token to the client."""
    secure = request_is_https(request)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.raw_token,
        max_age=_cookie_max_age(issued),
        httponly=True,      # unreadable from JavaScript: XSS cannot exfiltrate it
        samesite="lax",
        secure=secure,
        path="/",
    )
    # The CSRF token is NOT HttpOnly — the dashboard must read it to echo it
    # back. It is not a bearer credential: it only matters alongside the
    # HttpOnly cookie it is bound to server-side.
    response.headers["X-CSRF-Token"] = issued.csrf_token


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax"
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "CSRF_HEADER_NAME",
    "SESSION_COOKIE_NAME",
    "clear_session_cookies",
    "now_utc",
    "request_is_https",
    "set_session_cookies",
]
