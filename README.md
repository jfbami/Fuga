# Fuga

**Indoor directions, room to room.**

[View our DubHacks 2026 submission on Devpost](https://devpost.com/software/juno-s4y19m)

## Overview

Fuga combines LiDAR-based 3D reconstruction with a pretrained transformer-based matcher to estimate a phone camera’s position and orientation inside a building. Built at DubHacks 2026, it explores indoor wayfinding for students and visitors at UW

The reconstruction pipeline uses **Open3D’s volumetric TSDF fusion** to combine iPhone LiDAR scans into 3D hallway models. The localization pipeline uses **DISK**, a convolutional neural network, to extract visual features and **LightGlue**, a transformer-based matcher, to match those features against depth-backed reference views. **OpenCV’s PnP/RANSAC solver** then estimates the camera’s position and orientation.

The **SwiftUI** app uses **ARKit** to track movement, **SceneKit** to display routes, and **Dijkstra’s algorithm** to find paths through a hallway graph. Bundled **ElevenLabs** voice clips and **Core Haptics** provide spoken directions and vibration feedback.

## Highlights

- Reconstruct hallway geometry from Stray Scanner recordings containing RGB images, LiDAR depth, camera calibration, and camera poses.
- Estimate camera pose with pretrained DISK and LightGlue models running locally in PyTorch, followed by geometric verification in OpenCV.
- Explore an arrow interface, an AR floor path, spoken turns, and directional vibration.
- Test voice and vibration on an iPhone without starting navigation, or explore the interface through browser demos.

## Current status

Fuga is a hackathon research prototype. Reliable automatic guidance on ordinary iPhones has not been demonstrated.

The reconstructed scans, visual reference map, and floor-plan route graph are separate artifacts. Connecting a camera pose to a usable route still requires reviewed coordinate alignment, verified entrances and paths, and physical testing. Automatic and release-build walking guidance remain disabled. An explicit Debug-build manual test supports development on an unverified map.

The neural models use pretrained weights; the project does not train a building-specific network. Localization runs on a development computer through an optional local backend. Original scans, source floor plans, and the canonical data archive remain private, so the public repository alone does not reproduce the full mapping setup.

Read [how reconstruction connects to navigation](mgh/ios/RECONSTRUCTION_TO_NAVIGATION.md) for the technical boundaries and remaining work.

## Run the iPhone app

You need a Mac with **Xcode 16 or later** and a physical iPhone running **iOS 17 or later**.

1. Clone this repository and open `Fuga.xcodeproj`.
2. Select the **Fuga** target, open **Signing & Capabilities**, and choose your development team.
3. If the bundle identifier is unavailable, change `edu.uw.dubhacks.fuga` locally.
4. Connect your iPhone, select it as the run destination, and press **Run**.

Use **Audio & vibration check** on the start screen to test the bundled narration and haptic patterns. Physical hardware is required to assess vibration.

For camera capture, optional backend setup, and phone testing, follow the [phone-test guide](mgh/ios/PHONE_TEST_GUIDE.md). If your Xcode cannot open the committed project, regenerate it with [XcodeGen](https://github.com/yonaskolb/XcodeGen) using `brew install xcodegen && xcodegen`.

## What's in the app

| Path | Purpose |
| --- | --- |
| [Fuga/Localization/](Fuga/Localization/) | Calibrated camera capture, floor selection, spoken destination input, and experimental backend integration |
| [Fuga/Navigation/](Fuga/Navigation/) | ARKit tracking, hallway routing, route progress, camera view, and map alignment |
| [Fuga/Guidance/](Fuga/Guidance/) | Arrow and floor-path rendering, bundled voice playback, haptic feedback, and feedback tests |
| [Fuga/Maps/](Fuga/Maps/) | Draft hallway graph, room destinations, and landmarks |
| [mgh/localization/](mgh/localization/) | Python DISK/LightGlue reference-map building, camera pose estimation, and evaluation |
| [tools/mapping/](tools/mapping/) | Floor-plan processing, scan alignment, landmark placement, and routing tools |
| [scripts/generate_voice.py](scripts/generate_voice.py) | ElevenLabs voice-clip generation |
| [tests/](tests/) | Guidance, alignment, and voice-generation checks |

See [app notes](APP_NOTES.md) for implementation decisions and known cleanup, and the [mapping and localization handoff](mgh/README.md) for research results and data requirements.

## Browser demos

The browser demos let you explore the interface without Xcode:

- [Guided-walk demo](web-demo/index.html): simulate a route, replay a recorded LiDAR walk, or experiment with compass and step-based guidance.
- [Arrow preview](web-preview/index.html): try the arrow with a phone compass or drag to simulate turning.

These demos do not run the native app's camera localization. To host either on Vercel, import this repository, select the `ui/exit-arrow` branch, and set the root directory to `web-demo` or `web-preview`. Choose **Other** as the framework and leave the build command empty. Phone compass access requires HTTPS and motion permission.

## Development checks

The [iOS workflow](.github/workflows/ios-build.yml) builds the app for the simulator, runs logic checks, and checks bundled voice assets. A passing build does not verify physical navigation or haptic behavior.

To run the core guidance checks with a Swift toolchain:

```sh
swiftc Fuga/Guidance/VoiceCue.swift Fuga/Guidance/OffCourseHaptics.swift Fuga/Navigation/NavigationAccess.swift tests/main.swift -o /tmp/fuga-voice-tests
/tmp/fuga-voice-tests
```

The app includes twelve offline Juno narration clips. To regenerate them, configure `ELEVENLABS_API_KEY` in your local environment and run:

```sh
python3 scripts/generate_voice.py --dry-run
python3 scripts/generate_voice.py
```

Generation makes twelve billable requests using ElevenLabs' `eleven_multilingual_v2` model. Keep API keys out of Git.

