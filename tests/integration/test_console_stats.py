"""Inventory counts must agree across every page.

The bug this guards: Overview rendered `state.providers.length`, which only
counted built-in provider keys. An operator running entirely on a custom
provider saw "0 providers configured", and the onboarding step "Add at least
one provider key" stayed unticked even though routing worked.

`/api/stats` is now the single definition, and these tests pin its semantics.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def client(env):
    c, _up, _ = env
    return c


@pytest.fixture
def upstream_url(upstream):
    # Custom providers validate that the host resolves, so tests use the mock
    # upstream rather than a placeholder domain.
    return upstream.base_url


async def test_stats_shape(client):
    body = (await client.get("/api/stats")).json()
    for key in (
        "providers_configured",
        "providers_enabled",
        "providers_builtin",
        "providers_custom",
        "models_deployable",
        "models_catalog",
        "models_auto_eligible",
    ):
        assert key in body, key
        assert isinstance(body[key], int), key


async def test_catalog_is_larger_than_deployable(client):
    """The catalogue lists models you cannot serve; that distinction matters.

    Reporting catalog size as "available models" is what made the dashboard
    promise models the user had no key for.
    """
    body = (await client.get("/api/stats")).json()
    assert body["models_catalog"] > body["models_deployable"]


async def test_auto_eligible_is_a_subset_of_deployable(client):
    body = (await client.get("/api/stats")).json()
    assert body["models_auto_eligible"] <= body["models_deployable"]


async def test_custom_provider_counts_as_configured(client, upstream_url):
    """A working custom provider must move the configured count."""
    before = (await client.get("/api/stats")).json()

    r = await client.post(
        "/v1/custom-providers",
        json={
            "display_name": "Stats Test",
            "base_url": upstream_url,
            "api_key": "sk-test-key-for-stats",
            "is_enabled": True,
        },
    )
    assert r.status_code in (200, 201), r.text

    after = (await client.get("/api/stats")).json()
    assert after["providers_custom"] == before["providers_custom"] + 1
    assert after["providers_configured"] == before["providers_configured"] + 1


async def test_disabled_custom_provider_does_not_count(client, upstream_url):
    before = (await client.get("/api/stats")).json()
    r = await client.post(
        "/v1/custom-providers",
        json={
            "display_name": "Disabled One",
            "base_url": upstream_url,
            "api_key": "sk-test-key-disabled",
            "is_enabled": False,
        },
    )
    assert r.status_code in (200, 201), r.text
    after = (await client.get("/api/stats")).json()
    assert after["providers_configured"] == before["providers_configured"]


async def test_stats_requires_admin_session():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": "Bearer sk-geek-not-real"},
    ) as c:
        assert (await c.get("/api/stats")).status_code == 401
