# Fuga

**Indoor directions, room to room.**

Fuga is a prototype for indoor wayfinding with a Find My–style arrow, spoken turns and vibration. The intended flow is: choose a floor, say a destination, and give the camera a quick look to find your starting location. Automatic localization and route alignment are still being tested; reliable guidance on ordinary iPhones has not been demonstrated. This is general wayfinding, not a validated emergency-navigation system.

The new **Find where I am** screen captures calibrated ARKit frames, accepts a spoken destination, and can query the development map matcher. It saves a private diagnostic to share for analysis. Walking guidance is held until map/doorway/path verification. See [the phone-test guide](mgh/ios/PHONE_TEST_GUIDE.md). Existing arrow, route rendering and haptic implementations are preserved.

Built at DubHacks '26.

## Project scope and current limitations

The app has LiDAR-built maps of Mary Gates Hall's 4th floor, routing, a camera capture test and full guidance (arrow, floor line, spoken turns, vibration). Walking guidance is switched off (`RouteNavigator.guidanceEnabled = false`) until the map alignment and doorway/path checks are reviewed. This is not a working evacuation system.

## Offline ElevenLabs voice

During guidance, tap the speaker button to turn on short direction cues: "Continue straight ahead", "Turn to your left", "Turn to your right" and "Turn around". They come from four bundled ElevenLabs clips, so they need no network or API key on the phone. If a clip is missing, Apple's device voice reads the same words and the screen says so. The cues wait while the navigator is speaking a turn instruction. Arrival is announced by the navigator with the room name and side, so the bundled "You've reached the exit" clip isn't used in the app.

Generate clips before building (Python 3, no packages required):

```sh
# Configure ELEVENLABS_API_KEY in your local environment; never commit it.
python3 scripts/generate_voice.py --dry-run
python3 scripts/generate_voice.py
```

The default voice is `3T3dPoABJjGZZAI1eif7`, selected for Fuga, with
`eleven_multilingual_v2`. Set `ELEVENLABS_VOICE_ID` or pass `--voice-id` to change it.
Generation makes five billable text-to-speech requests and writes
`Fuga/VoiceAudio/fuga_*.mp3`; the synchronized Xcode folder includes them in the app.
Keep the generated clips with the app when distributing it. The script preserves
the existing set if any API request fails. API reference:
[ElevenLabs Create speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).

Direction changes must remain stable for 0.75 seconds, announcements are at least
3 seconds apart, and stationary guidance repeats every 12 seconds. Arrival interrupts
immediately and is spoken once. Muting or leaving the foreground stops playback.
The spoken cues omit changing distances so the full vocabulary can stay offline.
The browser preview remains a visual/compass demo.

In the app, `ContentView` feeds the navigator's arrow bearing and remaining route distance to `VoiceGuidance.update(bearing:distance:)` and `OffCourseHaptics` four times a second, only while walking a route.

Logic checks (no iOS SDK required):

```sh
swiftc Fuga/Guidance/VoiceCue.swift Fuga/Guidance/OffCourseHaptics.swift tests/main.swift -o /tmp/fuga-voice-tests
/tmp/fuga-voice-tests
```

On an iPhone, verify each direction, arrival, mute, background/foreground, and airplane
mode with generated clips. Also remove a clip to confirm the device-voice fallback.

### Off-course vibration

The iPhone gives subtle, light pulses every 2 seconds when it points at least 45°
away from the next waypoint. At 100° or more, it switches to maximum-intensity
heavy pulses every 0.75 seconds. Each new level must persist for 0.75 seconds
before a pulse. Strong nudges downgrade at 80° or less, and all nudges stop at
30° or less; these separate thresholds prevent compass noise from causing chatter.
Facing the right way and arriving use the Find My–style vibration instead. Nudges work with voice
muted and stop at arrival, invalid route input, or when the screen leaves the
foreground. Actual haptic strength depends on the iPhone hardware and settings.

They measure the phone's heading against the arrow (which follows the route), alongside the Find My–style taps you feel when you face the right way. Test on a physical iPhone: start a route, turn around, wait for repeating pulses, then turn back and check they stop.

## Run it

1. Open `Fuga.xcodeproj` in **Xcode 16 or later**.
2. Select the **Fuga** target → *Signing & Capabilities* → pick your own Team (your Apple ID works).
   If Xcode says the bundle ID is taken, add your initials to `edu.uw.dubhacks.fuga` locally and don't commit that change.
3. Plug in your iPhone (iOS 17+), choose it as the run destination, and press Run.

Adding files: the `Fuga/` folder is synced with the project, so new Swift files dropped into it are picked up automatically. No need to edit the project file.

If the project won't open on your Xcode, regenerate it with [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen && xcodegen`.

## Find where I am

The app opens directly to the live camera and **Find where I am**. Select your current floor as search context; do not select a starting room or landmark. Speak a destination such as "Take me to room 440," or check your location first and choose a destination afterward.

1. Point the camera down a hallway with doors, corners or windows.
2. Tap **Find where I am**. The app captures three matching image/calibration/ARKit pose pairs.
3. With the test server configured, it checks those frames against the saved visual reference map. Without a server, it only saves a camera test and leaves the location unconfirmed.
4. Status distinguishes **Not located yet**, **Checking the camera**, **Recognition map not ready**, and **Possible location - unverified**. An exported file or visual match is not a confirmed starting location.
5. Expand **Camera test settings & export** to configure the development server or privately share the calibrated JSON. Use **Test voice & vibration** to hear/feel feedback examples; these are not real route directions.

Walking guidance remains disabled. The reconstruction supplies 3D reference features to the experimental matcher, but its camera coordinates are not yet registered to the app's route graph. Room 440 still needs reviewed entrance/path anchors and a graph destination. Floor-2/3 reconstructed meshes are not yet recognition maps. The teammate's latest removal of the 3D display is preserved.

Read [the reconstruction-to-navigation explanation](mgh/ios/RECONSTRUCTION_TO_NAVIGATION.md) and [the phone test guide](mgh/ios/PHONE_TEST_GUIDE.md). The first native build and capture test of this revised screen are still required.

## What's in the app

| Path | What it is |
| --- | --- |
| `Fuga/Guidance/ExitArrowView.swift` | Find My–style arrow: bearing relative to the phone + distance. Turns green with a haptic tap when you face the right way |
| `Fuga/Guidance/FloorPathNode.swift` | The solid green route line on the floor in the camera view |
| `Fuga/Guidance/VoiceGuidance.swift`, `VoiceCue.swift` | Optional ElevenLabs direction cues (bundled clips, device-voice fallback) |
| `Fuga/Guidance/FeedbackTest.swift` | **Test voice & vibration** button: plays every spoken cue and vibration pattern without starting navigation |
| `Fuga/Guidance/OffCourseHaptics.swift` | Off-course nudges: light pulses at 45°+ off the route, heavy at 100°+ |
| `Fuga/Guidance/FindMyHaptics.swift` | Find My–style vibration: snap when aligned, taps that speed up as you get closer, arrival burst (Core Haptics) |
| `Fuga/Guidance/DistanceLabel.swift` | "13 ft / ahead" label, feet or meters by locale |
| `Fuga/Navigation/RouteNavigator.swift` | ARKit tracking, landmark start and re-pin, hallway heading correction, spoken turns, vibration, arrival |
| `Fuga/Navigation/HallwayGraph.swift` | Hallway graph + shortest route from any spot to a room's nearest door |
| `Fuga/Navigation/RouteTracker.swift` | Route geometry: progress along the route, look-ahead target, turns (no ARKit, easy to test) |
| `Fuga/Navigation/Route.swift` | Route model |
| `Fuga/Navigation/MiniMap.swift` | Flat map |
| `Fuga/Navigation/ARCameraView.swift` | Camera view; detected walls hide the floor line behind them |
| `Fuga/Maps/` | Hallway graph with rooms, doors and landmarks |
| `Fuga/Localization/` | Floor + spoken destination + three-frame camera test (Find my location) |
| `scripts/generate_voice.py`, `tests/` | Regenerate the ElevenLabs clips; logic tests for the cues and nudges |
| `tools/mapping/` | Pipeline: floor plan PDF + LiDAR walk -> map, landmarks, routes. See its README |

## Web demo (no Xcode needed)

`web-demo/index.html` is a browser version of the guided walk, for testing without building the app:

- **Start at the elevator:** uses the phone's compass and counts your steps (no camera tracking, so it's rougher than the app). Set your step length on the start screen.
- **Simulate the walk:** walks the route on its own, with spoken turns. Works anywhere, including a laptop.
- **Replay LiDAR walk:** plays back the real elevator-to-430 scan through the same guidance.

Vibration works on Android only; on iPhone the screen edge flashes for turns instead.

Deploy on Vercel: **Add New → Project**, import `jfbami/Fuga`, pick the `nav/route-guidance` branch, set **Root Directory** to `web-demo`, Framework Preset **Other**, no build command. Open the link on your phone and allow motion access when asked. The compass only works when the page is opened from its own link over HTTPS (Vercel is fine).

## Web preview (for phones without Xcode)

`web-preview/index.html` is a browser copy of the arrow screen. Deploy it on Vercel so everyone can try it on their phone:

1. On vercel.com, **Add New → Project**, import `jfbami/Fuga`, and pick the `ui/exit-arrow` branch (or whichever branch has `web-preview/`).
2. Set **Root Directory** to `web-preview`, Framework Preset **Other**, no build command.
3. Deploy, then open the link on your phone and tap **Use compass** (iPhone asks for motion access). Face a direction, tap **Exit is this way**, and turn around.

Without the compass, drag left or right anywhere on the screen to turn.
