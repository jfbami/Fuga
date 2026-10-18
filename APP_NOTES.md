# App notes (Swift side)

A running log for the iOS app (`Fuga/`, `tests/`), separate from the Mary Gates Hall
mapping/localization work tracked in `mgh/`. Add to this instead of letting context
live only in commit messages or chat. Append new entries; don't rewrite old ones —
if something turns out wrong, add a correction dated after it.

## Where to find things

The file table in [README.md](README.md#whats-in-the-app) ("What's in the app") is
the map of what each file does. Keep that table current when files move; this doc
is for context the table can't hold (why something is the way it is, what's half-done,
what's safe to delete).

## Known cleanup (safe to delete / simplify later)

- `Fuga/Guidance/FindMyHaptics.swift` — unused since 2026-10-18. Its on-target
  snap/taps logic was ported into `AlignedHaptics` (in `OffCourseHaptics.swift`) and
  its playback into `OffCourseHapticPlayer.swift`. `RouteNavigator` stopped calling
  the original class back in commit `5ceb948` ("Use Juno for native narration and
  add direct haptic diagnostics"); nothing else references it. Delete once a teammate
  has confirmed the new path works on a phone — keeping it for now as a diff reference.

## Decisions / change log

### 2026-10-18 — Haptics: reconnect on-target vibration, fix misleading status

**What was wrong:** `OffCourseHapticPlayer` reported "sent" as soon as iOS *accepted*
a haptic request, which isn't proof the motor moved (e.g. Accessibility → Touch →
Vibration off silences everything with no error). Separately, the "facing the right
way" snap/taps vibration was built (`FindMyHaptics.swift`) but had been disconnected
from `RouteNavigator` in `5ceb948` — so the feedback-test button showed it as working
while real navigation gave nothing for that case.

**What changed:**
- Added `AlignedHaptics` (`Fuga/Guidance/OffCourseHaptics.swift`) — same style as the
  existing `OffCourseHaptics`, no UIKit, testable without a phone. Covers the snap +
  distance-scaled taps.
- Rewrote `OffCourseHapticPlayer` to report what iOS actually told us, and to keep one
  haptic engine running during guidance instead of letting it idle-shutdown between
  pulses. Added `playSystemCheck()` — a plain UIKit tap that bypasses Core Haptics, so
  a tester can tell whether Core Haptics or the phone's settings are the problem.
- Wired `AlignedHaptics` into `ContentView.runCues()` alongside the existing
  `OffCourseHaptics` nudges (their angle ranges don't overlap, so at most one fires
  per tick) and added the arrival burst on `nav.phase == .arrived`.
- Extended the "Test voice & vibration" button (`FeedbackTest.swift`) to play every
  pattern in sequence, ending with the bypass tap.
- Did not touch `RouteNavigator.swift` — everything needed (`isAligned`,
  `distanceRemaining`, `phase`) was already published.

**Still open:** no distinct feedback for "almost facing the right way" (20°–45° off
the route currently gives nothing — below the off-course nudge threshold, above the
aligned threshold). Needs a decision on what that should feel like before building it.

**Verification status:** not compiled or run — no Swift toolchain on the machine this
was written on (Windows). A teammate with a Mac needs to build in Xcode and run the
feedback-test button on a physical iPhone before this is trusted.
