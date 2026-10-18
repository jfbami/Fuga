"""Local research backend for an existing phone app: POST /localize, optional POST /route.

No route or floor-plan alignment is invented. /route only serves a DRAFT route graph
in the same scan frame as the map when one is passed with --route-graph, and always
marks it unverified; it never enables guidance. Start on localhost by default;
use --host explicitly for a trusted development network.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
from PIL import Image
import sys

import mgh_localizer as core
import phone_localizer as phone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'routes'))
import scan_route

MAX_BODY_BYTES = 20 * 1024 * 1024


class PhoneEngine:
    def __init__(self, map_path, retrieval='legacy'):
        self.map_path = Path(map_path)
        self.manifest, self.references = core.load_map(self.map_path)
        self.extractor, self.matcher = core.setup_models()
        self.retrieval = retrieval
        self.manifest_hash = hashlib.sha256((self.map_path / 'manifest.json').read_bytes()).hexdigest()

    def localize(self, image, calibration, status):
        return phone.localize_phone(image, calibration, self.references, self.extractor,
                                     self.matcher, self.retrieval, status)

    def localize_for_context(self, image, calibration, status, building, floor):
        # Current visual maps cover the staircase recording, not the new floor-2/3
        # reconstructions. Do not silently search another floor or infer a floor from GPS.
        if building != 'MGH' or floor != 4 or self.manifest.get('scan_id') != 'b9dca4993d':
            return dict(accepted=False, pose_usable_for_app=False,
                        status='selected_floor_map_unavailable', supported_floors=[4])
        # Conservatively omit stairs/landings: reviewed continuous floor-4 corridor
        # segment begins after 48 s; 60 s is an exclusion margin, not a new alignment.
        references = [r for r in self.references if r['metadata']['capture_seconds'] >= 60]
        result = phone.localize_phone(image, calibration, references, self.extractor,
                                      self.matcher, self.retrieval, status)
        result['reference_context'] = 'MGH floor-4 corridor segment >=60s; no scan-to-plan registration'
        return result


def localize_payload(payload, engine):
    started = time.monotonic()
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object.')
    request_id = payload.get('request_id')
    capture_timestamp = payload.get('capture_timestamp')
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise ValueError('A request_id (1-128 characters) is required.')
    if isinstance(capture_timestamp, bool) or not isinstance(capture_timestamp, (int, float)) or not math.isfinite(capture_timestamp):
        raise ValueError('A finite capture_timestamp is required for frame association.')
    building, floor = payload.get('building_id'), payload.get('selected_floor')
    has_context = building is not None or floor is not None
    if has_context and (not isinstance(building, str) or not building or type(floor) is not int or floor not in {2, 3, 4}):
        raise ValueError('Context requires building_id and integer selected_floor (2, 3 or 4).')
    encoded = payload.get('image_base64')
    if not isinstance(encoded, str) or len(encoded) > MAX_BODY_BYTES:
        raise ValueError('Missing or oversized image.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError('Invalid image encoding.') from error
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 25_000_000:
            raise ValueError('Use a JPEG/PNG camera image, at most 25 megapixels.')
    parameters = payload.get('intrinsics')
    status = payload.get('calibration_status', 'missing')
    if status not in {'missing', 'verified', 'exif_estimate'}:
        raise ValueError('Invalid calibration_status.')
    if (parameters is None) != (status == 'missing'):
        raise ValueError('intrinsics and calibration_status disagree.')
    if parameters is not None:
        required = ['width', 'height', 'fx', 'fy', 'cx', 'cy']
        if not isinstance(parameters, dict) or any(k not in parameters for k in required):
            raise ValueError('Incomplete intrinsics.')
        if any(isinstance(parameters[k], bool) or not isinstance(parameters[k], (int, float)) or not math.isfinite(parameters[k]) for k in required):
            raise ValueError('Intrinsics must contain finite numbers.')
    image, calibration = phone.prepare_query(io.BytesIO(raw), parameters)
    if has_context:
        if not hasattr(engine, 'localize_for_context'):
            raise ValueError('This engine does not support building/floor context.')
        result = engine.localize_for_context(image, calibration, status, building, floor)
    else:
        result = engine.localize(image, calibration, status)
    # Even a custom engine cannot promote an uncalibrated result at this boundary.
    trusted = bool(result.get('accepted') and result.get('pose_usable_for_app') and status == 'verified')
    result.update(accepted=trusted, pose_usable_for_app=trusted,
        request_id=request_id, capture_timestamp=capture_timestamp,
        query_image_sha256=hashlib.sha256(raw).hexdigest(),
        map_manifest_sha256=engine.manifest_hash,
        coordinate_frame_id=engine.manifest['coordinate_frame_id'],
        pose_timestamp_meaning='Pose belongs to capture_timestamp, not response time.',
        request_runtime_seconds=time.monotonic() - started,
        registered_to_building=False, route_available=False, navigation_enabled=False)
    if has_context:
        result.update(building_id=building, selected_floor=floor)
    return result


class DraftRouter:
    """Serves one draft scan-frame route graph; refuses anything outside its frame/floor."""
    def __init__(self, graph_path, engine):
        raw = Path(graph_path).read_bytes()
        self.graph = json.loads(raw)
        self.graph_hash = hashlib.sha256(raw).hexdigest()
        if self.graph.get('coordinate_frame_id') != engine.manifest['coordinate_frame_id']:
            raise ValueError('Route graph and recognition map use different coordinate frames.')
        self.map_hash = engine.manifest_hash
        self.frame = engine.manifest['coordinate_frame_id']


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 3 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(f'{name} must be three finite numbers.')
    return [float(v) for v in value]


def route_payload(payload, router):
    if router is None:
        return dict(ok=False, status='route_graph_not_loaded', verified=False, guidance_allowed=False)
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object.')
    if payload.get('coordinate_frame_id') != router.frame or payload.get('map_manifest_sha256') != router.map_hash:
        raise ValueError('Pose is not from this server recognition map.')
    if payload.get('building_id') != 'MGH' or payload.get('selected_floor') != router.graph.get('floor'):
        return dict(ok=False, status='no_draft_route_for_floor', verified=False, guidance_allowed=False)
    room = payload.get('destination_room')
    if not isinstance(room, str) or not room.isdigit() or len(room) > 5:
        raise ValueError('destination_room must be a room number such as "440".')
    position = _vector(payload.get('position_scan_m'), 'position_scan_m')
    forward = _vector(payload.get('forward_scan'), 'forward_scan')
    horizontal = math.hypot(forward[0], forward[2])
    plan = scan_route.plan(router.graph, (position[0], position[2]),
                           (forward[0] / horizontal, forward[2] / horizontal) if horizontal > 0.1 else None,
                           f'MGH:{router.graph["floor"]}:{room}')
    common = dict(destination_room=room, coordinate_frame_id=router.frame, map_manifest_sha256=router.map_hash,
                  route_graph_sha256=router.graph_hash, route_status=router.graph.get('status'),
                  verified=False, guidance_allowed=False,
                  note='Draft preview: corridors are the scan walk, the target is a sign viewpoint, not a doorway.')
    if not plan['ok']:
        return dict(ok=False, status='no_route', reason=plan['reason'], **common)
    nodes = {n['id']: n for n in router.graph['nodes']}
    path = [[position[0], position[2]]] + [[nodes[i]['x'], nodes[i]['z']] for i in plan['path']]
    return dict(ok=True, status='draft_route_preview', meters=plan['meters'], snap_m=plan['snap_m'],
                initial_turn_degrees=plan['initial_turn_degrees'], target_id=plan['target'],
                path_scan_xz=path, **common)


def handler_for(engine, router=None):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, value):
            body = json.dumps(value, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != '/health':
                return self.respond(404, dict(error='Not found'))
            self.respond(200, dict(status='ready', coordinate_frame_id=engine.manifest['coordinate_frame_id'],
                map_manifest_sha256=engine.manifest_hash, navigation_enabled=False,
                draft_route_loaded=router is not None))

        def do_POST(self):
            if self.path not in ('/localize', '/route'):
                return self.respond(404, dict(error='Not found'))
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY_BYTES:
                    return self.respond(413, dict(error='Request body limit exceeded or missing length'))
                if self.headers.get_content_type() != 'application/json':
                    return self.respond(415, dict(error='Use application/json'))
                body = json.loads(self.rfile.read(length))
                result = localize_payload(body, engine) if self.path == '/localize' else route_payload(body, router)
                self.respond(200, result)
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.respond(400, dict(error=str(error)))

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=core.DEFAULT_MAP)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--retrieval', choices=['legacy', 'mutual_nn'], default='legacy')
    parser.add_argument('--route-graph', type=Path, default=None,
                        help='Optional DRAFT scan-frame route graph for preview only (private data).')
    args = parser.parse_args()
    engine = PhoneEngine(args.map, args.retrieval)
    router = DraftRouter(args.route_graph, engine) if args.route_graph else None
    server = HTTPServer((args.host, args.port), handler_for(engine, router))
    server.timeout = 60
    print(f'Phone localization backend ready at http://{args.host}:{args.port}; navigation disabled.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
