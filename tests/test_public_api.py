from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geoqa
from geoqa.api import GeoQAReport


class _NoOpGuard:
    def wait_until_safe(self, *, stage: str) -> None:
        return None


class PublicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.duplicate_vertex_sample = (
            self.repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        )
        self.self_intersection_sample = (
            self.repo_root / "data" / "public_samples" / "edge_cases" / "self_intersection_polygon.geojson"
        )

    def test_top_level_validate_returns_geoqa_report(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = geoqa.validate(self.duplicate_vertex_sample, profile="geometry")
        self.assertIsInstance(result, GeoQAReport)
        self.assertTrue(any(issue.problem_name == "duplicate_vertex" for issue in result.issues))
        self.assertEqual(result.summary["issue_count"], 1)
        self.assertIn("issues=1", repr(result))

    def test_geoqa_report_exposes_score_and_ml_rows(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            result = geoqa.validate(self.duplicate_vertex_sample, profile="geometry")
        self.assertIsInstance(result.score(), float)
        self.assertIsInstance(result.to_ml(), list)
        self.assertEqual(result.to_ml()[0]["problem_name"], "duplicate_vertex")

    def test_top_level_validate_can_return_summary(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            summary = geoqa.validate(self.duplicate_vertex_sample, profile="geometry", return_summary=True)
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["issue_count"], 1)

    def test_top_level_score_returns_float(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            value = geoqa.score(self.duplicate_vertex_sample, profile="geometry")
        self.assertIsInstance(value, float)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)

    def test_expect_valid_crs_returns_issue_list(self) -> None:
        issues = geoqa.expect.valid_crs(self.duplicate_vertex_sample, expected_crs="EPSG:3857")
        self.assertIsInstance(issues, list)
        self.assertEqual(issues.count(), len(issues))
        self.assertTrue(any(issue.problem_name == "invalid_spatial_reference" for issue in issues))

    def test_expect_self_intersections_returns_issue_list(self) -> None:
        issues = geoqa.expect.no_self_intersections(self.self_intersection_sample)
        self.assertIsInstance(issues, list)
        self.assertTrue(any(issue.problem_name == "self_intersection" for issue in issues))

    def test_fluent_check_interface(self) -> None:
        checker = geoqa.check(self.self_intersection_sample)
        issues = checker.self_intersections()
        self.assertTrue(any(issue.problem_name == "self_intersection" for issue in issues))

    def test_expect_namespaces_scale_beyond_flat_wrappers(self) -> None:
        geometry_issues = geoqa.expect.geometry.valid(self.duplicate_vertex_sample)
        self.assertTrue(any(issue.problem_name == "duplicate_vertex" for issue in geometry_issues))
        topology_issues = geoqa.expect.topology.clean(self.self_intersection_sample)
        self.assertIsInstance(topology_issues, list)
        crs_issues = geoqa.expect.crs.valid(self.duplicate_vertex_sample, expected_crs="EPSG:3857")
        self.assertTrue(any(issue.problem_name == "invalid_spatial_reference" for issue in crs_issues))

    def test_geoqa_report_fix_returns_exportable_fixed_layer(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            report = geoqa.validate(self.duplicate_vertex_sample, profile="geometry")
        fixed = report.fix()
        self.assertTrue(hasattr(fixed, "export"))
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cleaned.geojson"
            written = fixed.export(output_path)
            self.assertEqual(written, output_path)
            self.assertTrue(output_path.exists())

    def test_geoqa_report_clean_alias_returns_fixed_layer(self) -> None:
        with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
            report = geoqa.validate(self.duplicate_vertex_sample, profile="geometry")
        fixed = report.clean()
        self.assertTrue(hasattr(fixed, "export"))

    def test_compatibility_exports_still_available(self) -> None:
        self.assertTrue(callable(geoqa.GeoQAScriptBase))
        self.assertTrue(callable(geoqa.ThermalGuard))
        self.assertTrue(callable(geoqa.validate_dataset_with_profile))
        self.assertTrue(hasattr(geoqa, "thermal"))


if __name__ == "__main__":
    unittest.main()
