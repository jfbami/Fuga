# Fuga

**When you can't see the way out, Fuga can.**

Fuga guides you to the nearest exit of a building you don't know, even in smoke and without a connection. Each building is scanned once with a LiDAR iPhone; after that, any iPhone can find its position from the signs around it and point the way out.

Built at DubHacks '26.

## Project scope and current limitations

The intended pipeline is LiDAR building capture → stored walkable map → sign-based
localization → A* exit routing → visual, haptic, and spoken guidance. This branch
currently implements the guidance UI and a compass demo. Building capture, camera/AR,
sign recognition, maps, localization, and routing are not implemented here. The floor,
exit bearing, and distance are demo inputs; this is not a working evacuation system.

## Offline ElevenLabs voice

Tap **Enable voice** to hear directions. The native iOS app plays five bundled
ElevenLabs clips (ahead, left, right, behind, arrival). Clips are generated during
development, so guidance needs neither a network connection nor an API key on the
phone. Until clips are generated, or if a clip cannot play, the app uses Apple's
device speech voice and displays that fallback in the UI. Speech is currently English;
the visual distance and VoiceOver description still use locale-specific units.

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

When routing is ready, feed the next waypoint's relative bearing and remaining route
distance to `VoiceGuidance.update(bearing:distance:)` alongside `ExitArrowView`.
Only pass an arrival distance when the router has actually confirmed the exit.

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
There is no vibration for facing the exit or arriving. Nudges work with voice
muted and stop at arrival, invalid route input, or when the screen leaves the
foreground. Actual haptic strength depends on the iPhone hardware and settings.

This currently measures phone heading against the demo target, not the user's
walking trajectory or distance from a mapped route. Test on a physical iPhone:
set the exit ahead, turn around, wait for repeating pulses, then turn back and
verify they stop. Also test with voice muted, arrival distance, and backgrounding.

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
| `Fuga/Guidance/ExitArrowView.swift` | The bottom-center arrow, styled after Find My's precision-finding arrow. Takes a bearing relative to the phone and a distance. Turns green when you face the exit |
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
