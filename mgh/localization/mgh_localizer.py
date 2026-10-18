import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

WORKSPACE = Path(os.environ.get('MGH_WORKSPACE', Path(__file__).resolve().parents[3]))
if (WORKSPACE / 'work/LightGlue').exists():
    sys.path.insert(0, str(WORKSPACE / 'work/LightGlue'))

import cv2
import numpy as np
import torch
from lightglue import DISK, LightGlue
from PIL import Image, ImageDraw, ImageOps

SCAN_ID = 'b9dca4993d'
DEFAULT_MAP = Path(__file__).resolve().parent / 'visual_map_v3'
ASSOCIATION = 'sequential decoded video ordinal + timestamp-fingerprint-verified offset -> odometry/depth row; no CAP_PROP_POS_FRAMES seeking'


class BlobReader(io.RawIOBase):
    def __init__(self, blob):
        self.blob = blob

    def readable(self):
        return True

    def seekable(self):
        return True

    def read(self, size=-1):
        return self.blob.read(size)

    def seek(self, offset, whence=0):
        self.blob.seek(offset, whence)
        return self.blob.tell()

    def tell(self):
        return self.blob.tell()


def dump_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')


def camera_pose(row):
    quaternion = np.array([float(row[key]) for key in ['qx', 'qy', 'qz', 'qw']])
    quaternion /= np.linalg.norm(quaternion)
    quat_x, quat_y, quat_z, quat_w = quaternion
    transform = np.eye(4)
    transform[:3, :3] = [
        [1 - 2 * (quat_y**2 + quat_z**2), 2 * (quat_x * quat_y - quat_z * quat_w), 2 * (quat_x * quat_z + quat_y * quat_w)],
        [2 * (quat_x * quat_y + quat_z * quat_w), 1 - 2 * (quat_x**2 + quat_z**2), 2 * (quat_y * quat_z - quat_x * quat_w)],
        [2 * (quat_x * quat_z - quat_y * quat_w), 2 * (quat_y * quat_z + quat_x * quat_w), 1 - 2 * (quat_x**2 + quat_y**2)],
    ]
    transform[:3, 3] = [float(row[key]) for key in ['x', 'y', 'z']]
    return transform


@contextmanager
def source_archive():
    connection = sqlite3.connect((WORKSPACE / 'outputs/MGH_Master.sqlite').as_uri() + '?mode=ro', uri=True)
    asset = connection.execute('SELECT blob_id,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE logical_path=?',
        (f'scans/{SCAN_ID}/original/MGH Staircase.zip',)).fetchone()
    if asset is None:
        connection.close()
        raise ValueError('Original staircase recording is not embedded in the canonical master.')
    try:
        with connection.blobopen('blobs', 'content', asset[0], readonly=True) as blob:
            with zipfile.ZipFile(BlobReader(blob)) as archive:
                yield archive, asset[1]
    finally:
        connection.close()


def source_video():
    return WORKSPACE / f'work/localization_inputs/{SCAN_ID}/rgb.mp4'


def source_inputs(archive):
    poses = list(csv.DictReader(io.StringIO(archive.read(f'{SCAN_ID}/odometry.csv').decode()), skipinitialspace=True))
    video = source_video()
    video.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(f'{SCAN_ID}/rgb.mp4') as source, video.open('wb') as destination:
        shutil.copyfileobj(source, destination)
    return poses, cv2.VideoCapture(str(video))


def verified_row_offset(video, poses):
    """Find the odometry/depth row shown by each decoded video ordinal from the dropped-frame timestamp pattern.

    Reads presentation timestamps sequentially without decoding pixels. The recording must contain enough
    irregular gaps, exactly one offset must agree with every gap, and the residual must stay under one frame.
    """
    capture = cv2.VideoCapture(str(video))
    stamps = []
    while capture.grab():
        stamps.append(capture.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    capture.release()
    stamps = np.array(stamps)
    rows = np.array([float(row['timestamp']) for row in poses])
    rows -= rows[0]
    gaps = int((np.diff(rows) > .03).sum())
    if gaps < 10:
        raise ValueError('Too few dropped-frame gaps to verify video/odometry association; do not assume ordinal == row.')
    fits = []
    for offset in range(-5, 6):
        ordinals = np.arange(len(stamps))
        keep = (ordinals + offset >= 0) & (ordinals + offset < len(rows))
        video_times, row_times = stamps[keep], rows[ordinals[keep] + offset]
        residual = (video_times - video_times[0]) - (row_times - row_times[0])
        fits.append(dict(offset=offset, gap_agreement=float(((np.diff(video_times) > .03) == (np.diff(row_times) > .03)).mean()),
            max_residual_seconds=float(np.abs(residual - np.median(residual)).max())))
    exact = [fit for fit in fits if fit['gap_agreement'] == 1 and fit['max_residual_seconds'] < .0125]
    if len(exact) != 1:
        raise ValueError(f'Video/odometry association is ambiguous or inconsistent: {fits}')
    return dict(verified=True, row_minus_decoded_ordinal=exact[0]['offset'], decoded_frames=len(stamps), odometry_rows=len(rows),
        odometry_gaps_over_30ms=gaps, gap_agreement=exact[0]['gap_agreement'], max_residual_seconds=exact[0]['max_residual_seconds'],
        method='CAP_PROP_POS_MSEC after sequential grab vs odometry timestamps; irregular-gap fingerprint')


def turning_speed(poses, frame):
    """Camera rotation rate (degrees/second) from recorded poses over +-3 rows."""
    lower, upper = max(frame - 3, 0), min(frame + 3, len(poses) - 1)
    elapsed = float(poses[upper]['timestamp']) - float(poses[lower]['timestamp'])
    return angular_disagreement(camera_pose(poses[lower])[:3, :3], camera_pose(poses[upper])[:3, :3]) / elapsed if elapsed > 0 else float('inf')


def calibration_for_row(row):
    return np.array([[float(row['fx']), 0, float(row['cx'])], [0, float(row['fy']), float(row['cy'])], [0, 0, 1]])


def decode_selected_frames(capture, frame_numbers):
    requested = sorted(set(int(frame) for frame in frame_numbers))
    if not requested or requested[0] < 0:
        raise ValueError('Select at least one nonnegative decoded frame index.')
    if int(capture.get(cv2.CAP_PROP_POS_FRAMES)) != 0:
        raise ValueError('Sequential indexing requires a freshly opened video capture.')
    selected = set(requested)
    for frame in range(requested[-1] + 1):
        if not capture.grab():
            raise RuntimeError(f'Sequential decode ended before requested frame {frame}.')
        if frame in selected:
            success, pixels = capture.retrieve()
            if not success:
                raise RuntimeError(f'Cannot retrieve decoded frame {frame}.')
            yield frame, pixels


def orient_scan_image(pixels, row):
    raw_height, raw_width = pixels.shape[:2]
    factor = 640 / max(raw_width, raw_height)
    width, height = round(raw_width * factor), round(raw_height * factor)
    image = cv2.cvtColor(cv2.resize(pixels, (width, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    scale = np.diag([width / raw_width, height / raw_height, 1.0])
    pose = camera_pose(row)
    up_camera = pose[:3, :3].T @ np.array([0, 1, 0])
    quarter_turns = int(round(math.atan2(up_camera[0], -up_camera[1]) / (math.pi / 2))) % 4
    image_transforms = [np.eye(3), np.array([[0, 1, 0], [-1, 0, width - 1], [0, 0, 1]]),
        np.array([[-1, 0, width - 1], [0, -1, height - 1], [0, 0, 1]]),
        np.array([[0, -1, height - 1], [1, 0, 0], [0, 0, 1]])]
    camera_rotations = [np.eye(3), np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]]),
        np.diag([-1, -1, 1]), np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])]
    homography = image_transforms[quarter_turns] @ scale
    image = np.ascontiguousarray(np.rot90(image, quarter_turns))
    rotation = camera_rotations[quarter_turns]
    calibration = homography @ calibration_for_row(row) @ rotation.T
    upright_pose = pose.copy()
    upright_pose[:3, :3] = pose[:3, :3] @ rotation.T
    return image, homography, calibration, upright_pose, (raw_width, raw_height)


def features_for_image(image, extractor):
    tensor = torch.from_numpy(np.ascontiguousarray(image.transpose(2, 0, 1))).float() / 255
    features = extractor.extract(tensor, resize=None)
    return {key: value[0].detach().cpu().numpy() for key, value in features.items() if isinstance(value, torch.Tensor)}


def lift_points(archive, frame, points, homography, row, raw_size):
    depth = np.array(Image.open(io.BytesIO(archive.read(f'{SCAN_ID}/depth/{frame:06d}.png'))))
    confidence = np.array(Image.open(io.BytesIO(archive.read(f'{SCAN_ID}/confidence/{frame:06d}.png'))))
    native = np.column_stack([points, np.ones(len(points))]) @ np.linalg.inv(homography).T
    columns = np.clip(np.rint(native[:, 0] * depth.shape[1] / raw_size[0]).astype(int), 1, depth.shape[1] - 2)
    rows = np.clip(np.rint(native[:, 1] * depth.shape[0] / raw_size[1]).astype(int), 1, depth.shape[0] - 2)
    patches = np.stack([depth[rows + row_offset, columns + column_offset] for row_offset in [-1, 0, 1] for column_offset in [-1, 0, 1]], axis=1)
    valid = (confidence[rows, columns] == 2) & (patches.min(axis=1) >= 250) & (patches.max(axis=1) < 4800) & (np.ptp(patches.astype(np.int32), axis=1) <= 150)
    distances = np.median(patches, axis=1) / 1000
    camera_points = np.column_stack([(native[:, 0] - float(row['cx'])) / float(row['fx']) * distances,
        (native[:, 1] - float(row['cy'])) / float(row['fy']) * distances, distances])
    pose = camera_pose(row)
    world = camera_points @ pose[:3, :3].T + pose[:3, 3]
    world[~valid] = np.nan
    return world.astype(np.float32), valid


def setup_models(with_matcher=True):
    torch.set_num_threads(4)
    torch.manual_seed(42)
    cv2.setNumThreads(4)
    cv2.setRNGSeed(42)
    torch.hub.set_dir(str(WORKSPACE / 'work/mgh_model_weights'))
    extractor = DISK(max_num_keypoints=1024).eval().cpu()
    matcher = LightGlue(features='disk').eval().cpu() if with_matcher else None
    return extractor, matcher


def build(arguments):
    destination = arguments.map
    if destination.exists():
        raise ValueError('Choose a new map output directory; completed or partial builds are preserved.')
    destination.mkdir(parents=True)
    (destination / 'images').mkdir()
    (destination / 'features').mkdir()
    extractor, unused_matcher = setup_models(False)
    started = time.monotonic()
    references, rejected = [], []
    with source_archive() as (archive, checksum):
        poses, capture = source_inputs(archive)
        association = verified_row_offset(source_video(), poses)
        offset = association['row_minus_decoded_ordinal']
        decodable = lambda ordinal: 0 <= ordinal < association['decoded_frames'] and 0 <= ordinal + offset < len(poses)
        if arguments.selection == 'stride':
            ordinals = [ordinal for ordinal in range(0, len(poses) - 1, arguments.stride) if decodable(ordinal)]
        else:
            # lowest recorded turning speed inside each stride window: fast rotation makes RGB/depth/pose disagree
            ordinals = []
            for start in range(0, len(poses) - 1, arguments.stride):
                window = [ordinal for ordinal in range(start, start + arguments.stride) if decodable(ordinal)]
                if window:
                    ordinals.append(min(window, key=lambda ordinal: turning_speed(poses, ordinal + offset)))
        for ordinal, pixels in decode_selected_frames(capture, ordinals):
            frame = ordinal + offset
            image, homography, calibration, pose, raw_size = orient_scan_image(pixels, poses[frame])
            sharpness = float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())
            if sharpness < 15 or abs(pose[1, 2]) > .85:
                rejected.append(dict(frame=frame, reason='blur_or_near_vertical_view', sharpness=sharpness))
                continue
            features = features_for_image(image, extractor)
            world, valid = lift_points(archive, frame, features['keypoints'], homography, poses[frame], raw_size)
            if valid.sum() < 30:
                rejected.append(dict(frame=frame, reason='too_few_confident_3d_features', count=int(valid.sum())))
                continue
            image_path, feature_path = f'images/row_{frame:06d}.jpg', f'features/row_{frame:06d}.npz'
            Image.fromarray(image).save(destination / image_path, quality=94)
            np.savez_compressed(destination / feature_path, **features, world_points=world, valid_depth=valid)
            capture_time = float(poses[frame]['timestamp']) - float(poses[0]['timestamp'])
            references.append(dict(frame=frame, odometry_row=frame, decoded_video_ordinal=ordinal, turning_deg_s=turning_speed(poses, frame),
                capture_seconds=capture_time, image=image_path, features=feature_path,
                width=image.shape[1], height=image.shape[0], keypoints=len(world), confident_3d_points=int(valid.sum()),
                floor_hint=3 if capture_time < 18 else 4 if capture_time > 48 else None,
                floor_hint_boundaries_verified=False, sharpness=sharpness, calibration=calibration.tolist(),
                world_from_upright_camera=pose.tolist(), raw_to_reference_pixels=homography.tolist()))
            if len(references) % 20 == 0:
                print(f'Built {len(references)} reference views at frame {frame}', flush=True)
        capture.release()
    if len(references) < 10:
        raise ValueError('Insufficient reference coverage; partial artifacts preserved for inspection.')
    weights = []
    for path in sorted((WORKSPACE / 'work/mgh_model_weights').rglob('*.pth')):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        weights.append(dict(filename=path.name, sha256=digest, bytes=path.stat().st_size))
    manifest = dict(format='MGH visual reference map v3', scan_id=SCAN_ID, coordinate_frame_id=f'scan:{SCAN_ID}',
        original_zip_sha256=checksum, feature_extractor='pretrained DISK depth weights', max_keypoints=1024,
        matching='pretrained LightGlue disk; geometric PnP verification', device='cpu',
        learned_building_specific_weights=False, features_use_recorded_depth_and_pose=True,
        query_solver_requires_depth=False, registered_to_building=False, enabled_navigation=False,
        torch_version=torch.__version__, cv2_version=cv2.__version__, weights_at_build=weights,
        video_frame_selection=ASSOCIATION, video_association=association,
        frame_index_meaning='frame = odometry/depth row (acquisition index); decoded_video_ordinal = frame - row_minus_decoded_ordinal',
        reference_selection=dict(mode=arguments.selection, stride_rows=arguments.stride),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        stride_frames=arguments.stride, reference_count=len(references), total_confident_3d_features=sum(item['confident_3d_points'] for item in references),
        runtime_seconds=time.monotonic() - started, rejected_frames=rejected, references=references,
        limitations=['Recorded-pose/depth map without global optimization.', 'No independent phone test.', 'Floor hints are approximate capture context, not an input to query retrieval.', 'No verified doorway anchors or enabled route graph.'])
    dump_json(destination / 'manifest.json', manifest)
    tiles = []
    for reference in references[::max(1, len(references) // 36)][:36]:
        picture = Image.open(destination / reference['image'])
        picture.thumbnail((240, 180))
        tile = Image.new('RGB', (250, 215), 'white')
        tile.paste(picture, ((250 - picture.width) // 2, 0))
        ImageDraw.Draw(tile).text((5, 185), f"{reference['capture_seconds']:.1f}s | row {reference['frame']}", fill='black')
        tiles.append(tile)
    sheet = Image.new('RGB', (1500, math.ceil(len(tiles) / 6) * 215), '#dddddd')
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 6) * 250, (index // 6) * 215))
    sheet.save(destination / 'reference_contact_sheet.jpg', quality=94)
    print(json.dumps({key: value for key, value in manifest.items() if key not in {'references', 'rejected_frames'}}, indent=2), flush=True)


def load_map(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('video_frame_selection') != ASSOCIATION or not manifest.get('video_association', {}).get('verified'):
        raise ValueError('Legacy reference map: v1 used random seeking and v2 paired decoded ordinal i with row i (one frame early). '
            'Preserve them as diagnostics and rebuild with the timestamp-verified association.')
    references = []
    for metadata in manifest['references']:
        with np.load(directory / metadata['features'], allow_pickle=False) as saved:
            references.append(dict(metadata=metadata, features={key: saved[key].copy() for key in saved.files}))
    return manifest, references


def tensor_features(features):
    return {key: torch.from_numpy(features[key].astype(np.float32))[None] for key in ['keypoints', 'descriptors', 'image_size']}


def angular_disagreement(first, second):
    return float(np.degrees(np.arccos(np.clip((np.trace(first.T @ second) - 1) / 2, -1, 1))))


def solve_pose(query, reference, matches, calibration):
    world = reference['features']['world_points'][matches[:, 1]]
    valid = np.isfinite(world).all(axis=1)
    world = np.ascontiguousarray(world[valid], dtype=np.float64)
    pixels = np.ascontiguousarray(query['keypoints'][matches[valid, 0]], dtype=np.float64)
    if len(world) < 12:
        return None
    success, rotation_vector, translation_vector, inliers = cv2.solvePnPRansac(world, pixels, calibration, None,
        iterationsCount=1000, reprojectionError=4, confidence=.999, flags=cv2.SOLVEPNP_EPNP)
    if not success or inliers is None or len(inliers) < 8:
        return None
    selected = inliers.ravel()
    rotation_vector, translation_vector = cv2.solvePnPRefineLM(world[selected], pixels[selected], calibration, None, rotation_vector, translation_vector)
    projected, unused_jacobian = cv2.projectPoints(world[selected], rotation_vector, translation_vector, calibration, None)
    residual = np.linalg.norm(projected.reshape(-1, 2) - pixels[selected], axis=1)
    camera_from_world = cv2.Rodrigues(rotation_vector)[0]
    position = -camera_from_world.T @ translation_vector.ravel()
    area = float(cv2.contourArea(cv2.convexHull(pixels[selected].astype(np.float32))) / np.prod(query['image_size']))
    positive_depth = bool(np.all((world[selected] @ camera_from_world.T + translation_vector.ravel())[:, 2] > 0))
    reference_position = np.array(reference['metadata']['world_from_upright_camera'])[:3, 3]
    accepted = len(selected) >= 15 and len(selected) / len(world) >= .35 and float(np.median(residual)) < 3 and area >= .01 and positive_depth and np.linalg.norm(position - reference_position) < 6
    return dict(reference_frame=reference['metadata']['frame'], reference_capture_seconds=reference['metadata']['capture_seconds'],
        matches_with_valid_depth=len(world), inliers=len(selected), inlier_ratio=len(selected) / len(world),
        median_reprojection_px=float(np.median(residual)), inlier_image_area_fraction=area,
        per_view_accepted=bool(accepted), position_scan_m=position.tolist(), rotation_world_camera=camera_from_world.T.tolist())


@torch.inference_mode()
def localize(image, calibration, references, extractor, matcher, excluded_time=None, candidate_limit=10):
    started = time.monotonic()
    query = features_for_image(image, extractor)
    eligible = [reference for reference in references if excluded_time is None or abs(reference['metadata']['capture_seconds'] - excluded_time) >= 2]
    if len(query['descriptors']) < 15 or not eligible:
        return dict(accepted=False, status='insufficient_features_or_references', runtime_seconds=time.monotonic() - started)
    retrieval = cv2.FlannBasedMatcher({'algorithm': 1, 'trees': 4}, {'checks': 64})
    retrieval.add([reference['features']['descriptors'].astype(np.float32) for reference in eligible])
    retrieval.train()
    neighbors = retrieval.knnMatch(query['descriptors'].astype(np.float32), k=2)
    votes = np.zeros(len(eligible))
    for pair in neighbors:
        if len(pair) == 2 and pair[0].distance < .85 * pair[1].distance:
            votes[pair[0].imgIdx] += 1
    query_mean = query['descriptors'].mean(axis=0)
    query_mean /= max(float(np.linalg.norm(query_mean)), 1e-9)
    means = np.array([reference['features']['descriptors'].mean(axis=0) for reference in eligible])
    means /= np.maximum(np.linalg.norm(means, axis=1, keepdims=True), 1e-9)
    vote_order = np.argsort(votes)[::-1][:candidate_limit]
    mean_order = np.argsort(means @ query_mean)[::-1][:3]
    indices = list(dict.fromkeys([int(index) for index in vote_order] + [int(index) for index in mean_order]))
    query_tensors = tensor_features(query)
    candidates, appearances = [], []
    for index in indices:
        reference = eligible[index]
        prediction = matcher({'image0': query_tensors, 'image1': tensor_features(reference['features'])})
        matches = prediction['matches'][0].cpu().numpy()
        appearances.append(dict(reference_frame=reference['metadata']['frame'], matches=len(matches), retrieval_votes=int(votes[index])))
        if calibration is not None and len(matches) >= 12:
            estimate = solve_pose(query, reference, matches, calibration)
            if estimate is not None:
                candidates.append(estimate)
    verified = [candidate for candidate in candidates if candidate['per_view_accepted']]
    clusters = [[other for other in verified if np.linalg.norm(np.array(candidate['position_scan_m']) - np.array(other['position_scan_m'])) < .75
        and angular_disagreement(np.array(candidate['rotation_world_camera']), np.array(other['rotation_world_camera'])) < 10] for candidate in verified]
    best_cluster = max(clusters, key=lambda cluster: (len(cluster), sum(item['inliers'] for item in cluster)), default=[])
    independent_support = len(best_cluster) >= 2 and max(item['reference_capture_seconds'] for item in best_cluster) - min(item['reference_capture_seconds'] for item in best_cluster) >= .5
    result = dict(accepted=bool(independent_support), status='pose_candidate_consistent' if independent_support else 'appearance_only_unverified' if calibration is None else 'insufficient_consistent_geometric_support',
        coordinate_frame_id=f'scan:{SCAN_ID}', navigation_enabled=False, references_tested=len(indices),
        consistent_support_frames=[item['reference_frame'] for item in best_cluster],
        appearances=sorted(appearances, key=lambda item: item['matches'], reverse=True), candidates=candidates,
        runtime_seconds=time.monotonic() - started)
    if independent_support:
        best = max(best_cluster, key=lambda item: item['inliers'])
        result.update(position_scan_m=best['position_scan_m'], rotation_world_camera=best['rotation_world_camera'])
    return result


def evaluate(arguments):
    if arguments.output.exists():
        raise ValueError('Preserve prior evaluations; choose a new output directory.')
    arguments.output.mkdir(parents=True)
    manifest, references = load_map(arguments.map)
    extractor, matcher = setup_models()
    results = []
    with source_archive() as (archive, unused_checksum):
        poses, capture = source_inputs(archive)
        association = verified_row_offset(source_video(), poses)
        if association['row_minus_decoded_ordinal'] != manifest['video_association']['row_minus_decoded_ordinal']:
            raise RuntimeError('Evaluation video association differs from the map build; do not mix associations.')
        offset = association['row_minus_decoded_ordinal']
        stride = manifest['stride_frames']
        # query selection is by decoded RGB ordinal so the same images can be compared across map versions
        query_ordinals = arguments.query_ordinals or [int(frame // stride * stride + max(1, stride // 2)) for frame in np.linspace(600, len(poses) - 300, arguments.queries).astype(int)]
        reference_ordinals = {reference['metadata']['decoded_video_ordinal'] for reference in references}
        for ordinal, pixels in decode_selected_frames(capture, query_ordinals):
            if ordinal in reference_ordinals:
                raise RuntimeError('Held-out query accidentally occurs in reference map.')
            frame = ordinal + offset
            image, unused_homography, calibration, recorded_pose, unused_size = orient_scan_image(pixels, poses[frame])
            timestamp = float(poses[frame]['timestamp']) - float(poses[0]['timestamp'])
            result = localize(image, calibration, references, extractor, matcher, excluded_time=timestamp)
            result.update(query_frame=frame, query_odometry_row=frame, query_decoded_video_ordinal=ordinal, capture_seconds=timestamp,
                query_turning_deg_s=turning_speed(poses, frame))
            Image.fromarray(image).save(arguments.output / f'query_row_{frame:06d}.jpg', quality=94)
            if result['accepted']:
                result['position_disagreement_with_recorded_pose_m'] = float(np.linalg.norm(np.array(result['position_scan_m']) - recorded_pose[:3, 3]))
                result['orientation_disagreement_with_recorded_pose_degrees'] = angular_disagreement(np.array(result['rotation_world_camera']), recorded_pose[:3, :3])
                result['within_0_5m_10degrees_of_recorded_pose'] = result['position_disagreement_with_recorded_pose_m'] <= .5 and result['orientation_disagreement_with_recorded_pose_degrees'] <= 10
            results.append(result)
            print(f'Query row {frame} (ordinal {ordinal}): accepted={result["accepted"]}, support={result.get("consistent_support_frames")}, position_disagreement={result.get("position_disagreement_with_recorded_pose_m")}', flush=True)
            dump_json(arguments.output / 'progress.json', dict(results=results))
        capture.release()
    accepted = [result for result in results if result['accepted']]
    summary = dict(test_type='Withheld images from SAME recording; temporal exclusion >=2s. Not an independent-phone or surveyed accuracy test.',
        query_set_label=arguments.query_set_label, query_decoded_video_ordinals=query_ordinals,
        feature_extractor='DISK', matcher='LightGlue disk', map_manifest_sha256=hashlib.sha256((arguments.map / 'manifest.json').read_bytes()).hexdigest(),
        video_frame_selection=ASSOCIATION, video_association=association,
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reference_count=manifest['reference_count'], query_count=len(results), accepted_queries=len(accepted),
        accepted_within_0_5m_10degrees_of_recorded_pose=sum(result['within_0_5m_10degrees_of_recorded_pose'] for result in accepted),
        median_runtime_seconds=float(np.median([result['runtime_seconds'] for result in results])),
        query_depth_used_for_solver=False, recorded_query_pose_used_for_solver=False, query_intrinsics_used=True,
        temporal_exclusion_seconds=2, independent_phone_test_passed=False, navigation_ready=False,
        acceptance_rules=dict(min_inliers=15, min_ratio=.35, max_median_reprojection_px=3, min_image_area_fraction=.01,
            max_reference_camera_distance_m=6, min_consistent_references=2, max_pose_spread_m=.75,
            max_pose_rotation_spread_degrees=10, min_support_time_spread_seconds=.5), results=results)
    dump_json(arguments.output / 'results.json', summary)
    print(json.dumps({key: value for key, value in summary.items() if key != 'results'}, indent=2), flush=True)


def query(arguments):
    if arguments.output.exists():
        raise ValueError('Choose a new query result path; existing results are preserved.')
    manifest, references = load_map(arguments.map)
    source = ImageOps.exif_transpose(Image.open(arguments.image)).convert('RGB')
    width, height = source.size
    factor = 640 / max(width, height)
    image = np.asarray(source.resize((round(width * factor), round(height * factor)), Image.Resampling.LANCZOS))
    calibration = None
    if arguments.intrinsics:
        parameters = json.loads(arguments.intrinsics.read_text())
        if parameters['width'] != width or parameters['height'] != height:
            raise ValueError('Intrinsics dimensions must match the EXIF-normalized image, not a different phone or orientation.')
        if any(abs(value) > 1e-12 for value in parameters.get('distortion', [])):
            raise ValueError('This prototype requires an undistorted image/calibration pair; do not ignore nonzero lens distortion.')
        calibration = np.array([[parameters['fx'] * image.shape[1] / width, 0, parameters['cx'] * image.shape[1] / width],
            [0, parameters['fy'] * image.shape[0] / height, parameters['cy'] * image.shape[0] / height], [0, 0, 1]], dtype=float)
    extractor, matcher = setup_models()
    result = localize(image, calibration, references, extractor, matcher)
    result.update(source_image=str(arguments.image.resolve()), image_sha256=hashlib.sha256(arguments.image.read_bytes()).hexdigest(),
        calibration_source=str(arguments.intrinsics.resolve()) if arguments.intrinsics else None,
        ordinary_phone_validation=False, registered_to_building=manifest['registered_to_building'])
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    dump_json(arguments.output, result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description='MGH research-only RGB-to-depth-reference localization. No routing is enabled.')
    commands = parser.add_subparsers(dest='command', required=True)
    build_parser = commands.add_parser('build')
    build_parser.add_argument('--map', type=Path, default=DEFAULT_MAP)
    build_parser.add_argument('--stride', type=int, default=90)
    build_parser.add_argument('--selection', choices=['stride', 'low_rotation'], default='stride',
        help='stride: every Nth decoded ordinal; low_rotation: slowest-turning frame in each stride window')
    evaluate_parser = commands.add_parser('evaluate')
    evaluate_parser.add_argument('--map', type=Path, default=DEFAULT_MAP)
    evaluate_parser.add_argument('--output', type=Path, required=True)
    evaluate_parser.add_argument('--queries', type=int, default=20)
    evaluate_parser.add_argument('--query-ordinals', type=lambda text: [int(value) for value in text.split(',')],
        help='comma-separated decoded RGB ordinals (overrides --queries); declare held-out sets before running')
    evaluate_parser.add_argument('--query-set-label', default='default_linspace')
    query_parser = commands.add_parser('query')
    query_parser.add_argument('--map', type=Path, default=DEFAULT_MAP)
    query_parser.add_argument('--image', type=Path, required=True)
    query_parser.add_argument('--intrinsics', type=Path)
    query_parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == 'build' and arguments.stride <= 0:
        parser.error('--stride must be positive')
    if arguments.command == 'evaluate' and arguments.queries <= 0:
        parser.error('--queries must be positive')
    {'build': build, 'evaluate': evaluate, 'query': query}[arguments.command](arguments)


if __name__ == '__main__':
    main()
