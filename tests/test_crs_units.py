"""Tests for CRS assessment, unit reasoning, and guarded reprojection.

The property that matters: nothing is changed silently. Every recommendation is
a finding, and the reprojection helper refuses to return a result it cannot
reconcile.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from geoqa.validations.crs_units import (
    assess_crs,
    check_length_units,
    crs_report,
    reproject_within_tolerance,
    validate_crs_consistency,
)


def _lines(crs="EPSG:4326", n=20, **extra):
    """Line features whose coordinates suit the CRS unit.

    Geographic data spans ~0.01 degrees; projected data spans ~1000 m at the
    same real location (UTM 40N, near lon 55 / lat 23).
    """
    if str(crs) in {"EPSG:4326", "EPSG:3857"}:
        x0, y0, step = 55.0, 23.0, 0.01
    else:
        x0, y0, step = 400_000.0, 2_600_000.0, 1000.0
    geoms = [
        LineString([(x0 + i * step, y0), (x0 + (i + 1) * step, y0)])
        for i in range(n)
    ]
    return gpd.GeoDataFrame(extra, geometry=geoms, crs=crs)


def _names(issues):
    return [i.problem_name for i in issues]


# --- assessment ---------------------------------------------------------

def test_geographic_crs_is_detected():
    assessment = assess_crs(_lines("EPSG:4326"))
    assert assessment.is_geographic is True
    assert assessment.is_usable_for_measurement is False
    assert assessment.geographic_warning


def test_projected_crs_is_usable():
    assessment = assess_crs(_lines("EPSG:32640"))
    assert assessment.is_geographic is False
    assert assessment.is_usable_for_measurement is True
    assert assessment.metres_per_unit == pytest.approx(1.0)


def test_web_mercator_is_flagged():
    assessment = assess_crs(_lines("EPSG:3857"))
    assert assessment.is_web_mercator is True
    assert "Web Mercator" in assessment.geographic_warning


def test_polar_crs_is_flagged():
    assessment = assess_crs(_lines("EPSG:3413"))
    assert assessment.is_polar is True


def test_missing_crs_reports_critical_and_stops():
    layer = _lines()
    layer = layer.set_crs(None, allow_override=True)
    issues = validate_crs_consistency(layer)
    assert "missing_spatial_reference" in _names(issues)
    assert str(issues[0].severity) == "critical"


def test_utm_is_recommended_for_geographic_data():
    assessment = assess_crs(_lines("EPSG:4326"))
    assert assessment.recommended_crs == 32640   # lon 55 falls in zone 40
    assert "UTM" in (assessment.recommended_name or "")


def test_recommendation_is_a_finding_not_an_action():
    layer = _lines("EPSG:4326")
    issues = validate_crs_consistency(layer)
    assert "crs_reprojection_recommended" in _names(issues)
    recommendation = next(
        i for i in issues if i.problem_name == "crs_reprojection_recommended"
    )
    assert "unchanged" in recommendation.description


def test_geographic_crs_says_lengths_are_degrees():
    issues = validate_crs_consistency(_lines("EPSG:4326"))
    issue = next(i for i in issues if i.problem_name == "angular_crs_measurements_invalid")
    assert "degrees" in issue.description


def test_web_mercator_area_is_called_unusable():
    issues = validate_crs_consistency(_lines("EPSG:3857"))
    assert "web_mercator_area_unusable" in _names(issues)


# --- unit reasoning -------------------------------------------------------

def test_metre_length_column_is_consistent_in_a_metric_crs():
    layer = _lines("EPSG:32640", pipe_len=[1000.0] * 20)
    findings = check_length_units(layer, columns=["pipe_len"])
    assert len(findings) == 1
    assert findings[0].is_consistent is True
    assert findings[0].implied_unit == "metres"


def test_degree_values_in_a_metric_column_are_flagged():
    """The classic failure: EPSG:32640 coordinates with degree-valued lengths."""
    layer = _lines("EPSG:32640", pipe_len=[0.01] * 20)
    findings = check_length_units(layer, columns=["pipe_len"])
    assert findings[0].is_consistent is False
    assert "smaller than the geometric length" in findings[0].note


def test_feet_column_is_identified():
    layer = _lines("EPSG:32640", pipe_len=[3280.84] * 20)
    findings = check_length_units(layer, columns=["pipe_len"])
    assert findings[0].is_consistent is True
    assert findings[0].implied_unit == "feet"


def test_inconsistent_length_becomes_a_high_finding():
    layer = _lines("EPSG:32640", pipe_len=[0.01] * 20)
    issues = validate_crs_consistency(layer, length_columns=["pipe_len"])
    issue = next(i for i in issues if i.problem_name == "length_unit_inconsistent_with_crs")
    assert str(issue.severity) == "high"
    assert "pipe_len" in issue.description


def test_length_columns_are_discovered_by_name():
    layer = _lines("EPSG:32640", pipe_length=[1000.0] * 20)
    findings = check_length_units(layer)
    assert [f.column for f in findings] == ["pipe_length"]


def test_non_numeric_columns_are_ignored():
    layer = _lines("EPSG:32640", pipe_len=["long", "x"] * 10)
    assert check_length_units(layer) == []


def test_zero_and_negative_values_are_skipped():
    layer = _lines("EPSG:32640", pipe_len=[0.0] * 20)
    assert check_length_units(layer, columns=["pipe_len"]) == []


def test_degree_crs_length_column_reports_degrees():
    """In a geographic CRS a computed length is already in degrees."""
    layer = _lines("EPSG:4326", pipe_len=[0.01] * 20)
    findings = check_length_units(layer, columns=["pipe_len"])
    assert findings[0].is_consistent is True
    assert findings[0].implied_unit == "degrees"


# --- guarded reprojection ---------------------------------------------------

def test_reprojection_returns_a_new_layer():
    layer = _lines("EPSG:4326")
    projected = reproject_within_tolerance(layer, "EPSG:32640")
    assert projected.crs.to_epsg() == 32640
    assert layer.crs.to_epsg() == 4326, "source layer must not be mutated"


def test_reprojection_records_provenance():
    layer = _lines("EPSG:4326")
    projected = reproject_within_tolerance(layer, "EPSG:32640")
    assert "32640" in projected.attrs["geoqa_reprojected_to"]


def test_reprojection_refuses_when_a_consistent_column_breaks():
    layer = _lines("EPSG:32640", pipe_len=[1000.0] * 20)
    with pytest.raises(RuntimeError, match="internal consistency"):
        reproject_within_tolerance(layer, "EPSG:4326")


def test_reprojection_to_same_crs_is_a_no_op():
    layer = _lines("EPSG:32640")
    assert reproject_within_tolerance(layer, "EPSG:32640").crs.to_epsg() == 32640


def test_reprojection_without_source_crs_raises():
    layer = _lines()
    layer = layer.set_crs(None, allow_override=True)
    with pytest.raises(ValueError, match="no CRS"):
        reproject_within_tolerance(layer, "EPSG:32640")


def test_reprojection_preserves_feature_count():
    layer = _lines("EPSG:4326", n=37)
    assert len(reproject_within_tolerance(layer, "EPSG:32640")) == 37


def test_reprojected_length_is_metres():
    """The practical outcome: degrees in, metres out."""
    layer = _lines("EPSG:4326")
    projected = reproject_within_tolerance(layer, "EPSG:32640")
    # 0.01 degrees of longitude at 23N is roughly 1020 m.
    assert 900 < float(projected.geometry.iloc[0].length) < 1150


# --- report ------------------------------------------------------------------

def test_report_carries_everything():
    layer = _lines("EPSG:32640", pipe_len=[1000.0] * 20)
    report = crs_report(layer)
    assert report["feature_count"] == 20
    assert report["crs"]["is_geographic"] is False
    assert len(report["length_columns"]) == 1
    assert len(report["total_bounds"]) == 4


def test_point_layer_report_works():
    layer = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(55, 23)], crs="EPSG:4326")
    assert crs_report(layer)["feature_count"] == 1


def test_empty_layer_is_safe():
    empty = gpd.GeoDataFrame({"pipe_len": []}, geometry=[], crs="EPSG:32640")
    assert crs_report(empty)["feature_count"] == 0
    assert check_length_units(empty) == []