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

**First, record the map once (Mapping Mode, any iPhone; a Pro is best):**
1. Open Fuga, tap **Mapping Mode**.
2. Stand just outside the elevator, facing down the hallway, and tap **Elevator**.
3. Walk the hallways slowly in both directions (elevator lobby, 400J, 400M past both 430 doors), phone upright.
4. Stop at a few of the listed spots and tap each one when you're standing there: at least 2 far apart, e.g. the elevator and the east door of 430. More is better.
5. Tap **Save map**, then **Done**. To put the map on other phones, tap **Share map files**, AirDrop them to a Mac and add both files to `Fuga/Maps/`.

**Then navigate from anywhere in the mapped hallways:**
1. Open Fuga and look around slowly. Within a few seconds it says **Found you** and where you are.
2. Pick a room (430 Computer Classroom, 416 iLounge, 420 Student Services, or back to the elevator) and tap **Start from here**.
3. Follow the arrow. Turns are spoken 4 m ahead and at the corner (**2 vibration pulses for left, 3 for right**); on arrival it says which side the door is on. If you wander off, it plans a new route from where you are.

No map yet? **Start at the elevator** still works: step out of the elevator, face down the hallway, tap Start.

How it works: ARKit saves a 3D map of the hallways (an `ARWorldMap`). Next time, the camera recognizes the hallway and ARKit snaps back into the map's coordinates. The checkpoints you tapped while mapping tie those coordinates to the UW floor plan (2 checkpoints line up to within about 0.4 m, tested on the LiDAR scan). Routes are computed on the phone over a small hallway graph (`Fuga/Maps/mgh4_graph.json`).

## What's in the app

| Path | What it is |
| --- | --- |
| `Fuga/Guidance/ExitArrowView.swift` | Find My–style arrow: bearing relative to the phone + distance. Turns green with a haptic tap when you face the right way |
| `Fuga/Guidance/DistanceLabel.swift` | "13 ft / ahead" label, feet or meters by locale |
| `Fuga/Navigation/RouteNavigator.swift` | ARKit tracking, map recognition, Mapping Mode, elevator fallback, rerouting, spoken turns, vibration, arrival |
| `Fuga/Navigation/HallwayGraph.swift` | Hallway graph + shortest route from any spot to a room's nearest door |
| `Fuga/Navigation/WorldMapStore.swift` | Saves/loads the ARKit map and its alignment to the floor plan (checkpoint fit) |
| `Fuga/Navigation/RouteTracker.swift` | Route geometry: progress along the route, look-ahead target, turns (no ARKit, easy to test) |
| `Fuga/Navigation/Route.swift` | Route model |
| `Fuga/Navigation/MiniMap.swift`, `ARCameraView.swift` | Debug map and camera background |
| `Fuga/Maps/` | Hallway graph, plus saved maps (`mgh4.arworldmap`, `mgh4.alignment.json`) if you add them |
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
