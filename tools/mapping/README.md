# Mapping pipeline

Turns a UW Space Viewer floor plan plus one LiDAR walk (Stray Scanner) into what the app needs:
a walkable map, landmarks placed on it, and routes with turn-by-turn steps.

```
pip install -r tools/mapping/requirements.txt

# 1. Floor map from the Space Viewer PDF -> floor.json + grid.png (kept out of git; plans are NetID-only)
python3 tools/mapping/build_floor.py MGH1197_04.pdf --out data/mgh/04 --building MGH --floor 4

# 2. Fit the walk onto the map (start and end rooms are just hints for the search)
python3 tools/mapping/align_scan.py SCAN_DIR data/mgh/04 --start 4EL1 --end 430

# 3. Place signs using LiDAR depth + camera pose (detections: frame, label, kind, name, box)
python3 tools/mapping/place_landmarks.py SCAN_DIR data/mgh/04 data/mgh/04/detections_iLounge-walk.json

# 4. Route with spoken steps
python3 tools/mapping/route.py data/mgh/04 --from 400W --to 430 --out data/mgh/04/route_elevator_430.json

# Check by eye: plan + walk + landmarks + routes
python3 tools/mapping/overlay.py MGH1197_04.pdf data/mgh/04 check.png --crop
```

`SCAN_DIR` is an unzipped Stray Scanner recording (`rgb.mp4`, `odometry.csv`, `depth/`, `confidence/`).

## Coordinates

Everything in `data/` is in **plan meters**: origin at the bottom-left of the plan drawing, x to the right, y up the page. The page is not north-up; the arrow on the PDF shows north.

## Notes from the MGH 4th-floor walk (elevator to 430, 106 s, 56 m)

- Stray Scanner poses use the OpenCV camera frame (x right, y down, looking along +z). With that, the two sightings of the 416 sign agree to 6 cm.
- Signs found: 416 iLounge, 420 Student Services, 430 Computer Classroom (one sign at each door), the iSchool wall sign by the elevator, and one EXIT sign at the 400J/400M corner. A second EXIT sign was left out because its hand-drawn box placed it inside room 430; re-check it on the next walk.
- Text recognition only reads signs the camera faced squarely. On the next walk, pause about a second at each door with the camera on its number.
