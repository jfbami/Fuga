"""Phone-facing localization adapter with audit-motivated reference retrieval.

The scan's recorded depth is used for map features only. Query inputs are RGB and
optional calibration. Missing/estimated calibration never yields an app-usable pose.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

import mgh_localizer as core


def rank_mutual_nn(query_descriptors, references):
    """Count per-reference mutual nearest descriptors; never use room labels/poses."""
    query = torch.as_tensor(query_descriptors, dtype=torch.float32)
    scores = []
    with torch.inference_mode():
        for reference in references:
            descriptors = torch.as_tensor(reference['features']['descriptors'], dtype=torch.float32)
            if not len(query) or not len(descriptors):
                scores.append(0)
                continue
            distances = query.square().sum(1)[:, None] + descriptors.square().sum(1)[None, :] - 2 * (query @ descriptors.T)
            closest_reference = distances.argmin(1)
            closest_query = distances.argmin(0)
            scores.append(int((closest_query[closest_reference] == torch.arange(len(query))).sum()))
    return sorted(range(len(references)), key=lambda i: (-scores[i], i)), scores


def localize_phone(image, calibration, references, extractor, matcher,
                   retrieval='mutual_nn', calibration_status='missing'):
    if calibration_status not in {'verified', 'exif_estimate', 'missing'}:
        raise ValueError('Unknown calibration status.')
    if calibration_status == 'missing' and calibration is not None:
        raise ValueError('Calibration provenance must be explicit.')
    if calibration_status != 'missing' and calibration is None:
        raise ValueError('Calibration matrix is required for this status.')
    if retrieval == 'legacy':
        result = core.localize(image, calibration, references, extractor, matcher)
        ranking = None
    elif retrieval == 'mutual_nn':
        features = core.features_for_image(image, extractor)
        indices, scores = rank_mutual_nn(features['descriptors'], references)
        selected = indices[:13]
        # Exactly the same matcher, PnP and consensus. With <=13 eligible views,
        # candidate_limit=13 tests every selected reference, regardless of vote order.
        result = core.localize(image, calibration, [references[i] for i in selected],
                               extractor, matcher, candidate_limit=13)
        ranking = [dict(reference_frame=references[i]['metadata']['frame'], mutual_nn_count=scores[i]) for i in selected]
    else:
        raise ValueError('Unknown retrieval method.')
    numerical_acceptance = result['accepted']
    result.update(retrieval_method=retrieval, retrieval_ranking=ranking,
        calibration_status=calibration_status, geometric_consensus_accepted=numerical_acceptance,
        accepted=bool(numerical_acceptance and calibration_status == 'verified'),
        pose_usable_for_app=bool(numerical_acceptance and calibration_status == 'verified'),
        ordinary_phone_validation_passed=False, navigation_enabled=False)
    if numerical_acceptance and calibration_status != 'verified':
        result['candidate_position_scan_m'] = result.pop('position_scan_m')
        result['candidate_rotation_world_camera'] = result.pop('rotation_world_camera')
        result['status'] = 'geometric_hypothesis_requires_verified_calibration'
    return result


def prepare_query(path, parameters=None):
    source = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    width, height = source.size
    factor = 640 / max(width, height)
    image = np.asarray(source.resize((round(width * factor), round(height * factor)), Image.Resampling.LANCZOS))
    if parameters is None:
        return image, None
    if (parameters['width'], parameters['height']) != (width, height):
        raise ValueError('Calibration must match the EXIF-normalized image dimensions.')
    if any(abs(value) > 1e-12 for value in parameters.get('distortion', [])):
        raise ValueError('Provide an undistorted image/calibration pair; distortion is not silently ignored.')
    sx, sy = image.shape[1] / width, image.shape[0] / height
    calibration = np.array([[parameters['fx'] * sx, 0, parameters['cx'] * sx],
                            [0, parameters['fy'] * sy, parameters['cy'] * sy], [0, 0, 1]], dtype=float)
    if not np.isfinite(calibration).all() or calibration[0, 0] <= 0 or calibration[1, 1] <= 0:
        raise ValueError('Invalid calibration matrix.')
    return image, calibration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--map', type=Path, default=core.DEFAULT_MAP)
    parser.add_argument('--intrinsics', type=Path)
    parser.add_argument('--calibration-status', choices=['missing', 'exif_estimate', 'verified'], default='missing')
    parser.add_argument('--retrieval', choices=['legacy', 'mutual_nn'], default='mutual_nn')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve prior results; choose a new path.')
    parameters = json.loads(args.intrinsics.read_text()) if args.intrinsics else None
    image, calibration = prepare_query(args.image, parameters)
    manifest, references = core.load_map(args.map)
    extractor, matcher = core.setup_models()
    result = localize_phone(image, calibration, references, extractor, matcher,
                            args.retrieval, args.calibration_status)
    result.update(image_sha256=hashlib.sha256(args.image.read_bytes()).hexdigest(),
                  map_manifest_sha256=hashlib.sha256((args.map / 'manifest.json').read_bytes()).hexdigest(),
                  implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    core.dump_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
