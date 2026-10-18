"""Replay capture-only app exports offline and draw what the route preview would show.

For each export: run every frame through the same recognition server code the app would
call (no network), apply the app's two-frame agreement rule (review_quicklook), ask the
draft /route for the destination, and draw on the actual photo:
  - the green draft route on the floor (projected with the phone's own calibration),
  - the arrow direction and distance the app would show,
  - a top-down map of the draft graph with the estimated position and route.

Floor height follows the app's fallback: 1.35 m below the phone (FloorPathNode).
Outputs are private (photos + scan coordinates). Nothing here verifies position accuracy:
it shows the system's hypothesis so a person who stood there can judge it.
"""
import argparse, base64, io, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'routes'))
import serve_phone_localizer as server
import review_quicklook
import scan_route

PHONE_HEIGHT_M = 1.35   # FloorPathNode fallback when ARKit has no floor plane
GREEN, DARK = (52, 199, 89), (13, 107, 41)


def font(size):
    for name in ['segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf']:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def project(points_scan, R, t, k):
    """Scan-frame points -> pixel coordinates in the portrait photo (OpenCV camera, +Z forward)."""
    cam = (np.asarray(points_scan) - t) @ R          # R^T (P - t) for each row
    out = []
    for X, Y, Z in cam:
        out.append(None if Z < 0.3 else (k['fx'] * X / Z + k['cx'], k['fy'] * Y / Z + k['cy']))
    return out


def densify(xz, step=0.25):
    pts = [np.asarray(xz[0], float)]
    for a, b in zip(xz[:-1], xz[1:]):
        a, b = np.asarray(a, float), np.asarray(b, float)
        n = max(1, int(np.linalg.norm(b - a) / step))
        pts += [a + (b - a) * (i / n) for i in range(1, n + 1)]
    return np.array(pts)


def arrow_bearing(position_xz, forward_xz, path_xz):
    """Same rule as the app: aim 2 m along the route; clockwise-positive degrees."""
    path = np.asarray(path_xz, float)
    along = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    aim = np.array([np.interp(2.0, along, path[:, 0]), np.interp(2.0, along, path[:, 1])])
    a, f = aim - position_xz, np.asarray(forward_xz)
    cross = f[0] * a[1] - f[1] * a[0]                # scan top view: left turn when cross < 0
    return math.degrees(math.atan2(cross, float(f @ a)))   # left negative, right positive


def draw_photo(image, route_scan_xz, floor_y, R, t, k, label_lines, bearing, meters):
    im = image.convert('RGB'); d = ImageDraw.Draw(im, 'RGBA')
    pts3 = [(x, floor_y, z) for x, z in densify(route_scan_xz)]
    px = project(pts3, R, t, k)
    w = max(6, im.width // 60)
    for a, b in zip(px[:-1], px[1:]):
        if a and b and all(-2 * im.width < c < 3 * im.width for c in (*a, *b)):
            d.line([a, b], fill=DARK + (230,), width=w + 6)
    for a, b in zip(px[:-1], px[1:]):
        if a and b and all(-2 * im.width < c < 3 * im.width for c in (*a, *b)):
            d.line([a, b], fill=GREEN + (235,), width=w)
    # arrow puck, bottom centre, like the app (0 = ahead, + = right)
    cx, cy, r = im.width / 2, im.height - im.width * 0.22, im.width * 0.12
    aligned = abs(bearing) <= 20
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(GREEN + (235,)) if aligned else (0, 0, 0, 150))
    ang = math.radians(bearing)
    tip = (cx + 0.75 * r * math.sin(ang), cy - 0.75 * r * math.cos(ang))
    tail = (cx - 0.55 * r * math.sin(ang), cy + 0.55 * r * math.cos(ang))
    d.line([tail, tip], fill='white', width=int(r * 0.18))
    for side in (-1, 1):
        h = ang + math.pi + side * 0.55
        d.line([tip, (tip[0] + 0.45 * r * math.sin(h), tip[1] - 0.45 * r * math.cos(h))], fill='white', width=int(r * 0.18))
    f = font(max(18, im.width // 28))
    d.text((cx, cy + r + 12), f'{meters:.0f} m', fill='white', font=f, anchor='mt', stroke_width=3, stroke_fill='black')
    fs = font(max(16, im.width // 40)); y = 18
    for line in label_lines:
        d.text((18, y), line, fill='white', font=fs, stroke_width=3, stroke_fill='black'); y += int(fs.size * 1.3)
    return im


def draw_map(graph, position_xz, forward_xz, route_xz, size=900):
    xz = np.array([[n['x'], n['z']] for n in graph['nodes']])
    lo, hi = xz.min(0) - 3, xz.max(0) + 3
    s = (size - 40) / (hi - lo).max()
    P = lambda p: tuple(((np.asarray(p) - lo) * s + 20).tolist())
    H = int((hi - lo)[1] * s + 40)
    im = Image.new('RGB', (size, H), 'white'); d = ImageDraw.Draw(im)
    for e in graph['edges']:
        d.line([P(xz[e['a']]), P(xz[e['b']])], fill=(170, 190, 220), width=3)
    d.line([P(p) for p in route_xz], fill=GREEN, width=7)
    for t in graph['targets']:
        q = P(t['sign_xz']); d.rectangle([q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6], fill=(200, 0, 0))
        d.text((q[0] + 9, q[1] - 8), t['room_key'][-3:] + ' sign', fill=(150, 0, 0), font=font(16))
    c = P(position_xz); f = np.asarray(forward_xz)
    d.ellipse([c[0] - 9, c[1] - 9, c[0] + 9, c[1] + 9], fill=(30, 100, 220))
    d.line([c, (c[0] + f[0] * 40, c[1] + f[1] * 40)], fill=(30, 100, 220), width=5)
    d.text((20, H - 26), 'Top view, draft scan frame (x right, z down). Blue = estimated phone and facing.', fill='black', font=font(15))
    return im


def replay(export_path, engine, router, out_dir, note=''):
    bundle = json.loads(Path(export_path).read_text(encoding='utf-8'))
    room = ''.join(ch for ch in str(bundle.get('requested_destination') or '440') if ch.isdigit()) or '440'
    responses = [server.localize_payload(r, engine) for r in bundle['requests']]
    review = review_quicklook.review_bundle(dict(bundle, responses=responses), engine.manifest_hash)
    by_id = {r['request_id']: r for r in responses}
    summary = dict(export=Path(export_path).name, session_id=bundle.get('session_id'), note=note,
                   destination_room=room, frames=len(responses),
                   accepted_frames=sum(bool(r.get('accepted')) for r in responses),
                   app_status=('Possible location - unverified' if review['status'] == 'consistent_alignment_hypothesis'
                               else 'Not located yet'), verified=False)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stem = (bundle.get('session_id') or Path(export_path).stem)[:8]
    if review['status'] != 'consistent_alignment_hypothesis':
        req = bundle['requests'][-1]
        img = Image.open(io.BytesIO(base64.b64decode(req['image_base64']))).convert('RGB')
        ImageDraw.Draw(img).text((18, 18), f'NOT LOCATED: {summary["accepted_frames"]}/{len(responses)} frames accepted, no agreement',
                                 fill='white', font=font(img.width // 32), stroke_width=3, stroke_fill='black')
        img.save(out / f'{stem}_photo.jpg', quality=88)
        summary.update(image=f'{stem}_photo.jpg', reasons=[d.get('reason') for d in review['frame_diagnostics']])
        return summary
    rid = review['support_request_ids'][-1]
    req = next(r for r in bundle['requests'] if r['request_id'] == rid); res = by_id[rid]
    R, t = np.array(res['rotation_world_camera']), np.array(res['position_scan_m'])
    route = server.route_payload(dict(destination_room=room, building_id='MGH', selected_floor=4,
        coordinate_frame_id=res['coordinate_frame_id'], map_manifest_sha256=res['map_manifest_sha256'],
        position_scan_m=t.tolist(), forward_scan=R[:, 2].tolist()), router)
    fwd = R[:, 2][[0, 2]]; fwd = fwd / np.linalg.norm(fwd)
    summary.update(position_scan_m=t.round(2).tolist(), route_ok=route['ok'],
                   route_reason=route.get('reason'), meters=route.get('meters'))
    img = Image.open(io.BytesIO(base64.b64decode(req['image_base64'])))
    lines = ['DRAFT ROUTE PREVIEW (offline replay)', 'UNVERIFIED MAP - NOT GUIDANCE', f'to room {room}']
    if route['ok']:
        bearing = arrow_bearing(t[[0, 2]], fwd, route['path_scan_xz'])
        summary['arrow_bearing_deg'] = round(bearing, 1)
        photo = draw_photo(img, route['path_scan_xz'], t[1] - PHONE_HEIGHT_M, R, t, req['intrinsics'],
                           lines + [f'{route["meters"]:.0f} m, arrow {abs(bearing):.0f} deg {"right" if bearing > 0 else "left"}'],
                           bearing, route['meters'])
        top = draw_map(router.graph, t[[0, 2]], fwd, route['path_scan_xz'])
    else:
        photo = img.convert('RGB'); ImageDraw.Draw(photo).text((18, 18), f'Located, but no route: {route.get("reason")}',
                                                               fill='white', font=font(img.width // 32), stroke_width=3, stroke_fill='black')
        top = draw_map(router.graph, t[[0, 2]], fwd, [t[[0, 2]].tolist(), t[[0, 2]].tolist()])
    # side by side: photo (scaled) | map
    ph = photo.resize((int(photo.width * 900 / photo.height), 900))
    tp = top.resize((int(top.width * min(1, 900 / top.height)), int(top.height * min(1, 900 / top.height))))
    sheet = Image.new('RGB', (ph.width + tp.width + 20, 900), 'white')
    sheet.paste(ph, (0, 0)); sheet.paste(tp, (ph.width + 20, (900 - tp.height) // 2))
    sheet.save(out / f'{stem}_route_preview.jpg', quality=88)
    summary['image'] = f'{stem}_route_preview.jpg'
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('exports', nargs='+', type=Path)
    p.add_argument('--map', type=Path, default=HERE / 'visual_map_v4_low_rotation')
    p.add_argument('--route-graph', type=Path, default=HERE.parent / 'routes/scan_b9dca4993d_floor4_draft/route_graph.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--notes', type=Path, help='Optional JSON {export filename: tester note}')
    a = p.parse_args()
    notes = json.loads(a.notes.read_text(encoding='utf-8')) if a.notes else {}
    engine = server.PhoneEngine(a.map)
    router = server.DraftRouter(a.route_graph, engine)
    results = [replay(e, engine, router, a.output, notes.get(e.name, '')) for e in a.exports]
    (a.output / 'replay_summary.json').write_text(json.dumps(dict(
        map_manifest_sha256=engine.manifest_hash, route_graph_sha256=router.graph_hash,
        phone_height_assumption_m=PHONE_HEIGHT_M, verified=False, results=results), indent=1))
    for r in results:
        print(json.dumps(r))


if __name__ == '__main__':
    main()
