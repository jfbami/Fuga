"""Research audit of visual_map_v2 retrieval recall and cross-view 3D correspondence consistency.

Recorded poses and query LiDAR depth are used only AFTER matching, as diagnostic oracles. They are never
inputs to retrieval, matching, PnP, or the unchanged per-view / two-view acceptance rules. This script reuses
the active localizer's orientation, lifting, feature, matching, and pose functions without modification. It
writes only a new audit folder plus working video copies under work/audit_inputs; it never edits the master.
"""
import csv
import hashlib
import io
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
LOCALIZATION = WORKSPACE / 'outputs/MGH_Project/localization'
sys.path.insert(0, str(LOCALIZATION))
import mgh_localizer as L  # noqa: E402
import cv2  # noqa: E402
import torch  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = LOCALIZATION / 'audit_v2_retrieval_correspondence'
MAP = LOCALIZATION / 'visual_map_v2'
V2_RESULTS = LOCALIZATION / 'evaluation_v2_framefix/results.json'
SHIFTS = [-1, 0, 1, 2]
COVISIBLE_MIN = 30
TOP_TESTED = 13


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def dump(path, payload):
    path.write_text(json.dumps(payload, indent=2, allow_nan=False, default=lambda value: value.item() if hasattr(value, 'item') else str(value)), encoding='utf-8')


def finite(value):
    return None if value is None or not np.isfinite(value) else float(value)


def median(values):
    values = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.median(values)) if values else None


# ---------------------------------------------------------------- part 0: timestamp fingerprint, all scans
def timestamp_alignment():
    connection = sqlite3.connect((WORKSPACE / 'outputs/MGH_Master.sqlite').as_uri() + '?mode=ro', uri=True)
    originals = connection.execute("SELECT current_assets.scan_id, logical_path, blob_id, sha256 FROM current_assets "
        "JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip' ORDER BY current_assets.scan_id").fetchall()
    results = []
    try:
        for scan_id, logical, blob_id, checksum in originals:
            video = WORKSPACE / 'work/audit_inputs' / scan_id / 'rgb.mp4'
            video.parent.mkdir(parents=True, exist_ok=True)
            with connection.blobopen('blobs', 'content', blob_id, readonly=True) as blob:
                with zipfile.ZipFile(L.BlobReader(blob)) as archive:
                    names = archive.namelist()
                    odometry_name = [name for name in names if name.endswith('odometry.csv')]
                    video_name = [name for name in names if name.endswith('rgb.mp4')]
                    if len(odometry_name) != 1 or len(video_name) != 1:
                        results.append(dict(scan_id=scan_id, status='unexpected_layout'))
                        continue
                    rows = list(csv.DictReader(io.StringIO(archive.read(odometry_name[0]).decode()), skipinitialspace=True))
                    depth_files = sum(1 for name in names if '/depth/' in name and name.endswith('.png'))
                    with archive.open(video_name[0]) as source, video.open('wb') as destination:
                        while chunk := source.read(1 << 22):
                            destination.write(chunk)
            odometry = np.array([float(row['timestamp']) for row in rows])
            odometry -= odometry[0]
            capture = cv2.VideoCapture(str(video))
            container_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            stamps = []
            while capture.grab():
                stamps.append(capture.get(cv2.CAP_PROP_POS_MSEC) / 1000)
            capture.release()
            stamps = np.array(stamps)
            hypotheses = []
            for shift in range(-5, 6):
                ordinals = np.arange(len(stamps))
                keep = (ordinals + shift >= 0) & (ordinals + shift < len(odometry))
                video_times, row_times = stamps[ordinals[keep]], odometry[ordinals[keep] + shift]
                residual = (video_times - video_times[0]) - (row_times - row_times[0])
                hypotheses.append(dict(row_minus_ordinal=shift,
                    max_abs_time_residual_s=float(np.abs(residual - np.median(residual)).max()),
                    gap_pattern_agreement=float(((np.diff(video_times) > .03) == (np.diff(row_times) > .03)).mean())))
            best = max(hypotheses, key=lambda item: (item['gap_pattern_agreement'], -item['max_abs_time_residual_s']))
            results.append(dict(scan_id=scan_id, original_asset=logical, original_sha256=checksum, odometry_rows=len(rows),
                frame_column_equals_row_index=[int(row['frame']) for row in rows] == list(range(len(rows))),
                depth_pngs=depth_files, container_reported_frames=container_frames, sequentially_decoded_frames=len(stamps),
                odometry_gaps_over_30ms=int((np.diff(odometry) > .03).sum()), video_gaps_over_30ms=int((np.diff(stamps) > .03).sum()),
                hypotheses=hypotheses, best_row_minus_ordinal=best['row_minus_ordinal'],
                best_is_unique=sum(item['gap_pattern_agreement'] == best['gap_pattern_agreement'] for item in hypotheses) == 1))
            entry = results[-1]
            entry['conclusive'] = bool(entry['best_is_unique'] and entry['odometry_gaps_over_30ms'] >= 10 and best['max_abs_time_residual_s'] < .0125)
            if not entry['conclusive']:
                entry['best_row_minus_ordinal'] = None
                entry['note'] = 'Too few dropped-frame gaps or a tie: the timestamp fingerprint cannot determine the video/odometry offset for this scan.'
            log(f'timestamp fingerprint {scan_id}: conclusive={entry["conclusive"]} gaps={entry["odometry_gaps_over_30ms"]} rows={len(rows)} decoded={len(stamps)} best row-ordinal={best["row_minus_ordinal"]} '
                f'agreement={best["gap_pattern_agreement"]:.4f} residual={best["max_abs_time_residual_s"]:.4f}s')
    finally:
        connection.close()
    return results


# ---------------------------------------------------------------- geometry helpers (reuse localizer code)
DUMMY = np.zeros((1440, 1920, 3), np.uint8)


def oriented_geometry(row, expected_homography=None):
    unused_image, homography, calibration, pose, raw_size = L.orient_scan_image(DUMMY, row)
    if expected_homography is not None and not np.allclose(homography, expected_homography):
        return None
    return dict(homography=homography, calibration=calibration, pose=pose, raw_size=raw_size)


def project(world, calibration, pose):
    camera = (world - pose[:3, 3]) @ pose[:3, :3]
    pixels = camera @ calibration.T
    with np.errstate(invalid='ignore', divide='ignore'):
        return pixels[:, :2] / pixels[:, 2:3], camera[:, 2]


def load_depth(archive, frame):
    depth = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/depth/{frame:06d}.png'))))
    confidence = np.array(Image.open(io.BytesIO(archive.read(f'{L.SCAN_ID}/confidence/{frame:06d}.png'))))
    return depth, confidence


def sample_depth(depth_pair, pixels, homography, raw_size):
    depth, confidence = depth_pair
    native = np.column_stack([pixels, np.ones(len(pixels))]) @ np.linalg.inv(homography).T
    columns = np.rint(native[:, 0] * depth.shape[1] / raw_size[0]).astype(int)
    rows = np.rint(native[:, 1] * depth.shape[0] / raw_size[1]).astype(int)
    inside = (columns >= 0) & (columns < depth.shape[1]) & (rows >= 0) & (rows < depth.shape[0])
    values = np.full(len(pixels), np.nan)
    levels = np.full(len(pixels), -1)
    values[inside] = depth[rows[inside], columns[inside]] / 1000
    levels[inside] = confidence[rows[inside], columns[inside]]
    return values, levels


def depth_reasons(depth_pair, points, homography, raw_size):
    """Replicates the individual tests inside L.lift_points so invalid depth can be attributed."""
    depth, confidence = depth_pair
    native = np.column_stack([points, np.ones(len(points))]) @ np.linalg.inv(homography).T
    columns = np.clip(np.rint(native[:, 0] * depth.shape[1] / raw_size[0]).astype(int), 1, depth.shape[1] - 2)
    rows = np.clip(np.rint(native[:, 1] * depth.shape[0] / raw_size[1]).astype(int), 1, depth.shape[0] - 2)
    patches = np.stack([depth[rows + a, columns + b] for a in [-1, 0, 1] for b in [-1, 0, 1]], axis=1).astype(np.int32)
    return dict(low_confidence=confidence[rows, columns] != 2, too_near=patches.min(axis=1) < 250,
        too_far=patches.max(axis=1) >= 4800, depth_edge=np.ptp(patches, axis=1) > 150, center_depth_m=depth[rows, columns] / 1000)


def rotation_speed(rows, frame):
    if frame + 1 >= len(rows):
        return None
    first, second = L.camera_pose(rows[frame])[:3, :3], L.camera_pose(rows[frame + 1])[:3, :3]
    elapsed = float(rows[frame + 1]['timestamp']) - float(rows[frame]['timestamp'])
    return L.angular_disagreement(first, second) / elapsed if elapsed > 0 else None


def covisible_count(world, valid, target_geometry, target_depth, image_size):
    points = world[valid]
    if not len(points):
        return 0, 0
    pixels, depth = project(points, target_geometry['calibration'], target_geometry['pose'])
    inside = (depth > .2) & (pixels[:, 0] >= 0) & (pixels[:, 0] < image_size[0]) & (pixels[:, 1] >= 0) & (pixels[:, 1] < image_size[1])
    if not inside.any():
        return 0, 0
    measured, levels = sample_depth(target_depth, pixels[inside], target_geometry['homography'], target_geometry['raw_size'])
    agrees = (levels >= 1) & (measured > .25) & (np.abs(depth[inside] - measured) <= .10 + .05 * depth[inside])
    return int(agrees.sum()), int(inside.sum())


def reprojection_errors(world, valid, pixels_target, target_geometry):
    errors = np.full(len(world), np.nan)
    if valid.any():
        projected, depth = project(world[valid], target_geometry['calibration'], target_geometry['pose'])
        error = np.linalg.norm(projected - pixels_target[valid], axis=1)
        error[depth <= 0] = np.nan
        errors[valid] = error
    return errors


def error_summary(errors):
    finite_errors = errors[np.isfinite(errors)]
    if not len(finite_errors):
        return dict(count=0, median_px=None, fraction_under_3px=None, fraction_under_8px=None)
    return dict(count=int(len(finite_errors)), median_px=float(np.median(finite_errors)),
        fraction_under_3px=float((finite_errors < 3).mean()), fraction_under_8px=float((finite_errors < 8).mean()))


def decide(candidates):
    """Exact copy of the cluster/acceptance logic in L.localize (unchanged thresholds)."""
    verified = [candidate for candidate in candidates if candidate['per_view_accepted']]
    clusters = [[other for other in verified if np.linalg.norm(np.array(candidate['position_scan_m']) - np.array(other['position_scan_m'])) < .75
        and L.angular_disagreement(np.array(candidate['rotation_world_camera']), np.array(other['rotation_world_camera'])) < 10] for candidate in verified]
    best_cluster = max(clusters, key=lambda cluster: (len(cluster), sum(item['inliers'] for item in cluster)), default=[])
    accepted = len(best_cluster) >= 2 and max(item['reference_capture_seconds'] for item in best_cluster) - min(item['reference_capture_seconds'] for item in best_cluster) >= .5
    best = max(best_cluster, key=lambda item: item['inliers']) if accepted else None
    return accepted, [item['reference_frame'] for item in best_cluster], best


def pose_error(candidate, truth):
    position = float(np.linalg.norm(np.array(candidate['position_scan_m']) - truth[:3, 3]))
    rotation = L.angular_disagreement(np.array(candidate['rotation_world_camera']), truth[:3, :3])
    return position, rotation


def pose_class(position, rotation):
    return 'correct' if position <= .5 and rotation <= 10 else 'near_0p5_to_2m' if position <= 2 else 'wrong_place_over_2m'


# ---------------------------------------------------------------- retrieval scores
def squared_distances(first, second):
    return np.maximum((first**2).sum(1)[:, None] + (second**2).sum(1)[None] - 2 * first @ second.T, 0)


def top_two(distances):
    """Column indices of the nearest and second-nearest entry in each row (partial selection, then ordered)."""
    candidates = np.argpartition(distances, 1, axis=1)[:, :2]
    values = np.take_along_axis(distances, candidates, axis=1)
    return np.take_along_axis(candidates, np.argsort(values, axis=1), axis=1)


def retrieval_scores(query_descriptors, eligible, references, owner_lists, v2_rng_seed):
    """Scores for every eligible reference. Recorded poses are not used here."""
    query = query_descriptors.astype(np.float32)
    per_reference_ratio, mutual, best_two = [], [], []
    for index in eligible:
        reference = references[index]['features']['descriptors'].astype(np.float32)
        distances = squared_distances(query, reference)
        order = top_two(distances)
        first, second = distances[np.arange(len(query)), order[:, 0]], distances[np.arange(len(query)), order[:, 1]]
        per_reference_ratio.append(int((np.sqrt(first) < .85 * np.sqrt(second)).sum()))
        mutual.append(int((np.argmin(distances, axis=0)[order[:, 0]] == np.arange(len(query))).sum()))
        best_two.append(np.stack([np.sqrt(first), np.sqrt(second)], axis=1))
    # exact version of the v2 cross-image ratio vote: nearest + second-nearest over ALL eligible references
    stacked = np.stack(best_two, axis=1)  # query x eligible x 2
    flat_distance = stacked.reshape(len(query), -1)
    flat_owner = np.repeat(np.arange(len(eligible)), 2)
    order = np.argsort(flat_distance, axis=1)[:, :2]
    nearest, runner_up = flat_distance[np.arange(len(query)), order[:, 0]], flat_distance[np.arange(len(query)), order[:, 1]]
    nearest_owner, runner_owner = flat_owner[order[:, 0]], flat_owner[order[:, 1]]
    passes = nearest < .85 * runner_up
    exact_votes = np.bincount(nearest_owner[passes], minlength=len(eligible))
    # replicate the v2 FLANN implementation exactly (randomized trees; RNG seeded for reproducibility)
    cv2.setRNGSeed(v2_rng_seed)
    retrieval = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 4}, {'checks': 64})
    retrieval.add([references[index]['features']['descriptors'].astype(np.float32) for index in eligible])
    retrieval.train()
    flann_votes = np.zeros(len(eligible))
    for pair in retrieval.knnMatch(query, k=2):
        if len(pair) == 2 and pair[0].distance < .85 * pair[1].distance:
            flann_votes[pair[0].imgIdx] += 1
    query_mean = query_descriptors.mean(axis=0)
    query_mean /= max(float(np.linalg.norm(query_mean)), 1e-9)
    means = np.array([references[index]['features']['descriptors'].mean(axis=0) for index in eligible])
    means /= np.maximum(np.linalg.norm(means, axis=1, keepdims=True), 1e-9)
    return dict(flann_cross_image_votes=flann_votes, exact_cross_image_votes=exact_votes.astype(float), mean_descriptor=means @ query_mean,
        per_reference_ratio=np.array(per_reference_ratio, float), mutual_nearest_neighbors=np.array(mutual, float)), \
        dict(nearest_owner=nearest_owner, runner_owner=runner_owner, passes=passes)


def v2_tested_set(scores):
    votes = np.argsort(scores['flann_cross_image_votes'])[::-1][:10]
    means = np.argsort(scores['mean_descriptor'])[::-1][:3]
    return list(dict.fromkeys([int(index) for index in votes] + [int(index) for index in means]))


# ---------------------------------------------------------------- main audit
def main():
    if (OUT / 'results.json').exists():
        raise ValueError('Audit already completed; preserve it and choose a new folder.')
    plan = json.loads((OUT / 'AUDIT_PLAN.json').read_text())
    started = time.monotonic()
    timestamp_results = timestamp_alignment()
    manifest, references = L.load_map(MAP)
    v2 = json.loads(V2_RESULTS.read_text())
    v2_by_query = {item['query_frame']: item for item in v2['results']}
    extractor, matcher = L.setup_models()
    stride = manifest['stride_frames']
    with L.source_archive() as (archive, checksum):
        if checksum != manifest['original_zip_sha256']:
            raise RuntimeError('Map was not built from the current original ZIP.')
        rows, capture = L.source_inputs(archive)
        times = np.array([float(row['timestamp']) for row in rows]) - float(rows[0]['timestamp'])
        set_a = [int(frame // stride * stride + max(1, stride // 2)) for frame in np.linspace(600, len(rows) - 300, 20).astype(int)]
        if set_a != plan['query_set_A_decoded_ordinals']:
            raise RuntimeError('Query set A does not reproduce the v2 evaluation ordinals.')
        reference_frames = [reference['metadata']['frame'] for reference in references]
        log(f'map: {len(references)} references; queries: {set_a}')

        # reference geometry for every association hypothesis (row = decoded ordinal + shift)
        reference_geometry = []
        reproduced = True
        for reference in references:
            frame = reference['metadata']['frame']
            stored_homography = np.array(reference['metadata']['raw_to_reference_pixels'])
            keypoints = reference['features']['keypoints']
            per_shift = {}
            for shift in SHIFTS:
                row = frame + shift
                geometry = oriented_geometry(rows[row], stored_homography) if 0 <= row < len(rows) else None
                if geometry is None:
                    per_shift[shift] = None
                    continue
                world, valid = L.lift_points(archive, row, keypoints, geometry['homography'], rows[row], geometry['raw_size'])
                per_shift[shift] = dict(geometry, world=world.astype(np.float64), valid=valid, row=row, seconds=float(times[row]))
            stored_world = reference['features']['world_points']
            same = per_shift[0] is not None and np.array_equal(np.isnan(stored_world), np.isnan(per_shift[0]['world'])) and \
                np.allclose(np.nan_to_num(stored_world), np.nan_to_num(per_shift[0]['world']), atol=1e-4)
            reproduced &= bool(same)
            reference_geometry.append(per_shift)
        log(f'reference geometry computed; shift-0 lifting reproduces stored v2 world points: {reproduced}')

        # queries: decode the same RGB ordinals sequentially and extract features once
        queries = {}
        for frame, pixels in L.decode_selected_frames(capture, set_a):
            image, homography, calibration, pose, raw_size = L.orient_scan_image(pixels, rows[frame])
            saved = np.asarray(Image.open(LOCALIZATION / f'evaluation_v2_framefix/query_{frame:06d}.jpg'), dtype=np.float32)
            identity_difference = float(np.abs(saved - image.astype(np.float32)).mean()) if saved.shape == image.shape else None
            features = L.features_for_image(image, extractor)
            per_shift = {}
            for shift in SHIFTS:
                row = frame + shift
                geometry = oriented_geometry(rows[row], homography) if 0 <= row < len(rows) else None
                if geometry is not None:
                    geometry.update(depth=load_depth(archive, row), row=row, seconds=float(times[row]))
                per_shift[shift] = geometry
            queries[frame] = dict(image=image, features=features, geometry=per_shift, seconds_v2=float(times[frame]),
                identity_mean_abs_difference_vs_saved_v2_jpeg=identity_difference, rotation_speed_deg_s=rotation_speed(rows, frame + 1))
        capture.release()
        log('queries decoded and featurized')

        # ---------------------------------------------------- matching (LightGlue, unchanged configuration)
        tensors = [L.tensor_features(reference['features']) for reference in references]
        matches = {}
        cache_path = OUT / 'lightglue_matches.npz'
        cache = {}
        if cache_path.exists():
            with np.load(cache_path) as saved:
                cache = {(key.split('_')[0], int(key.split('_')[1]), int(key.split('_')[2])): saved[key].copy() for key in saved.files}
            log(f'reusing {len(cache)} cached LightGlue match sets')

        @torch.inference_mode()
        def lightglue(first, second):
            return matcher({'image0': first, 'image1': second})['matches'][0].cpu().numpy().astype(np.int32)

        def match(key, first, second):
            matches[key] = cache[key] if key in cache else lightglue(first, second)

        eligibility, scores, redundancy = {}, {}, {}
        for query_index, frame in enumerate(set_a):
            query = queries[frame]
            # v2 eligibility convention: |reference capture_seconds - query timestamp| >= 2 s, both at shift 0
            eligible = [index for index, reference in enumerate(references) if abs(reference['metadata']['capture_seconds'] - query['seconds_v2']) >= 2]
            eligibility[frame] = eligible
            scores[frame], redundancy[frame] = retrieval_scores(query['features']['descriptors'], eligible, references, None, 42 + query_index)
            query_tensor = L.tensor_features(query['features'])
            tick = time.monotonic()
            for index in eligible:
                match(('query', frame, reference_frames[index]), query_tensor, tensors[index])
            log(f'query {frame}: matched {len(eligible)} eligible references in {time.monotonic() - tick:.1f}s')

        # reference-reference pairs: temporal neighbours plus appearance-selected revisits (>20 s apart)
        descriptor_sets = [reference['features']['descriptors'].astype(np.float32) for reference in references]
        appearance = np.zeros((len(references), len(references)))
        for first in range(len(references)):
            for second in range(len(references)):
                if first != second:
                    distances = squared_distances(descriptor_sets[first], descriptor_sets[second])
                    order = np.sort(np.partition(distances, 1, axis=1)[:, :2], axis=1)
                    appearance[first, second] = (np.sqrt(order[:, 0]) < .85 * np.sqrt(order[:, 1])).sum()
        pairs = set()
        for first in range(len(references)):
            for second in range(first + 1, min(first + 4, len(references))):
                pairs.add((first, second))
            gaps = np.abs(np.array([reference['metadata']['capture_seconds'] for reference in references]) - references[first]['metadata']['capture_seconds'])
            candidates = [index for index in np.argsort(appearance[first])[::-1] if gaps[index] > 20][:4]
            pairs.update((min(first, index), max(first, index)) for index in candidates)
        tick = time.monotonic()
        for first, second in sorted(pairs):
            match(('reference', reference_frames[first], reference_frames[second]), tensors[first], tensors[second])
        log(f'matched {len(pairs)} reference pairs in {time.monotonic() - tick:.1f}s')
        if not cache_path.exists():
            np.savez_compressed(cache_path, **{f'{kind}_{first:06d}_{second:06d}': pair for (kind, first, second), pair in matches.items()})

        # ---------------------------------------------------- association-shift test (cross-view reprojection)
        def shift_errors(source_world, source_valid, target_pixels, target_geometry):
            return error_summary(reprojection_errors(source_world, source_valid, target_pixels, target_geometry))

        shift_records = []
        for (kind, first_frame, second_frame), pair in matches.items():
            if len(pair) < 20:
                continue
            record = dict(kind=kind, first=first_frame, second=second_frame, matches=len(pair), by_shift={})
            if kind == 'query':
                query = queries[first_frame]
                reference = reference_geometry[reference_frames.index(second_frame)]
                query_pixels = query['features']['keypoints'][pair[:, 0]]
                speed = [query['rotation_speed_deg_s'], rotation_speed(rows, second_frame + 1)]
                for shift in SHIFTS:
                    if reference[shift] is None or query['geometry'][shift] is None:
                        continue
                    record['by_shift'][shift] = shift_errors(reference[shift]['world'][pair[:, 1]], reference[shift]['valid'][pair[:, 1]], query_pixels, query['geometry'][shift])
            else:
                first_index, second_index = reference_frames.index(first_frame), reference_frames.index(second_frame)
                first, second = reference_geometry[first_index], reference_geometry[second_index]
                first_pixels = references[first_index]['features']['keypoints'][pair[:, 0]]
                second_pixels = references[second_index]['features']['keypoints'][pair[:, 1]]
                speed = [rotation_speed(rows, first_frame + 1), rotation_speed(rows, second_frame + 1)]
                for shift in SHIFTS:
                    if first[shift] is None or second[shift] is None:
                        continue
                    forward = reprojection_errors(first[shift]['world'][pair[:, 0]], first[shift]['valid'][pair[:, 0]], second_pixels, second[shift])
                    backward = reprojection_errors(second[shift]['world'][pair[:, 1]], second[shift]['valid'][pair[:, 1]], first_pixels, first[shift])
                    record['by_shift'][shift] = error_summary(np.concatenate([forward, backward]))
            record['max_rotation_speed_deg_s'] = max([value for value in speed if value is not None], default=None)
            shift_records.append(record)
        overlapping = [record for record in shift_records if record['by_shift'] and max((value['fraction_under_3px'] or 0) for value in record['by_shift'].values()) >= .3
            and all(record['by_shift'].get(shift) and record['by_shift'][shift]['count'] >= 15 for shift in SHIFTS)]

        def pooled(records):
            return {str(shift): dict(median_of_pair_median_px=median([record['by_shift'][shift]['median_px'] for record in records]),
                median_fraction_under_3px=median([record['by_shift'][shift]['fraction_under_3px'] for record in records]),
                pairs_where_best=int(sum(min(SHIFTS, key=lambda value: record['by_shift'][value]['median_px']) == shift for record in records))) for shift in SHIFTS}

        fast = [record for record in overlapping if (record['max_rotation_speed_deg_s'] or 0) >= 20]
        slow = [record for record in overlapping if (record['max_rotation_speed_deg_s'] or 0) < 20]
        shift_test = dict(definition='Reprojection of LightGlue-matched confident 3D points into the other view, under the hypothesis odometry/depth row = decoded RGB ordinal + shift for BOTH views. Uses recorded poses as oracle.',
            overlapping_pairs=len(overlapping), all_pairs=pooled(overlapping), rotation_speed_at_least_20deg_s=dict(pairs=len(fast), **pooled(fast)) if fast else None,
            rotation_speed_under_20deg_s=dict(pairs=len(slow), **pooled(slow)) if slow else None)
        primary = min(SHIFTS, key=lambda shift: shift_test['all_pairs'][str(shift)]['median_of_pair_median_px'])
        staircase_timestamp = next(item for item in timestamp_results if item['scan_id'] == L.SCAN_ID)
        shift_test.update(geometric_best_row_minus_ordinal=primary, timestamp_best_row_minus_ordinal=staircase_timestamp['best_row_minus_ordinal'],
            geometric_and_timestamp_agree=primary == staircase_timestamp['best_row_minus_ordinal'])
        log(f'association shift test: geometric best={primary}; ' + json.dumps(shift_test['all_pairs']))

        # ---------------------------------------------------- per-reference depth coverage at primary association
        reasons_total = dict(low_confidence=0, too_near=0, too_far=0, depth_edge=0)
        coverage = []
        reference_reasons = []
        for index, reference in enumerate(references):
            geometry = reference_geometry[index][primary]
            depth_pair = load_depth(archive, geometry['row'])
            reasons = depth_reasons(depth_pair, reference['features']['keypoints'], geometry['homography'], geometry['raw_size'])
            reference_reasons.append(reasons)
            for key in reasons_total:
                reasons_total[key] += int(reasons[key].sum())
            coverage.append(float(geometry['valid'].mean()))
            geometry['depth'] = depth_pair
        total_keypoints = sum(len(reference['features']['keypoints']) for reference in references)

        # ---------------------------------------------------- per-query retrieval / correspondence / PnP audit
        per_query, pair_rows, decisions = [], [], {name: [] for name in ['v2_recorded_tested_set_shift0', 'v2_recorded_tested_set_corrected',
            'flann_replica_tested_set_corrected', 'per_reference_ratio_top13_corrected', 'lightglue_count_top13_corrected',
            'exhaustive_all_eligible_corrected', 'oracle_covisible_only_corrected']}
        image_size = None
        for frame in set_a:
            query = queries[frame]
            truth = query['geometry'][primary]
            image_size = query['features']['image_size']
            eligible = eligibility[frame]
            query_world, query_valid = L.lift_points(archive, truth['row'], query['features']['keypoints'], truth['homography'], rows[truth['row']], truth['raw_size'])
            covisible = []
            for index in eligible:
                geometry = reference_geometry[index][primary]
                covisible.append(covisible_count(geometry['world'], geometry['valid'], truth, truth['depth'], image_size)[0])
            covisible = np.array(covisible)
            true_set = {index for index, count in zip(eligible, covisible) if count >= COVISIBLE_MIN}
            candidates_shift0, candidates_corrected = {}, {}
            for position, index in enumerate(eligible):
                reference = references[index]
                pair = matches[('query', frame, reference_frames[index])]
                corrected = reference_geometry[index][primary]
                row = dict(query_frame=frame, reference_frame=reference_frames[index], reference_seconds=reference['metadata']['capture_seconds'],
                    time_gap_s=abs(reference['metadata']['capture_seconds'] - query['seconds_v2']), covisible_points=int(covisible[position]),
                    true_overlap=index in true_set, lightglue_matches=len(pair),
                    **{f'score_{name}': float(values[position]) for name, values in scores[frame].items()})
                if len(pair):
                    reference_valid = corrected['valid'][pair[:, 1]]
                    reasons = reference_reasons[index]
                    row.update(matches_with_reference_depth=int(reference_valid.sum()),
                        invalid_low_confidence=int(reasons['low_confidence'][pair[:, 1]][~reference_valid].sum()),
                        invalid_too_far=int(reasons['too_far'][pair[:, 1]][~reference_valid].sum()),
                        invalid_too_near=int(reasons['too_near'][pair[:, 1]][~reference_valid].sum()),
                        invalid_depth_edge=int(reasons['depth_edge'][pair[:, 1]][~reference_valid].sum()))
                    errors = reprojection_errors(corrected['world'][pair[:, 1]], reference_valid, query['features']['keypoints'][pair[:, 0]], truth)
                    summary = error_summary(errors)
                    row.update(oracle_reprojection_median_px=summary['median_px'], oracle_fraction_under_3px=summary['fraction_under_3px'],
                        oracle_fraction_under_8px=summary['fraction_under_8px'])
                    both = reference_valid & query_valid[pair[:, 0]]
                    row['matches_with_both_depths'] = int(both.sum())
                    row['median_3d_disagreement_m'] = float(np.median(np.linalg.norm(corrected['world'][pair[:, 1]][both] - query_world[pair[:, 0]][both], axis=1))) if both.any() else None
                if len(pair) >= 12:
                    old_reference = dict(metadata=reference['metadata'], features=reference['features'])
                    new_metadata = dict(reference['metadata'], world_from_upright_camera=corrected['pose'].tolist(), capture_seconds=corrected['seconds'])
                    new_reference = dict(metadata=new_metadata, features=dict(reference['features'], world_points=corrected['world'].astype(np.float32)))
                    for label, reference_view, calibration, store in [('shift0', old_reference, query['geometry'][0]['calibration'], candidates_shift0),
                            ('corrected', new_reference, truth['calibration'], candidates_corrected)]:
                        cv2.setRNGSeed(7)
                        estimate = L.solve_pose(query['features'], reference_view, pair, calibration)
                        if estimate is not None:
                            position_error, rotation_error = pose_error(estimate, truth['pose'])
                            estimate.update(oracle_position_error_m=position_error, oracle_rotation_error_deg=rotation_error)
                            store[index] = estimate
                            row[f'{label}_per_view_accepted'] = estimate['per_view_accepted']
                            row[f'{label}_inliers'] = estimate['inliers']
                            row[f'{label}_oracle_position_error_m'] = position_error
                pair_rows.append(row)

            # retrieval recall per method (rank among eligible references; 1 = best)
            method_scores = dict(scores[frame], lightglue_matches=np.array([len(matches[('query', frame, reference_frames[index])]) for index in eligible], float),
                lightglue_matches_with_depth=np.array([int(reference_geometry[index][primary]['valid'][matches[('query', frame, reference_frames[index])][:, 1]].sum())
                    if len(matches[('query', frame, reference_frames[index])]) else 0 for index in eligible], float))
            recall = {}
            for name, values in method_scores.items():
                order = [eligible[position] for position in np.argsort(-values, kind='stable')]
                ranks = [order.index(index) + 1 for index in true_set]
                recall[name] = dict(first_true_rank=min(ranks) if ranks else None, true_in_top13=sum(rank <= TOP_TESTED for rank in ranks),
                    true_in_top5=sum(rank <= 5 for rank in ranks))
            tested_v2_frames = [item['reference_frame'] for item in v2_by_query[frame]['appearances']]
            tested_v2 = [reference_frames.index(value) for value in tested_v2_frames]
            tested_flann = [eligible[position] for position in v2_tested_set(scores[frame])]
            recall['v2_recorded_tested_set'] = dict(tested=len(tested_v2), true_in_tested=len(true_set & set(tested_v2)))
            recall['flann_replica_tested_set'] = dict(tested=len(tested_flann), true_in_tested=len(true_set & set(tested_flann)),
                overlap_with_recorded_v2_set=len(set(tested_flann) & set(tested_v2)))

            # why the cross-image ratio test rejects: is the runner-up the same place in another reference?
            info = redundancy[frame]
            failed = ~info['passes']
            eligible_true = np.array([eligible[position] in true_set for position in range(len(eligible))])
            cross = failed & (info['nearest_owner'] != info['runner_owner'])
            both_true = cross & eligible_true[info['nearest_owner']] & eligible_true[info['runner_owner']]
            ratio_audit = dict(query_features=int(len(failed)), passed_cross_image_ratio=int(info['passes'].sum()), failed=int(failed.sum()),
                failed_runner_up_in_other_reference=int(cross.sum()), failed_both_neighbours_in_true_overlap_references=int(both_true.sum()),
                nearest_in_true_overlap_reference=int(eligible_true[info['nearest_owner']].sum()))

            outcome = {}
            def run(name, tested, store):
                accepted, support, best = decide([store[index] for index in tested if index in store])
                result = dict(accepted=accepted, tested=len(tested), support=support)
                if accepted:
                    position_error, rotation_error = pose_error(best, truth['pose'])
                    result.update(oracle_position_error_m=position_error, oracle_rotation_error_deg=rotation_error, pose_class=pose_class(position_error, rotation_error))
                decisions[name].append(dict(query_frame=frame, **result))
                outcome[name] = result
            run('v2_recorded_tested_set_shift0', tested_v2, candidates_shift0)
            run('v2_recorded_tested_set_corrected', tested_v2, candidates_corrected)
            run('flann_replica_tested_set_corrected', tested_flann, candidates_corrected)
            run('per_reference_ratio_top13_corrected', [eligible[position] for position in np.argsort(-scores[frame]['per_reference_ratio'], kind='stable')[:TOP_TESTED]], candidates_corrected)
            run('lightglue_count_top13_corrected', [eligible[position] for position in np.argsort(-method_scores['lightglue_matches'], kind='stable')[:TOP_TESTED]], candidates_corrected)
            run('exhaustive_all_eligible_corrected', eligible, candidates_corrected)
            run('oracle_covisible_only_corrected', sorted(true_set), candidates_corrected)

            per_view = {}
            for label, store in [('shift0', candidates_shift0), ('corrected', candidates_corrected)]:
                accepted_views = [estimate for estimate in store.values() if estimate['per_view_accepted']]
                per_view[label] = dict(candidates=len(store), per_view_accepted=len(accepted_views),
                    per_view_classes={name: sum(pose_class(item['oracle_position_error_m'], item['oracle_rotation_error_deg']) == name for item in accepted_views)
                        for name in ['correct', 'near_0p5_to_2m', 'wrong_place_over_2m']})
            best_true = eligible[int(np.argmax(covisible))] if len(covisible) else None
            per_query.append(dict(query_frame=frame, odometry_row_used_as_truth=truth['row'], capture_seconds=truth['seconds'],
                rotation_speed_deg_s=query['rotation_speed_deg_s'], query_keypoints=int(len(query['features']['keypoints'])),
                query_keypoints_with_own_depth=int(query_valid.sum()), identity_mean_abs_difference_vs_saved_v2_jpeg=query['identity_mean_abs_difference_vs_saved_v2_jpeg'],
                eligible_references=len(eligible), true_overlap_references=len(true_set),
                true_overlap_at_15=int((covisible >= 15).sum()), true_overlap_at_60=int((covisible >= 60).sum()),
                best_covisible_reference=reference_frames[best_true] if best_true is not None else None, best_covisible_points=int(covisible.max()) if len(covisible) else 0,
                true_overlap_reference_frames=sorted(reference_frames[index] for index in true_set),
                recall=recall, cross_image_ratio_audit=ratio_audit, per_view=per_view, outcomes=outcome))
            log(f'query {frame}: true overlaps={len(true_set)} ' + ' '.join(f'{name}={value["accepted"]}' for name, value in outcome.items()))

        # ---------------------------------------------------- reference-reference consistency (same pass vs revisit)
        revisit_rows, neighbour_rows = [], []
        for (kind, first_frame, second_frame), pair in matches.items():
            if kind != 'reference':
                continue
            first_index, second_index = reference_frames.index(first_frame), reference_frames.index(second_frame)
            first, second = reference_geometry[first_index][primary], reference_geometry[second_index][primary]
            gap = abs(references[first_index]['metadata']['capture_seconds'] - references[second_index]['metadata']['capture_seconds'])
            covisible = covisible_count(first['world'], first['valid'], second, second['depth'], references[second_index]['features']['image_size'])[0]
            row = dict(first=first_frame, second=second_frame, time_gap_s=gap, lightglue_matches=len(pair), covisible_points=covisible,
                recorded_camera_distance_m=float(np.linalg.norm(first['pose'][:3, 3] - second['pose'][:3, 3])))
            if len(pair):
                both = first['valid'][pair[:, 0]] & second['valid'][pair[:, 1]]
                row['matches_with_both_depths'] = int(both.sum())
                if both.any():
                    distances = np.linalg.norm(first['world'][pair[:, 0]][both] - second['world'][pair[:, 1]][both], axis=1)
                    row.update(median_3d_disagreement_m=float(np.median(distances)), fraction_3d_under_10cm=float((distances < .10).mean()))
                errors = reprojection_errors(first['world'][pair[:, 0]], first['valid'][pair[:, 0]], references[second_index]['features']['keypoints'][pair[:, 1]], second)
                row.update({f'oracle_{key}': value for key, value in error_summary(errors).items()})
            if len(pair) >= 12:
                reference_view = dict(metadata=dict(references[first_index]['metadata'], world_from_upright_camera=first['pose'].tolist()),
                    features=dict(references[first_index]['features'], world_points=first['world'].astype(np.float32)))
                cv2.setRNGSeed(7)
                estimate = L.solve_pose(references[second_index]['features'], reference_view, np.ascontiguousarray(pair[:, ::-1]), second['calibration'])
                if estimate is not None:
                    position_error, rotation_error = pose_error(estimate, second['pose'])
                    row.update(pnp_per_view_accepted=estimate['per_view_accepted'], pnp_inliers=estimate['inliers'],
                        pnp_position_vs_recorded_m=position_error, pnp_rotation_vs_recorded_deg=rotation_error)
            (revisit_rows if gap > 20 else neighbour_rows).append(row)

    # ---------------------------------------------------- aggregate
    def count(name, predicate=lambda item: item['accepted']):
        return sum(predicate(item) for item in decisions[name])

    decision_summary = {name: dict(accepted=count(name),
        accepted_correct=count(name, lambda item: item['accepted'] and item['pose_class'] == 'correct'),
        accepted_wrong_place=count(name, lambda item: item['accepted'] and item['pose_class'] == 'wrong_place_over_2m'),
        accepted_near=count(name, lambda item: item['accepted'] and item['pose_class'] == 'near_0p5_to_2m')) for name in decisions}
    method_names = list(per_query[0]['recall'].keys())
    retrieval_summary = {}
    for name in method_names:
        if 'first_true_rank' in per_query[0]['recall'][name]:
            ranks = [item['recall'][name]['first_true_rank'] for item in per_query if item['true_overlap_references']]
            retrieval_summary[name] = dict(queries_with_true_overlap=len(ranks), recall_at_1=sum(rank == 1 for rank in ranks), recall_at_5=sum(rank <= 5 for rank in ranks),
                recall_at_13=sum(rank <= 13 for rank in ranks), queries_with_two_true_in_top13=sum(item['recall'][name]['true_in_top13'] >= 2 for item in per_query),
                median_first_true_rank=median(ranks))
        else:
            retrieval_summary[name] = dict(queries_with_any_true_tested=sum(item['recall'][name]['true_in_tested'] >= 1 for item in per_query),
                queries_with_two_true_tested=sum(item['recall'][name]['true_in_tested'] >= 2 for item in per_query))
    ratio_totals = {key: sum(item['cross_image_ratio_audit'][key] for item in per_query) for key in per_query[0]['cross_image_ratio_audit']}
    true_pairs = [row for row in pair_rows if row['true_overlap'] and row['lightglue_matches'] >= 20 and row.get('oracle_fraction_under_3px') is not None]
    false_pairs = [row for row in pair_rows if not row['true_overlap'] and row['lightglue_matches'] >= 50]
    query_matches_true = [row for row in pair_rows if row['true_overlap'] and row['lightglue_matches']]
    correspondence = dict(
        true_overlap_pairs_with_20plus_matches=len(true_pairs),
        median_matches=median([row['lightglue_matches'] for row in true_pairs]),
        median_fraction_with_reference_depth=median([row['matches_with_reference_depth'] / row['lightglue_matches'] for row in true_pairs]),
        median_oracle_fraction_under_3px=median([row['oracle_fraction_under_3px'] for row in true_pairs]),
        median_oracle_reprojection_px=median([row['oracle_reprojection_median_px'] for row in true_pairs]),
        median_3d_disagreement_m=median([row['median_3d_disagreement_m'] for row in true_pairs]),
        invalid_depth_reasons_among_matches_true_overlap={key: sum(row.get(f'invalid_{key}', 0) for row in query_matches_true) for key in ['low_confidence', 'too_far', 'too_near', 'depth_edge']},
        matches_total_true_overlap=sum(row['lightglue_matches'] for row in query_matches_true),
        matches_with_reference_depth_true_overlap=sum(row.get('matches_with_reference_depth', 0) for row in query_matches_true),
        non_overlap_pairs_with_50plus_matches=len(false_pairs),
        non_overlap_50plus_examples=sorted(false_pairs, key=lambda row: -row['lightglue_matches'])[:12])

    def ref_summary(rows_, label):
        good = [row for row in rows_ if row.get('pnp_per_view_accepted')]
        return dict(label=label, pairs=len(rows_), with_12plus_matches=sum(row['lightglue_matches'] >= 12 for row in rows_),
            pnp_per_view_accepted=len(good),
            accepted_pose_within_0p5m=sum(row['pnp_position_vs_recorded_m'] <= .5 for row in good),
            accepted_pose_over_2m=sum(row['pnp_position_vs_recorded_m'] > 2 for row in good),
            median_pnp_position_vs_recorded_m=median([row['pnp_position_vs_recorded_m'] for row in good]),
            median_3d_disagreement_m_for_covisible=median([row.get('median_3d_disagreement_m') for row in rows_ if row['covisible_points'] >= COVISIBLE_MIN]),
            covisible_pairs=sum(row['covisible_points'] >= COVISIBLE_MIN for row in rows_))

    results = dict(
        audit='visual_map_v2 retrieval and cross-view 3D correspondence audit',
        plan_sha256=hashlib.sha256((OUT / 'AUDIT_PLAN.json').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        localizer_sha256=hashlib.sha256((LOCALIZATION / 'mgh_localizer.py').read_bytes()).hexdigest(),
        map_manifest_sha256=hashlib.sha256((MAP / 'manifest.json').read_bytes()).hexdigest(),
        original_zip_sha256=manifest['original_zip_sha256'], torch_version=torch.__version__, cv2_version=cv2.__version__,
        oracle_policy=plan['oracle_policy'], acceptance_rules_unchanged=plan['acceptance_rules_unchanged'],
        shift0_lifting_reproduces_v2_world_points=reproduced, runtime_seconds=time.monotonic() - started,
        timestamp_alignment=timestamp_results, association_shift_test=shift_test, primary_row_minus_ordinal=primary,
        depth_coverage=dict(reference_keypoints=total_keypoints, median_valid_fraction=median(coverage), min_valid_fraction=min(coverage),
            invalid_reason_counts_not_exclusive=reasons_total),
        retrieval_summary=retrieval_summary, cross_image_ratio_totals=ratio_totals, correspondence=correspondence,
        decisions=decision_summary, reference_pairs=dict(neighbours=ref_summary(neighbour_rows, 'temporal neighbours <=20 s'),
            revisits=ref_summary(revisit_rows, 'appearance-selected revisits >20 s')),
        per_query=per_query, decisions_per_query=decisions)
    dump(OUT / 'results.json', results)
    with (OUT / 'query_reference_pairs.csv').open('w', newline='', encoding='utf-8') as stream:
        keys = sorted({key for row in pair_rows for key in row})
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(pair_rows)
    with (OUT / 'reference_pairs.csv').open('w', newline='', encoding='utf-8') as stream:
        all_rows = [dict(row, category='revisit') for row in revisit_rows] + [dict(row, category='neighbour') for row in neighbour_rows]
        keys = sorted({key for row in all_rows for key in row})
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)

    # contact sheet: query | v2 top appearance | oracle best covisible reference
    tiles = []
    for item in per_query:
        frame = item['query_frame']
        top_v2 = v2_by_query[frame]['appearances'][0]['reference_frame'] if v2_by_query[frame]['appearances'] else None
        row = Image.new('RGB', (3 * 230, 200), 'white')
        for column, (label, picture) in enumerate([(f'query {frame}', Image.fromarray(queries[frame]['image'])),
                (f'v2 top match {top_v2}', Image.open(MAP / f'images/frame_{top_v2:06d}.jpg') if top_v2 is not None else None),
                (f'best covisible {item["best_covisible_reference"]} ({item["best_covisible_points"]} pts)', Image.open(MAP / f'images/frame_{item["best_covisible_reference"]:06d}.jpg') if item['best_covisible_reference'] is not None else None)]):
            if picture is not None:
                picture = picture.copy()
                picture.thumbnail((220, 170))
                row.paste(picture, (column * 230 + (220 - picture.width) // 2, 0))
            ImageDraw.Draw(row).text((column * 230 + 4, 182), label, fill='black')
        tiles.append(row)
    sheet = Image.new('RGB', (2 * 3 * 230 + 20, (len(tiles) + 1) // 2 * 205), '#dddddd')
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 2) * (3 * 230 + 20), (index // 2) * 205))
    sheet.save(OUT / 'retrieval_examples.jpg', quality=90)
    log('audit complete: ' + json.dumps(dict(primary=primary, decisions=decision_summary, retrieval=retrieval_summary), indent=1))


if __name__ == '__main__':
    main()
