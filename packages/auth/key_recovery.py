"""Sealing and opening the copyable copy of sk-geek-* keys.

AES-256-GCM (authenticated encryption) with a dedicated key,
``API_KEY_RECOVERY_KEY``, kept separate from ``CREDENTIAL_ENCRYPTION_KEY``.
The API-key row id is bound as associated data, so a ciphertext copied onto
another row does not open.

Format: ``b"\\x01" + nonce(12) + ciphertext+tag``.

There is deliberately no development fallback: without a configured key, new
keys are stored hash-only instead of being sealed with a publicly-known value.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from packages.auth.encryption import materialize_encryption_key

VERSION_BYTE = b"\x01"
_NONCE_LEN = 12
_AAD_PREFIX = b"geekcubo-api-key:"


class RecoveryUnavailable(RuntimeError):
    """No API_KEY_RECOVERY_KEY is configured."""


def _key() -> bytes:
    value = ""
    try:
        from app.config import get_settings

        value = get_settings().api_key_recovery_key or ""
    except Exception:
        pass
    if not value:
        value = os.environ.get("API_KEY_RECOVERY_KEY", "")
    if not value:
        raise RecoveryUnavailable(
            "API_KEY_RECOVERY_KEY is not configured, so recoverable keys are unavailable."
        )
    return materialize_encryption_key(value)


def recovery_available() -> bool:
    try:
        _key()
    except RecoveryUnavailable:
        return False
    return True


def seal_api_key(plaintext: str, key_id: str) -> bytes:
    nonce = os.urandom(_NONCE_LEN)
    aad = _AAD_PREFIX + key_id.encode("utf-8")
    return VERSION_BYTE + nonce + AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), aad)


def open_api_key(blob: bytes, key_id: str) -> str:
    """Decrypt a stored copy. Raises on a wrong key, a wrong row or tampering."""
    if not blob or blob[:1] != VERSION_BYTE or len(blob) < 1 + _NONCE_LEN + 16:
        raise ValueError("unsupported recoverable-key ciphertext")
    aad = _AAD_PREFIX + key_id.encode("utf-8")
    return AESGCM(_key()).decrypt(blob[1:1 + _NONCE_LEN], blob[1 + _NONCE_LEN:], aad).decode("utf-8")
