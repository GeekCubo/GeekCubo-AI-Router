"""Catalog merge for Local AI Connect models.

Local models are exposed to routing under ``local/<machine>/<model_key>``.
The triple is unambiguous even across adapters: a machine is identified by its
UUID, and the model key is the adapter-local name (``llama3.1:8b``). The
deployment's ``litellm_model`` is ``geekcubo_local/<machine_id>::<model_key>``
so the custom provider handler can recover the routing target from the wire
string alone.

Local models are genuinely free — the operator pays for their own hardware, not
per token — so their routing price is a confirmed zero, never an unpriced stub.
``price_source="local"`` lets `app.auto_routing.is_priced_for_auto` accept them
while everything that reports a price keeps treating their cost as 0.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.local_connect.enrollment import (
    STATUS_APPROVED,
    machine_online,
)
from packages.db.models.local_connect import LocalMachine, LocalModel, LocalSettings

LOCAL_SLUG = "local"
LITELLM_PROVIDER = "geekcubo_local"
LITELLM_PREFIX = f"{LITELLM_PROVIDER}/"
WIRE_SEPARATOR = "::"


def wire_model_id(machine_id: str, model_key: str) -> str:
    return f"{machine_id}{WIRE_SEPARATOR}{model_key}"


def parse_wire_model_id(value: str) -> tuple[str, str] | None:
    """Recover `(machine_id, model_key)` from a wire model id."""
    prefix = f"{LITELLM_PREFIX}"
    if value.startswith(prefix):
        value = value[len(prefix):]
    if WIRE_SEPARATOR not in value:
        return None
    machine_id, model_key = value.split(WIRE_SEPARATOR, 1)
    if not machine_id or not model_key:
        return None
    return machine_id, model_key


def machine_slug(machine: LocalMachine) -> str:
    """Short, stable, human-readable machine component for model ids."""
    return machine.id


def local_model_id(machine: LocalMachine, model_key: str) -> str:
    return f"{LOCAL_SLUG}/{machine_slug(machine)}/{model_key}"


def machine_id_of_model_id(model_id: str) -> str | None:
    """Extract the machine component from `local/<machine>/<model>`.

    Model keys may themselves contain slashes (`mlx-community/...`), so only
    the first two path segments are meaningful.
    """
    parts = model_id.split("/")
    if len(parts) < 3 or parts[0] != LOCAL_SLUG:
        return None
    return parts[1]

def _adapters(machine: LocalMachine) -> list[str]:
    if not machine.adapters_json:
        return []
    try:
        value = json.loads(machine.adapters_json)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


async def load_local_settings(db: AsyncSession, workspace_id: str) -> LocalSettings:
    """Settings for a workspace, materialised on first write.

    Only writers (the PUT handler) should call this: it inserts a row and
    flushes, which takes a SQLite write lock. Read paths (router build,
    catalog merge, GET handlers) must use `read_local_settings` so polling the
    dashboard never contends with the request-log writer.
    """
    row = await db.get(LocalSettings, workspace_id)
    if row is None:
        row = LocalSettings(workspace_id=workspace_id)
        db.add(row)
        await db.flush()
    return row


async def read_local_settings(
    db: AsyncSession, workspace_id: str
) -> LocalSettings:
    """Settings for a workspace without touching the database.

    Returns a transient row carrying the model defaults when none is stored,
    so every caller can read `.enabled` without a null check and without the
    write (and write lock) an upsert would take.
    """
    row = await db.get(LocalSettings, workspace_id)
    if row is not None:
        return row
    # `server_default` only fires on INSERT, so a transient object would carry
    # None for every flag. Spell the defaults out to match the column ones.
    return LocalSettings(
        workspace_id=workspace_id,
        enabled=True,
        eligible_for_auto=True,
        no_cloud_fallback=False,
    )


async def approved_machines(db: AsyncSession, *, only_online: bool = False) -> list[LocalMachine]:
    rows = (
        await db.execute(
            select(LocalMachine).where(
                LocalMachine.is_deleted == 0,
                LocalMachine.status == STATUS_APPROVED,
            )
        )
    ).scalars().all()
    machines = list(rows)
    if only_online:
        machines = [m for m in machines if machine_online(m)]
    return machines


async def enabled_local_models(db: AsyncSession) -> list[tuple[LocalMachine, LocalModel]]:
    """Approved machines × enabled models, regardless of liveness.

    Liveness is a routing-time concern: a model on an offline machine is still
    a valid pinned target (the request fails with a clear error) and appears in
    listings marked offline.
    """
    machines = await approved_machines(db)
    if not machines:
        return []
    by_id = {m.id: m for m in machines}
    rows = (
        await db.execute(
            select(LocalModel).where(
                LocalModel.is_enabled.is_(True),
                LocalModel.machine_id.in_(list(by_id)),
            )
        )
    ).scalars().all()
    out = [(by_id[row.machine_id], row) for row in rows if row.machine_id in by_id]
    out.sort(key=lambda pair: (pair[0].display_name.lower(), pair[1].model_key.lower()))
    return out


async def local_catalog_entries(
    db: AsyncSession,
    *,
    settings: LocalSettings | None = None,
    eligible_only: bool = True,
    workspace_id: str = "default",
) -> list:
    """Local models as `CatalogModel` records, priced at zero.

    `eligible_only=True` (the auto-routing path) keeps only models on machines
    the operator marked auto-eligible, and returns nothing at all when the
    feature is disabled or the routing policy excludes local models.
    `eligible_only=False` (listings / pinning) keeps every approved machine's
    enabled models so an operator can still pin one.
    """
    from packages.litellm_adapter.catalog import CatalogModel

    if settings is None:
        settings = await read_local_settings(db, workspace_id)
    if not settings.enabled:
        return []

    pairs = await enabled_local_models(db)
    out = []
    from app.reasoning import capability, local_thinking_from_metadata

    for machine, model in pairs:
        if eligible_only and not (machine.eligible_for_auto and settings.eligible_for_auto):
            continue
        model_id = local_model_id(machine, model.model_key)
        out.append(
            CatalogModel(
                id=model_id,
                provider=LOCAL_SLUG,
                litellm_prefix=LITELLM_PREFIX,
                supports_tools=bool(model.supports_tools),
                supports_vision=bool(model.supports_vision),
                supports_json_mode=bool(model.supports_json_mode),
                supports_json_schema=False,
                input_cost_per_token=0.0,
                output_cost_per_token=0.0,
                context_length=model.context_length,
                price_source="local",
                # The runtime decides: Ollama reports the exact `think`
                # values per model; LM Studio only takes an effort for models
                # it knows reason and reports nothing. None stays Unknown.
                reasoning_levels=capability(
                    model_id,
                    provider=LITELLM_PROVIDER,
                    local_adapter=model.adapter,
                    local_thinking=local_thinking_from_metadata(model.metadata_json),
                ).levels,
            )
        )
    return out


def machine_adapters(machine: LocalMachine) -> list[str]:
    return _adapters(machine)
