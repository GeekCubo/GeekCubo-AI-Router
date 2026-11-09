"""Routing policy: strategies, pools, fallback, escalation, stickiness.

Pure-function tests over `plan_auto` with an explicit catalog, so each rule is
asserted without a DB, a network call or a fake router. The end-to-end
wiring (chat handler, headers, log rows) is covered in
tests/integration/test_routing_integration.py.
"""

from __future__ import annotations

import pytest

from app.auto_planner import AutoRoutingError, plan_auto, reset_state
from app.routing_policy import (
    ADAPTIVE_MIN_SAMPLES,
    PolicyError,
    classify_difficulty,
    default_policy,
    effective_strategy,
    normalize_policy,
    pool_membership,
)
from packages.litellm_adapter.catalog import CatalogModel


def model(mid, *, provider="p", tools=True, vision=False, json_mode=False,
          json_schema=False, inc=1e-6, out=2e-6, ctx=None):
    return CatalogModel(
        id=mid, provider=provider, litellm_prefix="openai/",
        supports_tools=tools, supports_vision=vision, supports_json_mode=json_mode,
        supports_json_schema=json_schema,
        input_cost_per_token=inc, output_cost_per_token=out, context_length=ctx,
    )


@pytest.fixture(autouse=True)
def _clean_state():
    reset_state()
    yield
    reset_state()


def plan(catalog, *, needs=("tools",), strategy="balanced", policy=None,
         deployable=None, allowlist=None, evidence=None, body=None, hints=None,
         quality=None):
    return plan_auto(
        body=body or {"messages": [{"role": "user", "content": "hi"}]},
        needs=set(needs),
        deployable=deployable if deployable is not None else {m.id for m in catalog},
        catalog=catalog,
        strategy=strategy,
        preferred_models=[],
        allowlist=allowlist,
        quality_scores=quality,
        tps_scores=None,
        ttft_scores=None,
        policy=policy or default_policy(),
        evidence=evidence or {},
        hints=hints or {},
    )


# ── policy validation ─────────────────────────────────────────────────────


def test_defaults_reproduce_pre_policy_limits():
    p = default_policy()
    assert p["fallback"]["max_attempts"] == 5  # == legacy top_n
    assert p["escalation"]["mode"] == "off"
    assert p["stickiness"]["enabled"] is False
    assert p["pools"] == {"mundane": [], "hard": [], "fallback": []}


def test_normalize_is_idempotent_and_drops_unknown_keys():
    once = normalize_policy({"strategy_note": "ignored", "balanced_min_quality": 30})
    twice = normalize_policy(once)
    assert once == twice
    assert "strategy_note" not in once


@pytest.mark.parametrize("bad", [
    {"balanced_min_quality": 101},
    {"balanced_min_quality": -1},
    {"pools": {"mundane": "not-a-list"}},
    {"escalation": {"mode": "sometimes"}},
    {"escalation": {"max_per_conversation": 99}},
    {"fallback": {"max_attempts": 0}},
    {"pool_overrides": [{"model": "x", "pool": "nonsense"}]},
])
def test_invalid_policy_rejected(bad):
    with pytest.raises(PolicyError):
        normalize_policy(bad)


def test_dsl_is_not_a_strategy():
    """A rule language is out of scope; accepting the key would imply support."""
    from app.routing_policy import STRATEGIES
    assert "dsl" not in STRATEGIES


# ── strategies ───────────────────────────────────────────────────────────


def test_cheapest_picks_lowest_blended_cost():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("pricey", inc=1e-5, out=1e-5)]
    assert plan(cat, strategy="cheapest").candidates[0] == "cheap"


def test_quality_picks_highest_score():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("pricey", inc=1e-5, out=1e-5)]
    p = plan(cat, strategy="quality", quality={"cheap": 10, "pricey": 90})
    assert p.candidates[0] == "pricey"


def test_balanced_honours_the_quality_floor():
    """A dirt-cheap, low-quality model is excluded by the floor."""
    cat = [
        model("bad", inc=1e-8, out=1e-8),
        model("mid", inc=1e-6, out=1e-6),
        model("good", inc=1e-5, out=1e-5),
    ]
    policy = default_policy()
    policy["balanced_min_quality"] = 50
    quality = {"bad": 5, "mid": 50, "good": 95}
    picked = plan(cat, strategy="balanced", policy=policy, quality=quality).candidates
    assert "bad" not in picked
    assert set(picked) == {"mid", "good"}


def test_quality_floor_without_scores_is_reported_not_faked():
    cat = [model("a", inc=1e-8, out=1e-8)]
    policy = default_policy()
    policy["balanced_min_quality"] = 50
    p = plan(cat, strategy="balanced", policy=policy, quality=None)
    assert p.candidates == ["a"]
    assert any("quality floor" in n for n in p.notes)


def test_adaptive_without_evidence_degrades_and_says_so():
    cat = [model("a"), model("b", inc=5e-6, out=5e-6)]
    p = plan(cat, strategy="adaptive")
    assert p.effective_strategy == "balanced"
    assert any("not enough evidence" in n for n in p.notes)


def test_adaptive_reranks_once_evidence_exists():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("steady", inc=1e-5, out=1e-5)]
    evidence = {
        "cheap": {"n": 50, "success": 0.4, "latency_ms": 3000},
        "steady": {"n": 50, "success": 0.99, "latency_ms": 500},
    }
    p = plan(cat, strategy="adaptive", evidence=evidence)
    assert p.effective_strategy == "adaptive"
    assert p.candidates[0] == "steady"


def test_adaptive_ignores_thin_evidence_per_model():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("steady", inc=1e-5, out=1e-5)]
    evidence = {
        "cheap": {"n": 3, "success": 0.0, "latency_ms": 9000},
        "steady": {"n": ADAPTIVE_MIN_SAMPLES, "success": 1.0, "latency_ms": 100},
    }
    p = plan(cat, strategy="adaptive", evidence=evidence)
    # Only one model has enough evidence -> nothing to compare it against, so
    # the deterministic strategy is used and reported as such.
    assert p.effective_strategy == "balanced"
    assert set(p.candidates) == {"cheap", "steady"}
    assert any("not enough evidence" in n for n in p.notes)


def test_effective_strategy_names_the_fallback_explicitly():
    assert effective_strategy("balanced", 0) == ("balanced", None)
    eff, note = effective_strategy("adaptive", 0)
    assert eff == "balanced" and "balanced" in note


# ── capability enforcement ───────────────────────────────────────────────


def test_capability_filter_still_applies():
    cat = [model("no-tools", tools=False), model("with-tools")]
    assert plan(cat, needs=("tools",)).candidates == ["with-tools"]


def test_empty_result_raises_for_the_caller_to_diagnose():
    cat = [model("no-tools", tools=False)]
    with pytest.raises(AutoRoutingError):
        plan(cat, needs=("tools",))


def test_pools_never_bypass_capability():
    """A hard pool made only of non-tool models cannot serve a tools request."""
    cat = [model("weak", tools=False)]
    policy = default_policy()
    policy["pools"]["hard"] = ["weak"]
    with pytest.raises(AutoRoutingError) as exc:
        plan(cat, needs=("tools",), strategy="adaptive_gated", policy=policy)
    assert exc.value.category == "pool_mismatch"


# ── gating (Mundane / Hard) ──────────────────────────────────────────────


def test_tools_request_lands_in_hard_pool_and_explains_why():
    cat = [
        model("mundane-m", inc=1e-7, out=1e-7),
        model("hard-m", inc=1e-5, out=1e-5),
    ]
    policy = default_policy()
    policy["pools"]["mundane"] = ["mundane-m"]
    policy["pools"]["hard"] = ["hard-m"]
    p = plan(cat, needs=("tools",), strategy="adaptive_gated", policy=policy)
    assert p.tier == "hard"
    assert p.candidates == ["hard-m"]
    assert "tools" in p.reason


def test_simple_request_lands_in_mundane_pool():
    cat = [model("mundane-m", inc=1e-7, out=1e-7), model("hard-m", inc=1e-5, out=1e-5)]
    policy = default_policy()
    policy["pools"]["mundane"] = ["mundane-m"]
    policy["pools"]["hard"] = ["hard-m"]
    p = plan(cat, needs=(), strategy="adaptive_gated", policy=policy)
    assert p.tier == "mundane"
    assert p.candidates == ["mundane-m"]


def test_hard_pool_falls_back_to_mundane_when_it_cannot_serve():
    cat = [model("mundane-m"), model("hard-no-tools", tools=False)]
    policy = default_policy()
    policy["pools"]["mundane"] = ["mundane-m"]
    policy["pools"]["hard"] = ["hard-no-tools"]
    p = plan(cat, needs=("tools",), strategy="adaptive_gated", policy=policy)
    assert p.tier == "fallback"
    assert p.candidates == ["mundane-m"]


def test_fallback_pool_used_before_mundane():
    cat = [model("mundane-m"), model("fb-m")]
    policy = default_policy()
    policy["pools"]["mundane"] = ["mundane-m"]
    policy["pools"]["hard"] = []
    policy["pools"]["fallback"] = ["fb-m"]
    p = plan(cat, needs=("tools",), strategy="adaptive_gated", policy=policy)
    assert p.tier == "fallback"
    assert p.candidates[0] == "fb-m"


def test_empty_hard_pool_is_an_error_not_a_silent_widening():
    cat = [model("mundane-m")]
    policy = default_policy()
    policy["pools"]["mundane"] = ["mundane-m"]
    policy["gated"]["allow_mundane_fallback"] = False
    with pytest.raises(AutoRoutingError) as exc:
        plan(cat, needs=("tools",), strategy="adaptive_gated", policy=policy)
    assert exc.value.category == "pool_mismatch"


def test_classify_difficulty_signals_are_observable_only():
    policy = default_policy()
    d = classify_difficulty(
        {"messages": [{"role": "user", "content": "x" * 8000}]}, set(), policy
    )
    assert d.tier == "hard"
    assert any("prompt chars" in s for s in d.signals)


def test_gating_can_be_disabled():
    policy = default_policy()
    policy["gated"]["enabled"] = False
    policy["pools"]["mundane"] = ["m"]
    policy["pools"]["hard"] = ["h"]
    p = plan([model("m"), model("h")], needs=("tools",), strategy="adaptive_gated",
             policy=policy)
    assert p.tier == "mundane"


# ── fallback ─────────────────────────────────────────────────────────────


def test_explicit_fallback_models_are_appended_after_capability_check():
    cat = [model("primary", inc=1e-7, out=1e-7), model("backup", inc=1e-5, out=1e-5)]
    policy = default_policy()
    policy["fallback"]["models"] = ["backup"]
    p = plan(cat, strategy="cheapest", policy=policy)
    assert p.candidates == ["primary", "backup"]


def test_fallback_respects_capabilities():
    cat = [model("primary", inc=1e-7, out=1e-7), model("blind", tools=False, inc=1e-5)]
    policy = default_policy()
    policy["fallback"]["models"] = ["blind"]
    p = plan(cat, needs=("tools",), strategy="cheapest", policy=policy)
    assert "blind" not in p.candidates


@pytest.mark.parametrize("need,flag", [
    ("json_mode", "json_mode"),
    ("json_schema", "json_schema"),
])
def test_fallback_respects_each_json_capability(need, flag):
    """The primary qualifies for the requested JSON capability; a fallback
    that only carries the *other* JSON flag must be excluded, and a fallback
    carrying the right one is kept."""
    kwargs = {"json_mode": False, "json_schema": False}
    primary = dict(kwargs, **{flag: True})
    other = dict(kwargs, **{"json_schema" if flag == "json_mode" else "json_mode": True})
    right = dict(kwargs, **{flag: True})
    cat = [model("primary", inc=1e-7, out=1e-7, **primary),
           model("wrong", inc=1e-5, out=1e-5, **other),
           model("right", inc=1e-5, out=1e-5, **right)]
    policy = default_policy()
    policy["fallback"]["models"] = ["wrong", "right"]
    p = plan(cat, needs=(need,), strategy="cheapest", policy=policy)
    assert p.candidates == ["primary", "right"]


def test_max_attempts_caps_the_chain():
    cat = [model(f"m{i}", inc=1e-7 * (i + 1), out=1e-7) for i in range(6)]
    policy = default_policy()
    policy["fallback"]["max_attempts"] = 2
    assert len(plan(cat, strategy="cheapest", policy=policy).candidates) == 2


def test_fallback_can_be_disabled():
    cat = [model("a", inc=1e-7, out=1e-7), model("b", inc=1e-6, out=1e-6)]
    policy = default_policy()
    policy["fallback"]["enabled"] = False
    assert plan(cat, strategy="cheapest", policy=policy).candidates == ["a"]


# ── escalation ───────────────────────────────────────────────────────────


def _escalation_policy(**esc):
    policy = default_policy()
    policy["pools"]["mundane"] = ["cheap"]
    policy["pools"]["hard"] = ["strong"]
    policy["escalation"].update({"mode": "auto", "failure_threshold": 2,
                                 "max_per_conversation": 2, "from_pool": "mundane",
                                 "to_pool": "hard"})
    policy["escalation"].update(esc)
    return policy


def test_escalation_requires_observed_failures():
    from app.auto_planner import record_outcome

    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4, out=1e-4)]
    policy = _escalation_policy()
    body = {"messages": [{"role": "user", "content": "help me refactor"}]}

    p0 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert not p0.escalated

    key = p0.conversation_key
    record_outcome(key, status_code=503, served_model="cheap")
    p1 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert not p1.escalated, "one strike must not escalate"

    record_outcome(key, status_code=502, served_model="cheap")
    p2 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert p2.escalated
    assert p2.candidates[0] == "strong"


def test_client_errors_do_not_strike():
    from app.auto_planner import record_outcome

    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4)]
    policy = _escalation_policy(failure_threshold=1)
    body = {"messages": [{"role": "user", "content": "q"}]}
    p0 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    record_outcome(p0.conversation_key, status_code=400, served_model="cheap")
    assert not plan(cat, needs=(), strategy="adaptive_gated", policy=policy,
                    body=body).escalated


def test_escalation_respects_max_per_conversation():
    from app.auto_planner import record_outcome

    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4)]
    policy = _escalation_policy(failure_threshold=1, max_per_conversation=1)
    body = {"messages": [{"role": "user", "content": "once"}]}
    p0 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    key = p0.conversation_key
    record_outcome(key, status_code=503, served_model="cheap")
    p1 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert p1.escalated
    # Sticky to the escalated tier; the counter must not grow.
    p2 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert p2.escalated
    state = __import__("app.auto_planner", fromlist=["_CONVERSATIONS"])._CONVERSATIONS[key]
    assert state.escalations == 1


def test_escalation_is_off_by_default():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4)]
    p = plan(cat, needs=(), strategy="cheapest")
    assert not p.escalated


def test_manual_escalation_requires_the_client_signal():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4)]
    policy = _escalation_policy(mode="manual")
    body = {"messages": [{"role": "user", "content": "manual"}]}
    assert not plan(cat, needs=(), strategy="adaptive_gated", policy=policy,
                    body=body).escalated
    assert plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body,
                hints={"escalate": "1"}).escalated


def test_shadow_escalation_reports_but_does_not_switch():
    from app.auto_planner import record_outcome

    cat = [model("cheap", inc=1e-7, out=1e-7), model("strong", inc=1e-4)]
    policy = _escalation_policy(failure_threshold=1, shadow=True)
    body = {"messages": [{"role": "user", "content": "shadow"}]}
    p0 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    record_outcome(p0.conversation_key, status_code=503, served_model="cheap")
    p1 = plan(cat, needs=(), strategy="adaptive_gated", policy=policy, body=body)
    assert p1.shadow_escalation is True
    assert p1.escalated is False
    assert p1.candidates[0] == "cheap"


def test_escalation_with_empty_target_pool_is_actionable():
    cat = [model("cheap", inc=1e-7, out=1e-7)]
    policy = _escalation_policy(mode="manual")
    policy["pools"]["hard"] = []
    with pytest.raises(AutoRoutingError) as exc:
        plan(cat, needs=(), strategy="adaptive_gated", policy=policy,
             hints={"escalate": "1"})
    assert exc.value.category == "pool_mismatch"
    assert "hard" in exc.value.message


# ── stickiness ───────────────────────────────────────────────────────────


def test_stickiness_keeps_the_conversation_on_its_model():
    from app.auto_planner import record_outcome

    cat = [model("cheap", inc=1e-7, out=1e-7), model("mid", inc=1e-5, out=1e-5)]
    policy = default_policy()
    policy["stickiness"] = {"enabled": True, "ttl_minutes": 30}
    body = {"messages": [{"role": "user", "content": "sticky"}]}

    p0 = plan(cat, strategy="cheapest", policy=policy, body=body)
    assert p0.candidates[0] == "cheap"
    record_outcome(p0.conversation_key, status_code=200, served_model="mid")

    p1 = plan(cat, strategy="cheapest", policy=policy, body=body)
    assert p1.candidates[0] == "mid"
    assert p1.sticky is True


def test_stickiness_off_by_default():
    cat = [model("cheap", inc=1e-7, out=1e-7), model("mid", inc=1e-5, out=1e-5)]
    assert plan(cat, strategy="cheapest").sticky is False


# ── context ──────────────────────────────────────────────────────────────


def test_context_limit_excludes_a_model_that_cannot_fit():
    cat = [model("small", inc=1e-7, out=1e-7, ctx=100),
           model("large", inc=1e-5, out=1e-5, ctx=1_000_000)]
    body = {"messages": [{"role": "user", "content": "x" * 8000}]}
    p = plan(cat, strategy="cheapest", body=body)
    assert p.candidates[0] == "large"


def test_unknown_context_never_excludes():
    cat = [model("unknown-ctx", ctx=None, inc=1e-7, out=1e-7)]
    body = {"messages": [{"role": "user", "content": "x" * 100000}]}
    assert plan(cat, strategy="cheapest", body=body).candidates == ["unknown-ctx"]


# ── allowlist ────────────────────────────────────────────────────────────


def test_allowlist_filters_candidates():
    cat = [model("a", inc=1e-7, out=1e-7), model("b", inc=1e-5, out=1e-5)]
    assert plan(cat, strategy="cheapest", allowlist=["b"]).candidates == ["b"]


def test_empty_allowlist_matches_nothing():
    cat = [model("a")]
    with pytest.raises(AutoRoutingError):
        plan(cat, strategy="cheapest", allowlist=[])


def test_pool_membership_filters_deleted_models():
    policy = default_policy()
    policy["pools"]["mundane"] = ["gone", "here"]
    assert pool_membership(policy, known_ids={"here"})["mundane"] == {"here"}
