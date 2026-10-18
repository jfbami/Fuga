# Ordinary-camera recognition prototype

This is a **research-only** visual reference map and command-line localizer for staircase scan `b9dca4993d`. It does not enable navigation, merge scans, or claim a new ordinary phone has been localized successfully.

**Current state (2026-10-17):** v3/A 2/20 accepted (2 within internal tolerance, 0 >2 m); v3/B 2/20 accepted (2 within internal tolerance, 0 >2 m); v4/B 5/20 accepted (5 within internal tolerance, 0 >2 m). See `evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. v1 random-seeking and v2 one-frame-offset results remain superseded diagnostics. v3 uses timestamp-verified row=ordinal+1; v4 adds predeclared low-rotation reference selection. Both map schemas use the v3 format identifier. Routing is disabled and independent-phone validation is pending.

## What it does

- Reads the original scan directly from the canonical SQLite archive; a working RGB extraction is written under `work/localization_inputs/`.
- Samples reference views every 90 frames, filters blur/near-vertical views, and normalizes the image's quarter-turn orientation using recorded gravity. This is a new experiment, not a change to the original reconstruction.
- Extracts up to 1,024 pretrained DISK features at a 640-pixel long edge. Confidence-2 depth lifts valid reference features into the scan's own 3D frame. Other 2D features remain available for matching, with invalid depth explicitly masked.
- Retrieves candidate views using local-descriptor votes and mean-descriptor similarity, then uses pretrained LightGlue to match features. This is a custom LiDAR-supported pipeline inspired by hloc, **not a full hloc installation or deployment**.
- With correct query calibration, estimates pose with PnP/RANSAC and checks reprojection, image coverage, positive depth, distance to reference, and support from at least two mutually consistent reference views. Query depth is not needed. Results remain research candidates even when accepted by these checks.
- Without calibration, reports only unverified appearance matches, never an exact position or navigational instruction.
- Evaluates withheld same-recording RGB queries with a two-second reference exclusion. Recorded query poses are used only afterward to measure internal disagreement, never by retrieval/matching/pose solving. Temporal exclusion uses timestamps, not guessed frame rate.

The stronger matcher is not assumed to fix every failure. Repeated architecture, insufficient overlap, depth edge errors, calibration, tracking drift, lighting, and occlusions can all matter. Inspect every accepted/rejected query, not just a summary success count.

## Run on this machine

Run from the task workspace in PowerShell:

```powershell
$python = '.\work\mgh_localization_env\Scripts\python.exe'
$tool = 'outputs/MGH_Project/localization/mgh_localizer.py'
& $python $tool --help
& $python $tool build --map outputs/MGH_Project/localization/visual_map_v3
& $python $tool evaluate --map outputs/MGH_Project/localization/visual_map_v3 --output outputs/MGH_Project/localization/evaluation_additional --queries 20
& $python $tool query --image PATH_TO_ORIGINAL_PHOTO.jpg --output outputs/MGH_Project/localization/query_001.json
& $python $tool query --image PATH_TO_ORIGINAL_PHOTO.jpg --intrinsics PATH_TO_INTRINSICS.json --output outputs/MGH_Project/localization/query_002.json
```

Choose new map/evaluation/result names for additional runs; the CLI refuses to replace existing completed or partial outputs. The default map is `visual_map_v3/manifest.json`; `visual_map_v4_low_rotation/manifest.json` is the tested selection variant. v1/v2 maps are rejected by the current loader and retained as diagnostics. Maps and experiment reports are also embedded in the master after processing. Runtime results are generated only when commands are run; no server, mobile camera, or background voice listener is active.

Input images are EXIF-orientation-normalized. For a pose query, supply calibration in the normalized image's pixel coordinate system:

```json
{"width": 4032, "height": 3024, "fx": 2800, "fy": 2800, "cx": 2016, "cy": 1512, "distortion": []}
```

**Those numbers are illustrative, not your phone's calibration.** Do not use them for a real query. Nonzero distortion is rejected by this prototype; provide a correctly undistorted image/intrinsics pair or implement distortion-aware solving. Estimated EXIF focal lengths are not exact camera calibration. Intrinsics from the LiDAR capture cannot be silently reused for another phone.

## Independent testing and doorway review

Follow `../capture/REGULAR_PHONE_TEST.md`. Do not insert the first independent test photos into the reference map before evaluating them. Obtain calibration and independently known locations to quantify pose accuracy. Test wrong-floor/out-of-map images and report false accepts. An accepted internal pose is not proof of ordinary-phone performance.

`doorway_review_queue.csv` lists candidate destinations and the evidence still needed. It contains no invented 3D doorway coordinates. The next routing milestone is one verified 416 entrance connected to reviewed corridor nodes, not the whole building.

## Reproduce elsewhere

Use Python 3.12 and the saved runtime version manifest. PyTorch CPU wheels were installed from `https://download.pytorch.org/whl/cpu`; OpenCV-headless, Pillow, and Kornia from PyPI. LightGlue source comes from `https://github.com/cvg/LightGlue`, pinned to the commit recorded in the environment provenance. Original model-download sources and SHA-256 hashes are recorded with the experiment. The isolated virtual environment lives under `work/` and is not embedded in the building archive.

Install the pinned dependencies and the included vendor source archive (or the recorded upstream commit) in your own environment. Set `MGH_WORKSPACE` if the task workspace is elsewhere. Extract the reference map and source master to the expected layout. Preserve any upstream license files when extracting vendor source. DISK/LightGlue were selected rather than SuperPoint for this experiment; commercial use needs a model/dependency license review, not merely a successful import.

`setup_localization.ps1` creates an isolated Windows environment and installs the primary pinned packages. The vendor archive is a DISK/LightGlue-only subset: its upstream source files and Apache-2.0 LICENSE are unchanged, with a minimal import file; other extractors are not bundled. The full upstream commit is recorded in `environment_provenance.json`.

Pretrained weights are embedded under `project/MGH_Project/localization/models/` in the master. For offline inference, export them into the workspace's `work/mgh_model_weights/checkpoints/` using their original filenames; otherwise the upstream libraries fetch those public weights on first use. The requirements lock records transitive runtime versions; the virtual environment itself is not portable or embedded.

Sources: [LightGlue](https://github.com/cvg/LightGlue), [hloc](https://github.com/cvg/Hierarchical-Localization).


Predeclared evaluation: pass `--query-ordinals` and `--query-set-label` exactly as listed in `EVALUATION_PLAN_v3_v4.json`. A and B have now been evaluated; do not tune new variants on them. Use fresh held-out data for later changes.


## Existing-app camera interface

Use `phone_localizer.py` for explicit query-calibration provenance and optional mutual-NN retrieval, or `serve_phone_localizer.py` for a model-reusing `/localize` backend. See `PHONE_APP_INTERFACE.md` and `evaluation_independent_phone_430_440/PHONE_REPORT.md`. Two independent iPhone 14 photos were tested: 430 gives an exploratory geometric hypothesis; 440 remains unsupported. Estimated calibration is never promoted to an app-usable pose. The app arrow/UI remains in the existing GitHub navigation work.
