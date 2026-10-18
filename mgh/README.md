# MGH indoor localization: team handoff

Research prototype for Mary Gates Hall (MGH) floor 4: a regular phone camera estimates position and direction against a LiDAR-built reference map, and voice commands will later route users to labeled rooms. This is general wayfinding, **not** an emergency-navigation system. **Routing is disabled.** No result here is independent-phone validation.

## What's in this folder

| Path | Contents |
|---|---|
| `project/PROJECT_LOG.md` | Full history, decision register (D001-D015), roadmap. **Read first.** |
| `AGENTS.md` | Ground rules for anyone, human or AI, working on the data |
| `localization/mgh_localizer.py` | DISK + LightGlue localizer CLI (`build`, `evaluate`, `query`) |
| `localization/audit_v2_retrieval_correspondence/AUDIT_REPORT.md` | Latest findings: why v2 accepted only 1/20 |
| `localization/visual_map_v3/` | Current reference map: 125 views, association fixed, **not yet evaluated** |
| `localization/EVALUATION_PLAN_v3_v4.json` | Pre-declared query sets A (diagnostic) and B (held out) |
| `project/capture/REGULAR_PHONE_TEST.md` | Protocol for independent phone test photos |
| `localization/doorway_review_queue.csv` | Destinations that still need verified doorway anchors |
| `archive_tools/` | Tools and format guide for the canonical SQLite master |
| `scripts/` | Audit, diagnostic, and archive scripts |

**Not in GitHub:** the canonical archive `MGH_Master.sqlite` (1.9 GB) and the original Stray Scanner ZIPs (over GitHub's file limit), plus all floor plans (UW Space Viewer, NetID-only; do not publish). Get the master from the project owner through a private channel. Building, evaluating, and auditing need it at `outputs/MGH_Master.sqlite` relative to the workspace root (set `MGH_WORKSPACE`). Model weights download automatically from their upstream sources; hashes are in `localization/environment_provenance.json`.

## Current state (2026-10-17)

- Three scans, each in its own coordinate frame, none registered or merged:
  - `b43779c138`: iLounge, floor 4.
  - `b9dca4993d`: STAIR 1 from floor 3 to 4, then floor-4 corridors.
  - `e1a70b754b`: building/floor unassigned.
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

1. **Evaluate v3** (needs the master). Run `evaluate` on set A and set B from `EVALUATION_PLAN_v3_v4.json` (`--query-ordinals`, `--query-set-label`). Report both. Optionally rebuild v4 with `build --selection low_rotation` and evaluate on B only.
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
