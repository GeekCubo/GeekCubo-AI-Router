"""Tests for authenticated, versioned GeekCubo credential ciphertext."""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag


@pytest.fixture
def hex_key(monkeypatch):
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    from app import config as cfg

    cfg.get_settings.cache_clear()
    settings = cfg.Settings(_env_file=None, credential_encryption_key="ab" * 32)
    monkeypatch.setattr(cfg, "get_settings", lambda: settings)
    return bytes.fromhex("ab" * 32)


def test_encrypt_produces_versioned_blob(hex_key):
    from packages.auth.encryption import VERSION_BYTE, decrypt_credential, encrypt_credential

    blob = encrypt_credential("sk-secret")
    assert blob[:1] == VERSION_BYTE
    assert len(blob) == 1 + 12 + len(b"sk-secret") + 16
    assert decrypt_credential(blob) == "sk-secret"


@pytest.mark.parametrize("version", [b"\x00", b"\x02", b"\xff"])
def test_unknown_ciphertext_version_is_rejected(hex_key, version):
    from packages.auth.encryption import decrypt_credential, encrypt_credential

    blob = encrypt_credential("sk-secret")
    with pytest.raises(InvalidTag, match="unsupported ciphertext version"):
        decrypt_credential(version + blob[1:])


def test_ciphertext_tampering_is_rejected(hex_key):
    from packages.auth.encryption import decrypt_credential, encrypt_credential

    blob = encrypt_credential("sk-secret")
    with pytest.raises(InvalidTag):
        decrypt_credential(blob[:-1] + bytes([blob[-1] ^ 1]))


def test_wrong_key_raises_invalid_tag(hex_key):
    from packages.auth.encryption import decrypt_credential, encrypt_credential

    blob = encrypt_credential("x")
    with pytest.raises(InvalidTag):
        decrypt_credential(blob, key=bytes.fromhex("cd" * 32))


@pytest.mark.parametrize("length", [0, 1, 8, 28])
def test_truncated_blob_raises_rather_than_returning_garbage(hex_key, length):
    from packages.auth.encryption import decrypt_credential, encrypt_credential

    blob = encrypt_credential("x")
    with pytest.raises(InvalidTag):
        decrypt_credential(blob[:length])


def test_credential_is_decryptable_reports_current_key_only(hex_key, monkeypatch):
    from app import config as cfg
    from packages.auth.encryption import (
        credential_is_decryptable,
        decrypt_credential,
        encrypt_credential,
        materialize_encryption_key,
    )

    blob = encrypt_credential("sk-secret")
    assert credential_is_decryptable(blob) is True
    other = cfg.Settings(_env_file=None, credential_encryption_key="cd" * 32)
    monkeypatch.setattr(cfg, "get_settings", lambda: other)
    assert credential_is_decryptable(blob) is False
    assert decrypt_credential(blob, key=materialize_encryption_key("ab" * 32)) == "sk-secret"


def test_materialize_encryption_key_accepts_hex_and_passphrase():
    from packages.auth.encryption import materialize_encryption_key

    key = materialize_encryption_key("ab" * 32)
    assert key == bytes.fromhex("ab" * 32)
    assert len(materialize_encryption_key("not-hex-passphrase")) == 32
