# Frame-association root cause and corrected evaluation

## Confirmed bug

The original visual-map builder and evaluator used `CAP_PROP_POS_FRAMES` random seeking and assumed the returned RGB image had that decoded acquisition index. For this recording/backend, 13 of 14 sampled seek requests did not return the requested sequential frame. This was verified by exact SHA-256 matches of resized decoded pixels across all 14337 sequential frames, not inferred merely from image appearance or metadata. Reported average video FPS was 56.319476.

The wrong RGB image was subsequently paired with the requested index's depth, intrinsics, and pose. This invalidates the old DISK/LightGlue map's 3D feature associations and the original 0/20 physical-position evaluation. That number remains preserved as a historical failed run but is **not evidence of the scan's achievable accuracy or camera-navigation feasibility**. This is an implementation error, not a demonstrated limitation of the uploaded scan.

The precise internal seeking mechanism was not instrumented. Time-based/variable-rate seeking is a plausible explanation, not a separately proved decoder-internals finding. OpenCV documents backend-dependent property behavior: https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html.

## Fix

Decode in order from the start, select by decoded ordinal, and only then look up the same-index pose/depth/calibration. Rebuilt the map in a new `visual_map_v2/` directory and evaluated the same 20 query ordinals in `evaluation_v2_framefix/`. Original v1 files were not overwritten. The query API defaults to v2 and refuses maps without verified sequential-index metadata.

Feature extraction, image size, candidate retrieval, matching, geometric acceptance thresholds, and two-reference consistency rules were not relaxed. Query/reference ordinals remained disjoint; the minimum actual tested reference gap was 2.250 seconds. Query depth/pose was not used by the solver. Recorded query pose is used only for post-hoc internal disagreement.

## Corrected result

- Reference map: **125 views / 66,773 confident 3D features**.
- Full multi-reference acceptances: **1/20**.
- Accepted estimates within the internal 0.5 m / 10-degree tolerance: **1**.
- Median CPU query runtime: **7.11 seconds**, excluding model initialization.
- Independent ordinary-phone validation: **not performed**. No route enabled, no global scan registration, no doorway anchors verified.

These are same-recording consistency measurements against recorded poses, not surveyed accuracy. Every acceptance, rejection, per-reference candidate, and residual remains in `results.json`. An accepted estimate outside internal tolerance must not be hidden from the report. Passing an internal test would still not demonstrate reliable independent-phone navigation.

## Scope of earlier evidence

- The TSDF reconstruction and original iLounge SIFT extraction used sequential decoding, so this particular random-seeking bug does not invalidate their frame selection. Geometry is not thereby proven accurate; their existing limits remain.
- The old staircase contact sheets, manually reviewed sign images, cross-scan PnP, and depth-rigid matching helpers used random seeking. Visible sign identities remain observations of actual captured images, but old filenames/frame numbers were seek requests rather than verified acquisition indices. Old camera-pose and timestamp associations must not be used as accurate anchors.
- Corrected sign-image provenance is linked through the diagnostic mapping below. The original image assets and annotation history remain preserved. Floor/stair identities are still draft navigation data, and architectural stair-ID correspondence/landing thresholds remain pending.
- The old cross-scan registration numbers are not a valid aligned-data registration experiment and need a fresh, sequentially indexed rerun. No geometry merge was made from them.

## Seek request -> actual decoded index

The mean pixel difference compares the old seek image with the *requested* sequential image at 160x120. Exact hash matching identifies its actual ordinal(s). Multiple ordinals, if any, would be explicitly listed rather than silently choosing one.

| Old seek request / filename label | Actual matching decoded ordinal(s) | Mean same-index RGB difference |
|---|---|---:|
| 0 | 0 | 0.00 |
| 610 | 648 | 62.87 |
| 900 | 957 | 68.83 |
| 2565 | 2728 | 32.24 |
| 3500 | 3724 | 67.25 |
| 4250 | 4442 | 71.48 |
| 7000 | 7191 | 44.26 |
| 7092 | 7289 | 50.89 |
| 8450 | 8572 | 44.14 |
| 9808 | 9858 | 65.30 |
| 10865 | 10886 | 68.91 |
| 11000 | 11003 | 26.56 |
| 14000 | 13975 | 27.07 |
| 14034 | 14012 | 32.99 |

## Every corrected query

| Query ordinal | Accepted | Consistent reference support | Position disagreement with recorded pose (m) |
|---|---|---:|---|
| 585 | False | 0 | n/a |
| 1305 | False | 1 | n/a |
| 2025 | False | 1 | n/a |
| 2745 | False | 0 | n/a |
| 3465 | True | 4 | 0.07786136190700571 |
| 4095 | False | 1 | n/a |
| 4815 | False | 1 | n/a |
| 5535 | False | 0 | n/a |
| 6255 | False | 0 | n/a |
| 6975 | False | 0 | n/a |
| 7695 | False | 1 | n/a |
| 8415 | False | 0 | n/a |
| 9045 | False | 1 | n/a |
| 9765 | False | 1 | n/a |
| 10485 | False | 0 | n/a |
| 11205 | False | 0 | n/a |
| 11925 | False | 0 | n/a |
| 12645 | False | 1 | n/a |
| 13365 | False | 0 | n/a |
| 13995 | False | 0 | n/a |

## Next gates

If recognition still rejects views, separately audit retrieval recall and cross-view feature/depth consistency before changing any acceptance thresholds. Then test fresh ordinary-phone images with correct calibration, include wrong-floor/out-of-map rejection tests, verify a room entrance and corridor graph, and validate tracking/voice directions. More compute or a larger model is not a substitute for correct data association.
