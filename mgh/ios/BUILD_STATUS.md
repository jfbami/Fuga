# Phone test build status

Source is ready for the teammate's first Xcode build on branch `mgh-localization`, PR #1. Native compilation and iPhone tests have not run here.

Implemented: floor choice, spoken destination (on-device with typed fallback), live camera preview, three exact-frame ARKit image/calibration/pose captures, optional local matching, capture-time multi-frame consistency and private JSON sharing. Room-number OCR is optional. GPS fusion is not implemented. Floor-2/3 captures are supported for diagnostics, but their recognition maps are unavailable.

Passed on Windows: 18 contract/geometry tests, six Swift grammar parses, plist/configuration checks, and a real model/image HTTP request. The smoke test uses an existing estimated-calibration photo and keeps app pose/routing disabled; it is not iPhone accuracy validation.

Next: teammate builds with Xcode on a physical iPhone, records one private capture-only test near an identifiable place on floor 4, and shares its JSON with the project owner. Once camera orientation/calibration and capture metadata are verified, connect the development server for calibrated starting-location tests. Scan-to-ARKit candidate consistency still does not register the floor plan or verify doors and paths. Arrow/buzz guidance remains blocked until those steps are reviewed. Room 440's two possible entrances, stair/elevator links, and independent metric position/direction validation remain unresolved.
