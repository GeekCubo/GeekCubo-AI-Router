"""Current GeekCubo schema maintenance preserves credentials and integrity."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from packages.auth.encryption import decrypt_credential, encrypt_credential
from packages.auth.hashing import generate_api_key
from packages.db.engine import build_engine


async def test_current_schema_maintenance_preserves_credentials(tmp_sqlite_url, isolated_env, monkeypatch):
    from app import config as cfg
    from packages.db.migrate import (
        ensure_auth_columns,
        ensure_budget_columns,
        ensure_custom_provider_columns,
        ensure_quality_columns,
        ensure_routing_columns,
    )
    from packages.db.models.api_key import ApiKey
    from packages.db.models.base import Base
    from packages.db.models.provider_key import ProviderKey

    settings = cfg.Settings(_env_file=None, credential_encryption_key="ab" * 32)
    monkeypatch.setattr(cfg, "get_settings", lambda: settings)
    engine = build_engine(tmp_sqlite_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    raw_key, key_hash, key_prefix = generate_api_key()
    encrypted = encrypt_credential("provider-test-secret")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as db:
            db.add(ApiKey(id="current-key", workspace_id="default", name="current",
                          key_hash=key_hash, key_prefix=key_prefix))
            db.add(ProviderKey(id="current-provider", provider="openai",
                               encrypted_key=encrypted, key_prefix="test"))
            await db.commit()
        for _ in range(3):
            for migrate in (ensure_budget_columns, ensure_custom_provider_columns,
                            ensure_auth_columns, ensure_routing_columns, ensure_quality_columns):
                await migrate(engine)
        async with factory() as db:
            key = await db.get(ApiKey, "current-key")
            provider = await db.get(ProviderKey, "current-provider")
            assert raw_key.startswith("sk-geek-")
            assert key.key_hash == key_hash
            assert key.key_prefix == key_prefix
            assert key.expires_at is None
            assert provider.encrypted_key == encrypted
            assert decrypt_credential(provider.encrypted_key) == "provider-test-secret"
        async with engine.connect() as conn:
            assert (await conn.execute(text("PRAGMA integrity_check"))).scalar_one() == "ok"
    finally:
        await engine.dispose()
