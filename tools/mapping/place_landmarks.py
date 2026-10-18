#!/usr/bin/env python3
"""Place detected signs on the floor map using LiDAR depth + the camera pose of each frame.

Input: detections.json, a list of
  {"frame": 6000, "label": "430", "kind": "room_number", "name": "Computer Classroom",
   "box": [left, top, width, height]}            # pixels in the 1920x1440 video frame
Output: landmarks.json in the floor directory (plan meters, merged across frames).

Usage:
  python3 place_landmarks.py SCAN_DIR data/mgh/04 detections.json
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

DEPTH_SCALE = 1920 / 256  # depth maps are 256x192, video 1920x1440


def quat_to_matrix(qx, qy, qz, qw):
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ])


def load_odometry(scan):
    rows = list(csv.reader(open(Path(scan) / "odometry.csv")))[1:]
    out = {}
    for r in rows:
        f = int(r[1])
        out[f] = {
            "t": np.array([float(r[2]), float(r[3]), float(r[4])]),
            "R": quat_to_matrix(*(float(v) for v in r[5:9])),
            "K": [float(v) for v in r[9:13]],  # fx, fy, cx, cy
        }
    return out


def sign_depth(scan, frame, box):
    """Median depth (m) inside the box, using only confident LiDAR pixels."""
    depth = np.array(Image.open(Path(scan) / "depth" / f"{frame:06d}.png")).astype(float) / 1000.0
    conf = np.array(Image.open(Path(scan) / "confidence" / f"{frame:06d}.png"))
    l, t, w, h = box
    j0, j1 = int(l / DEPTH_SCALE), int(math.ceil((l + w) / DEPTH_SCALE))
    i0, i1 = int(t / DEPTH_SCALE), int(math.ceil((t + h) / DEPTH_SCALE))
    d = depth[i0:i1 + 1, j0:j1 + 1]
    c = conf[i0:i1 + 1, j0:j1 + 1]
    good = d[(c >= 1) & (d > 0.1)]
    if good.size == 0:
        good = d[d > 0.1]
    return float(np.median(good)) if good.size else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("floor_dir")
    ap.add_argument("detections")
    ap.add_argument("--merge-radius", type=float, default=2.0)
    args = ap.parse_args()

    fd = Path(args.floor_dir)
    al = json.loads((fd / "alignment.json").read_text())
    th = al["thetaRadians"]
    c, s = math.cos(th), math.sin(th)
    origin = np.array(al["originArkitTopDown"])
    trans = np.array(al["translation"])

    def to_plan(world):
        p = np.array([world[0], -world[2]]) - origin  # top-down (x, -z)
        return np.array([p[0] * c - p[1] * s, p[0] * s + p[1] * c]) + trans

    odo = load_odometry(args.scan)
    dets = json.loads(Path(args.detections).read_text())
    placed = []
    for det in dets:
        pose = odo[det["frame"]]
        d = sign_depth(args.scan, det["frame"], det["box"])
        if d is None:
            print("no depth for", det)
            continue
        l, t, w, h = det["box"]
        u, v = l + w / 2, t + h / 2
        fx, fy, cx, cy = pose["K"]
        # Stray Scanner poses use the OpenCV camera frame: x right, y down, looking down +z.
        # (Checked on the MGH 4 scan: with this convention repeat sightings of the same sign
        # agree to ~0.1 m; with ARKit's y-up/-z frame they scatter by 5+ m.)
        ray = np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
        cam_point = ray * d  # LiDAR depth is distance along the optical axis
        world = pose["R"] @ cam_point + pose["t"]
        cam_plan = to_plan(pose["t"])
        sign_plan = to_plan(world)
        placed.append({**det, "depth": d, "plan": sign_plan, "camera": cam_plan, "height": world[1]})

    # Merge sightings of the same label that land close together.
    groups = defaultdict(list)
    for p in placed:
        key = (p["label"], p["kind"])
        for g in groups[key]:
            if np.linalg.norm(np.mean([q["plan"] for q in g], axis=0) - p["plan"]) < args.merge_radius:
                g.append(p)
                break
        else:
            groups[key].append([p])

    landmarks = []
    for (label, kind), gs in groups.items():
        for n, g in enumerate(gs):
            pos = np.mean([q["plan"] for q in g], axis=0)
            # The sign faces the cameras that read it: average direction from sign to camera.
            facing_vec = np.mean([q["camera"] - q["plan"] for q in g], axis=0)
            facing = (math.degrees(math.atan2(facing_vec[0], facing_vec[1])) + 360) % 360  # 0 = plan up
            spread = max(float(np.linalg.norm(q["plan"] - pos)) for q in g)
            landmarks.append({
                "id": f"lm-{label.lower().replace(' ', '-')}" + (f"-{n + 1}" if len(gs) > 1 else ""),
                "label": label,
                "kind": kind,
                "name": g[0].get("name"),
                "x": round(float(pos[0]), 2),
                "y": round(float(pos[1]), 2),
                "heightMeters": round(float(np.mean([q["height"] for q in g]) - 0.0), 2),
                "facingDegrees": round(facing, 0),
                "sightings": len(g),
                "spreadMeters": round(spread, 2),
                "unique": kind == "room_number",
                "frames": [q["frame"] for q in g],
            })
    landmarks.sort(key=lambda l: l["id"])
    (fd / "landmarks.json").write_text(json.dumps({
        "frame": "plan meters (see floor.json); facingDegrees clockwise from plan up",
        "heightNote": "heightMeters is relative to the camera height at the start of the scan",
        "landmarks": landmarks,
    }, indent=2))
    for l in landmarks:
        print(f"{l['id']:22s} ({l['x']:6.2f}, {l['y']:6.2f})  faces {l['facingDegrees']:5.0f}°  "
              f"{l['sightings']} sightings, spread {l['spreadMeters']} m")


if __name__ == "__main__":
    main()
