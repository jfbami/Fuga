# Predeclared v3/v4 same-recording evaluations

Date: 2026-10-17 (America/Los_Angeles). Scan `b9dca4993d`, its own unregistered frame.

| Map / set | Views / 3D features | Accepted | Within 0.5 m / 10 deg | Wrong place >2 m | Median query CPU runtime |
|---|---:|---:|---:|---:|---:|
| v3 / A | 125 / 65,708 | 2/20 | 2 | 0 | 14.79 s |
| v3 / B | 125 / 65,708 | 2/20 | 2 | 0 | 14.34 s |
| v4 / B | 146 / 79,062 | 5/20 | 5 | 0 | 8.95 s |

Set A was inspected during the earlier audit and is diagnostic. Set B was held out from that audit and is the primary same-recording comparison. Both map variants were specified in `../EVALUATION_PLAN_v3_v4.json` before these runs. B is now consumed: later changes need a new held-out set, ideally independent-phone photographs. No further variant was tuned on B.

v3 changes only association to decoded ordinal i = odometry/depth row i+1; its 125 RGB views match v2. v4 additionally selects the lowest recorded turning speed within each 90-ordinal window. The v4 manifest retains the v3 format identifier because the data schema is shared; `reference_selection.mode=low_rotation` identifies the variant. Earlier interrupted/stopped partial maps remain preserved and were not evaluated.

v4 retains 146 views versus v3's 125 because more selected frames survive the unchanged quality filters. The comparison measures the full selection/retention effect, not rotation in isolation.

Median recorded turning speed of accepted reference views: v3 57.1 degrees/s; v4 13.8 degrees/s. This measures selection on recorded poses, not corrected rolling shutter or physical pose accuracy.

The v2 historical 1/20 on A is superseded by the confirmed one-frame offset. The audit's simulated 2/20 and oracle/retrieval scenarios are separate diagnostics, not these CLI runs. Candidate retrieval and PnP retain their existing settings; query-specific FLANN/RANSAC behavior means a simulation's count need not equal a fresh complete evaluation.

## Verification and interpretation

Checked exact declared ordinal lists and denominators, query/reference disjointness, >=2 s timestamp exclusion for all tested references, row=ordinal+1, implementation/manifest hashes, and unchanged acceptance parameters. Per-view requirements remain >=15 inliers, ratio >=0.35, median residual <3 px, image coverage >=0.01, positive depth, and reference distance <6 m. Acceptance still requires >=2 consistent references, position spread <0.75 m, rotation spread <10 degrees, and support times separated by >=0.5 s. Recorded query poses are used only after acceptance for internal disagreement; query depth is never used by the solver.

The accepted fraction remains too small for reliable navigation. Zero wrong-place accepts in these small same-recording sets would not establish a false-accept rate for ordinary phones. Position/orientation differences below are comparisons with recorded poses, not surveyed physical accuracy. Runtime excludes model loading and timestamp verification; concurrent host activity can affect it and it is not a controlled speed comparison.

Routing stays disabled. Labels and floor hints remain draft; doorway and stair landing anchors, scan registration, wrong-floor/out-of-map testing, independent phone calibration and independently known positions remain pending. Do not request a whole-building rescan. Start independent held-out phone testing with the existing 10-15-photo iSchool lobby -> 416 -> hallway-turn protocol; if missing viewpoints are demonstrated, request one short deliberate out-and-back LiDAR pass.

## Accepted query details

### v3, set A

- Ordinal 2025 / row 2026: 0.065 m, 0.89 degrees; support rows [2161, 1801].
- Ordinal 3465 / row 3466: 0.056 m, 0.81 degrees; support rows [4141, 3871, 4951, 4231].

### v3, set B

- Ordinal 225 / row 226: 0.095 m, 1.43 degrees; support rows [901, 1081].
- Ordinal 945 / row 946: 0.041 m, 0.92 degrees; support rows [451, 1081, 1171].

### v4, set B

- Ordinal 945 / row 946: 0.064 m, 0.55 degrees; support rows [439, 1159].
- Ordinal 2385 / row 2386: 0.215 m, 2.91 degrees; support rows [1306, 1182].
- Ordinal 4455 / row 4456: 0.025 m, 0.50 degrees; support rows [4941, 3421].
- Ordinal 5895 / row 5896: 0.089 m, 1.87 degrees; support rows [6080, 5259].
- Ordinal 13725 / row 13726: 0.053 m, 1.90 degrees; support rows [12602, 13252].
