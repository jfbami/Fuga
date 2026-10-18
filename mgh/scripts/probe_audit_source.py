import sys, io, csv, json
sys.path.insert(0, r'C:\Users\jfbaa\Documents\Codex\2026-10-17\hiwhat-was-the-treehacks-or-any-2\outputs\MGH_Project\localization')
import mgh_localizer as L
import numpy as np, cv2
from PIL import Image
with L.source_archive() as (archive, sha):
    names = archive.namelist()
    print('sha', sha, 'entries', len(names))
    tops = {}
    for n in names:
        parts = n.split('/')
        key = '/'.join(parts[:2]) if len(parts) > 2 else n
        tops[key] = tops.get(key, 0) + 1
    print(json.dumps(tops, indent=1))
    odo = archive.read(f'{L.SCAN_ID}/odometry.csv').decode().splitlines()
    print(odo[0]); print(odo[1]); print(odo[-1]); print('rows', len(odo) - 1)
    rows = list(csv.DictReader(io.StringIO('\n'.join(odo)), skipinitialspace=True))
    frames = [int(r['frame']) for r in rows]
    print('frame col == index:', frames == list(range(len(rows))), frames[:3], frames[-3:])
    ts = np.array([float(r['timestamp']) for r in rows]); d = np.diff(ts)
    print('dt median %.5f min %.5f max %.5f; gaps>0.03: %d' % (np.median(d), d.min(), d.max(), (d > .03).sum()))
    for n in names:
        if n.endswith('camera_matrix.csv') or n.endswith('imu.csv'):
            print(n, archive.read(n).decode().splitlines()[:3])
    dp = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/depth/000000.png'))))
    cf = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/confidence/000000.png'))))
    print('depth', dp.shape, dp.dtype, 'conf', cf.shape, cf.dtype, np.unique(cf))
    print('fx..', {k: rows[0][k] for k in ['fx', 'fy', 'cx', 'cy']} if 'fx' in rows[0] else 'no per-row K')
cap = cv2.VideoCapture(str(L.WORKSPACE / f'work/localization_inputs/{L.SCAN_ID}/rgb.mp4'))
print('video', cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT), cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT))
