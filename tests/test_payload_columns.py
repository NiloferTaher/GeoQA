"""Tests for structured payloads stored in scalar text columns.

The regression worth protecting is the silent one: a tolerant parser stops
matching, returns an empty list instead of raising, and the only symptom is a
report with photographs missing. That is why the parse-failure condition is
severity high while the mis-typing condition is medium.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoqa.validations.payload_columns import (
    payload_columns,
    profile_payload_column,
    validate_payload_columns,
)


def _layer(**columns) -> gpd.GeoDataFrame:
    length = max((len(v) for v in columns.values()), default=0)
    return gpd.GeoDataFrame(
        columns,
        geometry=[Point(i, i) for i in range(length)],
        crs="EPSG:4326",
    )


VENDOR_PHOTO = (
    '___json[{"pathname":"/Collected Media/2025-08/mdc_photo_812.jpg",'
    '"title":"IMG-0041.jpg"}]'
)
VENDOR_TWO = (
    '___json[{"pathname":"/Collected Media/2025-08/a.jpg","title":"a.jpg"},'
    '{"pathname":"/Collected Media/2025-08/b.jpg","title":"b.jpg"}]'
)


def test_vendor_photo_payload_is_detected():
    layer = _layer(photo=[VENDOR_PHOTO, VENDOR_TWO, VENDOR_PHOTO, VENDOR_TWO])
    names = {i.problem_name for i in validate_payload_columns(layer)}
    assert "json_in_text_column" in names


def test_plain_text_column_is_not_flagged():
    layer = _layer(comments=["no leaks found", "wet soil", "under construction", ""])
    assert validate_payload_columns(layer) == []


def test_mis_typed_column_is_medium_severity():
    layer = _layer(photo=[VENDOR_PHOTO] * 4)
    issue = next(i for i in validate_payload_columns(layer) if i.problem_name == "json_in_text_column")
    assert str(issue.severity) == "medium"


def test_unparseable_payload_is_high_severity():
    """The dangerous case: a row that looks structured but will not parse."""
    layer = _layer(photo=[VENDOR_PHOTO, VENDOR_TWO, "___json[{broken", VENDOR_PHOTO])
    names = {i.problem_name for i in validate_payload_columns(layer)}
    assert "json_in_text_unparseable" in names
    issue = next(i for i in validate_payload_columns(layer) if i.problem_name == "json_in_text_unparseable")
    assert str(issue.severity) == "high"


def test_fully_parseable_payload_reports_no_parse_failure():
    layer = _layer(photo=[VENDOR_PHOTO, VENDOR_TWO, VENDOR_PHOTO])
    names = {i.problem_name for i in validate_payload_columns(layer)}
    assert "json_in_text_unparseable" not in names


def test_one_incidental_value_does_not_make_it_a_defect():
    """A stray brace in a comment is not a schema defect."""
    layer = _layer(comments=["normal", "normal", "normal", "{odd"])
    assert validate_payload_columns(layer) == []


def test_require_structured_false_reports_any_single_occurrence():
    layer = _layer(comments=["normal", "{odd"])
    names = {i.problem_name for i in validate_payload_columns(layer, require_structured=False)}
    assert "json_in_text_column" in names


def test_bare_json_without_vendor_marker_is_detected():
    layer = _layer(notes=['[{"a":1}]', '[{"b":2}]', '[{"c":3}]'])
    names = {i.problem_name for i in validate_payload_columns(layer)}
    assert "json_in_text_column" in names


def test_object_payload_is_detected():
    layer = _layer(meta=['{"k":1}', '{"k":2}', '{"k":3}'])
    names = {i.problem_name for i in validate_payload_columns(layer)}
    assert "json_in_text_column" in names


def test_column_restriction_is_honoured():
    layer = _layer(photo=[VENDOR_PHOTO] * 4, note=["x"] * 4)
    profiles = payload_columns(layer, columns=["note"])
    assert [p.column for p in profiles] == ["note"]
    assert profiles[0].structured == 0


def test_unknown_column_is_skipped_not_raised():
    layer = _layer(photo=[VENDOR_PHOTO] * 3)
    assert validate_payload_columns(layer, columns=["does_not_exist"]) == []


def test_empty_layer_is_safe():
    empty = gpd.GeoDataFrame({"photo": []}, geometry=[], crs="EPSG:4326")
    assert validate_payload_columns(empty) == []


def test_profile_counts_are_reported():
    layer = _layer(photo=[VENDOR_PHOTO, None, VENDOR_TWO, "___json[{bad"])
    p = payload_columns(layer)[0]
    assert p.rows == 4
    assert p.nonempty == 3
    assert p.structured == 3
    assert p.parse_failures == 1
    assert p.structured_fraction == pytest.approx(1.0)
    assert "___json" in p.vendor_markers


def test_extra_payload_records_declared_and_actual_type():
    layer = _layer(photo=[VENDOR_PHOTO] * 3)
    issue = next(i for i in validate_payload_columns(layer) if i.problem_name == "json_in_text_column")
    payload = issue.to_dict()
    assert payload["declared_type"] == "text"
    assert payload["actual_shape"] == "json"


def test_nulls_are_not_counted_as_structured():
    p = profile_payload_column("photo", [None, None, ""])
    assert p.structured == 0
    assert p.nonempty == 0