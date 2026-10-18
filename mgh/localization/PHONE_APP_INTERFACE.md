# Camera localization input for the existing app

The user's intended behavior is destination selection (for example room 440), an arrow following the corridor path, and vibration indicating progress toward the destination. Existing app UI/navigation work lives on `nav/route-guidance`; this localization work supplies image-to-map position and orientation. It does not replace that UI.

## Run the local backend

From the canonical workspace:

```powershell
work/mgh_localization_env/Scripts/python.exe outputs/MGH_Project/localization/serve_phone_localizer.py --host 127.0.0.1 --port 8765
```

Models and map load once; requests run sequentially. `/health` reports the frame and manifest hash. For a phone on a trusted development LAN, explicitly choose a reachable host and use that machine's address in the client. This is an unencrypted development service; it has not been deployed. No server is left running by the evaluation scripts.

POST `/localize` with `Content-Type: application/json`:

```json
{
  "request_id": "unique-frame-id",
  "capture_timestamp": 123.456,
  "image_base64": "BASE64_ENCODED_JPEG_OR_PNG",
  "calibration_status": "verified",
  "intrinsics": {
    "width": 1920,
    "height": 1440,
    "fx": 1400,
    "fy": 1400,
    "cx": 960,
    "cy": 720,
    "distortion": []
  }
}
```

The numbers above are schema examples, not calibration. The image and matrix must describe the exact same frame, lens, pixel dimensions, crop and orientation. For ARKit capture use the frame's `ARCamera.intrinsics` and matching camera image; Apple defines the focal lengths and principal point in pixels ([official documentation](https://developer.apple.com/documentation/arkit/arcamera/intrinsics)). If the image is rotated, cropped or resized before upload, transform its calibration consistently. Supply an undistorted pair; this solver does not model nonzero lens distortion. Omit intrinsics and use `calibration_status="missing"` for appearance matching only. `exif_estimate` is exploratory and never yields an app-usable pose.

## Response and app handoff

- `accepted` and `pose_usable_for_app` require both geometric consensus and declared verified calibration. A failed request never supplies a trusted navigation pose.
- `position_scan_m` and `rotation_world_camera`, when accepted, belong to the returned `coordinate_frame_id`, currently `scan:b9dca4993d`. Camera axes are OpenCV image axes: +X image-right, +Y image-down, +Z forward, for the normalized submitted image. Rotation is camera-to-scan, not camera-to-ARKit or camera-to-floor-plan.
- `request_id` and `capture_timestamp` are echoed unchanged. Associate the returned pose with the ARKit transform saved for that exact captured frame. A response can arrive seconds later; applying it to the current AR frame would create a new synchronization error. Use correctly transformed camera axes and the captured pair to anchor subsequent AR tracking; do not treat this server as a real-time frame tracker.
- Estimated-calibration numerical consensus is exposed only as `geometric_consensus_accepted` plus `candidate_*` fields. `accepted` remains false. This records useful diagnostics without enabling guidance.
- `registered_to_building`, `route_available` and `navigation_enabled` remain false. The existing app's plan-meter graph and separately recorded ARWorldMap are different frames. A reviewed rigid registration and verified doorway/route anchors are required before feeding a scan pose into that graph. No approximate scale correction or implicit coordinate merge is applied.

For the existing arrow/buzz layer: use the next reachable route waypoint for bearing, and remaining distance along the route for progress feedback. Reset progress feedback after rerouting or relocalization; suspend it when tracking/localization is unavailable. Room 440 is not in the inspected navigation branch's graph at commit `d7229ac`; these photos establish signed doorway context, not a reviewed 3D entrance node or path.

The backend is CPU research code. Current still-photo tests and HTTP contract tests do not establish live iPhone latency, stable multi-frame tracking, route accessibility or end-to-end guidance. No iOS build or on-device test ran on this Windows host.

## Quick-look integration update

The `mgh-localization` branch now merges the existing app work through `nav/route-guidance` commit `fbcfcc1` and adds `Fuga/Localization/`. Use the new floor/voice/quick-look test screen and `mgh/ios/PHONE_TEST_GUIDE.md`. On-device compilation and capture are still outstanding. Room-number OCR is optional and is not implemented or required by this flow.

Requests may include `building_id="MGH"` and integer `selected_floor=4`. When supplied, both fields are required and echoed. Floor-4 contextual inference conservatively excludes staircase references before 60 s of the reviewed recording; it does not change geometric acceptance thresholds. Floor 2/3 context returns `selected_floor_map_unavailable` without running the wrong-floor matcher. Legacy requests without context retain the earlier behavior. This contextual reference restriction is a new development variant, not a rerun or improvement claim on consumed query sets A/B.

Capture uses one ARFrame for image, intrinsics, timestamp and transform. Native pixels rotate clockwise 90 degrees with no crop/resize: `u' = H - 1 - v, v' = u`; portrait intrinsics are `fx'=fy, fy'=fx, cx'=H-1-cy, cy'=cx`. The portrait OpenCV camera maps into the ARKit camera by row matrix `[[0,1,0],[1,0,0],[0,0,-1]]`. Thus `scan_from_arkit_world = scan_from_image_cv @ inverse(arkit_world_from_image_cv)` using the **captured** ARFrame pose. `ARCamera.intrinsics` is device-provided calibration, not independent metric validation. Image orientation/encoding still needs on-device verification.

Three distinct frames are captured first, at least 0.5 s apart, before sequential HTTP requests. Replies must match request identity/time, image hash, map, floor and coordinate frame. At least two candidate scan-from-ARKit transforms must agree within the existing 0.75 m / 10-degree consistency tolerances. The resulting message is only a possible start for review; it does not enable routing, register a floor plan or verify doorway anchors. Adjacent burst samples are correlated, not independent validation cases. `review_quicklook.py` rechecks private exports with the explicitly selected manifest hash.

Microphone input chooses a requested destination; it does not locate the phone. Voice recognition is on-device when supported, with typed fallback. GPS is not wired into this implementation. The selected floor currently supplies the contextual restriction. No public server was deployed and no new camera capture is automatically uploaded.
