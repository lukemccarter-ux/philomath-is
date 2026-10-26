"""Workshop room: one-point perspective construction drawing with a pencil feel.

Writes img/workshop.svg (and a mirrored composition when asked). Each station is its own
<g id="st-..."> so the page can ink stations in one at a time, and so Luke can draw over
them one sheet at a time. Stations carry data-label, data-href and data-depth (parallax).

Usage: python3 tools/workshop_layout.py [--mirror] [--print] out.svg
"""
import sys, math, random

MIRROR = '--mirror' in sys.argv
PRINT = '--print' in sys.argv           # darker lines, labels and registration marks for the A3 sheet
OUT = [a for a in sys.argv[1:] if not a.startswith('--')][0] if len([a for a in sys.argv[1:] if not a.startswith('--')]) else 'img/workshop.svg'
random.seed(11)

W, H = 2400, 1350                        # picture plane in viewBox units (2 mm per unit)
VP = (1200, 560)                         # eye level, a touch high so the bench tops read
F = 1800                                 # focal length
D = 2500                                 # back wall depth (a medium residential room, not a hall)
CEIL = -260                              # ceiling plane; above the picture frame at the near end, so the room reads tall
INK = '#4a4139' if PRINT else '#5a5248'

def P(x, y, z):
    """project a 3D point: x across (0 left wall, W right wall), y down (0 ceiling, H floor), z into the room"""
    if MIRROR: x = W - x
    s = F / (F + z)
    return (VP[0] + (x - VP[0]) * s, VP[1] + (y - VP[1]) * s)

def jitter_path(pts, amp=1.4, seg=38):
    """polyline through pts with a little hand wobble, as an SVG path"""
    out = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / seg))
        nx, ny = (-(y1 - y0) / L, (x1 - x0) / L) if L else (0, 0)
        for k in range(n + 1):
            t = k / n; j = 0 if k in (0, n) else random.uniform(-amp, amp)
            out.append((x0 + (x1 - x0) * t + nx * j, y0 + (y1 - y0) * t + ny * j))
    return 'M' + ' L'.join('%.1f %.1f' % p for p in out)

class Layer:
    def __init__(self, gid, label=None, href=None, depth=1.0):
        self.gid, self.label, self.href, self.depth, self.parts = gid, label, href, depth, []
    def line(self, pts, w=2.0, op=.85, closed=False, double=True):
        d = jitter_path(pts + ([pts[0]] if closed else []))
        self.parts.append('<path d="%s" stroke-width="%.1f" opacity="%.2f"/>' % (d, w, op))
        if double:   # a second, lighter pass slightly off, the way a pencil line is really two or three lines
            d2 = jitter_path([(x + random.uniform(-2, 2), y + random.uniform(-2, 2)) for x, y in (pts + ([pts[0]] if closed else []))], amp=1.8)
            self.parts.append('<path d="%s" stroke-width="%.1f" opacity="%.2f"/>' % (d2, w * .7, op * .45))
    def hatch(self, poly, angle=45, gap=14, w=1.1, op=.35):
        """parallel hatch lines clipped to a convex-ish polygon by scanline on the rotated frame"""
        a = math.radians(angle); ca, sa = math.cos(a), math.sin(a)
        def rot(p): return (p[0] * ca + p[1] * sa, -p[0] * sa + p[1] * ca)
        def unrot(p): return (p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca)
        rp = [rot(p) for p in poly]
        v0, v1 = min(p[1] for p in rp), max(p[1] for p in rp)
        v = v0 + gap * random.uniform(.2, .9)
        while v < v1:
            xs = []
            for i in range(len(rp)):
                (ax, ay), (bx, by) = rp[i], rp[(i + 1) % len(rp)]
                if (ay <= v < by) or (by <= v < ay):
                    xs.append(ax + (bx - ax) * (v - ay) / (by - ay))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                p0, p1 = unrot((xs[i], v)), unrot((xs[i + 1], v))
                self.parts.append('<path d="%s" stroke-width="%.1f" opacity="%.2f"/>' % (jitter_path([p0, p1], amp=.8), w, op))
            v += gap * random.uniform(.85, 1.15)
    def svg(self):
        attrs = ' data-label="%s"' % self.label if self.label else ''
        attrs += ' data-href="%s"' % self.href if self.href else ''
        attrs += ' data-depth="%.2f"' % self.depth
        return '<g id="%s"%s fill="none" stroke="%s" stroke-linecap="round" stroke-linejoin="round">%s</g>' % (self.gid, attrs, INK, ''.join(self.parts))

def box(L, x0, x1, y0, y1, z0, z1, w=2.0):
    """a box on the floor or a wall: front face, top face when below eye level, inner side face"""
    f = [P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0)]
    L.line(f, w, closed=True)
    if y0 > VP[1]:  # top visible
        L.line([P(x0, y0, z0), P(x0, y0, z1), P(x1, y0, z1), P(x1, y0, z0)], w)
    cx = (x0 + x1) / 2
    if cx < VP[0] and x1 < W - 1:      # right side visible
        L.line([P(x1, y0, z0), P(x1, y0, z1), P(x1, y1, z1), P(x1, y1, z0)], w)
    elif cx > VP[0] and x0 > 1:       # left side visible
        L.line([P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)], w)

def wall_rect(L, plane, a0, a1, b0, b1, w=2.0, **k):
    """rectangle on a wall plane: 'L' (x=0, a=z, b=y), 'R' (x=W), 'B' (z=D, a=x, b=y)"""
    if plane == 'L': pts = [P(0, b0, a0), P(0, b0, a1), P(0, b1, a1), P(0, b1, a0)]
    elif plane == 'R': pts = [P(W, b0, a0), P(W, b0, a1), P(W, b1, a1), P(W, b1, a0)]
    else: pts = [P(a0, b0, D), P(a1, b0, D), P(a1, b1, D), P(a0, b1, D)]
    L.line(pts, w, closed=True, **k)
    return pts

layers = []
ell = lambda cx, cy, cz, rx, rz, n=24: [P(cx + rx * math.cos(math.radians(t)), cy, cz + rz * math.sin(math.radians(t))) for t in range(0, 361, 360 // n)]

# ---- room shell: walls, two ceiling beams, herringbone floor, rugs ----
sh = Layer('shell', depth=1.0)
sh.line([P(0, CEIL, D), P(W, CEIL, D), P(W, H, D), P(0, H, D)], 2.2, closed=True)      # back wall
for (x, y) in [(0, CEIL), (W, CEIL), (W, H), (0, H)]:                                    # receding edges
    sh.line([P(x, y, 0), P(x, y, D)], 2.2)
for z in (850, 1700):                                                                    # ceiling beams
    sh.line([P(0, CEIL, z), P(W, CEIL, z)], 1.8)
    sh.line([P(0, CEIL + 90, z), P(W, CEIL + 90, z)], 1.6)
    sh.line([P(0, CEIL, z + 110), P(W, CEIL, z + 110)], 1.2, op=.5)
    sh.hatch([P(0, CEIL, z), P(W, CEIL, z), P(W, CEIL + 90, z), P(0, CEIL + 90, z)], angle=0, gap=16, op=.1)
# herringbone floor, faint: rows of short planks at +45 and -45 in plan
PL = 150
for zr in range(100, D, PL):
    for xr in range(0, W, PL * 2):
        sh.line([P(xr, H, zr), P(xr + PL, H, zr + PL)], .9, op=.16, double=False)
        sh.line([P(xr + PL, H, zr + PL), P(xr + 2 * PL, H, zr)], .9, op=.16, double=False)
sh.hatch([P(0, H, 0), P(0, H, D), P(0, H - 50, D), P(0, H - 50, 0)], angle=60, gap=22, op=.16)   # baseboard shadow
def rug(x0, x1, z0, z1, fringe=True):
    sh.line([P(x0, H, z0), P(x1, H, z0), P(x1, H, z1), P(x0, H, z1)], 1.6, closed=True)
    sh.line([P(x0 + 40, H, z0 + 40), P(x1 - 40, H, z0 + 40), P(x1 - 40, H, z1 - 40), P(x0 + 40, H, z1 - 40)], 1.0, op=.45, closed=True, double=False)
    if fringe:
        x = x0 + 20
        while x < x1:
            sh.line([P(x, H, z0), P(x, H, z0 - 26)], .9, op=.45, double=False); sh.line([P(x, H, z1), P(x, H, z1 + 26)], .9, op=.45, double=False); x += 34
rug(1560, 2360, 1000, 1800)            # reading corner rug
rug(620, 1760, 1120, 2000, fringe=False)   # under the island
for x in (1000, 1380):                         # two pendants over the island (shell, so the island stop zooms on the island)
    sh.line([P(x, CEIL, 1500), P(x, 360, 1500)], 1.2)
    sh.line([P(x - 90, 360, 1500), P(x + 90, 360, 1500), P(x + 60, 250, 1500), P(x - 60, 250, 1500)], 1.6, closed=True)
    sh.line(ell(x, 360, 1500, 90, 30), 1.2)
layers.append(sh)

# ---- 1. desk: along the left wall, three screens in an arc on arms, the tall chair ----
st = Layer('st-monitors', 'Projects', '#projects', depth=1.08)
box(st, 0, 360, 975, 1350, 260, 1060)                                     # the desk
box(st, 0, 360, 1040, 1350, 260, 420, w=1.2)                              # drawer pedestal at the near end
st.line([P(120, 1120, 262), P(240, 1120, 262)], 1.2); st.line([P(120, 1230, 262), P(240, 1230, 262)], 1.2)   # drawer pulls
wall_rect(st, 'L', 480, 880, 640, 920, w=2.2)                             # centre screen
st.line([P(40, 640, 300), P(40, 640, 470), P(40, 920, 470), P(40, 920, 300)], 2.0, closed=True)        # left wing, toed in
st.line([P(60, 640, 890), P(130, 640, 1050), P(130, 920, 1050), P(60, 920, 890)], 2.0, closed=True)    # right wing, toed in
st.line([P(0, 975, 680), P(0, 920, 680)], 1.6)                            # arm post
for z0, z1 in ((300, 470), (480, 880), (890, 1050)):
    st.hatch([P(30, 650, z0), P(30, 650, z1), P(30, 910, z1), P(30, 910, z0)], angle=20, gap=30, op=.1)
st.line([P(60, 985, 560), P(330, 985, 560), P(330, 985, 680), P(60, 985, 680)], 1.4, closed=True)    # keyboard
st.line([P(300, 985, 760), P(350, 985, 760), P(350, 985, 820), P(300, 985, 820)], 1.2, closed=True)  # mouse
st.line([P(120, 985, 440), P(330, 985, 440), P(330, 985, 520), P(120, 985, 520)], 1.1, closed=True)  # notebook
# the chair, back to the viewer, facing the screens: tall back with a headrest, seat, five-star base
CX, CZ = 560, 700
st.line([P(CX - 110, 1130, CZ + 130), P(CX + 110, 1130, CZ + 130), P(CX + 110, 560, CZ + 120), P(CX - 110, 560, CZ + 120)], 1.8, closed=True)   # tall back
st.line([P(CX - 60, 560, CZ + 120), P(CX + 60, 560, CZ + 120), P(CX + 60, 500, CZ + 120), P(CX - 60, 500, CZ + 120)], 1.4, closed=True)       # headrest
st.line([P(CX - 130, 1130, CZ - 90), P(CX + 130, 1130, CZ - 90), P(CX + 130, 1130, CZ + 130)], 1.5)                                            # seat edge
st.line([P(CX - 130, 1130, CZ - 90), P(CX - 130, 1130, CZ + 130)], 1.5)
st.line([P(CX - 135, 1040, CZ - 60), P(CX - 135, 1040, CZ + 110)], 1.3); st.line([P(CX + 135, 1040, CZ - 60), P(CX + 135, 1040, CZ + 110)], 1.3)   # armrests
st.line([P(CX, 1170, CZ + 20), P(CX, 1300, CZ + 20)], 1.6)
for ang in range(0, 360, 72):
    st.line([P(CX, 1300, CZ + 20), P(CX + 120 * math.cos(math.radians(ang)), 1345, CZ + 20 + 110 * math.sin(math.radians(ang)))], 1.3)
st.hatch([P(CX - 110, 1130, CZ + 130), P(CX + 110, 1130, CZ + 130), P(CX + 110, 560, CZ + 120), P(CX - 110, 560, CZ + 120)], angle=80, gap=18, op=.12)
layers.append(st)

# ---- 2. guitar wall (left wall, far) ----
st = Layer('st-guitars', 'Music', '#about', depth=1.0)
def guitar_on_left_wall(zc, yc, scale=1.0):
    pts = []
    for t in range(0, 360, 12):
        a = math.radians(t); r = 150 * scale * (1 + .18 * math.cos(2 * a) - .08 * math.cos(a))
        pts.append(P(0, yc + r * math.sin(a) * 1.15, zc + r * math.cos(a) * .85))
    st.line(pts, 1.8, closed=True)
    st.line([P(0, yc - 150 * scale, zc), P(0, yc - 560 * scale, zc)], 1.6)
    st.line([P(0, yc - 150 * scale, zc + 34), P(0, yc - 560 * scale, zc + 34)], 1.6)
    st.line([P(0, yc - 560 * scale, zc - 10), P(0, yc - 640 * scale, zc - 10), P(0, yc - 640 * scale, zc + 44), P(0, yc - 560 * scale, zc + 44)], 1.4, closed=True)
    st.line([P(0, yc - 20, zc - 30), P(0, yc - 20, zc + 70)], 1.2)
for zc, yc, sc in ((1380, 700, .95), (1720, 680, 1.0), (2060, 710, .9)):
    guitar_on_left_wall(zc, yc, sc)
    st.line([P(0, yc - 700 * sc, zc + 17), P(0, yc - 740 * sc, zc + 17)], 1.6)
box(st, 0, 260, 1100, 1350, 1520, 1920, w=1.6)                            # amp
st.hatch([P(0, 1130, 1540), P(0, 1130, 1900), P(0, 1320, 1900), P(0, 1320, 1540)], angle=90, gap=18, op=.2)
layers.append(st)

# ---- 3. the island: a workbench in the middle of the room, two stools, the guitar opened up, a soldering station ----
bench = Layer('st-bench', 'Builds', '#projects', depth=1.05)
IX0, IX1, IZ0, IZ1, IT = 760, 1620, 1240, 1760, 960
box(bench, IX0, IX1, IT, 1350, IZ0, IZ1)                                   # the island
bench.line([P(IX0, IT + 60, IZ0), P(IX1, IT + 60, IZ0)], 1.2, op=.5)       # apron
box(bench, IX0 + 40, IX1 - 40, 1120, 1320, IZ0 + 30, IZ1 - 30, w=1.2)     # lower shelf
for x in (IX0 + 20, IX1 - 20):
    bench.line([P(x, IT, IZ0), P(x, 1350, IZ0)], 1.4)
# blueprint, then the guitar body and neck on top
bench.line([P(820, IT, 1290), P(1360, IT, 1270), P(1380, IT, 1640), P(840, IT, 1660)], 1.3, closed=True)
for k in range(5):
    bench.line([P(860 + k * 100, IT, 1300), P(865 + k * 100, IT, 1620)], .9, op=.3, double=False)
gpts = []
for t in range(0, 360, 10):
    a = math.radians(t); r = 170 * (1 + .2 * math.cos(2 * a) - .1 * math.cos(a))
    gpts.append(P(1060 + r * math.cos(a) * 1.25, IT, 1470 + r * math.sin(a) * .7))
bench.line(gpts, 2.0, closed=True)
bench.line([P(1230, IT, 1455), P(1600, IT, 1440), P(1600, IT, 1485), P(1230, IT, 1500)], 1.6, closed=True)   # neck
bench.line([P(1000, IT, 1500), P(1120, IT, 1500), P(1120, IT, 1560), P(1000, IT, 1560)], 1.3, closed=True)   # control cavity
bench.line([P(1010, IT, 1410), P(1090, IT, 1410)], 1.3)
# soldering station at the near-left corner: iron in its stand, a spool, a small fume fan
bench.line([P(800, IT, 1690), P(860, IT, 1690), P(860, IT, 1740), P(800, IT, 1740)], 1.3, closed=True)       # stand base
bench.line([P(830, IT, 1715), P(830, IT - 70, 1715)], 1.4); bench.line(ell(830, IT - 70, 1715, 22, 10, 12), 1.2)   # holder coil
bench.line([P(840, IT - 60, 1715), P(960, IT - 90, 1690)], 1.6)                                               # the iron
bench.line(ell(910, IT, 1710, 28, 14), 1.2); bench.line(ell(910, IT - 40, 1710, 28, 14), 1.2)                 # solder spool
bench.line([P(882, IT, 1710), P(882, IT - 40, 1710)], 1.0); bench.line([P(938, IT, 1710), P(938, IT - 40, 1710)], 1.0)
bench.line([P(990, IT, 1700), P(1060, IT, 1700), P(1060, IT - 80, 1700), P(990, IT - 80, 1700)], 1.2, closed=True)   # fume fan
# two stools on the near side
def stool(cx, cz):
    bench.line(ell(cx, 1060, cz, 70, 32), 1.6)
    for dx, dz in ((-50, -20), (50, -20), (-50, 20), (50, 20)):
        bench.line([P(cx + dx, 1060, cz + dz), P(cx + dx * 1.15, 1350, cz + dz * 1.15)], 1.3)
    bench.line([P(cx - 55, 1250, cz - 20), P(cx + 55, 1250, cz - 20)], 1.0, op=.6)
stool(960, 1900); stool(1420, 1900)
layers.append(bench)

# ---- 4. watch corner: the right end of the island ----
st = Layer('st-watch', 'Watches', '#now', depth=1.05)
for x0, x1 in ((1420, 1500), (1520, 1600)):                                 # two covered trays, stacked pair at the end
    box(st, x0, x1, IT - 28, IT, 1600, 1690, w=1.4)
    st.line([P(x0 + 8, IT - 28, 1615), P(x1 - 8, IT - 28, 1615)], 1.0, op=.5)
box(st, 1420, 1500, IT - 28, IT, 1540, 1590, w=1.3)                       # a third tray in front
st.line([P(1530, IT, 1545), P(1580, IT, 1545)], 1.6); st.line(ell(1555, IT, 1570, 20, 10, 12), 1.4)   # loupe
for k in range(4):                                                         # oilers in a block
    st.line([P(1440 + k * 16, IT, 1720), P(1440 + k * 16, IT - 36, 1720)], 1.2)
st.line([P(1430, IT, 1708), P(1500, IT, 1708), P(1500, IT, 1735), P(1430, IT, 1735)], 1.2, closed=True)
st.line(ell(1545, IT, 1725, 36, 16), 1.3)                                  # palette
box(st, 1596, 1618, IT - 46, IT, 1700, 1722, w=1.2)                        # medium bottle
st.line([P(1510, IT, 1300), P(1570, IT, 1320)], 1.1); st.line([P(1512, IT, 1315), P(1572, IT, 1335)], 1.1)   # two brushes, parked
layers.append(st)

# ---- 5. doorway to the studio (back wall, right) ----
st = Layer('st-door', 'Studio', '#about', depth=.96)
wall_rect(st, 'B', 1930, 2290, 220, 1350, w=2.4)
st.line([P(1930, 220, D), P(1930, 220, D + 240), P(1930, 1350, D + 240)], 1.6, op=.6)
kz = D + 900
st.line([P(2110 + 70 * math.cos(math.radians(t)), 1040 + 70 * math.sin(math.radians(t)), kz) for t in range(0, 361, 20)], 1.4, op=.6)
st.line([P(2060 + 42 * math.cos(math.radians(t)), 900 + 30 * math.sin(math.radians(t)), kz) for t in range(0, 361, 30)], 1.2, op=.6)
st.line([P(2180 + 55 * math.cos(math.radians(t)), 820 + 14 * math.sin(math.radians(t)), kz) for t in range(0, 361, 30)], 1.2, op=.6)
st.line([P(2180, 820, kz), P(2180, 1130, kz)], 1.0, op=.5)
st.line([P(1990, 700, kz - 300), P(1990, 1150, kz - 300)], 1.2, op=.6); st.line([P(1975, 690, kz - 300), P(2005, 690, kz - 300)], 1.4, op=.6)
st.hatch([P(1930, 220, D), P(2290, 220, D), P(2290, 1350, D), P(1930, 1350, D)], angle=75, gap=26, op=.1)
st.line([P(1930, 1350, D), P(1760, 1350, D - 600), P(2460, 1350, D - 600), P(2290, 1350, D)], 1.0, op=.3, double=False)
layers.append(st)

# ---- 6. bookshelf: floor to ceiling on the right wall, near, with cupboards below ----
st = Layer('st-books', 'Reading', '#now', depth=1.08)
wall_rect(st, 'R', 300, 1040, 40, 1350, w=2.2)
for y in (240, 440, 640, 840):
    st.line([P(W, y, 300), P(W, y, 1040)], 1.6); st.line([P(W, y, 300), P(W - 260, y, 300)], 1.0, op=.4)
st.line([P(W, 1080, 300), P(W, 1080, 1040)], 1.8)                          # counter over the cupboards
for z in (300, 550, 800, 1040):
    st.line([P(W, 1080, z), P(W, 1350, z)], 1.4)
for z in (425, 675, 920):
    st.line([P(W, 1200, z - 20), P(W, 1200, z + 20)], 1.4)                 # handles
for y0 in (40, 240, 440, 640):
    z = 320
    while z < 1010:
        wdt = random.uniform(22, 48); hgt = random.uniform(130, 175)
        st.line([P(W, y0 + 200 - hgt, z), P(W, y0 + 200 - hgt, z + wdt), P(W, y0 + 200, z + wdt)], 1.1, op=.55, double=False)
        z += wdt + random.uniform(2, 8)
st.line(ell(W - 6, 830, 960, 1, 40, 12), 1.0, op=.6)                        # a small plant pot on a shelf
st.line([P(W - 6, 830, 960), P(W - 6, 750, 930)], 1.0, op=.6); st.line([P(W - 6, 830, 960), P(W - 6, 760, 1000)], 1.0, op=.6)
st.line([P(2230, 1120, 1100), P(2230, 1320, 1100), P(2380, 1320, 1100), P(2380, 1120, 1100)], 1.2, closed=True)   # record crate
for k in range(8):
    st.line([P(2240 + k * 17, 1125, 1105), P(2240 + k * 17, 1310, 1105)], .9, op=.4, double=False)
layers.append(st)

# ---- 7. gallery wall: the back wall, left of the door, facing the viewer ----
st = Layer('st-gallery', 'Sketchbook', '#sketchbook', depth=1.0)
frames = [(260, 560, 200, 470), (610, 790, 230, 370), (610, 790, 410, 560), (840, 1200, 170, 440), (270, 500, 520, 700), (840, 1020, 490, 620), (1060, 1200, 490, 690), (1250, 1500, 260, 560), (1250, 1500, 610, 760), (1550, 1850, 300, 520), (1560, 1760, 570, 740)]
for x0, x1, y0, y1 in frames:
    wall_rect(st, 'B', x0, x1, y0, y1, w=1.8)
    wall_rect(st, 'B', x0 + 12, x1 - 12, y0 + 12, y1 - 12, w=1.0, op=.5, double=False)
    st.hatch([P(x0, y0, D), P(x1, y0, D), P(x1, y0 + 10, D), P(x0, y0 + 10, D)], angle=0, gap=6, op=.2)
st.line([P(230, 1350, D - 10), P(230, 1120, D - 10), P(1880, 1120, D - 10), P(1880, 1350, D - 10)], 1.4)   # low console under the frames
st.line([P(230, 1120, D - 10), P(230, 1120, D - 200), P(1880, 1120, D - 200), P(1880, 1120, D - 10)], 1.2)
layers.append(st)

# ---- seating: the reading corner at the near right, lamp on the wall side ----
st = Layer('furniture', depth=1.04)
def chair(cx, cz, w=320, d=320, seat=1060, back=720, arm=940):
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2
    box(st, x0, x1, seat, 1350, z0, z1, w=1.6)
    box(st, x0, x0 + 70, arm, 1350, z0, z1, w=1.4); box(st, x1 - 70, x1, arm, 1350, z0, z1, w=1.4)
    box(st, x0, x1, back, arm, z1 - 90, z1, w=1.6)
    st.line([P(x0 + 30, seat, z0 + 30), P(x1 - 30, seat, z0 + 30), P(x1 - 30, seat, z1 - 110), P(x0 + 30, seat, z1 - 110)], 1.0, op=.5, closed=True, double=False)
    st.hatch([P(x0, arm, z1 - 90), P(x1, arm, z1 - 90), P(x1, back, z1 - 90), P(x0, back, z1 - 90)], angle=15, gap=20, op=.12)
chair(2080, 1400)
st.line([P(2300, 1350, 1720), P(2300, 520, 1720)], 1.6); st.line(ell(2300, 1345, 1720, 40, 20), 1.3)          # floor lamp
st.line([P(2210, 520, 1720), P(2390, 520, 1720), P(2360, 380, 1720), P(2240, 380, 1720)], 1.6, closed=True)
box(st, 1980, 2200, 1180, 1350, 1040, 1200, w=1.4)                                                           # low table
st.line([P(2020, 1180, 1080), P(2080, 1180, 1080), P(2080, 1180, 1140), P(2020, 1180, 1140)], 1.1, closed=True)  # mug
st.line([P(2110, 1180, 1070), P(2180, 1180, 1070), P(2180, 1180, 1170), P(2110, 1180, 1170)], 1.1, closed=True)  # open book
st.line([P(2145, 1180, 1070), P(2145, 1180, 1170)], 1.0, op=.5)
layers.append(st)

# ---- assemble ----
body = ''.join(l.svg() for l in layers)
paper = ''
if PRINT:
    marks = ''
    for (x, y) in ((40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)):
        marks += '<path d="M%d %d h-24 M%d %d v-24 M%d %d h24 M%d %d v24" stroke="#999" stroke-width="1.5"/>' % (x, y, x, y, x, y, x, y)
        marks += '<circle cx="%d" cy="%d" r="10" fill="none" stroke="#999" stroke-width="1.5"/>' % (x, y)
    labels = ''
    for l in layers:
        if l.label:
            labels += '<text font-family="Arial" font-size="26" fill="#b84a1f" data-for="%s">%s</text>' % (l.gid, l.label)
    paper = '<g id="print-marks">%s</g>' % marks
    body += paper
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="The workshop, a sketch: desk and monitors, a guitar wall, a workbench with a guitar opened up, a small watch bench, a bookshelf, a gallery wall, and a doorway into the studio">%s</svg>' % (W, H, body)
open(OUT, 'w').write(svg)
print(OUT, len(svg), 'bytes;', 'mirrored' if MIRROR else 'composition A')
