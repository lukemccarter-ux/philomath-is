"""Sketch pass: turns a polished render into a loose pencil sketch with a light wash.

Every room drawing on the site goes through this, so the set shares one hand no matter
how prettily the source was rendered. Steps:
  1. edge-preserving smoothing flattens fine texture, glossy reflections and over-rendered hatching
  2. XDoG (extended difference of Gaussians) pulls pencil line work out of the flattened image
  3. a faint wash: the flattened image, heavily desaturated and pulled toward the paper colour
  4. graphite lines multiplied over paper plus wash, with a little grain so lines read as pencil

Usage: python3 tools/sketchify.py in.png out.png [--wash 0.32] [--sat 0.35] [--detail 1.0] [--smooth 60]
  --wash   opacity of the colour wash under the lines (0 = pure pencil, 1 = full render)
  --sat    saturation kept in the wash (0 = grey, 1 = source)
  --detail line fineness: lower = fewer, bolder lines; higher = more, finer lines
  --smooth how hard step 1 flattens texture (higher = flatter, fewer reflections)
"""
import sys, argparse
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--wash', type=float, default=0.32)
ap.add_argument('--sat', type=float, default=0.35)
ap.add_argument('--detail', type=float, default=1.0)
ap.add_argument('--smooth', type=float, default=60)
ap.add_argument('--seed', type=int, default=3)
ap.add_argument('--crush', type=float, default=0.0, help='0..1: flatten tones below 0.4 so reflections inside dark paint vanish')
ap.add_argument('--eps', type=float, default=0.72, help='XDoG threshold: lower = only real edges become lines, mid-tones stay paper')
ap.add_argument('--shade', type=float, default=0.0, help='0..1: clean hatched shading from the image darkness, drawn separately from the lines')
ap.add_argument('--fill_lo', type=float, default=0.30)
ap.add_argument('--fill_hi', type=float, default=0.62)
a = ap.parse_args()
rng = np.random.default_rng(a.seed)

PAPER = np.array([235, 241, 244], np.float32) / 255.0     # BGR of #f4f1eb, the site's paper
GRAPHITE = np.array([62, 70, 78], np.float32) / 255.0     # BGR of #4e463e, warm graphite (pencil, not ink)

src = cv2.imread(a.src, cv2.IMREAD_COLOR)
h, w = src.shape[:2]

# 1. flatten: two edge-preserving passes (recursive filter) plus a light bilateral
flat = cv2.edgePreservingFilter(src, flags=1, sigma_s=a.smooth, sigma_r=0.35)
flat = cv2.edgePreservingFilter(flat, flags=1, sigma_s=a.smooth * 0.5, sigma_r=0.3)
flat = cv2.bilateralFilter(flat, 7, 40, 7)

# 2. XDoG line work on the flattened luminance
g = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
if a.crush > 0:
    T = 0.42
    g = np.where(g < T, T - (T - g) * (1 - a.crush), g)
    g = cv2.medianBlur((g * 255).astype(np.uint8), 5).astype(np.float32) / 255.0 * (a.crush > 0.5) + g * (a.crush <= 0.5)
sig = 1.15 / max(0.4, a.detail)
g1 = cv2.GaussianBlur(g, (0, 0), sig)
g2 = cv2.GaussianBlur(g, (0, 0), sig * 1.6)
p, eps, phi = 22.0, a.eps, 18.0
S = (1 + p) * g1 - p * g2
E = np.where(S >= eps, 1.0, 1.0 + np.tanh(phi * (S - eps)))
E = np.clip(E, 0, 1)
# soften the very darkest fills so big dark shapes read as hatched pencil, not ink
E = 0.18 + 0.82 * E
# drop isolated specks: anything darker than paper that is tiny and faint
ink = (1 - E)
ink = cv2.GaussianBlur(ink, (0, 0), 0.6)
ink[ink < 0.08] = 0

# large dark fills (a black car, drapes, a shadowed floor) become hatching instead of solid ink:
# a sketcher shades a big dark shape with strokes and keeps its outline crisp
fill = cv2.GaussianBlur(ink, (0, 0), 5.0)
m = np.clip((fill - a.fill_lo) / (a.fill_hi - a.fill_lo), 0, 1)
m = m * m * (3 - 2 * m)
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
P = 6.5
hatch = np.clip((np.cos((xx + yy) * 2 * np.pi / P) - 0.35) / 0.65, 0, 1)
hatch2 = np.clip((np.cos((xx - yy) * 2 * np.pi / (P * 1.15)) - 0.55) / 0.45, 0, 1)
tone = 0.30 * hatch + 0.22 * hatch2 * np.clip((fill - 0.7) / 0.3, 0, 1)
ink = ink * (1 - m) + m * np.clip(0.30 * ink + tone * (0.55 + 0.45 * fill), 0, 0.85)

# clean shading: two or three hatch levels from the smoothed darkness of the flattened image,
# so shadows read as light pencil strokes instead of mottled fill
if a.shade > 0:
    dark = 1 - cv2.GaussianBlur(cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0, (0, 0), 4.0)
    yy2, xx2 = np.mgrid[0:h, 0:w].astype(np.float32)
    def lines(angle, period, width=0.5):
        t = np.cos(np.radians(angle)) * xx2 + np.sin(np.radians(angle)) * yy2
        return np.clip((np.cos(t * 2 * np.pi / period) - (1 - width)) / width, 0, 1)
    def step(lo, hi): return np.clip((dark - lo) / (hi - lo), 0, 1)
    shading = (0.55 * lines(-55, 7.0) * step(0.30, 0.40)
             + 0.45 * lines(35, 8.0) * step(0.50, 0.60)
             + 0.35 * lines(-55, 3.5, 0.4) * step(0.70, 0.80))
    shading = cv2.GaussianBlur(shading, (0, 0), 0.5) * a.shade
    ink = np.maximum(ink, shading)

# pencil grain: modulate line strength with fine noise, a touch of directional streak
noise = rng.normal(0, 1, (h, w)).astype(np.float32)
noise = cv2.GaussianBlur(noise, (0, 0), 0.7)
streak = cv2.blur(rng.normal(0, 1, (h, w)).astype(np.float32), (9, 1))
grain = np.clip(0.82 + 0.10 * noise + 0.08 * streak, 0.55, 1.0)
ink = np.clip(ink * grain * 1.02, 0, 0.9)

# 3. wash: flattened colour, desaturated, pulled toward paper
hsv = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV).astype(np.float32)
hsv[..., 1] *= a.sat
wash = cv2.cvtColor(hsv.clip(0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255.0
wash = cv2.GaussianBlur(wash, (0, 0), 1.2)
base = PAPER * (1 - a.wash) + wash * a.wash
# keep the wash from going muddy: lift its darkest values
base = np.maximum(base, PAPER * 0.68)

# 4. graphite over paper and wash
out = base * (1 - ink[..., None]) + (GRAPHITE * base) * ink[..., None]
# paper tooth over everything
tooth = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.0)
out = out * (1 + 0.018 * tooth[..., None])
cv2.imwrite(a.dst, (np.clip(out, 0, 1) * 255).astype(np.uint8))
print(a.dst, 'wash', a.wash, 'sat', a.sat, 'detail', a.detail, 'smooth', a.smooth)
