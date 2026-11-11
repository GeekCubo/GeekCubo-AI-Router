"""Reasoning-effort: one normalized vocabulary, translated per provider.

A client asks for a *reasoning effort* — `none`, `minimal`, `low`, `medium`,
`high`, `xhigh` or `max` — and this module decides whether the selected model
can honour it and what the provider actually needs to receive. It is the only
place that knows how an effort becomes a wire parameter, so routes, the auto
ranker and the native protocol adapters never re-interpret the value.

Three things are deliberately kept apart:

* **Capability** — can this model control reasoning effort at all, and at
  which levels? Tri-state, like every other capability in GeekCubo:
  Supported / Unsupported / Unknown. Unknown is *not* Unsupported: a model
  whose metadata is silent is attempted with the requested effort preserved,
  and a confirmed unsupported-parameter error from the provider is what
  settles it.
* **Translation** — the provider-specific parameter. Anthropic has adaptive
  thinking (`output_config.effort`) and legacy thinking (`budget_tokens`);
  Gemini has thinking budgets on 2.5 and thinking levels on 3; DeepSeek has
  on/off only; Ollama has `think`. None of these are interchangeable, and a
  level a provider cannot represent is refused rather than rounded.
* **Output** — returning reasoning *text* is a separate concern and is not
  implemented here. This module only controls how much the model thinks.

The effort ladder is ordered, which is what makes the optional downgrade
policy possible: `none < minimal < low < medium < high < xhigh < max`.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

# Ordered weakest → strongest. The order is load-bearing: the downgrade
# policy walks it downward and never upward.
LEVELS: tuple[str, ...] = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
LEVEL_RANK: dict[str, int] = {name: i for i, name in enumerate(LEVELS)}

# Anthropic's legacy thinking interface takes a token budget, not a level.
# These are the same budgets LiteLLM 1.108.1 uses for its own effort mapping,
# so a request behaves identically whether it arrives as an effort or as a
# budget. They are NOT a claim that "high" means 4096 tokens everywhere —
# only that this is the budget this adapter sends for that level.
BUDGET_BY_EFFORT: dict[str, int] = {
    "minimal": 1024,
    "low": 1024,
    "medium": 2048,
    "high": 4096,
    "xhigh": 8192,
    "max": 16384,
}

# Anthropic requires `budget_tokens < max_tokens`. When a client sends a
# budget but no output cap we cannot prove the request is valid, so the
# budget is capped to this many tokens below the model's own ceiling.
_MIN_OUTPUT_HEADROOM = 1024

# GeekCubo provider ids → LiteLLM provider ids. LiteLLM's metadata keys, its
# parameter validation and its per-provider translation are all keyed on the
# latter, so every lookup goes through this map.
LITELLM_PROVIDER: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "gemini",
    "groq": "groq",
    "deepseek": "deepseek",
    "xai": "xai",
    "mistral": "mistral",
    "together": "together_ai",
    "fireworks": "fireworks_ai",
    "cohere": "cohere_chat",
    "perplexity": "perplexity",
}

# Providers whose reasoning control is a plain on/off switch. Every level
# above `none` collapses to "on" — which is why these models are reported as
# supporting only `none` and `high` rather than the whole ladder.
_BOOLEAN_THINKING_PROVIDERS = frozenset({"deepseek"})

# Providers that can express an effort for models that reason. Used only to
# decide whether a model with NO metadata is worth advertising as "support
# unknown" — never to claim support.
EFFORT_PASSTHROUGH_PROVIDERS = frozenset(
    {
        "openai", "groq", "xai", "mistral", "together", "fireworks",
        "cohere", "perplexity",
    }
)

# Local AI Connect adapters. Ollama speaks `think`; LM Studio and the other
# OpenAI-compatible servers speak `reasoning_effort` (LM Studio only for
# models it knows reason — see `_local_params`).
_LOCAL_PROVIDER = "geekcubo_local"
_OLLAMA_ADAPTERS = frozenset({"ollama"})
_OPENAI_COMPAT_ADAPTERS = frozenset({"lmstudio", "vllm", "llamacpp", "custom"})

# Providers that expose *some* reasoning control (possibly model-dependent),
# i.e. a model on one of them is a candidate for the reasoning selector.
_REASONING_PROVIDERS = (
    EFFORT_PASSTHROUGH_PROVIDERS
    | _BOOLEAN_THINKING_PROVIDERS
    | {"anthropic", "google", _LOCAL_PROVIDER}
)

# Keys a translated level can produce. Used to tell two levels apart.
_REASONING_KEYS = ("reasoning_effort", "thinking", "thinkingConfig", "output_config")

# A probe needs an output cap. Kept modest: some models reject a max_tokens
# above their own ceiling, and LiteLLM does not validate Anthropic's
# budget_tokens against it, so a small cap does not hide any level.
_PROBE_MAX_TOKENS = 8192


class ReasoningError(Exception):
    """A reasoning request that cannot be honoured.

    Carries the HTTP status and error type the route should surface, so an
    unsupported parameter is never reported as a provider outage (503).
    """

    def __init__(self, message: str, *, status_code: int, error_type: str) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


def _invalid(message: str) -> ReasoningError:
    return ReasoningError(
        message, status_code=400, error_type="invalid_reasoning_effort"
    )


def _unsupported(message: str) -> ReasoningError:
    return ReasoningError(
        message, status_code=400, error_type="unsupported_reasoning_effort"
    )


# ── Normalization ──────────────────────────────────────────────────────


def normalize_effort(value: object) -> str | None:
    """Validate a client-supplied effort. `None` means "provider default".

    An invalid value raises rather than being dropped: silently discarding an
    explicit setting is the bug this module exists to prevent.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(
            f"reasoning_effort must be a string, got {type(value).__name__}"
        )
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized not in LEVEL_RANK:
        raise _invalid(
            f"Invalid reasoning_effort {value!r}. Supported values: "
            + ", ".join(LEVELS)
            + "."
        )
    return normalized


def effort_from_budget(budget: object) -> str | None:
    """Map an Anthropic/Gemini thinking budget onto the nearest level.

    Used only when a client speaks a native budget interface. The mapping is
    the inverse of `BUDGET_BY_EFFORT` and is documented as approximate: a
    budget is a token count, a level is a request for relative effort.
    """
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        return None
    if budget == 0:
        return "none"
    if budget <= 1024:
        return "low"
    if budget <= 2048:
        return "medium"
    if budget <= 4096:
        return "high"
    if budget <= 8192:
        return "xhigh"
    return "max"


def budget_for_effort(effort: str) -> int:
    return BUDGET_BY_EFFORT.get(effort, BUDGET_BY_EFFORT["medium"])


def is_weaker(candidate: str, requested: str) -> bool:
    """Whether `candidate` is a genuine step down from `requested`."""
    return LEVEL_RANK.get(candidate, -1) < LEVEL_RANK.get(requested, -1)


def downgrade_candidates(requested: str, *, minimum: str | None = None) -> list[str]:
    """Levels below `requested`, strongest first, floored at `minimum`.

    `none` and `minimal` are never produced as a downgrade target, whatever
    the floor: a request for `high` must not silently become "no reasoning
    at all", and a downgrade never moves upward.
    """
    floor = LEVEL_RANK.get(minimum, 0) if minimum else 0
    floor = max(floor, LEVEL_RANK["low"])
    start = LEVEL_RANK.get(requested, 0)
    return [LEVELS[i] for i in range(start - 1, floor - 1, -1)]


# ── Capability ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReasoningCapability:
    """What a model can do with reasoning effort.

    `levels` is `None` when the model's support is Unknown — the caller must
    not read that as "unsupported". `adjustable` is False for models that
    reason but expose no effort control (DeepSeek's on/off switch, a local
    model with a boolean `think`), which is the distinction that stops
    "supports reasoning" from being mistaken for "supports Low/Medium/High".
    """

    levels: tuple[str, ...] | None
    adjustable: bool
    source: str

    @property
    def state(self) -> str:
        if self.levels is None:
            return "unknown"
        return "supported" if self.levels else "unsupported"


def _litellm_meta(model_id: str, provider: str | None) -> dict:
    """LiteLLM's metadata for a model, or {} when it has none."""
    try:
        import litellm
    except Exception:  # pragma: no cover - litellm is a hard dependency
        return {}
    model_cost = getattr(litellm, "model_cost", {}) or {}
    llm_provider = LITELLM_PROVIDER.get(provider or "", provider)
    candidates = [model_id]
    if llm_provider:
        candidates.insert(0, f"{llm_provider}/{model_id}")
    for key in candidates:
        meta = model_cost.get(key)
        if isinstance(meta, dict):
            return meta
    return {}


@functools.lru_cache(maxsize=4096)
def _resolve_level(
    model_id: str, provider: str, level: str
) -> tuple[tuple[tuple[str, str], ...], bool]:
    """What LiteLLM itself produces for one level: (params, accepted).

    The authoritative answer for "will this reach the provider". LiteLLM
    knows its own providers: `reasoning_effort=xhigh` on a Gemini 2.5 model
    raises (the family has no such level), `reasoning_effort=low` on DeepSeek
    silently becomes `thinking.enabled` (on/off only), and an unknown model on
    a custom OpenAI endpoint passes the value straight through.

    Resolution is offline — no network, no cost — and cached per (model,
    provider, level).
    """
    llm_provider = LITELLM_PROVIDER.get(provider, provider)
    if not llm_provider:
        return (), False
    try:
        from litellm.utils import get_optional_params
    except Exception:  # pragma: no cover
        return (), False
    try:
        params = get_optional_params(
            model=model_id,
            custom_llm_provider=llm_provider,
            reasoning_effort=level,
            max_tokens=_PROBE_MAX_TOKENS,
        )
    except Exception:
        return (), False
    lifted = tuple(
        sorted(
            (key, repr(_effort_signature(key, params[key])))
            for key in _REASONING_KEYS
            if params.get(key) is not None
        )
    )
    return lifted, True


def _effort_signature(key: str, value: object) -> object:
    """The part of a translated control that changes how much the model thinks.

    Gemini's `includeThoughts` only asks for thought summaries in the reply;
    LiteLLM turns it off for `none`, which made `none` look distinct from
    `low` on Gemini 3 even though both send `thinkingLevel: low`.
    """
    if key == "thinkingConfig" and isinstance(value, dict):
        return {k: v for k, v in value.items() if k != "includeThoughts"}
    return value


def _levels_from_litellm(model_id: str, provider: str) -> tuple[str, ...]:
    """Levels LiteLLM actually translates into a provider control.

    A level is supported only when LiteLLM accepts it AND the resulting
    parameters change when the requested level changes. That second condition
    is what keeps a boolean-thinking provider honest: DeepSeek accepts every
    level and emits the same `thinking.enabled` for all of them, so only the
    levels it can distinguish (`none`, `high`) are reported.
    """
    signature: dict[tuple[tuple[str, str], ...], list[str]] = {}
    for level in LEVELS:
        params, accepted = _resolve_level(model_id, provider, level)
        if accepted and params:
            signature.setdefault(params, []).append(level)
    if not signature:
        return ()
    if len(signature) == 1:
        # One distinct control: the model thinks or it does not. Name the
        # strongest level in the group so a `high` request can still land.
        group = next(iter(signature.values()))
        usable = [level for level in group if level != "none"]
        return ("none", usable[-1]) if "none" in group else (usable[-1],)
    # Several levels that produce the same wire control are one level, not
    # several: Gemini 3 Pro sends `thinkingLevel: low` for none, minimal and
    # low alike. Only the strongest name in such a group is offered, so a
    # request is never silently turned into something stronger or weaker
    # than it asked for.
    return tuple(
        level for level in LEVELS
        if level in {_group_name(params, g) for params, g in signature.items()}
    )


def _group_name(params: tuple[tuple[str, str], ...], group: list[str]) -> str:
    """The one level that honestly names a group of identical translations.

    The level the wire value itself names wins (Mistral sends
    `reasoning_effort: "high"` for everything from minimal to max, so that
    group is `high`). Otherwise the strongest level up to `high`, the
    conventional "on"; `xhigh`/`max` only when nothing weaker shares it.
    """
    blob = " ".join(value for _key, value in params)
    named = [level for level in group if f"'{level}'" in blob]
    if named:
        return named[-1]
    usual = [level for level in group if LEVEL_RANK[level] <= LEVEL_RANK["high"]]
    return (usual or group)[-1]


# OpenAI-style levels outside the classic low/medium/high trio. LiteLLM
# passes any `reasoning_effort` string straight through for these providers,
# so a probe alone cannot tell whether the model accepts it; only an explicit
# `supports_<level>_reasoning_effort: true` in its metadata counts.
_FLAGGED_LEVELS = ("none", "minimal", "xhigh", "max")


def _openai_style_levels(model_id: str, provider: str) -> tuple[str, ...] | None:
    """Levels for an OpenAI-style `reasoning_effort` model, or None (Unknown).

    A model is confirmed only when LiteLLM's metadata marks it as a
    reasoning model; then low/medium/high are what the API documents, and
    every other level needs its own metadata flag. A model without that
    evidence stays Unknown — attempted with the effort preserved, never
    advertised as supporting a level.
    """
    meta = _litellm_meta(model_id, provider)
    if meta.get("supports_reasoning") is not True:
        if meta and not any(_resolve_level(model_id, provider, lv)[0] for lv in LEVELS):
            # Catalogued, and no level produces a reasoning control: LiteLLM
            # either refuses the parameter (gpt-4o) or accepts it and sends
            # nothing (Magistral, which only gets a fixed system prompt).
            # Either way it is confirmed unsupported, not Unknown — sending
            # it would silently do nothing while reporting it honoured.
            return ()
        return None
    probed = _levels_from_litellm(model_id, provider)
    if not probed and any(_resolve_level(model_id, provider, lv)[1] for lv in LEVELS):
        # A reasoning model whose effort LiteLLM accepts but never forwards
        # (Magistral): the setting would vanish, so the model has no effort
        # control as far as this gateway can deliver.
        return ()
    listed = meta.get("reasoning_effort_levels")
    listed = set(listed) if isinstance(listed, list) else set()
    levels = tuple(
        level for level in probed
        if level not in _FLAGGED_LEVELS
        or level in listed
        or meta.get(f"supports_{level}_reasoning_effort") is True
    )
    return levels or None


def _anthropic_levels(model_id: str, probed: tuple[str, ...]) -> tuple[str, ...]:
    """Claude levels that reach the model as requested.

    * Adaptive thinking takes `output_config.effort` in low/medium/high, and
      `xhigh`/`max` only on models whose metadata flags them — LiteLLM
      refuses the rest locally (claude-opus-4-6 has `max` but not `xhigh`).
    * `none` is `thinking: {type: disabled}`, except on always-on models
      (Fable/Mythos 5), where LiteLLM removes it and the model thinks anyway.
    """
    meta = _litellm_meta(model_id, "anthropic")
    levels = probed
    if meta.get("supports_adaptive_thinking") is True:
        levels = tuple(
            level for level in levels
            if level in ("low", "medium", "high")
            or (level in ("xhigh", "max")
                and meta.get(f"supports_{level}_reasoning_effort") is True)
        )
    if levels and "none" not in levels and meta.get("thinking_always_on") is not True:
        levels = ("none",) + levels
    return levels


# Gemini 2.5 Pro has no thinking switch: its budget range starts at 128, and
# `thinkingBudget: 0` (what `none` becomes) is rejected. LiteLLM's mapping
# does not know this, so it is stated here.
_GEMINI_ALWAYS_THINKING = ("gemini-2.5-pro",)


def _gemini_levels(model_id: str, probed: tuple[str, ...]) -> tuple[str, ...]:
    if any(prefix in model_id.lower() for prefix in _GEMINI_ALWAYS_THINKING):
        return tuple(level for level in probed if level != "none")
    return probed


def _boolean_thinking_levels(model_id: str, provider: str) -> tuple[str, ...]:
    """Levels a provider can distinguish when its control is on/off.

    DeepSeek accepts every level and emits `thinking.enabled` for all of
    them, so the ladder collapses to "off" and "on". The strongest level is
    the one reported for "on": a `high` request is honoured exactly, and a
    `low` request is refused rather than silently upgraded.
    """
    off, on = _resolve_level(model_id, provider, "none")
    if not off or not on or off == on:
        return ()
    return ("none", "high")


@functools.lru_cache(maxsize=2048)
def _capability_cached(
    model_id: str,
    provider: str | None,
    local_adapter: str | None,
    local_thinking: tuple[str, ...] | None = None,
) -> ReasoningCapability:
    if provider == _LOCAL_PROVIDER:
        return _local_capability(model_id, local_adapter, local_thinking)
    if provider is not None and provider in _BOOLEAN_THINKING_PROVIDERS:
        levels = _boolean_thinking_levels(model_id, provider)
        if levels:
            return ReasoningCapability(levels=levels, adjustable=False, source="provider")
        return ReasoningCapability(levels=None, adjustable=True, source="unknown")
    if provider is None or provider not in _REASONING_PROVIDERS:
        # A custom provider slug is an OpenAI-compatible endpoint, which is
        # how GeekCubo registers them; anything else has no reasoning
        # interface at all.
        if provider is not None:
            # An operator endpoint (custom provider or gateway). A model name
            # LiteLLM knows says nothing about what THIS endpoint does with
            # the field — live testing found a gateway serving gpt-6.1-sol
            # that accepts and ignores any value, including invalid ones. So
            # nothing is borrowed by name: the deployment's own evidence
            # (administrator override or verification) is passed in by the
            # caller as `endpoint_levels`; otherwise the model is Unknown.
            return ReasoningCapability(levels=None, adjustable=True, source="unknown")
        return ReasoningCapability(levels=(), adjustable=False, source="provider")

    if provider in EFFORT_PASSTHROUGH_PROVIDERS:
        levels = _openai_style_levels(model_id, provider)
        if levels == ():
            return ReasoningCapability(levels=(), adjustable=False, source="litellm")
    else:
        levels = _levels_from_litellm(model_id, provider)
        if provider == "anthropic" and levels:
            levels = _anthropic_levels(model_id, levels)
        elif provider == "google" and levels:
            levels = _gemini_levels(model_id, levels)
    if levels:
        return ReasoningCapability(levels=levels, adjustable=True, source="litellm")
    return ReasoningCapability(levels=None, adjustable=True, source="unknown")


def _local_model_key(model_id: str) -> str:
    """`local/<machine>/<key>` → `<key>` (keys may contain slashes)."""
    parts = model_id.split("/", 2)
    return parts[2] if len(parts) == 3 else model_id


def _is_gpt_oss(model_key: str) -> bool:
    return model_key.lower().startswith("gpt-oss")


def local_thinking_from_metadata(metadata: object) -> tuple[str, ...] | None:
    """Ollama's reported `think` values as a hashable tuple, or None.

    The connector stores `thinking_values` (from `/api/show`'s
    `thinking.values`, booleans rendered as "true"/"false") or, on older
    Ollama, a plain `thinking` boolean from the capability list. None means
    nothing was reported — Unknown, not Unsupported.
    """
    if isinstance(metadata, str):
        import json

        try:
            metadata = json.loads(metadata)
        except ValueError:
            return None
    if not isinstance(metadata, dict):
        return None
    values = metadata.get("thinking_values")
    if isinstance(values, list):
        out = []
        for v in values:
            if isinstance(v, bool):
                out.append("true" if v else "false")
            elif isinstance(v, str) and v.strip():
                out.append(v.strip().lower())
        return tuple(out)
    flag = metadata.get("thinking")
    if isinstance(flag, bool):
        # Older Ollama: a thinking-capable model takes on/off.
        return ("true", "false") if flag else ("false",)
    return None


def _ollama_levels(model_key: str, thinking: tuple[str, ...] | None) -> ReasoningCapability:
    """Levels Ollama's `think` can express for one model.

    Named levels are honoured exactly; a boolean switch is "off" (`none`)
    and "on" (reported as `high`, like every other on/off control).
    `values: [false]` is Ollama's way of saying the model cannot think.
    """
    if thinking is None:
        if _is_gpt_oss(model_key):
            # gpt-oss documents low/medium/high and cannot be switched off.
            return ReasoningCapability(
                levels=("low", "medium", "high"), adjustable=True, source="ollama"
            )
        return ReasoningCapability(levels=None, adjustable=False, source="unknown")
    named = tuple(level for level in LEVELS if level in thinking and level != "none")
    off = "false" in thinking
    if named:
        return ReasoningCapability(
            levels=(("none",) if off else ()) + named, adjustable=True, source="ollama"
        )
    if "true" in thinking:
        return ReasoningCapability(
            levels=("none", "high") if off else ("high",), adjustable=False, source="ollama"
        )
    return ReasoningCapability(levels=(), adjustable=False, source="ollama")


def _local_capability(
    model_key: str, adapter: str | None, thinking: tuple[str, ...] | None
) -> ReasoningCapability:
    """Local models: only what the connector actually reported.

    Ollama's `think` is a boolean for most models and a named level for a
    few (gpt-oss), as reported by `/api/show`. LM Studio and other
    OpenAI-compatible runtimes accept `reasoning_effort` only for models they
    recognise as reasoning models and report nothing, so they stay Unknown.
    """
    if adapter in _OLLAMA_ADAPTERS:
        return _ollama_levels(model_key, thinking)
    if adapter in _OPENAI_COMPAT_ADAPTERS:
        return ReasoningCapability(levels=None, adjustable=True, source="local")
    return ReasoningCapability(levels=None, adjustable=False, source="unknown")


def _bare(model_id: str, provider: str | None = None) -> str:
    """Strip a custom provider's `slug/` namespace from a model id.

    Built-in providers do not namespace: Groq's `openai/gpt-oss-120b` is the
    real model name and is left intact.
    """
    if provider in _REASONING_PROVIDERS:
        return model_id
    return model_id.split("/", 1)[-1] if "/" in model_id else model_id


def capability(
    model_id: str,
    *,
    provider: str | None = None,
    local_adapter: str | None = None,
    local_thinking: tuple[str, ...] | None = None,
) -> ReasoningCapability:
    """Capability for a model id, with the provider's own prefix stripped.

    Custom-provider models are namespaced (`slug/model`); the bare id is what
    LiteLLM's metadata is keyed on, so the namespace is removed before the
    lookup. A namespaced id that matches nothing stays Unknown.
    """
    if provider == _LOCAL_PROVIDER:
        # Local ids are `local/<machine>/<key>`; the key is what matters.
        return _capability_cached(
            _local_model_key(model_id), provider, local_adapter, local_thinking
        )
    return _capability_cached(_bare(model_id, provider), provider, local_adapter)


def supported_levels(
    model_id: str,
    *,
    provider: str | None = None,
    local_adapter: str | None = None,
    local_thinking: tuple[str, ...] | None = None,
) -> tuple[str, ...] | None:
    return capability(
        model_id, provider=provider, local_adapter=local_adapter,
        local_thinking=local_thinking,
    ).levels


def supports_effort(
    model_id: str,
    effort: str,
    *,
    provider: str | None = None,
    local_adapter: str | None = None,
    local_thinking: tuple[str, ...] | None = None,
) -> bool | None:
    """True / False / None (unknown) for one level on one model."""
    levels = supported_levels(
        model_id, provider=provider, local_adapter=local_adapter,
        local_thinking=local_thinking,
    )
    if levels is None:
        return None
    return effort in levels


# ── Translation ────────────────────────────────────────────────────────


def _anthropic_params(
    *, model_id: str, effort: str, max_tokens: int | None
) -> dict:
    meta = _litellm_meta(model_id, "anthropic")
    adaptive = meta.get("supports_adaptive_thinking") is True
    if adaptive:
        # Adaptive thinking takes an effort, not a budget. `none` disables it.
        if effort == "none":
            return {"thinking": {"type": "disabled"}}
        return {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }
    if effort == "none":
        return {"thinking": {"type": "disabled"}}
    budget = budget_for_effort(effort)
    if max_tokens is not None and budget >= max_tokens:
        raise _unsupported(
            f"reasoning_effort={effort!r} needs max_tokens greater than "
            f"{budget} for {model_id}; raise max_tokens or lower the effort."
        )
    return {"thinking": {"type": "enabled", "budget_tokens": budget}}


def thinking_enabled(params: dict) -> bool:
    """Whether translated Anthropic params turn thinking on."""
    thinking = params.get("thinking")
    return isinstance(thinking, dict) and thinking.get("type") in ("enabled", "adaptive")


def check_thinking_continuity(model_id: str, messages: list[dict] | None) -> None:
    """Refuse an Anthropic tool loop whose thinking blocks were not kept.

    With thinking on, Anthropic requires the assistant turn that made the
    pending tool call to start with its signed thinking block(s), returned
    unchanged. A client that did not send them back (an OpenAI-format client
    only has the reasoning text, not the signature) cannot satisfy that, and
    the only alternatives would be a provider 400 or silently running the
    turn without thinking. This says so up front instead.
    """
    last_assistant = next(
        (m for m in reversed(messages or []) if m.get("role") == "assistant"), None
    )
    if not last_assistant or not last_assistant.get("tool_calls"):
        return
    if last_assistant.get("thinking_blocks"):
        return
    raise _unsupported(
        f"{model_id} needs the signed thinking blocks of the previous assistant "
        "turn to continue this tool call with reasoning on, and the request did "
        "not include them. Send the assistant turn back unchanged (Anthropic "
        "Messages API clients do this automatically), or omit reasoning_effort "
        "for this turn."
    )


def _gemini_params(*, effort: str) -> dict:
    # LiteLLM maps `reasoning_effort` onto the right control for the family:
    # a thinking budget on 2.5, a thinking level on 3. Sending the effort
    # rather than a hand-built thinkingConfig keeps that mapping in one place.
    return {"reasoning_effort": effort}


# Per-call LiteLLM override that lets `reasoning_effort` through its local
# parameter validation. Scoped to one parameter on one call — the global
# `drop_params` stays off, so nothing else is ever silently removed.
_PASSTHROUGH = {"allowed_openai_params": ["reasoning_effort"]}


def _boolean_thinking_params(*, effort: str) -> dict:
    return {"thinking": {"type": "disabled" if effort == "none" else "enabled"}}


def _local_params(
    *, model_id: str, adapter: str | None, effort: str, cap: ReasoningCapability
) -> dict:
    if adapter in _OLLAMA_ADAPTERS:
        if effort == "none":
            return {"think": False}
        if cap.adjustable:
            # Named levels (gpt-oss): Ollama takes the level itself.
            return {"think": effort}
        if cap.levels is not None or effort == "high":
            # A boolean switch. Capability has already refused anything it
            # cannot express, so the only remaining level means "on".
            return {"think": True}
        # Nothing reported: Ollama may only offer on/off, and it silently
        # ignores a level name it does not know, so an intermediate level
        # cannot be sent faithfully. Only `none` and `high` are expressible.
        raise _unsupported(
            f"{model_id} did not report graded thinking levels; only "
            "reasoning_effort 'none' or 'high' can be sent to it."
        )
    if adapter in _OPENAI_COMPAT_ADAPTERS:
        # LiteLLM validates OpenAI params against the provider; the local
        # handler is a custom provider it knows nothing about, so the effort
        # is allowed explicitly for this one call (never globally).
        return {"reasoning_effort": effort, **_PASSTHROUGH}
    raise _unsupported(
        f"The local adapter for {model_id!r} does not support reasoning control."
    )


def provider_params(
    *,
    model_id: str,
    provider: str | None,
    effort: str,
    max_tokens: int | None = None,
    local_adapter: str | None = None,
    local_thinking: tuple[str, ...] | None = None,
    messages: list[dict] | None = None,
    endpoint_levels: tuple[str, ...] | None = None,
) -> dict:
    """The provider-specific parameters for one effort level.

    Raises `ReasoningError` when the model is known not to support the level.
    An Unknown model is translated on a best-effort basis with the effort
    preserved — the provider's own rejection is the authoritative answer.

    `endpoint_levels` is this deployment's own evidence (administrator
    override or verification) and takes precedence over generic metadata.
    """
    cap = capability(
        model_id,
        provider=provider,
        local_adapter=local_adapter,
        local_thinking=local_thinking,
    )
    if endpoint_levels is not None:
        cap = ReasoningCapability(levels=tuple(endpoint_levels), adjustable=True, source="endpoint")
    if cap.levels is not None and effort not in cap.levels:
        raise _unsupported(
            f"{model_id} does not support reasoning_effort={effort!r}. "
            + (
                "Supported: " + ", ".join(cap.levels) + "."
                if cap.levels
                else "This model does not support adjustable reasoning."
            )
        )

    if provider == _LOCAL_PROVIDER:
        return _local_params(model_id=model_id, adapter=local_adapter, effort=effort, cap=cap)
    if provider == "anthropic":
        params = _anthropic_params(model_id=model_id, effort=effort, max_tokens=max_tokens)
        if thinking_enabled(params):
            check_thinking_continuity(model_id, messages)
        return params
    if provider == "google":
        return _gemini_params(effort=effort)
    if provider in _BOOLEAN_THINKING_PROVIDERS:
        return _boolean_thinking_params(effort=effort)
    # OpenAI and every OpenAI-compatible provider (including custom ones).
    params = {"reasoning_effort": effort}
    if cap.levels is None and not _litellm_meta(_bare(model_id, provider), provider):
        # Unknown to LiteLLM: its validator would refuse the parameter before
        # the provider ever saw it. Unknown is not Unsupported, so let the
        # provider decide; its rejection becomes a 400, never a silent drop.
        # Models LiteLLM *does* know keep its validation untouched.
        params.update(_PASSTHROUGH)
    return params


def apply(
    kwargs: dict,
    *,
    model_id: str,
    provider: str | None,
    effort: str | None,
    max_tokens: int | None = None,
    local_adapter: str | None = None,
    local_thinking: tuple[str, ...] | None = None,
) -> dict:
    """Merge the translated reasoning parameters into a completion payload.

    A no-op when `effort` is None, so requests that never mention reasoning
    are byte-for-byte what they were before this module existed.
    """
    if effort is None:
        return kwargs
    params = provider_params(
        model_id=model_id,
        provider=provider,
        effort=effort,
        max_tokens=max_tokens,
        local_adapter=local_adapter,
        local_thinking=local_thinking,
    )
    return {**kwargs, **params}


def describe(
    *, requested: str | None, effective: str | None, model_id: str
) -> dict[str, str]:
    """Non-secret diagnostics for headers and the request log."""
    out: dict[str, str] = {}
    if requested is not None:
        out["x-geek-reasoning-requested"] = requested
    if effective is not None:
        out["x-geek-reasoning-effective"] = effective
    if requested is not None and effective is not None and requested != effective:
        out["x-geek-reasoning-downgraded"] = "true"
    return out


# ── Catalog advertising ────────────────────────────────────────────────


def catalog_levels(
    model_id: str, provider: str | None
) -> tuple[tuple[str, ...] | None, bool]:
    """What the model inventory should publish for a built-in model.

    Returns `(levels, blocked)`:

      * `levels` — the confirmed supported levels, an empty tuple when the
        model is confirmed not to support effort control, or None when it is
        unknown.
      * `blocked` — True when the effort selector must not offer anything:
        the model is known to LiteLLM and has no reasoning control, or it
        belongs to a provider that has no reasoning interface at all.

    A model LiteLLM has never heard of on a reasoning-capable provider stays
    Unknown rather than being written off: that is what lets a newer model
    reach the router before the cost map is updated.
    """
    cap = capability(model_id, provider=provider)
    if cap.levels is not None:
        return cap.levels, False
    if _litellm_meta(_bare(model_id, provider), provider):
        return None, True
    if provider in _REASONING_PROVIDERS:
        return None, False
    return None, True
