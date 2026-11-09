"""Release packaging: Docker identity, assets, and no-secrets guarantees.

These are cheap static checks that catch the class of mistake a rebrand
introduces: a referenced asset that was renamed, a container name that no
longer matches the docs, or a secret committed into an example file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_compose_uses_geekcubo_identity_but_keeps_the_data_volume():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "container_name: geekcubo" in text
    assert "image: geekcubo" in text
    # Renaming either of these would orphan an existing install's data.
    assert "geekcubo-data:/data" in text
    assert "geekcubo.db" in text


def test_compose_has_restart_policy_and_log_rotation():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "restart: unless-stopped" in text
    assert "max-size" in text and "max-file" in text


def test_compose_binds_loopback_only():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:8787:8000"' in text


def test_dockerfile_runs_unprivileged_and_loads_the_bundled_cost_map():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^USER geekcubo$", text, re.M)
    # Offline startup: no outbound cost-map download.
    assert "LITELLM_LOCAL_MODEL_COST_MAP=True" in text
    assert "HEALTHCHECK" in text


def test_startup_events_are_geekcubo_named():
    text = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "geekcubo_starting" in text
    assert "geekcubo_ready" in text
    assert "lite_starting" not in text
    assert "lite_ready" not in text


def test_every_referenced_brand_asset_exists():
    html = (ROOT / "design" / "index.html").read_text(encoding="utf-8")
    # The app mounts design/ at /static/, so strip that prefix before looking
    # on disk.
    refs = re.findall(r'"/(static/brand/[^"]+)"', html)
    assert refs, "index.html should reference the brand assets"
    missing = [r for r in refs if not (ROOT / "design" / r.removeprefix("static/")).exists()]
    assert not missing, f"missing brand assets: {missing}"


def test_webmanifest_icons_exist_and_are_png():
    import json

    manifest = json.loads((ROOT / "design" / "brand" / "site.webmanifest").read_text(encoding="utf-8"))
    for icon in manifest["icons"]:
        path = ROOT / "design" / icon["src"].removeprefix("/static/")
        assert path.exists(), icon["src"]
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", icon["src"]


def test_brand_pack_complete():
    """All expected brand assets exist on disk."""
    BRAND = ROOT / "design" / "brand"
    expected = [
        # SVGs
        "geekcubo-symbol.svg",
        "geekcubo-symbol-dark.svg",
        "geekcubo-symbol-mono.svg",
        "geekcubo-wordmark.svg",
        "geekcubo-wordmark-dark.svg",
        "geekcubo-logo.svg",
        "geekcubo-logo-dark.svg",
        "geekcubo-logo-mono.svg",
        "favicon.svg",
        "app-icon.svg",
        "og-image.svg",
        "site.webmanifest",
        # Favicon PNGs (canonical names with dimensions)
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon-48x48.png",
        "favicon-64x64.png",
        "favicon.ico",
        # Platform icons
        "apple-touch-icon.png",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "app-icon-maskable-512.png",
        # Social / avatar
        "og-image.png",
        "github-avatar.png",
        "social-avatar.png",
        # Mark exports
        "geekcubo-symbol-256.png",
        "geekcubo-logo.png",
        "geekcubo-logo-dark.png",
    ]
    missing = [n for n in expected if not (BRAND / n).exists()]
    assert not missing, f"missing brand assets: {missing}"


def test_brand_pack_uses_the_cube_and_not_the_imported_mark():
    """The mark is the isometric cube authored in this repository.

    It previously carried a document-tile mark whose geometry and palette were
    copied from an unrelated local project without authorization. This test
    pins the current identity and fails if that artwork is reintroduced.
    """
    BRAND = ROOT / "design" / "brand"
    symbol = (BRAND / "geekcubo-symbol.svg").read_text(encoding="utf-8")
    # Cube geometry from the generator's coordinates.
    assert "<polygon" in symbol and "mask" in symbol
    assert "gc-cut" in symbol

    imported = [
        "#5B5FEF", "#6D63F2", "#EEEAFE", "#A8A4FF", "#17171B",
        "#F7F7FA", "#E7E4FF", "M9 7h9.4L23", "M18.4 7V11.6H23",
    ]
    offenders = [token for token in imported if token in symbol]
    assert not offenders, f"imported artwork tokens present in the mark: {offenders}"

    # And nowhere else in the pack, or in the generator that produces it.
    for path in sorted(BRAND.glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        found = [t for t in imported if t in text]
        assert not found, f"{path.name} still contains imported artwork tokens {found}"
    gen = (ROOT / "scripts" / "brand" / "build_brand.py").read_text(encoding="utf-8")
    found = [t for t in imported if t in gen]
    assert not found, f"generator still contains imported artwork tokens {found}"


def test_wordmark_is_outlined_not_live_text():
    """A live <text font-family="Inter"> silently falls back on machines
    without Inter, which is how wrong wordmarks shipped in the PNGs."""
    for name in ("geekcubo-logo.svg", "geekcubo-wordmark.svg"):
        text = (ROOT / "design" / "brand" / name).read_text(encoding="utf-8")
        assert "<text" not in text, f"{name} uses live <text>"
        assert "<path" in text


def test_og_image_is_correct_size():
    """og-image.png must be exactly 1200x630 (Open Graph standard)."""
    import subprocess
    result = subprocess.run(
        ["identify", "-format", "%wx%h", str(ROOT / "design" / "brand" / "og-image.png")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, "ImageMagick identify failed"
    assert result.stdout.strip() == "1200x630", f"og-image.png is {result.stdout.strip()}, expected 1200x630"


def test_html_head_has_og_and_favicon_meta():
    html = (ROOT / "design" / "index.html").read_text(encoding="utf-8")
    assert 'property="og:image"' in html, "missing og:image meta"
    assert 'og-image.png' in html, "og:image should point to og-image.png"
    assert 'favicon-32x32.png' in html, "missing 32x32 favicon link"
    assert 'favicon-16x16.png' in html, "missing 16x16 favicon link"


@pytest.mark.parametrize("name", [".env.example", "README.md", "DEPLOYMENT.md"])
def test_no_real_secrets_in_shipped_documents(name):
    text = (ROOT / name).read_text(encoding="utf-8")
    # sk-geek-... / sk-... placeholders are fine; a long literal key is not.
    assert not re.search(r"sk-(?:geek-)?[A-Za-z0-9]{32,}", text), name
    assert "CREDENTIAL_ENCRYPTION_KEY=" not in text or "your-" in text or "change" in text.lower()


def test_gitignore_excludes_local_state():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "*.sqlite", "/attachments/"):
        assert pattern in text, pattern
    # The pattern is anchored to the repo root so it never hides the
    # `app/attachments/` source package from version control.
    lines = {line.strip() for line in text.splitlines()}
    assert "/attachments/" in lines
    assert "attachments/" not in lines - {"/attachments/"}


def test_docs_describe_the_actual_default_base_url():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "127.0.0.1:8787/v1" in readme
