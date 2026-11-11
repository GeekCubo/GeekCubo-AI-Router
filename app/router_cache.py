"""Router cache — single-workspace, single-router edition.

Replaces the SaaS edition's per-workspace LRU + Redis pub/sub invalidation with
a single cached `GeekCuboLLMClient`. Rebuilt on demand when provider keys
change (callers invoke `invalidate_router()`).

`build_deployments()` is split out as pure-Python so it can be tested without
instantiating litellm.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from packages.auth.encryption import decrypt_credential
from packages.litellm_adapter.catalog import models_for_provider
from packages.litellm_adapter.types import ProviderDeployment

logger = logging.getLogger("geekcubo.router")

if TYPE_CHECKING:
    from app.config import Settings
    from app.custom_providers import CustomProviderView
    from app.local_connect.deployments import LocalDeploymentView
    from packages.db.models.provider_key import ProviderKey


def build_deployments(
    *,
    env_keys: dict[str, str],
    db_keys: list["ProviderKey"],
    settings: "Settings",
    custom_providers: list["CustomProviderView"] | None = None,
    local_models: list["LocalDeploymentView"] | None = None,
) -> list[ProviderDeployment]:
    """Assemble the deployment list from env vars + DB rows + custom providers.

    Precedence:
      1. DB provider keys (UI-edited, authoritative; encrypted at rest)
      2. Env vars for providers not present in DB
      3. Custom OpenAI-compatible providers (namespaced `{slug}/{model_id}`)
      4. Local AI Connect models (`local/<machine>/<model>`)
    """
    deployments: list[ProviderDeployment] = []
    db_provider_keys: dict[str, str] = {}

    for row in db_keys:
        if not row.is_enabled or row.is_deleted:
            continue
        plaintext = _decrypt_stored_key(row, log_failures=True)
        if plaintext is None:
            continue
        db_provider_keys[row.provider] = plaintext

    # Step 1+2: provider keys (DB > env).
    for provider, models in (
        (p, models_for_provider(p)) for p in {*db_provider_keys, *env_keys}
    ):
        api_key = db_provider_keys.get(provider) or env_keys.get(provider)
        if not api_key:
            continue
        for model in models:
            deployments.append(
                ProviderDeployment(
                    model_name=model.id,
                    litellm_model=f"{model.litellm_prefix}{model.id}",
                    api_key=api_key,
                    provider=provider,
                )
            )

    # Step 3: custom OpenAI-compatible providers. Enabled + decryptable rows
    # only; the api_base and openai-format wire id are carried on each
    # deployment so LiteLLM sends the credential to the operator's URL, never
    # to the built-in OpenAI endpoint.
    if custom_providers:
        from app.custom_providers import providers_to_deployments

        deployments.extend(providers_to_deployments(custom_providers))

    # Step 4: Local AI Connect. One deployment per enabled model on an
    # approved machine; the wire id carries the machine + model so the
    # `geekcubo_local` custom handler can dispatch it over that machine's
    # WebSocket. Cost is a confirmed zero (see app.local_connect.catalog).
    if local_models:
        from packages.litellm_adapter.types import ProviderDeployment as _PD

        for local in local_models:
            deployments.append(
                _PD(
                    model_name=local.model_name,
                    litellm_model=local.wire_model,
                    api_key="local",
                    provider="local",
                    custom_llm_provider="geekcubo_local",
                    input_cost_per_token=0.0,
                    output_cost_per_token=0.0,
                    deployment_id=local.deployment_id,
                    operator_priced=True,
                    local_adapter=getattr(local, "adapter", None),
                    local_thinking=getattr(local, "thinking", None),
                )
            )

    return deployments


def usable_providers_from_db(db_keys: list["ProviderKey"]) -> set[str]:
    """Set of provider names whose DB-stored key actually decrypts.

    Single source of truth for "is this provider deployable from a DB row?"
    Used by the providers list and `/v1/analytics/unreachable` so the
    dashboard's "configured providers" view stays in lockstep with what
    `build_deployments` will actually wire up. Without this, an undecryptable
    row (after `CREDENTIAL_ENCRYPTION_KEY` rotation) would falsely suppress
    models while the router can't reach them either.
    """
    out: set[str] = set()
    for row in db_keys:
        if not row.is_enabled or row.is_deleted:
            continue
        if _decrypt_stored_key(row, log_failures=False) is None:
            continue
        out.add(row.provider)
    return out


def _decrypt_stored_key(row: "ProviderKey", *, log_failures: bool) -> str | None:
    """Decrypt a DB row. Returns None when the current key cannot open it.

    `build_deployments` still skips the row (env fallback stays available)
    but logs so a CREDENTIAL_ENCRYPTION_KEY rotation is not silent.
    Listing/unreachable helpers pass `log_failures=False` to avoid
    repeating the same warning on every dashboard poll.
    """
    try:
        return decrypt_credential(row.encrypted_key)
    except Exception as exc:
        if log_failures:
            logger.warning(
                "undecryptable_provider_key: stored key for %s cannot be "
                "decrypted with the current CREDENTIAL_ENCRYPTION_KEY (%s). "
                "The row is skipped so env fallback can still serve traffic. "
                "Re-save the key in the dashboard, or set "
                "CREDENTIAL_ENCRYPTION_PREVIOUS_KEY to the prior value "
                "and restart to re-encrypt.",
                row.provider,
                type(exc).__name__,
            )
        return None


# ── Cached router instance ────────────────────────────────────────────────

_cached_client: object | None = None
_cache_lock = asyncio.Lock()


async def get_router(session) -> object:
    """Return the cached GeekCuboLLMClient, building it on first call.

    Imports `GeekCuboLLMClient` lazily so unit tests of `build_deployments`
    don't drag in litellm.
    """
    global _cached_client
    if _cached_client is not None:
        return _cached_client
    async with _cache_lock:
        if _cached_client is not None:
            return _cached_client

        from sqlalchemy import select

        from app.auto_routing import litellm_routing_strategy
        from app.config import get_settings
        from app.seed import DEFAULT_WORKSPACE_ID
        from packages.db.models.provider_key import ProviderKey
        from packages.db.models.routing_config import RoutingConfig
        from packages.litellm_adapter.client import GeekCuboLLMClient

        settings = get_settings()
        rows = (
            await session.execute(
                select(ProviderKey).where(ProviderKey.is_deleted == 0)
            )
        ).scalars().all()

        from app.custom_providers import load_custom_providers

        custom_rows = await load_custom_providers(session)

        from app.local_connect.deployments import load_local_deployments

        local_rows = await load_local_deployments(session)

        deployments = build_deployments(
            env_keys=settings.env_provider_keys(),
            db_keys=list(rows),
            settings=settings,
            custom_providers=custom_rows,
            local_models=local_rows,
        )

        routing_row = (
            await session.execute(
                select(RoutingConfig).where(
                    RoutingConfig.workspace_id == DEFAULT_WORKSPACE_ID,
                    RoutingConfig.is_deleted == 0,
                )
            )
        ).scalar_one_or_none()
        strategy = routing_row.strategy if routing_row else "balanced"
        preferred_models = (
            list(routing_row.preferred_models or []) if routing_row else []
        )
        from app.routing_policy import PolicyError, default_policy, normalize_policy

        try:
            routing_policy = normalize_policy(routing_row.policy if routing_row else None)
        except PolicyError:
            # A corrupt stored policy must never take Auto down: fall back to
            # defaults (== pre-policy behaviour) and keep serving.
            routing_policy = default_policy()

        _cached_client = GeekCuboLLMClient(
            deployments=deployments,
            strategy=strategy,
            preferred_models=preferred_models,
            litellm_routing_strategy=litellm_routing_strategy(strategy),
            # Wire LiteLLM Router built-ins from settings so a deployment
            # that 404s once stays cooled down (no immediate re-pick), and
            # the cascade engine has policy for which errors fail fast.
            cooldown_time=float(settings.router_cooldown_seconds),
            allowed_fails=settings.router_allowed_fails,
            enable_pre_call_checks=settings.router_pre_call_checks,
            num_retries=settings.router_num_retries_default,
        )
        _cached_client.routing_policy = routing_policy
        return _cached_client


def invalidate_router() -> None:
    """Drop the cached router so the next request rebuilds it."""
    global _cached_client
    _cached_client = None
