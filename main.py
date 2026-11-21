#!/usr/bin/env python3
"""news-image-20261121 v3 — THE WORLD AT A CROSSROADS.

One front page for Saturday 21 November 2026: a Didone-serif masthead,
a stylised summit band, a shaded globe with eight numbered pins, four
story vignettes, a hero band, an honest DATE CHECK, a 19 NOV context box,
four feature stories with body text, and a 35-story strip — every dated
item happened or was first reported 20-21 Nov 2026.

Python 3 stdlib only (math, os, struct, zlib). No network, no fonts on
disk: every letter is drawn from vector outlines defined below and
rasterised at 4x supersampling, so the serif reads as smooth Didone
(thick verticals, hairline horizontals, thin bracketed serifs) instead
of a pixel font. Deterministic: two runs write byte-identical PNGs.
"""
import math
import os
import struct
import zlib

W = 1024
H = 1024
SS = 4  # supersampling factor for all text

# ---------------------------------------------------------------- palette
PAPER = (242, 234, 216)
INK = (18, 35, 63)        # navy ink on paper
NAVY = (14, 28, 51)       # dark field
NAVY2 = (22, 41, 74)      # vignette panel
GOLD = (201, 162, 39)
GOLD_L = (216, 178, 84)
CREAM = (242, 234, 216)
RED = (192, 57, 43)
CRIMSON = (126, 42, 36)
TEAL = (21, 94, 107)
TEAL_D = (13, 58, 74)
LAND = (217, 164, 65)
LAND_D = (190, 138, 44)
GREEN = (74, 124, 67)
SAND = (198, 168, 118)
SKIN = (222, 184, 150)
SKIN2 = (206, 164, 128)
SKIN3 = (232, 200, 168)
WHITE = (245, 244, 238)
GREY = (120, 128, 140)

# ------------------------------------------------------------------- image
class Img:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill(bg)

    def fill(self, c):
        r, g, b = c
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        """Blend colour c over pixel (x, y) with alpha a in 0..1."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0.0:
            i = (y * self.w + x) * 3
            if a >= 1.0:
                self.px[i], self.px[i + 1], self.px[i + 2] = c
            else:
                ia = 1.0 - a
                self.px[i] = int(self.px[i] * ia + c[0] * a + 0.5)
                self.px[i + 1] = int(self.px[i + 1] * ia + c[1] * a + 0.5)
                self.px[i + 2] = int(self.px[i + 2] * ia + c[2] * a + 0.5)

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        for y in range(y0, y1):
            base = (y * self.w + x0) * 3
            for x in range(x0, x1):
                i = base + (x - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = c

    def hline(self, x0, x1, y, c, t=1):
        for yy in range(int(y), int(y) + t):
            self.rect(x0, yy, x1, yy + 1, c)

    def vline(self, x, y0, y1, c, t=1):
        for xx in range(int(x), int(x) + t):
            self.rect(xx, y0, xx + 1, y1, c)


def poly_fill(img, pts, c):
    """Scanline-fill a polygon (list of (x, y)) with a solid colour."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(img.h - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for k in range(n):
            x0, yy0 = pts[k]
            x1, yy1 = pts[(k + 1) % n]
            if (yy0 <= yc < yy1) or (yy1 <= yc < yy0):
                if yy1 != yy0:
                    xs.append(x0 + (yc - yy0) * (x1 - x0) / (yy1 - yy0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(img.w, int(math.floor(xs[k + 1])))
            if xb > xa:
                img.rect(xa, y, xb, y + 1, c)


def disc(img, cx, cy, r, c):
    r = int(r)
    for y in range(int(cy) - r, int(cy) + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        img.rect(cx - dx, y, cx + dx + 1, y + 1, c)


def disc_blend(img, cx, cy, r, c, a):
    r = int(r)
    for y in range(int(cy) - r, int(cy) + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(int(cx) - dx, int(cx) + dx + 1):
            img.blend(x, y, c, a)


def ellipse_fill(img, cx, cy, rx, ry, c):
    rx = int(rx)
    ry = int(ry)
    for y in range(int(cy) - ry, int(cy) + ry + 1):
        dy = (y - cy) / max(1, ry)
        if abs(dy) >= 1:
            continue
        dx = int(rx * math.sqrt(1 - dy * dy))
        img.rect(cx - dx, y, cx + dx + 1, y + 1, c)


def ellipse_blend(img, cx, cy, rx, ry, c, a):
    rx = int(rx)
    ry = int(ry)
    for y in range(int(cy) - ry, int(cy) + ry + 1):
        dy = (y - cy) / max(1, ry)
        if abs(dy) >= 1:
            continue
        dx = int(rx * math.sqrt(1 - dy * dy))
        for x in range(int(cx) - dx, int(cx) + dx + 1):
            img.blend(x, y, c, a)


def line(img, x0, y0, x1, y1, c, t=1):
    """Thick line via small discs along the segment (short segments only)."""
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(math.hypot(dx, dy)))
    r = max(1, t // 2)
    for s in range(steps + 1):
        x = int(x0 + dx * s / steps)
        y = int(y0 + dy * s / steps)
        disc(img, x, y, r, c)


# ------------------------------------------------------- vector glyph kit
# Glyph space: em = 100 units, y UP, baseline y = 0, cap height 70.
# Every glyph is a list of polygons (each a list of (x, y) points).
# Polygons are built from rectangles, ellipses and elliptical ring arcs,
# which keeps stems, bowls and curves smooth at any size.

def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _ell(cx, cy, rx, ry, n=40):
    return [(cx + rx * math.cos(2 * math.pi * k / n),
             cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _arc(cx, cy, rx, ry, ix, iy, a0, a1, n=14):
    """Elliptical ring sector from angle a0 to a1 (degrees, y-up)."""
    if a1 < a0:
        a1 += 360.0
    pts = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    for k in range(n, -1, -1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append((cx + ix * math.cos(a), cy + iy * math.sin(a)))
    return pts


def _diag(x0, y0, x1, y1, w):
    dx = x1 - x0
    dy = y1 - y0
    L = math.hypot(dx, dy) or 1.0
    ox = -dy / L * w / 2.0
    oy = dx / L * w / 2.0
    return [(x0 + ox, y0 + oy), (x1 + ox, y1 + oy),
            (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)]


def _stem(x, y0, y1, w, serif=False):
    """Vertical stem; serif=True adds thin bracketed slabs top/bottom."""
    out = [_rect(x, y0, x + w, y1)]
    if serif:
        out.append(_rect(x - 5, y1 - 4, x + w + 5, y1))
        out.append(_rect(x - 5, y0, x + w + 5, y0 + 4))
        out.append([(x - 5, y1 - 4), (x, y1 - 4), (x, y1 - 11)])
        out.append([(x + w + 5, y1 - 4), (x + w, y1 - 4), (x + w, y1 - 11)])
        out.append([(x - 5, y0 + 4), (x, y0 + 4), (x, y0 + 11)])
        out.append([(x + w + 5, y0 + 4), (x + w, y0 + 4), (x + w, y0 + 11)])
    return out


def _bar(x0, x1, y, t):
    return [_rect(x0, y, x1, y + t)]


def _bowl(cx, cy, rx, ry, t, a0=-90.0, a1=90.0):
    """Right-side bowl: one ring arc of uniform thickness t."""
    return [_arc(cx, cy, rx, ry, rx - t, ry - t, a0, a1)]


def _ring(cx, cy, rx, ry, t):
    return [_arc(cx, cy, rx, ry, rx - t, ry - t, 0.0, 360.0)]


def _stroke(pts, w):
    """Thick polyline stroke: quads between points + joint discs."""
    out = []
    for a, b in zip(pts, pts[1:]):
        out.append(_diag(a[0], a[1], b[0], b[1], w))
    for (x, y) in pts:
        out.append(_ell(x, y, w / 2.0, w / 2.0, 12))
    return out


# S skeleton: top-right terminal, over the top, down the left to the
# middle, sweep right, down the right side, along the bottom to the
# lower-left terminal. (Two half-ring arcs leave the middle unjoined.)
_S_PTS = [(52, 64), (40, 68), (24, 66), (14, 58), (12, 46), (20, 36),
          (33, 33), (46, 30), (54, 22), (56, 12), (48, 4), (32, 2),
          (18, 6)]
_S_LOW = [(40, 44), (30, 48), (18, 46), (10, 40), (9, 32), (15, 26),
          (26, 24), (36, 21), (42, 15), (43, 8), (37, 2), (25, 1),
          (14, 4)]
# 2 skeleton: top bowl, diagonal down-left, base bar.
_2_PTS = [(14, 66), (28, 69), (44, 66), (53, 56), (48, 44), (34, 26),
          (20, 12), (12, 4)]


def _didone_bowl(cx, cy, rx, ry):
    """Full ring with Didone contrast: thick sides, hairline top/bottom."""
    return [
        _arc(cx, cy, rx, ry, rx - 14, ry - 14, -55, 55),
        _arc(cx, cy, rx, ry, rx - 5, ry - 5, 55, 125),
        _arc(cx, cy, rx, ry, rx - 14, ry - 14, 125, 235),
        _arc(cx, cy, rx, ry, rx - 5, ry - 5, 235, 305),
    ]

# ---------------------------------------------------------- serif (Didone)
# Uppercase + digits + punctuation. Thick verticals (15u), hairline
# horizontals (5u), thin serif slabs with tiny brackets.
S = {}  # char -> (advance, [polygons])


def _sg(ch, adv, polys):
    S[ch] = (adv, polys)


_sg('A', 74, [_diag(10, 0, 37, 70, 15), _diag(64, 0, 37, 70, 15),
              _rect(25, 26, 49, 31), _rect(32, 66, 42, 70),
              _rect(3, 0, 19, 4), _rect(55, 0, 71, 4)])
_sg('B', 68, _stem(6, 0, 70, 15, True)
    + _bar(6, 46, 66, 4) + _bar(6, 46, 33, 4) + _bar(6, 46, 0, 4)
    + _bowl(21, 50, 26, 17, 13) + _bowl(21, 17, 28, 17, 14))
_sg('C', 68, [_arc(34, 35, 28, 35, 14, 30, 110, 250),
              _arc(34, 35, 28, 35, 23, 30, 50, 110),
              _arc(34, 35, 28, 35, 23, 30, 250, 310),
              _rect(46, 59, 58, 63), _rect(46, 7, 58, 11)])
_sg('D', 70, _stem(6, 0, 70, 15, True)
    + _bar(6, 44, 66, 4) + _bar(6, 44, 0, 4)
    + _bowl(21, 35, 30, 35, 14, -75, 75))
_sg('E', 62, _stem(6, 0, 70, 15, True)
    + _bar(6, 58, 66, 4) + _bar(6, 50, 33, 4) + _bar(6, 58, 0, 4))
_sg('F', 58, _stem(6, 0, 70, 15, True)
    + _bar(6, 56, 66, 4) + _bar(6, 48, 33, 4))
_sg('G', 70, [_arc(34, 35, 28, 35, 14, 30, 110, 250),
              _arc(34, 35, 28, 35, 23, 30, 50, 110),
              _arc(34, 35, 28, 35, 23, 30, 250, 310),
              _rect(46, 59, 58, 63), _rect(40, 30, 64, 34), _rect(58, 26, 64, 52)])
_sg('H', 70, _stem(6, 0, 70, 15, True) + _stem(49, 0, 70, 15, True)
    + _bar(6, 64, 33, 5))
_sg('I', 40, _stem(13, 0, 70, 14, True)
    + _bar(6, 34, 66, 4) + _bar(6, 34, 0, 4))
_sg('J', 56, _stem(38, 8, 70, 14, True) + _bar(30, 52, 66, 4)
    + [_arc(30, 16, 16, 14, 8, 7, 180, 360), _rect(8, 0, 24, 4)])
_sg('K', 70, _stem(6, 0, 70, 15, True)
    + [_diag(21, 35, 58, 70, 13), _diag(21, 35, 58, 0, 13),
       _rect(52, 66, 64, 70), _rect(52, 0, 64, 4)])
_sg('L', 58, _stem(6, 0, 70, 15, True) + _bar(6, 54, 0, 4))
_sg('M', 80, _stem(6, 0, 70, 15, True) + _stem(59, 0, 70, 15, True)
    + [_diag(13, 70, 40, 12, 12), _diag(67, 70, 40, 12, 12)])
_sg('N', 72, _stem(6, 0, 70, 15, True) + _stem(51, 0, 70, 15, True)
    + [_diag(13, 70, 58, 0, 12)])
_sg('O', 72, _didone_bowl(36, 35, 26, 35))
_sg('P', 64, _stem(6, 0, 70, 15, True)
    + _bar(6, 44, 66, 4) + _bar(6, 44, 33, 4) + _bowl(21, 50, 25, 17, 13))
_sg('Q', 74, _didone_bowl(36, 35, 26, 35)
    + [_diag(48, 18, 66, 0, 10)])
_sg('R', 66, _stem(6, 0, 70, 15, True)
    + _bar(6, 44, 66, 4) + _bar(6, 44, 33, 4) + _bowl(21, 50, 25, 17, 13)
    + [_diag(24, 33, 60, 0, 13), _rect(54, 0, 66, 4)])
_sg('S', 66, _stroke(_S_PTS, 12))
_sg('T', 64, _bar(4, 60, 66, 4) + _stem(25, 0, 66, 15, True))
_sg('U', 70, _stem(6, 10, 70, 15, True) + _stem(49, 10, 70, 15, True)
    + [_arc(32, 14, 22, 14, 10, 6, 180, 360)])
_sg('V', 70, [_diag(8, 70, 35, 0, 15), _diag(62, 70, 35, 0, 15),
              _rect(2, 66, 18, 70), _rect(52, 66, 68, 70)])
_sg('W', 90, [_diag(6, 70, 22, 0, 13), _diag(22, 0, 40, 70, 13),
              _diag(50, 70, 66, 0, 13), _diag(66, 0, 84, 70, 13)])
_sg('X', 68, [_diag(8, 70, 60, 0, 14), _diag(60, 70, 8, 0, 14)])
_sg('Y', 66, [_diag(8, 70, 33, 30, 14), _diag(58, 70, 33, 30, 14)]
    + _stem(26, 0, 30, 14, True))
_sg('Z', 64, _bar(6, 58, 66, 4) + _bar(6, 58, 0, 4)
    + [_diag(58, 66, 6, 4, 13)])
_sg('0', 68, _didone_bowl(34, 35, 22, 35))
_sg('1', 56, _stem(32, 0, 70, 13, True)
    + [_diag(32, 70, 16, 56, 10), _rect(18, 0, 50, 4)])
_sg('2', 64, _stroke(_2_PTS, 12) + _bar(8, 56, 0, 4))
_sg('3', 66, _bowl(32, 52, 24, 17, 13) + _bowl(32, 18, 26, 17, 14)
    + _bar(10, 54, 66, 4) + _bar(10, 56, 33, 4) + _bar(10, 56, 0, 4))
_sg('4', 66, [_diag(44, 70, 14, 20, 12), _rect(10, 20, 54, 25)]
    + _stem(40, 0, 70, 13, True))
_sg('5', 62, _bar(10, 54, 66, 4) + _stem(10, 36, 66, 13, True)
    + _bar(10, 40, 33, 4) + _bowl(32, 18, 24, 18, 13))
_sg('6', 64, [_arc(32, 18, 24, 18, 12, 9, 0, 360),
              _arc(32, 35, 24, 35, 12, 23, 100, 260)])
_sg('7', 60, _bar(8, 56, 66, 4) + [_diag(56, 66, 26, 0, 13)])
_sg('8', 66, _ring(32, 50, 22, 16, 11) + _ring(32, 19, 24, 17, 12))
_sg('9', 64, [_arc(32, 52, 24, 18, 12, 9, 0, 360)] + _stem(44, 0, 66, 13, True))
_sg('.', 24, [_rect(8, 0, 15, 7)])
_sg(',', 24, [_rect(8, 0, 15, 7), [(8, 0), (15, 0), (10, -12)]])
_sg('-', 36, _bar(4, 32, 33, 5))
_sg('—', 56, _bar(4, 52, 33, 5))
_sg('·', 24, [_rect(9, 28, 15, 34)])
_sg(':', 24, [_rect(9, 44, 15, 50), _rect(9, 8, 15, 14)])
_sg(';', 24, [_rect(9, 44, 15, 50), _rect(9, 8, 15, 14), [(8, 8), (15, 8), (10, -4)]])
_sg("'", 20, [[(8, 70), (14, 70), (10, 54)]])
_sg('(', 28, [_arc(20, 35, 10, 35, 5, 30, 90, 270)])
_sg(')', 28, [_arc(8, 35, 10, 35, 5, 30, -90, 90)])
_sg('%', 72, _ring(20, 52, 13, 13, 6) + _ring(52, 18, 13, 13, 6)
    + [_diag(58, 66, 14, 4, 9)])
_sg('&', 62, _ring(30, 46, 15, 15, 7) + _ring(30, 16, 14, 14, 7)
    + [_diag(48, 66, 14, 2, 9)])
_sg('/', 36, [_diag(26, 70, 10, 0, 10)])
_sg('+', 56, [_rect(25, 8, 31, 62), _rect(6, 32, 50, 38)])
_sg('=', 56, _bar(6, 50, 44, 5) + _bar(6, 50, 26, 5))
_sg('!', 24, _stem(9, 20, 70, 12) + [_rect(9, 0, 15, 6)])
_sg(' ', 30, [])

# ------------------------------------------------------- sans (Helvetica)
# Uniform 13u stems, no serifs. x-height 50, ascenders 70, descenders -20.
N = {}  # char -> (advance, [polygons])


def _ng(ch, adv, polys):
    N[ch] = (adv, polys)


def _nstem(x, y0, y1, w=13):
    return [_rect(x, y0, x + w, y1)]


_ng('A', 70, [_diag(10, 0, 35, 70, 13), _diag(60, 0, 35, 70, 13),
              _rect(24, 26, 46, 31)])
_ng('B', 64, _nstem(6, 0, 70) + _bar(6, 42, 66, 4) + _bar(6, 42, 33, 4)
    + _bar(6, 42, 0, 4) + _bowl(19, 50, 24, 17, 12) + _bowl(19, 17, 26, 17, 12))
_ng('C', 64, [_arc(32, 35, 26, 35, 14, 23, 45, 315)])
_ng('D', 66, _nstem(6, 0, 70) + _bar(6, 42, 66, 4) + _bar(6, 42, 0, 4)
    + _bowl(19, 35, 28, 35, 12, -75, 75))
_ng('E', 58, _nstem(6, 0, 70) + _bar(6, 54, 66, 4) + _bar(6, 46, 33, 4)
    + _bar(6, 54, 0, 4))
_ng('F', 54, _nstem(6, 0, 70) + _bar(6, 52, 66, 4) + _bar(6, 44, 33, 4))
_ng('G', 66, [_arc(32, 35, 26, 35, 14, 23, 45, 315),
              _rect(38, 30, 60, 34), _rect(54, 26, 60, 50)])
_ng('H', 66, _nstem(6, 0, 70) + _nstem(47, 0, 70) + _bar(6, 60, 33, 5))
_ng('I', 36, _nstem(12, 0, 70))
_ng('J', 52, _nstem(36, 6, 70) + [_arc(28, 14, 15, 14, 7, 7, 180, 360)])
_ng('K', 66, _nstem(6, 0, 70) + [_diag(19, 35, 54, 70, 12),
                                 _diag(19, 35, 54, 0, 12)])
_ng('L', 54, _nstem(6, 0, 70) + _bar(6, 50, 0, 4))
_ng('M', 76, _nstem(6, 0, 70) + _nstem(57, 0, 70)
    + [_diag(13, 70, 38, 12, 11), _diag(63, 70, 38, 12, 11)])
_ng('N', 68, _nstem(6, 0, 70) + _nstem(49, 0, 70) + [_diag(13, 70, 56, 0, 11)])
_ng('O', 68, _ring(34, 35, 26, 35, 12))
_ng('P', 60, _nstem(6, 0, 70) + _bar(6, 42, 66, 4) + _bar(6, 42, 33, 4)
    + _bowl(19, 50, 24, 17, 12))
_ng('Q', 70, _ring(34, 35, 26, 35, 12) + [_diag(46, 18, 62, 0, 9)])
_ng('R', 62, _nstem(6, 0, 70) + _bar(6, 42, 66, 4) + _bar(6, 42, 33, 4)
    + _bowl(19, 50, 24, 17, 12) + [_diag(22, 33, 56, 0, 12)])
_ng('S', 62, _stroke(_S_PTS, 11))
_ng('T', 60, _bar(4, 56, 66, 4) + _nstem(24, 0, 66))
_ng('U', 66, _nstem(6, 8, 70) + _nstem(47, 8, 70)
    + [_arc(30, 12, 21, 12, 10, 5, 180, 360)])
_ng('V', 66, [_diag(8, 70, 33, 0, 13), _diag(58, 70, 33, 0, 13)])
_ng('W', 86, [_diag(6, 70, 21, 0, 12), _diag(21, 0, 38, 70, 12),
              _diag(48, 70, 63, 0, 12), _diag(63, 0, 80, 70, 12)])
_ng('X', 64, [_diag(8, 70, 56, 0, 12), _diag(56, 70, 8, 0, 12)])
_ng('Y', 62, [_diag(8, 70, 31, 30, 12), _diag(54, 70, 31, 30, 12)]
    + _nstem(25, 0, 30))
_ng('Z', 60, _bar(6, 54, 66, 4) + _bar(6, 54, 0, 4)
    + [_diag(54, 66, 6, 4, 12)])
_ng('a', 56, _ring(28, 25, 20, 25, 11) + _nstem(42, 0, 50))
_ng('b', 56, _nstem(6, 0, 70) + _ring(30, 25, 20, 25, 11))
_ng('c', 52, [_arc(28, 25, 20, 25, 9, 14, 45, 315)])
_ng('d', 56, _ring(26, 25, 20, 25, 11) + _nstem(40, 0, 70))
_ng('e', 54, _ring(28, 25, 20, 25, 11) + _bar(8, 48, 22, 5))
_ng('f', 40, _nstem(18, 0, 70) + [_arc(18, 62, 12, 8, 5, 4, 0, 180)]
    + _bar(8, 36, 44, 5))
_ng('g', 56, _ring(28, 25, 20, 25, 11) + _nstem(42, -18, 25)
    + [_arc(30, -14, 14, 8, 6, 3, 180, 360)])
_ng('h', 56, _nstem(6, 0, 70) + [_arc(28, 25, 16, 25, 6, 14, 0, 180)]
    + _nstem(40, 0, 50))
_ng('i', 28, _nstem(8, 0, 50) + [_rect(8, 58, 20, 68)])
_ng('j', 28, _nstem(8, -20, 50) + [_rect(8, 58, 20, 68)]
    + [_arc(14, -14, 10, 8, 4, 3, 180, 300)])
_ng('k', 54, _nstem(6, 0, 70) + [_diag(18, 28, 38, 50, 11),
                                 _diag(18, 28, 40, 0, 11)])
_ng('l', 28, _nstem(8, 0, 70))
_ng('m', 80, _nstem(6, 0, 50) + [_arc(20, 25, 12, 25, 4, 14, 0, 180)]
    + _nstem(28, 0, 50) + [_arc(44, 25, 12, 25, 4, 14, 0, 180)]
    + _nstem(52, 0, 50))
_ng('n', 56, _nstem(6, 0, 50) + [_arc(28, 25, 16, 25, 6, 14, 0, 180)]
    + _nstem(40, 0, 50))
_ng('o', 54, _ring(27, 25, 20, 25, 11))
_ng('p', 56, _nstem(6, -20, 50) + _ring(30, 25, 20, 25, 11))
_ng('q', 56, _ring(26, 25, 20, 25, 11) + _nstem(40, -20, 50))
_ng('r', 40, _nstem(6, 0, 50) + [_arc(22, 36, 12, 12, 4, 5, 0, 180)])
_ng('s', 52, _stroke(_S_LOW, 10))
_ng('t', 40, _nstem(14, 0, 62) + _bar(4, 34, 44, 5) + _bar(14, 28, 0, 5))
_ng('u', 56, _nstem(6, 0, 50) + [_arc(26, 8, 14, 8, 5, 3, 180, 360)]
    + _nstem(36, 0, 50))
_ng('v', 54, [_diag(8, 50, 24, 0, 12), _diag(40, 50, 24, 0, 12)])
_ng('w', 76, [_diag(6, 50, 18, 0, 11), _diag(18, 0, 32, 50, 11),
              _diag(44, 50, 56, 0, 11), _diag(56, 0, 70, 50, 11)])
_ng('x', 54, [_diag(8, 50, 46, 0, 11), _diag(46, 50, 8, 0, 11)])
_ng('y', 54, [_diag(8, 50, 24, 0, 12), _diag(40, 50, 24, 0, 12),
              _diag(24, 0, 12, -20, 11)])
_ng('z', 52, _bar(8, 46, 45, 5) + _bar(8, 46, 0, 5)
    + [_diag(46, 45, 8, 5, 11)])
for _d in '0123456789':
    N[_d] = S[_d]
_ng('.', 24, [_rect(8, 0, 15, 7)])
_ng(',', 24, [_rect(8, 0, 15, 7), [(8, 0), (15, 0), (10, -12)]])
_ng('-', 36, _bar(4, 32, 33, 5))
_ng('—', 56, _bar(4, 52, 33, 5))
_ng('·', 24, [_rect(9, 28, 15, 34)])
_ng(':', 24, [_rect(9, 44, 15, 50), _rect(9, 8, 15, 14)])
_ng(';', 24, [_rect(9, 44, 15, 50), _rect(9, 8, 15, 14), [(8, 8), (15, 8), (10, -4)]])
_ng("'", 20, [[(8, 70), (14, 70), (10, 54)]])
_ng('(', 28, [_arc(20, 35, 10, 35, 5, 30, 90, 270)])
_ng(')', 28, [_arc(8, 35, 10, 35, 5, 30, -90, 90)])
_ng('%', 72, _ring(20, 52, 13, 13, 6) + _ring(52, 18, 13, 13, 6)
    + [_diag(58, 66, 14, 4, 9)])
_ng('&', 60, _ring(28, 38, 14, 14, 6) + _ring(28, 14, 13, 13, 6)
    + [_diag(44, 62, 12, 2, 8)])
_ng('/', 36, [_diag(26, 70, 10, 0, 10)])
_ng('+', 56, [_rect(25, 8, 31, 62), _rect(6, 32, 50, 38)])
_ng('=', 56, _bar(6, 50, 44, 5) + _bar(6, 50, 26, 5))
_ng('!', 24, _nstem(9, 20, 70) + [_rect(9, 0, 15, 6)])
_ng('$', 60, _stroke(_S_PTS, 11) + _nstem(24, -6, 76, 11))
_ng(' ', 30, [])


# ------------------------------------------------- glyph rasteriser (4x AA)
_GLYPH_CACHE = {}


def _rasterise(font, ch, cap):
    """Return (alpha rows, width_px, top_px, bottom_px) for one glyph.

    The vector outlines are scaled so cap height = cap px, rasterised on
    a SSx grid with a scanline polygon fill, then box-downsampled: the
    result is a smooth greyscale mask, not a pixel font.
    """
    key = (id(font), ch, cap)
    if key in _GLYPH_CACHE:
        return _GLYPH_CACHE[key]
    adv, polys = font.get(ch, (30, []))
    scale = cap / 70.0
    # glyph-space bounds (y-up), with a small margin for descenders/serifs
    xs = [p[0] for poly in polys for p in poly] or [0, adv]
    ys = [p[1] for poly in polys for p in poly] or [0, 70]
    gx0 = min(min(xs), 0)
    gx1 = max(max(xs), adv)
    gy0 = min(min(ys), 0)
    gy1 = max(max(ys), 70)
    w_sub = max(1, int(math.ceil((gx1 - gx0) * scale * SS)))
    h_sub = max(1, int(math.ceil((gy1 - gy0) * scale * SS)))
    # scale polygons into subpixel space, y DOWN, origin at (gx0, gy1)
    sp = []
    for poly in polys:
        sp.append([((x - gx0) * scale * SS,
                    (gy1 - y) * scale * SS) for (x, y) in poly])
    # scanline fill into a bytearray of subpixel coverage
    cov = bytearray(w_sub * h_sub)
    for sy in range(h_sub):
        yc = sy + 0.5
        intervals = []
        for poly in sp:
            n = len(poly)
            xs2 = []
            for k in range(n):
                x0, yy0 = poly[k]
                x1, yy1 = poly[(k + 1) % n]
                if (yy0 <= yc < yy1) or (yy1 <= yc < yy0):
                    if yy1 != yy0:
                        xs2.append(x0 + (yc - yy0) * (x1 - x0) / (yy1 - yy0))
            xs2.sort()
            for k in range(0, len(xs2) - 1, 2):
                intervals.append((xs2[k], xs2[k + 1]))
        if not intervals:
            continue
        intervals.sort()
        merged = []
        for a, b in intervals:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        row = sy * w_sub
        for a, b in merged:
            xa = max(0, int(math.ceil(a)))
            xb = min(w_sub, int(math.floor(b)))
            for sx in range(xa, xb):
                cov[row + sx] = 1
    # box-downsample SSxSS -> float alpha rows
    w_px = (w_sub + SS - 1) // SS
    h_px = (h_sub + SS - 1) // SS
    rows = []
    for py in range(h_px):
        row = []
        for px in range(w_px):
            s = 0
            for dy in range(SS):
                sy = py * SS + dy
                if sy >= h_sub:
                    break
                base = sy * w_sub + px * SS
                for dx in range(SS):
                    sx = px * SS + dx
                    if sx < w_sub:
                        s += cov[base + dx]
            row.append(s / (SS * SS))
        rows.append(row)
    top = int(round((gy1 - 70) * scale))      # px above cap top
    adv_px = adv * scale
    res = (rows, w_px, h_px, top, adv_px, gx0 * scale)
    _GLYPH_CACHE[key] = res
    return res


def text_width(font, text, cap, tracking=0.0):
    w = 0.0
    for ch in text:
        adv = font.get(ch, (30, []))[0]
        w += adv * cap / 70.0 + tracking
    return w - tracking if text else 0.0


def draw_text(img, x, baseline, text, font, cap, colour, tracking=0.0,
              align='l'):
    """Draw text with its baseline at y=baseline (px). align l/c/r."""
    if align != 'l':
        w = text_width(font, text, cap, tracking)
        if align == 'c':
            x -= w / 2.0
        else:
            x -= w
    cx = float(x)
    for ch in text:
        if ch == ' ':
            cx += font.get(' ', (30, []))[0] * cap / 70.0 + tracking
            continue
        rows, w_px, h_px, top, adv_px, gx0 = _rasterise(font, ch, cap)
        # glyph bitmap top sits (cap + top) px above the baseline
        gy = int(round(baseline - cap - top))
        gx = int(round(cx + gx0))
        for py in range(h_px):
            row = rows[py]
            iy = gy + py
            if iy < 0 or iy >= img.h:
                continue
            for px in range(w_px):
                a = row[px]
                if a > 0.0:
                    img.blend(gx + px, iy, colour, a)
        cx += adv_px + tracking
    return cx


def wrap_text(font, text, cap, max_w, tracking=0.0):
    """Greedy word wrap; returns a list of lines."""
    words = text.split(' ')
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_width(font, trial, cap, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ------------------------------------------------------------- the globe
# Coarse continent outlines (lon, lat), drawn from general geography.
# Europe and Asia are separate polygons with a sea gap between ~28E
# and ~42E, so the Black Sea / Urals gap stays visible.
AFRICA = [(-17, 14), (-16, 20), (-12, 25), (-8, 28), (-4, 31), (3, 31),
          (10, 32), (11, 30), (20, 32), (30, 31), (32, 28), (35, 22),
          (40, 15), (44, 11), (48, 10), (51, 11), (46, 5), (41, -2),
          (40, -10), (36, -18), (33, -26), (28, -33), (20, -35),
          (17, -32), (14, -22), (12, -18), (9, -13), (13, -10),
          (9, -1), (4, 6), (-8, 4), (-13, 8), (-17, 12)]
EUROPE = [(-10, 36), (-9, 38), (-9, 43), (-2, 44), (-2, 48), (0, 46),
          (2, 43), (3, 42), (7, 44), (8, 44), (12, 45), (14, 45),
          (18, 40), (19, 42), (23, 40), (26, 38), (28, 41), (27, 44),
          (28, 45), (24, 45), (22, 48), (24, 50), (28, 50), (28, 54),
          (24, 58), (21, 59), (18, 60), (12, 58), (10, 59), (5, 58),
          (5, 60), (10, 62), (12, 60), (10, 57), (8, 57), (8, 55),
          (5, 53), (3, 51), (0, 51), (-2, 51), (-5, 50), (-5, 48),
          (-2, 46), (-4, 44), (-9, 43)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (1, 52), (0, 51)]
ASIA = [(42, 47), (42, 44), (48, 44), (50, 46), (54, 47), (58, 45),
        (60, 46), (66, 45), (70, 50), (75, 55), (80, 60), (90, 62),
        (100, 65), (110, 68), (120, 70), (130, 72), (140, 72), (150, 70),
        (158, 66), (162, 60), (160, 55), (155, 50), (150, 45), (142, 42),
        (140, 38), (135, 35), (130, 33), (127, 35), (122, 38), (120, 32),
        (115, 28), (110, 22), (108, 18), (105, 10), (103, 8), (100, 8),
        (98, 12), (95, 16), (92, 20), (90, 22), (88, 22), (85, 19),
        (82, 17), (80, 13), (77, 8), (75, 10), (72, 20), (68, 23),
        (66, 25), (62, 25), (58, 26), (56, 27), (52, 26), (50, 29),
        (48, 30), (44, 29), (42, 32), (42, 38)]
PINS = [("1", 52.2, 21.0), ("2", 50.4, 30.5), ("3", 36.9, 30.7),
        ("4", 22.5, 114.1), ("5", 52.0, 4.3), ("6", 51.5, -0.1),
        ("7", 55.7, 12.6), ("8", 19.3, 84.9)]
LAT0 = math.radians(25.0)
LON0 = math.radians(30.0)


def _project(lon, lat, cx, cy, r):
    ph = math.radians(lat)
    dl = math.radians(lon) - LON0
    x3 = math.cos(ph) * math.sin(dl)
    y3 = math.cos(LAT0) * math.sin(ph) - math.sin(LAT0) * math.cos(ph) * math.cos(dl)
    z3 = math.sin(LAT0) * math.sin(ph) + math.cos(LAT0) * math.cos(ph) * math.cos(dl)
    return cx + r * x3, cy - r * y3, z3


def _clip_visible(poly, cx, cy, r):
    """Clip a lat/lon polygon to the visible hemisphere, project to px."""
    pts3 = []
    for lon, lat in poly:
        ph = math.radians(lat)
        dl = math.radians(lon) - LON0
        pts3.append((math.cos(ph) * math.sin(dl),
                     math.cos(LAT0) * math.sin(ph) - math.sin(LAT0) * math.cos(ph) * math.cos(dl),
                     math.sin(LAT0) * math.sin(ph) + math.cos(LAT0) * math.cos(ph) * math.cos(dl)))
    out = []
    n = len(pts3)
    for k in range(n):
        a = pts3[k]
        b = pts3[(k + 1) % n]
        if a[2] > 0:
            out.append(a)
        if (a[2] > 0) != (b[2] > 0):
            t = a[2] / (a[2] - b[2])
            out.append((a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t, 0.0))
    return [(cx + r * p[0], cy - r * p[1]) for p in out]


def draw_globe(img, cx, cy, r):
    # atmosphere glow + ocean disc
    disc_blend(img, cx, cy, r + 7, (38, 90, 110), 0.45)
    disc_blend(img, cx, cy, r + 3, (30, 80, 100), 0.5)
    # ocean: vertical shading bands, light from the upper right (gold side)
    for yy in range(cy - r, cy + r + 1):
        dy = (yy - cy) / r
        if abs(dy) >= 1:
            continue
        dx = int(r * math.sqrt(1 - dy * dy))
        # warm on the right, deep blue on the left
        for xx in range(cx - dx, cx + dx + 1):
            t = (xx - (cx - dx)) / max(1, 2 * dx)  # 0 left .. 1 right
            cr = int(TEAL_D[0] + (52 - TEAL_D[0]) * t)
            cg = int(TEAL_D[1] + (110 - TEAL_D[1]) * t)
            cb = int(TEAL_D[2] + (120 - TEAL_D[2]) * t)
            img.set(xx, yy, (cr, cg, cb))
    # landmasses
    for poly in (AFRICA, EUROPE, UK, ASIA):
        pts = _clip_visible(poly, cx, cy, r)
        if len(pts) >= 3:
            poly_fill(img, pts, LAND)
    # limb shadow on the left
    ellipse_blend(img, cx - r * 0.55, cy, r * 0.55, r * 0.95, (8, 20, 40), 0.28)
    # clouds
    ellipse_blend(img, cx - 30, cy - 55, 34, 8, WHITE, 0.20)
    ellipse_blend(img, cx + 45, cy + 20, 28, 7, WHITE, 0.16)
    ellipse_blend(img, cx - 55, cy + 60, 24, 6, WHITE, 0.14)
    # pins (badges nudged apart where the true dots would collide,
    # with a thin leader line back to the true position)
    _OFF = {"1": (-14, -6), "2": (14, 8), "3": (0, 0), "4": (0, 0),
            "5": (-16, -12), "6": (-14, 14), "7": (12, -14), "8": (0, 0)}
    for num, lat, lon in PINS:
        px, py, z = _project(lon, lat, cx, cy, r)
        if z <= 0:
            continue
        ox, oy = _OFF[num]
        bx, by = int(px) + ox, int(py) + oy
        disc(img, int(px), int(py), 2, WHITE)
        if ox or oy:
            line(img, int(px), int(py), bx, by, WHITE, 1)
        disc(img, bx, by, 8, RED)
        draw_text(img, bx, by + 3, num, N, 9, WHITE, align='c')
    # rim
    for rr in range(r, r + 2):
        for a in range(0, 360):
            th = math.radians(a)
            img.set(int(cx + rr * math.cos(th)), int(cy + rr * math.sin(th)),
                    GOLD_L)


# ------------------------------------------------------------ summit band
def _flag_us(img, x, y):
    img.rect(x, y, x + 34, y + 20, (178, 34, 52))
    for k in range(4):
        img.rect(x, y + 1 + k * 5, x + 34, y + 3 + k * 5, WHITE)
    img.rect(x, y, x + 14, y + 10, (30, 50, 110))
    for fy in (y + 2, y + 5, y + 8):
        for fx in (x + 2, x + 6, x + 10):
            img.set(fx, fy, WHITE)


def _flag_cn(img, x, y):
    img.rect(x, y, x + 34, y + 20, (222, 41, 16))
    disc(img, x + 8, y + 7, 3, GOLD)
    for dx, dy in ((16, 4), (19, 8), (18, 12), (14, 13)):
        disc(img, x + dx, y + dy, 1, GOLD)


def _flag_ru(img, x, y):
    img.rect(x, y, x + 34, y + 7, WHITE)
    img.rect(x, y + 7, x + 34, y + 14, (0, 57, 166))
    img.rect(x, y + 14, x + 34, y + 20, (213, 0, 50))


def draw_figure(img, cx, base, skin, hair, suit, flag_fn, name):
    # flag on a pole to the figure's left, at shoulder height
    img.vline(cx - 60, base - 72, base - 34, GOLD_L, 2)
    flag_fn(img, cx - 60, base - 72)
    # shoulders / suit
    poly_fill(img, [(cx - 44, base), (cx + 44, base), (cx + 30, base - 30),
                    (cx + 14, base - 38), (cx - 14, base - 38),
                    (cx - 30, base - 30)], suit)
    # shirt + tie
    poly_fill(img, [(cx - 10, base - 38), (cx + 10, base - 38),
                    (cx, base - 22)], WHITE)
    poly_fill(img, [(cx - 4, base - 36), (cx + 4, base - 36),
                    (cx + 5, base - 24), (cx, base - 20),
                    (cx - 5, base - 24)], RED)
    # neck + head (no face: blank, stylised)
    img.rect(cx - 7, base - 46, cx + 8, base - 36, skin)
    ellipse_fill(img, cx, base - 58, 13, 15, skin)
    # hair cap
    if hair == 'blond':
        poly_fill(img, [(cx - 13, base - 62), (cx + 13, base - 62),
                        (cx + 12, base - 70), (cx - 4, base - 74),
                        (cx - 13, base - 68)], (232, 196, 120))
        img.rect(cx - 13, base - 66, cx - 8, base - 58, (232, 196, 120))
    elif hair == 'black':
        ellipse_fill(img, cx, base - 68, 13, 7, (20, 20, 20))
        img.rect(cx - 13, base - 68, cx + 14, base - 64, (20, 20, 20))
    else:  # grey
        ellipse_fill(img, cx, base - 68, 13, 7, (150, 150, 150))
        img.rect(cx - 13, base - 68, cx + 14, base - 64, (150, 150, 150))
    draw_text(img, cx, base + 14, name, N, 10, GOLD_L, tracking=1.0, align='c')


# --------------------------------------------------------------- vignettes
def _panel(img, x, y, w, h, label):
    img.rect(x, y, x + w, y + h, NAVY2)
    img.rect(x, y, x + w, y + 1, GOLD)
    img.rect(x, y + h - 1, x + w, y + h, GOLD)
    img.rect(x, y, x + 1, y + h, GOLD)
    img.rect(x + w - 1, y, x + w, y + h, GOLD)
    img.rect(x + 1, y + 1, x + w - 1, y + 20, NAVY)
    draw_text(img, x + 8, y + 15, label, N, 9, GOLD_L, tracking=1.0)


def vignette_poland(img, x, y, w, h):
    _panel(img, x, y, w, h, 'POLAND  —  SECURITY')
    img.rect(x + 1, y + 62, x + w - 1, y + h - 1, (58, 96, 58))
    img.rect(x + 1, y + 62, x + w - 1, y + 66, (46, 78, 46))
    for tx in (x + 30, x + 62, x + 96):
        poly_fill(img, [(tx - 12, y + 92), (tx + 12, y + 92), (tx, y + 58)],
                  (28, 58, 30))
        img.rect(tx - 2, y + 92, tx + 3, y + 100, (40, 30, 20))
    # distant jet
    poly_fill(img, [(x + 200, y + 38), (x + 252, y + 34), (x + 252, y + 40),
                    (x + 200, y + 44)], (200, 205, 210))
    poly_fill(img, [(x + 224, y + 34), (x + 232, y + 26), (x + 236, y + 34)],
              (200, 205, 210))
    # impact burst
    bx, by = x + 232, y + 62
    for ang in range(0, 360, 30):
        th = math.radians(ang)
        line(img, bx, by, int(bx + 11 * math.cos(th)),
             int(by + 11 * math.sin(th)), (255, 220, 120), 2)
    disc(img, bx, by, 4, (255, 240, 180))
    draw_text(img, x + 8, y + h - 8, 'KH-101 DOWN AT NOWY LIPOWIEC · 20 NOV',
              N, 8, (220, 225, 230))


def vignette_markets(img, x, y, w, h):
    _panel(img, x, y, w, h, 'MARKETS  —  TECH SELLS OFF')
    # faint circuit traces
    for cy in (y + 34, y + 48, y + 92):
        img.hline(x + 10, x + w - 10, cy, (90, 90, 80), 1)
    for cx in (x + 40, x + 120, x + 210, x + 270):
        disc(img, cx, y + 34, 2, GOLD)
        disc(img, cx, y + 92, 2, GOLD)
    # falling line
    pts = [(x + 14, y + 38), (x + 70, y + 42), (x + 120, y + 48),
           (x + 170, y + 58), (x + 220, y + 68), (x + 268, y + 78)]
    for a, b in zip(pts, pts[1:]):
        line(img, a[0], a[1], b[0], b[1], RED, 3)
    for px, py in pts:
        disc(img, px, py, 3, (255, 120, 100))
    # volume bars (kept clear of the caption line)
    for k, bh in enumerate((14, 20, 12, 26, 34, 44, 52)):
        bx = x + 180 + k * 15
        img.rect(bx, y + h - 20 - bh, bx + 10, y + h - 20, RED)
    draw_text(img, x + 8, y + h - 8, 'S&P -3.7% · NASDAQ -5.3% · FRI 20 NOV',
              N, 8, (255, 150, 130))


def vignette_gaza(img, x, y, w, h):
    _panel(img, x, y, w, h, 'GAZA  —  CIVILIANS RETURN')
    img.rect(x + 1, y + 20, x + w - 1, y + h - 1, SAND)
    img.rect(x + 1, y + 20, x + w - 1, y + 30, (210, 182, 132))
    # damaged houses
    for hx, hw, hh in ((x + 16, 56, 44), (x + 84, 66, 52), (x + 164, 58, 40),
                        (x + 232, 50, 46)):
        img.rect(hx, y + h - 12 - hh, hx + hw, y + h - 12, (150, 118, 82))
        poly_fill(img, [(hx - 3, y + h - 12 - hh), (hx + hw + 3, y + h - 12 - hh),
                        (hx + hw // 2, y + h - 12 - hh - 14)], (120, 92, 60))
        img.rect(hx + hw // 2 - 5, y + h - 30, hx + hw // 2 + 5, y + h - 12,
                 (70, 50, 32))
    # rubble
    poly_fill(img, [(x + 140, y + h - 12), (x + 160, y + h - 12),
                    (x + 150, y + h - 26)], (130, 110, 88))
    # three small figures, dignified, walking home
    for fx in (x + 96, x + 128, x + 196):
        img.rect(fx - 4, y + h - 34, fx + 5, y + h - 12, (30, 44, 80))
        disc(img, fx, y + h - 40, 5, SKIN)
    draw_text(img, x + 8, y + h - 8, 'FAMILIES RETURN TO DAMAGED HOMES',
              N, 8, (90, 66, 40))


def vignette_hague(img, x, y, w, h):
    _panel(img, x, y, w, h, 'THE HAGUE  —  JUSTICE')
    # palace
    bx, by, bw = x + 30, y + h - 14, 150
    img.rect(bx, by - 8, bx + bw, by, (200, 188, 160))
    img.rect(bx + 8, by - 14, bx + bw - 8, by - 8, (210, 198, 172))
    poly_fill(img, [(bx, by - 14), (bx + bw, by - 14),
                    (bx + bw // 2, by - 40)], (225, 214, 190))
    for k in range(4):
        cx = bx + 18 + k * 40
        img.rect(cx - 5, by - 52, cx + 6, by - 14, (235, 228, 210))
        img.rect(cx - 8, by - 56, cx + 9, by - 52, (235, 228, 210))
    img.rect(bx + 8, by - 56, bx + bw - 8, by - 52, (235, 228, 210))
    # scales of justice
    sx, sy = x + 238, y + 52
    img.vline(sx, sy - 26, sy + 22, GOLD, 2)
    img.hline(sx - 22, sx + 22, sy - 24, GOLD, 2)
    line(img, sx - 22, sy - 24, sx - 30, sy - 8, GOLD, 1)
    line(img, sx - 22, sy - 24, sx - 14, sy - 8, GOLD, 1)
    poly_fill(img, [(sx - 32, sy - 8), (sx - 12, sy - 8), (sx - 22, sy + 2)],
              GOLD)
    line(img, sx + 22, sy - 24, sx + 30, sy - 8, GOLD, 1)
    line(img, sx + 22, sy - 24, sx + 14, sy - 8, GOLD, 1)
    poly_fill(img, [(sx + 12, sy - 8), (sx + 32, sy - 8), (sx + 22, sy + 2)],
              GOLD)
    disc(img, sx, sy - 28, 3, GOLD)
    draw_text(img, x + 8, y + h - 8, 'ICJ RULING WAS 19 NOV — SEE CONTEXT BOX',
              N, 8, (210, 200, 170))

# ---------------------------------------------------------------- content
# Every dated item below happened or was first reported 20-21 Nov 2026.
# Shenzhen (19 Nov) and the ICJ ruling (19 Nov) are NOT in this list:
# they live in the CONTEXT box only. Full sourcing in STORIES.md.
STRIP = [
    "POLAND — MISSILES LAND · 20 NOV",
    "RUTTE — TO WARSAW SAT. · 21 NOV",
    "UK-EU — FOOD, YOUTH, CARBON · 20 NOV",
    "DENMARK — EXPELS ATTACHE · 20 NOV",
    "ITALY — GENERAL STRIKE · 20 NOV",
    "DRILL — 11-NATION DRILL ENDS · 20 NOV",
    "KYIV — 110+ MISSILES, 3 BRIDGES · 20 NOV",
    "HORMUZ — TANKER STRUCK · 20 NOV",
    "PEACE — US 28-PT PLAN TO KYIV · 21 NOV",
    "MOSCOW — NO NATO-LIKE STATUS · 20 NOV",
    "EU AID — EUR 7.9BN TO KYIV · 20 NOV",
    "VENEZUELA — REJECTS ICJ · 20 NOV",
    "ROHINGYA — 10,000 TO TURKIYE · 20 NOV",
    "COP31 — OVERTIME, NO FUELS · 20-21 NOV",
    "CLIMATE — OCT. 1.8C ABOVE NORM · 20 NOV",
    "WALL ST — S&P, DOW CORRECT · 20 NOV",
    "NASDAQ — -5.3%, WORST WEEK · 20 NOV",
    "SEC — PROBES NVIDIA BOOKS · 20 NOV",
    "ANTHROPIC — -8.5% AFTER IPO · 20 NOV",
    "VIX — VIX HITS 35.89 · 20 NOV",
    "MONGOLIA — PRESIDENT QUITS · 20 NOV",
    "AKVAN — LANDFALL; 300K OUT · 20 NOV",
    "LEBANON — ISRAEL HITS SITE · 20 NOV",
    "GUPTA — JAILED 235 MONTHS · 20 NOV",
    "IRAQ — TROOPS IN MILITIA BASE · 20 NOV",
    "HUANG — TRUMP WANTS HIM BACK · 20 NOV",
    "EU ARMS — EUR 1BN MORE · 20 NOV",
    "GENOA — DRONES SHUT AIRPORT · 20 NOV",
    "BAYER — $7.25BN DEAL OKD · 20 NOV",
    "RIKERS — NYC TO CLOSE BY 2032 · 20 NOV",
    "KIM — TOURS FACTORIES · 20 NOV",
    "PANAMA — THREATENS COP31 VETO · 20 NOV",
    "GRIPEN — SCRAMBLE OVER POLAND · 20 NOV",
    "UN VOTE — US ABSTAINS · 20 NOV",
    "YEMEN — HITS 6 HOUTHI SITES · 21 NOV",
]

FEATURES = [
    ("POLAND · SECURITY", "MISSILES LAND IN POLAND",
     "Two Kh-101 missiles and a jet drone fell in south-east Poland on "
     "Friday. Warsaw calls it provocation.",
     "3 OBJECTS · 0 HURT · JETS UP"),
    ("COP31 · CLIMATE", "CLIMATE TALKS IN OVERTIME",
     "COP31 in Antalya passed its Friday deadline with no deal. The "
     "draft drops fossil fuels and the $120BN target.",
     "DRAFT 144 TO 80 · 1.5C NAMED"),
    ("WALL STREET · MARKETS", "WALL STREET IN CORRECTION",
     "The S&P 500 fell 3.7% on Friday, its seventh straight down day, "
     "and the Dow is now 10% below its peak.",
     "S&P -3.7% · VIX 35.89"),
    ("NATO · WARSAW", "RUTTE FLIES TO WARSAW",
     "NATO chief Mark Rutte visits Warsaw on Saturday as Poland asks "
     "for more Eastern Sentry troops.",
     "VISIT SAT 21 NOV · GRIPENS UP"),
]

DATE_CHECK = [
    "DATE CHECK — SHENZHEN SUMMIT + ICJ RULING WERE 19 NOV, NOT 21 NOV.",
    "ALSO 19 NOV, NOT HERE: KERCH BRIDGE, RIYADH TOWER, PETE ROSE PARDON,",
    "ANDROMEDA, KUSHNER + TOKYO BRIEFINGS. EVERY STORY BELOW IS 20-21 NOV.",
]

CONTEXT = [
    "CONTEXT — 19 NOV (NOT TODAY'S NEWS): SHENZHEN — TRUMP, XI, PUTIN MEET;",
    "4-POINT DECLARATION  ·  ICJ — MYANMAR GUILTY OF ROHINGYA GENOCIDE, 9-6.",
]


# ------------------------------------------------------------------ layout
def build():
    img = Img(W, H, PAPER)

    # --- masthead
    draw_text(img, 512, 76, "WORLD NEWS", S, 58, INK, tracking=2.0, align='c')
    draw_text(img, 512, 104, "SATURDAY, 21 NOVEMBER 2026", N, 15, INK,
              tracking=6.0, align='c')
    img.hline(20, 1004, 112, INK, 3)
    img.hline(20, 1004, 117, INK, 1)

    # --- dark field: summit + globe + vignettes
    img.rect(20, 122, 1004, 448, NAVY)
    img.rect(20, 122, 1004, 123, GOLD)
    img.rect(20, 447, 1004, 448, GOLD)
    draw_figure(img, 280, 196, SKIN3, 'blond', (24, 32, 58), _flag_us, "TRUMP")
    draw_figure(img, 512, 196, SKIN2, 'black', (32, 32, 32), _flag_cn,
                "XI JINPING")
    draw_figure(img, 744, 196, SKIN, 'grey', (28, 30, 46), _flag_ru, "PUTIN")
    vignette_poland(img, 28, 222, 300, 104)
    vignette_markets(img, 696, 222, 300, 104)
    vignette_gaza(img, 28, 334, 300, 104)
    vignette_hague(img, 696, 334, 300, 104)
    draw_globe(img, 512, 330, 112)

    # --- hero band
    img.rect(20, 454, 1004, 518, NAVY)
    img.rect(20, 454, 1004, 455, GOLD)
    img.rect(20, 517, 1004, 518, GOLD)
    draw_text(img, 512, 492, "MISSILES LAND IN POLAND", S, 42, CREAM,
              tracking=1.0, align='c')
    draw_text(img, 512, 512,
              "RUTTE TO WARSAW — COP31 IN OVERTIME — WALL STREET IN CORRECTION",
              N, 11, GOLD_L, tracking=1.0, align='c')

    # --- DATE CHECK (crimson, honest by construction)
    img.rect(20, 524, 1004, 578, CRIMSON)
    for k, ln in enumerate(DATE_CHECK):
        draw_text(img, 512, 542 + k * 13, ln, N, 10, CREAM, tracking=0.5,
                  align='c')

    # --- CONTEXT box: the two 19 Nov items, outside the main strip
    img.rect(20, 584, 1004, 616, (232, 222, 196))
    img.rect(20, 584, 1004, 585, INK)
    img.rect(20, 615, 1004, 616, INK)
    img.rect(20, 584, 21, 616, INK)
    img.rect(1003, 584, 1004, 616, INK)
    for k, ln in enumerate(CONTEXT):
        draw_text(img, 512, 598 + k * 13, ln, N, 10, INK, tracking=0.5,
                  align='c')

    # --- ALSO TODAY header
    draw_text(img, 28, 648, "ALSO TODAY", S, 26, INK, tracking=1.0)
    draw_text(img, 996, 644,
              "35 STORIES — 6 REGIONS — SOURCES: REUTERS, AP, NYT, WSJ",
              N, 9, INK, tracking=0.5, align='r')
    img.hline(28, 996, 654, INK, 2)

    # --- four feature stories with body text
    for col, (kick, head, body, stat) in enumerate(FEATURES):
        x = 28 + col * 244
        if col:
            img.vline(x - 8, 664, 788, (190, 180, 158), 1)
        draw_text(img, x, 670, kick, N, 9, (140, 40, 32), tracking=1.0)
        hl = wrap_text(S, head, 17, 240)
        by = 692
        for ln in hl[:2]:
            draw_text(img, x, by, ln, S, 17, INK, tracking=0.5)
            by += 21
        bl = wrap_text(N, body, 9.5, 240)
        by += 2
        for ln in bl[:3]:
            draw_text(img, x, by, ln, N, 9.5, (40, 44, 54), tracking=0.2)
            by += 12.5
        img.hline(x, x + 232, by + 2, (190, 180, 158), 1)
        draw_text(img, x, by + 14, stat, N, 8.5, INK, tracking=0.5)

    # --- 35-story strip, 3 columns x 12 rows (one draw call per row)
    img.hline(28, 996, 790, INK, 1)
    for idx, txt in enumerate(STRIP):
        col = idx // 12
        row = idx % 12
        x = 28 + col * 328
        y = 806 + row * 13
        num = "%02d" % (idx + 1)
        draw_text(img, x, y, num, N, 8.5, GOLD, tracking=0.5)
        draw_text(img, x + 22, y, txt, N, 8.5, INK, tracking=0.2)

    # --- bottom headline
    img.hline(28, 996, 952, INK, 2)
    draw_text(img, 512, 992, "THE WORLD AT A CROSSROADS", S, 34, INK,
              tracking=1.0, align='c')
    draw_text(img, 512, 1014,
              "ALL STORIES HAPPENED OR WERE FIRST REPORTED 20-21 NOV 2026",
              N, 8, (90, 90, 90), tracking=1.0, align='c')
    return img


# --------------------------------------------------------------------- png
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(img, path):
    raw = bytearray()
    for y in range(img.h):
        raw.append(0)
        raw += img.px[y * img.w * 3:(y + 1) * img.w * 3]
    comp = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", img.w, img.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", comp)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    img = build()
    n = write_png(img, os.path.join(out_dir, "entry.png"))
    print("wrote %s/entry.png (%d bytes, %dx%d)"
          % (out_dir, n, img.w, img.h))


if __name__ == "__main__":
    main()
