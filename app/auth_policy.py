"""Explicit route authorization policy.

One table, in one place, that says what every path is allowed to do. The
middleware consults this — never `path.startswith("/v1/")`, which was the old
(and wrong) approximation: `/v1/keys` is administrative, `/v1/chat/completions`
is inference, and both live under `/v1/`.

Three classes:

``PUBLIC``
    No credential at all. Health, the SPA shell, static assets, and the
    authentication endpoints that necessarily precede a session. Anything here
    must be safe to serve to an anonymous caller.

``ADMIN``
    Browser session only. Provider credentials, custom providers, model
    catalog administration, routing, analytics, quality overrides, API-key
    management, and everything under ``/api/``. An ``sk-geek-*`` inference key
    does NOT satisfy these routes — an inference key is a machine credential
    for an application, not an operator credential for the console.

``INFERENCE``
    ``sk-geek-*`` API key only. The OpenAI / Anthropic / Gemini surfaces plus
    the model listing their SDKs call. A dashboard session cookie does NOT
    satisfy these: a session must not become a portable inference credential,
    and inference traffic must keep working when the administrator is logged
    out.

**Default deny.** `classify()` returns ADMIN for anything it does not
recognize. A new route is therefore protected the moment it is added; making
it public requires an explicit edit here, which is exactly the review we want.
`test_auth_policy.py` asserts every registered route is classified on purpose,
so an unclassified route fails the suite rather than silently shipping open.
"""

from __future__ import annotations

import re
from enum import Enum


class AuthClass(str, Enum):
    PUBLIC = "public"
    ADMIN = "admin"
    INFERENCE = "inference"
    # A path no route serves. Accepts either credential so a legitimate caller
    # receives an honest 404/405 in its own protocol envelope instead of a
    # misleading "Administrator session required". Never anonymous.
    #
    # This is safe only because NO registered route may be UNROUTED:
    # `assert_routes_classified()` runs in create_app and refuses to boot if a
    # route was added without an explicit entry here.
    UNROUTED = "unrouted"


# Exact-match public paths: no credential, no data beyond the shell itself.
_PUBLIC_EXACT: frozenset[str] = frozenset({
    "/",
    "/health",
    "/health/ready",
    # SPA deep links. All of them serve the same unauthenticated HTML shell;
    # the client still has to hold a session before any API call succeeds.
    "/providers",
    "/models",
    "/routing",
    "/analytics",
    "/keys",
    "/settings",
    "/settings/security",
    "/settings/api-keys",
    # Authentication endpoints that necessarily precede a session. Each
    # enforces its own restriction: setup requires a one-time CLI-issued token
    # and refuses once an administrator exists; login is rate limited.
    #
    # Everything ELSE under /api/auth (me, logout, change-password, sessions)
    # is deliberately NOT here: it falls through to ADMIN, so the middleware
    # resolves the session and enforces CSRF on it like any other admin route.
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
})

_PUBLIC_PREFIXES: tuple[str, ...] = ("/static",)

# --- inference surfaces ---------------------------------------------------
# Kept as exact paths / narrow patterns rather than "/v1/" so a future admin
# route under /v1 cannot be swept into the inference class by accident.

_INFERENCE_EXACT: frozenset[str] = frozenset({
    "/v1/chat/completions",
    "/v1/models",
    "/v1/messages",
    "/v1/messages/count_tokens",
    "/v1beta/models",
})

_INFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        # Gemini: GET /v1beta/models/{model_id:path} and
        # POST /v1beta/models/{model_and_action:path}. Both are `:path`
        # converters, so the id may contain slashes — "models/gemini-1.5-flash"
        # (the resource-name form the listing itself returns) and
        # provider-qualified ids like "openrouter/foo:generateContent". The
        # whole /v1beta/models/ subtree is inference; nothing administrative
        # lives under /v1beta at all.
        r"^/v1beta/models/.+$",
        r"^/v1beta/tunedModels/.+$",
    )
)

# --- administrative surfaces ---------------------------------------------
# Exact matches first, then prefixes for families with ids in the path.

_ADMIN_EXACT: frozenset[str] = frozenset({
    "/v1/providers",
    "/v1/custom-providers",
    "/v1/custom-providers/test",
    "/v1/routing",
    "/v1/routing-profiles",
    "/v1/model-intelligence",
    "/v1/keys",
    "/v1/quality",
    "/v1/quality/refresh",
    "/v1/quality/auto-preview",
    "/v1/quality/overrides",
    "/v1/quality/key",
    "/v1/quality/key/test",
    "/api/models",
    "/api/stats",
    "/api/routing/models",
    "/api/routing/explain",
})

_ADMIN_PREFIXES: tuple[str, ...] = (
    "/v1/providers/",
    "/v1/custom-providers/",
    "/v1/routing-profiles/",
    "/v1/model-intelligence/",
    "/v1/keys/",
    "/v1/quality/overrides/",
    "/v1/analytics",
    "/api/",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _is_inference(path: str) -> bool:
    if path in _INFERENCE_EXACT:
        return True
    return any(p.match(path) for p in _INFERENCE_PATTERNS)


def _is_admin(path: str) -> bool:
    if path in _ADMIN_EXACT:
        return True
    return any(path.startswith(p) for p in _ADMIN_PREFIXES)


def explicit_class(path: str) -> AuthClass | None:
    """The class explicitly assigned to `path`, or None if it is unlisted."""
    normalized = path.rstrip("/") or "/"
    if _is_public(normalized):
        return AuthClass.PUBLIC
    if _is_inference(normalized):
        return AuthClass.INFERENCE
    if _is_admin(normalized):
        return AuthClass.ADMIN
    return None


def classify(path: str) -> AuthClass:
    """Return the auth class the middleware enforces for `path`.

    Unlisted paths are UNROUTED: they require *some* valid credential (never
    anonymous), and because startup guarantees every real route is listed,
    an UNROUTED request can only ever reach a 404/405 handler.
    """
    found = explicit_class(path)
    return found if found is not None else AuthClass.UNROUTED


class UnclassifiedRouteError(RuntimeError):
    """A registered route has no explicit authorization class."""


def registered_paths(app) -> set[str]:
    """Every path the app actually serves, including mounted routers.

    FastAPI wraps `include_router(...)` results in an `_IncludedRouter` whose
    `path` is None, so iterating `app.routes` alone (the obvious way) silently
    reports only the handful of routes declared directly in create_app — the
    check would pass while every /v1 route was invisible to it.
    """
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
            continue
        original = getattr(route, "original_router", None)
        for sub in getattr(original, "routes", ()) or ():
            sub_path = getattr(sub, "path", None)
            if sub_path:
                paths.add(sub_path)
    return paths


def assert_routes_classified(paths) -> None:
    """Refuse to boot when a registered route is missing from this policy.

    Default-deny alone is not enough once UNROUTED accepts an inference key: a
    new admin route that nobody listed would otherwise be reachable by any
    sk-geek-* key. Failing at startup turns "forgot to classify" from a silent
    security hole into a crash the developer sees immediately.
    """
    missing = sorted({p for p in paths if explicit_class(p) is None})
    if missing:
        raise UnclassifiedRouteError(
            "Routes without an explicit auth class in app/auth_policy.py: "
            + ", ".join(missing)
        )


def is_inference_path(path: str) -> bool:
    return classify(path) is AuthClass.INFERENCE


def is_public_path(path: str) -> bool:
    return classify(path) is AuthClass.PUBLIC


def is_admin_path(path: str) -> bool:
    return classify(path) is AuthClass.ADMIN


# State-changing methods that need CSRF protection on admin routes. GET/HEAD
# are safe by definition; OPTIONS must stay open for CORS preflight.
CSRF_PROTECTED_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
