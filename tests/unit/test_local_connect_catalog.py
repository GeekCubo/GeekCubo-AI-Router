"""Local AI Connect — catalog ids, settings access and router deployments.

These pin the naming contract that ties the four moving parts together: the
connector reports a model key, the server exposes `local/<machine>/<model>`,
the router deploys `geekcubo_local/<machine>::<model>`, and the custom-provider
handler parses that wire id back into a dispatch target. A change to any one of
the separators silently breaks routing, so the round-trip lives here.
"""

from __future__ import annotations

import pytest

from app.local_connect import catalog as local_catalog
from packages.db.models.local_connect import (
    LocalMachine,
    LocalModel,
    LocalSettings,
)

# ── id helpers (pure) ──────────────────────────────────────────────────────


def test_wire_model_id_round_trips_model_keys_with_slashes():
    """Model keys like `mlx-community/Qwen2.5-7B` keep their slash."""
    wire = local_catalog.wire_model_id("m-1", "mlx-community/Qwen2.5-7B")
    assert wire == "m-1::mlx-community/Qwen2.5-7B"
    assert local_catalog.parse_wire_model_id(wire) == (
        "m-1",
        "mlx-community/Qwen2.5-7B",
    )


def test_parse_wire_model_id_accepts_router_prefixed_form():
    """The Router hands the handler the `geekcubo_local/` prefixed id."""
    parsed = local_catalog.parse_wire_model_id("geekcubo_local/m-1::llama3.1:8b")
    assert parsed == ("m-1", "llama3.1:8b")


@pytest.mark.parametrize("value", ["", "m-1", "::", "m-1::", "::llama"])
def test_parse_wire_model_id_rejects_malformed(value):
    assert local_catalog.parse_wire_model_id(value) is None


def test_local_model_id_uses_machine_uuid():
    machine = LocalMachine(display_name="Studio", credential_hash="h", credential_prefix="lc-")
    machine.id = "8f14e45f"
    assert local_catalog.local_model_id(machine, "llama3.1:8b") == "local/8f14e45f/llama3.1:8b"


def test_machine_id_of_model_id_ignores_slashes_in_model_key():
    assert (
        local_catalog.machine_id_of_model_id("local/m-1/mlx-community/Qwen2.5-7B")
        == "m-1"
    )


@pytest.mark.parametrize("value", ["", "m-1/llama", "local/m-1", "cloud/m-1/llama"])
def test_machine_id_of_model_id_rejects_non_local(value):
    assert local_catalog.machine_id_of_model_id(value) is None


def test_machine_adapters_tolerates_bad_json():
    machine = LocalMachine(
        display_name="Box", credential_hash="h", credential_prefix="lc-", adapters_json="not json"
    )
    assert local_catalog.machine_adapters(machine) == []


def test_machine_adapters_reads_list():
    machine = LocalMachine(
        display_name="Box",
        credential_hash="h",
        credential_prefix="lc-",
        adapters_json='["ollama", "lmstudio"]',
    )
    assert local_catalog.machine_adapters(machine) == ["ollama", "lmstudio"]


# ── settings: read paths must not write ────────────────────────────────────


async def _seed_workspace(db):
    from app.seed import seed_initial_state

    await seed_initial_state(db)


async def test_read_local_settings_returns_defaults_without_inserting(db_session):
    await _seed_workspace(db_session)
    first = await local_catalog.read_local_settings(db_session, "default")
    second = await local_catalog.read_local_settings(db_session, "default")

    assert first.enabled is True
    assert first.eligible_for_auto is True
    assert first.no_cloud_fallback is False
    # Transient objects, distinct per call, and no row persisted.
    assert first is not second
    assert (await db_session.get(LocalSettings, "default")) is None


async def test_read_local_settings_returns_stored_row(db_session):
    await _seed_workspace(db_session)
    row = LocalSettings(
        workspace_id="default", enabled=False, eligible_for_auto=False, no_cloud_fallback=True
    )
    db_session.add(row)
    await db_session.flush()

    loaded = await local_catalog.read_local_settings(db_session, "default")
    assert loaded.enabled is False
    assert loaded.no_cloud_fallback is True


async def test_load_local_settings_inserts_once(db_session):
    await _seed_workspace(db_session)
    created = await local_catalog.load_local_settings(db_session, "default")
    assert created.workspace_id == "default"
    assert (await db_session.get(LocalSettings, "default")) is not None
    again = await local_catalog.load_local_settings(db_session, "default")
    assert again is (await db_session.get(LocalSettings, "default"))


# ── catalog entries / deployments ──────────────────────────────────────────


async def _approved_machine(db, *, name="Studio", eligible=True, machine_id="m-1"):
    machine = LocalMachine(
        display_name=name,
        status="approved",
        credential_hash=f"h-{machine_id}",
        credential_prefix="lc-...abcd",
        eligible_for_auto=eligible,
    )
    machine.id = machine_id
    db.add(machine)
    await db.flush()
    return machine


async def _model(db, machine, *, key="llama3.1:8b", enabled=True, adapter="ollama"):
    row = LocalModel(
        machine_id=machine.id,
        model_key=key,
        display_name=key,
        adapter=adapter,
        is_enabled=enabled,
        context_length=8192,
        supports_tools=True,
    )
    db.add(row)
    await db.flush()
    return row


async def test_local_catalog_entries_are_zero_priced(db_session):
    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session)
    await _model(db_session, machine)

    entries = await local_catalog.local_catalog_entries(db_session)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == "local/m-1/llama3.1:8b"
    assert entry.price_source == "local"
    assert entry.input_cost_per_token == 0.0
    assert entry.output_cost_per_token == 0.0
    assert entry.supports_tools is True


async def test_local_catalog_entries_disabled_when_settings_off(db_session):
    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session)
    await _model(db_session, machine)
    db_session.add(LocalSettings(workspace_id="default", enabled=False))
    await db_session.flush()

    assert await local_catalog.local_catalog_entries(db_session) == []


async def test_local_catalog_entries_auto_filter_requires_machine_eligibility(db_session):
    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session, eligible=False)
    await _model(db_session, machine)

    assert await local_catalog.local_catalog_entries(db_session, eligible_only=True) == []
    listing = await local_catalog.local_catalog_entries(db_session, eligible_only=False)
    assert [e.id for e in listing] == ["local/m-1/llama3.1:8b"]


async def test_local_catalog_entries_skips_disabled_models(db_session):
    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session)
    await _model(db_session, machine, key="llama3.1:8b")
    await _model(db_session, machine, key="disabled-model", enabled=False)

    listing = await local_catalog.local_catalog_entries(db_session, eligible_only=False)
    assert [e.id for e in listing] == ["local/m-1/llama3.1:8b"]


async def test_local_catalog_entries_skip_pending_and_revoked_machines(db_session):
    await _seed_workspace(db_session)
    pending = await _approved_machine(db_session, name="Pending", machine_id="p-1")
    pending.status = "pending"
    revoked = await _approved_machine(db_session, name="Revoked", machine_id="r-1")
    revoked.status = "revoked"
    await db_session.flush()
    await _model(db_session, pending, key="pending-model")
    await _model(db_session, revoked, key="revoked-model")

    assert await local_catalog.local_catalog_entries(db_session, eligible_only=False) == []


async def test_load_local_deployments_maps_wire_and_deployment_ids(db_session):
    from app.local_connect import deployments

    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session)
    await _model(db_session, machine)

    views = await deployments.load_local_deployments(db_session)
    assert len(views) == 1
    view = views[0]
    assert view.model_name == "local/m-1/llama3.1:8b"
    assert view.wire_model == "geekcubo_local/m-1::llama3.1:8b"
    assert view.deployment_id == "local::m-1::llama3.1:8b"
    assert view.machine_id == "m-1"
    assert view.model_key == "llama3.1:8b"


async def test_load_local_deployments_empty_when_feature_disabled(db_session):
    from app.local_connect import deployments

    await _seed_workspace(db_session)
    machine = await _approved_machine(db_session)
    await _model(db_session, machine)
    db_session.add(LocalSettings(workspace_id="default", enabled=False))
    await db_session.flush()

    assert await deployments.load_local_deployments(db_session) == []


# ── auto-routing price gate ────────────────────────────────────────────────


def test_local_price_source_is_priced_for_auto():
    from app.auto_routing import is_priced_for_auto
    from packages.litellm_adapter.catalog import CatalogModel

    model = CatalogModel(
        id="local/m-1/llama3.1:8b",
        provider="local",
        litellm_prefix="geekcubo_local/",
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        price_source="local",
    )
    assert is_priced_for_auto(model) is True


def test_unpriced_zero_cost_cloud_model_stays_out_of_auto():
    """The local exemption must not leak to a zero-priced cloud stub."""
    from app.auto_routing import is_priced_for_auto
    from packages.litellm_adapter.catalog import CatalogModel

    model = CatalogModel(
        id="custom/x",
        provider="custom",
        litellm_prefix="openai/",
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        price_source="custom",
    )
    assert is_priced_for_auto(model) is False


def test_local_policy_defaults_and_validation():
    from app.routing_policy import DEFAULT_POLICY, PolicyError, normalize_policy

    assert DEFAULT_POLICY["local"]["enabled"] is True
    assert DEFAULT_POLICY["local"]["no_cloud_fallback"] is False
    assert DEFAULT_POLICY["local"]["machines"] == []

    out = normalize_policy(
        {"local": {"enabled": False, "no_cloud_fallback": True, "machines": ["m-1", "", "m-2"]}}
    )
    assert out["local"] == {
        "enabled": False,
        "no_cloud_fallback": True,
        "machines": ["m-1", "m-2"],
    }

    with pytest.raises(PolicyError):
        normalize_policy({"local": {"machines": "m-1"}})
    with pytest.raises(PolicyError):
        normalize_policy({"local": "on"})


def test_build_deployments_appends_local_entries_as_zero_cost():
    from app.config import Settings
    from app.local_connect.deployments import LocalDeploymentView
    from app.router_cache import build_deployments

    views = [
        LocalDeploymentView(
            model_name="local/m-1/llama3.1:8b",
            wire_model="geekcubo_local/m-1::llama3.1:8b",
            deployment_id="local::m-1::llama3.1:8b",
            machine_id="m-1",
            model_key="llama3.1:8b",
        )
    ]
    deps = build_deployments(
        env_keys={}, db_keys=[], settings=Settings(_env_file=None), local_models=views
    )
    assert len(deps) == 1
    dep = deps[0]
    assert dep.model_name == "local/m-1/llama3.1:8b"
    assert dep.litellm_model == "geekcubo_local/m-1::llama3.1:8b"
    assert dep.provider == "local"
    assert dep.custom_llm_provider == "geekcubo_local"
    assert dep.input_cost_per_token == 0.0
    assert dep.output_cost_per_token == 0.0
    assert dep.operator_priced is True
    assert dep.deployment_id == "local::m-1::llama3.1:8b"
