"""Follow-up to the v2 retrieval/correspondence audit: where does cross-view 3D inconsistency come from?

G1  depth-only consistency (no RGB): lift confident LiDAR depth of row A with its recorded pose, project
    into row B, compare with B's depth. Tests whether recorded poses and depth agree with each other.
G2  RGB timing sweep: re-lift and re-project LightGlue correspondences with poses interpolated at
    (row time + delta) for both views, delta in [-50, +50] ms, on top of the verified row = ordinal + 1.
G3  per-view PnP orientation vs recorded orientation, against camera turning speed and time gap.

Diagnostic only: recorded poses are oracles here. Nothing changes acceptance rules or the master.
"""
import csv
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
LOCALIZATION = WORKSPACE / 'outputs/MGH_Project/localization'
sys.path.insert(0, str(LOCALIZATION))
import mgh_localizer as L  # noqa: E402
import cv2  # noqa: E402
from PIL import Image  # noqa: E402

AUDIT = LOCALIZATION / 'audit_v2_retrieval_correspondence'
MAP = LOCALIZATION / 'visual_map_v2'
OFFSET = 1  # verified row = decoded ordinal + 1 (timestamp fingerprint and geometric shift test)
DELTAS_MS = list(range(-50, 52, 4))
DUMMY = np.zeros((1440, 1920, 3), np.uint8)


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def median(values):
    values = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.median(values)) if values else None


def quaternion_slerp(first, second, fraction):
    if np.dot(first, second) < 0:
        second = -second
    dot = float(np.clip(np.dot(first, second), -1, 1))
    if dot > .9995:
        result = first + fraction * (second - first)
    else:
        angle = np.arccos(dot)
        result = (np.sin((1 - fraction) * angle) * first + np.sin(fraction * angle) * second) / np.sin(angle)
    return result / np.linalg.norm(result)


class Trajectory:
    def __init__(self, rows):
        self.rows = rows
        self.times = np.array([float(row['timestamp']) for row in rows])
        self.quaternions = np.array([[float(row[key]) for key in ['qx', 'qy', 'qz', 'qw']] for row in rows])
        self.quaternions /= np.linalg.norm(self.quaternions, axis=1, keepdims=True)
        self.positions = np.array([[float(row[key]) for key in ['x', 'y', 'z']] for row in rows])

    def row_at(self, index, delta_seconds):
        """Copy of odometry row `index` with its pose interpolated at (row time + delta)."""
        target = self.times[index] + delta_seconds
        upper = int(np.clip(np.searchsorted(self.times, target), 1, len(self.times) - 1))
        lower = upper - 1
        fraction = float(np.clip((target - self.times[lower]) / (self.times[upper] - self.times[lower]), 0, 1))
        quaternion = quaternion_slerp(self.quaternions[lower], self.quaternions[upper], fraction)
        position = (1 - fraction) * self.positions[lower] + fraction * self.positions[upper]
        row = dict(self.rows[index])
        row.update(qx=quaternion[0], qy=quaternion[1], qz=quaternion[2], qw=quaternion[3], x=position[0], y=position[1], z=position[2])
        return row

    def turning_speed(self, index):
        lower, upper = max(index - 3, 0), min(index + 3, len(self.rows) - 1)
        first, second = L.camera_pose(self.rows[lower])[:3, :3], L.camera_pose(self.rows[upper])[:3, :3]
        return L.angular_disagreement(first, second) / (self.times[upper] - self.times[lower])


def project(world, calibration, pose):
    camera = (world - pose[:3, 3]) @ pose[:3, :3]
    pixels = camera @ calibration.T
    with np.errstate(invalid='ignore', divide='ignore'):
        return pixels[:, :2] / pixels[:, 2:3], camera[:, 2]


def depth_only_consistency(archive, trajectory, first, second, step=2):
    depth_a = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/depth/{first:06d}.png')))) / 1000
    confidence_a = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/confidence/{first:06d}.png'))))
    depth_b = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/depth/{second:06d}.png')))) / 1000
    confidence_b = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/confidence/{second:06d}.png'))))
    height, width = depth_a.shape
    scale = width / 1920

    def calibration(row):
        # depth pixel centres: raw = (depth_index + 0.5) / scale - 0.5
        return float(row['fx']) * scale, float(row['fy']) * scale, (float(row['cx']) + .5) * scale - .5, (float(row['cy']) + .5) * scale - .5

    fx, fy, cx, cy = calibration(trajectory.rows[first])
    rows_index, columns_index = np.mgrid[0:height:step, 0:width:step]
    keep = (confidence_a[rows_index, columns_index] == 2) & (depth_a[rows_index, columns_index] > .25) & (depth_a[rows_index, columns_index] < 4.8)
    z = depth_a[rows_index, columns_index][keep]
    camera = np.column_stack([(columns_index[keep] - cx) / fx * z, (rows_index[keep] - cy) / fy * z, z])
    pose_a, pose_b = L.camera_pose(trajectory.rows[first]), L.camera_pose(trajectory.rows[second])
    world = camera @ pose_a[:3, :3].T + pose_a[:3, 3]
    in_b = (world - pose_b[:3, 3]) @ pose_b[:3, :3]
    fx, fy, cx, cy = calibration(trajectory.rows[second])
    with np.errstate(invalid='ignore', divide='ignore'):
        u, v = in_b[:, 0] / in_b[:, 2] * fx + cx, in_b[:, 1] / in_b[:, 2] * fy + cy
    column, row = np.rint(u).astype(int), np.rint(v).astype(int)
    inside = (in_b[:, 2] > .25) & (column >= 0) & (column < width) & (row >= 0) & (row < height)
    if inside.sum() < 200:
        return None
    measured = depth_b[row[inside], column[inside]]
    valid = (confidence_b[row[inside], column[inside]] == 2) & (measured > .25)
    difference = np.abs(in_b[inside, 2][valid] - measured[valid])
    if len(difference) < 200:
        return None
    return dict(points=int(len(difference)), median_abs_m=float(np.median(difference)), fraction_under_5cm=float((difference < .05).mean()),
        p25_abs_m=float(np.percentile(difference, 25)))


def main():
    destination = AUDIT / 'crossview_geometry.json'
    if destination.exists():
        raise ValueError('Cross-view follow-up already exists; preserve it.')
    results = json.loads((AUDIT / 'results.json').read_text())
    manifest, references = L.load_map(MAP)
    reference_frames = [reference['metadata']['frame'] for reference in references]
    with np.load(AUDIT / 'lightglue_matches.npz') as saved:
        matches = {(key.split('_')[0], int(key.split('_')[1]), int(key.split('_')[2])): saved[key].copy() for key in saved.files}
    extractor, unused_matcher = L.setup_models(False)
    output = dict(follow_up_to=str((AUDIT / 'results.json').relative_to(WORKSPACE)), offset_row_minus_ordinal=OFFSET,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        localizer_sha256=hashlib.sha256((LOCALIZATION / 'mgh_localizer.py').read_bytes()).hexdigest(), oracle_policy='diagnostic only; recorded poses used as oracle')
    with L.source_archive() as (archive, checksum):
        rows, capture = L.source_inputs(archive)
        trajectory = Trajectory(rows)

        # G1: depth-only pose/depth consistency at several time gaps across the recording
        depth_only = {}
        for gap in [6, 30, 96, 300]:
            samples = []
            for first in range(60, len(rows) - gap - 1, 240):
                value = depth_only_consistency(archive, trajectory, first, first + gap)
                if value:
                    samples.append(dict(first=first, second=first + gap, turning_deg_s=trajectory.turning_speed(first), **value))
            depth_only[str(gap)] = dict(gap_rows=gap, approx_gap_seconds=gap / 60, pairs=len(samples),
                median_of_median_abs_m=median([item['median_abs_m'] for item in samples]),
                median_fraction_under_5cm=median([item['fraction_under_5cm'] for item in samples]),
                slow_turning_median_abs_m=median([item['median_abs_m'] for item in samples if item['turning_deg_s'] < 15]),
                fast_turning_median_abs_m=median([item['median_abs_m'] for item in samples if item['turning_deg_s'] >= 15]), samples=samples)
            log(f'G1 depth-only gap {gap}: pairs={len(samples)} median|dz|={depth_only[str(gap)]["median_of_median_abs_m"]}')
        output['depth_only_consistency'] = depth_only

        # Query features (same decoded ordinals as the audit) for G2/G3
        query_ordinals = [item['query_frame'] for item in results['per_query']]
        queries = {}
        for ordinal, pixels in L.decode_selected_frames(capture, query_ordinals):
            image, homography, unused_calibration, unused_pose, raw_size = L.orient_scan_image(pixels, rows[ordinal + OFFSET])
            queries[ordinal] = dict(features=L.features_for_image(image, extractor), homography=homography, raw_size=raw_size)
        capture.release()

        depth_cache = {}

        def lifted(ordinal, keypoints, homography, raw_size, delta):
            row_index = ordinal + OFFSET
            row = trajectory.row_at(row_index, delta)
            unused_image, check, calibration, pose, unused_size = L.orient_scan_image(DUMMY, row)
            if not np.allclose(check, homography):
                return None
            world, valid = L.lift_points(archive, row_index, keypoints, homography, row, raw_size)
            return dict(world=world.astype(np.float64), valid=valid, calibration=calibration, pose=pose)

        def geometry(ordinal, homography, delta):
            row = trajectory.row_at(ordinal + OFFSET, delta)
            unused_image, check, calibration, pose, unused_size = L.orient_scan_image(DUMMY, row)
            return dict(calibration=calibration, pose=pose) if np.allclose(check, homography) else None

        # G2/G3 pair list: query-reference true-overlap pairs and covisible temporal-neighbour reference pairs
        pair_list = []
        for row in csv.DictReader(open(AUDIT / 'query_reference_pairs.csv', encoding='utf-8')):
            if row['true_overlap'] == 'True' and int(row['lightglue_matches']) >= 20:
                pair_list.append(('query', int(row['query_frame']), int(row['reference_frame'])))
        for row in csv.DictReader(open(AUDIT / 'reference_pairs.csv', encoding='utf-8')):
            if row['category'] == 'neighbour' and int(row['covisible_points']) >= 30 and int(row['lightglue_matches']) >= 20:
                pair_list.append(('reference', int(row['first']), int(row['second'])))
        records = []
        for kind, first, second in pair_list:
            pair = matches[(kind, first, second)]
            if kind == 'query':
                source = references[reference_frames.index(second)]
                source_ordinal, target_ordinal = second, first
                source_keypoints, target_keypoints = source['features']['keypoints'][pair[:, 1]], queries[first]['features']['keypoints'][pair[:, 0]]
                source_h, target_h = np.array(source['metadata']['raw_to_reference_pixels']), queries[first]['homography']
                target_features = queries[first]['features']
                pnp_matches = pair
                source_full = source['features']
            else:
                source = references[reference_frames.index(first)]
                target = references[reference_frames.index(second)]
                source_ordinal, target_ordinal = first, second
                source_keypoints, target_keypoints = source['features']['keypoints'][pair[:, 0]], target['features']['keypoints'][pair[:, 1]]
                source_h, target_h = np.array(source['metadata']['raw_to_reference_pixels']), np.array(target['metadata']['raw_to_reference_pixels'])
                target_features = target['features']
                pnp_matches = np.ascontiguousarray(pair[:, ::-1])
                source_full = source['features']
            sweep = {}
            for delta_ms in DELTAS_MS:
                source_geometry = lifted(source_ordinal, source_keypoints, source_h, (1920, 1440), delta_ms / 1000)
                target_geometry = geometry(target_ordinal, target_h, delta_ms / 1000)
                if source_geometry is None or target_geometry is None or source_geometry['valid'].sum() < 12:
                    continue
                projected, depth = project(source_geometry['world'][source_geometry['valid']], target_geometry['calibration'], target_geometry['pose'])
                error = np.linalg.norm(projected - target_keypoints[source_geometry['valid']], axis=1)
                error = error[depth > 0]
                sweep[delta_ms] = dict(median_px=float(np.median(error)), fraction_under_3px=float((error < 3).mean()))
            if not sweep:
                continue
            best_delta = min(sweep, key=lambda key: sweep[key]['median_px'])
            # G3: per-view PnP (unchanged solver) vs recorded orientation at delta 0
            base = lifted(source_ordinal, source_full['keypoints'], source_h, (1920, 1440), 0)
            target_geometry = geometry(target_ordinal, target_h, 0)
            reference_view = dict(metadata=dict(frame=source_ordinal, capture_seconds=0.0, world_from_upright_camera=base['pose'].tolist()),
                features=dict(source_full, world_points=base['world'].astype(np.float32)))
            cv2.setRNGSeed(7)
            estimate = L.solve_pose(target_features, reference_view, pnp_matches, target_geometry['calibration'])
            record = dict(kind=kind, source=source_ordinal, target=target_ordinal, matches=len(pair),
                time_gap_s=abs(trajectory.times[source_ordinal + OFFSET] - trajectory.times[target_ordinal + OFFSET]),
                source_turning_deg_s=trajectory.turning_speed(source_ordinal + OFFSET), target_turning_deg_s=trajectory.turning_speed(target_ordinal + OFFSET),
                median_px_at_delta0=sweep.get(0, {}).get('median_px'), best_delta_ms=best_delta, median_px_at_best_delta=sweep[best_delta]['median_px'], sweep=sweep)
            if estimate is not None:
                record.update(pnp_per_view_accepted=estimate['per_view_accepted'], pnp_inliers=estimate['inliers'], pnp_median_reprojection_px=estimate['median_reprojection_px'],
                    pnp_position_vs_recorded_m=float(np.linalg.norm(np.array(estimate['position_scan_m']) - target_geometry['pose'][:3, 3])),
                    pnp_rotation_vs_recorded_deg=L.angular_disagreement(np.array(estimate['rotation_world_camera']), target_geometry['pose'][:3, :3]))
            records.append(record)
        log(f'G2/G3 pairs analysed: {len(records)}')

    def pooled(selection):
        common = [delta for delta in DELTAS_MS if all(delta in record['sweep'] for record in selection)]
        curve = {str(delta): median([record['sweep'][delta]['median_px'] for record in selection]) for delta in common}
        best = min(curve, key=curve.get) if curve else None
        return dict(pairs=len(selection), pooled_median_px_by_delta_ms=curve, pooled_best_delta_ms=int(best) if best else None,
            median_of_per_pair_best_delta_ms=median([record['best_delta_ms'] for record in selection]))

    accepted = [record for record in records if record.get('pnp_per_view_accepted')]
    turning = lambda record: max(record['source_turning_deg_s'], record['target_turning_deg_s'])
    output['timing_sweep'] = dict(all_pairs=pooled(records), query_pairs=pooled([record for record in records if record['kind'] == 'query']),
        reference_neighbour_pairs=pooled([record for record in records if record['kind'] == 'reference']))
    bins = [(0, 10), (10, 25), (25, 50), (50, 1e9)]
    output['pnp_orientation_vs_recorded'] = dict(per_view_accepted_pairs=len(accepted),
        median_rotation_deg=median([record['pnp_rotation_vs_recorded_deg'] for record in accepted]),
        median_position_m=median([record['pnp_position_vs_recorded_m'] for record in accepted]),
        by_max_turning_deg_s=[dict(range=[low, high if high < 1e9 else None], pairs=len(selected),
            median_rotation_deg=median([record['pnp_rotation_vs_recorded_deg'] for record in selected]),
            median_position_m=median([record['pnp_position_vs_recorded_m'] for record in selected]),
            median_px_at_delta0=median([record['median_px_at_delta0'] for record in selected]))
            for low, high in bins for selected in [[record for record in accepted if low <= turning(record) < high]]],
        by_time_gap_s=[dict(range=[low, high if high < 1e9 else None], pairs=len(selected),
            median_rotation_deg=median([record['pnp_rotation_vs_recorded_deg'] for record in selected]),
            median_position_m=median([record['pnp_position_vs_recorded_m'] for record in selected]))
            for low, high in [(0, 3), (3, 8), (8, 20), (20, 1e9)] for selected in [[record for record in accepted if low <= record['time_gap_s'] < high]]],
        spearman_rotation_error_vs_turning=float(np.corrcoef(np.argsort(np.argsort([record['pnp_rotation_vs_recorded_deg'] for record in accepted])),
            np.argsort(np.argsort([turning(record) for record in accepted])))[0, 1]) if len(accepted) > 3 else None,
        spearman_rotation_error_vs_time_gap=float(np.corrcoef(np.argsort(np.argsort([record['pnp_rotation_vs_recorded_deg'] for record in accepted])),
            np.argsort(np.argsort([record['time_gap_s'] for record in accepted])))[0, 1]) if len(accepted) > 3 else None)
    for record in records:
        record['sweep'] = {str(key): value for key, value in record['sweep'].items()}
    output['pairs'] = records
    destination.write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    log(json.dumps({key: value for key, value in output.items() if key in ['timing_sweep', 'pnp_orientation_vs_recorded']}, indent=1))
    log(json.dumps({gap: {key: value for key, value in item.items() if key != 'samples'} for gap, item in depth_only.items()}, indent=1))


if __name__ == '__main__':
    main()
