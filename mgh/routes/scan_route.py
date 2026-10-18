"""Draft walking route inside one scan's own coordinate frame.

The corridor graph is the path the scanning phone actually walked (recorded camera
positions), resampled and joined where the walk revisits the same spot. Destinations
are depth-backed SIGN points snapped to the nearest walked node. Nothing here is a
verified doorway, a floor-plan registration or validated navigation.

Scan frame: Stray Scanner/ARKit world, metres, +y up (gravity), no scale correction.
Odometry rows are camera-to-world: position (x, y, z) and quaternion (qx, qy, qz, qw).
The rotation uses OpenCV camera axes (x right, y down, camera looks along +Z), checked on
the frames that photographed the 416/430/440 signs; ARKit's own camera looks along -Z.
"""
import heapq, json, math
import numpy as np

NODE_SPACING_M = 0.75     # resample walked path every 0.75 m of horizontal travel
REVISIT_JOIN_M = 0.8      # join non-consecutive nodes the walk passed within 0.8 m of
TRACKING_JUMP_M = 0.5     # a single 60 Hz pose step longer than this breaks the path
MAX_SNAP_M = 3.0          # a camera farther than this from the walked path is off-map
JOIN_RADIUS_M = 2.0       # the camera may join the walked path at any node this close
SMOOTH_ROWS = 61          # ~1 s centred moving average removes hand/step sway (60 Hz poses)


def read_odometry(path):
    rows = np.genfromtxt(path, delimiter=',', skip_header=1, usecols=range(9))
    return rows  # timestamp, frame, x, y, z, qx, qy, qz, qw


def forward_xz(q, camera_axes='opencv'):
    """Horizontal unit vector the camera faces: +Z for OpenCV axes, -Z for ARKit axes."""
    qx, qy, qz, qw = q
    sign = 1.0 if camera_axes == 'opencv' else -1.0 if camera_axes == 'arkit' else None
    if sign is None:
        raise ValueError(camera_axes)
    # third column of the rotation matrix
    fx = sign * 2 * (qx * qz + qw * qy)
    fz = sign * (1 - 2 * (qx * qx + qy * qy))
    n = math.hypot(fx, fz)
    return (fx / n, fz / n) if n > 1e-6 else None


def build_graph(odometry, start_s, min_y, signs):
    t = odometry[:, 0] - odometry[0, 0]
    keep = (t >= start_s) & (odometry[:, 3] >= min_y)
    rows = np.flatnonzero(keep)
    # Smoothed horizontal position for the graph; raw rows still define continuity/jumps.
    k = np.ones(SMOOTH_ROWS) / SMOOTH_ROWS
    pad = SMOOTH_ROWS // 2
    smooth = {}
    for seg in np.split(rows, np.flatnonzero(np.diff(rows) != 1) + 1):
        if len(seg) == 0:
            continue
        xz_seg = odometry[seg][:, [2, 4]]
        padded = np.pad(xz_seg, ((pad, pad), (0, 0)), mode='edge')
        avg = np.column_stack([np.convolve(padded[:, c], k, mode='valid') for c in range(2)])
        smooth.update(zip(seg.tolist(), avg))
    nodes, edges, breaks = [], set(), 0
    last_xz, travelled, prev_node, prev_row = None, 0.0, None, None
    for r in rows:
        xz = smooth[int(r)]
        if prev_row is not None:
            step = np.linalg.norm(odometry[r, 2:5] - odometry[prev_row, 2:5])
            if r != prev_row + 1 or step > TRACKING_JUMP_M:
                prev_node, last_xz, travelled = None, None, 0.0
                breaks += 1
        if last_xz is not None:
            travelled += float(np.linalg.norm(xz - last_xz))
        last_xz = xz
        prev_row = r
        if prev_node is None or travelled >= NODE_SPACING_M:
            nodes.append(dict(id=len(nodes), x=float(xz[0]), z=float(xz[1]),
                              camera_y=float(odometry[r, 3]), odometry_row=int(r),
                              seconds=round(float(t[r]), 3)))
            if prev_node is not None:
                edges.add((prev_node, len(nodes) - 1))
            prev_node, travelled = len(nodes) - 1, 0.0
    xz = np.array([[n['x'], n['z']] for n in nodes])
    sequential = set(edges)
    for i in range(len(nodes)):
        d = np.linalg.norm(xz - xz[i], axis=1)
        for j in np.flatnonzero(d < REVISIT_JOIN_M):
            if j > i + 2 and (i, j) not in sequential:
                edges.add((i, int(j)))
    edge_list = [dict(a=a, b=b, meters=round(float(np.linalg.norm(xz[a] - xz[b])), 3),
                      source='walked' if (a, b) in sequential else 'revisit_join') for a, b in sorted(edges)]
    targets = []
    for s in signs:
        p = np.array([s['position_scan_m'][0], s['position_scan_m'][2]])
        d = np.linalg.norm(xz - p, axis=1)
        k = int(np.argmin(d))
        targets.append(dict(id=s['room_key'] + ':sign-viewpoint', room_key=s['room_key'], label=s['label'],
                            node=k, sign_xz=[float(p[0]), float(p[1])], sign_to_node_m=round(float(d[k]), 3),
                            source_landmark=s['id'], kind='sign_viewpoint_not_doorway',
                            doorway_verified=False, placement_verified=False))
    return dict(nodes=nodes, edges=edge_list, targets=targets, path_breaks=breaks)


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _adjacency(graph):
    adj = {n['id']: [] for n in graph['nodes']}
    for e in graph['edges']:
        adj[e['a']].append((e['b'], e['meters']))
        adj[e['b']].append((e['a'], e['meters']))
    return adj


def shortest_path(graph, start, goal):
    adj, dist, prev, heap = _adjacency(graph), {start: 0.0}, {}, [(0.0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == goal:
            break
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj[u]:
            if d + w < dist.get(v, math.inf):
                dist[v], prev[v] = d + w, u
                heapq.heappush(heap, (d + w, v))
    if goal not in dist:
        return None, math.inf
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return path[::-1], dist[goal]


def distances_to(graph, goal):
    """Walking distance from every node to `goal`, and each node's next step toward it."""
    adj, dist, nxt, heap = _adjacency(graph), {goal: 0.0}, {}, [(0.0, goal)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, math.inf):
            continue
        for v, w in adj[u]:
            if d + w < dist.get(v, math.inf):
                dist[v], nxt[v] = d + w, u
                heapq.heappush(heap, (d + w, v))
    return dist, nxt


def plan(graph, camera_xz, camera_forward_xz, room_key):
    """Route from a scan-frame camera position to a room's sign viewpoint.

    Returns None-valued fields with a reason when off-map or unknown; never guesses.
    initial_turn_degrees: + means turn left (counter-clockwise seen from above, +y up).
    """
    target = next((t for t in graph['targets'] if t['room_key'] == room_key), None)
    if target is None:
        return dict(ok=False, reason=f'no draft target for {room_key}')
    xz = np.array([[n['x'], n['z']] for n in graph['nodes']])
    d = np.linalg.norm(xz - np.asarray(camera_xz), axis=1)
    nearest = int(np.argmin(d))
    if d[nearest] > MAX_SNAP_M:
        return dict(ok=False, reason=f'camera is {d[nearest]:.1f} m from the walked path (limit {MAX_SNAP_M} m)')
    to_goal, nxt = distances_to(graph, target['node'])
    # Join the walked path where the WHOLE trip is shortest, not at the nearest node: the
    # scan walk wiggles, and the nearest node can sit behind you, adding a backtrack.
    near = [int(i) for i in np.flatnonzero(d <= max(JOIN_RADIUS_M, d[nearest])) if int(i) in to_goal]
    if not near:
        return dict(ok=False, reason='target not connected to the walked path')
    start = min(near, key=lambda i: d[i] + to_goal[i])
    path, meters = [start], to_goal[start]
    while path[-1] != target['node']:
        path.append(nxt[path[-1]])
    # aim at the first path point at least 2 m ahead so a jittery first node doesn't set the turn
    aim = next((xz[p] for p in path if np.linalg.norm(xz[p] - camera_xz) >= 2.0), xz[path[-1]])
    turn = None
    if camera_forward_xz is not None and np.linalg.norm(aim - camera_xz) > 0.3:
        a = aim - np.asarray(camera_xz)
        f = np.asarray(camera_forward_xz)
        # seen from above with +y up, (x, z) is a left-handed view: left turn = cross(f, a) < 0
        cross = f[0] * a[1] - f[1] * a[0]
        turn = -math.degrees(math.atan2(cross, float(f @ a)))
    return dict(ok=True, start_node=start, snap_m=round(float(d[start]), 3), path=path,
                meters=round(meters + float(d[start]), 2), initial_turn_degrees=None if turn is None else round(turn, 1),
                target=target['id'], verified=False)
