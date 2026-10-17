#!/usr/bin/env python3
"""Draw the floor plan with the aligned walk, landmarks and a route, to check everything by eye.

Usage: python3 overlay.py PLAN.pdf data/mgh/04 out.png [--crop]
"""
import argparse
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("floor_dir")
    ap.add_argument("out")
    ap.add_argument("--zoom", type=float, default=2.5)
    ap.add_argument("--crop", action="store_true", help="crop to the walk and route")
    args = ap.parse_args()
    fd = Path(args.floor_dir)
    floor = json.loads((fd / "floor.json").read_text())
    mpp, x0, ytop, z = floor["metersPerPdfPoint"], floor["pdfOrigin"]["x"], floor["pdfOrigin"]["yTop"], args.zoom

    pix = pymupdf.open(args.pdf)[0].get_pixmap(matrix=pymupdf.Matrix(z, z))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    d = ImageDraw.Draw(im)

    def P(x, y):
        return ((x / mpp + x0) * z, (ytop - y / mpp) * z)

    pts = []
    al = fd / "alignment.json"
    if al.exists():
        path = json.loads(al.read_text())["path"]
        xy = [P(p["x"], p["y"]) for p in path]
        pts += xy
        d.line(xy, fill=(30, 110, 230), width=5)
        d.ellipse([xy[0][0] - 9, xy[0][1] - 9, xy[0][0] + 9, xy[0][1] + 9], fill=(30, 170, 60))
        d.rectangle([xy[-1][0] - 8, xy[-1][1] - 8, xy[-1][0] + 8, xy[-1][1] + 8], fill=(220, 40, 40))
    rt = fd / "route.json"
    if rt.exists():
        route = json.loads(rt.read_text())
        xy = [P(p["x"], p["y"]) for p in route["points"]]
        pts += xy
        d.line(xy, fill=(52, 199, 89), width=4)
    lm = fd / "landmarks.json"
    if lm.exists():
        for l in json.loads(lm.read_text())["landmarks"]:
            x, y = P(l["x"], l["y"])
            pts.append((x, y))
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(240, 150, 0), outline=(0, 0, 0))
            d.text((x + 9, y - 7), l["label"], fill=(160, 60, 0))
    if args.crop and pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        m = 60 * z / 2.5
        im = im.crop((max(0, min(xs) - m), max(0, min(ys) - m), min(im.width, max(xs) + m), min(im.height, max(ys) + m)))
    im.save(args.out)


if __name__ == "__main__":
    main()
