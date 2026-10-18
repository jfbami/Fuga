# MGH indoor localization: team handoff

Research prototype for Mary Gates Hall (MGH) floor 4: a regular phone camera estimates position and direction against a LiDAR-built reference map, and voice commands will later route users to labeled rooms. This is general wayfinding, **not** an emergency-navigation system. **Routing is disabled.** No result here is independent-phone validation.

## What's in this folder

| Path | Contents |
|---|---|
| `project/PROJECT_LOG.md` | Full history, decision register (D001-D022), roadmap. **Read first.** |
| `AGENTS.md` | Ground rules for anyone, human or AI, working on the data |
| `localization/mgh_localizer.py` | DISK + LightGlue localizer CLI (`build`, `evaluate`, `query`) |
| `localization/audit_v2_retrieval_correspondence/AUDIT_REPORT.md` | Latest findings: why v2 accepted only 1/20 |
| `localization/visual_map_v3/` | Default reference map: 125 views, association fixed, evaluated on A/B |
| `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md` | Completed predeclared v3 A/B and v4 B results |
| `localization/visual_map_v4_low_rotation/` | Predeclared low-rotation variant, evaluated on B only |
| `localization/EVALUATION_PLAN_v3_v4.json` | Pre-declared query sets A (diagnostic) and B (held out) |
| `project/capture/REGULAR_PHONE_TEST.md` | Protocol for independent phone test photos |
| `localization/doorway_review_queue.csv` | Destinations that still need verified doorway anchors |
| `archive_tools/` | Tools and format guide for the canonical SQLite master |
| `scripts/` | Audit, diagnostic, and archive scripts |

**Not in GitHub:** the canonical archive `MGH_Master.sqlite` (about 4.5 GB at revision 9) and the original Stray Scanner ZIPs (over GitHub's file limit), plus all floor plans (UW Space Viewer, NetID-only; do not publish). Get the master from the project owner through a private channel. Building, evaluating, and auditing need it at `outputs/MGH_Master.sqlite` relative to the workspace root (set `MGH_WORKSPACE`). Model weights download automatically from their upstream sources; hashes are in `localization/environment_provenance.json`.

## Current state (2026-10-17)

Completed evaluations: **v3/A: 2/20; v3/B: 2/20; v4/B: 5/20**. See `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. All acceptance thresholds and retrieval are unchanged. Same-recording only; B is now consumed by the two predeclared variants. The canonical master is revision 9, fully integrity/checksum verified; `archive_tools/MGH_Master_v3_v4_update.json` is the receipt. D016/D017 and these results are embedded together.

- Five scans, each in its own coordinate frame, none registered or merged:
  - `b43779c138`: iLounge, floor 4.
  - `b9dca4993d`: STAIR 1 from floor 3 to 4, then floor-4 corridors.
  - `e1a70b754b`: building/floor unassigned.
  - `5a6579fe23`: new floor-3 corridors/landing capture.
  - `0162f41946`: new floor-2 corridors/atrium/elevator-context capture; reviewed RGB timestamp anomaly boundary excluded.
- Room labels (416, 420, 430, 440) are draft identities, **not** verified doorway anchors.
- Bugs fixed so far:
  1. Random video seeking paired the wrong RGB frames (fixed in v2).
  2. Decoded video frame *i* actually shows depth/pose row *i + 1* (fixed in v3; see the audit).
- Main remaining limits (see the audit):
  - With the 2 s exclusion, few reference views overlap each same-recording query.
  - The scan was captured while sweeping the phone fast (median 66 degrees/s), so features from overlapping views disagree by about 15 cm / 3 degrees.
  - 14 of 34 single-view pose candidates were wrong place (>2 m). Keep the two-reference rule.

## Suggested work split

Each track is independent. Do not lower acceptance thresholds to raise scores. Declare any new held-out query set **before** looking at results.

1. **Review completed evaluations.** v3 A/B and low-rotation v4 B are complete; see the comparison report and detailed per-query results. Keep failed diagnostics. Later algorithm changes require a new held-out set; do not tune on A or B.
2. **Retrieval.** The audit shows mutual-nearest-neighbour or LightGlue-count ranking recalls overlapping views far better than v2's cross-image ratio vote. Implement it behind a flag, and test on a *new* held-out set, not A or B.
3. **Independent phone photos** (fieldwork). Follow `project/capture/REGULAR_PHONE_TEST.md`, starting with iSchool lobby -> room 416 -> hallway turn:
   - 10-15 original rear-1x photos, facing both directions.
   - Record the floor, where the photographer stood, and which way they faced.
   - Clearly identify the actual 416 entrance.
   - Keep these photos out of the map. Metric results need correct camera calibration.
4. **Doorway and stair anchors.** Verify the real 416 entrance threshold first, then 420/430/440 and the STAIR 1 landings. Use the decoded ordinals and rows in `doorway_review_queue.csv`.
5. **Scan registration.** Rerun staircase-to-iLounge registration with the corrected association (row = ordinal + 1). No geometry merge without reviewed, distributed overlap.

A new LiDAR recording is **not** requested yet. If one is needed later: one short out-and-back pass, slow walking, slow turns (no sweeping), pauses at signs and doorways, and both doorway approaches.

## Setup

Use Python 3.12 and `localization/setup_localization.ps1` (Windows), or install `localization/requirements-lock.txt` plus the vendored LightGlue subset in `localization/vendor/`. Run `python localization/mgh_localizer.py --help`.


## Existing-app localization backend and independent photos

The arrow/navigation UI already exists on `nav/route-guidance`; focus this handoff on supplying image-to-map pose. `localization/serve_phone_localizer.py` provides a model-reusing `/localize` backend; see `localization/PHONE_APP_INTERFACE.md` for image/calibration/frame-timestamp requirements and coordinate conventions. Its models run locally on CPU; no server is deployed or left running.

Two original iPhone 14 photos were tested, kept out of mapping and out of this public repository. 430 yields a two-reference numerical hypothesis with explicitly estimated EXIF calibration; 440 remains unsupported even after exhaustive v3 matching. Mutual-NN retrieval is an option, not a demonstrated fix for these two images. See `localization/evaluation_independent_phone_430_440/PHONE_REPORT.md`. Six contract tests plus one real model/image HTTP smoke test passed. Estimated calibration never produces an app-usable pose.

The newer app branch uses a separate ARWorldMap and plan-meter graph without 440. No reviewed transform ties that graph to this staircase scan. Verified camera calibration, coordinate registration, actual entrance/path anchors and stable live tracking remain pending. The user offered floor-2/3 plans/scans; those files had not arrived at this update. Preserve each new scan separately and keep floor plans private.


## Revision 9: private new captures and room-anchor catalog

Two additional original scans and full plans for floors 2/3/4 are preserved privately in the sole master. Separate floor-2/3 prototypes are built; cross-scan/plan registration and elevator connectivity remain pending. Only the small text inventory and verification receipt under `project/data_inventory_revision9/` are public here. New scan originals/geometry, source/raster floor plans, plan-derived coordinates, the room CSV/JSON and private review viewer are excluded.

The owner has a private catalog of 305 plan labels: 230 room-number labels, 56 other plan spaces, 14 stair labels and 5 elevator labels. Six floor-4 plan doorway candidates cover 416, 420, 430 and 440; 430/440 each have two corridor entrances. Measured sign candidates exist for 416/430/440 in the staircase scan frame, while the selected 420 sign lacks confident depth. Sign points and printed plan-label points are not doorway thresholds. Verified 3D doorway anchors remain zero; routing stays disabled. Existing app arrow code is unchanged.
