# main.py — news-image-20261121 v5 (authored fresh in this session)
#
# One-day world-news front page: Saturday 21 November 2026.
# Renders 1024x1024 PNG to /output/entry.png, stdlib only, no network,
# deterministic (two runs = byte-identical).
#
# Typography comes from a real-font bitmap atlas (atlas.bin + atlas.json,
# built by tools/gen_atlas.py from Bodoni Moda, Libre Baskerville,
# Gelasio, Liberation Sans and Roboto). This program only blits atlas
# glyphs; it has no font engine. All content (stories, dates, numbers)
# is written out in this file from STORIES.md; layout reproduces the v4
# front page measured from its rendered PNG.
#
# Usage: python3 main.py   (writes /output/entry.png, or
# $MAKEFUN_OUTPUT_DIR/entry.png when that variable is set)

import json
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1024, 1024

# ---- palette (sampled from the v4 reference render) ----
CREAM = (247, 240, 220)
NAVY = (22, 35, 63)
NAVY2 = (24, 40, 70)
NAVY3 = (35, 47, 77)
RED = (140, 47, 38)
GOLD = (232, 220, 170)
GOLD2 = (216, 178, 105)
GOLD3 = (198, 158, 88)
TEAL = (30, 74, 104)
GREY_RULE = (200, 196, 182)
GREEN_FIELD = (58, 107, 53)
PINE = (30, 74, 42)
SKY_POL = (28, 52, 96)
TAN = (214, 196, 158)
TAN_DARK = (201, 177, 131)
HOUSE = (138, 106, 69)
ROOF = (90, 70, 50)
MARKET_RED = (198, 60, 44)
STAT_GOLD = (143, 113, 48)
SKIN = (232, 195, 154)
BLOND = (232, 210, 120)
HAIR_GREY = (181, 181, 177)
HAIR_BLACK = (24, 22, 20)
WHITE = (255, 255, 255)
CLOUD = (207, 224, 232)
SUIT = (35, 47, 77)


# ---- atlas ----
class Atlas(object):
    def __init__(self, base):
        with open(os.path.join(base, "atlas.json"), encoding="utf-8") as fh:
            self.data = json.load(fh)
        with open(os.path.join(base, "atlas.bin"), "rb") as fh:
            self.pixels = fh.read()
        self.aw = self.data["width"]
        self.glyphs = self.data["glyphs"]
        self.kern = self.data["kern"]

    def text_width(self, style, text, tracking=0.0):
        g = self.glyphs[style]
        k = self.kern.get(style, {})
        total = 0.0
        prev = None
        for ch in text:
            rec = g.get(ch)
            if rec is None:
                continue
            if prev is not None:
                total += k.get(prev + ch, 0.0)
            total += rec["adv"] + tracking
            prev = ch
        if text:
            total -= tracking
        return total

    def draw(self, cv, style, x, baseline, text, color, tracking=0.0):
        """Blit text; x is the pen position of the first glyph.
        Returns the pen x after the last glyph."""
        g = self.glyphs[style]
        k = self.kern.get(style, {})
        pen = float(x)
        prev = None
        for ch in text:
            rec = g.get(ch)
            if rec is None:
                continue
            if prev is not None:
                pen += k.get(prev + ch, 0.0)
            w = rec["w"]
            h = rec["h"]
            if w and h:
                gx = int(round(pen + rec["bx"]))
                gy = int(round(baseline + rec["by"]))
                cv.blit(self.pixels, self.aw, rec["x"], rec["y"], w, h,
                        gx, gy, color)
            pen += rec["adv"] + tracking
            prev = ch
        return pen

    def draw_aligned(self, cv, style, cx, baseline, text, color,
                     tracking=0.0, align="center"):
        w = self.text_width(style, text, tracking)
        if align == "center":
            x = cx - w / 2.0
        elif align == "right":
            x = cx - w
        else:
            x = cx
        return self.draw(cv, style, x, baseline, text, color, tracking)


def fit_tracking(atlas, style, text, target_w):
    """Letter-spacing needed to stretch text to exactly target_w."""
    w = atlas.text_width(style, text, 0.0)
    n = max(1, len(text) - 1)
    return (target_w - w) / n


# ---- canvas ----
class Canvas(object):
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, len(self.buf), 3):
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def rect(self, x0, y0, x1, y1, color):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w - 1, x1)
        y1 = min(self.h - 1, y1)
        r, g, b = color
        for y in range(y0, y1 + 1):
            i = self._idx(x0, y)
            n = x1 - x0 + 1
            self.buf[i:i + n * 3] = bytes((r, g, b)) * n

    def hline(self, x0, x1, y, color):
        self.rect(x0, y, x1, y, color)

    def vline(self, x, y0, y1, color):
        self.rect(x, y0, x, y1, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def blit(self, src, src_w, sx, sy, w, h, dx, dy, color):
        """Alpha-blend a grayscale bitmap onto the canvas."""
        r, g, b = color
        for row in range(h):
            yy = dy + row
            if yy < 0 or yy >= self.h:
                continue
            sbase = (sy + row) * src_w + sx
            dbase = (yy * self.w + dx) * 3
            for col in range(w):
                xx = dx + col
                if xx < 0 or xx >= self.w:
                    continue
                a = src[sbase + col]
                if a == 0:
                    continue
                di = dbase + col * 3
                if a == 255:
                    self.buf[di] = r
                    self.buf[di + 1] = g
                    self.buf[di + 2] = b
                else:
                    ia = 255 - a
                    self.buf[di] = (r * a + self.buf[di] * ia) // 255
                    self.buf[di + 1] = (g * a + self.buf[di + 1] * ia) // 255
                    self.buf[di + 2] = (b * a + self.buf[di + 2] * ia) // 255

    def circle(self, cx, cy, rad, color):
        for y in range(cy - rad, cy + rad + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, rad * rad - dy * dy)))
            self.hline(cx - dx, cx + dx, y, color)

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / float(ry)
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.hline(cx - dx, cx + dx, y, color)

    def poly(self, pts, color):
        """Scanline fill of a simple polygon."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
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
                self.hline(int(math.ceil(xs[i])), int(math.floor(xs[i + 1])),
                           y, color)


# ---- PNG writer (stdlib only; filter 0, zlib level 9) ----
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# ---- content (from STORIES.md; body text rendered uppercase like v4) ----
FEATURES_LEFT = [
    ("COP31", "CLIMATE TALKS IN OVERTIME",
     "COP31 in Antalya passed its Friday deadline with no deal. "
     "A third draft was due Saturday morning.",
     "DRAFT 144 TO 80 \u00b7 1.5C NAMED \u00b7 NO FUELS"),
    ("KYIV", "COUNTS ITS DEAD",
     "The toll of Friday night's barrage was confirmed Saturday: "
     "7 dead in Kyiv, 3 bridges hit; 2 dead, 42 hurt in Kryvyi Rih.",
     "7 DEAD IN KYIV \u00b7 2 IN KRYVYI RIH \u00b7 42 HURT"),
    ("RUTTE", "FLIES TO WARSAW",
     "NATO chief in Warsaw Saturday as Poland seeks more Eastern "
     "Sentry troops. Visit Sat 21 Nov.",
     None),
    ("YEMEN", "SIX HOUTHI SITES HIT",
     "The Saudi-led coalition said it destroyed six missile and "
     "drone workshops in Sana'a. Reported Sat.",
     None),
    ("PERU", "QUAKE 6.8 SHAKES JUNIN",
     "A magnitude 6.8 quake struck Junin; tremors felt in Lima, "
     "320 km away. Saturday's lead quake story. M6.8",
     None),
    ("PENTAGON", "US\u2013CANADA TIES CURBED",
     "A classified Pentagon memo set new limits on US\u2013Canada "
     "military ties, the Post reported Saturday.",
     None),
    ("NORWAY", "OIL LICENCES RULED OUT",
     "Norway's Supreme Court ruled climate-disputed oil licences "
     "invalid on Saturday. Top court.",
     None),
]

FEATURES_RIGHT = [
    ("RIYADH", "THREE MISSILES DOWN",
     "Saudi defences intercepted three Houthi ballistic missiles "
     "headed for Riyadh in the early hours of Saturday.",
     "3 DOWN \u00b7 ALERT 01:53 \u00b7 2ND ATTACK IN DAYS"),
    ("MERCURY", "THE 8-YEAR VOYAGE ENDS",
     "The ESA\u2013JAXA BepiColombo probe was captured by Mercury's "
     "gravity on Saturday, only the 2nd craft ever to orbit it.",
     "8 YEARS \u00b7 2 ORBITERS \u00b7 SCIENCE APR 2027"),
    ("PEACE", "28-POINT PLAN LANDS IN KYIV",
     "Zelenskyy's office confirmed Kyiv received the US draft; "
     "talks with Trump to follow. 28 points.",
     None),
    ("WALL ST", "IN CORRECTION",
     "Stocks skidded into correction as AI worries intensified; "
     "the sell-off led Saturday's papers. S&P \u20133.7%.",
     None),
    ("INDIA", "RECORD CASH INFLOW",
     "Foreign investors poured a record Rs 1.22 lakh crore into "
     "Indian shares in November. Record inflow.",
     None),
    ("KIM", "TOURS FACTORIES",
     "State media said Saturday Kim Jong Un inspected school "
     "equipment sites after Trump's Asia trip. KCNA.",
     None),
    ("EBOLA", "LAST PATIENT OUT",
     "Kenya discharged its last Ebola patient as the DRC death "
     "toll passed 5,300. DRC toll 5,300.",
     None),
]

# (label, date) — strip order is row-major across 3 columns
STRIP = [
    ("COP31 \u2014 OVERTIME, NO DEAL", "21 NOV"),
    ("RIYADH \u2014 3 MISSILES DOWN", "21 NOV"),
    ("KYIV \u2014 TOLL CONFIRMED SAT", "21 NOV"),
    ("BEPICOLOMBO \u2014 MERCURY", "21 NOV"),
    ("RUTTE \u2014 WARSAW SAT", "21 NOV"),
    ("PEACE \u2014 28-PT PLAN", "21 NOV"),
    ("YEMEN \u2014 6 SITES HIT", "21 NOV"),
    ("JAZAN \u2014 2 MORE DOWN", "21 NOV"),
    ("WALL ST \u2014 CORRECTION", "21 NOV"),
    ("KIM \u2014 FACTORY TOUR", "21 NOV"),
    ("PERU \u2014 QUAKE 6.8", "21 NOV"),
    ("INDIA \u2014 FPI RECORD", "21 NOV"),
    ("NEPAL \u2014 PM TO DELHI", "21 NOV"),
    ("RAHUL \u2014 SENA CENTURY", "21 NOV"),
    ("PENTAGON \u2014 CANADA MEMO", "21 NOV"),
    ("IRAN \u2014 OIL SANCTIONS", "21 NOV"),
    ("IRGC \u2014 US DRONE CLAIM", "21 NOV"),
    ("TRUMP \u2014 DATA-CENTRE BAN", "21 NOV"),
    ("UFO \u2014 FILES RELEASED", "21 NOV"),
    ("FRENCH POLICE \u2014 JAILED", "21 NOV"),
    ("CEUTA \u2014 MIGRANT CRISIS", "21 NOV"),
    ("AFD \u2014 SAXONY-ANHALT WIN", "21 NOV"),
    ("NORWAY \u2014 OIL LICENCES VOID", "21 NOV"),
    ("GHANA \u2014 NEW BANKNOTES", "21 NOV"),
    ("KENYA \u2014 EBOLA PATIENT OUT", "21 NOV"),
    ("DRC \u2014 EBOLA TOLL 5,300", "21 NOV"),
    ("SWISS \u2014 ICJ RULING HAILED", "21 NOV"),
    ("RUBIO \u2014 ATHENS TALKS", "21 NOV"),
    ("GUINEA \u2014 BANS RTB", "21 NOV"),
    ("NIGERIA \u2014 NAVAL SHIPS", "21 NOV"),
    ("TSHISEKEDI \u2014 REFORM LAW", "21 NOV"),
    ("KENYA \u2014 293,600 SAUDI JOBS", "21 NOV"),
    ("S. AFRICA \u2014 PROTESTS BARRED", "21 NOV"),
    ("ANTHROPIC \u2014 SLIDE CONTINUES", "21 NOV"),
    ("TRUMP \u2014 NO KIM MEETING", "21 NOV"),
    ("PANAMA \u2014 COP31 VETO THREAT", "20 NOV"),
]

TIMELINE = [
    ("00:51 UTC", "RIYADH 3 DOWN"),
    ("01:51 UTC", "JAZAN 2 DOWN"),
    ("01:56 UTC", "COP31 OVERTIME"),
    ("SAT AM", "DRAFT 3 DUE"),
    ("SATURDAY", "MERCURY CAPTURE"),
    ("SATURDAY", "RUTTE WARSAW"),
]


def wrap(atlas, style, text, max_w, tracking=0.0):
    """Greedy word wrap; returns a list of lines (each <= max_w)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if atlas.text_width(style, trial, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---- globe (orthographic, centre 30E/25N, radius 80 at (146,188)) ----
GLOBE_C = (146, 188)
GLOBE_R = 80
LON0, LAT0 = 30.0, 25.0

# coarse continent outlines, (lon, lat), drawn from real geography
AFRICA = [(-6, 35), (10, 37), (20, 32), (30, 31), (32, 28), (35, 20),
          (38, 18), (43, 12), (51, 11), (48, 5), (41, -2), (40, -10),
          (36, -18), (33, -26), (29, -33), (20, -35), (17, -29),
          (14, -22), (12, -17), (13, -10), (9, -2), (9, 4), (4, 6),
          (-8, 5), (-13, 8), (-17, 12), (-17, 20), (-16, 28), (-10, 31)]
EUROPE = [(-10, 36), (-9, 43), (-2, 48), (-4, 50), (0, 51), (4, 53),
          (8, 55), (10, 58), (18, 56), (21, 55), (24, 59), (21, 64),
          (18, 69), (25, 71), (30, 70), (28, 64), (24, 60), (28, 58),
          (24, 54), (19, 54), (19, 49), (23, 46), (28, 44), (23, 40),
          (19, 42), (14, 45), (8, 44), (3, 43), (-2, 37), (-6, 36)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (0, 53), (1, 51), (-2, 51)]
ASIA = [(42, 47), (48, 45), (52, 42), (56, 39), (60, 37), (64, 34),
        (68, 32), (72, 30), (76, 32), (80, 30), (84, 28), (88, 26),
        (92, 24), (96, 22), (100, 20), (104, 18), (108, 16), (110, 20),
        (114, 22), (118, 25), (120, 28), (122, 31), (122, 35), (120, 38),
        (124, 40), (128, 42), (132, 43), (136, 44), (140, 46), (142, 50),
        (141, 55), (140, 59), (138, 60), (142, 61), (146, 60), (150, 60),
        (156, 61), (160, 62), (162, 60), (160, 56), (157, 52), (154, 48),
        (150, 45), (146, 42), (142, 40), (140, 36), (138, 34), (134, 34),
        (130, 33), (127, 35), (126, 38), (124, 40), (122, 38), (120, 35),
        (117, 32), (113, 28), (109, 22), (106, 20), (103, 15), (100, 12),
        (97, 10), (94, 15), (92, 20), (89, 22), (86, 20), (83, 17),
        (80, 13), (77, 8), (74, 12), (72, 20), (69, 22), (66, 25),
        (63, 28), (60, 30), (57, 33), (54, 36), (51, 39), (48, 42),
        (45, 44), (42, 47)]
ARABIA = [(35, 29), (39, 29), (43, 28), (48, 29), (52, 27), (55, 24),
          (58, 22), (57, 18), (54, 16), (51, 14), (48, 13), (45, 12),
          (43, 13), (40, 16), (38, 20), (36, 24), (35, 28)]
INDIA = [(68, 24), (70, 22), (72, 20), (74, 16), (76, 10), (77, 8),
         (80, 10), (80, 14), (84, 18), (88, 22), (89, 24), (87, 27),
         (84, 28), (80, 30), (76, 32), (72, 32), (68, 28)]
SEASIA = [(92, 22), (95, 20), (97, 16), (98, 12), (100, 8), (101, 5),
          (103, 2), (104, 5), (105, 9), (107, 11), (109, 14), (109, 18),
          (106, 20), (103, 18), (101, 14), (99, 12), (97, 14), (94, 17),
          (92, 21)]
# (number, lon, lat, badge dx, dy)
PINS = [(1, 21.0, 52.2, 14, -16), (2, 30.5, 50.4, 18, -4),
        (3, 30.7, 36.9, 16, 10), (4, 114.1, 22.5, -2, 16),
        (5, 4.3, 52.0, -16, -14), (6, -0.1, 51.5, -18, 4),
        (7, 12.6, 55.7, 0, -18), (8, 84.9, 19.3, 10, 14)]


def project(lon, lat):
    lam = math.radians(lon - LON0)
    phi = math.radians(lat)
    phi0 = math.radians(LAT0)
    cosc = (math.sin(phi0) * math.sin(phi)
            + math.cos(phi0) * math.cos(phi) * math.cos(lam))
    x = GLOBE_R * math.cos(phi) * math.sin(lam)
    y = -GLOBE_R * (math.cos(phi0) * math.sin(phi)
                    - math.sin(phi0) * math.cos(phi) * math.cos(lam))
    return (GLOBE_C[0] + x, GLOBE_C[1] + y, cosc)


def clip_polygon(poly):
    """Project a lon/lat polygon, clipping edges at the limb (cosc=0)."""
    pts = [project(lon, lat) for lon, lat in poly]
    out = []
    n = len(pts)
    for i in range(n):
        x0, y0, c0 = pts[i]
        x1, y1, c1 = pts[(i + 1) % n]
        if c0 > 0:
            out.append((x0, y0))
        if (c0 > 0) != (c1 > 0):
            t = c0 / (c0 - c1) if c0 != c1 else 0.0
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return [(int(round(x)), int(round(y))) for x, y in out]


def draw_globe(cv, atlas):
    cx, cy = GLOBE_C
    cv.circle(cx, cy, GLOBE_R, TEAL)
    for poly, color in ((AFRICA, GOLD2), (EUROPE, GOLD2), (UK, GOLD2),
                        (ASIA, GOLD2), (ARABIA, GOLD3), (INDIA, GOLD3),
                        (SEASIA, GOLD2)):
        pts = clip_polygon(poly)
        if len(pts) >= 3:
            cv.poly(pts, color)
    # clouds
    cv.ellipse(150, 208, 20, 5, CLOUD)
    cv.ellipse(118, 152, 16, 4, CLOUD)
    cv.ellipse(196, 176, 12, 4, CLOUD)
    # gold rim on the upper-left limb
    for deg in range(175, 276):
        th = math.radians(deg)
        for rr in (GLOBE_R, GLOBE_R - 1):
            cv.set(int(round(cx + rr * math.cos(th))),
                   int(round(cy + rr * math.sin(th))), GOLD2)
    # pins: true dot + offset badge + leader
    for num, lon, lat, dx, dy in PINS:
        x, y, c = project(lon, lat)
        if c <= 0:
            continue
        bx, by = int(round(x)) + dx, int(round(y)) + dy
        cv.line(int(round(x)), int(round(y)), bx, by, GOLD)
        cv.circle(int(round(x)), int(round(y)), 2, MARKET_RED)
        cv.circle(bx, by, 7, MARKET_RED)
        atlas.draw_aligned(cv, "sans_stat", bx, by + 4, str(num), WHITE)


def draw_flag(cv, x, y, kind):
    """Small 34x20 flag at (x, y)."""
    if kind == "us":
        for i in range(7):
            cv.rect(x, y + i * 3, x + 33, y + i * 3 + 1,
                    MARKET_RED if i % 2 == 0 else WHITE)
        cv.rect(x, y, x + 13, y + 9, NAVY2)
        for dx in (3, 8):
            for dy in (3, 7):
                cv.set(x + dx, y + dy, WHITE)
    elif kind == "cn":
        cv.rect(x, y, x + 33, y + 19, MARKET_RED)
        cv.circle(x + 8, y + 9, 3, GOLD2)
        for dx, dy in ((16, 4), (20, 7), (20, 12), (16, 15)):
            cv.circle(x + dx, y + dy, 1, GOLD2)
    else:  # ru
        cv.rect(x, y, x + 33, y + 6, WHITE)
        cv.rect(x, y + 7, x + 33, y + 12, (40, 80, 160))
        cv.rect(x, y + 13, x + 33, y + 19, MARKET_RED)


def draw_figure(cv, cx, hair):
    """Summit bust: suit, shirt, tie, head, hair cap."""
    cv.poly([(cx - 22, 215), (cx + 22, 215), (cx + 16, 196),
             (cx - 16, 196)], SUIT)
    cv.poly([(cx - 6, 196), (cx + 6, 196), (cx, 214)], WHITE)
    cv.poly([(cx - 3, 197), (cx + 3, 197), (cx + 2, 212), (cx - 2, 212)],
            MARKET_RED)
    cv.circle(cx, 178, 13, SKIN)
    cv.ellipse(cx, 170, 13, 7, hair)


def draw_vignettes(cv, atlas):
    panels = [(20, 262), (267, 509), (514, 756), (761, 1013)]
    labels = ["POLAND \u2014 RUTTE IN WARSAW", "GAZA \u2014 CIVILIANS RETURN",
              "THE HAGUE \u2014 JUSTICE", "MARKETS \u2014 TECH SELLS OFF"]
    captions = ["SAT 21 NOV \u00b7 NATO CHIEF VISITS",
                "HOMES DAMAGED \u00b7 NO DATE CLAIMED",
                "ICJ RULING WAS 19 NOV \u00b7 SEE CONTEXT",
                "CORRECTION REPORTED SAT 21 NOV"]
    for (x0, x1), label, cap in zip(panels, labels, captions):
        cv.rect(x0, 278, x1, 296, NAVY)
        cv.rect(x0, 336, x1, 355, NAVY)
        atlas.draw(cv, "sans_label", x0 + 8, 292, label, GOLD)
        atlas.draw(cv, "robo_cap", x0 + 8, 350, cap, CREAM)
        for xx in (x0, x1):
            cv.vline(xx, 278, 355, GOLD3)
        cv.hline(x0, x1, 278, GOLD3)
        cv.hline(x0, x1, 355, GOLD3)
    # Poland: sky, field, pines, jet, starburst
    x0, x1 = panels[0]
    cv.rect(x0 + 1, 297, x1 - 1, 325, SKY_POL)
    cv.rect(x0 + 1, 326, x1 - 1, 335, GREEN_FIELD)
    for tx in (x0 + 30, x0 + 62, x0 + 94):
        cv.poly([(tx, 306), (tx - 9, 330), (tx + 9, 330)], PINE)
        cv.rect(tx - 1, 330, tx + 1, 335, PINE)
    jx, jy = x0 + 165, 306
    cv.poly([(jx - 22, jy), (jx + 22, jy - 2), (jx + 26, jy),
             (jx + 22, jy + 2)], WHITE)
    cv.poly([(jx - 2, jy - 2), (jx + 8, jy - 8), (jx + 10, jy - 2)], WHITE)
    sx, sy = x0 + 208, 310
    for ang in range(0, 360, 45):
        th = math.radians(ang)
        cv.line(sx, sy, int(sx + 9 * math.cos(th)),
                int(sy + 9 * math.sin(th)), GOLD2)
    cv.circle(sx, sy, 2, GOLD2)
    # Gaza: tan ground, houses, figures
    x0, x1 = panels[1]
    cv.rect(x0 + 1, 297, x1 - 1, 335, TAN)
    cv.rect(x0 + 1, 326, x1 - 1, 335, TAN_DARK)
    for i, hx in enumerate((x0 + 14, x0 + 72, x0 + 130, x0 + 188)):
        cv.rect(hx, 312, hx + 38, 335, HOUSE)
        cv.poly([(hx - 3, 312), (hx + 41, 312), (hx + 34, 302),
                 (hx + 4, 302)], ROOF)
        cv.rect(hx + 16, 322, hx + 22, 335, ROOF)
    for fx in (x0 + 60, x0 + 122, x0 + 178):
        cv.circle(fx, 330, 2, NAVY)
        cv.rect(fx - 2, 332, fx + 2, 335, NAVY)
    # The Hague: courthouse + scales
    x0, x1 = panels[2]
    cv.rect(x0 + 1, 297, x1 - 1, 335, NAVY2)
    hx = (x0 + x1) // 2 - 52
    cv.poly([(hx, 306), (hx + 72, 306), (hx + 36, 296)], WHITE)
    cv.rect(hx + 2, 306, hx + 70, 310, WHITE)
    for i in range(4):
        cv.rect(hx + 6 + i * 17, 310, hx + 12 + i * 17, 330, WHITE)
    cv.rect(hx + 2, 330, hx + 70, 335, WHITE)
    sx = x1 - 42
    cv.vline(sx, 302, 332, GOLD2)
    cv.hline(sx - 16, sx + 16, 304, GOLD2)
    for px_ in (sx - 16, sx + 16):
        cv.line(px_, 304, px_ - 6, 318, GOLD2)
        cv.line(px_, 304, px_ + 6, 318, GOLD2)
        cv.poly([(px_ - 7, 318), (px_ + 7, 318), (px_, 324)], GOLD2)
    # Markets: falling line + rising bars
    x0, x1 = panels[3]
    cv.rect(x0 + 1, 297, x1 - 1, 335, NAVY2)
    pts = [(x0 + 12, 304), (x0 + 55, 308), (x0 + 98, 312), (x0 + 140, 318),
           (x0 + 175, 322), (x0 + 205, 326)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], MARKET_RED)
    for px_, py_ in pts:
        cv.circle(px_, py_, 2, MARKET_RED)
    for i, bh in enumerate((6, 10, 14, 18, 23, 28)):
        bx = x1 - 58 + i * 10
        cv.rect(bx, 335 - bh, bx + 7, 335, MARKET_RED)


def draw_features(cv, atlas):
    tops = [464, 537, 612, 650, 688, 726, 764]
    for col_x, col_w, feats in ((10, 495, FEATURES_LEFT),
                                (522, 488, FEATURES_RIGHT)):
        for i, (kick, head, body, stat) in enumerate(feats):
            top = tops[i]
            if i < 2:
                atlas.draw(cv, "sans_kick", col_x, top + 10, kick, RED)
                atlas.draw(cv, "bask_feat", col_x, top + 29, head, NAVY)
                lines = wrap(atlas, "gel_body", body.upper(), col_w)
                atlas.draw(cv, "gel_body", col_x, top + 44, lines[0], NAVY)
                if len(lines) > 1:
                    atlas.draw(cv, "gel_body", col_x, top + 56, lines[1],
                               NAVY)
                if stat:
                    atlas.draw(cv, "sans_stat", col_x, top + 69, stat,
                               STAT_GOLD)
            else:
                pen = atlas.draw(cv, "gel_head2", col_x, top + 13,
                                 kick + " \u2014 ", RED)
                atlas.draw(cv, "gel_head2", pen, top + 13, head, NAVY)
                lines = wrap(atlas, "gel_body", body.upper(), col_w)
                atlas.draw(cv, "gel_body", col_x, top + 26, lines[0], NAVY)
                if len(lines) > 1:
                    atlas.draw(cv, "gel_body", col_x, top + 38, lines[1],
                               NAVY)
        cv.hline(col_x, col_x + col_w - 1, 536, GREY_RULE)
        cv.hline(col_x, col_x + col_w - 1, 609, GREY_RULE)
    cv.vline(511, 464, 806, GREY_RULE)


def draw_strip(cv, atlas):
    cols = [(10, 335), (345, 670), (680, 1010)]
    for row in range(12):
        y = 812 + row * 11
        for c in range(3):
            n = row * 3 + c + 1
            label, date = STRIP[n - 1]
            x0, x1 = cols[c]
            atlas.draw(cv, "sans_strip", x0, y + 9,
                       "%02d %s" % (n, label), NAVY)
            atlas.draw_aligned(cv, "sans_strip", x1, y + 9, date, NAVY,
                               align="right")


def render():
    atlas = Atlas(HERE)
    cv = Canvas(W, H, CREAM)
    # top bar + masthead + date + rules
    cv.rect(0, 0, W - 1, 9, NAVY)
    atlas.draw_aligned(cv, "bodoni_mast", 512, 74, "WORLD NEWS", NAVY)
    tr = fit_tracking(atlas, "sans_date", "SATURDAY, 21 NOVEMBER 2026", 414)
    atlas.draw_aligned(cv, "sans_date", 512, 88,
                       "SATURDAY, 21 NOVEMBER 2026", NAVY, tracking=tr)
    cv.rect(0, 94, W - 1, 95, NAVY)
    cv.rect(0, 98, W - 1, 99, NAVY)
    cv.rect(0, 102, W - 1, 103, GOLD2)
    # hero band
    cv.rect(0, 104, W - 1, 271, NAVY)
    draw_globe(cv, atlas)
    atlas.draw(cv, "bask_hero", 235, 158, "COP31 IN OVERTIME", CREAM)
    atlas.draw(cv, "bask_sub", 232, 192,
               "RIYADH: 3 MISSILES DOWN \u00b7 BEPICOLOMBO REACHES MERCURY",
               GOLD)
    atlas.draw(cv, "bask_sub", 232, 211,
               "KYIV TOLL CONFIRMED \u00b7 RUTTE IN WARSAW "
               "\u00b7 28-POINT PEACE PLAN", GOLD)
    atlas.draw(cv, "bask_sub", 232, 229,
               "200 NATIONS \u00b7 DRAFT 144 TO 80 \u00b7 1.5C NAMED "
               "\u00b7 NO FOSSIL FUELS", GOLD)
    atlas.draw(cv, "bask_sub", 232, 248,
               "SATURDAY 21 NOVEMBER 2026 \u2014 THE DAY'S NEWS IN ONE PAGE",
               GOLD2)
    # summit figures
    atlas.draw_aligned(cv, "sans_shenzhen", 1010, 122, "SHENZHEN \u2014 19 NOV",
                       GOLD2, align="right")
    for (cx, flag, hair, name) in (
            (868, "us", BLOND, "TRUMP"),
            (938, "cn", HAIR_BLACK, "XI JINPING"),
            (1002, "ru", HAIR_GREY, "PUTIN")):
        draw_flag(cv, cx - 17, 128, flag)
        draw_figure(cv, cx, hair)
        atlas.draw_aligned(cv, "sans_name", cx, 228, name, CREAM)
    atlas.draw_aligned(cv, "sans_note", 1010, 252, "SEE CONTEXT BOX", GOLD2,
                       align="right")
    # vignettes
    draw_vignettes(cv, atlas)
    # date check + context bands
    cv.rect(0, 362, W - 1, 399, RED)
    atlas.draw_aligned(
        cv, "sans_datecheck", 512, 379,
        "DATE CHECK \u2014 SHENZHEN SUMMIT + ICJ RULING WERE 19 NOV, "
        "NOT 21 NOV.", CREAM)
    atlas.draw_aligned(
        cv, "sans_datecheck", 512, 395,
        "ALSO NOT SATURDAY: POLAND MISSILES, DENMARK PLOT, BAYER, RIKERS, "
        "MEASLES, AI CHIPS 900K \u2014 ALL 19\u201320 NOV.", CREAM)
    cv.rect(0, 404, W - 1, 425, GOLD)
    atlas.draw_aligned(
        cv, "sans_context", 512, 419,
        "CONTEXT \u2014 19 NOV (NOT TODAY'S NEWS): SHENZHEN \u2014 TRUMP, XI, "
        "PUTIN MEET \u00b7 ICJ \u2014 MYANMAR GUILTY OF ROHINGYA GENOCIDE, 9\u20136.",
        NAVY)
    # also today + meta
    atlas.draw(cv, "bodoni_also", 20, 455, "ALSO TODAY", NAVY)
    atlas.draw_aligned(cv, "sans_meta", 1010, 452,
                       "36 STORIES \u00b7 7 REGIONS \u00b7 SOURCES: REUTERS, "
                       "AP, BBC, ESA", NAVY, align="right")
    cv.rect(0, 458, W - 1, 459, NAVY)
    # features + strip
    draw_features(cv, atlas)
    cv.rect(0, 806, W - 1, 807, NAVY)
    draw_strip(cv, atlas)
    # timeline
    cv.rect(0, 944, W - 1, 945, NAVY)
    atlas.draw(cv, "sans_small", 20, 956, "TIMELINE \u2014 UTC", RED)
    for (tm, label), cx in zip(TIMELINE, (300, 430, 565, 700, 840, 965)):
        atlas.draw_aligned(cv, "sans_small", cx, 956, tm, STAT_GOLD)
        cv.circle(cx, 964, 3, RED)
        atlas.draw_aligned(cv, "sans_small", cx, 979, label, NAVY)
    cv.hline(150, 1003, 964, NAVY)
    # numbers strip
    atlas.draw_aligned(
        cv, "sans_small", 512, 994,
        "THE DAY IN NUMBERS \u2014 3 MISSILES DOWN OVER RIYADH \u00b7 9 DEAD "
        "IN KYIV BARRAGE \u00b7 42 HURT IN KRYVYI RIH \u00b7 6.8 PERU QUAKE "
        "\u00b7 28 PEACE POINTS \u00b7 8 YEARS TO MERCURY", STAT_GOLD)
    # bottom headline
    cv.rect(0, 996, W - 1, 996, NAVY)
    tr = fit_tracking(atlas, "bask_bottom", "THE WORLD AT A CROSSROADS", 984)
    atlas.draw_aligned(cv, "bask_bottom", 512, 1022,
                       "THE WORLD AT A CROSSROADS", NAVY, tracking=tr)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    path = os.path.join(out_dir, "entry.png")
    cv = render()
    n = write_png(cv, path)
    print("wrote %s (%d bytes)" % (path, n))


if __name__ == "__main__":
    main()
