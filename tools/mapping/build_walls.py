#!/usr/bin/env python3
"""Wall lines for the app's 3D view, from a UW Space Viewer floor-plan PDF.

Output: <name>_walls.json with wall segments and room labels in plan meters (same frame as
build_floor.py: origin at the plan's bottom-left, x right, y up). The app extrudes these into
a 3D model of the floor. The plans are NetID-only, so the output is gitignored: generate it
locally and drop it into Fuga/Maps/ (the app falls back to a simple model from the hallway
graph without it).

Usage:
  python3 build_walls.py MGH1197_04.pdf --out Fuga/Maps/mgh4_walls.json
"""
import argparse
import json
import math
import re
from pathlib import Path

import pymupdf

from build_floor import BLOCKING_GROUPS, ROOM_LABEL, scale_bar

WALL_GROUPS = [2, 3, 7, 9]   # walls, wall details, glazing (columns/stairs left out of the 3D view)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-length", type=float, default=0.15, help="drop wall pieces shorter than this (m)")
    args = ap.parse_args()

    page = pymupdf.open(args.pdf)[0]
    drawings = page.get_drawings()
    m_per_pt = scale_bar(drawings)

    # Same frame as build_floor.py (bounds from all blocking groups, 2 m margin).
    blocking = [it for g in BLOCKING_GROUPS for it in drawings[g]["items"] if it[0] == "l"]
    xs = [p.x for it in blocking for p in it[1:3]]
    ys = [p.y for it in blocking for p in it[1:3]]
    pad = 2.0 / m_per_pt
    x0, y1 = min(xs) - pad, max(ys) + pad

    def to_m(p):
        return ((p.x - x0) * m_per_pt, (y1 - p.y) * m_per_pt)

    segs = set()
    for g in WALL_GROUPS:
        for it in drawings[g]["items"]:
            if it[0] != "l":
                continue
            (ax, ay), (bx, by) = to_m(it[1]), to_m(it[2])
            if math.hypot(bx - ax, by - ay) < args.min_length:
                continue
            a, b = sorted([(round(ax, 2), round(ay, 2)), (round(bx, 2), round(by, 2))])
            segs.add((*a, *b))

    rooms = []
    for x_a, y_a, x_b, y_b, word, *_ in page.get_text("words"):
        if ROOM_LABEL.match(word):
            mx, my = to_m(pymupdf.Point((x_a + x_b) / 2, (y_a + y_b) / 2))
            rooms.append({"id": word, "x": round(mx, 2), "y": round(my, 2)})

    out = {"frame": "plan meters, origin bottom-left, x right, y up",
           "wallHeight": 2.7,
           "walls": sorted(segs),
           "rooms": rooms}
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(segs)} wall segments, {len(rooms)} room labels -> {args.out}")


if __name__ == "__main__":
    main()
