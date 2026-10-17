# Fuga

**When you can't see the way out, Fuga can.**

Fuga guides you to the nearest exit of a building you don't know, even in smoke and without a connection. Each building is scanned once with a LiDAR iPhone; after that, any iPhone can find its position from the signs around it and point the way out.

Built at DubHacks '26.

## Run it

1. Open `Fuga.xcodeproj` in **Xcode 16 or later**.
2. Select the **Fuga** target → *Signing & Capabilities* → pick your own Team (your Apple ID works).
   If Xcode says the bundle ID is taken, add your initials to `edu.uw.dubhacks.fuga` locally and don't commit that change.
3. Plug in your iPhone (iOS 17+), choose it as the run destination, and press Run.

Adding files: the `Fuga/` folder is synced with the project, so new Swift files dropped into it are picked up automatically. No need to edit the project file.

If the project won't open on your Xcode, regenerate it with [XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen && xcodegen`.

## What's here so far

| Path | What it is |
| --- | --- |
| `Fuga/Guidance/ExitArrowView.swift` | The bottom-center arrow, styled after Find My's precision-finding arrow. Takes a bearing relative to the phone and a distance. Turns green with a haptic tap when you face the exit |
| `Fuga/Guidance/DistanceLabel.swift` | "13 ft / ahead" label, feet or meters by locale, plus the spoken description |
| `Fuga/Demo/CompassDemo.swift` | Temporary driver: on a phone, tap **Exit is this way**, then turn around and the arrow keeps pointing there. In the Simulator it sweeps automatically |
| `Fuga/ContentView.swift` | Main screen: camera placeholder, floor label, arrow |

### Connecting real routing

`ExitArrowView(relativeBearing:distanceMeters:)` is the whole interface:

- `relativeBearing`: degrees from where the phone points to the next point on the route. `0` ahead, `+90` right, `-90` left, `±180` behind. Point at the next turn, not straight at the exit through walls.
- `distanceMeters`: remaining distance along the route. Under 1.5 m it shows "Exit".

Replace `CompassDemo` with the router's output once localization and A* are in.

## Web preview (for phones without Xcode)

`web-preview/index.html` is a browser copy of the arrow screen. Deploy it on Vercel so everyone can try it on their phone:

1. On vercel.com, **Add New → Project**, import `jfbami/Fuga`, and pick the `ui/exit-arrow` branch (or whichever branch has `web-preview/`).
2. Set **Root Directory** to `web-preview`, Framework Preset **Other**, no build command.
3. Deploy, then open the link on your phone and tap **Use compass** (iPhone asks for motion access). Face a direction, tap **Exit is this way**, and turn around.

Without the compass, drag left or right anywhere on the screen to turn.
