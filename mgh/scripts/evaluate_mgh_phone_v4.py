"""Try the already-predeclared low-rotation map, unchanged retrieval/thresholds."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'outputs/MGH_Project/localization'
sys.path.insert(0,str(LOCAL))
import mgh_localizer as core
import phone_localizer as phone

OUT=LOCAL/'evaluation_independent_phone_430_440'
core.dump_json(OUT/'FOLLOWUP_V4_PLAN.json',dict(
    reason='Evaluate the low-rotation map declared before the independent photos were supplied; not a new map tuned to those photos.',
    images=['IMG_5385','IMG_5386'],map='visual_map_v4_low_rotation',retrieval='legacy',
    calibration='Same EXIF estimates as the primary exploratory diagnostic.',
    geometric_thresholds='unchanged',fresh_held_out_claim=False))
manifest,references=core.load_map(LOCAL/'visual_map_v4_low_rotation')
extractor,matcher=core.setup_models()
for name in ['IMG_5385','IMG_5386']:
    parameters=json.loads((OUT/f'{name}_estimated_intrinsics.json').read_text())
    image,calibration=phone.prepare_query(ROOT/f'outputs/MGH_Project/capture/independent_phone_20261017/normalized/{name}.png',parameters)
    core.cv2.setRNGSeed(42)
    print('Running v4',name,flush=True)
    result=phone.localize_phone(image,calibration,references,extractor,matcher,'legacy','exif_estimate')
    result.update(image=name,map_variant='v4_low_rotation',followup_diagnostic=True)
    core.dump_json(OUT/f'{name}_legacy_v4.json',result)
    print(json.dumps({k:result.get(k) for k in ['image','geometric_consensus_accepted','consistent_support_frames','candidate_position_scan_m']}),flush=True)
