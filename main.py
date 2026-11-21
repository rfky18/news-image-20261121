# news-image-20261121 v4 — fresh build, written from scratch in this session.
# One 1024x1024 front page: Saturday 21 November 2026 world news.
# Stdlib only. Deterministic: two runs write byte-identical PNG.
# Text is drawn from a fresh filled bitmap atlas (supersampled 4x):
# Didone serif for masthead/headlines, Helvetica-style sans for labels/body.
# No geometric stroke font: every glyph is filled shapes (rects, ellipse
# rings, arc rings) rasterised large and downsampled.
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024
SS = 4  # supersampling factor for glyph masks

CREAM = (247, 240, 220)
PAPER = (250, 244, 228)
INK = (24, 28, 44)
NAVY = (22, 35, 63)
NAVY2 = (16, 26, 48)
GOLD = (217, 164, 65)
GOLD2 = (232, 196, 110)
CRIMSON = (140, 47, 38)
CRIMSON2 = (122, 38, 30)
TEAL = (38, 110, 118)
SEA = (46, 126, 138)
LAND = (216, 178, 105)
LAND2 = (198, 158, 88)
GREY = (90, 92, 104)
LGREY = (200, 196, 182)
WHITE = (255, 255, 255)
RED = (198, 60, 44)

# ---------------------------------------------------------------- PNG out
def _chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

def write_png(path, px, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]
    data = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    blob = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", data) + _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(blob)

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill(bg)

    def fill(self, c):
        r, g, b = c
        row = bytes((r, g, b)) * self.w
        for y in range(self.h):
            self.px[y * self.w * 3:(y + 1) * self.w * 3] = row

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = c
        row = bytes((r, g, b)) * (x1 - x0)
        for y in range(y0, y1):
            self.px[y * self.w * 3 + x0 * 3:y * self.w * 3 + x1 * 3] = row

    def hline(self, x0, x1, y, c, t=1):
        self.rect(x0, y, x1, y + t, c)

    def vline(self, x, y0, y1, c, t=1):
        self.rect(x, y0, x + t, y1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(int(cy - ry), int(cy + ry) + 1):
            dy = (yy - cy) / max(1.0, ry)
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(1 - dy * dy)
            self.rect(cx - dx, yy, cx + dx + 1, yy + 1, c)

    def circle(self, cx, cy, r, c):
        self.ellipse(cx, cy, r, r, c)

    def poly(self, pts, c):
        # scanline fill of a simple polygon
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(xs[k], y, xs[k + 1] + 1, y + 1, c)

    def thick_line(self, x0, y0, x1, y1, w, c):
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * w / 2.0, dx / ln * w / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                  (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)

    def arc_poly(self, cx, cy, rx, ry, a0, a1, steps=24):
        pts = []
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        return pts

    def ring(self, cx, cy, rx, ry, t, c, a0=0, a1=360):
        # filled ring (or arc ring) as polygon: outer arc + inner arc back
        outer = self.arc_poly(cx, cy, rx, ry, a0, a1)
        inner = self.arc_poly(cx, cy, max(0.5, rx - t), max(0.5, ry - t), a1, a0)
        self.poly(outer + inner, c)

# ---------------------------------------------------------------- glyph masks
# A glyph is drawn into a float mask at SS scale, then downsampled.
class Mask:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.m = bytearray(w * h)

    def rect(self, x0, y0, x1, y1):
        x0 = max(0, int(round(x0))); y0 = max(0, int(round(y0)))
        x1 = min(self.w, int(round(x1))); y1 = min(self.h, int(round(y1)))
        for y in range(y0, y1):
            base = y * self.w
            for x in range(x0, x1):
                self.m[base + x] = 255

    def ellipse(self, cx, cy, rx, ry):
        for yy in range(max(0, int(cy - ry)), min(self.h, int(cy + ry) + 1)):
            dy = (yy - cy) / max(1.0, ry)
            if abs(dy) > 1:
                continue
            dx = rx * math.sqrt(1 - dy * dy)
            self.rect(cx - dx, yy, cx + dx + 1, yy + 1)

    def poly(self, pts):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(xs[k], y, xs[k + 1] + 1, y + 1)

    def thick_line(self, x0, y0, x1, y1, w):
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * w / 2.0, dx / ln * w / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                  (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])

    def arc_pts(self, cx, cy, rx, ry, a0, a1, steps=28):
        pts = []
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        return pts

    def ring(self, cx, cy, rx, ry, t, a0=0, a1=360):
        outer = self.arc_pts(cx, cy, rx, ry, a0, a1)
        inner = self.arc_pts(cx, cy, max(0.5, rx - t), max(0.5, ry - t), a1, a0)
        self.poly(outer + inner)

    def blit(self, cv, ox, oy, color):
        # downsample SSxSS mask blocks onto canvas with alpha blend
        gw, gh = self.w // SS, self.h // SS
        r, g, b = color
        for gy in range(gh):
            cy = oy + gy
            if cy < 0 or cy >= cv.h:
                continue
            for gx in range(gw):
                cx = ox + gx
                if cx < 0 or cx >= cv.w:
                    continue
                s = 0
                for dy in range(SS):
                    base = (gy * SS + dy) * self.w + gx * SS
                    for dx in range(SS):
                        s += self.m[base + dx]
                a = s / (SS * SS * 255.0)
                if a <= 0:
                    continue
                i = (cy * cv.w + cx) * 3
                if a >= 1:
                    cv.px[i], cv.px[i + 1], cv.px[i + 2] = r, g, b
                else:
                    cv.px[i] = int(cv.px[i] * (1 - a) + r * a)
                    cv.px[i + 1] = int(cv.px[i + 1] * (1 - a) + g * a)
                    cv.px[i + 2] = int(cv.px[i + 2] * (1 - a) + b * a)

# ---------------------------------------------------------------- glyphs
# Glyph space: cap height 100 units, baseline y=100, mask height 124 units
# (24 below baseline for comma / Q tail / J hook). One builder per letter,
# parameterised by style: serif=True -> Didone (thick stem, hairline bars,
# bracketed serifs); serif=False -> Helvetica-style sans (even stem).
def _stem(m, u, x, w, S):
    m.rect(x * u, 0, (x + w) * u, 100 * u)
    if S["serif"]:
        m.rect((x - 5) * u, 0, (x + w + 5) * u, 5 * u)
        m.rect((x - 5) * u, 95 * u, (x + w + 5) * u, 100 * u)

def _bar(m, u, x0, x1, y, t, S):
    m.rect(x0 * u, y * u, x1 * u, (y + t) * u)
    if S["serif"] and t <= 6:
        # hairline bars get tiny end serifs on horizontal strokes
        pass

def _diag(m, u, x0, y0, x1, y1, w):
    m.thick_line(x0 * u, y0 * u, x1 * u, y1 * u, w * u)

def _bowl(m, u, cx, cy, rx, ry, t):
    m.ring(cx * u, cy * u, rx * u, ry * u, t * u)

def _foot(m, u, x, w, S):
    if S["serif"]:
        m.rect((x - 5) * u, 95 * u, (x + w + 5) * u, 100 * u)

def _glyph_draw(ch, m, u, S, wd):
    st = S["stem"]; hr = S["hair"]
    if ch == "A":
        _diag(m, u, 8, 100, 34, 0, st); _diag(m, u, 60, 100, 34, 0, st)
        _bar(m, u, 20, 48, 62, hr + 1, S); _foot(m, u, 2, st, S); _foot(m, u, 54, st, S)
    elif ch == "B":
        _stem(m, u, 6, st, S)
        _bowl(m, u, 34, 26, 26, 26, st); _bowl(m, u, 34, 74, 28, 26, st)
        m.rect(6 * u, 0, 40 * u, 6 * u); m.rect(6 * u, 48 * u, 42 * u, 54 * u)
        m.rect(6 * u, 94 * u, 42 * u, 100 * u)
    elif ch == "C":
        m.ring(36 * u, 50 * u, 32 * u, 50 * u, st * u, 55, 305)
        _bar(m, u, 58, 70, 12, hr + 2, S); _bar(m, u, 58, 70, 82, hr + 2, S)
    elif ch == "D":
        _stem(m, u, 6, st, S)
        m.ring(34 * u, 50 * u, 30 * u, 50 * u, st * u, -90, 90)
        m.rect(6 * u, 0, 38 * u, 6 * u); m.rect(6 * u, 94 * u, 38 * u, 100 * u)
    elif ch == "E":
        _stem(m, u, 6, st, S)
        _bar(m, u, 6, 62, 0, hr + 1, S); _bar(m, u, 6, 52, 47, hr + 1, S)
        _bar(m, u, 6, 62, 94, hr + 1, S)
    elif ch == "F":
        _stem(m, u, 6, st, S)
        _bar(m, u, 6, 60, 0, hr + 1, S); _bar(m, u, 6, 50, 47, hr + 1, S)
    elif ch == "G":
        m.ring(36 * u, 50 * u, 32 * u, 50 * u, st * u, 55, 305)
        _bar(m, u, 58, 70, 12, hr + 2, S)
        m.rect(36 * u, 50 * u, 70 * u, 56 * u); m.rect(58 * u, 50 * u, 70 * u, 88 * u)
    elif ch == "H":
        _stem(m, u, 6, st, S); _stem(m, u, 54, st, S)
        _bar(m, u, 6, 70, 47, hr + 1, S)
    elif ch == "I":
        _stem(m, u, 26, st, S)
        _bar(m, u, 12, 54, 0, hr + 1, S); _bar(m, u, 12, 54, 94, hr + 1, S)
    elif ch == "J":
        m.ring(34 * u, 78 * u, 26 * u, 30 * u, st * u, 0, 180)
        _stem(m, u, 48, st, S); _bar(m, u, 34, 68, 0, hr + 1, S)
    elif ch == "K":
        _stem(m, u, 6, st, S)
        _diag(m, u, 22, 50, 62, 0, st); _diag(m, u, 30, 46, 64, 100, st)
    elif ch == "L":
        _stem(m, u, 6, st, S); _bar(m, u, 6, 60, 94, hr + 1, S)
    elif ch == "M":
        _stem(m, u, 4, st, S); _stem(m, u, 66, st, S)
        _diag(m, u, 18, 0, 40, 62, hr + 3); _diag(m, u, 62, 0, 40, 62, hr + 3)
    elif ch == "N":
        _stem(m, u, 6, st, S); _stem(m, u, 56, st, S)
        _diag(m, u, 20, 0, 58, 100, hr + 3)
    elif ch == "O":
        m.ring(36 * u, 50 * u, 32 * u, 50 * u, st * u)
    elif ch == "P":
        _stem(m, u, 6, st, S)
        m.ring(34 * u, 26 * u, 26 * u, 26 * u, st * u, -90, 90)
        m.rect(6 * u, 0, 38 * u, 6 * u); m.rect(6 * u, 46 * u, 38 * u, 52 * u)
    elif ch == "Q":
        m.ring(36 * u, 50 * u, 32 * u, 50 * u, st * u)
        _diag(m, u, 48, 66, 72, 108, hr + 3)
    elif ch == "R":
        _stem(m, u, 6, st, S)
        m.ring(34 * u, 26 * u, 26 * u, 26 * u, st * u, -90, 90)
        m.rect(6 * u, 0, 38 * u, 6 * u); m.rect(6 * u, 46 * u, 38 * u, 52 * u)
        _diag(m, u, 30, 48, 66, 100, st)
    elif ch == "S":
        m.ring(34 * u, 28 * u, 28 * u, 26 * u, st * u, 60, 340)
        m.ring(34 * u, 74 * u, 28 * u, 26 * u, st * u, -80, 200)
    elif ch == "T":
        _bar(m, u, 4, 70, 0, hr + 1, S); _stem(m, u, 28, st, S)
    elif ch == "U":
        m.ring(34 * u, 66 * u, 28 * u, 34 * u, st * u, 0, 180)
        _stem(m, u, 6, st, S); _stem(m, u, 54, st, S)
        m.rect(6 * u, 0, 6 * u + st * u, 66 * u); m.rect(54 * u, 0, 54 * u + st * u, 66 * u)
    elif ch == "V":
        _diag(m, u, 6, 0, 34, 100, st); _diag(m, u, 62, 0, 34, 100, st)
    elif ch == "W":
        _diag(m, u, 4, 0, 20, 100, st); _diag(m, u, 20, 100, 36, 0, st)
        _diag(m, u, 36, 0, 52, 100, st); _diag(m, u, 52, 100, 68, 0, st)
    elif ch == "X":
        _diag(m, u, 6, 0, 62, 100, st); _diag(m, u, 62, 0, 6, 100, st)
    elif ch == "Y":
        _diag(m, u, 6, 0, 34, 48, st); _diag(m, u, 62, 0, 34, 48, st)
        _stem(m, u, 26, st, S)
        m.rect(26 * u, 48 * u, (26 + st) * u, 100 * u)
    elif ch == "Z":
        _bar(m, u, 6, 62, 0, hr + 1, S); _bar(m, u, 6, 62, 94, hr + 1, S)
        _diag(m, u, 58, 6, 10, 94, hr + 3)
    elif ch == "0":
        m.ring(32 * u, 50 * u, 28 * u, 50 * u, st * u)
        _diag(m, u, 16, 82, 48, 18, hr + 1)
    elif ch == "1":
        _diag(m, u, 36, 0, 16, 22, hr + 2); _stem(m, u, 28, st, S)
        _bar(m, u, 14, 50, 94, hr + 1, S)
    elif ch == "2":
        m.ring(32 * u, 28 * u, 26 * u, 26 * u, st * u, 180, 360)
        _diag(m, u, 56, 52, 10, 94, hr + 3); _bar(m, u, 8, 58, 94, hr + 1, S)
    elif ch == "3":
        m.ring(34 * u, 26 * u, 26 * u, 24 * u, st * u, 200, 480)
        m.ring(34 * u, 74 * u, 26 * u, 24 * u, st * u, 300, 560)
    elif ch == "4":
        _diag(m, u, 46, 0, 10, 58, hr + 3); _stem(m, u, 40, st, S)
        _bar(m, u, 8, 58, 56, hr + 1, S)
    elif ch == "5":
        _bar(m, u, 8, 58, 0, hr + 1, S); _stem(m, u, 8, st, S)
        m.rect(8 * u, 0, (8 + st) * u, 50 * u)
        m.ring(34 * u, 74 * u, 26 * u, 24 * u, st * u, 300, 560)
    elif ch == "6":
        m.ring(32 * u, 52 * u, 28 * u, 48 * u, st * u, 150, 360)
        m.ring(32 * u, 74 * u, 26 * u, 24 * u, st * u)
    elif ch == "7":
        _bar(m, u, 8, 60, 0, hr + 1, S); _diag(m, u, 56, 6, 20, 100, hr + 3)
    elif ch == "8":
        m.ring(32 * u, 28 * u, 24 * u, 24 * u, st * u)
        m.ring(32 * u, 72 * u, 26 * u, 26 * u, st * u)
    elif ch == "9":
        m.ring(32 * u, 28 * u, 26 * u, 24 * u, st * u)
        m.ring(32 * u, 50 * u, 28 * u, 48 * u, st * u, 300, 540)
    elif ch == ".":
        m.rect(28 * u, 88 * u, 40 * u, 100 * u)
    elif ch == ",":
        m.rect(28 * u, 88 * u, 40 * u, 100 * u)
        _diag(m, u, 38, 98, 28, 118, hr + 1)
    elif ch == ":":
        m.rect(28 * u, 38 * u, 40 * u, 50 * u); m.rect(28 * u, 76 * u, 40 * u, 88 * u)
    elif ch == ";":
        m.rect(28 * u, 38 * u, 40 * u, 50 * u); m.rect(28 * u, 76 * u, 40 * u, 88 * u)
        _diag(m, u, 38, 86, 28, 106, hr + 1)
    elif ch == "-":
        _bar(m, u, 10, 54, 46, hr + 1, S)
    elif ch == "\u2013":  # en dash
        _bar(m, u, 6, 62, 46, hr + 1, S)
    elif ch == "\u2014":  # em dash
        _bar(m, u, 2, 66, 46, hr + 1, S)
    elif ch == "'":
        _diag(m, u, 34, 0, 26, 26, hr + 2)
    elif ch == "(":
        m.ring(52 * u, 50 * u, 30 * u, 52 * u, st * u, 90, 270)
    elif ch == ")":
        m.ring(16 * u, 50 * u, 30 * u, 52 * u, st * u, -90, 90)
    elif ch == "%":
        m.ring(20 * u, 26 * u, 14 * u, 22 * u, hr + 2)
        m.ring(48 * u, 74 * u, 14 * u, 22 * u, hr + 2)
        _diag(m, u, 56, 6, 12, 94, hr + 2)
    elif ch == "+":
        _bar(m, u, 8, 60, 44, hr + 2, S); m.rect(28 * u, 16 * u, 40 * u, 76 * u)
    elif ch == "$":
        m.ring(34 * u, 28 * u, 26 * u, 24 * u, st * u, 60, 340)
        m.ring(34 * u, 74 * u, 26 * u, 24 * u, st * u, -80, 200)
        m.rect(30 * u, -4 * u, 38 * u, 104 * u)
    elif ch == "\u00b7":  # middle dot
        m.rect(28 * u, 44 * u, 40 * u, 56 * u)
    elif ch == "/":
        _diag(m, u, 50, 0, 18, 100, hr + 2)
    elif ch == "!":
        _stem(m, u, 28, st, S); m.rect(28 * u, 84 * u, 40 * u, 100 * u)
    elif ch == "?":
        m.ring(34 * u, 28 * u, 26 * u, 26 * u, st * u, 150, 510)
        _diag(m, u, 48, 50, 34, 66, hr + 2)
        m.rect(28 * u, 82 * u, 40 * u, 100 * u)
    elif ch == "&":
        m.ring(34 * u, 30 * u, 22 * u, 24 * u, hr + 2)
        m.ring(34 * u, 72 * u, 26 * u, 26 * u, hr + 2, 200, 560)
        _diag(m, u, 20, 60, 58, 100, hr + 2)
    elif ch == '"':
        _diag(m, u, 22, 0, 16, 22, hr + 2); _diag(m, u, 46, 0, 40, 22, hr + 2)

ADV = {
    "A": 68, "B": 66, "C": 70, "D": 68, "E": 62, "F": 58, "G": 72, "H": 72,
    "I": 52, "J": 62, "K": 68, "L": 60, "M": 84, "N": 74, "O": 72, "P": 64,
    "Q": 74, "R": 68, "S": 66, "T": 68, "U": 72, "V": 68, "W": 92, "X": 68,
    "Y": 66, "Z": 64, "0": 64, "1": 58, "2": 62, "3": 62, "4": 64, "5": 62,
    "6": 64, "7": 62, "8": 64, "9": 64, ".": 40, ",": 40, ":": 40, ";": 40,
    "-": 56, "\u2013": 62, "\u2014": 68, "'": 34, "(": 44, ")": 44, "%": 68,
    "+": 62, "$": 66, "\u00b7": 40, "/": 56, "!": 46, "?": 62, "&": 68,
    '"': 52, " ": 30,
}

SERIF = {"stem": 17, "hair": 5, "serif": True}
SANS = {"stem": 14, "hair": 6, "serif": False}

_cache = {}

def glyph_mask(ch, size, serif):
    key = (ch, size, serif)
    if key in _cache:
        return _cache[key]
    adv = ADV.get(ch, 30)
    u = size / 100.0 * SS
    mw = max(SS, int(math.ceil(adv * u)))
    mh = int(math.ceil(124 * u))
    m = Mask(mw, mh)
    S = SERIF if serif else SANS
    _glyph_draw(ch, m, u, S, adv)
    out = (m, mw // SS, mh // SS)
    _cache[key] = out
    return out

def text_width(s, size, serif, tracking=0):
    w = 0
    for ch in s:
        w += ADV.get(ch, 30) * size / 100.0 + tracking
    return w

def draw_text(cv, x, y, s, size, color, serif=True, tracking=0, align="left"):
    # y = top of cap height
    w = text_width(s, size, serif, tracking)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    cx = x
    for ch in s:
        if ch != " ":
            m, gw, gh = glyph_mask(ch, size, serif)
            m.blit(cv, int(round(cx)), int(round(y)), color)
        cx += ADV.get(ch, 30) * size / 100.0 + tracking
    return w

def wrap_text(s, size, serif, maxw, tracking=0):
    words = s.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(trial, size, serif, tracking) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- globe
LAT0, LON0 = 25.0, 30.0

def _proj(lat, lon, cx, cy, r):
    la, lo = math.radians(lat), math.radians(lon - LON0)
    p0 = math.radians(LAT0)
    x = math.cos(la) * math.sin(lo)
    y = math.cos(p0) * math.sin(la) - math.sin(p0) * math.cos(la) * math.cos(lo)
    vis = math.sin(p0) * math.sin(la) + math.cos(p0) * math.cos(la) * math.cos(lo)
    return cx + x * r, cy - y * r, vis > 0.02

# Coarse hand-drawn coastlines from real lat/lon. Europe's east edge stops
# near 30E; Asia's west edge starts near 42E, so the Black Sea / Urals gap
# between them stays open at mid-latitudes.
AFRICA = [(35, -6), (35, 10), (31, 32), (27, 33), (22, 37), (18, 39),
          (15, 40), (11, 43), (10, 51), (4, 47), (-1, 41), (-10, 40),
          (-18, 35), (-26, 33), (-34, 20), (-34, 18), (-28, 16),
          (-17, 12), (-12, 13), (-8, 13), (-1, 9), (4, 6), (6, -3),
          (5, -8), (8, -13), (10, -16), (15, -17), (20, -17), (27, -13),
          (31, -10)]
EUROPE = [(36, -9), (38, -9), (43, -9), (44, -2), (46, -2), (48, -5),
          (49, 0), (51, 2), (53, 4), (55, 8), (57, 8), (58, 5), (60, 5),
          (62, 6), (64, 11), (68, 14), (70, 19), (70, 30), (66, 32),
          (60, 28), (55, 24), (50, 28), (46, 30), (44, 28), (41, 28),
          (38, 27), (36, 26), (38, 23), (40, 22), (42, 19), (44, 15),
          (44, 12), (43, 10), (44, 8), (43, 5), (42, 3), (40, 0),
          (38, -1), (36, -6)]
ASIA = [(42, 42), (44, 44), (46, 48), (48, 50), (52, 55), (55, 60),
        (58, 68), (62, 72), (66, 72), (70, 75), (72, 80), (73, 90),
        (72, 100), (70, 110), (68, 120), (66, 130), (62, 140), (60, 150),
        (60, 162), (58, 162), (55, 158), (52, 156), (50, 142), (48, 140),
        (45, 135), (43, 132), (40, 128), (38, 122), (35, 120), (32, 120),
        (30, 122), (28, 121), (25, 118), (22, 114), (20, 110), (18, 106),
        (15, 105), (12, 109), (10, 105), (8, 100), (6, 98), (5, 100),
        (2, 102), (0, 104), (-2, 106), (-6, 106), (-8, 110), (-8, 114),
        (-6, 118), (-4, 120), (-2, 122), (0, 120), (2, 118), (5, 116),
        (8, 114), (12, 110), (15, 108), (18, 106), (20, 108), (22, 110),
        (24, 108), (28, 104), (30, 100), (32, 96), (34, 92), (36, 88),
        (38, 82), (40, 76), (42, 70), (42, 64), (42, 58), (42, 52),
        (42, 46)]
ARABIA = [(12, 44), (14, 48), (16, 52), (18, 56), (20, 58), (22, 59),
          (24, 58), (26, 56), (28, 52), (29, 48), (30, 47), (28, 44),
          (24, 42), (20, 40), (17, 42), (14, 42)]
INDIA = [(8, 77), (10, 80), (14, 80), (17, 82), (20, 86), (22, 88),
         (21, 91), (18, 93), (14, 94), (10, 92), (8, 90), (7, 85), (6, 80)]
UK = [(50, -5), (51, -3), (53, -3), (55, -2), (57, -2), (58, -4), (56, -6),
      (54, -5), (52, -5), (50, -5)]

def draw_globe(cv, cx, cy, r, pins):
    # ocean: concentric depth rings
    for k in range(6, 0, -1):
        rr = r * k / 6.0
        shade = (26 + k * 4, 62 + k * 6, 92 + k * 6)
        cv.ellipse(cx, cy, rr, rr, shade)
    cv.ellipse(cx, cy, r, r, (30, 74, 104))
    # gold-lit western rim
    cv.ring(cx, cy, r - 1, r - 1, 3, GOLD, 100, 260)
    for poly, col in ((AFRICA, LAND), (EUROPE, LAND), (ASIA, LAND2),
                      (ARABIA, LAND), (INDIA, LAND), (UK, LAND)):
        pts = []
        for lat, lon in poly:
            x, y, v = _proj(lat, lon, cx, cy, r)
            # clamp points past the limb onto the globe edge instead of
            # dropping the whole continent when one vertex is just hidden
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d > r * 0.995:
                x, y = cx + dx / d * r * 0.995, cy + dy / d * r * 0.995
            pts.append((x, y))
        if len(pts) > 2:
            cv.poly(pts, col)
    # clouds: pale arcs
    cv.ellipse(cx - r * 0.45, cy - r * 0.55, 26, 7, (210, 225, 232))
    cv.ellipse(cx + r * 0.30, cy + r * 0.35, 30, 8, (200, 218, 228))
    cv.ellipse(cx + r * 0.10, cy - r * 0.75, 20, 6, (205, 222, 230))
    # pins: dot at the true spot, numbered badge offset with a leader line
    # (Warsaw/Kyiv/Antalya and The Hague/London/Copenhagen would collide)
    OFF = {1: (14, -12), 2: (14, 12), 3: (12, 14), 4: (0, 0), 5: (-14, -10),
           6: (-16, 8), 7: (10, -14), 8: (0, 0)}
    for num, lat, lon in pins:
        x, y, v = _proj(lat, lon, cx, cy, r)
        if not v:
            continue
        ox, oy = OFF.get(num, (0, 0))
        bx, by = int(x) + ox, int(y) + oy
        cv.circle(int(x), int(y), 2, WHITE)
        if ox or oy:
            cv.thick_line(int(x), int(y), bx, by, 1, WHITE)
        cv.circle(bx, by, 7, RED)
        cv.circle(bx, by, 7, WHITE)
        cv.circle(bx, by, 6, RED)
        draw_text(cv, bx, by - 4, str(num), 8, WHITE, serif=False, align="center")

# ---------------------------------------------------------------- vignettes
def vignette_frame(cv, x, y, w, h, title, sub):
    cv.rect(x, y, x + w, y + h, NAVY2)
    cv.rect(x + 1, y + 1, x + w - 1, y + h - 1, (24, 40, 70))
    draw_text(cv, x + 6, y + 4, title, 10, GOLD2, serif=False, tracking=1)
    draw_text(cv, x + 6, y + h - 12, sub, 8, (220, 220, 205), serif=False)

def vig_poland(cv, x, y, w, h):
    vignette_frame(cv, x, y, w, h, "POLAND — RUTTE IN WARSAW", "SAT 21 NOV · NATO CHIEF VISITS")
    cv.rect(x + 1, y + 16, x + w - 1, y + h - 14, (28, 52, 96))
    cv.rect(x + 1, y + h - 34, x + w - 1, y + h - 14, (52, 96, 58))
    for tx in (x + 20, x + 44, x + 70):
        cv.poly([(tx, y + h - 34), (tx + 10, y + h - 62), (tx + 20, y + h - 34)], (28, 70, 40))
    # distant jet
    cv.poly([(x + 120, y + 30), (x + 168, y + 26), (x + 120, y + 36)], (230, 230, 225))
    cv.poly([(x + 140, y + 28), (x + 148, y + 20), (x + 152, y + 28)], (230, 230, 225))
    cv.circle(x + 190, y + 42, 5, GOLD)
    for a in range(8):
        ang = a * math.pi / 4
        cv.thick_line(x + 190, y + 42, x + 190 + 11 * math.cos(ang), y + 42 + 11 * math.sin(ang), 1, GOLD2)

def vig_gaza(cv, x, y, w, h):
    vignette_frame(cv, x, y, w, h, "GAZA — CIVILIANS RETURN", "HOMES DAMAGED · NO DATE CLAIMED")
    cv.rect(x + 1, y + 16, x + w - 1, y + h - 14, (214, 196, 158))
    cv.rect(x + 1, y + h - 30, x + w - 1, y + h - 14, (190, 168, 128))
    for hx in (x + 14, x + 78, x + 142, x + 196):
        cv.rect(hx, y + h - 56, hx + 44, y + h - 30, (168, 138, 100))
        cv.poly([(hx - 3, y + h - 56), (hx + 22, y + h - 72), (hx + 47, y + h - 56)], (140, 106, 72))
        cv.rect(hx + 18, y + h - 44, hx + 26, y + h - 30, (90, 70, 50))
    for fx in (x + 66, x + 130):
        cv.circle(fx, y + h - 38, 4, (40, 52, 80))
        cv.rect(fx - 3, y + h - 34, fx + 3, y + h - 20, (40, 52, 80))

def vig_hague(cv, x, y, w, h):
    vignette_frame(cv, x, y, w, h, "THE HAGUE — JUSTICE", "ICJ RULING WAS 19 NOV · SEE CONTEXT")
    cv.rect(x + 1, y + 16, x + w - 1, y + h - 14, (24, 40, 70))
    for cx0 in (x + 30, x + 62, x + 94, x + 126):
        cv.rect(cx0, y + 34, cx0 + 8, y + h - 22, (232, 226, 210))
    cv.rect(x + 20, y + 26, x + 146, y + 34, (232, 226, 210))
    cv.rect(x + 16, y + h - 22, x + 150, y + h - 14, (232, 226, 210))
    # scales
    sx = x + 190
    cv.vline(sx, y + 30, y + h - 22, GOLD2, 2)
    cv.hline(sx - 18, sx + 18, y + 34, GOLD2, 2)
    cv.thick_line(sx - 18, y + 34, sx - 28, y + 52, 1, GOLD2)
    cv.thick_line(sx - 18, y + 34, sx - 8, y + 52, 1, GOLD2)
    cv.poly([(sx - 30, y + 52), (sx - 6, y + 52), (sx - 18, y + 64)], GOLD)
    cv.thick_line(sx + 18, y + 34, sx + 8, y + 52, 1, GOLD2)
    cv.thick_line(sx + 18, y + 34, sx + 28, y + 52, 1, GOLD2)
    cv.poly([(sx + 6, y + 52), (sx + 30, y + 52), (sx + 18, y + 64)], GOLD)

def vig_markets(cv, x, y, w, h):
    vignette_frame(cv, x, y, w, h, "MARKETS — TECH SELLS OFF", "CORRECTION REPORTED SAT 21 NOV")
    cv.rect(x + 1, y + 16, x + w - 1, y + h - 14, (24, 40, 70))
    pts = [(x + 12 + i * 18, y + 26 + i * 3) for i in range(10)]
    for i in range(len(pts) - 1):
        cv.thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 2, RED)
    for i, bh in enumerate((14, 20, 12, 26, 18, 30, 22, 34, 28, 38)):
        bx = x + 120 + i * 10
        cv.rect(bx, y + h - 16 - bh, bx + 7, y + h - 16, (178, 52, 38) if i % 2 else (150, 44, 34))
    # circuit traces
    cv.hline(x + 12, x + 100, y + h - 24, GOLD2, 1)
    cv.vline(x + 40, y + h - 40, y + h - 24, GOLD2, 1)
    cv.vline(x + 75, y + h - 34, y + h - 24, GOLD2, 1)
    cv.circle(x + 40, y + h - 40, 2, GOLD2)
    cv.circle(x + 75, y + h - 34, 2, GOLD2)

def summit_figure(cv, x, y, w, flag, name, skin, hair):
    # small stylised bust: no photoreal face, flag above, name below
    fx = x + w // 2 - 14
    if flag == "US":
        cv.rect(fx, y, fx + 28, y + 16, (178, 52, 48))
        for sy in (y + 3, y + 8, y + 13):
            cv.hline(fx, fx + 28, sy, WHITE, 2)
        cv.rect(fx, y, fx + 12, y + 8, (40, 60, 120))
    elif flag == "RU":
        cv.rect(fx, y, fx + 28, y + 16, WHITE)
        cv.rect(fx, y + 5, fx + 28, y + 11, (40, 90, 160))
        cv.rect(fx, y + 11, fx + 28, y + 16, (178, 40, 36))
    else:  # CN
        cv.rect(fx, y, fx + 28, y + 16, (178, 40, 36))
        cv.circle(fx + 7, y + 5, 2, GOLD2)
    cv.circle(x + w // 2, y + 34, 11, skin)
    cv.ellipse(x + w // 2, y + 26, 11, 5, hair)
    cv.poly([(x + 6, y + 62), (x + w // 2 - 8, y + 46), (x + w // 2 + 8, y + 46),
             (x + w - 6, y + 62)], (30, 32, 40))
    cv.poly([(x + w // 2 - 3, y + 46), (x + w // 2 + 3, y + 46),
             (x + w // 2, y + 62)], (150, 40, 34))
    draw_text(cv, x + w // 2, y + 66, name, 9, (235, 230, 215), serif=False, align="center")

# ---------------------------------------------------------------- content
# All 36 strip stories happened or were first reported Sat 21 Nov 2026.
# Friday events appear ONLY in the DATE CHECK / CONTEXT. See STORIES.md.
BIG_FEATURES = [
    ("COP31", "CLIMATE TALKS IN OVERTIME",
     "COP31 IN ANTALYA PASSED ITS FRIDAY DEADLINE WITH NO DEAL. A THIRD DRAFT WAS DUE SATURDAY MORNING.",
     "DRAFT 144 TO 80 · 1.5C NAMED · NO FUELS"),
    ("RIYADH", "THREE MISSILES DOWN",
     "SAUDI DEFENCES INTERCEPTED THREE HOUTHI BALLISTIC MISSILES HEADED FOR RIYADH IN THE EARLY HOURS OF SATURDAY.",
     "3 DOWN · ALERT 01:53 · 2ND ATTACK IN DAYS"),
    ("KYIV", "COUNTS ITS DEAD",
     "THE TOLL OF FRIDAY NIGHT'S BARRAGE WAS CONFIRMED SATURDAY: 7 DEAD IN KYIV, 3 BRIDGES HIT; 2 DEAD, 42 HURT IN KRYVYI RIH.",
     "7 DEAD IN KYIV · 2 IN KRYVYI RIH · 42 HURT"),
    ("MERCURY", "THE 8-YEAR VOYAGE ENDS",
     "THE ESA-JAXA BEPICOLOMBO PROBE WAS CAPTURED BY MERCURY'S GRAVITY ON SATURDAY, ONLY THE 2ND CRAFT EVER TO ORBIT IT.",
     "8 YEARS · 2 ORBITERS · SCIENCE APR 2027"),
]

MED_FEATURES = [
    ("RUTTE", "FLIES TO WARSAW",
     "NATO CHIEF IN WARSAW SATURDAY AS POLAND SEEKS MORE EASTERN SENTRY TROOPS. VISIT SAT 21 NOV."),
    ("PEACE", "28-POINT PLAN LANDS IN KYIV",
     "ZELENSKYY'S OFFICE CONFIRMED KYIV RECEIVED THE US DRAFT; TALKS WITH TRUMP TO FOLLOW. 28 POINTS."),
    ("YEMEN", "SIX HOUTHI SITES HIT",
     "THE SAUDI-LED COALITION SAID IT DESTROYED SIX MISSILE AND DRONE WORKSHOPS IN SANA'A. REPORTED SAT."),
    ("WALL ST", "IN CORRECTION",
     "STOCKS SKIDDED INTO CORRECTION AS AI WORRIES INTENSIFIED; THE SELL-OFF LED SATURDAY'S PAPERS. S&P -3.7%."),
    ("PERU", "QUAKE 6.8 SHAKES JUNIN",
     "A MAGNITUDE 6.8 QUAKE STRUCK JUNIN; TREMORS FELT IN LIMA, 320 KM AWAY. SATURDAY'S LEAD QUAKE STORY. M6.8."),
    ("INDIA", "RECORD CASH INFLOW",
     "FOREIGN INVESTORS POURED A RECORD RS 1.22 LAKH CRORE INTO INDIAN SHARES IN NOVEMBER. RECORD INFLOW."),
    ("PENTAGON", "US-CANADA TIES CURBED",
     "A CLASSIFIED PENTAGON MEMO SET NEW LIMITS ON US-CANADA MILITARY TIES, THE POST REPORTED SATURDAY."),
    ("KIM", "TOURS FACTORIES",
     "STATE MEDIA SAID SATURDAY KIM JONG UN INSPECTED SCHOOL EQUIPMENT SITES AFTER TRUMP'S ASIA TRIP. KCNA."),
    ("NORWAY", "OIL LICENCES RULED OUT",
     "NORWAY'S SUPREME COURT RULED CLIMATE-DISPUTED OIL LICENCES INVALID ON SATURDAY. TOP COURT."),
    ("EBOLA", "LAST PATIENT OUT",
     "KENYA DISCHARGED ITS LAST EBOLA PATIENT AS THE DRC DEATH TOLL PASSED 5,300. DRC TOLL 5,300."),
]

STRIP = [
    "COP31 — OVERTIME, NO DEAL", "RIYADH — 3 MISSILES DOWN",
    "KYIV — TOLL CONFIRMED SAT", "BEPICOLOMBO — MERCURY",
    "RUTTE — WARSAW SAT", "PEACE — 28-PT PLAN",
    "YEMEN — 6 SITES HIT", "JAZAN — 2 MORE DOWN",
    "WALL ST — CORRECTION", "KIM — FACTORY TOUR",
    "PERU — QUAKE 6.8", "INDIA — FPI RECORD",
    "NEPAL — PM TO DELHI", "RAHUL — SENA CENTURY",
    "PENTAGON — CANADA MEMO", "IRAN — OIL SANCTIONS",
    "IRGC — US DRONE CLAIM", "TRUMP — DATA-CENTRE BAN",
    "UFO — FILES RELEASED", "FRENCH POLICE — JAILED",
    "CEUTA — MIGRANT CRISIS", "AFD — SAXONY-ANHALT WIN",
    "NORWAY — OIL LICENCES VOID", "GHANA — NEW BANKNOTES",
    "KENYA — EBOLA PATIENT OUT", "DRC — EBOLA TOLL 5,300",
    "SWISS — ICJ RULING HAILED", "RUBIO — ATHENS TALKS",
    "GUINEA — BANS RTB", "NIGERIA — NAVAL SHIPS",
    "TSHISEKEDI — REFORM LAW", "KENYA — 293,600 SAUDI JOBS",
    "S. AFRICA — PROTESTS BARRED", "ANTHROPIC — SLIDE CONTINUES",
    "TRUMP — NO KIM MEETING", "ECB — LAGARDE RESIGNS",
]

TIMELINE = [
    ("00:51 UTC", "RIYADH 3 DOWN"), ("01:51 UTC", "JAZAN 2 DOWN"),
    ("01:56 UTC", "COP31 OVERTIME"), ("SAT AM", "DRAFT 3 DUE"),
    ("SATURDAY", "MERCURY CAPTURE"), ("SATURDAY", "RUTTE WARSAW"),
]

PINS = [(1, 52.2, 21.0), (2, 50.4, 30.5), (3, 36.9, 30.7), (4, 22.5, 114.1),
        (5, 52.0, 4.3), (6, 51.5, -0.1), (7, 55.7, 12.6), (8, 19.3, 84.9)]

# ---------------------------------------------------------------- build
def build():
    cv = Canvas(W, H, CREAM)
    cv.rect(0, 0, W, 10, NAVY)
    # masthead
    draw_text(cv, W // 2, 12, "WORLD NEWS", 56, NAVY, serif=True, tracking=2, align="center")
    draw_text(cv, W // 2, 74, "SATURDAY, 21 NOVEMBER 2026", 15, INK, serif=False, tracking=7, align="center")
    cv.hline(20, 1004, 94, NAVY, 2)
    cv.hline(20, 1004, 98, NAVY, 1)
    # hero band
    cv.rect(0, 102, W, 272, NAVY)
    cv.rect(0, 102, W, 104, NAVY2)
    draw_globe(cv, 148, 188, 80, PINS)
    draw_text(cv, 250, 116, "COP31 IN OVERTIME", 38, CREAM, serif=True, tracking=1)
    draw_text(cv, 250, 166, "RIYADH: 3 MISSILES DOWN · BEPICOLOMBO REACHES MERCURY", 13, GOLD2, serif=False, tracking=1)
    draw_text(cv, 250, 188, "KYIV TOLL CONFIRMED · RUTTE IN WARSAW · 28-POINT PEACE PLAN", 11.5, (225, 225, 210), serif=False)
    draw_text(cv, 250, 210, "200 NATIONS · DRAFT 144 TO 80 · 1.5C NAMED · NO FOSSIL FUELS", 11.5, (200, 205, 220), serif=False)
    draw_text(cv, 250, 238, "SATURDAY 21 NOVEMBER 2026 — THE DAY'S NEWS IN ONE PAGE", 10, GOLD2, serif=False, tracking=1)
    # summit figures (19 Nov context, labelled as such)
    draw_text(cv, 922, 108, "SHENZHEN — 19 NOV", 9, GOLD2, serif=False, align="center")
    summit_figure(cv, 842, 126, 50, "US", "TRUMP", (232, 190, 160), (240, 210, 120))
    summit_figure(cv, 897, 126, 50, "CN", "XI JINPING", (228, 186, 152), (30, 28, 26))
    summit_figure(cv, 952, 126, 50, "RU", "PUTIN", (230, 188, 158), (200, 200, 200))
    draw_text(cv, 922, 234, "SEE CONTEXT BOX", 8, (190, 195, 210), serif=False, align="center")
    cv.hline(0, W, 272, GOLD, 2)
    # vignettes
    vig_poland(cv, 20, 278, 243, 78)
    vig_gaza(cv, 267, 278, 243, 78)
    vig_hague(cv, 514, 278, 243, 78)
    vig_markets(cv, 761, 278, 243, 78)
    # date check
    cv.rect(20, 362, 1004, 400, CRIMSON)
    draw_text(cv, W // 2, 366, "DATE CHECK — SHENZHEN SUMMIT + ICJ RULING WERE 19 NOV, NOT 21 NOV.", 11, WHITE, serif=False, align="center")
    draw_text(cv, W // 2, 382, "ALSO NOT SATURDAY: POLAND MISSILES, DENMARK PLOT, BAYER, RIKERS, MEASLES, AI CHIPS 900K — ALL 19–20 NOV.", 10, WHITE, serif=False, align="center")
    # context
    cv.rect(20, 404, 1004, 426, (232, 220, 170))
    draw_text(cv, W // 2, 409, "CONTEXT — 19 NOV (NOT TODAY'S NEWS): SHENZHEN — TRUMP, XI, PUTIN MEET · ICJ — MYANMAR GUILTY OF ROHINGYA GENOCIDE, 9–6.", 10, INK, serif=False, align="center")
    # also today header
    draw_text(cv, 20, 430, "ALSO TODAY", 24, NAVY, serif=True)
    draw_text(cv, 1004, 438, "36 STORIES · 7 REGIONS · SOURCES: REUTERS, AP, BBC, ESA", 10, GREY, serif=False, align="right")
    cv.hline(20, 1004, 458, NAVY, 1)
    # big features 2x2
    y = 464
    for r in range(2):
        for c in range(2):
            tag, head, body, stat = BIG_FEATURES[r * 2 + c]
            x = 20 + c * 497
            draw_text(cv, x, y, tag, 10, CRIMSON, serif=False, tracking=1)
            draw_text(cv, x, y + 13, head, 16, INK, serif=True)
            bl = wrap_text(body, 10.5, False, 487)
            for i, ln in enumerate(bl[:2]):
                draw_text(cv, x, y + 33 + i * 12, ln, 10.5, (52, 54, 66), serif=False)
            draw_text(cv, x, y + 59, stat, 10, (150, 110, 30), serif=False, tracking=1)
        y += 72
    cv.vline(511, 464, 608, LGREY, 1)
    cv.hline(20, 1004, 536, LGREY, 1)
    # medium features 2 cols x 5 rows
    y = 612
    for r in range(5):
        for c in range(2):
            tag, head, body = MED_FEATURES[r * 2 + c]
            x = 20 + c * 497
            draw_text(cv, x, y, tag + " — " + head, 12.5, INK, serif=True)
            bl = wrap_text(body, 9.5, False, 487)
            for i, ln in enumerate(bl[:2]):
                draw_text(cv, x, y + 16 + i * 11, ln, 9.5, (52, 54, 66), serif=False)
        y += 38
    cv.vline(511, 612, 802, LGREY, 1)
    # strip: 36 stories, 3 cols x 12 rows, all 21 NOV
    cv.hline(20, 1004, 806, NAVY, 1)
    for i, label in enumerate(STRIP):
        row, col = divmod(i, 3)
        x = 20 + col * 333
        yy = 812 + row * 11
        draw_text(cv, x, yy, "%02d %s" % (i + 1, label), 9, INK, serif=False)
        draw_text(cv, x + 320, yy, "21 NOV", 9, GREY, serif=False, align="right")
    # timeline UTC
    cv.hline(20, 1004, 944, NAVY, 1)
    draw_text(cv, 20, 948, "TIMELINE — UTC", 10, CRIMSON, serif=False, tracking=1)
    tl_x0, tl_x1 = 150, 1004
    cv.hline(tl_x0, tl_x1, 964, NAVY, 1)
    for i, (t, ev) in enumerate(TIMELINE):
        cx = tl_x0 + (tl_x1 - tl_x0) * (i + 0.5) / 6
        cv.circle(int(cx), 964, 3, CRIMSON)
        draw_text(cv, cx, 948, t, 8.5, GREY, serif=False, align="center")
        draw_text(cv, cx, 970, ev, 8.5, INK, serif=False, align="center")
    # numbers strip
    draw_text(cv, W // 2, 984, "THE DAY IN NUMBERS — 3 MISSILES DOWN OVER RIYADH · 9 DEAD IN KYIV BARRAGE · 42 HURT IN KRYVYI RIH · 6.8 PERU QUAKE · 28 PEACE POINTS · 8 YEARS TO MERCURY", 10, (150, 110, 30), serif=False, align="center")
    # bottom headline
    cv.hline(20, 1004, 996, NAVY, 1)
    draw_text(cv, W // 2, 1000, "THE WORLD AT A CROSSROADS", 22, NAVY, serif=True, tracking=1, align="center")
    return cv

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "MAKEFUN_OUTPUT_DIR", "/output") + "/entry.png"
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        out = os.path.join(sys.argv[1], "entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cv = build()
    write_png(out, cv.px, W, H)
    print("wrote", out, os.path.getsize(out), "bytes")

if __name__ == "__main__":
    main()
