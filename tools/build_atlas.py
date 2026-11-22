#!/usr/bin/env python3
"""Build the bitmap type atlas for news-image-20261121 v9.

Build-time only. Reads the OFL TTFs from the workspace fonts directory,
renders every needed glyph (2x supersampled, downscaled for smooth
anti-aliasing) into one LA atlas PNG plus a JSON metric table.

The runtime (main.py) is stdlib-only and only blits this atlas; it never
touches a font file.

Usage:
    python3 tools/build_atlas.py <fonts-dir> <out-dir>
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 2  # supersample factor

CHARS = "".join(chr(c) for c in range(32, 127)) + "·—–’‘“”ü°"

# key -> (filename, size, variation axes or None)
# Variation axes are given as a dict {axis_tag: value}.
SPECS = [
    ("bodoni62", "BodoniModa%5Bopsz%2Cwght%5D.ttf", 62, {"opsz": 60, "wght": 700}),
    ("bask17", "LibreBaskerville-Bold.ttf", 17, None),
    ("bask13", "LibreBaskerville-Bold.ttf", 13, None),
    ("gel15", "Gelasio%5Bwght%5D.ttf", 15, None),
    ("gel11", "Gelasio%5Bwght%5D.ttf", 11, None),
    ("gel10", "Gelasio%5Bwght%5D.ttf", 10, None),
    ("sans30b", "LiberationSans-Bold.ttf", 30, None),
    ("sans19b", "LiberationSans-Bold.ttf", 19, None),
    ("sans13b", "LiberationSans-Bold.ttf", 13, None),
    ("sans12b", "LiberationSans-Bold.ttf", 12, None),
    ("sans11b", "LiberationSans-Bold.ttf", 11, None),
    ("sans10b", "LiberationSans-Bold.ttf", 10, None),
    ("sans9b", "LiberationSans-Bold.ttf", 9, None),
    ("sans9", "LiberationSans-Regular.ttf", 9, None),
    ("sans8b", "LiberationSans-Bold.ttf", 8, None),
    ("sans8", "LiberationSans-Regular.ttf", 8, None),
]

ATLAS_W = 1024
PAD = 1  # cell padding in atlas pixels


def load_font(path, size, variation):
    f = ImageFont.truetype(path, size)
    if variation:
        try:
            axes = [variation[a] for a in ("opsz", "wght") if a in variation]
            # set_variation_by_axes expects values in file axis order.
            f.set_variation_by_axes(axes)
        except Exception:
            pass
    return f


def render_glyph(font1x, font2x, ch, ascent):
    """Return (bitmap_L_image, advance, bx, by).

    bitmap is a grayscale coverage image at 1x scale. (bx, by) is the
    offset from the pen origin (baseline start) to the bitmap's top-left.
    PIL measures getbbox() from the ascender top, so the baseline sits
    `ascent` below the bbox origin: by = t - 1 - ascent.
    """
    bbox = font1x.getbbox(ch)
    adv = int(round(font1x.getlength(ch)))
    if bbox is None:
        return None, adv, 0, 0
    l, t, r, b = bbox
    w, h = r - l, b - t
    if w <= 0 or h <= 0:
        return None, adv, l, t
    # Draw at 2x with a 2px (2x-space) margin, then downscale.
    img2 = Image.new("L", (w * SS + 4, h * SS + 4), 0)
    d = ImageDraw.Draw(img2)
    d.text((-l * SS + 2, -t * SS + 2), ch, font=font2x, fill=255)
    small = img2.resize((w + 2, h + 2), Image.LANCZOS)
    return small, adv, l - 1, t - 1 - ascent


def main():
    fonts_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    glyphs = {}
    specs_meta = {}
    # First pass: render every glyph, remember bitmaps and metrics.
    rendered = []  # (spec_key, ch, bitmap, adv, bx, by)
    for key, fname, size, variation in SPECS:
        path = os.path.join(fonts_dir, fname)
        f1 = load_font(path, size, variation)
        f2 = load_font(path, size * SS, variation)
        ascent, descent = f1.getmetrics()
        specs_meta[key] = {"size": size, "ascent": ascent, "descent": descent}
        glyphs[key] = {}
        for ch in CHARS:
            bmp, adv, bx, by = render_glyph(f1, f2, ch, ascent)
            rendered.append((key, ch, bmp, adv, bx, by))

    # Pack into rows.
    rows = []
    cur = []
    cur_w = 0
    cur_h = 0
    for item in rendered:
        key, ch, bmp, adv, bx, by = item
        gw = bmp.width if bmp is not None else 0
        gh = bmp.height if bmp is not None else 0
        cell_w = gw + PAD * 2
        cell_h = gh + PAD * 2
        if cur and cur_w + cell_w > ATLAS_W:
            rows.append((cur, cur_h))
            cur, cur_w, cur_h = [], 0, 0
        cur.append(item)
        cur_w += cell_w
        cur_h = max(cur_h, cell_h)
    if cur:
        rows.append((cur, cur_h))

    atlas_h = sum(h for _, h in rows) + PAD
    lum = Image.new("L", (ATLAS_W, atlas_h), 255)
    alpha = Image.new("L", (ATLAS_W, atlas_h), 0)
    y = PAD
    for row_items, row_h in rows:
        x = PAD
        for key, ch, bmp, adv, bx, by in row_items:
            if bmp is not None:
                alpha.paste(bmp, (x + PAD, y + PAD))
                glyphs[key][ch] = [x + PAD, y + PAD, bmp.width, bmp.height,
                                   adv, bx, by]
            else:
                glyphs[key][ch] = [0, 0, 0, 0, adv, 0, 0]
            x += (bmp.width if bmp is not None else 0) + PAD * 2
        y += row_h
    atlas = Image.merge("LA", (lum, alpha))
    atlas.save(os.path.join(out_dir, "atlas.png"))
    with open(os.path.join(out_dir, "atlas.json"), "w") as fh:
        json.dump({"specs": specs_meta, "glyphs": glyphs}, fh,
                  sort_keys=True, separators=(",", ":"))
    print("atlas %dx%d, %d glyphs" % (ATLAS_W, atlas_h, len(rendered)))
    # Sanity: masthead width.
    m = glyphs["bodoni62"]
    w = sum(m[c][4] for c in "Saturday 21 November 2026")
    print("masthead width at 62px:", w)


if __name__ == "__main__":
    main()
