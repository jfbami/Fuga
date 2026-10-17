#!/usr/bin/env python3
"""Draw a marked floor plan: the scanned walk, routes, landmarks and (optionally) the walkable area.

Usage:
  python3 overlay.py PLAN.pdf data/mgh/04 out.png [--crop] [--routes route_a.json route_b.json]
                     [--no-walk] [--no-landmarks] [--walkable] [--title "..."]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROUTE_COLORS = [(52, 199, 89), (175, 82, 222), (255, 149, 0), (0, 122, 255)]
WALK_COLOR = (30, 110, 230)
LANDMARK_COLOR = (255, 159, 10)


def font(size):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("floor_dir")
    ap.add_argument("out")
    ap.add_argument("--zoom", type=float, default=2.5)
    ap.add_argument("--crop", action="store_true", help="crop to what is drawn")
    ap.add_argument("--routes", nargs="*", help="route files (default: every route_*.json in floor_dir)")
    ap.add_argument("--no-walk", action="store_true")
    ap.add_argument("--no-landmarks", action="store_true")
    ap.add_argument("--walkable", action="store_true", help="tint the walkable area (needs grid.png)")
    ap.add_argument("--title")
    args = ap.parse_args()
    fd = Path(args.floor_dir)
    floor = json.loads((fd / "floor.json").read_text())
    mpp, x0, ytop, z = floor["metersPerPdfPoint"], floor["pdfOrigin"]["x"], floor["pdfOrigin"]["yTop"], args.zoom
    s = z / 2.5  # scale line widths with zoom

    pix = pymupdf.open(args.pdf)[0].get_pixmap(matrix=pymupdf.Matrix(z, z))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def P(x, y):
        return ((x / mpp + x0) * z, (ytop - y / mpp) * z)

    if args.walkable:
        g = np.array(Image.open(fd / floor["grid"]["file"])) > 0
        cell = floor["grid"]["cellMeters"]
        tint = Image.new("RGBA", im.size, (0, 0, 0, 0))
        td = ImageDraw.Draw(tint)
        H = g.shape[0]
        for i, j in zip(*np.nonzero(g)):
            x, y = j * cell, (H - 1 - i) * cell
            (ax, ay), (bx, by) = P(x, y + cell), P(x + cell, y)
            td.rectangle([ax, ay, bx, by], fill=(52, 199, 89, 70))
        im = Image.alpha_composite(im.convert("RGBA"), tint).convert("RGB")

    d = ImageDraw.Draw(im)
    pts, legend = [], []

    al = fd / "alignment.json"
    if al.exists() and not args.no_walk:
        path = json.loads(al.read_text())["path"]
        xy = [P(p["x"], p["y"]) for p in path]
        pts += xy
        d.line(xy, fill=WALK_COLOR, width=int(4 * s))
        r = 9 * s
        d.ellipse([xy[0][0] - r, xy[0][1] - r, xy[0][0] + r, xy[0][1] + r], fill=WALK_COLOR)
        legend.append((WALK_COLOR, "Scanned walk (LiDAR)"))

    route_files = [Path(r) for r in args.routes] if args.routes is not None else sorted(fd.glob("route_*.json"))
    for k, rf in enumerate(route_files):
        route = json.loads(Path(rf).read_text())
        color = ROUTE_COLORS[k % len(ROUTE_COLORS)]
        xy = [P(p["x"], p["y"]) for p in route["points"]]
        pts += xy
        d.line(xy, fill=color, width=int(6 * s), joint="curve")
        r = 10 * s
        d.ellipse([xy[0][0] - r, xy[0][1] - r, xy[0][0] + r, xy[0][1] + r], fill=(30, 30, 30))
        d.rectangle([xy[-1][0] - r, xy[-1][1] - r, xy[-1][0] + r, xy[-1][1] + r], fill=color, outline=(30, 30, 30), width=2)
        legend.append((color, f"Route: elevator to {route['to']['name']} ({route['lengthMeters']} m)"))

    lm = fd / "landmarks.json"
    if lm.exists() and not args.no_landmarks:
        f = font(int(15 * s))
        for l in json.loads(lm.read_text())["landmarks"]:
            x, y = P(l["x"], l["y"])
            pts.append((x, y))
            r = 8 * s
            d.ellipse([x - r, y - r, x + r, y + r], fill=LANDMARK_COLOR, outline=(0, 0, 0), width=2)
            text = l["label"] if not l.get("name") or l["kind"] != "room_number" else f"{l['label']} {l['name']}"
            tx, ty = x + 12 * s, y - 9 * s
            box = d.textbbox((tx, ty), text, font=f)
            d.rectangle([box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2], fill=(255, 255, 255))
            d.text((tx, ty), text, fill=(150, 70, 0), font=f)
        legend.append((LANDMARK_COLOR, "Sign found in the scan"))

    if args.crop and pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        m = 70 * s
        im = im.crop((int(max(0, min(xs) - m)), int(max(0, min(ys) - m)),
                      int(min(im.width, max(xs) + m)), int(min(im.height, max(ys) + m))))
        d = ImageDraw.Draw(im)

    # Title + legend band along the top.
    f = font(int(16 * s))
    lines = ([args.title] if args.title else []) + [t for _, t in legend]
    band_h = int((len(lines) * 24 + 16) * s)
    canvas = Image.new("RGB", (im.width, im.height + band_h), (255, 255, 255))
    canvas.paste(im, (0, band_h))
    cd = ImageDraw.Draw(canvas)
    y = int(8 * s)
    if args.title:
        cd.text((int(12 * s), y), args.title, fill=(20, 20, 20), font=font(int(18 * s)))
        y += int(24 * s)
    for color, text in legend:
        cd.rectangle([int(12 * s), y + int(4 * s), int(32 * s), y + int(16 * s)], fill=color)
        cd.text((int(40 * s), y), text, fill=(40, 40, 40), font=f)
        y += int(24 * s)
    canvas.save(args.out)


if __name__ == "__main__":
    main()
