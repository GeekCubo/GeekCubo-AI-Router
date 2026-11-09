"""Local administrator CLI.

The CLI is the recovery path, so its contract matters: it must work without a
running server, must never take the password as an argument, must not touch
provider credentials or API keys, and must sign sessions out.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(db_url: str, *args: str, stdin: str | None = None):
    env = {
        "PYTHONPATH": str(REPO_ROOT),
        "DATABASE_URL": db_url,
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": "/tmp",
    }
    return subprocess.run(
        [sys.executable, "-m", "app.admin_cli", *args],
        cwd=str(REPO_ROOT),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.fixture
def db_url(tmp_sqlite_url):
    return tmp_sqlite_url


def test_status_before_setup(db_url):
    r = _run(db_url, "status")
    assert r.returncode == 0, r.stderr
    assert "NOT INITIALIZED" in r.stdout


def test_setup_token_printed_and_usable(db_url):
    r = _run(db_url, "setup-token")
    assert r.returncode == 0, r.stderr
    token = [ln.strip() for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith(("One-time", "Expires", "Paste"))]
    assert token, r.stdout
    assert len(token[0]) > 20

    # A fresh run replaces it: the previous token is invalidated.
    r2 = _run(db_url, "setup-token")
    assert r2.returncode == 0
    assert token[0] not in r2.stdout


def test_setup_creates_admin_with_stdin_password(db_url):
    r = _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
             stdin="correct horse battery staple\n")
    assert r.returncode == 0, r.stderr
    assert "created" in r.stdout

    status = _run(db_url, "status")
    assert "admin" not in status.stdout.split("Administrator:")[1]
    assert "geeklocal" in status.stdout


def test_setup_rejects_short_password_from_stdin(db_url):
    r = _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
             stdin="short12\n")
    assert r.returncode == 1
    assert "at least 8 characters" in r.stderr


def test_setup_refuses_when_admin_exists(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "setup", "--username", "second", "--password-stdin",
             stdin="another long passphrase\n")
    assert r.returncode == 1
    assert "already exists" in r.stderr


def test_setup_token_refused_once_initialized(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "setup-token")
    assert r.returncode == 1
    assert "already exists" in r.stderr


def test_reset_password_changes_it(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "reset-password", "--password-stdin",
             stdin="recovered by the operator\n")
    assert r.returncode == 0, r.stderr
    assert "reset" in r.stdout
    # Explicitly reassures the operator nothing else moved.
    assert "API keys" in r.stdout


def test_reset_password_rejects_weak(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "reset-password", "--password-stdin", stdin="short12\n")
    assert r.returncode == 1


def test_reset_password_without_admin_fails(db_url):
    r = _run(db_url, "reset-password", "--password-stdin",
             stdin="recovered by the operator\n")
    assert r.returncode == 1
    assert "No administrator exists" in r.stderr


def test_reset_password_rejects_wrong_username(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "reset-password", "--username", "someone-else",
             "--password-stdin", stdin="recovered by the operator\n")
    assert r.returncode == 1
    assert "geeklocal" in r.stderr


def test_no_password_flag_exists():
    """Accepting `--password VALUE` would put the secret in shell history and
    `ps` output. The flag must not exist at all."""
    r = _run("sqlite+aiosqlite:///:memory:", "reset-password", "--password", "x")
    assert r.returncode == 2  # argparse: unrecognized arguments
    assert "unrecognized" in r.stderr.lower() or "invalid" in r.stderr.lower()


def test_revoke_sessions(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "revoke-sessions")
    assert r.returncode == 0, r.stderr
    assert "Revoked" in r.stdout


def test_reset_password_leaves_provider_keys_and_api_keys_alone(db_url):
    """The recovery path must not disturb anything but the password."""
    import asyncio

    from sqlalchemy import select

    from packages.db.engine import build_engine
    from packages.db.models.api_key import ApiKey
    from packages.db.models.provider_key import ProviderKey

    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")

    async def seed():
        engine = build_engine(db_url)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from packages.auth.encryption import encrypt_credential
        from packages.db.models.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            s.add(ProviderKey(
                provider="openai",
                encrypted_key=encrypt_credential("sk-openai-existing-key"),
                key_prefix="sk-open...key",
            ))
            from app.seed import seed_initial_state

            await seed_initial_state(s)
            await s.commit()
        async with factory() as s:
            providers = [(r.provider, r.encrypted_key) for r in
                         (await s.execute(select(ProviderKey))).scalars()]
            keys = [(r.id, r.key_hash) for r in
                    (await s.execute(select(ApiKey))).scalars()]
        await engine.dispose()
        return providers, keys

    before_providers, before_keys = asyncio.run(seed())

    r = _run(db_url, "reset-password", "--password-stdin",
             stdin="recovered by the operator\n")
    assert r.returncode == 0, r.stderr

    async def snapshot():
        engine = build_engine(db_url)
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            providers = [(r.provider, r.encrypted_key) for r in
                         (await s.execute(select(ProviderKey))).scalars()]
            keys = [(r.id, r.key_hash) for r in
                    (await s.execute(select(ApiKey))).scalars()]
        await engine.dispose()
        return providers, keys

    after_providers, after_keys = asyncio.run(snapshot())
    assert after_providers == before_providers
    assert after_keys == before_keys


def test_cli_is_not_reachable_over_http():
    """There is no importable router for the CLI — it cannot be exposed by
    accident. (The module must not define an APIRouter.)"""
    import app.admin_cli as cli

    assert not hasattr(cli, "router")
    assert not hasattr(cli, "app")


def test_cli_module_runs_from_the_docker_command_shape(db_url):
    """`python -m app.admin_cli` (what the docs tell operators to run) works
    from a bare PYTHONPATH, exactly as it does inside the container."""
    r = _run(db_url, "status")
    assert r.returncode == 0
    assert "Administrator" in r.stdout


def test_password_never_echoed_by_cli(db_url):
    _run(db_url, "setup", "--username", "geeklocal", "--password-stdin",
         stdin="correct horse battery staple\n")
    r = _run(db_url, "reset-password", "--password-stdin",
             stdin="recovered by the operator\n")
    combined = r.stdout + r.stderr
    assert "recovered by the operator" not in combined
    assert "correct horse battery staple" not in combined
