#!/usr/bin/env python3
"""Shortest walkable route between two places on a floor map, with turn-by-turn steps.

Places are room ids from floor.json ("4EL1", "430") or landmark ids ("lm-430-1").
A room's sign is used as the destination when one was found in the scan, so the
route ends at the door instead of the middle of the room.

Usage:
  python3 route.py data/mgh/04 --from 400W --to 430 --out data/mgh/04/route_elevator_430.json
"""
import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def astar(walk, cost, start, goal):
    H, W = walk.shape
    moves = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1),
             (-1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (1, 1, math.sqrt(2))]
    g = {start: 0.0}
    came = {}
    pq = [(0.0, start)]
    while pq:
        _, cur = heapq.heappop(pq)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        for di, dj, step in moves:
            n = (cur[0] + di, cur[1] + dj)
            if not (0 <= n[0] < H and 0 <= n[1] < W) or not walk[n]:
                continue
            ng = g[cur] + step * cost[n]
            if ng < g.get(n, float("inf")):
                g[n] = ng
                came[n] = cur
                h = math.hypot(goal[0] - n[0], goal[1] - n[1])
                heapq.heappush(pq, (ng + h, n))
    return None


def simplify(points, tol):
    """Ramer-Douglas-Peucker."""
    if len(points) < 3:
        return points
    a, b = np.array(points[0]), np.array(points[-1])
    ab = b - a
    norm = np.linalg.norm(ab) or 1e-9
    dists = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / norm for p in points[1:-1]]
    k = int(np.argmax(dists)) + 1
    if dists[k - 1] > tol:
        return simplify(points[: k + 1], tol)[:-1] + simplify(points[k:], tol)
    return [points[0], points[-1]]


def arrival_side(points, target):
    """Is the destination on the left or right of the last stretch of the walk?"""
    # Judge against the last real stretch of corridor, not a short final step toward the sign.
    k = len(points) - 1
    while k > 1 and math.dist(points[k - 1], points[k]) < 3.0:
        k -= 1
    (x0, y0), (x1, y1) = points[k - 1], points[k]
    cross = (x1 - x0) * (target[1] - y0) - (y1 - y0) * (target[0] - x0)
    if abs(cross) < 0.3 * math.hypot(x1 - x0, y1 - y0):
        return "ahead"
    return "left" if cross > 0 else "right"


def steps_for(points, room_name):
    """Turn-by-turn instructions. Turns under 30 degrees are folded into the walk."""
    segs = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        segs.append({"length": math.hypot(x1 - x0, y1 - y0), "heading": math.degrees(math.atan2(y1 - y0, x1 - x0))})
    steps, walk = [], 0.0
    for i, s in enumerate(segs):
        walk += s["length"]
        if i + 1 < len(segs):
            turn = (segs[i + 1]["heading"] - s["heading"] + 540) % 360 - 180
            if abs(turn) >= 30:
                steps.append({"action": "walk", "meters": round(walk, 1)})
                side = "left" if turn > 0 else "right"
                steps.append({"action": "turn", "direction": side, "degrees": round(abs(turn))})
                walk = 0.0
    steps.append({"action": "walk", "meters": round(walk, 1)})
    steps.append({"action": "arrive", "name": room_name})
    return steps


def spoken(step):
    if step["action"] == "walk":
        return f"Walk {round(step['meters'])} meters"
    if step["action"] == "turn":
        sharp = "slightly " if step["degrees"] < 60 else ""
        return f"Turn {sharp}{step['direction']}"
    where = "ahead" if step.get("side") == "ahead" else f"on your {step.get('side')}"
    return f"{step['name']} is {where}" if step.get("side") else f"You've arrived at {step['name']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("floor_dir")
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    fd = Path(args.floor_dir)
    floor = json.loads((fd / "floor.json").read_text())
    cell = floor["grid"]["cellMeters"]
    walk = np.array(Image.open(fd / floor["grid"]["file"])) > 0
    H = walk.shape[0]
    lms = json.loads((fd / "landmarks.json").read_text())["landmarks"] if (fd / "landmarks.json").exists() else []
    rooms = {r["id"]: r for r in floor["rooms"]}
    names = {l["label"]: l["name"] for l in lms if l.get("name")}

    def place(pid):
        lm = [l for l in lms if l["id"] == pid]
        if lm:
            return (lm[0]["x"], lm[0]["y"]), lm[0].get("name") or lm[0]["label"]
        signs = [l for l in lms if l["label"] == pid and l["kind"] == "room_number"]
        if signs:
            return (signs[0]["x"], signs[0]["y"]), f"{pid} {signs[0].get('name') or ''}".strip()
        r = rooms[pid]
        return (r["x"], r["y"]), pid

    def to_cell(x, y):
        i, j = int(round(H - 1 - y / cell)), int(round(x / cell))
        if walk[i, j]:
            return (i, j)
        # Snap to the nearest walkable cell (signs sit on walls).
        d, (ii, jj) = ndimage.distance_transform_edt(~walk, return_indices=True)
        return (int(ii[i, j]), int(jj[i, j]))

    (sx, sy), src_name = place(args.src)
    (tx, ty), dst_name = place(args.dst)
    start, goal = to_cell(sx, sy), to_cell(tx, ty)

    # Prefer the middle of corridors: cells near walls cost more.
    clearance = ndimage.distance_transform_edt(walk) * cell
    cost = 1.0 + 2.0 * np.exp(-clearance / 0.4)

    path = astar(walk, cost, start, goal)
    if path is None:
        raise SystemExit("No route found")
    pts = [((j + 0.5) * cell, (H - 1 - i + 0.5) * cell) for i, j in path]
    simple = simplify(pts, tol=0.6)
    length = sum(math.dist(a, b) for a, b in zip(simple, simple[1:]))
    steps = steps_for(simple, dst_name)
    steps[-1]["side"] = arrival_side(simple, (tx, ty))
    out = {
        "from": {"id": args.src, "name": src_name},
        "to": {"id": args.dst, "name": dst_name},
        "lengthMeters": round(length, 1),
        "points": [{"x": round(x, 2), "y": round(y, 2)} for x, y in simple],
        "steps": [{**s, "say": spoken(s)} for s in steps],
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"{src_name} -> {dst_name}: {length:.1f} m, {len(simple)} points")
    for s in out["steps"]:
        print("  ", s["say"])


if __name__ == "__main__":
    main()
