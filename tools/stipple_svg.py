"""Prototype: pre-rendered vector stipple of a word, lit from the upper left.
Dots are placed once (variable-spacing Poisson disc) and written as SVG, so the browser
rasterises them at the device's own resolution. No canvas, no font race, no per-frame cost.
Usage: python3 -I stipple_svg.py <font.ttf> <word> <out.svg> [seed]
"""
import sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

font_path, word, out = sys.argv[1], sys.argv[2], sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 7
random.seed(seed); np.random.seed(seed)

FS = 400                      # mask font size in px; the SVG viewBox is in these units
TRACK = -0.045 * FS           # letter-spacing, same as the site (-.045em)
LX, LY = -0.55, -0.835        # light direction (unit vector, from the upper left; y down)
RAMP_DARK, RAMP_LIGHT = (74, 58, 46), (150, 138, 124)
NB = 6                        # tone buckets

font = ImageFont.truetype(font_path, FS)
# glyph-by-glyph so the tracking matches the CSS letter-spacing
adv = [font.getlength(ch) for ch in word]
width = int(sum(adv) + TRACK * (len(word) - 1)) + 2 * 40
height = int(FS * 1.3)
mask = Image.new("L", (width, height), 0)
d = ImageDraw.Draw(mask)
x = 40.0
asc, desc = font.getmetrics()
for ch, a in zip(word, adv):
    d.text((x, 20), ch, font=font, fill=255)
    x += a + TRACK
m = np.asarray(mask) > 128
# trim to the ink box (+ margin)
ys, xs = np.where(m)
x0, x1, y0, y1 = xs.min() - 12, xs.max() + 13, ys.min() - 12, ys.max() + 13
m = m[y0:y1, x0:x1]; H, W = m.shape

# distance to the edge (inside) and the outward normal from a blurred mask
dist = ndimage.distance_transform_edt(m)
blur = ndimage.gaussian_filter(m.astype(float), 6)
gy, gx = np.gradient(blur)
gl = np.hypot(gx, gy) + 1e-9
nx, ny = -gx / gl, -gy / gl          # outward normal
lit = nx * LX + ny * LY              # +1 facing the light, -1 in shadow
yy, xx = np.mgrid[0:H, 0:W]
v = (yy - yy[m].min()) / max(1, (yy[m].max() - yy[m].min()))   # 0 top of the word, 1 base

# tone field in [0,1], 1 = light. Near the edge the normal decides; inside, the light falls from top to base.
edge_w = np.clip(1 - dist / 28.0, 0, 1)
shade_edge = 0.5 + 0.5 * lit
shade_in = 0.25 + 0.6 * (1 - v) + 0.08 * (1 - xx / W)
shade = np.clip(edge_w * shade_edge + (1 - edge_w) * shade_in, 0, 1)

# spacing and radius fields (mask px). Lit areas: sparser, smaller dots. Shadow: denser, bigger.
S0 = FS / 50.0
spacing = S0 * (0.72 + 0.75 * shade)
radius = (S0 * 0.34) * (1.30 - 0.55 * shade)
# the outline: a ring just inside the edge, tighter spacing so the silhouette reads clean
ring = (dist > 0.5) & (dist <= S0 * 0.55)
spacing = np.where(ring, S0 * 0.62 * (0.85 + 0.35 * shade), spacing)

# variable-spacing dart throwing with a spatial hash
cell = float(spacing.min())
gw, gh = int(W / cell) + 1, int(H / cell) + 1
grid = [[] for _ in range(gw * gh)]
pts = []
def ok(px, py, sp):
    cx, cy = int(px / cell), int(py / cell)
    r = int(math.ceil(sp / cell)) + 1
    for j in range(max(0, cy - r), min(gh, cy + r + 1)):
        for i in range(max(0, cx - r), min(gw, cx + r + 1)):
            for (qx, qy, qs) in grid[j * gw + i]:
                dd = (qx - px) ** 2 + (qy - py) ** 2
                need = 0.5 * (sp + qs)
                if dd < need * need:
                    return False
    return True
inside_idx = np.flatnonzero(m)
# 1. outline first (ring pixels), 2. then interior
for sel, tries in ((np.flatnonzero(ring), 90000), (inside_idx, 260000)):
    order = np.random.choice(sel, size=min(tries, len(sel) * 4), replace=True)
    for k in order:
        py, px = divmod(int(k), W)
        px += random.random(); py += random.random()
        if not m[min(H - 1, int(py)), min(W - 1, int(px))]:
            continue
        sp = float(spacing[int(py), int(px)])
        if ok(px, py, sp):
            grid[int(py / cell) * gw + int(px / cell)].append((px, py, sp))
            pts.append((px, py))

# write SVG: one path per tone, circles as arc pairs (compact), plus a few terracotta dots on the lit edge
def tone_colour(q):
    return "rgb(%d,%d,%d)" % tuple(int(RAMP_DARK[i] + (RAMP_LIGHT[i] - RAMP_DARK[i]) * q) for i in range(3))
buckets = [[] for _ in range(NB)]
warm = []
for (px, py) in pts:
    ix, iy = min(W - 1, int(px)), min(H - 1, int(py))
    s = float(shade[iy, ix]) + random.uniform(-0.05, 0.05)
    b = min(NB - 1, max(0, int(s * NB)))
    r = float(radius[iy, ix]) * random.uniform(0.9, 1.1)
    buckets[b].append((px, py, r))
    if ring[iy, ix] and lit[iy, ix] > 0.55 and random.random() < 0.06:
        warm.append((px, py, r * 1.05))
def circ(px, py, r):
    return "M%.1f %.1fa%.2f %.2f 0 1 0 %.2f 0a%.2f %.2f 0 1 0 %.2f 0z" % (px - r, py, r, r, 2 * r, r, r, -2 * r)
parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (W, H, word)]
for b, arr in enumerate(buckets):
    if not arr: continue
    parts.append('<path fill="%s" d="%s"/>' % (tone_colour(b / (NB - 1)), "".join(circ(*c) for c in arr)))
if warm:
    parts.append('<path fill="rgba(192,94,47,.75)" d="%s"/>' % "".join(circ(*c) for c in warm))
parts.append('</svg>')
open(out, "w").write("".join(parts))
print("dots", len(pts), "viewBox", W, H, "bytes", sum(len(p) for p in parts))
