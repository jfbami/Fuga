"""Copy an explicit public-safe allowlist to the existing PR checkout; do not push."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/MGH_Project'
TARGET = ROOT / 'work/github_Fuga/mgh'


def main():
    receipt = json.loads((ROOT / 'outputs/MGH_Master_v3_v4_update.json').read_text())
    assert receipt['verification']['passed'] and receipt['revision'] == 8
    summary = json.loads((SOURCE / 'localization/evaluation_v3_v4_comparison/summary.json').read_text())
    for relative in ['PROJECT_LOG.md', 'localization/README.md', 'localization/PHONE_APP_INTERFACE.md',
                     'localization/phone_localizer.py', 'localization/serve_phone_localizer.py']:
        destination = TARGET / ('project/PROJECT_LOG.md' if relative == 'PROJECT_LOG.md' else relative)
        shutil.copy2(SOURCE / relative, destination)
    shutil.copy2(ROOT / 'AGENTS.md', TARGET / 'AGENTS.md')
    shutil.copy2(ROOT / 'outputs/MGH_Master_README.md', TARGET / 'archive_tools/MGH_Master_README.md')
    for folder in ['evaluation_v3_setA', 'evaluation_v3_setB', 'evaluation_v4_setB',
                   'evaluation_v3_v4_comparison', 'visual_map_v4_low_rotation']:
        destination = TARGET / 'localization' / folder
        if destination.exists():
            raise RuntimeError(f'Unexpected existing handoff output: {destination}')
        shutil.copytree(SOURCE / 'localization' / folder, destination)
    # New independent photos stay private; share only their code/text diagnostics.
    phone_out = TARGET / 'localization/evaluation_independent_phone_430_440'
    phone_out.mkdir(exist_ok=False)
    for source in (SOURCE / 'localization/evaluation_independent_phone_430_440').iterdir():
        if source.suffix.lower() in {'.json', '.md'}:
            shutil.copy2(source, phone_out / source.name)
    shutil.copy2(ROOT / 'outputs/MGH_Master_v3_v4_update.json', TARGET / 'archive_tools/MGH_Master_v3_v4_update.json')
    for name in ['run_mgh_declared_evaluations.py', 'report_mgh_v3_v4.py', 'archive_mgh_v3_v4.py',
                 'prepare_mgh_v3_v4_handoff.py', 'evaluate_v3_setA.log', 'evaluate_v3_setB.log',
                 'build_v4_low_rotation.log', 'evaluate_v4_low_rotation_setB.log',
                 'prepare_mgh_phone_photos.py', 'evaluate_mgh_phone_photos.py', 'evaluate_mgh_phone_v4.py',
                 'diagnose_mgh_phone_440_exhaustive.py', 'inspect_mgh_440_reference_coverage.py', 'report_mgh_phone_photos.py',
                 'test_mgh_phone_localizer.py', 'test_mgh_phone_service.py', 'smoke_mgh_phone_http.py',
                 'evaluate_independent_phone_430_440.log', 'evaluate_mgh_phone_v4.log', 'diagnose_mgh_phone_440_exhaustive.log',
                 'test_mgh_phone_localizer.log', 'test_mgh_phone_service.log', 'smoke_mgh_phone_http.log']:
        shutil.copy2(ROOT / 'work' / name, TARGET / 'scripts' / name)
    counts = '; '.join(f"{r['map_variant']}/{r['query_set_label']}: {r['accepted_queries']}/20" for r in summary['runs'])
    readme = TARGET / 'README.md'
    text = readme.read_text(encoding='utf-8')
    text = text.replace('D001-D015', 'D001-D019')
    text = text.replace('Current reference map: 125 views, association fixed, **not yet evaluated**', 'Default reference map: 125 views, association fixed, evaluated on A/B')
    text = text.replace('| `localization/EVALUATION_PLAN_v3_v4.json`', '| `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md` | Completed predeclared v3 A/B and v4 B results |\n| `localization/visual_map_v4_low_rotation/` | Predeclared low-rotation variant, evaluated on B only |\n| `localization/EVALUATION_PLAN_v3_v4.json`', 1)
    text = text.replace('## Current state (2026-10-17)', f'## Current state (2026-10-17)\n\nCompleted evaluations: **{counts}**. See `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. All acceptance thresholds and retrieval are unchanged. Same-recording only; B is now consumed by the two predeclared variants. The canonical master is revision 8, fully integrity/checksum verified; `archive_tools/MGH_Master_v3_v4_update.json` is the receipt. D016/D017 and these results are embedded together.')
    text = text.replace('1. **Evaluate v3** (needs the master). Run `evaluate` on set A and set B from `EVALUATION_PLAN_v3_v4.json` (`--query-ordinals`, `--query-set-label`). Report both. Optionally rebuild v4 with `build --selection low_rotation` and evaluate on B only.', '1. **Review completed evaluations.** v3 A/B and low-rotation v4 B are complete; see the comparison report and detailed per-query results. Keep failed diagnostics. Later algorithm changes require a new held-out set; do not tune on A or B.')
    text += '''

## Existing-app localization backend and independent photos

The arrow/navigation UI already exists on `nav/route-guidance`; focus this handoff on supplying image-to-map pose. `localization/serve_phone_localizer.py` provides a model-reusing `/localize` backend; see `localization/PHONE_APP_INTERFACE.md` for image/calibration/frame-timestamp requirements and coordinate conventions. Its models run locally on CPU; no server is deployed or left running.

Two original iPhone 14 photos were tested, kept out of mapping and out of this public repository. 430 yields a two-reference numerical hypothesis with explicitly estimated EXIF calibration; 440 remains unsupported even after exhaustive v3 matching. Mutual-NN retrieval is an option, not a demonstrated fix for these two images. See `localization/evaluation_independent_phone_430_440/PHONE_REPORT.md`. Six contract tests plus one real model/image HTTP smoke test passed. Estimated calibration never produces an app-usable pose.

The newer app branch uses a separate ARWorldMap and plan-meter graph without 440. No reviewed transform ties that graph to this staircase scan. Verified camera calibration, coordinate registration, actual entrance/path anchors and stable live tracking remain pending. The user offered floor-2/3 plans/scans; those files had not arrived at this update. Preserve each new scan separately and keep floor plans private.
'''
    readme.write_text(text, encoding='utf-8')
    body = f'''Adds `mgh/`: the Mary Gates Hall camera-localization research prototype and completed predeclared evaluations. Start with `mgh/README.md`.

- Fixed association: decoded frame i = depth/pose row i+1, verified from timestamp gaps. v3 retains exactly the same 125 reference images as v2.
- Completed results: **{counts}**, under unchanged retrieval, PnP and two-reference acceptance thresholds. Detailed accepted/rejected queries and reproducibility checks are included.
- Built the predeclared low-rotation v4 variant; evaluated it on B only. A is audit-exposed diagnostic data; B is now consumed and future changes require fresh held-out data.
- Added a phone-localization adapter and model-reusing HTTP backend for the existing app. Calibrated poses retain capture timestamps and the scan frame; routing is still disabled. Optional mutual-NN retrieval preserves geometric thresholds.
- Tested two independent iPhone 14 photos, held out from mapping: 430 gives a two-reference numerical hypothesis; 440 remains unsupported even with exhaustive v3 matching. Calibration is EXIF-estimated, so neither is an app-usable or surveyed pose. Six contract tests and one real model/image HTTP smoke test passed.
- Updated project history through D019, current documentation, scripts and master revision-8 verification receipt. Earlier invalidated diagnostics and partial builds remain preserved in the canonical archive.

Research only: routing disabled, room labels and doorway/stair anchors remain draft, scans remain unregistered, and no independent-phone validation has passed. Recorded poses provide internal comparisons, not surveyed accuracy. Independent phone photos/calibration and wrong-floor/out-of-map testing remain pending.

Excluded: the canonical SQLite master, original scan ZIPs, all UW floor plans, and the newly supplied independent-phone images (originals and derivatives). These stay private. Existing arrow/app UI code is untouched; the newer navigation branch uses a separate coordinate frame and needs reviewed registration before consuming this scan pose.
'''
    (ROOT / 'work/mgh_pr1_body.md').write_text(body, encoding='utf-8')
    print(counts)


if __name__ == '__main__':
    main()
