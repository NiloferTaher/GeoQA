from __future__ import annotations

import unittest

import geopandas as gpd
from shapely.geometry import LineString, Point

from geoqa.validations.accuracy import coordinate_precision, xy_tolerance


class TestAccuracyValidation(unittest.TestCase):
    def test_coordinate_precision_is_more_permissive_for_broad_geographic_extent(self) -> None:
        broad = gpd.GeoDataFrame(
            geometry=[LineString([(0.12345678901, 0.0), (30.12345678901, 0.0)])],
            crs="EPSG:4326",
        )
        local = gpd.GeoDataFrame(
            geometry=[Point(0.12345678901, 0.12345678901)],
            crs="EPSG:4326",
        )

        broad_issues = coordinate_precision(broad)
        local_issues = coordinate_precision(local)

        self.assertEqual(len(broad_issues), 0)
        self.assertEqual(len(local_issues), 1)

    def test_xy_tolerance_is_more_permissive_for_broad_projected_extent(self) -> None:
        layer = gpd.GeoDataFrame(
            geometry=[LineString([(0, 0), (2_000_000, 0)])],
            crs="EPSG:3857",
        )
        layer.attrs["xy_tolerance"] = 1.0

        issues = xy_tolerance(layer)

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
