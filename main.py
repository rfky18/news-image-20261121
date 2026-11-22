#!/usr/bin/env python3
"""news-image-20261121 v7 — one front page, Saturday 21 November 2026.

Stdlib-only renderer: draws every pixel in pure Python and blits text
from the bitmap atlas built by tools/gen_atlas.py (real OFL TTFs).
No external images, no network. Deterministic: same inputs => same bytes.

Layout (1024x1024, cream paper #f7f2e7, navy #1a2a4a, red #b3232a):
  kicker | date masthead | sub-headline | 6-number stat strip | region bar
  3 hero cards + 10 secondary cards (flat-vector illustrations, badges)
  dotted-grid world map with numbered pins 1-13 | 22 more stories (14-35)
  DATE CHECK (red frame) | verification footer
"""
import json
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = "/output"

W, H = 1024, 1024

PAPER = (247, 242, 231)
CARD = (255, 253, 246)
INK = (20, 20, 20)
NAVY = (26, 42, 74)
RED = (179, 35, 42)
GREY = (110, 108, 100)
LINE = (70, 70, 66)
TEAL = (15, 118, 110)
OCHRE = (180, 83, 9)
MAP_BG = (227, 233, 236)
MAP_DOT = (46, 74, 102)
GOLD = (201, 162, 39)

# ---------------------------------------------------------------- data

KICKER_L = "THE WORLD IN ONE DAY"
KICKER_R = "35 STORIES \u00b7 7 REGIONS \u00b7 EVERY ONE DATED SATURDAY 21 NOVEMBER 2026"
MASTHEAD = "Saturday 21 November 2026"
SUB = "COP31 talks run into overtime \u00b7 missiles intercepted over Riyadh \u00b7 a 6.7 quake shakes Peru"

STATS = [
    ("DAY 13", "of COP31, meant to close on day 12"),
    ("3", "missiles shot down over Riyadh"),
    ("6.7", "magnitude of the Peru quake"),
    ("146", "people safe after the Davao landing"),
    ("$58,983", "bitcoin early Saturday, down 3.9% in a day"),
    ("124*", "K L Rahul\u2019s score at tea in Wellington"),
]

REGIONS = [
    ("EUROPE", 4, (47, 93, 168)),
    ("ASIA", 9, (179, 35, 42)),
    ("MIDDLE EAST", 3, (136, 78, 160)),
    ("AFRICA", 2, (30, 132, 73)),
    ("AMERICAS", 11, (91, 44, 111)),
    ("OCEANIA", 3, (20, 143, 119)),
    ("GLOBAL", 3, (93, 109, 126)),
]

# (num, place, beat, badge, headline, deck, source)
HEROES = [
    (1, "RIYADH \u00b7 SAUDI ARABIA", "CONFLICT", "CONFIRMED",
     "Saudi defences shoot down three missiles aimed at the capital",
     "Third night of alerts in a row; two blasts heard about 02:00, no damage or casualties.",
     "Reuters \u00b7 AFP \u00b7 coalition statement"),
    (2, "ANTALYA \u00b7 T\u00dcRKIYE", "CLIMATE", "OFFICIAL",
     "Climate summit runs into overtime with no deal",
     "Talks pass Friday\u2019s deadline with no agreement; a third draft is due Saturday morning.",
     "AP \u00b7 AFP \u00b7 Al Jazeera"),
    (3, "CARHUAMAYO \u00b7 PERU", "EARTHQUAKE", "OFFICIAL",
     "Magnitude 6.7 earthquake rattles central Peru",
     "A deep tremor struck near Carhuamayo just after midnight UTC. Peru\u2019s institute reported no deaths, no tsunami risk.",
     "USGS \u00b7 IGP"),
]

SECONDARY = [
    (4, "KYIV \u00b7 WAR", "CONFIRMED",
     "Russian strikes kill 12 in Ukraine",
     "Two dead, 42 hurt in the Kryvyi Rih double strike; toll confirmed Saturday.",
     "Kyiv Post \u00b7 AP"),
    (5, "WARSAW \u00b7 NATO", "OFFICIAL",
     "Rutte flies to Warsaw for NATO talks",
     "NATO chief visits on Saturday; Warsaw asks for more Eastern Sentry forces.",
     "AP"),
    (6, "MERCURY \u00b7 SPACE", "OFFICIAL",
     "BepiColombo burns for Mercury",
     "Thrusters fire at 19:24 CET tonight.",
     "ESA"),
    (7, "HORMUZ \u00b7 WAR", "REPORTED",
     "Iran says it downed a US drone",
     "Tehran claims the shootdown; Washington has not confirmed it.",
     "IRIB"),
    (8, "WASHINGTON \u00b7 TECHNOLOGY", "REPORTED",
     "Trump vows tax on data centres abroad",
     "\u201cTremendous\u201d penalty promised; no details yet.",
     "ABC"),
    (9, "BEIJING \u00b7 DIPLOMACY", "REPORTED",
     "China tells Japan to \u2018correct\u2019 Taiwan words",
     "Tokyo says its stance is unchanged.",
     "Ministry \u00b7 AFP"),
    (10, "DAVAO \u00b7 AVIATION", "CONFIRMED",
     "Jet lands safely after engine fire alert",
     "Air Niugini 767 diverts after midnight; all 146 on board safe.",
     "Airline \u00b7 AP"),
    (11, "CANBERRA \u00b7 DIPLOMACY", "OFFICIAL",
     "Australia and China agree AI talks",
     "Albanese ends an 11-day trip.",
     "ABC"),
    (12, "WORLD \u00b7 MARKETS", "CONFIRMED",
     "Bitcoin slips below $59,000",
     "Down 3.9% in 24 hours; ether $1,625.",
     "CoinGecko"),
    (13, "WELLINGTON \u00b7 CRICKET", "CONFIRMED",
     "Rahul century puts India on top",
     "India 344 for 2 at tea, replying to 368.",
     "AFP"),
]

# (num, one-liner with source in parens)
MORE = [
    (14, "Copenhagen: Russian attach\u00e9 expelled (Al Jazeera)"),
    (15, "Antalya: EU warns COP31 risks a \u201cfossil summit\u201d (AFP)"),
    (16, "Antalya: Panama threatens to block climate text (Al Jazeera)"),
    (17, "Antalya: Indonesia PLN signs clean-power deals (Antara)"),
    (18, "Yemen: Houthis threaten Jeddah and Red Sea ports (Al Jazeera)"),
    (19, "Washington: Vance \u2014 Iran strikes were Trump\u2019s call (Reuters)"),
    (20, "Washington: Lawmaker threatens SpaceX\u2019s funding (CNN)"),
    (21, "Texas: Execution of man of 70 takes 63 minutes (ABC)"),
    (22, "Los Angeles: Jury convicts man of starting Palisades fire (ABC)"),
    (23, "Missouri: Judge approves $7.25bn Roundup settlement (AFP)"),
    (24, "Vancouver: Canada rests defence in youth climate trial (AFP)"),
    (25, "Pyongyang: Kim tours factories after no Trump meeting (AFP)"),
    (26, "Bayelsa: Funeral boat capsizes, 4 dead (AFP/Al Jazeera)"),
    (27, "Taipei: Budget and cash payout are passed (Taipei Times)"),
    (28, "Bangkok: Six-point plan on arsenic in two rivers (The Nation)"),
    (29, "New Delhi: Pakistani minister joins SCO forum in India (Dawn)"),
    (30, "Eastern India: Rain alerts as Akvan\u2019s remnant moves inland (ETV)"),
    (31, "Myanmar: Rights groups urge sanctions after court ruling (AP)"),
    (32, "Port Louis: African rating agency talks to 15 states (Al Jazeera)"),
    (33, "Melbourne: Cummins keeps the Australian captaincy (ABC)"),
    (34, "Las Vegas: Verstappen sent to stewards after contact (Autosport)"),
    (35, "Las Vegas: Russell fastest in final practice, 1:34.041 (Formula 1)"),
]

DATE_CHECK = (
    "DATE CHECK \u2014 Left out as Friday 20 November\u2019s news: Wall Street\u2019s fall "
    "into a correction \u00b7 the Russian barrage that hit Kyiv\u2019s bridges \u00b7 the missile "
    "that landed in Poland \u00b7 the UK\u2013EU deal \u00b7 Cyclone Akvan\u2019s landfall \u00b7 Gaza "
    "strikes that killed six. Older still: the Shenzhen summit and the ICJ Myanmar ruling "
    "(Thursday 19 November) \u00b7 Voyager 1\u2019s light-day (18 November). Not confirmed when "
    "drawn, so not shown: a final COP31 text."
)

FOOTER = ("Every story here happened, or was first reported, on Saturday 21 November 2026. "
          "Sources named beside each story \u00b7 Original drawings \u00b7 Drawn in code")

# Dotted-grid world map: 51 cols x 30 rows, '#' = land. Hand-drawn schematic
# (lon -180..180 left to right, lat 78..-55 top to bottom). Normalised in code.
MAP_ROWS = [
    "......###...................#......#############...",
    "...########..#####..............##################.",
    "#############.###..........#############################",
    ".#############........#....########################",
    ".##############.........#..###.###################.",
    ".....##########.........#####..###################.",
    "......#########.........#########################..",
    "......#########..........#######...###.....########",
    "......#########.........##########.####...######.##",
    "......########..........###....#####.####.#####....",
    ".....#######.............###########..#########....",
    "......####...............###########..###..###.....",
    ".......###...............###########..###..####....",
    "........###...............#########....##..######..",
    ".........###...............#########.......######..",
    "..........###...............########........######.",
    "...........####..............#######..........#####",
    "...........#####.............######...........####.",
    "...........######.............#####.............###",
    "...........######.............####..........#####..",
    "............#####.............####.........#######.",
    "............#####.............###.#........#######.",
    "............####..............###.#........#######.",
    "............####..............###...........#####..",
    "............###...............##............####..#",
    "............###..............................###..#",
    "............##....................................#",
    "............##.....................................",
    "............##.....................................",
    "............#......................................",
]

# (num, x, y) pin centres in page coords; schematic, nudged so neighbours
# in crowded Europe do not overlap. 6 = ESA Darmstadt (flies BepiColombo).
PINS = [
    (1, 206, 743), (2, 197, 727), (3, 105, 788), (4, 201, 709),
    (5, 188, 697), (6, 176, 713), (7, 222, 734), (8, 104, 723),
    (9, 268, 722), (10, 276, 765), (11, 296, 820), (12, 163, 700),
    (13, 317, 828),
]

BADGE_COLOR = {"OFFICIAL": NAVY, "CONFIRMED": TEAL, "REPORTED": OCHRE}


# ---------------------------------------------------------------- canvas

class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(bytes(bg) * (w * h))
        self.cx0, self.cy0, self.cx1, self.cy1 = 0, 0, w, h

    def clip(self, x0, y0, x1, y1):
        self.cx0, self.cy0, self.cx1, self.cy1 = x0, y0, x1, y1

    def unclip(self):
        self.cx0, self.cy0, self.cx1, self.cy1 = 0, 0, self.w, self.h

    def px(self, x, y, c):
        if self.cx0 <= x < self.cx1 and self.cy0 <= y < self.cy1:
            o = (y * self.w + x) * 3
            self.buf[o] = c[0]
            self.buf[o + 1] = c[1]
            self.buf[o + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0 = max(x, self.cx0)
        x1 = min(x + w, self.cx1)
        y0 = max(y, self.cy0)
        y1 = min(y + h, self.cy1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            o = (yy * self.w + x0) * 3
            self.buf[o:o + len(row)] = row

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x0, x1, y, c, t=1):
        self.rect(x0, y, x1 - x0, t, c)

    def vline(self, x, y0, y1, c, t=1):
        self.rect(x, y0, t, y1 - y0, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.px(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, c):
        # Scanline fill, even-odd.
        ys = [p[1] for p in pts]
        for y in range(max(min(ys), self.cy0), min(max(ys) + 1, self.cy1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                a, b = int(math.ceil(xs[i])), int(math.floor(xs[i + 1]))
                self.rect(a, y, max(0, b - a + 1), 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for y in range(max(cy - ry, self.cy0), min(cy + ry + 1, self.cy1)):
            t = (y - cy) / ry
            if abs(t) > 1:
                continue
            dx = int(rx * math.sqrt(1 - t * t))
            self.rect(cx - dx, y, 2 * dx + 1, 1, c)

    def disc(self, cx, cy, r, c):
        self.ellipse(cx, cy, r, r, c)

    def ring(self, cx, cy, r, t, c):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = math.hypot(xx - cx, yy - cy)
                if r - t <= d <= r:
                    self.px(xx, yy, c)

    def dashed_line(self, x0, y0, x1, y1, c, dash=5, gap=4):
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(dist))
        on = True
        run = 0
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            if on:
                self.px(x, y, c)
            run += 1
            if run >= (dash if on else gap):
                on = not on
                run = 0

    def bezier_dash(self, p0, p1, p2, c, dash=4, gap=3):
        prev = None
        on = True
        run = 0
        for i in range(101):
            t = i / 100
            x = int(round((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]))
            y = int(round((1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
            if prev is not None and (x, y) != prev:
                if on:
                    self.line(prev[0], prev[1], x, y, c)
                run += 1
                if run >= (dash if on else gap):
                    on = not on
                    run = 0
            prev = (x, y)

    def star(self, cx, cy, r, c):
        self.line(cx - r, cy, cx + r, cy, c)
        self.line(cx, cy - r, cx, cy + r, c)
        self.line(cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2, c)
        self.line(cx - r // 2, cy + r // 2, cx + r // 2, cy - r // 2, c)

    def sparkle(self, cx, cy, r, c):
        self.poly([(cx, cy - r), (cx + r // 3, cy - r // 3), (cx + r, cy),
                   (cx + r // 3, cy + r // 3), (cx, cy + r),
                   (cx - r // 3, cy + r // 3), (cx - r, cy),
                   (cx - r // 3, cy - r // 3)], c)


# ---------------------------------------------------------------- text

class Atlas:
    def __init__(self):
        with open(os.path.join(ROOT, "atlas.json")) as f:
            data = json.load(f)
        with open(os.path.join(ROOT, "atlas.bin"), "rb") as f:
            self.pix = f.read()
        self.aw = data["w"]
        self.glyphs = data["glyphs"]
        self.metrics = data["metrics"]

    def asc(self, font):
        return self.metrics[font]["asc"]

    def width(self, font, s):
        total = 0
        for ch in s:
            g = self.glyphs.get("%s|%d" % (font, ord(ch)))
            if g is None:
                g = self.glyphs.get("%s|%d" % (font, 63))
            total += g[4]
        return total

    def draw(self, cv, x, y_top, s, font, color):
        base = y_top + self.metrics[font]["asc"]
        pen = x
        aw = self.aw
        pix = self.pix
        buf = cv.buf
        cw = cv.w
        for ch in s:
            g = self.glyphs.get("%s|%d" % (font, ord(ch)))
            if g is None:
                g = self.glyphs.get("%s|%d" % (font, 63))
            gx, gy, gw, gh, adv, ox, oy = g
            if gw and gh:
                dx = pen + ox
                dy = base + oy
                for iy in range(gh):
                    row = (gy + iy) * aw + gx
                    by = dy + iy
                    if by < cv.cy0 or by >= cv.cy1:
                        continue
                    for ix in range(gw):
                        m = pix[row + ix]
                        if not m:
                            continue
                        bx = dx + ix
                        if bx < cv.cx0 or bx >= cv.cx1:
                            continue
                        o = (by * cw + bx) * 3
                        if m == 255:
                            buf[o] = color[0]
                            buf[o + 1] = color[1]
                            buf[o + 2] = color[2]
                        else:
                            inv = 255 - m
                            buf[o] = (color[0] * m + buf[o] * inv) // 255
                            buf[o + 1] = (color[1] * m + buf[o + 1] * inv) // 255
                            buf[o + 2] = (color[2] * m + buf[o + 2] * inv) // 255
            pen += adv
        return pen

    def draw_at(self, cv, x, y_top, s, font, color, align="l", width=None):
        w = self.width(font, s)
        if align == "c":
            x = x + (width - w) // 2
        elif align == "r":
            x = x + width - w
        return self.draw(cv, x, y_top, s, font, color)

    def wrap(self, s, font, maxw):
        words = s.split(" ")
        lines, cur = [], ""
        for wd in words:
            trial = wd if not cur else cur + " " + wd
            if self.width(font, trial) <= maxw:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                while self.width(font, wd) > maxw and len(wd) > 1:
                    cut = len(wd) - 1
                    while cut > 1 and self.width(font, wd[:cut]) > maxw:
                        cut -= 1
                    lines.append(wd[:cut])
                    wd = wd[cut:]
                cur = wd
        if cur:
            lines.append(cur)
        return lines

# ---------------------------------------------------------------- badges

def draw_badge(cv, at, x_right, y, label):
    color = BADGE_COLOR[label]
    w = at.width("sansb9", label) + 10
    h = 13
    cv.rect(x_right - w, y, w, h, color)
    at.draw(cv, x_right - w + 5, y + 2, label, "sansb9", (255, 255, 255))


# ---------------------------------------------------------------- illustrations
# Each ill(cv, at, x, y, w, h) draws a flat-vector scene inside the box.

def ill_riyadh(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (13, 20, 45))
    for sx, sy, r in [(30, 10, 3), (150, 6, 2), (210, 14, 3), (90, 16, 2), (280, 8, 2)]:
        cv.sparkle(x + sx, y + sy, r, (240, 220, 140))
    cv.disc(x + w - 28, y + 16, 9, (240, 230, 180))
    cv.disc(x + w - 24, y + 13, 8, (13, 20, 45))
    base = y + h
    towers = [(0, 34, 26), (36, 26, 42), (64, 30, 20), (96, 28, 48),
              (126, 32, 30), (160, 26, 54), (188, 30, 24), (220, 28, 40),
              (250, 30, 28), (282, 26, 46), (310, 18, 30)]
    for bx, bw, bh in towers:
        cv.rect(x + bx, base - bh, bw, bh, (24, 34, 66))
        for wy in range(base - bh + 5, base - 3, 7):
            for wx in range(x + bx + 4, x + bx + bw - 3, 7):
                if (wx + wy) % 3:
                    cv.rect(wx, wy, 2, 3, (250, 210, 110))
    cv.rect(x, base - 4, w, 4, (8, 12, 28))
    arcs = [((x + 30, y + 2), (x + 80, y + 26), (x + 128, y + 40)),
            ((x + 130, y + 0), (x + 180, y + 20), (x + 216, y + 34)),
            ((x + 230, y + 4), (x + 268, y + 24), (x + 296, y + 30))]
    for p0, p1, p2 in arcs:
        cv.bezier_dash(p0, p1, p2, (250, 220, 130))
        cv.star(p2[0], p2[1], 6, (255, 190, 60))
        cv.disc(p2[0], p2[1], 2, (255, 240, 180))


def ill_cop(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (222, 238, 228))
    gx, gy, gr = x + 54, y + 34, 26
    cv.disc(gx, gy, gr, (64, 132, 168))
    cv.ellipse(gx - 12, gy - 14, 9, 7, (86, 168, 104))
    cv.ellipse(gx + 4, gy + 2, 11, 8, (86, 168, 104))
    cv.ellipse(gx - 4, gy + 12, 7, 5, (86, 168, 104))
    cv.ring(gx, gy, gr, 2, (26, 42, 74))
    cv.line(gx - gr, gy - 8, gx - 6, gy - 20, (255, 255, 255))
    # Upright thermometer with scale + red fill (not a lollipop).
    tx = x + 138
    cv.rect(tx - 2, y + 8, 12, 46, (255, 255, 255))
    cv.frame(tx - 2, y + 8, 12, 46, NAVY, 1)
    cv.rect(tx + 1, y + 22, 6, 32, RED)
    cv.disc(tx + 4, y + 58, 9, RED)
    cv.disc(tx + 4, y + 58, 9, RED)
    cv.frame(tx - 2, y + 8, 12, 46, NAVY, 1)
    cv.disc(tx + 4, y + 58, 6, (255, 255, 255))
    cv.disc(tx + 4, y + 58, 5, RED)
    for i in range(5):
        ty = y + 12 + i * 9
        cv.hline(tx + 10, tx + 16, ty, NAVY)
    at.draw(cv, tx + 18, y + 10, "+1.5\u00b0C", "sansb11", RED)
    at.draw(cv, tx + 18, y + 24, "LIMIT", "sans9", GREY)
    # Wall clock: DAY 13.
    cx, cy, cr = x + 262, y + 32, 24
    cv.disc(cx, cy, cr, (255, 255, 255))
    cv.ring(cx, cy, cr, 2, NAVY)
    cv.disc(cx, cy, 2, NAVY)
    cv.line(cx, cy, cx, cy - 15, NAVY)
    cv.line(cx, cy, cx + 11, cy + 6, NAVY)
    at.draw(cv, cx - 18, y + 58, "DAY 13", "sansb10", NAVY)


def ill_peru(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (233, 236, 226))
    cv.poly([(x, y + h), (x + 90, y + 12), (x + 180, y + h)], (146, 110, 74))
    cv.poly([(x + 78, y + 20), (x + 90, y + 12), (x + 102, y + 20), (x + 90, y + 26)], (255, 255, 255))
    cv.poly([(x + 130, y + h), (x + 230, y + 22), (x + 330, y + h)], (120, 88, 58))
    cv.poly([(x + 220, y + 29), (x + 230, y + 22), (x + 240, y + 29), (x + 230, y + 35)], (255, 255, 255))
    cv.rect(x, y + h - 10, w, 10, (110, 140, 90))
    # Red seismograph trace.
    pts = [(x + 8, y + 40), (x + 40, y + 40), (x + 52, y + 28), (x + 64, y + 52),
           (x + 76, y + 22), (x + 88, y + 56), (x + 100, y + 40), (x + 150, y + 40),
           (x + 162, y + 30), (x + 174, y + 50), (x + 186, y + 40), (x + 240, y + 40)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], RED)
    # House with red roof.
    hx, hy = x + w - 62, y + h - 34
    cv.rect(hx, hy + 10, 34, 16, (250, 244, 224))
    cv.poly([(hx - 4, hy + 12), (hx + 17, hy - 4), (hx + 38, hy + 12)], RED)
    cv.rect(hx + 14, hy + 16, 7, 10, NAVY)
    cv.disc(x + 24, y + 20, 15, RED)
    at.draw_at(cv, x + 24, y + 20, "6.7", "bask13", (255, 255, 255), align="c", width=0)


def ill_kyiv(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (16, 24, 52))
    cv.sparkle(x + 20, y + 8, 3, (240, 220, 140))
    cv.sparkle(x + 150, y + 6, 2, (240, 220, 140))
    base = y + h
    for bx, bw, bh in [(0, 30, 22), (32, 24, 32), (58, 28, 18), (88, 26, 30),
                       (116, 30, 20), (148, 26, 34), (176, 18, 24)]:
        cv.rect(x + bx, base - bh, bw, bh, (30, 42, 78))
        for wy in range(base - bh + 4, base - 3, 6):
            for wx in range(x + bx + 3, x + bx + bw - 2, 6):
                if (wx * 7 + wy) % 4 == 0:
                    cv.rect(wx, wy, 2, 2, (250, 210, 110))
    cv.star(x + w - 30, y + 14, 8, (255, 160, 40))
    cv.disc(x + w - 30, y + 14, 4, (255, 220, 120))
    cv.disc(x + 60, y + 12, 6, (120, 120, 120))
    cv.disc(x + 70, y + 9, 5, (140, 140, 140))


def ill_warsaw(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (214, 228, 238))
    cv.disc(x + w - 24, y + 12, 8, (250, 200, 90))
    cv.rect(x + 20, y + h - 24, 90, 24, (150, 150, 148))
    cv.poly([(x + 20, y + h - 24), (x + 65, y + h - 38), (x + 110, y + h - 24)], (120, 120, 118))
    for i in range(5):
        cx = x + 34 + i * 14
        cv.vline(cx, y + h - 22, y + h - 2, (240, 240, 238))
    # Poland flag (white over red) and NATO flag (blue, white dots).
    cv.vline(x + 130, y + 6, y + h - 2, NAVY)
    cv.rect(x + 130, y + 6, 22, 6, (255, 255, 255))
    cv.rect(x + 130, y + 12, 22, 6, (220, 40, 50))
    cv.vline(x + 162, y + 6, y + h - 2, NAVY)
    cv.rect(x + 162, y + 6, 22, 12, (30, 70, 160))
    for dx, dy in [(4, 3), (11, 2), (17, 4), (7, 8), (15, 8)]:
        cv.disc(x + 162 + dx, y + 6 + dy, 1, (255, 255, 255))


def ill_bepi(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (10, 14, 30))
    for sx, sy in [(12, 8), (40, 20), (170, 6), (150, 34), (90, 6), (185, 26), (60, 36)]:
        cv.disc(x + sx, y + sy, 1, (255, 255, 255))
    # Mercury, bottom right, cratered.
    cv.disc(x + w - 18, y + h - 12, 10, (150, 148, 140))
    cv.disc(x + w - 22, y + h - 15, 2, (110, 108, 100))
    cv.disc(x + w - 14, y + h - 9, 3, (110, 108, 100))
    # Solar panels (blue, grid lines) + gold body + dish.
    bx, by = x + w // 2, y + h // 2 - 4
    cv.rect(bx - 62, by - 4, 34, 10, (40, 90, 170))
    cv.rect(bx + 28, by - 4, 34, 10, (40, 90, 170))
    for gx in range(bx - 62, bx + 62, 8):
        if gx < bx - 28 or gx > bx + 28:
            cv.vline(gx, by - 4, by + 6, (180, 200, 230))
    cv.rect(bx - 28, by - 8, 56, 16, (201, 162, 39))
    cv.frame(bx - 28, by - 8, 56, 16, (120, 90, 20), 1)
    cv.rect(bx - 6, by - 3, 12, 6, (120, 90, 20))
    cv.line(bx - 20, by - 8, bx - 28, by - 13, (220, 220, 220))
    cv.disc(bx - 29, by - 14, 3, (220, 220, 220))
    # Thruster flames + dotted trail.
    cv.poly([(bx - 12, by + 8), (bx - 4, by + 8), (bx - 8, by + 20)], (255, 140, 40))
    cv.poly([(bx + 4, by + 8), (bx + 12, by + 8), (bx + 8, by + 20)], (255, 200, 60))
    cv.dashed_line(bx - 8, by + 22, bx - 8, y + h - 2, (255, 200, 120), 3, 3)
    at.draw(cv, x + 4, y + 3, "19:24 CET", "robo8", (255, 255, 255))


def ill_hormuz(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (200, 220, 235))
    cv.disc(x + 24, y + 12, 8, (250, 200, 90))
    cv.rect(x, y + 26, w, h - 26, (38, 108, 128))
    for wy in range(y + 30, y + h - 2, 6):
        for wx in range(x + 4, x + w - 4, 16):
            cv.hline(wx, wx + 8, wy, (180, 220, 230))
    cx, cy = x + w // 2, y + 16
    cv.ellipse(cx, cy, 12, 4, (30, 30, 30))
    cv.line(cx - 16, cy - 6, cx + 16, cy + 6, (30, 30, 30))
    cv.line(cx - 16, cy + 6, cx + 16, cy - 6, (30, 30, 30))
    for rx, ry in [(-18, -7), (18, 7), (-18, 7), (18, -7)]:
        cv.hline(cx + rx - 5, cx + rx + 5, cy + ry, (30, 30, 30))
    cv.disc(cx, cy + 2, 2, RED)


def ill_washington(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (26, 42, 74))
    cv.sparkle(x + 18, y + 8, 2, (240, 220, 140))
    cx = x + w // 2
    cv.ellipse(cx, y + 20, 26, 14, (240, 240, 236))
    cv.rect(cx - 26, y + 20, 52, 4, (240, 240, 236))
    cv.rect(cx - 22, y + 24, 44, 16, (225, 225, 220))
    for i in range(6):
        cv.vline(cx - 19 + i * 8, y + 24, y + 40, NAVY)
    cv.rect(cx - 30, y + 40, 60, 4, (240, 240, 236))
    cv.vline(cx, y + 2, y + 8, (240, 240, 236))
    cv.rect(cx, y + 2, 10, 6, RED)


def ill_beijing(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (198, 44, 44))
    for sx, sy, r in [(16, 8, 3), (28, 12, 2), (36, 6, 2), (24, 18, 2)]:
        cv.sparkle(x + sx, y + sy, r, (250, 220, 80))
    gx = x + w // 2 - 40
    cv.rect(gx, y + h - 26, 80, 26, (90, 20, 30))
    cv.poly([(gx - 6, y + h - 26), (gx + 40, y + h - 40), (gx + 86, y + h - 26)], (60, 12, 20))
    cv.rect(gx + 34, y + h - 18, 12, 18, (250, 220, 80))
    for i in range(3):
        cv.vline(gx + 12 + i * 26, y + h - 24, y + h - 2, (60, 12, 20))
    cv.rect(x, y + h - 4, w, 4, (140, 28, 28))


def ill_davao(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (186, 214, 236))
    cv.ellipse(x + 20, y + 8, 14, 5, (255, 255, 255))
    cv.ellipse(x + 130, y + 6, 16, 5, (255, 255, 255))
    cx, cy = x + w // 2, y + 18
    cv.ellipse(cx, cy, 34, 7, (255, 255, 255))
    cv.poly([(cx - 6, cy - 2), (cx + 6, cy - 2), (cx + 26, cy + 12), (cx + 14, cy + 12)], (220, 225, 230))
    cv.poly([(cx + 20, cy - 4), (cx + 30, cy - 4), (cx + 34, cy + 4), (cx + 26, cy + 4)], (220, 225, 230))
    cv.poly([(cx - 30, cy - 2), (cx - 22, cy - 2), (cx - 26, cy - 10), (cx - 32, cy - 8)], (200, 205, 210))
    cv.disc(cx - 14, cy + 8, 2, (40, 40, 40))
    cv.disc(cx + 12, cy + 8, 2, (40, 40, 40))
    cv.rect(x, y + h - 8, w, 8, (90, 90, 90))
    for wx in range(x + 8, x + w - 8, 20):
        cv.hline(wx, wx + 10, y + h - 4, (255, 255, 255))
    cv.disc(x + w - 16, y + 10, 8, (30, 132, 73))
    cv.line(x + w - 20, y + 10, x + w - 17, y + 13, (255, 255, 255))
    cv.line(x + w - 17, y + 13, x + w - 11, y + 6, (255, 255, 255))


def ill_canberra(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (222, 230, 222))
    cv.rect(x + 104, y + 20, 66, h - 20, (170, 170, 166))
    for wy in range(y + 25, y + h - 3, 7):
        for wx in range(x + 109, x + 166, 8):
            cv.rect(wx, wy, 3, 4, (240, 240, 238))
    cv.vline(x + 16, y + 6, y + h - 2, NAVY)
    cv.rect(x + 16, y + 6, 30, 16, (30, 70, 160))
    cv.sparkle(x + 24, y + 12, 2, (255, 255, 255))
    cv.sparkle(x + 36, y + 16, 2, (255, 255, 255))
    cv.sparkle(x + 40, y + 10, 2, (255, 255, 255))
    cv.vline(x + 56, y + 6, y + h - 2, NAVY)
    cv.rect(x + 56, y + 6, 30, 16, (198, 44, 44))
    cv.sparkle(x + 64, y + 12, 3, (250, 220, 80))
    cv.sparkle(x + 74, y + 10, 2, (250, 220, 80))
    cv.sparkle(x + 78, y + 16, 2, (250, 220, 80))


def ill_markets(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (255, 253, 246))
    cv.vline(x + 8, y + 4, y + h - 8, (180, 180, 175))
    cv.hline(x + 8, x + w - 8, y + h - 8, (180, 180, 175))
    candles = [(22, 12, 10), (48, 18, 10), (74, 24, 10), (100, 30, 10), (126, 36, 10)]
    for cx, top, ch in candles:
        cv.vline(x + cx + 5, y + top - 4, y + top + ch + 4, RED)
        cv.rect(x + cx, y + top, 10, ch, RED)
    cv.line(x + 22, y + 8, x + 136, y + 40, RED)
    cv.disc(x + w - 22, y + 32, 11, GOLD)
    at.draw_at(cv, x + w - 22, y + 27, "B", "bask13", (120, 85, 10), align="c", width=0)


def ill_cricket(cv, at, x, y, w, h):
    cv.rect(x, y, w, h, (96, 160, 96))
    at.draw(cv, x + 4, y + 3, "124*", "sansb10", (255, 255, 255))
    # Horizontal pitch strip with stumps standing on it.
    cv.rect(x + 24, y + 26, w - 48, 12, (214, 186, 140))
    sx = x + w // 2 - 8
    for i in range(3):
        cv.vline(sx + i * 7, y + 14, y + 26, (250, 220, 90))
    cv.hline(sx, sx + 14, y + 14, (250, 220, 90))
    # Bat leaning on the strip, bottom left; red ball flying at the stumps.
    cv.poly([(x + 22, y + h - 2), (x + 32, y + h - 4), (x + 58, y + 28), (x + 48, y + 30)], (222, 184, 120))
    cv.disc(x + w // 2 - 16, y + 16, 5, (179, 35, 42))


ILL = {1: ill_riyadh, 2: ill_cop, 3: ill_peru, 4: ill_kyiv, 5: ill_warsaw,
       6: ill_bepi, 7: ill_hormuz, 8: ill_washington, 9: ill_beijing,
       10: ill_davao, 11: ill_canberra, 12: ill_markets, 13: ill_cricket}


# ---------------------------------------------------------------- cards

def hero_card(cv, at, x, y, w, h, story):
    num, place, beat, badge, headline, deck, src = story
    cv.rect(x, y, w, h, CARD)
    cv.frame(x, y, w, h, LINE, 1)
    cv.clip(x + 1, y + 1, x + w - 1, y + 71)
    ILL[num](cv, at, x + 1, y + 1, w - 2, 70)
    cv.unclip()
    draw_badge(cv, at, x + w - 5, y + 5, badge)
    at.draw(cv, x + 8, y + 76, "%d  %s \u2014 %s" % (num, place, beat), "sansb11", RED)
    lines = at.wrap(headline, "bask17", w - 16)[:2]
    yy = y + 90
    for ln in lines:
        at.draw(cv, x + 8, yy, ln, "bask17", INK)
        yy += 20
    dlines = at.wrap(deck, "gel10", w - 16)[:2]
    yy = y + 132
    for ln in dlines:
        at.draw(cv, x + 8, yy, ln, "gel10", INK)
        yy += 13
    at.draw(cv, x + 8, y + 160, src, "robo8", GREY)


def sec_card(cv, at, x, y, w, h, story):
    num, place, badge, headline, deck, src = story
    cv.rect(x, y, w, h, CARD)
    cv.frame(x, y, w, h, LINE, 1)
    cv.clip(x + 1, y + 1, x + w - 1, y + 47)
    ILL[num](cv, at, x + 1, y + 1, w - 2, 46)
    cv.unclip()
    draw_badge(cv, at, x + w - 4, y + 4, badge)
    at.draw(cv, x + 7, y + 50, "%d  %s" % (num, place), "sansb10", RED)
    lines = at.wrap(headline, "bask13", w - 14)[:2]
    yy = y + 63
    for ln in lines:
        at.draw(cv, x + 7, yy, ln, "bask13", INK)
        yy += 15
    dlines = at.wrap(deck, "gel9", w - 14)[:2]
    yy = y + 95
    for ln in dlines:
        at.draw(cv, x + 7, yy, ln, "gel9", INK)
        yy += 12
    at.draw(cv, x + 7, y + 121, src, "robo8", GREY)

# ---------------------------------------------------------------- page

def draw_map(cv, at, x0, y0, w, h):
    # Panel background + dotted-grid continents.
    cv.rect(x0, y0, w, h, MAP_BG)
    cv.frame(x0, y0, w, h, LINE, 1)
    at.draw(cv, x0 + 8, y0 + 8, "WHERE IT HAPPENED", "sansb12", NAVY)
    mx, my = x0 + 8, y0 + 26
    for r, row in enumerate(MAP_ROWS):
        row = row.ljust(51)[:51]
        for c, ch in enumerate(row):
            if ch == "#":
                cv.disc(mx + c * 6 + 3, my + r * 6 + 3, 2, MAP_DOT)
    for num, px, py in PINS:
        cv.disc(px, py, 7, RED)
        cv.ring(px, py, 7, 1, (255, 255, 255))
        at.draw_at(cv, px, py - 5, str(num), "sansb9", (255, 255, 255),
                align="c", width=0)
    cy = my + 184
    at.draw(cv, x0 + 8, cy, "Pins 1\u201313 mark the pictured stories.", "gel9", INK)
    at.draw(cv, x0 + 8, cy + 11, "6 BepiColombo is flown from Darmstadt.", "gel9", INK)
    at.draw(cv, x0 + 8, cy + 26, "Badges on the pictured stories:", "gel9", INK)
    yy = cy + 40
    for label, note in [("OFFICIAL", "official source"),
                        ("CONFIRMED", "several sources agree"),
                        ("REPORTED", "one claim, not yet confirmed")]:
        draw_badge(cv, at, x0 + 8 + at.width("sansb9", label) + 10, yy, label)
        at.draw(cv, x0 + 8 + at.width("sansb9", label) + 18, yy + 1, note, "gel9", INK)
        yy += 13
    at.draw(cv, x0 + 8, yy + 1, "Map: schematic dotted grid, not to scale.", "gel9", GREY)


def draw_list(cv, at, x0, y0, w):
    at.draw(cv, x0, y0, "ALSO ON SATURDAY 21 NOVEMBER 2026 \u2014 22 MORE STORIES",
            "sansb11", NAVY)
    cv.hline(x0, x0 + w, y0 + 18, LINE)
    col_w = (w - 14) // 2
    for half in range(2):
        cx = x0 + half * (col_w + 14)
        yy = y0 + 26
        for num, text in MORE[half * 11:(half + 1) * 11]:
            at.draw(cv, cx, yy, str(num), "sansb10", RED)
            lines = at.wrap(text, "gel10", col_w - 24)
            ly = yy
            for ln in lines:
                at.draw(cv, cx + 24, ly, ln, "gel10", INK)
                ly += 13
            yy = ly + 10


def render():
    at = Atlas()
    cv = Canvas(W, H, PAPER)
    cv.rect(0, 0, W, 4, RED)
    at.draw(cv, 8, 6, KICKER_L, "sansb11", RED)
    at.draw_at(cv, 8, 6, KICKER_R, "sansb11", INK, align="r", width=1008)
    cv.hline(8, 1016, 20, INK)
    at.draw_at(cv, 0, 18, MASTHEAD, "bodoni62", INK, align="c", width=W)
    cv.hline(8, 1016, 104, INK)
    at.draw_at(cv, 0, 108, SUB, "gel15i", INK, align="c", width=W)

    # Stat strip: 6 cells.
    for i, (val, lab) in enumerate(STATS):
        x = 8 + i * 168
        if i:
            cv.vline(x - 1, 124, 176, (200, 196, 186))
        color = RED if i in (0, 1, 4) else NAVY
        at.draw(cv, x + 2, 126, val, "bask28", color)
        lines = at.wrap(lab, "gel9", 164)[:2]
        yy = 156
        for ln in lines:
            at.draw(cv, x + 2, yy, ln, "gel9", GREY)
            yy += 9
    cv.hline(8, 1016, 176, LINE)

    # Region bar, widths proportional to counts (sum = 35).
    rx = 8
    for name, count, color in REGIONS:
        seg = int(round(count / 35 * 1008))
        cv.rect(rx, 180, seg, 16, color)
        at.draw_at(cv, rx, 182, "%s %d" % (name, count), "sansb9", (255, 255, 255),
                align="c", width=seg)
        rx += seg

    # Hero row.
    for i, story in enumerate(HEROES):
        hero_card(cv, at, 8 + i * 338, 200, 330, 172, story)
    # Secondary rows.
    for row in range(2):
        for col in range(5):
            sec_card(cv, at, 8 + col * 203, 376 + row * 141, 195, 135,
                     SECONDARY[row * 5 + col])

    # Bottom: map + list.
    draw_map(cv, at, 8, 656, 322, 300)
    draw_list(cv, at, 338, 656, 678)

    # DATE CHECK, red frame.
    cv.frame(8, 960, 1008, 42, RED, 2)
    prefix = "DATE CHECK \u2014 "
    body = DATE_CHECK[len(prefix):]
    pw = at.width("sansb10", prefix)
    lines = at.wrap(body, "gel10", 1008 - 16 - pw)
    at.draw(cv, 16, 965, prefix, "sansb10", RED)
    at.draw(cv, 16 + pw, 965, lines[0], "gel10", INK)
    for j, ln in enumerate(lines[1:3]):
        at.draw(cv, 16, 965 + (j + 1) * 13, ln, "gel10", INK)

    at.draw_at(cv, 0, 1007, FOOTER, "gel9", GREY, align="c", width=W)
    return cv


# ---------------------------------------------------------------- png

def chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def save_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * cv.w * 3:(y + 1) * cv.w * 3]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, "entry.png")
    cv = render()
    save_png(cv, out)


if __name__ == "__main__":
    main()
