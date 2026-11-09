from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.sh"
BASH = shutil.which("bash") or "/bin/bash"

FAKE_DOCKER = r"""#!/usr/bin/env bash
set -u
printf 'docker %s\n' "$*" >> "${FAKE_DOCKER_LOG}"

if [[ "${1:-}" == "info" ]]; then
  if [[ -n "${FAKE_INFO_FAIL:-}" && -z "${FAKE_VIA_SUDO:-}" ]]; then
    exit 1
  fi
  exit 0
fi

if [[ "${1:-}" != "compose" ]]; then
  exit 0
fi
shift

if [[ "${1:-}" == "version" ]]; then
  [[ -n "${FAKE_COMPOSE_VERSION_FAIL:-}" ]] && exit 1
  echo "Docker Compose version v2.24.0"
  exit 0
fi

if [[ "${1:-}" == "config" ]]; then
  [[ -n "${FAKE_CONFIG_FAIL:-}" ]] && exit 1
  echo "services: {}"
  exit 0
fi

if [[ "${1:-}" == "up" ]]; then
  [[ -n "${FAKE_UP_FAIL:-}" ]] && exit 1
  echo "started"
  exit 0
fi

if [[ "${1:-}" == "port" ]]; then
  echo "${FAKE_BIND:-127.0.0.1:8787}"
  exit 0
fi

if [[ "${1:-}" == "ps" ]]; then
  echo "NAME STATUS"
  echo "geekcubo running"
  exit 0
fi

if [[ "${1:-}" == "logs" ]]; then
  echo "fake application log"
  exit 0
fi

if [[ "${1:-}" == "exec" ]]; then
  shift
  while [[ "${1:-}" == -* ]]; do shift; done
  shift
  cmd="$*"
  case "$cmd" in
    *urllib.request*)
      [[ -n "${FAKE_HEALTH_FAIL:-}" ]] && exit 1
      exit 0
      ;;
    *"app.admin_cli status"*)
      [[ -n "${FAKE_STATUS_FAIL:-}" ]] && { echo "status failed" >&2; exit 1; }
      if [[ "${FAKE_ADMIN_STATE:-pending}" == "configured" ]]; then
        echo "Administrator: admin"
        echo "Active API keys: 1"
      else
        echo "Administrator: NOT INITIALIZED"
        echo "  Run python -m app.admin_cli setup-token (dashboard)."
      fi
      exit 0
      ;;
    *"app.admin_cli setup-token"*)
      [[ -n "${FAKE_SETUP_TOKEN_FAIL:-}" ]] && { echo "token command failed" >&2; exit 1; }
      if [[ "${FAKE_ADMIN_STATE:-pending}" == "configured" ]]; then
        echo "error: an administrator already exists" >&2
        exit 1
      fi
      echo "One-time administrator setup token (any previous token is now invalid):"
      echo "  ${FAKE_SETUP_TOKEN:-fake-token-1234567890abcdef}"
      echo "Expires: 2030-01-01T00:00:00+00:00"
      echo "Paste it into the dashboard's Create Administrator Account form."
      exit 0
      ;;
  esac
  exit 0
fi

exit 0
"""

FAKE_SUDO = r"""#!/usr/bin/env bash
set -u
printf 'sudo %s\n' "$*" >> "${FAKE_DOCKER_LOG}"
if [[ -n "${FAKE_SUDO_DISABLE:-}" ]]; then
  exit 1
fi
export FAKE_VIA_SUDO=1
if [[ "${1:-}" == "-n" ]]; then shift; fi
exec "$@"
"""


def _make_bin(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    sudo = bin_dir / "sudo"
    docker.write_text(FAKE_DOCKER, encoding="utf-8")
    sudo.write_text(FAKE_SUDO, encoding="utf-8")
    docker.chmod(0o755)
    sudo.chmod(0o755)
    log = tmp_path / "docker.log"
    if not log.exists():
        log.write_text("", encoding="utf-8")
    return bin_dir, log


def _install_root(tmp_path: Path, env_text: str | None = None) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy2(INSTALLER, root / "install.sh")
    shutil.copy2(ROOT / "docker-compose.yml", root / "docker-compose.yml")
    shutil.copy2(ROOT / ".env.example", root / ".env.example")
    if env_text is not None:
        (root / ".env").write_text(env_text, encoding="utf-8")
    return root


def _run(
    tmp_path: Path,
    root: Path,
    *,
    path: str | None = None,
    extra_env: dict | None = None,
    args: list[str] | None = None,
):
    bin_dir, log = _make_bin(tmp_path)
    extra_env = dict(extra_env or {})
    if extra_env.pop("FAKE_NO_NGINX", None) is None:
        _write_bin(bin_dir, "nginx", FAKE_NGINX_DEBIAN)
    if extra_env.pop("FAKE_NGINX_CONFLICT", None) is not None:
        extra_env["GEEKCUBO_FAKE_NGINX_CONFLICT"] = "1"
    if extra_env.pop("FAKE_SS_OCCUPIED", None) is not None:
        _write_bin(bin_dir, "ss", FAKE_SS_80443)
    else:
        _write_bin(bin_dir, "ss", FAKE_SS_FREE)
    _write_bin(bin_dir, "ufw", FAKE_UFW)
    if extra_env.pop("FAKE_SELINUX_DISABLED", None) is None:
        _write_bin(bin_dir, "getenforce", FAKE_GETENFORCE)
    env = {
        "PATH": path or f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "FAKE_DOCKER_LOG": str(log),
        "GEEKCUBO_INSTALL_HEALTH_TIMEOUT": "5",
        "GEEKCUBO_INSTALL_HEALTH_INTERVAL": "0",
    }
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [BASH, str(root / "install.sh"), *(args or [])],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result, log.read_text(encoding="utf-8")


def test_installer_is_executable_and_valid_bash():
    assert os.access(INSTALLER, os.X_OK)
    subprocess.run([BASH, "-n", str(INSTALLER)], check=True)


def test_help_exits_without_docker(tmp_path):
    minbin = tmp_path / "minbin"
    minbin.mkdir()
    (minbin / "dirname").symlink_to(shutil.which("dirname"))
    (minbin / "cat").symlink_to(shutil.which("cat"))
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, path=str(minbin), args=["--help"])
    assert result.returncode == 0
    assert "Usage: ./install.sh" in result.stdout
    assert log == ""


def test_invalid_health_timeout_is_rejected_before_docker_is_used(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={"GEEKCUBO_INSTALL_HEALTH_TIMEOUT": "soon"},
    )

    assert result.returncode == 1
    assert "GEEKCUBO_INSTALL_HEALTH_TIMEOUT must be a whole number" in result.stderr
    assert log == ""


def test_fresh_install_displays_setup_token_and_local_url(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root)

    assert result.returncode == 0, result.stderr
    assert (root / ".env").is_file()
    assert "Administrator setup token:" in result.stdout
    assert "fake-token-1234567890abcdef" in result.stdout
    assert "Dashboard: http://127.0.0.1:8787" in result.stdout
    assert "compose up -d --build" in log
    assert "app.admin_cli setup-token" in log
    assert "down" not in log


def test_existing_admin_does_not_request_or_display_a_token(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, extra_env={"FAKE_ADMIN_STATE": "configured"})

    assert result.returncode == 0, result.stderr
    assert "An administrator already exists" in result.stdout
    assert "fake-token" not in result.stdout
    assert "setup-token" not in log


def test_existing_env_is_not_modified(tmp_path):
    original = "OPENAI_API_KEY=sk-keep-me\nPUBLIC_BASE_URL=https://existing.example.com\n"
    root = _install_root(tmp_path, env_text=original)
    result, _ = _run(tmp_path, root)

    assert result.returncode == 0, result.stderr
    assert (root / ".env").read_text(encoding="utf-8") == original
    assert "Dashboard: https://existing.example.com" in result.stdout


def test_health_failure_stops_before_token_and_prints_safe_diagnostics(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={
            "FAKE_HEALTH_FAIL": "1",
            "GEEKCUBO_INSTALL_HEALTH_TIMEOUT": "0",
        },
    )

    assert result.returncode == 1
    assert "Health check did not pass" in result.stderr
    assert "Container status:" in result.stderr
    assert "docker compose logs --tail=100 api" in result.stderr
    assert "fake application log" not in result.stderr
    assert "app.admin_cli setup-token" not in log


def test_docker_missing_is_explained(tmp_path):
    minbin = tmp_path / "minbin"
    minbin.mkdir()
    for name in ("dirname", "sed", "head", "tail", "grep", "sleep", "cp", "tr", "uname", "mktemp", "mv", "chmod", "mkdir", "stat", "date", "ls"):
        target = shutil.which(name)
        if target:
            (minbin / name).symlink_to(target)

    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, path=str(minbin))

    assert result.returncode == 1
    assert "Docker is not installed" in result.stderr


def test_docker_permission_failure_mentions_sudo(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"FAKE_INFO_FAIL": "1", "FAKE_SUDO_DISABLE": "1"},
    )

    assert result.returncode == 1
    assert "cannot reach the daemon" in result.stderr
    assert "rerun with sudo" in result.stderr


def test_docker_access_through_sudo_is_supported(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, extra_env={"FAKE_INFO_FAIL": "1"})

    assert result.returncode == 0, result.stderr
    assert "reachable through sudo" in result.stdout
    assert "sudo docker compose ps" in result.stdout
    assert "sudo -n docker info" in log
    assert "docker compose up -d --build" in log


def test_compose_v2_missing_is_explained(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, extra_env={"FAKE_COMPOSE_VERSION_FAIL": "1"})

    assert result.returncode == 1
    assert "Docker Compose v2 is required" in result.stderr


def test_invalid_compose_config_blocks_startup(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, extra_env={"FAKE_CONFIG_FAIL": "1"})

    assert result.returncode == 1
    assert "rejected the configuration" in result.stderr
    assert "compose up" not in log


def test_public_base_url_from_environment(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"PUBLIC_BASE_URL": "https://ai.example.com/"},
    )

    assert result.returncode == 0, result.stderr
    assert "Dashboard: https://ai.example.com" in result.stdout
    assert "Reverse proxy target: http://127.0.0.1:8787" in result.stdout
    assert "TRUST_PROXY_HEADERS=true" in result.stdout


def test_invalid_public_base_url_is_rejected(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, extra_env={"PUBLIC_BASE_URL": "ftp://example.com"})

    assert result.returncode == 1
    assert "PUBLIC_BASE_URL must start with http:// or https://" in result.stderr


def test_non_loopback_binding_is_described_without_inventing_a_hostname(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, extra_env={"FAKE_BIND": "0.0.0.0:8787"})

    assert result.returncode == 0, result.stderr
    assert "published on 0.0.0.0:8787" in result.stdout
    assert "Do not expose the administrator port directly" in result.stdout


def test_provider_secrets_are_not_echoed_and_no_destructive_command_is_run(tmp_path):
    root = _install_root(tmp_path, env_text="OPENAI_API_KEY=sk-test-provider-secret\n")
    result, log = _run(tmp_path, root)

    assert result.returncode == 0, result.stderr
    assert "sk-test-provider-secret" not in result.stdout
    assert "sk-test-provider-secret" not in result.stderr
    assert "down -v" not in log
    assert "volume rm" not in log


def test_setup_token_failure_is_actionable(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, extra_env={"FAKE_SETUP_TOKEN_FAIL": "1"})

    assert result.returncode == 1
    assert "Could not issue the administrator setup token" in result.stderr
    assert "Retry with:" in result.stderr


def test_all_readme_install_sections_match_the_installer():
    readmes = sorted(ROOT.glob("README*.md"))
    assert len(readmes) == 12
    for path in readmes:
        text = path.read_text(encoding="utf-8")
        assert "./install.sh" in text, path.name
        assert "setup-token" in text, path.name
        assert "http://127.0.0.1:8787/v1" in text, path.name
        assert "✓ geekcubo ready. API key" not in text, path.name
        assert "docker compose up\n" not in text, path.name


def test_installer_is_in_the_sdist():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"install.sh"' in pyproject


FAKE_SS_FREE = r"""#!/usr/bin/env bash
echo "State Recv-Q Send-Q Local Address:Port"
exit 0
"""

FAKE_SS_80443 = r"""#!/usr/bin/env bash
echo "State Recv-Q Send-Q Local Address:Port"
echo "LISTEN 0 511 0.0.0.0:80 0.0.0.0:*"
echo "LISTEN 0 511 0.0.0.0:443 0.0.0.0:*"
exit 0
"""

FAKE_NGINX_DEBIAN = r"""#!/usr/bin/env bash
printf 'nginx %s\n' "$*" >> "${FAKE_DOCKER_LOG}"
if [[ "${1:-}" == "-t" ]]; then
  exit 0
fi
if [[ "${1:-}" == "-T" ]]; then
  echo "# configuration file /etc/nginx/nginx.conf:"
  echo "include /etc/nginx/sites-enabled/*;"
  exit 0
fi
if [[ "${1:-}" == "-s" && "${2:-}" == "reload" ]]; then
  exit 0
fi
exit 0
"""

FAKE_GETENFORCE = r"""#!/usr/bin/env bash
echo "${FAKE_GETENFORCE_STATE:-Enforcing}"
exit 0
"""

FAKE_UFW = r"""#!/usr/bin/env bash
echo "Status: active"
exit 0
"""


def _write_bin(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _os_release(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "os-release"
    path.write_text(text, encoding="utf-8")
    return path


def test_help_lists_modes_and_flags(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, args=["--help"])
    assert result.returncode == 0
    for needle in ("--mode", "--hostname", "--yes", "--dry-run", "--cloudflare-token-file"):
        assert needle in result.stdout
    assert "Cloudflare Tunnel removal" in result.stdout
    assert log == ""


def test_mode1_default_dry_run_mutates_nothing(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, args=["--mode", "1", "--yes", "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert "planned host-level changes" in result.stdout
    assert "No secrets were read or printed" in result.stdout
    assert log == ""
    assert not (root / ".env").exists()
    assert not (root / "deploy").exists()


def test_mode_persistence_file_is_created_and_reused(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, args=["--mode", "5", "--yes"])
    assert result.returncode == 0, result.stderr
    mode_file = root / "deploy" / ".mode"
    assert mode_file.is_file()
    assert oct(mode_file.stat().st_mode & 0o777) == "0o600"
    assert "MODE=5" in mode_file.read_text(encoding="utf-8")

    result2, _ = _run(tmp_path, root, args=["--yes"])
    assert result2.returncode == 0, result2.stderr
    assert "Reusing the previously selected mode 5" in result2.stdout


def test_invalid_mode_is_rejected(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, args=["--mode", "9", "--yes"])
    assert result.returncode == 1
    assert "--mode must be a number between 1 and 5" in result.stderr
    assert log == ""


def test_mode2_requires_hostname_noninteractively(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, args=["--mode", "2", "--yes"])
    assert result.returncode == 1
    assert "requires a hostname" in result.stderr


def test_mode2_happy_path_with_token_file(tmp_path):
    root = _install_root(tmp_path)
    token_src = tmp_path / "cf-token-src"
    token_src.write_text("CFSECRETTOKEN-should-never-appear", encoding="utf-8")
    token_src.chmod(0o600)
    result, log = _run(
        tmp_path,
        root,
        args=[
            "--mode", "2",
            "--hostname", "ai.example.com",
            "--yes",
            "--cloudflare-token-file", str(token_src),
        ],
    )
    assert result.returncode == 0, result.stderr
    target = root / "deploy" / "cloudflare" / "token"
    assert target.is_file()
    assert oct(target.stat().st_mode & 0o777) == "0o600"
    override = (root / "deploy" / "cloudflare" / "docker-compose.cloudflare.yml").read_text(encoding="utf-8")
    assert "cloudflare/cloudflared" in override
    assert "secrets:" in override
    assert "CFSECRETTOKEN" not in override
    combined = result.stdout + result.stderr + log
    assert "CFSECRETTOKEN" not in combined
    assert "-f deploy/cloudflare/docker-compose.cloudflare.yml" in log
    assert "--profile cloudflare" in log
    assert "never creates or deletes DNS records" in result.stdout
    assert "connector health" in result.stdout


def test_mode2_token_file_with_bad_perms_is_rejected(tmp_path):
    root = _install_root(tmp_path)
    token_src = tmp_path / "cf-token-bad"
    token_src.write_text("CFSECRETTOKEN2", encoding="utf-8")
    token_src.chmod(0o644)
    result, _ = _run(
        tmp_path,
        root,
        args=["--mode", "2", "--hostname", "ai.example.com", "--yes",
              "--cloudflare-token-file", str(token_src)],
    )
    assert result.returncode == 1
    assert "permissions" in result.stderr
    assert "CFSECRETTOKEN2" not in result.stdout + result.stderr
    assert not (root / "deploy" / "cloudflare" / "token").exists()


def test_mode2_dry_run_shows_plan_without_secret(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        args=["--mode", "2", "--hostname", "ai.example.com", "--yes", "--dry-run"],
    )
    assert result.returncode == 0, result.stderr
    assert "cloudflare" in result.stdout
    assert "No DNS records would be created" in result.stdout
    assert log == ""
    assert not (root / "deploy").exists()


def test_mode3_generates_vhost_and_installs_with_debian_layout(tmp_path):
    root = _install_root(tmp_path)
    etc = tmp_path / "etcnginx"
    (etc / "sites-available").mkdir(parents=True)
    (etc / "sites-enabled").mkdir(parents=True)
    result, log = _run(
        tmp_path,
        root,
        extra_env={"FAKE_NGINX_ETC": str(etc)},
        args=["--mode", "3", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    vhost = (root / "deploy" / "nginx" / "geekcubo.conf").read_text(encoding="utf-8")
    assert "proxy_pass http://127.0.0.1:8787;" in vhost
    assert "X-Forwarded-For" in vhost
    assert "Upgrade" in vhost
    assert "proxy_read_timeout" in vhost
    assert "server_name ai.example.com;" in vhost
    assert "map $http_upgrade $geekcubo_connection_upgrade" in vhost
    assert "proxy_set_header Connection $geekcubo_connection_upgrade;" in vhost
    assert "$connection_upgrade;" not in vhost.replace("$geekcubo_connection_upgrade;", "")


def test_mode3_refuses_conflicting_server_name(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"FAKE_NGINX_CONFLICT": "1"},
        args=["--mode", "3", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 1
    assert "already claims server_name ai.example.com" in result.stderr


def test_mode3_without_nginx_prints_manual_instructions(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={"FAKE_NO_NGINX": "1"},
        args=["--mode", "3", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "nginx is not installed" in result.stderr
    assert "Manual nginx setup" in result.stderr
    assert (root / "deploy" / "nginx" / "geekcubo.conf").is_file()


def test_mode3_selinux_enforcing_message(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        args=["--mode", "3", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "SELinux is in Enforcing mode" in result.stderr
    assert "httpd_can_network_connect" in result.stderr
    assert "never disables SELinux" in result.stderr


def test_mode4_happy_path_generates_caddy_files(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        args=["--mode", "4", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    caddyfile = (root / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    assert "ai.example.com" in caddyfile
    assert "reverse_proxy 127.0.0.1:8787" in caddyfile
    override = (root / "deploy" / "caddy" / "docker-compose.caddy.yml").read_text(encoding="utf-8")
    assert "caddy-data" in override
    assert "80:80" in override
    assert "-f deploy/caddy/docker-compose.caddy.yml" in log
    assert "--profile caddy" in log
    assert "ufw" in result.stdout


def test_mode4_refuses_when_ports_occupied(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={"FAKE_SS_OCCUPIED": "1"},
        args=["--mode", "4", "--hostname", "ai.example.com", "--yes"],
    )
    assert result.returncode == 1
    assert "already have a listener" in result.stderr
    assert "Refusing to silently compete" in result.stderr
    assert "compose up" not in log


def test_mode5_prints_ssh_tunnel_template(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(tmp_path, root, args=["--mode", "5", "--yes"])
    assert result.returncode == 0, result.stderr
    assert "ssh -L 8787:127.0.0.1:8787 <user>@<server>" in result.stdout
    assert "Keeping loopback-only binding" in result.stdout


def test_docker_missing_uses_distro_guidance(tmp_path):
    minbin = tmp_path / "minbin2"
    minbin.mkdir()
    for name in ("dirname", "sed", "head", "tail", "grep", "sleep", "cp", "tr", "uname", "mktemp", "mv", "chmod", "mkdir", "stat", "date", "ls"):
        target = shutil.which(name)
        if target:
            (minbin / name).symlink_to(target)
    osr = _os_release(tmp_path, 'ID=ubuntu\nVERSION_ID="24.04"\nPRETTY_NAME="Ubuntu 24.04"\n')
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        path=str(minbin),
        extra_env={"GEEKCUBO_OS_RELEASE": str(osr)},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 1
    assert "apt-get install" in result.stderr
    assert "docs.docker.com" in result.stderr
    assert "never installs packages itself" in result.stderr


def test_docker_missing_fedora_guidance(tmp_path):
    minbin = tmp_path / "minbin3"
    minbin.mkdir()
    for name in ("dirname", "sed", "head", "tail", "grep", "sleep", "cp", "tr", "uname", "mktemp", "mv", "chmod", "mkdir", "stat", "date", "ls"):
        target = shutil.which(name)
        if target:
            (minbin / name).symlink_to(target)
    osr = _os_release(tmp_path, 'ID=fedora\nVERSION_ID="40"\nPRETTY_NAME="Fedora 40"\n')
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        path=str(minbin),
        extra_env={"GEEKCUBO_OS_RELEASE": str(osr)},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 1
    assert "dnf install" in result.stderr


def test_os_detection_reported(tmp_path):
    osr = _os_release(tmp_path, 'ID=debian\nVERSION_ID="12"\nPRETTY_NAME="Debian GNU/Linux 12"\n')
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"GEEKCUBO_OS_RELEASE": str(osr)},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "Detected OS: Debian GNU/Linux 12" in result.stdout


def test_web_search_default_skip_noninteractive(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(tmp_path, root, args=["--mode", "1", "--yes"])
    assert result.returncode == 0, result.stderr
    assert "Web search skipped" in result.stdout
    assert "--profile search" not in log


def test_web_search_searxng_via_env_var(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={"GEEKCUBO_SEARCH_BACKEND": "searxng"},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "private SearXNG will start" in result.stdout
    assert "--profile search" in log
    env_text = (root / ".env").read_text(encoding="utf-8")
    assert "SEARXNG_SECRET=" in env_text


def test_web_search_searxng_idempotent_preserves_secret(tmp_path):
    original = "SEARXNG_SECRET=existing-secret-preserve-me\n"
    root = _install_root(tmp_path, env_text=original)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"GEEKCUBO_SEARCH_BACKEND": "searxng"},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    env_text = (root / ".env").read_text(encoding="utf-8")
    assert env_text.count("SEARXNG_SECRET=") == 1
    assert "existing-secret-preserve-me" in env_text


def test_web_search_existing_url_via_env_var(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={
            "GEEKCUBO_SEARCH_BACKEND": "existing",
            "GEEKCUBO_SEARXNG_URL": "http://search.internal:8080",
        },
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "existing SearXNG at http://search.internal:8080" in result.stdout
    assert "--profile search" not in log


def test_web_search_brave_via_env_var(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={
            "GEEKCUBO_SEARCH_BACKEND": "brave",
            "GEEKCUBO_BRAVE_KEY": "BSA-test-key-never-printed",
        },
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "Brave Search API key will be stored via the dashboard" in result.stdout
    assert "--profile search" not in log
    combined = result.stdout + result.stderr + log
    assert "BSA-test-key-never-printed" not in combined


def test_web_search_tavily_via_env_var(tmp_path):
    root = _install_root(tmp_path)
    result, log = _run(
        tmp_path,
        root,
        extra_env={
            "GEEKCUBO_SEARCH_BACKEND": "tavily",
            "GEEKCUBO_TAVILY_KEY": "tvly-test-key-never-printed",
        },
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "Tavily API key will be stored via the dashboard" in result.stdout
    assert "--profile search" not in log
    combined = result.stdout + result.stderr + log
    assert "tvly-test-key-never-printed" not in combined


def test_web_search_invalid_backend_defaults_to_skip(tmp_path):
    root = _install_root(tmp_path)
    result, _ = _run(
        tmp_path,
        root,
        extra_env={"GEEKCUBO_SEARCH_BACKEND": "invalid"},
        args=["--mode", "1", "--yes"],
    )
    assert result.returncode == 0, result.stderr
    assert "Web search skipped" in result.stdout


def test_docker_compose_yml_has_searxng_resource_limits():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "deploy:" in compose_text
    assert "limits:" in compose_text
    assert "memory: 512M" in compose_text
    assert "healthcheck:" in compose_text
