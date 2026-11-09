from __future__ import annotations

from types import SimpleNamespace

from app import model_metadata as mm


def _model(**kwargs):
    base = dict(
        model_id="gpt-4o",
        metadata_json=None,
        context_length=None,
        supports_tools=False,
        supports_vision=False,
        supports_json_mode=False,
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


def _source(key: str, entries: dict, *, stale: bool = False):
    return {"key": key, "name": key, "entries": entries, "stale": stale}


def _entry(**kwargs):
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


def test_exact_provider_match_is_trusted_provider_catalog():
    m = _model()
    sources = [_source("openai", {"openai/gpt-4o": _entry()})]
    meta, resolved = mm.resolve_one("openai", m, sources)

    assert resolved is not None
    assert meta["identity"]["confidence"] == "exact_provider"
    assert meta["reference"]["trust"] == "provider_catalog"
    assert m.reference_input_cost_per_token == 2.5 / 1_000_000
    assert m.context_length == 128000
    assert m.supports_tools is True
    assert meta["capabilities"]["tools"]["state"] == "supported"


def test_custom_slug_unique_bare_is_only_a_reference_estimate():
    m = _model()
    sources = [_source("openai", {"openai/gpt-4o": _entry()})]
    meta, _ = mm.resolve_one("apixo", m, sources)

    assert meta["identity"]["confidence"] == "unique_bare"
    assert meta["identity"]["catalog_key"] == "openai/gpt-4o"
    assert meta["reference"]["trust"] == "reference_estimate"
    assert mm.effective_custom_price(m) == (None, None, "unknown")
    assert mm.effective_routing_price(m)[:2] == (2.5e-6, 10e-6)


def test_ambiguous_bare_id_does_not_guess_a_price():
    m = _model(model_id="gpt-4o")
    sources = [
        _source("openai", {"openai/gpt-4o": _entry()}),
        _source("azure", {"azure/gpt-4o": _entry(input_per_million=3.0)}),
    ]
    meta, resolved = mm.resolve_one("aggregator", m, sources)

    assert resolved is None
    assert meta["identity"]["confidence"] == "ambiguous"
    assert len(meta["identity"]["candidates"]) == 2
    assert m.reference_input_cost_per_token is None
    assert meta["reference"]["trust"] == "unknown"


def test_alias_overrides_ambiguous_match():
    m = _model(metadata_json=mm.dump_metadata({"manual": {"alias": "azure/gpt-4o"}}))
    sources = [
        _source("openai", {"openai/gpt-4o": _entry()}),
        _source("azure", {"azure/gpt-4o": _entry(input_per_million=3.0)}),
    ]
    meta, _ = mm.resolve_one("aggregator", m, sources)

    assert meta["identity"]["confidence"] == "alias"
    assert meta["identity"]["catalog_key"] == "azure/gpt-4o"
    assert m.reference_input_cost_per_token == 3.0 / 1_000_000


def test_catalog_never_overwrites_confirmed_custom_prices():
    m = _model(input_cost_per_token=1e-6, output_cost_per_token=2e-6)
    sources = [_source("openai", {"openai/gpt-4o": _entry()})]
    mm.resolve_one("openai", m, sources)

    assert m.input_cost_per_token == 1e-6
    assert m.output_cost_per_token == 2e-6
    assert mm.effective_custom_price(m) == (1e-6, 2e-6, "custom")
    assert m.reference_input_cost_per_token == 2.5 / 1_000_000


def test_explicit_capability_override_survives_refresh():
    m = _model(metadata_json=mm.dump_metadata({
        "manual": {"capabilities": {"vision": True}},
        "capabilities": {"vision": {"state": "unsupported", "source": "administrator_override"}},
    }))
    sources = [_source("openai", {"openai/gpt-4o": _entry(vision=True)})]
    mm.resolve_one("openai", m, sources)

    assert m.supports_vision is False
    meta = mm.load_metadata(m.metadata_json)
    assert meta["capabilities"]["vision"]["state"] == "unsupported"
    assert meta["capabilities"]["vision"]["source"] == "administrator_override"


def test_unknown_price_state_is_not_treated_as_free():
    m = _model()
    sources = [_source("openai", {"openai/gpt-4o": _entry(price_state="unknown")})]
    meta, _ = mm.resolve_one("openai", m, sources)

    assert m.reference_input_cost_per_token is None
    assert meta["reference"]["price_state"] == "unknown"
    assert mm.effective_routing_price(m) == (0.0, 0.0, "unknown")


def test_stale_source_is_marked_without_becoming_authoritative():
    m = _model()
    sources = [_source("openai", {"openai/gpt-4o": _entry()}, stale=True)]
    meta, _ = mm.resolve_one("openai", m, sources)

    assert meta["reference"]["stale"] is True
    assert meta["reference"]["price_state"] == "cached"
    assert meta["capabilities"]["tools"]["stale"] is True


def test_vendor_prefixed_model_id_matches_exact_catalog_key():
    m = _model(model_id="openai/gpt-4o")
    sources = [_source("openai", {"openai/gpt-4o": _entry()})]
    meta, _ = mm.resolve_one("aggregator", m, sources)

    assert meta["identity"]["confidence"] == "vendor_prefix"
    assert meta["identity"]["catalog_key"] == "openai/gpt-4o"


def test_unmatched_resolution_preserves_manual_reference_provenance():
    m = _model()
    mm.set_reference_price(m, input_per_million=4, output_per_million=8)
    mm.mark_context_manual(m)
    m.context_length = 42
    mm.apply_capability_override(m, "tools", "unknown")
    before = mm.load_metadata(m.metadata_json)
    meta, resolved = mm.resolve_one("aggregator", m, [])
    assert resolved is None
    for key in ("manual", "reference", "context"):
        assert meta[key] == before[key]
    assert meta["capabilities"]["tools"] == before["capabilities"]["tools"]
    assert m.context_length == 42
    assert m.reference_source == "administrator"


def test_resolve_missing_context_removes_stale_value():
    m = _model(context_length=64000)
    meta, _ = mm.resolve_one("openai", m, [
        _source("mock", {"openai/gpt-4o": _entry(context=None)})
    ])
    assert m.context_length is None
    assert meta["context"]["manual"] is False


def test_partial_custom_price_preserves_other_rates():
    m = _model()
    mm.apply_custom_price(m, input_per_million=1, output_per_million=2, cache_read_per_million=3)
    mm.apply_custom_price(m, input_per_million=4, output_per_million=None)
    assert mm.effective_custom_price(m) == (4e-6, 2e-6, "custom")
    assert mm.load_metadata(m.metadata_json)["custom"]["cache_read_per_million"] == 3


# ── match_status / preview_model (discovery preview) ────────────────────────


def test_match_status_maps_confidence_and_core_fields():
    complete = {
        "context": 128000, "input_per_million": 2.5,
        "output_per_million": 10.0, "tools": True,
    }
    assert mm.match_status("exact_provider", complete) == "resolved"
    assert mm.match_status("alias", complete) == "resolved"
    assert mm.match_status("unique_bare", complete) == "resolved"
    # Any missing core field downgrades a real match to partial.
    assert mm.match_status("exact_provider", {**complete, "context": None}) == "partial"
    assert mm.match_status("exact_provider", {**complete, "input_per_million": None}) == "partial"
    assert mm.match_status("exact_provider", {**complete, "output_per_million": None}) == "partial"
    assert mm.match_status("exact_provider", {**complete, "tools": None}) == "partial"
    assert mm.match_status("ambiguous", complete) == "ambiguous"
    assert mm.match_status("none", complete) == "unmatched"


def test_preview_model_resolves_exact_provider_without_persisting():
    sources = [_source("openai", {"openai/gpt-4o": _entry()})]
    preview = mm.preview_model("openai", "gpt-4o", sources, alias=None)

    assert preview["catalog_key"] == "openai/gpt-4o"
    assert preview["confidence"] == "exact_provider"
    assert preview["status"] == "resolved"
    assert preview["fields"]["context"] == 128000
    assert preview["price_state"] == "reference"
    assert preview["stale"] is False


def test_preview_model_reports_partial_when_fields_missing():
    sources = [_source("openai", {"openai/gpt-4o": _entry(context=None)})]
    preview = mm.preview_model("openai", "gpt-4o", sources, alias=None)

    assert preview["status"] == "partial"
    assert preview["fields"]["context"] is None


def test_preview_model_lists_candidates_for_ambiguous_id():
    sources = [
        _source("openai", {"openai/gpt-4o": _entry()}),
        _source("azure", {"azure/gpt-4o": _entry(input_per_million=3.0)}),
    ]
    preview = mm.preview_model("apixo", "gpt-4o", sources, alias=None)

    assert preview["confidence"] == "ambiguous"
    assert preview["status"] == "ambiguous"
    assert preview["catalog_key"] is None
    assert set(preview["candidates"]) == {"openai/gpt-4o", "azure/gpt-4o"}


def test_preview_model_honours_alias_for_ambiguous_id():
    sources = [
        _source("openai", {"openai/gpt-4o": _entry()}),
        _source("azure", {"azure/gpt-4o": _entry(input_per_million=3.0)}),
    ]
    preview = mm.preview_model("apixo", "gpt-4o", sources, alias="azure/gpt-4o")

    assert preview["confidence"] == "alias"
    assert preview["status"] == "resolved"
    assert preview["catalog_key"] == "azure/gpt-4o"
    assert preview["fields"]["input_per_million"] == 3.0


def test_preview_model_unmatched_has_no_key():
    preview = mm.preview_model("apixo", "totally-new-model", [], alias=None)

    assert preview["confidence"] == "none"
    assert preview["status"] == "unmatched"
    assert preview["catalog_key"] is None
    assert preview["candidates"] == []
    assert preview["price_state"] == "unknown"


def test_capabilities_resolve_independently_even_when_price_is_unknown():
    m = _model(model_id="vis-tool")
    sources = [_source("litellm", {"apixo/vis-tool": _entry(
        price_state="unknown", input_per_million=None, output_per_million=None,
        tools=True, vision=True, json_mode=False, json_schema=None, context=64000,
    )})]
    meta, resolved = mm.resolve_one("apixo", m, sources)

    assert resolved is not None
    assert (m.supports_tools, m.supports_vision, m.supports_json_mode, m.supports_json_schema) == (True, True, False, False)
    caps = meta["capabilities"]
    assert caps["tools"]["state"] == "supported"
    assert caps["vision"]["state"] == "supported"
    assert caps["json_mode"]["state"] == "unsupported"
    assert caps["json_schema"]["state"] == "unknown"
    assert all(caps[c]["source"] == "litellm" for c in ("tools", "vision", "json_mode"))
    assert caps["json_schema"]["source"] is None
    assert m.context_length == 64000
    assert meta["context"]["source"] == "litellm"
    assert m.reference_input_cost_per_token is None
    assert meta["reference"]["price_state"] == "unknown"
    assert mm.effective_custom_price(m) == (None, None, "unknown")


def test_missing_capability_stays_unknown_and_fields_fill_from_next_source():
    m = _model(model_id="m1")
    sources = [
        _source("litellm", {"apixo/m1": _entry(tools=True, vision=None, json_mode=None, json_schema=None, context=None)}),
        _source("models-dev", {"apixo/m1": _entry(tools=False, vision=None, json_mode=None, json_schema=True, context=32000)}),
    ]
    meta, _ = mm.resolve_one("apixo", m, sources)

    caps = meta["capabilities"]
    assert caps["tools"] == {"state": "supported", "source": "litellm", "stale": False, "override": False}
    assert caps["vision"]["state"] == "unknown" and caps["vision"]["source"] is None
    # models.dev reports structured outputs, which is JSON Schema evidence —
    # it must never be borrowed as JSON-mode evidence.
    assert caps["json_mode"]["state"] == "unknown" and caps["json_mode"]["source"] is None
    assert caps["json_schema"]["state"] == "supported" and caps["json_schema"]["source"] == "models-dev"
    assert m.supports_vision is False
    assert m.supports_json_mode is False and m.supports_json_schema is True
    assert m.context_length == 32000
    assert meta["context"]["source"] == "models-dev"


def test_ambiguous_model_never_borrows_capabilities():
    m = _model(model_id="gpt-4o")
    sources = [
        _source("openai", {"openai/gpt-4o": _entry()}),
        _source("azure", {"azure/gpt-4o": _entry()}),
    ]
    meta, _ = mm.resolve_one("aggregator", m, sources)

    assert (m.supports_tools, m.supports_vision, m.supports_json_mode, m.supports_json_schema) == (False, False, False, False)
    assert {meta["capabilities"][c]["state"] for c in ("tools", "vision", "json_mode", "json_schema")} == {"unknown"}
    assert m.context_length is None


def test_explicit_unknown_override_survives_refresh():
    m = _model()
    mm.apply_capability_override(m, "tools", "unknown")
    sources = [_source("openai", {"openai/gpt-4o": _entry(tools=True)})]
    meta, _ = mm.resolve_one("openai", m, sources)

    assert m.supports_tools is False
    assert meta["capabilities"]["tools"]["state"] == "unknown"
    assert meta["capabilities"]["tools"]["source"] == "administrator_override"
    assert meta["capabilities"]["vision"]["state"] == "supported"


def test_json_mode_and_json_schema_are_resolved_independently():
    mode_only = _model(model_id="mode-only")
    schema_only = _model(model_id="schema-only")
    sources = [_source("litellm", {
        # `supports_json_mode` is the only JSON-mode evidence key.
        "litellm/mode-only": _entry(tools=True, json_mode=True, json_schema=None),
        # `supports_response_schema` is JSON-Schema evidence only.
        "litellm/schema-only": _entry(tools=True, json_mode=None, json_schema=True),
    })]
    mm.resolve_one("litellm", mode_only, sources)
    mm.resolve_one("litellm", schema_only, sources)

    assert mode_only.supports_json_mode is True and mode_only.supports_json_schema is False
    assert schema_only.supports_json_mode is False and schema_only.supports_json_schema is True


def test_per_capability_overrides_and_catalog_reversion():
    m = _model()
    mm.apply_capability_override(m, "json_mode", "supported")
    mm.apply_capability_override(m, "json_schema", "unsupported")
    sources = [_source("litellm", {"openai/gpt-4o": _entry(
        json_mode=False, json_schema=True,
    )})]
    meta, _ = mm.resolve_one("openai", m, sources)

    # Both overrides survive the refresh, each on its own capability.
    assert meta["capabilities"]["json_mode"] == {
        "state": "supported", "source": "administrator_override", "stale": False, "override": True,
    }
    assert meta["capabilities"]["json_schema"] == {
        "state": "unsupported", "source": "administrator_override", "stale": False, "override": True,
    }
    assert (m.supports_json_mode, m.supports_json_schema) == (True, False)

    # Reverting JSON mode alone restores its catalog value; the JSON-Schema
    # override is untouched.
    mm.clear_capability_override(m, "json_mode")
    meta, _ = mm.resolve_one("openai", m, sources)
    assert meta["capabilities"]["json_mode"] == {
        "state": "unsupported", "source": "litellm", "stale": False, "override": False,
    }
    assert meta["capabilities"]["json_schema"]["source"] == "administrator_override"
    assert (m.supports_json_mode, m.supports_json_schema) == (False, False)


def test_refresh_preserves_admin_choices_for_both_json_capabilities():
    m = _model()
    mm.apply_capability_override(m, "json_mode", "unknown")
    mm.apply_capability_override(m, "json_schema", "supported")
    sources = [_source("openai", {"openai/gpt-4o": _entry(json_mode=True, json_schema=False)})]
    meta, _ = mm.resolve_one("openai", m, sources)

    assert meta["capabilities"]["json_mode"]["state"] == "unknown"
    assert meta["capabilities"]["json_mode"]["override"] is True
    assert meta["capabilities"]["json_schema"]["state"] == "supported"
    assert meta["capabilities"]["json_schema"]["override"] is True
    assert (m.supports_json_mode, m.supports_json_schema) == (False, True)
