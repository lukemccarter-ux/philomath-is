"""Garage: the wall-hung road bike becomes a mountain bike (2026-11-01, Luke: "fix back to mountain bike").

Runs on the sketched garage (after tools/sketchify.py and tools/fix_garage_v3.py).
1. Paints the ChatGPT bike out of the wall: the wall is rebuilt as a smooth plane fitted to the
   wall pixels around it, plus paper tooth, so the patch reads as untouched paper.
2. Redraws the ceiling trim line (L2) that ran behind the old bike's bars, only inside the patch.
3. Draws a hardtail mountain bike from real geometry (29er, 66 deg head angle, suspension fork,
   flat bar, dropper post, 1x drivetrain, disc rotors, knobby tyres). The side view is drawn in
   millimetres and projected onto the wall plane with a homography anchored where the old wheels
   were, so the perspective matches the room.
4. Everything is drawn in the sketch's own vocabulary: graphite multiplied over the paper, double
   pencil strokes with grain, light hatching for shade. No fills that read as ink.

Coordinates are in the 1448 x 1086 garage drawing.
Usage: python3 tools/fix_garage_bike.py sketched.png out.png
"""
import sys
import numpy as np
import cv2

src, dst = sys.argv[1], sys.argv[2]
im = cv2.imread(src, cv2.IMREAD_COLOR).astype(np.float32)
h, w = im.shape[:2]
rng = np.random.default_rng(11)
GRAPHITE = np.array([62, 70, 78], np.float32) / 255.0
SS = 3  # supersampling for the line work

# ---------------------------------------------------------------- 1. paint the old bike out
hull = [(1108, 192), (1116, 140), (1150, 128), (1215, 128), (1262, 132), (1330, 138), (1384, 122),
        (1432, 126), (1447, 150), (1447, 300), (1432, 338), (1346, 344), (1300, 345), (1262, 338),
        (1236, 354), (1190, 372), (1136, 370), (1108, 330)]
m = np.zeros((h, w), np.uint8)
cv2.fillPoly(m, [np.array(hull, np.int32)], 255)
ring = cv2.dilate(m, np.ones((25, 25), np.uint8)) & ~cv2.dilate(m, np.ones((7, 7), np.uint8))
lum = cv2.cvtColor(np.clip(im, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
ys, xs = np.nonzero(ring)
keep = lum[ys, xs] > np.percentile(lum[ys, xs], 45)          # wall only, not lines or boxes
ys, xs = ys[keep], xs[keep]
A = np.c_[xs, ys, np.ones_like(xs)].astype(np.float32)
plane = [np.linalg.lstsq(A, im[ys, xs, c], rcond=None)[0] for c in range(3)]
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
wall = np.dstack([plane[c][0] * xx + plane[c][1] * yy + plane[c][2] for c in range(3)])
tooth = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.0)
wall = wall * (1 + 0.018 * tooth[..., None])
mf = cv2.GaussianBlur(m.astype(np.float32) / 255.0, (0, 0), 1.6)[..., None]
im = im * (1 - mf) + wall * mf

# ---------------------------------------------------------------- drawing helpers (supersampled ink layer)
ink = np.zeros((h * SS, w * SS), np.float32)

def P(pts):
    return np.round(np.asarray(pts, np.float32) * SS).astype(np.int32).reshape(-1, 1, 2)

def stroke(pts, weight=1.5, strength=0.8, closed=False, double=True, layer=None):
    """A pencil stroke: a main line plus a lighter second pass a hair off, both antialiased."""
    L = ink if layer is None else layer
    tmp = np.zeros_like(L)
    cv2.polylines(tmp, [P(pts)], closed, 1.0, max(1, int(round(weight * SS))), cv2.LINE_AA)
    if double:
        off = np.asarray(pts, np.float32) + np.array([0.45, 0.55], np.float32)
        cv2.polylines(tmp, [P(off)], closed, 0.45, max(1, int(round(weight * SS * 0.55))), cv2.LINE_AA)
    np.maximum(L, np.clip(tmp, 0, 1) * strength, out=L)

def fill(pts, strength):
    tmp = np.zeros_like(ink)
    cv2.fillPoly(tmp, [P(pts)], 1.0, cv2.LINE_AA)
    np.maximum(ink, tmp * strength, out=ink)

def hatch(pts, strength=0.3, angle=-55, period=3.6, width=0.45):
    tmp = np.zeros_like(ink)
    cv2.fillPoly(tmp, [P(pts)], 1.0, cv2.LINE_AA)
    Y, X = np.mgrid[0:h * SS, 0:w * SS].astype(np.float32) / SS
    t = np.cos(np.radians(angle)) * X + np.sin(np.radians(angle)) * Y
    lines = np.clip((np.cos(t * 2 * np.pi / period) - (1 - width)) / width, 0, 1)
    np.maximum(ink, tmp * lines * strength, out=ink)

# ---------------------------------------------------------------- 2. the trim line behind the old bars
trim = np.zeros_like(ink)
stroke([(1018, 206), (1447, 50)], weight=2.3, strength=0.95, layer=trim)

# ---------------------------------------------------------------- 3. the bike, side view in mm (y up, origin = bottom bracket)
R_TYRE, R_CASING, R_RIM_OUT, R_RIM_IN = 371, 340, 311, 292
REAR, FRONT = np.array([-431.0, 60.0]), np.array([749.0, 60.0])
side = np.float32([[REAR[0], REAR[1] + R_TYRE], [REAR[0], REAR[1] - R_TYRE],
                   [FRONT[0], FRONT[1] + R_TYRE], [FRONT[0], FRONT[1] - R_TYRE]])
# where the old wheels sat on the wall (top and bottom of each tyre), so the bike keeps the composition
wallpts = np.float32([[1170, 214], [1170, 364], [1356, 160], [1356, 334]])
H = cv2.getPerspectiveTransform(side, wallpts)

def proj(pts):
    pts = np.asarray(pts, np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, H).reshape(-1, 2)

def circle(c, r, a0=0, a1=360, n=None):
    n = n or max(24, int(abs(a1 - a0) / 3))
    a = np.radians(np.linspace(a0, a1, n))
    return np.c_[c[0] + r * np.cos(a), c[1] + r * np.sin(a)]

def tube(p, q, d):
    """Outline of a tube from p to q, diameter d (mm), as its two edges."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    v = q - p; n = np.array([-v[1], v[0]]) / (np.linalg.norm(v) + 1e-9) * d / 2
    return [p + n, q + n], [p - n, q - n], [p + n, q + n, q - n, p - n]

def draw_tube(p, q, d, wgt=1.9, s=0.9, shade=0.0):
    e1, e2, poly = tube(p, q, d)
    fill(proj(poly), 0.12)
    stroke(proj(e1), wgt, s); stroke(proj(e2), wgt, s)
    if shade:
        hatch(proj(poly), shade)

BB = np.array([0.0, 0.0])
ST_TOP = BB + 420 * np.array([-np.cos(np.radians(74)), np.sin(np.radians(74))])
HT_TOP = np.array([440.0, 600.0])
HT_DIR = np.array([np.cos(np.radians(66)), -np.sin(np.radians(66))])
HT_BOT = HT_TOP + 100 * HT_DIR
TT_SEAT = BB + 380 * np.array([-np.cos(np.radians(74)), np.sin(np.radians(74))])
SS_SEAT = BB + 355 * np.array([-np.cos(np.radians(74)), np.sin(np.radians(74))])

# wheels first (behind the frame): tyre casing shaded, knobs on the tread, rim, hub, rotor, a few spokes
for c in (REAR, FRONT):
    outer, casing, rim_o, rim_i = circle(c, R_TYRE), circle(c, R_CASING), circle(c, R_RIM_OUT), circle(c, R_RIM_IN)
    ring_poly = np.vstack([proj(outer), proj(rim_o)[::-1]])
    hatch(ring_poly, 0.5, angle=-55, period=3.0, width=0.5)
    hatch(ring_poly, 0.26, angle=35, period=3.4, width=0.45)
    stroke(proj(outer), 2.3, 0.9, closed=True)
    stroke(proj(casing), 0.9, 0.38, closed=True, double=False)
    stroke(proj(rim_o), 1.7, 0.85, closed=True)
    stroke(proj(rim_i), 1.0, 0.6, closed=True, double=False)
    for a in np.arange(0, 360, 8.0):          # knobs: the thing that says mountain bike from across the room
        a0, a1 = np.radians(a - 2.6), np.radians(a + 2.6)
        k = [c + r * np.array([np.cos(t), np.sin(t)]) for r, t in ((R_TYRE - 2, a0), (R_TYRE + 15, a0 + 0.008), (R_TYRE + 15, a1 - 0.008), (R_TYRE - 2, a1))]
        fill(proj(k), 0.86)
    for a in np.arange(0, 360, 30.0):         # spokes, light
        sp = [c + 34 * np.array([np.cos(np.radians(a)), np.sin(np.radians(a))]),
              c + R_RIM_IN * np.array([np.cos(np.radians(a + 9)), np.sin(np.radians(a + 9))])]
        stroke(proj(sp), 0.6, 0.32, double=False)
    stroke(proj(circle(c, 90)), 1.0, 0.65, closed=True)      # disc rotor
    stroke(proj(circle(c, 62)), 0.7, 0.45, closed=True, double=False)
    stroke(proj(circle(c, 22)), 1.2, 0.8, closed=True)       # hub

# drivetrain: 1x chainring, cassette, chain, derailleur, crank and flat pedal
for r in (26, 40, 54):
    stroke(proj(circle(REAR, r)), 0.8, 0.55, closed=True, double=False)
stroke(proj(circle(BB, 78)), 1.3, 0.8, closed=True)
stroke(proj(circle(BB, 66)), 0.7, 0.45, closed=True, double=False)
stroke(proj([BB + [0, 78], REAR + [0, 54]]), 0.9, 0.62)
stroke(proj([BB + [0, -78], REAR + [-20, -70], REAR + [0, -54]]), 0.9, 0.62)
der = [REAR + [-12, -40], REAR + [-30, -115], REAR + [8, -125], REAR + [16, -50]]
stroke(proj(der), 1.0, 0.72, closed=True)
crank_end = BB + 170 * np.array([np.cos(np.radians(-118)), np.sin(np.radians(-118))])
draw_tube(BB, crank_end, 30, 1.8, 0.9, shade=0.35)
ped = [crank_end + [-55, -10], crank_end + [55, -10], crank_end + [55, 12], crank_end + [-55, 12]]
stroke(proj(ped), 1.2, 0.85, closed=True)
hatch(proj(ped), 0.4)

# frame: chainstay, seatstay, seat tube, top tube, down tube (big and shaded), head tube
draw_tube(BB, REAR, 22)
draw_tube(SS_SEAT, REAR, 17)
draw_tube(BB, ST_TOP, 34)
draw_tube(HT_TOP + 0.25 * (HT_BOT - HT_TOP), TT_SEAT, 38)
draw_tube(HT_BOT + 0.2 * (HT_TOP - HT_BOT), BB + [8, 12], 58, 2.0, 0.92, shade=0.32)
draw_tube(HT_TOP + 12 * (-HT_DIR), HT_BOT, 48, 2.0, 0.92)
stroke(proj(circle(BB, 30)), 1.2, 0.8, closed=True)       # bottom bracket shell

# suspension fork: crown, stanchions, fatter lowers with the arch, down to the front axle
crown_c = HT_BOT + 20 * HT_DIR
fork_dir = (FRONT - crown_c) / np.linalg.norm(FRONT - crown_c)
crown = [crown_c + [-40, 12], crown_c + [40, -6], crown_c + [44, -26], crown_c + [-36, -10]]
stroke(proj(crown), 1.3, 0.85, closed=True)
hatch(proj(crown), 0.35)
seal = crown_c + 175 * fork_dir
draw_tube(crown_c, seal, 34)
draw_tube(seal, FRONT + 20 * fork_dir, 46, 2.0, 0.9, shade=0.3)
stroke(proj([seal + [-26, 6], seal + [26, -6]]), 1.6, 0.9)   # dust seal ring
stroke(proj([seal + [-24, 30], seal + [-60, 70], seal + [-30, 92]]), 1.0, 0.6)  # arch, behind

# cockpit: short stem, flat bar seen nearly end-on (the near end comes out toward the room), grip, lever
clamp = HT_TOP + 22 * (-HT_DIR) + np.array([48, 8])
draw_tube(HT_TOP + 22 * (-HT_DIR), clamp, 34)
cl = proj([clamp])[0]
bar_near = cl + np.array([-30.0, 13.0])   # in image px: toward the viewer, a touch lower
bar_far = cl + np.array([9.0, -4.0])
stroke([bar_far, cl, bar_near], 2.4, 0.88)
grip = [bar_near + [0.0, 0.0], bar_near + [-15.0, 6.5]]
stroke(grip, 4.2, 0.85)
stroke([bar_near + [-3, 1.5], bar_near + [-4.0, 9.5], bar_near + [-11.0, 13.0]], 1.2, 0.8)  # brake lever

# dropper post and saddle
post_top = BB + 575 * np.array([-np.cos(np.radians(74)), np.sin(np.radians(74))])
draw_tube(ST_TOP, post_top, 31, 1.8, 0.88)
stroke(proj([ST_TOP + [-18, 70], ST_TOP + [18, 74]]), 1.4, 0.85)    # dropper collar
sad = post_top + [0, 18]
saddle = [sad + [-150, 26], sad + [-20, 34], sad + [120, 18], sad + [128, 4], sad + [20, -6], sad + [-140, 4]]
stroke(proj(saddle), 1.4, 0.88, closed=True)
hatch(proj(saddle), 0.38, angle=35)
stroke(proj([sad + [-40, -6], post_top]), 1.1, 0.75)

# wall hooks: two J-hooks under the top tube carry the bike
for f in (0.32, 0.68):
    p = HT_TOP + 0.25 * (HT_BOT - HT_TOP) + f * (TT_SEAT - (HT_TOP + 0.25 * (HT_BOT - HT_TOP)))
    a = proj([p + [0, -22]])[0]
    stroke([a + [0, 0], a + [-1, 9], a + [-6, 11]], 1.6, 0.85)
    stroke([a + [-1, 9], a + [5, 14], a + [9, 13]], 1.2, 0.7)

# ---------------------------------------------------------------- 4. down-sample, add grain, composite
def down(layer):
    return cv2.resize(cv2.GaussianBlur(layer, (0, 0), SS * 0.42), (w, h), interpolation=cv2.INTER_AREA)

bike = np.clip(down(ink) * 1.32, 0, 1)            # the room's other objects carry heavier graphite
tr = down(trim) * mf[..., 0]                      # the trim line only where the old bike was painted out
inkf = np.maximum(bike, tr)
noise = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.7)
streak = cv2.blur(rng.normal(0, 1, (h, w)).astype(np.float32), (9, 1))
grain = np.clip(0.84 + 0.10 * noise + 0.07 * streak, 0.55, 1.0)
inkf = np.clip(inkf * grain, 0, 0.9)[..., None]
base = im / 255.0
out = base * (1 - inkf) + (GRAPHITE * base) * inkf
cv2.imwrite(dst, (np.clip(out, 0, 1) * 255).astype(np.uint8))
print(dst)
