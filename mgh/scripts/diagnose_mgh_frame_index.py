import csv
import hashlib
import io
import json
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace / 'outputs/MGH_Project/localization'))
import mgh_localizer as localizer
import cv2
import numpy as np
from PIL import Image

output = workspace / 'outputs/MGH_Project/localization/frame_index_diagnostic'
output.mkdir(exist_ok=True)
if (output / 'results.json').exists():
    raise RuntimeError('Preserve the completed frame-index diagnostic.')
with localizer.source_archive() as (archive, source_sha256):
    poses = list(csv.DictReader(io.StringIO(archive.read('b9dca4993d/odometry.csv').decode()), skipinitialspace=True))
video = workspace / 'work/localization_inputs/b9dca4993d/rgb.mp4'
requested = sorted({0, 610, 900, 2565, 3500, 4250, 7000, 7092, 8450, 9808, 10865, 11000, 14000, 14034})
capture = cv2.VideoCapture(str(video))
fps = capture.get(cv2.CAP_PROP_FPS)
targets = {}
for frame in requested:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
    success, pixels = capture.read()
    if not success:
        raise RuntimeError(f'Cannot seek/read frame {frame}')
    small = cv2.resize(pixels, (160, 120))
    targets[frame] = dict(digest=hashlib.sha256(small.tobytes()).hexdigest(), image=small, matched_ordinals=[])
capture.release()
digest_to_requested = {}
for frame, target in targets.items():
    digest_to_requested.setdefault(target['digest'], []).append(frame)
capture = cv2.VideoCapture(str(video))
actual_index = 0
same_index_differences = {}
while True:
    success, pixels = capture.read()
    if not success:
        break
    small = cv2.resize(pixels, (160, 120))
    if actual_index in targets:
        same_index_differences[actual_index] = float(np.abs(small.astype(float) - targets[actual_index]['image'].astype(float)).mean())
    digest = hashlib.sha256(small.tobytes()).hexdigest()
    for requested_frame in digest_to_requested.get(digest, []):
        targets[requested_frame]['matched_ordinals'].append(actual_index)
        image, unused_homography, unused_calibration, unused_pose, unused_size = localizer.orient_scan_image(pixels, poses[actual_index])
        Image.fromarray(image).save(output / f'corrected_requested_{requested_frame:06d}_actual_{actual_index:06d}.jpg', quality=95)
    actual_index += 1
    if actual_index % 3000 == 0:
        print(f'Checked {actual_index} sequentially decoded frames', flush=True)
capture.release()
results = [dict(requested_frame=frame, matching_actual_ordinals=target['matched_ordinals'],
    resized_decoded_rgb_sha256=target['digest'], same_ordinal_mean_absolute_rgb_difference=same_index_differences.get(frame),
    matched_pose_capture_seconds=[float(poses[index]['timestamp']) - float(poses[0]['timestamp']) for index in target['matched_ordinals']],
    requested_pose_capture_seconds=float(poses[frame]['timestamp']) - float(poses[0]['timestamp'])) for frame, target in targets.items()]
summary = dict(test='Random CAP_PROP_POS_FRAMES seek/read versus sequential decoded ordinal, compared by exact SHA-256 of resized RGB pixels',
    source_original_sha256=source_sha256, opencv_version=cv2.__version__, video_reported_average_fps=fps,
    sequential_decoded_frames=actual_index, tested_frames=len(results),
    mismatch_count=sum(row['requested_frame'] not in row['matching_actual_ordinals'] for row in results),
    fix='Decode sequentially and select by decoded ordinal before looking up same-index pose/depth/calibration.',
    scope='Confirmed for this recording/backend. Do not assume arbitrary MP4 seeking identifies acquisition frame ordinals.', results=results)
(output / 'results.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2), flush=True)
