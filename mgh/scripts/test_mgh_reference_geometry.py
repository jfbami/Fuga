import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/MGH_Project/localization'))
from geometric_reference_audit import verify_pair


class ReferenceGeometryTests(unittest.TestCase):
    def test_known_nonplanar_projections_with_outliers(self):
        rng=np.random.default_rng(6)
        world=np.column_stack([rng.uniform(-2,2,100),rng.uniform(-1.3,1.3,100),rng.uniform(4,10,100)])
        k=np.array([[400,0,320],[0,400,240],[0,0,1.]])
        first=world@k.T;first=first[:,:2]/first[:,2:]
        second=(world-np.array([1,0,.1]))@k.T;second=second[:,:2]/second[:,2:]
        second+=rng.normal(0,.1,second.shape)
        second[-20:]=rng.uniform([0,0],[640,480],(20,2))
        result,mask=verify_pair(first,second,(640,480),(640,480))
        self.assertGreaterEqual(int(mask[:80].sum()),75)
        self.assertLess(int(mask[80:].sum()),8)
        self.assertFalse(result['accepted']);self.assertFalse(result['pose_usable_for_app'])

    def test_identical_planar_pattern_is_ambiguous_not_a_place_fix(self):
        rng=np.random.default_rng(2)
        p=rng.uniform([0,0],[640,480],(80,2))
        q=p*np.array([.85,.9])+np.array([20,15])
        result,_=verify_pair(p,q,(640,480),(640,480))
        self.assertTrue(result['planar_or_low_parallax_ambiguous'])
        self.assertFalse(result['navigation_enabled'])

    def test_few_matches_do_not_rank_or_accept(self):
        p=np.arange(12).reshape(6,2)
        result,_=verify_pair(p,p,(640,480),(640,480))
        self.assertEqual(result['coverage_weighted_score'],0)
        self.assertFalse(result['accepted'])

    def test_bad_points_and_dimensions_fail(self):
        p=np.zeros((10,2))
        with self.assertRaises(ValueError):verify_pair(p,p,(0,480),(640,480))
        p[0,0]=np.nan
        with self.assertRaises(ValueError):verify_pair(p,p,(640,480),(640,480))


if __name__=='__main__':unittest.main(verbosity=2)
