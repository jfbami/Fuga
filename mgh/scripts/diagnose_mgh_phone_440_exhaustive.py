"""Determine whether 440 lacks retrieval or geometric support; no thresholds change."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'outputs/MGH_Project/localization'
sys.path.insert(0, str(LOCAL))
import mgh_localizer as core
import phone_localizer as phone

OUT = LOCAL / 'evaluation_independent_phone_430_440'
photo = ROOT / 'outputs/MGH_Project/capture/independent_phone_20261017/normalized/IMG_5386.png'
core.dump_json(OUT / 'FOLLOWUP_EXHAUSTIVE_PLAN.json', dict(image_sha256=hashlib.sha256(photo.read_bytes()).hexdigest(),
    reason='Both predeclared retrieval methods yielded only one consistent reference for the independent 440 photo.',
    test='Match all 125 v3 references with unchanged matcher, PnP and two-reference rules; diagnostic follow-up, not fresh held-out validation.',
    calibration='Same EXIF estimate as primary diagnostic; no metric accuracy or app-ready pose claim.'))
manifest, references = core.load_map(LOCAL / 'visual_map_v3')
parameters = json.loads((OUT / 'IMG_5386_estimated_intrinsics.json').read_text())
image, calibration = phone.prepare_query(photo, parameters)
extractor, matcher = core.setup_models()
result = core.localize(image, calibration, references, extractor, matcher, candidate_limit=len(references))
result.update(image='IMG_5386', diagnostic='exhaustive_all_v3_references', calibration_status='exif_estimate',
    geometric_consensus_accepted=result['accepted'], accepted=False, pose_usable_for_app=False,
    navigation_enabled=False, independent_phone_validation_passed=False)
if 'position_scan_m' in result:
    result['candidate_position_scan_m'] = result.pop('position_scan_m')
    result['candidate_rotation_world_camera'] = result.pop('rotation_world_camera')
core.dump_json(OUT / 'IMG_5386_exhaustive_v3.json', result)
print(json.dumps({k:result.get(k) for k in ['geometric_consensus_accepted','consistent_support_frames','candidate_position_scan_m','references_tested']},indent=2),flush=True)
