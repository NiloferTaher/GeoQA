"""Tests for cross-period recurrence.

The distinction under test is the one that changes what gets repaired: a
recurring asset is a chronic component defect, a recurring location with a
different asset is an upstream or boundary problem and replacing the component
will not help.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoqa.validations.repeat_incident import (
    RepeatProfile,
    detect_period_gaps,
    profile_repeats,
    validate_repeats,
)


def _layer(rows):
    return gpd.GeoDataFrame(
        rows,
        geometry=[Point(r.pop("x"), r.pop("y")) for r in rows],
        crs="EPSG:32640",
    )


def _names(issues):
    return [i.problem_name for i in issues]


# --- the central distinction ----------------------------------------------

def test_same_asset_across_periods_is_a_chronic_defect():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-03", "asset": "P1", "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(layer, period_column="period", key_column="asset")
    repeat = next(i for i in issues if i.problem_name == "repeat_same_asset")
    assert str(repeat.severity) == "high"
    assert "chronic asset" in repeat.description
    assert repeat.to_dict()["period_count"] == 3


def test_different_asset_same_place_is_an_upstream_problem():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P2", "x": 0.0, "y": 0.0},
        {"period": "2025-03", "asset": "P3", "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(layer, period_column="period", key_column="asset")
    assert "repeat_same_place" in _names(issues)
    issue = next(i for i in issues if i.problem_name == "repeat_same_place")
    assert "asset is not the cause" in issue.description
    assert set(issue.to_dict()["asset_ids"]) == {"P1", "P2", "P3"}


def test_the_two_kinds_are_counted_separately():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-01", "asset": "P9", "x": 500.0, "y": 500.0},
        {"period": "2025-02", "asset": "P8", "x": 500.0, "y": 500.0},
    ])
    profile = profile_repeats(layer, period_column="period", key_column="asset")
    assert profile.same_asset == 1
    assert profile.same_place == 1


def test_without_a_key_column_recurrence_is_unattributed():
    layer = _layer([
        {"period": "2025-01", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(layer, period_column="period")
    issue = next(i for i in issues if i.problem_name == "repeat_unattributed")
    assert str(issue.severity) == "medium"
    assert "logical-asset key" in issue.description


# --- spatial grouping ------------------------------------------------------

def test_locations_are_grouped_within_tolerance():
    """A leak recorded a few metres apart is the same place, not two."""
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 3.0, "y": 4.0},
    ])
    profile = profile_repeats(layer, period_column="period", key_column="asset")
    assert len(profile.findings) == 1
    assert profile.findings[0].period_count == 2


def test_locations_beyond_tolerance_are_separate():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 500.0, "y": 500.0},
    ])
    assert profile_repeats(layer, period_column="period", key_column="asset").findings == []


def test_tolerance_is_configurable():
    rows = [
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 20.0, "y": 0.0},
    ]
    layer = _layer(rows)
    assert profile_repeats(layer, period_column="period", key_column="asset").findings
    assert not profile_repeats(
        layer, period_column="period", key_column="asset", location_tolerance_m=5.0
    ).findings


def test_single_occurrence_is_not_a_repeat():
    layer = _layer([{"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0}])
    assert validate_repeats(layer, period_column="period", key_column="asset") == []


def test_two_observations_in_one_period_are_not_a_repeat():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-01", "asset": "P1", "x": 1.0, "y": 1.0},
    ])
    assert validate_repeats(layer, period_column="period", key_column="asset") == []


# --- period gaps ---------------------------------------------------------------

def test_contiguous_periods_have_no_gap():
    assert detect_period_gaps(["2025-01", "2025-02", "2025-03"]) == []


def test_monthly_gap_is_detected():
    assert detect_period_gaps(["2025-01", "2025-04"]) == [("2025-01", "2025-04")]


def test_named_months_are_understood():
    assert detect_period_gaps(["Jan2025", "Mar2025"]) == [("Jan2025", "Mar2025")]


def test_unparseable_labels_are_not_treated_as_gaps():
    assert detect_period_gaps(["Q1 2025", "Q3 2025"]) == []


def test_gap_is_reported_alongside_the_repeat():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-04", "asset": "P1", "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(layer, period_column="period", key_column="asset")
    gap = next(i for i in issues if i.problem_name == "period_gap")
    assert str(gap.severity) == "medium"
    assert gap.to_dict()["from"] == "2025-01"
    assert gap.to_dict()["to"] == "2025-04"


def test_missing_expected_period_is_high():
    """A period with no data is not evidence that nothing happened."""
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(
        layer, period_column="period", key_column="asset",
        expected_periods=["2025-01", "2025-02", "2025-03"],
    )
    missing = next(i for i in issues if i.problem_name == "period_missing")
    assert str(missing.severity) == "high"
    assert missing.to_dict()["missing_period"] == "2025-03"


def test_periods_seen_includes_expected_when_absent():
    layer = _layer([{"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0}])
    profile = profile_repeats(
        layer, period_column="period", key_column="asset",
        expected_periods=["2025-01", "2025-02"],
    )
    assert "2025-02" in profile.periods_seen


# --- profile --------------------------------------------------------------------

def test_profile_summary_adds_up():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 0.0, "y": 0.0},
    ])
    summary = profile_repeats(layer, period_column="period", key_column="asset").summary()
    assert summary["occurrences"] == 2
    assert summary["repeat_same_asset"] == 1
    assert summary["periods_seen"] == ["2025-01", "2025-02"]


def test_findings_are_ordered_by_persistence():
    layer = _layer([
        {"period": "2025-01", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": "P1", "x": 0.0, "y": 0.0},
        {"period": "2025-01", "asset": "P9", "x": 900.0, "y": 900.0},
        {"period": "2025-02", "asset": "P9", "x": 900.0, "y": 900.0},
        {"period": "2025-03", "asset": "P9", "x": 900.0, "y": 900.0},
    ])
    findings = profile_repeats(layer, period_column="period", key_column="asset").findings
    assert findings[0].period_count == 3
    assert findings[0].repeats == 2


def test_missing_period_column_raises():
    layer = _layer([{"period": "2025-01", "x": 0.0, "y": 0.0}])
    with pytest.raises(KeyError):
        profile_repeats(layer, period_column="nope")


def test_null_geometry_is_skipped():
    frame = gpd.GeoDataFrame(
        {"period": ["2025-01", "2025-02"], "asset": ["P1", "P1"]},
        geometry=[Point(0, 0), None],
        crs="EPSG:32640",
    )
    assert validate_repeats(frame, period_column="period", key_column="asset") == []


def test_empty_layer_is_safe():
    empty = gpd.GeoDataFrame({"period": [], "asset": []}, geometry=[], crs="EPSG:32640")
    assert validate_repeats(empty, period_column="period", key_column="asset") == []


def test_null_asset_falls_back_to_unattributed():
    layer = _layer([
        {"period": "2025-01", "asset": None, "x": 0.0, "y": 0.0},
        {"period": "2025-02", "asset": None, "x": 0.0, "y": 0.0},
    ])
    issues = validate_repeats(layer, period_column="period", key_column="asset")
    assert "repeat_unattributed" in _names(issues)