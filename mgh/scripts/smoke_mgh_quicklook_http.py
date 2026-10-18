"""Real-model localhost request with explicit floor context; not an iPhone validation."""
import base64,http.client,json,sys,threading
from http.server import HTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'outputs/MGH_Project/localization'
sys.path.insert(0,str(LOCAL))
import serve_phone_localizer as service
engine=service.PhoneEngine(LOCAL/'visual_map_v4_low_rotation')
server=HTTPServer(('127.0.0.1',0),service.handler_for(engine))
thread=threading.Thread(target=server.handle_request);thread.start()
photo=LOCAL/'evaluation_independent_phone_430_440'
image=ROOT/'outputs/MGH_Project/capture/independent_phone_20261017/normalized/IMG_5385.png'
payload=dict(request_id='quicklook-context-smoke',capture_timestamp=123.75,building_id='MGH',selected_floor=4,
    image_base64=base64.b64encode(image.read_bytes()).decode(),calibration_status='exif_estimate',
    intrinsics=json.loads((photo/'IMG_5385_estimated_intrinsics.json').read_text()))
client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=120)
try:
    client.request('POST','/localize',json.dumps(payload),{'Content-Type':'application/json'})
    reply=client.getresponse();result=json.loads(reply.read())
    assert reply.status==200 and result['request_id']==payload['request_id']
    assert result['capture_timestamp']==123.75 and result['selected_floor']==4
    assert not result['accepted'] and not result['pose_usable_for_app'] and not result['navigation_enabled']
    assert 'reference_context' in result
    out=LOCAL/'quicklook_integration_checks'
    out.mkdir(exist_ok=True)
    (out/'real_http_smoke.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(http_status=reply.status,status=result['status'],accepted=result['accepted'],selected_floor=4,phone_validation=False)))
finally:
    client.close();thread.join(timeout=120);server.server_close()
