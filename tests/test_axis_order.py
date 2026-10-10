"""Tests for coordinate axis order.

The behaviour worth protecting: an ambiguous pair is reported as ambiguous
rather than guessed, and an unambiguous swap is critical rather than medium.
Getting either wrong is worse than reporting nothing, because the first
invents a defect and the second hides one.
"""

from __future__ import annotations

import pytest

from geoqa.validations.axis_order import (
    CANONICAL_ORDERS,
    canonical_order,
    infer_axis_order,
    interpret_postgres_result,
    validate_axis_order,
    validate_axis_order_postgis_sql,
    validate_axis_order_sql,
)


OMAN = (52.0, 16.0, 60.0, 26.5)


def _names(issues):
    return [i.problem_name for i in issues]


def _frame(**columns):
    return {name: values for name, values in columns.items()}


# --- what the standards actually say -------------------------------------

def test_epsg_4326_is_formally_latitude_first():
    """EPSG:4326 is north/east. This is the source of most of the confusion."""
    assert canonical_order("EPSG:4326") == ("latitude", "longitude")


def test_crs84_and_geojson_are_longitude_first():
    assert canonical_order("OGC:CRS84") == ("longitude", "latitude")
    assert canonical_order("urn:ogc:def:crs:OGC:1.3:CRS84") == ("longitude", "latitude")
    assert canonical_order("geojson") == ("longitude", "latitude")


def test_wfs_versions_disagree_with_each_other():
    """WFS 1.0 is lon/lat; 1.1 and 2.0 follow EPSG and are lat/lon."""
    assert canonical_order("wfs-1.0") == ("longitude", "latitude")
    assert canonical_order("wfs-2.0") == ("latitude", "longitude")


def test_postgis_is_longitude_first():
    assert canonical_order("postgis") == ("longitude", "latitude")


def test_unknown_declaration_returns_none():
    assert canonical_order("something-else") is None
    assert canonical_order(None) is None


# --- the user's case ------------------------------------------------------

def test_muscat_longitude_first_is_correct():
    """Muscat is about 23.6 N, 58.2 E."""
    finding = infer_axis_order(58.196, 23.588, declared_order=("longitude", "latitude"))
    assert finding.inference == "ambiguous"  # both in range, needs extent


def test_muscat_against_declared_extent_confirms_lon_first():
    """58.2, 23.6 only fits longitude-first for an Omani extent."""
    extent = OMAN
    finding = infer_axis_order(58.196, 23.588, expected_extent=extent)
    assert finding.inference == "longitude_first"


def test_the_swapped_reading_is_rejected_by_the_same_extent():
    """23.6, 58.2 is the same two numbers read the wrong way round."""
    extent = (52.0, 16.0, 60.0, 26.5)
    finding = infer_axis_order(23.588, 58.196, expected_extent=extent)
    assert finding.inference == "latitude_first"


def test_undeclared_order_is_high_not_a_guess():
    issues = validate_axis_order(_frame(col_a=[58.2, 59.0], col_b=[23.6, 23.9]))
    issue = next(i for i in issues if i.problem_name == "coordinate_axis_order_undeclared")
    assert str(issue.severity) == "high"


def test_columns_named_lat_lon_establish_the_order():
    issues = validate_axis_order(
        _frame(latitude=[23.6, 24.0], longitude=[58.2, 58.9]), expected_extent=OMAN
    )
    assert _names(issues) == []


# --- unambiguous swaps ---------------------------------------------------

def test_latitude_in_the_longitude_slot_is_critical():
    """A value above 90 cannot be a latitude anywhere on Earth."""
    issues = validate_axis_order(
        _frame(longitude=[58.2], latitude=[121.5]),
        declared_crs="EPSG:4326",
        declared_order=("longitude", "latitude"),
    )
    issue = next(i for i in issues if i.problem_name == "coordinate_axis_order_swapped")
    assert str(issue.severity) == "critical"
    assert issue.to_dict()["rows_affected"] == 1


def test_swap_detected_against_a_declared_epsg_4326():
    """Lat/lon columns holding lon/lat values is the classic import mistake.

    Only decidable with an extent: 58.2 and 23.6 are both legal in either slot.
    """
    issues = validate_axis_order(
        _frame(latitude=[58.2], longitude=[23.6]),
        declared_crs="EPSG:4326",
        expected_extent=OMAN,
    )
    assert "coordinate_axis_order_swapped" in _names(issues)


def test_ambiguous_is_reported_when_nothing_can_decide():
    issues = validate_axis_order(
        _frame(longitude=[58.2, 59.0], latitude=[23.6, 23.9]),
        declared_crs="OGC:CRS84",
    )
    issue = next(i for i in issues if i.problem_name == "coordinate_axis_order_ambiguous")
    assert str(issue.severity) == "medium"
    assert "expected_extent" in issue.description


def test_ambiguity_does_not_fire_when_a_swap_exists():
    issues = validate_axis_order(
        _frame(longitude=[58.2, 58.9], latitude=[23.6, 121.5]),
        declared_crs="OGC:CRS84",
    )
    assert "coordinate_axis_order_ambiguous" not in _names(issues)


def test_pair_outside_the_extent_under_both_orders():
    issues = validate_axis_order(
        _frame(longitude=[200.0], latitude=[95.0]),
        declared_crs="OGC:CRS84",
        expected_extent=OMAN,
    )
    assert "coordinate_axis_order_out_of_extent" in _names(issues)


# --- declaration conflicts -----------------------------------------------

def test_column_names_conflicting_with_declaration_is_flagged():
    issues = validate_axis_order(
        _frame(latitude=[23.6], longitude=[58.2]),
        declared_crs="OGC:CRS84",
    )
    issue = next(i for i in issues if i.problem_name == "coordinate_axis_order_declared_mismatch")
    assert str(issue.severity) == "high"
    assert issue.to_dict()["column_order"] == ["latitude", "longitude"]


# --- messy input ---------------------------------------------------------

def test_non_numeric_coordinates_are_reported():
    issues = validate_axis_order(
        _frame(longitude=[58.2, "n/a"], latitude=[23.6, 24.0]),
        declared_crs="OGC:CRS84",
    )
    issue = next(i for i in issues if i.problem_name == "coordinate_axis_order_non_numeric")
    assert issue.to_dict()["rows"] == 1


def test_blank_and_boolean_values_are_not_coordinates():
    from geoqa.validations.axis_order import _as_float

    assert _as_float("") is None
    assert _as_float(None) is None
    assert _as_float(True) is None
    assert _as_float(" 58.2 ") == pytest.approx(58.2)


def test_missing_second_column_is_reported_rather_than_crashing():
    issues = validate_axis_order(_frame(longitude=[58.2]))
    assert "coordinate_axis_order_undeclared" in _names(issues)


def test_empty_frame_is_safe():
    assert validate_axis_order({}) == []


def test_explicit_columns_override_inference():
    issues = validate_axis_order(
        _frame(a=[24.0], b=[121.5]),
        declared_crs="OGC:CRS84",
        first_column="a",
        second_column="b",
    )
    assert "coordinate_axis_order_swapped" in _names(issues)


def test_row_limit_bounds_the_check():
    rows = _frame(longitude=[58.2] * 100, latitude=[23.6] * 100)
    assert validate_axis_order(rows, declared_crs="OGC:CRS84", max_rows=10)
    assert _names(validate_axis_order(rows, declared_crs="OGC:CRS84", max_rows=10)) == [
        "coordinate_axis_order_ambiguous"
    ]


# --- PostgreSQL ----------------------------------------------------------

def test_postgres_sql_names_the_columns():
    sql = validate_axis_order_sql(table="public.meters", x_column="easting", y_column="northing")
    assert "public.meters" in sql
    assert "easting" in sql and "northing" in sql
    assert "axis_a_out_of_latitude_range" in sql


def test_postgres_sql_requires_identifiers():
    with pytest.raises(ValueError, match="required"):
        validate_axis_order_sql(table="", x_column="x", y_column="y")


def test_postgis_sql_checks_ordinates():
    sql = validate_axis_order_postgis_sql(table="meters", geometry_column="geom")
    assert "ST_X" in sql and "ST_Y" in sql
    assert "meters" in sql


def test_interpreting_counts_produces_issues():
    issues = interpret_postgres_result(
        [("axis_a_out_of_latitude_range", 12), ("undecidable_within_legal_ranges", 400)]
    )
    swap = next(i for i in issues if i.problem_name == "coordinate_axis_order_swapped")
    assert swap.to_dict()["violating_rows"] == 12


def test_clean_postgres_result_produces_nothing_serious():
    issues = interpret_postgres_result([("undecidable_within_legal_ranges", 400)])
    assert [i for i in issues if str(i.severity) in {"critical", "high"}] == []


def test_all_canonical_orders_are_two_axes():
    for name, order in CANONICAL_ORDERS.items():
        assert set(order) == {"latitude", "longitude"}, name