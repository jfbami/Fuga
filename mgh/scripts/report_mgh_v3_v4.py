"""Summarize the predeclared experiments and refresh continuity documents."""
import hashlib
import json
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'outputs/MGH_Project'
LOCAL = PROJECT / 'localization'
PLAN = json.loads((LOCAL / 'EVALUATION_PLAN_v3_v4.json').read_text())
DATE = datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
RUNS = [('v3', 'A'), ('v3', 'B'), ('v4', 'B')]


def main():
    destination = LOCAL / 'evaluation_v3_v4_comparison'
    destination.mkdir(exist_ok=False)
    summaries = []
    rows = []
    details = []
    v2 = json.loads((LOCAL / 'visual_map_v2/manifest.json').read_text())
    v3 = json.loads((LOCAL / 'visual_map_v3/manifest.json').read_text())
    assert [r['frame'] for r in v2['references']] == [r['decoded_video_ordinal'] for r in v3['references']]
    assert all(hashlib.sha256((LOCAL / 'visual_map_v2' / old['image']).read_bytes()).digest() ==
               hashlib.sha256((LOCAL / 'visual_map_v3' / new['image']).read_bytes()).digest()
               for old, new in zip(v2['references'], v3['references']))
    for version, label in RUNS:
        folder = f'evaluation_{version}_set{label}'
        result = json.loads((LOCAL / folder / 'results.json').read_text())
        map_name = 'visual_map_v3' if version == 'v3' else 'visual_map_v4_low_rotation'
        manifest = json.loads((LOCAL / map_name / 'manifest.json').read_text())
        assert manifest['original_zip_sha256'] == v3['original_zip_sha256']
        assert manifest['weights_at_build'] == v3['weights_at_build']
        queries = result['results']
        assert result['query_set_label'] == label
        assert result['query_decoded_video_ordinals'] == PLAN['query_sets'][label]['ordinals']
        assert [q['query_decoded_video_ordinal'] for q in queries] == PLAN['query_sets'][label]['ordinals']
        assert len(queries) == result['query_count'] == 20
        assert all(q['query_odometry_row'] == q['query_decoded_video_ordinal'] + 1 for q in queries)
        assert result['implementation_sha256'] == manifest['implementation_sha256'] == hashlib.sha256((LOCAL / 'mgh_localizer.py').read_bytes()).hexdigest()
        assert result['map_manifest_sha256'] == hashlib.sha256((LOCAL / map_name / 'manifest.json').read_bytes()).hexdigest()
        assert {**result['acceptance_rules'], 'temporal_exclusion_seconds': result['temporal_exclusion_seconds']} == PLAN['acceptance_rules_unchanged']
        assert not result['query_depth_used_for_solver'] and not result['recorded_query_pose_used_for_solver']
        references = {ref['frame']: ref for ref in manifest['references']}
        assert not set(result['query_decoded_video_ordinals']) & {r['decoded_video_ordinal'] for r in references.values()}
        for q in queries:
            assert all(abs(references[c['reference_frame']]['capture_seconds'] - q['capture_seconds']) >= 2 for c in q.get('candidates', []))
            assert all(abs(references[c['reference_frame']]['capture_seconds'] - q['capture_seconds']) >= 2 for c in q.get('appearances', []))
        accepted = [q for q in queries if q['accepted']]
        wrong = sum(q['position_disagreement_with_recorded_pose_m'] > 2 for q in accepted)
        summary = {k: v for k, v in result.items() if k != 'results'}
        summary.update(map_variant=version, map_directory=map_name, results_asset=f'{folder}/results.json',
                       wrong_place_accepted_over_2m=wrong,
                       accepted_ordinals=[q['query_decoded_video_ordinal'] for q in accepted],
                       median_reference_turning_deg_s=statistics.median(r['turning_deg_s'] for r in references.values()),
                       reference_fraction_turning_over_30_deg_s=sum(r['turning_deg_s'] > 30 for r in references.values()) / len(references),
                       confident_3d_features=manifest['total_confident_3d_features'])
        summaries.append(summary)
        rows.append(f"| {version} / {label} | {result['reference_count']} / {manifest['total_confident_3d_features']:,} | {len(accepted)}/20 | {result['accepted_within_0_5m_10degrees_of_recorded_pose']} | {wrong} | {result['median_runtime_seconds']:.2f} s |")
        details.append(f"### {version}, set {label}\n\n" + ('\n'.join(
            f"- Ordinal {q['query_decoded_video_ordinal']} / row {q['query_odometry_row']}: {q['position_disagreement_with_recorded_pose_m']:.3f} m, {q['orientation_disagreement_with_recorded_pose_degrees']:.2f} degrees; support rows {q['consistent_support_frames']}." for q in accepted) or 'No query accepted.'))
    comparison = dict(date_local=DATE, scan_id='b9dca4993d',
        evaluation_plan_sha256=hashlib.sha256((LOCAL / 'EVALUATION_PLAN_v3_v4.json').read_bytes()).hexdigest(),
        acceptance_thresholds_changed=False, retrieval_changed=False, independent_phone_test_passed=False,
        navigation_enabled=False, checks=dict(exact_declared_query_sets=True, query_reference_disjoint=True,
        timestamp_exclusion_verified=True, association_offset_one=True, implementation_and_manifest_hashes_verified=True,
        same_v2_v3_rgb_images_verified_by_sha256=True, same_original_and_model_weights=True),
        runs=summaries)
    (destination / 'summary.json').write_text(json.dumps(comparison, indent=2), encoding='utf-8')
    table = '\n'.join(['| Map / set | Views / 3D features | Accepted | Within 0.5 m / 10 deg | Wrong place >2 m | Median query CPU runtime |',
                       '|---|---:|---:|---:|---:|---:|', *rows])
    report = f'''# Predeclared v3/v4 same-recording evaluations

Date: {DATE} (America/Los_Angeles). Scan `b9dca4993d`, its own unregistered frame.

{table}

Set A was inspected during the earlier audit and is diagnostic. Set B was held out from that audit and is the primary same-recording comparison. Both map variants were specified in `../EVALUATION_PLAN_v3_v4.json` before these runs. B is now consumed: later changes need a new held-out set, ideally independent-phone photographs. No further variant was tuned on B.

v3 changes only association to decoded ordinal i = odometry/depth row i+1; its 125 RGB views match v2. v4 additionally selects the lowest recorded turning speed within each 90-ordinal window. The v4 manifest retains the v3 format identifier because the data schema is shared; `reference_selection.mode=low_rotation` identifies the variant. Earlier interrupted/stopped partial maps remain preserved and were not evaluated.

Median recorded turning speed of accepted reference views: v3 {summaries[0]['median_reference_turning_deg_s']:.1f} degrees/s; v4 {summaries[2]['median_reference_turning_deg_s']:.1f} degrees/s. This measures selection on recorded poses, not corrected rolling shutter or physical pose accuracy.

The v2 historical 1/20 on A is superseded by the confirmed one-frame offset. The audit's simulated 2/20 and oracle/retrieval scenarios are separate diagnostics, not these CLI runs. Candidate retrieval and PnP retain their existing settings; query-specific FLANN/RANSAC behavior means a simulation's count need not equal a fresh complete evaluation.

## Verification and interpretation

Checked exact declared ordinal lists and denominators, query/reference disjointness, >=2 s timestamp exclusion for all tested references, row=ordinal+1, implementation/manifest hashes, and unchanged acceptance parameters. Per-view requirements remain >=15 inliers, ratio >=0.35, median residual <3 px, image coverage >=0.01, positive depth, and reference distance <6 m. Acceptance still requires >=2 consistent references, position spread <0.75 m, rotation spread <10 degrees, and support times separated by >=0.5 s. Recorded query poses are used only after acceptance for internal disagreement; query depth is never used by the solver.

The accepted fraction remains too small for reliable navigation. Zero wrong-place accepts in these small same-recording sets would not establish a false-accept rate for ordinary phones. Position/orientation differences below are comparisons with recorded poses, not surveyed physical accuracy. Runtime excludes model loading and timestamp verification; concurrent host activity can affect it and it is not a controlled speed comparison.

Routing stays disabled. Labels and floor hints remain draft; doorway and stair landing anchors, scan registration, wrong-floor/out-of-map testing, independent phone calibration and independently known positions remain pending. Do not request a whole-building rescan. Start independent held-out phone testing with the existing 10-15-photo iSchool lobby -> 416 -> hallway-turn protocol; if missing viewpoints are demonstrated, request one short deliberate out-and-back LiDAR pass.

## Accepted query details

''' + '\n\n'.join(details) + '\n'
    (destination / 'EVALUATION_REPORT.md').write_text(report, encoding='utf-8')
    concise = '; '.join(f"{r['map_variant']}/{r['query_set_label']} {r['accepted_queries']}/20 accepted ({r['accepted_within_0_5m_10degrees_of_recorded_pose']} within internal tolerance, {r['wrong_place_accepted_over_2m']} >2 m)" for r in summaries)
    log = PROJECT / 'PROJECT_LOG.md'
    content = log.read_text(encoding='utf-8')
    content = content.replace('## 1. Goal and current scope', f"**Current evaluation update, {DATE}:** {concise}. See `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. This supersedes the historical 'not yet evaluated' state below; no independent-phone or routing pass.\n\n## 1. Goal and current scope", 1)
    content = content.replace('| D016 | Publish code, docs, audit, and map v3 to public GitHub repo jfbami/Fuga (PR 1); keep master, ZIPs, floor plans private | User decision 2026-10-17 |', '| D016 | Publish code, docs, audit, and map v3 to public GitHub repo jfbami/Fuga (PR 1); keep master, ZIPs, floor plans private | User decision 2026-10-17 |\n| D017 | Complete predeclared v3 A/B and low-rotation v4 B without changing thresholds or retrieval; reserve fresh data for later variants | User continuation request and implementation choice; B consumed by these two variants |')
    content = content.replace('| Build improved single-scan visual reference map | Corrected v2: 125 views / 66,773 confident 3D features | `localization/visual_map_v2/manifest.json`; v1 retained only as invalidated frame-association diagnostics |', '| Build improved single-scan visual reference map | v3 association fixed; v4 low-rotation built | Manifests and comparison report; v1/v2 and partial builds remain historical diagnostics |')
    content = content.replace('| Run withheld-image diagnostics | v1 0/20 invalidated; corrected v2 accepts 1/20 | Same query ordinals and unchanged acceptance rules; still unreliable, not independent-phone or survey validation |', f'| Run withheld-image diagnostics | {concise} | Predeclared A/B; thresholds unchanged; same-recording only |')
    content += f'''\n### {DATE} — Continued predeclared v3/v4 evaluation and prepared team handoff update

- Resumed at the user's request; inspected revision 7/current records, D015/D016 and the audit before running.
- D017: {concise}. All three runs completed all 20 declared queries; no threshold or retrieval change. Full results, query images, manifests, comparison checks and logs are preserved. v4 was rebuilt into a new directory; stopped partials are untouched.
- Set A is audit-exposed diagnostic data. Set B is now consumed by the two predeclared variants; future algorithm changes require a new held-out set. Recorded-pose disagreement is internal consistency, not surveyed accuracy or independent-phone validation.
- The revised log (including D016, previously absent from revision 7), results, maps, continuity documents and structured current records are staged for one canonical-master transaction by `work/archive_mgh_v3_v4.py`. Its post-commit receipt `../MGH_Master_v3_v4_update.json` records revision and full integrity/checksum verification. Original scan checksums and older history are retained.
- Prepared updated docs/results for existing public PR https://github.com/jfbami/Fuga/pull/1. Publication excludes the master, original ZIPs and floor plans; actual Git push is verified separately after the archive update.
- Routing remains disabled. Unresolved room/cropped labels, doorway/stair anchors, alignment, floor-3 corridor coverage, unassigned earlier scan and independent-phone validation remain pending. No whole-building rescan requested.
'''
    log.write_text(content, encoding='utf-8')
    for path in [ROOT / 'AGENTS.md']:
        text = path.read_text(encoding='utf-8')
        text = text.replace('v2 is superseded; `visual_map_v3` (association fixed) is built but not yet evaluated. Next: evaluate it per `localization/EVALUATION_PLAN_v3_v4.json`.', f'v2 is superseded. Predeclared evaluation completed: {concise}. See `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. Set B is consumed; later changes need a new held-out set.')
        path.write_text(text, encoding='utf-8')
    readme = LOCAL / 'README.md'
    text = readme.read_text(encoding='utf-8')
    start = text.index('**Frame-index correction')
    end = text.index('\n\n## What it does', start)
    text = text[:start] + f"**Current state ({DATE}):** {concise}. See `evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. v1 random-seeking and v2 one-frame-offset results remain superseded diagnostics. v3 uses timestamp-verified row=ordinal+1; v4 adds predeclared low-rotation reference selection. Both map schemas use the v3 format identifier. Routing is disabled and independent-phone validation is pending." + text[end:]
    text = text.replace('--map outputs/MGH_Project/localization/visual_map_v2', '--map outputs/MGH_Project/localization/visual_map_v3')
    text = text.replace('The current map is `visual_map_v2/manifest.json`; the first v1 map is retained only as an invalidated diagnostic.', 'The default map is `visual_map_v3/manifest.json`; `visual_map_v4_low_rotation/manifest.json` is the tested selection variant. v1/v2 maps are rejected by the current loader and retained as diagnostics.')
    text += '\n\nPredeclared evaluation: pass `--query-ordinals` and `--query-set-label` exactly as listed in `EVALUATION_PLAN_v3_v4.json`. A and B have now been evaluated; do not tune new variants on them. Use fresh held-out data for later changes.\n'
    readme.write_text(text, encoding='utf-8')
    master_readme = ROOT / 'outputs/MGH_Master_README.md'
    text = master_readme.read_text(encoding='utf-8')
    text = text.replace('## How future uploads are added', f'**Latest association/evaluation update ({DATE}):** decoded ordinal i pairs with depth/pose row i+1 for staircase and iLounge scans; v2 is superseded. {concise}. See the embedded `project/MGH_Project/localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. Set B is consumed; independent-phone validation and navigation remain pending.\n\n## How future uploads are added', 1)
    master_readme.write_text(text, encoding='utf-8')
    print(json.dumps(comparison, indent=2))


if __name__ == '__main__':
    main()
