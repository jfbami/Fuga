# Fuga

**Indoor directions, room to room.**

Fuga guides you through a building you don't know: pick a room, and the phone points the way with a Find My–style arrow, spoken turns and vibration. It's built for blind and low-vision people, new students and visitors. Each building is scanned once with a LiDAR iPhone and lined up with UW's floor plans; after that, any iPhone can be guided.

Built at DubHacks '26.

## Run it

1. Open `Fuga.xcodeproj` in **Xcode 16 or later**.
2. Select the **Fuga** target → *Signing & Capabilities* → pick your own Team (your Apple ID works).
   If Xcode says the bundle ID is taken, add your initials to `edu.uw.dubhacks.fuga` locally and don't commit that change.
3. Plug in your iPhone (iOS 17+), choose it as the run destination, and press Run.

Adding files: the `Fuga/` folder is synced with the project, so new Swift files dropped into it are picked up automatically. No need to edit the project file.

If the project won't open on your Xcode, regenerate it with [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen && xcodegen`.

## Try it: elevator to 430 in Mary Gates Hall

1. Build to your iPhone (iOS 17+, any model with ARKit; LiDAR not needed). Allow camera access.
2. Take the elevator to the **4th floor of Mary Gates Hall**.
3. Pick **430 Computer Classroom** (or **416 iLounge**).
4. Step out of the elevator and **face straight down the hallway**, phone upright, then tap **Start**.
5. Walk. The arrow points along the route and turns green when you face the right way. Turns are spoken 4 m ahead and again at the corner, with **2 vibration pulses for left and 3 for right**. On arrival it says which side the door is on.

The small map (top right) shows the route and your blue dot. If the dot drifts off the line, walk back to the elevator and tap **I'm at the elevator** to restart.

How it stays on track: ARKit follows every step from the elevator. When you walk straight along a hallway, the app compares that with the route and corrects its heading, so being up to about 25° off when you tap Start is fine (tested by replaying the LiDAR walk with `tools/mapping/replay_navigation.py`).

## What's in the app

| Path | What it is |
| --- | --- |
| `Fuga/Guidance/ExitArrowView.swift` | Find My–style arrow: bearing relative to the phone + distance. Turns green with a haptic tap when you face the right way |
| `Fuga/Guidance/DistanceLabel.swift` | "13 ft / ahead" label, feet or meters by locale |
| `Fuga/Navigation/RouteNavigator.swift` | ARKit tracking, start calibration, hallway heading correction, spoken turns, vibration, arrival |
| `Fuga/Navigation/RouteTracker.swift` | Route geometry: progress along the route, look-ahead target, turns (no ARKit, easy to test) |
| `Fuga/Navigation/Route.swift` | Route model and the MGH 4th-floor destinations + start point |
| `Fuga/Navigation/MiniMap.swift`, `ARCameraView.swift` | Debug map and camera background |
| `Fuga/Routes/*.json` | Routes made by `tools/mapping/route.py` |
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
