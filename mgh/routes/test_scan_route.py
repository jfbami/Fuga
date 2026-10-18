"""Contract tests for the draft scan-frame route. Synthetic tests check conventions;
replay tests use the SAME recording's poses, so they are self-consistency checks,
not localization or navigation accuracy evidence."""
import json, math, sys, unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan_route

GRAPH = HERE / 'scan_b9dca4993d_floor4_draft' / 'route_graph.json'


def quat_yaw(deg):
    """Camera upright, rotated by deg about +y (counter-clockwise from above)."""
    h = math.radians(deg) / 2
    return (0.0, math.sin(h), 0.0, math.cos(h))


def line_graph(n=10):
    nodes = [dict(id=i, x=float(i), z=0.0) for i in range(n)]
    edges = [dict(a=i, b=i + 1, meters=1.0, source='walked') for i in range(n - 1)]
    return dict(nodes=nodes, edges=edges, targets=[dict(id='T', room_key='R', node=n - 1)])


class Synthetic(unittest.TestCase):
    def test_identity_camera_forward_by_convention(self):
        f = scan_route.forward_xz((0, 0, 0, 1))
        self.assertAlmostEqual(f[0], 0); self.assertAlmostEqual(f[1], 1)        # OpenCV: +Z
        f = scan_route.forward_xz((0, 0, 0, 1), 'arkit')
        self.assertAlmostEqual(f[0], 0); self.assertAlmostEqual(f[1], -1)       # ARKit: -Z
        with self.assertRaises(ValueError): scan_route.forward_xz((0, 0, 0, 1), 'other')

    def test_yaw_left_90_faces_minus_x(self):
        f = scan_route.forward_xz(quat_yaw(90), 'arkit')
        self.assertAlmostEqual(f[0], -1, places=6); self.assertAlmostEqual(f[1], 0, places=6)

    def test_turn_sign(self):
        g = line_graph()   # route runs toward +x
        facing_minus_z = scan_route.plan(g, (0, 0), (0, -1), 'R')
        self.assertAlmostEqual(facing_minus_z['initial_turn_degrees'], -90, delta=1)   # +x is to the right
        facing_plus_z = scan_route.plan(g, (0, 0), (0, 1), 'R')
        self.assertAlmostEqual(facing_plus_z['initial_turn_degrees'], 90, delta=1)
        ahead = scan_route.plan(g, (0, 0), (1, 0), 'R')
        self.assertAlmostEqual(ahead['initial_turn_degrees'], 0, delta=1)

    def test_off_map_and_unknown_room_refused(self):
        g = line_graph()
        self.assertFalse(scan_route.plan(g, (0, 10), (1, 0), 'R')['ok'])
        self.assertFalse(scan_route.plan(g, (0, 0), (1, 0), 'MGH:4:420')['ok'])

    def test_path_length(self):
        r = scan_route.plan(line_graph(), (0, 0.5), (1, 0), 'R')
        self.assertTrue(r['ok']); self.assertAlmostEqual(r['meters'], 9.5, places=2)


@unittest.skipUnless(GRAPH.exists(), 'private graph not built')
class DraftGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = scan_route.load(GRAPH)

    def test_marked_draft_and_disabled(self):
        g = self.g
        self.assertEqual(g['status'], 'draft_unverified'); self.assertFalse(g['routing_enabled'])
        self.assertEqual(g['doorway_anchors_verified'], 0); self.assertFalse(g['registered_to_floor_plan'])
        self.assertEqual(sorted(t['room_key'] for t in g['targets']), ['MGH:4:416', 'MGH:4:430', 'MGH:4:440'])
        self.assertTrue(all(not t['doorway_verified'] and t['kind'] == 'sign_viewpoint_not_doorway' for t in g['targets']))

    def test_all_targets_connected_and_near_signs(self):
        for t in self.g['targets']:
            self.assertLess(t['sign_to_node_m'], 2.5)
            for u in self.g['targets']:
                path, m = scan_route.shortest_path(self.g, t['node'], u['node'])
                self.assertIsNotNone(path)

    def test_route_not_shorter_than_straight_line(self):
        xz = {n['id']: np.array([n['x'], n['z']]) for n in self.g['nodes']}
        for t in self.g['targets']:
            for u in self.g['targets']:
                _, m = scan_route.shortest_path(self.g, t['node'], u['node'])
                self.assertGreaterEqual(m + 1e-6, np.linalg.norm(xz[t['node']] - xz[u['node']]))

    def test_sign_frames_face_their_signs(self):
        """The recorded frames that photographed each sign must face it (pins the axis convention)."""
        odo = HERE / 'scan_b9dca4993d_floor4_draft' / 'sign_view_poses.json'
        for t in self.g['targets']:
            pose = json.loads(odo.read_text())[t['room_key']]
            f = np.array(scan_route.forward_xz(pose['quaternion_xyzw']))
            s = np.array(t['sign_xz']) - np.array(pose['xz'])
            self.assertGreater(f @ s / np.linalg.norm(s), math.cos(math.radians(30)))

    def test_edges_short(self):
        self.assertLess(max(e['meters'] for e in self.g['edges']), 1.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
