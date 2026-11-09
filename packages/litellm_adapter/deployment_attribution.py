"""Provider attribution for completed calls.

After a call returns, the adapter must say which deployment actually served it
and, for operator-priced (custom) deployments, what price to record. LiteLLM
stashes per-call diagnostics on ``_hidden_params``; these helpers recover the
winning deployment from those, plus a model-name fallback for streams that do
not expose them.
"""

from __future__ import annotations

from packages.litellm_adapter.types import ProviderDeployment


def hidden_params_of(resp: object) -> dict:
    """LiteLLM stashes per-call diagnostics on `_hidden_params` (dict)."""
    hidden = getattr(resp, "_hidden_params", None)
    return hidden if isinstance(hidden, dict) else {}


def _norm_base(url: str | None) -> str:
    return (url or "").rstrip("/")


def _bare(name: str) -> str:
    return name.split("/", 1)[-1] if "/" in name else name


def _model_matches(deployment: ProviderDeployment, served_model: str | None) -> bool:
    if not served_model:
        return False
    if served_model in (deployment.model_name, deployment.litellm_model):
        return True
    bare = _bare(served_model)
    return bare == deployment.model_name or bare == _bare(deployment.litellm_model)


def match_served_deployment(
    deployments: list[ProviderDeployment],
    *,
    hidden: dict | None = None,
    served_model: str | None = None,
) -> ProviderDeployment | None:
    """Identify the deployment LiteLLM actually called.

    Preference order:
      1. pinned `model_info.id`
      2. `api_base` — the strongest identity when present
      3. model-name match, but only when it is unambiguous
    """
    hidden = hidden or {}
    model_id = hidden.get("model_id")
    if isinstance(model_id, str) and model_id:
        for deployment in deployments:
            if deployment.deployment_id == model_id:
                return deployment

    api_base = hidden.get("api_base")
    if isinstance(api_base, str) and api_base:
        norm = _norm_base(api_base)
        at_base = [
            d for d in deployments
            if d.api_base and _norm_base(d.api_base) == norm
        ]
        if at_base:
            for deployment in at_base:
                if _model_matches(deployment, served_model):
                    return deployment
            providers = {d.provider for d in at_base}
            if len(providers) == 1:
                return at_base[0]

    if not served_model:
        return None
    name_hits = [d for d in deployments if _model_matches(d, served_model)]
    if not name_hits:
        return None
    if len({d.provider for d in name_hits}) == 1:
        return name_hits[0]
    return None


def resolve_provider(
    deployments: list[ProviderDeployment],
    *,
    hidden: dict | None = None,
    served_model: str | None = None,
    requested_model: str | None = None,
    litellm_provider: str | None = None,
) -> str:
    """Return the provider that served a completed call."""
    served = match_served_deployment(
        deployments, hidden=hidden, served_model=served_model,
    )
    if served is not None:
        return served.provider
    # LiteLLM reports the underlying transport for a CustomLLM handler (the
    # local provider surfaces as "openai"), so the custom provider name is not
    # authoritative when our own pinned deployment already matched above.
    if litellm_provider:
        return litellm_provider
    if served_model:
        for deployment in deployments:
            if deployment.litellm_model == served_model or deployment.model_name == served_model:
                return deployment.provider
    return "unknown"


def operator_price_meta(served: ProviderDeployment | None) -> dict:
    """Cost metadata for a call served by an operator-priced deployment.

    Returns {} for built-in deployments (their existing cost tiers apply). For
    custom deployments it returns the configured per-token prices, or `None`
    when the operator configured none. `None` means UNKNOWN cost and must
    never be replaced by a catalog or echoed-model price.
    """
    if served is None or not getattr(served, "operator_priced", False):
        return {}
    inp, out = served.input_cost_per_token, served.output_cost_per_token
    if not inp and not out:
        return {"operator_price": None, "served_deployment": served.model_name}
    return {
        "operator_price": [float(inp or 0.0), float(out or 0.0)],
        "served_deployment": served.model_name,
    }
