from __future__ import annotations

import time
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from geoqa.interactive_validation import validate_layer
from geoqa.validation_runtime import (
    FileValidationCache,
    InMemoryValidationCache,
    ValidationLimits,
    ValidationProfile,
    ValidationProgressEvent,
    clear_custom_validators,
    clear_validation_profiles,
    get_validation_profile,
    register_custom_validator,
    register_validation_profile,
)
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

    def __init__(self, coords) -> None:
        self.coords = list(coords)


class SimpleLayer:
    def __init__(self, records: list[dict[str, object]], *, attrs: dict[str, object] | None = None) -> None:
        self._frame = pd.DataFrame(records)
        self.attrs = attrs or {}
        self.crs = None

    @property
    def columns(self):
        return self._frame.columns

    def iterrows(self):
        return self._frame.iterrows()

    def __getitem__(self, key):
        return self._frame.__getitem__(key)

    def __len__(self) -> int:
        return len(self._frame)


class TestValidationRuntime(unittest.TestCase):
    def setUp(self) -> None:
        clear_custom_validators()
        clear_validation_profiles()

    def tearDown(self) -> None:
        clear_custom_validators()
        clear_validation_profiles()

    def test_custom_validator_registration_and_execution(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}])

        def custom_validator(current_layer, **context):
            self.assertIsNone(context["expected_crs"])
            return [
                ValidationIssue(
                    "custom_runtime_issue",
                    "medium",
                    "Custom validator ran.",
                    "Review the custom runtime validator output.",
                    1,
                )
            ]

        register_custom_validator("geometry", "custom_runtime", custom_validator)
        issues = validate_layer(layer, "geometry")
        self.assertTrue(any(issue.problem_name == "custom_runtime_issue" for issue in issues))

    def test_validation_profile_limits_execution(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": None}, {"ID": 2, "geometry": FakeGeometry(0, 0)}])
        profile = ValidationProfile(
            name="geometry_quick",
            dataset_type="geometry",
            enabled_validators=("null_geometry",),
        )
        register_validation_profile(profile)

        issues = validate_layer(layer, "geometry", profile="geometry_quick")
        self.assertEqual([issue.problem_name for issue in issues], ["null_geometry"])
        self.assertIsNotNone(get_validation_profile("geometry_quick"))

    def test_progress_callback_receives_events(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": None}, {"ID": 2, "geometry": FakeGeometry(0, 0)}])
        events: list[ValidationProgressEvent] = []

        validate_layer(layer, "geometry", progress_callback=events.append, profile=ValidationProfile(name="all"))

        self.assertEqual(len(events), 7)
        self.assertEqual(events[0].status, "started")
        self.assertEqual(events[1].status, "completed")
        self.assertEqual(events[0].validator_name, "null_geometry")
        self.assertEqual(events[-1].status, "skipped")
        self.assertEqual(events[-1].validator_name, "self_intersection")

    def test_cache_reuses_validator_result(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}], attrs={"source_path": "memory://layer"})
        cache = InMemoryValidationCache()
        calls = {"count": 0}

        def cached_validator(current_layer, **_context):
            calls["count"] += 1
            return [
                ValidationIssue(
                    "cached_custom_issue",
                    "low",
                    "Cacheable custom validator ran.",
                    "No action needed.",
                    1,
                )
            ]

        register_custom_validator("geometry", "cached_validator", cached_validator)
        first = validate_layer(layer, "geometry", cache=cache, cache_tag="demo")
        second = validate_layer(layer, "geometry", cache=cache, cache_tag="demo")

        self.assertEqual(calls["count"], 1)
        self.assertTrue(any(issue.problem_name == "cached_custom_issue" for issue in first))
        self.assertTrue(any(issue.problem_name == "cached_custom_issue" for issue in second))

    def test_parallel_validation_execution_runs_custom_validators(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}])
        completed: list[str] = []

        def parallel_one(current_layer, **_context):
            time.sleep(0.05)
            return [ValidationIssue("parallel_one_issue", "low", "first", "none", 1)]

        def parallel_two(current_layer, **_context):
            time.sleep(0.05)
            return [ValidationIssue("parallel_two_issue", "low", "second", "none", 1)]

        register_custom_validator("geometry", "parallel_one", parallel_one)
        register_custom_validator("geometry", "parallel_two", parallel_two)
        profile = ValidationProfile(
            name="parallel_geometry",
            dataset_type="geometry",
            enabled_validators=("parallel_one", "parallel_two"),
        )

        events: list[ValidationProgressEvent] = []
        issues = validate_layer(layer, "geometry", profile=profile, progress_callback=events.append, max_workers=2)

        completed = [event.validator_name for event in events if event.status == "completed"]
        self.assertEqual(set(completed), {"parallel_one", "parallel_two"})
        self.assertEqual({issue.problem_name for issue in issues}, {"parallel_one_issue", "parallel_two_issue"})

    def test_file_backed_cache_reuses_results_across_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}], attrs={"source_path": "memory://layer"})
            cache = FileValidationCache(Path(temp_dir) / "cache")
            calls = {"count": 0}

            def cached_validator(current_layer, **_context):
                calls["count"] += 1
                return [ValidationIssue("file_cached_issue", "low", "cached", "none", 1)]

            register_custom_validator("geometry", "file_cached_validator", cached_validator)
            first = validate_layer(layer, "geometry", cache=cache, cache_tag="file-cache")
            second = validate_layer(layer, "geometry", cache=cache, cache_tag="file-cache")

            self.assertEqual(calls["count"], 1)
            self.assertTrue(any(issue.problem_name == "file_cached_issue" for issue in first))
            self.assertTrue(any(issue.problem_name == "file_cached_issue" for issue in second))

    def test_validation_limits_reject_too_many_features(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}, {"ID": 2, "geometry": FakeGeometry(1, 1)}])

        with self.assertRaisesRegex(ValueError, "above the configured limit of 1"):
            validate_layer(layer, "geometry", limits=ValidationLimits(max_features=1))

    def test_validation_limits_use_source_file_size_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "demo.geojson"
            source_path.write_text("x" * 4096, encoding="utf-8")
            layer = SimpleLayer(
                [{"ID": 1, "geometry": FakeGeometry(0, 0)}],
                attrs={"source_path": str(source_path)},
            )

            with self.assertRaisesRegex(ValueError, "source file is"):
                validate_layer(layer, "geometry", limits=ValidationLimits(max_source_size_mb=0.001))

    def test_validation_limits_can_reject_high_vertex_count(self) -> None:
        layer = SimpleLayer(
            [
                {
                    "ID": 1,
                    "geometry": FakeLineGeometry([(0, 0), (1, 1), (2, 2), (3, 3)]),
                }
            ]
        )

        with self.assertRaisesRegex(ValueError, "geometry vertices"):
            validate_layer(layer, "geometry", limits=ValidationLimits(max_total_vertices=3))

    def test_prefer_high_priority_can_defer_lower_priority_validators_under_actionable_stop(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": FakeGeometry(0, 0)}])
        calls: list[str] = []

        def informational_validator(current_layer, **_context):
            calls.append("informational_validator")
            return [
                ValidationIssue(
                    "informational_issue",
                    "low",
                    "informational",
                    "none",
                    1,
                    actionable=False,
                    confidence="low",
                )
            ]

        def actionable_validator(current_layer, **_context):
            calls.append("actionable_validator")
            return [
                ValidationIssue(
                    "actionable_issue",
                    "high",
                    "actionable",
                    "none",
                    1,
                    actionable=True,
                    confidence="high",
                )
            ]

        register_custom_validator("geometry", "informational_validator", informational_validator)
        register_custom_validator("geometry", "actionable_validator", actionable_validator)
        profile = ValidationProfile(
            name="priority_geometry",
            dataset_type="geometry",
            enabled_validators=("informational_validator", "actionable_validator"),
        )

        result = validate_layer(
            layer,
            "geometry",
            profile=profile,
            prefer_high_priority=True,
            problem_policies={
                "actionable_validator": {"priority_score": 10, "actionable": True, "confidence": "high"},
                "informational_validator": {"priority_score": 1, "actionable": False, "confidence": "low"},
            },
            stop_after_actionable=1,
            return_result=True,
        )

        self.assertEqual(calls, ["actionable_validator"])
        self.assertTrue(result.partial_result)
        self.assertEqual(result.stop_reason, "actionable_target_reached")
        self.assertIn("informational_validator", result.validators_deferred)


if __name__ == "__main__":
    unittest.main()
