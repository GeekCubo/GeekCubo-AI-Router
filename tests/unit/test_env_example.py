""".env.example is the copy-and-configure template, so it must stay in step with
the real configuration schema.

* every user-configurable `Settings` field appears exactly once;
* every variable it names is one the application, Compose or installer reads;
* active (uncommented) lines are only safe, non-secret defaults that parse;
* generated secrets are never assigned an active empty value that would block
  first-run provisioning;
* Docker Compose accepts it as `.env`.

Nothing here reads or writes the owner's real `.env`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / ".env.example"

# Read by something other than `Settings`: the bundled SearXNG Compose service.
# (PUBLIC_BASE_URL is a Settings field and is also read by ./install.sh.)
NON_SETTINGS_VARS = {"SEARXNG_SECRET"}

# Settings fields deliberately left out of the template.
INTERNAL_FIELDS: set[str] = set()

SECRETS = {"CREDENTIAL_ENCRYPTION_KEY", "API_KEY_PEPPER", "CREDENTIAL_ENCRYPTION_PREVIOUS_KEY"}

_LINE = re.compile(r"^(#\s*)?([A-Z][A-Z0-9_]*)=(.*)$")


def _entries() -> list[tuple[str, bool, str]]:
    """(name, active, value) for every KEY=value line, commented or not."""
    out = []
    for raw in EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = _LINE.match(raw.strip())
        if m:
            out.append((m.group(2), m.group(1) is None, m.group(3).strip()))
    return out


def _settings_vars() -> set[str]:
    from app.config import Settings

    return {name.upper() for name in Settings.model_fields}


def test_every_setting_is_listed_exactly_once():
    names = [name for name, _active, _value in _entries()]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, f"listed more than once: {duplicates}"
    missing = sorted(_settings_vars() - INTERNAL_FIELDS - set(names))
    assert not missing, f"Settings fields missing from .env.example: {missing}"


def test_no_unknown_or_obsolete_variables():
    known = _settings_vars() | NON_SETTINGS_VARS
    unknown = sorted({name for name, _a, _v in _entries()} - known)
    assert not unknown, f"variables no component reads: {unknown}"


def test_active_lines_are_safe_defaults_that_parse():
    from app.config import Settings

    active = {name: value for name, is_active, value in _entries() if is_active}
    assert active, "expected a few active defaults"
    assert not (set(active) & SECRETS), "secrets must never be active in the template"
    assert not any(n.endswith("_API_KEY") for n in active), "provider keys must stay commented"
    # Active defaults must equal the schema defaults (a copied .env changes nothing).
    fields = Settings.model_fields
    for name, value in active.items():
        default = fields[name.lower()].default
        assert str(default) == value, f"{name}={value} differs from the default {default!r}"


def test_secrets_are_commented_and_empty():
    for name, is_active, value in _entries():
        if name in SECRETS:
            assert not is_active and value == "", name


def test_local_connect_public_url_is_documented_as_not_derived():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "# LOCAL_CONNECT_PUBLIC_URL=https://example.com" in text
    assert "Not derived automatically" in text

    # The behaviour the comment describes: empty → placeholder host.
    from app.routes import local_connect

    class _S:
        local_connect_public_url = ""

    orig = local_connect.get_settings
    try:
        local_connect.get_settings = lambda: _S()
        assert "https://your-geekcubo-host" in local_connect._install_command()
        _S.local_connect_public_url = "https://example.com/"
        assert "--server https://example.com " in local_connect._install_command()
    finally:
        local_connect.get_settings = orig


def test_copied_template_does_not_change_settings(tmp_path, monkeypatch):
    """A fresh `cp .env.example .env` must yield the schema defaults."""
    from app.config import Settings

    for name in _settings_vars():
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    shutil.copy2(EXAMPLE, env)
    loaded = Settings(_env_file=str(env))
    defaults = Settings(_env_file=None)
    assert loaded.model_dump() == defaults.model_dump()


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_docker_compose_accepts_the_template(tmp_path):
    shutil.copy2(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    shutil.copy2(EXAMPLE, tmp_path / ".env")
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip("docker compose v2 unavailable")
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "--quiet"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
