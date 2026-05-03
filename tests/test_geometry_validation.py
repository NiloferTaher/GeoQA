from __future__ import annotations

import unittest

try:
    import geopandas as gpd
    from shapely.geometry import LineString
except ImportError:  # pragma: no cover
    gpd = None
    LineString = None

from geoqa.validations.geometry import duplicate_vertex, null_geometry, self_intersection


@unittest.skipIf(gpd is None or LineString is None, "GeoPandas and Shapely are required for geometry validation tests.")
class TestGeometryValidation(unittest.TestCase):
    def test_null_geometry(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1, 2], "geometry": [None, LineString([(0, 0), (1, 1)])]},
            geometry="geometry",
        )
        issues = null_geometry(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "null_geometry")
        self.assertEqual(issues[0].feature_id, 1)

    def test_self_intersection(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [11], "geometry": [LineString([(0, 0), (1, 1), (1, 0), (0, 1)])]},
            geometry="geometry",
        )
        issues = self_intersection(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "self_intersection")
        self.assertEqual(issues[0].feature_id, 11)

    def test_duplicate_vertex(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [21], "geometry": [LineString([(0, 0), (1, 1), (1, 1), (2, 2)])]},
            geometry="geometry",
        )
        issues = duplicate_vertex(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "duplicate_vertex")
        self.assertEqual(issues[0].feature_id, 21)


if __name__ == "__main__":
    unittest.main()
