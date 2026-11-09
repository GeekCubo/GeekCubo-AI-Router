"""Shared test fixtures for GeekCubo."""

import os
import tempfile
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio


@pytest.fixture(autouse=True)
def _reset_module_state() -> Generator[None, None, None]:
    """Wipe module-level singletons between tests so cache state doesn't leak."""
    yield
    try:
        from app import prompt_cache
        prompt_cache.reset_backend()
    except Exception:
        pass
    try:
        from app import router_cache
        router_cache.invalidate_router()
    except Exception:
        pass
    try:
        from packages.litellm_adapter import quality_index
        quality_index.reset_cache()
    except Exception:
        pass
    try:
        from app import quality_scores
        quality_scores.reset_metrics_cache()
    except Exception:
        pass


@pytest.fixture
def isolated_env(monkeypatch) -> Generator[None, None, None]:
    """Strip every GEEKCUBO_*/OPENAI_*/ANTHROPIC_*/etc env var before a test.

    Also blocks pydantic-settings from re-reading them out of `.env`
    on the next `Settings()` instantiation. Without this guard, tests
    asserting "no providers configured" silently pull whatever is in
    the developer's local `.env` (which usually has real keys for
    manual testing) and flake under those configurations.
    """
    drop = [
        k for k in os.environ
        if k.startswith(("OPENAI_", "ANTHROPIC_", "GOOGLE_", "GROQ_",
                         "TOGETHER_", "FIREWORKS_", "GEEKCUBO_",
                         "DATABASE_", "REDIS_", "CREDENTIAL_", "API_KEY_"))
    ]
    for k in drop:
        monkeypatch.delenv(k, raising=False)

    # Stop pydantic-settings from re-reading `.env` and undoing the
    # delenv work above. The class-level model_config dict is shared
    # across every Settings() call, so monkeypatch.setitem (which
    # restores on teardown) is the right scope.
    try:
        from app.config import Settings
        monkeypatch.setitem(Settings.model_config, "env_file", None)
    except Exception:
        pass

    # Settings is @lru_cache'd, and .env is read on the FIRST get_settings()
    # call of the process — which usually happens in an earlier test. Without
    # dropping it here, a developer .env carrying CREDENTIAL_ENCRYPTION_KEY
    # stays cached and turns fail-closed guard tests into no-ops (they passed
    # in isolation and failed in the full run). Restored on teardown so the
    # isolated settings don't leak forward either.
    from app import config as cfg

    def _clear_settings_cache() -> None:
        # Tests that monkeypatch get_settings with a plain lambda have no
        # cache_clear — that is fine, there is nothing cached to drop.
        clear = getattr(cfg.get_settings, "cache_clear", None)
        if clear is not None:
            clear()

    _clear_settings_cache()
    try:
        yield
    finally:
        _clear_settings_cache()


@pytest.fixture
def tmp_sqlite_url() -> Generator[str, None, None]:
    """Disposable SQLite URL pointing to a tempfile."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield f"sqlite+aiosqlite:///{path}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest_asyncio.fixture
async def db_session(tmp_sqlite_url) -> AsyncGenerator:
    """Initialised AsyncSession against a fresh SQLite DB with all tables created."""
    from packages.db.engine import build_engine
    from packages.db.models.base import Base

    engine = build_engine(tmp_sqlite_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()
