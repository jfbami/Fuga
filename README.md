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

## Try it in Mary Gates Hall, 4th floor

The floor's map ships inside the app, so anyone can open Fuga and go. No setup, no scanning.

1. Open Fuga. Under **Where are you?**, pick the room or landmark you're closest to: the Elevator, 416 iLounge, 420 Student Services, or either door of 430 Computer Classroom.
2. Stand in front of that door, facing it, phone upright. That tells Fuga exactly where you are and which way you're facing.
3. Under **Where to?**, pick a room and tap **Start**. It tells you which way to turn first (usually "Turn around").
4. Follow the arrow. It points along the route drawn on the map: down the hallway you're in, swinging to the next hallway just before each corner. The number under it is how far you still have to walk to the room.
5. Look through the camera: a **green line on the hallway floor** runs from your feet to the room, with chevrons pointing the way and pulses travelling along it, like a GPS route drawn in the real world. It fades out about 15 m ahead so it doesn't show through walls past the next corner.
6. Vibration works like Find My: when you turn to face the way the arrow points, it turns green with a firm **snap**, then **taps** while you keep facing that way, faster and stronger as you get closer. Face the wrong way and it goes quiet. At a corner the arrow swings, the taps stop, and they come back when you've turned. Turns are also spoken 4 m ahead and at the corner, and on arrival a short burst plays, it says which side the door is on, and the arrow points at the door.
7. Passing a room on the list? Tap **I'm at a landmark** and pick it to fix any drift. It re-plans the route from there.

How it works: the landmark you pick pins your spot and direction on the UW floor plan. ARKit then follows every step with the camera and motion sensors. Walking straight down a hallway corrects the direction if you weren't facing the door squarely (tested: recovers a 28° error). Routes are computed on the phone over a small hallway graph (`Fuga/Maps/mgh4_graph.json`).

## What's in the app

| Path | What it is |
| --- | --- |
| `Fuga/Guidance/ExitArrowView.swift` | Find My–style arrow: bearing relative to the phone + distance. Turns green with a haptic tap when you face the right way |
| `Fuga/Guidance/FloorPathNode.swift` | The pulsing green AR path on the floor (SceneKit ribbon + shader) |
| `Fuga/Guidance/FindMyHaptics.swift` | Find My–style vibration: snap when aligned, taps that speed up as you get closer, arrival burst (Core Haptics) |
| `Fuga/Guidance/DistanceLabel.swift` | "13 ft / ahead" label, feet or meters by locale |
| `Fuga/Navigation/RouteNavigator.swift` | ARKit tracking, landmark start and re-pin, hallway heading correction, spoken turns, vibration, arrival |
| `Fuga/Navigation/HallwayGraph.swift` | Hallway graph + shortest route from any spot to a room's nearest door |
| `Fuga/Navigation/RouteTracker.swift` | Route geometry: progress along the route, look-ahead target, turns (no ARKit, easy to test) |
| `Fuga/Navigation/Route.swift` | Route model |
| `Fuga/Navigation/MiniMap.swift`, `ARCameraView.swift` | Debug map and camera background |
| `Fuga/Maps/` | Hallway graph with rooms, doors and landmarks |
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
