"""Auto planner: turns a routing policy into an ordered candidate list.

`choose_auto_model` (app/auto_routing.py) is the ranker that has always
served `model="auto"`, and it stays the ranker. This module only decides
WHICH catalog slice it ranks and WHAT to append as fallback:

    capability / deployability / pricing / allowlist / context filters
        -> optional pool restriction (Adaptive-Gated tier, escalation)
        -> strategy ranking (the existing choose_auto_model)
        -> optional evidence re-rank (Adaptive, only with enough data)
        -> explicit fallback list, capped by max_attempts
        -> optional stickiness (same model for the same conversation)

With the default policy every optional stage is a no-op, so the result is
identical to the pre-policy resolver. Tests pin that equivalence.

The planner never calls an upstream and never asks a model to judge
difficulty: there is no hidden cost per request.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from app.auto_routing import (
    _model_meets,
    choose_auto_model,
    is_confirmed_price,
    is_priced_for_auto,
)
from app.routing_policy import (
    ADAPTIVE_MIN_SAMPLES,
    STRATEGY_LABELS,
    allows_reference_estimates,
    apply_quality_floor,
    classify_difficulty,
    pool_membership,
)

# ── diagnosis categories ───────────────────────────────────────────────────
# Stable machine-readable codes (header `x-geek-routing-diagnosis`). The
# x-geek-error-type header keeps its original two values so the native
# Anthropic / Gemini surfaces map these exactly as before.
NO_PROVIDERS = "no_providers_configured"
ALL_DISABLED = "all_providers_disabled"
NO_AUTO_ELIGIBLE = "no_auto_eligible_providers"
NO_MODELS = "no_registered_models"
CAPABILITY = "capability_mismatch"
CONTEXT = "context_mismatch"
POOL = "pool_mismatch"
NOT_ALLOWED = "allowlist_mismatch"
EXHAUSTED = "candidates_exhausted"

_PROVIDER_LEVEL = {NO_PROVIDERS, ALL_DISABLED}


def error_type_for(category: str) -> str:
    """Map a diagnosis to the legacy x-geek-error-type value."""
    return "no_providers_configured" if category in _PROVIDER_LEVEL else "no_capable_provider"


class AutoRoutingError(Exception):
    def __init__(self, category: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code


@dataclass
class AutoPlan:
    candidates: list[str]
    strategy: str                 # what the admin configured
    effective_strategy: str       # what actually ranked this request
    tier: str | None = None       # mundane | hard | fallback | escalated
    reason: str = ""
    candidate_count: int = 0      # eligible models after filtering
    escalated: bool = False
    shadow_escalation: bool = False
    sticky: bool = False
    conversation_key: str | None = None
    notes: list[str] = field(default_factory=list)
    # Routing profile slug when the request named one (`model="economy"`).
    profile: str | None = None

    def headers(self) -> dict[str, str]:
        out = {
            "x-geek-routing-profile": self.profile or "auto",
            "x-geek-routing-strategy": self.strategy,
            "x-geek-routing-effective": self.effective_strategy,
            "x-geek-routing-candidates": str(self.candidate_count),
        }
        if self.tier:
            out["x-geek-routing-tier"] = self.tier
        if self.escalated:
            out["x-geek-routing-escalated"] = "true"
        if self.reason:
            # Headers must be latin-1; keep the reason ASCII and short.
            out["x-geek-routing-reason"] = self.reason.encode("ascii", "replace").decode()[:200]
        return out


# ── conversation state (stickiness + escalation strikes) ──────────────────
# In-process and TTL-bounded. Conversation state is a routing hint, not a
# record of truth: losing it on restart only means a fresh start, never a
# wrong answer. Multi-worker deployments see per-worker state (documented).


@dataclass
class _ConvState:
    last_model: str | None = None
    failures: int = 0
    escalations: int = 0
    escalated_cost_microcents: int = 0
    escalated_active: bool = False
    updated: float = field(default_factory=time.monotonic)


_CONVERSATIONS: dict[str, _ConvState] = {}
_MAX_CONVERSATIONS = 5000
_DEFAULT_TTL_S = 30 * 60


def reset_state() -> None:
    """Test hook."""
    _CONVERSATIONS.clear()
    _EVIDENCE_CACHE.clear()


def conversation_key(body: dict, hint: str | None = None) -> str | None:
    """A stable id for "this conversation".

    An explicit `x-geek-conversation-id` wins. Otherwise the opening of the
    conversation (system prompt + first user turn) is hashed: chat clients
    resend the full history, so that prefix is stable across turns. Only a
    hash is kept — no message content is stored.
    """
    if hint:
        return "h:" + hashlib.sha256(hint.strip().encode()).hexdigest()[:32]
    messages = body.get("messages") or []
    first_system = next(
        (m.get("content") for m in messages
         if isinstance(m, dict) and m.get("role") == "system"), ""
    )
    first_user = next(
        (m.get("content") for m in messages
         if isinstance(m, dict) and m.get("role") == "user"), None
    )
    if first_user is None:
        return None
    raw = repr((first_system, first_user)).encode("utf-8", "replace")
    return "m:" + hashlib.sha256(raw).hexdigest()[:32]


def _state(key: str | None, ttl_s: int) -> _ConvState | None:
    if not key:
        return None
    now = time.monotonic()
    st = _CONVERSATIONS.get(key)
    if st is not None and now - st.updated > ttl_s:
        st = None
    if st is None:
        if len(_CONVERSATIONS) >= _MAX_CONVERSATIONS:
            oldest = min(_CONVERSATIONS, key=lambda k: _CONVERSATIONS[k].updated)
            _CONVERSATIONS.pop(oldest, None)
        st = _ConvState()
        _CONVERSATIONS[key] = st
    return st


def record_outcome(
    key: str | None,
    *,
    status_code: int,
    served_model: str | None,
    cost_microcents: int = 0,
    escalated: bool = False,
    ttl_s: int = _DEFAULT_TTL_S,
) -> None:
    """Feed an observed outcome back into conversation state.

    Only objective signals count: an HTTP status from the upstream path.
    A 4xx caused by the client's own request is not the model's failure and
    does not strike.
    """
    st = _state(key, ttl_s)
    if st is None:
        return
    st.updated = time.monotonic()
    if status_code >= 500 or status_code in (408, 429):
        st.failures += 1
    elif status_code < 400:
        st.failures = 0
        if served_model:
            st.last_model = served_model
    if escalated:
        st.escalated_cost_microcents += max(0, int(cost_microcents or 0))


# ── adaptive evidence ─────────────────────────────────────────────────────

_EVIDENCE_CACHE: dict[str, tuple[float, dict[str, dict[str, float]]]] = {}
_EVIDENCE_TTL_S = 60.0
_EVIDENCE_WINDOW_DAYS = 7


async def load_evidence(db) -> dict[str, dict[str, float]]:
    """Per-model observed outcomes from this installation's request log.

    `{model_id: {"n": count, "success": rate 0-1, "latency_ms": mean}}`,
    keyed by the routed candidate (Auto) or the pinned model name. Cached
    for a minute so Auto does not aggregate the log on every request.
    """
    cached = _EVIDENCE_CACHE.get("all")
    if cached and time.monotonic() - cached[0] < _EVIDENCE_TTL_S:
        return cached[1]

    from datetime import datetime, timedelta, timezone

    from sqlalchemy import case, func, select

    from packages.db.models.request_log import RequestLog

    since = datetime.now(timezone.utc) - timedelta(days=_EVIDENCE_WINDOW_DAYS)
    model_col = func.coalesce(RequestLog.routed_model, RequestLog.model_requested)
    stmt = (
        select(
            model_col.label("model"),
            func.count().label("n"),
            func.sum(case((RequestLog.status_code < 400, 1), else_=0)).label("ok"),
            func.avg(RequestLog.latency_ms).label("lat"),
        )
        .where(
            RequestLog.created_at >= since,
            RequestLog.is_deleted == 0,
            RequestLog.provider != "cache",
        )
        .group_by(model_col)
    )
    out: dict[str, dict[str, float]] = {}
    try:
        for row in (await db.execute(stmt)).all():
            if not row.model or row.model == "auto":
                continue
            n = int(row.n or 0)
            out[row.model] = {
                "n": n,
                "success": (float(row.ok or 0) / n) if n else 0.0,
                "latency_ms": float(row.lat or 0.0),
            }
    except Exception:
        # Evidence is an optimisation; a failing aggregate must never break
        # routing. Fall through with no evidence (deterministic strategy).
        out = {}
    _EVIDENCE_CACHE["all"] = (time.monotonic(), out)
    return out


def _evidence_rank(ids: list[str], evidence: dict[str, dict[str, float]]) -> list[str]:
    """Order by observed success (dominant), then latency. Stable for ties."""
    def key(item: tuple[int, str]):
        idx, mid = item
        ev = evidence.get(mid)
        if not ev or ev["n"] < ADAPTIVE_MIN_SAMPLES:
            return (1, 0.0, 0.0, idx)  # unproven: after proven, keep base order
        return (0, -ev["success"], ev["latency_ms"], idx)
    return [mid for _, mid in sorted(enumerate(ids), key=key)]


# ── helpers ───────────────────────────────────────────────────────────────


def estimate_prompt_tokens(body: dict) -> int:
    """Cheap upper-bound-ish estimate (~4 chars/token). No tokenizer call."""
    chars = 0
    for m in body.get("messages") or []:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chars += len(part["text"])
    for tool in body.get("tools") or []:
        chars += len(repr(tool))
    return chars // 4


# ── planning ──────────────────────────────────────────────────────────────


def plan_auto(
    *,
    body: dict,
    needs: set[str],
    deployable: set[str],
    catalog: list,
    strategy: str,
    preferred_models: list[str] | None,
    allowlist: list[str] | None,
    quality_scores: dict[str, float] | None,
    tps_scores: dict[str, float] | None,
    ttft_scores: dict[str, float] | None,
    policy: dict[str, Any],
    evidence: dict[str, dict[str, float]] | None = None,
    hints: dict[str, str] | None = None,
) -> AutoPlan:
    """Return the ordered candidate list for one Auto request.

    Raises `AutoRoutingError` with a categorised, actionable message when no
    candidate qualifies. Never raises for a policy the router cannot fully
    honour (e.g. Adaptive without evidence) — it degrades to a named
    deterministic strategy and reports that in `notes`.
    """
    hints = hints or {}
    evidence = evidence or {}
    notes: list[str] = []
    ranker_strategy = "balanced" if strategy == "adaptive_gated" else strategy
    if ranker_strategy == "adaptive":
        ranker_strategy = "balanced"
    effective = ranker_strategy

    # ── context window filter (operator-configured limits only) ──
    est_tokens = estimate_prompt_tokens(body)
    context_dropped: list[str] = []
    usable_catalog = []
    for m in catalog:
        limit = getattr(m, "context_length", None)
        if limit and est_tokens > limit:
            context_dropped.append(m.id)
            continue
        usable_catalog.append(m)

    # ── quality floor (Balanced) ──
    if ranker_strategy == "balanced" and policy.get("balanced_min_quality"):
        if quality_scores:
            usable_catalog = apply_quality_floor(
                usable_catalog, int(policy["balanced_min_quality"]), quality_scores
            )
        else:
            notes.append("quality floor set but no quality scores available; floor not applied")

    allow_estimates = allows_reference_estimates(policy)

    def _qualifies(m) -> bool:
        return (
            m.id in deployable
            and _model_meets(m, needs)
            and is_priced_for_auto(m, allow_estimates=allow_estimates)
            and (allowlist is None or m.id in allowlist)
        )

    all_ids = {m.id for m in usable_catalog}
    pools = pool_membership(policy, known_ids=all_ids)
    convo = conversation_key(body, hints.get("conversation_id"))
    esc = policy.get("escalation") or {}
    stick = policy.get("stickiness") or {}
    ttl_s = int(stick.get("ttl_minutes") or 30) * 60
    state = _state(convo, ttl_s) if (esc.get("mode", "off") != "off" or stick.get("enabled")) else None

    # ── escalation decision (pre-request only; never mid-stream) ──
    escalated = False
    shadow = False
    mode = esc.get("mode", "off")
    want_escalate = False
    trigger = ""
    if mode != "off" and state is not None:
        if state.escalated_active:
            want_escalate, trigger = True, "conversation already escalated"
        elif mode == "manual" and hints.get("escalate"):
            want_escalate, trigger = True, "client requested escalation"
        elif mode == "auto" and state.failures >= int(esc.get("failure_threshold", 2)):
            want_escalate, trigger = True, f"{state.failures} consecutive upstream failures"
        if want_escalate:
            cap = esc.get("max_cost_microcents")
            if not state.escalated_active and state.escalations >= int(esc.get("max_per_conversation", 2)):
                want_escalate = False
                notes.append("escalation limit reached for this conversation")
            elif cap is not None and state.escalated_cost_microcents >= int(cap):
                want_escalate = False
                notes.append("escalation spend cap reached")
    if want_escalate:
        if esc.get("shadow"):
            shadow = True
            notes.append(f"shadow: would escalate ({trigger})")
        else:
            escalated = True

    # ── tier / pool selection ──
    tier: str | None = None
    pool_ids: set[str] | None = None
    reason_bits: list[str] = []
    if escalated:
        tier = "escalated"
        pool_ids = pools.get(esc.get("to_pool", "hard")) or set()
        reason_bits.append(f"escalated: {trigger}")
        if not pool_ids:
            raise AutoRoutingError(
                POOL,
                f"Escalation target pool '{esc.get('to_pool', 'hard')}' has no "
                "registered models. Add models to it on the Routing page or "
                "turn escalation off.",
            )
    elif strategy == "adaptive_gated":
        diff = classify_difficulty(body, needs, policy)
        tier = diff.tier
        pool_ids = pools.get(diff.tier) or set()
        reason_bits.append(
            f"{diff.tier}: " + (", ".join(diff.signals) if diff.signals else "no hard signals")
        )
        if not pool_ids:
            notes.append(f"{diff.tier} pool is empty")

    def _ranked(slice_catalog: list, strat: str) -> list[str]:
        ids, _ = choose_auto_model(
            needs=needs,
            deployable=deployable,
            candidates=slice_catalog,
            strategy=strat,
            preferred_models=preferred_models,
            allowlist=allowlist,
            quality_scores=quality_scores,
            tps_scores=tps_scores,
            ttft_scores=ttft_scores,
            top_n=max(1, int((policy.get("fallback") or {}).get("max_attempts", 5))),
            allow_estimates=allow_estimates,
        )
        return ids

    if pool_ids is not None:
        ranked = _ranked([m for m in usable_catalog if m.id in pool_ids], ranker_strategy)
        if not ranked and strategy == "adaptive_gated" and not escalated:
            # Tier pool has nothing capable: explicit fallback pool, then the
            # mundane pool if the admin allowed it. Never the whole catalog —
            # pools exist precisely to keep requests out of models the admin
            # did not choose.
            fallback_pool = pools.get("fallback") or set()
            ranked = _ranked([m for m in usable_catalog if m.id in fallback_pool], ranker_strategy)
            if ranked:
                tier = "fallback"
                reason_bits.append("tier pool had no capable model; used fallback pool")
            elif tier == "hard" and (policy.get("gated") or {}).get("allow_mundane_fallback", True):
                mundane = pools.get("mundane") or set()
                ranked = _ranked([m for m in usable_catalog if m.id in mundane], ranker_strategy)
                if ranked:
                    tier = "fallback"
                    reason_bits.append("hard pool had no capable model; used mundane pool")
        if not ranked:
            target = tier or "pool"
            raise AutoRoutingError(
                POOL,
                f"No capable model in the {target} pool for capabilities "
                f"{sorted(needs) or 'none'}. Add a capable model to the pool "
                "(or the fallback pool) on the Routing page.",
            )
    else:
        ranked = _ranked(usable_catalog, ranker_strategy)

    if not ranked:
        # Empty message = "ask diagnose_empty()": the caller has the custom
        # provider views and full catalog needed for the categorised answer.
        raise AutoRoutingError(CONTEXT if context_dropped else CAPABILITY, "")

    # ── adaptive evidence re-rank ──
    if strategy in ("adaptive", "adaptive_gated"):
        proven = [mid for mid in ranked if (evidence.get(mid) or {}).get("n", 0) >= ADAPTIVE_MIN_SAMPLES]
        if len(proven) >= 1 and len(ranked) > 1 and len(proven) >= min(2, len(ranked)):
            ranked = _evidence_rank(ranked, evidence)
            effective = "adaptive"
            reason_bits.append(f"ranked by observed success/latency ({len(proven)} proven)")
        else:
            counts = [int((evidence.get(mid) or {}).get("n", 0)) for mid in ranked]
            notes.append(
                f"adaptive: not enough evidence (need {ADAPTIVE_MIN_SAMPLES} requests "
                f"per model, have {max(counts) if counts else 0}); using balanced"
            )

    candidate_count = len(ranked)

    # ── report evidence-free degradations honestly ──
    # The ranker keeps routing when the evidence a strategy needs is missing,
    # but it does so by a different rule. Name that rule instead of letting
    # the decision claim a basis it did not have. Ranking and the
    # `effective_strategy` header contract are unchanged; only notes are added.
    def _has(scores, mid: str) -> bool:
        if not scores:
            return False
        return scores.get(mid) is not None or (
            "." in mid and scores.get(mid.replace(".", "-")) is not None
        )

    if ranker_strategy == "quality" and not any(_has(quality_scores, m) for m in ranked):
        notes.append(
            "quality: no quality score for any candidate; ranked by price as a "
            "proxy (most expensive first). Add Artificial Analysis or manual "
            "scores on the Quality page."
        )
    elif ranker_strategy == "quality":
        unscored = [m for m in ranked if not _has(quality_scores, m)]
        if unscored:
            notes.append(
                "quality: unscored candidates rank after scored ones: " + ", ".join(unscored)
            )
    elif (
        ranker_strategy == "balanced"
        and effective == "balanced"
        and not any(_has(quality_scores, m) for m in ranked)
    ):
        notes.append(
            "balanced: no quality score for any eligible candidate; ranked by "
            "price only (cheapest first)"
        )
    elif ranker_strategy == "fastest" and not any(
        _has(tps_scores, m) and _has(ttft_scores, m) for m in ranked
    ):
        notes.append(
            "fastest: no throughput/first-token benchmark for any eligible "
            "candidate; latency is unknown, so ranked by price only (cheapest first)"
        )

    # ── explicit fallback list ──
    fb = policy.get("fallback") or {}
    max_attempts = max(1, int(fb.get("max_attempts", 5)))
    if not fb.get("enabled", True):
        ranked = ranked[:1]
    else:
        by_id = {m.id: m for m in usable_catalog}
        for mid in fb.get("models") or []:
            m = by_id.get(mid)
            if m is not None and mid not in ranked and _qualifies(m):
                ranked.append(mid)
        ranked = ranked[:max_attempts]

    # ── stickiness ──
    sticky = False
    if stick.get("enabled") and state is not None and state.last_model and not escalated:
        if state.last_model in ranked and ranked[0] != state.last_model:
            ranked.remove(state.last_model)
            ranked.insert(0, state.last_model)
            sticky = True
            reason_bits.append("kept conversation on its previous model")
        elif ranked and ranked[0] == state.last_model:
            sticky = True

    if escalated and state is not None:
        if not state.escalated_active:
            state.escalations += 1
        state.escalated_active = True
        state.failures = 0

    if allow_estimates:
        by_id_all = {m.id: m for m in usable_catalog}
        estimated = [
            mid for mid in ranked
            if mid in by_id_all and not is_confirmed_price(by_id_all[mid])
        ]
        if estimated:
            notes.append(
                "estimate-based pricing: "
                + ", ".join(estimated)
                + " ranked on reference estimates, not confirmed provider rates"
            )

    # `fastest` is a legacy strategy outside STRATEGY_LABELS; without this the
    # reason read "fastest: best of N" next to an effective label "fastest".
    label = STRATEGY_LABELS.get(strategy) or {"fastest": "Fastest"}.get(strategy, strategy)
    if not reason_bits:
        reason_bits.append(f"{label}: best of {candidate_count} eligible")
    return AutoPlan(
        candidates=ranked,
        strategy=strategy,
        effective_strategy=effective,
        tier=tier,
        reason="; ".join(reason_bits),
        candidate_count=candidate_count,
        escalated=escalated,
        shadow_escalation=shadow,
        sticky=sticky,
        conversation_key=convo,
        notes=notes,
    )


# ── diagnosis for an empty result ─────────────────────────────────────────


def diagnose_empty(
    *,
    needs: set[str],
    deployable: set[str],
    full_catalog: list,
    auto_catalog: list,
    custom_views: list,
    allowlist: list[str] | None,
    body: dict,
    allow_estimates: bool = False,
) -> tuple[str, str]:
    """Categorise WHY Auto has no candidate. Returns (category, message).

    Ordered from the most fundamental cause to the most specific so the
    operator fixes the first real blocker, not a symptom.
    """
    custom_total = sum(len(p.models) for p in custom_views)

    if not deployable and not custom_views:
        return NO_PROVIDERS, (
            "No providers are configured. Add a provider key or a custom "
            "provider under Providers."
        )
    if not deployable and custom_views and all(not p.is_enabled for p in custom_views):
        return ALL_DISABLED, (
            "All providers are disabled. Enable a provider under Providers."
        )

    auto_deployable = [m for m in auto_catalog if m.id in deployable]
    if not auto_deployable:
        if custom_views and custom_total == 0:
            return NO_MODELS, (
                "Custom providers have no registered models. Use 'Fetch Available "
                "Models' or add a model on the provider."
            )
        if custom_views and not any(p.eligible_for_auto and p.is_enabled for p in custom_views):
            return NO_AUTO_ELIGIBLE, (
                "No provider is eligible for Auto: every custom provider is "
                "pinned-only. Click 'Enable Auto' on a provider to let model=auto use it."
            )
        return NO_AUTO_ELIGIBLE, (
            "No deployable model is eligible for Auto. Enable Auto on a provider "
            "or pin a specific model."
        )

    priced = [
        m for m in auto_deployable if is_priced_for_auto(m, allow_estimates=allow_estimates)
    ]
    if not priced:
        if any(is_priced_for_auto(m, allow_estimates=True) for m in auto_deployable):
            return NO_MODELS, (
                "Auto-eligible models only have reference price estimates. Strict "
                "routing requires a confirmed provider price: set the custom "
                "input/output price on the model, or explicitly enable "
                "estimate-based pricing in the routing policy."
            )
        return NO_MODELS, (
            "Auto-eligible models have no pricing configured; Auto treats "
            "unpriced models as unknown, not free. Set input/output pricing."
        )

    capable = [m for m in priced if _model_meets(m, needs)]
    if not capable:
        missing = ", ".join(sorted(needs)) or "none"
        return CAPABILITY, (
            f"No Auto-eligible model supports the requested capabilities ({missing}). "
            "Enable the capability on a model that supports it, or pin a model."
        )

    est = estimate_prompt_tokens(body)
    fits = [m for m in capable if not (getattr(m, "context_length", None) and est > m.context_length)]
    if not fits:
        return CONTEXT, (
            f"The request (~{est} tokens) exceeds the context limit of every "
            "capable Auto-eligible model."
        )

    if allowlist is not None and not any(m.id in allowlist for m in fits):
        return NOT_ALLOWED, (
            "Capable models exist, but none are in this API key's model allowlist."
        )

    return CAPABILITY, (
        f"No deployable model satisfies the requested capabilities "
        f"({sorted(needs) or 'none'})."
    )
