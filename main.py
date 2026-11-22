#!/usr/bin/env python3
"""news-image-20261121 v8 -- one-day world news front page, 1024x1024.

Stdlib only. No network. Deterministic: two runs produce byte-identical
PNG. Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).

All text comes from a bitmap atlas (atlas.bin + atlas.json) rendered at
build time from real TTF files by tools/gen_atlas.py -- every glyph is a
filled bitmap from the actual font, never a geometric stroke font.

Layout: classic front page. Masthead IS the date. Stat strip, region
bar, 3 hero cards + 10 secondary cards (all 13 with a bold banner label
and a verification badge), dotted-grid world map with numbered pins,
22 more dated stories, DATE CHECK, footer. 35 stories, 7 regions.
Every story happened, or was first reported, on Saturday 21 November
2026. News from 19-20 November appears ONLY in the DATE CHECK box.
"""
import json
import os
import struct
import zlib

W, H = 1024, 1024
BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)
CARD = (255, 253, 246)
INK = (22, 22, 22)
NAVY = (26, 42, 74)
RED = (179, 35, 42)
TEAL = (15, 118, 110)
OCHRE = (183, 121, 31)
BLUE = (47, 93, 138)
PURPLE = (124, 74, 138)
GREEN = (63, 125, 78)
GRAY = (107, 98, 89)
LINE = (201, 191, 168)
CARDBRD = (216, 205, 180)
WHITE = (255, 255, 255)
SKY = (207, 227, 234)
NIGHT = (16, 28, 54)
NIGHT2 = (30, 48, 84)
GOLD = (232, 196, 90)
CREAM = (250, 240, 200)


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

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = c
        row = bytes((r, g, b)) * (x1 - x0)
        for yy in range(y0, y1):
            self.px[yy * self.w * 3 + x0 * 3: yy * self.w * 3 + x1 * 3] = row

    def hline(self, x0, x1, y, c, t=1):
        for dy in range(t):
            for x in range(x0, x1):
                self.set(x, y + dy, c)

    def vline(self, x, y0, y1, c, t=1):
        for dx in range(t):
            for y in range(y0, y1):
                self.set(x + dx, y, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            for a in range(t):
                for b in range(t):
                    self.set(x + a, y + b, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            dx = int((r * r - dy * dy) ** 0.5) if abs(dy) <= r else -1
            if dx >= 0:
                self.rect(cx - dx, yy, dx * 2 + 1, 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for yy in range(cy - r - 1, cy + r + 2):
            for xx in range(cx - r - 1, cx + r + 2):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if abs(d - r) <= t / 2.0:
                    self.set(xx, yy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            dy = (yy - cy) / float(ry) if ry else 0
            if abs(dy) > 1:
                continue
            dx = int(rx * (1 - dy * dy) ** 0.5)
            self.rect(cx - dx, yy, dx * 2 + 1, 1, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / float(y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), y, max(1, int(xs[i + 1]) - int(xs[i])), 1, c)

    def outline(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)


# ------------------------------------------------------------------- atlas
class Atlas:
    def __init__(self, base):
        with open(os.path.join(base, "atlas.json")) as f:
            self.meta = json.load(f)
        with open(os.path.join(base, "atlas.bin"), "rb") as f:
            self.raw = f.read()
        self.sw = self.meta["_sheet"]["w"]

    def width(self, key, s):
        g = self.meta[key]["glyphs"]
        tot = 0
        for ch in s:
            gl = g.get(ch) or g["?"]
            tot += gl[4]
        return tot

    def draw(self, cv, x, y, key, s, color):
        """Draw text; y is the top of the ascender line."""
        g = self.meta[key]["glyphs"]
        r, gg, b = color
        for ch in s:
            gl = g.get(ch) or g["?"]
            sx, sy, gw, gh, adv, ox, oy = gl
            if gw and gh:
                dx0, dy0 = x + ox, y + oy
                for row in range(gh):
                    yy = dy0 + row
                    if yy < 0 or yy >= cv.h:
                        continue
                    base = (sy + row) * self.sw + sx
                    for col in range(gw):
                        v = self.raw[base + col]
                        if v:
                            xx = dx0 + col
                            if 0 <= xx < cv.w:
                                i = (yy * cv.w + xx) * 3
                                if v >= 255:
                                    cv.px[i], cv.px[i + 1], cv.px[i + 2] = r, gg, b
                                else:
                                    cv.px[i] = (cv.px[i] * (255 - v) + r * v) // 255
                                    cv.px[i + 1] = (cv.px[i + 1] * (255 - v) + gg * v) // 255
                                    cv.px[i + 2] = (cv.px[i + 2] * (255 - v) + b * v) // 255
            x += adv
        return x

    def line_h(self, key):
        return self.meta[key]["line"]


ATLAS = None


def tw(key, s):
    return ATLAS.width(key, s)


def text(cv, x, y, key, s, color):
    return ATLAS.draw(cv, x, y, key, s, color)


def center(cv, cx, y, key, s, color):
    return text(cv, cx - tw(key, s) // 2, y, key, s, color)


def wrap(s, key, max_w, max_lines):
    """Greedy word wrap; returns at most max_lines lines."""
    words = s.split(" ")
    lines = []
    cur = ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if tw(key, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def para(cv, x, y, key, s, max_w, max_lines, color, leading=None):
    lh = leading if leading is not None else ATLAS.line_h(key)
    for i, ln in enumerate(wrap(s, key, max_w, max_lines)):
        text(cv, x, y + i * lh, key, ln, color)
    return y + len(wrap(s, key, max_w, max_lines)) * lh


# --------------------------------------------------------------------- png
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# -------------------------------------------------------------------- data
# 35 stories, all Saturday 21 November 2026. Sources named per story.
# Numbers/names cross-checked across the live top-10 consensus.
STATS = [
    ("DAY 13", "of COP31, meant to close on day 12", RED),
    ("3", "missiles shot down over Riyadh", NAVY),
    ("6.7", "magnitude of the Peru quake", RED),
    ("146", "people safe after the Davao landing", NAVY),
    ("$58,983", "bitcoin early Saturday, down 3.9% in a day", RED),
    ("124*", "K L Rahul's score at tea in Wellington", NAVY),
]

REGIONS = [
    ("EUROPE 4", 4, BLUE),
    ("ASIA 9", 9, RED),
    ("MIDDLE EAST 3", 3, TEAL),
    ("AFRICA 2", 2, PURPLE),
    ("AMERICAS 11", 11, NAVY),
    ("OCEANIA 3", 3, GREEN),
    ("GLOBAL 3", 3, GRAY),
]

BADGE_COLOR = {"OFFICIAL": TEAL, "CONFIRMED": NAVY, "REPORTED": RED}

# hero: (num, dateline, banner, headline, deck, source, badge, chip)
HEROES = [
    (1, "RIYADH · SAUDI ARABIA — CONFLICT", "RIYADH: MISSILES",
     "Saudi defences shoot down three missiles aimed at the capital",
     "Third night of alerts in a row; two blasts heard about 02:00, "
     "no damage or casualties.",
     "Reuters · AFP · coalition statement", "CONFIRMED",
     "3 shot down · 02:00 blasts"),
    (2, "ANTALYA · TÜRKIYE — CLIMATE", "COP31: OVERTIME",
     "Climate summit runs into overtime with no deal",
     "Talks pass Friday's deadline with no agreement; a third draft "
     "is due Saturday morning.",
     "AP · AFP · Al Jazeera", "OFFICIAL",
     "No deal · day 13"),
    (3, "CARHUAMAYO · PERU — EARTHQUAKE", "PERU: QUAKE 6.7",
     "Magnitude 6.7 earthquake rattles central Peru",
     "A deep tremor struck near Carhuamayo after midnight UTC; "
     "no deaths, no tsunami risk.",
     "USGS · IGP", "OFFICIAL",
     "00:09 UTC · 108 km deep"),
]

# secondary: (num, dateline, banner, banner_color, headline, deck,
#              source, badge)
SECONDARY = [
    (4, "KYIV · WAR", "12 KILLED", RED,
     "Russian strikes kill 12 in Ukraine",
     "Two dead, 42 injured in the Kryvyi Rih double strike; the toll "
     "was confirmed on Saturday.",
     "Kyiv Post · AP", "CONFIRMED"),
    (5, "WARSAW · NATO", "RUTTE VISITS", NAVY,
     "Rutte flies to Warsaw for NATO talks",
     "NATO chief visits on Saturday; Warsaw asks for more Eastern "
     "Sentry forces.",
     "AP", "OFFICIAL"),
    (6, "MERCURY · SPACE", "19:24 CET", TEAL,
     "BepiColombo burns for Mercury",
     "Thrusters fire at 19:24 CET tonight.",
     "ESA", "OFFICIAL"),
    (7, "HORMUZ · WAR", "DRONE DOWNED", RED,
     "Iran says it downed a US drone",
     "Tehran claims the shootdown; Washington has not confirmed it.",
     "IRIB", "REPORTED"),
    (8, "WASHINGTON · TECHNOLOGY", "DATA-CENTRE TAX", NAVY,
     "Trump vows tax on data centres abroad",
     "“Tremendous” penalty promised; no details yet.",
     "ABC", "REPORTED"),
    (9, "BEIJING · DIPLOMACY", "TAIWAN ROW", RED,
     "China tells Japan to ‘correct’ Taiwan words",
     "Tokyo says its stance is unchanged.",
     "Ministry · AFP", "REPORTED"),
    (10, "DAVAO · AVIATION", "146 SAFE", TEAL,
     "Jet lands safely after engine fire alert",
     "Air Niugini 767 diverts after midnight; all 146 on board safe.",
     "Airline · AP", "CONFIRMED"),
    (11, "CANBERRA · DIPLOMACY", "AI TALKS", NAVY,
     "Australia and China agree AI talks",
     "Albanese ends an 11-day trip.",
     "ABC", "OFFICIAL"),
    (12, "WORLD · MARKETS", "$58,983", OCHRE,
     "Bitcoin slips below $59,000",
     "Down 3.9% in 24 hours; ether $1,625.",
     "CoinGecko", "CONFIRMED"),
    (13, "WELLINGTON · CRICKET", "124*", OCHRE,
     "Rahul century puts India on top",
     "India 344 for 2 at tea, replying to 368.",
     "AFP", "CONFIRMED"),
]

# stories 14-35, two columns of 11
MORE = [
    "14 Copenhagen: Russian attaché expelled (Al Jazeera)",
    "15 Antalya: EU warns COP31 risks a “fossil summit” (AFP)",
    "16 Antalya: Panama threatens to block climate text (Al Jazeera)",
    "17 Antalya: Indonesia PLN signs clean-power deals (Antara)",
    "18 Yemen: Houthis threaten Jeddah and Red Sea ports (Al Jazeera)",
    "19 Washington: Vance — Iran strikes were Trump’s call (Reuters)",
    "20 Washington: Lawmaker threatens SpaceX’s funding (CNN)",
    "21 Texas: Execution of man of 70 takes 63 minutes (ABC)",
    "22 Los Angeles: Jury convicts man of starting Palisades fire (ABC)",
    "23 Missouri: Judge approves $7.25bn Roundup settlement (AFP)",
    "24 Vancouver: Canada rests defence in youth climate trial (AFP)",
    "25 Pyongyang: Kim tours factories after no Trump meeting (AFP)",
    "26 Bayelsa: Funeral boat capsizes, 4 dead (AFP/Al Jazeera)",
    "27 Taipei: Budget and cash payout are passed (Taipei Times)",
    "28 Bangkok: Six-point plan on arsenic in two rivers (The Nation)",
    "29 New Delhi: Pakistani minister joins SCO forum in India (Dawn)",
    "30 Eastern India: Rain alerts as Akvan’s remnant moves inland (ETV)",
    "31 Myanmar: Rights groups urge sanctions after court ruling (AP)",
    "32 Port Louis: African rating agency talks to 15 states (Al Jazeera)",
    "33 Melbourne: Cummins keeps the Australian captaincy (ABC)",
    "34 Las Vegas: Verstappen sent to stewards after contact (Autosport)",
    "35 Las Vegas: Russell fastest in final practice, 1:34.041 (Formula 1)",
]

DATE_CHECK = ("Left out as Friday 20 November’s news: Wall Street’s "
              "correction · the barrage that hit Kyiv’s bridges · the "
              "missile that landed in Poland · the UK–EU deal · Cyclone "
              "Akvan’s landfall · Gaza strikes that killed six. Older: "
              "the Shenzhen summit and ICJ Myanmar ruling (19 November) "
              "· Voyager 1’s light-day (18 November). Not confirmed when "
              "drawn: a final COP31 text.")


# ------------------------------------------------------------- illustrations
def starfield(cv, x, y, w, h, seed):
    pts = []
    s = seed
    for _ in range(26):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        px = x + 4 + s % max(1, w - 8)
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        py = y + 3 + s % max(1, h - 6)
        pts.append((px, py))
    for px, py in pts:
        cv.set(px, py, WHITE)
        if (px + py) % 3 == 0:
            cv.set(px + 1, py, WHITE)


def burst(cv, cx, cy, r, c):
    for k in range(8):
        ang = k * 3.14159 / 4
        dx = int(r * 0.9 * (1 if k % 2 == 0 else 0.6) * __import__("math").cos(ang))
        dy = int(r * 0.9 * (1 if k % 2 == 0 else 0.6) * __import__("math").sin(ang))
        cv.line(cx, cy, cx + dx, cy + dy, c, 2)
    cv.circle(cx, cy, 3, c)


def dashed_arc(cv, x0, y0, x1, y1, c):
    n = 26
    for i in range(n):
        if i % 2:
            continue
        t0 = i / float(n)
        t1 = (i + 1) / float(n)
        ax = int(x0 + (x1 - x0) * t0)
        ay = int(y0 + (y1 - y0) * t0 - 26 * 4 * t0 * (1 - t0))
        bx = int(x0 + (x1 - x0) * t1)
        by = int(y0 + (y1 - y0) * t1 - 26 * 4 * t1 * (1 - t1))
        cv.line(ax, ay, bx, by, c, 2)


def illo_riyadh(cv, x, y, w, h):
    cv.rect(x, y, w, h, NIGHT)
    cv.rect(x, y, w, 12, NIGHT2)
    starfield(cv, x, y, w, h - 26, 12345)
    cv.circle(x + w - 34, y + 16, 11, CREAM)
    cv.circle(x + w - 30, y + 13, 10, NIGHT)
    # skyline: five towers with lit windows
    base = y + h
    towers = [(0, 44, 34), (38, 58, 26), (72, 38, 40), (118, 52, 30),
              (152, 62, 22), (182, 46, 36), (222, 58, 26), (254, 40, 38),
              (292, 54, 30)]
    for tx, th, twd in towers:
        cv.rect(x + tx, base - th, twd, th, (10, 18, 38))
        for wy in range(base - th + 5, base - 4, 7):
            for wx in range(x + tx + 4, x + tx + twd - 3, 7):
                if (wx * 7 + wy * 3) % 5:
                    cv.rect(wx, wy, 2, 3, GOLD)
    # three dashed missile arcs + bursts
    dashed_arc(cv, x + 40, y + 8, x + 120, y + 46, GOLD)
    dashed_arc(cv, x + 150, y + 4, x + 215, y + 40, GOLD)
    dashed_arc(cv, x + 240, y + 10, x + 295, y + 44, GOLD)
    burst(cv, x + 120, y + 46, 8, GOLD)
    burst(cv, x + 215, y + 40, 7, WHITE)
    burst(cv, x + 295, y + 44, 8, GOLD)
    cv.line(x + 60, base - 44, x + 40, y + 6, (120, 140, 190), 1)
    cv.line(x + 250, base - 40, x + 285, y + 8, (120, 140, 190), 1)
    cv.rect(x, base - 3, w, 3, (8, 14, 30))


def illo_cop31(cv, x, y, w, h):
    cv.rect(x, y, w, h, SKY)
    cv.circle(x + w - 26, y + 14, 10, GOLD)
    for k in range(8):
        ang = k * 3.14159 / 4
        cv.line(x + w - 26, y + 14, x + w - 26 + int(16 * __import__("math").cos(ang)),
                y + 14 + int(16 * __import__("math").sin(ang)), GOLD, 1)
    # globe
    gx, gy, gr = x + 52, y + 38, 24
    cv.circle(gx, gy, gr, (64, 130, 190))
    cv.ellipse(gx - 8, gy - 6, 10, 7, (86, 170, 90))
    cv.ellipse(gx + 6, gy + 8, 9, 6, (86, 170, 90))
    cv.ellipse(gx + 10, gy - 12, 6, 5, (86, 170, 90))
    cv.ring(gx, gy, gr, NAVY, 1)
    # hills + flags (kept right so they never cross the clock label)
    cv.poly([(x, y + h), (x + 90, y + h - 22), (x + 170, y + h - 8),
             (x + w, y + h - 18), (x + w, y + h)], (86, 170, 90))
    for fx, fc in [(x + 282, RED), (x + 296, TEAL), (x + 310, OCHRE)]:
        cv.vline(fx, y + h - 30, y + h - 6, INK, 1)
        cv.rect(fx + 1, y + h - 30, 12, 9, fc)
    # thermometer
    tx = x + 150
    cv.rect(tx, y + 10, 12, 44, WHITE)
    cv.outline(tx, y + 10, 12, 44, NAVY, 1)
    cv.rect(tx + 2, y + 26, 8, 26, RED)
    cv.circle(tx + 6, y + 56, 9, RED)
    cv.circle(tx + 6, y + 56, 5, (200, 60, 60))
    for k in range(4):
        cv.hline(tx + 12, tx + 18, y + 16 + k * 9, NAVY, 1)
    text(cv, tx + 20, y + 8, "sansB9", "+1.5°C", RED)
    text(cv, tx + 20, y + 20, "sans9", "LIMIT", NAVY)
    # clock
    cx, cy = x + 250, y + 34
    cv.circle(cx, cy, 15, WHITE)
    cv.ring(cx, cy, 15, NAVY, 2)
    cv.line(cx, cy, cx, cy - 9, NAVY, 2)
    cv.line(cx, cy, cx + 6, cy + 3, NAVY, 2)
    text(cv, cx - 13, cy + 17, "sansB9", "DAY 13", NAVY)


def illo_peru(cv, x, y, w, h):
    cv.rect(x, y, w, h, (232, 224, 200))
    cv.circle(x + w - 30, y + 14, 9, GOLD)
    # mountain ranges
    cv.poly([(x, y + h), (x + 40, y + 22), (x + 90, y + h - 30),
             (x + 130, y + 18), (x + 190, y + h - 24), (x + 240, y + 30),
             (x + 290, y + h - 28), (x + w, y + h - 20), (x + w, y + h)],
            (120, 104, 84))
    cv.poly([(x, y + h), (x + 70, y + 44), (x + 150, y + h - 18),
             (x + 230, y + 48), (x + w, y + h - 14), (x + w, y + h)],
            (150, 132, 108))
    # seismograph trace
    pts = []
    for i in range(0, w - 8, 6):
        amp = 2 if i < w // 3 else (10 if w // 3 <= i < 2 * w // 3 else 3)
        pts.append((x + 4 + i, y + 26 + ((i * 37) % (2 * amp + 1)) - amp))
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], RED, 2)
    # houses with red roofs
    for hx in (x + 30, x + 120, x + 225):
        cv.rect(hx, y + h - 22, 34, 18, (240, 235, 220))
        cv.poly([(hx - 3, y + h - 22), (hx + 17, y + h - 34),
                 (hx + 37, y + h - 22)], RED)
        cv.rect(hx + 13, y + h - 12, 7, 8, NAVY)
    # cracked ground
    cv.line(x + 60, y + h - 4, x + 90, y + h - 12, (90, 70, 50), 1)
    cv.line(x + 90, y + h - 12, x + 130, y + h - 5, (90, 70, 50), 1)
    # magnitude badge
    cv.circle(x + 26, y + 20, 14, RED)
    text(cv, x + 26 - tw("sansB11", "6.7") // 2, y + 13, "sansB11", "6.7", WHITE)


def illo_mini(cv, x, y, w, h, num):
    if num == 4:  # Kyiv: night skyline + smoke
        cv.rect(x, y, w, h, NIGHT)
        starfield(cv, x, y, w, h - 14, 777)
        for bx, bh, bw in [(0, 22, 26), (30, 30, 20), (56, 18, 30),
                           (92, 26, 24), (122, 20, 26), (152, 28, 22)]:
            cv.rect(x + bx, y + h - bh, bw, bh, (10, 18, 38))
            for wy in range(y + h - bh + 4, y + h - 3, 6):
                for wx in range(x + bx + 3, x + bx + bw - 2, 6):
                    if (wx + wy) % 4 == 0:
                        cv.rect(wx, wy, 2, 2, GOLD)
        cv.circle(x + 150, y + 10, 7, (200, 120, 60))
        cv.circle(x + 156, y + 6, 5, (220, 150, 80))
    elif num == 5:  # Warsaw: parliament + Polish flag
        cv.rect(x, y, w, h, (214, 222, 228))
        cv.rect(x + 30, y + 16, 130, 20, (120, 122, 128))
        cv.poly([(x + 40, y + 16), (x + 95, y + 4), (x + 150, y + 16)], (90, 92, 100))
        for cx in range(44, 156, 14):
            cv.rect(x + cx, y + 20, 5, 14, (240, 240, 240))
        cv.vline(x + 176, y + 6, y + 34, INK, 1)
        cv.rect(x + 177, y + 6, 14, 6, WHITE)
        cv.rect(x + 177, y + 12, 14, 6, RED)
    elif num == 6:  # BepiColombo spacecraft
        cv.rect(x, y, w, h, NIGHT)
        starfield(cv, x, y, w, h, 4242)
        cv.circle(x + 168, y + 10, 8, (180, 180, 180))
        cv.rect(x + 52, y + 14, 26, 8, (64, 130, 190))
        cv.rect(x + 122, y + 14, 26, 8, (64, 130, 190))
        cv.rect(x + 82, y + 10, 36, 16, GOLD)
        cv.rect(x + 90, y + 14, 20, 8, (200, 160, 60))
        cv.line(x + 100, y + 10, x + 100, y + 2, WHITE, 1)
        cv.circle(x + 100, y + 2, 2, WHITE)
        cv.poly([(x + 82, y + 26), (x + 118, y + 26), (x + 108, y + 40),
                 (x + 92, y + 40)], (240, 120, 40))
        cv.circle(x + 100, y + 42, 3, GOLD)
    elif num == 7:  # Hormuz: drone over sea
        cv.rect(x, y, w, h, (168, 200, 214))
        cv.circle(x + 24, y + 10, 8, GOLD)
        cv.rect(x, y + 26, w, h - 26, (52, 96, 140))
        for wy in range(y + 30, y + h - 2, 6):
            cv.hline(x + 4, x + w - 4, wy, (120, 170, 205), 1)
        cv.rect(x + 88, y + 8, 20, 6, INK)
        cv.line(x + 78, y + 11, x + 88, y + 11, INK, 2)
        cv.line(x + 108, y + 11, x + 118, y + 11, INK, 2)
        cv.vline(x + 98, y + 4, y + 8, INK, 1)
    elif num == 8:  # Washington: capitol dome
        cv.rect(x, y, w, h, NAVY)
        cv.rect(x + 58, y + 26, 80, 12, WHITE)
        cv.poly([(x + 58, y + 26), (x + 98, y + 6), (x + 138, y + 26)], WHITE)
        cv.circle(x + 98, y + 18, 12, WHITE)
        cv.vline(x + 98, y + 2, y + 8, WHITE, 1)
        for cx in range(64, 132, 10):
            cv.rect(x + cx, y + 28, 4, 10, (200, 205, 215))
    elif num == 9:  # Beijing: flags + hall
        cv.rect(x, y, w, h, RED)
        cv.circle(x + 22, y + 12, 3, GOLD)
        cv.circle(x + 34, y + 9, 2, GOLD)
        cv.circle(x + 36, y + 18, 2, GOLD)
        cv.rect(x + 60, y + 18, 110, 20, (120, 40, 40))
        cv.poly([(x + 66, y + 18), (x + 115, y + 6), (x + 164, y + 18)], (90, 30, 30))
        cv.vline(x + 178, y + 6, y + 34, WHITE, 1)
        cv.rect(x + 179, y + 6, 12, 8, WHITE)
        cv.circle(x + 185, y + 10, 3, RED)
    elif num == 10:  # Davao: jet + runway
        cv.rect(x, y, w, h, SKY)
        cv.ellipse(x + 56, y + 12, 42, 8, WHITE)
        cv.poly([(x + 130, y + 16), (x + 150, y + 8), (x + 150, y + 20)], WHITE)
        cv.poly([(x + 66, y + 20), (x + 84, y + 34), (x + 96, y + 20)], WHITE)
        cv.line(x + 56, y + 16, x + 44, y + 12, WHITE, 2)
        for wx in range(62, 128, 8):
            cv.rect(x + wx, y + 15, 3, 3, NAVY)
        cv.rect(x, y + 36, w, 3, (90, 90, 90))
        cv.rect(x, y + 39, w, 5, (86, 170, 90))
    elif num == 11:  # Canberra: two flags
        cv.rect(x, y, w, h, (200, 216, 224))
        cv.rect(x + 30, y + 14, 120, 22, (150, 155, 160))
        for cx in range(38, 146, 12):
            cv.rect(x + cx, y + 18, 5, 14, (230, 230, 230))
        for fx, fc in [(x + 164, BLUE), (x + 182, RED)]:
            cv.vline(fx, y + 4, y + 34, INK, 1)
            cv.rect(fx + 1, y + 4, 12, 8, fc)
        cv.circle(x + 170, y + 8, 2, WHITE)
        cv.circle(x + 188, y + 8, 2, GOLD)
    elif num == 12:  # Markets: falling chart + coin
        cv.rect(x, y, w, h, (214, 232, 210))
        pts = [(x + 8, y + 10), (x + 40, y + 16), (x + 72, y + 14),
               (x + 104, y + 26), (x + 136, y + 30), (x + 168, y + 38)]
        for a, b in zip(pts, pts[1:]):
            cv.line(a[0], a[1], b[0], b[1], RED, 2)
        for px, py in pts:
            cv.circle(px, py, 3, RED)
        cv.circle(x + 178, y + 12, 9, GOLD)
        text(cv, x + 178 - tw("sansB9", "B") // 2, y + 8, "sansB9", "B", NAVY)
    elif num == 13:  # Cricket: bat, ball, stumps
        cv.rect(x, y, w, h, (120, 170, 110))
        cv.rect(x, y + 34, w, 10, (90, 140, 85))
        for sx in (x + 30, x + 36, x + 42):
            cv.vline(sx, y + 24, y + 34, GOLD, 2)
        cv.poly([(x + 90, y + 10), (x + 104, y + 8), (x + 100, y + 30),
                 (x + 88, y + 32)], (220, 200, 150))
        cv.circle(x + 150, y + 14, 6, RED)
        cv.circle(x + 152, y + 12, 2, WHITE)

# -------------------------------------------------------------------- cards
def badge(cv, x, y, label):
    w = tw("sansB9", label) + 10
    cv.rect(x, y, w, 14, BADGE_COLOR[label])
    text(cv, x + 5, y + 2, "sansB9", label, WHITE)
    return w


def chip(cv, x, y, s):
    w = tw("sansB9", s) + 12
    cv.rect(x, y, w, 17, WHITE)
    cv.outline(x, y, w, 17, NAVY, 1)
    text(cv, x + 6, y + 3, "sansB9", s, NAVY)
    return w


def hero_card(cv, x, y, w, h, hero, illo_fn):
    num, dateline, banner, headline, deck, source, bdg, chip_txt = hero
    cv.rect(x, y, w, h, CARD)
    cv.outline(x, y, w, h, CARDBRD, 1)
    illo_fn(cv, x + 1, y + 1, w - 2, 76)
    # badge top-right inside illustration
    bw = tw("sansB9", bdg) + 10
    badge(cv, x + w - bw - 6, y + 6, bdg)
    # overlay chip with the key fact, bottom-left of the illustration
    chip(cv, x + 6, y + 76 - 23, chip_txt)
    # bold red banner label across the whole card
    cv.rect(x + 1, y + 77, w - 2, 22, RED)
    text(cv, x + 8, y + 81, "sansB15", banner, WHITE)
    # dateline, headline, deck, source
    text(cv, x + 8, y + 103, "sansB10", dateline, RED)
    para(cv, x + 8, y + 118, "bask18", headline, w - 16, 2, INK, leading=22)
    para(cv, x + 8, y + 163, "gel11", deck, w - 16, 2, INK, leading=14)
    text(cv, x + 8, y + 189, "rob9", source, GRAY)


def secondary_card(cv, x, y, w, h, sec):
    num, dateline, banner, bcol, headline, deck, source, bdg = sec
    cv.rect(x, y, w, h, CARD)
    cv.outline(x, y, w, h, CARDBRD, 1)
    # coloured header strip carrying the key value / keyword
    cv.rect(x + 1, y + 1, w - 2, 20, bcol)
    text(cv, x + 8, y + 5, "sansB11", banner, WHITE)
    bw = tw("sansB9", bdg) + 10
    badge(cv, x + w - bw - 5, y + 24, bdg)
    illo_mini(cv, x + 1, y + 21, w - 2, 44, num)
    text(cv, x + 8, y + 68, "sansB9", dateline, RED)
    # source on the same row, right-aligned, like a byline
    text(cv, x + w - 8 - tw("rob9", source), y + 68, "rob9", source, GRAY)
    para(cv, x + 8, y + 81, "bask13", headline, w - 16, 2, INK, leading=16)
    para(cv, x + 8, y + 113, "gel10", deck, w - 16, 3, INK, leading=12)


# ---------------------------------------------------------------------- map
# Continents as unions of ellipses in (lon, lat, rx, ry) degrees.
BLOBS = [
    (-100, 48, 32, 16), (-95, 32, 18, 10), (-122, 62, 14, 9),
    (-152, 64, 11, 6), (-85, 14, 9, 5), (-42, 73, 9, 6), (-88, 21, 7, 4),
    (-60, -8, 11, 11), (-64, -22, 7, 11), (-70, -38, 4, 7),
    (10, 52, 14, 7), (22, 62, 11, 7), (24, 40, 9, 5), (-2, 54, 3, 3),
    (17, 6, 16, 12), (20, -14, 11, 11), (28, -26, 7, 6), (44, 8, 7, 5),
    (55, 52, 22, 11), (88, 52, 26, 11), (105, 32, 16, 9), (78, 21, 9, 7),
    (101, 14, 9, 6), (45, 28, 11, 7), (135, 36, 8, 7), (140, 58, 13, 7),
    (122, 48, 10, 8), (113, -2, 10, 4), (138, 37, 4, 7), (104, 1, 4, 3),
    (134, -25, 13, 7), (172, -41, 3, 4),
]

# (num, lon, lat, dx, dy) -- pins 1-13, nudged where Europe crowds
PINS = [
    (1, 46.7, 24.6, 0, 0),
    (2, 30.7, 36.9, 0, 0),
    (3, -76.0, -10.9, 0, 0),
    (4, 30.5, 50.4, 7, -6),
    (5, 21.0, 52.2, -8, 5),
    (6, 8.65, 49.87, -10, 8),
    (7, 56.5, 26.5, 12, -10),
    (8, -77.0, 38.9, 0, 0),
    (9, 116.4, 39.9, 0, 0),
    (10, 125.6, 7.1, 0, 0),
    (11, 149.1, -35.3, 0, 0),
    (12, -30.0, 25.0, 0, 0),
    (13, 174.8, -41.3, 0, 0),
]


def draw_map(cv, x, y, w, h):
    mx0, my0 = x, y
    mw, mh = w, h
    lon0, lon1, lat0, lat1 = -170.0, 190.0, 75.0, -55.0

    def proj(lon, lat):
        px = mx0 + (lon - lon0) / (lon1 - lon0) * mw
        py = my0 + (lat0 - lat) / (lat0 - lat1) * mh
        return px, py

    lat = 72.0
    while lat >= -52.0:
        lon = -168.0
        while lon <= 188.0:
            inside = False
            for clon, clat, rx, ry in BLOBS:
                d = ((lon - clon) / rx) ** 2 + ((lat - clat) / ry) ** 2
                if d <= 1.0:
                    inside = True
                    break
            if inside:
                px, py = proj(lon, lat)
                cv.circle(int(px), int(py), 2, (47, 74, 107))
            lon += 3.2
        lat -= 3.2
    for num, lon, lat, dx, dy in PINS:
        px, py = proj(lon, lat)
        cx, cy = int(px) + dx, int(py) + dy
        cv.circle(cx, cy, 7, RED)
        cv.ring(cx, cy, 7, WHITE, 1)
        s = str(num)
        text(cv, cx - tw("sansB9", s) // 2, cy - 5, "sansB9", s, WHITE)


# ------------------------------------------------------------------- layout
def build():
    global ATLAS
    ATLAS = Atlas(BASE)
    cv = Canvas(W, H, PAPER)

    # kicker
    cv.rect(0, 0, W, 3, RED)
    text(cv, 8, 8, "sansB11", "THE WORLD IN ONE DAY", RED)
    right = "35 STORIES · 7 REGIONS · EVERY ONE DATED SATURDAY 21 NOVEMBER 2026"
    text(cv, W - 8 - tw("sans9", right), 9, "sans9", right, INK)
    cv.hline(8, W - 8, 26, LINE, 1)

    # masthead IS the date
    center(cv, W // 2, 30, "bodoni62", "Saturday 21 November 2026", INK)
    cv.hline(8, W - 8, 98, INK, 1)
    center(cv, W // 2, 104, "gel15",
           "COP31 talks run into overtime · missiles intercepted over Riyadh "
           "· a 6.7 quake shakes Peru", INK)

    # stat strip
    cell = 168
    for i, (val, label, col) in enumerate(STATS):
        cx = 8 + i * cell
        if i:
            cv.vline(cx - 4, 124, 166, LINE, 1)
        text(cv, cx, 124, "bask30", val, col)
        para(cv, cx, 158, "sans9", label, cell - 10, 2, GRAY, leading=11)
    cv.hline(8, W - 8, 172, LINE, 1)

    # region bar (widths proportional, sum = 35 stories)
    total = sum(n for _, n, _ in REGIONS)
    rx = 8
    for label, n, col in REGIONS:
        seg = int(round(1008 * n / total))
        cv.rect(rx, 176, seg, 16, col)
        text(cv, rx + (seg - tw("sansB9", label)) // 2, 179, "sansB9",
             label, WHITE)
        rx += seg

    # hero row: 3 cards, bold red banner + fact chip on every card
    illos = [illo_riyadh, illo_cop31, illo_peru]
    for i, hero in enumerate(HEROES):
        hero_card(cv, 8 + i * 338, 196, 330, 200, hero, illos[i])

    # secondary rows: 2 x 5, coloured value strip on every card
    for r in range(2):
        for c in range(5):
            sec = SECONDARY[r * 5 + c]
            secondary_card(cv, 8 + c * 203, 400 + r * 156, 196, 152, sec)

    # bottom: map left, story list right
    cv.rect(8, 712, 322, 256, CARD)
    cv.outline(8, 712, 322, 256, CARDBRD, 1)
    text(cv, 16, 718, "sansB11", "WHERE IT HAPPENED", NAVY)
    draw_map(cv, 14, 738, 310, 120)
    ly = 866
    for s in ["Pins 1-13 mark the pictured stories.",
              "6 BepiColombo is flown from Darmstadt."]:
        text(cv, 16, ly, "gel9", s, INK)
        ly += 13
    for label, desc in [("OFFICIAL", "official source"),
                        ("CONFIRMED", "several sources"),
                        ("REPORTED", "one claim, not yet confirmed")]:
        cv.rect(16, ly + 1, 10, 10, BADGE_COLOR[label])
        text(cv, 30, ly, "sansB9", label, INK)
        text(cv, 30 + tw("sansB9", label) + 6, ly, "gel9", desc, GRAY)
        ly += 14
    text(cv, 16, ly + 2, "gel9",
         "Map: schematic dotted grid, not to scale.", GRAY)

    cv.rect(338, 712, 678, 256, CARD)
    cv.outline(338, 712, 678, 256, CARDBRD, 1)
    text(cv, 348, 718, "sansB11",
         "ALSO ON SATURDAY 21 NOVEMBER 2026 — 22 MORE STORIES", NAVY)
    for i, item in enumerate(MORE):
        col = 0 if i < 11 else 1
        row = i % 11
        text(cv, 348 + col * 340, 740 + row * 21, "gel10", item, INK)

    # DATE CHECK: 19-20 Nov news lives ONLY here
    cv.rect(8, 976, 1008, 32, (255, 250, 244))
    cv.outline(8, 976, 1008, 32, RED, 2)
    text(cv, 16, 981, "sansB10", "DATE CHECK — ", RED)
    dx = 16 + tw("sansB10", "DATE CHECK — ")
    para(cv, dx, 981, "gel10", DATE_CHECK, 1008 - (dx - 8) - 8, 2, INK,
         leading=13)

    # footer
    center(cv, W // 2, 1012, "gel9",
           "Every story here happened, or was first reported, on Saturday "
           "21 November 2026. Sources named beside each story · Original "
           "drawings · Drawn in code", GRAY)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
