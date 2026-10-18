import base64
import http.client
import io
import json
import sys
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/MGH_Project/localization'))
from PIL import Image
import serve_phone_localizer as service


class FakeEngine:
    manifest={'coordinate_frame_id':'scan:test'}
    manifest_hash='test-manifest'

    def localize(self,image,calibration,status):
        return dict(accepted=True,pose_usable_for_app=True)


class ServiceTests(unittest.TestCase):
    def payload(self):
        data=io.BytesIO()
        Image.new('RGB',(48,64)).save(data,format='PNG')
        return dict(request_id='camera-frame-17',capture_timestamp=123.5,
            image_base64=base64.b64encode(data.getvalue()).decode())

    def test_frame_identity_is_echoed_and_missing_calibration_cannot_guide(self):
        result=service.localize_payload(self.payload(),FakeEngine())
        self.assertEqual(result['request_id'],'camera-frame-17')
        self.assertEqual(result['capture_timestamp'],123.5)
        self.assertFalse(result['accepted'])
        self.assertFalse(result['navigation_enabled'])
        self.assertFalse(result['route_available'])

    def test_invalid_matrix_and_capture_timestamp_fail(self):
        payload=self.payload()
        payload.update(calibration_status='verified',intrinsics=dict(width=48,height=64,fx=0,fy=50,cx=24,cy=32))
        with self.assertRaises(ValueError): service.localize_payload(payload,FakeEngine())
        payload=self.payload();payload['capture_timestamp']=float('nan')
        with self.assertRaises(ValueError): service.localize_payload(payload,FakeEngine())

    def test_real_http_round_trip(self):
        server=HTTPServer(('127.0.0.1',0),service.handler_for(FakeEngine()))
        thread=threading.Thread(target=server.handle_request)
        thread.start()
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
        try:
            connection.request('POST','/localize',json.dumps(self.payload()),{'Content-Type':'application/json'})
            response=connection.getresponse()
            result=json.loads(response.read())
            self.assertEqual(response.status,200)
            self.assertEqual(result['coordinate_frame_id'],'scan:test')
            self.assertFalse(result['pose_usable_for_app'])
        finally:
            connection.close();thread.join(timeout=10);server.server_close()


if __name__=='__main__': unittest.main()
