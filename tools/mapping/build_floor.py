#!/usr/bin/env python3
"""Turn a UW Space Viewer floor-plan PDF (ArcGIS export) into a routable floor map.

Outputs (in --out):
  floor.json  rooms (label + position in meters), scale, grid metadata
  grid.png    walkable grid: white = walkable, black = blocked (1 px = --cell meters)

Plan frame: meters, origin at the plan's bottom-left drawing corner, x right, y up (page up).

Usage:
  python3 build_floor.py MGH1197_04.pdf --out data/mgh/04 --building MGH --floor 4
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw
from scipy import ndimage

# Drawing groups in this ArcGIS export (checked by rendering each one on MGH 4):
#   2 walls, 3/7/9 wall details and glazing, 6 columns, 13 stairs/seating, 14 shafts
#   8 door swings (left out so doorways stay open), 4/10/11/12/15 outlines and roof edges (left out)
BLOCKING_GROUPS = [2, 3, 6, 7, 9, 13, 14]
ROOM_LABEL = re.compile(r"^\d[0-9A-Z]{1,4}$")


def scale_bar(drawings):
    """Meters per PDF point from the 120 ft scale bar (the long 1 pt line under the plan)."""
    bars = [
        d for d in drawings
        if len(d["items"]) == 1 and d["items"][0][0] == "l"
        and abs(d["rect"].y1 - d["rect"].y0) < 0.5 and d["rect"].width > 200
    ]
    if not bars:
        raise SystemExit("Scale bar not found")
    return 120 * 0.3048 / bars[0]["rect"].width


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--building", default="MGH")
    ap.add_argument("--floor", type=int, default=4)
    ap.add_argument("--cell", type=float, default=0.15, help="grid cell size in meters")
    ap.add_argument("--clearance", type=float, default=0.25, help="keep paths this far from walls (m)")
    args = ap.parse_args()

    page = pymupdf.open(args.pdf)[0]
    drawings = page.get_drawings()
    m_per_pt = scale_bar(drawings)

    walls = [it for g in BLOCKING_GROUPS for it in drawings[g]["items"] if it[0] == "l"]
    xs = [p.x for it in walls for p in it[1:3]]
    ys = [p.y for it in walls for p in it[1:3]]
    pad = 2.0 / m_per_pt  # 2 m margin
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad

    def to_m(px, py):
        """PDF point -> plan meters (x right, y up)."""
        return ((px - x0) * m_per_pt, (y1 - py) * m_per_pt)

    width_m, height_m = (x1 - x0) * m_per_pt, (y1 - y0) * m_per_pt
    gw, gh = int(np.ceil(width_m / args.cell)), int(np.ceil(height_m / args.cell))

    # Rasterize walls. Grid row 0 is the top (max y), like an image.
    img = Image.new("L", (gw, gh), 0)
    draw = ImageDraw.Draw(img)
    for it in walls:
        (ax, ay), (bx, by) = to_m(it[1].x, it[1].y), to_m(it[2].x, it[2].y)
        draw.line(
            [(ax / args.cell, (height_m - ay) / args.cell), (bx / args.cell, (height_m - by) / args.cell)],
            fill=255, width=1,
        )
    blocked = np.array(img) > 0

    # Seal hairline gaps in walls (< ~0.3 m), then mark the outside of the building as blocked.
    sealed = ndimage.binary_closing(blocked, iterations=1)
    free = ~sealed
    labels, _ = ndimage.label(free)
    outside = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    inside = free & ~np.isin(labels, list(outside))

    # Keep paths off the walls by eroding the walkable area.
    clear_cells = max(1, int(round(args.clearance / args.cell)))
    walkable = ndimage.binary_erosion(inside, iterations=clear_cells)

    # Rooms from the plan's text labels.
    rooms = []
    for x_a, y_a, x_b, y_b, word, *_ in page.get_text("words"):
        if ROOM_LABEL.match(word) and x0 < x_a < x1 and y0 < y_a < y1:
            mx, my = to_m((x_a + x_b) / 2, (y_a + y_b) / 2)
            kind = "stair" if "ST" in word else "elevator" if "EL" in word else "room"
            rooms.append({"id": word, "kind": kind, "x": round(mx, 2), "y": round(my, 2)})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray((walkable * 255).astype(np.uint8)).save(out / "grid.png")
    floor = {
        "building": args.building,
        "floor": args.floor,
        "source": Path(args.pdf).name,
        "frame": "meters; origin at bottom-left of the plan drawing; x right, y up (page up)",
        "metersPerPdfPoint": round(m_per_pt, 6),
        "pdfOrigin": {"x": round(x0, 2), "yTop": round(y1, 2)},
        "grid": {
            "file": "grid.png",
            "cellMeters": args.cell,
            "width": gw,
            "height": gh,
            "rowZeroIsTop": True,
            "walkable": "white",
            "clearanceMeters": args.clearance,
        },
        "rooms": sorted(rooms, key=lambda r: r["id"]),
    }
    (out / "floor.json").write_text(json.dumps(floor, indent=2))
    print(f"scale {m_per_pt:.5f} m/pt, plan {width_m:.1f} x {height_m:.1f} m, grid {gw}x{gh}, "
          f"rooms {len(rooms)}, walkable {walkable.mean():.1%} of grid")


if __name__ == "__main__":
    main()
