#!/usr/bin/env python3
"""news-image-20261121 v9 — one front page of Saturday 21 November 2026.

Stdlib only (math, os, struct, sys, zlib, json). No network, no PIL at
runtime. All type is blitted from atlas.png / atlas.json, a bitmap atlas
built at build time from the OFL TTFs in the workspace fonts directory
(see tools/build_atlas.py). All illustration is drawn in code.

Usage:
    python3 main.py [output.png]     # default: /output/entry.png
"""
import json
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024
BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)
INK = (20, 20, 20)
NAVY = (26, 42, 74)
RED = (179, 35, 42)
TEAL = (15, 118, 110)
OCHRE = (183, 121, 31)
GREEN = (46, 125, 50)
PURPLE = (107, 79, 161)
GREY = (107, 114, 128)
BLUE = (31, 78, 121)
DARKGREEN = (30, 107, 74)
LABELGREY = (85, 80, 63)
FOOTGREY = (110, 105, 90)
RULE = (201, 194, 178)
MAPBG = (215, 227, 232)
MAPLINE = (185, 201, 209)
TAN = (217, 192, 138)
SKY = (14, 26, 48)
WHITE = (255, 255, 255)
YELLOW = (255, 215, 106)

# ------------------------------------------------------------------- PNG
# Minimal PNG codec: decode 8-bit non-interlaced (grey, RGB, LA, RGBA),
# encode 8-bit RGB with Sub filtering. Deterministic.


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def png_decode(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    w = h = None
    ctype = None
    bitdepth = None
    idat = bytearray()
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, ctype, comp, filt, inter = struct.unpack(
                ">IIBBBBB", chunk)
            assert bitdepth == 8 and comp == 0 and filt == 0 and inter == 0
            assert ctype in (0, 2, 4, 6), "unsupported color type %d" % ctype
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(bytes(idat))
    stride = w * nch
    out = bytearray(w * h * nch)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        row = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(nch, stride):
                row[i] = (row[i] + row[i - nch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = row[i - nch] if i >= nch else 0
                row[i] = (row[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = row[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF
        out[y * stride:(y + 1) * stride] = row
        prev = row
    return w, h, ctype, bytes(out)


def _chunk(typ, payload):
    return (struct.pack(">I", len(payload)) + typ + payload +
            struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))


def png_encode_rgb(img, w, h):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(h):
        raw.append(1)  # Sub filter
        row = img[y * w * 3:(y + 1) * w * 3]
        raw.append(row[0])
        raw.append(row[1])
        raw.append(row[2])
        for i in range(3, len(row)):
            raw.append((row[i] - row[i - 3]) & 0xFF)
    comp = zlib.compress(bytes(raw), 9)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", comp) + _chunk(b"IEND", b""))


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _clip(self, x0, y0, x1, y1):
        x0 = max(0, min(self.w, x0))
        y0 = max(0, min(self.h, y0))
        x1 = max(0, min(self.w, x1))
        y1 = max(0, min(self.h, y1))
        return x0, y0, x1, y1

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def fill_rect(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = self._clip(x0, y0, x1, y1)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = c
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            n = (x1 - x0) * 3
            self.px[i:i + n] = bytes((r, g, b)) * (x1 - x0)

    def hline(self, x0, x1, y, c):
        self.fill_rect(x0, y, x1, y + 1, c)

    def vline(self, x, y0, y1, c):
        self.fill_rect(x, y0, x + 1, y1, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        if r <= 0:
            return
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    def ring(self, cx, cy, r, c, t=1):
        for k in range(t):
            rr = r - k
            for a in range(360):
                th = math.radians(a)
                self.set(int(cx + rr * math.cos(th)),
                         int(cy + rr * math.sin(th)), c)

    def ellipse(self, cx, cy, rx, ry, c):
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-ry, ry + 1):
            dx = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / float(ry * ry))))
            self.fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    def polygon(self, pts, c):
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, ya = pts[i]
                x1, yb = pts[(i + 1) % n]
                if (ya <= y < yb) or (yb <= y < ya):
                    t = (y - ya) / float(yb - ya)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)

    def polyline(self, pts, c):
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], c)

    def rrect(self, x0, y0, x1, y1, r, c):
        r = max(1, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
        self.fill_rect(x0 + r, y0, x1 - r, y1, c)
        self.fill_rect(x0, y0 + r, x1, y1 - r, c)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r - 1, y0 + r),
                       (x0 + r, y1 - r - 1), (x1 - r - 1, y1 - r - 1)):
            self.circle(cx, cy, r, c)

    def star(self, cx, cy, ro, ri, c, rot=-90.0):
        pts = []
        for i in range(10):
            ang = math.radians(rot + i * 36.0)
            rr = ro if i % 2 == 0 else ri
            pts.append((int(cx + rr * math.cos(ang)),
                        int(cy + rr * math.sin(ang))))
        self.polygon(pts, c)

    def burst(self, cx, cy, r, c):
        self.circle(cx, cy, 2, WHITE)
        for a in range(0, 360, 30):
            th = math.radians(a)
            self.line(cx, cy, int(cx + r * math.cos(th)),
                      int(cy + r * math.sin(th)), c)
        self.circle(cx, cy, 3, c)

    def quad_dots(self, p0, p1, p2, c, step=7):
        """Dotted quadratic bezier: dots every `step` px of arc length."""
        pts = []
        n = 120
        for i in range(n + 1):
            t = i / float(n)
            x = (1 - t) * (1 - t) * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
            y = (1 - t) * (1 - t) * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
            pts.append((x, y))
        dist = 0.0
        last = pts[0]
        self.circle(int(pts[0][0]), int(pts[0][1]), 1, c)
        for p in pts[1:]:
            dist += math.hypot(p[0] - last[0], p[1] - last[1])
            last = p
            if dist >= step:
                dist = 0.0
                self.circle(int(p[0]), int(p[1]), 1, c)

# -------------------------------------------------------------------- type
class Atlas:
    def __init__(self, base):
        with open(os.path.join(base, "atlas.json")) as fh:
            meta = json.load(fh)
        self.specs = meta["specs"]
        self.glyphs = meta["glyphs"]
        with open(os.path.join(base, "atlas.png"), "rb") as fh:
            w, h, ctype, raw = png_decode(fh.read())
        assert ctype == 4, "atlas must be LA"
        self.aw = w
        self.alpha = raw  # 2 bytes/px: L, A

    def width(self, spec, s, tracking=0):
        g = self.glyphs[spec]
        tot = 0
        for ch in s:
            cell = g.get(ch)
            tot += (cell[4] if cell else 0) + tracking
        return tot - tracking if s else 0

    def draw(self, cv, spec, x, y_base, s, color, tracking=0):
        g = self.glyphs[spec]
        r0, g0, b0 = color
        for ch in s:
            cell = g.get(ch)
            if cell is None:
                continue
            gx, gy, gw, gh, adv, bx, by = cell
            if gw and gh:
                ox = x + bx
                oy = y_base + by
                for row in range(gh):
                    yy = oy + row
                    if yy < 0 or yy >= cv.h:
                        continue
                    base = ((gy + row) * self.aw + gx) * 2 + 1
                    for col in range(gw):
                        a = self.alpha[base + col * 2]
                        if not a:
                            continue
                        xx = ox + col
                        if xx < 0 or xx >= cv.w:
                            continue
                        i = (yy * cv.w + xx) * 3
                        if a == 255:
                            cv.px[i] = r0
                            cv.px[i + 1] = g0
                            cv.px[i + 2] = b0
                        else:
                            cv.px[i] = (r0 * a + cv.px[i] * (255 - a)) // 255
                            cv.px[i + 1] = (g0 * a + cv.px[i + 1] * (255 - a)) // 255
                            cv.px[i + 2] = (b0 * a + cv.px[i + 2] * (255 - a)) // 255
            x += adv + tracking
        return x

    def wrap(self, spec, s, width):
        """Greedy word wrap; returns list of lines."""
        words = s.split(" ")
        lines = []
        cur = ""
        for wd in words:
            trial = wd if not cur else cur + " " + wd
            if self.width(spec, trial) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines


def draw_centered(at, cv, spec, cx, y_base, s, color):
    at.draw(cv, spec, cx - at.width(spec, s) // 2, y_base, s, color)


def draw_right(at, cv, spec, x_right, y_base, s, color):
    at.draw(cv, spec, x_right - at.width(spec, s), y_base, s, color)


# -------------------------------------------------------------------- data
# Every story happened, or was first reported, on Saturday 21 November
# 2026. News from 19-20 November appears ONLY in the DATE CHECK box.
STATS = [
    ("DAY 13", RED, ["of COP31, meant to close", "on day 12"]),
    ("5", RED, ["missiles shot down over", "Riyadh and Jizan"]),
    ("6.7", NAVY, ["magnitude of the Peru quake"]),
    ("146", NAVY, ["people safe after the", "Davao landing"]),
    ("$58,983", NAVY, ["bitcoin early Saturday,", "down 3.9% in a day"]),
    ("124*", NAVY, ["K L Rahul's score at tea", "in Wellington"]),
]

REGIONS = [
    ("EUROPE 4", BLUE, 4),
    ("ASIA 9", RED, 9),
    ("MIDDLE EAST 3", OCHRE, 3),
    ("AFRICA 3", DARKGREEN, 3),
    ("AMERICAS 11", PURPLE, 11),
    ("OCEANIA 3", TEAL, 3),
    ("GLOBAL 3", GREY, 3),
]

HEROES = [
    dict(banner="RIYADH: MISSILES",
         dateline="RIYADH · SAUDI ARABIA — CONFLICT",
         headline="Five missiles shot down over Riyadh and Jizan",
         deck=("The Saudi-led coalition said three were destroyed over "
               "Riyadh before dawn and two over Jizan, a day after it "
               "bombed Hodeidah port."),
         source="AFP · Dawn", badge="CONFIRMED",
         chip="5 shot down · 3 Riyadh + 2 Jizan"),
    dict(banner="COP31: OVERTIME",
         dateline="ANTALYA · TÜRKIYE — CLIMATE",
         headline="Climate summit runs into overtime with no deal",
         deck=("Talks pass Friday's deadline with no agreement; a third "
               "draft is due Saturday morning."),
         source="AP · AFP · Al Jazeera", badge="OFFICIAL",
         chip="No deal · day 13"),
    dict(banner="PERU: QUAKE 6.7",
         dateline="CARHUAMAYO · PERU — EARTHQUAKE",
         headline="Magnitude 6.7 earthquake rattles central Peru",
         deck=("A deep tremor struck near Carhuamayo just after midnight "
               "UTC. Peru's institute reported no deaths, no tsunami risk."),
         source="USGS · IGP", badge="OFFICIAL",
         chip="00:09 UTC · 108 km deep"),
]

# strip, dateline, headline, deck, source, badge, flag ("UA"/"PL"/"US"/"CN"
# drawn; anything else is a 2-letter code chip), region (for the map pin)
SECONDARY = [
    ("12 KILLED", "KYIV · WAR", "Russian strikes kill 12 in Ukraine",
     "Two dead, 42 injured in the Kryvyi Rih double strike; the toll was "
     "confirmed on Saturday.", "Kyiv Post · AP", "CONFIRMED", "UA"),
    ("RUTTE VISITS", "WARSAW · NATO", "Rutte flies to Warsaw for NATO talks",
     "NATO chief visits on Saturday; Warsaw asks for more Eastern Sentry "
     "forces.", "AP", "OFFICIAL", "PL"),
    ("19:24 CET", "MERCURY · SPACE", "BepiColombo burns for Mercury",
     "Thrusters fire at 19:24 CET tonight.", "ESA", "OFFICIAL", "ESA"),
    ("DRONE DOWNED", "HORMUZ · WAR", "Iran says it downed a US drone",
     "Tehran claims the shootdown; Washington has not confirmed it.",
     "IRIB", "REPORTED", "IR"),
    ("DATA-CENTRE TAX", "WASHINGTON · TECHNOLOGY",
     "Trump vows tax on data centres abroad",
     "'Tremendous' penalty promised; no details yet.", "ABC", "REPORTED", "US"),
    ("TAIWAN ROW", "BEIJING · DIPLOMACY",
     "China tells Japan to 'correct' Taiwan words",
     "Tokyo says its stance is unchanged.", "Ministry · AFP", "REPORTED", "CN"),
    ("146 SAFE", "DAVAO · AVIATION",
     "Jet lands safely after engine fire alert",
     "Air Niugini 767 diverts after midnight; all 146 on board safe.",
     "Airline · AP", "CONFIRMED", "PH"),
    ("AI TALKS", "CANBERRA · DIPLOMACY", "Australia and China agree AI talks",
     "Albanese ends an 11-day trip.", "ABC", "OFFICIAL", "AU"),
    ("$58,983", "WORLD · MARKETS", "Bitcoin slips below $59,000",
     "Down 3.9% in 24 hours; ether $1,625.", "CoinGecko", "CONFIRMED", "BTC"),
    ("124*", "WELLINGTON · CRICKET", "Rahul century puts India on top",
     "India 344 for 2 at tea, replying to 368.", "AFP", "CONFIRMED", "NZ"),
]

LIST_ITEMS = [
    "Copenhagen: Russian attaché expelled (Al Jazeera)",
    "Antalya: EU warns COP31 risks a “fossil summit” (AFP)",
    "Antalya: Panama threatens to block climate text (Al Jazeera)",
    "Antalya: Indonesia PLN signs clean-power deals (Antara)",
    "Yemen: Houthis threaten Jeddah and Red Sea ports (Al Jazeera)",
    "Washington: Vance — Iran strikes were Trump’s call (Reuters)",
    "Washington: Lawmaker threatens SpaceX’s funding (CNN)",
    "Texas: Execution of man of 70 takes 63 minutes (ABC)",
    "Los Angeles: Jury convicts man of starting Palisades fire (ABC)",
    "Missouri: Judge approves $7.25bn Roundup settlement (AFP)",
    "Vancouver: Canada rests defence in youth climate trial (AFP)",
    "Pyongyang: Kim tours factories after no Trump meeting (AFP)",
    "Bayelsa: Funeral boat capsizes, 4 dead (AFP/Al Jazeera)",
    "Taipei: Budget and cash payout are passed (Taipei Times)",
    "Bangkok: Six-point plan on arsenic in two rivers (The Nation)",
    "New Delhi: Pakistani minister joins SCO forum in India (Dawn)",
    "Eastern India: Rain alerts as Akvan’s remnant moves inland (ETV)",
    "Myanmar: Rights groups urge sanctions after court ruling (AP)",
    "Port Louis: African rating agency talks to 15 states (Al Jazeera)",
    "Melbourne: Cummins keeps the Australian captaincy (ABC)",
    "Las Vegas: Verstappen sent to stewards after contact (Autosport)",
    "Las Vegas: Russell fastest in final practice, 1:34.041 (F1)",
    "Johannesburg: ANC wins 31%, worst since 1994 (BBC)",
]

DATE_CHECK = (
    "Left out as Friday 20 November’s news: Wall Street’s correction · "
    "the barrage that hit Kyiv’s bridges · the missile that landed in "
    "Poland · the UK–EU deal · Cyclone Akvan’s landfall · Gaza strikes "
    "that killed six. Older: the Shenzhen summit and the ICJ Myanmar "
    "ruling (19 November) · Voyager 1’s light-day (18 November). Not "
    "confirmed when drawn: a final COP31 text.")

BADGE_COLOR = {"OFFICIAL": NAVY, "CONFIRMED": TEAL, "REPORTED": RED}
STRIP_COLOR = [RED, NAVY, TEAL, RED, NAVY, RED, TEAL, NAVY, OCHRE, GREEN]

# ------------------------------------------------------------- mini flags
def draw_flag(cv, code, x, y):
    """30x18 flag, drawn only where the design is simple and certain."""
    if code == "UA":
        cv.fill_rect(x, y, x + 30, y + 9, (0, 87, 183))
        cv.fill_rect(x, y + 9, x + 30, y + 18, (255, 215, 0))
    elif code == "PL":
        cv.fill_rect(x, y, x + 30, y + 9, WHITE)
        cv.fill_rect(x, y + 9, x + 30, y + 18, (220, 20, 60))
    elif code == "US":
        for i in range(7):
            col = (178, 34, 52) if i % 2 == 0 else WHITE
            cv.fill_rect(x, y + i * 2, x + 30, y + i * 2 + 3, col)
        cv.fill_rect(x, y, x + 12, y + 10, (60, 59, 110))
        for dx in (3, 7):
            for dy in (3, 7):
                cv.set(x + dx, y + dy, WHITE)
    elif code == "CN":
        cv.fill_rect(x, y, x + 30, y + 18, (222, 41, 16))
        cv.star(x + 8, y + 9, 5, 2, (255, 222, 0))
        for sx, sy in ((18, 4), (23, 7), (23, 12), (18, 15)):
            cv.star(sx, sy, 2, 1, (255, 222, 0))
    cv.fill_rect(x, y, x + 30, y + 1, (0, 0, 0))
    cv.fill_rect(x, y + 17, x + 30, y + 18, (0, 0, 0))
    cv.fill_rect(x, y, x + 1, y + 18, (0, 0, 0))
    cv.fill_rect(x + 29, y, x + 30, y + 18, (0, 0, 0))


def code_chip(at, cv, code, x, y):
    cv.rrect(x, y, x + 30, y + 16, 3, NAVY)
    draw_centered(at, cv, "sans8b", x + 15, y + 12, code, WHITE)


def badge_pill(at, cv, badge, x, y, white_bg=True):
    w = at.width("sans8b", badge) + 12
    if white_bg:
        cv.rrect(x, y, x + w, y + 14, 3, WHITE)
        draw_centered(at, cv, "sans8b", x + w // 2, y + 11, badge,
                      BADGE_COLOR[badge])
    else:
        cv.rrect(x, y, x + w, y + 14, 3, BADGE_COLOR[badge])
        draw_centered(at, cv, "sans8b", x + w // 2, y + 11, badge, WHITE)
    return w


def chip_text(at, cv, text, x, y):
    w = at.width("sans9b", text) + 14
    cv.rrect(x, y, x + w, y + 16, 3, WHITE)
    draw_centered(at, cv, "sans9b", x + w // 2, y + 12, text, NAVY)
    return w


# ------------------------------------------------------- hero illustrations
def hero_riyadh(at, cv, x0, y0):
    cv.fill_rect(x0, y0, x0 + 330, y0 + 84, SKY)
    for sx, sy in ((30, 10), (120, 6), (200, 12), (300, 8), (90, 16), (260, 22)):
        cv.set(x0 + sx, y0 + sy, (200, 210, 235))
    cv.polygon([(x0 + 70, y0 + 84), (x0 + 86, y0 + 84), (x0 + 56, y0 + 8),
                (x0 + 40, y0 + 8)], (28, 51, 85))
    cv.polygon([(x0 + 250, y0 + 84), (x0 + 264, y0 + 84), (x0 + 290, y0 + 8),
                (x0 + 276, y0 + 8)], (28, 51, 85))
    cv.circle(x0 + 252, y0 + 16, 9, (245, 230, 184))
    cv.circle(x0 + 256, y0 + 13, 8, SKY)
    towers = [(10, 26, 58), (40, 24, 70), (68, 28, 48), (100, 22, 64),
              (126, 26, 52), (156, 24, 44)]
    for dx, tw, th in towers:
        cv.fill_rect(x0 + dx, y0 + 84 - th, x0 + dx + tw, y0 + 84, (6, 13, 26))
        for wy in range(y0 + 84 - th + 6, y0 + 80, 9):
            for wx in range(x0 + dx + 4, x0 + dx + tw - 3, 7):
                cv.fill_rect(wx, wy, wx + 3, wy + 4, YELLOW)
    cv.polygon([(x0 + 40, y0 + 14), (x0 + 52, y0 + 4), (x0 + 64, y0 + 14)],
               (6, 13, 26))
    for dx, tw, th in ((212, 24, 38), (240, 22, 48), (266, 26, 34)):
        cv.fill_rect(x0 + dx, y0 + 84 - th, x0 + dx + tw, y0 + 84, (6, 13, 26))
        for wy in range(y0 + 84 - th + 6, y0 + 80, 9):
            for wx in range(x0 + dx + 4, x0 + dx + tw - 3, 7):
                cv.fill_rect(wx, wy, wx + 3, wy + 4, YELLOW)
    arcs = [((30, 6), (55, 16), (70, 38)), ((80, 4), (105, 14), (120, 30)),
            ((130, 8), (150, 18), (162, 42)), ((215, 6), (235, 16), (248, 34)),
            ((270, 8), (288, 18), (298, 40))]
    for p0, p1, p2 in arcs:
        cv.quad_dots((x0 + p0[0], y0 + p0[1]), (x0 + p1[0], y0 + p1[1]),
                     (x0 + p2[0], y0 + p2[1]), YELLOW)
        cv.burst(x0 + p2[0], y0 + p2[1], 8, YELLOW)
    chip_text(at, cv, "5 shot down · 3 Riyadh + 2 Jizan", x0 + 6, y0 + 62)
    badge_pill(at, cv, "CONFIRMED", x0 + 330 - 62, y0 + 6)


def hero_cop(at, cv, x0, y0):
    cv.fill_rect(x0, y0, x0 + 330, y0 + 84, (220, 239, 232))
    cv.polygon([(x0, y0 + 84), (x0, y0 + 70), (x0 + 60, y0 + 76),
                (x0 + 120, y0 + 68), (x0 + 180, y0 + 78), (x0 + 240, y0 + 70),
                (x0 + 330, y0 + 76), (x0 + 330, y0 + 84)], (88, 160, 110))
    cv.circle(x0 + 52, y0 + 44, 30, (47, 127, 193))
    cv.ellipse(x0 + 40, y0 + 32, 12, 8, (88, 160, 92))
    cv.ellipse(x0 + 64, y0 + 56, 10, 7, (88, 160, 92))
    cv.ellipse(x0 + 50, y0 + 58, 6, 4, (88, 160, 92))
    cv.ring(x0 + 52, y0 + 44, 30, (30, 90, 150))
    tx = x0 + 128
    cv.rrect(tx, y0 + 12, tx + 14, y0 + 64, 6, WHITE)
    cv.fill_rect(tx + 4, y0 + 34, tx + 10, y0 + 60, RED)
    cv.circle(tx + 7, y0 + 62, 11, WHITE)
    cv.circle(tx + 7, y0 + 62, 9, RED)
    at.draw(cv, "sans9b", tx + 22, y0 + 30, "+1.5°C", RED)
    at.draw(cv, "sans8b", tx + 22, y0 + 42, "LIMIT", INK)
    cv.circle(x0 + 232, y0 + 38, 22, WHITE)
    cv.ring(x0 + 232, y0 + 38, 22, INK, 2)
    cv.line(x0 + 232, y0 + 38, x0 + 232, y0 + 22, INK)
    cv.line(x0 + 232, y0 + 38, x0 + 244, y0 + 46, INK)
    cv.circle(x0 + 232, y0 + 38, 2, INK)
    draw_centered(at, cv, "sans9b", x0 + 232, y0 + 72, "DAY 13", NAVY)
    for i, col in enumerate((TEAL, RED, OCHRE)):
        px = x0 + 272 + i * 16
        cv.vline(px, y0 + 56, y0 + 78, INK)
        cv.fill_rect(px, y0 + 56, px + 12, y0 + 64, col)
    chip_text(at, cv, "No deal · day 13", x0 + 6, y0 + 62)
    badge_pill(at, cv, "OFFICIAL", x0 + 330 - 62, y0 + 6)


def hero_peru(at, cv, x0, y0):
    cv.fill_rect(x0, y0, x0 + 330, y0 + 84, (239, 227, 200))
    cv.polygon([(x0, y0 + 84), (x0 + 40, y0 + 40), (x0 + 90, y0 + 58),
                (x0 + 140, y0 + 34), (x0 + 200, y0 + 60), (x0 + 260, y0 + 42),
                (x0 + 330, y0 + 66), (x0 + 330, y0 + 84)], (176, 154, 122))
    cv.polygon([(x0, y0 + 84), (x0 + 60, y0 + 58), (x0 + 130, y0 + 72),
                (x0 + 210, y0 + 52), (x0 + 280, y0 + 70), (x0 + 330, y0 + 60),
                (x0 + 330, y0 + 84)], (138, 111, 77))
    cv.fill_rect(x0 + 10, y0 + 14, x0 + 320, y0 + 44, WHITE)
    trace = [(12, 29), (30, 29), (38, 18), (46, 40), (54, 29), (70, 29),
             (78, 22), (86, 36), (94, 29), (120, 29), (128, 16), (136, 42),
             (144, 29), (170, 29), (178, 24), (186, 34), (194, 29),
             (230, 29), (238, 20), (246, 38), (254, 29), (280, 29),
             (288, 26), (296, 32), (304, 29), (318, 29)]
    cv.polyline([(x0 + a, y0 + b) for a, b in trace], RED)
    for hx in (30, 150, 255):
        cv.fill_rect(x0 + hx, y0 + 68, x0 + hx + 26, y0 + 84, WHITE)
        cv.polygon([(x0 + hx - 3, y0 + 68), (x0 + hx + 13, y0 + 56),
                    (x0 + hx + 29, y0 + 68)], RED)
        cv.fill_rect(x0 + hx + 11, y0 + 76, x0 + hx + 15, y0 + 84, (60, 45, 30))
    cv.polyline([(x0 + 100, y0 + 84), (x0 + 110, y0 + 76), (x0 + 118, y0 + 84)],
                (90, 70, 50))
    cv.polyline([(x0 + 210, y0 + 84), (x0 + 218, y0 + 78), (x0 + 226, y0 + 84)],
                (90, 70, 50))
    cv.circle(x0 + 215, y0 + 14, 14, WHITE)
    cv.ring(x0 + 215, y0 + 14, 14, RED, 2)
    draw_centered(at, cv, "sans12b", x0 + 215, y0 + 19, "6.7", RED)
    chip_text(at, cv, "00:09 UTC · 108 km deep", x0 + 6, y0 + 62)
    badge_pill(at, cv, "OFFICIAL", x0 + 330 - 62, y0 + 6)


HERO_DRAW = (hero_riyadh, hero_cop, hero_peru)


# ------------------------------------------------- secondary illustrations
def sec_art(at, cv, idx, x0, y0):
    w, h = 195, 48
    if idx == 0:  # Kyiv night
        cv.fill_rect(x0, y0, x0 + w, y0 + h, SKY)
        for bx, bw, bh in ((8, 20, 18), (32, 16, 26), (52, 24, 20),
                           (80, 18, 28), (102, 20, 22), (126, 16, 30),
                           (146, 22, 18), (172, 18, 24)):
            cv.fill_rect(x0 + bx, y0 + h - bh, x0 + bx + bw, y0 + h,
                         (6, 13, 26))
            for wy in range(y0 + h - bh + 4, y0 + h - 2, 8):
                for wx in range(x0 + bx + 3, x0 + bx + bw - 2, 7):
                    cv.fill_rect(wx, wy, wx + 2, wy + 3, YELLOW)
        cv.burst(x0 + 160, y0 + 12, 9, (255, 140, 26))
    elif idx == 1:  # Warsaw parliament
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (223, 227, 230))
        cv.polygon([(x0 + 50, y0 + 14), (x0 + 97, y0 + 2), (x0 + 145, y0 + 14)],
                   (150, 150, 150))
        cv.fill_rect(x0 + 55, y0 + 14, x0 + 140, y0 + 48, (120, 125, 130))
        for cx in range(x0 + 62, x0 + 138, 15):
            cv.fill_rect(cx, y0 + 18, cx + 6, y0 + 48, (235, 235, 235))
        cv.fill_rect(x0 + 48, y0 + 44, x0 + 147, y0 + 48, (100, 105, 110))
    elif idx == 2:  # Mercury
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (11, 16, 32))
        for sx, sy in ((90, 8), (150, 14), (180, 6), (120, 40), (170, 40)):
            cv.set(x0 + sx, y0 + sy, (220, 225, 240))
        cv.circle(x0 + 40, y0 + 24, 14, (184, 168, 138))
        for cx, cy, r in ((34, 20, 2), (46, 28, 3), (38, 32, 2)):
            cv.circle(x0 + cx, y0 + cy, r, (150, 135, 110))
        cv.fill_rect(x0 + 120, y0 + 18, x0 + 140, y0 + 28, WHITE)
        cv.fill_rect(x0 + 128, y0 + 14, x0 + 132, y0 + 18, (242, 201, 76))
        cv.polygon([(x0 + 140, y0 + 20), (x0 + 152, y0 + 23),
                    (x0 + 140, y0 + 26)], (255, 140, 26))
    elif idx == 3:  # Hormuz
        cv.fill_rect(x0, y0, x0 + w, y0 + 28, (127, 179, 213))
        cv.fill_rect(x0, y0 + 28, x0 + w, y0 + h, (47, 109, 163))
        cv.circle(x0 + 25, y0 + 12, 7, (245, 230, 180))
        cv.polygon([(x0 + 60, y0 + 30), (x0 + 140, y0 + 30),
                    (x0 + 130, y0 + 40), (x0 + 70, y0 + 40)], (30, 40, 60))
        cv.fill_rect(x0 + 95, y0 + 20, x0 + 115, y0 + 30, WHITE)
        cv.fill_rect(x0 + 158, y0 + 8, x0 + 166, y0 + 12, (90, 95, 100))
        cv.line(x0 + 154, y0 + 10, x0 + 170, y0 + 10, (90, 95, 100))
    elif idx == 4:  # Washington capitol
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (22, 35, 63))
        for sx, sy in ((20, 8), (170, 10), (150, 6)):
            cv.set(x0 + sx, y0 + sy, (220, 225, 240))
        cv.ellipse(x0 + 97, y0 + 36, 30, 16, WHITE)
        cv.fill_rect(x0 + 60, y0 + 36, x0 + 134, y0 + 48, WHITE)
        cv.fill_rect(x0 + 96, y0 + 16, x0 + 98, y0 + 22, WHITE)
        cv.circle(x0 + 97, y0 + 15, 2, WHITE)
        cv.fill_rect(x0 + 52, y0 + 44, x0 + 142, y0 + 48, (200, 200, 200))
    elif idx == 5:  # Beijing wall
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (176, 58, 46))
        cv.polygon([(x0, y0 + 48), (x0, y0 + 36), (x0 + 30, y0 + 36),
                    (x0 + 30, y0 + 30), (x0 + 60, y0 + 30), (x0 + 60, y0 + 36),
                    (x0 + 120, y0 + 36), (x0 + 120, y0 + 28),
                    (x0 + 150, y0 + 28), (x0 + 150, y0 + 36),
                    (x0 + 195, y0 + 36), (x0 + 195, y0 + 48)], (90, 50, 35))
        for tx in (55, 130):
            cv.fill_rect(x0 + tx, y0 + 18, x0 + tx + 14, y0 + 30, (90, 50, 35))
            cv.polygon([(x0 + tx - 2, y0 + 18), (x0 + tx + 7, y0 + 12),
                        (x0 + tx + 16, y0 + 18)], (70, 38, 26))
    elif idx == 6:  # Davao plane
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (168, 200, 224))
        cv.ellipse(x0 + 30, y0 + 12, 14, 5, WHITE)
        cv.ellipse(x0 + 150, y0 + 10, 16, 6, WHITE)
        cv.ellipse(x0 + 120, y0 + 38, 14, 5, WHITE)
        cv.ellipse(x0 + 97, y0 + 24, 42, 7, WHITE)
        cv.polygon([(x0 + 85, y0 + 24), (x0 + 110, y0 + 36),
                    (x0 + 118, y0 + 36), (x0 + 100, y0 + 24)], WHITE)
        cv.polygon([(x0 + 55, y0 + 22), (x0 + 48, y0 + 12),
                    (x0 + 56, y0 + 12), (x0 + 62, y0 + 22)], WHITE)
        for wx in (80, 92, 104):
            cv.set(x0 + wx, y0 + 23, NAVY)
    elif idx == 7:  # Canberra
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (232, 226, 208))
        cv.fill_rect(x0, y0 + 44, x0 + w, y0 + h, (110, 170, 100))
        cv.polygon([(x0 + 54, y0 + 16), (x0 + 98, y0 + 4), (x0 + 142, y0 + 16)],
                   (165, 170, 175))
        cv.fill_rect(x0 + 58, y0 + 16, x0 + 138, y0 + 44, (140, 145, 150))
        for cx in range(x0 + 66, x0 + 134, 14):
            cv.fill_rect(cx, y0 + 20, cx + 5, y0 + 44, (215, 215, 215))
    elif idx == 8:  # Markets
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (26, 26, 46))
        cv.polyline([(x0 + 60, y0 + 10), (x0 + 85, y0 + 16), (x0 + 110, y0 + 12),
                     (x0 + 135, y0 + 26), (x0 + 160, y0 + 22),
                     (x0 + 185, y0 + 38)], RED)
        for px, py in ((60, 10), (85, 16), (110, 12), (135, 26), (160, 22),
                       (185, 38)):
            cv.circle(x0 + px, y0 + py, 2, (255, 120, 110))
        cv.circle(x0 + 28, y0 + 30, 12, (242, 201, 76))
        cv.ring(x0 + 28, y0 + 30, 12, (180, 140, 40))
        draw_centered(at, cv, "sans12b", x0 + 28, y0 + 35, "B",
                      (122, 92, 0))
    elif idx == 9:  # Wellington cricket
        cv.fill_rect(x0, y0, x0 + w, y0 + h, (61, 139, 64))
        cv.fill_rect(x0 + 70, y0 + 20, x0 + 125, y0 + 48, (210, 190, 150))
        for sx in (92, 98, 104):
            cv.fill_rect(x0 + sx, y0 + 24, x0 + sx + 3, y0 + 38, (255, 215, 0))
        cv.fill_rect(x0 + 92, y0 + 22, x0 + 107, y0 + 24, (255, 215, 0))
        cv.circle(x0 + 150, y0 + 14, 5, RED)
        cv.polygon([(x0 + 118, y0 + 30), (x0 + 126, y0 + 44),
                    (x0 + 130, y0 + 42), (x0 + 124, y0 + 28)], (150, 110, 60))


# ---------------------------------------------------------------------- map
CONTINENTS = [
    [(-168, 66), (-145, 70), (-130, 71), (-115, 73), (-100, 73), (-90, 74),
     (-82, 70), (-76, 71), (-68, 64), (-60, 55), (-55, 47), (-65, 44),
     (-70, 42), (-75, 36), (-76, 32), (-80, 26), (-84, 28), (-90, 21),
     (-95, 18), (-100, 16), (-105, 19), (-110, 22), (-114, 27), (-118, 32),
     (-122, 37), (-124, 42), (-125, 48), (-130, 55), (-140, 60),
     (-152, 58), (-162, 58), (-168, 66)],
    [(-55, 60), (-45, 60), (-38, 64), (-30, 68), (-22, 70), (-25, 76),
     (-35, 80), (-50, 79), (-56, 74), (-55, 60)],
    [(-79, 9), (-72, 11), (-64, 10), (-58, 7), (-52, 4), (-50, 0),
     (-44, -3), (-38, -5), (-36, -9), (-39, -14), (-41, -21), (-47, -26),
     (-52, -32), (-58, -38), (-64, -41), (-68, -50), (-70, -54),
     (-73, -50), (-73, -41), (-72, -31), (-71, -22), (-70, -18),
     (-76, -12), (-80, -6), (-80, 0), (-79, 9)],
    [(-10, 36), (-9, 43), (-3, 48), (-5, 50), (-1, 51), (2, 53), (7, 55),
     (8, 57), (12, 56), (18, 56), (21, 55), (23, 58), (27, 59), (30, 62),
     (28, 65), (24, 68), (20, 70), (14, 69), (10, 66), (6, 61), (3, 58),
     (-2, 57), (-6, 54), (-10, 51), (-10, 46), (-10, 40), (-10, 36)],
    [(-5, 50), (-3, 53), (-6, 56), (-3, 58), (-1, 57), (0, 52), (-4, 50)],
    [(-17, 15), (-16, 21), (-11, 28), (-6, 33), (0, 36), (9, 37), (11, 34),
     (19, 32), (25, 32), (30, 31), (32, 31), (34, 28), (37, 23), (39, 19),
     (43, 12), (48, 11), (51, 10), (46, 5), (41, -2), (40, -7), (38, -12),
     (36, -18), (34, -24), (32, -28), (29, -32), (25, -34), (20, -35),
     (17, -31), (14, -24), (12, -17), (10, -10), (9, -2), (9, 3), (5, 5),
     (-3, 5), (-8, 5), (-13, 8), (-17, 15)],
    [(30, 62), (35, 66), (42, 68), (50, 69), (60, 69), (70, 72), (80, 73),
     (90, 75), (100, 76), (112, 74), (125, 72), (140, 72), (155, 70),
     (162, 66), (170, 66), (178, 65), (170, 61), (162, 56), (158, 52),
     (152, 46), (145, 42), (142, 39), (139, 35), (135, 33), (130, 32),
     (127, 34), (124, 38), (121, 35), (120, 30), (117, 24), (111, 21),
     (108, 18), (105, 10), (102, 8), (99, 10), (97, 15), (94, 17), (92, 21),
     (89, 22), (86, 20), (82, 17), (79, 13), (77, 8), (75, 11), (73, 17),
     (70, 21), (67, 24), (63, 25), (59, 26), (56, 26), (53, 27), (50, 29),
     (48, 30), (45, 29), (42, 30), (39, 31), (36, 36), (34, 36), (31, 36),
     (28, 39), (27, 41), (26, 40), (28, 44), (30, 46), (32, 50), (35, 54),
     (33, 58), (30, 60), (30, 62)],
    [(113, -22), (114, -30), (115, -34), (120, -34), (126, -32), (130, -32),
     (135, -35), (140, -38), (145, -38), (150, -37), (153, -33),
     (153, -27), (150, -23), (146, -19), (142, -15), (142, -11),
     (137, -12), (135, -15), (132, -12), (129, -13), (126, -14),
     (122, -17), (118, -20), (113, -22)],
    [(130, 31), (132, 33), (135, 34), (137, 35), (139, 37), (140, 39),
     (141, 41), (142, 44), (143, 43), (141, 40), (140, 37), (138, 35),
     (136, 33), (133, 32), (130, 31)],
    [(167, -45), (170, -42), (173, -40), (176, -38), (178, -37),
     (175, -40), (172, -42), (169, -44), (167, -45)],
]

# (number, lon, lat, dx, dy) — dx/dy nudge the drawn pin off its true spot
# where the Europe / Gulf clusters would collide.
PINS = [
    (1, 47.0, 24.6, 0, 0), (2, 30.7, 36.9, 0, 8), (3, -75.8, -11.0, 0, 0),
    (4, 30.5, 50.4, 8, 2), (5, 21.0, 52.2, -6, -6), (6, 8.6, 49.9, -10, 10),
    (7, 56.5, 27.0, 13, 11), (8, -77.0, 38.9, 0, 0), (9, 116.4, 39.9, 0, 0),
    (10, 125.6, 7.1, 0, 0), (11, 149.1, -35.3, 0, 0),
    (12, -25.0, -15.0, 0, 0), (13, 174.8, -41.3, 0, 0),
]

MAP_X, MAP_Y, MAP_W, MAP_H = 14, 774, 310, 134


def project(lon, lat):
    return (MAP_X + (lon + 170.0) / 360.0 * MAP_W,
            MAP_Y + (75.0 - lat) / 130.0 * MAP_H)

# -------------------------------------------------------------------- layout
def draw_header(at, cv):
    cv.fill_rect(0, 0, W, 3, RED)
    at.draw(cv, "sans13b", 8, 19, "THE WORLD IN ONE DAY", RED)
    draw_right(at, cv, "sans10b", 1016, 19,
               "36 STORIES · 7 REGIONS · EVERY ONE DATED "
               "SATURDAY 21 NOVEMBER 2026", INK)
    cv.hline(8, 1016, 25, INK)
    at.draw(cv, "bodoni62", 8, 88, "Saturday 21 November 2026", INK)
    cv.hline(8, 1016, 95, INK)
    draw_centered(at, cv, "gel15", 512, 113,
                  "COP31 talks run into overtime · five missiles shot down "
                  "over Riyadh and Jizan · a 6.7 quake shakes Peru", INK)


def draw_stats(at, cv):
    for i, (num, col, labels) in enumerate(STATS):
        cx = 8 + i * 168
        if i:
            cv.vline(cx, 122, 164, RULE)
        at.draw(cv, "sans30b", cx + 2, 146, num, col)
        for j, lab in enumerate(labels):
            at.draw(cv, "sans9", cx + 2, 157 + j * 10, lab, LABELGREY)


def draw_regions(at, cv):
    total = sum(n for _, _, n in REGIONS)
    unit = 1008.0 / total
    x = 8
    for label, col, n in REGIONS:
        w = int(round(n * unit))
        cv.fill_rect(x, 172, x + w, 188, col)
        draw_centered(at, cv, "sans9b", x + w // 2, 184, label, WHITE)
        x += w


def draw_heroes(at, cv):
    for i, h in enumerate(HEROES):
        x0 = 8 + i * 339
        HERO_DRAW[i](at, cv, x0, 194)
        cv.fill_rect(x0, 278, x0 + 330, 302, RED)
        at.draw(cv, "sans19b", x0 + 10, 295, h["banner"], WHITE)
        at.draw(cv, "sans10b", x0 + 2, 316, h["dateline"], RED)
        for j, ln in enumerate(at.wrap("bask17", h["headline"], 326)):
            at.draw(cv, "bask17", x0 + 2, 336 + j * 21, ln, INK)
        for j, ln in enumerate(at.wrap("gel11", h["deck"], 326)):
            at.draw(cv, "gel11", x0 + 2, 376 + j * 14, ln, INK)
        at.draw(cv, "sans9", x0 + 2, 416, h["source"], LABELGREY)


def draw_secondary(at, cv):
    for row in range(2):
        for col in range(5):
            idx = row * 5 + col
            strip, dateline, headline, deck, source, badge, flag = SECONDARY[idx]
            x0 = 8 + col * 203
            y0 = 424 + row * 166
            cv.fill_rect(x0, y0, x0 + 195, y0 + 20, STRIP_COLOR[idx])
            at.draw(cv, "sans12b", x0 + 8, y0 + 15, strip, WHITE)
            sec_art(at, cv, idx, x0, y0 + 20)
            badge_pill(at, cv, badge, x0 + 4, y0 + 24, white_bg=False)
            if flag in ("UA", "PL", "US", "CN"):
                draw_flag(cv, flag, x0 + 195 - 34, y0 + 24)
            else:
                code_chip(at, cv, flag, x0 + 195 - 34, y0 + 24)
            at.draw(cv, "sans9b", x0 + 2, y0 + 82, dateline, RED)
            draw_right(at, cv, "sans8", x0 + 193, y0 + 82, source, LABELGREY)
            for j, ln in enumerate(at.wrap("bask13", headline, 191)):
                at.draw(cv, "bask13", x0 + 2, y0 + 98 + j * 16, ln, INK)
            for j, ln in enumerate(at.wrap("gel10", deck, 191)):
                at.draw(cv, "gel10", x0 + 2, y0 + 128 + j * 13, ln, INK)


def draw_map(at, cv):
    cv.fill_rect(MAP_X, MAP_Y, MAP_X + MAP_W, MAP_Y + MAP_H, MAPBG)
    for cont in CONTINENTS:
        pts = [(int(px), int(py)) for px, py in
               (project(lon, lat) for lon, lat in cont)]
        cv.polygon(pts, TAN)
        cv.polyline(pts + [pts[0]], (180, 155, 100))
    for lon, lat in ((105, -5), (110, -7), (115, -8), (120, -9),
                     (125, -8), (130, -4), (135, -4), (140, -6)):
        px, py = project(lon, lat)
        cv.ellipse(int(px), int(py), 4, 2, TAN)
    for num, lon, lat, dx, dy in PINS:
        px, py = project(lon, lat)
        qx, qy = int(px) + dx, int(py) + dy
        if dx or dy:
            cv.line(int(px), int(py), qx, qy, RED)
        cv.circle(qx, qy, 6, RED)
        cv.ring(qx, qy, 6, WHITE)
        draw_centered(at, cv, "sans8b", qx, qy + 3, str(num), WHITE)


def draw_bottom(at, cv):
    at.draw(cv, "sans11b", 8, 768, "WHERE IT HAPPENED", NAVY)
    draw_map(at, cv)
    at.draw(cv, "sans9", 14, 918, "Pins 1–13 mark the pictured stories.", INK)
    at.draw(cv, "sans9", 14, 928,
            "6 BepiColombo is flown from Darmstadt.", INK)
    lx = 14
    for col, txt in ((NAVY, "OFFICIAL = official source"),
                     (TEAL, "CONFIRMED = several sources")):
        cv.fill_rect(lx, 933, lx + 7, 940, col)
        lx += 10
        lx = at.draw(cv, "sans8", lx, 940, txt, INK)
        lx += 10
    cv.fill_rect(14, 943, 21, 950, RED)
    at.draw(cv, "sans8", 24, 950,
            "REPORTED = one claim, not yet confirmed", INK)
    at.draw(cv, "sans9", 14, 960, "Map: schematic, not to scale.", LABELGREY)

    at.draw(cv, "sans11b", 338, 768,
            "ALSO ON SATURDAY 21 NOVEMBER 2026 — 23 MORE STORIES", NAVY)
    for k, item in enumerate(LIST_ITEMS):
        col = 0 if k < 12 else 1
        row = k if k < 12 else k - 12
        x0 = 338 + col * 344
        yb = 788 + row * 15
        num = str(14 + k)
        at.draw(cv, "sans10b", x0, yb, num, RED)
        at.draw(cv, "gel10", x0 + at.width("sans10b", num) + 5, yb, item, INK)

    cv.fill_rect(8, 968, 1016, 970, RED)
    cv.fill_rect(8, 1004, 1016, 1006, RED)
    cv.fill_rect(8, 968, 10, 1006, RED)
    cv.fill_rect(1014, 968, 1016, 1006, RED)
    lead = "DATE CHECK — "
    lead_w = at.width("sans10b", lead)
    at.draw(cv, "sans10b", 16, 984, lead, RED)
    # First line shares its row with the lead; later lines use full width.
    words = DATE_CHECK.split(" ")
    first_w = 992 - lead_w - 8
    lines = []
    cur = ""
    limit = first_w
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if at.width("gel10", trial) <= limit or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
            limit = 984
    if cur:
        lines.append(cur)
    at.draw(cv, "gel10", 16 + lead_w, 984, lines[0], INK)
    for j, ln in enumerate(lines[1:]):
        at.draw(cv, "gel10", 16, 998 + j * 13, ln, INK)
    draw_centered(at, cv, "sans9", 512, 1018,
                  "Every story here happened, or was first reported, on "
                  "Saturday 21 November 2026. Sources named beside each "
                  "story · Original drawings · Drawn in code", FOOTGREY)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    at = Atlas(BASE)
    cv = Canvas(W, H, PAPER)
    draw_header(at, cv)
    draw_stats(at, cv)
    draw_regions(at, cv)
    draw_heroes(at, cv)
    draw_secondary(at, cv)
    draw_bottom(at, cv)
    data = png_encode_rgb(cv.px, W, H)
    with open(out, "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes)" % (out, len(data)))


if __name__ == "__main__":
    main()
