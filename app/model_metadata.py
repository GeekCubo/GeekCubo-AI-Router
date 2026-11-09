"""Trusted metadata resolution for registered custom-provider models.

This module connects the existing Model Intelligence catalogs to the models an
operator registers on a custom provider. It deliberately stays conservative:

* Matching is exact-first. A bare model id is accepted only when it identifies
  one catalog entry unambiguously. Loose/fuzzy matching is never used, and an
  aggregator prefix is never blindly stripped into a vendor price.
* Reference (original vendor) rates are estimates. Confirmed custom-provider
  rates live in separate columns and are never overwritten by catalog data.
* Capabilities are tri-state (supported / unsupported / unknown) with source
  attribution. Unknown is not the same as unsupported.
* Operator overrides win and are recorded, so a later refresh cannot silently
  undo them.

All functions are deterministic and network-free. Callers pass the already
cached Model Intelligence sources from the database.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from app import model_intelligence as mi

CAPABILITY_FIELDS = {
    "tools": ("supports_tools", "tools"),
    "vision": ("supports_vision", "vision"),
    "json_mode": ("supports_json_mode", "json_mode"),
    "json_schema": ("supports_json_schema", "json_schema"),
}
CAPABILITY_STATES = {"supported", "unsupported", "unknown"}


def load_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_metadata(meta: dict[str, Any]) -> str:
    return json.dumps(meta, separators=(",", ":"), sort_keys=True)


def _manual(meta: dict[str, Any]) -> dict[str, Any]:
    manual = meta.get("manual")
    return manual if isinstance(manual, dict) else {}


def _manual_caps(meta: dict[str, Any]) -> dict[str, Any]:
    caps = _manual(meta).get("capabilities")
    return caps if isinstance(caps, dict) else {}


def custom_pricing_configured(model) -> bool:
    """Whether the operator explicitly supplied a custom provider rate.

    Legacy rows predate the manual flag; a positive stored rate is treated as
    an explicit custom price. A stored zero with no flag stays unknown, never
    free.
    """
    meta = load_metadata(getattr(model, "metadata_json", None))
    if _manual(meta).get("pricing") is True:
        return True
    return bool(
        (getattr(model, "input_cost_per_token", 0) or 0) > 0
        or (getattr(model, "output_cost_per_token", 0) or 0) > 0
    )


def effective_custom_price(model) -> tuple[float | None, float | None, str]:
    """Return the confirmed custom rates used for spend accounting."""
    if not custom_pricing_configured(model):
        return None, None, "unknown"
    return (
        float(getattr(model, "input_cost_per_token", 0) or 0),
        float(getattr(model, "output_cost_per_token", 0) or 0),
        "custom",
    )


def effective_routing_price(model) -> tuple[float, float, str]:
    """Rates used for Auto comparisons.

    A confirmed custom rate wins. Otherwise the reference estimate may be used
    for comparison, but the returned source makes clear it is not billing.
    """
    inp, out, state = effective_custom_price(model)
    if state == "custom":
        return inp or 0.0, out or 0.0, "custom"
    ref_in = getattr(model, "reference_input_cost_per_token", None)
    ref_out = getattr(model, "reference_output_cost_per_token", None)
    if ref_in is not None or ref_out is not None:
        return float(ref_in or 0.0), float(ref_out or 0.0), "reference"
    return 0.0, 0.0, "unknown"


def _catalog_keys(sources: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for src in sources:
        entries = src.get("entries") or {}
        if isinstance(entries, dict):
            keys.update(str(k).lower() for k in entries)
    return keys


def match_model(
    provider_slug: str,
    model_id: str,
    *,
    alias: str | None,
    available_keys: set[str],
) -> dict[str, Any]:
    """Resolve one model identity against available catalog keys.

    Confidence values:
      exact_provider — the provider slug is itself the catalog provider
      alias          — an administrator-confirmed mapping
      vendor_prefix  — the stored id is already a full vendor/model key
      unique_bare    — exactly one catalog entry carries this bare id
      ambiguous      — several entries share the bare id; no auto-merge
      none           — no catalog entry
    """
    slug = (provider_slug or "").strip().lower()
    mid = (model_id or "").strip().lower()
    exact = f"{slug}/{mid}"
    if exact in available_keys:
        return {"key": exact, "confidence": "exact_provider", "candidates": [exact]}
    if alias:
        alias_key = alias.strip().lower()
        if alias_key in available_keys:
            return {"key": alias_key, "confidence": "alias", "candidates": [alias_key]}

    if "/" in mid and mid in available_keys:
        return {"key": mid, "confidence": "vendor_prefix", "candidates": [mid]}

    bare = mid.split("/", 1)[1] if mid.count("/") == 1 and mid.split("/", 1)[0] in {
        "openai", "anthropic", "google", "gemini", "xai", "deepseek", "mistral",
        "groq", "together", "fireworks", "cohere", "perplexity",
    } else mid
    candidates = sorted(
        key for key in available_keys if key.split("/", 1)[-1] == bare
    )
    if len(candidates) == 1:
        return {"key": candidates[0], "confidence": "unique_bare", "candidates": candidates}
    if len(candidates) > 1:
        # Never auto-picked. Ordering only decides which keys the picker can
        # offer: a plain alphabetical cut at 25 hid the vendor's own entry
        # (zai/glm-5.3, moonshotai/kimi-k3) behind dozens of resellers.
        return {
            "key": None,
            "confidence": "ambiguous",
            "candidates": _order_candidates(candidates, bare)[:MAX_CANDIDATES],
            "candidate_total": len(candidates),
        }
    return {"key": None, "confidence": "none", "candidates": []}


MAX_CANDIDATES = 25

# First-party catalog namespaces for a model family, keyed by the id prefix.
# Used ONLY to order an ambiguous candidate list for display; it never
# selects a key and never makes a match "resolved".
_FAMILY_VENDORS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gpt-", ("openai",)),
    ("o1", ("openai",)), ("o3", ("openai",)), ("o4", ("openai",)),
    ("claude-", ("anthropic",)),
    ("gemini-", ("google", "gemini", "vertex_ai")),
    ("gemma-", ("google",)),
    ("grok-", ("xai",)),
    ("deepseek-", ("deepseek",)),
    ("glm-", ("zai", "zhipuai")),
    ("kimi-", ("moonshotai", "moonshot")),
    ("mimo-", ("xiaomi",)),
    ("qwen", ("alibaba", "qwen")),
    ("mistral-", ("mistral",)),
)


def _order_candidates(candidates: list[str], bare: str) -> list[str]:
    vendors: tuple[str, ...] = ()
    for prefix, names in _FAMILY_VENDORS:
        if bare.startswith(prefix):
            vendors = names
            break

    def rank(key: str) -> tuple[int, str]:
        ns = key.split("/", 1)[0]
        return (vendors.index(ns) if ns in vendors else len(vendors), key)

    return sorted(candidates, key=rank)


def match_status(confidence: str, fields: dict[str, Any]) -> str:
    """Map a match to a coarse resolution status for the dashboard.

    resolved — a catalog key matched and the core fields (context, input and
               output reference prices, tool support) are all known
    partial  — matched, but at least one core field is unknown
    ambiguous— several catalog entries share the id; a pick is required
    unmatched— no catalog entry
    """
    if confidence in ("ambiguous",):
        return "ambiguous"
    if confidence == "none":
        return "unmatched"
    missing = (
        fields.get("context") is None
        or fields.get("input_per_million") is None
        or fields.get("output_per_million") is None
        or fields.get("tools") is None
    )
    return "partial" if missing else "resolved"


def preview_model(
    provider_slug: str,
    model_id: str,
    sources: list[dict[str, Any]],
    *,
    alias: str | None = None,
) -> dict[str, Any]:
    """Resolve a model id without persisting anything.

    Used by model discovery to show, before registration, whether each
    fetched id maps to a catalog entry and what metadata it would inherit.
    """
    match = match_model(
        provider_slug,
        model_id,
        alias=alias,
        available_keys=_catalog_keys(sources),
    )
    key = match.get("key")
    resolved = _pick_resolved(key, sources) if key else None
    fields = resolved["fields"] if resolved else {}
    return {
        "catalog_key": key,
        "confidence": match["confidence"],
        "candidates": match["candidates"],
        "candidate_total": match.get("candidate_total", len(match["candidates"])),
        "status": match_status(match["confidence"], fields),
        "fields": fields,
        "sources": resolved["sources"] if resolved else {},
        "stale": bool(resolved["stale"]) if resolved else False,
        "price_state": resolved["price_state"] if resolved else "unknown",
    }



def _pick_resolved(key: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    field_sources: dict[str, str] = {}
    stale = False
    for field in (
        "input_per_million",
        "output_per_million",
        "cache_read_per_million",
        "cache_write_per_million",
        "context",
        "tools",
        "vision",
        "json_mode",
        "json_schema",
    ):
        for src in sources:
            entry = (src.get("entries") or {}).get(key)
            if not isinstance(entry, dict):
                continue
            if field in ("input_per_million", "output_per_million") and entry.get(
                "price_state"
            ) == "unknown":
                continue
            # Catalog entries written before JSON mode and JSON Schema were
            # separate used a single "json" key sourced from structured-output
            # flags. It is JSON Schema evidence, never JSON-mode evidence.
            if field == "json_schema" and "json_schema" not in entry:
                value = entry.get("json")
            else:
                value = entry.get(field)
            if value is not None:
                fields[field] = value
                field_sources[field] = src["key"]
                stale = stale or bool(src.get("stale"))
                break
        else:
            fields[field] = None
            field_sources[field] = "unknown"

    price_source = field_sources.get("input_per_million")
    if price_source == "unknown":
        price_source = field_sources.get("output_per_million")
    price_state = "unknown"
    if price_source and price_source != "unknown":
        price_state = "cached" if stale else "reference"
    return {
        "fields": fields,
        "sources": field_sources,
        "stale": stale,
        "price_state": price_state,
        "price_source": None if price_source == "unknown" else price_source,
    }


PROVIDER_REPORT_SOURCE = "provider_models_endpoint"


def provider_report(meta: dict[str, Any]) -> dict[str, Any]:
    report = meta.get("provider_reported")
    return report if isinstance(report, dict) else {}


def record_provider_report(model, entry: dict[str, Any]) -> bool:
    """Store the limits the provider's own `GET /models` reported for this id.

    This is evidence about THIS deployment (the operator's provider), so it
    ranks above a generic catalog entry for context and below an explicit
    administrator value. Only positive integers are kept; nothing is
    inferred. Returns True when the stored report changed.
    """
    meta = load_metadata(getattr(model, "metadata_json", None))
    report: dict[str, Any] = {}
    for key in ("context_window", "max_output_tokens"):
        value = entry.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            report[key] = value
    if not report:
        return False
    previous = provider_report(meta)
    if all(previous.get(k) == v for k, v in report.items()) and set(previous) - {"source"} == set(report):
        return False
    meta["provider_reported"] = {**report, "source": PROVIDER_REPORT_SOURCE}
    model.metadata_json = dump_metadata(meta)
    return True


def _apply_context(model, meta: dict[str, Any], catalog_context: Any, catalog_source: str | None, stale: bool) -> None:
    """Context precedence: administrator > provider-reported > catalog > unknown."""
    if _manual(meta).get("context"):
        return
    reported = provider_report(meta).get("context_window")
    if isinstance(reported, int) and reported > 0:
        model.context_length = reported
        meta["context"] = {"source": PROVIDER_REPORT_SOURCE, "stale": False, "manual": False}
        return
    if catalog_context is not None:
        model.context_length = int(catalog_context)
        meta["context"] = {"source": catalog_source, "stale": stale, "manual": False}
        return
    model.context_length = None
    meta["context"] = {"source": None, "stale": False, "manual": False}


def resolve_one(
    provider_slug: str,
    model,
    sources: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve and apply metadata for one ORM model (no commit)."""
    meta = load_metadata(getattr(model, "metadata_json", None))
    manual = _manual(meta)
    alias = manual.get("alias")
    match = match_model(
        provider_slug,
        getattr(model, "model_id", ""),
        alias=alias if isinstance(alias, str) else None,
        available_keys=_catalog_keys(sources),
    )
    matched_key = match.get("key")
    resolved = _pick_resolved(matched_key, sources) if matched_key else None

    meta["identity"] = {
        "catalog_key": matched_key,
        "confidence": match["confidence"],
        "candidates": match["candidates"],
        "candidate_total": match.get("candidate_total", len(match["candidates"])),
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }

    if resolved is None:
        if not manual.get("reference"):
            model.reference_input_cost_per_token = None
            model.reference_output_cost_per_token = None
            model.reference_cache_read_cost_per_token = None
            model.reference_cache_write_cost_per_token = None
            model.reference_source = None
        _apply_context(model, meta, None, None, False)
        for cap, (flag, _field) in CAPABILITY_FIELDS.items():
            if not _manual_caps(meta).get(cap):
                setattr(model, flag, False)
                _set_cap_state(meta, cap, "unknown", None, stale=False)
        if not manual.get("reference"):
            meta["reference"] = {
                "trust": "unknown",
                "price_state": "unknown",
                "source": None,
                "stale": False,
            }
        model.metadata_json = dump_metadata(meta)
        return meta, None

    fields = resolved["fields"]
    field_sources = resolved["sources"]
    if manual.get("reference"):
        reference = meta.get("reference") if isinstance(meta.get("reference"), dict) else {}
    else:
        model.reference_input_cost_per_token = _per_token(fields.get("input_per_million"))
        model.reference_output_cost_per_token = _per_token(fields.get("output_per_million"))
        model.reference_cache_read_cost_per_token = _per_token(fields.get("cache_read_per_million"))
        model.reference_cache_write_cost_per_token = _per_token(fields.get("cache_write_per_million"))
        model.reference_source = matched_key
        reference = {
            "trust": (
                "provider_catalog"
                if matched_key.startswith(f"{provider_slug.strip().lower()}/")
                else "reference_estimate"
            ),
            "price_state": resolved["price_state"],
            "source": resolved["price_source"],
            "source_key": matched_key,
            "stale": resolved["stale"],
            "fields": {
                "input_per_million": fields.get("input_per_million"),
                "output_per_million": fields.get("output_per_million"),
                "cache_read_per_million": fields.get("cache_read_per_million"),
                "cache_write_per_million": fields.get("cache_write_per_million"),
            },
        }
    meta["reference"] = reference

    _apply_context(
        model, meta, fields.get("context"), field_sources.get("context"), resolved["stale"]
    )

    for cap, (flag, field) in CAPABILITY_FIELDS.items():
        if _manual_caps(meta).get(cap):
            continue
        value = fields.get(field)
        if value is True:
            state = "supported"
        elif value is False:
            state = "unsupported"
        else:
            state = "unknown"
        setattr(model, flag, state == "supported")
        _set_cap_state(
            meta, cap, state, field_sources.get(field), stale=resolved["stale"]
        )

    model.metadata_json = dump_metadata(meta)
    return meta, resolved


def _set_cap_state(
    meta: dict[str, Any],
    capability: str,
    state: str,
    source: str | None,
    *,
    stale: bool,
) -> None:
    caps = meta.get("capabilities")
    if not isinstance(caps, dict):
        caps = {}
    caps[capability] = {
        "state": state if state in CAPABILITY_STATES else "unknown",
        "source": source if source and source != "unknown" else None,
        "stale": bool(stale),
        "override": bool(_manual_caps(meta).get(capability)),
    }
    meta["capabilities"] = caps


_STATE_TO_TRI: dict[str, bool | None] = {
    "supported": True,
    "unsupported": False,
    "unknown": None,
}


def capability_state(model, capability: str) -> str:
    """Tri-state view of one capability for a registered model row.

    Precedence: the persisted per-capability metadata state (operator
    override, source-resolved value, or explicit unknown) wins; a bare True
    flag — an operator checkbox saved before tri-state metadata existed or a
    row not yet resolved — counts as Supported. Anything else is Unknown;
    a False flag alone is never read as Unsupported because it may simply
    mean "not resolved yet". The next metadata refresh rewrites the state
    from the catalog sources.
    """
    if capability not in CAPABILITY_FIELDS:
        raise ValueError(f"unknown capability '{capability}'")
    meta = load_metadata(getattr(model, "metadata_json", None))
    caps = meta.get("capabilities")
    entry = caps.get(capability) if isinstance(caps, dict) else None
    state = entry.get("state") if isinstance(entry, dict) else None
    if state in CAPABILITY_STATES:
        return state
    if getattr(model, CAPABILITY_FIELDS[capability][0], False) is True:
        return "supported"
    return "unknown"


def catalog_support(model, capability: str) -> bool | None:
    """Capability as a catalog tri-state: True, False, or None (Unknown)."""
    return _STATE_TO_TRI[capability_state(model, capability)]


def _per_token(per_million: Any) -> float | None:
    if per_million is None:
        return None
    try:
        return float(per_million) / 1_000_000
    except (TypeError, ValueError):
        return None


def apply_capability_override(model, capability: str, state: str) -> None:
    if capability not in CAPABILITY_FIELDS:
        raise ValueError(f"unknown capability '{capability}'")
    if state not in CAPABILITY_STATES:
        raise ValueError("capability state must be supported, unsupported or unknown")
    meta = load_metadata(getattr(model, "metadata_json", None))
    manual = meta.setdefault("manual", {})
    caps_manual = manual.setdefault("capabilities", {})
    # Even "unknown" is an explicit administrator decision: it must not be
    # silently replaced by a catalog value on the next refresh.
    caps_manual[capability] = state
    flag = CAPABILITY_FIELDS[capability][0]
    setattr(model, flag, state == "supported")
    _set_cap_state(meta, capability, state, "administrator_override", stale=False)
    model.metadata_json = dump_metadata(meta)


def clear_capability_override(model, capability: str) -> None:
    if capability not in CAPABILITY_FIELDS:
        raise ValueError(f"unknown capability '{capability}'")
    meta = load_metadata(getattr(model, "metadata_json", None))
    caps_manual = _manual(meta).get("capabilities")
    if isinstance(caps_manual, dict):
        caps_manual.pop(capability, None)
    _set_cap_state(meta, capability, "unknown", None, stale=False)
    setattr(model, CAPABILITY_FIELDS[capability][0], False)
    model.metadata_json = dump_metadata(meta)


def apply_custom_price(
    model,
    *,
    input_per_million: float | None,
    output_per_million: float | None,
    cache_read_per_million: float | None = None,
    cache_write_per_million: float | None = None,
    manual: bool = True,
) -> None:
    """Set confirmed custom-provider rates without touching reference rates."""
    meta = load_metadata(getattr(model, "metadata_json", None))
    manual_flags = meta.setdefault("manual", {})
    if manual:
        manual_flags["pricing"] = True
    custom = meta.setdefault("custom", {})
    if input_per_million is None:
        input_per_million = float(model.input_cost_per_token or 0.0) * 1_000_000
    if output_per_million is None:
        output_per_million = float(model.output_cost_per_token or 0.0) * 1_000_000
    if cache_read_per_million is None:
        cache_read_per_million = custom.get("cache_read_per_million")
    if cache_write_per_million is None:
        cache_write_per_million = custom.get("cache_write_per_million")
    model.input_cost_per_token = float(input_per_million) / 1_000_000
    model.output_cost_per_token = float(output_per_million) / 1_000_000
    custom.update({
        "input_per_million": float(input_per_million or 0.0),
        "output_per_million": float(output_per_million or 0.0),
        "cache_read_per_million": cache_read_per_million,
        "cache_write_per_million": cache_write_per_million,
        "source": "administrator",
    })
    model.metadata_json = dump_metadata(meta)


def set_reference_price(
    model,
    *,
    input_per_million: float | None,
    output_per_million: float | None,
    cache_read_per_million: float | None = None,
    cache_write_per_million: float | None = None,
) -> None:
    meta = load_metadata(getattr(model, "metadata_json", None))
    meta.setdefault("manual", {})["reference"] = True
    if input_per_million is None:
        input_per_million = None if model.reference_input_cost_per_token is None else model.reference_input_cost_per_token * 1_000_000
    if output_per_million is None:
        output_per_million = None if model.reference_output_cost_per_token is None else model.reference_output_cost_per_token * 1_000_000
    if cache_read_per_million is None:
        cache_read_per_million = None if model.reference_cache_read_cost_per_token is None else model.reference_cache_read_cost_per_token * 1_000_000
    if cache_write_per_million is None:
        cache_write_per_million = None if model.reference_cache_write_cost_per_token is None else model.reference_cache_write_cost_per_token * 1_000_000
    model.reference_input_cost_per_token = _per_token(input_per_million)
    model.reference_output_cost_per_token = _per_token(output_per_million)
    model.reference_cache_read_cost_per_token = _per_token(cache_read_per_million)
    model.reference_cache_write_cost_per_token = _per_token(cache_write_per_million)
    model.reference_source = "administrator"
    meta["reference"] = {
        "trust": "reference_estimate",
        "price_state": "configured",
        "source": "administrator",
        "source_key": None,
        "stale": False,
        "fields": {
            "input_per_million": input_per_million,
            "output_per_million": output_per_million,
            "cache_read_per_million": cache_read_per_million,
            "cache_write_per_million": cache_write_per_million,
        },
    }
    model.metadata_json = dump_metadata(meta)


def set_alias(model, catalog_key: str | None) -> None:
    meta = load_metadata(getattr(model, "metadata_json", None))
    manual = meta.setdefault("manual", {})
    if catalog_key:
        manual["alias"] = catalog_key.strip().lower()
    else:
        manual.pop("alias", None)
    model.metadata_json = dump_metadata(meta)


def reset_context_override(model) -> None:
    meta = load_metadata(getattr(model, "metadata_json", None))
    manual = meta.setdefault("manual", {})
    manual.pop("context", None)
    meta.pop("context", None)
    model.metadata_json = dump_metadata(meta)


def mark_context_manual(model) -> None:
    meta = load_metadata(getattr(model, "metadata_json", None))
    meta.setdefault("manual", {})["context"] = True
    meta["context"] = {"source": "administrator", "stale": False, "manual": True}
    model.metadata_json = dump_metadata(meta)


def mark_capabilities_manual(model, states: dict[str, str]) -> None:
    for capability, state in states.items():
        apply_capability_override(model, capability, state)


async def load_enabled_sources(db) -> list[dict[str, Any]]:
    """Enabled Model Intelligence sources, priority-ordered, cached entries."""
    from sqlalchemy import select

    from app.seed import DEFAULT_WORKSPACE_ID
    from packages.db.models.metadata_source import MetadataSource

    rows = list(
        (
            await db.execute(
                select(MetadataSource)
                .where(
                    MetadataSource.workspace_id == DEFAULT_WORKSPACE_ID,
                    MetadataSource.is_deleted == 0,
                )
                .order_by(MetadataSource.priority, MetadataSource.name)
            )
        ).scalars().all()
    )
    out = []
    has_litellm = False
    for row in rows:
        if row.key == "litellm":
            has_litellm = True
        if not row.is_enabled:
            continue
        out.append({
            "key": row.key,
            "name": row.name,
            "entries": row.cache or {},
            "stale": mi.is_stale(row.last_success_at, row.sync_interval_hours),
        })
    if not has_litellm:
        # First-run convenience: the bundled LiteLLM catalog needs no network
        # and is enabled by default. Once a source row exists, its enabled flag
        # (and cache) is authoritative.
        try:
            from litellm import model_cost

            entries = mi.parse_litellm(model_cost)
            if entries:
                out.insert(0, {
                    "key": "litellm",
                    "name": "LiteLLM bundled catalog",
                    "entries": entries,
                    "stale": False,
                })
        except Exception:
            pass
    return out


async def sync_provider_models(
    db, provider_id: str, *, provider_slug: str, models: Iterable
) -> None:
    sources = await load_enabled_sources(db)
    if not sources:
        return
    for model in models:
        resolve_one(provider_slug, model, sources)


async def sync_all_registered(db) -> int:
    """Re-resolve every registered model after catalog changes.

    Manual overrides are preserved. Returns the number of models touched.
    """
    from sqlalchemy import select

    from packages.db.models.custom_provider import CustomProvider, CustomProviderModel

    sources = await load_enabled_sources(db)
    if not sources:
        return 0
    providers = {
        row.id: row.slug
        for row in (
            await db.execute(select(CustomProvider))
        ).scalars().all()
    }
    models = list(
        (
            await db.execute(select(CustomProviderModel))
        ).scalars().all()
    )
    touched = 0
    for model in models:
        slug = providers.get(model.provider_id)
        if not slug:
            continue
        resolve_one(slug, model, sources)
        touched += 1
    return touched
