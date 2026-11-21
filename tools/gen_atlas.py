# gen_atlas.py — build-time atlas generator for news-image-20261121 v5.
#
# Purpose: render REAL font glyphs (not hand-drawn strokes) into one
# grayscale bitmap atlas + a JSON glyph map, so the stdlib-only entry
# program (main.py) can typeset the whole front page by blitting.
#
# Fonts (all OFL or metric-compatible, downloaded 21 Nov 2026 from the
# official google/fonts GitHub repo, raw.githubusercontent.com; Liberation
# Sans from the system install /usr/share/fonts/truetype/liberation/):
#   - Bodoni Moda (variable, opsz+wght)  -> masthead / section heads
#   - Libre Baskerville (variable, wght) -> main headlines
#   - Gelasio (variable, wght)           -> secondary headlines, body text
#   - Liberation Sans (static)           -> dates, labels, metadata, strip
#   - Roboto (variable, wdth+wght)       -> small captions
# Variable fonts are set with PIL set_variation_by_axes. Every TTF was
# verified by magic bytes (0x00010000) before use.
#
# Method: each glyph is rendered at 2x with PIL/FreeType (real hinting and
# antialiasing), then downscaled with LANCZOS to 1x for smooth edges.
# Kerning pairs with |kern| >= 0.5 px are measured with getlength and
# stored, so main.py can kern properly. Output is atlas.bin (raw 8-bit
# grayscale, row-major) + atlas.json (dimensions, per-style ascent/
# descent, per-glyph atlas rect + advance + bearings, kerning table).
# This script is BUILD-TIME ONLY (needs PIL + the TTFs); main.py at
# grade time only reads atlas.bin + atlas.json with the standard library.
#
# Usage: python3 tools/gen_atlas.py [--fonts DIR] [--out DIR]
#   --fonts: directory holding the 4 Google TTFs (default /tmp/fonts-v5)
#   --out:   directory for atlas.bin + atlas.json (default repo root)

import argparse
import json
import os
import string
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 2  # supersample factor

FONTS_DIR_DEFAULT = "/tmp/fonts-v5"
LIBERATION_DIR = "/usr/share/fonts/truetype/liberation"

# style -> (filename or absolute path, pixel size, variation axes or None)
STYLES = {
    "bodoni_mast":   ("BodoniModa[opsz,wght].ttf", 78, [700, 72]),
    "bodoni_also":   ("BodoniModa[opsz,wght].ttf", 30, [700, 30]),
    "bask_hero":     ("LibreBaskerville[wght].ttf", 49, [700]),
    "bask_feat":     ("LibreBaskerville[wght].ttf", 19, [700]),
    "bask_bottom":   ("LibreBaskerville[wght].ttf", 34, [700]),
    "bask_sub":      ("LibreBaskerville[wght].ttf", 15, [700]),
    "gel_head2":     ("Gelasio[wght].ttf", 15, [700]),
    "gel_body":      ("Gelasio[wght].ttf", 12, [400]),
    "sans_date":     ("LiberationSans-Regular.ttf", 20, None),
    "sans_kick":     ("LiberationSans-Bold.ttf", 12, None),
    "sans_label":    ("LiberationSans-Bold.ttf", 13, None),
    "sans_meta":     ("LiberationSans-Regular.ttf", 13, None),
    "sans_stat":     ("LiberationSans-Bold.ttf", 11, None),
    "sans_strip":    ("LiberationSans-Regular.ttf", 12, None),
    "sans_small":    ("LiberationSans-Bold.ttf", 12, None),
    "sans_name":     ("LiberationSans-Bold.ttf", 12, None),
    "sans_note":     ("LiberationSans-Regular.ttf", 11, None),
    "sans_shenzhen": ("LiberationSans-Bold.ttf", 12, None),
    "sans_datecheck": ("LiberationSans-Bold.ttf", 15, None),
    "sans_context":  ("LiberationSans-Regular.ttf", 14, None),
    "robo_cap":      ("Roboto[wdth,wght].ttf", 11, [400, 100]),
}

CHARSET = (
    string.ascii_letters + string.digits + " "
    + ".,:;!?-'\"()[]/\\&%$#@*+=<>_|~^`"
    + "\u2013\u2014\u2018\u2019\u201c\u201d\u00b7\u2026\u00d7\u00e9\u00fc"
)

ATLAS_W = 1024
PAD = 2


def load_font(path, size, axes):
    font = ImageFont.truetype(path, size * SS)
    if axes is not None:
        font.set_variation_by_axes(axes)
    return font


def render_glyph(font, ch):
    """Render one char at 2x, downscale to 1x. Returns (bitmap Image or
    None, advance_1x, bearing_x_1x, bearing_y_1x). Bearings are relative
    to the pen position on the baseline: bitmap left = pen_x + bearing_x,
    bitmap top = baseline_y + bearing_y."""
    adv2 = font.getlength(ch)
    asc2, desc2 = font.getmetrics()
    cw = int(adv2) + 10
    chh = asc2 + desc2 + 10
    img = Image.new("L", (cw, chh), 0)
    d = ImageDraw.Draw(img)
    # anchor "la": the y given IS the ascender top, so draw at y=5 and
    # the baseline sits at 5 + ascent (2x).
    d.text((5, 5), ch, font=font, fill=255, anchor="la")
    bbox = img.getbbox()
    adv1 = adv2 / SS
    if bbox is None:
        return None, adv1, 0.0, 0.0
    l, t, r, b = bbox
    crop = img.crop(bbox)
    w1 = max(1, round((r - l) / SS))
    h1 = max(1, round((b - t) / SS))
    small = crop.resize((w1, h1), Image.LANCZOS)
    bx = (l - 5) / SS
    by = (t - (5 + asc2)) / SS
    return small, adv1, bx, by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default=FONTS_DIR_DEFAULT)
    ap.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)) + "/..")
    args = ap.parse_args()

    def resolve(name):
        if name.startswith("LiberationSans"):
            return os.path.join(LIBERATION_DIR, name)
        return os.path.join(args.fonts, name)

    # verify TTF magic bytes before use
    for name in set(v[0] for v in STYLES.values()):
        p = resolve(name)
        with open(p, "rb") as fh:
            magic = fh.read(4)
        assert magic in (bytes.fromhex("00010000"), b"true", b"OTTO"), \
            "bad TTF magic for %s: %s" % (p, magic.hex())
        print("verified", name, magic.hex())

    glyphs = {}   # style -> char -> dict
    metrics = {}  # style -> (ascent, descent) at 1x
    kern = {}     # style -> {"ab": value}
    items = []    # (style, char, bitmap, adv, bx, by) for packing

    for style, (fname, size, axes) in STYLES.items():
        font = load_font(resolve(fname), size, axes)
        asc2, desc2 = font.getmetrics()
        metrics[style] = (asc2 / SS, desc2 / SS)
        glyphs[style] = {}
        kmap = {}
        for ch in CHARSET:
            bmp, adv, bx, by = render_glyph(font, ch)
            glyphs[style][ch] = {
                "adv": round(adv, 2), "bx": round(bx, 2), "by": round(by, 2),
                "w": 0, "h": 0, "x": 0, "y": 0,
            }
            if bmp is not None:
                items.append((style, ch, bmp, adv, bx, by))
        # kerning: measure every pair, keep only visible ones
        for a in CHARSET:
            for b in CHARSET:
                k2 = font.getlength(a + b) - font.getlength(a) - font.getlength(b)
                k1 = k2 / SS
                if abs(k1) >= 0.5:
                    kmap[a + b] = round(k1, 2)
        kern[style] = kmap
        print("style", style, "size", size,
              "glyphs", sum(1 for s2, _c, _b, _a, _x, _y in items if s2 == style),
              "kern pairs", len(kmap))

    # shelf packing, tallest first
    items.sort(key=lambda t: (-t[2].height, -t[2].width))
    atlas_h = 0
    x = 0
    y = 0
    row_h = 0
    atlas = Image.new("L", (ATLAS_W, 4096), 0)
    for style, ch, bmp, adv, bx, by in items:
        w, h = bmp.size
        if x + w + PAD > ATLAS_W:
            x = 0
            y += row_h + PAD
            row_h = 0
        atlas.paste(bmp, (x, y))
        g = glyphs[style][ch]
        g.update({"x": x, "y": y, "w": w, "h": h})
        x += w + PAD
        row_h = max(row_h, h)
    atlas_h = y + row_h + PAD
    atlas = atlas.crop((0, 0, ATLAS_W, atlas_h))

    atlas_path = os.path.join(args.out, "atlas.bin")
    json_path = os.path.join(args.out, "atlas.json")
    os.makedirs(args.out, exist_ok=True)
    with open(atlas_path, "wb") as fh:
        fh.write(atlas.tobytes())
    data = {
        "width": ATLAS_W,
        "height": atlas_h,
        "metrics": {s: {"ascent": a, "descent": d}
                    for s, (a, d) in metrics.items()},
        "glyphs": glyphs,
        "kern": kern,
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print("atlas", ATLAS_W, "x", atlas_h,
          "bin bytes", os.path.getsize(atlas_path),
          "json bytes", os.path.getsize(json_path))


if __name__ == "__main__":
    main()
