"""Reasoning effort: normalization, capability, translation and Auto gating.

Capability is derived offline from LiteLLM's own metadata and parameter
mapping, so these tests make no network calls.
"""

from __future__ import annotations

import pytest

from app import reasoning
from app.reasoning import ReasoningError

# ── normalization ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw, expected", [
    (None, None), ("", None), ("  ", None), ("HIGH", "high"), (" low ", "low"),
    ("xhigh", "xhigh"), ("max", "max"), ("none", "none"),
])
def test_normalize_effort(raw, expected):
    assert reasoning.normalize_effort(raw) == expected


@pytest.mark.parametrize("raw", ["extreme", 3, True, ["high"]])
def test_normalize_effort_rejects_invalid(raw):
    with pytest.raises(ReasoningError) as exc:
        reasoning.normalize_effort(raw)
    assert exc.value.status_code == 400
    assert exc.value.error_type == "invalid_reasoning_effort"


def test_downgrade_never_upgrades_and_never_reaches_none_or_minimal():
    assert reasoning.downgrade_candidates("high") == ["medium", "low"]
    assert reasoning.downgrade_candidates("max", minimum="medium") == ["xhigh", "high", "medium"]
    # Even an explicit floor of `none` stops at `low`.
    assert reasoning.downgrade_candidates("medium", minimum="none") == ["low"]
    assert reasoning.downgrade_candidates("low") == []


@pytest.mark.parametrize("budget, level", [
    (0, "none"), (512, "low"), (1024, "low"), (2048, "medium"), (4096, "high"),
    (8192, "xhigh"), (32000, "max"), (-1, None), ("x", None),
])
def test_effort_from_budget(budget, level):
    assert reasoning.effort_from_budget(budget) == level


# ── capability ─────────────────────────────────────────────────────────────


def test_non_reasoning_openai_model_is_confirmed_unsupported():
    cap = reasoning.capability("gpt-4o", provider="openai")
    assert cap.levels == ()
    assert cap.state == "unsupported"


def test_o_series_offers_documented_levels_only():
    assert reasoning.supported_levels("o3", provider="openai") == ("low", "medium", "high")


def test_flagged_levels_need_explicit_metadata():
    gpt5 = reasoning.supported_levels("gpt-5", provider="openai")
    assert gpt5 is not None and "minimal" in gpt5 and "none" not in gpt5
    gpt51 = reasoning.supported_levels("gpt-5.1", provider="openai")
    assert gpt51 is not None and "none" in gpt51 and "minimal" not in gpt51


def test_unknown_model_is_unknown_not_unsupported():
    cap = reasoning.capability("some-model-released-tomorrow", provider="openai")
    assert cap.levels is None
    assert cap.state == "unknown"
    assert reasoning.supports_effort("some-model-released-tomorrow", "high", provider="openai") is None


def test_boolean_provider_collapses_to_off_and_on():
    cap = reasoning.capability("deepseek-chat", provider="deepseek")
    assert cap.levels == ("none", "high")
    assert cap.adjustable is False


def test_builtin_slash_id_is_not_stripped():
    # Groq's model id contains a slash; it must not be read as a namespace.
    assert reasoning.supported_levels("openai/gpt-oss-120b", provider="groq") == (
        "low", "medium", "high",
    )


def test_custom_provider_never_borrows_capability_by_model_name():
    # A gateway serving "o3" may ignore reasoning_effort entirely (observed
    # live: gpt-6.1-sol via a gateway accepted even an invalid value). Only
    # the deployment's own evidence counts, so a bare name match is Unknown.
    assert reasoning.supported_levels("myslug/o3", provider="myslug") is None
    assert reasoning.supported_levels("myslug/unknown-llm", provider="myslug") is None


def test_endpoint_evidence_drives_custom_model_translation():
    # Override/verification confirms levels → strict checking applies.
    with pytest.raises(reasoning.ReasoningError):
        reasoning.provider_params(model_id="myslug/m", provider="myslug", effort="xhigh",
                                  endpoint_levels=("low", "high"))
    assert reasoning.provider_params(
        model_id="myslug/m", provider="myslug", effort="high", endpoint_levels=("low", "high")
    )["reasoning_effort"] == "high"
    # Verified "field ignored" → refused instead of silently dropped.
    with pytest.raises(reasoning.ReasoningError):
        reasoning.provider_params(model_id="myslug/m", provider="myslug", effort="high",
                                  endpoint_levels=())
    # No evidence → Unknown: forwarded with the effort preserved.
    assert reasoning.provider_params(
        model_id="myslug/m", provider="myslug", effort="high"
    )["reasoning_effort"] == "high"


# ── translation ────────────────────────────────────────────────────────────


def test_apply_without_effort_is_a_no_op():
    kwargs = {"model": "o3", "messages": []}
    assert reasoning.apply(kwargs, model_id="o3", provider="openai", effort=None) is kwargs


def test_openai_translation_is_reasoning_effort():
    assert reasoning.provider_params(model_id="o3", provider="openai", effort="high") == {
        "reasoning_effort": "high",
    }


def test_unsupported_level_is_a_400_not_a_drop():
    with pytest.raises(ReasoningError) as exc:
        reasoning.provider_params(model_id="o3", provider="openai", effort="max")
    assert exc.value.status_code == 400
    assert exc.value.error_type == "unsupported_reasoning_effort"
    with pytest.raises(ReasoningError):
        reasoning.provider_params(model_id="gpt-4o", provider="openai", effort="low")


def test_unknown_openai_compatible_model_passes_through_explicitly():
    params = reasoning.provider_params(
        model_id="some-model-released-tomorrow", provider="openai", effort="high",
    )
    assert params["reasoning_effort"] == "high"
    assert params["allowed_openai_params"] == ["reasoning_effort"]


def test_anthropic_legacy_budget_and_max_tokens_guard():
    params = reasoning.provider_params(
        model_id="claude-sonnet-4-5", provider="anthropic", effort="high",
    )
    assert params == {"thinking": {"type": "enabled", "budget_tokens": 4096}}
    assert reasoning.provider_params(
        model_id="claude-sonnet-4-5", provider="anthropic", effort="none",
    ) == {"thinking": {"type": "disabled"}}
    with pytest.raises(ReasoningError):
        reasoning.provider_params(
            model_id="claude-sonnet-4-5", provider="anthropic", effort="high", max_tokens=4096,
        )


def test_anthropic_adaptive_model_uses_output_effort():
    params = reasoning.provider_params(
        model_id="claude-opus-4-6", provider="anthropic", effort="medium",
    )
    assert params == {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}


def test_gemini_sends_reasoning_effort():
    assert reasoning.provider_params(
        model_id="gemini-2.5-flash", provider="google", effort="low",
    ) == {"reasoning_effort": "low"}


def test_deepseek_refuses_intermediate_level():
    assert reasoning.provider_params(
        model_id="deepseek-chat", provider="deepseek", effort="high",
    ) == {"thinking": {"type": "enabled"}}
    with pytest.raises(ReasoningError):
        reasoning.provider_params(model_id="deepseek-chat", provider="deepseek", effort="low")


# ── local runtimes ─────────────────────────────────────────────────────────

LOCAL = "geekcubo_local"


@pytest.mark.parametrize("metadata, expected", [
    ({"thinking_values": [True, False]}, ("true", "false")),
    ({"thinking_values": ["low", "medium", "high"]}, ("low", "medium", "high")),
    ({"thinking": True}, ("true", "false")),
    ({"thinking": False}, ("false",)),
    ('{"thinking": true}', ("true", "false")),
    ({}, None), (None, None), ("not json", None),
])
def test_local_thinking_from_metadata(metadata, expected):
    assert reasoning.local_thinking_from_metadata(metadata) == expected


def test_ollama_boolean_model():
    kw = dict(provider=LOCAL, local_adapter="ollama", local_thinking=("true", "false"))
    assert reasoning.supported_levels("local/m1/qwen3:8b", **kw) == ("none", "high")
    assert reasoning.provider_params(model_id="local/m1/qwen3:8b", effort="high", **kw) == {"think": True}
    assert reasoning.provider_params(model_id="local/m1/qwen3:8b", effort="none", **kw) == {"think": False}
    with pytest.raises(ReasoningError):
        reasoning.provider_params(model_id="local/m1/qwen3:8b", effort="low", **kw)


def test_ollama_named_levels():
    kw = dict(provider=LOCAL, local_adapter="ollama", local_thinking=("low", "medium", "high"))
    assert reasoning.provider_params(model_id="local/m1/gpt-oss:20b", effort="medium", **kw) == {
        "think": "medium",
    }


def test_ollama_gpt_oss_without_metadata():
    kw = dict(provider=LOCAL, local_adapter="ollama")
    assert reasoning.supported_levels("local/m1/gpt-oss:20b", **kw) == ("low", "medium", "high")


def test_ollama_model_that_cannot_think():
    kw = dict(provider=LOCAL, local_adapter="ollama", local_thinking=("false",))
    assert reasoning.supported_levels("local/m1/llama3.1:8b", **kw) == ()


def test_ollama_unreported_model_only_sends_expressible_levels():
    kw = dict(provider=LOCAL, local_adapter="ollama")
    assert reasoning.supported_levels("local/m1/mystery", **kw) is None
    assert reasoning.provider_params(model_id="local/m1/mystery", effort="high", **kw) == {"think": True}
    with pytest.raises(ReasoningError):
        reasoning.provider_params(model_id="local/m1/mystery", effort="medium", **kw)


def test_lmstudio_passes_reasoning_effort_per_call():
    params = reasoning.provider_params(
        model_id="local/m1/org/some-model", provider=LOCAL, local_adapter="lmstudio", effort="low",
    )
    assert params == {"reasoning_effort": "low", "allowed_openai_params": ["reasoning_effort"]}


# ── headers ────────────────────────────────────────────────────────────────


def test_describe_reports_downgrade():
    assert reasoning.describe(requested=None, effective=None, model_id="x") == {}
    out = reasoning.describe(requested="high", effective="medium", model_id="x")
    assert out == {
        "x-geek-reasoning-requested": "high",
        "x-geek-reasoning-effective": "medium",
        "x-geek-reasoning-downgraded": "true",
    }
