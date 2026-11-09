"""Generate the GeekCubo brand asset pack (SVG + PNG + ICO).

The mark ("The Intelligent Cube") is pure geometry, authored in this
repository and produced from coordinates rather than traced: a flat isometric
cube whose three faces are three model families, meeting at one central
routing node. The faces are separated by real transparent cuts (an SVG mask),
not white strokes, so every variant sits cleanly on light, dark or
photographic backgrounds.

Wordmark: "GeekCubo" with "Geek" in ink and "Cubo" in the brand blue. The type
is OUTLINED (see `_outlines.py`), not live <text>: an earlier revision relied
on font-family="Inter", which is absent on most machines, so the wordmark
silently rendered in a fallback face -- including in the shipped PNGs. Glyph
outlines remove the runtime font dependency. Regenerate them with
scripts/brand/outline_text.py (needs Inter Bold, SIL OFL 1.1).

Run from the repository root:

    python scripts/brand/build_brand.py            # SVG + manifest only
    python scripts/brand/build_brand.py --raster   # + PNG/ICO (Playwright + ImageMagick)

Outputs go to design/brand/. Deterministic: re-running produces byte-identical
SVGs.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _outlines as T  # noqa: E402  (generated outline data)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "design" / "brand"

# ── palette ────────────────────────────────────────────────────────────────
COBALT = "#2563EB"
INDIGO = "#6366F1"
CYAN = "#0891B2"

LIGHT = {
    # top face lightest, right face deepest: reads as lit from the upper left
    "top": "#3B82F6",
    "left": COBALT,
    "right": "#4F46E5",
    "node": CYAN,
    "word_a": "#0F172A",
    "word_b": COBALT,
}
DARK = {
    "top": "#60A5FA",
    "left": "#3B82F6",
    "right": INDIGO,
    "node": "#22D3EE",
    "word_a": "#F1F5F9",
    "word_b": "#60A5FA",
}

# ── geometry (64x64 artboard) ──────────────────────────────────────────────
C = 32.0          # centre of the hexagon silhouette
R = 28.0          # vertex radius
GAP = 2.6         # width of the transparent cuts between faces
NODE_R = 5.2      # routing node radius
NODE_RING = 2.4   # transparent ring separating node from faces


def _vertex(angle_deg: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return (C + R * math.cos(a), C + R * math.sin(a))


TOP = _vertex(-90)
UR = _vertex(-30)
LR = _vertex(30)
BOT = _vertex(90)
LL = _vertex(150)
UL = _vertex(210)
CEN = (C, C)


def _pts(*points: tuple[float, float]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _mark_body(p: dict, *, mask_id: str, mono: bool = False) -> str:
    """The cube as SVG elements (no wrapper). Uses `currentColor` when mono."""
    fill = (lambda key: "currentColor") if mono else (lambda key: p[key])
    # Mono reads as one solid form with cuts; keep subtle face separation via
    # opacity so the cube still reads as three-dimensional at 16px.
    op = {"top": 1.0, "left": 0.82, "right": 0.64} if mono else {"top": 1, "left": 1, "right": 1}
    cut = (
        f'<mask id="{mask_id}" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">'
        '<rect width="64" height="64" fill="#fff"/>'
        f'<g stroke="#000" stroke-width="{GAP}" stroke-linecap="round">'
        f'<line x1="{CEN[0]:.2f}" y1="{CEN[1]:.2f}" x2="{UL[0]:.2f}" y2="{UL[1]:.2f}"/>'
        f'<line x1="{CEN[0]:.2f}" y1="{CEN[1]:.2f}" x2="{UR[0]:.2f}" y2="{UR[1]:.2f}"/>'
        f'<line x1="{CEN[0]:.2f}" y1="{CEN[1]:.2f}" x2="{BOT[0]:.2f}" y2="{BOT[1]:.2f}"/>'
        "</g>"
        f'<circle cx="{CEN[0]:.2f}" cy="{CEN[1]:.2f}" r="{NODE_R + NODE_RING:.2f}" fill="#000"/>'
        "</mask>"
    )
    faces = (
        f'<g mask="url(#{mask_id})">'
        f'<polygon points="{_pts(TOP, UR, CEN, UL)}" fill="{fill("top")}" fill-opacity="{op["top"]}"/>'
        f'<polygon points="{_pts(UL, CEN, BOT, LL)}" fill="{fill("left")}" fill-opacity="{op["left"]}"/>'
        f'<polygon points="{_pts(UR, LR, BOT, CEN)}" fill="{fill("right")}" fill-opacity="{op["right"]}"/>'
        "</g>"
    )
    node = f'<circle cx="{CEN[0]:.2f}" cy="{CEN[1]:.2f}" r="{NODE_R:.2f}" fill="{fill("node")}"/>'
    return f"<defs>{cut}</defs>{faces}{node}"


def mark_svg(p: dict, *, mono: bool = False) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
        'role="img" aria-label="GeekCubo">'
        "<title>GeekCubo</title>"
        f'{_mark_body(p, mask_id="gc-cut", mono=mono)}'
        "</svg>\n"
    )


# ── wordmark (outlined) ────────────────────────────────────────────────────
LOCKUP_SIZE = 31.0      # px, matches the original lockup
LOCKUP_X = 76.0
LOCKUP_BASELINE = 42.5
LOCKUP_ADVANCE = T.WORDMARK["ADVANCE"] * (LOCKUP_SIZE / T.UPM)
LOCKUP_W = LOCKUP_X + LOCKUP_ADVANCE + 4   # a hair of right air
LOCKUP_H = 64.0


def _wordmark_group(p: dict, *, size: float, x: float, baseline: float, mono: bool = False) -> str:
    s = size / T.UPM
    a = "currentColor" if mono else p["word_a"]
    b = "currentColor" if mono else p["word_b"]
    return (
        f'<g transform="translate({x} {baseline}) scale({s:.6f})" aria-hidden="true">'
        f'<path d="{T.WORDMARK["PATH1"]}" fill="{a}"/>'
        f'<path d="{T.WORDMARK["PATH2"]}" fill="{b}"/>'
        "</g>"
    )


def logo_svg(p: dict, *, mono: bool = False) -> str:
    """Horizontal lockup: cube + outlined "GeekCubo"."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LOCKUP_W:.2f} {LOCKUP_H:.0f}" '
        f'width="{LOCKUP_W:.2f}" height="{LOCKUP_H:.0f}" role="img" aria-label="GeekCubo">'
        "<title>GeekCubo</title>"
        f'{_mark_body(p, mask_id="gc-cut-l", mono=mono)}'
        f'{_wordmark_group(p, size=LOCKUP_SIZE, x=LOCKUP_X, baseline=LOCKUP_BASELINE, mono=mono)}'
        "</svg>\n"
    )


def wordmark_svg(p: dict, *, mono: bool = False) -> str:
    """Wordmark alone, for places that already show the symbol."""
    w = LOCKUP_ADVANCE + 4
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} 64" '
        f'width="{w:.2f}" height="64" role="img" aria-label="GeekCubo">'
        "<title>GeekCubo</title>"
        f'{_wordmark_group(p, size=LOCKUP_SIZE, x=2, baseline=LOCKUP_BASELINE, mono=mono)}'
        "</svg>\n"
    )


def favicon_svg() -> str:
    """Favicon that follows the browser's light/dark chrome."""
    light = _mark_body(LIGHT, mask_id="gc-l")
    dark = _mark_body(DARK, mask_id="gc-d")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
        "<style>.d{display:none}@media (prefers-color-scheme:dark){.l{display:none}.d{display:inline}}</style>"
        f'<g class="l">{light}</g><g class="d">{dark}</g>'
        "</svg>\n"
    )


def app_icon_svg(size: int = 512) -> str:
    """Square app icon: cube on a solid dark tile (PWA / maskable safe zone).

    Content sits at 64% of the canvas, safely inside the inner 80% circle that
    Android crops maskable icons to.
    """
    pad = size * 0.18
    scale = (size - 2 * pad) / 64
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">'
        f'<rect width="{size}" height="{size}" fill="#0B1220"/>'
        f'<g transform="translate({pad:.2f} {pad:.2f}) scale({scale:.4f})">'
        f'{_mark_body(DARK, mask_id="gc-app")}'
        "</g></svg>\n"
    )


def og_image_svg() -> str:
    """1200x630 social card. Type is outlined, so it renders identically."""
    w, h = 1200, 630
    canvas = "#0B1220"

    def line(d: dict, x: float, baseline: float, size: float, color: str) -> str:
        s = size / T.UPM
        return (
            f'<g transform="translate({x} {baseline}) scale({s:.6f})">'
            f'<path d="{d["PATH1"]}" fill="{color}"/></g>'
        )

    # Cube at 2x (128px) on the left, wordmark 40px, then the tagline.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        'role="img" aria-label="GeekCubo — One Gateway. Every AI Model.">'
        "<title>GeekCubo — One Gateway. Every AI Model.</title>"
        f'<rect width="{w}" height="{h}" fill="{canvas}"/>'
        '<circle cx="1010" cy="90" r="300" fill="#1E293B" opacity="0.55"/>'
        '<circle cx="1120" cy="560" r="210" fill="#1E3A8A" opacity="0.35"/>'
        f'<g transform="translate(72 84) scale(2)">{_mark_body(DARK, mask_id="gc-og")}</g>'
        f'{_wordmark_group(DARK, size=40, x=224, baseline=136)}'
        f'{line(T.OG_LINE1, 72, 330, 64, "#F8FAFC")}'
        f'{line(T.OG_LINE2, 72, 410, 64, "#60A5FA")}'
        f'{line(T.OG_SUB, 72, 492, 26, "#CBD5E1")}'
        "</svg>\n"
    )


MANIFEST = {
    "name": "GeekCubo",
    "short_name": "GeekCubo",
    "description": "One Gateway. Every AI Model.",
    "icons": [
        {"src": "/static/brand/android-chrome-192x192.png", "sizes": "192x192",
         "type": "image/png"},
        {"src": "/static/brand/android-chrome-512x512.png", "sizes": "512x512",
         "type": "image/png"},
        {"src": "/static/brand/app-icon-maskable-512.png", "sizes": "512x512",
         "type": "image/png", "purpose": "maskable"},
    ],
    "theme_color": COBALT,
    "background_color": "#0B1220",
    "display": "standalone",
    "start_url": "/",
}


def write_svgs() -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    svgs = {
        # canonical symbol / wordmark / lockup
        "geekcubo-symbol.svg": mark_svg(LIGHT),
        "geekcubo-symbol-dark.svg": mark_svg(DARK),
        "geekcubo-symbol-mono.svg": mark_svg(LIGHT, mono=True),
        "geekcubo-wordmark.svg": wordmark_svg(LIGHT),
        "geekcubo-wordmark-dark.svg": wordmark_svg(DARK),
        "geekcubo-wordmark-mono.svg": wordmark_svg(LIGHT, mono=True),
        "geekcubo-logo.svg": logo_svg(LIGHT),
        "geekcubo-logo-dark.svg": logo_svg(DARK),
        "geekcubo-logo-mono.svg": logo_svg(LIGHT, mono=True),
        # browser + PWA
        "favicon.svg": favicon_svg(),
        "app-icon.svg": app_icon_svg(),
        "og-image.svg": og_image_svg(),
    }
    paths = {}
    for name, body in svgs.items():
        path = OUT / name
        path.write_text(body, encoding="utf-8")
        paths[name] = path

    manifest = OUT / "site.webmanifest"
    manifest.write_text(json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")
    paths["site.webmanifest"] = manifest
    return paths


# ── rasterisation ──────────────────────────────────────────────────────────
# (source SVG, output PNG, width, height, opaque background or None)
JOBS = [
    ("app-icon.svg", "android-chrome-512x512.png", 512, None, None),
    ("app-icon.svg", "app-icon-maskable-512.png", 512, None, None),
    ("app-icon.svg", "android-chrome-192x192.png", 192, None, None),
    ("app-icon.svg", "apple-touch-icon.png", 180, None, "#FFFFFF"),
    ("favicon.svg", "favicon-16x16.png", 16, None, None),
    ("favicon.svg", "favicon-32x32.png", 32, None, None),
    ("favicon.svg", "favicon-48x48.png", 48, None, None),
    ("favicon.svg", "favicon-64x64.png", 64, None, None),
    ("geekcubo-symbol.svg", "geekcubo-symbol-256.png", 256, None, None),
    ("geekcubo-symbol-dark.svg", "github-avatar.png", 512, None, "#0B1220"),
    ("geekcubo-symbol-dark.svg", "social-avatar.png", 800, None, "#0B1220"),
    ("geekcubo-logo.svg", "geekcubo-logo.png", 960, 256, None),
    ("geekcubo-logo-dark.svg", "geekcubo-logo-dark.png", 960, 256, None),
    ("og-image.svg", "og-image.png", 1200, 630, "#0B1220"),
]

ICO_SIZES = [16, 32, 48, 64]


def _data_uri(path: Path) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(
        path.read_bytes()).decode("ascii")


def rasterize() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is required for --raster (pip install playwright).")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(device_scale_factor=1)
        for src, dst, w, h, bg in JOBS:
            h = h or w
            uri = _data_uri(OUT / src)
            body_bg = bg or "transparent"
            page.set_viewport_size({"width": w, "height": h})
            page.set_content(
                f"<html><body style='margin:0;background:{body_bg}'>"
                f"<img src='{uri}' width='{w}' height='{h}' "
                "style='display:block'></body></html>"
            )
            page.wait_for_timeout(50)
            page.screenshot(
                path=str(OUT / dst),
                omit_background=bg is None,
                clip={"x": 0, "y": 0, "width": w, "height": h},
            )
        browser.close()

    convert = shutil.which("convert") or shutil.which("magick")
    if convert:
        srcs = [str(OUT / f"favicon-{s}x{s}.png") for s in ICO_SIZES]
        subprocess.run([convert, *srcs, str(OUT / "favicon.ico")], check=True)
    else:
        print("ImageMagick not found: favicon.ico skipped (PNGs still written).")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raster", action="store_true", help="also render PNG/ICO")
    args = ap.parse_args(argv)
    paths = write_svgs()
    print(f"wrote {len(paths)} SVG/manifest files to {OUT.relative_to(REPO)}")
    if args.raster:
        rasterize()
        print("rendered PNG/ICO assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
