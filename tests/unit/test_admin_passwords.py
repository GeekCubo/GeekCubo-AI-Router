"""Password hashing and policy."""

from __future__ import annotations

import pytest

from packages.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordPolicyError,
    hash_password,
    needs_rehash,
    password_strength_hint,
    validate_new_password,
    validate_username,
    verify_password,
)

GOOD = "correct horse battery staple"


def test_argon2id_is_used():
    digest = hash_password(GOOD)
    assert digest.startswith("$argon2id$")
    # Never the plaintext, and not a bare digest.
    assert GOOD not in digest


def test_hash_is_salted_per_call():
    assert hash_password(GOOD) != hash_password(GOOD)


def test_verify_round_trip():
    digest = hash_password(GOOD)
    assert verify_password(digest, GOOD) is True
    assert verify_password(digest, GOOD + "x") is False


def test_verify_rejects_corrupt_hash_without_raising():
    for bad in ("", "not-a-hash", "$argon2id$v=19$m=1,t=1,p=1$ZZ$ZZ"):
        assert verify_password(bad, GOOD) is False


def test_needs_rehash_false_for_current_params():
    assert needs_rehash(hash_password(GOOD)) is False


def test_needs_rehash_true_for_garbage():
    assert needs_rehash("garbage") is True


@pytest.mark.parametrize("password", [
    "",
    "short",
    "1234567",
    "a" * (MIN_PASSWORD_LENGTH - 1),
    "            ",          # whitespace only
    "a" * 40,                # single repeated character
])
def test_weak_passwords_rejected(password):
    with pytest.raises(PasswordPolicyError):
        validate_new_password(password)


@pytest.mark.parametrize("password", ["password1234", "Password123!", "changeme1234"])
def test_common_passwords_rejected(password):
    with pytest.raises(PasswordPolicyError, match="too common"):
        validate_new_password(password)


def test_minimum_length_is_eight():
    assert MIN_PASSWORD_LENGTH == 8


@pytest.mark.parametrize("password", [
    "12345678",          # digits only — accepted
    "abcdefgh",          # lowercase only — accepted
    "ABCDEFGH",          # uppercase only — accepted
    "!@#$%^&*",          # symbols only — accepted
    # NB: a single repeated character ("!!!!!!!!") is still rejected by the
    # general anti-guessing safeguard, which applies regardless of length.
    "password",          # no composition, 8 chars — accepted
    "correct horse",     # space-separated, no digits — accepted
])
def test_no_composition_requirements(password):
    """Length is the only rule: no mandatory character classes."""
    validate_new_password(password)


def test_long_passphrase_accepted():
    phrase = " ".join(["correct", "horse"] * 10)
    validate_new_password(phrase)  # must not raise
    assert len(phrase) > 100


def test_max_length_enforced():
    with pytest.raises(PasswordPolicyError, match="at most"):
        validate_new_password("a1" * (MAX_PASSWORD_LENGTH // 2 + 1))


def test_password_cannot_equal_username():
    with pytest.raises(PasswordPolicyError):
        validate_new_password("administrator", username="administrator")


def test_password_cannot_contain_username():
    with pytest.raises(PasswordPolicyError, match="contain the username"):
        validate_new_password("adminadminadmin123", username="adminadmin")


def test_short_username_is_not_substring_checked():
    """A 3-letter username appears in far too many good passphrases."""
    validate_new_password(GOOD, username="adm")


def test_strength_hint_mentions_the_minimum():
    assert str(MIN_PASSWORD_LENGTH) in password_strength_hint()


@pytest.mark.parametrize("username", ["admin", "ops.user", "a_b-c", "x@y.com", "root+1"])
def test_valid_usernames(username):
    assert validate_username(username) == username


@pytest.mark.parametrize("username", ["", "   ", "with space", ".dot",
                                     "a" * 65, "emoji🙂"])
def test_invalid_usernames(username):
    with pytest.raises(PasswordPolicyError):
        validate_username(username)


def test_username_is_stripped():
    # Surrounding whitespace is normalised away rather than rejected: a paste
    # from a terminal routinely carries it, and the stored value is trimmed.
    assert validate_username("  admin  ") == "admin"


async def test_dummy_hash_timing_is_comparable():
    """Unknown-user logins must not be measurably faster than real ones."""
    import time

    from packages.auth.passwords import burn_verification_time

    start = time.perf_counter()
    burn_verification_time("anything")
    elapsed = time.perf_counter() - start
    # Argon2id at m=64MiB/t=3 lands in the tens of milliseconds; the floor here
    # exists to catch a "return immediately" regression, not to be tight.
    assert elapsed > 0.001
