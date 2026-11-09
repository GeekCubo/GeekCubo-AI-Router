"""Strict pricing: reference estimates never satisfy Cheapest or a cost ceiling.

Only confirmed prices (built-in catalog rates or an administrator-confirmed
custom rate) take part in Auto by default. Reference estimates are used only
when the routing policy explicitly opts in, and such decisions are labelled.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import auto_planner
from app.auto_routing import choose_auto_model, is_confirmed_price, is_priced_for_auto
from app.custom_providers import explain_auto_exclusions
from app.routing_policy import allows_reference_estimates, default_policy, normalize_policy
from app.routing_profiles import apply_profile_filter
from packages.litellm_adapter.catalog import CatalogModel


def _cm(mid: str, inp: float, out: float, source: str) -> CatalogModel:
    return CatalogModel(
        id=mid,
        provider=mid.split("/")[0],
        litellm_prefix="openai/",
        supports_tools=True,
        supports_vision=False,
        supports_json_mode=True,
        input_cost_per_token=inp,
        output_cost_per_token=out,
        price_source=source,
    )


CONFIRMED = _cm("acme/confirmed", 2e-6, 8e-6, "custom")
ESTIMATE = _cm("acme/estimate", 1e-7, 2e-7, "reference")
UNKNOWN = _cm("acme/unknown", 0.0, 0.0, "unknown")
BUILTIN = _cm("openai/builtin", 3e-6, 9e-6, "catalog")
ALL = [CONFIRMED, ESTIMATE, UNKNOWN, BUILTIN]
DEPLOYABLE = {m.id for m in ALL}


def test_confirmed_sources():
    assert is_confirmed_price(CONFIRMED)
    assert is_confirmed_price(BUILTIN)
    assert not is_confirmed_price(ESTIMATE)
    assert not is_confirmed_price(UNKNOWN)


def test_price_gate_excludes_estimates_by_default():
    assert is_priced_for_auto(CONFIRMED)
    assert is_priced_for_auto(BUILTIN)
    assert not is_priced_for_auto(ESTIMATE)
    assert not is_priced_for_auto(UNKNOWN)


def test_price_gate_with_explicit_estimate_opt_in():
    assert is_priced_for_auto(ESTIMATE, allow_estimates=True)
    assert not is_priced_for_auto(UNKNOWN, allow_estimates=True)


def test_cheapest_never_picks_a_reference_estimate_by_default():
    ids, _ = choose_auto_model(
        needs=set(), deployable=DEPLOYABLE, candidates=ALL, strategy="cheapest",
    )
    assert ESTIMATE.id not in ids
    assert UNKNOWN.id not in ids
    assert ids[0] == CONFIRMED.id


def test_cheapest_uses_estimate_only_when_opted_in():
    ids, _ = choose_auto_model(
        needs=set(), deployable=DEPLOYABLE, candidates=ALL, strategy="cheapest",
        allow_estimates=True,
    )
    assert ids[0] == ESTIMATE.id
    assert UNKNOWN.id not in ids


def test_profile_ceiling_rejects_estimates_and_unknown():
    ceiling = 1_000_000  # $1 per 1M blended
    kept, reasons = apply_profile_filter(ALL, {"max_cost_per_million_micros": ceiling})
    assert kept == []
    assert any("confirmed provider prices" in r for r in reasons)


def test_profile_ceiling_accepts_confirmed_price_under_limit():
    kept, _ = apply_profile_filter(ALL, {"max_cost_per_million_micros": 10_000_000})
    assert [m.id for m in kept] == [CONFIRMED.id]


def test_profile_ceiling_accepts_estimate_only_when_opted_in():
    kept, _ = apply_profile_filter(
        ALL, {"max_cost_per_million_micros": 1_000_000}, allow_estimates=True,
    )
    assert [m.id for m in kept] == [ESTIMATE.id]


def test_policy_pricing_flag_defaults_off_and_round_trips():
    assert allows_reference_estimates(default_policy()) is False
    assert allows_reference_estimates(None) is False
    pol = normalize_policy({"pricing": {"allow_reference_estimates": True}})
    assert allows_reference_estimates(pol) is True


def test_policy_pricing_must_be_object():
    from app.routing_policy import PolicyError

    with pytest.raises(PolicyError):
        normalize_policy({"pricing": "yes"})


def _plan(catalog, policy):
    return auto_planner.plan_auto(
        body={"messages": [{"role": "user", "content": "hi"}]},
        needs=set(), deployable={m.id for m in catalog}, catalog=catalog,
        strategy="cheapest", preferred_models=None, allowlist=None,
        quality_scores=None, tps_scores=None, ttft_scores=None, policy=policy,
    )


def test_planner_estimate_only_catalog_fails_strictly():
    with pytest.raises(auto_planner.AutoRoutingError):
        _plan([ESTIMATE], default_policy())


def test_planner_labels_estimate_based_decisions():
    policy = normalize_policy({"pricing": {"allow_reference_estimates": True}})
    plan = _plan([ESTIMATE, CONFIRMED], policy)
    assert plan.candidates[0] == ESTIMATE.id
    assert any("estimate-based pricing" in n for n in plan.notes)


def test_planner_confirmed_only_has_no_estimate_note():
    plan = _plan([CONFIRMED, ESTIMATE], default_policy())
    assert plan.candidates == [CONFIRMED.id]
    assert not any("estimate-based" in n for n in plan.notes)


def test_diagnosis_explains_estimate_only():
    category, message = auto_planner.diagnose_empty(
        needs=set(), deployable={ESTIMATE.id}, full_catalog=[ESTIMATE],
        auto_catalog=[ESTIMATE], custom_views=[], allowlist=None,
        body={"messages": []},
    )
    assert category == auto_planner.NO_MODELS
    assert "reference price estimates" in message


def _view_model(**kw):
    base = dict(
        id="m1", model_id="m1", is_enabled=True, metadata_json=None,
        supports_tools=False, supports_vision=False, supports_json_mode=False,
        input_cost_per_token=0.0, output_cost_per_token=0.0,
        reference_input_cost_per_token=1e-6, reference_output_cost_per_token=2e-6,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_exclusion_explains_reference_only_model():
    prov = SimpleNamespace(
        slug="acme", display_name="Acme", is_enabled=True, eligible_for_auto=True,
        models=[_view_model()],
    )
    lines = explain_auto_exclusions([prov], needs=set(), deployable={"acme/m1"})
    assert lines and "reference price estimate" in lines[0]
    assert explain_auto_exclusions(
        [prov], needs=set(), deployable={"acme/m1"}, allow_estimates=True,
    ) == []
