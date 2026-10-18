# Diagnostic: compare pose-derived camera turning speed with the independent gyroscope (imu.csv).
import sys, io, csv, json
sys.path.insert(0, r'C:\Users\jfbaa\Documents\Codex\2026-10-17\hiwhat-was-the-treehacks-or-any-2\outputs\MGH_Project\localization')
import mgh_localizer as L
import numpy as np
with L.source_archive() as (archive, sha):
    rows = list(csv.DictReader(io.StringIO(archive.read(f'{L.SCAN_ID}/odometry.csv').decode()), skipinitialspace=True))
    imu = np.loadtxt(io.StringIO(archive.read(f'{L.SCAN_ID}/imu.csv').decode()), delimiter=',', skiprows=1)
t = np.array([float(r['timestamp']) for r in rows])
R = np.array([L.camera_pose(r)[:3, :3] for r in rows])
def speed(window):
    out = np.full(len(rows), np.nan)
    for i in range(window, len(rows) - window):
        a, b = R[i - window], R[i + window]
        out[i] = np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1))) / (t[i + window] - t[i - window])
    return out
gyro_t = imu[:, 0]; gyro = np.degrees(np.linalg.norm(imu[:, 4:7], axis=1))
print('imu rate Hz ~', 1 / np.median(np.diff(gyro_t)), 'imu span', gyro_t[0] - t[0], gyro_t[-1] - t[-1])
out = {}
for w in [1, 3, 15, 30]:
    s = speed(w)
    out[w] = s
    print('pose window +-%d rows: median %.1f p75 %.1f p90 %.1f deg/s' % (w, np.nanmedian(s), np.nanpercentile(s, 75), np.nanpercentile(s, 90)))
print('gyro |omega|: median %.1f p75 %.1f p90 %.1f deg/s' % (np.median(gyro), np.percentile(gyro, 75), np.percentile(gyro, 90)))
# gyro averaged over the same +-3-row window, at reference/query rows
g_at = np.interp(t, gyro_t, gyro)
ref_rows = [o + 1 for o in range(0, 14337, 90)]
print('at reference rows: pose(+-3) median %.1f, gyro median %.1f deg/s' % (np.nanmedian(out[3][ref_rows]), np.median(g_at[ref_rows])))
# per-segment
for lo, hi, label in [(0, 18, 'floor-3 landing'), (18, 48, 'stairs'), (48, 255, 'floor-4 corridors')]:
    m = (t - t[0] >= lo) & (t - t[0] < hi)
    print(label, 'pose(+-15) median %.1f deg/s, gyro median %.1f deg/s, fraction of time gyro >30 deg/s: %.2f' % (np.nanmedian(out[15][m]), np.median(g_at[m]), (g_at[m] > 30).mean()))
c = np.corrcoef(np.nan_to_num(out[3]), g_at)[0, 1]
print('corr pose(+-3) vs gyro', round(c, 3))
