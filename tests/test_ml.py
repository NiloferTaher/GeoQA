from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from geoqa.ml import (
    annotate_layer_with_issues,
    build_issue_feature_rows,
    build_quality_feature_frame,
    export_annotated_dataset,
    export_issue_features,
)
from geoqa.validations.base import ValidationIssue


class FakeGeometry:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    @property
    def wkt(self) -> str:
        return f"POINT ({self.x} {self.y})"


class TestMLAnnotations(unittest.TestCase):
    def test_annotate_layer_with_issues(self) -> None:
        layer = pd.DataFrame(
            {
                "ID": [1, 2],
                "geometry": [FakeGeometry(0, 0), FakeGeometry(1, 1)],
            }
        )
        issues = [
            ValidationIssue("null_geometry", "critical", "desc", "hint", 1),
            ValidationIssue("duplicate_vertex", "high", "desc", "hint2", 1),
        ]
        annotated = annotate_layer_with_issues(layer, issues)
        self.assertTrue(bool(annotated.loc[0, "qa_has_issue"]))
        self.assertEqual(int(annotated.loc[0, "qa_issue_count"]), 2)
        self.assertEqual(annotated.loc[1, "qa_issue_count"], 0)
        self.assertEqual(annotated.loc[0, "qa_max_severity"], "critical")

    def test_build_quality_feature_frame(self) -> None:
        layer = pd.DataFrame({"ID": [1, 2], "value": [10, 20]})
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        annotated = build_quality_feature_frame(layer, issues)
        self.assertIn("qa_problem_null_geometry", annotated.columns)
        self.assertEqual(int(annotated.loc[0, "qa_problem_null_geometry"]), 1)
        self.assertEqual(int(annotated.loc[1, "qa_problem_null_geometry"]), 0)


class TestMLFeaturesAndExports(unittest.TestCase):
    def test_build_issue_feature_rows(self) -> None:
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        rows = build_issue_feature_rows(issues)
        self.assertEqual(rows[0]["severity_rank"], 4)
        self.assertTrue(rows[0]["has_repair_hint"])

    def test_export_annotated_dataset_csv(self) -> None:
        layer = pd.DataFrame({"ID": [1], "geometry": [FakeGeometry(0, 0)]})
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_annotated_dataset(layer, issues, Path(tmpdir) / "annotated.csv", format="csv")
            data = Path(output).read_text(encoding="utf-8")
        self.assertIn("qa_issue_count", data)
        self.assertIn("POINT (0 0)", data)

    def test_export_annotated_dataset_jsonl(self) -> None:
        layer = pd.DataFrame({"ID": [1], "geometry": [FakeGeometry(0, 0)]})
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_annotated_dataset(layer, issues, Path(tmpdir) / "annotated.jsonl", format="jsonl")
            line = Path(output).read_text(encoding="utf-8").strip()
            payload = json.loads(line)
        self.assertEqual(payload["qa_issue_count"], 1)
        self.assertEqual(payload["geometry"], "POINT (0 0)")

    def test_export_issue_features_jsonl(self) -> None:
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_issue_features(issues, Path(tmpdir) / "features.jsonl", format="jsonl")
            payload = json.loads(Path(output).read_text(encoding="utf-8").strip())
        self.assertEqual(payload["problem_name"], "null_geometry")


if __name__ == "__main__":
    unittest.main()
