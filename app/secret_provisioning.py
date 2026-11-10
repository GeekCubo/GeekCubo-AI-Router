"""First-run secret provisioning for the credential-encryption key and pepper.

GeekCubo seals provider/AA credentials at rest with ``CREDENTIAL_ENCRYPTION_KEY``
and hashes inference keys with ``API_KEY_PEPPER``. Asking an operator to
generate those by hand is friction a fresh install should not have, so on first
boot the app generates them, stores them next to the database, and reuses them
on every later start.

Safety rules:

* Idempotent — if either value is already configured (environment or ``.env``),
  nothing is generated, and a configured value is never overwritten.
* Persistent — secrets are written to a ``.geekcubo-secrets`` file in the same
  directory as the SQLite database (so the Docker volume mount keeps them with
  the data), mode ``0o600``, created atomically so concurrent workers never
  clobber each other.
* No silent data loss — if the database already contains encrypted records but
  no key is configured and no secrets file exists, provisioning refuses to
  invent a key (which could never decrypt the existing ciphertext) and raises a
  clear recovery message instead.
* Secrets are never printed or logged. Only a "generated" / "loaded" event with
  no values is emitted.

Non-SQLite databases have no obvious local file location, so provisioning is
skipped there and the operator must set the values explicitly (unchanged
behaviour, now documented).
"""

from __future__ import annotations

import logging
import os
import secrets as _secrets
from pathlib import Path

# stdlib logging (not structlog): this module runs in the server lifespan AND
# in `app.admin_cli`, where structlog is unconfigured and its default
# PrintLogger would write to stdout — corrupting the CLI's machine-readable
# `setup-token` payload. stdlib logging's default handler writes to stderr, so
# a "secrets generated" event can never leak into a parsed stdout value.
logger = logging.getLogger("geekcubo.secrets")

SECRETS_FILENAME = ".geekcubo-secrets"
_KEY_VAR = "CREDENTIAL_ENCRYPTION_KEY"
_PEPPER_VAR = "API_KEY_PEPPER"
# Dedicated key that seals the copyable copy of sk-geek-* keys. Generated alongside the
# other two, but provisioned independently: an install upgraded from a release
# without it gains it on the next start, and nothing else changes.
_RECOVERY_VAR = "API_KEY_RECOVERY_KEY"
_FIELDS = {
    _KEY_VAR: "credential_encryption_key",
    _PEPPER_VAR: "api_key_pepper",
    _RECOVERY_VAR: "api_key_recovery_key",
}


def _sqlite_dir(database_url: str) -> Path | None:
    """Parent directory of a SQLite database file, or None for non-SQLite.

    Handles ``sqlite+aiosqlite:///./geekcubo.db`` and
    ``sqlite+aiosqlite:////data/geekcubo.db`` (both 3 and 4 slash forms).
    """
    if not database_url.startswith("sqlite"):
        return None
    rest = database_url.split("sqlite", 1)[1]
    # rest is like "+aiosqlite:///./geekcubo.db" or ":///data/geekcubo.db"
    path_part = rest.split("///", 1)[-1] if "///" in rest else ""
    if not path_part:
        return None
    # Strip query/fragment.
    path_part = path_part.split("?", 1)[0].split("#", 1)[0]
    p = Path(path_part)
    if p.name in ("", ":memory:"):
        return None
    parent = p.parent
    return parent if str(parent) else Path(".")


def _secrets_path(database_url: str) -> Path | None:
    d = _sqlite_dir(database_url)
    return d / SECRETS_FILENAME if d is not None else None


def _read_secrets_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _atomic_write_secrets(path: Path, values: dict[str, str]) -> None:
    """Write secrets atomically with 0600 perms, tolerating a concurrent write.

    Two workers starting together may both see the file as missing. One creates
    it; the other reads the winner's file instead of overwriting it. The
    temp-file + ``os.link`` step makes the write atomic (never visible partially
    written) and fails if the file already exists, so a slow worker cannot
    clobber a fresh one.
    """
    body = "".join(f"{k}={v}\n" for k, v in sorted(values.items()))
    # Write the full body to a private temp file first, then hard-link it into
    # place: link() fails if the target exists (same guarantee as O_EXCL), and
    # the target is never visible half-written to a concurrent reader.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{_secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass  # someone else already wrote it; read theirs instead
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _append_secrets(path: Path, values: dict[str, str]) -> None:
    """Add new KEY=value lines to an existing secrets file, keeping the rest.

    Rewritten atomically (temp file + rename) with the original lines first and
    unchanged, so an existing CREDENTIAL_ENCRYPTION_KEY or API_KEY_PEPPER can
    never be altered by an upgrade. Keys already present are never replaced.
    """
    current = _read_secrets_file(path)
    additions = {k: v for k, v in values.items() if k not in current}
    if not additions:
        return
    original = path.read_text(encoding="utf-8")
    if original and not original.endswith("\n"):
        original += "\n"
    body = original + "".join(f"{k}={v}\n" for k, v in sorted(additions.items()))
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{_secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _configured() -> dict[str, str]:
    """Which of the managed secrets are already present (env or .env)."""
    out: dict[str, str] = {}
    for var, field in _FIELDS.items():
        value = os.environ.get(var, "")
        if value:
            out[var] = value
        else:
            try:
                from app.config import get_settings

                s = get_settings()
                value = getattr(s, field, "") or ""
                if value:
                    out[var] = value
            except Exception:
                pass
    return out


async def _encrypted_records_exist(engine) -> bool:
    """True when any table holds ciphertext sealed with the credential key."""
    from sqlalchemy import select

    from packages.db.models.custom_provider import CustomProvider
    from packages.db.models.metadata_source import MetadataSource
    from packages.db.models.provider_key import ProviderKey
    from packages.db.models.quality_settings import QualitySettings

    async with engine.connect() as conn:
        for model, col in (
            (ProviderKey, ProviderKey.encrypted_key),
            (CustomProvider, CustomProvider.encrypted_key),
            (QualitySettings, QualitySettings.encrypted_api_key),
            (MetadataSource, MetadataSource.encrypted_token),
        ):
            try:
                row = (await conn.execute(
                    select(model.id).where(col.isnot(None)).limit(1)
                )).first()
            except Exception:
                # Table missing (partial upgrade) — treat as no records;
                # the migration layer and drift check run first.
                continue
            if row is not None:
                return True
    return False


async def _recoverable_keys_exist(engine) -> bool:
    """True when any API key row carries a recoverable (encrypted) copy."""
    from sqlalchemy import select

    from packages.db.models.api_key import ApiKey

    async with engine.connect() as conn:
        try:
            row = (await conn.execute(
                select(ApiKey.id).where(ApiKey.encrypted_secret.isnot(None)).limit(1)
            )).first()
        except Exception:
            return False
    return row is not None


async def provision_secrets(settings, engine) -> None:
    """Generate or load the credential key + pepper for a fresh install.

    Awaited from the server lifespan and the admin CLI, both of which already
    run inside an event loop. Call after ``create_all`` + migrations, before
    the encryption guards, so the guards see a real key (not the dev fallback)
    on a fresh database.

    Idempotent and side-effect-free when secrets are already configured; raises
    ``RuntimeError`` only in the "existing ciphertext but no key" case.
    """
    existing = _configured()
    if all(var in existing for var in _FIELDS):
        return  # fully configured — nothing to do

    path = _secrets_path(settings.database_url)
    if path is None:
        # Non-SQLite: leave manual configuration to the operator. If they
        # already set one of the two, nothing we can safely add here.
        return

    if _KEY_VAR in existing and _PEPPER_VAR in existing and not path.exists():
        # The operator manages secrets explicitly (.env / environment) and has
        # no secrets file. Do not create one just for the optional recovery
        # key: recoverable keys stay unavailable until API_KEY_RECOVERY_KEY is
        # set the same way.
        return

    loaded: dict[str, str] = {}
    if path.exists():
        loaded = _read_secrets_file(path)

    # Reuse whatever the file already has for the missing values.
    for var in _FIELDS:
        if var not in existing and var in loaded:
            os.environ[var] = loaded[var]

    # Re-check after loading the file: maybe the file supplied everything.
    still_missing = [v for v in _FIELDS
                     if v not in existing and not os.environ.get(v)]

    if not still_missing:
        if loaded:
            logger.info("geekcubo_secrets_loaded")
        return

    # We need to generate at least one secret. If the database already has
    # ciphertext but no key exists, inventing one would orphan that data.
    if _RECOVERY_VAR in still_missing and await _recoverable_keys_exist(engine):
        raise RuntimeError(
            "API_KEY_RECOVERY_KEY is missing but the database holds recoverable "
            "API keys sealed with it. Refusing to generate a new key that could "
            "never open them. Restore API_KEY_RECOVERY_KEY from backup (the "
            ".geekcubo-secrets file or .env)."
        )
    if _KEY_VAR in still_missing and await _encrypted_records_exist(engine):
        raise RuntimeError(
            "Credential secrets are missing but the database already contains "
            "encrypted records. Refusing to generate a new key that could "
            "never decrypt them. Restore CREDENTIAL_ENCRYPTION_KEY (and "
            "API_KEY_PEPPER) from backup, or remove the .geekcubo-secrets "
            "file only if you are certain the data is disposable."
        )

    generated = {v: _secrets.token_hex(32) for v in still_missing}
    if loaded:
        # Upgrade: the file exists but predates a newly managed secret. Add the
        # missing value without touching the existing ones (see _append_secrets).
        _append_secrets(path, generated)
    else:
        _atomic_write_secrets(path, {**_configured(), **loaded, **generated})
    # Read back what actually landed (a concurrent worker may have won the
    # write), so every worker uses identical secrets.
    final = _read_secrets_file(path)
    for var in still_missing:
        os.environ[var] = final.get(var, generated[var])
    logger.info("geekcubo_secrets_generated count=%d", len(still_missing))
