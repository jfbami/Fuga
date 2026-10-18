#!/usr/bin/env python3
"""Fit a Stray Scanner walk onto a floor map built by build_floor.py.

Finds the rotation + translation that puts the walked path inside the plan's corridors,
starting near one room (e.g. the elevator) and ending near another. Both are metric,
so there is no scale to solve.

Outputs alignment.json: the 2D transform from ARKit world (top-down x, -z) to plan meters,
plus the aligned path.

Usage:
  python3 align_scan.py SCAN_DIR data/mgh/04 --start 4EL1 --end 430
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage, optimize


def load_path(scan_dir):
    """ARKit camera positions, top-down: (x, -z) keeps the view un-mirrored (y is up)."""
    rows = list(csv.reader(open(Path(scan_dir) / "odometry.csv")))[1:]
    t = np.array([float(r[0]) for r in rows])
    xyz = np.array([[float(r[2]), float(r[3]), float(r[4])] for r in rows])
    return t - t[0], np.stack([xyz[:, 0], -xyz[:, 2]], axis=1), xyz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("floor_dir")
    ap.add_argument("--start", required=True, help="room id the walk starts next to")
    ap.add_argument("--end", required=True, help="room id the walk ends next to")
    ap.add_argument("--start-radius", type=float, default=6.0)
    ap.add_argument("--end-radius", type=float, default=9.0)
    args = ap.parse_args()

    floor_dir = Path(args.floor_dir)
    floor = json.loads((floor_dir / "floor.json").read_text())
    cell = floor["grid"]["cellMeters"]
    walk = np.array(Image.open(floor_dir / floor["grid"]["file"])) > 0
    H, W = walk.shape
    # Distance (m) to the nearest blocked cell: rewards a path that stays in the middle of corridors.
    inside_dist = ndimage.distance_transform_edt(walk) * cell
    field = np.minimum(inside_dist, 1.0)

    rooms = {r["id"]: np.array([r["x"], r["y"]]) for r in floor["rooms"]}
    start_room, end_room = rooms[args.start], rooms[args.end]

    t, p2, _ = load_path(args.scan)
    sub = p2[:: max(1, len(p2) // 400)]

    def score(points):
        j = np.clip((points[:, 0] / cell).astype(int), 0, W - 1)
        i = np.clip((H - 1 - points[:, 1] / cell).astype(int), 0, H - 1)
        return field[i, j].mean()

    def transform(points, theta, tx, ty):
        c, s = math.cos(theta), math.sin(theta)
        return points @ np.array([[c, s], [-s, c]]) + np.array([tx, ty])

    # Coarse search: rotate about the first point, place it on a grid around the start room.
    rel = sub - sub[0]
    end_rel = p2[-1] - p2[0]
    best = (-1, None)
    offsets = np.arange(-args.start_radius, args.start_radius + 1e-9, 0.3)
    for deg in range(360):
        th = math.radians(deg)
        r = transform(rel, th, 0, 0)
        e = transform(end_rel[None], th, 0, 0)[0]
        for dx in offsets:
            for dy in offsets:
                s0 = start_room + np.array([dx, dy])
                if np.hypot(dx, dy) > args.start_radius:
                    continue
                if np.linalg.norm(s0 + e - end_room) > args.end_radius:
                    continue
                sc = score(r + s0)
                if sc > best[0]:
                    best = (sc, (th, s0[0], s0[1]))
    if best[1] is None:
        raise SystemExit("No placement found; widen --start-radius/--end-radius")

    # Refine on a smoothed field.
    smooth = ndimage.gaussian_filter(field, 2)

    def neg(params):
        pts = transform(rel, *params)
        j = pts[:, 0] / cell
        i = H - 1 - pts[:, 1] / cell
        return -ndimage.map_coordinates(smooth, [i, j], order=1).mean()

    res = optimize.minimize(neg, x0=np.array(best[1]), method="Nelder-Mead",
                            options={"xatol": 1e-3, "fatol": 1e-5})
    theta, tx, ty = res.x
    aligned = transform(p2 - p2[0], theta, tx, ty)
    fit = score(transform(rel, theta, tx, ty))
    inside = walk[np.clip((H - 1 - aligned[:, 1] / cell).astype(int), 0, H - 1),
                  np.clip((aligned[:, 0] / cell).astype(int), 0, W - 1)].mean()

    out = {
        "scan": Path(args.scan).name,
        "from": "ARKit world, top-down (x, -z), meters",
        "to": "plan meters (see floor.json frame)",
        # plan = R(theta) applied to (p - origin) + translation
        "originArkitTopDown": [round(float(v), 4) for v in p2[0]],
        "thetaRadians": round(float(theta), 6),
        "thetaDegrees": round(math.degrees(theta) % 360, 2),
        "translation": [round(float(tx), 4), round(float(ty), 4)],
        "fitScore": round(float(fit), 3),
        "fractionInsideWalkable": round(float(inside), 3),
        "path": [{"t": round(float(tt), 2), "x": round(float(x), 2), "y": round(float(y), 2)}
                 for tt, (x, y) in list(zip(t, aligned))[::30]],
    }
    (floor_dir / "alignment.json").write_text(json.dumps(out, indent=1))
    print(f"theta {out['thetaDegrees']} deg, start at ({tx:.2f}, {ty:.2f}), "
          f"fit {fit:.3f}, {inside:.1%} of path inside walkable space")


if __name__ == "__main__":
    main()
