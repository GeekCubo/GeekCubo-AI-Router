"""Strategy acceptance: one fixture catalog, every strategy, observable results.

Each test asserts the model a strategy actually selects AND the explanation
it records, over the same deterministic fixtures:

    cheap      $0.10 / $0.10   ctx 128k   tools ✓  vision ✗  json_mode ✓  schema ?
    mid        $1.00 / $2.00   ctx 32k    tools ✓  vision ✓  json_mode ?  schema ✓
    premium    $5.00 / $15.00  ctx 1M     tools ✓  vision ✓  json_mode ✓  schema ✓
    tie-a/b    $1.00 / $2.00   (same price as mid, unknown capabilities)
    noprice    unknown price   (custom provider, no confirmed rate)
    estimate   reference-only  ($0.01 / $0.01 vendor estimate, not confirmed)

No DB, no network: `plan_auto` is the function the chat engine calls.
"""

from __future__ import annotations

import pytest

from app.auto_planner import AutoRoutingError, plan_auto, reset_state
from app.auto_routing import is_priced_for_auto
from app.routing_policy import ADAPTIVE_MIN_SAMPLES, default_policy
from packages.litellm_adapter.catalog import CatalogModel

M = 1e-6  # $ per token for $1 / 1M


def model(mid, inp, out, *, tools=True, vision=None, json_mode=None, schema=None,
          ctx=None, source="custom"):
    return CatalogModel(
        id=mid, provider="t", litellm_prefix="openai/",
        supports_tools=tools, supports_vision=vision,
        supports_json_mode=json_mode, supports_json_schema=schema,
        input_cost_per_token=inp, output_cost_per_token=out,
        context_length=ctx, price_source=source,
    )


CATALOG = [
    model("cheap", 0.1 * M, 0.1 * M, vision=False, json_mode=True, ctx=128_000),
    model("mid", 1 * M, 2 * M, vision=True, schema=True, ctx=32_000),
    model("premium", 5 * M, 15 * M, vision=True, json_mode=True, schema=True, ctx=1_000_000),
    model("noprice", 0.0, 0.0, source="unknown"),
    model("estimate", 0.01 * M, 0.01 * M, source="reference"),
]
IDS = {m.id for m in CATALOG}
HI = [{"role": "user", "content": "hi"}]


@pytest.fixture(autouse=True)
def _clean():
    reset_state()
    yield
    reset_state()


def run(strategy, *, needs=(), catalog=CATALOG, policy=None, quality=None,
        tps=None, ttft=None, evidence=None, body=None, deployable=None):
    return plan_auto(
        body=body or {"messages": HI},
        needs=set(needs),
        deployable=deployable if deployable is not None else {m.id for m in catalog},
        catalog=catalog,
        strategy=strategy,
        preferred_models=[],
        allowlist=None,
        quality_scores=quality,
        tps_scores=tps,
        ttft_scores=ttft,
        policy=policy or default_policy(),
        evidence=evidence or {},
    )


# ── shared gates (every strategy) ──────────────────────────────────────────

ALL = ("balanced", "cheapest", "quality", "adaptive", "adaptive_gated", "fastest")


@pytest.mark.parametrize("strategy", ALL)
def test_unknown_and_estimate_prices_never_qualify_by_default(strategy):
    policy = default_policy()
    if strategy == "adaptive_gated":
        policy["pools"]["mundane"] = sorted(IDS)
    plan = run(strategy, policy=policy)
    assert "noprice" not in plan.candidates
    assert "estimate" not in plan.candidates


@pytest.mark.parametrize("strategy", ALL)
def test_unknown_capability_never_satisfies_a_requirement(strategy):
    """json_schema: cheap is Unknown, mid/premium Supported."""
    policy = default_policy()
    if strategy == "adaptive_gated":
        policy["pools"]["mundane"] = sorted(IDS)
    plan = run(strategy, needs={"json_schema"}, policy=policy)
    assert "cheap" not in plan.candidates
    assert set(plan.candidates) <= {"mid", "premium"}


@pytest.mark.parametrize("strategy", ALL)
def test_context_limit_excludes_models_too_small(strategy):
    policy = default_policy()
    if strategy == "adaptive_gated":
        policy["pools"]["mundane"] = sorted(IDS)
        policy["pools"]["hard"] = sorted(IDS)
    long_prompt = {"messages": [{"role": "user", "content": "x" * 4 * 60_000}]}  # ~60k tokens
    plan = run(strategy, body=long_prompt, policy=policy)
    assert "mid" not in plan.candidates  # 32k window
    assert set(plan.candidates) <= {"cheap", "premium"}


@pytest.mark.parametrize("strategy", ALL)
def test_nothing_eligible_raises_a_categorised_error(strategy):
    policy = default_policy()
    if strategy == "adaptive_gated":
        policy["pools"]["mundane"] = sorted(IDS)
    with pytest.raises(AutoRoutingError):
        run(strategy, needs={"vision", "json_mode", "tools"},
            catalog=[m for m in CATALOG if m.id != "premium"], policy=policy)


@pytest.mark.parametrize("strategy", ALL)
def test_disabled_or_undeployable_models_are_never_selected(strategy):
    policy = default_policy()
    if strategy == "adaptive_gated":
        policy["pools"]["mundane"] = sorted(IDS)
    plan = run(strategy, policy=policy, deployable={"mid", "premium"})
    assert "cheap" not in plan.candidates


# ── Cheapest ───────────────────────────────────────────────────────────────

def test_cheapest_selects_lowest_blended_cost_and_says_so():
    plan = run("cheapest")
    assert plan.candidates == ["cheap", "mid", "premium"]
    assert plan.effective_strategy == "cheapest"
    assert plan.reason == "Cheapest: best of 3 eligible"


def test_cheapest_blends_input_and_output_30_70():
    """Output-heavy weighting: low input but high output loses to balanced rates."""
    cat = [
        model("in-cheap", 0.1 * M, 10 * M),   # blended 7.03
        model("even", 3 * M, 3 * M),          # blended 3.0
    ]
    assert run("cheapest", catalog=cat).candidates[0] == "even"


def test_cheapest_uses_the_confirmed_override_not_the_reference():
    """The catalog entry carries the EFFECTIVE routing price. For a custom
    model with an administrator rate that rate is used (see
    model_metadata.effective_routing_price); the reference estimate is not."""
    from types import SimpleNamespace

    from app.model_metadata import dump_metadata, effective_routing_price

    row = SimpleNamespace(
        input_cost_per_token=0.2 * M, output_cost_per_token=0.2 * M,
        reference_input_cost_per_token=0.3 * M, reference_output_cost_per_token=1.2 * M,
        metadata_json=dump_metadata({"manual": {"pricing": True}}),
    )
    inp, out, source = effective_routing_price(row)
    assert (round(inp / M, 6), round(out / M, 6), source) == (0.2, 0.2, "custom")

    no_override = SimpleNamespace(
        input_cost_per_token=0.0, output_cost_per_token=0.0,
        reference_input_cost_per_token=0.3 * M, reference_output_cost_per_token=1.2 * M,
        metadata_json=None,
    )
    assert effective_routing_price(no_override)[2] == "reference"
    assert not is_priced_for_auto(model("x", 0.3 * M, 1.2 * M, source="reference"))


def test_cheapest_ties_break_by_model_id():
    cat = [model("tie-b", 1 * M, 2 * M), model("tie-a", 1 * M, 2 * M)]
    assert run("cheapest", catalog=cat).candidates == ["tie-a", "tie-b"]


def test_cheapest_with_every_price_unknown_fails_instead_of_choosing():
    cat = [model("a", 0.0, 0.0, source="unknown"), model("b", 0.0, 0.0, source="unknown")]
    with pytest.raises(AutoRoutingError):
        run("cheapest", catalog=cat)


def test_reference_estimates_qualify_only_when_explicitly_allowed():
    policy = default_policy()
    policy["pricing"]["allow_reference_estimates"] = True
    plan = run("cheapest", policy=policy)
    assert plan.candidates[0] == "estimate"
    assert any("estimate-based pricing" in n for n in plan.notes)


# ── Balanced ───────────────────────────────────────────────────────────────

def test_balanced_weighs_quality_and_cost():
    """50/50 of min-max-normalised quality and inverted blended cost:
    mid = 0.5*0.50 + 0.5*0.87 = 0.68; cheap = 0.5*0 + 0.5*1 = 0.50;
    premium = 0.5*1 + 0.5*0 = 0.50 (tie broken by lower cost → cheap)."""
    quality = {"cheap": 30.0, "mid": 60.0, "premium": 90.0}
    plan = run("balanced", quality=quality)
    assert plan.effective_strategy == "balanced"
    assert plan.candidates == ["mid", "cheap", "premium"]
    assert not plan.notes


def test_balanced_quality_floor_excludes_weak_models_and_unscored_ones_fall_out():
    policy = default_policy()
    policy["balanced_min_quality"] = 50
    quality = {"cheap": 30.0, "mid": 60.0, "premium": 90.0}
    plan = run("balanced", policy=policy, quality=quality)
    assert "cheap" not in plan.candidates
    assert plan.candidates[0] == "mid"


def test_balanced_never_treats_unknown_quality_as_a_pass():
    """Unscored models do not take part in Balanced ranking when scores
    exist for others (strict coverage)."""
    quality = {"mid": 60.0, "premium": 90.0}
    plan = run("balanced", quality=quality)
    assert "cheap" not in plan.candidates


def test_balanced_without_any_quality_data_ranks_by_price_and_reports_it():
    plan = run("balanced", quality={})
    assert plan.candidates[0] == "cheap"
    assert any("no quality score" in n and "price only" in n for n in plan.notes)


def test_balanced_floor_without_scores_is_reported_not_applied():
    policy = default_policy()
    policy["balanced_min_quality"] = 80
    plan = run("balanced", policy=policy, quality={})
    assert plan.candidates[0] == "cheap"
    assert any("floor not applied" in n for n in plan.notes)


# ── Quality First ──────────────────────────────────────────────────────────

def test_quality_first_ranks_by_score_with_overrides_winning():
    """Scores arrive pre-merged (overrides > AA, see quality_scores.py)."""
    quality = {"cheap": 95.0, "mid": 60.0, "premium": 40.0}  # override lifted cheap
    plan = run("quality", quality=quality)
    assert plan.candidates == ["cheap", "mid", "premium"]
    assert plan.reason == "Quality First: best of 3 eligible"


def test_quality_first_keeps_unscored_models_last_and_names_them():
    plan = run("quality", quality={"mid": 70.0})
    assert plan.candidates[0] == "mid"
    assert any("unscored candidates rank after scored ones" in n for n in plan.notes)


def test_quality_first_without_scores_uses_price_proxy_and_says_so():
    plan = run("quality", quality={})
    assert plan.candidates[0] == "premium"  # most expensive first
    assert any("ranked by price as a proxy" in n for n in plan.notes)


# ── Adaptive ───────────────────────────────────────────────────────────────

def test_adaptive_below_sample_threshold_runs_balanced_and_reports_counts():
    evidence = {"cheap": {"n": 3, "success": 1.0, "latency_ms": 100.0}}
    plan = run("adaptive", evidence=evidence, quality={"cheap": 50.0, "mid": 50.0, "premium": 50.0})
    assert plan.effective_strategy == "balanced"
    assert any(f"need {ADAPTIVE_MIN_SAMPLES}" in n and "have 3" in n for n in plan.notes)


def test_adaptive_reranks_on_observed_success_then_latency():
    n = ADAPTIVE_MIN_SAMPLES
    evidence = {
        "cheap": {"n": n, "success": 0.5, "latency_ms": 100.0},
        "mid": {"n": n, "success": 0.99, "latency_ms": 900.0},
        "premium": {"n": n, "success": 0.99, "latency_ms": 300.0},
    }
    plan = run("adaptive", evidence=evidence, quality={"cheap": 50.0, "mid": 50.0, "premium": 50.0})
    assert plan.effective_strategy == "adaptive"
    assert plan.candidates == ["premium", "mid", "cheap"]
    assert "observed success/latency" in plan.reason


def test_adaptive_unproven_models_keep_base_order_after_proven_ones():
    n = ADAPTIVE_MIN_SAMPLES
    evidence = {
        "mid": {"n": n, "success": 0.9, "latency_ms": 500.0},
        "premium": {"n": n, "success": 0.95, "latency_ms": 500.0},
    }
    plan = run("adaptive", evidence=evidence, quality={"cheap": 50.0, "mid": 50.0, "premium": 50.0})
    assert plan.candidates[:2] == ["premium", "mid"]
    assert plan.candidates[-1] == "cheap"


# ── Adaptive-Gated ─────────────────────────────────────────────────────────

def gated_policy():
    policy = default_policy()
    policy["pools"] = {"mundane": ["cheap"], "hard": ["premium"], "fallback": ["mid"]}
    return policy


def test_gated_plain_request_uses_the_mundane_pool():
    plan = run("adaptive_gated", policy=gated_policy())
    assert (plan.tier, plan.candidates[0]) == ("mundane", "cheap")
    assert "no hard signals" in plan.reason


def test_gated_tool_request_uses_the_hard_pool():
    plan = run("adaptive_gated", needs={"tools"}, policy=gated_policy())
    assert (plan.tier, plan.candidates[0]) == ("hard", "premium")
    assert "tools" in plan.reason


def test_gated_long_context_request_is_hard():
    body = {"messages": [{"role": "user", "content": "x" * 7000}]}
    plan = run("adaptive_gated", body=body, policy=gated_policy())
    assert plan.tier == "hard"
    assert "prompt chars" in plan.reason


def test_gated_incapable_tier_uses_fallback_pool_keeping_capabilities():
    """Vision request: hard pool (premium) disabled → fallback pool (mid,
    vision ✓) serves it; cheap (vision ✗) is never used."""
    plan = run("adaptive_gated", needs={"vision"}, policy=gated_policy(),
               deployable={"cheap", "mid"})
    assert plan.tier == "fallback"
    assert plan.candidates == ["mid"]


def test_gated_empty_pools_fail_safely_instead_of_using_the_whole_catalog():
    policy = default_policy()  # every pool empty
    with pytest.raises(AutoRoutingError) as err:
        run("adaptive_gated", policy=policy)
    assert err.value.category == "pool_mismatch"


def test_gated_hard_pool_falls_back_to_mundane_only_if_capable_and_allowed():
    policy = gated_policy()
    policy["pools"]["fallback"] = []
    plan = run("adaptive_gated", needs={"tools"}, policy=policy, deployable={"cheap"})
    assert (plan.tier, plan.candidates) == ("fallback", ["cheap"])
    policy["gated"]["allow_mundane_fallback"] = False
    with pytest.raises(AutoRoutingError):
        run("adaptive_gated", needs={"tools"}, policy=policy, deployable={"cheap"})


# ── Fastest (legacy) ───────────────────────────────────────────────────────

def test_fastest_uses_throughput_and_first_token_benchmarks():
    tps = {"cheap": 50.0, "mid": 200.0, "premium": 100.0}
    ttft = {"cheap": 2.0, "mid": 0.3, "premium": 0.5}
    plan = run("fastest", tps=tps, ttft=ttft)
    assert plan.candidates[0] == "mid"
    assert plan.reason == "Fastest: best of 3 eligible"
    assert not plan.notes


def test_fastest_never_treats_missing_latency_as_fast():
    """Only `mid` is benchmarked: unmeasured models are dropped, never
    ranked as zero latency."""
    plan = run("fastest", tps={"mid": 10.0}, ttft={"mid": 5.0})
    assert plan.candidates == ["mid"]


def test_fastest_without_benchmarks_ranks_by_price_and_reports_it():
    plan = run("fastest", tps={}, ttft={})
    assert plan.candidates[0] == "cheap"
    assert any("latency is unknown" in n for n in plan.notes)


# ── fallback chain ─────────────────────────────────────────────────────────

def test_fallback_chain_respects_max_attempts_and_capabilities():
    policy = default_policy()
    policy["fallback"]["max_attempts"] = 2
    plan = run("cheapest", needs={"vision"}, policy=policy)
    assert plan.candidates == ["mid", "premium"]


def test_fallback_disabled_means_a_single_candidate():
    policy = default_policy()
    policy["fallback"]["enabled"] = False
    assert run("cheapest", policy=policy).candidates == ["cheap"]
