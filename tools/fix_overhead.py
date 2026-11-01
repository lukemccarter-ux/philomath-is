"""Structural fixes painted onto the sketched overhead (after tools/sketchify.py).

Works in the sketch's own vocabulary: flat wash plus graphite lines, so a patch of wall
colour with paper tooth and a redrawn edge reads as part of the drawing.
Fix 1 (2026-11-01, Luke): the main entrance opened into the study. The double doors and
mat are painted out of the study's front wall; the living room's glazed front door becomes
the entrance and gets the mat.
Coordinates are in the 1448 x 1086 cutaway (cutaway-v3).

Usage: python3 tools/fix_overhead.py sketched.png out.png
"""
import sys
import numpy as np
import cv2

src, dst = sys.argv[1], sys.argv[2]
im = cv2.imread(src, cv2.IMREAD_COLOR).astype(np.float32)
h, w = im.shape[:2]
rng = np.random.default_rng(7)
GRAPHITE = np.array([62, 70, 78], np.float32)

def sample(x0, y0, x1, y1):
    return np.median(im[y0:y1, x0:x1].reshape(-1, 3), axis=0)

def fill_poly(pts, colour, feather=1.5):
    m = np.zeros((h, w), np.float32)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 1.0)
    m = cv2.GaussianBlur(m, (0, 0), feather)
    tooth = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.0)
    patch = colour[None, None, :] * (1 + 0.018 * tooth[..., None])
    im[:] = im * (1 - m[..., None]) + patch * m[..., None]

def pencil_line(p0, p1, weight=2.2, strength=0.78):
    m = np.zeros((h, w), np.float32)
    # two passes slightly apart, like a pencil line drawn twice
    cv2.line(m, tuple(map(int, p0)), tuple(map(int, p1)), 1.0, int(round(weight)), cv2.LINE_AA)
    q0 = (p0[0] + 0.6, p0[1] + 0.9); q1 = (p1[0] - 0.5, p1[1] + 0.8)
    m2 = np.zeros((h, w), np.float32)
    cv2.line(m2, tuple(map(int, q0)), tuple(map(int, q1)), 0.45, 1, cv2.LINE_AA)
    m = np.clip(m + m2, 0, 1)
    grain = np.clip(0.85 + 0.12 * cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.7), 0.5, 1)
    m = m * grain * strength
    base = im.copy()
    im[:] = base * (1 - m[..., None]) + (GRAPHITE / 255.0 * base) * m[..., None]

# --- fix 1: entrance out of the study ---
wall = sample(322, 822, 382, 858)          # plain stretch of the same front wall
ground = sample(526, 958, 560, 988)        # the landing in front of the old door
# copy the doormat before painting it out, so it can move to the living room door
mat_box = (446, 932, 532, 978)
mat = im[mat_box[1]:mat_box[3], mat_box[0]:mat_box[2]].copy()
fill_poly([(394, 840), (506, 813), (506, 950), (418, 962), (416, 880), (392, 880)], wall, 2.4)   # doors and frame, stopping short of the cap line and the bush
fill_poly([(444, 941), (524, 929), (532, 974), (450, 986)], ground, 2.0)            # the mat
pencil_line((420, 957), (506, 945), weight=2.0, strength=0.55)                       # wall base, redrawn
pencil_line((392, 837), (508, 810), weight=2.0, strength=0.6)                        # underside of the wall cap, redrawn
# mat in front of the living room's glazed door
mh, mw = mat.shape[:2]
ox, oy = 588, 958
sub = im[oy:oy + mh, ox:ox + mw]
mask = np.zeros((mh, mw), np.float32)
cv2.fillPoly(mask, [np.array([(2, 12), (mw - 8, 2), (mw - 2, 36), (8, 44)], np.int32)], 1.0)
mask = cv2.GaussianBlur(mask, (0, 0), 1.2)[..., None]
im[oy:oy + mh, ox:ox + mw] = sub * (1 - mask) + mat * mask

cv2.imwrite(dst, np.clip(im, 0, 255).astype(np.uint8))
print(dst)
