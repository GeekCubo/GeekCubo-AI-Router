"""Advanced Auto routing policy: pools, gating, fallback and escalation.

The policy is stored as JSON on `routing_config.policy`. A NULL policy means
DEFAULTS, which reproduce the pre-policy behaviour exactly — an existing
install that never opens the Routing page keeps routing the way it did.

Honesty rules this module is built around:

* Nothing here invents quality. `quality` ranking uses the Artificial
  Analysis index (or admin overrides) that already existed; when no evidence
  is available the caller is told so, and the deterministic fallback is used.
* "Adaptive" is not learning. It re-ranks by *observed* success rate and
  latency from this installation's own request log, and only once there is
  enough evidence; below the threshold it falls back to a named deterministic
  strategy. `adaptive_status()` reports which one actually ran.
* Escalation triggers on observable events (upstream failures), never on a
  guess about whether the model's answer was correct.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

# Strategies the router actually implements. `dsl` is deliberately absent:
# a rule language is out of scope, and accepting the key would imply support.
STRATEGIES = ("balanced", "cheapest", "quality", "adaptive", "adaptive_gated")

STRATEGY_LABELS = {
    "balanced": "Balanced",
    "cheapest": "Cheapest",
    "quality": "Quality First",
    "adaptive": "Adaptive",
    "adaptive_gated": "Adaptive-Gated",
}

# Deterministic strategies an "adaptive" policy may degrade to.
DETERMINISTIC_FALLBACKS = ("balanced", "cheapest", "quality")

ESCALATION_MODES = ("off", "manual", "auto")

# Minimum observations before adaptive ranking is used at all. Below this the
# sample is a coin flip and would just add variance to routing.
ADAPTIVE_MIN_SAMPLES = 20
# Escalation is a cost multiplier; cap it hard by default.
DEFAULT_MAX_ESCALATIONS = 2

DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    # Balanced: minimum quality percentile (0-100) a candidate must clear
    # before cost is optimised. 0 == no floor (pure cost ordering).
    "balanced_min_quality": 0,
    "pools": {
        "mundane": [],
        "hard": [],
        "fallback": [],
    },
    "pool_overrides": [],  # [{model, pool}] forced assignments
    "gated": {
        "enabled": True,
        # A request is "hard" when it shows any of these observable signals.
        # This is a heuristic over the REQUEST, not a judgement about whether
        # an answer would be correct.
        "hard_on_tools": True,
        "hard_on_vision": True,
        "hard_on_min_messages": 8,
        "hard_on_min_prompt_chars": 6000,
        "hard_on_max_output_tokens": 4000,
        # When the hard pool has no capable candidate, fall back to these.
        "allow_mundane_fallback": True,
    },
    "fallback": {
        "enabled": True,
        # Primary + fallbacks, total. 5 matches the pre-policy resolver's
        # top_n, so a default policy routes exactly as before.
        "max_attempts": 5,
        # Explicit ordered list; empty = use the strategy's ranked candidates.
        "models": [],
    },
    "escalation": {
        "mode": "off",
        "failure_threshold": 2,
        "max_per_conversation": DEFAULT_MAX_ESCALATIONS,
        "from_pool": "mundane",
        "to_pool": "hard",
        "max_cost_microcents": None,
        "shadow": False,
    },
    "stickiness": {
        "enabled": False,
        "ttl_minutes": 30,
    },
    "pricing": {
        # Off by default: only confirmed prices (built-in catalog or an
        # administrator-confirmed custom rate) take part in Auto, Cheapest
        # and cost ceilings. When on, reference estimates are also used and
        # every decision based on one is labelled as estimate-based.
        "allow_reference_estimates": False,
    },
    "local": {
        # Local AI Connect models (`local/<machine>/<model>`) may take part in
        # `model="auto"`. Global master switch stays on local_settings; this is
        # the routing-policy view so a policy can pin a specific machine set.
        "enabled": True,
        # When true, a request Auto routed to a local model must not be
        # retried against a cloud provider if the machine is offline or fails.
        "no_cloud_fallback": False,
        # Optional machine ids allowed in Auto. Empty = every approved,
        # auto-eligible machine.
        "machines": [],
    },
}

_INT_FIELDS = {
    ("balanced_min_quality",): (0, 100),
    ("fallback", "max_attempts"): (1, 20),
    ("escalation", "failure_threshold"): (1, 20),
    ("escalation", "max_per_conversation"): (0, 10),
    ("stickiness", "ttl_minutes"): (1, 24 * 60),
}


class PolicyError(ValueError):
    """Invalid policy payload. Message is safe to return to the admin UI."""


def default_policy() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_POLICY)


def normalize_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a stored/partial policy onto the defaults and validate it.

    Unknown keys are dropped rather than stored, so a typo cannot lurk in the
    database looking like configuration that works.
    """
    out = default_policy()
    if not raw:
        return out
    if not isinstance(raw, dict):
        raise PolicyError("policy must be an object")

    if "balanced_min_quality" in raw:
        out["balanced_min_quality"] = _as_int(
            raw["balanced_min_quality"], "balanced_min_quality", 0, 100
        )

    pools = raw.get("pools")
    if pools is not None:
        if not isinstance(pools, dict):
            raise PolicyError("pools must be an object")
        for name in ("mundane", "hard", "fallback"):
            if name in pools:
                out["pools"][name] = _as_str_list(pools[name], f"pools.{name}")

    if "pool_overrides" in raw:
        overrides = raw["pool_overrides"]
        if not isinstance(overrides, list):
            raise PolicyError("pool_overrides must be a list")
        clean = []
        for item in overrides:
            if not isinstance(item, dict):
                raise PolicyError("each pool_overrides entry must be an object")
            model = str(item.get("model") or "").strip()
            pool = str(item.get("pool") or "").strip()
            if not model or pool not in ("mundane", "hard"):
                raise PolicyError(
                    "pool_overrides entries need {model, pool} with pool one of mundane|hard"
                )
            clean.append({"model": model, "pool": pool})
        out["pool_overrides"] = clean

    gated = raw.get("gated")
    if gated is not None:
        if not isinstance(gated, dict):
            raise PolicyError("gated must be an object")
        for key in ("enabled", "hard_on_tools", "hard_on_vision", "allow_mundane_fallback"):
            if key in gated:
                out["gated"][key] = bool(gated[key])
        for key, lo, hi in (
            ("hard_on_min_messages", 0, 1000),
            ("hard_on_min_prompt_chars", 0, 10_000_000),
            ("hard_on_max_output_tokens", 0, 10_000_000),
        ):
            if key in gated:
                out["gated"][key] = _as_int(gated[key], f"gated.{key}", lo, hi)

    fallback = raw.get("fallback")
    if fallback is not None:
        if not isinstance(fallback, dict):
            raise PolicyError("fallback must be an object")
        if "enabled" in fallback:
            out["fallback"]["enabled"] = bool(fallback["enabled"])
        if "max_attempts" in fallback:
            out["fallback"]["max_attempts"] = _as_int(
                fallback["max_attempts"], "fallback.max_attempts", 1, 20
            )
        if "models" in fallback:
            out["fallback"]["models"] = _as_str_list(fallback["models"], "fallback.models")

    esc = raw.get("escalation")
    if esc is not None:
        if not isinstance(esc, dict):
            raise PolicyError("escalation must be an object")
        if "mode" in esc:
            mode = str(esc["mode"]).strip().lower()
            if mode not in ESCALATION_MODES:
                raise PolicyError(f"escalation.mode must be one of {list(ESCALATION_MODES)}")
            out["escalation"]["mode"] = mode
        for key, lo, hi in (
            ("failure_threshold", 1, 20),
            ("max_per_conversation", 0, 10),
        ):
            if key in esc:
                out["escalation"][key] = _as_int(esc[key], f"escalation.{key}", lo, hi)
        for key in ("from_pool", "to_pool"):
            if key in esc:
                pool = str(esc[key]).strip()
                if pool not in ("mundane", "hard", "fallback"):
                    raise PolicyError(f"escalation.{key} must be mundane|hard|fallback")
                out["escalation"][key] = pool
        if "max_cost_microcents" in esc:
            value = esc["max_cost_microcents"]
            out["escalation"]["max_cost_microcents"] = (
                None if value is None
                else _as_int(value, "escalation.max_cost_microcents", 0, 10**12)
            )
        if "shadow" in esc:
            out["escalation"]["shadow"] = bool(esc["shadow"])

    stick = raw.get("stickiness")
    if stick is not None:
        if not isinstance(stick, dict):
            raise PolicyError("stickiness must be an object")
        if "enabled" in stick:
            out["stickiness"]["enabled"] = bool(stick["enabled"])
        if "ttl_minutes" in stick:
            out["stickiness"]["ttl_minutes"] = _as_int(
                stick["ttl_minutes"], "stickiness.ttl_minutes", 1, 24 * 60
            )

    local = raw.get("local")
    if local is not None:
        if not isinstance(local, dict):
            raise PolicyError("local must be an object")
        if "enabled" in local:
            out["local"]["enabled"] = bool(local["enabled"])
        if "no_cloud_fallback" in local:
            out["local"]["no_cloud_fallback"] = bool(local["no_cloud_fallback"])
        if "machines" in local:
            machines = local["machines"]
            if not isinstance(machines, list):
                raise PolicyError("local.machines must be a list of machine ids")
            out["local"]["machines"] = [str(m) for m in machines if str(m).strip()]

    pricing = raw.get("pricing")
    if pricing is not None:
        if not isinstance(pricing, dict):
            raise PolicyError("pricing must be an object")
        if "allow_reference_estimates" in pricing:
            out["pricing"]["allow_reference_estimates"] = bool(
                pricing["allow_reference_estimates"]
            )
    return out


def allows_reference_estimates(policy: dict[str, Any] | None) -> bool:
    """Whether the policy explicitly opts into estimate-based pricing."""
    if not isinstance(policy, dict):
        return False
    return bool((policy.get("pricing") or {}).get("allow_reference_estimates", False))


def _as_int(value: Any, name: str, lo: int, hi: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"{name} must be an integer") from exc
    if ivalue < lo or ivalue > hi:
        raise PolicyError(f"{name} must be between {lo} and {hi}")
    return ivalue


def _as_str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PolicyError(f"{name} must be a list of model ids")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PolicyError(f"{name} entries must be strings")
        item = item.strip()
        if item and item not in out:
            out.append(item)
    return out


# ── request difficulty ─────────────────────────────────────────────────────


@dataclass
class Difficulty:
    """Why a request was classified into a tier (observable signals only)."""

    tier: str = "mundane"          # "mundane" | "hard"
    signals: list[str] = field(default_factory=list)


def classify_difficulty(
    body: dict,
    needs: set[str],
    policy: dict[str, Any],
) -> Difficulty:
    """Classify a request as mundane or hard from signals in the request.

    Explicitly NOT a prediction of whether the answer will be correct — the
    router cannot know that. These are observable, configurable triggers:
    tool use, image input, conversation length, prompt size and requested
    output length.
    """
    gated = (policy or {}).get("gated", {})
    if not gated.get("enabled", True):
        return Difficulty(tier="mundane", signals=["gating disabled"])

    signals: list[str] = []
    if gated.get("hard_on_tools", True) and "tools" in needs:
        signals.append("tools")
    if gated.get("hard_on_vision", True) and "vision" in needs:
        signals.append("vision")

    messages = body.get("messages") or []
    min_messages = gated.get("hard_on_min_messages", 8)
    if min_messages and len(messages) >= min_messages:
        signals.append(f"{len(messages)} messages")

    chars = 0
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chars += len(part["text"])
    min_chars = gated.get("hard_on_min_prompt_chars", 6000)
    if min_chars and chars >= min_chars:
        signals.append(f"{chars} prompt chars")

    max_out = body.get("max_completion_tokens") or body.get("max_tokens") or 0
    threshold = gated.get("hard_on_max_output_tokens", 4000)
    if threshold and isinstance(max_out, int) and max_out >= threshold:
        signals.append(f"max_tokens={max_out}")

    return Difficulty(tier="hard" if signals else "mundane", signals=signals)


def pool_membership(policy: dict[str, Any], known_ids: set[str] | None = None) -> dict[str, set[str]]:
    """Configured pool membership, with overrides applied.

    `known_ids` (when given) filters out entries that no longer resolve to a
    registered model, so a deleted model cannot silently occupy a pool slot.
    """
    pools = policy.get("pools") or {}
    out = {
        name: set(pools.get(name) or [])
        for name in ("mundane", "hard", "fallback")
    }
    for override in policy.get("pool_overrides") or []:
        model, pool = override["model"], override["pool"]
        out.setdefault(pool, set()).add(model)
    if known_ids is not None:
        out = {name: {m for m in ids if m in known_ids} for name, ids in out.items()}
    return out


def effective_strategy(strategy: str, adaptive_evidence: int) -> tuple[str, str | None]:
    """Resolve the strategy that will actually run.

    Returns `(effective_strategy, note)`. `adaptive` only re-ranks once there
    is enough evidence; otherwise it names the deterministic strategy used
    instead, so callers can report that honestly.
    """
    if strategy != "adaptive":
        return strategy, None
    if adaptive_evidence >= ADAPTIVE_MIN_SAMPLES:
        return "adaptive", None
    note = (
        f"adaptive needs {ADAPTIVE_MIN_SAMPLES} observed requests per model; "
        f"{adaptive_evidence} available, using balanced"
    )
    return "balanced", note


def apply_quality_floor(
    candidates: list,
    min_quality: int,
    quality_scores: dict[str, float] | None,
) -> list:
    """Drop candidates below the configured quality percentile.

    `min_quality == 0` is a no-op. When it is set but no scores exist, nothing
    is dropped (we cannot rank what we cannot measure) — the caller surfaces
    that as a warning rather than pretending the floor applied.
    """
    if not min_quality or not quality_scores:
        return candidates
    values = sorted(float(v) for v in quality_scores.values() if v is not None)
    if not values:
        return candidates
    idx = min(len(values) - 1, max(0, round((min_quality / 100) * (len(values) - 1))))
    threshold = values[idx]
    kept = [
        m for m in candidates
        if quality_scores.get(m.id) is None or float(quality_scores[m.id]) >= threshold
    ]
    return kept or candidates
