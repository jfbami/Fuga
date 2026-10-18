# Audit of visual_map_v2: retrieval and cross-view 3D correspondences

Date: 2026-10-17. Scan: `b9dca4993d` (STAIR 1 floor 3 -> 4, then floor-4 corridors), its own coordinate frame. Research diagnostic only: no route, scan merge, scale correction, or independent-phone result.

**Bottom line.** The v2 rejections were not mainly a retrieval problem. Three separate causes were found:

1. **A remaining one-frame RGB/depth/pose offset (software bug, fixed in v3).** Sequential decoding was correct, but decoded video ordinal *i* actually shows odometry/depth row *i + 1*. The first odometry row has no video frame; the "missing trailing frame" assumption was wrong.
2. **Too little geometric support for the two-reference rule in this same-recording test.** After the 2-second exclusion, 5/20 queries have at most one reference that actually overlaps the query view. Even perfect (oracle) retrieval accepts only 3/20.
3. **Fast camera rotation during the scan.** The gyroscope and poses agree (correlation 0.98) that the camera turned at a median of about 66 degrees/second and exceeded 30 degrees/second for about 85% of the corridor recording. At that rate, millisecond-level RGB timing and rolling-shutter effects move features by many pixels relative to depth and pose. Matched features in truly overlapping views therefore disagree by a median of about 15 cm in 3D. The unchanged per-view rule (median residual < 3 px, inlier ratio >= 0.35) rejects many geometrically correct views.

Acceptance thresholds were not changed. The recorded poses and query LiDAR depth were used only *after* matching, as diagnostic oracles. They were never inputs to retrieval, matching, PnP, or acceptance.

## Method

Everything was pre-declared in `AUDIT_PLAN.json` before any results existed, including a second query set (B) that the audit never looked at. The audit script (`work/audit_mgh_retrieval_correspondence.py`, archived under `project/MGH_Project/scripts/`) imports the revision-6 localizer (`mgh_localizer.py` SHA-256 `7d5e2688…`) and reuses its orientation, depth lifting, DISK features, LightGlue matcher, and PnP solver unchanged. Re-lifting with the v2 association reproduced every stored v2 3D point exactly.

- Query set A: the same 20 decoded RGB ordinals as `evaluation_v2_framefix`.
- Every query was matched with LightGlue against **every** eligible reference (about 123 each, exhaustive), plus 836 reference-reference pairs (temporal neighbours and appearance-selected revisits more than 20 s apart). Matches are cached in `lightglue_matches.npz`.
- *Covisible point*: a reference's confident 3D point that projects inside the query image under the recorded query pose and agrees with the query's own LiDAR depth within 0.10 m + 5%. *True-overlap reference*: at least 30 covisible points. *Correct pose*: within 0.5 m and 10 degrees of the recorded pose; *wrong place*: more than 2 m.
- The first audit run crashed in its last stage on an index-order bug in the audit script, not the localizer. Its log is preserved as `work/audit_run_attempt1_failed_refpair_indexing.log`. The fix swapped the match columns for reference-pair PnP, and the rerun reused the cached matches.

## 1. Video/odometry association

**Timestamp fingerprint.** Each scan has irregular dropped-frame gaps in both the odometry timestamps and the decoded video presentation timestamps. Exactly one alignment makes every gap coincide:

| Scan | Odometry rows | Decoded frames | Gaps > 30 ms | Best row - ordinal | Gap agreement | Max time residual |
|---|---:|---:|---:|---:|---:|---:|
| `b9dca4993d` staircase | 14,338 | 14,337 | 936 | **+1** | 100% (next best 90%) | 7.4 ms |
| `b43779c138` iLounge | 6,037 | 6,036 | 315 | **+1** | 100% | 3.4 ms |
| `e1a70b754b` unassigned | 1,943 | 1,942 | 0 | undetermined | - | - |

`e1a70b754b` has no gaps to fingerprint, so its offset is **unknown, not zero**.

**Geometric confirmation (staircase).** Matched confident 3D points were reprojected into the other view under each hypothesis "row = ordinal + shift", applied to both views:

| Shift | Median of pair-median error (23 overlapping pairs) | Median fraction under 3 px | Pairs where best |
|---:|---:|---:|---:|
| -1 | 12.4 px | 0.00 | 0 |
| 0 (v2) | 4.8 px | 0.11 | 7 |
| **+1** | **3.5 px** | **0.39** | **16** |
| +2 | 7.3 px | 0.01 | 0 |

The timestamps and the geometry agree independently. v1's random seeking was off by tens to hundreds of frames; v2 was off by exactly one frame, about 17-50 ms.

**Consequences.**

- **Sign-image provenance:** the corrected sign ordinals (648, 2728, 7289, 8572, 9858, 10886, 14012) remain correct *decoded image* identities. Their depth/pose rows are ordinal + 1.
- **Reconstructions:** TSDF fusion pairs depth with pose from the same row, so its geometry is unaffected by this offset. Only mesh colours come from a frame 17-50 ms away.
- **iLounge 1/16 SIFT result:** it used the same ordinal == row pairing, so it carries the same offset. It was not rerun and stays a historical research result.

## 2. Retrieval

v2 votes for references with a Lowe ratio test across *all* reference images at once. Overlapping references see the same physical points, so the runner-up neighbour is usually the same point in another reference. Of 19,952 query features, only **158 passed** (0.8%). In 14,333 rejections the runner-up came from a different reference image. Votes therefore mostly measure noise.

Ranking of true-overlap references, over the 17 queries that have at least one:

| Ranking method | Recall@1 | Recall@5 | Recall@13 | 2+ true in top 13 | Median first rank |
|---|---:|---:|---:|---:|---:|
| v2 FLANN cross-image votes | 7 | 9 | 11 | 6 | 5 |
| Exact cross-image votes | 6 | 8 | 8 | 2 | 29 |
| Mean descriptor (v2's 3 extra candidates) | 2 | 6 | 10 | 2 | 11 |
| Per-reference ratio test | 5 | 9 | 13 | 8 | 4 |
| Mutual nearest neighbours | 9 | 15 | 16 | 9 | 1 |
| LightGlue match count (exhaustive) | 10 | 14 | 16 | 10 | 1 |

The set of references that v2 actually tested contained at least one true-overlap reference for 11/20 queries, and two or more for 7/20. Mutual-nearest-neighbour counting is an inexpensive and clearly better ranking. **However, better retrieval alone would not change the score much** (section 4).

LightGlue also produced 50+ matches for 67 query-reference pairs that do not overlap under recorded poses. Examples include 238 matches for query 6255 vs reference 5400, and 215 for query 8415 vs reference 9000. Most such matches lacked confident depth, so they produced no pose. They show how repetitive the corridor appearance is, and that match count alone is not place evidence.

## 3. Cross-view 3D correspondences

**Depth coverage.** Of 124,972 reference keypoints, a median of 56% per view have confident depth (minimum 4%). Among invalid keypoints, low LiDAR confidence is the main cause (53,897), then range beyond 4.8 m (22,943) and depth edges (20,582); the causes are not exclusive. In true-overlap query pairs, 3,232 of 5,015 matches (64%) had reference depth.

**Consistency in truly overlapping pairs** (46 query-reference pairs with 20+ matches, corrected association): median 84.5 matches, median reprojection error under the recorded query pose **14.5 px**, median fraction under 3 px **0.0**, median 3D disagreement between the reference-lifted and query-lifted point **0.15 m**. Reference neighbour pairs show the same: 0.16 m for covisible same-pass pairs and 0.23 m for revisits.

Follow-up tests (`crossview_geometry.json`, `work/audit_mgh_crossview_geometry.py`) separated the causes:

- **Depth vs pose, no RGB:** projecting confident depth from one row into another changes depth by a median of 1.3 cm over 0.1 s, 2.0 cm over 0.5 s, 4.6 cm over 1.6 s, and 10.6 cm over 5 s. Depth and pose are mutually consistent at short range. This test is weak for lateral or rotational errors on surfaces facing the camera, and inconsistency grows with time (VIO drift without loop closure).
- **Sub-frame RGB timing:** poses were interpolated at (row time + delta) for both views. The pooled error is lowest near delta = -6 ms (8.5 px), against about 11 px at 0 ms and 13-20 px at +2 to +18 ms. A small residual RGB-earlier timing offset is plausible. It does not explain most of the error, and it is estimated from these same frames, so it was **not** applied.
- **Turning speed (real, not pose noise):** independent gyroscope rate in `imu.csv`: median 66 degrees/s, 90th percentile 140 degrees/s; pose-derived rate correlates 0.98. Corridor frames exceed 30 degrees/s 85% of the time. At 640-pixel images (focal length about 445 px), 66 degrees/s is about 0.5 px per millisecond, so a rolling-shutter readout or exposure-timing difference of 10-20 ms shifts features 5-10 px.
- **Per-view PnP vs recorded pose:** in 53 per-view-accepted pairs, the PnP orientation differs from the recorded orientation by a median of 3.0 degrees, and position by 0.16 m. The difference grows with time between the views (2.1 degrees within 3 s, 6.4 degrees beyond 20 s).

Interpretation: the map's 3D points are lifted at RGB keypoints that were imaged while the camera was turning quickly. This produces several-pixel / several-centimetre inconsistencies that the 3 px median-residual and 35% inlier-ratio rules were not designed to tolerate. This is mostly a **capture-motion limitation of this recording**, plus a small timing component. It is not a reason to loosen the rules: loosening them would also admit the wrong-place poses described next.

## 4. Pose decisions with unchanged acceptance

Each scenario tests a different reference set; the PnP solver and the per-view and two-reference rules are identical:

| Scenario (corrected association unless noted) | Accepted | Correct (<=0.5 m, <=10 deg) | Wrong place (>2 m) |
|---|---:|---:|---:|
| v2's tested references, v2 association (replicates v2) | 1 | 1 | 0 |
| v2's tested references | 2 | 2 | 0 |
| FLANN replica tested set | 3 | 3 | 0 |
| Per-reference ratio top 13 | 2 | 2 | 0 |
| LightGlue-count top 13 | 3 | 3 | 0 |
| Exhaustive: all eligible references | 3 | 3 | 0 |
| Oracle: only true-overlap references | 3 | 3 | 0 |

Accepted queries: 2025 (6.5 cm / 0.9 degrees), 3465 (5.6-7.3 cm), 1305 (0.32 m / 7.3 degrees).

**Safety-relevant:** across all queries, 34 single-view candidates passed the per-view checks, and **14 of them were wrong place (>2 m)**. The two-consistent-reference rule rejected every one; no wrong-place query was accepted in any scenario. Single-view acceptance is not trustworthy on this building's repetitive corridors.

**Coverage limit:** 3 queries (585, 5535, 6975) have no true-overlap reference, 2 more (2745, 13365) have only one, and 7 have exactly two. With the two-reference rule and the 2 s exclusion against a single-pass map sampled about every 1.6 s, most queries could not be accepted even with perfect retrieval and matching.

## 5. What this means for next steps

- **Software (done here):** fix the association (v3); results are below. Keep the two-reference rule and the existing thresholds.
- **Software (candidates, not adopted):** mutual-nearest-neighbour or LightGlue-count retrieval; choosing low-rotation reference frames (tested as v4, below); triangulating far or low-confidence keypoints across neighbouring references; rolling-shutter-aware or time-offset-calibrated projection. Each needs a fresh held-out test; none should be tuned on set A.
- **Capture:** the evidence supports the planned guidance: slow, deliberate turns, brief pauses at signs and doorways, and overlapping views from both approach directions. Do not sweep the phone. A pause is worth more than many fast passes.
- **Independent-phone validation is still not done.** Same-recording queries share the scan's camera, lighting, and timing. They cannot establish ordinary-phone performance.
