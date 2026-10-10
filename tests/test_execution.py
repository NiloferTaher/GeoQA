from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geoqa.execution import validate_dataset_with_profile
from geoqa.profile_registry import GeoQAProfile, ValidationFamilyProfile, clear_geoqa_profiles, register_geoqa_profile


class _NoOpGuard:
    def wait_until_safe(self, *, stage: str) -> None:
        return None


class TestExecutionRuntime(unittest.TestCase):
    def tearDown(self) -> None:
        clear_geoqa_profiles()

    def test_validate_dataset_with_profile_writes_report(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "runtime_report"
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(
                    sample,
                    profile="geometry",
                    output_format="json",
                    report_path=report_base,
                )
        self.assertEqual(result.profile_name, "geometry")
        self.assertGreaterEqual(result.feature_count, 1)
        self.assertTrue(any(issue.problem_name == "duplicate_vertex" for issue in result.issues))
        self.assertEqual(result.report_path, str(report_base.with_suffix(".json")))
        self.assertIn("issue_count", result.summary)

    def test_profile_problem_policies_apply_confidence_and_actionability(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        register_geoqa_profile(
            GeoQAProfile(
                name="geometry_calibrated",
                description="Geometry profile with calibrated duplicate-vertex policy.",
                families=(
                    ValidationFamilyProfile(
                        dataset_type="geometry",
                        enabled_validators=("duplicate_vertex",),
                    ),
                ),
                problem_policies={
                    "duplicate_vertex": {
                        "severity": "low",
                        "confidence": "low",
                        "actionable": False,
                    }
                },
            )
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="geometry_calibrated")
        self.assertEqual(len(result.issues), 1)
        issue = result.issues[0]
        self.assertEqual(issue.problem_name, "duplicate_vertex")
        self.assertEqual(issue.severity, "low")
        self.assertEqual(issue.confidence, "low")
        self.assertFalse(issue.actionable)

    def test_profile_problem_policies_can_suppress_issues(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        register_geoqa_profile(
            GeoQAProfile(
                name="geometry_suppressed",
                description="Geometry profile with duplicate-vertex suppression.",
                families=(
                    ValidationFamilyProfile(
                        dataset_type="geometry",
                        enabled_validators=("duplicate_vertex",),
                    ),
                ),
                problem_policies={
                    "duplicate_vertex": {
                        "suppress": True,
                        "suppression_reason": "Suppressed for this workflow.",
                    }
                },
            )
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="geometry_suppressed")
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.suppressed_issues), 1)
        self.assertEqual(result.suppressed_issues[0].suppression["reason"], "Suppressed for this workflow.")

    def test_profile_downgrade_rules_apply_without_full_problem_policy(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        register_geoqa_profile(
            GeoQAProfile(
                name="geometry_downgraded",
                description="Geometry profile with duplicate-vertex downgrade.",
                families=(
                    ValidationFamilyProfile(
                        dataset_type="geometry",
                        enabled_validators=("duplicate_vertex",),
                    ),
                ),
                downgrade_rules={"duplicate_vertex": "low"},
            )
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="geometry_downgraded")
        self.assertEqual(result.issues[0].severity, "low")

    def test_profile_suppression_rules_apply_without_full_problem_policy(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        register_geoqa_profile(
            GeoQAProfile(
                name="geometry_suppression_rule",
                description="Geometry profile with suppression rules.",
                families=(
                    ValidationFamilyProfile(
                        dataset_type="geometry",
                        enabled_validators=("duplicate_vertex",),
                    ),
                ),
                suppression_rules={
                    "duplicate_vertex": {
                        "suppress": True,
                        "suppression_reason": "Suppressed by explicit suppression rule.",
                    }
                },
            )
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="geometry_suppression_rule")
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.suppressed_issues), 1)
        self.assertEqual(result.suppressed_issues[0].suppression["reason"], "Suppressed by explicit suppression rule.")

    def test_profile_validator_options_tune_coordinate_precision_threshold(self) -> None:
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": 1},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [0.12345678901, 1.12345678901],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "precision.geojson"
            dataset_path.write_text(json.dumps(feature_collection), encoding="utf-8")
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                strict_result = validate_dataset_with_profile(dataset_path, profile="generic_strict")
            register_geoqa_profile(
                GeoQAProfile(
                    name="generic_precision_tight",
                    description="Generic strict variant with tight precision threshold.",
                    families=(
                        ValidationFamilyProfile(
                            dataset_type="accuracy",
                            enabled_validators=("coordinate_precision",),
                            validator_options={"coordinate_precision": {"max_decimal_places": 8}},
                        ),
                    ),
                )
            )
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                tight_result = validate_dataset_with_profile(dataset_path, profile="generic_precision_tight")

        self.assertFalse(any(issue.problem_name == "coordinate_precision_not_fit_for_use" for issue in strict_result.issues))
        self.assertTrue(any(issue.problem_name == "coordinate_precision_not_fit_for_use" for issue in tight_result.issues))

    def test_water_network_profile_uses_domain_pack_validators(self) -> None:
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
                    "properties": {"asset_id": "A3", "pipe_diameter": 100, "status": "active", "asset_class": "service"},
                    "geometry": {"type": "LineString", "coordinates": [[2, 0], [3, 0]]},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "water.geojson"
            dataset_path.write_text(json.dumps(feature_collection), encoding="utf-8")
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                result = validate_dataset_with_profile(dataset_path, profile="water_network")
        self.assertTrue(any(issue.problem_name == "line_dangle" for issue in result.issues))
        self.assertIn("pack_summary", result.summary)
        self.assertEqual(result.summary["pack_summary"]["pack"], "water_network")

    def test_max_runtime_seconds_stops_execution_safely(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="generic_strict", max_runtime_seconds=0.0)
        self.assertFalse(result.completed)
        self.assertTrue(any(issue.problem_name == "runtime_limit_exceeded" for issue in result.issues))
        self.assertEqual(result.execution_status, "budget-limited")
        self.assertTrue(result.summary["partial_result"])
        self.assertIn("validators_deferred", result.summary)

    def test_max_issues_stops_execution_with_partial_result(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="generic_audit", max_issues=1)
        self.assertFalse(result.completed)
        self.assertEqual(result.execution_status, "partial")
        self.assertEqual(result.execution_reason, "issue ceiling reached")
        self.assertTrue(result.summary["partial_result"])
        self.assertGreaterEqual(len(result.validators_deferred), 1)

    def test_profile_problem_policies_can_override_priority_score(self) -> None:
        sample = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "public_samples"
            / "edge_cases"
            / "duplicate_vertex_line.geojson"
        )
        register_geoqa_profile(
            GeoQAProfile(
                name="geometry_priority_override",
                description="Geometry profile with explicit priority override.",
                families=(
                    ValidationFamilyProfile(
                        dataset_type="geometry",
                        enabled_validators=("duplicate_vertex",),
                    ),
                ),
                problem_policies={"duplicate_vertex": {"priority_score": 7}},
            )
        )
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = validate_dataset_with_profile(sample, profile="geometry_priority_override")
        self.assertEqual(result.issues[0].priority_score, 7)


if __name__ == "__main__":
    unittest.main()
