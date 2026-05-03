from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from geoqa.agent import (
    AgentRunResult,
    apply_approved_fixes,
    apply_fixes_interactively,
    generate_agent_report,
    generate_final_report,
    infer_dataset_type,
    normalize_dataset_type,
    review_fixes_on_sample,
    run_agent_workflow,
    suggest_fixes,
    validate_layer_for_dataset_type,
)
from geoqa.fixes import drop_null_geometries
from geoqa.validations.base import ValidationIssue


class FakeGeometry:
    geom_type = "Point"

    def __init__(self, x: float, y: float) -> None:
        self.coords = [(x, y)]

    def distance(self, other: "FakeGeometry") -> float:
        dx = self.coords[0][0] - other.coords[0][0]
        dy = self.coords[0][1] - other.coords[0][1]
        return (dx**2 + dy**2) ** 0.5

    @property
    def wkt(self) -> str:
        x, y = self.coords[0]
        return f"POINT ({x} {y})"


class FakeLineGeometry:
    geom_type = "LineString"

    def __init__(self, coords: list[tuple[float, float]]) -> None:
        self.coords = coords

    @property
    def wkt(self) -> str:
        return "LINESTRING (" + ", ".join(f"{x} {y}" for x, y in self.coords) + ")"


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

    def head(self, sample_size: int):
        sample = self._frame.head(sample_size).copy()
        layer = SimpleLayer(sample.to_dict("records"), crs=self.crs, attrs=dict(self.attrs), has_sindex=self.has_sindex)
        return layer

    def copy(self):
        return self.head(len(self._frame))

    def __len__(self) -> int:
        return len(self._frame)

    def __getitem__(self, key):
        return self._frame.__getitem__(key)

    def __setitem__(self, key, value) -> None:
        self._frame.__setitem__(key, value)

    @property
    def loc(self):
        return self._frame.loc

    @property
    def iloc(self):
        return self._frame.iloc


class TestAgentInference(unittest.TestCase):
    def test_infer_dataset_type(self) -> None:
        layer = SimpleLayer([{"pipe_diameter": 100, "geometry": FakeGeometry(0, 0)}])
        self.assertEqual(infer_dataset_type(layer), "water_network")

    def test_normalize_dataset_type(self) -> None:
        dataset_type, inferred = normalize_dataset_type("3")
        self.assertEqual(dataset_type, "land_use")
        self.assertIsNone(inferred)


class TestAgentRouting(unittest.TestCase):
    def test_validate_layer_for_land_use(self) -> None:
        layer = SimpleLayer(
            [{"ID": 1, "land_use": 99, "geometry": FakeGeometry(0, 0)}],
            crs=FakeCRS("EPSG:4326", 4326),
        )
        issues = validate_layer_for_dataset_type(layer, "land_use")
        self.assertTrue(any(issue.problem_name == "domain_violation" for issue in issues))

    def test_validate_layer_for_environmental_metadata(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}], crs=FakeCRS("EPSG:3857", 3857))
        issues = validate_layer_for_dataset_type(
            layer,
            "environmental",
            metadata={"title": "", "abstract": "", "extent": None, "lineage": ""},
            expected_crs="EPSG:4326",
        )
        self.assertTrue(any(issue.problem_name == "invalid_spatial_reference" for issue in issues))
        self.assertTrue(any(issue.problem_name == "missing_metadata_title" for issue in issues))

    def test_chunked_validation_preserves_full_layer_uniqueness(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "asset_id": "A-1", "pipe_diameter": 10, "status": "active", "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "asset_id": "B-2", "pipe_diameter": 12, "status": "active", "geometry": FakeGeometry(1, 1)},
                {"ID": 3, "asset_id": "A-1", "pipe_diameter": 14, "status": "active", "geometry": FakeGeometry(2, 2)},
            ],
            crs=FakeCRS("EPSG:4326", 4326),
        )
        with patch("geoqa.agent._run_geometry_checks", return_value=[]):
            issues = validate_layer_for_dataset_type(layer, "water_network", validation_chunk_size=2)
        duplicates = [issue for issue in issues if issue.problem_name == "non_unique_attribute"]
        self.assertEqual(len(duplicates), 2)

    def test_chunked_validation_uses_sleep_and_guard_between_chunks(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "land_use": 1, "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "land_use": 2, "geometry": FakeGeometry(1, 1)},
                {"ID": 3, "land_use": 3, "geometry": FakeGeometry(2, 2)},
            ],
            crs=FakeCRS("EPSG:4326", 4326),
        )

        class GuardRecorder:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def cool_down_if_needed(self, *, stage: str):
                self.calls.append(f"cool:{stage}")

            def wait_until_safe(self, *, stage: str):
                self.calls.append(f"wait:{stage}")

        guard = GuardRecorder()
        sleep_calls: list[float] = []

        with patch("geoqa.agent._run_geometry_checks", return_value=[]):
            validate_layer_for_dataset_type(
                layer,
                "land_use",
                validation_chunk_size=2,
                sleep_between_validation_chunks_seconds=0.25,
                thermal_guard=guard,
                sleep_fn=sleep_calls.append,
            )

        self.assertEqual(sleep_calls, [0.25])
        self.assertEqual(
            guard.calls,
            ["cool:validation_chunk_1_cooldown", "wait:validation_chunk_2_pre"],
        )

    def test_geometry_weighted_chunking_splits_by_vertex_budget(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": FakeLineGeometry([(0, 0), (1, 1), (2, 2), (3, 3)])},
                {"ID": 2, "geometry": FakeLineGeometry([(0, 0), (1, 1), (2, 2), (3, 3)])},
                {"ID": 3, "geometry": FakeLineGeometry([(0, 0), (1, 1), (2, 2), (3, 3)])},
            ],
            crs=FakeCRS("EPSG:4326", 4326),
        )
        chunk_sizes: list[int] = []

        def capture_chunks(chunk):
            chunk_sizes.append(len(chunk))
            return []

        with patch("geoqa.agent._run_geometry_checks", side_effect=capture_chunks):
            validate_layer_for_dataset_type(
                layer,
                "land_use",
                validation_target_vertices_per_chunk=5,
            )

        self.assertEqual(chunk_sizes, [1, 1, 1])

    def test_chunked_validation_can_reduce_chunk_size_under_thermal_pressure(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "land_use": 1, "geometry": FakeGeometry(0, 0)},
                {"ID": 2, "land_use": 2, "geometry": FakeGeometry(1, 1)},
                {"ID": 3, "land_use": 3, "geometry": FakeGeometry(2, 2)},
                {"ID": 4, "land_use": 1, "geometry": FakeGeometry(3, 3)},
                {"ID": 5, "land_use": 2, "geometry": FakeGeometry(4, 4)},
            ],
            crs=FakeCRS("EPSG:4326", 4326),
        )

        class HotGuard:
            warn_temp_c = 64.0
            max_temp_c = 70.0

            class _Snap:
                def __init__(self, value: float) -> None:
                    self.max_temp_c = value

            def snapshot(self):
                return self._Snap(69.5)

            def cool_down_if_needed(self, *, stage: str):
                return None

            def wait_until_safe(self, *, stage: str):
                return None

        chunk_sizes: list[int] = []
        messages: list[str] = []

        def capture_chunks(chunk):
            chunk_sizes.append(len(chunk))
            return []

        with patch("geoqa.agent._run_geometry_checks", side_effect=capture_chunks):
            validate_layer_for_dataset_type(
                layer,
                "land_use",
                validation_chunk_size=3,
                thermal_guard=HotGuard(),
                messages=messages,
            )

        self.assertEqual(chunk_sizes, [3, 2])
        self.assertTrue(any("reducing chunk size" in message.lower() for message in messages))


class TestAgentFixWorkflow(unittest.TestCase):
    def test_suggest_fixes(self) -> None:
        issues = [
            ValidationIssue("null_geometry", "critical", "desc", "hint", 1),
            ValidationIssue("null_geometry", "critical", "desc", "hint", 2),
        ]
        suggestions = suggest_fixes(issues)
        self.assertEqual(len(suggestions), 1)
        self.assertTrue(suggestions[0].auto_fix_available)

    def test_review_and_apply_fixes(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": None},
                {"ID": 2, "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        sample_layer, approved, actions = review_fixes_on_sample(layer, issues, input_func=lambda _: "y")
        self.assertEqual(len(sample_layer), 1)
        self.assertEqual(approved, ["null_geometry"])
        self.assertTrue(any(action.status == "applied" for action in actions))

        full_layer, full_actions = apply_approved_fixes(layer, approved)
        self.assertEqual(len(full_layer), 1)
        self.assertTrue(any(action.scope == "full_dataset" for action in full_actions))

    def test_apply_approved_fixes_with_batch_size(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": None},
                {"ID": 2, "geometry": FakeGeometry(1, 1)},
                {"ID": 3, "geometry": None},
                {"ID": 4, "geometry": FakeGeometry(2, 2)},
            ]
        )
        fixed_layer, actions = apply_approved_fixes(layer, ["null_geometry"], batch_size=2)
        self.assertEqual(len(fixed_layer), 2)
        self.assertTrue(any(action.scope == "full_dataset_batch" for action in actions))

    def test_drop_null_geometries(self) -> None:
        frame = pd.DataFrame({"geometry": [None, FakeGeometry(0, 0)]})
        fixed = drop_null_geometries(frame)
        self.assertEqual(len(fixed), 1)


class TestAgentReporting(unittest.TestCase):
    def test_generate_agent_report_json(self) -> None:
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_agent_report(issues, [], output_format="json", file_path=str(Path(tmpdir) / "agent_report"))
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["issues"][0]["problem_name"], "null_geometry")

    def test_generate_final_report_json(self) -> None:
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_final_report(issues, [], output_format="json", file_path=str(Path(tmpdir) / "final_report"))
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["issues"][0]["problem_name"], "null_geometry")

    def test_generate_agent_report_with_geometry_payload(self) -> None:
        issues = [ValidationIssue("self_intersection", "high", "desc", "hint", 1, geometry=FakeGeometry(0, 0))]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = generate_agent_report(issues, [], output_format="json", file_path=str(Path(tmpdir) / "agent_report"))
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["issues"][0]["geometry"], "POINT (0 0)")


class TestAgentConvenience(unittest.TestCase):
    def test_apply_fixes_interactively_decline_full(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": None},
                {"ID": 2, "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        responses = iter(["y", "n"])
        fixed_layer, actions = apply_fixes_interactively(layer, issues, input_func=lambda _: next(responses))
        self.assertEqual(len(fixed_layer), 2)
        self.assertTrue(any(action.status == "rejected" and action.scope == "full_dataset" for action in actions))
        self.assertTrue(any(action.preview is not None for action in actions if action.scope == "sample"))

    def test_apply_fixes_interactively_without_visual_feedback(self) -> None:
        layer = SimpleLayer(
            [
                {"ID": 1, "geometry": None},
                {"ID": 2, "geometry": FakeGeometry(1, 1)},
            ]
        )
        issues = [ValidationIssue("null_geometry", "critical", "desc", "hint", 1)]
        responses = iter(["y", "n"])
        _, actions = apply_fixes_interactively(
            layer,
            issues,
            visual_feedback=False,
            input_func=lambda _: next(responses),
        )
        self.assertTrue(all(action.preview is None for action in actions if action.scope == "sample"))


class TestAgentResultShape(unittest.TestCase):
    def test_agent_run_result_to_dict(self) -> None:
        result = AgentRunResult(
            dataset_path="dataset.geojson",
            dataset_type="generic",
            inferred_dataset_type=None,
            issues=[],
            fix_actions=[],
            messages=["message"],
            recommendations=[{"kind": "recommendation"}],
            issue_report_path="issues.json",
            final_report_path="final.json",
            fix_log_path="fixes.jsonl",
        )
        payload = result.to_dict()
        self.assertEqual(payload["messages"], ["message"])
        self.assertEqual(payload["fix_log_path"], "fixes.jsonl")


class TestChunkingRecommendationWorkflow(unittest.TestCase):
    def test_noninteractive_run_adds_chunking_recommendation(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}], crs=FakeCRS("EPSG:4326", 4326))
        first_issues = [ValidationIssue("validation_runtime_error", "high", "desc", "hint", None)]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("geoqa.agent._load_dataset", return_value=layer),
                patch("geoqa.agent.validate_layer_for_dataset_type", return_value=first_issues),
            ):
                result = run_agent_workflow(
                    "dataset.geojson",
                    dataset_type="generic",
                    interactive=False,
                    issue_report_format="json",
                    issue_report_path=str(Path(tmpdir) / "issues"),
                    final_report_format="json",
                    final_report_path=str(Path(tmpdir) / "final"),
                )
        self.assertIsNotNone(result.recommendations)
        self.assertTrue(any(item["kind"] == "chunking_recommended" for item in result.recommendations or []))

    def test_interactive_run_can_rerun_with_chunking(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}], crs=FakeCRS("EPSG:4326", 4326))
        first_issues = [ValidationIssue("validation_runtime_error", "high", "desc", "hint", None)]
        second_issues = []
        validate_calls: list[dict[str, object]] = []

        def fake_validate(*args, **kwargs):
            validate_calls.append(dict(kwargs))
            if len(validate_calls) == 1:
                return first_issues
            return second_issues

        responses = iter(["y"])
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("geoqa.agent._load_dataset", return_value=layer),
                patch("geoqa.agent.validate_layer_for_dataset_type", side_effect=fake_validate),
            ):
                result = run_agent_workflow(
                    "dataset.geojson",
                    dataset_type="generic",
                    interactive=True,
                    input_func=lambda _: next(responses),
                    issue_report_format="json",
                    issue_report_path=str(Path(tmpdir) / "issues"),
                    final_report_format="json",
                    final_report_path=str(Path(tmpdir) / "final"),
                )
        self.assertEqual(len(validate_calls), 2)
        self.assertIsNone(validate_calls[0]["validation_chunk_size"])
        self.assertEqual(validate_calls[1]["validation_chunk_size"], 500)
        self.assertEqual(validate_calls[1]["sleep_between_validation_chunks_seconds"], 1.0)
        self.assertTrue(any("Re-running validation with chunking" in message for message in result.messages))


if __name__ == "__main__":
    unittest.main()
