"""Router cache: deployment-list assembly.

These tests pin the contract of `build_deployments` without instantiating
litellm.Router (covered by integration tests). Pure-Python is the right
shape for TDD on this layer.
"""

from __future__ import annotations


def test_no_keys_no_deployments():
    """Empty inputs → empty deployment list."""
    from app.config import Settings
    from app.router_cache import build_deployments

    s = Settings(_env_file=None)
    assert build_deployments(env_keys={}, db_keys=[], settings=s) == []


def test_env_openai_key_creates_deployments_per_openai_model():
    """An env-sourced openai key creates one deployment per OpenAI catalog entry."""
    from app.config import Settings
    from app.router_cache import build_deployments
    from packages.litellm_adapter.catalog import models_for_provider

    s = Settings(_env_file=None)
    deps = build_deployments(env_keys={"openai": "sk-x"}, db_keys=[], settings=s)

    expected = {m.id for m in models_for_provider("openai")}
    actual = {d.model_name for d in deps if d.provider == "openai"}
    assert actual == expected
    for d in deps:
        assert d.api_key == "sk-x"
        assert d.litellm_model.startswith("openai/")


def test_env_keys_for_multiple_providers_combine():
    from app.config import Settings
    from app.router_cache import build_deployments

    s = Settings(_env_file=None)
    deps = build_deployments(
        env_keys={"openai": "sk-o", "anthropic": "sk-a"},
        db_keys=[],
        settings=s,
    )
    providers = {d.provider for d in deps}
    assert providers == {"openai", "anthropic"}


def test_db_provider_key_takes_precedence_over_env():
    """If both env and DB set a provider key, DB wins (UI-edited keys are authoritative)."""
    from app.config import Settings
    from app.router_cache import build_deployments
    from packages.auth.encryption import encrypt_credential
    from packages.db.models.provider_key import ProviderKey

    s = Settings(_env_file=None)
    db_row = ProviderKey(
        provider="openai",
        encrypted_key=encrypt_credential("sk-from-db"),
        key_prefix="sk-from-...",
        label="default",
        is_enabled=True,
    )

    deps = build_deployments(
        env_keys={"openai": "sk-from-env"},
        db_keys=[db_row],
        settings=s,
    )
    openai_deps = [d for d in deps if d.provider == "openai"]
    assert openai_deps  # at least one
    assert all(d.api_key == "sk-from-db" for d in openai_deps)


def test_disabled_db_provider_key_is_skipped():
    from app.config import Settings
    from app.router_cache import build_deployments
    from packages.auth.encryption import encrypt_credential
    from packages.db.models.provider_key import ProviderKey

    s = Settings(_env_file=None)
    db_row = ProviderKey(
        provider="openai",
        encrypted_key=encrypt_credential("sk-disabled"),
        key_prefix="sk-...",
        label="default",
        is_enabled=False,
    )
    deps = build_deployments(env_keys={}, db_keys=[db_row], settings=s)
    assert deps == []


def test_build_deployments_logs_undecryptable_rows(caplog):
    """Issue #137: decrypt failures must not be a silent `continue`.
    The row is still skipped (env fallback stays available) but a
    warning names the provider so operators can see the rotation."""
    import logging

    from app.config import Settings
    from app.router_cache import build_deployments
    from packages.db.models.provider_key import ProviderKey

    s = Settings(_env_file=None)
    caplog.set_level(logging.WARNING, logger="geekcubo.router")
    deps = build_deployments(
        env_keys={},
        db_keys=[
            ProviderKey(
                provider="openai",
                encrypted_key=b"too-short-to-be-valid-aesgcm",
                key_prefix="sk-...",
                label="default",
                is_enabled=True,
            )
        ],
        settings=s,
    )
    assert deps == []
    assert "openai" in caplog.text
    assert "CREDENTIAL_ENCRYPTION_KEY" in caplog.text


def test_usable_providers_from_db_skips_undecryptable_rows():
    """Helper that mirrors build_deployments' decryption filter so callers
    reporting 'configured providers' (e.g. /v1/analytics/unreachable) can't
    drift from what the router actually deploys."""
    from app.router_cache import usable_providers_from_db
    from packages.auth.encryption import encrypt_credential
    from packages.db.models.provider_key import ProviderKey

    rows = [
        ProviderKey(
            provider="openai",
            encrypted_key=encrypt_credential("sk-good"),
            key_prefix="sk-...", label="default", is_enabled=True,
        ),
        ProviderKey(
            provider="anthropic",
            encrypted_key=b"corrupt-blob-cant-decrypt",
            key_prefix="sk-ant-...", label="default", is_enabled=True,
        ),
        ProviderKey(
            provider="google",
            encrypted_key=encrypt_credential("sk-disabled"),
            key_prefix="sk-...", label="default", is_enabled=False,
        ),
    ]
    assert usable_providers_from_db(rows) == {"openai"}
