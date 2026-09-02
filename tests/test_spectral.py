import unittest
import pandas as pd
import sys
sys.path.insert(0, r"G:\My Drive\Python-G-drive\GeoQA")
from geoqa.validations.spectral import validate_spectral_indices, validate_band_radiance

class TestSpectral(unittest.TestCase):
    def test_ndvi_out_of_range(self):
        df = pd.DataFrame({'ndvi':[1.4], 'ndwi':[0.2]})
        issues = validate_spectral_indices(df)
        self.assertTrue(any(i.problem_name=='ndvi_out_of_range' for i in issues))

    def test_nan_flag(self):
        df = pd.DataFrame({'ndvi':[float('nan')], 'ndwi':[0.1]})
        issues = validate_spectral_indices(df)
        self.assertTrue(any(i.problem_name=='spectral_index_nan' for i in issues))

    def test_temporal_spike_tanager_case(self):
        # Tanager VR-5: s2proxy +0.252 vs s2_actual -0.080 => delta 0.332 >0.30
        df = pd.DataFrame({'ndvi':[0.252, -0.08], 'date':['2025-09-25','2025-11-05']})
        issues = validate_spectral_indices(df, date_col='date')
        self.assertTrue(any(i.problem_name=='ndvi_temporal_spike' for i in issues))

    def test_inconsistency(self):
        df = pd.DataFrame({'ndvi':[0.55], 'ndwi':[0.45]})
        issues = validate_spectral_indices(df)
        self.assertTrue(any(i.problem_name=='ndwi_ndvi_inconsistency' for i in issues))

    def test_negative_radiance(self):
        df = pd.DataFrame({'band_1':[-0.5], 'band_2':[120.0]})
        issues = validate_band_radiance(df)
        self.assertTrue(any(i.problem_name=='spectral_band_negative_radiance' for i in issues))

    def test_vector_noop(self):
        # Pure vector dataset without index columns should be no-op
        df = pd.DataFrame({'name':['a'], 'geometry':[None]})
        issues = validate_spectral_indices(df)
        self.assertEqual(len(issues), 0)

if __name__ == '__main__':
    unittest.main()
