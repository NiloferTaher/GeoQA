"""Tests for boundary-cut and continuity-break detection.

The behaviour that matters is the distinction the module exists for: a feature
cut by a boundary that nothing declares is a **high** finding, while the same
fragment on a reference that other features also claim is a legitimate
subdivision and only **low**. Conflating those two makes the check useless on
any layer that was correctly clipped.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon, box

from geoqa.validations.boundary_conformance import (
    continuity_breaks,
    profile_boundary_conformance,
    validate_boundary_conformance,
)


def _polys(rows):
    return gpd.GeoDataFrame(
        rows,
        geometry=[r.pop("geometry") for r in rows],
        crs="EPSG:4326",
    )


def _reference(polygons):
    return gpd.GeoDataFrame(
        {"ref_id": list(range(len(polygons)))},
        geometry=polygons,
        crs="EPSG:4326",
    )


def _names(issues):
    return [i.problem_name for i in issues]


# --- the accidental cut ------------------------------------------------

def test_fragment_of_a_larger_reference_is_high():
    """A small piece of a big polygon, with nothing else claiming it."""
    big = box(0, 0, 10, 10)
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 4, 10)}])
    reference = _reference([big])

    issues = validate_boundary_conformance(layer, reference)
    assert len(issues) == 1
    assert str(issues[0].severity) == "high"
    assert issues[0].problem_name == "boundary_condition_conformance"


def test_coverage_is_reported():
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 5, 10)}])
    reference = _reference([box(0, 0, 10, 10)])
    issue = validate_boundary_conformance(layer, reference)[0]
    assert issue.to_dict()["coverage"] == pytest.approx(0.5, abs=0.001)


def test_fully_covered_feature_is_silent():
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 10, 10)}])
    reference = _reference([box(0, 0, 10, 10)])
    assert validate_boundary_conformance(layer, reference) == []


# --- the legitimate subdivision ----------------------------------------

def test_subdivided_reference_is_low_not_high():
    """Two features claiming one reference means it was deliberately split."""
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([
        {"fid": 1, "geometry": box(0, 0, 5, 10)},
        {"fid": 2, "geometry": box(5, 0, 10, 10)},
    ])

    issues = validate_boundary_conformance(layer, reference)
    assert len(issues) == 2
    assert {str(i.severity) for i in issues} == {"low"}
    assert all(i.to_dict()["shares_reference"] for i in issues)


def test_subdivided_reference_raises_no_undeclared_cut():
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([
        {"fid": 1, "geometry": box(0, 0, 5, 10)},
        {"fid": 2, "geometry": box(5, 0, 10, 10)},
    ])
    profile = profile_boundary_conformance(layer, reference)
    # Still fragments of the reference, but no *undeclared* cut among them.
    assert profile.undeclared_cuts == 0
    assert profile.fragments == 2


# --- the declared boundary ----------------------------------------------

def test_boundary_layer_downgrades_an_explained_cut_to_info():
    """A cut edge that follows a declared boundary is correct behaviour."""
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 4, 10)}])
    # A boundary running down x=4, exactly the fragment's cut edge.
    boundary = gpd.GeoDataFrame(
        {"b": [1]}, geometry=[LineString([(4, 0), (4, 10)])], crs="EPSG:4326"
    )

    issues = validate_boundary_conformance(layer, reference, boundary_layer=boundary)
    assert len(issues) == 1
    assert str(issues[0].severity) == "info"
    assert issues[0].to_dict()["boundary_explains_cut"] is True


def test_unrelated_boundary_does_not_explain_the_cut():
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 4, 10)}])
    boundary = gpd.GeoDataFrame(
        {"b": [1]}, geometry=[LineString([(7, 0), (7, 10)])], crs="EPSG:4326"
    )
    issues = validate_boundary_conformance(layer, reference, boundary_layer=boundary)
    assert str(issues[0].severity) == "high"
    assert issues[0].to_dict()["boundary_explains_cut"] is False


def test_absent_boundary_layer_asks_for_one():
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 4, 10)}])
    issue = validate_boundary_conformance(layer, reference)[0]
    assert issue.to_dict()["boundary_layer_supplied"] is False
    assert "boundary_layer" in issue.description


# --- profile -------------------------------------------------------------

def test_profile_counts_add_up():
    reference = _reference([box(0, 0, 10, 10), box(20, 0, 30, 10)])
    layer = _polys([
        {"fid": 1, "geometry": box(0, 0, 10, 10)},    # covered
        {"fid": 2, "geometry": box(0, 0, 3, 10)},     # fragment
        {"fid": 3, "geometry": box(20, 0, 30, 10)},   # covered
    ])
    profile = profile_boundary_conformance(layer, reference)
    assert profile.features == 3
    assert profile.covered == 2
    assert profile.fragments == 1
    assert profile.undeclared_cuts == 1


def test_profile_summary_serialises():
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([{"fid": 1, "geometry": box(0, 0, 10, 10)}])
    summary = profile_boundary_conformance(layer, reference).summary()
    assert summary["features"] == 1
    assert "covered" in summary["coverage_buckets"]


def test_feature_outside_any_reference_is_not_a_fragment():
    reference = _reference([box(0, 0, 10, 10)])
    layer = _polys([{"fid": 1, "geometry": box(50, 50, 60, 60)}])
    profile = profile_boundary_conformance(layer, reference)
    assert profile.fragments == 0
    assert profile.undeclared_cuts == 0


def test_empty_layer_is_safe():
    reference = _reference([box(0, 0, 10, 10)])
    empty = gpd.GeoDataFrame({"fid": []}, geometry=[], crs="EPSG:4326")
    assert validate_boundary_conformance(empty, reference) == []


def test_null_geometry_is_skipped():
    reference = _reference([box(0, 0, 10, 10)])
    layer = gpd.GeoDataFrame(
        {"fid": [1, 2]},
        geometry=[None, box(0, 0, 10, 10)],
        crs="EPSG:4326",
    )
    assert validate_boundary_conformance(layer, reference) == []


# --- continuity -----------------------------------------------------------

def test_continuity_break_when_a_run_is_cut():
    """One logical asset in two pieces with a gap between them."""
    layer = gpd.GeoDataFrame(
        {"asset": ["A", "A"]},
        geometry=[
            LineString([(0, 0), (5, 0)]),
            LineString([(6, 0), (10, 0)]),
        ],
        crs="EPSG:4326",
    )
    issues = continuity_breaks(layer, key_column="asset")
    assert _names(issues) == ["continuity_break"]
    assert issues[0].to_dict()["gap_distance"] == pytest.approx(1.0)


def test_continuous_run_has_no_break():
    layer = gpd.GeoDataFrame(
        {"asset": ["A", "A"]},
        geometry=[
            LineString([(0, 0), (5, 0)]),
            LineString([(5, 0), (10, 0)]),
        ],
        crs="EPSG:4326",
    )
    assert continuity_breaks(layer, key_column="asset") == []


def test_continuity_needs_a_key_column():
    layer = gpd.GeoDataFrame(
        {"asset": ["A", "A"]},
        geometry=[LineString([(0, 0), (5, 0)]), LineString([(6, 0), (10, 0)])],
        crs="EPSG:4326",
    )
    assert continuity_breaks(layer) == []


def test_continuity_ignores_different_assets():
    layer = gpd.GeoDataFrame(
        {"asset": ["A", "B"]},
        geometry=[LineString([(0, 0), (5, 0)]), LineString([(6, 0), (10, 0)])],
        crs="EPSG:4326",
    )
    assert continuity_breaks(layer, key_column="asset") == []


def test_continuity_with_unknown_key_column_is_safe():
    layer = gpd.GeoDataFrame(
        {"asset": ["A"]}, geometry=[LineString([(0, 0), (5, 0)])], crs="EPSG:4326"
    )
    assert continuity_breaks(layer, key_column="nope") == []