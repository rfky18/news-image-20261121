#!/usr/bin/env python3
"""Generate the bitmap font atlas for the news-image-20261121 front page.

Reads real OFL TrueType files, rasterises every needed glyph with Pillow
into one grayscale atlas image (atlas.bin, raw bytes) plus a JSON index
(atlas.json). main.py is stdlib-only and only ever blits this atlas, so the
submitted program never touches a font file or the network.

Run from the repo root:  python3 tools/gen_atlas.py
Writes atlas.bin + atlas.json next to main.py.
"""

import json
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT_DIR = os.path.join(HERE, "fonts")

# family -> (local filename, download URL or None, variation name or None)
FONTS = {
    "bodoni": (
        "BodoniModa[opsz,wght].ttf",
        "https://github.com/google/fonts/raw/main/ofl/bodonimoda/"
        "BodoniModa%5Bopsz%2Cwght%5D.ttf",
        "Bold",
    ),
    "baskerville": (
        "LibreBaskerville[wght].ttf",
        "https://github.com/google/fonts/raw/main/ofl/librebaskerville/"
        "LibreBaskerville%5Bwght%5D.ttf",
        "Bold",
    ),
    "gelasio": (
        "Gelasio[wght].ttf",
        "https://github.com/google/fonts/raw/main/ofl/gelasio/"
        "Gelasio%5Bwght%5D.ttf",
        None,
    ),
    "libsans": (
        "LiberationSans-Regular.ttf",
        None,
        None,
    ),
    "libsans_b": (
        "LiberationSans-Bold.ttf",
        None,
        None,
    ),
    "roboto": (
        "Roboto[wdth,wght].ttf",
        "https://github.com/google/fonts/raw/main/ofl/roboto/"
        "Roboto%5Bwdth%2Cwght%5D.ttf",
        None,
    ),
}

# (family, pixel size) pairs the page actually uses.
SIZES = [
    ("bodoni", 62),
    ("baskerville", 17),
    ("baskerville", 13),
    ("gelasio", 15),
    ("gelasio", 11),
    ("gelasio", 10),
    ("gelasio", 9),
    ("libsans_b", 30),
    ("libsans_b", 13),
    ("libsans_b", 12),
    ("libsans_b", 11),
    ("libsans_b", 10),
    ("libsans_b", 9),
    ("libsans_b", 8),
    ("libsans", 10),
    ("libsans", 9),
    ("roboto", 9),
    ("roboto", 8),
]

# Printable ASCII plus the punctuation / accented letters the page needs.
EXTRA = "\u2013\u2014\u2018\u2019\u201c\u201d\u00b7\u00b0\u00dc\u00e9"
CHARS = [chr(c) for c in range(32, 127)] + list(EXTRA)

PAD = 2          # padding around each glyph inside its temp canvas
ATLAS_W = 1024   # fixed atlas width; height grows as needed
GAP = 2          # gap between packed glyphs


def fetch_font(name):
    fname, url, _var = FONTS[name]
    path = os.path.join(FONT_DIR, fname)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        with open(path, "rb") as fh:
            head = fh.read(4)
        if head in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            return path
        print("  %s looks corrupt, re-downloading" % fname)
    if url is None:
        raise SystemExit(
            "missing font %s; install it from your OS package "
            "(fonts-liberation) into tools/fonts/ and rerun." % fname
        )
    print("  downloading %s ..." % fname)
    os.makedirs(FONT_DIR, exist_ok=True)
    urllib.request.urlretrieve(url, path)
    return path


def load_font(name, size):
    _fname, _url, var = FONTS[name]
    path = fetch_font(name)
    font = ImageFont.truetype(path, size)
    if var:
        font.set_variation_by_name(var)
    return font


def render_glyph(font, ch):
    """Rasterise one char. Returns (bitmap Image or None, advance, ox, oy).

    ox/oy is the offset of the bitmap's top-left corner from the pen
    position on the baseline, so blitting at (pen_x + ox, base_y + oy)
    reproduces the glyph exactly.
    """
    adv = int(round(font.getlength(ch)))
    if ch == " ":
        return None, adv, 0, 0
    ascent, _descent = font.getmetrics()
    tmp_w = adv + 2 * PAD + 4
    tmp_h = ascent + font.size + 2 * PAD + 4
    tmp = Image.new("L", (tmp_w, tmp_h), 0)
    draw = ImageDraw.Draw(tmp)
    draw.text((PAD, PAD + ascent), ch, font=font, fill=255, anchor="ls")
    bbox = tmp.getbbox()
    if bbox is None:
        return None, adv, 0, 0
    bmp = tmp.crop(bbox)
    ox = bbox[0] - PAD
    oy = bbox[1] - (PAD + ascent)
    return bmp, adv, ox, oy


def main():
    fonts = {}
    glyphs = {}   # key "family:size:ord" -> [x, y, w, h, adv, ox, oy]
    bitmaps = []  # (key, Image, adv, ox, oy) in packing order
    for family, size in SIZES:
        font = load_font(family, size)
        ascent, descent = font.getmetrics()
        key = "%s:%d" % (family, size)
        fonts[key] = {"ascent": ascent, "descent": descent,
                      "height": ascent + descent}
        for ch in CHARS:
            bmp, adv, ox, oy = render_glyph(font, ch)
            gkey = "%s:%d:%d" % (family, size, ord(ch))
            if bmp is None:
                glyphs[gkey] = [0, 0, 0, 0, adv, 0, 0]
            else:
                bitmaps.append((gkey, bmp, adv, ox, oy))
                glyphs[gkey] = [0, 0, bmp.width, bmp.height, adv, ox, oy]

    # Pack bitmaps into rows, tallest first (deterministic order).
    bitmaps.sort(key=lambda item: (-item[1].height, item[0]))
    atlas = Image.new("L", (ATLAS_W, 16), 0)
    x = 0
    y = 0
    row_h = 0
    for gkey, bmp, _adv, _ox, _oy in bitmaps:
        w, h = bmp.width, bmp.height
        if x + w + GAP > ATLAS_W:
            x = 0
            y += row_h + GAP
            row_h = 0
        if y + h + GAP > atlas.height:
            bigger = Image.new("L", (ATLAS_W, y + h + GAP + 16), 0)
            bigger.paste(atlas, (0, 0))
            atlas = bigger
        atlas.paste(bmp, (x, y))
        glyphs[gkey][0] = x
        glyphs[gkey][1] = y
        x += w + GAP
        row_h = max(row_h, h)
    atlas = atlas.crop((0, 0, ATLAS_W, y + row_h))

    atlas_path = os.path.join(ROOT, "atlas.bin")
    with open(atlas_path, "wb") as fh:
        fh.write(atlas.tobytes())
    index = {"w": atlas.width, "h": atlas.height,
             "fonts": fonts, "glyphs": glyphs}
    with open(os.path.join(ROOT, "atlas.json"), "w") as fh:
        json.dump(index, fh, sort_keys=True)
    print("atlas %dx%d, %d glyphs, %d bytes"
          % (atlas.width, atlas.height, len(glyphs), len(atlas.tobytes())))


if __name__ == "__main__":
    main()
