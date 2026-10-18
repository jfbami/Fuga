import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'outputs/MGH_Project/localization'
sys.path.insert(0, str(LOCAL))
import phone_localizer as phone
import mgh_localizer as core

PHOTOS = ROOT / 'outputs/MGH_Project/capture/independent_phone_20261017'
OUT = LOCAL / 'evaluation_independent_phone_430_440'


def main():
    OUT.mkdir(exist_ok=False)
    manifest = json.loads((PHOTOS / 'manifest.json').read_text())
    # Fix all experimental settings before the first call to feature extraction.
    experiments = []
    for photo in manifest['photos']:
        width, height = photo['normalized_width'], photo['normalized_height']
        focal35 = float(photo['camera_metadata']['FocalLengthIn35mmFilm'])
        focal = focal35 * math.hypot(width, height) / math.hypot(36, 24)
        parameters = dict(width=width, height=height, fx=focal, fy=focal, cx=(width - 1) / 2, cy=(height - 1) / 2,
            distortion=[], provenance='EXIF 35mm equivalent via diagonal crop; centred principal point; no verified calibration or distortion model.',
            calibration_status='exif_estimate')
        name = Path(photo['original_filename']).stem
        core.dump_json(OUT / f'{name}_estimated_intrinsics.json', parameters)
        experiments.append(dict(image=name, parameters=parameters, image_sha256=photo['normalized_sha256']))
    core.dump_json(OUT / 'PLAN.json', dict(photo_manifest_sha256=hashlib.sha256((PHOTOS / 'manifest.json').read_bytes()).hexdigest(),
        experiments=experiments, maps=['visual_map_v3'], methods=['legacy', 'mutual_nn'],
        mnn_selection='top 13 by per-reference exact mutual nearest descriptor count, stable reference-order tie break',
        geometry='unchanged baseline PnP and two-reference consensus; no query depth, room labels or recorded query poses',
        estimated_calibration_never_app_usable=True, no_tuning_on_these_images=True))
    map_manifest, references = core.load_map(LOCAL / 'visual_map_v3')
    extractor, matcher = core.setup_models()
    results = []
    for experiment, photo in zip(experiments, manifest['photos']):
        image, calibration = phone.prepare_query(PHOTOS / photo['normalized_image'], experiment['parameters'])
        for method in ['legacy', 'mutual_nn']:
            # Identical initial RNG state for each independent diagnostic case.
            core.cv2.setRNGSeed(42)
            core.torch.manual_seed(42)
            print(f"Running {experiment['image']} / {method}", flush=True)
            result = phone.localize_phone(image, calibration, references, extractor, matcher, method, 'exif_estimate')
            result.update(image=experiment['image'], query_image_sha256=experiment['image_sha256'],
                map_manifest_sha256=hashlib.sha256((LOCAL / 'visual_map_v3/manifest.json').read_bytes()).hexdigest(),
                baseline_implementation_sha256=hashlib.sha256((LOCAL / 'mgh_localizer.py').read_bytes()).hexdigest(),
                phone_implementation_sha256=hashlib.sha256((LOCAL / 'phone_localizer.py').read_bytes()).hexdigest(),
                room_label_used_by_solver=False)
            core.dump_json(OUT / f"{experiment['image']}_{method}.json", result)
            results.append(result)
            print(json.dumps({k: result.get(k) for k in ['image','retrieval_method','geometric_consensus_accepted','pose_usable_for_app','consistent_support_frames','candidate_position_scan_m']}), flush=True)
    core.dump_json(OUT / 'results.json', dict(results=results, independent_phone_validation_passed=False,
        calibrated_metric_validation=False, navigation_enabled=False))


if __name__ == '__main__':
    main()
