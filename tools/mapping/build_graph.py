#!/usr/bin/env python3
"""Hallway graph for on-phone routing on MGH 4 (plan meters).

Nodes sit on corridor centerlines (measured from the LiDAR walk and the walkable grid);
door nodes carry the door/sign position so the app can say which side the door is on.
Landmarks are doors a person can stand in front of (facing the door) to tell the app where they are.

Usage: python3 build_graph.py data/mgh/04 [--check]   (--check needs grid.png from build_floor.py)
"""
import json, math, sys
from pathlib import Path

NODES = [
    # id, x, y, door (x, y) or None, landmark label or None
    ("elevator", 16.27, 36.67, (16.18, 38.37), "Elevator"),
    ("lobby",    16.27, 34.88, None, None),
    ("400J-top", 19.72, 31.88, None, None),
    ("416",      19.75, 19.76, (21.31, 19.76), "416 iLounge"),
    ("junction", 19.75, 14.50, None, None),
    ("420",      18.40, 14.50, (17.64, 13.72), "420 Student Services"),
    ("430-west", 23.54, 14.50, (23.54, 13.20), "430 Computer Classroom, west door"),
    ("430-east", 33.72, 14.50, (33.72, 13.08), "430 Computer Classroom, east door"),
]
EDGES = [("elevator", "lobby"), ("lobby", "400J-top"), ("400J-top", "416"), ("416", "junction"),
         ("junction", "420"), ("junction", "430-west"), ("430-west", "430-east")]
DESTINATIONS = [
    {"id": "430", "title": "430", "subtitle": "Computer Classroom", "doors": ["430-west", "430-east"]},
    {"id": "416", "title": "416", "subtitle": "iLounge", "doors": ["416"]},
    {"id": "420", "title": "420", "subtitle": "Student Services", "doors": ["420"]},
    {"id": "elevator", "title": "Elevator", "subtitle": "Back to the elevator", "doors": ["elevator"]},
]


def main():
    fd = Path(sys.argv[1])
    graph = {
        "building": "Mary Gates Hall", "floorLabel": "4th Floor", "frame": "plan meters (see floor.json)",
        "startNode": "elevator", "startFacingDegrees": -90,
        "nodes": [{"id": i, "x": x, "y": y, **({"doorX": d[0], "doorY": d[1]} if d else {}),
                   **({"landmark": cp} if cp else {})} for i, x, y, d, cp in NODES],
        "edges": [list(e) for e in EDGES],
        "destinations": DESTINATIONS,
    }
    (fd / "hallway_graph.json").write_text(json.dumps(graph, indent=2))
    print("wrote", fd / "hallway_graph.json")
    if "--check" in sys.argv:
        import numpy as np
        from PIL import Image
        floor = json.loads((fd / "floor.json").read_text())
        g = np.array(Image.open(fd / floor["grid"]["file"])) > 0
        c, H = floor["grid"]["cellMeters"], g.shape[0]
        pos = {n[0]: (n[1], n[2]) for n in NODES}
        for a, b in EDGES:
            (x0, y0), (x1, y1) = pos[a], pos[b]
            n = max(2, int(math.dist(pos[a], pos[b]) / 0.1))
            bad = sum(not g[int(H - 1 - (y0 + (y1 - y0) * t / n) / c), int((x0 + (x1 - x0) * t / n) / c)] for t in range(n + 1))
            print(f"{a:>9} -> {b:<9} {math.dist(pos[a], pos[b]):5.1f} m  {'OK' if bad == 0 else f'{bad} samples off the walkable area'}")


if __name__ == "__main__":
    main()
