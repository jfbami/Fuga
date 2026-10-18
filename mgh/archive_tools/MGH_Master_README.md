# MGH master building archive

**Canonical project file: `MGH_Master.sqlite`.** It is a standard SQLite database, readable with Python's built-in `sqlite3` module. The original scan ZIPs, derived meshes, images, reports, visual features, and versioned annotations are embedded in this one file. Its existing data does not depend on Downloads, temporary image paths, the current browser server, or the loose output folders remaining available.

The nearby `MGH_Master_tools.py` is a convenience command-line utility. A copy of it and this guide are also embedded in the archive under `project/`, so the master remains self-contained. The database is the working archive; it is not a newly merged, verified whole-building mesh, and it is not yet a graphical annotation application.

## Current scope

- Mary Gates Hall, floor 4: iLounge scan `b43779c138`, with its original ZIP, reconstruction, floor-plan overlay, draft labels, length comparison, and localization experiments.
- Staircase scan `b9dca4993d`: original ZIP, multi-level reconstruction, source views, and reviewed signs. It records a floor-3 to floor-4 ascent in physically signed STAIR 1, then overlapping and additional floor-4 corridor coverage. Floor 3 currently has only limited stair/landing coverage, not a floor reconstruction.
- The staircase recording remains in its own coordinate frame. Visual overlap with the iLounge lobby is evident, but initial automated registration candidates failed multi-view/depth consistency. No candidate is approved for merging geometry. The architectural plan's stair ID and actual landing doorway anchors still need review.
- Earlier scan `e1a70b754b`: original data and reconstruction preserved, but building and floor remain **unassigned** until confirmed. It has not been merged into MGH geometry.
- Draft room destinations: 416 iLounge, 420 Student Services, 430 Computer Classroom. Labels and approximate sign positions come from the supplied annotated plan; doorway anchors are not verified.
- Floor-plan labels 400A, 400B, and 416A remain unverified room records. The iSchool and EXIT signs are landmark records. The clipped label at the right edge stays unresolved.
- 400W / 400J / 400M are draft area/context labels. The observed STAIR 1 connection between floors 3 and 4 is retained as a draft, with routing disabled. No enabled navigation route exists.
- A room-440 sign is visible in the staircase recording; this is a draft destination identity, not a verified entrance anchor. IT Help Desk is a sign observation without an assigned room number.
- The failed Open3D 0.20 fusion artifacts are retained only as diagnostics, not as the preferred reconstruction.
- The 78.5 ft reference and provisional 77.8 ft reconstructed span are preserved with endpoint assumptions. The 1-of-16 camera-localization result is also preserved as a research result, not a passed deployment test.
- `MGH_Project/localization/` adds an experimental DISK/LightGlue map with 129 views / 84,043 confident 3D features from the staircase recording. Its stricter two-reference withheld-image test accepted 0/20, so positioning remains unvalidated. This is not a controlled comparison to the earlier SIFT experiment. No route, voice listener, or independent-phone pass is enabled or claimed.
- **Correction:** the original DISK/LightGlue v1 map and 0/20 positioning result are invalidated diagnostics because random video seeking paired wrong RGB frames with depth/calibration/poses. The corrected sequentially decoded v2 map has 125 views / 66,773 confident features; unchanged checks accepted 1/20 same-recording queries. This is still not reliable navigation or an independent-phone pass. Exact sign-source ordinals 610 -> 648 and 2565 -> 2728 correct legacy seek-request labels; physical sign identities remain observations, not doorway anchors. Old cross-scan registration trials also need a correctly indexed rerun. See `MGH_Project/localization/evaluation_v2_framefix/FRAME_FIX_REPORT.md`.

**Latest association/evaluation update (2026-10-17):** decoded ordinal i pairs with depth/pose row i+1 for staircase and iLounge scans; v2 is superseded. v3/A 2/20 accepted (2 within internal tolerance, 0 >2 m); v3/B 2/20 accepted (2 within internal tolerance, 0 >2 m); v4/B 5/20 accepted (5 within internal tolerance, 0 >2 m). See the embedded `project/MGH_Project/localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md`. Set B is consumed; independent-phone validation and navigation remain pending.

## How future uploads are added

1. Embed the original upload unchanged, with its SHA-256 checksum and source provenance.
2. Add or update its scan record: floor, approximate area, capture context, and its own coordinate frame. Leave unknown fields unknown.
3. Embed derived reconstruction and analysis files under that scan's asset prefix.
4. Add a reviewed alignment when there is evidence relating the new scan to an existing scan or floor plan. Collect a shared doorway, landmark, or overlapping corridor in adjacent recordings to make this possible.
5. Add room, door, stair, elevator, sign, and observation records as evidence becomes available. Keep room identity separate from individual door entrances and sightings.
6. Store every annotation change in a new revision. Old records and original blobs remain available. Conflicting labels and alignments require review; they are not silently overwritten.
7. Update coverage and outstanding tasks, then run the archive integrity/checksum verification.

Record every floor connection explicitly, including which floors it joins. Do not combine scans simply because their coordinates happen to overlap; each capture starts in its own coordinate system. Store registrations first, then derive a combined view from verified transformations.

## Internal layout

- `metadata`: archive identity and format version.
- `revisions`: timestamped, transactional edit history.
- `blobs`: embedded binary files deduplicated by SHA-256.
- `assets`: logical filenames, provenance, scan association, roles, and historical versions.
- `records`: versioned JSON objects for buildings, floors, scans, frames, alignments, rooms, landmarks, observations, routes, measurements, validations, and tasks.
- `record_assets`: evidence links with foreign-key constraints.
- `current_assets` and `current_records`: current views without discarding historical versions.

The database stores original scan frames and depth losslessly inside their original ZIPs. It does not expand thousands of depth PNGs into extra files. Temporary SQLite journal files may exist during an edit; after a completed transaction and closed connection the archive is one file.

## Commands

Run with Python 3.12 or later. All commands use only the Python standard library.

```powershell
python MGH_Master_tools.py summary
python MGH_Master_tools.py verify
python MGH_Master_tools.py list-assets --scan b43779c138
python MGH_Master_tools.py get-record room MGH:4:416
python MGH_Master_tools.py export scans/b43779c138/original/iLounge.zip extracted/iLounge.zip
```

Exports refuse to overwrite an existing destination. To export an older asset, add `--revision REVISION_NUMBER`.

```powershell
python MGH_Master_tools.py import-scan NEW_SCAN.zip --floor 4 --area "Near rooms 430 and 440"
python MGH_Master_tools.py add-asset NEW_ASSET.png --path references/NEW_ASSET.png --role uploaded_reference
python MGH_Master_tools.py put-record room MGH:4:416 room_416.json --state draft --evidence annotations/floor4/building_draft.json --description "Review room 416 entrance"
```

`import-scan` supports a ZIP containing one Stray Scanner recording. It embeds the original, creates a scan/frame record, and updates the selected floor's scan list. Without `--floor`, floor assignment remains unknown. An identical reimport does not duplicate data; conflicting bytes under the same scan ID require review. Reconstruction and alignment remain pending. Other formats can be preserved with `add-asset` and reviewed separately.

An asset import alone does not establish a floor, alignment, or room label: add the corresponding structured records. Enabled navigation edges and geometry-merge alignments require verified review status. Verification checks database integrity, foreign keys, and every embedded file checksum; it does not assess whether a human room label or physical alignment is correct.

## Continuity

The organized working folder is `MGH_Project/`. Its `PROJECT_LOG.md` consolidates history, current evidence, actual decisions, and the roadmap; keep it updated during future project work and embed each version under `project/PROJECT_LOG.md`. Camera-recognition code, reference-map experiments, and independent-photo capture instructions live alongside that log. These exports do not replace the canonical database.

Use this archive as the canonical record in future MGH work. Existing loose files are preserved as working copies and exports. Synchronize any new annotation or derivative back into the master before reporting it as saved. The archive retains revision history, but it is still one physical file; a separate user-managed backup protects against loss of that file.


Independent phone update: two iPhone 14 originals (430 and 440) are preserved as queries, not map references. 430 gives an exploratory EXIF-calibrated geometric hypothesis; 440 remains unresolved. The app-facing backend and frame/calibration contract are embedded under project/MGH_Project/localization/. Existing arrow/UI work is separate; no reviewed plan-to-staircase transform or verified 440 route is enabled. New floor-2/3 data has been offered but not received.
