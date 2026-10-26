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
D = 2600                                 # back wall depth
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

# ---- room shell ----
sh = Layer('shell', depth=1.0)
c = [P(0, CEIL, D), P(W, CEIL, D), P(W, H, D), P(0, H, D)]    # back wall
sh.line(c, 2.2, closed=True)
for (x, y) in [(0, CEIL), (W, CEIL), (W, H), (0, H)]:             # the four receding edges
    sh.line([P(x, y, 0), P(x, y, D)], 2.2)
for z in range(400, D, 400):                                     # floor boards, faint
    sh.line([P(0, H, z), P(W, H, z)], 1.0, op=.25, double=False)
for x in range(300, W, 300):
    sh.line([P(x, H, 0), P(x, H, D)], 1.0, op=.18, double=False)
# baseboard shadow hatch along the left and right floor edges
sh.hatch([P(0, H, 0), P(0, H, D), P(0, H - 60, D), P(0, H - 60, 0)], angle=60, gap=22, op=.18)
# rugs: a big one mid-room, a small one by the reading chair; fringe on the short ends
def rug(x0, x1, z0, z1, fringe=True):
    sh.line([P(x0, H, z0), P(x1, H, z0), P(x1, H, z1), P(x0, H, z1)], 1.6, closed=True)
    sh.line([P(x0 + 40, H, z0 + 40), P(x1 - 40, H, z0 + 40), P(x1 - 40, H, z1 - 40), P(x0 + 40, H, z1 - 40)], 1.0, op=.45, closed=True, double=False)
    if fringe:
        x = x0 + 20
        while x < x1:
            sh.line([P(x, H, z0), P(x, H, z0 - 28)], .9, op=.45, double=False)
            sh.line([P(x, H, z1), P(x, H, z1 + 28)], .9, op=.45, double=False)
            x += 34
rug(520, 1700, 700, 1900)
rug(1740, 2360, 720, 1300, fringe=False)
layers.append(sh)

# ---- 1. desk and monitors (left wall, near) ----
st = Layer('st-monitors', 'Projects', '#projects', depth=1.08)
box(st, 0, 330, 975, 1350, 150, 1150)                                   # desk, pulled toward the viewer
box(st, 60, 300, 1000, 1350, 900, 1120, w=1.2)                         # tower under the desk, at the far end
st.line([P(110, 1070, 920), P(250, 1070, 920), P(250, 1210, 920), P(110, 1210, 920)], 1.2, closed=True)  # fan grille
wall_rect(st, 'L', 300, 1000, 640, 940, w=2.2)                          # wide monitor, faces into the room
st.line([P(0, 930, 640), P(0, 985, 640)], 1.6)                          # stand
st.line([P(0, 985, 520), P(0, 985, 760)], 1.6)
wall_rect(st, 'L', 1040, 1140, 760, 940, w=1.4)                         # small second screen
st.line([P(40, 985, 340), P(300, 985, 340), P(300, 985, 460), P(40, 985, 460)], 1.4, closed=True)   # keyboard
st.line([P(230, 985, 520), P(290, 985, 520), P(290, 985, 580), P(230, 985, 580)], 1.2, closed=True) # mouse
st.hatch([P(0, 640, 300), P(0, 640, 1000), P(0, 940, 1000), P(0, 940, 300)], angle=20, gap=30, op=.12)  # screen tone
layers.append(st)

# ---- 2. guitar wall (left wall, far) ----
st = Layer('st-guitars', 'Music', '#about', depth=1.0)
def guitar_on_left_wall(zc, yc, scale=1.0):
    # body as a rounded outline in the wall plane (z across, y down), neck straight up
    pts = []
    for t in range(0, 360, 12):
        a = math.radians(t)
        r = 150 * scale * (1 + .18 * math.cos(2 * a) - .08 * math.cos(a))
        pts.append(P(0, yc + r * math.sin(a) * 1.15, zc + r * math.cos(a) * .85))
    st.line(pts, 1.8, closed=True)
    st.line([P(0, yc - 150 * scale, zc), P(0, yc - 560 * scale, zc)], 1.6)
    st.line([P(0, yc - 150 * scale, zc + 34), P(0, yc - 560 * scale, zc + 34)], 1.6)
    st.line([P(0, yc - 560 * scale, zc - 10), P(0, yc - 640 * scale, zc - 10), P(0, yc - 640 * scale, zc + 44), P(0, yc - 560 * scale, zc + 44)], 1.4, closed=True)
    st.line([P(0, yc - 20, zc - 30), P(0, yc - 20, zc + 70)], 1.2)      # bridge
    st.line([P(0, yc + 6, zc - 8), P(0, yc + 6, zc + 6)], 1.2)
for zc, yc, s in ((1380, 760, .95), (1720, 740, 1.0), (2060, 770, .9)):
    guitar_on_left_wall(zc, yc, s)
    st.line([P(0, yc - 700 * s, zc + 17), P(0, yc - 740 * s, zc + 17)], 1.6)   # hanger
box(st, 0, 260, 1120, 1350, 1520, 1920, w=1.6)                            # small amp under the guitars
st.hatch([P(0, 1150, 1540), P(0, 1150, 1900), P(0, 1320, 1900), P(0, 1320, 1540)], angle=90, gap=18, op=.2)
layers.append(st)

# ---- 3. workbench with the open guitar (back wall, centre), and 4. watch corner ----
bench = Layer('st-bench', 'Builds', '#projects', depth=1.05)
box(bench, 365, 1565, 975, 1350, 2240, D)                               # bench, centred between the corner and the door
for x in (405, 1525):                                                   # legs
    bench.line([P(x, 1000, 2250), P(x, 1350, 2250)], 1.6)
# blueprint sheet on the bench, then the guitar body on top of it
bench.line([P(565, 975, 2290), P(1225, 975, 2270), P(1245, 975, 2560), P(585, 975, 2580)], 1.3, closed=True)
for k in range(5):
    bench.line([P(605 + k * 120, 975, 2300), P(610 + k * 120, 975, 2540)], .9, op=.3, double=False)
gpts = []
for t in range(0, 360, 10):
    a = math.radians(t); r = 185 * (1 + .2 * math.cos(2 * a) - .1 * math.cos(a))
    gpts.append(P(855 + r * math.cos(a) * 1.25, 975, 2420 + r * math.sin(a) * .62))
bench.line(gpts, 2.0, closed=True)
bench.line([P(1035, 975, 2400), P(1505, 975, 2385), P(1505, 975, 2425), P(1035, 975, 2440)], 1.6, closed=True)  # neck
bench.line([P(795, 975, 2440), P(915, 975, 2440), P(915, 975, 2500), P(795, 975, 2500)], 1.3, closed=True)   # control cavity
bench.line([P(805, 975, 2360), P(885, 975, 2360)], 1.3)                                                       # pickup rout
bench.line([P(505, 975, 2300), P(565, 975, 2300), P(565, 975, 2360), P(505, 975, 2360)], 1.3, closed=True)     # meter
bench.line([P(565, 975, 2330), P(805, 975, 2460)], 1.0, op=.5)                                                 # probe lead
layers.append(bench)

st = Layer('st-watch', 'Watches', '#now', depth=1.05)
for i, (x0, x1) in enumerate(((1285, 1385), (1405, 1505), (1525, 1625))):   # three covered trays
    box(st, x0, x1, 945, 975, 2300, 2400, w=1.4)
    st.line([P(x0 + 10, 945, 2320), P(x1 - 10, 945, 2320)], 1.0, op=.5)
st.line([P(1305, 975, 2470), P(1365, 975, 2470)], 1.6)                     # loupe
st.line([P(1335 + 22 * math.cos(math.radians(t)), 975, 2500 + 22 * math.sin(math.radians(t)) * .6) for t in range(0, 361, 30)], 1.4)
for k in range(4):                                                         # oilers in a block
    st.line([P(1415 + k * 18, 975, 2480), P(1415 + k * 18, 940, 2480)], 1.2)
st.line([P(1405, 975, 2470), P(1485, 975, 2470), P(1485, 975, 2500), P(1405, 975, 2500)], 1.2, closed=True)
st.line([P(1525 + 40 * math.cos(math.radians(t)), 975, 2520 + 40 * math.sin(math.radians(t)) * .6) for t in range(0, 361, 30)], 1.3)  # palette
box(st, 1595, 1625, 925, 975, 2500, 2530, w=1.2)                           # medium bottle
st.line([P(1505, 975, 2560), P(1565, 975, 2580)], 1.1)                     # two brushes
st.line([P(1505, 975, 2575), P(1567, 975, 2592)], 1.1)
layers.append(st)

# ---- 5. doorway to the studio (back wall, right) ----
st = Layer('st-door', 'Studio', '#about', depth=.96)
wall_rect(st, 'B', 1930, 2290, 250, 1350, w=2.4)
st.line([P(1930, 250, D), P(1930, 250, D + 240), P(1930, 1350, D + 240)], 1.6, op=.6)   # jamb depth
# through the door: a kit in silhouette, a mic stand, the drape edge
kz = D + 900
st.line([P(2110 + 70 * math.cos(math.radians(t)), 1040 + 70 * math.sin(math.radians(t)), kz) for t in range(0, 361, 20)], 1.4, op=.6)   # kick
st.line([P(2060 + 42 * math.cos(math.radians(t)), 900 + 30 * math.sin(math.radians(t)), kz) for t in range(0, 361, 30)], 1.2, op=.6)    # tom
st.line([P(2180 + 55 * math.cos(math.radians(t)), 820 + 14 * math.sin(math.radians(t)), kz) for t in range(0, 361, 30)], 1.2, op=.6)    # cymbal
st.line([P(2180, 820, kz), P(2180, 1130, kz)], 1.0, op=.5)
st.line([P(1990, 700, kz - 300), P(1990, 1150, kz - 300)], 1.2, op=.6)   # mic stand
st.line([P(1975, 690, kz - 300), P(2005, 690, kz - 300)], 1.4, op=.6)
st.hatch([P(1930, 250, D), P(2290, 250, D), P(2290, 1350, D), P(1930, 1350, D)], angle=75, gap=26, op=.1)   # the dark beyond
# light spilling onto the floor
st.line([P(1930, 1350, D), P(1760, 1350, D - 700), P(2460, 1350, D - 700), P(2290, 1350, D)], 1.0, op=.3, double=False)
layers.append(st)

# ---- 6. bookshelf (right wall, near) ----
st = Layer('st-books', 'Reading', '#now', depth=1.08)
wall_rect(st, 'R', 120, 880, 330, 1350, w=2.2)
for y in (520, 700, 880, 1060, 1240):
    st.line([P(W, y, 120), P(W, y, 880)], 1.6)
    st.line([P(W, y, 120), P(W - 240, y, 120)], 1.0, op=.4)             # shelf depth hint at the near end
for y0 in (520, 700, 880, 1060):
    z = 140
    while z < 850:
        wdt = random.uniform(22, 48); hgt = random.uniform(120, 165)
        st.line([P(W, y0 + 180 - hgt, z), P(W, y0 + 180 - hgt, z + wdt), P(W, y0 + 180, z + wdt)], 1.1, op=.55, double=False)
        z += wdt + random.uniform(2, 8)
st.hatch([P(W, 330, 120), P(W, 330, 160), P(W, 1350, 160), P(W, 1350, 120)], angle=0, gap=16, op=.15)
layers.append(st)

# ---- 7. gallery wall (right wall, far) ----
st = Layer('st-gallery', 'Sketchbook', '#sketchbook', depth=1.0)
frames = [(980, 1220, 330, 560), (1260, 1400, 360, 480), (1260, 1400, 510, 640), (1440, 1760, 300, 540), (990, 1180, 600, 760), (1440, 1600, 580, 700), (1640, 1760, 580, 760), (1800, 2000, 380, 640)]
for z0, z1, y0, y1 in frames:
    wall_rect(st, 'R', z0, z1, y0, y1, w=1.8)
    wall_rect(st, 'R', z0 + 14, z1 - 14, y0 + 14, y1 - 14, w=1.0, op=.5, double=False)
    st.hatch([P(W, y0, z0), P(W, y0, z1), P(W, y0 + 12, z1), P(W, y0 + 12, z0)], angle=0, gap=6, op=.2)   # frame top shadow
st.line([P(2230, 1120, 960), P(2230, 1320, 960), P(2380, 1320, 960), P(2380, 1120, 960)], 1.2, closed=True)  # record crate on the floor by the shelf
for k in range(8):
    st.line([P(2240 + k * 17, 1125, 965), P(2240 + k * 17, 1310, 965)], .9, op=.4, double=False)
layers.append(st)


# ---- seating: a reading chair on the small rug, angled toward the room, and a floor lamp ----
st = Layer('furniture', depth=1.04)
def chair(cx, cz, w=340, d=340, seat=1060, back=760, arm=940):
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2
    box(st, x0, x1, seat, 1350, z0, z1, w=1.6)                                    # seat block
    box(st, x0, x0 + 70, arm, 1350, z0, z1, w=1.4)                                 # left arm
    box(st, x1 - 70, x1, arm, 1350, z0, z1, w=1.4)                                 # right arm
    box(st, x0, x1, back, arm, z1 - 90, z1, w=1.6)                                 # back cushion
    st.line([P(x0 + 30, seat, z0 + 30), P(x1 - 30, seat, z0 + 30), P(x1 - 30, seat, z1 - 110), P(x0 + 30, seat, z1 - 110)], 1.0, op=.5, closed=True, double=False)
    st.hatch([P(x0, arm, z1 - 90), P(x1, arm, z1 - 90), P(x1, back, z1 - 90), P(x0, back, z1 - 90)], angle=15, gap=20, op=.12)
chair(2060, 1010, w=310, d=310)
# floor lamp beside the chair
st.line([P(2290, 1350, 1320), P(2290, 560, 1320)], 1.6)
st.line([P(2290 + 40 * math.cos(math.radians(t)), 1345, 1320 + 40 * math.sin(math.radians(t)) * .5) for t in range(0, 361, 30)], 1.3)
st.line([P(2200, 560, 1320), P(2380, 560, 1320), P(2350, 420, 1320), P(2230, 420, 1320)], 1.6, closed=True)   # shade
# a low table in front of the chair with a mug and an open book
box(st, 1950, 2170, 1180, 1350, 560, 720, w=1.4)
st.line([P(1990, 1180, 600), P(2050, 1180, 600), P(2050, 1180, 660), P(1990, 1180, 660)], 1.1, closed=True)
st.line([P(2080, 1180, 590), P(2150, 1180, 590), P(2150, 1180, 690), P(2080, 1180, 690)], 1.1, closed=True)
st.line([P(2115, 1180, 590), P(2115, 1180, 690)], 1.0, op=.5)
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
