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

1. The app now opens directly to **Find where I am** and starts looking by itself; there is no capture button and no starting-room selection. It takes one same-frame camera capture at least 1 second apart while tracking is normal. Without a server it saves a 3-frame test; with a server it checks each frame before taking the next and stops when two agree (up to 20 frames / 90 s). Changing floor, returning to the app or tapping **Look again** restarts it.
2. Select **Floor 4**. Tap **Say your destination**, say “Take me to room 440,” then stop listening if needed. Check that **Requested destination: room 440** appears. This is a request, not verification that a route to 440 exists.
3. Leave the server address blank for this first capture test.
4. Because looking starts on its own, the capture taken right at app launch is wherever you happened to be. Walk to one identifiable place near 430 or 440, hold the phone upright toward doors/corners/windows, and tap **Look again**. Hold it there for about 3 seconds while it saves the test. You do not scan the floor or need to point at a room number.
5. Expand **Camera test settings & export**, then tap **Share camera test**. Send the exported JSON privately to the project owner and note the actual floor, where you stood, and which way you faced. It includes the submitted JPEGs, same-frame calibration, timestamps, tracking state and ARKit transforms. Do not commit it to GitHub. Captures are diagnostic queries, never mapping references.

A destination is optional for finding the starting location. The expected capture-only outcome is **Camera test saved**, with **Not located yet** status; it does not claim that the phone has found its location. Normal Camera-app MOV files cannot substitute for this calibrated frame/pose export.

## Then connect the map matcher

On the Windows computer with the canonical project and existing Python environment, from that workspace:

```powershell
work/mgh_localization_env/Scripts/python.exe outputs/MGH_Project/localization/serve_phone_localizer.py --map outputs/MGH_Project/localization/visual_map_v4_low_rotation --route-graph outputs/MGH_Project/routes/scan_b9dca4993d_floor4_draft/route_graph.json --host 0.0.0.0 --port 8765
```

The server is not left running by our tests. Start it only for the development session, use a trusted LAN, and stop it with Ctrl+C afterward. The iPhone must reach that computer on the same network. Windows Firewall may need a private-network exception for this process/port; no firewall settings were changed here.

Expand **Camera test settings & export** and enter `http://COMPUTER.local:8765` or `http://PRIVATE-LAN-IP:8765` in the app. Replace the example with the computer's real address; `localhost` on the phone means the phone itself. `/health` should report ready. Then tap **Look again** (editing the address does not restart looking by itself). The configuration allows local networking and insecure HTTP only for the private LAN ranges used by this development server; public hosts should use HTTPS. No public backend is deployed. See [Apple ATS local networking](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking).

Repeat one short quick-look test. The CPU backend checks the three saved frames sequentially, so this is not a demonstrated instant or real-time service. A possible starting-location message needs at least two agreeing calibrated scan-to-ARKit transforms from distinct frames. Different phone positions are compared using their capture-time transforms, not by assuming the phone stood still. This remains a hypothesis for review, not independently validated location accuracy.

Floors 2/3 can export capture tests, but their recognition maps are not built/approved. Contextual backend requests for those floors return `selected_floor_map_unavailable`; they do not silently search floor 4. GPS is not fused by this implementation. The selected floor supplies context; GPS remains a planned building-context aid, never a substitute for indoor coordinates.

### Easiest: Tailscale (laptop can stay at home)

The phone reaches the laptop over Tailscale from anywhere, including cellular, so nobody carries the laptop to the building and nothing is exposed to the public internet.

1. Laptop: keep it on, with Tailscale connected. Start the server bound to its Tailscale address only (`tailscale ip -4` prints it, e.g. `100.x.y.z`), replacing `--host 0.0.0.0` above with `--host 100.x.y.z`. If Windows asks, allow Python on private networks.
2. iPhone: install the Tailscale app and connect. Either sign in to the same account as the laptop, or have the laptop owner **share just the laptop** with the tester's own Tailscale account (admin console → Machines → laptop → Share). Do not add testers to a shared lab network.
3. In the app's server field enter `http://LAPTOP.TAILNET.ts.net:8765` (the laptop's Tailscale name, shown in the Tailscale app), then tap **Look again**. The app allows plain HTTP only for `*.ts.net` and private LAN ranges; Tailscale encrypts the connection itself.
4. Stop the server after the test. While it runs, any device allowed by the tailnet's access rules can reach it.

## Second test: location plus draft route preview

With the server running (including `--route-graph`, which is private data on the owner's computer), say or type **440** (or 416/430), then point the phone down the floor-4 hallway near 430/440. Each frame takes about 7 s on the server. Once two frames agree, the status shows **Possible location — unverified**, and an orange **DRAFT ROUTE PREVIEW · UNVERIFIED MAP · NOT GUIDANCE** panel appears with the existing arrow and distance. The green line is drawn on the floor in the small camera view.

- The preview never speaks or vibrates and does not start walking guidance (`RouteNavigator.guidanceEnabled` stays false).
- The route follows where the original scan walked. It ends at the room sign's viewpoint, not a verified doorway. 420 has no target.
- Walk a few metres and note whether the line stays on the corridor floor and the arrow points along it. If you move more than 3 m off the line, it says so; tap **Look again**.
- Share the export as before, and note the actual spot, facing, and whether the line and arrow looked right.

On 2026-10-18 the first capture (4C1B520E) was replayed through this exact chain offline: the route started within 5 cm of the phone's own position, was 12.1 m to the 440 sign viewpoint, and the arrow pointed about 2° left. That is a same-capture consistency check, not a walked test.

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

The existing arrow, path rendering, spoken-turn, feedback test and haptic code is retained. Manual starting-room/landmark pickers have been removed from the app UI. The actual scan reconstruction and the old floor-plan display are distinct; see RECONSTRUCTION_TO_NAVIGATION.md. Both manual and automatic starts remain blocked until the canonical route/doorway work is verified. The public team's graph/alignment files are unreviewed relative to the canonical scan; merging app source does not approve or merge those coordinates. This is general wayfinding, not a validated emergency-navigation system.
