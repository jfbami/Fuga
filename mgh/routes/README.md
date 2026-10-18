# Draft scan-frame walking route (floor 4, scan b9dca4993d)

**Status: draft, unverified. Routing stays disabled in the app.**

This is the first walking route that lives in the **same 3D coordinate frame as the camera-recognition map**. A recognized camera pose from the localizer (scan frame) can be routed directly, without registering the floor plan or the app's separate plan-meter graph.

## What it is

- **Corridors**: where the scanning phone actually walked on floor 4. The camera positions come from the original ZIP's `odometry.csv`, taken from 50 s onward with camera height ≥ 3.8 m, after the STAIR 1 climb. Positions are smoothed over about 1 s to remove hand sway, then resampled every 0.75 m. Spots the walk passed again within 0.8 m are joined. The result has 155 nodes and 254 edges, with no tracking breaks. Corridors the scan didn't walk are absent.
- **Destinations**: the draft depth-backed **sign points** for 416, 430 and 440, each snapped to the nearest walked node (1.2–1.5 m away). These are sign viewpoints, **not doorways**. 430 and 440 each have two plan entrances, and nothing here picks one. 420 has no target because its sign lacks confident depth.
- **Planner** (`scan_route.plan`): takes a scan-frame camera position and facing direction. It snaps to the walked path (refusing if more than 3 m away), finds the shortest path to the target, and reports the length and the first turn (+ = left).

## Camera axis convention (checked)

The scan's odometry rotations use OpenCV camera axes: the camera looks along **+Z**. With ARKit's −Z, the frames that photographed each sign faced about 170° away from it. With +Z they face the sign. `test_sign_frames_face_their_signs` pins this. Any pose fed in from the app or server must state its axes (`forward_xz(q, 'opencv' | 'arkit')`).

## Example routes (same-recording poses; self-consistency only)

| Start (recorded scan pose) | To 416 | To 430 | To 440 |
|---|---|---|---|
| Top of STAIR 1 (t = 55 s) | 21.6 m | 43.1 m | 51.6 m |
| Facing the 430 sign | 20.9 m, turn right ~99° | — | 9.5 m, turn left ~101° |
| Facing the 440 sign | 30.9 m, turn right ~62° | 9.5 m, turn right ~62° | — |

These lengths use the scan's own (unverified) scale and the walked, not straightened, path.

## Not done / not claimed

- No independent localization: starts come from the scan's own poses, not a new phone.
- Doorway thresholds, the 430/440 entrance choice, and 420 are unresolved. No floor-plan registration, no link to the app's route graph or to other scans.
- The app has no bridge from scan pose to ARKit/arrow yet; `RouteNavigator.guidanceEnabled` stays false.
- Route data (`scan_b9dca4993d_floor4_draft/`) is private scan geometry. Only the code is public.

## Files

- `scan_route.py`: graph building and the planner.
- `build_scan_route_b9dca4993d.py`: builds from the master (checksum-verified ZIP plus sign records).
- `test_scan_route.py`: 10 tests (synthetic conventions plus checks on the draft graph).
- `example_routes_b9dca4993d.py`: produces the example table above.
- `scan_b9dca4993d_floor4_draft/`: `route_graph.json`, `sign_view_poses.json`, `example_routes.json`, `route_review.png` (all private).
