import base64,copy,hashlib,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/MGH_Project/localization'))
import serve_phone_localizer as service
import review_quicklook as review


def fixture():
    data=io.BytesIO();Image.new('RGB',(48,64)).save(data,format='PNG');raw=data.getvalue()
    requests=[];responses=[]
    for i in range(3):
        ar=np.eye(4);ar[0,3]=i
        requests.append(dict(request_id=f'frame-{i}',capture_timestamp=100+i,session_id='session',building_id='MGH',selected_floor=4,
            image_base64=base64.b64encode(raw).decode(),calibration_status='verified',
            intrinsics=dict(width=48,height=64,fx=50,fy=50,cx=24,cy=32,distortion=[]),
            capture_metadata=dict(tracking_state='normal',arkit_world_from_image_camera_cv=ar.tolist())))
        responses.append(dict(request_id=f'frame-{i}',capture_timestamp=100+i,building_id='MGH',selected_floor=4,
            accepted=True,pose_usable_for_app=True,calibration_status='verified',query_image_sha256=hashlib.sha256(raw).hexdigest(),
            map_manifest_sha256='a'*64,coordinate_frame_id='scan:b9dca4993d',rotation_world_camera=np.eye(3).tolist(),position_scan_m=[5+i,0,0]))
    return dict(format='MGH quick-look diagnostic v1',session_id='session',selected_floor=4,requests=requests,responses=responses)


class QuickLookTests(unittest.TestCase):
    def test_moving_camera_gives_constant_capture_time_alignment(self):
        r=review.review_bundle(fixture(),'a'*64)
        self.assertEqual(r['status'],'consistent_alignment_hypothesis')
        self.assertAlmostEqual(r['candidate_scan_from_arkit_world'][0][3],5)
        self.assertFalse(r['navigation_enabled']);self.assertFalse(r['pose_usable_for_app'])

    def test_one_wrong_pose_is_excluded(self):
        b=fixture();b['responses'][2]['position_scan_m']=[99,0,0]
        r=review.review_bundle(b,'a'*64)
        self.assertEqual(r['support_request_ids'],['frame-0','frame-1'])

    def test_disagreeing_poses_do_not_locate(self):
        b=fixture()
        for i,r in enumerate(b['responses']):r['position_scan_m']=[10*i,0,0]
        self.assertNotIn('candidate_scan_from_arkit_world',review.review_bundle(b,'a'*64))

    def test_late_or_wrong_image_responses_are_rejected(self):
        b=fixture()
        b['responses'][0]['capture_timestamp']=999
        b['responses'][1]['query_image_sha256']='b'*64
        b['responses'][2]['map_manifest_sha256']='b'*64
        self.assertEqual(review.review_bundle(b,'a'*64)['candidate_frames'],0)

    def test_estimated_calibration_or_other_floor_cannot_locate(self):
        for field,value in [('calibration_status','exif_estimate'),('selected_floor',3)]:
            b=fixture()
            for r in b['requests']:r[field]=value
            self.assertEqual(review.review_bundle(b,'a'*64)['candidate_frames'],0)

    def test_scaled_or_reflected_poses_rejected(self):
        for value in [2,-1]:
            b=fixture()
            for r in b['requests']:r['capture_metadata']['arkit_world_from_image_camera_cv'][0][0]=value
            self.assertEqual(review.review_bundle(b,'a'*64)['candidate_frames'],0)

    def test_duplicate_frames_are_not_multiple_support(self):
        b=fixture();b['requests'][1]=copy.deepcopy(b['requests'][0])
        with self.assertRaises(ValueError):review.review_bundle(b,'a'*64)

    def test_short_timestamp_span_not_accepted(self):
        b=fixture()
        for i in range(3):
            b['requests'][i]['capture_timestamp']=100+i*.1
            b['responses'][i]['capture_timestamp']=100+i*.1
        self.assertEqual(review.review_bundle(b,'a'*64)['status'],'starting_location_unconfirmed')

    def test_camera_rotation_preserves_projection_and_world_rays(self):
        # Independently project 3D points, rotate actual pixel coordinates, and
        # compare with the documented portrait calibration/axis transformation.
        w,h=1920,1440;fx,fy,cx,cy=1450,1440,920,650
        native=np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
        portrait=np.array([[fy,0,h-1-cy],[0,fx,cx],[0,0,1.]])
        rotate=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
        ar_from_cv=np.diag([1,-1,-1])
        ar_from_portrait=np.array([[0,1,0],[1,0,0],[0,0,-1.]])
        for point in [np.array([.5,.2,3]),np.array([-.4,-.7,2]),np.array([0,0,1.])]:
            uv=native@point;uv/=uv[2]
            expected=np.array([h-1-uv[1],uv[0],1])
            actual=portrait@rotate@point;actual/=actual[2]
            np.testing.assert_allclose(expected,actual)
            np.testing.assert_allclose(ar_from_cv@point,ar_from_portrait@rotate@point)

    def engine(self):
        engine=service.PhoneEngine.__new__(service.PhoneEngine)
        engine.manifest={'scan_id':'b9dca4993d','coordinate_frame_id':'scan:b9dca4993d'}
        engine.manifest_hash='a'*64;engine.extractor=None;engine.matcher=None;engine.retrieval='legacy'
        engine.references=[{'metadata':{'capture_seconds':t}} for t in [10,45,59,60,100]]
        return engine

    def test_floor_2_3_do_not_run_floor_4_matcher(self):
        for floor in [2,3]:
            payload=fixture()['requests'][0];payload['selected_floor']=floor
            with patch.object(service.phone,'localize_phone',side_effect=AssertionError('Wrong-floor inference')):
                r=service.localize_payload(payload,self.engine())
            self.assertEqual(r['status'],'selected_floor_map_unavailable')
            self.assertEqual(r['selected_floor'],floor);self.assertFalse(r['accepted'])

    def test_context_omits_stair_views_without_changing_thresholds(self):
        with patch.object(service.phone,'localize_phone',return_value=dict(accepted=False,pose_usable_for_app=False)) as fn:
            r=service.localize_payload(fixture()['requests'][0],self.engine())
        self.assertEqual([x['metadata']['capture_seconds'] for x in fn.call_args.args[2]],[60,100])
        self.assertEqual(r['building_id'],'MGH');self.assertFalse(r['navigation_enabled'])

    def test_partial_or_invalid_context_is_rejected(self):
        for context in [dict(selected_floor=True),dict(selected_floor=5),dict(building_id=None)]:
            b=fixture()['requests'][0];b.update(context)
            with self.assertRaises(ValueError):service.localize_payload(b,self.engine())


if __name__=='__main__':unittest.main(verbosity=2)
