"""garage-v3 (ChatGPT, 2026-11-01): take out the leaning tyre and the rug before the sketch pass.
Usage: python3 tools/fix_garage_v3.py garage-v3.png out.png
"""
import sys
import numpy as np, cv2
im = cv2.imread(sys.argv[1])
H, W = im.shape[:2]
# 1. the tyre against the wall: rebuild the wall, door frame and baseboard behind it
tyre = np.zeros((H, W), np.uint8)
cv2.ellipse(tyre, (1369, 825), (70, 84), 0, 0, 360, 255, -1)
wall_r = np.median(im[720:745, 1372:1430].reshape(-1, 3), axis=0)
wall_l = np.median(im[720:745, 1338:1360].reshape(-1, 3), axis=0)
floor = np.median(im[905:930, 1340:1440].reshape(-1, 3), axis=0)
fill = im.copy()
fill[:888, 1364:] = wall_r; fill[:888, 1300:1364] = wall_l; fill[888:, 1300:] = floor
frame_c = np.median(im[720:745, 1329:1335].reshape(-1, 3), axis=0)
for x in (1332, 1364):
    cv2.line(fill, (x, 740), (x, 888), frame_c.tolist(), 3)
cv2.line(fill, (1300, 889), (1448, 891), (frame_c * 0.9).tolist(), 2)
m = cv2.GaussianBlur(tyre.astype(np.float32) / 255, (0, 0), 2)[..., None]
im = (im * (1 - m) + fill * m).astype(np.uint8)
# 2. the rug: floor tone everywhere the rug shows outside the car and its shadow
rug = np.zeros((H, W), np.uint8)
cv2.fillPoly(rug, [np.array([(0, 852), (1422, 994), (1422, 1004), (935, 1086), (570, 1086), (0, 880)], np.int32)], 255)
car = np.zeros((H, W), np.uint8)
cv2.fillPoly(car, [np.array([(140, 560), (1185, 560), (1192, 905), (1178, 1000), (700, 1022), (505, 1006), (140, 905)], np.int32)], 255)
rug[car > 0] = 0
floor_l = np.median(im[1040:1080, 40:300].reshape(-1, 3), axis=0)
floor_r = np.median(im[1040:1080, 1150:1420].reshape(-1, 3), axis=0)
ramp = np.linspace(0, 1, W)[None, :, None]
floor_img = (floor_l * (1 - ramp) + floor_r * ramp) * np.ones((H, 1, 1))
tooth = cv2.GaussianBlur(np.random.default_rng(5).normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.2)[..., None]
floor_img = floor_img * (1 + 0.02 * tooth)
mr = cv2.GaussianBlur(rug.astype(np.float32) / 255, (0, 0), 2.5)[..., None]
im = np.clip(im * (1 - mr) + floor_img * mr, 0, 255).astype(np.uint8)
cv2.imwrite(sys.argv[2], im); print(sys.argv[2])
