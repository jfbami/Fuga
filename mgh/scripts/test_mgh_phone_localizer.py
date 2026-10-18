import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outputs/MGH_Project/localization'))
import numpy as np
from PIL import Image
import phone_localizer as phone


class PhoneContractTests(unittest.TestCase):
    def test_mutual_counts_do_not_use_cross_image_runner_up(self):
        query = np.array([[0., 0.], [10., 0.], [0., 10.]], dtype=np.float32)
        references = [dict(features=dict(descriptors=query.copy())),
                      dict(features=dict(descriptors=query.copy())),
                      dict(features=dict(descriptors=np.array([[100., 100.]], dtype=np.float32)))]
        order, scores = phone.rank_mutual_nn(query, references)
        self.assertEqual(scores, [3, 3, 1])
        self.assertEqual(order, [0, 1, 2])

    def test_estimated_calibration_cannot_be_an_app_pose(self):
        candidate = dict(accepted=True, position_scan_m=[1,2,3], rotation_world_camera=np.eye(3).tolist())
        with patch.object(phone.core, 'localize', return_value=candidate):
            result = phone.localize_phone(None, np.eye(3), [], None, None, 'legacy', 'exif_estimate')
        self.assertTrue(result['geometric_consensus_accepted'])
        self.assertFalse(result['accepted'])
        self.assertFalse(result['pose_usable_for_app'])
        self.assertNotIn('position_scan_m', result)

    def test_intrinsics_use_both_resize_axes_and_reject_mismatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            path = Path(folder)/'photo.png'
            Image.new('RGB', (301,403)).save(path)
            parameters = dict(width=301,height=403,fx=350,fy=351,cx=150,cy=201)
            image, calibration = phone.prepare_query(path, parameters)
            self.assertAlmostEqual(calibration[0,0], 350*image.shape[1]/301)
            self.assertAlmostEqual(calibration[1,1], 351*image.shape[0]/403)
            with self.assertRaises(ValueError):
                phone.prepare_query(path, dict(parameters,width=403,height=301))


if __name__ == '__main__':
    unittest.main()
