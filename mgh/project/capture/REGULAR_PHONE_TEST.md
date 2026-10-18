# Independent regular-phone test capture

Purpose: test whether an ordinary phone can recognize the mapped MGH hallway. This is a separate pass, not additional frames from the reference recording. These first test photos should remain held out from reference-map construction.

1. Use the rear **1x** camera. Keep original files and metadata; avoid digital zoom, panorama, portrait effects, cropping, and screenshots.
2. Take approximately **20-30 photographs** along the mapped floor-4 lobby/corridors, facing both directions. Include the iSchool poster/lobby, the iLounge approach, the turn, and the classroom corridor. Stay only in permitted areas.
3. Include surrounding architecture as well as a sign or doorway. Hold still; avoid pointing mostly at blank floor/ceiling. Include a few plain sections to test realistic failure cases.
4. Add several clearly labeled **out-of-map** images and, if available, similar-looking locations on another floor. The app should reject or remain uncertain rather than guess a room/floor.
5. For each photo, record its original filename, phone model, lens, nearby landmark, actual floor, facing direction, and capture notes in `test_photo_manifest.csv`. A room near the photographer is not automatically the room shown ahead.
6. For metric error testing, identify an independently measured camera location, not a coordinate guessed from the reconstruction. Otherwise we can judge place/floor correspondence without claiming centimeter/meter accuracy.
7. Mark the exact **416 entrance threshold** in one clear image and on the plan if possible. Capture an approach from each direction. We will review the anchor before creating a route.

Upload the original photos together with the completed manifest. Do not add them to the visual reference library before the first independent evaluation. If we later use them to improve the map, preserve that decision and gather a new held-out test set.

The prototype's calibrated-pose command needs intrinsics for the submitted image after orientation normalization: image width/height and `fx`, `fy`, `cx`, `cy` in pixels, plus lens distortion if applicable. A future capture app can collect calibration. If calibration is unavailable, first run appearance/place matching only; do not silently use the scanning phone's calibration or present an approximate EXIF-derived calibration as exact.
