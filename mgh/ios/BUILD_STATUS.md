# Phone test build status

Source is ready for the teammate's first Xcode build on branch `mgh-localization`, PR #1. Native compilation and iPhone tests have not run here.

Implemented: floor choice, spoken destination (on-device with typed fallback), live camera preview, three exact-frame ARKit image/calibration/pose captures, optional local matching, capture-time multi-frame consistency and private JSON sharing. Room-number OCR is optional. GPS fusion is not implemented. Floor-2/3 captures are supported for diagnostics, but their recognition maps are unavailable.

2026-10-18: merged teammate `nav/route-guidance` 69698d4 (ElevenLabs corner clips, haptics allowed while recording, feedback-test summary). The camera-first start screen is kept, and the test's final summary stays visible after it ends. Corner clips now hold off the 4-per-second direction cues until they finish; that path is only active once guidance is enabled. All 20 app Swift files pass grammar parsing; no native build has run.

2026-10-18 (later): locating now starts by itself when the screen opens, with no capture button. One exact-frame capture at least 1 s apart, each checked before the next; it stops when two frames agree (max 20 frames / 90 s), or saves a 3-frame test when no server is set. Floor 2/3 reports map unavailable without capturing. Destination entry and the feedback test stay usable while it looks. A result is still only an unverified candidate and does not start guidance.

2026-10-18 (route preview): after a possible location, with a destination room and a server started with `--route-graph`, the app asks `/route` for the DRAFT scan-frame route and draws it with the existing green floor line and arrow. Labelled unverified, with no voice, no vibration, and guidance still off. The coordinate math (`RoutePreviewMath`) has swiftc tests in `tests/route_preview/`, run by CI. Five server tests passed on Windows, including an offline replay of the first iPhone capture.

Passed on Windows: 18 contract/geometry tests, six Swift grammar parses, plist/configuration checks, and a real model/image HTTP request. The smoke test uses an existing estimated-calibration photo and keeps app pose/routing disabled; it is not iPhone accuracy validation.

Next: teammate builds with Xcode on a physical iPhone, records one private capture-only test near an identifiable place on floor 4, and shares its JSON with the project owner. Once camera orientation/calibration and capture metadata are verified, connect the development server for calibrated starting-location tests. Scan-to-ARKit candidate consistency still does not register the floor plan or verify doors and paths. Arrow/buzz guidance remains blocked until those steps are reviewed. Room 440's two possible entrances, stair/elevator links, and independent metric position/direction validation remain unresolved.
