#!/usr/bin/env python3
"""Build a bitmap font atlas from real TTF files (build-time only, needs PIL).

Reads TTFs from tools/fonts/, renders every needed glyph into one
grayscale sheet, writes atlas.bin (raw bytes) + atlas.json (glyph rects).

The runtime (main.py) is stdlib-only: it just blits rectangles from the
atlas. No stroke/geometric fonts anywhere -- every glyph is a filled
bitmap rendered from the real font file.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(ROOT, "tools", "fonts")

# (atlas key, file name, pixel size, axis targets by name)
SPECS = [
    ("bodoni62", "BodoniModa[opsz,wght].ttf", 62, {"opsz": 62, "wght": 700}),
    ("bask30", "LibreBaskerville[wght].ttf", 30, {"wght": 700}),
    ("bask18", "LibreBaskerville[wght].ttf", 18, {"wght": 700}),
    ("bask13", "LibreBaskerville[wght].ttf", 13, {"wght": 700}),
    ("gel15", "Gelasio[wght].ttf", 15, {"wght": 400}),
    ("gel11", "Gelasio[wght].ttf", 11, {"wght": 400}),
    ("gel10", "Gelasio[wght].ttf", 10, {"wght": 400}),
    ("gel9", "Gelasio[wght].ttf", 9, {"wght": 400}),
    ("sansB15", "LiberationSans-Bold.ttf", 15, {}),
    ("sansB11", "LiberationSans-Bold.ttf", 11, {}),
    ("sansB10", "LiberationSans-Bold.ttf", 10, {}),
    ("sansB9", "LiberationSans-Bold.ttf", 9, {}),
    ("sans10", "LiberationSans-Regular.ttf", 10, {}),
    ("sans9", "LiberationSans-Regular.ttf", 9, {}),
    ("rob9", "Roboto[wdth,wght].ttf", 9, {"wdth": 100, "wght": 400}),
]

CHARS = "".join(chr(c) for c in range(32, 127))
CHARS += "·—’‘“”°ÜüÉéÑñ–"

SHEET_W = 1024
PAD = 2


def load_font(fname, size, axes):
    path = os.path.join(FONTS_DIR, fname)
    font = ImageFont.truetype(path, size)
    if axes:
        try:
            values = []
            for a in font.get_variation_axes():
                name = a["name"] if isinstance(a, dict) else a.name
                lo = a["minimum"] if isinstance(a, dict) else a.minimum
                hi = a["maximum"] if isinstance(a, dict) else a.maximum
                df = a["default"] if isinstance(a, dict) else a.default
                if name in axes:
                    values.append(max(lo, min(hi, axes[name])))
                else:
                    values.append(df)
            font.set_variation_by_axes(values)
        except Exception as exc:  # noqa: BLE001 - variable font optional
            print("variation axes skipped for %s: %s" % (fname, exc))
    return font


def main():
    placements = []  # (x, y, bitmap)
    meta = {}
    y_cursor = 0
    for key, fname, size, axes in SPECS:
        font = load_font(fname, size, axes)
        ascent, descent = font.getmetrics()
        meta[key] = {"ascent": ascent, "descent": descent,
                     "line": ascent + descent, "glyphs": {}}
        x_cursor = 0
        row_h = 0
        for ch in CHARS:
            if ch == " ":
                adv = int(round(font.getlength(" ")))
                meta[key]["glyphs"][ch] = [0, 0, 0, 0, adv, 0, 0]
                continue
            # True ink box: render the char on a tile at a known pen
            # position (anchor "la": pen at left edge / ascender top) and
            # measure the ink. (font.getbbox/textbbox return the ADVANCE
            # box, not the ink box -- bearings would read as 0.)
            adv = int(round(font.getlength(ch)))
            tile_w = adv + 8
            tile_h = ascent + descent + 8
            tile = Image.new("L", (tile_w, tile_h), 0)
            d = ImageDraw.Draw(tile)
            d.text((4, 4), ch, font=font, fill=255, anchor="la")
            tb = tile.getbbox()
            if tb is None:
                meta[key]["glyphs"][ch] = [0, 0, 0, 0, adv, 0, 0]
                continue
            gw, gh = tb[2] - tb[0], tb[3] - tb[1]
            ox, oy = tb[0] - 4, tb[1] - 4
            if x_cursor + gw + PAD > SHEET_W:
                y_cursor += row_h + PAD
                x_cursor = 0
                row_h = 0
            placements.append((x_cursor, y_cursor, tile.crop(tb)))
            meta[key]["glyphs"][ch] = [x_cursor, y_cursor, gw, gh, adv, ox, oy]
            x_cursor += gw + PAD
            row_h = max(row_h, gh)
        y_cursor += row_h + PAD
    sheet = Image.new("L", (SHEET_W, y_cursor), 0)
    for x, y, bmp in placements:
        sheet.paste(bmp, (x, y))
    raw = sheet.tobytes()
    with open(os.path.join(ROOT, "atlas.bin"), "wb") as f:
        f.write(raw)
    meta["_sheet"] = {"w": SHEET_W, "h": y_cursor}
    with open(os.path.join(ROOT, "atlas.json"), "w") as f:
        json.dump(meta, f, sort_keys=True, separators=(",", ":"))
    print("atlas %dx%d, %d glyphs, %d bytes raw"
          % (SHEET_W, y_cursor, len(placements), len(raw)))


if __name__ == "__main__":
    main()
