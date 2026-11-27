from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import geoqa
from geoqa.conversion import (
    default_vector_layer_name,
    list_vector_layers,
    load_all_vector_layers,
    load_vector_dataset,
)
from geoqa.reports.tables import (
    features_to_dataframe,
    geojson_to_dataframe,
    geojson_to_pivot,
    geojson_to_table,
)

OSM_FIXTURE = "tests/fixtures/tiny_extract.osm"
_POINT = {"type": "Point", "coordinates": [58.4, 23.6]}
_POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


def _issue(**overrides):
    from geoqa.validations.base import ValidationIssue

    payload = {
        "problem_name": "sliver_polygon",
        "severity": "high",
        "description": "Thin polygon.",
        "solution_hint": "Fix the width.",
        "feature_id": 1,
        "geometry": _POLYGON,
    }
    payload.update(overrides)
    return ValidationIssue(**payload)


class TestOsmSupport(unittest.TestCase):
    """An OSM extract must be usable directly, without conversion."""

    def test_osm_exposes_separate_logical_layers(self) -> None:
        layers = list_vector_layers(OSM_FIXTURE)

        self.assertIn("lines", layers)
        self.assertIn("points", layers)

    def test_default_layer_is_not_empty(self) -> None:
        layers = list_vector_layers(OSM_FIXTURE)
        chosen = default_vector_layer_name(layers, path=OSM_FIXTURE)

        self.assertEqual("lines", chosen)

    def test_default_layer_actually_contains_features(self) -> None:
        frame = load_vector_dataset(OSM_FIXTURE)

        self.assertGreater(len(frame), 0)

    def test_osm_tags_survive_loading(self) -> None:
        frame = load_vector_dataset(OSM_FIXTURE, ogr_layer="lines")

        self.assertIn("highway", frame.columns)
        self.assertIn("name", frame.columns)
        self.assertGreater(len(frame), 0)

    def test_load_all_layers_returns_every_populated_layer(self) -> None:
        layers = load_all_vector_layers(OSM_FIXTURE)

        self.assertIn("lines", layers)
        self.assertIn("points", layers)
        self.assertTrue(all(len(frame) > 0 for frame in layers.values()))

    def test_load_all_layers_can_keep_empty(self) -> None:
        layers = load_all_vector_layers(OSM_FIXTURE, skip_empty=False)

        self.assertGreaterEqual(len(layers), 2)

    def test_validation_runs_directly_on_osm(self) -> None:
        report = geoqa.validate(OSM_FIXTURE, ogr_layer="lines")

        self.assertIsInstance(report, geoqa.GeoQAReport)
        self.assertGreater(len(report.issues), 0)

    def test_all_layer_kwarg_is_rejected_clearly(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            load_vector_dataset(OSM_FIXTURE, ogr_layer="all")

        self.assertIn("load_all_vector_layers", str(ctx.exception))


class TestTables(unittest.TestCase):
    def test_geojson_to_dataframe_flattens_properties(self) -> None:
        collection = geoqa.issues_to_geojson([_issue(extra={"nested": {"a": 1}})])
        frame = geojson_to_dataframe(collection)

        self.assertIn("problem_name", frame.columns)
        self.assertIn("severity", frame.columns)

    def test_table_exposes_spatial_columns(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        frame = geojson_to_dataframe(collection)

        for column in ("wkt", "centroid_lon", "centroid_lat", "has_geometry"):
            self.assertIn(column, frame.columns)

    def test_wkt_and_centroid_are_populated(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        frame = geojson_to_dataframe(collection)

        self.assertTrue(frame.loc[0, "has_geometry"])
        self.assertIn("POLYGON", str(frame.loc[0, "wkt"]))
        self.assertAlmostEqual(0.5, float(frame.loc[0, "centroid_lon"]), places=6)

    def test_attribute_only_findings_are_not_dropped(self) -> None:
        issues = [_issue(geometry=None)]
        frame = geojson_to_dataframe(geoqa.issues_to_geojson(issues))

        self.assertEqual(1, len(frame))
        self.assertFalse(bool(frame.loc[0, "has_geometry"]))

    def test_attribute_only_findings_survive_a_geojson_file(self) -> None:
        collection = geoqa.issues_to_geojson([_issue(geometry=None)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.geojson"
            path.write_text(json.dumps(collection), encoding="utf-8")
            frame = geojson_to_dataframe(path)

        self.assertEqual(1, len(frame))

    def test_reads_geojson_from_disk(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.geojson"
            path.write_text(json.dumps(collection), encoding="utf-8")
            frame = geojson_to_dataframe(path)

        self.assertEqual(1, len(frame))

    def test_writes_csv(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        with tempfile.TemporaryDirectory() as tmp:
            path = geojson_to_table(collection, Path(tmp) / "out.csv")

            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8-sig")

        self.assertIn("problem_name", text)

    def test_writes_xlsx(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        with tempfile.TemporaryDirectory() as tmp:
            path = geojson_to_table(collection, Path(tmp) / "out.xlsx")

            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_report_to_table_method(self) -> None:
        report = geoqa.validate(OSM_FIXTURE, ogr_layer="lines")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = report.to_table(Path(tmp) / "r.csv")
            xlsx_path = report.to_table(Path(tmp) / "r.xlsx")

            self.assertTrue(csv_path.exists())
            self.assertTrue(xlsx_path.exists())

    def test_unsupported_format_rejected(self) -> None:
        collection = geoqa.issues_to_geojson([_issue()])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                geojson_to_table(collection, Path(tmp) / "out.docx")

    def test_pivot_summarises_severity_by_rule(self) -> None:
        issues = [_issue(), _issue(), _issue(severity="low")]
        pivot = geojson_to_pivot(geoqa.issues_to_geojson(issues))

        self.assertIsNotNone(pivot)
        self.assertGreaterEqual(int(pivot.values.sum()), 3)

    def test_empty_collection_yields_empty_frame(self) -> None:
        frame = features_to_dataframe([])

        self.assertEqual(0, len(frame))


if __name__ == "__main__":
    unittest.main()