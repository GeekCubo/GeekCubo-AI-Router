"""Model Intelligence — metadata sources, normalization and price precedence.

Sources are INFORMATION, not inference providers and not authorities over the
operator. Rules enforced here:

* Every catalog is normalized to one shape keyed by an exact
  `provider/model` identity. There is no fuzzy matching: two models whose
  names merely look alike are never merged, and an aggregator's
  `apixo/gpt-4o` is never priced from `openai/gpt-4o`.
* Units are converted explicitly per source:
    LiteLLM    — USD per token        → x 1,000,000      = USD / 1M tokens
    models.dev — USD per 1M tokens    → unchanged
    Portkey    — US CENTS per token   → x 1,000,000 / 100 = USD / 1M tokens
* Price states are separate: "priced", "free" (a source that explicitly
  lists $0 for both input and output) and "unknown". Portkey's zeros are
  ambiguous (its template uses 0 for "not set"), so Portkey never yields
  "free"; a $0/$0 Portkey entry is treated as unknown.
* Capabilities (tools, vision, JSON mode, JSON Schema / structured outputs)
  are resolved field by field with source attribution. Only an explicit
  true/false from a matched model becomes supported/unsupported; anything
  else stays unknown. A source that reports structured outputs never
  grants JSON mode, and vice versa. Administrator overrides always win.
* Inference never depends on this module. All sources offline still serves
  every configured model.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

BUILTIN_SOURCES = (
    {
        "key": "litellm",
        "name": "LiteLLM (bundled)",
        "kind": "litellm",
        "url": None,
        "priority": 10,
        "description": "Ships with the installed LiteLLM version. Offline, no network.",
    },
    {
        "key": "models-dev",
        "name": "Models.dev",
        "kind": "models_dev",
        "url": "https://models.dev/api.json",
        "priority": 20,
        "description": "Open catalog of providers and models (prices, limits, capabilities).",
    },
    {
        "key": "portkey",
        "name": "Portkey Models",
        "kind": "portkey",
        "url": "https://configs.portkey.ai/pricing/{provider}.json",
        "priority": 30,
        "description": "Per-provider pricing. Values are cents per token, converted here.",
    },
)

PRICE_FIELDS = ("input", "output", "cache_read", "cache_write")


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _entry(
    *,
    prices: dict[str, float | None],
    context: int | None = None,
    tools: bool | None = None,
    vision: bool | None = None,
    json_mode: bool | None = None,
    json_schema: bool | None = None,
    zero_means_free: bool,
) -> dict[str, Any]:
    p = {k: prices.get(k) for k in PRICE_FIELDS}
    if p["input"] is None and p["output"] is None:
        state = "unknown"
    elif (p["input"] or 0) == 0 and (p["output"] or 0) == 0:
        state = "free" if zero_means_free else "unknown"
        if not zero_means_free:
            p = {k: None for k in PRICE_FIELDS}
    else:
        state = "priced"
    return {
        "price_state": state,
        "input_per_million": p["input"],
        "output_per_million": p["output"],
        "cache_read_per_million": p["cache_read"],
        "cache_write_per_million": p["cache_write"],
        "context": context,
        "tools": tools,
        "vision": vision,
        "json_mode": json_mode,
        "json_schema": json_schema,
    }


# ── parsers (pure; each returns {"provider/model": entry}) ─────────────────


def parse_litellm(model_cost: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for raw_id, meta in (model_cost or {}).items():
        if not isinstance(meta, dict) or raw_id == "sample_spec":
            continue
        provider = str(meta.get("litellm_provider") or "").strip().lower()
        if not provider:
            continue
        bare = raw_id.split("/", 1)[1] if raw_id.lower().startswith(provider + "/") else raw_id
        key = f"{provider}/{bare}".lower()

        def per_m(field: str, _meta=meta) -> float | None:
            v = _num(_meta.get(field))
            return None if v is None else v * 1_000_000

        out[key] = _entry(
            prices={
                "input": per_m("input_cost_per_token"),
                "output": per_m("output_cost_per_token"),
                "cache_read": per_m("cache_read_input_token_cost"),
                "cache_write": per_m("cache_creation_input_token_cost"),
            },
            context=int(meta["max_input_tokens"]) if isinstance(meta.get("max_input_tokens"), int) else None,
            tools=meta.get("supports_function_calling") if isinstance(meta.get("supports_function_calling"), bool) else None,
            vision=meta.get("supports_vision") if isinstance(meta.get("supports_vision"), bool) else None,
            json_mode=meta.get("supports_json_mode") if isinstance(meta.get("supports_json_mode"), bool) else None,
            json_schema=(
                meta.get("supports_response_schema")
                if isinstance(meta.get("supports_response_schema"), bool)
                else meta.get("supports_json_schema")
                if isinstance(meta.get("supports_json_schema"), bool)
                else None
            ),
            # LiteLLM leaves unknown prices as 0 in places; never call it free.
            zero_means_free=False,
        )
    return out


def parse_models_dev(data: Any) -> dict[str, dict]:
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object of providers")
    out: dict[str, dict] = {}
    for provider_id, provider in data.items():
        if not isinstance(provider, dict):
            continue
        models = provider.get("models")
        if not isinstance(models, dict):
            continue
        pid = str(provider.get("id") or provider_id).strip().lower()
        for model_id, m in models.items():
            if not isinstance(m, dict):
                continue
            cost = m.get("cost") if isinstance(m.get("cost"), dict) else {}
            limit = m.get("limit") if isinstance(m.get("limit"), dict) else {}
            modalities = m.get("modalities") if isinstance(m.get("modalities"), dict) else {}
            inputs = modalities.get("input") if isinstance(modalities.get("input"), list) else None
            ctx = limit.get("context")
            out[f"{pid}/{m.get('id') or model_id}".lower()] = _entry(
                prices={k: _num(cost.get(k)) for k in PRICE_FIELDS},
                context=int(ctx) if isinstance(ctx, (int, float)) and ctx > 0 else None,
                tools=m.get("tool_call") if isinstance(m.get("tool_call"), bool) else None,
                vision=("image" in inputs) if inputs is not None else None,
                json_mode=m.get("json_mode") if isinstance(m.get("json_mode"), bool) else None,
                json_schema=m.get("structured_output") if isinstance(m.get("structured_output"), bool) else None,
                # models.dev publishes explicit costs; a stated 0/0 is free.
                zero_means_free=bool(cost),
            )
    return out


PORTKEY_CENTS_PER_TOKEN_TO_USD_PER_MILLION = 1_000_000 / 100  # = 10,000


def parse_portkey(provider: str, data: Any) -> dict[str, dict]:
    """Portkey per-provider pricing file. Prices are US CENTS per token."""
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object of models")
    pid = provider.strip().lower()
    out: dict[str, dict] = {}
    for model_id, cfg in data.items():
        # "default" is a template with every price at 0. Using it would make
        # every unknown model look free.
        if model_id == "default" or not isinstance(cfg, dict):
            continue
        pricing = cfg.get("pricing_config") if isinstance(cfg.get("pricing_config"), dict) else {}
        payg = pricing.get("pay_as_you_go") if isinstance(pricing.get("pay_as_you_go"), dict) else {}

        def rate(field: str, _payg=payg) -> float | None:
            node = _payg.get(field)
            v = _num(node.get("price")) if isinstance(node, dict) else None
            return None if v is None else v * PORTKEY_CENTS_PER_TOKEN_TO_USD_PER_MILLION

        out[f"{pid}/{model_id}".lower()] = _entry(
            prices={
                "input": rate("request_token"),
                "output": rate("response_token"),
                "cache_read": rate("cache_read_input_token"),
                "cache_write": rate("cache_write_input_token"),
            },
            zero_means_free=False,
        )
    return out


# ── resolution ────────────────────────────────────────────────────────────


def resolve(
    model_key: str,
    *,
    configured: dict[str, Any] | None,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve one model's effective metadata with field-level fallback.

    `configured` is the operator's own setting (custom model row), which
    always wins. `sources` are enabled sources in priority order, each
    `{"key", "name", "entries", "stale"}`. Each field is taken from the first
    source that has a non-null value and is attributed to it, so a missing
    field in the primary source falls through to the next one.
    """
    key = model_key.strip().lower()
    result: dict[str, Any] = {"model": model_key, "fields": {}, "per_source": []}

    for src in sources:
        entry = (src.get("entries") or {}).get(key)
        result["per_source"].append({
            "source": src["key"],
            "name": src["name"],
            "stale": bool(src.get("stale")),
            "found": entry is not None,
            "entry": entry,
        })

    def pick(field: str):
        if configured and configured.get(field) not in (None, 0, 0.0):
            return configured[field], "configured", False
        for src in sources:
            entry = (src.get("entries") or {}).get(key)
            if entry is None:
                continue
            if field in ("input_per_million", "output_per_million") and entry.get("price_state") == "unknown":
                continue
            if field == "json_schema" and "json_schema" not in entry:
                value = entry.get("json")
            else:
                value = entry.get(field)
            if value is not None:
                return value, src["key"], bool(src.get("stale"))
        return None, None, False

    for field in (
        "input_per_million", "output_per_million",
        "cache_read_per_million", "cache_write_per_million", "context",
        "tools", "vision", "json_mode", "json_schema",
    ):
        value, origin, stale = pick(field)
        result["fields"][field] = {"value": value, "source": origin, "stale": stale}

    inp = result["fields"]["input_per_million"]
    out = result["fields"]["output_per_million"]
    if inp["source"] == "configured" or out["source"] == "configured":
        state = "configured"
    elif inp["value"] is None and out["value"] is None:
        state = "unknown"
    elif (inp["value"] or 0) == 0 and (out["value"] or 0) == 0:
        state = "free"
    elif inp["stale"] or out["stale"]:
        state = "cached"
    else:
        state = "catalog_estimate"
    result["price_state"] = state
    return result


def is_stale(last_success_at: datetime | None, interval_hours: int) -> bool:
    if last_success_at is None:
        return True
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - last_success_at).total_seconds() / 3600
    return age_h > max(1, interval_hours) * 2


def parse_json_bytes(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"the source did not return valid JSON ({type(exc).__name__})") from exc
