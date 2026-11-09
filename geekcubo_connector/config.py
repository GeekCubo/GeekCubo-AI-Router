"""Connector runtime configuration and on-disk credential storage.

The credential is stored under the user's config directory with ``0600``
permissions. It is a bearer secret: anyone holding it can impersonate this
machine to the server until an administrator rotates or revokes it. We keep it
in one JSON file so ``enroll`` and ``run`` agree on server URL plus credential
without environment juggling.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_ENV_VAR = "GEEKCUBO_CONNECTOR_CONFIG"
DEFAULT_CONFIG_NAME = "config.json"


def config_dir() -> Path:
    """Per-user config directory, honouring XDG on Linux and the platform
    defaults on macOS and Windows."""
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve().parent
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "GeekCubo" / "Connector"
    if _is_macos():
        return Path.home() / "Library" / "Application Support" / "GeekCubo" / "Connector"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "geekcubo" / "connector"


def _is_macos() -> bool:
    import sys

    return sys.platform == "darwin"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return config_dir() / DEFAULT_CONFIG_NAME


@dataclass
class ConnectorConfig:
    """Persisted identity plus optional per-run overrides."""

    server: str
    credential: str | None = None
    machine_id: str | None = None
    display_name: str | None = None
    # Only used for the one-shot `enroll` handshake; never persisted, since a
    # code is single-use and the credential supersedes it.
    enrollment_code: str | None = None
    adapters: list[str] = field(default_factory=list)
    # Base URLs for adapters whose endpoint is not the default. Keys are
    # adapter names; values are absolute http(s) URLs (or ws(s) for custom).
    adapter_urls: dict[str, str] = field(default_factory=dict)
    # Optional bearer token for a custom OpenAI-compatible adapter endpoint.
    adapter_api_key: str | None = None

    def to_dict(self) -> dict:
        return {
            "server": self.server,
            "credential": self.credential,
            "machine_id": self.machine_id,
            "display_name": self.display_name,
            "adapters": list(self.adapters),
            "adapter_urls": dict(self.adapter_urls),
            "adapter_api_key": self.adapter_api_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectorConfig":
        return cls(
            server=str(data.get("server") or "").rstrip("/"),
            credential=data.get("credential"),
            machine_id=data.get("machine_id"),
            display_name=data.get("display_name"),
            adapters=list(data.get("adapters") or []),
            adapter_urls=dict(data.get("adapter_urls") or {}),
            adapter_api_key=data.get("adapter_api_key"),
        )


def load_config(path: Path | None = None) -> ConnectorConfig | None:
    target = path or config_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    config = ConnectorConfig.from_dict(data)
    if not config.server:
        return None
    return config


def save_config(config: ConnectorConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_dict(), indent=2)
    # Write to a temp file then rename so a crash cannot leave a half-written
    # credential file, and tighten permissions before the secret lands.
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass
    os.replace(tmp, target)
    return target


def clear_config(path: Path | None = None) -> None:
    target = path or config_path()
    try:
        target.unlink()
    except FileNotFoundError:
        pass
