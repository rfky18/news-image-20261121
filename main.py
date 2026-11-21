#!/usr/bin/env python3
"""Render the Saturday 21 November 2026 front page as one 1024x1024 PNG.

Stdlib only. All lettering is blitted from the bitmap atlas built by
tools/gen_atlas.py (real OFL fonts: Bodoni Moda, Libre Baskerville,
Gelasio, Liberation Sans, Roboto). All pictures are flat vector drawings
made here in code. No network, no randomness: two runs are byte-identical.

Usage:  python3 main.py [output.png]     (default /output/entry.png)
"""

import binascii
import json
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)
CARD = (255, 253, 247)
INK = (20, 20, 20)
NAVY = (26, 42, 74)
RED = (179, 35, 42)
GRAY = (107, 107, 107)
HAIR = (216, 207, 184)
SEA = (223, 232, 234)
LAND = (216, 203, 166)
LANDB = (184, 171, 132)
TEAL = (31, 122, 109)
OCHRE = (185, 122, 18)
BLUE = (47, 109, 179)
GREEN = (61, 122, 58)
PURPLE = (107, 79, 161)
DARK = (74, 74, 74)

# ---------------------------------------------------------------- atlas
with open(os.path.join(HERE, "atlas.json")) as fh:
    _ATLAS_INDEX = json.load(fh)
with open(os.path.join(HERE, "atlas.bin"), "rb") as fh:
    _ATLAS = fh.read()
_ATLAS_W = _ATLAS_INDEX["w"]
_GLYPHS = _ATLAS_INDEX["glyphs"]
_FONTS = _ATLAS_INDEX["fonts"]


def glyph(family, size, ch):
    return _GLYPHS["%s:%d:%d" % (family, size, ord(ch))]


def font_ascent(family, size):
    return _FONTS["%s:%d" % (family, size)]["ascent"]


def text_w(family, size, text, tracking=0):
    total = 0
    for ch in text:
        total += glyph(family, size, ch)[4]
    if len(text) > 1:
        total += tracking * (len(text) - 1)
    return total


def wrap(text, family, size, maxw, tracking=0):
    """Greedy word wrap. Returns a list of lines that fit maxw."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(family, size, trial, tracking) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, color):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        r, g, b = color
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def blend(self, x, y, color, alpha):
        """Blend color over the pixel with coverage alpha (0..255)."""
        if alpha == 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 3
        if alpha == 255:
            self.px[i], self.px[i + 1], self.px[i + 2] = color
            return
        inv = 255 - alpha
        self.px[i] = (alpha * color[0] + inv * self.px[i]) // 255
        self.px[i + 1] = (alpha * color[1] + inv * self.px[i + 1]) // 255
        self.px[i + 2] = (alpha * color[2] + inv * self.px[i + 2]) // 255

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = color

    def rect(self, x, y, w, h, color, width=1):
        self.fill_rect(x, y, w, width, color)
        self.fill_rect(x, y + h - width, w, width, color)
        self.fill_rect(x, y, width, h, color)
        self.fill_rect(x + w - width, y, width, h, color)

    def hline(self, x, y, w, color, width=1):
        self.fill_rect(x, y, w, width, color)

    def vline(self, x, y, h, color, width=1):
        self.fill_rect(x, y, width, h, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        r = max(1, width // 2)
        while True:
            if width <= 1:
                self.set(x, y, color)
            else:
                self.circle(x, y, r, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def dashed_line(self, x0, y0, x1, y1, color, dash=6, gap=4):
        import math
        length = math.hypot(x1 - x0, y1 - y0)
        if length == 0:
            return
        ux, uy = (x1 - x0) / length, (y1 - y0) / length
        d = 0.0
        while d < length:
            e = min(d + dash, length)
            self.line(int(round(x0 + ux * d)), int(round(y0 + uy * d)),
                      int(round(x0 + ux * e)), int(round(y0 + uy * e)),
                      color, 1)
            d = e + gap

    def circle(self, cx, cy, r, color):
        if r <= 0:
            return
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            half = int((r * r - dy * dy) ** 0.5)
            self.fill_rect(cx - half, yy, half * 2 + 1, 1, color)

    def ellipse(self, cx, cy, rx, ry, color):
        if rx <= 0 or ry <= 0:
            return
        for yy in range(cy - ry, cy + ry + 1):
            dy = (yy - cy) / float(ry)
            half = int(rx * (1.0 - dy * dy) ** 0.5)
            self.fill_rect(cx - half, yy, half * 2 + 1, 1, color)

    def ring(self, cx, cy, r, color, width=2):
        import math
        for rr in range(r - width + 1, r + 1):
            steps = max(8, int(2 * math.pi * rr))
            for i in range(steps):
                a = 2 * math.pi * i / steps
                self.set(cx + int(round(rr * math.cos(a))),
                         cy + int(round(rr * math.sin(a))), color)

    def polygon(self, pts, color):
        """Scanline fill, even-odd rule."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            nodes = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    nodes.append(x0 + (yy - y0) * (x1 - x0) / float(y1 - y0))
            nodes.sort()
            for k in range(0, len(nodes) - 1, 2):
                self.fill_rect(int(round(nodes[k])), yy,
                               int(round(nodes[k + 1])) - int(round(nodes[k])),
                               1, color)

    def polyline(self, pts, color, width=1):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      color, width)

    def round_rect(self, x, y, w, h, r, color):
        self.fill_rect(x + r, y, w - 2 * r, h, color)
        self.fill_rect(x, y + r, w, h - 2 * r, color)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.circle(cx, cy, r, color)

    def star(self, cx, cy, r, color):
        self.line(cx - r, cy, cx + r, cy, color, 1)
        self.line(cx, cy - r, cx, cy + r, color, 1)
        self.line(cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2, color, 1)
        self.line(cx - r // 2, cy + r // 2, cx + r // 2, cy - r // 2, color, 1)

    # ------------------------------------------------------------ text
    def draw_text(self, family, size, x, y_top, text, color,
                  align="left", tracking=0):
        """Draw text with its em-box top at y_top. Returns width drawn."""
        width = text_w(family, size, text, tracking)
        if align == "center":
            pen = x - width // 2
        elif align == "right":
            pen = x - width
        else:
            pen = x
        base = y_top + font_ascent(family, size)
        for ch in text:
            gx, gy, gw, gh, adv, ox, oy = glyph(family, size, ch)
            if gw and gh:
                for row in range(gh):
                    src = (gy + row) * _ATLAS_W + gx
                    for col in range(gw):
                        a = _ATLAS[src + col]
                        if a:
                            self.blend(pen + ox + col, base + oy + row,
                                       color, a)
            pen += adv + tracking
        return width

    def draw_wrapped(self, family, size, x, y_top, text, color, maxw,
                     line_h, tracking=0):
        lines = wrap(text, family, size, maxw, tracking)
        y = y_top
        for ln in lines:
            self.draw_text(family, size, x, y, ln, color, tracking=tracking)
            y += line_h
        return y  # y just past the last line


# ---------------------------------------------------------------- PNG out
def write_png(path, canvas):
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", canvas.w, canvas.h,
                                      8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)

# ---------------------------------------------------------------- content
# All facts below are the consensus figures from the prep note; every
# headline and deck is written here in fresh words.

STAT = [
    ("DAY 13", "of COP31, meant to", "close on day 12"),
    ("3", "missiles shot down", "over Riyadh"),
    ("6.7", "magnitude of the", "Peru quake"),
    ("146", "people safe after", "the Davao landing"),
    ("$58,983", "bitcoin early Saturday,", "down 3.9% in a day"),
    ("124*", "K L Rahul's score", "at tea in Wellington"),
]

REGIONS = [
    ("EUROPE 4", 4, BLUE),
    ("ASIA 10", 10, RED),
    ("MIDDLE EAST 3", 3, OCHRE),
    ("AFRICA 1", 1, GREEN),
    ("AMERICAS 11", 11, PURPLE),
    ("OCEANIA 3", 3, TEAL),
    ("GLOBAL 3", 3, DARK),
]

HERO = [
    {"num": 1, "place": "RIYADH \u00b7 SAUDI ARABIA", "beat": "CONFLICT",
     "headline": "Saudi defences shoot down three missiles aimed at the capital",
     "deck": "Third night of alerts in a row; two blasts heard about 02:00, "
             "no damage or casualties.",
     "src": "Reuters \u00b7 AFP \u00b7 coalition statement",
     "chip": "3 SHOT DOWN"},
    {"num": 2, "place": "ANTALYA \u00b7 T\u00dcRKIYE", "beat": "CLIMATE",
     "headline": "Climate summit runs into overtime with no deal",
     "deck": "Talks pass Friday's deadline with no agreement; a third draft "
             "is due Saturday morning.",
     "src": "AP \u00b7 AFP \u00b7 Al Jazeera",
     "chip": "DAY 13 \u00b7 NO DEAL"},
    {"num": 3, "place": "CARHUAMAYO \u00b7 PERU", "beat": "EARTHQUAKE",
     "headline": "Magnitude 6.7 earthquake rattles central Peru",
     "deck": "A deep tremor struck near Carhuamayo just after midnight UTC. "
             "Peru's institute reported no deaths, no tsunami risk.",
     "src": "USGS \u00b7 IGP",
     "chip": "6.7 \u00b7 00:09 UTC"},
]

SECONDARY = [
    (4, "KYIV \u00b7 WAR", "Russian strikes kill 12 in Ukraine",
     "Two dead, 42 hurt in the Kryvyi Rih double strike; toll confirmed Saturday.",
     "Kyiv Post \u00b7 AP", "42 HURT"),
    (5, "WARSAW \u00b7 NATO", "Rutte flies to Warsaw for NATO talks",
     "NATO chief visits on Saturday; Warsaw asks for more Eastern Sentry forces.",
     "AP", None),
    (6, "MERCURY \u00b7 SPACE", "BepiColombo reaches Mercury",
     "Thrusters fire at 19:24 CET tonight.",
     "ESA", "19:24 CET"),
    (7, "HORMUZ \u00b7 WAR", "Iran says it downed a US drone",
     "Tehran claims the shootdown; Washington has not confirmed it.",
     "IRIB", None),
    (8, "WASHINGTON \u00b7 TECHNOLOGY", "Trump vows tax on data centres abroad",
     "\u201cTremendous\u201d penalty promised; no details yet.",
     "ABC", None),
    (9, "BEIJING \u00b7 DIPLOMACY", "China tells Japan to \u201ccorrect\u201d Taiwan words",
     "Tokyo says its stance is unchanged.",
     "Ministry \u00b7 AFP", None),
    (10, "DAVAO \u00b7 AVIATION", "Jet lands safely after engine fire alert",
     "Air Niugini 767 diverts after midnight; all 146 on board safe.",
     "Airline \u00b7 AP", "146 SAFE"),
    (11, "CANBERRA \u00b7 DIPLOMACY", "Australia and China agree AI talks",
     "Albanese ends an 11-day trip.",
     "ABC", None),
    (12, "WORLD \u00b7 MARKETS", "Bitcoin slips below $59,000",
     "Down 3.9% in 24 hours; ether $1,625.",
     "CoinGecko", "$58,983"),
    (13, "WELLINGTON \u00b7 CRICKET", "Rahul century puts India on top",
     "India 344 for 2 at tea, replying to 368.",
     "AFP", "124*"),
]

MORE = [
    (14, "Copenhagen: Russian attach\u00e9 expelled (Al Jazeera)"),
    (15, "Antalya: EU warns COP31 risks a \u201cfossil summit\u201d (AFP)"),
    (16, "Antalya: Panama threatens to block climate text (Al Jazeera)"),
    (17, "Antalya: Indonesia PLN signs clean-power deals (Antara)"),
    (18, "Yemen: Houthis threaten Jeddah and Red Sea ports (Al Jazeera)"),
    (19, "Washington: Vance \u2014 Iran strikes were Trump's call (Reuters)"),
    (20, "Washington: Lawmaker threatens SpaceX's funding (CNN)"),
    (21, "Texas: Execution of man of 70 takes 63 minutes (ABC)"),
    (22, "Los Angeles: Jury convicts Palisades fire starter (ABC)"),
    (23, "Missouri: Judge approves $7.25bn Roundup settlement (AFP)"),
    (24, "Vancouver: Canada rests defence in youth climate trial (AFP)"),
    (25, "Pyongyang: Kim tours factories after no Trump meeting (AFP)"),
    (26, "Sejong: Freight train derails, no one hurt (Korea Herald)"),
    (27, "Taipei: Budget and cash payout are passed (Taipei Times)"),
    (28, "Bangkok: Six-point plan on arsenic in two rivers (The Nation)"),
    (29, "New Delhi: Pakistani minister joins SCO forum in India (Dawn)"),
    (30, "Eastern India: Rain alerts as Akvan remnant moves inland (ETV)"),
    (31, "Myanmar: Rights groups urge sanctions after court ruling (AP)"),
    (32, "Port Louis: Rating agency talks to 15 states (Al Jazeera)"),
    (33, "Melbourne: Cummins keeps the Australian captaincy (ABC)"),
    (34, "Las Vegas: Verstappen to stewards after contact (Autosport)"),
    (35, "Las Vegas: Russell fastest in practice, 1:34.041 (F1)"),
]

DATE_CHECK = (
    "Left out as Friday 20 November's news: Wall Street's fall into a "
    "correction \u00b7 the Russian barrage that hit Kyiv's bridges \u00b7 the "
    "missile that landed in Poland \u00b7 the UK\u2013EU deal \u00b7 Cyclone "
    "Akvan's landfall \u00b7 Gaza strikes that killed six. Older still: the "
    "Shenzhen summit and the ICJ Myanmar ruling (Thursday 19 November) "
    "\u00b7 Voyager 1's light-day (18 November). Not confirmed when drawn, "
    "so not shown: a final COP31 text."
)

FOOTER = ("Every story here happened, or was first reported, on Saturday "
          "21 November 2026. Sources named beside each story \u00b7 "
          "Original drawings \u00b7 Drawn in code")

SUBHEAD = ("COP31 talks run into overtime \u00b7 missiles intercepted over "
           "Riyadh \u00b7 a 6.7 quake shakes Peru")


# ---------------------------------------------------------------- helpers
def chip(c, x, y, text, bg, fg=(255, 255, 255)):
    """Small filled label chip; returns its width."""
    w = text_w("libsans_b", 8, text) + 10
    c.fill_rect(x, y, w, 13, bg)
    c.draw_text("libsans_b", 8, x + 5, y + 2, text, fg)
    return w


def kicker_line(c, x, y, num, place, beat, size=10):
    """'1  RIYADH · SAUDI ARABIA — CONFLICT' with number + beat in red."""
    n = str(num)
    c.draw_text("libsans_b", size, x, y, n, RED)
    px = x + text_w("libsans_b", size, n) + 5
    mid = place + " \u2014 "
    c.draw_text("libsans_b", size, px, y, mid, INK)
    px += text_w("libsans_b", size, mid)
    c.draw_text("libsans_b", size, px, y, beat, RED)


# ---------------------------------------------------------------- hero art
def art_riyadh(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (16, 24, 52))
    # crescent moon
    c.circle(x + w - 34, y + 14, 9, (240, 214, 130))
    c.circle(x + w - 30, y + 12, 8, (16, 24, 52))
    # skyline
    base = y + h
    for bx, bw, bh in ((0, 46, 34), (52, 34, 48), (92, 52, 30), (150, 30, 44),
                       (186, 44, 26), (236, 36, 40), (278, 48, 32)):
        c.fill_rect(x + bx, base - bh, bw, bh, (10, 16, 36))
        for wy in range(base - bh + 6, base - 5, 9):
            for wx in range(x + bx + 5, x + bx + bw - 5, 9):
                if (wx * 7 + wy * 13) % 5:
                    c.fill_rect(wx, wy, 3, 4, (240, 200, 90))
    # three dashed missile arcs + star bursts
    c.dashed_line(x + 30, base - 6, x + 110, y + 12, (240, 214, 130))
    c.dashed_line(x + 150, base - 6, x + 210, y + 8, (240, 214, 130))
    c.dashed_line(x + 250, base - 6, x + 300, y + 16, (240, 214, 130))
    for sx, sy in ((110, 12), (210, 8), (300, 16)):
        c.star(x + sx, y + sy, 7, (255, 220, 120))
        c.circle(x + sx, y + sy, 2, (255, 255, 255))
    chip(c, x + 6, y + h - 19, "3 SHOT DOWN", RED)


def art_cop31(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (222, 236, 224))
    # globe
    gx, gy, gr = x + 46, y + 28, 22
    c.circle(gx, gy, gr, (47, 109, 179))
    c.ellipse(gx - 7, gy - 5, 10, 7, (61, 150, 90))
    c.ellipse(gx + 7, gy + 7, 8, 6, (61, 150, 90))
    c.ellipse(gx + 10, gy - 10, 5, 4, (61, 150, 90))
    c.ring(gx, gy, gr, (26, 42, 74), 2)
    # thermometer
    tx = x + 118
    c.round_rect(tx, y + 10, 16, 44, 8, (255, 255, 255))
    c.rect(tx, y + 10, 16, 44, (26, 42, 74), 1)
    c.fill_rect(tx + 5, y + 22, 6, 26, RED)
    c.circle(tx + 8, y + 52, 9, RED)
    c.circle(tx + 8, y + 52, 5, (255, 255, 255))
    c.circle(tx + 8, y + 52, 3, RED)
    c.draw_text("libsans_b", 10, tx + 22, y + 12, "+1.5\u00b0C", RED)
    # wall clock, hands at five past one
    cx, cy = x + 238, y + 30
    c.circle(cx, cy, 22, (255, 255, 255))
    c.ring(cx, cy, 22, (26, 42, 74), 2)
    c.line(cx, cy, cx, cy - 15, INK, 2)
    c.line(cx, cy, cx + 10, cy - 5, INK, 2)
    c.circle(cx, cy, 2, RED)
    c.draw_text("libsans_b", 10, cx - 22, y + 56, "DAY 13", NAVY)
    chip(c, x + 6, y + h - 19, "DAY 13 \u00b7 NO DEAL", RED)


def art_peru(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (238, 226, 200))
    # mountains
    c.polygon([(x, y + h), (x + 70, y + 18), (x + 140, y + h)], (150, 110, 70))
    c.polygon([(x + 100, y + h), (x + 190, y + 8), (x + 280, y + h)],
              (120, 88, 56))
    c.polygon([(x + 58, y + 30), (x + 70, y + 18), (x + 82, y + 30)],
              (255, 255, 255))
    c.polygon([(x + 178, y + 20), (x + 190, y + 8), (x + 202, y + 20)],
              (255, 255, 255))
    # seismograph trace
    pts = []
    for i in range(25):
        px = x + 8 + i * 13
        py = y + 44 + ((i * 37) % 17 - 8) * (1 if i % 3 else 2)
        pts.append((px, py))
    c.polyline(pts, RED, 2)
    # house with red roof
    hx, hy = x + 250, y + 44
    c.fill_rect(hx, hy, 34, 20, (255, 255, 255))
    c.rect(hx, hy, 34, 20, (26, 42, 74), 1)
    c.polygon([(hx - 4, hy), (hx + 17, hy - 12), (hx + 38, hy)], RED)
    c.fill_rect(hx + 14, hy + 10, 7, 10, (26, 42, 74))
    # magnitude badge
    c.circle(x + 34, y + 20, 15, RED)
    c.draw_text("libsans_b", 10, x + 34, y + 15, "6.7", (255, 255, 255),
                align="center")
    chip(c, x + 6, y + h - 19, "6.7 \u00b7 00:09 UTC", RED)


HERO_ART = (art_riyadh, art_cop31, art_peru)


# ------------------------------------------------------------- mini art
def mini_sky(c, x, y, w, h, top, bottom):
    c.fill_rect(x, y, w, h, top)
    c.fill_rect(x, y + h - 10, w, 10, bottom)


def art_kyiv(c, x, y, w, h):
    mini_sky(c, x, y, w, h, (26, 42, 74), (16, 24, 52))
    for bx, bw, bh in ((6, 34, 26), (46, 28, 34), (80, 36, 22), (122, 30, 30),
                       (158, 32, 24)):
        c.fill_rect(x + bx, y + h - 10 - bh, bw, bh, (10, 16, 36))
        for wy in range(y + h - 10 - bh + 5, y + h - 12, 8):
            for wx in range(x + bx + 4, x + bx + bw - 4, 8):
                if (wx + wy) % 3:
                    c.fill_rect(wx, wy, 2, 3, (240, 200, 90))
    c.star(x + 168, y + 12, 8, (255, 170, 60))
    c.fill_rect(x + 8, y + 6, 22, 4, (47, 109, 179))
    c.fill_rect(x + 8, y + 10, 22, 4, (240, 200, 90))
    chip(c, x + 4, y + h - 17, "42 HURT", RED)


def art_warsaw(c, x, y, w, h):
    mini_sky(c, x, y, w, h, (214, 228, 238), (180, 190, 196))
    # Polish flag + NATO flag
    c.fill_rect(x + 10, y + 8, 30, 8, (255, 255, 255))
    c.fill_rect(x + 10, y + 16, 30, 8, (220, 40, 50))
    c.fill_rect(x + 48, y + 8, 30, 16, (20, 60, 160))
    c.star(x + 63, y + 16, 5, (255, 255, 255))
    # plane (dark, so it reads against the pale sky)
    c.polygon([(x + 110, y + 30), (x + 150, y + 26), (x + 186, y + 30),
               (x + 150, y + 34)], NAVY)
    c.polygon([(x + 140, y + 26), (x + 148, y + 16), (x + 154, y + 26)],
              NAVY)
    c.line(x + 100, y + 40, x + 190, y + 40, NAVY, 1)


def art_mercury(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (12, 14, 30))
    for sx, sy in ((20, 8), (60, 16), (150, 10), (180, 22), (40, 40),
                   (120, 42), (170, 44)):
        c.set(x + sx, y + sy, (255, 255, 255))
        c.set(x + sx + 1, y + sy, (220, 220, 220))
    c.circle(x + 96, y + 28, 18, (168, 158, 140))
    c.circle(x + 90, y + 22, 3, (140, 130, 112))
    c.circle(x + 102, y + 32, 4, (140, 130, 112))
    c.circle(x + 98, y + 18, 2, (140, 130, 112))
    chip(c, x + 4, y + h - 17, "19:24 CET", NAVY)


def art_hormuz(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (150, 190, 205))
    c.fill_rect(x, y + 30, w, h - 30, (38, 90, 130))
    c.fill_rect(x, y + 30, w, 2, (255, 255, 255))
    # tanker
    c.fill_rect(x + 40, y + 30, 110, 12, (60, 60, 60))
    c.fill_rect(x + 120, y + 20, 14, 10, (60, 60, 60))
    c.fill_rect(x + 40, y + 42, 110, 4, (179, 35, 42))
    # drone
    c.fill_rect(x + 150, y + 8, 22, 4, (20, 20, 20))
    for dx, dy in ((148, 5), (174, 5), (148, 13), (174, 13)):
        c.circle(x + dx, y + dy, 3, (20, 20, 20))


def art_washington(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (26, 42, 74))
    # server racks
    for rx in (10, 44, 78):
        c.fill_rect(x + rx, y + 8, 28, 34, (16, 24, 52))
        for ry in range(y + 12, y + 40, 7):
            c.fill_rect(x + rx + 4, ry, 12, 3, (90, 200, 140))
            c.circle(x + rx + 22, ry + 1, 1, (240, 200, 90))
    # capitol dome: drum + dome + lantern
    c.fill_rect(x + 140, y + 40, 40, 6, (240, 235, 225))
    c.polygon([(x + 142, y + 40), (x + 148, y + 28), (x + 172, y + 28),
               (x + 178, y + 40)], (240, 235, 225))
    c.fill_rect(x + 158, y + 20, 4, 8, (240, 235, 225))
    c.circle(x + 160, y + 19, 3, (240, 235, 225))
    c.fill_rect(x + 144, y + 46, 4, 4, (240, 235, 225))
    c.fill_rect(x + 172, y + 46, 4, 4, (240, 235, 225))


def art_beijing(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (200, 30, 36))
    c.star(x + 26, y + 16, 9, (255, 220, 60))
    for sx, sy in ((52, 10), (60, 18), (56, 28), (46, 30)):
        c.star(x + sx, y + sy, 4, (255, 220, 60))
    # pagoda roof silhouette
    c.polygon([(x + 100, y + 44), (x + 140, y + 20), (x + 180, y + 44)],
              (26, 42, 74))
    c.fill_rect(x + 112, y + 44, 56, 4, (26, 42, 74))
    c.polygon([(x + 118, y + 48), (x + 140, y + 34), (x + 162, y + 48)],
              (26, 42, 74))


def art_davao(c, x, y, w, h):
    mini_sky(c, x, y, w, h, (150, 200, 225), (120, 130, 120))
    # plane
    c.ellipse(x + 96, y + 22, 46, 7, (255, 255, 255))
    c.polygon([(x + 80, y + 22), (x + 96, y + 8), (x + 108, y + 22)],
              (230, 230, 230))
    c.polygon([(x + 120, y + 26), (x + 128, y + 38), (x + 134, y + 26)],
              (230, 230, 230))
    c.fill_rect(x + 140, y + 18, 4, 10, (200, 30, 36))
    # runway + green check
    c.fill_rect(x, y + h - 8, w, 3, (90, 90, 90))
    c.circle(x + 176, y + 14, 10, (61, 150, 90))
    c.polyline([(x + 171, y + 14), (x + 175, y + 18), (x + 182, y + 9)],
               (255, 255, 255), 2)
    chip(c, x + 4, y + h - 17, "146 SAFE", TEAL)


def art_canberra(c, x, y, w, h):
    mini_sky(c, x, y, w, h, (214, 228, 238), (120, 160, 110))
    # Australian flag (blue + stars) and Chinese flag (red + stars)
    c.fill_rect(x + 14, y + 8, 52, 28, (20, 60, 160))
    for sx, sy in ((24, 16), (40, 14), (52, 20), (30, 28), (48, 30)):
        c.star(x + sx, y + sy, 3, (255, 255, 255))
    c.fill_rect(x + 74, y + 8, 52, 28, (200, 30, 36))
    c.star(x + 88, y + 18, 6, (255, 220, 60))
    for sx, sy in ((104, 13), (110, 19), (106, 27), (98, 28)):
        c.star(x + sx, y + sy, 2, (255, 220, 60))
    c.fill_rect(x + 138, y + 8, 52, 28, (255, 255, 255))
    c.draw_text("libsans_b", 10, x + 164, y + 16, "AI", NAVY, align="center")


def art_markets(c, x, y, w, h):
    c.fill_rect(x, y, w, h, (255, 253, 247))
    for gy in range(y + 8, y + h - 8, 10):
        c.hline(x + 6, gy, w - 12, (230, 224, 208), 1)
    c.polyline([(x + 10, y + 12), (x + 50, y + 18), (x + 90, y + 14),
                (x + 130, y + 28), (x + 150, y + 40)], RED, 2)
    c.circle(x + 172, y + 24, 13, (240, 160, 40))
    c.draw_text("libsans_b", 12, x + 172, y + 19, "B", (255, 255, 255),
                align="center")
    chip(c, x + 4, y + h - 17, "$58,983", NAVY)


def art_wellington(c, x, y, w, h):
    mini_sky(c, x, y, w, h, (150, 200, 225), (90, 150, 90))
    # stumps + bat + ball
    for sx in (96, 103, 110):
        c.fill_rect(x + sx, y + 26, 3, 16, (240, 210, 120))
    c.fill_rect(x + 96, y + 24, 17, 3, (240, 210, 120))
    c.line(x + 130, y + 44, x + 150, y + 14, (150, 110, 70), 4)
    c.circle(x + 162, y + 12, 5, RED)
    c.circle(x + 30, y + 14, 11, (255, 255, 255))
    c.draw_text("libsans_b", 8, x + 30, y + 11, "124*", NAVY, align="center")
    chip(c, x + 4, y + h - 17, "124*", TEAL)


MINI_ART = {4: art_kyiv, 5: art_warsaw, 6: art_mercury, 7: art_hormuz,
            8: art_washington, 9: art_beijing, 10: art_davao,
            11: art_canberra, 12: art_markets, 13: art_wellington}

# ---------------------------------------------------------------- world map
# Rough continent outlines (lon, lat), drawn by hand for this page.
NA = [(-168, 66), (-158, 58), (-145, 60), (-132, 56), (-126, 50), (-124, 42),
      (-120, 34), (-114, 29), (-108, 23), (-102, 18), (-96, 16), (-92, 15),
      (-86, 12), (-82, 9), (-79, 9), (-83, 11), (-87, 14), (-90, 20),
      (-92, 19), (-97, 24), (-94, 29), (-89, 30), (-84, 30), (-81, 26),
      (-80, 32), (-76, 35), (-74, 40), (-70, 42), (-66, 45), (-60, 47),
      (-55, 51), (-59, 55), (-64, 58), (-68, 59), (-76, 62), (-82, 66),
      (-88, 66), (-94, 69), (-102, 68), (-112, 68), (-122, 70), (-132, 69),
      (-142, 70), (-152, 71), (-160, 71), (-166, 68)]
GL = [(-56, 64), (-52, 60), (-44, 60), (-40, 64), (-32, 68), (-24, 70),
      (-20, 74), (-24, 77), (-34, 79), (-46, 80), (-56, 78), (-58, 74),
      (-59, 69)]
SA = [(-79, 9), (-77, 5), (-79, 0), (-81, -5), (-79, -9), (-76, -13),
      (-72, -18), (-70, -22), (-70, -28), (-72, -34), (-73, -40),
      (-73, -46), (-74, -50), (-70, -54), (-66, -55), (-68, -51),
      (-65, -46), (-62, -41), (-58, -38), (-57, -35), (-52, -33),
      (-48, -28), (-42, -23), (-39, -18), (-35, -9), (-35, -6), (-38, -4),
      (-43, -2), (-48, 0), (-52, 4), (-56, 6), (-60, 8), (-64, 10),
      (-68, 11), (-72, 12), (-76, 10)]
EU = [(-10, 36), (-9, 38), (-9, 43), (-3, 44), (-1, 46), (-4, 48), (-1, 49),
      (2, 51), (4, 53), (7, 54), (8, 57), (10, 58), (12, 56), (16, 56),
      (19, 55), (21, 55), (24, 58), (27, 59), (30, 60), (29, 62), (25, 65),
      (21, 69), (25, 71), (30, 70), (34, 68), (38, 66), (42, 65), (44, 62),
      (41, 60), (39, 57), (36, 55), (33, 53), (30, 52), (28, 51), (25, 49),
      (23, 46), (21, 44), (19, 42), (16, 40), (14, 42), (12, 44), (8, 44),
      (5, 43), (3, 42), (0, 40), (-2, 37), (-6, 36)]
AF = [(-6, 35), (-9, 32), (-13, 28), (-16, 24), (-17, 20), (-17, 15),
      (-16, 11), (-13, 8), (-9, 5), (-5, 5), (0, 6), (5, 5), (9, 4),
      (9, 1), (11, -3), (13, -8), (12, -12), (13, -17), (14, -22),
      (15, -27), (17, -31), (19, -34), (24, -34), (28, -33), (31, -29),
      (34, -26), (35, -22), (36, -18), (39, -15), (40, -11), (41, -5),
      (42, -1), (46, 0), (51, 2), (51, 8), (49, 11), (45, 11), (43, 12),
      (40, 15), (38, 18), (37, 21), (35, 25), (34, 28), (32, 31), (28, 32),
      (23, 33), (18, 33), (13, 33), (10, 35), (6, 37), (2, 37), (-2, 35)]
AS = [(30, 36), (28, 41), (30, 45), (35, 46), (40, 47), (45, 47), (50, 46),
      (55, 48), (60, 50), (65, 52), (70, 55), (75, 58), (80, 60), (85, 63),
      (90, 65), (95, 68), (100, 70), (105, 72), (110, 74), (115, 73),
      (120, 73), (125, 72), (130, 72), (135, 71), (140, 71), (145, 72),
      (150, 71), (155, 70), (160, 69), (165, 68), (170, 66), (175, 66),
      (178, 65), (170, 64), (162, 60), (158, 56), (156, 52), (150, 59),
      (142, 54), (140, 48), (138, 44), (136, 38), (132, 35), (129, 33),
      (127, 38), (124, 40), (122, 38), (120, 32), (118, 26), (114, 22),
      (110, 20), (108, 16), (106, 10), (104, 6), (102, 2), (100, 6),
      (98, 10), (96, 14), (94, 16), (92, 21), (90, 22), (88, 21),
      (86, 20), (82, 17), (80, 14), (80, 8), (77, 8), (75, 11), (73, 16),
      (71, 20), (69, 22), (67, 24), (64, 25), (61, 25), (58, 25),
      (57, 27), (55, 27), (52, 28), (50, 29), (48, 30), (45, 29),
      (42, 27), (40, 24), (39, 21), (37, 17), (35, 15), (33, 13),
      (31, 12), (34, 12), (37, 13), (40, 14), (43, 12), (46, 12),
      (49, 14), (52, 15), (55, 17), (58, 20), (58, 24), (56, 26),
      (54, 27), (52, 28), (50, 29), (48, 30), (45, 29), (43, 28),
      (41, 26), (39, 23), (37, 20), (36, 17), (35, 14), (34, 13),
      (32, 12), (30, 14), (28, 18), (27, 22), (28, 26), (30, 30),
      (33, 31), (35, 33), (36, 36)]
AU = [(113, -22), (114, -30), (115, -33), (118, -35), (124, -33),
      (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
      (145, -38), (150, -37), (153, -32), (153, -27), (150, -23),
      (146, -19), (142, -15), (142, -11), (137, -12), (135, -15),
      (132, -12), (130, -13), (126, -14), (122, -17), (118, -20),
      (114, -21)]
NZ = [(167, -45), (168, -44), (172, -41), (174, -39), (176, -38),
      (178, -37), (175, -40), (172, -43), (168, -46)]

# pin number -> (lon, lat, nudge_x, nudge_y); 6 is flown from Darmstadt,
# 12 is the markets story, pinned in New York.
PINS = {
    1: (30.7, 36.9, 0, 0),
    2: (46.7, 24.6, -8, 8),
    3: (-76.0, -10.8, 0, 0),
    4: (30.5, 50.4, 10, -5),
    5: (21.0, 52.2, -3, -10),
    6: (8.6, 49.9, -13, 8),
    7: (56.5, 26.5, 10, -6),
    8: (-77.0, 38.9, -16, 10),
    9: (116.4, 39.9, 0, 0),
    10: (125.6, 7.1, 0, 0),
    11: (149.1, -35.3, 0, 0),
    12: (-74.0, 40.7, 12, -10),
    13: (174.8, -41.3, 0, 0),
}


def draw_map(c, x, y, w, h):
    c.fill_rect(x, y, w, h, SEA)
    sx = w / 360.0
    sy = h / 131.0

    def pt(lon, lat):
        return (int(round(x + (lon + 170) * sx)),
                int(round(y + (75 - lat) * sy)))

    for poly in (NA, GL, SA, EU, AF, AS, AU, NZ):
        c.polygon([pt(lon, lat) for lon, lat in poly], LAND)
        c.polyline([pt(lon, lat) for lon, lat in poly] + [pt(*poly[0])],
                   LANDB, 1)
    for num in range(1, 14):
        lon, lat, nx, ny = PINS[num]
        px, py = pt(lon, lat)
        px += nx
        py += ny
        r = 8 if num >= 10 else 7
        c.circle(px, py, r, RED)
        c.ring(px, py, r, (255, 255, 255), 1)
        c.draw_text("libsans_b", 8, px, py - 5, str(num),
                    (255, 255, 255), align="center")


# ---------------------------------------------------------------- layout
def build():
    c = Canvas(W, H, PAPER)

    # ---- kicker
    c.draw_text("libsans_b", 11, 8, 5, "THE WORLD IN ONE DAY", RED)
    c.draw_text("libsans_b", 10, 1016, 6,
                "35 STORIES \u00b7 7 REGIONS \u00b7 EVERY ONE DATED "
                "SATURDAY 21 NOVEMBER 2026", INK, align="right")
    c.hline(8, 21, 1008, NAVY, 2)

    # ---- masthead: the date is the biggest text on the page
    c.draw_text("bodoni", 62, 512, 27, "Saturday 21 November 2026", INK,
                align="center")
    c.hline(8, 97, 1008, INK, 1)
    c.draw_text("gelasio", 15, 512, 102, SUBHEAD, INK, align="center")
    c.hline(8, 122, 1008, HAIR, 1)

    # ---- stat strip: six big numbers
    cell = 1008 // 6
    for i, (num, lab1, lab2) in enumerate(STAT):
        cx = 8 + i * cell
        c.draw_text("libsans_b", 30, cx + 8, 128, num,
                    RED if i % 2 == 0 else NAVY)
        c.draw_text("gelasio", 9, cx + 8, 160, lab1, INK)
        c.draw_text("gelasio", 9, cx + 8, 170, lab2, INK)
        if i:
            c.vline(cx, 128, 54, HAIR, 1)

    # ---- region bar (widths proportional to story counts, min 56)
    total = sum(n for _lbl, n, _col in REGIONS)
    widths = []
    for _lbl, n, _col in REGIONS:
        widths.append(max(56, 1008 * n // total))
    widths[4] -= sum(widths) - 1008  # take the rounding slack from Americas
    rx = 8
    for (label, _n, col), wseg in zip(REGIONS, widths):
        c.fill_rect(rx, 186, wseg, 16, col)
        c.draw_text("libsans_b", 9, rx + wseg // 2, 189, label,
                    (255, 255, 255), align="center")
        rx += wseg

    # ---- three hero cards
    hy = 208
    hh = 170
    hw = 330
    for i, hero in enumerate(HERO):
        x = 8 + i * (hw + 9)
        c.fill_rect(x, hy, hw, hh, CARD)
        c.rect(x, hy, hw, hh, HAIR, 1)
        HERO_ART[i](c, x + 1, hy + 1, hw - 2, 70)
        kicker_line(c, x + 6, hy + 77, hero["num"], hero["place"],
                    hero["beat"], 10)
        end = c.draw_wrapped("baskerville", 17, x + 6, hy + 91,
                             hero["headline"], INK, hw - 12, 19)
        end = c.draw_wrapped("gelasio", 11, x + 6, end + 2, hero["deck"],
                             INK, hw - 12, 12)
        c.draw_text("roboto", 8, x + 6, min(end + 2, hy + hh - 12),
                    hero["src"], GRAY)

    # ---- ten secondary cards, two rows of five
    sy = 384
    sh = 148
    sw = 198
    for row in range(2):
        for col in range(5):
            idx = row * 5 + col
            num, place, head, deck, src, _chip = SECONDARY[idx]
            x = 8 + col * (sw + 4)
            y = sy + row * (sh + 6)
            c.fill_rect(x, y, sw, sh, CARD)
            c.rect(x, y, sw, sh, HAIR, 1)
            MINI_ART[num](c, x + 1, y + 1, sw - 2, 52)
            c.draw_text("libsans_b", 9, x + 6, y + 57, str(num), RED)
            c.draw_text("libsans_b", 9,
                        x + 6 + text_w("libsans_b", 9, str(num)) + 4,
                        y + 57, place, INK)
            end = c.draw_wrapped("baskerville", 13, x + 6, y + 70, head,
                                 INK, sw - 12, 16)
            end = c.draw_wrapped("gelasio", 9, x + 6, end + 1, deck, INK,
                                 sw - 12, 12)
            c.draw_text("roboto", 8, x + 6, y + sh - 11, src, GRAY)

    # ---- bottom: map left, list right
    by = 692
    c.draw_text("libsans_b", 11, 8, by, "WHERE IT HAPPENED", INK)
    draw_map(c, 8, by + 18, 322, 192)
    c.draw_text("gelasio", 9, 8, by + 214,
                "Pins 1\u201313 mark the pictured stories.", INK)
    c.draw_text("gelasio", 9, 8, by + 225,
                "6 BepiColombo is flown from Darmstadt.", INK)

    c.draw_text("libsans_b", 11, 338, by,
                "ALSO ON SATURDAY 21 NOVEMBER 2026 \u2014 22 MORE STORIES",
                INK)
    for i, (num, text) in enumerate(MORE):
        col = i // 11
        row = i % 11
        lx = 338 + col * 344
        ly = by + 20 + row * 19
        c.draw_text("libsans_b", 10, lx, ly, str(num), RED)
        size = 10
        while size > 8 and text_w("gelasio", size, text) > 308:
            size -= 1
        c.draw_text("gelasio", size, lx + 24, ly, text, INK)

    # ---- date check
    dy = 938
    c.fill_rect(8, dy, 1008, 50, (251, 240, 234))
    c.rect(8, dy, 1008, 50, RED, 2)
    lines = wrap("DATE CHECK \u2014 " + DATE_CHECK, "gelasio", 10, 980)
    y = dy + 5
    for ln in lines:
        if ln.startswith("DATE CHECK"):
            head = "DATE CHECK \u2014 "
            c.draw_text("libsans_b", 10, 20, y, head, RED)
            c.draw_text("gelasio", 10, 20 + text_w("libsans_b", 10, head),
                        y, ln[len(head):], INK)
        else:
            c.draw_text("gelasio", 10, 20, y, ln, INK)
        y += 13

    # ---- footer
    c.hline(8, 994, 1008, HAIR, 1)
    c.draw_text("gelasio", 9, 512, 1000, FOOTER, GRAY, align="center")
    return c


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    canvas = build()
    n = write_png(out, canvas)
    print("wrote %s (%d bytes)" % (out, n))


if __name__ == "__main__":
    main()
