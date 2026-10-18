# First iPhone test: floor → voice destination → quick camera look

This build contains the first capture/localization integration. **It has not been compiled with Xcode or run on an iPhone here.** Backend/geometry checks and Swift syntax checks pass on Windows; those do not replace a native build. Walking guidance remains off. No room-number reading is required for localization.

## Teammate: install from the Mac

For a fresh checkout, run:

```sh
git clone --branch mgh-localization https://github.com/jfbami/Fuga.git Fuga-phone-test
cd Fuga-phone-test
open Fuga.xcodeproj
```

For an existing checkout, save local work first, fetch origin, switch to `mgh-localization`, and pull with `--ff-only`. Do not use the older `nav/route-guidance` branch for this test; its latest app work is merged into this branch with the new capture flow.

1. Use Xcode 16 or later and a physical iPhone running iOS 17 or later. The simulator cannot validate ARKit camera tracking.
2. Select the **Fuga** target → **Signing & Capabilities** → choose a development Team. Keep personal signing/bundle-ID changes local.
3. Connect the unlocked iPhone to the Mac, trust the Mac, and enable Developer Mode if prompted. Choose that iPhone as the run destination.
4. Build and Run. If compilation fails, retain the full Xcode error text; the first native build is still outstanding. Do not remove the guidance guard to make the demo run.
5. Allow camera access. Microphone and Speech permissions are requested when **Say your destination** is tapped. Voice input uses on-device recognition; if unavailable, type the requested room for the capture test.

Apple reference: [Run on a physical device](https://developer.apple.com/documentation/xcode/running-your-app-on-simulated-or-physical-devices).

## First test: no backend needed

1. Open **Find my location · say a destination**.
2. Select **Floor 4**. Tap **Say your destination**, say “Take me to room 440,” then stop listening if needed. Check that **Requested destination: room 440** appears. This is a request, not verification that a route to 440 exists.
3. Leave the server address blank for this first capture test.
4. At one identifiable place near 430 or 440, hold the phone upright, show doors/corners/windows, and tap **Find my starting location**. Keep it fairly steady for the short three-frame capture. You do not scan the floor or need to point at a room number.
5. Tap **Share camera test**. Send the exported JSON privately to the project owner and note the actual floor, where you stood, and which way you faced. It includes the three submitted JPEGs, same-frame calibration, timestamps, tracking state and ARKit transforms. Do not commit it to GitHub. Captures are diagnostic queries, never mapping references.

The expected capture-only outcome is **Camera test saved**, not a claim that the phone has found its location. Normal Camera-app MOV files cannot substitute for this calibrated frame/pose export.

## Then connect the map matcher

On the Windows computer with the canonical project and existing Python environment, from that workspace:

```powershell
work/mgh_localization_env/Scripts/python.exe outputs/MGH_Project/localization/serve_phone_localizer.py --map outputs/MGH_Project/localization/visual_map_v4_low_rotation --host 0.0.0.0 --port 8765
```

The server is not left running by our tests. Start it only for the development session, use a trusted LAN, and stop it with Ctrl+C afterward. The iPhone must reach that computer on the same network. Windows Firewall may need a private-network exception for this process/port; no firewall settings were changed here.

Enter `http://COMPUTER.local:8765` or `http://PRIVATE-LAN-IP:8765` in the app. Replace the example with the computer's real address; `localhost` on the phone means the phone itself. `/health` should report ready. The configuration allows local networking and insecure HTTP only for the private LAN ranges used by this development server; public hosts should use HTTPS. No public backend is deployed. See [Apple ATS local networking](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking).

Repeat one short quick-look test. The CPU backend checks the three saved frames sequentially, so this is not a demonstrated instant or real-time service. A possible starting-location message needs at least two agreeing calibrated scan-to-ARKit transforms from distinct frames. Different phone positions are compared using their capture-time transforms, not by assuming the phone stood still. This remains a hypothesis for review, not independently validated location accuracy.

Floors 2/3 can export capture tests, but their recognition maps are not built/approved. Contextual backend requests for those floors return `selected_floor_map_unavailable`; they do not silently search floor 4. GPS is not fused by this implementation. The selected floor supplies context; GPS remains a planned building-context aid, never a substitute for indoor coordinates.

## Reviewing a private export

Preserve the original JSON. From the canonical workspace:

```powershell
work/mgh_localization_env/Scripts/python.exe outputs/MGH_Project/localization/review_quicklook.py PRIVATE_CAPTURE.json --map outputs/MGH_Project/localization/visual_map_v4_low_rotation --output work/quicklook_review_new.json
```

For a capture-only file, run its saved requests through the backend and retain the responses before geometric review. The reviewer checks image hashes, map identity, capture timestamps, calibration and rigid transforms. It rejects missing/estimated calibration and never enables guidance. Archive any received original/analysis through the sole canonical master with provenance; do not copy the master to this Git repository.

## What is still missing before arrow/buzz navigation

- The teammate's Xcode build and real iPhone capture test.
- Reliable calibrated starting-location recognition on independent observations.
- Reviewed registration between the scan and the app's plan coordinates.
- Verified 440 entrance(s), walking path and applicable stair/elevator links.
- Native tracking/interruption/latency tests and independent location/direction checks.

The existing arrow, path rendering, spoken-turn and haptic code is retained. Both manual and automatic starts remain blocked until the canonical route/doorway work is verified. The public team's graph/alignment files are unreviewed relative to the canonical scan; merging app source does not approve or merge those coordinates. This is general wayfinding, not a validated emergency-navigation system.
