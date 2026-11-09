"""GeekCubo is self-hosted: user-facing instructions, generated configuration
and runtime defaults must never point at a GeekCubo-operated application host.

Allowed `geekcubo.com` references are the project website and the three
permanent support pages. Deployment examples use reserved documentation names
(`example.com`, `api.example.com`, `127.0.0.1`, `203.0.113.x`), and no such
example may become a runtime default.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

USER_FACING = [
    *sorted(ROOT.glob("README*.md")),
    ROOT / "DEPLOYMENT.md",
    ROOT / "DEMO.md",
    ROOT / ".env.example",
    ROOT / "install.sh",
    ROOT / "docker-compose.yml",
    ROOT / "design" / "index.html",
    ROOT / "design" / "app.js",
    *sorted((ROOT / "integrations").iterdir()),
    *sorted((ROOT / "app").rglob("*.py")),
    *sorted((ROOT / "geekcubo_connector").rglob("*.py")),
]

ALLOWED_GEEKCUBO_URLS = {
    "https://geekcubo.com",
    "https://geekcubo.com/providers/",
    "https://geekcubo.com/hosting/",
    "https://geekcubo.com/vpn/",
}

_HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+geekcubo\.com\b", re.I)
_URL = re.compile(r"https?://(?:[a-z0-9-]+\.)*geekcubo\.com[^\s)\"'`<>]*", re.I)


def _files():
    return [p for p in USER_FACING if p.is_file() and "__pycache__" not in p.parts]


def test_no_geekcubo_operated_application_hosts():
    hits = []
    for path in _files():
        for m in _HOST.finditer(path.read_text(encoding="utf-8", errors="replace")):
            hits.append(f"{path.relative_to(ROOT)}: {m.group(0)}")
    assert not hits, hits


def test_only_project_site_and_support_links_use_geekcubo_com():
    bad = []
    for path in _files():
        for m in _URL.finditer(path.read_text(encoding="utf-8", errors="replace")):
            url = m.group(0).rstrip(".,;:")
            if url not in ALLOWED_GEEKCUBO_URLS:
                bad.append(f"{path.relative_to(ROOT)}: {url}")
    assert not bad, bad


def test_documentation_hostnames_are_not_runtime_defaults():
    from app.config import Settings

    for name, field in Settings.model_fields.items():
        default = field.default
        if isinstance(default, str):
            assert "example.com" not in default and "geekcubo.com" not in default, name


def test_local_connect_install_command_uses_only_the_configured_url():
    from app.routes import local_connect

    class _S:
        local_connect_public_url = ""

    orig = local_connect.get_settings
    try:
        local_connect.get_settings = lambda: _S()
        empty = local_connect._install_command()
        assert "geekcubo.com" not in empty and "example.com" not in empty
        _S.local_connect_public_url = "https://api.example.com"
        assert "--server https://api.example.com " in local_connect._install_command()
        files = local_connect._service_file_templates("https://api.example.com")
        assert all("geekcubo.com" not in v for v in files.values())
    finally:
        local_connect.get_settings = orig
