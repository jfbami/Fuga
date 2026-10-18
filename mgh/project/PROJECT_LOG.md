# Mary Gates Hall: project history and decision log

Last updated: 2026-10-17. This is a working summary of the conversation and the saved evidence, not a verbatim transcript. Earlier work is grouped by milestone because exact dates for individual prior steps are not established here.

**Important correction, 2026-10-17:** the initial DISK/LightGlue 0/20 run was invalidated by a processing bug: random video seeking returned RGB frames different from the requested pose/depth index. The v1 map and numbers remain historical diagnostics, not evidence of the scan's achievable accuracy. A sequentially indexed v2 map and rerun supersede them; see the final activity entry and `localization/evaluation_v2_framefix/FRAME_FIX_REPORT.md`. Legacy staircase sign filenames are seek-request labels: lower request 610 maps to actual frame 648, upper request 2565 to actual 2728. Source identities remain visible, but the old timestamp/pose bindings were not correct.

**Current evaluation update, 2026-10-17:** v3/A 2/20 accepted (2 within internal tolerance, 0 >2 m); v3/B 2/20 accepted (2 within internal tolerance, 0 >2 m); v4/B 5/20 accepted (5 within internal tolerance, 0 >2 m). See `localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. This supersedes the historical 'not yet evaluated' state below; no independent-phone or routing pass.

**New coverage update, 2026-10-17:** received and reconstructed separate floor-2 and floor-3 captures plus their private plans. Five scan originals now preserved; MGH floors 2/3/4 remain partial and unregistered. See `ingest_floor2_floor3_20261017/INGEST_REPORT.md`.

## 1. Goal and current scope

Build a growing digital representation of Mary Gates Hall (MGH), University of Washington, that eventually supports ordinary-phone indoor wayfinding. A user should be able to ask, for example, "Take me to room 416," have the app determine their position and orientation, and receive directions to a reviewed entrance.

The initial discussion considered emergency wayfinding and the Keryx project. The user broadened the scope to general room directions, not an emergency-only system. Keryx remains inspiration; we have not deployed it or reproduced its complete system. A briefly referenced calibration-grid project was explicitly canceled and is not part of MGH work.

The user permits cloud AI, but the completed reconstructions and localization diagnostics have run locally. No cloud localization service, voice agent, mobile app, or paid service has been deployed. Cloud use is an option, not a completed integration.

Long-term coverage includes rooms, actual entrance thresholds, corridor junctions, stairs, elevators, exits, signs, and explicit floor connections. Current coverage is partial; we have not reconstructed all of MGH.

## 2. Where the project lives

**Canonical portable file: `../MGH_Master.sqlite`.** It embeds the original ZIPs byte for byte, meshes, point clouds, photographs, reports, features, annotations, and revision history. Checksums and provenance accompany the assets.

The master uses SQLite tables for revisions, content-addressed blobs, versioned assets, versioned JSON records, and evidence links. Records represent the building, floors, scans, coordinate frames, alignments, rooms, landmarks, observations, connections, measurements, validations, and tasks. `current_assets` and `current_records` expose the latest versions without discarding older ones.

`../MGH_Master_tools.py` reads, exports, verifies, and extends the master. Its usage and format are documented in `../MGH_Master_README.md`. This `MGH_Project/` folder organizes the working notes and camera-recognition prototype; it does not create a second canonical database. Browser URLs and loose output folders are temporary/working views, not the source of truth.

Before this documentation/localization milestone, revision 4 contained three scans, 253 current assets, 246 unique embedded blobs, and about 1.73 GB of database data. Full integrity, foreign-key, and SHA-256 checks passed. Later revisions may change these counts; inspect the master summary for current totals.

## 3. Capture inventory

| Scan | Original upload | Assignment | Recorded duration / path | Status |
|---|---|---|---|---|
| `e1a70b754b` | `e1a70b754b.zip` | Building and floor unconfirmed | About 32.4 s / 33.1 m | Original and prototype preserved; unassigned, not merged into MGH |
| `b43779c138` | `iLounge.zip` | MGH floor 4; draft context 400W -> 400J -> 400M | About 105.9 s / 56.4 m | Reconstructed; draft plan registration and labels; camera localization unreliable |
| `b9dca4993d` | `MGH Staircase.zip` | STAIR 1 ascent, floor 3 -> floor 4; then fourth-floor lobby/corridors | About 254.6 s / 161.6 m | Reconstructed in its own frame; not registered to iLounge |
| `5a6579fe23` | `3rd floor.zip` | User-identified MGH floor 3, corridors/landings | About 173.1 s / 173.2 m | Separate indexed prototype; plan registration pending |
| `0162f41946` | `2nf floor mgh + elevator.zip` | User-identified MGH floor 2, corridors/atrium/elevator context | About 293.4 s / 232.6 m | Separate indexed prototype; timestamp boundary excluded; no elevator route verified |

Recorded path lengths include turns and backtracking. They are not lengths of unique corridor coverage or independently surveyed dimensions.

Each Stray Scanner recording contains RGB video, depth images, depth confidence, camera poses, camera intrinsics, and inertial data. Retain the original archive; an ordinary exported video alone loses important mapping information.

The regular iPhone 14 discussion distinguished map capture from map use: LiDAR-equipped Pro capture provides depth for mapping; the eventual navigation phone can use RGB camera images without LiDAR. No independent regular-phone localization test has passed yet.

## 4. Reconstruction work completed

The local prototype fuses confidence-filtered LiDAR depth using the recorded camera poses. The working pipeline uses Open3D 0.19.0, scalable TSDF, 3 cm voxels, 9 cm truncation, depth confidence level 2, and a 0.25-4.8 m accepted depth range. Sampled blurred or insufficient-depth frames are rejected. Native RGB/depth calibration is maintained during fusion.

An installed Open3D 0.20.0 Windows build failed a synthetic-plane fusion check. Those outputs are preserved as failed diagnostics; 0.19.0 is the preferred reconstruction. This is not evidence that all Open3D 0.20 installations fail.

Outputs include colored triangle meshes (PLY/GLB), point clouds, camera trajectories, static previews, self-contained interactive HTML viewers, reconstruction summaries, and processing scripts. Mesh/cloud export element counts were checked by reading them back. No loop closure, global pose optimization, automatic hole filling, or invented geometry has been applied.

Working reconstructions:

- `../hallway_prototype/`: first, geographically unassigned scan.
- `../ilounge_prototype/`: fourth-floor iLounge capture.
- `../mgh_staircase_prototype/`: multilevel staircase and extended fourth-floor capture.

The staircase run integrated 1,242 of 1,434 sampled frames and produced 4,015,489 triangles / 1,480,307 cloud points. It decoded 14,337 video frames; one additional trailing container-reported frame was unavailable. Its reconstruction took approximately 88 seconds locally; that is one run's timing, not a device or service benchmark.

The staircase review adds an upper-height floor-4 slice and camera-height profile. The generic low-height `top_down.png` is not a complete map of a multilevel recording. Blank areas in any projection mean unknown/unobserved surfaces, not verified traversable space.

## 5. Geometric checks and floor-plan work

Before reconstruction, an initial visual trial sampled 30 images from the geographically unassigned first scan. It found readable EXIT signs at frames 1339 and 1741 (likely repeated sightings), an uncertain cabinet candidate, and an unreadable room plaque. Structural checks confirmed frame/pose/depth indexing. A sampled EXIT-sign depth patch was approximately 4.695 m but only confidence 0/1, so no precise sign coordinate was published. The assistant inspected the images; a deployed Keryx/Modal agent or external vision API did not run. See `../scan_trial_report.md`.

The user supplied a floor-4 architectural plan and a plan annotated with the walk and sign sightings. A draft transformation relates the iLounge scan's X/Z coordinates to the annotated image. It supports visual context and draft sign positions; it is not surveyed building registration.

The user supplied an approximately 78.5 ft hallway length, believed to correspond to 400J. A provisional reconstructed span was about 77.8 ft, conditional on matching the same endpoints. This does not validate all scan dimensions, floor-plan alignment, global drift, or whole-building accuracy. No scale correction was applied.

Nearby similarly directed depth views showed useful internal consistency in an earlier check (approximately 2.31 cm median of pairwise median disagreements across 20 pairs). This is not independent dimensional accuracy. Other generic adjacent-view checks include rotations and little/no overlap, so their large nearest-surface distances are not directly interpretable as tracking error.

### Capture and compute takeaways

The iLounge recording had a larger accepted-depth fraction (about 65% versus 32%) and a slower recorded path speed (about 0.53 versus 1.02 m/s) than the original hallway, but they show different places; this is not a controlled proof of capture improvement or accuracy. Turns still introduced blur, and some images mostly show plain walls/floor/ceiling. Useful practice is steady walking, slow turns, readable signs plus surrounding architecture, overlapping views, both travel directions, and clear views of landing/floor signs and doorway thresholds. Each new recording should overlap an already mapped location and preserve its full Stray Scanner ZIP.

Local CPU processing has already produced the geometry; compute has not been isolated as the reason localization fails. Data coverage, calibration, correspondence quality, and consistent geometry still need testing. Cloud AI remains permitted, but more compute alone is not evidence that an ambiguous match or an unverified route becomes correct.

## 6. Labels and observations

| Item | Evidence / current meaning | Still required |
|---|---|---|
| 416 iLounge | User-annotated plan plus newer entrance-context observation | Verified doorway threshold and route connection |
| 420 Student Services | User-annotated plan plus newer Student Services sign observation | Verified entrance anchor |
| 430 Computer Classroom | User-annotated plan plus newer classroom sign observation | Identify/verify actual entrance(s) |
| 440 Team & Quiet Labs | Staircase numeral plus user-supplied independent signed-door photo IMG_5386 | Reviewed 3D entrance anchor and route connection |
| iSchool sign / blue poster | Plan label and shared lobby appearance | Reviewed 3D landmark anchor if used for navigation |
| EXIT | Sign label from annotated plan | Physical exit route/destination and availability not verified |
| IT Help Desk | Sign sighting in staircase capture | Room number and doorway location unknown |
| 400A, 400B, 416A | Plan-only pending room records | Physical identification and entrance anchors |
| 400W, 400J, 400M | Draft lobby/corridor context labels | Reviewed boundaries and routing geometry |
| Cropped right-edge "430 Cor..." | Incomplete annotation | Remains unresolved; do not invent the full name |
| 4EL1 | Unverified architectural-plan label | Do not interpret it as an observed staircase connection |

Labels are stored as records and source observations. They are not yet a complete set of accurate, clickable doorway pins in the 3D viewer. Approximate sign locations are not door entrances. Signs reviewed by the assistant are not results from a validated automatic detector.

## 7. Staircase findings

The new recording is an **ascent**, not a descent. At approximately 10.2 seconds (frame 610), a partly cropped/blurred lower sign shows floor numeral 3. At approximately 42.8 seconds (frame 2565), an upper sign clearly identifies STAIR 1 and floor 4. The continuous walk and height trajectory support the 3 -> 4 connection.

The first roughly 45 seconds cover the ascent/landing; subsequent footage covers the upper-floor lobby and corridors. Segment boundaries remain approximate. The full recording's camera-height change is 3.69 m, not a surveyed floor-to-floor rise.

The upper sign also mentions locked roof access and exit on floor G. Those are observed sign statements only; neither route/access condition has been independently verified. Physical STAIR 1 has not yet been matched to an architectural stair identifier, and actual landing doorway thresholds are not anchored. The stored floor connection remains draft with routing disabled. Floor 3 has only limited stair/landing coverage, not a reconstructed floor plan.

## 8. Localization and registration experiments so far

### Original iLounge baseline

Built a reference library of 61 views and 20,396 depth-lifted SIFT feature points. Queries used RGB plus known camera calibration; query depth and recorded poses were not inputs to the position solver. Sixteen same-recording queries were withheld from the references; references within 2 seconds of each query were excluded.

Only **1/16** passed the predefined image-match/geometric thresholds. An exhaustive-reference diagnostic also accepted 1/16. The successful query showed the distinctive blue Information School poster. Both runs remain same-recording research checks, not independent-phone accuracy tests. Recomputed JPEG features changed the result's estimated pose, illustrating sensitivity to matching details.

### Staircase -> iLounge registration attempt

Visual overlap is evident in the blue-poster lobby and corridor context. However, the current automated transformation is not reliable:

- 26 new-recording queries were checked against 61 old reference views.
- Five met per-image PnP criteria, but the transforms did not form a consistent multi-view cluster under 0.75 m / 5-degree thresholds (largest cluster: one).
- A follow-up scale-preserving, depth-to-depth rigid check accepted **0/8** candidate pairs under all its checks.

These original numbers are now invalid as a synchronized registration experiment: the new-recording RGB seeking was misassociated with pose/depth indices. They remain historical diagnostics, not proof that the recordings show different places. A corrected cross-scan rerun is pending. No candidate matrix is approved for geometry merge; both scans retain their own frames. An apparently matching poster alone is insufficient to verify a building transform.

### Ordinary-phone recognition milestone

The user approved moving ahead with a visual reference map and a small independent-phone demonstration. Build and validate in the staircase scan's own frame first; full cross-scan merging is not a prerequisite for a single-map recognition experiment.

The implementation should select clear, distributed reference images, connect local features to measured 3D points, retrieve candidate views from an RGB query, estimate calibrated camera pose, and reject ambiguous or inconsistent results. Image recognition is not the same as knowing the phone's precise position and facing direction. Multiple views/frames are needed before trusting a navigation pose.

Run a stronger pretrained feature matcher rather than assuming the existing SIFT implementation is sufficient. A custom DISK + LightGlue experiment can use the existing depth map; do not describe it as a completed full hloc/COLMAP deployment. No building-specific neural-network training is needed for this initial approach. DISK is preferred for this experiment because the upstream LightGlue documentation distinguishes its Apache-2.0 licensing from SuperPoint's restrictive license. Commercial distribution still requires a dependency/model license review.

Independent ordinary-phone photos and reviewed entrance anchors are still needed. Do not fill these gaps with held-out images from the same video or the scanning phone's own poses.

## 9. Decisions register

| ID | Decision | Status / rationale |
|---|---|---|
| D001 | General voice-driven indoor wayfinding, not emergency-only scope | User direction; do not claim emergency readiness |
| D002 | Accumulate scans and annotations in one portable SQLite master | User direction; preserve bytes, provenance, and revision history |
| D003 | Keep each scan in its own frame until registration is reviewed | Active; prevent false geometric merges |
| D004 | Do not scale from the single approximate 78.5 ft reference | Active; endpoint correspondence and independent checks remain limited |
| D005 | Use measured depth/poses for prototype geometry, Open3D 0.19 locally | Implemented; failed 0.20 artifacts retained as diagnostics |
| D006 | Keep sign labels separate from entrance anchors and route connectivity | Active; all navigation remains disabled |
| D007 | Treat failed localization/registration separately from verified map data | Active; initial and cross-scan checks are not deployment passes |
| D008 | Prototype a small fourth-floor recognition-and-one-destination flow first | User approved 2026-10-17; ordinary-phone test photos still needed |
| D009 | Create this project folder and keep a running Markdown history/decision register | User approved 2026-10-17; sync revisions back into the master |
| D010 | Evaluate pretrained DISK + LightGlue locally, rather than train from scratch | Implementation choice 2026-10-17; not a guaranteed localization improvement |
| D011 | Keep the canonical database at its established path, organize around it | Avoid moving live assets or creating competing archives |
| D012 | Retain the stricter 0/20 result and leave routing disabled | Implementation choice 2026-10-17; do not lower checks to manufacture success |
| D013 | Select calibrated scan images by sequential decoded ordinal, never unchecked random seeking | Implementation correction 2026-10-17; exact pixel-hash audit found 13/14 wrong seek indices |
| D014 | Invalidate and block v1 pose-map use while retaining every original diagnostic | Supersedes treating D012's 0/20 as positioning-performance evidence; correct source observation provenance and rerun without relaxing acceptance |
| D015 | Map video ordinal i to odometry/depth row via verified timestamp fingerprint (+1 for b9dca4993d); supersede v2 maps | Implementation correction 2026-10-17; v2 numbers retained as diagnostics; thresholds unchanged |
| D016 | Publish code, docs, audit, and map v3 to public GitHub repo jfbami/Fuga (PR 1); keep master, ZIPs, floor plans private | User decision 2026-10-17 |
| D017 | Complete predeclared v3 A/B and low-rotation v4 B without changing thresholds or retrieval; reserve fresh data for later variants | User continuation request and implementation choice; B consumed by these two variants |
| D018 | Feed the existing app arrow/path/proximity-buzz flow with camera-to-map localization; keep existing UI work | User clarification; newer navigation code is on nav/route-guidance, separate map/frame |
| D019 | Preserve the two iPhone 14 photos as independent queries; gate estimated calibration and keep two-reference checks | User identified 430/440; implementation protocol fixed before matching; later follow-ups are diagnostics |
| D020 | Add floor-2/3 scan ZIPs and plans to the sole master, preserving originals and separate frames | User upload/continuation; plans and new raw data remain private |
| D021 | Retain floor-2 global association failure; verify both timestamp segments and exclude uncertain boundary ordinals | Implementation evidence; no pose-time interpolation, scale change or threshold relaxation |
| D022 | Catalog known room identities and keep plan labels, doorway candidates and measured sign landmarks separate | User asked for room labels/anchor points; draft placement only, no route activation |

Future decisions are not pre-approved merely because they appear in the roadmap. Add new IDs when an actual decision is made, identify whether it came from the user or an implementation choice, and record the consequences/evidence. Reversals should supersede earlier entries rather than erase them.

## 10. Roadmap and acceptance gates

| Step | Current state | Completion evidence |
|---|---|---|
| Preserve scans and create measured geometry | Three originals archived; prototypes exist | Checksums/export checks; not global survey accuracy |
| Build improved single-scan visual reference map | v3 association fixed; v4 low-rotation built | Manifests and comparison report; v1/v2 and partial builds remain historical diagnostics |
| Run withheld-image diagnostics | v3/A 2/20 accepted (2 within internal tolerance, 0 >2 m); v3/B 2/20 accepted (2 within internal tolerance, 0 >2 m); v4/B 5/20 accepted (5 within internal tolerance, 0 >2 m) | Predeclared A/B; thresholds unchanged; same-recording only |
| Test independent ordinary-phone images | Two original iPhone 14 photos received: 430 and 440; 430 numerical hypothesis, 440 unresolved | EXIF-estimated calibration only; no metric/live-navigation pass; keep photos out of mapping |
| Verify one destination entrance, initially 416 | Pending physical/image review | Exact threshold anchor plus documented room correspondence |
| Build a reviewed small navigation graph | Pending | Verified corridor edges, turns, entrance node; no mesh-gap inference |
| Estimate a stable live phone pose | Pending | Calibrated query and multi-frame agreement; honest failure state |
| Add voice command and guidance UI | Not implemented | Resolve destination, compute route, issue instructions from trusted pose |
| Register scans / extend to all MGH floors | Pending | Distributed overlap, reviewed transforms, explicit inter-floor edges |

No arbitrary accuracy threshold is recorded here as a passed requirement. Evaluate accepted-query fraction, wrong-place/wrong-floor cases, position/orientation disagreement, latency, and failure handling. Recorded poses supply internal consistency comparisons only; independently known positions are needed for physical error claims.

## 11. Next capture needed from the user

See `capture/REGULAR_PHONE_TEST.md`. Supply original rear-1x photos from a separate pass, both travel directions, with recognizable room/sign context. Include some plain stretches and deliberately out-of-map scenes to check rejection. Record nearby doorway/landmark and facing direction for each; do not substitute guessed exact coordinates. Use independently measured positions if we want metric accuracy figures.

Do not crop, perspective-correct, or send screenshots in place of originals. Preserve metadata. Camera intrinsics must correspond to the actual phone, lens, image dimensions, and orientation; never reuse the scanning phone's calibration for a different phone.

## 12. How to maintain this log

After meaningful processing, a result, or a user decision:

1. Inspect the master summary/current records before changing the project.
2. Append a dated activity entry with the request, actual actions/results, decision IDs, assets, limits, and next step.
3. Update current-state tables without erasing contradictory/older results; add superseding decision entries when necessary.
4. Embed the revised log and new originals/derivatives/records in a new master transaction. Keep original bytes and older revisions.
5. Run full archive integrity/checksum verification and report pending areas, labels, alignments, and localization tests.

This is a maintenance convention for future work in this project, not a background monitor or a promise to change files when no agent is running.

## 13. Activity log

### 2026-10-17 — Consolidated history and began camera-recognition milestone

- User approved the reference-map / ordinary-camera testing plan and requested a project folder, comprehensive Markdown summary, and future decisions recorded here.
- Created `MGH_Project/` without moving the canonical master or prior reconstruction exports.
- Recorded the existing geometry, sign evidence, scale caveats, label status, failed diagnostics, revised general-navigation scope, and pending independent-phone validation.
- Began an isolated local DISK + LightGlue setup and single-scan reference-map experiment. Results must be added below after execution; this entry alone does not mean the matcher works.

### 2026-10-17 — Built the experimental visual reference map

- Built 129 reference views and 84,043 depth-linked features from the staircase recording in its original coordinate frame. Pretrained DISK features were used; no building-specific model training or scan merge took place.
- Saved source images, features, map manifest, contact sheet, CLI, package lock, pinned upstream source subset, model sources/checksums, and a doorway-review queue. The model source subset includes only the needed Apache-2.0 DISK/LightGlue files, with unchanged upstream source/LICENSE and a minimal import surface.
- Fixed an initial integration issue: Python's SQLite BLOB reader lacks the `seekable()` interface expected by ZIP reads. A read-only adapter now provides that interface. The failed setup produced no reference map; the fixed build reads the preserved original directly from the master.
- Checked image/calibration orientation for four quarter-turn cases and reference 3D-to-image projection for all 84,043 valid points. Maximum numerical projection disagreement was approximately 0.0016 pixels. These are implementation consistency checks, not physical accuracy tests.
- Started a 20-query same-recording evaluation with >=2 s temporal exclusion and a requirement for support from two consistent reference poses. Its acceptance protocol is stricter than the old single-view baseline, and the recording differs; raw pass counts are not a controlled before/after matcher comparison.
- Independent regular-phone images, calibration, exact entrance anchors, route graph, live tracking, and voice integration remain pending.

### 2026-10-17 — Withheld-image experiment completed; not a localization pass

- **0/20** same-recording queries passed the complete multi-reference pose protocol. Per-view candidates were retained in the detailed report rather than promoted to trusted positions or discarded from the denominator.
- Median measured query runtime was approximately **8.26 seconds** on this local CPU, excluding initial model loading. No real-time phone performance claim is made.
- Confirmed query/reference frame disjointness and the >=2 s timestamp exclusion. The solver used RGB plus correct calibration, not query depth or recorded query pose.
- A separate external-image CLI smoke check matched an exported reference image most strongly to itself (frame 7110, 850 feature matches). That image was deliberately not independent, had no calibration supplied, and produced only an unverified appearance result; it is not part of the 20-query evaluation.
- Keep the map and matcher as research artifacts. A trained/working ordinary-phone positioning system has **not** been demonstrated. Further retrieval and depth/multiview consistency investigation is needed before attempting trusted guidance; collecting fresh test photos alone does not turn this failed internal test into a pass.
- Detailed results: `localization/RUN_REPORT.md`, `localization/experiment_summary.json`, and `localization/evaluation_v1/results.json`. Archived model weights and a source subset make the experiment reproducible without pretending the virtual environment itself is portable.
- Decision D012: retain the stricter failure result, do not loosen checks to make the demo look successful, and leave all routing disabled. This is an implementation/safety choice, not a new user-approved accuracy target.

### 2026-10-17 — Diagnosed and corrected RGB/depth/pose frame association

- The user asked how to fix the failed positioning result. Inspection found that random `CAP_PROP_POS_FRAMES` seeking did not return the requested acquisition-frame ordinal on this recording/backend.
- Exact SHA-256 comparison of resized decoded pixels across 14,337 sequential frames found mismatches in **13/14** sampled requests. For example, request 900 returned actual frame 957, and request 7000 returned 7191. This paired images with incorrect depth, intrinsics, and recorded poses, explaining a concrete source of inconsistent estimates.
- Corrected the active builder/evaluator to decode sequentially and select the true ordinal, built a separate v2 map, and blocked legacy map loading. No original ZIP, old map, old report, or earlier record revision was deleted. No geometric acceptance threshold was relaxed; candidate retrieval and model settings remained unchanged for the first corrected rerun.
- The original 0/20 test and staircase-to-iLounge registration trials are **invalidated as synchronized positioning evidence**. This is an implementation bug, not proof that the uploaded scan or regular-camera approach cannot work. Other remaining causes have not thereby been ruled out.
- The mesh fusion and original iLounge SIFT reference/query extraction already used sequential decoding; this specific seeking error does not invalidate their selection method. Earlier limitations and the 1/16 SIFT result remain separate research findings.
- Corrected staircase sign-source ordinals: lower floor-3 image 648 (~10.80 s), upper STAIR 1 / floor-4 image 2728 (~45.50 s). Other mapped seek aliases: iLounge 7092 -> 7289; Student Services 8450 -> 8572; Computer Classroom 9808 -> 9858; room 440 10865 -> 10886; IT Help Desk 14034 -> 14012. The old blue-poster observation at seek request 3470 lacks an exact-index correction in this audit and keeps an unknown source ordinal rather than a guessed one.
- The v2 map contains 125 reference views and 66,773 confident depth features. All feature-projection round trips passed (<0.002 px numerical disagreement), and the active loader rejected the invalidated v1 map. These are implementation checks, not physical accuracy validation.
- Retired random-seeking analysis helpers must not be reused to assign calibrated frame/pose data without correction. Visible sign labels remain draft identities, not doorway anchors. Floor-3 coverage is still only stairs/landing; the old industrial scan remains geographically unassigned; cross-scan registration and architectural stair correspondence remain pending.
- Completed the corrected rerun: **1/20** accepted with unchanged two-reference rules, and that estimate was within the internal 0.5 m / 10-degree tolerance. Query 3465 had four consistent reference views and approximately 0.078 m position disagreement with its recorded pose. This is not surveyed or independent-phone accuracy. Median CPU query runtime was approximately 7.11 s, excluding initialization.
- The fix removes a confirmed software error but does not make recognition reliable. Remaining work is to audit candidate retrieval and cross-view correspondences for rejected images, then validate independent-phone photos and reviewed entrance/route geometry. No acceptance threshold, query-depth shortcut, or recorded-query-pose oracle was introduced to make the result pass.

## 14. References and detailed evidence

- Inspiration discussed by the user: [Keryx](https://github.com/Wenjix/keryx). No complete Keryx deployment has run here.
- [Stray Scanner format](https://github.com/strayrobots/scanner/blob/main/docs/format.md) and [StrayVisualizer pose/fusion reference](https://github.com/kekeblom/StrayVisualizer/blob/main/stray_visualize.py).
- [Hierarchical Localization](https://github.com/cvg/Hierarchical-Localization): reference architecture for image retrieval, feature matching, and pose estimation; its documentation discusses using LiDAR-supported maps.
- [LightGlue upstream](https://github.com/cvg/LightGlue): pretrained matcher and feature integrations; check model-specific licenses before shipping.
- `../ilounge_localization_check/CHECK_REPORT.md`: original 1/16 research result. Its then-pending distance discussion predates the later 78.5 ft comparison.
- `../ilounge_dimension_check/measurement.json`: conditional length comparison.
- `../mgh_floor4_draft/building_draft.json`: draft image registration and sign labels.
- `../mgh_staircase_review/REVIEW.md`: floor/sign evidence, reconstruction notes, and failed cross-scan checks.
- `../MGH_Master_staircase_update.json`: revision-4 integrity/checksum receipt. Inspect the newest receipt for later verification.

All evidence files above are also embedded in the master. Use `MGH_Master_tools.py list-assets` to discover exact archive logical paths and `export` to recover them.

### 2026-10-17 — Audited v2 retrieval and cross-view 3D correspondences; work paused by user

- Pre-declared plan: `localization/audit_v2_retrieval_correspondence/AUDIT_PLAN.json` (query set A = the v2 queries; set B held out, not yet evaluated). Full findings: `AUDIT_REPORT.md` in the same folder. Recorded poses and query depth were used only as post-hoc diagnostic oracles. No acceptance threshold was changed.
- **New software bug confirmed:** decoded video ordinal *i* shows odometry/depth row *i + 1* (first odometry row has no video frame). Confirmed by timestamp-gap fingerprint (100% agreement, 936 gaps) and by geometry (median cross-view error 3.5 px at +1 vs 4.8 px at 0). iLounge `b43779c138` shows the same +1 by timestamps, so its 1/16 SIFT result carries the offset (not rerun). `e1a70b754b` has no gaps, so its offset is unknown.
- Sign images keep their corrected decoded ordinals (648, 2728, 7289, 8572, 9858, 10886, 14012). Their depth/pose rows are ordinal + 1. `doorway_review_queue.csv` was rewritten from stale seek labels to these values.
- Retrieval: v2's cross-image ratio vote passed only 158/19,952 query features. Mutual-NN or LightGlue-count ranking recalls overlapping references far better. **But** even oracle retrieval accepts only 3/20 under unchanged rules: 5/20 queries have at most one overlapping reference after the 2 s exclusion.
- Cross-view 3D: overlapping views disagree by a median of about 0.15 m / 3 degrees. The gyroscope confirms the camera turned at a median of 66 degrees/s (above 30 degrees/s about 85% of the time). Fast sweeping plus millisecond timing/rolling-shutter effects is the main cause. A residual of about -6 ms was estimated but **not** applied.
- Safety: 14 of 34 single-view-accepted poses were wrong place (>2 m). The two-reference rule rejected all of them; 0 wrong-place queries accepted.
- Simulated with the association fix and v2 retrieval: 2/20 accepted (both correct), up from 1/20.
- Implementation (D015): `mgh_localizer.py` now verifies the video/odometry offset by timestamp fingerprint at build/evaluate time and indexes maps by odometry row. Legacy v1/v2 maps are refused for querying. Added options `--selection low_rotation`, `--query-ordinals`, and `--query-set-label`.
- Built `visual_map_v3` (125 views, association fixed, same RGB images as v2). **Not yet evaluated.** `visual_map_v3_interrupted_partial` (session ended) and `visual_map_v4_low_rotation_stopped_partial` (stopped at user request) are preserved incomplete builds, not maps.
- Paused at user request. Remaining per `EVALUATION_PLAN_v3_v4.json`: evaluate v3 on sets A and B; optionally rebuild and evaluate v4 on set B. Routing stays disabled; independent-phone validation, doorway/stair anchors, and scan registration remain pending.
- D016 (user decision, 2026-10-17): published code, docs, audit, and `visual_map_v3` (corridor imagery) to the **public** repo `jfbami/Fuga`, branch `mgh-localization`, PR https://github.com/jfbami/Fuga/pull/1, under `mgh/`, to split work with teammates. Excluded: the SQLite master, original scan ZIPs, and all floor plans (NetID-only). This log entry was written after master revision 7 and is not yet embedded in the master.

### 2026-10-17 — Continued predeclared v3/v4 evaluation and prepared team handoff update

- Resumed at the user's request; inspected revision 7/current records, D015/D016 and the audit before running.
- D017: v3/A 2/20 accepted (2 within internal tolerance, 0 >2 m); v3/B 2/20 accepted (2 within internal tolerance, 0 >2 m); v4/B 5/20 accepted (5 within internal tolerance, 0 >2 m). All three runs completed all 20 declared queries; no threshold or retrieval change. Full results, query images, manifests, comparison checks and logs are preserved. v4 was rebuilt into a new directory; stopped partials are untouched.
- Set A is audit-exposed diagnostic data. Set B is now consumed by the two predeclared variants; future algorithm changes require a new held-out set. Recorded-pose disagreement is internal consistency, not surveyed accuracy or independent-phone validation.
- The revised log (including D016, previously absent from revision 7), results, maps, continuity documents and structured current records are staged for one canonical-master transaction by `work/archive_mgh_v3_v4.py`. Its post-commit receipt `../MGH_Master_v3_v4_update.json` records revision and full integrity/checksum verification. Original scan checksums and older history are retained.
- Prepared updated docs/results for existing public PR https://github.com/jfbami/Fuga/pull/1. Publication excludes the master, original ZIPs and floor plans; actual Git push is verified separately after the archive update.
- Routing remains disabled. Unresolved room/cropped labels, doorway/stair anchors, alignment, floor-3 corridor coverage, unassigned earlier scan and independent-phone validation remain pending. No whole-building rescan requested.

### 2026-10-17 — Tested independent phone photos and prepared existing-app localization interface

- User clarified the app goal: select a destination such as 440; the existing arrow follows the created corridor path and buzzing signals progress. Keep existing GitHub UI work; focus here on location/direction from the mapped 3D representation (D018).
- Received original IMG_5385.HEIC, user located in front of 430 Computer Classroom; IMG_5386.HEIC, in front of 440. Metadata: iPhone 14 rear wide. Preserved bytes/checksums/provenance and decoded lossless analysis images; never added either photo to mapping (D019). Room 440's sign visibly reads Team & Quiet Labs; its exact 3D doorway threshold is still unverified.
- 430 obtained consistent two-reference geometric hypotheses with v3/v4. 440 did not; exhaustive matching against all 125 v3 references still yielded one consistent reference. Mutual-NN retrieval was implemented as an option but did not improve these two outcomes. Full primary/follow-up plans and failed candidates are retained in `localization/evaluation_independent_phone_430_440/`.
- Calibration came only from an explicitly estimated EXIF-based matrix. No surveyed camera locations or known facing angles were provided. Numerical hypotheses are not app-usable poses or an independent-phone accuracy pass. Future tuned variants need new held-out photos.
- Added `phone_localizer.py`, `serve_phone_localizer.py` and `PHONE_APP_INTERFACE.md` to provide the existing app a concrete image/intrinsics/timestamp-to-scan-pose interface. Six contract tests passed, plus a real model/image HTTP smoke test; its temporary server closed afterward. The arrow/app source was not replaced. No iOS build or live walk ran on this Windows host.
- Inspected newer `nav/route-guidance` commit d7229ac. It has a separately saved ARWorldMap and plan-meter hallway graph without 440. Those coordinates and doorway assertions are unreviewed external working data relative to this archive, not an approved staircase-scan registration. No implicit merge/scale correction or routing enablement occurred.
- User offered floor-2/3 plans and new scans; files not yet received at this entry. Preserve originals and add to the same archive when supplied. No whole-building rescan requested. Floor plans and new independent-photo originals stay private; public handoff contains code and text results.

### 2026-10-17 — Added floor-2/3 plans and new scan captures

- User supplied `3rd floor.zip` (`5a6579fe23`), `2nf floor mgh + elevator.zip` (`0162f41946`), and `MGH1197_02.pdf` / `MGH1197_03.pdf`. D020: preserve all four originals byte for byte in the existing master with checksums/provenance; no competing archive. Both ZIP CRCs and expected depth/confidence filename coverage passed.
- Reconstructed both in their own coordinate frames with Open3D 0.19 and unchanged depth/TSDF settings. Colored fusion uses sequential RGB decoding and audited row association. Self-contained 3D viewers, static previews, frame logs, meshes, clouds and export checks are retained. Details/counts are in `ingest_floor2_floor3_20261017/INGEST_REPORT.md` and `ingest_summary.json`.
- D021: floor 3 has exact +1 fingerprint agreement (498 gaps). Floor 2 failed the strict global validator: a video timestamp-duration anomaly near 260 s and ~62 ppm clock difference. Both sides separately have unique exact +1 gap fingerprints (654/134 gaps); RGB ordinals 14924-14932 are excluded around the boundary, dropping one reconstruction sample. No pose-time interpolation, geometry scale correction or localization acceptance change was applied. The old global visual-map validator remains unchanged; its failure/logs are preserved.
- Floor 3 is no longer represented only by the earlier STAIR 1 landing; it now includes separate corridor coverage. Floor 2 has partial corridor/atrium/elevator context. Elevator views are observations, not a verified between-floor connection. Plan-to-scan alignment, shaft/stair IDs and actual entrance anchors remain pending. Earlier scan `e1a70b754b` stays building/floor unassigned.
- Batch archive script `work/archive_mgh_floor23.py` embeds new originals/derivatives, these notes and structured current records transactionally. Its post-commit receipt `../MGH_Master_floor23_update.json` records the actual revision and full integrity/checksum verification. Existing originals/history remain unchanged; routing stays disabled, phone-localization limitations remain open.
- Floor plans (including extracted contents/renders) and new scan originals/derivatives remain private. The earlier PR update was pushed at commit 61ec52a; any new public handoff update is restricted to code/text inventory and contains none of these new private source/geometry files.

### 2026-10-17 — Cataloged room labels and draft anchors across floors 2/3/4

- User asked to continue piecing the data together and label each known room for anchor creation (D022). Found the named full floor-4 PDF locally; preserved its provenance as an existing local project source, distinct from the two newly uploaded PDFs.
- Extracted 305 unique plan labels: 230 room-number labels, 56 other plan-space labels, 14 stair labels and 5 elevator labels. Kept native page/label bounding boxes, exact source checksums and unknown room functions. Existing known names and scan/photo evidence for 416/420/430/440 remain linked. Plans and extracted coordinates remain private.
- Created six distinct plan doorway candidates: 416 west, 420 east double doorway, 430 west/east and 440 west/east. The full plan shows multiple entrances for 430/440; the user's room-level photo location does not by itself identify which doorway. Other rooms are queued for doorway review rather than given guessed entrances.
- Recorded depth-backed draft 3D sign landmarks for 416, 430 and 440 in the staircase scan frame using sequential ordinal +1 and unchanged confidence/range/edge filters. 420 failed confident-depth support and keeps a null 3D position. These are sign points, not door thresholds or physical room centres, and are not surveyed accuracy evidence.
- Added private searchable room/anchor review, CSV/JSON catalog and source-marked plan/sign previews. Existing legacy 400A/400B room records retain pending classification. Verified 3D doorway anchors remain 0; scan-to-plan registration, corridor edges and routing remain disabled/pending.

- Archive implementation diagnostic: initial floor-2/3 batch assembly raised a missing-association metadata error before commit and rolled back to revision 8 (three scans). Corrected the per-scan metadata join and stage one final payload per record key in the batch; retain the failed script/receipt. No partial original/annotation import was committed.


### 2026-10-17 — Reviewed live-camera design and independent iPhone video

- D023 (user design clarification): camera stays open; user-selected floor plus GPS supplies context, room-number recognition supplies observations, visual localization and ARKit tracking must supply position/direction for the existing arrow/path/buzz. This architecture is intended, not implemented end-to-end. GPS is not a room anchor.
- D024: received IMG_5391.MOV; preserve unchanged original privately as a diagnostic query, never a mapping reference. Sequentially decoded 779 frames (~13 s), iPhone 14 portrait 1080x1920. Manually read 430 Computer Classroom at ordinal 0 and 440 Team & Quiet Labs at ordinal 480 (~8 s); this does not identify a surveyed phone path or specific plan entrance.
- GPS metadata reports ~16.6 m horizontal accuracy; exact coordinates remain private. No usable calibrated frame intrinsics or ARKit poses were found in parsed tracks; video-orientation/face/live-photo metadata is not ARKit tracking. No still-photo calibration was transferred to the video.
- Predeclared seven approximately two-second samples; unchanged v4/legacy retrieval produced appearance-only, unverified candidates for all seven. No metric pose queries were attempted because calibration is missing; this is not a 0/7 geometric failure or a localization pass. No automatic OCR test ran. Adjacent video frames are correlated, not seven independent tests.
- Preserved original, frames, metadata, planned diagnostic, raw results, comparisons, report and processing scripts in the sole master. Next implementation: instrument existing iOS frame/intrinsics/capture-time pose export and connect sign observations to building/floor context, then review map-to-ARKit alignment and 440 doorway/path anchors. No new capture requested now. Routing remains disabled; scan/plan/stair/elevator registration and independent-phone metric validation remain pending.

- Subsequent manual comparison: query ordinal 0 visibly shows 430, while top appearance-reference rows 10883/10910 visibly show 440. Preserve this concrete wrong-room appearance ranking; no geometric pose was attempted or accepted. Prioritize room-sign context to disambiguate candidates alongside calibrated geometric verification; floor alone cannot distinguish them.


### 2026-10-17 — Added first floor/voice/quick-look iPhone test flow

- D025 (user flow clarified): choose floor, speak destination, give the camera a quick look. Mapping is done beforehand; the user need not scan a whole floor or read room numbers. OCR is optional, superseding any implication in D023 that room-number recognition is required. GPS remains building context, not indoor positioning, and is not fused in this implementation.
- Merged public existing app source through nav/route-guidance fbcfcc1 into mgh-localization, preserving arrow/path/haptic implementations. Its graph/alignment files remain external, unreviewed coordinates; they were not imported as verified canonical room/door anchors or merged into scans. The new screen is added to the existing app. Both manual and automatic guidance starts are blocked until canonical route/doorway registration is reviewed.
- Implemented floor 2/3/4 selector, on-device spoken destination input with typed fallback, a live camera preview, three same-frame ARKit image/intrinsics/timestamp/transform captures, optional HTTP matching and private JSON export. Device intrinsics are not surveyed calibration/accuracy validation. Portrait pixel rotation, calibration and camera-axis transformations are explicit and projection-tested; actual iPhone orientation/encoding still needs verification. Room OCR is not required or implemented.
- Added explicit building/floor request context. Floor-4 requests conservatively omit references before 60 s (reviewed corridor after 48 s, exclusion margin); floor 2/3 requests return map unavailable without wrong-floor inference. Legacy requests and geometric thresholds are unchanged. This is a development reference restriction, not new held-out validation or an improved A/B score.
- Capture occurs before network requests; replies must match capture identity/time, image hash, map and context. Two agreeing capture-time scan-from-ARKit transforms produce only a possible-start diagnostic. Nothing applies that transform to the route graph or enables guidance. Correlated burst frames are not independent validation. Private capture export retains raw requests/responses and is shared only on explicit user action.
- Validation: 12 new context/geometry/export-review tests plus six existing service/phone tests passed (18 total). Six changed/new Swift files passed grammar syntax checks; plist/build configuration checks passed. A real v4 model/image HTTP request with floor context returned 200 and retained the estimated-calibration gate. Its temporary localhost server is closed. No native Swift typecheck, Xcode build, iPhone capture, voice permission flow, latency test or end-to-end guidance test ran on Windows.
- D026: user confirmed a teammate has Xcode on a Mac and asked how to install. Prepared mgh/ios/PHONE_TEST_GUIDE.md: build mgh-localization on a physical iPhone, first capture without a server, then share the private calibrated JSON. No additional regular video or whole-building rescan requested. Next is the teammate's native build/capture, then calibrated recognition debugging and verified route/doorway registration.
- Source, guide, checks and updated notes are embedded transactionally by work/archive_mgh_quicklook_integration.py. Full master verification follows. Public handoff contains source/text checks only; no original video/photos, floor plans, new private plan coordinates or reconstruction geometry are published. Scan frames, original bytes, unknown labels and unverified doorway/stair/elevator links remain preserved; routing remains disabled.


### 2026-10-17 — Audited 430/440 appearance ranking without room OCR

- User approved prioritizing the 430/440 matcher while the teammate merges/builds the app, and asked which framework is active. The implementation uses DISK + LightGlue with custom depth-backed PnP/multi-reference localization; full Keryx/hloc integration has not run. ARKit handles motion/capture, not a magically registered LiDAR mesh.
- D027 (development experiment, not an accuracy target): predeclared uncalibrated 2D geometry checks on seven exposed IMG_5391 samples, using exactly each old candidate pool. No new room-labelled candidates, OCR, GPS, query depth/pose/intrinsics or core threshold change. Tested fixed fundamental-inlier and coverage-weighted rankings; preserve all failures/ambiguities.
- At ordinal 0, the visible 430 query previously ranked a 440 reference first (row 10883, 125 raw matches). The 430 reference row 9433 had 118 raw matches; after verification it has 106 fundamental inliers versus 69 for misleading row 10883. Both declared rankings now select 9433. This improves one known appearance-ranking error, not phone position/direction accuracy. Wrong-room references still retain many 2D inliers. No calibrated fix for the 440 segment is demonstrated.
- Four new synthetic contract/geometry tests passed. Replayed all cached pairs with final helper source (including a dimension-validation guard added after initial launch); masks/scores are unchanged. Detailed counts, matching caches, comparisons, sources, fixed plan and report are retained privately in localization/audit_video_430_440_geometry/.
- Keep the module diagnostic-only. Default matcher/backend and iOS source are unchanged; teammate's merge/build steps remain valid. Seven frames from one exposed clip are not independent held-out cases. Calibrated capture plus new held-out observations are still needed before adoption. Routing remains disabled; labels/doorways, stair/elevator links, scan/plan registration and independent-phone metric validation remain pending.


### 2026-10-17 — Reviewed teammate's merged app update

- User asked to recheck the updated repo. Fetched origin and inspected nav/route-guidance 478ecc6cf7563d589e6c3c1afab5379f7b9b58da; it contains quick-look commit 6c27398, the e11892c typed-distortion-array compile fix, and merged ElevenLabs direction cues/off-course haptics. Our optional geometry diagnostic 6fea30c is not in that branch and does not affect the capture app. No teammate branch was edited, merged or pushed during review.
- The array fix addresses a Swift type error in our earlier source that Windows grammar parsing could not detect. Reviewed source/commit history does not establish a successful Xcode build or actual phone capture. No calibrated private export has been received.
- Guidance remains gated false, QuickLookModel does not initialize the route navigator, and room 440 is still missing from the shipped graph. README's manual Start instructions are therefore stale relative to the gate. Before eventual guidance enablement, check tracking-loss suspension of cues and overlap when a turn starts during a playing clip. Those paths remain inactive behind the guard.
- Saved exact public-source snapshots and a static review under repo_reviews/nav_478ecc6/. Next: teammate's native build of the updated nav branch and one private calibrated capture test. No source-data upload, coordinate merge, verified-anchor promotion or routing enablement occurred. Labels, doorway/stair/elevator anchors, registration and independent-phone accuracy remain pending.


### 2026-10-17 — Made camera location the primary app start

- D028 (user requirement): Find where I am must find the starting position; no manual starting-room selection. Selected floor remains context. User asked how the 3D reconstruction actually helps navigation now.
- Fetched newer nav/route-guidance a2dce60 and merged it into the existing mgh-localization handoff branch, preserving the teammate's typed distortion-array fix, bundled voice/off-course cues, removal of the old 3D display and new voice/vibration test. The separate Juno-native branch remains separate; no unrelated branch was substituted.
- Replaced the manual starting-point screen with the camera/floor/voice location screen as the primary idle view. Removed starting-room and landmark re-pin pickers from the UI. Location checking no longer requires a destination; voice destination input remains available independently. Development server/export controls are collapsed, and location status explicitly distinguishes unconfirmed, checking, map unavailable and unverified candidate. A capture-only export remains Not located yet. No accepted scan pose is applied to a route.
- Preserved the feedback test and fixed shared voice playback being silenced by the idle 250 ms cue loop. Camera/microphone work stops feedback samples; leaving/backgrounding stops the test. Future route cues pause on unavailable AR tracking and silence a playing direction clip when navigator turn speech is active. Walking guidance itself remains gated false.
- Documented the distinction between a colored reconstruction mesh (inspection), depth-backed image features (experimental camera localization), and the separate plan-coordinate walking graph (not registered). The reconstruction does not currently drive the live arrow. Room 440 remains absent from the graph; actual entrances/paths, scan/plan registration, floor-2/3 reference maps, GPS fusion and independent-phone metric validation remain pending. No mesh merge, scale correction or core matcher threshold change.
- Six Swift files passed grammar parsing and plist/configuration checks; direct source review confirmed removal of manual pickers and preservation of gates/capture metadata. This Windows host did not perform native typechecking, Xcode build, visual iPhone QA, voice/haptic device tests or positioning validation. The teammate must build the updated source and send a private calibrated test export.
- Updated code/docs/continuity are embedded in the sole master transactionally; the removed old display source is retained as retired history and an active source manifest identifies the current app. Private sources and phone queries remain excluded from GitHub.


### 2026-10-18 — Prepared AI continuity handoff and checked newer teammate commit

- User requested a context prompt for another AI chat. Created a complete handoff covering canonical state, app/data evidence, validation limits and next actions.
- Verified mgh-localization head 1e4941c12251da7ee4c6d729d3fbe09fb42a5e33. Teammate nav/route-guidance is now 69698d42b0c32ae1c5190f40239cd1bd9d530909, adding corner clip playback, haptic recording allowance and persistent feedback-test results. PR #1 targets nav/route-guidance and GitHub reports CONFLICTING/DIRTY. No resolution or app source edit was made in this handoff turn.
- The next AI must reconcile the new voice hook/results with the automatic-start UI before native build/capture. No private JSON export or independent positioning validation has been received. Handoff and revised log are embedded in revision 16; original source data and routing-disabled status remain unchanged.


### 2026-10-18 — Resolved PR #1 against teammate nav/route-guidance 69698d4

- Fetched origin; nav/route-guidance was still 69698d4 (ElevenLabs corner clips via nav.playCue, haptics allowed while recording, feedback-test summary that persists after the test). Merged it into mgh-localization as 44c8a18 with a normal push; GitHub now reports PR #1 MERGEABLE/CLEAN. Only ContentView.swift conflicted: kept our camera-first Find where I am start screen (the teammate side was the old manual starting-point screen, already removed by D028); their onAppear playCue hook, RouteNavigator, FindMyHaptics and FeedbackTest changes merged unchanged.
- Follow-up edits: QuickLookView now shows the feedback result whenever it is nonempty, so the teammate's end-of-test summary stays visible. Found that the 4-per-second direction cue loop would cut off a corner clip within 250 ms once guidance runs; added VoiceGuidance.playTurn, which holds direction updates for the clip's duration, and pointed playCue at it. This path is inactive while guidanceEnabled is false.
- All 20 app Swift files pass tree-sitter grammar parsing (now including Fuga/Guidance). No native typecheck, Xcode build, iPhone voice/haptic test or positioning test ran. codex/juno-native-fix was not inspected or merged. Routing remains disabled; registration, doorway anchors, room 440 graph entry and independent-phone validation remain pending.


### 2026-10-18 — Made starting-location lookup automatic (no tap)

- D029 (user requirement): the user should not have to take pictures or press a capture button; pointing the camera anywhere, with the selected floor, should be enough to detect the area. User also wants the learned 3D representation to be enough to start directions, apart from the floor selector. Previously one tap captured three frames.
- QuickLookModel.autoLocate now starts when the Find where I am screen opens, when the floor changes and when the app returns to the foreground. It takes one exact-frame capture (image, intrinsics, timestamp, ARKit transform from the same ARFrame) at least 1 s apart while tracking is normal, checks it against the server before the next, and stops when two frames give agreeing scan-from-AR transforms (max 20 frames / 90 s, then Look again). Without a server it saves a 3-frame capture-only test and stays Not located yet. Floor 2/3 reports map unavailable without capturing. Destination entry and the feedback test remain usable while looking. Export format string is unchanged (capture_mode automatic, variable frame count).
- Agreement logic, match thresholds and the unverified-candidate status are unchanged; more attempts are not new accuracy evidence. Nothing connects a candidate to RouteNavigator; guidanceEnabled stays false. The proposed scan-frame route (scan trajectory as corridor graph, draft sign targets, ARKit bridge) is not implemented.
- Checks: tree-sitter grammar parse of six localization/app files, 12 quick-look Python tests passed. A try-inside-ternary Swift error was found and fixed by inspection; no Swift compiler, Xcode build or iPhone test ran.


### 2026-10-18 — Built draft walking route in the staircase scan's own frame

- D030 (user approved): the 3D scan, not the separately drawn floor-plan graph, should be enough to start directions apart from the floor selector. Built a draft floor-4 route in scan b9dca4993d's coordinate frame, the same frame the camera-recognition map reports, so a recognized pose can be routed without floor-plan registration.
- Corridors = recorded camera path from the original ZIP odometry.csv (exported through the checksum-verified archive helper), t >= 50 s and camera y >= 3.8 m (after the STAIR 1 climb), smoothed over ~1 s (61 rows) to remove sway, resampled every 0.75 m, revisits within 0.8 m joined: 155 nodes, 254 edges (100 revisit joins, all local dwell), no tracking breaks. An unsmoothed first build (171 nodes) zigzagged and overstated lengths; superseded before archiving. Untraversed corridors are absent.
- Targets = draft depth-backed sign points for 416/430/440 snapped to nearest walked node (1.21/1.45/1.26 m). They are sign viewpoints, not doorways; 430/440 entrance choice is unresolved and 420 has no target (no confident sign depth). Nothing was promoted to a verified anchor.
- Finding: this scan's odometry rotations use OpenCV camera axes (+Z forward). With ARKit -Z, the frames that photographed each sign faced ~167-173 deg away; with +Z they face the sign. The first example run used -Z and gave mirrored turns; it was corrected before archiving and a test now pins the convention on the real sign frames. Any app/server pose fed to the planner must declare its axes.
- Planner snaps a scan-frame camera position to the walked path (refuses > 3 m), finds the shortest path and the first turn. Example routes from the same recording's poses: top of STAIR 1 to 440 51.6 m; facing 430 sign to 440 9.5 m, turn left ~101 deg; facing 440 sign to 416 30.9 m. Self-consistency only, scan scale uncorrected; not localization or a walked test.
- 10 tests passed. Route data (graph, poses, examples, review image) stays private in the master; scan_route.py, builder, tests and README are public code without coordinates. No app bridge from scan pose to ARKit/arrow is implemented; guidanceEnabled stays false. Remaining: independent phone localization, doorway/entrance verification, 420, app bridge, floors 2/3.


### 2026-10-18 — PR #1 merged; first native iOS compile passed in CI

- While D030 was being archived, teammate AJSkib merged PR #1 (head 74f0539, including the automatic no-tap look) and pushed ccde3b9, which merges Hasan Wazir's codex/juno-native-fix (5ceb948: Juno narration clips, OffCourseHapticPlayer, direct haptic diagnostics, a GitHub Actions iOS workflow) with the automatic-start flow, to nav/route-guidance and mgh-localization. Our VoiceGuidance.playTurn/nav.playCue corner-clip hook was replaced by their Juno narration path; autoLocate, Look again and guidanceEnabled = false are intact.
- The workflow run on nav/route-guidance at ccde3b9 succeeded: Swift guidance-logic tests, Python voice tests, xcodebuild of the full app for the generic iOS Simulator (CODE_SIGNING_ALLOWED=NO) and a bundled-clip check. This is the first native Swift typecheck/compile evidence for our localization source. It is not a physical-iPhone run: camera capture, calibration/orientation, voice/haptics on device and positioning remain untested.
- My D030 route-code commit was rejected on first push because the remote branch had moved; merged origin/mgh-localization normally (no conflict, d1b7eee) and pushed. No force-push. That commit postdates the merged PR and is code/docs only.


### 2026-10-18 — Decision: phone capture test before route bridge

- D031 (user decision): do not connect the draft scan-frame route (D030) to the app's arrow/voice/haptics yet. Wait for the teammate's physical-iPhone capture test (private calibrated export with actual standing location and facing) first. No app bridge code was written; guidanceEnabled stays false. Next app-side work after that test: scan pose -> draft route -> ARKit/arrow bridge behind the guidance switch, with the planner's camera-axis convention declared.


### 2026-10-18 — Reviewed teammate push b538587 (capture test unaffected)

- User asked whether newly pushed work still supports the planned capture test. Only codex/juno-native-fix moved (6a8c60f, b538587 by Hasan Wazir); nav/route-guidance and mgh-localization were unchanged at ccde3b9 / 1410f46. Not merged into either.
- QuickLookModel, QuickLookCapture and Config/Info.plist are byte-identical to ccde3b9; QuickLookView only gains an optional Developer navigation test section. Automatic look, Look again, capture-only export and Share remain. GitHub Actions on b538587 passed (Swift logic tests incl. a DEBUG variant, Python tests, unsigned iOS Simulator xcodebuild). No physical iPhone result yet.
- New in that branch: NavigationAccess lets a DEBUG build start the old plan-meter graph from a manually chosen landmark (labelled MANUAL TEST · UNVERIFIED MAP); release builds stay blocked and guidanceEnabled remains false. Xcode device runs are normally Debug, so testers will see it. It is a developer route demo on unregistered external coordinates, not the D028 primary flow and not verified navigation; its graph still lacks 440. Also removed FindMyHaptics from the navigator, setAllowHapticsAndSystemSoundsDuringRecording, and Apple-voice narration. No change made by us.


### 2026-10-18 — First real-iPhone app capture; offline recognition accepted it

- D032: user supplied the first app export from a physical iPhone, 4C1B520E-95F2-4493-86A8-D565700D4061.json (sha256 52ae35a8...). Preserved byte for byte as a private diagnostic query, never a mapping reference. Floor 4, destination "440", automatic capture-only mode; app correctly stayed Not located yet.
- Capture checks: 3 frames 1.267 s apart, tracking normal, portrait 1440x1920 JPEGs with same-ARFrame intrinsics, valid rotations, proper ARKit->OpenCV axis map. Image up matches world gravity up; camera ~11 deg down. This is the first device confirmation of the portrait rotation/intrinsic/axis handling. The phone moved ~1 cm across the burst.
- Offline replay of the unchanged requests to the localhost v4 server (map e4dccbe1..., unchanged thresholds; server stopped afterward): 3/3 accepted, ~7.2 s each, supported by scan references 9433/10102/9839 (430 corridor). Position ~(25.7, 4.3, 17.6) m in scan:b9dca4993d; frame spread 0.24 m. Vision pitch equals ARKit gravity pitch (11 deg) and scan-from-ARKit is a pure yaw (tilt 0.04-0.41 deg, scale 1), independent consistency evidence. 430 sign 3.7 m ahead, 440 sign 10.3 m 37 deg left, matching the photo. App reviewer: consistent_alignment_hypothesis, 3/3 candidate frames (would show Possible location - unverified).
- Limits: no reported ground-truth standing spot/facing yet; the burst is one correlated observation (1 location, not 3 tests); recognition was replayed offline, not run by the app; earlier A/B sets remain consumed and unchanged. Draft route from this pose: 12.0 m to the 440 sign viewpoint (D030 planner, unverified). Guidance stays off. Requested from user: actual standing spot and facing. Report: capture/quicklook_20261018_4C1B520E/REPORT.md.


- D032 follow-up: the user reported for capture 4C1B520E: "I was facing directly at the door." The estimated pose faces the 430 door/sign area (430 sign point 3.7 m ahead, 1 deg off-centre), so the facing direction agrees qualitatively. No measured standing spot, door number or distance was given, so metric position accuracy remains unverified. Still one location.


### 2026-10-18 — Built draft route preview bridge (guidance still off)

- D033 (user decision after the first phone capture): build the app-side bridge from a recognized scan pose to the D030 draft route and the existing arrow, kept switched off, so the next phone test can show the computed route without guiding.
- Server: serve_phone_localizer.py gains optional --route-graph and POST /route. It plans with scan_route.py on the private draft graph and returns the path in scan x/z, always verified=false and guidance_allowed=false. It refuses another map hash/frame, floors other than 4, rooms without a draft target (420), positions >3 m off the walked path and malformed input. The private graph stays on the owner's computer; GitHub has code only.
- App (PR jfbami/Fuga#2, mgh-localization): QuickLookModel keeps the agreeing capture-time scan-from-ARKit alignment as an unverified candidate. RoutePreview converts the live ARKit camera pose to scan coordinates, requests /route, converts the path back, and drives the existing FloorPathNode line and ExitArrowView at 10 Hz. Shown under an orange DRAFT ROUTE PREVIEW / UNVERIFIED MAP / NOT GUIDANCE label; no voice, no vibration, no RouteNavigator.start; guidanceEnabled stays false. RoutePreviewMath is ARKit-free with swiftc tests added to CI.
- Checks: 5 server tests passed; existing 3 + 12 server tests still pass; 25 Swift files grammar-parse; live localhost HTTP /route returned 440 12.07 m, 416 19.58 m, refused 420 (server stopped afterward). Offline replay of capture 4C1B520E through the same chain: route starts <5 cm from the phone's own AR position, 12.1 m to the 440 sign viewpoint, arrow ~2 deg left. Same-capture consistency only, not a walked test. Swift route-math tests and native build are pending CI; no phone preview test yet.
- A first draft of the server error message had an unescaped quote (syntax error caught by the test import) and was fixed before any run. The arrow and the server's initial turn use different aim points (2 m along the path vs first node >= 2 m away), so they differ (-1.5 vs 16 deg left); both indicate a slight left turn.

- D033 follow-up: GitHub Actions run 39109317029 on PR #2 head 0cf6ec2 succeeded: "Route preview math checks passed" (new tests/route_preview), existing voice-cue checks, Python tests, unsigned iOS Simulator xcodebuild (BUILD SUCCEEDED, no warnings reported in RoutePreview*/QuickLook* files) and the bundled-clip check. This is a native compile plus math tests, not a phone test of the preview.


### 2026-10-18 — Decision: phone-test the preview before merging PR #2

- D034 (user decision): the teammate builds and tests the route preview from the mgh-localization branch on a physical iPhone, with the owner's development server running with --route-graph, before PR #2 is merged into nav/route-guidance. PR #2 stays open and unmerged until that test's export and notes come back. Guidance stays off.
