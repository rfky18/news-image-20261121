# news-image-20261121 — v1
# "THE WORLD AT A CROSSROADS" — Saturday, 21 November 2026 in one image.
# Pure Python 3 stdlib, no network, no PIL. Writes /output/entry.png
# (1024x1024, <=1 MiB, deterministic). All text is real type from two
# bitmap atlases defined in this file: a Didone-style serif (masthead and
# headlines) and a Helvetica-style sans (date, labels, story strip).
# All artwork is drawn in code. See STORIES.md for the fact-check table.
import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---- palette: navy, charcoal, warm gold, muted crimson, ivory paper ----
IVORY = (246, 241, 230)
PAPER = (240, 234, 220)
NAVY = (16, 28, 51)
NAVY2 = (22, 38, 63)
NAVY3 = (38, 56, 86)
GOLD = (201, 162, 75)
GOLD_LT = (226, 190, 110)
CRIMSON = (122, 31, 31)
CRIMSON_LT = (172, 58, 58)
INK = (24, 28, 36)
WHITE = (250, 248, 242)
GREY = (110, 112, 118)
GREEN = (111, 125, 58)
GREEN_DK = (74, 88, 44)
SEA_DK = (18, 38, 63)
SEA_LT = (42, 90, 110)
SAND = (214, 196, 158)

# ---- canvas ----
px = bytearray(W * H * 3)


def put(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i], px[i + 1], px[i + 2] = c


def blend(x, y, c, a):
    # a in 0..1: paint colour c over what is already there
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i] = int(px[i] * (1 - a) + c[0] * a)
        px[i + 1] = int(px[i + 1] * (1 - a) + c[1] * a)
        px[i + 2] = int(px[i + 2] * (1 - a) + c[2] * a)


def rect(x, y, w, h, c):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    for yy in range(y0, y1):
        base = (yy * W + x0) * 3
        for xx in range(x0, x1):
            i = base + (xx - x0) * 3
            px[i], px[i + 1], px[i + 2] = c


def hline(x0, x1, y, c):
    for x in range(max(0, x0), min(W, x1)):
        put(x, y, c)


def vline(x, y0, y1, c):
    for y in range(max(0, y0), min(H, y1)):
        put(x, y, c)


def line(x0, y0, x1, y1, c):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        put(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def circle(cx, cy, r, c):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                put(xx, yy, c)


def disc(cx, cy, r, c, a=1.0):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                if a >= 1.0:
                    put(xx, yy, c)
                else:
                    blend(xx, yy, c, a)


def ellipse(cx, cy, rx, ry, c, a=1.0):
    for yy in range(cy - ry, cy + ry + 1):
        for xx in range(cx - rx, cx + rx + 1):
            if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                if a >= 1.0:
                    put(xx, yy, c)
                else:
                    blend(xx, yy, c, a)


def poly(points, c):
    # scanline fill of a simple polygon
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(H, max(ys) + 1)):
        xs = []
        n = len(points)
        for k in range(n):
            x0, y0 = points[k]
            x1, y1 = points[(k + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[k])), min(W, int(xs[k + 1]) + 1)):
                put(x, y, c)


def tri(x0, y0, x1, y1, x2, y2, c):
    poly([(x0, y0), (x1, y1), (x2, y2)], c)


# ---- PNG encoder (stdlib only, deterministic) ----
def write_png(path, w, h, data):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += data[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, body):
        out = struct.pack(">I", len(body)) + tag + body
        return out + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---- sans atlas: 7 wide x 9 tall, filled bitmap, Helvetica-style ----
# '#' is ink, '.' is empty. Every glyph is exactly 9 rows of 7 chars.
SANS = {
    "A": ("..###..", ".##.##.", "##...##", "##...##", "#######", "##...##", "##...##", "##...##", "##...##"),
    "B": ("######.", "##...##", "##...##", "##...##", "######.", "##...##", "##...##", "##...##", "######."),
    "C": ("..####.", ".##...#", "##.....", "##.....", "##.....", "##.....", "##.....", ".##...#", "..####."),
    "D": ("#####..", "##...##", "##....#", "##....#", "##....#", "##....#", "##....#", "##...##", "#####.."),
    "E": ("#######", "##.....", "##.....", "##.....", "#####..", "##.....", "##.....", "##.....", "#######"),
    "F": ("#######", "##.....", "##.....", "##.....", "#####..", "##.....", "##.....", "##.....", "##....."),
    "G": ("..####.", ".##...#", "##.....", "##.....", "##..###", "##...##", "##...##", ".##..##", "..###.#"),
    "H": ("##...##", "##...##", "##...##", "##...##", "#######", "##...##", "##...##", "##...##", "##...##"),
    "I": (".#####.", "...#...", "...#...", "...#...", "...#...", "...#...", "...#...", "...#...", ".#####."),
    "J": ("..#####", "......#", "......#", "......#", "......#", "......#", "##....#", "##...##", "..###.."),
    "K": ("##...##", "##..##.", "##.##..", "####...", "##.##..", "##..##.", "##...##", "##...##", "##...##"),
    "L": ("##.....", "##.....", "##.....", "##.....", "##.....", "##.....", "##.....", "##.....", "#######"),
    "M": ("##...##", "###.###", "#######", "##.#.##", "##...##", "##...##", "##...##", "##...##", "##...##"),
    "N": ("##...##", "###..##", "####.##", "##.####", "##..###", "##...##", "##...##", "##...##", "##...##"),
    "O": ("..###..", ".##.##.", "##...##", "##...##", "##...##", "##...##", "##...##", ".##.##.", "..###.."),
    "P": ("######.", "##...##", "##...##", "##...##", "######.", "##.....", "##.....", "##.....", "##....."),
    "Q": ("..###..", ".##.##.", "##...##", "##...##", "##...##", "##...##", "##.#.##", ".##.##.", "..##.##"),
    "R": ("######.", "##...##", "##...##", "##...##", "######.", "##.##..", "##..##.", "##...##", "##...##"),
    "S": ("..####.", ".##...#", "##.....", ".##....", "..###..", "....##.", ".....##", "#...##.", ".####.."),
    "T": ("#######", "...#...", "...#...", "...#...", "...#...", "...#...", "...#...", "...#...", "...#..."),
    "U": ("##...##", "##...##", "##...##", "##...##", "##...##", "##...##", "##...##", ".##.##.", "..###.."),
    "V": ("##...##", "##...##", "##...##", "##...##", "##...##", "##...##", ".##.##.", ".##.##.", "..###.."),
    "W": ("##...##", "##...##", "##...##", "##...##", "##.#.##", "#######", "###.###", "##...##", "##...##"),
    "X": ("##...##", "##...##", ".##.##.", "..###..", "..###..", ".##.##.", "##...##", "##...##", "##...##"),
    "Y": ("##...##", "##...##", ".##.##.", "..###..", "...#...", "...#...", "...#...", "...#...", "...#..."),
    "Z": ("#######", ".....##", "....##.", "...##..", "..##...", ".##....", "##.....", "##.....", "#######"),
    "0": ("..###..", ".##.##.", "##...##", "##..###", "##.#.##", "###..##", "##...##", ".##.##.", "..###.."),
    "1": ("...##..", "..###..", ".####..", "...#...", "...#...", "...#...", "...#...", "...#...", ".#####."),
    "2": ("..###..", ".##.##.", ".....##", "....##.", "...##..", "..##...", ".##....", "##.....", "#######"),
    "3": (".####..", "##...##", ".....##", "....##.", "..###..", "....##.", ".....##", "##...##", ".####.."),
    "4": ("....##.", "...##..", "..##...", ".##.##.", "##...##", "#######", "....##.", "....##.", "....##."),
    "5": ("#######", "##.....", "##.....", "#####..", "....##.", ".....##", ".....##", "##...##", ".####.."),
    "6": ("..###..", ".##....", "##.....", "##.###.", "###.###", "##...##", "##...##", ".##.##.", "..###.."),
    "7": ("#######", ".....##", "....##.", "...##..", "...##..", "..##...", "..##...", "..##...", "..##..."),
    "8": ("..###..", ".##.##.", "##...##", ".##.##.", "..###..", ".##.##.", "##...##", ".##.##.", "..###.."),
    "9": ("..###..", ".##.##.", "##...##", "##...##", ".####.#", "....###", ".....##", "....##.", "..###.."),
    " ": (".......", ".......", ".......", ".......", ".......", ".......", ".......", ".......", "......."),
    ".": (".......", ".......", ".......", ".......", ".......", ".......", ".......", ".##....", ".##...."),
    ",": (".......", ".......", ".......", ".......", ".......", ".......", ".##....", ".##....", "##....."),
    ":": (".......", ".##....", ".##....", ".......", ".......", ".##....", ".##....", ".......", "......."),
    ";": (".......", ".##....", ".##....", ".......", ".......", ".##....", ".##....", "##.....", "......."),
    "-": (".......", ".......", ".......", ".......", ".#####.", ".......", ".......", ".......", "......."),
    "!": ("...#...", "...#...", "...#...", "...#...", "...#...", "...#...", ".......", "...#...", "...#..."),
    "?": ("..###..", ".##.##.", ".....##", "....##.", "...##..", "...#...", ".......", "...#...", "...#..."),
    "(": ("....##.", "...##..", "..##...", "..##...", "..##...", "..##...", "..##...", "...##..", "....##."),
    ")": (".##....", "..##...", "...##..", "...##..", "...##..", "...##..", "...##..", "..##...", ".##...."),
    "/": (".....##", "....##.", "....##.", "...##..", "...##..", "..##...", "..##...", ".##....", ".##...."),
    "&": ("..##...", ".##.##.", "##...##", ".##.##.", "..##...", ".##.##.", "##...##", "##...##", ".###.##"),
    "%": ("##...##", "##..##.", "....##.", "...##..", "..##...", ".##....", "##..###", "##...##", "##...##"),
    "+": (".......", "...#...", "...#...", ".#####.", "...#...", "...#...", ".......", ".......", "......."),
    "=": (".......", ".......", ".#####.", ".......", ".#####.", ".......", ".......", ".......", "......."),
    "'": ("...#...", "...#...", "..##...", ".......", ".......", ".......", ".......", ".......", "......."),
    '"': (".##.##.", ".##.##.", ".##.##.", ".......", ".......", ".......", ".......", ".......", "......."),
    ".": (".......", ".......", ".......", ".......", ".......", ".......", ".......", ".##....", ".##...."),
    "\u00b7": (".......", ".......", ".......", ".......", "...#...", ".......", ".......", ".......", "......."),
}


# ---- serif atlas: 10 wide x 12 tall, Didone-style ----
# Thick vertical stems (2 px), thin horizontals (1 px), serif feet.
# Only the letters the masthead and headlines need.
SERIF = {
    "A": ("....##....", "...####...", "...#..#...", "..##..##..", "..##..##..", "..##..##..", ".##....##.", ".########.", "##......##", "##......##", "##......##", "##......##"),
    "C": ("...####...", "..##...##.", ".##.....##", ".##.......", "##........", "##........", "##........", "##........", ".##.......", ".##.....##", "..##...##.", "...####..."),
    "D": (".######...", ".##....##.", ".##.....##", ".##.....##", ".##.....##", ".##.....##", ".##.....##", ".##.....##", ".##.....##", ".##.....##", ".##....##.", ".######..."),
    "E": (".########.", ".##.......", ".##.......", ".##.......", ".#####....", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".########."),
    "H": (".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".########.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##."),
    "I": (".########.", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", ".########."),
    "L": (".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".########."),
    "M": (".##....##.", ".###..###.", ".###..###.", ".####.###.", ".##.##.##.", ".##.##.##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##."),
    "N": (".##....##.", ".###...##.", ".####..##.", ".##.#..##.", ".##..#.##.", ".##...###.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##."),
    "O": ("...####...", "..##..##..", ".##....##.", ".##....##.", "##......##", "##......##", "##......##", "##......##", ".##....##.", ".##....##.", "..##..##..", "...####..."),
    "P": (".#######..", ".##....##.", ".##....##.", ".##....##.", ".#######..", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##.......", ".##......."),
    "R": (".#######..", ".##....##.", ".##....##.", ".##....##.", ".#######..", ".##..##...", ".##...##..", ".##...##..", ".##....##.", ".##....##.", ".##....##.", ".##....##."),
    "S": ("...####...", "..##..##..", ".##....##.", ".##.......", ".##.......", "..###.....", "....###...", ".....##...", "......##..", "##.....##.", ".##...##..", "..#####..."),
    "T": (".########.", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##....", "....##...."),
    "W": (".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##....##.", ".##.##.##.", ".##.##.##.", ".###..###.", ".###..###.", ".##....##.", ".##....##.", ".##....##."),
    " ": ("..........", "..........", "..........", "..........", "..........", "..........", "..........", "..........", "..........", "..........", "..........", ".........."),
}


def draw_glyph(x, y, glyph, scale, c):
    for r, row in enumerate(glyph):
        for col, ch in enumerate(row):
            if ch == "#":
                rect(x + col * scale, y + r * scale, scale, scale, c)


def text_w(s, scale, font):
    gw = 7 if font is SANS else 10
    return len(s) * (gw + 1) * scale - scale


def draw_text(x, y, s, scale, c, font=SANS, tracking=1):
    # tracking: extra blank pixels between glyphs, in units of scale
    gw = 7 if font is SANS else 10
    cx = x
    for ch in s:
        g = font.get(ch)
        if g is not None:
            draw_glyph(cx, y, g, scale, c)
        cx += (gw + tracking) * scale
    return cx


def draw_text_c(cx, y, s, scale, c, font=SANS, tracking=1):
    w = text_w(s, scale, font) + (len(s) - 1) * (tracking - 1) * scale
    return draw_text(cx - w // 2, y, s, scale, c, font, tracking)


def draw_text_bold(x, y, s, scale, c, font=SANS):
    # bold by double-strike, one pixel right
    draw_text(x, y, s, scale, c, font)
    draw_text(x + scale, y, s, scale, c, font)


# ---- globe: orthographic, centre lon 30E / lat 25N ----
GX, GY, GR = 512, 382, 138
LON0 = math.radians(30.0)
LAT0 = math.radians(25.0)


def project(lon_deg, lat_deg):
    lon = math.radians(lon_deg)
    lat = math.radians(lat_deg)
    cx = math.cos(lat) * math.sin(lon - LON0)
    cy = math.cos(LAT0) * math.sin(lat) - math.sin(LAT0) * math.cos(lat) * math.cos(lon - LON0)
    cz = math.sin(LAT0) * math.sin(lat) + math.cos(LAT0) * math.cos(lat) * math.cos(lon - LON0)
    return GX + int(cx * GR), GY - int(cy * GR), cz


AFRICA = [(-17, 15), (-10, 30), (10, 37), (20, 32), (32, 31), (35, 28), (40, 15), (43, 11), (51, 11), (48, 0), (40, -10), (35, -20), (32, -29), (25, -34), (19, -35), (15, -27), (12, -18), (9, 4), (-8, 5), (-15, 11)]
EUROPE = [(-10, 37), (-9, 43), (-2, 49), (2, 51), (5, 53), (8, 57), (11, 58), (18, 56), (21, 54), (24, 58), (28, 60), (30, 64), (32, 68), (40, 68), (44, 68), (42, 60), (40, 55), (35, 50), (30, 46), (28, 44), (23, 40), (20, 42), (15, 44), (12, 44), (8, 44), (3, 43), (-1, 46), (-2, 48), (-5, 48), (-10, 44)]
ASIA = [(30, 68), (40, 68), (50, 69), (60, 69), (70, 72), (80, 73), (90, 75), (100, 77), (110, 74), (120, 73), (130, 72), (140, 72), (150, 70), (160, 66), (162, 60), (158, 55), (150, 59), (142, 55), (140, 45), (135, 43), (130, 38), (127, 35), (122, 32), (120, 28), (115, 23), (110, 20), (108, 18), (105, 10), (103, 8), (100, 8), (98, 12), (95, 16), (92, 21), (90, 22), (88, 22), (86, 20), (82, 17), (80, 15), (77, 8), (75, 12), (72, 20), (68, 22), (65, 25), (61, 25), (58, 26), (56, 27), (52, 28), (50, 29), (48, 30), (44, 29), (40, 30), (38, 32), (36, 36), (33, 38), (30, 41), (28, 44), (30, 46)]
ARABIA = [(43, 12), (45, 17), (50, 17), (55, 17), (58, 22), (56, 26), (52, 26), (50, 29), (48, 30), (44, 29), (42, 28), (40, 25), (39, 20), (38, 17), (36, 15), (40, 13)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51)]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (49, -20), (46, -24), (44, -22)]
JAPAN = [(130, 31), (132, 33), (135, 34), (138, 35), (140, 38), (141, 41), (142, 44), (140, 44), (139, 40), (137, 37), (134, 34), (131, 32)]
INDONESIA = [(95, -2), (100, -3), (105, -6), (110, -7), (115, -8), (120, -9), (125, -9), (130, -4), (135, -3), (140, -4)]


def shade(base, lit, d):
    # d in -1..1: light factor; returns colour between dark and lit
    t = max(0.0, min(1.0, (d + 0.35) / 1.1))
    return (int(base[0] + (lit[0] - base[0]) * t),
            int(base[1] + (lit[1] - base[1]) * t),
            int(base[2] + (lit[2] - base[2]) * t))


def draw_globe():
    # atmosphere glow
    for r in range(GR + 26, GR + 4, -2):
        a = 0.05 + 0.10 * (1 - (r - GR) / 26.0)
        disc(GX, GY, r, (70, 110, 150), a * 0.5)
    # sea, per-pixel lighting: gold from upper left, midnight blue lower right
    lx, ly, lz = -0.55, -0.42, 0.72
    nl = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / nl, ly / nl, lz / nl
    landmask = {}
    for poly_ll in (AFRICA, EUROPE, ASIA, ARABIA, UK, MADAGASCAR, JAPAN):
        pts = []
        for lon, lat in poly_ll:
            x, y, z = project(lon, lat)
            if z > -0.05:
                pts.append((x, y))
        if len(pts) >= 3:
            landmask[id(pts)] = pts
    # rasterise land into a set of pixels via polygon fill on a scratch pass:
    # instead, test each globe pixel against the projected polygons with a
    # point-in-polygon check (globe is small: ~60k pixels, 7 polygons).
    def inside(x, y, pts):
        n = len(pts)
        ok = False
        j = n - 1
        for i in range(n):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y):
                if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    ok = not ok
            j = i
        return ok

    polys = list(landmask.values())
    for yy in range(GY - GR, GY + GR + 1):
        for xx in range(GX - GR, GX + GR + 1):
            dx, dy = xx - GX, yy - GY
            if dx * dx + dy * dy > GR * GR:
                continue
            dz = math.sqrt(max(0.0, GR * GR - dx * dx - dy * dy)) / GR
            nx, ny, nz = dx / GR, -dy / GR, dz
            d = nx * lx + ny * ly + nz * lz
            on_land = False
            for pts in polys:
                if inside(xx, yy, pts):
                    on_land = True
                    break
            # Indonesia dots
            if not on_land:
                for lon, lat in INDONESIA:
                    ix, iy, iz = project(lon, lat)
                    if iz > 0 and (xx - ix) ** 2 + (yy - iy) ** 2 <= 9:
                        on_land = True
                        break
            if on_land:
                put(xx, yy, shade((46, 56, 30), (178, 140, 70), d))
            else:
                put(xx, yy, shade(SEA_DK, (64, 122, 138), d))
    # terminator softening: darken the far night side rim
    for yy in range(GY - GR, GY + GR + 1):
        for xx in range(GX - GR, GX + GR + 1):
            dx, dy = xx - GX, yy - GY
            rr = dx * dx + dy * dy
            if GR * GR * 0.92 < rr <= GR * GR:
                blend(xx, yy, (8, 14, 28), 0.35)
    # rim
    for ang in range(0, 360):
        a = math.radians(ang)
        put(GX + int(GR * math.cos(a)), GY + int(GR * math.sin(a)), GOLD_LT)
        put(GX + int((GR - 1) * math.cos(a)), GY + int((GR - 1) * math.sin(a)), GOLD_LT)
    # clouds: soft white ellipses, clipped to the disc
    clouds = [(470, 320, 34, 7), (560, 300, 28, 6), (520, 420, 40, 8), (450, 430, 26, 6), (590, 450, 30, 6), (500, 350, 22, 5)]
    for cx, cy, rx, ry in clouds:
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                    if (xx - GX) ** 2 + (yy - GY) ** 2 <= (GR - 2) ** 2:
                        blend(xx, yy, (245, 244, 238), 0.28)


PINS = [
    # num, lon, lat, badge dx, badge dy (badge offset where pins cluster)
    (1, 21.0, 52.2, 0, 0),     # Warsaw
    (2, 30.5, 50.4, 16, 12),   # Kyiv (badge shifted so it clears Warsaw)
    (3, 30.7, 36.9, 0, 0),     # Antalya
    (4, 114.1, 22.5, 0, 0),    # Shenzhen
    (5, 4.3, 52.0, 0, 0),      # The Hague
    (6, -0.1, 51.5, -22, -2),  # London (badge shifted left, clears The Hague)
    (7, 12.6, 55.7, -4, -20),  # Copenhagen (badge shifted up)
    (8, 84.9, 19.3, 0, 0),     # Gopalpur
]


def ring(cx, cy, r, c):
    for ang in range(0, 360):
        a = math.radians(ang)
        put(cx + int(r * math.cos(a)), cy + int(r * math.sin(a)), c)


def draw_pins():
    for num, lon, lat, dx, dy in PINS:
        x, y, z = project(lon, lat)
        if z <= 0:
            continue
        bx, by = x + dx, y + dy
        if dx or dy:
            disc(x, y, 3, CRIMSON)
            line(x, y, bx, by, WHITE)
        disc(bx, by, 8, CRIMSON)
        ring(bx, by, 8, WHITE)
        draw_text_c(bx, by - 4, str(num), 1, WHITE)


# ---- small figures and vignettes ----
def figure(x, y, skin, suit, s=1):
    # head + torso + legs, standing, facing viewer; y = top of head
    circle(x, y + 4 * s, 4 * s, skin)
    rect(x - 5 * s, y + 9 * s, 10 * s, 12 * s, suit)
    line(x - 3 * s, y + 21 * s, x - 3 * s, y + 28 * s, suit)
    line(x + 3 * s, y + 21 * s, x + 3 * s, y + 28 * s, suit)


def flag_us(x, y, w=40, h=26):
    rect(x, y, w, h, WHITE)
    for k in range(4):
        rect(x, y + k * 6 + 1, w, 2, CRIMSON_LT)
    rect(x, y, 16, 12, NAVY3)
    for r in range(3):
        for c in range(4):
            put(x + 2 + c * 4, y + 2 + r * 4, GOLD_LT)


def flag_cn(x, y, w=40, h=26):
    rect(x, y, w, h, CRIMSON)
    disc(x + 8, y + 8, 3, GOLD)
    for dx, dy in ((16, 4), (20, 8), (20, 13), (16, 16)):
        disc(x + dx, y + dy, 2, GOLD)


def flag_ru(x, y, w=40, h=26):
    rect(x, y, w, h, WHITE)
    rect(x, y + 9, w, 9, (40, 80, 160))
    rect(x, y + 18, w, 8, CRIMSON)


def summit():
    # three flags, three small leaders at one table, tension not celebration
    for fx, fn in ((400, flag_us), (492, flag_cn), (584, flag_ru)):
        fn(fx, 128)
        vline(fx + 20, 154, 196, GOLD)
    rect(396, 196, 232, 6, (90, 64, 38))
    rect(396, 202, 232, 2, GOLD)
    figure(420, 168, (232, 196, 160), (96, 108, 138))
    figure(512, 168, (226, 188, 150), (120, 112, 100))
    figure(604, 168, (228, 192, 158), (104, 116, 128))
    for fx in (420, 512, 604):
        rect(fx - 2, 177, 4, 12, WHITE)
    draw_text_c(420, 208, "TRUMP", 1, GOLD_LT)
    draw_text_c(512, 208, "XI JINPING", 1, GOLD_LT)
    draw_text_c(604, 208, "PUTIN", 1, GOLD_LT)
    draw_text_c(512, 222, "PEACE DECLARATION - BUT NO BREAKTHROUGH ON UKRAINE OR IRAN", 1, WHITE)


def panel(x0, y0, w, h, kicker, title):
    rect(x0, y0, w, h, NAVY2)
    rect(x0, y0, w, 1, GOLD)
    rect(x0, y0 + h - 1, w, 1, GOLD)
    rect(x0, y0, 1, h, GOLD)
    rect(x0 + w - 1, y0, 1, h, GOLD)
    draw_text_bold(x0 + 10, y0 + 7, kicker, 1, GOLD_LT)
    draw_text(x0 + 10 + text_w(kicker, 1, SANS) + 12, y0 + 7, title, 1, WHITE)


def poland_scene(x0, y0, w, h):
    # Polish field, pines, a distant jet, a red missile marker
    rect(x0 + 1, y0 + 26, w - 2, h - 27, (46, 74, 48))
    rect(x0 + 1, y0 + 26, w - 2, 26, NAVY3)
    for tx in (x0 + 30, x0 + 70, x0 + 110):
        tri(tx, y0 + 78, tx - 12, y0 + 108, tx + 12, y0 + 108, (28, 52, 34))
        rect(tx - 2, y0 + 108, 4, 8, (60, 44, 28))
    # distant jet silhouette
    jx, jy = x0 + 200, y0 + 40
    poly([(jx, jy), (jx + 34, jy + 4), (jx + 34, jy + 7), (jx, jy + 8),
          (jx + 8, jy + 14), (jx + 4, jy + 6)], (200, 200, 200))
    # missile marker burst in the field
    bx, by = x0 + 210, y0 + 88
    disc(bx, by, 7, CRIMSON)
    circle(bx, by, 7, WHITE)
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        line(bx + int(10 * math.cos(a)), by + int(10 * math.sin(a)),
             bx + int(16 * math.cos(a)), by + int(16 * math.sin(a)), GOLD_LT)


def gaza_scene(x0, y0, w, h):
    # tents, a damaged home, civilians walking home with dignity
    rect(x0 + 1, y0 + 26, w - 2, h - 27, (168, 148, 112))
    rect(x0 + 1, y0 + 26, w - 2, 30, NAVY3)
    # damaged home: walls standing, roofline broken
    hx, hy = x0 + 150, y0 + 62
    poly([(hx, hy + 40), (hx, hy + 8), (hx + 14, hy), (hx + 22, hy + 10),
          (hx + 34, hy + 2), (hx + 48, hy + 12), (hx + 48, hy + 40)], (196, 178, 140))
    rect(hx + 18, hy + 22, 12, 18, (60, 52, 40))
    # tents
    for tx in (x0 + 30, x0 + 80):
        tri(tx, y0 + 70, tx - 22, y0 + 106, tx + 22, y0 + 106, (226, 210, 170))
        line(tx - 22, y0 + 106, tx, y0 + 70, (120, 100, 70))
        line(tx + 22, y0 + 106, tx, y0 + 70, (120, 100, 70))
    # walking figures
    figure(x0 + 210, y0 + 76, (198, 164, 128), (70, 64, 58))
    figure(x0 + 240, y0 + 80, (210, 178, 140), (88, 80, 66))
    figure(x0 + 262, y0 + 84, (190, 156, 120), (60, 56, 50))


def icj_scene(x0, y0, w, h):
    # Peace Palace: pediment, columns, steps; scales of justice
    rect(x0 + 1, y0 + 26, w - 2, h - 27, (52, 66, 92))
    rect(x0 + 1, y0 + 26, w - 2, 22, NAVY3)
    px0, py = x0 + 55, y0 + 52
    tri(px0, py, px0 + 90, py, px0 + 45, py - 16, GOLD)
    rect(px0, py, 90, 6, (232, 224, 200))
    for cx in range(4):
        rect(px0 + 8 + cx * 22, py + 6, 8, 34, (232, 224, 200))
    rect(px0 - 6, py + 40, 102, 4, (232, 224, 200))
    rect(px0 - 12, py + 44, 114, 4, (200, 190, 160))
    # scales of justice, small, right of the palace
    sx, sy = x0 + 230, y0 + 78
    vline(sx, sy - 14, sy + 14, GOLD_LT)
    hline(sx - 14, sx + 14, sy - 14, GOLD_LT)
    line(sx - 14, sy - 14, sx - 18, sy + 2, GOLD_LT)
    line(sx + 14, sy - 14, sx + 18, sy + 2, GOLD_LT)
    tri(sx - 24, sy + 2, sx - 12, sy + 2, sx - 18, sy + 10, GOLD)
    tri(sx + 12, sy + 2, sx + 24, sy + 2, sx + 18, sy + 10, GOLD)
    rect(sx - 8, sy + 14, 16, 3, GOLD_LT)


def market_scene(x0, y0, w, h):
    # falling chart, semiconductor traces, server racks
    rect(x0 + 1, y0 + 26, w - 2, h - 27, (20, 24, 34))
    for gy in range(y0 + 34, y0 + h - 8, 14):
        for gx in range(x0 + 8, x0 + w - 8):
            if gx % 3 == 0:
                put(gx, gy, (52, 58, 70))
    pts = [(x0 + 12, y0 + 40), (x0 + 60, y0 + 52), (x0 + 108, y0 + 48),
           (x0 + 156, y0 + 66), (x0 + 204, y0 + 80), (x0 + 252, y0 + 100)]
    for a, b in zip(pts, pts[1:]):
        line(a[0], a[1], b[0], b[1], CRIMSON_LT)
        line(a[0], a[1] + 1, b[0], b[1] + 1, CRIMSON_LT)
    for p in pts:
        disc(p[0], p[1], 3, CRIMSON_LT)
    # circuit traces, lower left
    cy = y0 + h - 22
    line(x0 + 12, cy, x0 + 60, cy, GOLD)
    line(x0 + 60, cy, x0 + 60, cy - 10, GOLD)
    line(x0 + 60, cy - 10, x0 + 110, cy - 10, GOLD)
    for cx in (x0 + 12, x0 + 60, x0 + 110):
        disc(cx, cy if cx == x0 + 12 else cy - 10, 2, GOLD)
    # server racks, right
    for rx in range(3):
        sx = x0 + 190 + rx * 30
        rect(sx, y0 + 44, 24, 52, (36, 44, 60))
        for ry in range(4):
            put(sx + 5, y0 + 50 + ry * 12, (90, 220, 120))
            put(sx + 18, y0 + 50 + ry * 12, GOLD_LT)


# ---- the 30 stories: (kicker, rest) ----
STORIES = [
    ("01 POLAND", "MISSILES LAND, NATO ANSWERS"),
    ("02 RUTTE", "NATO CHIEF FLIES TO WARSAW"),
    ("03 UK-EU", "FOOD, YOUTH, CARBON DEALS"),
    ("04 DENMARK", "EXPELS RUSSIAN ATTACHE"),
    ("05 ITALY", "GENERAL STRIKE HITS ROME"),
    ("06 DRILL", "11-NATION EXERCISE IN POLAND"),
    ("07 KYIV", "110+ MISSILES, 3 BRIDGES HIT"),
    ("08 KERCH", "CRIMEA BRIDGE WRECKED"),
    ("09 PEACE", "KUSHNER: NATO-LIKE GUARANTEES"),
    ("10 MOSCOW", "REJECTS NATO-LIKE STATUS"),
    ("11 EU AID", "EUR 7.9BN TO KYIV, RECORD"),
    ("12 SHENZHEN", "TRUMP, XI, PUTIN MEET"),
    ("13 TOKYO", "TRUMP BRIEFS TAKAICHI"),
    ("14 ICJ", "MYANMAR GUILTY, 9-6"),
    ("15 ROHINGYA", "10,000 TO BE RESETTLED"),
    ("16 COP31", "OVERTIME, NO FOSSIL FUELS"),
    ("17 CLIMATE", "OCTOBER 1.8C ABOVE NORM"),
    ("18 WALL ST", "S&P, DOW IN CORRECTION"),
    ("19 NASDAQ", "-5.3%, WORST WEEK SINCE 2020"),
    ("20 NVIDIA", "-14% AS CEO HUANG DEPARTS"),
    ("21 ANTHROPIC", "-8.5% AFTER RECORD IPO"),
    ("22 VIX", "FEAR GAUGE AT 35.89"),
    ("23 MONGOLIA", "PRESIDENT QUITS, VOTE DUE"),
    ("24 AKVAN", "CYCLONE LANDS, 300,000 OUT"),
    ("25 GAZA", "GROUND OPERATION ENDS"),
    ("26 GUPTA", "JAILED 235 MONTHS IN PLOT"),
    ("27 RIYADH", "HOUTHI HIT DAMAGES TOWER"),
    ("28 ANDROMEDA", "FIRST LOOK AT STAR MERGER"),
    ("29 PETE ROSE", "TRUMP PARDONS ROSE"),
    ("30 GENOA", "DRONE SHUTS AIRPORT 4H"),
]


def build():
    rect(0, 0, W, H, IVORY)
    # ---- newspaper header ----
    draw_text_c(512, 12, "WORLD NEWS", 5, NAVY, SERIF, tracking=2)
    draw_text_c(512, 80, "SATURDAY, 21 NOVEMBER 2026", 2, INK, SANS, tracking=2)
    rect(28, 102, 968, 4, GOLD)
    rect(28, 109, 968, 1, NAVY)
    # ---- central navy illustration field ----
    rect(28, 116, 968, 428, NAVY)
    rect(28, 116, 968, 2, GOLD)
    rect(28, 542, 968, 2, GOLD)
    summit()
    draw_globe()
    draw_pins()
    # side vignettes, flanking the globe
    panel(40, 284, 290, 116, "POLAND", "SECURITY")
    poland_scene(40, 284, 290, 116)
    panel(40, 414, 290, 116, "GAZA", "CIVILIANS RETURN")
    gaza_scene(40, 414, 290, 116)
    panel(694, 284, 290, 116, "MARKETS", "TECH SELLS OFF")
    market_scene(694, 284, 290, 116)
    panel(694, 414, 290, 116, "THE HAGUE", "JUSTICE")
    icj_scene(694, 414, 290, 116)
    # ---- hero band ----
    rect(28, 552, 968, 58, NAVY2)
    rect(28, 552, 968, 1, GOLD)
    rect(28, 609, 968, 1, GOLD)
    draw_text_c(512, 560, "MISSILES LAND IN POLAND", 3, WHITE, SERIF, tracking=1)
    draw_text_c(512, 600, "RUTTE TO WARSAW - COP31 IN OVERTIME - WALL STREET IN CORRECTION", 1, GOLD_LT)
    # ---- DATE CHECK strip ----
    rect(28, 618, 968, 36, CRIMSON)
    draw_text_c(512, 624, "DATE CHECK - SHENZHEN SUMMIT AND ICJ RULING WERE 19 NOV, NOT 21 NOV.", 1, WHITE)
    draw_text_c(512, 638, "EVERY OTHER STORY HERE HAPPENED OR WAS FIRST REPORTED 20-21 NOV.", 1, WHITE)
    # ---- ALSO TODAY grid: 30 stories, 3 columns x 10 rows ----
    draw_text(28, 664, "ALSO TODAY", 2, NAVY)
    draw_text(1024 - 28 - text_w("30 STORIES - 6 REGIONS - SOURCES: REUTERS, AP, NYT, WSJ", 1, SANS), 670,
              "30 STORIES - 6 REGIONS - SOURCES: REUTERS, AP, NYT, WSJ", 1, GREY)
    rect(28, 688, 968, 2, GOLD)
    for r in range(10):
        y = 696 + r * 26
        for col in range(3):
            idx = r + col * 10
            kicker, rest = STORIES[idx]
            x = 28 + col * 324
            draw_text_bold(x, y, kicker, 1, (140, 110, 40))
            draw_text(x + text_w(kicker, 1, SANS) + 10, y, rest, 1, INK)
    # ---- bottom headline ----
    rect(28, 956, 968, 1, NAVY)
    draw_text_c(512, 964, "THE WORLD AT A CROSSROADS", 3, NAVY, SERIF, tracking=1)


def main():
    build()
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "entry.png")
    n = write_png(path, W, H, px)
    print(f"wrote {path} {n} bytes")


if __name__ == "__main__":
    main()
