from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point

from geoqa.audit_archive import discover_layers, run_audit_archive
from geoqa.interactive_validation import validate_layer


class TestGeoQAAuditArchive(unittest.TestCase):
    def test_point_layer_skips_line_validators_and_reports_duplicate_points(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1, 2, 3]},
            geometry=[Point(0, 0), Point(0, 0), Point(1, 1)],
            crs="EPSG:4326",
        )
        result = validate_layer(layer, "topology", return_result=True)

        problem_names = {issue.problem_name for issue in result.issues}
        self.assertIn("duplicate_geometry_same_layer", problem_names)
        self.assertNotIn("line_intersection_same_layer", problem_names)
        self.assertNotIn("feature_not_split_at_intersection", problem_names)

        coverage = result.validator_coverage
        skipped = [row for row in coverage if row["status"] == "skipped"]
        skipped_names = {row["validator_name"] for row in skipped}
        self.assertIn("line_intersection_same_layer", skipped_names)
        self.assertIn("feature_not_split_at_intersection", skipped_names)
        self.assertTrue(all(row["reason"] == "incompatible_geometry_type" for row in skipped))

    def test_line_layer_runs_line_intersection_validators(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1, 2]},
            geometry=[LineString([(0, 0), (2, 2)]), LineString([(0, 2), (2, 0)])],
            crs="EPSG:4326",
        )
        result = validate_layer(layer, "topology", return_result=True)

        problem_names = {issue.problem_name for issue in result.issues}
        self.assertIn("line_intersection_same_layer", problem_names)
        self.assertIn("feature_not_split_at_intersection", problem_names)

    def test_projected_crs_is_valid_without_expected_crs(self) -> None:
        layer = gpd.GeoDataFrame({"ID": [1]}, geometry=[Point(500000, 2500000)], crs="EPSG:32640")
        result = validate_layer(layer, "crs", return_result=True)

        self.assertEqual([], [issue.problem_name for issue in result.issues])

    def test_projected_crs_mismatch_when_expected_crs_is_explicit(self) -> None:
        layer = gpd.GeoDataFrame({"ID": [1]}, geometry=[Point(500000, 2500000)], crs="EPSG:32640")
        result = validate_layer(layer, "crs", expected_crs="EPSG:4326", return_result=True)

        self.assertEqual(["invalid_spatial_reference"], [issue.problem_name for issue in result.issues])
        self.assertEqual("EPSG:32640", result.issues[0].provenance["source_crs"])
        self.assertEqual("EPSG:4326", result.issues[0].provenance["expected_crs"])

    def test_zip_inventory_selected_layer_and_excel_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            points_dir = root / "points"
            lines_dir = root / "lines"
            points_dir.mkdir()
            lines_dir.mkdir()
            points_path = points_dir / "Flow_Meter.shp"
            lines_path = lines_dir / "pipes.shp"
            gpd.GeoDataFrame(
                {"ID": [1, 2, 3]},
                geometry=[Point(0, 0), Point(0, 0), Point(1, 1)],
                crs="EPSG:4326",
            ).to_file(points_path)
            gpd.GeoDataFrame(
                {"ID": [1, 2]},
                geometry=[LineString([(0, 0), (2, 2)]), LineString([(0, 2), (2, 0)])],
                crs="EPSG:4326",
            ).to_file(lines_path)

            zip_path = root / "demo_layers.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for file_path in [*points_dir.iterdir(), *lines_dir.iterdir()]:
                    archive.write(file_path, file_path.relative_to(root).as_posix())

            layers, _ = discover_layers(zip_path)
            self.assertEqual(2, len(layers))
            self.assertEqual({layer.layer_path for layer in layers}, {"lines/pipes", "points/Flow_Meter"})

            out_dir = root / "out"
            result = run_audit_archive(
                zip_path,
                output_dir=out_dir,
                selected_layer="points/Flow_Meter",
                excel=True,
                json_reports=True,
                command="geoqa audit-archive",
            )

            self.assertEqual(2, len(result.layers))
            self.assertEqual(1, len(result.validated_results))
            self.assertTrue(Path(result.excel_report or "").exists())
            self.assertTrue(Path(result.pdf_report or "").exists())
            self.assertEqual(1, len(result.json_reports))
            payload = json.loads(Path(result.json_reports[0]).read_text(encoding="utf-8"))
            self.assertIn("validator_coverage", payload["summary"])
            self.assertIn("validated", Path(result.summary_report).read_text(encoding="utf-8"))

    def test_all_layer_mode_validates_every_detected_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            point_path = root / "meters.geojson"
            line_path = root / "roads.geojson"
            gpd.GeoDataFrame({"ID": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_file(point_path, driver="GeoJSON")
            gpd.GeoDataFrame({"ID": [1]}, geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326").to_file(
                line_path,
                driver="GeoJSON",
            )
            result = run_audit_archive(root, output_dir=root / "out", all_layers=True, excel=False, json_reports=True)

            self.assertEqual(2, len(result.layers))
            self.assertEqual(2, len(result.validated_results))


if __name__ == "__main__":
    unittest.main()
