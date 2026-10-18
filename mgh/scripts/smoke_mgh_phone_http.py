"""One real image/model HTTP request; always close the test server."""
import base64
import http.client
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'outputs/MGH_Project/localization'
sys.path.insert(0,str(LOCAL))
from PIL import Image
import serve_phone_localizer as service

OUT=LOCAL/'evaluation_independent_phone_430_440'
image=OUT/'IMG_5385_request.jpg'
Image.open(ROOT/'outputs/MGH_Project/capture/independent_phone_20261017/normalized/IMG_5385.png').save(image,quality=94)
payload=dict(request_id='independent-430-http-smoke',capture_timestamp=123.456,
    image_base64=base64.b64encode(image.read_bytes()).decode(),calibration_status='exif_estimate',
    intrinsics=json.loads((OUT/'IMG_5385_estimated_intrinsics.json').read_text()))
engine=service.PhoneEngine(LOCAL/'visual_map_v3','legacy')
server=HTTPServer(('127.0.0.1',0),service.handler_for(engine))
thread=threading.Thread(target=server.handle_request)
thread.start()
client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=180)
try:
    client.request('POST','/localize',json.dumps(payload),{'Content-Type':'application/json'})
    response=client.getresponse()
    result=json.loads(response.read())
    assert response.status==200,result
    assert result['request_id']==payload['request_id'] and result['capture_timestamp']==payload['capture_timestamp']
    assert not result['pose_usable_for_app'] and not result['navigation_enabled']
    service.core.dump_json(OUT/'http_smoke_result.json',dict(http_status=response.status,result=result,server_closed_after_test=True))
    print(json.dumps({k:result[k] for k in ['request_id','geometric_consensus_accepted','pose_usable_for_app','consistent_support_frames']},indent=2))
finally:
    client.close();thread.join(timeout=180);server.server_close()
