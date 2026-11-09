"""One-off: outline the brand's typography into scripts/brand/_outlines.py.

Why this exists: the geekcubo.com artwork renders "GeekCubo" with live
<text font-family="Inter">. Inter is not installed on most machines -- it was
not installed here -- so the wordmark silently fell back to Noto Sans, in the
shipped PNGs as well. Every string the brand needs is therefore converted to
real glyph outlines once, and committed as plain data.

build_brand.py imports that data, so building the assets needs no font file,
no fonttools and no uharfbuzz. Re-run this only when the typography changes:

    python scripts/brand/outline_text.py /path/to/Inter-Bold.ttf

Inter is SIL OFL 1.1, which permits outlined glyphs inside a logo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

OUT = Path(__file__).with_name("_outlines.py")

# name: (text, tracking in em, index at which to split colour, tracking_only_between)
SPECS = {
    "WORDMARK": ("GeekCubo", -0.040, 4),
    "OG_LINE1": ("One Gateway.", -0.045, 0),
    "OG_LINE2": ("Every AI Model.", -0.045, 0),
    "OG_SUB": ("Self-hosted routing for every model, with fallback and cost control.", -0.015, 0),
    "OG_FOOT": ("geekcubo.com", -0.010, 0),
}


def outline(font_path: str, text: str, tracking_em: float, split: int) -> dict:
    blob = Path(font_path).read_bytes()
    hbfont = hb.Font(hb.Face(blob))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})

    tt = TTFont(font_path)
    upm = tt["head"].unitsPerEm
    glyphset = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    tracking = tracking_em * upm

    first: list[str] = []
    second: list[str] = []
    x = 0.0
    last = len(buf.glyph_infos) - 1
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions, strict=True)):
        name = order[info.codepoint]
        pen = SVGPathPen(glyphset)
        # font units are y-up; SVG is y-down with the baseline at y=0.
        glyphset[name].draw(TransformPen(pen, (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)))
        (second if split and info.cluster >= split else first).append(pen.getCommands())
        x += pos.x_advance + (tracking if i < last else 0)

    return {"advance": x, "path1": " ".join(first), "path2": " ".join(second)}


def _wrap(s: str, indent: str = "    ", width: int = 92) -> str:
    """Split a long SVG path into adjacent Python string literals.

    Every emitted line keeps its trailing space. Dropping it would fuse the
    last number on one line with the first number on the next ("20" + "72.5"
    becoming "2072.5") -- syntactically valid path data, silently wrong
    geometry.
    """
    lines, cur = [], ""
    for token in s.split(" "):
        piece = token + " "
        if cur and len(cur) + len(piece) > width:
            lines.append(cur)
            cur = ""
        cur += piece
    if cur:
        lines.append(cur)
    # The final line may keep its trailing space: harmless, and it keeps the
    # "always end with a space" invariant below honest.
    return "\n".join(f'{indent}"{ln}"' for ln in lines)


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    font_path = sys.argv[1]
    tt = TTFont(font_path)
    upm = tt["head"].unitsPerEm
    # nameID 4 on this build reads "Inter Regular" even though OS/2 weight is
    # 700, so report the weight class rather than trusting the string alone.
    family = tt["name"].getDebugName(1) or "unknown"
    name = f"{family} {tt['OS/2'].usWeightClass}"
    chunks = [
        '"""GENERATED DATA -- do not edit by hand.',
        "",
        'Glyph outlines for the GeekCubo wordmark and OG artwork, produced by',
        'scripts/brand/outline_text.py from:',
        f"    {name}",
        "",
        "Coordinates are font units, baseline at y=0, y grows downward. Each entry",
        "is a dict with ADVANCE (pen advance in font units), PATH1 and PATH2 (PATH2 is",
        "the second colour run of the wordmark, empty otherwise).",
        "",
        "They are outlines, not text: nothing here depends on an installed font.",
        '"""',
        "",
        f"UPM = {upm}",
        f"FONT = {name!r}",
        "",
    ]
    for key, (text, tracking, split) in SPECS.items():
        d = outline(font_path, text, tracking, split)
        chunks.append(f"# {text!r}  tracking={tracking}em")
        chunks.append(f"{key} = {{")
        chunks.append(f'    "ADVANCE": {d["advance"]:.1f},')
        chunks.append(f'    "PATH1": (\n{_wrap(d["path1"])}\n    ),')
        if d["path2"]:
            chunks.append(f'    "PATH2": (\n{_wrap(d["path2"])}\n    ),')
        else:
            chunks.append('    "PATH2": "",')
        chunks.append("}")
        chunks.append("")
        print(f"{key}: advance={d['advance']:.0f}u ({len(d['path1']) + len(d['path2'])} chars)")

    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print(f"wrote {OUT.name} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
