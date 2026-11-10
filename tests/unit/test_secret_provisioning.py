"""Automatic credential-encryption secret provisioning.

Covers fresh install (generates both secrets), restart idempotency (reuses the
file), existing-config preservation (never overwrites), and the fail-safe that
refuses to invent a key when encrypted records already exist.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app import secret_provisioning as sp


@pytest.fixture(autouse=True)
def _clear_env_and_settings(monkeypatch, tmp_path):
    # The repo .env may hold real secrets; chdir into a temp dir so Settings'
    # env_file=".env" (CWD-relative) never loads them, and strip the two vars.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(sp._KEY_VAR, raising=False)
    monkeypatch.delenv(sp._PEPPER_VAR, raising=False)
    monkeypatch.delenv(sp._RECOVERY_VAR, raising=False)
    from app import config as cfg

    cfg.get_settings.cache_clear()
    yield
    cfg.get_settings.cache_clear()


def test_sqlite_dir_handles_relative_and_absolute(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # Relative path: sqlite+aiosqlite:///./geekcubo.db -> the CWD.
    p = sp._sqlite_dir("sqlite+aiosqlite:///./geekcubo.db")
    assert p == Path(".")
    # Absolute path: sqlite+aiosqlite:////data/geekcubo.db -> /data.
    assert sp._sqlite_dir("sqlite+aiosqlite:////data/geekcubo.db") == Path("/data")
    # Non-SQLite -> None.
    assert sp._sqlite_dir("postgresql+asyncpg://u:p@h/db") is None


def test_fresh_install_generates_both_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()

    # No engine: pass None; _encrypted_records_exist is only called for the
    # key, and with no engine we won't generate. Give it a real engine instead.
    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(settings.database_url)
    try:
        import asyncio

        async def _mk():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(_mk())

        asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        import asyncio

        asyncio.run(engine.dispose())

    key = os.environ[sp._KEY_VAR]
    pepper = os.environ[sp._PEPPER_VAR]
    assert len(key) == 64  # 32 bytes hex-encoded
    assert len(pepper) == 64
    assert key != pepper  # independent randomness

    # The secrets file exists, mode 0600, and matches the env.
    path = tmp_path / sp.SECRETS_FILENAME
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    lines = sp._read_secrets_file(path)
    assert lines[sp._KEY_VAR] == key
    assert lines[sp._PEPPER_VAR] == pepper


def test_restart_does_not_regenerate(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()

    # First write a secrets file manually, then "restart" (clear env) and
    # confirm provisioning loads it without changing it.
    path = tmp_path / sp.SECRETS_FILENAME
    original_key = "ab" * 32
    original_pepper = "cd" * 32
    sp._atomic_write_secrets(
        path, {sp._KEY_VAR: original_key, sp._PEPPER_VAR: original_pepper}
    )

    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(settings.database_url)
    import asyncio

    async def _mk():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_mk())
    try:
        asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())

    assert os.environ[sp._KEY_VAR] == original_key
    assert os.environ[sp._PEPPER_VAR] == original_pepper
    assert sp._read_secrets_file(path)[sp._KEY_VAR] == original_key


def test_existing_env_secret_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    monkeypatch.setenv(sp._KEY_VAR, "ef" * 32)
    monkeypatch.setenv(sp._PEPPER_VAR, "fe" * 32)
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()

    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(settings.database_url)
    import asyncio

    async def _mk():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_mk())
    try:
        asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())

    assert os.environ[sp._KEY_VAR] == "ef" * 32
    assert os.environ[sp._PEPPER_VAR] == "fe" * 32
    # No secrets file was created for a fully-configured install.
    assert not (tmp_path / sp.SECRETS_FILENAME).exists()


def test_missing_key_with_existing_ciphertext_fails_safely(tmp_path, monkeypatch):
    """Refuse to invent a key that could never decrypt existing records."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()

    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(settings.database_url)
    import asyncio

    async def _mk():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed a provider key (ciphertext) so the guard must trip.
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO provider_keys (id, provider, encrypted_key, key_prefix) "
                "VALUES ('p1','openai', X'01020304', 'sk-...')"
            ))

    asyncio.run(_mk())
    try:
        with pytest.raises(RuntimeError, match="already contains encrypted records"):
            asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())


def test_generated_key_decrypts_ciphertext_roundtrip(tmp_path, monkeypatch):
    """The auto-generated key is a real, usable encryption key."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()

    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(settings.database_url)
    import asyncio

    async def _mk():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_mk())
    try:
        asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())

    from packages.auth.encryption import decrypt_credential, encrypt_credential

    blob = encrypt_credential("secret-value-1234")
    assert decrypt_credential(blob) == "secret-value-1234"


def test_server_lifespan_boots_fresh_install_without_secrets(tmp_path, monkeypatch):
    """A clean install with no key or pepper configured must boot.

    Regression: provisioning ran ``asyncio.run`` from inside the server
    lifespan's event loop, so the very first boot crashed with
    "asyncio.run() cannot be called from a running event loop".
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    from app.main import create_app

    app = create_app()

    async def _boot():
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(_boot())

    path = tmp_path / sp.SECRETS_FILENAME
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    stored = sp._read_secrets_file(path)
    assert stored[sp._KEY_VAR] == os.environ[sp._KEY_VAR]
    assert stored[sp._PEPPER_VAR] == os.environ[sp._PEPPER_VAR]
    assert stored[sp._KEY_VAR] != stored[sp._PEPPER_VAR]


def test_admin_cli_provisions_on_fresh_install(tmp_path, monkeypatch):
    """The admin CLI path also awaits provisioning inside its own loop."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    from app import admin_cli

    async def _noop(_session):
        return 0

    asyncio.run(admin_cli._with_db(_noop))
    assert (tmp_path / sp.SECRETS_FILENAME).exists()


def test_atomic_write_never_overwrites_and_leaves_no_temp(tmp_path):
    path = tmp_path / sp.SECRETS_FILENAME
    sp._atomic_write_secrets(path, {sp._KEY_VAR: "a" * 64, sp._PEPPER_VAR: "b" * 64})
    sp._atomic_write_secrets(path, {sp._KEY_VAR: "c" * 64, sp._PEPPER_VAR: "d" * 64})
    assert sp._read_secrets_file(path)[sp._KEY_VAR] == "a" * 64
    assert (path.stat().st_mode & 0o777) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == [sp.SECRETS_FILENAME]


def _engine_with_tables(url):
    import asyncio

    import packages.db.models  # noqa: F401
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(url)

    async def _mk():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_mk())
    return engine


def test_upgrade_adds_recovery_key_without_touching_existing_secrets(tmp_path, monkeypatch):
    """A secrets file from an older release gains API_KEY_RECOVERY_KEY only."""
    import asyncio

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()
    path = tmp_path / sp.SECRETS_FILENAME
    sp._atomic_write_secrets(path, {sp._KEY_VAR: "ab" * 32, sp._PEPPER_VAR: "cd" * 32})
    before = path.read_text()

    engine = _engine_with_tables(settings.database_url)
    try:
        asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())

    after = path.read_text()
    assert after.startswith(before)  # existing lines unchanged, in place
    values = sp._read_secrets_file(path)
    assert values[sp._KEY_VAR] == "ab" * 32 and values[sp._PEPPER_VAR] == "cd" * 32
    assert len(values[sp._RECOVERY_VAR]) == 64
    assert os.environ[sp._RECOVERY_VAR] == values[sp._RECOVERY_VAR]
    assert (path.stat().st_mode & 0o777) == 0o600


def test_missing_recovery_key_with_recoverable_rows_fails_safely(tmp_path, monkeypatch):
    import asyncio

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/geekcubo.db")
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.get_settings()
    # An install whose secrets file lost its recovery key.
    path = tmp_path / sp.SECRETS_FILENAME
    sp._atomic_write_secrets(path, {sp._KEY_VAR: "ef" * 32, sp._PEPPER_VAR: "fe" * 32})
    engine = _engine_with_tables(settings.database_url)

    async def _seed():
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("insert into workspaces (id, name, slug) values ('default', 'd', 'd')"))
            await conn.execute(text(
                "insert into api_keys (id, workspace_id, name, key_hash, key_prefix, is_deleted, "
                "spent_microcents, encrypted_secret) values "
                "('k1', 'default', 'k', 'h', 'sk-geek-....0000', 0, 0, x'01')"))

    try:
        asyncio.run(_seed())
        with pytest.raises(RuntimeError, match="API_KEY_RECOVERY_KEY"):
            asyncio.run(sp.provision_secrets(settings, engine))
    finally:
        asyncio.run(engine.dispose())
    assert sp._RECOVERY_VAR not in sp._read_secrets_file(path)
