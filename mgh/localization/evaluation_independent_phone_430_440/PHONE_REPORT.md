# Independent iPhone 14 photos: 430 and 440

The user supplied original `IMG_5385.HEIC` (in front of 430 Computer Classroom) and `IMG_5386.HEIC` (in front of 440). Both show signed doorways. The second sign reads Team & Quiet Labs. The original HEIC bytes, SHA-256 values and provenance are preserved under `capture/independent_phone_20261017/` and are never reference-map inputs. Lossless decoded PNGs were used for feature extraction. These new photos are kept out of the public handoff; text results/code may be shared.

The image-to-3D pipeline extracts learned DISK descriptors and matches them against measured depth-linked reference features. There are no newly trained building-specific network weights. Query input is RGB; query LiDAR depth and user room labels are not solver inputs.

## Results

| Photo / user location | Map / retrieval | Numerical two-reference consensus | Support odometry rows | App-usable pose |
|---|---|---|---|---|
| IMG_5385 (430) | v3 / legacy | yes | [10081, 9451] | no |
| IMG_5385 (430) | v3 / mutual-NN | yes | [10081, 9451] | no |
| IMG_5385 (430) | v4 / legacy | yes | [10054, 9839] | no |
| IMG_5386 (440) | v3 / legacy | no | [10891] | no |
| IMG_5386 (440) | v3 / mutual-NN | no | [10891] | no |
| IMG_5386 (440) | v4 / legacy | no | [8201] | no |

430 produces a geometric hypothesis under both existing retrieval and the audit-motivated mutual-nearest-neighbour option. Visual inspection of the v3 supporting images includes the 430 sign and entrance context. This is a useful cross-phone match; it does not independently establish the exact camera position or direction. The v3 estimate is about (26.94, 4.52, 17.40) m in the staircase scan frame. The v4 hypothesis differs by about 0.34 m; map-to-map agreement is not surveyed accuracy.

440 does not obtain two consistent references with either retrieval method or the low-rotation map. A follow-up matched it against all 125 v3 references, still retaining only row 10891 as the best singleton. Thus failure is not solely that a true second view was omitted by the tested v3 shortlist. Many single-view candidates fit other repeated doorways at incompatible positions. Do not enable a single-reference fallback. This experiment does not isolate viewpoint coverage, depth/pose quality and calibration effects; a larger map or model is not assumed to fix it.

## Calibration and evidence limits

EXIF identifies the iPhone 14 rear wide camera, 5.7mm, 26mm-equivalent. There is no verified intrinsic matrix, lens-distortion model, surveyed camera position or known facing angle. An exploratory matrix was fixed before matching using equivalent focal length and the image diagonal, square pixels and centred principal point. These assumptions are recorded in `PLAN.json` and the sidecars. They are estimates, not a reused scanning-phone calibration. Estimated geometry is stored as `candidate_*`; `accepted` and `pose_usable_for_app` remain false.

The original manifest declared the legacy vs mutual-NN comparison before matching. Later exhaustive/v4 checks each have their own follow-up plan and are development diagnostics, not new held-out validation. The photos are now inspected development data; future tuned variants need additional held-out photos. Thresholds and two-reference consensus were never relaxed. Query room labels were used only to interpret results afterward.

## Existing-app handoff

`phone_localizer.py` exposes the calibrated/missing/estimated query contract and an optional mutual-NN ranking. `serve_phone_localizer.py` provides a model-reusing HTTP backend that the existing app can call with an image, matching calibration, request ID and capture timestamp. See `../PHONE_APP_INTERFACE.md`. The real HTTP smoke test submitted a JPEG derivative of 430, received HTTP 200, echoed frame identity, and correctly withheld an app-usable pose with estimated calibration. The server closed after the test. Three phone-contract and three HTTP-contract tests passed; no iOS build/on-device test ran.

The user's goal is a destination arrow following a corridor path and buzzing as remaining path distance decreases. The inspected newer app branch `nav/route-guidance` at `d7229ac` already has arrow/routing/turn-feedback code plus a separate ARWorldMap workflow. Its plan-meter graph has no room 440 and is not registered to this staircase scan. No files or claims from that branch were silently merged into the canonical geometry. Coordinate registration, calibrated live frames, verified 440 entrance/path anchors and stable tracking remain necessary to connect this engine to trusted arrow/progress feedback. Routing stays disabled in this project.

The user also offered new floor-2/3 plans and scans. At this report's preparation no such files were received; no floor assignment or new reconstruction was invented. Add supplied originals to the same master with separate scan frames when they arrive; floor plans remain excluded from public GitHub.
