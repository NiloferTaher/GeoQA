from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geoqa.execution import validate_dataset_with_profile
from geoqa.packs.water_network import detect_water_network_schema


class _NoOpGuard:
    def wait_until_safe(self, *, stage: str) -> None:
        return None


def _write_feature_collection(directory: str, feature_collection: dict) -> Path:
    path = Path(directory) / "water_network.geojson"
    path.write_text(json.dumps(feature_collection), encoding="utf-8")
    return path


class TestWaterNetworkPack(unittest.TestCase):
    def test_detect_water_network_schema_returns_structured_hints(self) -> None:
        class Layer:
            columns = ["asset_id", "pipe_diameter", "material", "status", "asset_class", "geometry"]

        hints = detect_water_network_schema(Layer())
        self.assertEqual(hints.asset_id_field, "asset_id")
        self.assertEqual(hints.diameter_field, "pipe_diameter")
        self.assertEqual(hints.material_field, "material")
        self.assertEqual(hints.status_field, "status")
        self.assertEqual(hints.role_field, "asset_class")
        self.assertEqual(hints.schema_strength, "strong")

    def test_water_network_strict_distinguishes_dangle_from_allowed_terminal(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A1", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A2", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [2, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A3", "pipe_diameter": 25, "status": "active", "asset_class": "service"},
                    "geometry": {"type": "LineString", "coordinates": [[2, 0], [3, 0]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network_strict")

        dangles = [issue for issue in result.issues if issue.problem_name == "line_dangle"]
        self.assertEqual(len(dangles), 1)

    def test_water_network_audit_flags_isolated_segments(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A1", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A2", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [2, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A3", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[10, 0], [11, 0]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network_audit")

        isolated = [issue for issue in result.issues if issue.problem_name == "isolated_network_segment"]
        self.assertEqual(len(isolated), 1)

    def test_water_network_audit_flags_near_miss_and_unsnapped_endpoints(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A1", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A2", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[1.04, 0], [2, 0]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network_audit")

        near_miss = [issue for issue in result.issues if issue.problem_name == "suspicious_near_miss_endpoints"]
        unsnapped = [issue for issue in result.issues if issue.problem_name == "unsnapped_endpoints_within_tolerance"]
        self.assertGreaterEqual(len(near_miss), 2)
        self.assertGreaterEqual(len(unsnapped), 2)

    def test_water_network_strict_uses_schema_aware_attribute_rules(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "asset_id": "A1",
                        "pipe_diameter": -1,
                        "material": "wood",
                        "status": "broken",
                        "asset_class": "main",
                    },
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {
                        "asset_id": "A1",
                        "pipe_diameter": 100,
                        "material": "pvc",
                        "status": "active",
                        "asset_class": "main",
                    },
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [2, 0]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network_strict")

        problem_names = {issue.problem_name for issue in result.issues}
        self.assertIn("non_unique_attribute", problem_names)
        self.assertIn("domain_violation", problem_names)

    def test_water_network_quick_suppresses_precision_noise_but_audit_keeps_it(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A1", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {
                    "type": "LineString",
                        "coordinates": [[0.1234567890123, 0.1234567890123], [1.1234567890123, 0.1234567890123]],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                quick_result = validate_dataset_with_profile(dataset_path, profile="water_network_quick")
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                audit_result = validate_dataset_with_profile(dataset_path, profile="water_network_audit")

        self.assertTrue(
            any(issue.problem_name == "coordinate_precision_not_fit_for_use" for issue in quick_result.suppressed_issues)
        )
        self.assertTrue(any(issue.problem_name == "coordinate_precision_not_fit_for_use" for issue in audit_result.issues))

    def test_water_network_pack_summary_includes_junction_and_schema_details(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A1", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A2", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [2, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"asset_id": "A3", "pipe_diameter": 100, "status": "active", "asset_class": "main"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [1, 1]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = _write_feature_collection(tmpdir, feature_collection)
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network_strict")

        pack_summary = result.summary["pack_summary"]
        self.assertEqual(pack_summary["network_metrics"]["junction_count"], 1)
        self.assertEqual(pack_summary["network_metrics"]["terminal_endpoint_count"], 3)
        self.assertIn("explanation", pack_summary["schema"])
        self.assertIn("thresholds", pack_summary)


if __name__ == "__main__":
    unittest.main()
