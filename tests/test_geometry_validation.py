from __future__ import annotations

import unittest

try:
    import geopandas as gpd
    from shapely.geometry import LineString
except ImportError:  # pragma: no cover
    gpd = None
    LineString = None

from geoqa.validations.geometry import (
    below_minimum_feature_length,
    duplicate_vertex,
    null_geometry,
    self_intersection,
)


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


@unittest.skipIf(gpd is None or LineString is None, "GeoPandas and Shapely are required for geometry validation tests.")
class TestBelowMinimumFeatureLength(unittest.TestCase):
    """CRS-aware meter measurement for below_minimum_feature_length (hostile campaign P0-1 / F-01)."""

    def _layer(self, coords_list, crs=None) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {"ID": list(range(1, len(coords_list) + 1)), "geometry": [LineString(c) for c in coords_list]},
            geometry="geometry",
            crs=crs,
        )

    def test_projected_crs_measured_in_meters(self) -> None:
        # 1.5-meter line in EPSG:32618 (raw length == meters).
        layer = self._layer([[(0, 0), (0, 1.5)]], crs="EPSG:32618")
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=1.51)), 1)
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=1.49)), 0)

    def test_geographic_crs_measured_geodesically_in_meters(self) -> None:
        # ~111.3-meter segment on the equator (0.001 deg longitude).
        layer = self._layer([[(0, 0), (0.001, 0)]], crs="EPSG:4326")
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=100.0)), 0)
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=200.0)), 1)

    def test_threshold_boundary_is_strictly_less_than(self) -> None:
        # Exactly-at-threshold must NOT flag; strictly-below must flag.
        layer = self._layer([[(0, 0), (0, 2.0)]], crs="EPSG:32618")
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=2.0)), 0)
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=2.001)), 1)

    def test_same_physics_classified_identically_across_crs(self) -> None:
        # Metamorphic invariant: the same physical line gives the same classification
        # whether declared in degrees (EPSG:4326) or meters (EPSG:32618).
        geographic = self._layer([[(0, 0), (0.001, 0)]], crs="EPSG:4326")
        projected = self._layer([[(0, 0), (111.32, 0)]], crs="EPSG:32618")
        for threshold in (50.0, 120.0, 200.0):
            self.assertEqual(
                len(below_minimum_feature_length(geographic, min_length=threshold)),
                len(below_minimum_feature_length(projected, min_length=threshold)),
            )

    def test_missing_or_uninterpretable_crs_reports_no_length_issues(self) -> None:
        no_crs = self._layer([[(1, 1), (1, 1)]], crs=None)
        self.assertEqual(below_minimum_feature_length(no_crs, min_length=0.1), [])

        class _BadCrsLayer:
            def __init__(self) -> None:
                self.crs = 424242
                self._frame = gpd.GeoDataFrame(
                    {"ID": [1], "geometry": [LineString([(0, 0), (0, 1)])]},
                    geometry="geometry",
                )

            def iterrows(self):
                return self._frame.iterrows()

        self.assertEqual(below_minimum_feature_length(_BadCrsLayer(), min_length=0.1), [])

    def test_zero_length_true_positive_in_geographic_crs(self) -> None:
        layer = self._layer([[(1, 1), (1, 1)]], crs="EPSG:4326")
        issues = below_minimum_feature_length(layer, min_length=0.1)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "below_minimum_feature_length")

    def test_multiline_uses_total_feature_length(self) -> None:
        # Two ~55.7 m parts on the equator would each be below 100 m alone but the
        # combined feature (~111.3 m) must not be flagged at a 100 m threshold.
        layer = self._layer([[(0, 0), (0.0005, 0), (0.001, 0)]], crs="EPSG:4326")
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=100.0)), 0)
        self.assertEqual(len(below_minimum_feature_length(layer, min_length=120.0)), 1)


if __name__ == "__main__":
    unittest.main()
