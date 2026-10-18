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
