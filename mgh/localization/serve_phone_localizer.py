"""Local research backend for an existing phone app: POST /localize.

No route or floor-plan alignment is invented. Start on localhost by default;
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
import mgh_localizer as core
import phone_localizer as phone

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


def handler_for(engine):
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
                map_manifest_sha256=engine.manifest_hash, navigation_enabled=False))

        def do_POST(self):
            if self.path != '/localize':
                return self.respond(404, dict(error='Not found'))
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY_BYTES:
                    return self.respond(413, dict(error='Request body limit exceeded or missing length'))
                if self.headers.get_content_type() != 'application/json':
                    return self.respond(415, dict(error='Use application/json'))
                result = localize_payload(json.loads(self.rfile.read(length)), engine)
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
    args = parser.parse_args()
    engine = PhoneEngine(args.map, args.retrieval)
    server = HTTPServer((args.host, args.port), handler_for(engine))
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
