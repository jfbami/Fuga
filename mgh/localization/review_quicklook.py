"""Review private exported iPhone bursts. An alignment hypothesis never enables routing."""
import argparse
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image


def rigid(rows):
    t = np.asarray(rows, dtype=float)
    if t.shape != (4, 4) or not np.isfinite(t).all() or not np.allclose(t[3], [0, 0, 0, 1], atol=1e-4):
        raise ValueError('Invalid rigid transform dimensions/values.')
    r = t[:3, :3]
    if not np.allclose(r.T @ r, np.eye(3), atol=.01) or abs(np.linalg.det(r) - 1) >= .01:
        raise ValueError('Transform must be a rigid rotation, not scaled/reflected geometry.')
    return t


def review_bundle(bundle, expected_map_hash):
    if not isinstance(bundle, dict) or bundle.get('format') != 'MGH quick-look diagnostic v1':
        raise ValueError('Unknown capture bundle.')
    requests, responses = bundle.get('requests', []), bundle.get('responses', [])
    by_id = {r.get('request_id'): r for r in responses}
    if len(by_id) != len(responses):
        raise ValueError('Duplicate response identities.')
    ids, times, candidates, diagnostics = set(), set(), [], []
    for request in requests:
        identity = request.get('request_id')
        timestamp = request.get('capture_timestamp')
        if not isinstance(identity, str) or not identity or identity in ids or timestamp in times:
            raise ValueError('Duplicate/missing frame identity or timestamp.')
        if type(timestamp) not in {int, float} or not math.isfinite(timestamp):
            raise ValueError('Invalid frame timestamp.')
        ids.add(identity); times.add(timestamp)
        response = by_id.get(identity)
        diagnostic = dict(request_id=identity, capture_timestamp=timestamp, candidate=False)
        diagnostics.append(diagnostic)
        try:
            if request.get('session_id') != bundle.get('session_id'):
                raise ValueError('Frames belong to different capture sessions.')
            if request.get('building_id') != 'MGH' or request.get('selected_floor') != 4 or bundle.get('selected_floor') != 4:
                raise ValueError('Recognition map unavailable for this context.')
            raw = base64.b64decode(request['image_base64'], validate=True)
            k = request['intrinsics']
            with Image.open(io.BytesIO(raw)) as image:
                if image.size != (k['width'], k['height']):
                    raise ValueError('Calibration/image sizes disagree.')
            if request.get('calibration_status') != 'verified' or any(k.get('distortion', [])):
                raise ValueError('Verified undistorted calibration required.')
            if not all(type(k[x]) in {int, float} and math.isfinite(k[x]) for x in ['fx', 'fy', 'cx', 'cy']) or min(k['fx'], k['fy']) <= 0:
                raise ValueError('Invalid intrinsics.')
            metadata = request['capture_metadata']
            if metadata.get('tracking_state') != 'normal':
                raise ValueError('Capture tracking was not normal.')
            ar = rigid(metadata['arkit_world_from_image_camera_cv'])
            if not response or not response.get('accepted') or not response.get('pose_usable_for_app'):
                raise ValueError('No accepted calibrated frame pose.')
            if response.get('calibration_status') != 'verified':
                raise ValueError('Unverified response calibration.')
            if response.get('capture_timestamp') != timestamp or response.get('query_image_sha256') != hashlib.sha256(raw).hexdigest():
                raise ValueError('Response belongs to another capture/image.')
            if not expected_map_hash or response.get('map_manifest_sha256') != expected_map_hash:
                raise ValueError('Response map does not match the reviewed manifest.')
            if response.get('coordinate_frame_id') != 'scan:b9dca4993d' or response.get('building_id') != 'MGH' or response.get('selected_floor') != 4:
                raise ValueError('Response coordinate frame/context mismatch.')
            scan = np.eye(4)
            scan[:3, :3] = response['rotation_world_camera']
            scan[:3, 3] = response['position_scan_m']
            scan = rigid(scan)
            transform = scan @ np.linalg.inv(ar)
            candidates.append((identity, timestamp, transform))
            diagnostic['candidate'] = True
        except (KeyError, ValueError, TypeError) as error:
            diagnostic['reason'] = str(error)
    clusters = []
    for index, (_, _, a) in enumerate(candidates):
        support = []
        for j, (_, _, b) in enumerate(candidates):
            delta = np.linalg.inv(a) @ b
            angle = np.degrees(np.arccos(np.clip((np.trace(delta[:3, :3]) - 1) / 2, -1, 1)))
            if np.linalg.norm(delta[:3, 3]) < .75 and angle < 10:
                support.append(j)
        clusters.append(support)
    cluster = max(clusters, key=len, default=[])
    consistent = len(cluster) >= 2 and max(candidates[i][1] for i in cluster) - min(candidates[i][1] for i in cluster) >= .5
    result = dict(status='consistent_alignment_hypothesis' if consistent else 'starting_location_unconfirmed',
        frames_reviewed=len(requests), candidate_frames=len(candidates), frame_diagnostics=diagnostics,
        support_request_ids=[candidates[i][0] for i in cluster],
        navigation_enabled=False, pose_usable_for_app=False, route_registration_verified=False,
        independently_validated=False, note='Correlated burst frames are not independent accuracy validation. No OCR/GPS or query depth is used.')
    if consistent:
        result['candidate_scan_from_arkit_world'] = candidates[cluster[0]][2].tolist()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--map', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve old review results; choose a new output path.')
    manifest = args.map / 'manifest.json'
    result = review_bundle(json.loads(args.capture.read_text()), hashlib.sha256(manifest.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps(result, indent=2, allow_nan=False))
