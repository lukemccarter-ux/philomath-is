"""Place the watch items from the sketched watch desk onto the sketched guitar bench.
Both drawings come out of tools/sketchify.py with the same settings, so the items carry the same line.
Opaque items cover what is behind them; the glass dome is multiplied so the bench shows through.
Usage: python3 tools/merge_watch.py bench_sketch.png watchdesk_sketch.png out.png
"""
import sys
import numpy as np, cv2
bench = cv2.imread(sys.argv[1]).astype(np.float32); desk = cv2.imread(sys.argv[2]).astype(np.float32)
PAPER = np.array([235, 241, 244], np.float32)
GRAPHITE = np.array([62, 70, 78], np.float32)
# (name, box in the watch desk sketch, target left x, target bottom y, scale, glass)
ITEMS = [('oilers', (701, 421, 842, 558), 586, 568, 0.26, False),
         ('dome',   (359, 458, 467, 571), 626, 568, 0.27, True),
         ('holder', (634, 650, 805, 767), 659, 580, 0.27, False),
         ('loupe',  (613, 500, 672, 567), 708, 579, 0.27, False),
         ('palette',(867, 493, 1038, 575), 898, 574, 0.26, False),
         ('bottle', (1051, 435, 1105, 554), 948, 566, 0.27, False),
         ('brushes',(1134, 493, 1226, 625), 924, 577, 0.24, False)]
for name, (x0, y0, x1, y1), tx, by, s, glass in ITEMS:
    crop = desk[y0:y1, x0:x1].copy()
    ink = np.clip(1 - crop.mean(axis=2) / PAPER.mean(), 0, 1)
    lab_n, lab, st, _ = cv2.connectedComponentsWithStats((ink > 0.12).astype(np.uint8), 8)
    keep = np.zeros(ink.shape, np.uint8)
    for i in range(1, lab_n):
        x, y, w, h, area = st[i]
        if w > 0.9 * crop.shape[1] and h < 0.15 * crop.shape[0]: continue      # a sill or edge line running through
        if area < 6: continue
        keep[lab == i] = 255
    hull = np.zeros_like(keep)
    pts = cv2.findNonZero(keep)
    if pts is None: continue
    cv2.fillPoly(hull, [cv2.convexHull(pts)], 255)
    w2, h2 = max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))
    ink_k = ink * (keep > 0)
    i2 = cv2.resize(ink_k, (w2, h2), interpolation=cv2.INTER_AREA)
    # redraw at the bench's line weight: thin lines fade when scaled down, so boost and thicken them
    i2 = np.clip(i2 * 2.6, 0, 0.88)
    i2 = np.maximum(i2, cv2.dilate(i2, np.ones((2, 2), np.uint8)) * 0.9)
    hl = cv2.GaussianBlur(cv2.resize(hull, (w2, h2), interpolation=cv2.INTER_AREA).astype(np.float32) / 255, (0, 0), 0.6)
    tx0, ty0 = tx, by - h2
    reg = bench[ty0:ty0 + h2, tx0:tx0 + w2]
    if glass:
        base = reg
    else:
        top = np.median(bench[ty0 - 4:ty0 + h2, tx0 - 12:tx0 - 2].reshape(-1, 3), axis=0)   # bench-top tone beside the item
        base = reg * (1 - hl[..., None]) + top * hl[..., None]
    out = base * (1 - i2[..., None]) + (GRAPHITE * base / 255.0) * i2[..., None]
    bench[ty0:ty0 + h2, tx0:tx0 + w2] = out
cv2.imwrite(sys.argv[3], np.clip(bench, 0, 255).astype(np.uint8)); print(sys.argv[3])
