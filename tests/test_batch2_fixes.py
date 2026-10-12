import pytest
from shapely.geometry import LineString, Polygon

from geoqa.confidence import assess_finding
from geoqa.validation_runtime import (
    ValidationProfile,
    build_validation_cache_key,
    execute_validation_plan,
)
from geoqa.validations.base import ValidationIssue, ValidatorSkipped
from geoqa.validations.topology import duplicate_geometry_same_layer, polygon_gap_same_layer
from test_shape_and_dispatch import _frame


def _line_layer():
    return _frame(
        [
            {"geometry": LineString([(0, 0), (1, 0)])},
            {"geometry": LineString([(1, 0), (2, 0)])},
        ]
    )


def _coverage(result, validator_name):
    return next(
        row for row in result.validator_coverage
        if row["validator_name"] == validator_name
    )


def test_info_issue_has_lower_priority_than_low_issue() -> None:
    low = ValidationIssue("same_issue", "low", "finding", "fix", 1)
    info = ValidationIssue("same_issue", "info", "finding", "fix", 1)

    assert info.priority_score < low.priority_score


def test_within_tolerance_conditions_do_not_get_margin_evidence() -> None:
    near_miss = ValidationIssue(
        "suspicious_near_miss_endpoints",
        "medium",
        "finding",
        "fix",
        1,
        extra={"distance": 0.5, "tolerance": 1.0},
    )
    polygon_gap = ValidationIssue(
        "polygon_gap_same_layer",
        "medium",
        "finding",
        "fix",
        1,
        extra={"distance": 3.0, "tolerance": 1.0},
    )

    near_miss_evidence = assess_finding(near_miss, prior=0.5).evidence
    polygon_gap_evidence = assess_finding(polygon_gap, prior=0.5).evidence

    assert not any(item.name == "below_declared_tolerance" for item in near_miss_evidence)
    assert any(item.name == "margin_past_tolerance" for item in polygon_gap_evidence)


@pytest.mark.parametrize(
    ("dataset_type", "validator", "context_key", "missing_context", "context_value"),
    [
        ("geometry", "below_minimum_feature_length", "min_length", {}, 1.0),
        (
            "topology",
            "suspicious_near_miss_endpoints",
            "snap_tolerance",
            {"snap_tolerance": 0},
            1.0,
        ),
    ],
)
def test_missing_threshold_inputs_are_skipped_and_positive_inputs_complete(
    dataset_type, validator, context_key, missing_context, context_value
) -> None:
    profile = ValidationProfile(
        name=f"required_{validator}",
        dataset_type=dataset_type,
        enabled_validators=(validator,),
    )
    layer = _line_layer()
    missing = execute_validation_plan(
        layer,
        dataset_type,
        profile=profile,
        return_result=True,
        **missing_context,
    )
    supplied = execute_validation_plan(
        layer,
        dataset_type,
        profile=profile,
        return_result=True,
        **{context_key: context_value},
    )

    missing_coverage = _coverage(missing, validator)
    assert missing_coverage["status"] == "skipped"
    assert missing_coverage["reason"] == "missing_input"
    assert _coverage(supplied, validator)["status"] == "completed"


def test_missing_threshold_input_is_skipped_in_parallel() -> None:
    validator = "below_minimum_feature_length"
    profile = ValidationProfile(
        name="parallel_missing_threshold",
        dataset_type="geometry",
        enabled_validators=(validator,),
    )

    result = execute_validation_plan(
        _line_layer(),
        "geometry",
        profile=profile,
        return_result=True,
        max_workers=2,
    )

    assert _coverage(result, validator)["status"] == "skipped"
    assert validator not in result.validators_completed


@pytest.mark.parametrize(
    ("context", "first_value", "second_value"),
    [
        ({"tolerance": 1.0}, 1.0, 2.0),
        ({"min_gap_area": 1.0}, 1.0, 2.0),
    ],
)
def test_cache_key_changes_with_validation_threshold(context, first_value, second_value) -> None:
    left = {**context, next(iter(context)): first_value}
    right = {**context, next(iter(context)): second_value}
    layer = _line_layer()

    assert build_validation_cache_key(
        layer, "geometry", "validator", context=left
    ) != build_validation_cache_key(layer, "geometry", "validator", context=right)


def test_reversed_line_geometries_are_reported_as_duplicates() -> None:
    layer = _frame(
        [
            {"geometry": LineString([(0, 0), (1, 1), (2, 1)])},
            {"geometry": LineString([(2, 1), (1, 1), (0, 0)])},
        ]
    )

    issues = duplicate_geometry_same_layer(layer)

    assert len(issues) == 2
    assert {issue.problem_name for issue in issues} == {"duplicate_geometry_same_layer"}


def test_polygon_gap_union_error_is_reported_as_skipped(monkeypatch) -> None:
    import shapely.ops

    layer = _frame([{"geometry": Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])}])

    def fail_union(_geometries):
        raise RuntimeError("union failed")

    monkeypatch.setattr(shapely.ops, "unary_union", fail_union)
    with pytest.raises(ValidatorSkipped, match="union failed") as caught:
        polygon_gap_same_layer(layer)

    assert caught.value.reason == "validator_error"


def test_self_intersection_runtime_error_is_covered_as_skipped(monkeypatch) -> None:
    import geoqa.validation_runtime as runtime

    profile = ValidationProfile(
        name="self_intersection_error",
        dataset_type="geometry",
        enabled_validators=("self_intersection",),
    )

    def fail_self_intersection(_layer):
        raise RuntimeError("self-intersection failed")

    monkeypatch.setattr(runtime, "self_intersection", fail_self_intersection)
    result = runtime.execute_validation_plan(
        _line_layer(),
        "geometry",
        profile=profile,
        return_result=True,
    )

    coverage = _coverage(result, "self_intersection")
    assert coverage["status"] == "skipped"
    assert coverage["reason"] == "validator_error"
    assert coverage["notes"] == "self-intersection failed"
