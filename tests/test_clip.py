"""Tests for clip assignment and clip completeness.

The behaviour worth protecting: the assignment percentage is the caller's, not
the module's, and a half-geometry is reported as evidence of a centreline clip
rather than as a validity error, because it is perfectly valid geometry.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from geoqa.validations.clip import (
    DEFAULT_ASSIGNMENT_THRESHOLD,
    ClipMatch,
    StraddleRecord,
    profile_clip_assignment,
    profile_clip_completeness,
    validate_clip_assignment,
    validate_clip_completeness,
)


def _names(issues):
    return [i.problem_name for i in issues]


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layer(geometries, ids=None):
    return gpd.GeoDataFrame(
        {"id": ids if ids is not None else list(range(len(geometries)))},
        geometry=geometries,
        crs="EPSG:32640",
    )


#: Region covering x <= 5. A box spanning x = 0..10 lies half inside it.
INSIDE_LEFT_HALF = Polygon([(-100, -100), (5, -100), (5, 100), (-100, 100)])
#: Region covering x >= 9. A box spanning x = 0..10 is 10 percent inside it.
INSIDE_RIGHT_TENTH = Polygon([(9, -100), (200, -100), (200, 100), (9, 100)])


# --- assignment percentage is the caller's ---------------------------------

def test_threshold_is_configurable():
    """90% left of the line, and the answer flips with the rule."""
    # 9 of 10 units on the left.
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    layer = _layer([geometry])

    at_fifty = profile_clip_assignment(layer, INSIDE_RIGHT_TENTH, assignment_threshold=0.5)
    at_ninety = profile_clip_assignment(layer, INSIDE_RIGHT_TENTH, assignment_threshold=0.9)
    at_ninetyfive = profile_clip_assignment(layer, INSIDE_RIGHT_TENTH, assignment_threshold=0.95)

    assert at_fifty["records"][0]["assigned_side"] == "outside"
    assert at_ninety["records"][0]["assigned_side"] == "outside"
    # At 95% the 90% split no longer clears the bar.
    assert at_ninetyfive["records"][0]["assigned_side"] is None


def test_default_threshold_is_a_half_and_is_still_overridable():
    assert DEFAULT_ASSIGNMENT_THRESHOLD == 0.5
    layer = _layer([Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])])
    custom = profile_clip_assignment(layer, INSIDE_RIGHT_TENTH, assignment_threshold=0.8)
    assert custom["assignment_threshold"] == 0.8


def test_threshold_out_of_range_is_refused():
    layer = _layer([_box(0, 0, 1, 1)])
    for bad in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="greater than 0"):
            profile_clip_assignment(layer, INSIDE_LEFT_HALF, assignment_threshold=bad)


def test_no_threshold_measures_without_assigning():
    """The module refuses to pick a percentage for the caller."""
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    issues = validate_clip_assignment(_layer([geometry]), INSIDE_LEFT_HALF, assignment_threshold=None)
    assert "clip_assignment_unresolved" in _names(issues)


def test_features_entirely_on_one_side_are_not_straddlers():
    layer = _layer([_box(0, 0, 1, 1)])
    assert profile_clip_assignment(layer, INSIDE_LEFT_HALF)["straddlers"] == 0


def test_split_is_measured_from_real_area():
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    profile = profile_clip_assignment(layer=_layer([geometry]), boundary=INSIDE_RIGHT_TENTH)
    record = profile["records"][0]
    assert record["fraction_inside"] == pytest.approx(0.1, abs=0.01)
    assert record["fraction_outside"] == pytest.approx(0.9, abs=0.01)
    assert record["dominant_side"] == "outside"


def test_near_threshold_is_flagged():
    """A 52/48 split is a coin-flip and should not be presented as a finding."""
#: Region covering x <= 5.2, so a box spanning x = 0..10 splits 52/48.
INSIDE_52 = Polygon([(-100, -100), (5.2, -100), (5.2, 100), (-100, 100)])


def test_near_threshold_is_flagged():
    """A 52/48 split is a coin-flip and should not be presented as a finding."""
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    issues = validate_clip_assignment(_layer([geometry]), INSIDE_52, near_threshold=0.05)
    assert "clip_assignment_near_threshold" in _names(issues)


def test_clearly_asymmetric_split_is_evidence_not_a_warning():
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    issues = validate_clip_assignment(_layer([geometry]), INSIDE_RIGHT_TENTH, near_threshold=0.05)
    assert _names(issues) == ["clip_straddles_boundary"]
    assert str(issues[0].severity) == "info"


def test_evidence_can_be_suppressed():
    geometry = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    assert validate_clip_assignment(_layer([geometry]), INSIDE_RIGHT_TENTH, report_evidence=False) == []


# --- clip completeness ------------------------------------------------------

def test_exactly_half_is_high():
    """The signature of a centreline clip: valid geometry, wrong data."""
    source = _layer([_box(0, 0, 10, 10)], ids=["parcel"])
    clipped = _layer([_box(0, 0, 5, 10)], ids=["parcel_left"])
    issues = validate_clip_completeness(clipped, source)
    issue = next(i for i in issues if i.problem_name == "clip_feature_half_area")
    assert str(issue.severity) == "high"
    assert issue.to_dict()["area_fraction"] == pytest.approx(0.5)


def test_full_feature_is_not_half():
    source = _layer([_box(0, 0, 10, 10)], ids=["parcel"])
    clipped = _layer([_box(0, 0, 10, 10)], ids=["parcel"])
    assert "clip_feature_half_area" not in _names(validate_clip_completeness(clipped, source))


def test_half_fraction_is_configurable():
    """A corridor clip at a third is also a clip, just not at a half."""
    source = _layer([_box(0, 0, 10, 10)], ids=["parcel"])
    clipped = _layer([_box(0, 0, 4, 10)], ids=["parcel_part"])
    assert "clip_feature_half_area" not in _names(validate_clip_completeness(clipped, source))
    assert "clip_feature_half_area" in _names(
        validate_clip_completeness(clipped, source, half_fraction=0.4)
    )


def test_heavily_truncated_feature_is_high():
    source = _layer([_box(0, 0, 10, 10)], ids=["parcel"])
    clipped = _layer([_box(0, 0, 1, 10)], ids=["sliver"])
    issues = validate_clip_completeness(clipped, source, min_area_fraction=0.25)
    assert "clip_feature_heavily_truncated" in _names(issues)


def test_source_feature_missing_from_clip_is_high():
    source = _layer([_box(0, 0, 10, 10), _box(100, 100, 110, 110)], ids=["a", "b"])
    clipped = _layer([_box(0, 0, 10, 10)], ids=["a_left"])
    issues = validate_clip_completeness(clipped, source)
    issue = next(i for i in issues if i.problem_name == "clip_feature_missing_after_clip")
    assert issue.to_dict()["source_id"] == "b"


def test_clipped_feature_with_no_source_is_high():
    source = _layer([_box(0, 0, 10, 10)], ids=["a"])
    clipped = _layer([_box(500, 500, 510, 510)], ids=["stranger"])
    assert "clip_feature_absent_from_source" in _names(validate_clip_completeness(clipped, source))


def test_untouched_layer_reports_nothing_serious():
    layer = _layer([_box(0, 0, 10, 10), _box(20, 20, 30, 30)], ids=["a", "b"])
    assert validate_clip_completeness(layer, layer) == []


def test_profile_summary_shape():
    source = _layer([_box(0, 0, 10, 10)], ids=["p"])
    clipped = _layer([_box(0, 0, 5, 10)], ids=["p_half"])
    summary = profile_clip_completeness(clipped, source).summary()
    assert summary["matched"] == 1
    assert summary["halves"] == 1


def test_empty_clipped_layer_is_safe():
    source = _layer([_box(0, 0, 10, 10)], ids=["p"])
    empty = gpd.GeoDataFrame({"id": []}, geometry=[], crs="EPSG:32640")
    assert "clip_feature_missing_after_clip" in _names(validate_clip_completeness(empty, source))


def test_half_is_not_reported_twice():
    """A half is also heavily truncated; one feature, one finding."""
    source = _layer([_box(0, 0, 10, 10)], ids=["p"])
    clipped = _layer([_box(0, 0, 5, 10)], ids=["p_half"])
    names = _names(validate_clip_completeness(clipped, source, min_area_fraction=0.25))
    assert names.count("clip_feature_half_area") == 1
    assert "clip_feature_heavily_truncated" not in names


# --- record types -----------------------------------------------------------

def test_straddle_record_reports_its_own_threshold():
    record = StraddleRecord("p", 100.0, 0.7, 0.3, "boundary", False)
    assert record.as_dict()["assignment_fraction"] == pytest.approx(0.7)
    assert record.dominant_side == "boundary"


def test_clip_match_is_half_within_tolerance():
    assert ClipMatch("a", "b", 5.0, 10.0, 0.5).is_half is True
    assert ClipMatch("a", "b", 9.0, 10.0, 0.9).is_half is False