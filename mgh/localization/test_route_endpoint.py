"""Tests for the draft /route endpoint. Synthetic tests are public-safe; the replay test
uses the private draft graph and first iPhone capture when present (skipped otherwise)
and mirrors the app's RoutePreviewMath in numpy. Same-capture consistency only."""
import json, math, sys, unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import serve_phone_localizer as server

FRAME, MAP = 'scan:test', 'a' * 64


class FakeEngine:
    manifest = dict(coordinate_frame_id=FRAME)
    manifest_hash = MAP


def line_graph(tmp):
    nodes = [dict(id=i, x=float(i), z=0.0, camera_y=1.4) for i in range(11)]
    edges = [dict(a=i, b=i + 1, meters=1.0, source='walked') for i in range(10)]
    g = dict(coordinate_frame_id=FRAME, floor=4, status='draft_unverified', nodes=nodes, edges=edges,
             targets=[dict(id='MGH:4:440:sign-viewpoint', room_key='MGH:4:440', node=10)])
    path = tmp / 'graph.json'; path.write_text(json.dumps(g)); return path


def body(**kw):
    b = dict(destination_room='440', building_id='MGH', selected_floor=4, coordinate_frame_id=FRAME,
             map_manifest_sha256=MAP, position_scan_m=[0.0, 1.4, 0.3], forward_scan=[1.0, -0.2, 0.0])
    b.update(kw); return b


class RouteEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp())
        cls.router = server.DraftRouter(line_graph(cls.tmp), FakeEngine())

    def test_route_is_marked_draft_and_starts_at_camera(self):
        r = server.route_payload(body(), self.router)
        self.assertTrue(r['ok']); self.assertFalse(r['verified']); self.assertFalse(r['guidance_allowed'])
        self.assertEqual(r['path_scan_xz'][0], [0.0, 0.3])
        self.assertEqual(r['path_scan_xz'][-1], [10.0, 0.0])
        self.assertAlmostEqual(r['meters'], math.hypot(1, 0.3) + 9, places=2)   # joins ahead at node 1
        self.assertAlmostEqual(r['initial_turn_degrees'], 0, delta=10)

    def test_refuses_other_map_floor_room_or_missing_graph(self):
        with self.assertRaises(ValueError): server.route_payload(body(map_manifest_sha256='b' * 64), self.router)
        with self.assertRaises(ValueError): server.route_payload(body(coordinate_frame_id='scan:other'), self.router)
        self.assertEqual(server.route_payload(body(selected_floor=3), self.router)['status'], 'no_draft_route_for_floor')
        self.assertFalse(server.route_payload(body(destination_room='420'), self.router)['ok'])
        with self.assertRaises(ValueError): server.route_payload(body(destination_room='../x'), self.router)
        with self.assertRaises(ValueError): server.route_payload(body(position_scan_m=[0, float('nan'), 0]), self.router)
        self.assertEqual(server.route_payload(body(), None)['status'], 'route_graph_not_loaded')

    def test_off_map_refused(self):
        r = server.route_payload(body(position_scan_m=[0.0, 1.4, 9.0]), self.router)
        self.assertFalse(r['ok']); self.assertIn('walked path', r['reason'])

    def test_graph_frame_must_match_map(self):
        class Other(FakeEngine): manifest = dict(coordinate_frame_id='scan:other')
        with self.assertRaises(ValueError): server.DraftRouter(line_graph(self.tmp), Other())


CAP = HERE.parent / 'capture/quicklook_20261018_4C1B520E'
GRAPH = HERE.parent / 'routes/scan_b9dca4993d_floor4_draft/route_graph.json'


@unittest.skipUnless(CAP.exists() and GRAPH.exists(), 'private capture/graph not present')
class FirstCaptureReplay(unittest.TestCase):
    """Mirror of the app chain on capture 4C1B520E: alignment -> scan pose -> /route -> AR path -> arrow."""

    def test_route_lands_back_at_phone_and_arrow_points_left_toward_440(self):
        bundle = json.loads(next((CAP / 'originals').glob('*.json')).read_text(encoding='utf-8'))
        resp = json.loads((CAP / 'derived/responses.json').read_text())
        req = bundle['requests'][-1]; res = resp[-1]
        ar_cv = np.array(req['capture_metadata']['arkit_world_from_image_camera_cv'])
        scan_cv = np.eye(4); scan_cv[:3, :3] = res['rotation_world_camera']; scan_cv[:3, 3] = res['position_scan_m']
        T = scan_cv @ np.linalg.inv(ar_cv)                     # scanFromAR, as QuickLookGeometry.alignment
        ar_cam = np.array(req['capture_metadata']['arkit_world_from_camera'])
        scan_cam = T @ ar_cam                                   # RoutePreviewMath.scanPose
        position, forward = scan_cam[:3, 3], -scan_cam[:3, 2]
        engine = type('E', (), dict(manifest=dict(coordinate_frame_id='scan:b9dca4993d'), manifest_hash=res['map_manifest_sha256']))()
        router = server.DraftRouter(GRAPH, engine)
        r = server.route_payload(dict(destination_room='440', building_id='MGH', selected_floor=4,
            coordinate_frame_id='scan:b9dca4993d', map_manifest_sha256=res['map_manifest_sha256'],
            position_scan_m=position.tolist(), forward_scan=forward.tolist()), router)
        self.assertTrue(r['ok']); self.assertGreater(r['meters'], 8); self.assertLess(r['meters'], 16)
        inv = np.linalg.inv(T)                                  # RoutePreviewMath.arTopDown
        pts = [inv @ np.array([x, position[1], z, 1]) for x, z in r['path_scan_xz']]
        top = np.array([[p[0], -p[2]] for p in pts])
        phone = np.array([ar_cam[0, 3], -ar_cam[2, 3]])
        self.assertLess(np.linalg.norm(top[0] - phone), 0.05)  # route starts at the phone
        # arrow: RouteNavigator.topDownPose heading and RouteTracker.relativeBearing, aim 2 m ahead
        back = ar_cam[:3, 2]; heading = math.degrees(math.atan2(back[2], -back[0]))
        along = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(top, axis=0), axis=1))])
        aim = np.array([np.interp(2.0, along, top[:, 0]), np.interp(2.0, along, top[:, 1])])
        target = math.degrees(math.atan2(*(aim - phone)[::-1]))
        bearing = (heading - target + 180) % 360 - 180         # clockwise-positive
        self.assertLess(bearing, 0)                             # 440 is to the left in the photo
        self.assertGreater(bearing, -60)
        self.assertLess(abs(bearing + r['initial_turn_degrees']), 10)   # arrow and server turn agree
        self.__class__.result = dict(meters=r['meters'], arrow_bearing_deg=round(bearing, 1),
                                     server_initial_turn_deg=r['initial_turn_degrees'])
        print('\nreplay:', self.result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
