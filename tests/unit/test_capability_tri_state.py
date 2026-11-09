"""Capability resolution is tri-state: Supported / Unsupported / Unknown.

Missing catalog metadata must resolve to Unknown, never Unsupported. An
explicit False from a source stays Unsupported, an explicit True stays
Supported, and JSON mode / JSON Schema remain independent. Administrator
overrides (including an explicit Unknown) survive catalog refreshes, and
strict routing only accepts a confirmed True for a required capability.
"""

from __future__ import annotations

from types import SimpleNamespace

from app import model_metadata as mm
from app.auto_routing import _model_meets, required_capabilities
from app.custom_providers import _models_to_catalog
from packages.litellm_adapter.catalog import CatalogModel


def _catalog_entry(monkeypatch, **meta_overrides) -> CatalogModel:
    """Build one built-in catalog entry from controlled litellm metadata."""
    import litellm

    from packages.litellm_adapter import catalog as cat

    meta = {
        "litellm_provider": "openai",
        "mode": "chat",
        "input_cost_per_token": 1e-6,
        "output_cost_per_token": 2e-6,
    }
    meta.update(meta_overrides)
    monkeypatch.setattr(
        litellm, "model_cost", {"openai/tri-state-probe": meta}, raising=False
    )
    models = cat._build_catalog_from_litellm()
    return next(m for m in models if m.id == "tri-state-probe")


def _row(**kwargs) -> SimpleNamespace:
    base = dict(
        model_id="probe-model",
        metadata_json=None,
        context_length=None,
        supports_tools=False,
        supports_vision=False,
        supports_json_mode=False,
        supports_json_schema=False,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        reference_input_cost_per_token=None,
        reference_output_cost_per_token=None,
        reference_cache_read_cost_per_token=None,
        reference_cache_write_cost_per_token=None,
        reference_source=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _source(entries: dict) -> list[dict]:
    return [{"key": "openai", "name": "openai", "entries": entries, "stale": False}]


def _entry(**kwargs) -> dict:
    base = {
        "input_per_million": 2.5,
        "output_per_million": 10.0,
        "context": 128000,
        "tools": True,
        "vision": True,
        "json_mode": True,
        "json_schema": True,
        "price_state": "loaded",
    }
    base.update(kwargs)
    return base


# ── built-in catalog: missing metadata is Unknown, not Unsupported ─────────


def test_missing_json_mode_resolves_to_unknown(monkeypatch):
    model = _catalog_entry(monkeypatch, supports_response_schema=True)
    assert model.supports_json_mode is None


def test_explicit_false_json_mode_resolves_to_unsupported(monkeypatch):
    model = _catalog_entry(monkeypatch, supports_json_mode=False)
    assert model.supports_json_mode is False


def test_explicit_true_json_mode_resolves_to_supported(monkeypatch):
    model = _catalog_entry(monkeypatch, supports_json_mode=True)
    assert model.supports_json_mode is True


def test_json_schema_true_with_missing_json_mode_keeps_mode_unknown(monkeypatch):
    model = _catalog_entry(monkeypatch, supports_response_schema=True)
    assert model.supports_json_schema is True
    assert model.supports_json_mode is None


def test_json_mode_true_with_missing_json_schema_keeps_schema_unknown(monkeypatch):
    model = _catalog_entry(monkeypatch, supports_json_mode=True)
    assert model.supports_json_mode is True
    assert model.supports_json_schema is None


def test_missing_tools_and_vision_resolve_to_unknown(monkeypatch):
    model = _catalog_entry(monkeypatch)
    assert model.supports_tools is None
    assert model.supports_vision is None


def test_explicit_false_tools_and_vision_resolve_to_unsupported(monkeypatch):
    model = _catalog_entry(
        monkeypatch, supports_function_calling=False, supports_vision=False
    )
    assert model.supports_tools is False
    assert model.supports_vision is False


# ── custom models: metadata states drive catalog entries ───────────────────


def test_custom_model_metadata_states_drive_catalog_entries():
    row = _row()
    mm.apply_capability_override(row, "tools", "supported")
    mm.apply_capability_override(row, "vision", "unsupported")
    mm.apply_capability_override(row, "json_mode", "unknown")
    mm.apply_capability_override(row, "json_schema", "supported")

    entry = _models_to_catalog([row])[0]
    assert entry.supports_tools is True
    assert entry.supports_vision is False
    assert entry.supports_json_mode is None
    assert entry.supports_json_schema is True


def test_unresolved_custom_model_capabilities_are_unknown():
    entry = _models_to_catalog([_row()])[0]
    assert entry.supports_tools is None
    assert entry.supports_vision is None
    assert entry.supports_json_mode is None
    assert entry.supports_json_schema is None


# ── administrator overrides and catalog refresh ────────────────────────────


def test_admin_unsupported_and_unknown_overrides_survive_catalog_refresh():
    row = _row()
    mm.apply_capability_override(row, "tools", "unsupported")
    mm.apply_capability_override(row, "json_mode", "unknown")

    meta, resolved = mm.resolve_one(
        "openai", row, _source({"openai/probe-model": _entry()})
    )

    assert resolved is not None
    assert meta["capabilities"]["tools"]["state"] == "unsupported"
    assert meta["capabilities"]["tools"]["override"] is True
    assert meta["capabilities"]["json_mode"]["state"] == "unknown"
    assert meta["capabilities"]["json_mode"]["override"] is True
    assert row.supports_tools is False
    assert row.supports_json_mode is False


def test_use_catalog_restores_source_derived_value():
    row = _row()
    mm.apply_capability_override(row, "json_mode", "supported")
    mm.clear_capability_override(row, "json_mode")

    meta, _ = mm.resolve_one(
        "openai",
        row,
        _source({"openai/probe-model": _entry(json_mode=False, tools=True)}),
    )

    assert meta["capabilities"]["json_mode"]["state"] == "unsupported"
    assert meta["capabilities"]["json_mode"]["override"] is False
    assert row.supports_json_mode is False
    assert meta["capabilities"]["tools"]["state"] == "supported"
    assert row.supports_tools is True


# ── strict auto routing ────────────────────────────────────────────────────


def _model(**caps) -> CatalogModel:
    return CatalogModel(
        id="probe",
        provider="probe",
        litellm_prefix="openai/",
        **caps,
    )


def test_auto_routing_filters_each_required_capability_independently():
    confirmed = _model(
        supports_tools=True,
        supports_vision=True,
        supports_json_mode=True,
        supports_json_schema=True,
    )
    unknown = _model()
    unsupported = _model(
        supports_tools=False,
        supports_vision=False,
        supports_json_mode=False,
        supports_json_schema=False,
    )

    bodies = {
        "tools": {"tools": [{"type": "function", "function": {"name": "f"}}]},
        "vision": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "x"}}],
                }
            ]
        },
        "json_mode": {"response_format": {"type": "json_object"}},
        "json_schema": {"response_format": {"type": "json_schema"}},
    }
    for capability, body in bodies.items():
        needs = required_capabilities(body)
        assert needs == {capability}
        assert _model_meets(confirmed, needs) is True
        assert _model_meets(unknown, needs) is False
        assert _model_meets(unsupported, needs) is False

    # JSON mode and JSON Schema never stand in for each other.
    mode_only = _model(supports_json_mode=True, supports_json_schema=None)
    schema_only = _model(supports_json_mode=None, supports_json_schema=True)
    assert _model_meets(mode_only, {"json_mode"}) is True
    assert _model_meets(mode_only, {"json_schema"}) is False
    assert _model_meets(schema_only, {"json_schema"}) is True
    assert _model_meets(schema_only, {"json_mode"}) is False


def test_unknown_capabilities_do_not_block_ordinary_text_inference():
    unknown = _model()
    needs = required_capabilities(
        {"messages": [{"role": "user", "content": "hello"}]}
    )
    assert needs == set()
    assert _model_meets(unknown, needs) is True


# ── legacy rows: bare ORM flags without tri-state metadata ─────────────────


def test_legacy_bare_false_flags_resolve_to_unknown():
    """A pre-tri-state row (server_default False, no metadata_json) is never
    mistaken for a source-reported Unsupported."""
    row = _row()
    for capability in ("tools", "vision", "json_mode", "json_schema"):
        assert mm.capability_state(row, capability) == "unknown"
        assert mm.catalog_support(row, capability) is None


def test_legacy_bare_true_flag_counts_as_supported():
    """An operator checkbox saved before tri-state metadata existed keeps its
    Supported meaning."""
    row = _row(supports_tools=True, supports_vision=True)
    assert mm.capability_state(row, "tools") == "supported"
    assert mm.capability_state(row, "vision") == "supported"


def test_refresh_upgrades_legacy_false_to_source_unsupported():
    """Once a source reports False, the row becomes explicitly Unsupported
    with provenance instead of staying ambiguous."""
    row = _row()
    meta, resolved = mm.resolve_one(
        "openai", row, _source({"openai/probe-model": _entry(tools=False)})
    )
    assert resolved is not None
    entry = meta["capabilities"]["tools"]
    assert entry == {
        "state": "unsupported",
        "source": "openai",
        "stale": False,
        "override": False,
    }
    assert row.supports_tools is False


def test_refresh_upgrades_legacy_true_to_source_supported():
    row = _row()
    meta, resolved = mm.resolve_one(
        "openai", row, _source({"openai/probe-model": _entry(tools=True, json_mode=None)})
    )
    assert meta["capabilities"]["tools"]["state"] == "supported"
    assert meta["capabilities"]["tools"]["source"] == "openai"
    assert row.supports_tools is True
    # A source that says nothing downgrades the bare-False default to a
    # recorded Unknown, ready for a later refresh or an operator decision.
    assert meta["capabilities"]["json_mode"]["state"] == "unknown"
    assert meta["capabilities"]["json_mode"]["source"] is None


def test_refresh_downgrades_legacy_true_without_source_evidence():
    """A bare True flag is provisional: if no source confirms it, the next
    refresh records Unknown and clears the flag, so routing never credits an
    unverified capability."""
    row = _row(supports_tools=True)
    meta, resolved = mm.resolve_one(
        "openai", row, _source({"openai/probe-model": _entry(tools=None)})
    )
    assert meta["capabilities"]["tools"]["state"] == "unknown"
    assert row.supports_tools is False
    assert mm.capability_state(row, "tools") == "unknown"


def test_override_pinned_to_legacy_row_survives_refresh():
    """Overriding a legacy row (no prior metadata) is durable: the refresh
    keeps the administrator decision and attributes it correctly."""
    row = _row()
    mm.apply_capability_override(row, "vision", "unsupported")
    mm.apply_capability_override(row, "json_schema", "supported")

    meta, resolved = mm.resolve_one(
        "openai", row, _source({"openai/probe-model": _entry(vision=True, json_schema=False)})
    )
    assert resolved is not None
    assert meta["capabilities"]["vision"] == {
        "state": "unsupported", "source": "administrator_override",
        "stale": False, "override": True,
    }
    assert meta["capabilities"]["json_schema"] == {
        "state": "supported", "source": "administrator_override",
        "stale": False, "override": True,
    }
    assert (row.supports_vision, row.supports_json_schema) == (False, True)
