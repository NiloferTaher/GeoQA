from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geoqa.reports.geojson import errors_summary, issues_to_geojson
from geoqa.validations.base import ValidationIssue

_POINT = {"type": "Point", "coordinates": [58.4, 23.6]}
_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [0, 0.0001], [0.0001, 0.0001], [0, 0]]],
}


def _issue(**overrides) -> ValidationIssue:
    payload = {
        "problem_name": "duplicate_geometry_same_layer",
        "severity": "high",
        "description": "Two records share the same geometry.",
        "solution_hint": "Merge or link the records.",
        "feature_id": 1,
        "geometry": _POINT,
    }
    payload.update(overrides)
    return ValidationIssue(**payload)


class TestIssuesToGeojson(unittest.TestCase):
    def test_emits_errors_only_feature_collection(self) -> None:
        collection = issues_to_geojson([_issue()])

        self.assertEqual("FeatureCollection", collection["type"])
        self.assertEqual(1, len(collection["features"]))
        self.assertEqual("Feature", collection["features"][0]["type"])
        self.assertEqual("geoqa_errors", collection["name"])

    def test_declares_wgs84_crs(self) -> None:
        collection = issues_to_geojson([_issue()])

        self.assertEqual("EPSG:4326", collection["crs"]["properties"]["name"])

    def test_skips_issues_without_geometry(self) -> None:
        collection = issues_to_geojson([_issue(), _issue(geometry=None)])

        self.assertEqual(1, len(collection["features"]))

    def test_skips_unusable_geometry_payloads(self) -> None:
        for bad in ({"type": "WkbPoint"}, {"coordinates": [0, 0]}, "POINT (0 0)", 42):
            with self.subTest(bad=bad):
                collection = issues_to_geojson([_issue(geometry=bad)])

                self.assertEqual([], collection["features"])

    def test_keeps_non_actionable_when_requested(self) -> None:
        collection = issues_to_geojson([_issue(actionable=False)], keep_non_actionable=True)

        self.assertEqual(1, len(collection["features"]))
        self.assertFalse(collection["features"][0]["properties"]["actionable"])

    def test_drops_non_actionable_when_not_requested(self) -> None:
        collection = issues_to_geojson([_issue(actionable=False)], keep_non_actionable=False)

        self.assertEqual([], collection["features"])

    def test_geometry_type_is_recorded_as_property(self) -> None:
        collection = issues_to_geojson([_issue(geometry=_POLYGON)])

        properties = collection["features"][0]["properties"]
        self.assertEqual("Polygon", properties["geometry_type"])
        self.assertEqual("Polygon", collection["features"][0]["geometry"]["type"])

    def test_popup_fields_match_atlas_issue_contract(self) -> None:
        collection = issues_to_geojson([_issue()])
        properties = collection["features"][0]["properties"]

        for field in (
            "issue_id",
            "problem_name",
            "severity",
            "description",
            "solution_hint",
            "feature_id",
            "geometry_type",
            "validator_name",
            "validator_version",
            "issue_class",
            "iso_category",
            "confidence",
            "actionable",
            "priority_score",
            "suppressed",
        ):
            with self.subTest(field=field):
                self.assertIn(field, properties)

    def test_explanation_is_attached_for_popup(self) -> None:
        collection = issues_to_geojson([_issue()])
        properties = collection["features"][0]["properties"]

        self.assertEqual(
            "Multiple records share exactly the same geometry.",
            properties["what_geoqa_found"],
        )
        self.assertTrue(properties["why_it_matters"])
        self.assertTrue(properties["recommended_action"])

    def test_unknown_problem_falls_back_to_issue_text(self) -> None:
        collection = issues_to_geojson([_issue(problem_name="some_new_problem")])
        properties = collection["features"][0]["properties"]

        self.assertEqual("Two records share the same geometry.", properties["what_geoqa_found"])
        self.assertEqual("Merge or link the records.", properties["recommended_action"])

    def test_suppressed_issues_are_flagged(self) -> None:
        collection = issues_to_geojson([_issue(suppression={"reason": "profile"})])
        properties = collection["features"][0]["properties"]

        self.assertTrue(properties["suppressed"])
        self.assertEqual({"reason": "profile"}, properties["suppression"])

    def test_extra_fields_are_preserved(self) -> None:
        collection = issues_to_geojson([_issue(extra={"distance": 0.42})])

        self.assertEqual(0.42, collection["features"][0]["properties"]["distance"])

    def test_duplicate_geometry_maps_to_same_issue_id(self) -> None:
        first = issues_to_geojson([_issue()])["features"][0]["properties"]["issue_id"]
        second = issues_to_geojson([_issue()])["features"][0]["properties"]["issue_id"]

        self.assertEqual(first, second)

    def test_distinct_features_get_distinct_issue_ids(self) -> None:
        collection = issues_to_geojson([_issue(feature_id=1), _issue(feature_id=2)])
        ids = [feature["properties"]["issue_id"] for feature in collection["features"]]

        self.assertEqual(2, len(set(ids)))

    def test_accepts_plain_dict_issues(self) -> None:
        row = _issue().to_dict()
        collection = issues_to_geojson([row])

        self.assertEqual(1, len(collection["features"]))

    def test_result_is_json_serialisable(self) -> None:
        collection = issues_to_geojson([_issue(), _issue(geometry=_POLYGON)])

        json.loads(json.dumps(collection))

    def test_empty_input_yields_empty_collection(self) -> None:
        collection = issues_to_geojson([])

        self.assertEqual("FeatureCollection", collection["type"])
        self.assertEqual([], collection["features"])


class TestErrorsSummary(unittest.TestCase):
    def test_counts_features_by_severity_and_problem(self) -> None:
        collection = issues_to_geojson([
            _issue(severity="high"),
            _issue(severity="medium"),
            _issue(severity="medium"),
        ])
        summary = errors_summary(collection)

        self.assertEqual(3, summary["feature_count"])
        self.assertEqual({"medium": 2, "high": 1}, summary["by_severity"])
        self.assertEqual(3, summary["by_problem"]["duplicate_geometry_same_layer"])

    def test_empty_collection_summarises_cleanly(self) -> None:
        summary = errors_summary({"type": "FeatureCollection", "features": []})

        self.assertEqual(0, summary["feature_count"])
        self.assertEqual({}, summary["by_severity"])


class TestGeojsonExportPath(unittest.TestCase):
    def test_report_export_writes_geojson_file(self) -> None:
        from geoqa.api import GeoQAReport

        class _StubResult:
            profile_name = "stub"
            dataset_path = "stub.gpkg"

            def __init__(self, issues: list[ValidationIssue]) -> None:
                self.issues = issues
                self.suppressed_issues: list[ValidationIssue] = []
                self.summary = {"total_issues": len(issues)}

        report = GeoQAReport(_StubResult([_issue()]))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "errors.geojson"
            written = report.export(target)

            self.assertTrue(written.exists())
            payload = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual("FeatureCollection", payload["type"])
        self.assertEqual(1, len(payload["features"]))


if __name__ == "__main__":
    unittest.main()