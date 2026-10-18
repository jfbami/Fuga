# Geometry audit of the 430/440 video

The active recognition stack is DISK feature extraction + LightGlue matching, followed by our depth-backed 3D/PnP/multiple-reference checks when query calibration exists. It is not a complete integration of Keryx or hloc. ARKit handles iPhone capture/motion tracking; its native build remains pending with the teammate.

## Fixed experiment

Before matching, declared all seven previously exposed video samples and exactly their previously tested reference pools. No new room-labelled references, OCR, GPS, query calibration/depth/poses or threshold changes to the core localizer were used. The new diagnostic fits an uncalibrated fundamental matrix (USAC_MAGSAC, 1.5 px, 99.9%, 10,000 iterations), also checks a homography (3 px), and compares fixed rankings by inlier count and inlier count times square root of minimum image hull coverage. Detailed parameters are in PLAN.json. These are development diagnostics on consumed images, not a fresh held-out evaluation.

## Observed result

At video ordinal 0 the visible sign reads **430**. Raw match count ranked a reference showing **440** first: row 10883, 125 matches. The reference showing 430 (row 9433) had 118 matches and was third.

After 2D verification, the 430 reference has **106** fundamental inliers; the misleading 440 reference retains **69**. Both declared rankings now put row 9433 first. Coverage-weighted scores are 29.58 versus 12.73. This corrects one concrete appearance-ranking error without reading room numbers. It does not establish the camera's position, facing direction or a reliable room-identification rate.

Across seven correlated samples, the fundamental-count top choice changes on 1; the coverage-weighted top changes on 2. Other frames lack independently known camera positions, and a reference seeing the same corridor can legitimately overlap a query near a different sign; do not score a room-accuracy percentage from these images. The 440 segment still has no calibrated geometric fix. Importantly, the wrong-room 440 reference retains dozens of geometrically consistent 2D matches. Fundamental-matrix verification alone cannot be trusted to identify a room or supply an app pose, especially with repeated/planar signs and corridors.

## Validation and decision

Four synthetic contract/geometry tests passed: nonplanar projections with outliers, repeated planar patterns retaining ambiguity, too-few correspondences, and invalid inputs. Replayed all 85 cached match pairs with the final helper source and confirmed identical masks/scores after adding input-dimension validation. No feature model or geometric acceptance setting was retuned. No query became a mapping reference.

Keep this as an optional audit module, **not the default app/backend ranking**. Calibrated iPhone capture and a new held-out test remain necessary before adopting changes. The teammate's merge/Xcode path is unchanged. No iOS app files were changed in this audit. No routing, scan registration, doorway/stair/elevator anchor or independent-phone accuracy status changed.

Primary method references: [LightGlue](https://github.com/cvg/LightGlue), [OpenCV fundamental-matrix estimation](https://docs.opencv.org/5.0/main_modules/d_projection.html), [OpenCV USAC estimators](https://opencv.org/blog/evaluating-opencvs-new-ransacs/).
