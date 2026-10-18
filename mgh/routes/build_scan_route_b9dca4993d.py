"""Build the DRAFT floor-4 walking route in staircase scan b9dca4993d's own frame.

Inputs come from the sole master: the original ZIP's odometry.csv (read in place,
checksum recorded) and the draft depth-backed sign landmarks for 416/430/440.
Output stays private (scan geometry): route_graph.json and a top-view review image.
"""
import hashlib, json, sys, tempfile, zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'outputs')); sys.path.insert(0, str(HERE))
import MGH_Master_tools as archive
import scan_route

SCAN, ZIP = 'b9dca4993d', 'scans/b9dca4993d/original/MGH Staircase.zip'
FLOOR4_START_S = 50.0   # recording segments: stairs end ~48 s; floor-4 lobby/corridors after
FLOOR4_MIN_CAMERA_Y = 3.8
ROOMS = ['416', '430', '440']   # 420's sign lacks confident depth; no target is invented


def main(out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    con = archive.connect(ROOT / 'outputs/MGH_Master.sqlite')
    sha = con.execute('SELECT b.sha256 FROM current_assets a JOIN blobs b ON b.id=a.blob_id '
                      'WHERE a.logical_path=?', (ZIP,)).fetchone()[0]
    with tempfile.TemporaryDirectory() as tmp:
        archive.export_asset(con, ZIP, Path(tmp) / 'original.zip')   # verifies the stored checksum
        with zipfile.ZipFile(Path(tmp) / 'original.zip') as z:
            odo_bytes = z.read(f'{SCAN}/odometry.csv')
        (Path(tmp) / 'odometry.csv').write_bytes(odo_bytes)
        odometry = scan_route.read_odometry(Path(tmp) / 'odometry.csv')
    signs = []
    for room in ROOMS:
        row = con.execute("SELECT payload_json FROM current_records WHERE kind='landmark' AND record_key=?",
                          (f'MGH:4:{room}:measured-sign-candidate',)).fetchone()
        s = json.loads(row[0]); assert s['coordinate_frame_id'] == f'scan:{SCAN}' and s['position_scan_m']
        signs.append(s)
    con.close()
    g = scan_route.build_graph(odometry, FLOOR4_START_S, FLOOR4_MIN_CAMERA_Y, signs)
    graph = dict(
        format='MGH scan-frame draft route v1', coordinate_frame_id=f'scan:{SCAN}', floor=4, units='meters',
        axes='Stray Scanner/ARKit world, +y up; graph is horizontal (x, z); camera_y is phone height during the scan, not the floor',
        source=dict(original_zip=ZIP, original_zip_sha256=sha, odometry='odometry.csv',
                    odometry_sha256=hashlib.sha256(odo_bytes).hexdigest(),
                    floor4_start_seconds=FLOOR4_START_S, floor4_min_camera_y=FLOOR4_MIN_CAMERA_Y),
        parameters=dict(node_spacing_m=scan_route.NODE_SPACING_M, revisit_join_m=scan_route.REVISIT_JOIN_M,
                        tracking_jump_m=scan_route.TRACKING_JUMP_M, max_snap_m=scan_route.MAX_SNAP_M,
                        smooth_rows=scan_route.SMOOTH_ROWS),
        status='draft_unverified', routing_enabled=False, doorway_anchors_verified=0,
        registered_to_floor_plan=False, registered_to_app_graph=False, scale_correction_applied=False,
        excluded_rooms={'420': 'sign lacks confident depth; no position', '440_entrance': 'two plan entrances; sign viewpoint does not choose one'},
        note='Corridors are where the scanning phone walked; untraversed corridors are absent. Targets are sign viewpoints, not doorways.',
        **g)
    (out / 'route_graph.json').write_text(json.dumps(graph, indent=1))
    views = {s['room_key']: dict(odometry_row=s['source_odometry_row'],
                                 xz=odometry[s['source_odometry_row'], [2, 4]].tolist(),
                                 quaternion_xyzw=odometry[s['source_odometry_row'], 5:9].tolist()) for s in signs}
    (out / 'sign_view_poses.json').write_text(json.dumps(views, indent=1))
    review(graph, odometry, out / 'route_review.png')
    return graph


def review(graph, odometry, path):
    from PIL import Image, ImageDraw
    xz = np.array([[n['x'], n['z']] for n in graph['nodes']])
    allxz = np.vstack([odometry[:, [2, 4]], xz])
    lo, hi = allxz.min(0) - 2, allxz.max(0) + 2
    scale, pad = 1500 / (hi - lo).max(), 40
    W, H = (np.ceil((hi - lo) * scale) + 2 * pad).astype(int)
    px = lambda p: tuple(((np.asarray(p) - lo) * scale + pad).tolist())   # +x right, +z down
    im = Image.new('RGB', (int(W), int(H) + 60), 'white'); dr = ImageDraw.Draw(im)
    dr.line([px(p) for p in odometry[::10][:, [2, 4]]], fill=(215, 215, 215), width=1)
    for e in graph['edges']:
        dr.line([px(xz[e['a']]), px(xz[e['b']])], width=3,
                fill=(230, 120, 0) if e['source'] == 'revisit_join' else (30, 100, 200))
    for x in range(int(np.ceil(lo[0] / 5) * 5), int(hi[0]), 5):
        dr.text(px((x, lo[1] + 0.5)), f'{x} m', fill=(120, 120, 120))
    for t in graph['targets']:
        s, n = px(t['sign_xz']), px(xz[t['node']])
        dr.line([s, n], fill=(200, 0, 0), width=1)
        dr.rectangle([s[0] - 5, s[1] - 5, s[0] + 5, s[1] + 5], fill=(200, 0, 0))
        dr.ellipse([n[0] - 5, n[1] - 5, n[0] + 5, n[1] + 5], outline=(200, 0, 0), width=2)
        dr.text((s[0] + 8, s[1] - 14), f"{t['label']} sign ({t['sign_to_node_m']:.1f} m to path)", fill=(150, 0, 0))
    dr.text((pad, H + 5), f"DRAFT, UNVERIFIED floor-4 route, scan {SCAN} frame (top view, x right, z down). "
            f"{len(graph['nodes'])} nodes / {len(graph['edges'])} edges.", fill=(0, 0, 0))
    dr.text((pad, H + 25), 'blue = walked edge, orange = revisit join, grey = whole recording incl. stairs, '
            'red square = sign point (not a doorway), red circle = snapped target node', fill=(0, 0, 0))
    im.save(path)


if __name__ == '__main__':
    g = main(sys.argv[1] if len(sys.argv) > 1 else HERE / 'scan_b9dca4993d_floor4_draft')
    print(json.dumps(dict(nodes=len(g['nodes']), edges=len(g['edges']), path_breaks=g['path_breaks'],
                          revisit_joins=sum(e['source'] == 'revisit_join' for e in g['edges']),
                          targets=[(t['room_key'], t['node'], t['sign_to_node_m']) for t in g['targets']]), indent=1))
