# DISK + LightGlue reference-map experiment

## Result

- Built **129 reference views** and **84,043 confident depth-linked features** from staircase scan `b9dca4993d`.
- **0 / 20** withheld queries passed the full multi-reference pose acceptance protocol.
- 10 queries had at least one per-reference accepted pose (18 per-reference candidates in total). A plausible single image pair is not sufficient for final acceptance.
- 0 accepted queries were within 0.5 m and 10 degrees of their recorded poses. This is an internal tolerance, not surveyed accuracy.
- Median measured query runtime: **8.26 seconds**, local CPU, including feature extraction/retrieval/matching/pose solving but not initial model loading. No phone/cloud speed claim is made.

This is a **same-recording diagnostic**, not a separately captured regular-phone test. Query images were disjoint from reference frames. Every tested reference had a timestamp gap >=2 s; the actual minimum tested gap was 2.250 s. Query depth and recorded position/orientation were not supplied to the solver. Correct recorded query calibration was supplied. Reference selection used appearance, not query pose or floor hints.

## Meaning

The reference-map build and executable prototype are complete. The evaluation is an experiment with conservative acceptance, not a guarantee of useful navigation. Two consistent reference estimates are required, along with per-view inlier, reprojection, image coverage, depth-sign, and reference-distance checks. No threshold was reduced to inflate acceptance. The detailed accepted and rejected candidates remain in `evaluation_v1/results.json`.

This recording, feature extractor, reference sampling, image orientation normalization, and multi-reference protocol differ from the old iLounge SIFT baseline. Their success fractions do **not** establish a controlled matcher improvement or regression. Additional retrieval, depth-correspondence, multiview geometry, and calibration investigation may be needed. No full hloc/COLMAP deployment or building-specific network training ran.

## Every query

| Query frame | Capture seconds | Full acceptance | Best candidate inliers | Largest consistent support |
|---|---:|---|---:|---:|
| 585 | 9.8 | False | 0 | 0 |
| 1305 | 21.8 | False | 12 | 0 |
| 2025 | 33.8 | False | 65 | 1 |
| 2745 | 45.8 | False | 13 | 0 |
| 3465 | 57.8 | False | 104 | 1 |
| 4095 | 69.1 | False | 108 | 1 |
| 4815 | 82.6 | False | 52 | 1 |
| 5535 | 95.5 | False | 44 | 0 |
| 6255 | 107.9 | False | 11 | 0 |
| 6975 | 120.5 | False | 76 | 1 |
| 7695 | 133.5 | False | 0 | 0 |
| 8415 | 147.0 | False | 88 | 1 |
| 9045 | 158.5 | False | 178 | 1 |
| 9765 | 172.3 | False | 13 | 0 |
| 10485 | 185.6 | False | 102 | 1 |
| 11205 | 198.8 | False | 10 | 0 |
| 11925 | 211.7 | False | 143 | 1 |
| 12645 | 224.7 | False | 11 | 0 |
| 13365 | 237.6 | False | 26 | 1 |
| 13995 | 248.9 | False | 10 | 0 |

## Implementation checks

`implementation_checks.json` checks the read-only SQLite-ZIP adapter, quarter-turn camera/image transformations, and 3D-to-image round trips for every retained depth feature. These checks establish numerical consistency of this code path, not physical map accuracy. Runtime versions, source commit, sources/weights, and their hashes are recorded in `environment_provenance.json` and `requirements-lock.txt`.

The separate `self_image_appearance_smoke.json` uses an exported reference image as its own appearance query. It exercises the external-image CLI without calibration; it is deliberately **not held out**, is not counted above, and cannot validate localization.

## Still required

Fresh ordinary-phone photos and correct calibration; out-of-map/wrong-floor rejection tests; independently known positions for physical error measurement; actual room-416 and stair landing threshold anchors; reviewed corridor connectivity; validated live tracking, voice command resolution, and routing. Existing cross-scan alignment remains pending. All routing remains disabled.
