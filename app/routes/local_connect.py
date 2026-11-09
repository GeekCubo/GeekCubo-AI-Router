"""Local AI Connect — administrator API and the agent WebSocket.

REST (administrator session, CSRF-protected by the auth middleware):
    GET    /api/local-connect/overview
    GET    /api/local-connect/settings        PUT same
    POST   /api/local-connect/enrollments     -> one-time code
    GET    /api/local-connect/enrollments
    DELETE /api/local-connect/enrollments/{id}
    GET    /api/local-connect/machines
    POST   /api/local-connect/machines/{id}/approve
    POST   /api/local-connect/machines/{id}/revoke
    POST   /api/local-connect/machines/{id}/rotate
    POST   /api/local-connect/machines/{id}/discover
    POST   /api/local-connect/machines/{id}/models/{model_pk}  (enable/disable)
    DELETE /api/local-connect/machines/{id}
    GET    /api/local-connect/service-files   (systemd/launchd/Windows templates)
    GET    /api/local-connect/install-command

Agent socket (the connector authenticates with its own machine credential —
`AuthMiddleware` only guards HTTP, so this handler validates the credential
itself on the `hello` frame):
    WS     /api/local-connect/agent
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache_invalidation_bus
from app.config import get_settings
from app.deps import AdminContext, get_admin_context, get_db
from app.local_connect import catalog as local_catalog
from app.local_connect import dispatcher, enrollment, hub, protocol
from packages.db.models.local_connect import (
    LocalEnrollment,
    LocalMachine,
    LocalModel,
)

logger = logging.getLogger("geekcubo.local_connect")

router = APIRouter(prefix="/api/local-connect", tags=["local-connect"])


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _invalidate_router() -> None:
    await cache_invalidation_bus.broadcast_router_cache_invalidation()


# ── serializers ────────────────────────────────────────────────────────────


def _model_out(model: LocalModel, machine: LocalMachine) -> dict:
    return {
        "id": model.id,
        "model_key": model.model_key,
        "routing_id": local_catalog.local_model_id(machine, model.model_key),
        "display_name": model.display_name,
        "adapter": model.adapter,
        "family": model.family,
        "parameter_count": model.parameter_count,
        "quantization": model.quantization,
        "context_length": model.context_length,
        "supports_tools": bool(model.supports_tools),
        "supports_vision": bool(model.supports_vision),
        "supports_json_mode": bool(model.supports_json_mode),
        "is_enabled": bool(model.is_enabled),
        "tokens_per_second": model.tokens_per_second,
        "last_reported_at": _iso(model.last_reported_at),
    }


def _machine_out(machine: LocalMachine, models: list[LocalModel]) -> dict:
    return {
        "id": machine.id,
        "display_name": machine.display_name,
        "status": machine.status,
        "online": hub.is_online(machine.id),
        "last_seen_at": _iso(machine.last_seen_at),
        "hostname": machine.hostname,
        "platform": machine.platform,
        "agent_version": machine.agent_version,
        "adapters": local_catalog.machine_adapters(machine),
        "eligible_for_auto": bool(machine.eligible_for_auto),
        "credential_prefix": machine.credential_prefix,
        "approved_at": _iso(machine.approved_at),
        "revoked_at": _iso(machine.revoked_at),
        "created_at": _iso(machine.created_at),
        "models": [_model_out(m, machine) for m in models],
    }


async def _models_by_machine(db: AsyncSession, machine_ids: list[str]) -> dict[str, list[LocalModel]]:
    if not machine_ids:
        return {}
    rows = (
        await db.execute(
            select(LocalModel).where(LocalModel.machine_id.in_(machine_ids))
        )
    ).scalars().all()
    out: dict[str, list[LocalModel]] = {mid: [] for mid in machine_ids}
    for row in rows:
        out.setdefault(row.machine_id, []).append(row)
    for values in out.values():
        values.sort(key=lambda m: m.model_key.lower())
    return out


async def _settings_out(db: AsyncSession, workspace_id: str) -> dict:
    row = await local_catalog.read_local_settings(db, workspace_id)
    return {
        "enabled": bool(row.enabled),
        "eligible_for_auto": bool(row.eligible_for_auto),
        "no_cloud_fallback": bool(row.no_cloud_fallback),
    }


# ── overview / settings ────────────────────────────────────────────────────


@router.get("/overview")
async def overview(
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    machines = (
        await db.execute(
            select(LocalMachine).where(LocalMachine.is_deleted == 0)
        )
    ).scalars().all()
    machines = sorted(machines, key=lambda m: m.display_name.lower())
    models = await _models_by_machine(db, [m.id for m in machines])
    settings_row = await local_catalog.read_local_settings(db, ac.workspace_id)
    return {
        "settings": {
            "enabled": bool(settings_row.enabled),
            "eligible_for_auto": bool(settings_row.eligible_for_auto),
            "no_cloud_fallback": bool(settings_row.no_cloud_fallback),
        },
        "feature_enabled": bool(get_settings().local_connect_enabled),
        "machines": [_machine_out(m, models.get(m.id, [])) for m in machines],
        "counts": {
            "machines": len(machines),
            "approved": sum(1 for m in machines if m.status == enrollment.STATUS_APPROVED),
            "pending": sum(1 for m in machines if m.status == enrollment.STATUS_PENDING),
            "online": sum(1 for m in machines if hub.is_online(m.id)),
            "models": sum(len(v) for v in models.values()),
        },
        "install_command": _install_command(),
        "server_url": _server_url(),
    }


class SettingsBody(BaseModel):
    enabled: bool | None = None
    eligible_for_auto: bool | None = None
    no_cloud_fallback: bool | None = None


@router.put("/settings")
async def update_settings(
    body: SettingsBody,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await local_catalog.load_local_settings(db, ac.workspace_id)
    for field in ("enabled", "eligible_for_auto", "no_cloud_fallback"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, bool(value))
    await db.commit()
    await _invalidate_router()
    return await _settings_out(db, ac.workspace_id)


async def settings_view(
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _settings_out(db, ac.workspace_id)


router.add_api_route("/settings", settings_view, methods=["GET"])


# ── enrollments ────────────────────────────────────────────────────────────


class EnrollmentBody(BaseModel):
    display_name: str | None = None
    ttl_minutes: int | None = None


@router.post("/enrollments", status_code=201)
async def create_enrollment(
    body: EnrollmentBody,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ttl = body.ttl_minutes or get_settings().local_connect_enrollment_ttl_minutes
    row, code = await enrollment.create_enrollment(
        db, display_name=body.display_name, ttl_minutes=ttl
    )
    await db.commit()
    return {
        "id": row.id,
        "code": code,
        "code_prefix": row.code_prefix,
        "display_name": row.display_name,
        "expires_at": _iso(row.expires_at),
        "install_command": _install_command(),
        "server_url": _server_url(),
    }


@router.get("/enrollments")
async def list_enrollments(
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(LocalEnrollment)
            .where(LocalEnrollment.is_deleted == 0)
            .order_by(LocalEnrollment.created_at.desc())
        )
    ).scalars().all()
    return {
        "enrollments": [
            {
                "id": row.id,
                "code_prefix": row.code_prefix,
                "display_name": row.display_name,
                "expires_at": _iso(row.expires_at),
                "consumed_at": _iso(row.consumed_at),
                "machine_id": row.machine_id,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }


@router.delete("/enrollments/{enrollment_id}", status_code=204)
async def delete_enrollment(
    enrollment_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(LocalEnrollment, enrollment_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    row.is_deleted = 1
    await db.commit()


# ── machines ───────────────────────────────────────────────────────────────


@router.get("/machines")
async def list_machines(
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(LocalMachine)
            .where(LocalMachine.is_deleted == 0)
            .order_by(LocalMachine.display_name)
        )
    ).scalars().all()
    models = await _models_by_machine(db, [r.id for r in rows])
    return {"machines": [_machine_out(r, models.get(r.id, [])) for r in rows]}


async def _require_machine(db: AsyncSession, machine_id: str) -> LocalMachine:
    row = await db.get(LocalMachine, machine_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    return row


@router.post("/machines/{machine_id}/approve")
async def approve(
    machine_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_machine(db, machine_id)
    machine = await enrollment.approve_machine(db, machine_id)
    await db.commit()
    await _invalidate_router()
    models = await _models_by_machine(db, [machine_id])
    return _machine_out(machine, models.get(machine_id, []))


@router.post("/machines/{machine_id}/revoke")
async def revoke(
    machine_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    machine = await enrollment.revoke_machine(db, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    await db.commit()
    await _invalidate_router()
    live = hub.get(machine_id)
    if live is not None:
        try:
            await live.websocket.close(protocol.CLOSE_REJECTED)
        except Exception:
            pass
    models = await _models_by_machine(db, [machine_id])
    return _machine_out(machine, models.get(machine_id, []))


class MachineBody(BaseModel):
    display_name: str | None = None
    eligible_for_auto: bool | None = None


@router.patch("/machines/{machine_id}")
async def update_machine(
    machine_id: str,
    body: MachineBody,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    machine = await _require_machine(db, machine_id)
    if body.display_name is not None:
        value = body.display_name.strip()
        if not value:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")
        machine.display_name = value[:120]
    if body.eligible_for_auto is not None:
        machine.eligible_for_auto = bool(body.eligible_for_auto)
    await db.commit()
    await _invalidate_router()
    models = await _models_by_machine(db, [machine_id])
    return _machine_out(machine, models.get(machine_id, []))


@router.post("/machines/{machine_id}/rotate")
async def rotate(
    machine_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_machine(db, machine_id)
    credential = await enrollment.rotate_credential(db, machine_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    await db.commit()
    live = hub.get(machine_id)
    if live is not None:
        try:
            await live.websocket.close(protocol.CLOSE_REJECTED)
        except Exception:
            pass
    return {
        "machine_id": machine_id,
        "credential": credential,
        # The credential is shown once. The running connector keeps working
        # until it reconnects, when it will be rejected with the old value.
        "reconnect_required": True,
    }


@router.delete("/machines/{machine_id}", status_code=204)
async def delete_machine(
    machine_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await enrollment.delete_machine(db, machine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Machine not found")
    await db.commit()
    await _invalidate_router()
    live = hub.get(machine_id)
    if live is not None:
        try:
            await live.websocket.close(protocol.CLOSE_REJECTED)
        except Exception:
            pass


@router.post("/machines/{machine_id}/discover")
async def rediscover(
    machine_id: str,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_machine(db, machine_id)
    try:
        models = await dispatcher.discover(machine_id)
    except dispatcher.LocalOffline as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except dispatcher.LocalUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    machine = await db.get(LocalMachine, machine_id)
    if machine is not None:
        await _replace_models(db, machine, models)
        await db.commit()
        await _invalidate_router()
    models_by_machine = await _models_by_machine(db, [machine_id])
    return _machine_out(machine, models_by_machine.get(machine_id, []))


class ModelToggleBody(BaseModel):
    is_enabled: bool


@router.patch("/machines/{machine_id}/models/{model_pk}")
async def toggle_model(
    machine_id: str,
    model_pk: str,
    body: ModelToggleBody,
    ac: AdminContext = Depends(get_admin_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    machine = await _require_machine(db, machine_id)
    model = await db.get(LocalModel, model_pk)
    if model is None or model.machine_id != machine_id:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_enabled = bool(body.is_enabled)
    await db.commit()
    await _invalidate_router()
    return _model_out(model, machine)


# ── model sync from connector frames ───────────────────────────────────────


async def _replace_models(db: AsyncSession, machine: LocalMachine, entries: list[dict]) -> None:
    """Replace `machine`'s catalog with the list its connector just reported."""
    existing = {
        row.model_key: row
        for row in (
            await db.execute(
                select(LocalModel).where(LocalModel.machine_id == machine.id)
            )
        ).scalars().all()
    }
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("model_key") or entry.get("id") or "").strip()
        if not key:
            continue
        seen.add(key)
        adapter = str(entry.get("adapter") or "custom")[:30]
        row = existing.get(key)
        if row is None:
            row = LocalModel(machine_id=machine.id, model_key=key, adapter=adapter)
            db.add(row)
        row.display_name = str(entry.get("display_name") or key)[:200]
        row.adapter = adapter
        row.family = (str(entry["family"])[:80] if entry.get("family") else None)
        row.parameter_count = (
            str(entry["parameter_count"])[:40] if entry.get("parameter_count") else None
        )
        row.quantization = str(entry["quantization"])[:40] if entry.get("quantization") else None
        ctx = entry.get("context_length")
        row.context_length = int(ctx) if isinstance(ctx, (int, float)) and ctx else None
        row.supports_tools = bool(entry.get("supports_tools"))
        row.supports_vision = bool(entry.get("supports_vision"))
        row.supports_json_mode = bool(entry.get("supports_json_mode"))
        tps = entry.get("tokens_per_second")
        row.tokens_per_second = float(tps) if isinstance(tps, (int, float)) else None
        row.last_reported_at = now
        if entry.get("metadata") is not None:
            row.metadata_json = json.dumps(entry["metadata"])[:4000]
    for key, row in existing.items():
        if key not in seen:
            await db.delete(row)
    await db.flush()


# ── install helper ─────────────────────────────────────────────────────────


def _server_url() -> str:
    configured = (get_settings().local_connect_public_url or "").strip()
    return configured.rstrip("/")


def _install_command() -> str:
    base = _server_url() or "https://your-geekcubo-host"
    return f"python -m geekcubo_connector enroll --server {base} --code <ENROLLMENT_CODE>"


def _service_file_templates(server_url: str) -> dict:
    command = f"geekcubo-connector run --server {server_url or 'https://your-geekcubo-host'}"
    return {
        "systemd": (
            "[Unit]\n"
            "Description=GeekCubo Local AI Connect agent\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={command}\n"
            "Restart=always\n"
            "RestartSec=5\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        ),
        "launchd": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            "<dict>\n"
            "  <key>Label</key><string>com.geekcubo.connector</string>\n"
            "  <key>ProgramArguments</key>\n"
            "  <array>\n"
            "    <string>/usr/local/bin/geekcubo-connector</string>\n"
            "    <string>run</string>\n"
            f"    <string>--server</string><string>{server_url or 'https://your-geekcubo-host'}</string>\n"
            "  </array>\n"
            "  <key>RunAtLoad</key><true/>\n"
            "  <key>KeepAlive</key><true/>\n"
            "  <key>StandardOutPath</key><string>/tmp/geekcubo-connector.log</string>\n"
            "  <key>StandardErrorPath</key><string>/tmp/geekcubo-connector.log</string>\n"
            "</dict>\n"
            "</plist>\n"
        ),
        "windows": (
            "New-Service -Name GeekCuboConnector -StartupType Automatic -BinaryPathName "
            f"'{command}'\n"
        ),
    }


@router.get("/service-files")
async def service_files(
    ac: AdminContext = Depends(get_admin_context),
) -> dict:
    return {"server_url": _server_url(), "files": _service_file_templates(_server_url())}


@router.get("/install-command")
async def install_command(
    ac: AdminContext = Depends(get_admin_context),
) -> dict:
    return {"server_url": _server_url(), "command": _install_command()}


# ── agent WebSocket ────────────────────────────────────────────────────────


def _bearer(websocket: WebSocket) -> str | None:
    raw = websocket.headers.get("authorization") or ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return None


def _session():
    from packages.db import session as session_mod

    return session_mod.session_factory()()


async def agent_socket(websocket: WebSocket) -> None:
    """Outbound-connector endpoint. Authenticates on the `hello` frame."""
    settings = get_settings()
    await websocket.accept()
    if not settings.local_connect_enabled:
        await websocket.send_text(
            json.dumps(protocol.hello_error(code="disabled", message="Local AI Connect is disabled"))
        )
        await websocket.close(protocol.CLOSE_DISABLED)
        return

    if "credential" in websocket.query_params:
        await websocket.send_text(json.dumps(protocol.hello_error(
            code="unauthorized", message="use the Authorization header, not URL credentials"
        )))
        await websocket.close(protocol.CLOSE_UNAUTHORIZED)
        return
    credential = _bearer(websocket) or ""
    enrollment_code = None
    machine: LocalMachine | None = None
    connection = None

    factory = _session()
    try:
        async with factory as db:
            issued_credential: str | None = None
            if credential:
                machine = await enrollment.find_machine_by_credential(db, credential)
                if machine is None:
                    await websocket.send_text(
                        json.dumps(
                            protocol.hello_error(
                                code="unauthorized",
                                message="machine credential not recognized or revoked",
                            )
                        )
                    )
                    await websocket.close(protocol.CLOSE_UNAUTHORIZED)
                    return
            else:
                # Wait for a hello carrying an enrollment code, so a fresh
                # connector can register without a credential yet.
                first = await websocket.receive_text()
                try:
                    hello = json.loads(first)
                except ValueError:
                    hello = {}
                if not isinstance(hello, dict) or hello.get("type") != "hello":
                    await websocket.send_text(
                        json.dumps(protocol.hello_error(code="protocol", message="expected hello"))
                    )
                    await websocket.close(protocol.CLOSE_PROTOCOL)
                    return
                enrollment_code = hello.get("enrollment_code")
                machine, issued_credential, enroll_error = await _enroll_from_hello(
                    db, hello, enrollment_code
                )
                if machine is None:
                    await websocket.send_text(
                        json.dumps(
                            protocol.hello_error(
                                code="enrollment_failed",
                                message=enroll_error or "enrollment failed",
                            )
                        )
                    )
                    await websocket.close(protocol.CLOSE_UNAUTHORIZED)
                    return
                await db.commit()

            # Exactly one hello_ok per connection. Only the enrollment path
            # returns a credential; a reconnect never re-issues one.
            frame = protocol.hello_ok(
                machine_id=machine.id,
                display_name=machine.display_name,
                status=machine.status,
                heartbeat_seconds=settings.local_connect_heartbeat_seconds,
            )
            if issued_credential is not None:
                frame["credential"] = issued_credential
            await websocket.send_text(json.dumps(frame))
            await enrollment.touch_machine(db, machine)
            await db.commit()
            connection = await hub.register(machine.id, websocket)
            machine_id = machine.id

            await _agent_loop(websocket, db, machine_id, connection)
    finally:
        if connection is not None:
            await hub.unregister(connection.machine_id, connection)
        try:
            await websocket.close()
        except Exception:
            pass


async def _enroll_from_hello(db, hello: dict, code: str | None):
    if not code:
        return None, None, "enrollment code required on first connect"
    row, error = await enrollment.consume_enrollment(db, code)
    if row is None:
        return None, None, (error or "enrollment failed")
    display_name = (
        hello.get("display_name")
        or row.display_name
        or hello.get("hostname")
        or "Local machine"
    )
    machine, credential = await enrollment.create_machine(
        db,
        display_name=str(display_name),
        enrollment=row,
        hostname=hello.get("hostname"),
        platform=hello.get("platform"),
        agent_version=hello.get("agent_version"),
        adapters=list(hello.get("adapters") or []),
    )
    return machine, credential, None


async def _agent_loop(websocket: WebSocket, db, machine_id: str, connection: hub.Connection) -> None:
    from starlette.websockets import WebSocketDisconnect

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        try:
            frame = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(frame, dict):
            continue
        frame_type = frame.get("type")
        if frame_type == "pong":
            machine = await db.get(LocalMachine, machine_id)
            if machine is not None:
                await enrollment.touch_machine(db, machine)
                await db.commit()
            continue
        if frame_type in ("chunk", "done", "error"):
            request_id = frame.get("request_id")
            if request_id:
                connection.push(str(request_id), frame)
            continue
        if frame_type == "models":
            machine = await db.get(LocalMachine, machine_id)
            if machine is not None:
                await _replace_models(db, machine, list(frame.get("models") or []))
                await enrollment.touch_machine(
                    db, machine, adapters=list(frame.get("adapters") or [])
                )
                await db.commit()
                await _invalidate_router()
            # A `models` frame answering an explicit `discover` carries the
            # request_id; wake the caller waiting in `dispatcher.discover`.
            # A spontaneous catalog push has no request_id and is accepted
            # above without a waiter.
            request_id = frame.get("request_id")
            if request_id:
                connection.push(str(request_id), frame)
            continue
        # Unknown frame types are ignored so a newer connector can add frames
        # without breaking an older server.


router.add_api_websocket_route("/agent", agent_socket)
