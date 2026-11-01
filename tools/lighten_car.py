"""Garage prep before the sketch pass: turn the near-black, reflective car into a light car
whose panel lines, windows, wheels and lights carry the drawing.
Inside the car (large dark region): reflections are clamped to the paint tone, then the car's
tonal range is stretched up so it sits light on the paper; the bronze wheels are kept as drawn.
Usage: python3 tools/lighten_car.py garage.png out.png [--clamp 70] [--lo 0.38] [--hi 0.95]
"""
import sys, argparse
import numpy as np, cv2
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--clamp', type=float, default=55); ap.add_argument('--minlen', type=int, default=70); ap.add_argument('--glass', type=float, default=0.40); ap.add_argument('--lo', type=float, default=0.46); ap.add_argument('--hi', type=float, default=0.80)
a = ap.parse_args()
im = cv2.imread(a.src); hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
H, W = g.shape
# hand-placed silhouette of the car in garage-v2 (1448 x 1086); wheels and headlights are kept as drawn
CAR = [(200, 800), (197, 747), (215, 640), (273, 527), (320, 507), (453, 491), (693, 513), (887, 607),
       (1067, 673), (1120, 740), (1127, 800), (1107, 853), (960, 891), (627, 907), (533, 867), (240, 840)]
car = np.zeros((H, W), np.uint8); cv2.fillPoly(car, [np.array(CAR, np.int32)], 255)
keep = np.zeros((H, W), np.uint8)
cv2.ellipse(keep, (243, 767), (46, 76), 0, 0, 360, 255, -1)        # rear wheel
cv2.ellipse(keep, (607, 805), (70, 101), 0, 0, 360, 255, -1)       # front wheel
wheel = keep
inside = g[(car > 0) & (wheel == 0)]
q_lo, q_cl = np.percentile(inside, 2), np.percentile(inside, a.clamp)
gc = np.minimum(g, q_cl)                                   # reflections flattened to the paint
gc = cv2.medianBlur(gc.astype(np.uint8), 5).astype(np.float32)
# tone: only the broad forms (windows darker than the body), as an even light-to-mid grey
broad = cv2.GaussianBlur(gc, (0, 0), 10)
t = np.clip((broad - q_lo) / max(1, q_cl - q_lo), 0, 1)
light = (a.lo + (a.hi - a.lo) * t) * 255
# lines: panel gaps, window edges, handles and trim from the clamped image; lights and grille
# from the original, where they are bright detail rather than reflection
e1 = cv2.Canny(cv2.medianBlur(gc.astype(np.uint8), 9), 45, 110)
# keep only long edges (panel lines, window frames, sills); reflection outlines are short and blobby
n1, lab1, st1, _ = cv2.connectedComponentsWithStats((e1 > 0).astype(np.uint8), connectivity=8)
keep_ids = [i for i in range(1, n1) if max(st1[i, cv2.CC_STAT_WIDTH], st1[i, cv2.CC_STAT_HEIGHT]) >= a.minlen]
e1 = np.isin(lab1, keep_ids).astype(np.uint8) * 255
front = np.zeros_like(car); cv2.fillPoly(front, [np.array([(660, 690), (1125, 690), (1130, 860), (660, 860)], np.int32)], 255)
e2 = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.4).astype(np.uint8), 80, 170) * (front > 0)
edges = cv2.dilate(((e1 > 0) | (e2 > 0)).astype(np.uint8), np.ones((2, 2), np.uint8))
light = np.where(edges > 0, 0.22 * 255, light)
# the glasshouse, placed by hand: glass a step darker than the body, outlines and pillars as pencil lines
GLASS = [[(272, 606), (316, 521), (399, 509), (392, 621)],          # rear door glass and quarter
         [(405, 508), (494, 506), (556, 621), (398, 622)],          # front door glass
         [(503, 506), (700, 518), (884, 604), (577, 621)]]          # windscreen
for poly in GLASS:
    cv2.fillPoly(light, [np.array(poly, np.int32)], float(a.glass * 255))
LINES = [((400, 508), (393, 623), 3), ((316, 522), (301, 606), 2), ((500, 507), (577, 622), 3),
         ((268, 607), (560, 629), 2), ((362, 634), (358, 762), 2), ((300, 652), (536, 688), 1),
         ((290, 849), (537, 884), 2), ((577, 622), (884, 606), 2)]
for (p0, p1, wt) in LINES:
    cv2.line(light, p0, p1, 0.24 * 255, wt, cv2.LINE_AA)
for poly in GLASS:
    cv2.polylines(light, [np.array(poly, np.int32)], True, 0.26 * 255, 2, cv2.LINE_AA)
cv2.ellipse(light, (482, 611), (54, 17), -6, 0, 360, 0.26 * 255, 2, cv2.LINE_AA)      # mirror
cv2.ellipse(light, (243, 767), (64, 94), 0, 185, 355, 0.26 * 255, 2, cv2.LINE_AA)     # rear arch
cv2.ellipse(light, (607, 805), (90, 120), 0, 185, 355, 0.26 * 255, 2, cv2.LINE_AA)    # front arch
for (x, y) in ((278, 638), (381, 648)):
    cv2.line(light, (x - 13, y), (x + 13, y + 1), 0.26 * 255, 3, cv2.LINE_AA)       # door handles
light3 = np.repeat(light[..., None], 3, axis=2)
mcar = cv2.GaussianBlur(car.astype(np.float32) / 255, (0, 0), 3)[..., None]
mwh = cv2.GaussianBlur(wheel.astype(np.float32) / 255, (0, 0), 3)[..., None]
m = mcar * (1 - mwh)
out = im * (1 - m) + light3 * m
cv2.imwrite(a.dst, np.clip(out, 0, 255).astype(np.uint8)); print(a.dst, 'paint', q_lo, q_cl)
