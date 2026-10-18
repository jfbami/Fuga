# Diagnostic: align decoded-video presentation timestamps with odometry timestamps
# using the irregular dropped-frame gap pattern. Read-only; no outputs written.
import sys, io, csv, json, time
sys.path.insert(0, r'C:\Users\jfbaa\Documents\Codex\2026-10-17\hiwhat-was-the-treehacks-or-any-2\outputs\MGH_Project\localization')
import mgh_localizer as L
import numpy as np, cv2
with L.source_archive() as (archive, sha):
    rows = list(csv.DictReader(io.StringIO(archive.read(f'{L.SCAN_ID}/odometry.csv').decode()), skipinitialspace=True))
odo = np.array([float(r['timestamp']) for r in rows]); odo -= odo[0]
cap = cv2.VideoCapture(str(L.WORKSPACE / f'work/localization_inputs/{L.SCAN_ID}/rgb.mp4'))
t0 = time.monotonic(); pts = []
while cap.grab():
    pts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
pts = np.array(pts)
print('decoded', len(pts), 'secs %.1f' % (time.monotonic() - t0), 'first pts', pts[:4], 'last', pts[-2:])
dv, do = np.diff(pts), np.diff(odo)
print('video dt median %.5f, gaps>0.03: %d' % (np.median(dv), (dv > .03).sum()))
best = []
for shift in range(-5, 6):
    # hypothesis: decoded ordinal i <-> odometry row i+shift
    i = np.arange(len(pts))
    j = i + shift
    ok = (j >= 0) & (j < len(odo))
    a, b = pts[i[ok]], odo[j[ok]]
    resid = (a - a[0]) - (b - b[0])
    gap_v = np.diff(a) > .03; gap_o = np.diff(b) > .03
    agree = (gap_v == gap_o).mean()
    best.append((shift, float(np.abs(resid - np.median(resid)).max()), float(np.median(np.abs(np.diff(a) - np.diff(b)))), float(agree)))
for s in best:
    print('shift %+d  max|time residual| %.4f s  median|dt diff| %.5f  gap-pattern agreement %.5f' % s)
