"""Shared fixtures for the browser-level (Playwright) dashboard tests.

One real server process per module, booted with `scripts/start.py` against a
temp SQLite file, with the administrator provisioned through the real local
CLI (`python -m app.admin_cli setup`). Tests then drive the dashboard as an
operator would: sign in with username + password, not an API key.

Everything skips cleanly when Playwright or a Chromium build is unavailable.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("playwright.sync_api")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "correct horse battery staple"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LiveServer:
    """A running server plus a cookie-carrying admin HTTP helper."""

    def __init__(self, base_url: str, api_key: str, setup_token: str | None,
                 proc: subprocess.Popen, db_url: str, env: dict) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.setup_token = setup_token
        self.proc = proc
        self.db_url = db_url
        self.env = env
        self.workdir = Path(db_url.split("///", 1)[1]).parent
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )
        self._csrf = ""

    # -- admin HTTP helper (session cookie + CSRF), for test setup/teardown --

    def admin_login(self) -> None:
        body = json.dumps({"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self._opener.open(req, timeout=15) as r:
            self._csrf = json.loads(r.read())["csrf_token"]

    def admin(self, method: str, path: str, payload=None):
        if not self._csrf:
            self.admin_login()
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method,
            headers={"Content-Type": "application/json", "X-CSRF-Token": self._csrf},
        )
        try:
            with self._opener.open(req, timeout=15) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw

    def cli(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "app.admin_cli", *args],
            cwd=str(self.workdir), env=self.env, input=stdin,
            capture_output=True, text=True, timeout=180,
        )


def boot_server(workdir: Path, *, extra_env: dict | None = None,
                provision_admin: bool = True) -> LiveServer:
    port = free_port()
    log_path = workdir / "server.log"
    db_url = f"sqlite+aiosqlite:///{workdir / 'geekcubo.db'}"
    env = {
        **os.environ,
        "DATABASE_URL": db_url,
        "PORT": str(port),
        "HOST": "127.0.0.1",
        "ALLOW_INSECURE_DEV_KEY": "true",
        "PYTHONPATH": str(REPO_ROOT),
        "LOG_LEVEL": "warning",
        # print() banners are block-buffered when redirected to a file.
        "PYTHONUNBUFFERED": "1",
        **(extra_env or {}),
    }
    for key in list(env):
        if key.endswith("_API_KEY"):
            env.pop(key)

    log_file = log_path.open("w")
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "scripts" / "start.py")],
        cwd=str(workdir), env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    proc._geekcubo_log_file = log_file  # type: ignore[attr-defined]
    base_url = f"http://127.0.0.1:{port}"

    deadline = time.time() + 60
    api_key, setup_token = "", None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early:\n{log_path.read_text()[-4000:]}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as r:
                if r.status == 200:
                    text = log_path.read_text(errors="replace")
                    k = re.search(r"sk-geek-[0-9a-f]+", text)
                    t = re.search(r"setup token \(valid 24h\): (\S+)", text)
                    if k:
                        api_key = k.group(0)
                        setup_token = t.group(1) if t else None
                        break
        except Exception:
            pass
        time.sleep(0.25)
    if not api_key:
        proc.terminate()
        raise RuntimeError(f"server never became ready:\n{log_path.read_text()[-4000:]}")

    server = LiveServer(base_url, api_key, setup_token, proc, db_url, env)
    if provision_admin:
        r = server.cli("setup", "--username", ADMIN_USERNAME, "--password-stdin",
                       stdin=ADMIN_PASSWORD + "\n")
        if r.returncode != 0:
            stop_server(server)
            raise RuntimeError(f"admin_cli setup failed: {r.stderr}")
    return server


def stop_server(server: LiveServer) -> None:
    server.proc.terminate()
    try:
        server.proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        server.proc.kill()
    lf = getattr(server.proc, "_geekcubo_log_file", None)
    if lf:
        lf.close()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            instance = _launch_chromium(pw)
        except Exception as exc:  # pragma: no cover - depends on CI image
            pytest.skip(f"chromium not available for playwright: {exc}")
        yield instance
        instance.close()


def _launch_chromium(pw):
    """Launch Playwright's bundled Chromium, falling back to a system Chrome.

    The bundled `chrome-headless-shell` binary is large (120 MiB) and may be
    absent in offline environments. A system Chrome/Chromium at a well-known
    path works identically through `executable_path`.
    """
    candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        from pathlib import Path

        if Path(path).is_file():
            try:
                return pw.chromium.launch(executable_path=path, args=["--no-sandbox"])
            except Exception:
                continue
    return pw.chromium.launch(args=["--no-sandbox"])


def sign_in(page, base_url: str, *, path: str = "/") -> None:
    """Sign in through the real login form."""
    page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    page.wait_for_selector("#login-view:not([hidden])", timeout=15_000)
    page.fill("#login-username", ADMIN_USERNAME)
    page.fill("#login-password", ADMIN_PASSWORD)
    page.click("#login-submit")
    page.wait_for_selector("#app-shell:not([hidden])", timeout=15_000)
