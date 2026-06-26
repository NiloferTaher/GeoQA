from __future__ import annotations

import json
import unittest

import pandas as pd
from shapely.geometry import LineString, MultiLineString, Polygon

from geoqa.interactive_validation import validate_layer as interactive_validate_layer
from geoqa.validations.accuracy import coordinate_precision, positional_accuracy, xy_tolerance
from geoqa.validations.attributes import domain_range_checks, required_nulls, uniqueness
from geoqa.validations.crs import invalid_crs, missing_crs
from geoqa.validations.integrity import missing_spatial_index, non_rfc7946_geojson, outdated_index
from geoqa.validations.metadata import incomplete_metadata, missing_metadata_fields
from geoqa.validations.topology import (
    boundary_mismatch_against_reference,
    duplicate_geometry_same_layer,
    feature_within_feature,
    line_dangle,
    line_intersection_same_layer,
    polygon_gap_same_layer,
    polygon_overlap_same_layer,
    suspicious_near_miss_endpoints,
    unsnapped_endpoints_within_tolerance,
)


class FakeGeometry:
    geom_type = "Point"

    def __init__(self, x: float, y: float) -> None:
        self.coords = [(x, y)]

    def distance(self, other: "FakeGeometry") -> float:
        dx = self.coords[0][0] - other.coords[0][0]
        dy = self.coords[0][1] - other.coords[0][1]
        return (dx**2 + dy**2) ** 0.5

    def overlaps(self, other: "FakeGeometry") -> bool:
        return False

    def within(self, other: "FakeGeometry") -> bool:
        return False

    def intersects(self, other: "FakeGeometry") -> bool:
        return self.distance(other) == 0.0

    def touches(self, other: "FakeGeometry") -> bool:
        return self.distance(other) == 0.0


class FakeOverlapGeometry(FakeGeometry):
    def overlaps(self, other: "FakeGeometry") -> bool:
        return True


class FakeWithinGeometry(FakeGeometry):
    def within(self, other: "FakeGeometry") -> bool:
        return True


class FakeCrossGeometry(FakeGeometry):
    def intersects(self, other: "FakeGeometry") -> bool:
        return True

    def touches(self, other: "FakeGeometry") -> bool:
        return False


class FakeCRS:
    def __init__(self, code: str, epsg: int | None = None) -> None:
        self.code = code
        self.epsg = epsg

    def to_string(self) -> str:
        return self.code

    def to_epsg(self) -> int | None:
        return self.epsg

    def __str__(self) -> str:
        return self.code


class SimpleLayer:
    def __init__(
        self,
        records: list[dict[str, object]],
        *,
        crs: FakeCRS | None = None,
        attrs: dict[str, object] | None = None,
        has_sindex: bool | None = None,
    ) -> None:
        self._frame = pd.DataFrame(records)
        self.crs = crs
        self.attrs = attrs or {}
        self.has_sindex = has_sindex

    @property
    def columns(self):
        return self._frame.columns

    def iterrows(self):
        return self._frame.iterrows()


class FakeSpatialIndex:
    def __init__(self, result_positions: list[int]) -> None:
        self.result_positions = result_positions
        self.calls = 0

    def query(self, geometry):
        self.calls += 1
        return list(self.result_positions)


class TestAttributeValidation(unittest.TestCase):
    def test_required_nulls(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "name": None, "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "name": "ok", "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = required_nulls(layer, ["name"])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "null_attribute_in_required_field")
        self.assertEqual(issues[0].feature_id, 1)

    def test_uniqueness(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "asset_id": "A1", "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "asset_id": "A1", "geometry": FakeGeometry(1, 1)},
                {"ID": 3, "asset_id": "A2", "geometry": FakeGeometry(2, 2)},
            ]
        )
        issues = uniqueness(layer, "asset_id")
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(issue.problem_name == "non_unique_attribute" for issue in issues))

    def test_domain_range_checks(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "land_use": 2, "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "land_use": 99, "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = domain_range_checks(layer, "land_use", {1, 2, 3})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "domain_violation")
        self.assertEqual(issues[0].feature_id, 2)


class TestCRSValidation(unittest.TestCase):
    def test_missing_crs(self) -> None:
        issues = missing_crs(SimpleLayer([], crs=None))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "missing_spatial_reference")

    def test_invalid_crs(self) -> None:
        layer = SimpleLayer([], crs=FakeCRS("EPSG:3857", 3857))
        issues = invalid_crs(layer, FakeCRS("EPSG:4326", 4326))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "invalid_spatial_reference")


class TestMetadataValidation(unittest.TestCase):
    def test_missing_metadata_fields(self) -> None:
        issues = missing_metadata_fields({"title": "", "abstract": "", "extent": None})
        self.assertEqual(len(issues), 3)
        self.assertEqual(issues[0].problem_name, "missing_metadata_title")

    def test_incomplete_metadata(self) -> None:
        issues = incomplete_metadata({"extent": None, "lineage": ""})
        self.assertEqual(len(issues), 2)
        self.assertEqual({issue.problem_name for issue in issues}, {"missing_metadata_extent", "missing_metadata_lineage"})


class TestAccuracyValidation(unittest.TestCase):
    def test_coordinate_precision(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(1.123456789123, 2.0)}])
        issues = coordinate_precision(layer, max_decimal_places=6)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "coordinate_precision_not_fit_for_use")

    def test_xy_tolerance(self) -> None:
        layer = SimpleLayer([], crs=FakeCRS("EPSG:4326", 4326), attrs={"xy_tolerance": 0.001})
        issues = xy_tolerance(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "inappropriate_xy_tolerance")

    def test_positional_accuracy(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(100, 100)}])
        reference = SimpleLayer([{"ID": 9, "geometry": FakeGeometry(0, 0)}])
        issues = positional_accuracy(layer, reference, tolerance=10.0)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "positional_accuracy_exceeds_reference_tolerance")


class TestIntegrityValidation(unittest.TestCase):
    def test_missing_spatial_index(self) -> None:
        layer = SimpleLayer([], attrs={"spatial_index_status": "missing"}, has_sindex=False)
        issues = missing_spatial_index(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "missing_or_stale_spatial_index")

    def test_outdated_index(self) -> None:
        layer = SimpleLayer([], attrs={"spatial_index_status": "outdated"})
        issues = outdated_index(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "outdated_attribute_or_spatial_indexes")

    def test_non_rfc7946_geojson(self) -> None:
        payload = json.dumps({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:3857"}}})
        issues = non_rfc7946_geojson(payload)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "non_rfc7946_geojson_output")


class TestTopologyValidation(unittest.TestCase):
    def test_polygon_overlap_same_layer(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": FakeOverlapGeometry(0, 0)},
                {"ID": 2, "geometry": FakeOverlapGeometry(1, 1)},
            ]
        )
        issues = polygon_overlap_same_layer(layer)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(issue.problem_name == "polygon_overlap_same_layer" for issue in issues))

    def test_feature_within_feature(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": FakeWithinGeometry(0, 0)},
                {"ID": 2, "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = feature_within_feature(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "feature_within_feature")

    def test_line_intersection_same_layer(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": FakeCrossGeometry(0, 0)},
                {"ID": 2, "geometry": FakeCrossGeometry(1, 1)},
            ]
        )
        issues = line_intersection_same_layer(layer)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(issue.problem_name == "line_intersection_same_layer" for issue in issues))

    def test_boundary_mismatch_against_reference(self) -> None:
        layer = SimpleLayer(
            [
                {
                    "ID": 1,
                    "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]),
                }
            ]
        )
        reference = SimpleLayer(
            [
                {
                    "ID": 9,
                    "geometry": Polygon([(0, 0), (3.3, 0), (3.3, 4), (0, 4), (0, 0)]),
                }
            ]
        )
        issues = boundary_mismatch_against_reference(layer, reference, mismatch_ratio_threshold=0.05)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "boundary_mismatch_against_reference")

    def test_duplicate_geometry_same_layer(self) -> None:
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": polygon},
                {"ID": 2, "geometry": polygon},
            ]
        )
        issues = duplicate_geometry_same_layer(layer)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(issue.problem_name == "duplicate_geometry_same_layer" for issue in issues))

    def test_line_dangle(self) -> None:
        class FakeLine:
            geom_type = "LineString"

            def __init__(self, coords):
                self.coords = coords

        layer = SimpleLayer(
            [
                {"ID": 1, "asset_class": "main", "geometry": FakeLine([(0, 0), (1, 0)])},
                {"ID": 2, "asset_class": "main", "geometry": FakeLine([(1, 0), (2, 0)])},
                {"ID": 3, "asset_class": "service", "geometry": FakeLine([(2, 0), (3, 0)])},
            ]
        )
        issues = line_dangle(layer, role_field="asset_class", allowed_endpoint_values={"service"})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].feature_id, 1)

    def test_line_dangle_supports_multiline_strings(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "asset_class": "main", "geometry": MultiLineString([[(0, 0), (1, 0)], [(1, 0), (2, 0)]])},
                {"ID": 2, "asset_class": "main", "geometry": MultiLineString([[(2, 0), (3, 0)]])},
                {"ID": 3, "asset_class": "service", "geometry": MultiLineString([[(3, 0), (4, 0)]])},
            ]
        )
        issues = line_dangle(layer, role_field="asset_class", allowed_endpoint_values={"service"})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].feature_id, 1)

    def test_near_miss_endpoint_metadata_and_pair_dedupe(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": "A", "asset_class": "main", "geometry": LineString([(0, 0), (1, 0)])},
                {"ID": "B", "asset_class": "main", "geometry": LineString([(1.04, 0), (2, 0)])},
            ]
        )
        issues = suspicious_near_miss_endpoints(layer, snap_tolerance=0.1, role_field="asset_class")
        self.assertEqual(len(issues), 1)
        issue = issues[0].to_dict()
        self.assertEqual(issue["feature_id"], "A")
        self.assertEqual(issue["related_feature_id"], "B")
        self.assertEqual(issue["endpoint_a"], [1.0, 0.0])
        self.assertEqual(issue["endpoint_b"], [1.04, 0.0])
        self.assertAlmostEqual(issue["distance"], 0.04)
        self.assertEqual(issue["tolerance"], 0.1)
        self.assertEqual(issue["geometry"]["type"], "LineString")
        self.assertEqual(issue["geometry"]["coordinates"], [[1.0, 0.0], [1.04, 0.0]])

    def test_identical_endpoints_are_not_near_miss(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": "A", "asset_class": "main", "geometry": LineString([(0, 0), (1, 0)])},
                {"ID": "B", "asset_class": "main", "geometry": LineString([(1, 0), (2, 0)])},
            ]
        )
        issues = suspicious_near_miss_endpoints(layer, snap_tolerance=0.1, role_field="asset_class")
        self.assertEqual(len(issues), 0)

    def test_unsnapped_endpoint_metadata(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": "A", "asset_class": "main", "geometry": LineString([(0, 0), (1, 0)])},
                {"ID": "B", "asset_class": "main", "geometry": LineString([(1.04, 0), (2, 0)])},
            ]
        )
        issues = unsnapped_endpoints_within_tolerance(layer, snap_tolerance=0.1, role_field="asset_class")
        self.assertEqual(len(issues), 1)
        issue = issues[0].to_dict()
        self.assertEqual(issue["related_feature_id"], "B")
        self.assertEqual(issue["endpoint_a"], [1.0, 0.0])
        self.assertEqual(issue["endpoint_b"], [1.04, 0.0])

    def test_near_miss_geographic_crs_reports_meters(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": "A", "asset_class": "main", "geometry": LineString([(0, 0), (1, 0)])},
                {"ID": "B", "asset_class": "main", "geometry": LineString([(1.0001, 0), (2, 0)])},
            ],
            crs=FakeCRS("EPSG:4326", 4326),
        )
        issues = suspicious_near_miss_endpoints(layer, snap_tolerance=20, role_field="asset_class")
        self.assertEqual(len(issues), 1)
        issue = issues[0].to_dict()
        self.assertEqual(issue["distance_units"], "meters")
        self.assertGreater(issue["distance"], 10)
        self.assertLess(issue["distance"], 12)

    def test_polygon_gap_same_layer(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)], holes=[[(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]])},
            ]
        )
        issues = polygon_gap_same_layer(layer)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].problem_name, "polygon_gap_same_layer")

    def test_polygon_overlap_uses_spatial_index_when_available(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])},
                {"ID": 2, "geometry": Polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])},
            ]
        )
        layer.sindex = FakeSpatialIndex([0, 1])
        issues = polygon_overlap_same_layer(layer)
        self.assertEqual(len(issues), 2)
        self.assertGreater(layer.sindex.calls, 0)

    def test_boundary_mismatch_uses_reference_spatial_index_when_available(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)])},
            ]
        )
        reference = SimpleLayer(
            [
                {"ID": 9, "geometry": Polygon([(0, 0), (3.3, 0), (3.3, 4), (0, 4), (0, 0)])},
            ]
        )
        reference.sindex = FakeSpatialIndex([0])
        issues = boundary_mismatch_against_reference(layer, reference, mismatch_ratio_threshold=0.05)
        self.assertEqual(len(issues), 1)
        self.assertGreater(reference.sindex.calls, 0)


class TestInteractiveRouting(unittest.TestCase):
    def test_interactive_attributes_route(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "asset_id": None, "status": "bad", "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "asset_id": "A1", "status": "active", "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = interactive_validate_layer(
            layer,
            "attributes",
            required_fields=["asset_id"],
            domain_field="status",
            valid_domain={"active", "retired"},
        )
        self.assertTrue(any(issue.problem_name == "null_attribute_in_required_field" for issue in issues))
        self.assertTrue(any(issue.problem_name == "domain_violation" for issue in issues))

    def test_interactive_topology_route(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": FakeOverlapGeometry(0, 0)},
                {"ID": 2, "geometry": FakeOverlapGeometry(1, 1)},
            ]
        )
        issues = interactive_validate_layer(layer, "topology")
        self.assertTrue(any(issue.problem_name == "polygon_overlap_same_layer" for issue in issues))


if __name__ == "__main__":
    unittest.main()
