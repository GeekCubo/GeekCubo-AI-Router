"""Route authorization policy — the boundary itself.

The middleware's correctness rests entirely on this table, so it gets its own
tests:

  * every registered route has an explicit class (startup guard);
  * the classes do not drift (a /v1 route is not assumed to be inference);
  * unlisted paths are not anonymous;
  * representative paths from each family land where they should.
"""

from __future__ import annotations

import pytest

from app.auth_policy import (
    AuthClass,
    UnclassifiedRouteError,
    assert_routes_classified,
    classify,
    explicit_class,
    registered_paths,
)


@pytest.fixture(scope="module")
def app_paths():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    return registered_paths(create_app())


def test_every_registered_route_is_classified(app_paths):
    """The startup guard, asserted directly.

    A new route that nobody classifies must fail here rather than silently
    inheriting UNROUTED (which accepts an inference key).
    """
    assert app_paths, "no routes discovered — registered_paths is broken"
    unclassified = sorted(p for p in app_paths if explicit_class(p) is None)
    assert unclassified == [], f"unclassified routes: {unclassified}"


def test_registered_paths_sees_routes_from_included_routers(app_paths):
    """FastAPI wraps include_router() in an _IncludedRouter with path=None.

    A naive `for r in app.routes if r.path` check would see ~7 paths and
    conclude everything is classified while every /v1 route was invisible.
    """
    assert "/v1/chat/completions" in app_paths
    assert "/v1/providers" in app_paths
    assert "/api/auth/login" in app_paths
    assert len(app_paths) > 30


def test_assert_routes_classified_rejects_an_unknown_route():
    with pytest.raises(UnclassifiedRouteError) as exc:
        assert_routes_classified({"/v1/chat/completions", "/v1/brand-new-thing"})
    assert "/v1/brand-new-thing" in str(exc.value)


@pytest.mark.parametrize("path", [
    "/health",
    "/health/ready",
    "/",
    "/providers",
    "/settings/security",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
])
def test_public_paths(path):
    assert classify(path) is AuthClass.PUBLIC


def test_static_prefix_is_public_including_the_mount_itself():
    assert classify("/static/app.js") is AuthClass.PUBLIC
    assert classify("/static") is AuthClass.PUBLIC


@pytest.mark.parametrize("path", [
    # inference surfaces
    "/v1/chat/completions",
    "/v1/models",
    "/v1/messages",
    "/v1/messages/count_tokens",
    "/v1beta/models",
    "/v1beta/models/gemini-1.5-flash",
    "/v1beta/models/models/gemini-1.5-flash",
    "/v1beta/models/openrouter/foo:generateContent",
])
def test_inference_paths(path):
    assert classify(path) is AuthClass.INFERENCE


@pytest.mark.parametrize("path", [
    # administrative surfaces, several of which look like inference
    "/v1/providers",
    "/v1/providers/openai",
    "/v1/custom-providers",
    "/v1/custom-providers/test",
    "/v1/custom-providers/abc/models",
    "/v1/keys",
    "/v1/keys/abc/rotate",
    "/v1/routing",
    "/v1/analytics/recent",
    "/v1/quality",
    "/v1/quality/overrides/gpt-4o",
    "/api/models",
    # session housekeeping requires a session, so it is admin-classed
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/change-password",
    "/api/auth/sessions",
    "/api/auth/sessions/revoke-others",
])
def test_admin_paths(path):
    assert classify(path) is AuthClass.ADMIN


def test_v1_prefix_alone_does_not_imply_inference():
    """/v1/keys and /v1/chat/completions share a prefix and nothing else."""
    assert classify("/v1/keys") is AuthClass.ADMIN
    assert classify("/v1/chat/completions") is AuthClass.INFERENCE


def test_trailing_slash_does_not_escape_the_policy():
    assert classify("/v1/providers/") is AuthClass.ADMIN
    assert classify("/health/") is AuthClass.PUBLIC
    assert classify("/v1/chat/completions/") is AuthClass.INFERENCE


def test_unknown_path_is_unrouted_and_never_public():
    cls = classify("/totally/unknown")
    assert cls is AuthClass.UNROUTED
    assert cls is not AuthClass.PUBLIC


def test_lookalike_inference_paths_do_not_match_by_prefix():
    """A prefix match would let /v1/models/admin-widget pass as inference."""
    assert classify("/v1/modelsomething") is AuthClass.UNROUTED
    assert classify("/v1beta/modelz") is AuthClass.UNROUTED


def test_admin_prefixes_cannot_be_escaped_by_path_segments():
    assert classify("/v1/providers/../keys") is AuthClass.ADMIN
    assert classify("/v1/custom-providers/1/models/2") is AuthClass.ADMIN
