"""Example draft routes starting from the SAME recording's camera poses (self-consistency
only; not independent localization or a walked navigation test)."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import scan_route
odo_path, out = Path(sys.argv[1]), HERE / 'scan_b9dca4993d_floor4_draft' / 'example_routes.json'
g = scan_route.load(HERE / 'scan_b9dca4993d_floor4_draft' / 'route_graph.json')
assert hashlib.sha256(odo_path.read_bytes()).hexdigest() == g['source']['odometry_sha256']
odo = scan_route.read_odometry(odo_path)
t = odo[:, 0] - odo[0, 0]
starts = {'top of STAIR 1 (t=55 s)': int(np.searchsorted(t, 55.0)), '416 sign view (row 7290)': 7290,
          '430 sign view (row 9859)': 9859, '440 sign view (row 10887)': 10887}
results = []
for name, row in starts.items():
    for room in ['MGH:4:416', 'MGH:4:430', 'MGH:4:440']:
        r = scan_route.plan(g, odo[row, [2, 4]], scan_route.forward_xz(odo[row, 5:9]), room)
        results.append(dict(start=name, odometry_row=row, destination=room, ok=r['ok'],
                            meters=r.get('meters'), initial_turn_degrees=r.get('initial_turn_degrees'),
                            snap_m=r.get('snap_m'), reason=r.get('reason')))
out.write_text(json.dumps(dict(note=__doc__.strip(), verified=False, results=results), indent=1))
for r in results: print(f"{r['start']:28s} -> {r['destination'][-3:]}: {r['meters']} m, turn {r['initial_turn_degrees']}, snap {r['snap_m']}")
