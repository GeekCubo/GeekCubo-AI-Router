"""Local deployments for the router cache.

`router_cache.build_deployments` is pure Python so it can be unit-tested
without LiteLLM; this module supplies the local half of its input from the
database. Keeping it separate means the router cache never imports SQLAlchemy
models directly and the mapping (model name, wire id, deployment id) lives in
one place next to the catalog definitions it mirrors.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.local_connect import catalog as local_catalog
from app.local_connect.catalog import read_local_settings
from app.reasoning import local_thinking_from_metadata
from packages.db.models.local_connect import LocalMachine, LocalModel


@dataclass(frozen=True)
class LocalDeploymentView:
    model_name: str
    wire_model: str
    deployment_id: str
    machine_id: str
    model_key: str
    adapter: str | None = None
    thinking: tuple[str, ...] | None = None


def view_for(machine: LocalMachine, model: LocalModel) -> LocalDeploymentView:
    wire = f"{local_catalog.LITELLM_PREFIX}{local_catalog.wire_model_id(machine.id, model.model_key)}"
    model_name = local_catalog.local_model_id(machine, model.model_key)
    return LocalDeploymentView(
        model_name=model_name,
        wire_model=wire,
        deployment_id=f"local::{machine.id}::{model.model_key}",
        machine_id=machine.id,
        model_key=model.model_key,
        adapter=model.adapter,
        thinking=local_thinking_from_metadata(model.metadata_json),
    )


async def load_local_deployments(
    db: AsyncSession, *, workspace_id: str = "default"
) -> list[LocalDeploymentView]:
    """Every enabled model on an approved machine, if the feature is enabled.

    Auto eligibility is applied at catalog-merge time, not here: a model
    excluded from Auto is still a valid pinned target, so it must be deployed.
    """
    settings = await read_local_settings(db, workspace_id)
    if not settings.enabled:
        return []
    pairs = await local_catalog.enabled_local_models(db)
    return [view_for(machine, model) for machine, model in pairs]
