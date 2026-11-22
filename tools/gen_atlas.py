#!/usr/bin/env python3
"""Build a bitmap glyph atlas from the OFL TTFs in tools/fonts/.

Reads the official Google Fonts TTFs at build time and renders every
needed glyph into one grayscale atlas (atlas.bin) plus a metrics file
(atlas.json). main.py is stdlib-only and blits from these files.

Deterministic: same fonts + same Pillow => same bytes.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(ROOT, "tools", "fonts")
OUT_JSON = os.path.join(ROOT, "atlas.json")
OUT_BIN = os.path.join(ROOT, "atlas.bin")

# (key, filename, size, axis values by name, italic-shear)
SPECS = [
    ("bodoni62", "BodoniModa[opsz,wght].ttf", 62, {"opsz": 62, "wght": 700}, 0.0),
    ("bask28", "LibreBaskerville[wght].ttf", 28, {"wght": 700}, 0.0),
    ("bask17", "LibreBaskerville[wght].ttf", 17, {"wght": 700}, 0.0),
    ("bask13", "LibreBaskerville[wght].ttf", 13, {"wght": 700}, 0.0),
    ("gel15i", "Gelasio[wght].ttf", 15, {"wght": 400}, 0.16),
    ("gel11", "Gelasio[wght].ttf", 11, {"wght": 400}, 0.0),
    ("gel10", "Gelasio[wght].ttf", 10, {"wght": 400}, 0.0),
    ("gel9", "Gelasio[wght].ttf", 9, {"wght": 400}, 0.0),
    ("sansb12", "LiberationSans-Bold.ttf", 12, {}, 0.0),
    ("sansb11", "LiberationSans-Bold.ttf", 11, {}, 0.0),
    ("sansb10", "LiberationSans-Bold.ttf", 10, {}, 0.0),
    ("sansb9", "LiberationSans-Bold.ttf", 9, {}, 0.0),
    ("sans9", "LiberationSans-Regular.ttf", 9, {}, 0.0),
    ("robo9", "Roboto[wdth,wght].ttf", 9, {"wdth": 100, "wght": 400}, 0.0),
    ("robo8", "Roboto[wdth,wght].ttf", 8, {"wdth": 100, "wght": 400}, 0.0),
]

CHARS = "".join(chr(c) for c in range(32, 127))
CHARS += "\u00b7\u2014\u2013\u2019\u2018\u201c\u201d\u00dc\u00fc\u00e9\u00c9"
CHARS += "\u00e0\u00e8\u00ea\u00ee\u00f4\u00e2\u00e7\u00f1\u00b0\u00d7\u2022\u2026"
CHARS = "".join(dict.fromkeys(CHARS))  # dedupe, keep order

ATLAS_W = 1024
PAD = 2


def load_font(filename, size, axes):
    path = os.path.join(FONTS_DIR, filename)
    font = ImageFont.truetype(path, size)
    if axes:
        try:
            names = [a.name for a in font.get_variation_axes()]
            values = [axes[n] for n in names if n in axes]
            if len(values) == len(names):
                font.set_variation_by_axes(values)
        except Exception:
            pass
    return font


def render_glyph(font, ch, shear):
    """Return (ink Image L, adv, ox, oy). ox/oy = ink offset from pen/baseline."""
    size = font.size
    tmp_w, tmp_h = size * 4 + 40, size * 4 + 40
    base = size * 2 + 20
    img = Image.new("L", (tmp_w, tmp_h), 0)
    d = ImageDraw.Draw(img)
    d.text((20, base), ch, font=font, fill=255, anchor="ls")
    adv = int(round(font.getlength(ch)))
    bbox = img.getbbox()
    if bbox is None:
        return None, adv, 0, 0
    ink = img.crop(bbox)
    ox, oy = bbox[0] - 20, bbox[1] - base
    if shear:
        w, h = ink.size
        extra = int(h * shear) + 2
        ink = ink.transform(
            (w + extra, h), Image.AFFINE, (1, -shear, 0, 0, 1, 0), fillcolor=0
        )
    return ink, adv, ox, oy


def main():
    glyphs = {}
    metrics = {}
    cells = []
    for key, filename, size, axes, shear in SPECS:
        font = load_font(filename, size, axes)
        asc, desc = font.getmetrics()
        metrics[key] = {"asc": asc, "desc": desc, "size": size}
        for ch in CHARS:
            ink, adv, ox, oy = render_glyph(font, ch, shear)
            gkey = "%s|%d" % (key, ord(ch))
            if ink is None:
                glyphs[gkey] = [0, 0, 0, 0, adv, 0, 0]
                continue
            cells.append((gkey, ink, adv, ox, oy))

    # Pack cells into rows, tallest first for a compact deterministic atlas.
    cells.sort(key=lambda c: (-c[1].size[1], c[0]))
    cx, cy, row_h = 0, 0, 0
    placements = {}
    for gkey, ink, adv, ox, oy in cells:
        w, h = ink.size
        if cx + w + PAD > ATLAS_W:
            cy += row_h + PAD
            cx, row_h = 0, 0
        placements[gkey] = (cx, cy, ink, adv, ox, oy)
        row_h = max(row_h, h)
        cx += w + PAD
    atlas_h = cy + row_h + PAD

    atlas = Image.new("L", (ATLAS_W, atlas_h), 0)
    for gkey, (x, y, ink, adv, ox, oy) in placements.items():
        atlas.paste(ink, (x, y))
        w, h = ink.size
        glyphs[gkey] = [x, y, w, h, adv, ox, oy]

    with open(OUT_BIN, "wb") as f:
        f.write(atlas.tobytes())
    data = {"w": ATLAS_W, "h": atlas_h, "glyphs": glyphs, "metrics": metrics}
    with open(OUT_JSON, "w") as f:
        json.dump(data, f, sort_keys=True)
    print("atlas %dx%d, %d glyphs" % (ATLAS_W, atlas_h, len(glyphs)))


if __name__ == "__main__":
    main()
