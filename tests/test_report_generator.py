from __future__ import annotations

import json
import csv
import tempfile
import unittest
from pathlib import Path

from geoqa.reports.report_generator import format_summary_text, generate_report, summarize_report
from geoqa.validations.base import ValidationIssue


class TestReportGenerator(unittest.TestCase):
    def test_generate_json_report(self) -> None:
        issue = ValidationIssue(
            problem_name="null_geometry",
            severity="critical",
            description="Feature has no geometry.",
            solution_hint="Recreate shape.",
            feature_id=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report([issue], output_format="json", file_path=str(Path(tmpdir) / "report"))
            data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertIn("validation_rule_version", data)
        self.assertEqual(data["issues"][0]["problem_name"], "null_geometry")
        self.assertIn("issue_id", data["issues"][0])
        self.assertIn("validation_rule_version", data["issues"][0])
        self.assertIn("summary", data)

    def test_generate_csv_report_contains_extended_fields(self) -> None:
        issue = ValidationIssue(
            problem_name="self_intersection",
            severity="high",
            description="Crossing linework.",
            solution_hint="Repair geometry.",
            feature_id=123,
            validator_name="geometry",
            validator_version="2",
            issue_class="data_issue",
            iso_category="Logical Consistency",
            provenance={"profile": "generic_strict"},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report([issue], output_format="csv", file_path=str(Path(tmpdir) / "report"))
            with out_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["problem_name"], "self_intersection")
        self.assertEqual(rows[0]["validator_name"], "geometry")
        self.assertEqual(rows[0]["iso_category"], "Logical Consistency")
        self.assertIn("validation_rule_version", rows[0])

    def test_summarize_report_counts_issues(self) -> None:
        issues = [
            ValidationIssue("null_geometry", "critical", "Missing geometry.", "Fix.", 1),
            ValidationIssue("null_geometry", "critical", "Missing geometry.", "Fix.", 2, actionable=False),
            ValidationIssue("duplicate_vertex", "medium", "Duplicate vertex.", "Fix.", 3),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report(issues, output_format="json", file_path=str(Path(tmpdir) / "report"))
            summary = summarize_report(out_path)
        self.assertIn("validation_rule_version", summary)
        self.assertEqual(summary["issue_count"], 3)
        self.assertEqual(summary["by_problem"]["null_geometry"], 2)
        self.assertEqual(summary["actionable"], 2)
        self.assertEqual(summary["informational"], 1)
        self.assertIn("top_issues", summary)
        self.assertIn("by_priority_band", summary)
        self.assertIn("top_actionable", summary)
        self.assertIn("severity_distribution", summary)
        self.assertIn("problem_breakdown", summary)

    def test_format_summary_text_is_human_readable(self) -> None:
        issues = [
            ValidationIssue("null_geometry", "critical", "Missing geometry.", "Fix.", 1),
            ValidationIssue("duplicate_vertex", "medium", "Duplicate vertex.", "Fix.", 3, actionable=False),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report(issues, output_format="json", file_path=str(Path(tmpdir) / "report"))
            summary = summarize_report(out_path)
        text = format_summary_text(summary)
        self.assertIn("Total issues: 2", text)
        self.assertIn("Execution status:", text)
        self.assertIn("Actionable:", text)
        self.assertIn("Severity distribution:", text)
        self.assertIn("Top issues:", text)
        self.assertIn("Actionable ratio:", text)

    def test_generate_json_report_preserves_execution_summary_overrides(self) -> None:
        issue = ValidationIssue(
            problem_name="null_geometry",
            severity="critical",
            description="Feature has no geometry.",
            solution_hint="Recreate shape.",
            feature_id=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report(
                [issue],
                output_format="json",
                file_path=str(Path(tmpdir) / "report"),
                summary={
                    "validation_rule_version": "2026.03",
                    "execution_status": "budget-limited",
                    "execution_reason": "runtime budget reached",
                    "total_issues": 1,
                    "actionable": 1,
                    "informational": 0,
                    "actionable_ratio": 1.0,
                    "severity_distribution": [],
                    "top_issues": [],
                    "validators_completed": ["null_geometry"],
                    "validators_deferred": ["duplicate_vertex"],
                    "operator_next_steps": ["Retry with cache enabled."],
                },
            )
            summary = summarize_report(out_path)
        self.assertEqual(summary["execution_status"], "budget-limited")
        self.assertEqual(summary["execution_reason"], "runtime budget reached")

    def test_format_summary_text_includes_root_cause_groups_when_present(self) -> None:
        issues = [
            ValidationIssue(
                "self_intersection",
                "high",
                "Crossing polygon.",
                "Repair geometry.",
                1,
                provenance={"catalog_category": "geometry"},
            ),
            ValidationIssue(
                "duplicate_vertex",
                "medium",
                "Duplicate vertex.",
                "Repair geometry.",
                2,
                provenance={"catalog_category": "geometry"},
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_report(issues, output_format="json", file_path=str(Path(tmpdir) / "report"))
            summary = summarize_report(out_path)
        text = format_summary_text(summary)
        self.assertIn("Root-cause groups:", text)
        self.assertIn("geometry: 2", text)


if __name__ == "__main__":
    unittest.main()
