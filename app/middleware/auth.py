"""Auth middleware — one enforcement point, three route classes.

The old version had a single rule ("every /v1 path needs an inference key") and
a skip-list. That could not express the difference between the inference
surface and the administrative surface: both live under /v1, and the console
needed to reach its own management routes without pretending to be an SDK.

Now every request is classified by `app.auth_policy.classify`:

  PUBLIC     health, the SPA shell, static assets, and the auth endpoints that
             necessarily precede a session.
  ADMIN      the operator console: provider credentials, custom providers,
             key management, routing, analytics, quality, and everything under
             /api/. Requires a server-side browser session.
  INFERENCE  the OpenAI / Anthropic / Gemini surfaces. Requires sk-geek-*.

The two credentials are deliberately not interchangeable:

  * a session cookie never authorizes inference — otherwise "log into the
    dashboard" would mint a portable, non-rotatable inference credential that
    outlives key revocation;
  * an sk-geek-* key never authorizes admin routes — an application's key must
    not be able to read or rewrite upstream provider credentials.

Error envelopes stay protocol-specific on the inference surface so existing
SDKs keep parsing failures exactly as before.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from app.auth_policy import CSRF_PROTECTED_METHODS, AuthClass, classify
from packages.auth.key_validator import AuthError, validate_api_key
from packages.auth.sessions import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    csrf_token_matches,
    load_session,
)
from packages.db import session as session_mod

# The legacy names are kept as re-exports: tests and other modules imported
# them from here before the policy module existed.
SKIP_AUTH_PATHS = frozenset({"/", "/health", "/health/ready"})
SKIP_AUTH_PREFIXES: tuple[str, ...] = ("/static",)
GUARDED_PREFIXES: tuple[str, ...] = ("/api/", "/v1/", "/v1beta/")


def _get_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    for k, v in headers:
        if k == name:
            # Lenient decode: a raw non-UTF-8 byte in a credential header is
            # an unauthenticated, remotely reachable input — it must end as
            # a clean 401 for a key that can never validate, not as an
            # unhandled 500 out of the middleware.
            return v.decode("utf-8", "replace")
    return ""


def _cookies(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    raw = _get_header(headers, b"cookie")
    if not raw:
        return {}
    out: dict[str, str] = {}
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name:
            out[name.strip()] = value.strip()
    return out


def _extract_inference_credentials(scope) -> list[str]:
    """Collect the candidate sk-geek-* keys the client's SDK may have sent.

    Order: `Authorization: Bearer` → `x-api-key` → `x-goog-api-key` →
    `?key=` (query-param form only on /v1beta/, matching the legacy Google SDK,
    so credentials-in-URL stays contained).

    Every location is a CANDIDATE, not a commitment: a reverse proxy may inject
    an `Authorization` header of its own, so all locations are tried in turn.
    """
    headers = scope.get("headers", [])
    candidates: list[str] = []

    def _add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    auth_header = _get_header(headers, b"authorization")
    if auth_header.startswith("Bearer "):
        _add(auth_header[7:])
    for name in (b"x-api-key", b"x-goog-api-key"):
        _add(_get_header(headers, name))
    if scope.get("path", "").startswith("/v1beta/"):
        qs = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        vals = qs.get("key")
        if vals:
            _add(vals[0])
    return candidates


_ANTHROPIC_ERROR_TYPES = {401: "authentication_error", 403: "permission_error"}
_GOOGLE_STATUSES = {401: "UNAUTHENTICATED", 403: "PERMISSION_DENIED", 503: "UNAVAILABLE"}


def protocol_for_scope(scope) -> str:
    """Which error envelope the caller's SDK parses: "anthropic" for the
    /v1/messages surface, "gemini" for /v1beta/, else "openai".

    A request carrying `anthropic-version` (the Anthropic SDK and Claude Code
    always send it) also gets the Anthropic envelope — that is how GET
    /v1/models serves them the Anthropic listing, so its failures must speak
    the same language. The header signal is scoped to /v1 paths OTHER than
    /v1/chat/completions, and admin routes under /api are never rewritten."""
    path = scope.get("path", "")
    if path.startswith("/v1/messages"):
        return "anthropic"
    if path.startswith("/v1beta/"):
        return "gemini"
    if (
        path.startswith("/v1/")
        and not path.startswith("/v1/chat/completions")
        and _get_header(scope.get("headers", []), b"anthropic-version")
    ):
        return "anthropic"
    return "openai"


def _error_payload(protocol: str, status: int, message: str, error_type: str) -> bytes:
    """Render the auth error in the envelope the caller's SDK expects."""
    if protocol == "anthropic":
        body: dict = {
            "type": "error",
            "error": {
                "type": _ANTHROPIC_ERROR_TYPES.get(status, "api_error"),
                "message": message,
            },
        }
    elif protocol == "gemini":
        body = {
            "error": {
                "code": status,
                "message": message,
                "status": _GOOGLE_STATUSES.get(status, "INTERNAL"),
            }
        }
    else:
        body = {"error": {"message": message, "type": error_type}}
    return json.dumps(body).encode()


async def _send_error(send, scope, status: int, message: str, error_type: str) -> None:
    body = _error_payload(protocol_for_scope(scope), status, message, error_type)
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({"type": "http.response.body", "body": body})


# Specificity of AuthError messages from validate_api_key. A later
# candidate's "Invalid API key format" must not overwrite an earlier
# "API key revoked" — last-wins hid the useful error when a second
# header (proxy, extra SDK location) sent a non-sk-geek value.
_AUTH_ERROR_SPECIFICITY = {
    "API key revoked": 3,
    "API key expired": 3,
    "Invalid API key": 2,
    "Invalid API key format": 1,
}


def _specificity(message: str) -> int:
    """Rank an AuthError message; unlisted messages default to 2.

    The legacy-prefix rejection is a full sentence and lands on the default 2,
    which already beats "Invalid API key format" (1) -- the generic format
    error a second header would otherwise substitute for it -- while staying
    below a revoked/expired verdict (3) on a genuine key.
    """
    return _AUTH_ERROR_SPECIFICITY.get(message, 2)


def _prefer_auth_error(current: AuthError | None, candidate: AuthError) -> AuthError:
    """Keep the more specific AuthError; on a tie keep the first."""
    if current is None:
        return candidate
    current_rank = (current.status_code, _specificity(current.message))
    candidate_rank = (candidate.status_code, _specificity(candidate.message))
    return candidate if candidate_rank > current_rank else current


def _session_factory():
    return session_mod.session_factory()


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        auth_class = classify(path)

        if auth_class is AuthClass.PUBLIC:
            await self.app(scope, receive, send)
            return

        if auth_class is AuthClass.ADMIN:
            await self._handle_admin(scope, receive, send)
            return

        if auth_class is AuthClass.UNROUTED:
            await self._handle_unrouted(scope, receive, send)
            return

        await self._handle_inference(scope, receive, send)

    # ── unrouted (404/405 territory) ───────────────────────────────────────

    async def _handle_unrouted(self, scope, receive, send) -> None:
        """A path no route serves: accept either credential, never anonymous.

        Real routes can never land here — `assert_routes_classified` fails the
        boot if one is unlisted — so this only decides which "not found" a
        caller sees. Requiring a credential keeps the surface closed while
        still letting an SDK get an honest 404 in its own envelope.
        """
        token = _cookies(scope.get("headers", [])).get(SESSION_COOKIE_NAME, "")
        if token:
            try:
                async with _session_factory()() as session:
                    record = await load_session(session, token, touch=False)
            except Exception:
                record = None
            if record is not None:
                state = scope.setdefault("state", {})
                state["admin_session"] = record
                state["admin_id"] = record.admin_id
                state["admin_username"] = record.username
                state["auth_class"] = AuthClass.UNROUTED.value
                await self.app(scope, receive, send)
                return
        await self._handle_inference(scope, receive, send)

    # ── admin ──────────────────────────────────────────────────────────────

    async def _handle_admin(self, scope, receive, send) -> None:
        token = _cookies(scope.get("headers", [])).get(SESSION_COOKIE_NAME, "")
        if not token:
            await _send_error(
                send, scope, 401,
                "Administrator session required. Sign in at the dashboard.",
                "auth_error",
            )
            return

        method = scope.get("method", "GET").upper()
        try:
            async with _session_factory()() as session:
                record = await load_session(session, token)
                if record is None:
                    await _send_error(
                        send, scope, 401,
                        "Your session has expired or been revoked. Sign in again.",
                        "auth_error",
                    )
                    return

                if method in CSRF_PROTECTED_METHODS:
                    provided = _get_header(
                        scope.get("headers", []), CSRF_HEADER_NAME.encode()
                    )
                    if not csrf_token_matches(record.csrf_token, provided):
                        await _send_error(
                            send, scope, 403,
                            "CSRF token missing or invalid. Reload the dashboard "
                            "and try again.",
                            "forbidden",
                        )
                        return
        except Exception:
            await _send_error(
                send, scope, 503, "Service temporarily unavailable", "server_error"
            )
            return

        state = scope.setdefault("state", {})
        state["admin_session"] = record
        state["admin_id"] = record.admin_id
        state["admin_username"] = record.username
        state["auth_class"] = AuthClass.ADMIN.value
        await self.app(scope, receive, send)

    # ── inference ──────────────────────────────────────────────────────────

    async def _handle_inference(self, scope, receive, send) -> None:
        candidates = _extract_inference_credentials(scope)
        if not candidates:
            await _send_error(
                send, scope, 401,
                "Missing or invalid API key. Send it as 'Authorization: Bearer', "
                "'x-api-key', or 'x-goog-api-key'. (An administrator dashboard "
                "session cannot be used for inference.)",
                "auth_error",
            )
            return

        # Use the session factory with `async with` so the session is
        # GUARANTEED to close on every exit path. The old
        # `async for s in get_session(): break` pattern relied on generator
        # cleanup, which is timing-fragile and leaked connections on error.
        key_context = None
        auth_error: AuthError | None = None
        try:
            async with _session_factory()() as session:
                for raw_key in candidates:
                    try:
                        key_context = await validate_api_key(raw_key, session)
                        break
                    except AuthError as e:
                        auth_error = _prefer_auth_error(auth_error, e)
        except Exception:
            await _send_error(
                send, scope, 503, "Service temporarily unavailable", "server_error"
            )
            return

        if key_context is None:
            status = auth_error.status_code if auth_error else 401
            message = auth_error.message if auth_error else "Invalid API key"
            await _send_error(send, scope, status, message, "auth_error")
            return

        state = scope.setdefault("state", {})
        state["key_context"] = key_context
        state["workspace_id"] = key_context.workspace_id
        state["auth_class"] = AuthClass.INFERENCE.value
        await self.app(scope, receive, send)
