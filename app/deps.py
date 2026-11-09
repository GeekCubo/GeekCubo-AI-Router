"""Dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth.sessions import SessionRecord
from packages.auth.types import KeyContext
from packages.db.session import get_session

# Lite is single-tenant: every row belongs to the one seeded workspace.
DEFAULT_WORKSPACE_ID = "default"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def _state(request: Request, name: str):
    state = request.scope.get("state") or {}
    if isinstance(state, dict):
        return state.get(name)
    return getattr(state, name, None)


def get_key_context(request: Request) -> KeyContext:
    """Pull the inference KeyContext off scope.state (set by the middleware)."""
    kc = _state(request, "key_context")
    if kc is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Authentication required")
    return kc


def get_admin_session(request: Request) -> SessionRecord:
    """Pull the administrator session off scope.state.

    Defence in depth: the middleware already refuses admin routes without a
    session, but a route mounted outside it (a bare FastAPI app in a test, a
    future router included without the middleware) must not silently become
    public. Asking for this dependency is what makes that impossible.
    """
    record = _state(request, "admin_session")
    if record is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Administrator session required")
    return record


@dataclass(frozen=True)
class AdminContext:
    """Workspace scoping for administrative routes.

    Admin routes used to depend on a `KeyContext` borrowed from the inference
    credential. They now run as the administrator, who is unrestricted by
    definition — there is no allowlist or budget to check. This small value
    object keeps the `kc.workspace_id` call sites intact while removing any
    implication that an inference key took part in the decision.
    """

    workspace_id: str = DEFAULT_WORKSPACE_ID
    # Always unrestricted. Present so shared helpers that read these fields
    # keep working without a special case.
    model_allowlist: list[str] | None = None
    budget_limit_cents: int | None = None
    role_label: str = "administrator"


def get_admin_context(request: Request) -> AdminContext:
    """Administrator identity for routes that need a workspace scope."""
    get_admin_session(request)
    return AdminContext()
