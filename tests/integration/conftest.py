"""Shared integration fixtures.

`env` (real app + SQLite + mock upstream) and `upstream` are defined in
test_routing_integration and reused by the routing-profile, fallback,
accounting and model-intelligence suites. A module may override `upstream`
locally (e.g. a scripted failing upstream); `env` then uses that override.
"""

from tests.integration.test_routing_integration import env, upstream  # noqa: F401
