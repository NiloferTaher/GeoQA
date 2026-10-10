from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestGeoQACli(unittest.TestCase):
    def test_validate_command_writes_report(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "cli_report"
            env = os.environ.copy()
            env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "geoqa",
                    "validate",
                    str(sample),
                    "--profile",
                    "geometry",
                    "--output-format",
                    "json",
                    "--report-path",
                    str(report_base),
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            output_path = report_base.with_suffix(".json")
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(any(item["problem_name"] == "duplicate_vertex" for item in payload["issues"]))

    def test_validate_command_fail_on_error_returns_non_zero(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "geoqa",
                "validate",
                str(sample),
                "--profile",
                "geometry",
                "--fail-on-error",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, msg=result.stderr or result.stdout)

    def test_profiles_list_command(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "geoqa", "profiles", "list"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("Available profiles:", result.stdout)
        self.assertIn("generic_quick", result.stdout)
        self.assertIn("water_network_audit", result.stdout)

    def test_profiles_show_command(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "geoqa", "profiles", "show", "water_network", "--json"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "water_network")
        self.assertIn("problem_policies", payload)
        self.assertIn("downgrade_rules", payload)
        self.assertIn("suppression_rules", payload)

    def test_profiles_show_command_for_water_network_variant(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "geoqa", "profiles", "show", "water_network_quick", "--json"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "water_network_quick")

    def test_report_summarize_command_outputs_text_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "cli_report"
            env = os.environ.copy()
            env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
            validate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "geoqa",
                    "validate",
                    str(sample),
                    "--profile",
                    "geometry",
                    "--output-format",
                    "json",
                    "--report-path",
                    str(report_base),
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validate_result.returncode, 0, msg=validate_result.stderr or validate_result.stdout)
            summary_result = subprocess.run(
                [sys.executable, "-m", "geoqa", "report", "summarize", str(report_base.with_suffix(".json"))],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(summary_result.returncode, 0, msg=summary_result.stderr or summary_result.stdout)
        self.assertIn("Total issues:", summary_result.stdout)
        self.assertIn("Top issues:", summary_result.stdout)

    def test_report_stats_command_outputs_row_count(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "cli_report"
            env = os.environ.copy()
            env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
            validate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "geoqa",
                    "validate",
                    str(sample),
                    "--profile",
                    "geometry",
                    "--output-format",
                    "json",
                    "--report-path",
                    str(report_base),
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validate_result.returncode, 0, msg=validate_result.stderr or validate_result.stdout)
            stats_result = subprocess.run(
                [sys.executable, "-m", "geoqa", "report", "stats", str(report_base.with_suffix(".json"))],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(stats_result.returncode, 0, msg=stats_result.stderr or stats_result.stdout)
        self.assertIn("Row count:", stats_result.stdout)
        self.assertIn("Severity distribution:", stats_result.stdout)

    def test_benchmark_command_outputs_structured_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "geoqa",
                "benchmark",
                str(sample),
                "--profile",
                "geometry",
                "--json",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile_name"], "geometry")
        self.assertIn("dataset_path", payload)
        self.assertIn("duration_seconds", payload)
        self.assertIn("feature_count", payload)
        self.assertIn("issue_count", payload)
        self.assertIn("summary", payload)

    def test_benchmark_command_human_output_mentions_execution_status(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        env = os.environ.copy()
        env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "geoqa",
                "benchmark",
                str(sample),
                "--profile",
                "geometry",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("Execution status:", result.stdout)
        self.assertIn("Severity distribution:", result.stdout)

    def test_validate_command_supports_runtime_cache_and_progress_flags(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "cli_report"
            cache_dir = Path(tmpdir) / "cache"
            env = os.environ.copy()
            env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
            command = [
                sys.executable,
                "-m",
                "geoqa",
                "validate",
                str(sample),
                "--profile",
                "geometry",
                "--output-format",
                "json",
                "--report-path",
                str(report_base),
                "--max-workers",
                "2",
                "--chunk-size",
                "10",
                "--sleep",
                "0.0",
                "--thermal-profile",
                "balanced",
                "--max-features",
                "100",
                "--max-size-mb",
                "10",
                "--cache",
                str(cache_dir),
                "--cache-tag",
                "cli-runtime-demo",
                "--max-runtime-seconds",
                "30",
                "--progress",
            ]
            first_result = subprocess.run(
                command,
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first_result.returncode, 0, msg=first_result.stderr or first_result.stdout)
            self.assertTrue(report_base.with_suffix(".json").exists())
            self.assertIn("Loaded", first_result.stdout)
            self.assertIn("Detected", first_result.stdout)
            self.assertIn("[1/", first_result.stdout)

            second_result = subprocess.run(
                command,
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(second_result.returncode, 0, msg=second_result.stderr or second_result.stdout)
        self.assertIn("cache-hit", second_result.stdout)

    def test_validate_command_supports_low_resource_mode(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sample = repo_root / "data" / "public_samples" / "edge_cases" / "duplicate_vertex_line.geojson"
        with tempfile.TemporaryDirectory() as tmpdir:
            report_base = Path(tmpdir) / "low_resource_report"
            env = os.environ.copy()
            env["GEOQA_DISABLE_THERMAL_GUARD"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "geoqa",
                    "validate",
                    str(sample),
                    "--profile",
                    "generic_quick",
                    "--output-format",
                    "json",
                    "--report-path",
                    str(report_base),
                    "--low-resource",
                    "--max-runtime-seconds",
                    "30",
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            payload = json.loads(report_base.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertIn("Execution status:", result.stdout)
        self.assertIn(payload["summary"]["execution_status"], {"full", "partial", "budget-limited"})


if __name__ == "__main__":
    unittest.main()
