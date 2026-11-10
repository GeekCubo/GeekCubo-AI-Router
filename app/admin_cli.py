"""Local administrator CLI.

Runs against the same DATABASE_URL as the server, from the host or inside the
container. It is deliberately NOT reachable over HTTP: every command here needs
shell access to the machine (or `docker exec` into the container), which is the
authorization.

    python -m app.admin_cli status
    python -m app.admin_cli setup              # create the administrator
    python -m app.admin_cli setup-token        # print a one-time dashboard token
    python -m app.admin_cli reset-password     # forgotten-password recovery
    python -m app.admin_cli revoke-sessions    # sign every browser out

Docker:

    docker compose exec api python -m app.admin_cli reset-password

Passwords are read with `getpass` (no echo, not in shell history, not visible
in `ps`). For non-interactive automation, `--password-stdin` reads one line
from standard input instead. There is intentionally no `--password VALUE` flag.

None of these commands touch provider credentials, sk-geek-* API keys, custom
providers, models, request history, or the encryption key.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


async def _with_db(fn):
    """Open the configured database, ensure schema, run `fn(session)`."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    import packages.db.models  # noqa: F401  (register every table)
    from app.config import get_settings
    from packages.db.engine import build_engine
    from packages.db.migrate import (
        ensure_auth_columns,
        ensure_budget_columns,
        ensure_chat_attachment_columns,
        ensure_chat_columns,
        ensure_custom_provider_columns,
        ensure_json_capability_split,
        ensure_local_connect_tables,
        ensure_quality_columns,
        ensure_quality_connection_columns,
        ensure_routing_columns,
    )
    from packages.db.models.base import Base

    settings = get_settings()
    engine = build_engine(settings.database_url)
    try:
        # Additive only — the same idempotent steps the server runs at boot, so
        # the CLI works against an install that has never been upgraded.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await ensure_budget_columns(engine)
        await ensure_chat_columns(engine)
        await ensure_chat_attachment_columns(engine)
        await ensure_custom_provider_columns(engine)
        await ensure_json_capability_split(engine)
        await ensure_auth_columns(engine)
        await ensure_routing_columns(engine)
        await ensure_quality_columns(engine)
        await ensure_quality_connection_columns(engine)
        await ensure_local_connect_tables(engine)
        # Provision the credential key + pepper before the CLI touches any
        # encrypted field (e.g. `setup` re-encrypts nothing, but a fresh DB
        # should still get secrets so the server later starts secure).
        from app.secret_provisioning import provision_secrets

        await provision_secrets(settings, engine)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await fn(session)
    finally:
        await engine.dispose()


def _read_password(args, *, prompt: str, confirm: bool) -> str:
    if getattr(args, "password_stdin", False):
        line = sys.stdin.readline()
        if not line:
            raise SystemExit("error: no password on standard input")
        return line.rstrip("\r\n")
    if not sys.stdin.isatty():
        raise SystemExit(
            "error: no interactive terminal. Use --password-stdin to pipe the "
            "password, e.g. `docker compose exec -T api python -m app.admin_cli "
            "reset-password --password-stdin < pwfile`."
        )
    first = getpass.getpass(prompt)
    if confirm:
        second = getpass.getpass("Confirm password: ")
        if first != second:
            raise SystemExit("error: passwords do not match")
    return first


def _print_policy() -> None:
    from packages.auth.passwords import password_strength_hint

    print(f"Password policy: {password_strength_hint()}")


# ── commands ──────────────────────────────────────────────────────────────


def cmd_status(args) -> int:
    from packages.auth import admin_accounts

    async def run(db):
        from sqlalchemy import func, select

        from packages.db.models.admin import AdminSession
        from packages.db.models.api_key import ApiKey

        admin = await admin_accounts.get_admin(db)
        # `is_active` is stored as 'true' via the column's server_default on
        # SQLite, so `is_(True)` would miss seeded keys. Revocation always sets
        # `revoked_at`, which is the reliable signal.
        active_keys = (
            await db.execute(
                select(func.count()).select_from(ApiKey).where(
                    ApiKey.is_deleted == 0,
                    ApiKey.revoked_at.is_(None),
                )
            )
        ).scalar_one()
        live_sessions = 0
        if admin is not None:
            live_sessions = (
                await db.execute(
                    select(func.count()).select_from(AdminSession).where(
                        AdminSession.admin_id == admin.id,
                        AdminSession.revoked_at.is_(None),
                    )
                )
            ).scalar_one()
        return admin, active_keys, live_sessions

    admin, active_keys, live_sessions = asyncio.run(_with_db(run))
    if admin is None:
        print("Administrator: NOT INITIALIZED")
        print("  Run `python -m app.admin_cli setup` (shell) or "
              "`python -m app.admin_cli setup-token` (dashboard).")
    else:
        print(f"Administrator: {admin.username}")
        print(f"  password changed: {admin.password_changed_at or 'unknown'}")
        print(f"  last login:       {admin.last_login_at or 'never'}")
        print(f"  live sessions:    {live_sessions}")
    print(f"Active API keys: {active_keys}")
    return 0


def cmd_setup(args) -> int:
    from packages.auth import admin_accounts
    from packages.auth.passwords import PasswordPolicyError, validate_username

    async def already(db):
        return await admin_accounts.admin_exists(db)

    if asyncio.run(_with_db(already)):
        _err("an administrator already exists. Use `reset-password` to recover access.")
        return 1

    username = args.username
    if not username:
        if not sys.stdin.isatty():
            _err("--username is required without an interactive terminal")
            return 2
        username = input("Administrator username: ")
    try:
        username = validate_username(username)
    except PasswordPolicyError as exc:
        _err(str(exc))
        return 2

    _print_policy()
    password = _read_password(args, prompt="New administrator password: ", confirm=True)

    async def run(db):
        issued = await admin_accounts.issue_setup_token(db)
        return await admin_accounts.create_admin(
            db, username=username, password=password, setup_token=issued.raw_token
        )

    try:
        admin = asyncio.run(_with_db(run))
    except (PasswordPolicyError, admin_accounts.SetupError) as exc:
        _err(str(exc))
        return 1
    print(f"Administrator '{admin.username}' created. Sign in at the dashboard.")
    return 0


def cmd_setup_token(args) -> int:
    from packages.auth import admin_accounts

    async def run(db):
        if await admin_accounts.admin_exists(db):
            return None
        return await admin_accounts.issue_setup_token(db)

    issued = asyncio.run(_with_db(run))
    if issued is None:
        _err("an administrator already exists; setup tokens are disabled. "
             "Use `reset-password` to recover access.")
        return 1
    print("One-time administrator setup token (any previous token is now invalid):")
    print(f"  {issued.raw_token}")
    print(f"Expires: {issued.expires_at.isoformat()}")
    print("Paste it into the dashboard's “Create Administrator Account” form.")
    return 0


def cmd_reset_password(args) -> int:
    from packages.auth import admin_accounts
    from packages.auth.passwords import PasswordPolicyError

    _print_policy()
    password = _read_password(args, prompt="New administrator password: ", confirm=True)

    async def run(db):
        return await admin_accounts.reset_password_locally(
            db, username=args.username, new_password=password
        )

    try:
        admin = asyncio.run(_with_db(run))
    except (PasswordPolicyError, admin_accounts.SetupError) as exc:
        _err(str(exc))
        return 1
    print(f"Password for '{admin.username}' reset. All dashboard sessions were signed out.")
    print("API keys, providers and all other data are unchanged.")
    return 0


def cmd_revoke_sessions(args) -> int:
    from packages.auth import admin_accounts
    from packages.auth.sessions import revoke_all_sessions

    async def run(db):
        admin = await admin_accounts.get_admin(db)
        if admin is None:
            return None
        return await revoke_all_sessions(db, admin.id)

    count = asyncio.run(_with_db(run))
    if count is None:
        _err("no administrator exists")
        return 1
    print(f"Revoked {count} dashboard session(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.admin_cli",
        description="Local GeekCubo administrator management (requires shell access).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show administrator and key status").set_defaults(func=cmd_status)

    s = sub.add_parser("setup", help="create the administrator from the shell")
    s.add_argument("--username", help="administrator username (prompted if omitted)")
    s.add_argument("--password-stdin", action="store_true",
                   help="read the password from one line of standard input")
    s.set_defaults(func=cmd_setup)

    t = sub.add_parser("setup-token", help="print a one-time dashboard setup token")
    t.set_defaults(func=cmd_setup_token)

    r = sub.add_parser("reset-password", help="set a new administrator password")
    r.add_argument("--username", help="must match the existing administrator, if given")
    r.add_argument("--password-stdin", action="store_true",
                   help="read the password from one line of standard input")
    r.set_defaults(func=cmd_reset_password)

    v = sub.add_parser("revoke-sessions", help="sign every dashboard session out")
    v.set_defaults(func=cmd_revoke_sessions)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
