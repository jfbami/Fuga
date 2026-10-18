"""Fixed-pool diagnostic on already exposed video; no tuning or validation claims."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'outputs/MGH_Project/localization'
sys.path.insert(0,str(LOCAL))
import mgh_localizer as core
import phone_localizer as phone
from geometric_reference_audit import verify_pair
VIDEO=ROOT/'outputs/MGH_Project/capture/independent_video_IMG_5391'
OUT=LOCAL/'audit_video_430_440_geometry'
OUT.mkdir(exist_ok=False);(OUT/'matches').mkdir()
queries=json.loads((VIDEO/'manifest.json').read_text())['samples']
mapping,refs=core.load_map(LOCAL/'visual_map_v4_low_rotation')
by_row={r['metadata']['frame']:r for r in refs}
plan=dict(queries=[s['ordinal'] for s in queries],map='visual_map_v4_low_rotation',
    candidate_pool='Exact references previously tested for each video frame; no room-label candidate additions.',
    fundamental=dict(method='USAC_MAGSAC',threshold_px=1.5,confidence=.999,max_iterations=10000),
    homography=dict(method='USAC_MAGSAC',threshold_px=3.0,confidence=.999,max_iterations=10000),
    diagnostic_rankings=['fundamental_inlier_count','fundamental_inlier_count * sqrt(minimum hull coverage)'],
    minimum_inliers_for_weighted_score=15,planarity_flag='homography inliers >=85% of fundamental inliers; ambiguity only, no calibrated pose claim',
    calibration='missing; no invented intrinsics',room_or_floor_labels_used_by_solver=False,
    threshold_changes_to_core=False,query_depth_or_pose_used=False,held_out_evaluation=False,
    note='All seven frames are exposed development diagnostics from one video. Preserve failures. No app/default retrieval change.',
    map_manifest_sha256=hashlib.sha256((LOCAL/'visual_map_v4_low_rotation/manifest.json').read_bytes()).hexdigest())
core.dump_json(OUT/'PLAN.json',plan)
extractor,matcher=core.setup_models()
all_results=[]
for sample in queries:
    ordinal=sample['ordinal']
    image,_=phone.prepare_query(Path(sample['path']))
    features=core.features_for_image(image,extractor)
    old=json.loads((VIDEO/f'result_ordinal_{ordinal:06d}.json').read_text())
    pairs=[]
    for appearance in old['appearances']:
        row=appearance['reference_frame'];ref=by_row[row]
        with core.torch.inference_mode():
            match=matcher({'image0':core.tensor_features(features),'image1':core.tensor_features(ref['features'])})['matches'][0].cpu().numpy()
        q=features['keypoints'][match[:,0]];r=ref['features']['keypoints'][match[:,1]]
        diagnostic,mask=verify_pair(q,r,features['image_size'],ref['features']['image_size'])
        diagnostic.update(reference_frame=row,legacy_matches=appearance['matches'])
        np.savez_compressed(OUT/'matches'/f'q{ordinal:06d}_ref{row:06d}.npz',query_points=q,reference_points=r,matches=match,fundamental_mask=mask)
        pairs.append(diagnostic)
    ranked_count=sorted(pairs,key=lambda p:(-p['fundamental_inliers'],p['reference_frame']))
    ranked_coverage=sorted(pairs,key=lambda p:(-p['coverage_weighted_score'],p['reference_frame']))
    result=dict(ordinal=ordinal,capture_timestamp_ms=sample['decoder_timestamp_ms'],legacy_top=old['appearances'][:3],
        fundamental_top=ranked_count[:3],coverage_top=ranked_coverage[:3],pairs=pairs,
        accepted=False,pose_usable_for_app=False,navigation_enabled=False)
    core.dump_json(OUT/f'query_{ordinal:06d}.json',result)
    all_results.append(result)
    print(json.dumps(dict(ordinal=ordinal,legacy_top=old['appearances'][0]['reference_frame'],
        fundamental_top=[(x['reference_frame'],x['fundamental_inliers']) for x in ranked_count[:3]],
        coverage_top=[(x['reference_frame'],round(x['coverage_weighted_score'],2)) for x in ranked_coverage[:3]])),flush=True)
    # All illustrations stay private, including independent-phone pixels.
    canvas=Image.new('RGB',(1280,340),'white');draw=ImageDraw.Draw(canvas)
    items=[(Path(sample['path']),f'Query {ordinal} / {sample["decoder_timestamp_ms"]/1000:.2f}s')]
    for p in ranked_coverage[:3]:items.append((LOCAL/'visual_map_v4_low_rotation'/by_row[p['reference_frame']]['metadata']['image'],f'Row {p["reference_frame"]} | F {p["fundamental_inliers"]} | score {p["coverage_weighted_score"]:.1f}'))
    for col,(path,label) in enumerate(items):
        picture=Image.open(path).convert('RGB');picture.thumbnail((310,300))
        canvas.paste(picture,(col*320+(310-picture.width)//2,30));draw.text((col*320+4,5),label,fill='black')
    canvas.save(OUT/f'comparison_{ordinal:06d}.jpg',quality=93)
core.dump_json(OUT/'results.json',dict(plan=plan,results=all_results))
print('DONE',flush=True)
