"""Administrator password hashing and policy.

Argon2id via argon2-cffi with memory-hard parameters: a local dashboard gets
few logins, so the per-verify cost (~100ms, 64 MiB) is irrelevant to usability
and expensive for anyone who walks off with the SQLite file.

No PBKDF2/bcrypt fallback: a silent downgrade is worse than a hard import
failure, and the dependency is a hard requirement of this package.
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# OWASP-recommended Argon2id baseline (m=64 MiB, t=3, p=4). Encoded into each
# stored PHC string, so raising these later still verifies old hashes and
# `needs_rehash` upgrades them on the next successful login.
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Password policy: a length floor and nothing else. Composition rules
# (mixed case, digits, symbols) are not required — they push operators toward
# short, guessable, scribbled-down strings.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256

# A short list of passwords that are long enough to pass the length check but
# are still the first thing anyone tries. Not a real dictionary attack — that
# would need a file we cannot ship — just a cheap guard against the obvious.
_COMMON_PASSWORDS = {
    "password1234", "password12345", "123456789012", "qwertyuiop12",
    "letmein12345", "administrator", "changeme1234", "passwordpassword",
    "iloveyou1234", "welcome12345", "adminadmin12", "geekcubo12",
    "geekcubolite", "password123!", "Password123!", "qwerty123456",
}

REDACTED = "[REDACTED]"


class PasswordPolicyError(ValueError):
    """A candidate password fails policy. Message is safe to show to the user."""


def hash_password(password: str) -> str:
    """Return an Argon2id PHC string. Never store the plaintext."""
    return _HASHER.hash(_check_bounds(password))


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-shape verification. False on mismatch or a corrupt hash."""
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash predates the current cost parameters."""
    try:
        return _HASHER.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# A real hash of a throwaway value. Login verifies against this when the
# username does not exist, so a missing account costs the same wall-clock time
# as a wrong password and cannot be distinguished by timing.
_DUMMY_HASH = _HASHER.hash("timing-equalization-placeholder-value")


def burn_verification_time(password: str) -> None:
    """Perform a throwaway verification to equalize failure timing."""
    try:
        _HASHER.verify(_DUMMY_HASH, (password or "")[:MAX_PASSWORD_LENGTH])
    except Exception:
        pass


def _check_bounds(password: str) -> str:
    if not isinstance(password, str):
        raise PasswordPolicyError("Password must be text.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
        )
    return password


def validate_new_password(password: str, *, username: str = "") -> None:
    """Raise PasswordPolicyError when `password` is unacceptable.

    Messages are actionable and never echo the password itself.
    """
    _check_bounds(password)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if password.strip() == "":
        raise PasswordPolicyError("Password cannot be blank.")
    if password.strip().lower() in _COMMON_PASSWORDS:
        raise PasswordPolicyError(
            "That password is too common. Choose something unique to this installation."
        )
    # Single repeated character ("aaaaaaaaaaaa") passes a length check alone.
    if len(set(password)) == 1:
        raise PasswordPolicyError(
            "Password cannot be a single repeated character."
        )
    if username and password.strip().lower() == username.strip().lower():
        raise PasswordPolicyError("Password cannot be the same as the username.")
    if username and len(password) >= MIN_PASSWORD_LENGTH:
        # A password that literally contains the username is trivially guessed.
        if username.strip().lower() in password.strip().lower() and len(username.strip()) >= 4:
            raise PasswordPolicyError(
                "Password cannot contain the username."
            )


def password_strength_hint() -> str:
    """One-line policy summary for the UI."""
    return f"Minimum {MIN_PASSWORD_LENGTH} characters"


_SAFE_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]*$")


def validate_username(username: str) -> str:
    """Normalize + validate the administrator username."""
    value = (username or "").strip()
    if not value:
        raise PasswordPolicyError("Username is required.")
    if len(value) > 64:
        raise PasswordPolicyError("Username must be at most 64 characters.")
    if not _SAFE_USERNAME.match(value):
        raise PasswordPolicyError(
            "Username may contain letters, digits, and . _ @ + - only, and must "
            "start with a letter or digit."
        )
    return value
