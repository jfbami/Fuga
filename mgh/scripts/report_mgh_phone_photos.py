"""Preserve independent-photo findings and the user's clarified app goal."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'outputs/MGH_Project'
LOCAL=PROJECT/'localization'
OUT=LOCAL/'evaluation_independent_phone_430_440'


def main():
    variants=[('v3 / legacy','legacy'),('v3 / mutual-NN','mutual_nn'),('v4 / legacy','legacy_v4')]
    rows=[]
    runs=[]
    for name in ['IMG_5385','IMG_5386']:
        for label,suffix in variants:
            path=OUT/f'{name}_{suffix}.json'
            result=json.loads(path.read_text())
            runs.append(dict(image=name,variant=label,results=path.name,
                geometric_consensus_accepted=result['geometric_consensus_accepted'],
                support_rows=result['consistent_support_frames'],pose_usable_for_app=result['pose_usable_for_app']))
            rows.append(f"| {name} ({'430' if name=='IMG_5385' else '440'}) | {label} | {'yes' if result['geometric_consensus_accepted'] else 'no'} | {result['consistent_support_frames']} | no |")
    exhaustive=json.loads((OUT/'IMG_5386_exhaustive_v3.json').read_text())
    http=json.loads((OUT/'http_smoke_result.json').read_text())
    summary=dict(photos_received=2,camera='iPhone 14 rear wide, 5.7mm, 26mm equivalent',
        originals_kept_out_of_mapping=True,independent_phone_validation_passed=False,
        verified_calibration_available=False,surveyed_camera_positions_available=False,
        room_labels_used_by_solver=False,thresholds_changed=False,
        runs=runs,exhaustive_440=dict(references_tested=exhaustive['references_tested'],
            geometric_consensus_accepted=exhaustive['geometric_consensus_accepted'],support_rows=exhaustive['consistent_support_frames']),
        real_http_smoke=dict(status=http['http_status'],frame_identity_echoed=True,
            geometric_consensus_accepted=http['result']['geometric_consensus_accepted'],
            pose_usable_for_app=False,server_closed_after_test=True),
        unit_tests=dict(phone_contract=3,http_contract=3,passed=True),navigation_enabled=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    report='''# Independent iPhone 14 photos: 430 and 440

The user supplied original `IMG_5385.HEIC` (in front of 430 Computer Classroom) and `IMG_5386.HEIC` (in front of 440). Both show signed doorways. The second sign reads Team & Quiet Labs. The original HEIC bytes, SHA-256 values and provenance are preserved under `capture/independent_phone_20261017/` and are never reference-map inputs. Lossless decoded PNGs were used for feature extraction. These new photos are kept out of the public handoff; text results/code may be shared.

The image-to-3D pipeline extracts learned DISK descriptors and matches them against measured depth-linked reference features. There are no newly trained building-specific network weights. Query input is RGB; query LiDAR depth and user room labels are not solver inputs.

## Results

| Photo / user location | Map / retrieval | Numerical two-reference consensus | Support odometry rows | App-usable pose |
|---|---|---|---|---|
'''+'\n'.join(rows)+'''

430 produces a geometric hypothesis under both existing retrieval and the audit-motivated mutual-nearest-neighbour option. Visual inspection of the v3 supporting images includes the 430 sign and entrance context. This is a useful cross-phone match; it does not independently establish the exact camera position or direction. The v3 estimate is about (26.94, 4.52, 17.40) m in the staircase scan frame. The v4 hypothesis differs by about 0.34 m; map-to-map agreement is not surveyed accuracy.

440 does not obtain two consistent references with either retrieval method or the low-rotation map. A follow-up matched it against all 125 v3 references, still retaining only row 10891 as the best singleton. Thus failure is not solely that a true second view was omitted by the tested v3 shortlist. Many single-view candidates fit other repeated doorways at incompatible positions. Do not enable a single-reference fallback. This experiment does not isolate viewpoint coverage, depth/pose quality and calibration effects; a larger map or model is not assumed to fix it.

## Calibration and evidence limits

EXIF identifies the iPhone 14 rear wide camera, 5.7mm, 26mm-equivalent. There is no verified intrinsic matrix, lens-distortion model, surveyed camera position or known facing angle. An exploratory matrix was fixed before matching using equivalent focal length and the image diagonal, square pixels and centred principal point. These assumptions are recorded in `PLAN.json` and the sidecars. They are estimates, not a reused scanning-phone calibration. Estimated geometry is stored as `candidate_*`; `accepted` and `pose_usable_for_app` remain false.

The original manifest declared the legacy vs mutual-NN comparison before matching. Later exhaustive/v4 checks each have their own follow-up plan and are development diagnostics, not new held-out validation. The photos are now inspected development data; future tuned variants need additional held-out photos. Thresholds and two-reference consensus were never relaxed. Query room labels were used only to interpret results afterward.

## Existing-app handoff

`phone_localizer.py` exposes the calibrated/missing/estimated query contract and an optional mutual-NN ranking. `serve_phone_localizer.py` provides a model-reusing HTTP backend that the existing app can call with an image, matching calibration, request ID and capture timestamp. See `../PHONE_APP_INTERFACE.md`. The real HTTP smoke test submitted a JPEG derivative of 430, received HTTP 200, echoed frame identity, and correctly withheld an app-usable pose with estimated calibration. The server closed after the test. Three phone-contract and three HTTP-contract tests passed; no iOS build/on-device test ran.

The user's goal is a destination arrow following a corridor path and buzzing as remaining path distance decreases. The inspected newer app branch `nav/route-guidance` at `d7229ac` already has arrow/routing/turn-feedback code plus a separate ARWorldMap workflow. Its plan-meter graph has no room 440 and is not registered to this staircase scan. No files or claims from that branch were silently merged into the canonical geometry. Coordinate registration, calibrated live frames, verified 440 entrance/path anchors and stable tracking remain necessary to connect this engine to trusted arrow/progress feedback. Routing stays disabled in this project.

The user also offered new floor-2/3 plans and scans. At this report's preparation no such files were received; no floor assignment or new reconstruction was invented. Add supplied originals to the same master with separate scan frames when they arrive; floor plans remain excluded from public GitHub.
'''
    (OUT/'PHONE_REPORT.md').write_text(report,encoding='utf-8')
    log=PROJECT/'PROJECT_LOG.md'
    text=log.read_text(encoding='utf-8')
    text=text.replace('| D017 | Complete predeclared v3 A/B and low-rotation v4 B without changing thresholds or retrieval; reserve fresh data for later variants | User continuation request and implementation choice; B consumed by these two variants |', '| D017 | Complete predeclared v3 A/B and low-rotation v4 B without changing thresholds or retrieval; reserve fresh data for later variants | User continuation request and implementation choice; B consumed by these two variants |\n| D018 | Feed the existing app arrow/path/proximity-buzz flow with camera-to-map localization; keep existing UI work | User clarification; newer navigation code is on nav/route-guidance, separate map/frame |\n| D019 | Preserve the two iPhone 14 photos as independent queries; gate estimated calibration and keep two-reference checks | User identified 430/440; implementation protocol fixed before matching; later follow-ups are diagnostics |')
    text=text.replace('| Test independent ordinary-phone images | Pending user capture | 20-30 new views with locations/directions; do not use them as training references |', '| Test independent ordinary-phone images | Two original iPhone 14 photos received: 430 and 440; 430 numerical hypothesis, 440 unresolved | EXIF-estimated calibration only; no metric/live-navigation pass; keep photos out of mapping |')
    text=text.replace('| 440 | Room numeral visibly reviewed in staircase capture | Confirm destination metadata and entrance anchor |', '| 440 Team & Quiet Labs | Staircase numeral plus user-supplied independent signed-door photo IMG_5386 | Reviewed 3D entrance anchor and route connection |')
    text+='''
### 2026-10-17 — Tested independent phone photos and prepared existing-app localization interface

- User clarified the app goal: select a destination such as 440; the existing arrow follows the created corridor path and buzzing signals progress. Keep existing GitHub UI work; focus here on location/direction from the mapped 3D representation (D018).
- Received original IMG_5385.HEIC, user located in front of 430 Computer Classroom; IMG_5386.HEIC, in front of 440. Metadata: iPhone 14 rear wide. Preserved bytes/checksums/provenance and decoded lossless analysis images; never added either photo to mapping (D019). Room 440's sign visibly reads Team & Quiet Labs; its exact 3D doorway threshold is still unverified.
- 430 obtained consistent two-reference geometric hypotheses with v3/v4. 440 did not; exhaustive matching against all 125 v3 references still yielded one consistent reference. Mutual-NN retrieval was implemented as an option but did not improve these two outcomes. Full primary/follow-up plans and failed candidates are retained in `localization/evaluation_independent_phone_430_440/`.
- Calibration came only from an explicitly estimated EXIF-based matrix. No surveyed camera locations or known facing angles were provided. Numerical hypotheses are not app-usable poses or an independent-phone accuracy pass. Future tuned variants need new held-out photos.
- Added `phone_localizer.py`, `serve_phone_localizer.py` and `PHONE_APP_INTERFACE.md` to provide the existing app a concrete image/intrinsics/timestamp-to-scan-pose interface. Six contract tests passed, plus a real model/image HTTP smoke test; its temporary server closed afterward. The arrow/app source was not replaced. No iOS build or live walk ran on this Windows host.
- Inspected newer `nav/route-guidance` commit d7229ac. It has a separately saved ARWorldMap and plan-meter hallway graph without 440. Those coordinates and doorway assertions are unreviewed external working data relative to this archive, not an approved staircase-scan registration. No implicit merge/scale correction or routing enablement occurred.
- User offered floor-2/3 plans and new scans; files not yet received at this entry. Preserve originals and add to the same archive when supplied. No whole-building rescan requested. Floor plans and new independent-photo originals stay private; public handoff contains code and text results.
'''
    log.write_text(text,encoding='utf-8')
    readme=LOCAL/'README.md'
    text=readme.read_text(encoding='utf-8')+'\n\n## Existing-app camera interface\n\nUse `phone_localizer.py` for explicit query-calibration provenance and optional mutual-NN retrieval, or `serve_phone_localizer.py` for a model-reusing `/localize` backend. See `PHONE_APP_INTERFACE.md` and `evaluation_independent_phone_430_440/PHONE_REPORT.md`. Two independent iPhone 14 photos were tested: 430 gives an exploratory geometric hypothesis; 440 remains unsupported. Estimated calibration is never promoted to an app-usable pose. The app arrow/UI remains in the existing GitHub navigation work.\n'
    readme.write_text(text,encoding='utf-8')
    # A selection change also changes which frames survive the existing quality filters.
    report_path=LOCAL/'evaluation_v3_v4_comparison/EVALUATION_REPORT.md'
    text=report_path.read_text(encoding='utf-8')
    text=text.replace('Median recorded turning speed of accepted reference views:', 'v4 retains 146 views versus v3\'s 125 because more selected frames survive the unchanged quality filters. The comparison measures the full selection/retention effect, not rotation in isolation.\n\nMedian recorded turning speed of accepted reference views:')
    report_path.write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
