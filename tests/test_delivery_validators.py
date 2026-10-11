"""Tests for the validators ported from Nilofer's own delivery scripts.

Each test states the failure it prevents. Where a rule came from a script
that had to work around the defect in practice, the test asserts the
defect is caught rather than worked around.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box

from geoqa.problem_registry import get_problem_definition
from geoqa.validations.containment import (
    describe_tolerance,
    round_trip,
    scale_dependent_tolerance,
    verify_containment,
)
from geoqa.validations.cross_layer import (
    bidirectional_coverage,
    declared_domain,
    normalise_key,
    orphaned_by_geometry,
    referential_integrity,
)
from geoqa.validations.datatypes import (
    postgis_expectations,
    profile_datatypes,
    profile_geometry_parts,
    validate_datatypes,
    validate_geometry_parts,
)
from geoqa.validations.encoding import (
    check_text_encoding,
    detect_encoding,
    looks_like_mojibake,
)
from geoqa.validations.sentinels import (
    DEFAULT_NUMERIC_SENTINELS,
    detect_sentinels,
    sentinel_report,
    validate_sentinels,
)


def _frame(rows, crs="EPSG:27700"):
    return gpd.GeoDataFrame(rows, crs=crs)


# --------------------------------------------------------------------------
# Cross-layer referential integrity
# --------------------------------------------------------------------------


class TestKeyNormalisation:
    def test_numeric_spellings_compare_equal(self):
        assert normalise_key(70677) == normalise_key("70677") == normalise_key(" 70677 ")

    def test_float_spelling_is_recognised(self):
        assert normalise_key(70677.0) == normalise_key("70677")

    def test_blank_and_null_become_none(self):
        assert normalise_key(None) is None
        assert normalise_key("") is None
        assert normalise_key("   ") is None

    def test_non_numeric_text_is_left_alone(self):
        assert normalise_key("WL-123") == "WL-123"


class TestReferentialIntegrity:
    def _layers(self):
        parent = _frame([{"asset_id": 1, "geometry": Point(0, 0)},
                         {"asset_id": 2, "geometry": Point(1, 1)}])
        child = _frame([{"asset_id": 1, "geometry": Point(0, 0)},
                        {"asset_id": 99, "geometry": Point(2, 2)}])
        return child, parent

    def test_orphan_is_found(self):
        child, parent = self._layers()
        names = [i.problem_name for i in referential_integrity(
            child, parent, child_field="asset_id", parent_field="asset_id")]
        assert names == ["cross_layer_orphan"]

    def test_matched_child_is_silent(self):
        parent = _frame([{"asset_id": 1, "geometry": Point(0, 0)}])
        child = _frame([{"asset_id": 1, "geometry": Point(0, 0)}])
        assert referential_integrity(
            child, parent, child_field="asset_id", parent_field="asset_id") == []

    def test_missing_key_is_reported_not_skipped(self):
        """A row with no key cannot be shown to be correct, so it is reported."""
        parent = _frame([{"asset_id": 1, "geometry": Point(0, 0)}])
        child = _frame([{"asset_id": None, "geometry": Point(0, 0)}])
        names = [i.problem_name for i in referential_integrity(
            child, parent, child_field="asset_id", parent_field="asset_id")]
        assert "cross_layer_key_missing" in names

    def test_text_and_numeric_keys_join(self):
        """The cast on the join key in the original query was the defect this prevents."""
        parent = _frame([{"asset_id": "70677", "geometry": Point(0, 0)}])
        child = _frame([{"asset_id": 70677, "geometry": Point(0, 0)}])
        assert referential_integrity(
            child, parent, child_field="asset_id", parent_field="asset_id") == []


class TestBidirectionalCoverage:
    def test_both_directions_are_reported(self):
        left = _frame([{"k": "a", "geometry": Point(0, 0)},
                       {"k": "b", "geometry": Point(1, 1)}])
        right = _frame([{"k": "a", "geometry": Point(0, 0)},
                        {"k": "c", "geometry": Point(2, 2)}])
        names = [i.problem_name for i in bidirectional_coverage(
            left, right, left_field="k", right_field="k")]
        assert names == ["cross_layer_unmatched_child", "cross_layer_unmatched_parent"]

    def test_asymmetric_check_reports_one_side_only(self):
        left = _frame([{"k": "a", "geometry": Point(0, 0)},
                       {"k": "b", "geometry": Point(1, 1)}])
        right = _frame([{"k": "a", "geometry": Point(0, 0)},
                        {"k": "c", "geometry": Point(2, 2)}])
        names = [i.problem_name for i in bidirectional_coverage(
            left, right, left_field="k", right_field="k", require_symmetry=False)]
        assert names == ["cross_layer_unmatched_child"]

    def test_perfect_agreement_is_silent(self):
        frame = _frame([{"k": "a", "geometry": Point(0, 0)}])
        assert bidirectional_coverage(frame, frame, left_field="k", right_field="k") == []


class TestGeometricOrphans:
    def test_asset_with_no_nearby_main_is_reported(self):
        assets = _frame([{"id": "a1", "geometry": box(0, 0, 10, 10)},
                         {"id": "a2", "geometry": box(500, 500, 510, 510)}])
        mains = _frame([{"id": "m1", "geometry": LineString([(0, 0), (10, 10)])}])
        names = [i.problem_name for i in orphaned_by_geometry(assets, mains, id_field="id")]
        assert names == ["cross_layer_geometric_orphan"]

    def test_all_assets_matched_is_silent(self):
        assets = _frame([{"id": "a1", "geometry": box(0, 0, 10, 10)}])
        mains = _frame([{"id": "m1", "geometry": LineString([(0, 0), (10, 10)])}])
        assert orphaned_by_geometry(assets, mains, id_field="id") == []


class TestDeclaredDomain:
    def test_domain_is_counted_and_sorted(self):
        frame = _frame([{"diameter": 100, "geometry": Point(0, 0)},
                        {"diameter": 100, "geometry": Point(1, 1)},
                        {"diameter": 150, "geometry": Point(2, 2)}])
        domain = declared_domain(frame, "diameter")
        assert domain["distinct"] == 2
        assert list(domain["values"]) == ["100", "150"]

    def test_expected_flags_unexpected_values(self):
        frame = _frame([{"diameter": 100, "geometry": Point(0, 0)},
                        {"diameter": 999, "geometry": Point(1, 1)}])
        assert declared_domain(frame, "diameter", expected=[100, 150])["unexpected"] == ["999"]

    def test_absent_column_is_reported_not_raised(self):
        frame = _frame([{"a": 1, "geometry": Point(0, 0)}])
        assert declared_domain(frame, "nope")["present"] is False


# --------------------------------------------------------------------------
# Geometry parts: the single-versus-multi question
# --------------------------------------------------------------------------


class TestGeometryParts:
    @staticmethod
    def _multipolygon_with_empty_part():
        """Build the state by decoding stored bytes, which is the only way it occurs.

        Constructing ``MultiPolygon([box(...), Polygon()])`` succeeds and silently
        drops the empty part, so a test built that way would prove nothing. Every
        delivered format arrives through a decoder, and the decoder keeps it.
        """
        import struct

        from shapely import wkb

        def polygon_wkb(rings):
            out = struct.pack("<BII", 1, 3, len(rings))
            for ring in rings:
                out += struct.pack("<I", len(ring))
                for x, y in ring:
                    out += struct.pack("<dd", x, y)
            return out

        square = polygon_wkb([[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]])
        empty = polygon_wkb([])
        return wkb.loads(struct.pack("<BII", 1, 6, 2) + square + empty)

    def test_empty_part_is_reported(self):
        geometry = self._multipolygon_with_empty_part()
        parts = list(geometry.geoms)
        assert len(parts) == 2 and sum(1 for p in parts if p.is_empty) == 1, (
            "fixture must actually contain an empty part for this test to mean anything"
        )

        layer = gpd.GeoDataFrame({"geometry": [geometry]}, crs="EPSG:4326")
        names = [i.problem_name for i in validate_geometry_parts(layer)]
        assert "geometry_empty_part" in names

    def test_clean_multipolygon_has_no_empty_part(self):
        layer = _frame([{"geometry": MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])}])
        assert "geometry_empty_part" not in [i.problem_name for i in validate_geometry_parts(layer)]

    def test_empty_part_can_be_suppressed_by_the_caller(self):
        geometry = self._multipolygon_with_empty_part()
        layer = gpd.GeoDataFrame({"geometry": [geometry]}, crs="EPSG:4326")
        assert validate_geometry_parts(layer, reject_empty_parts=False) == []

    def test_single_and_multi_are_counted_separately(self):
        layer = _frame([
            {"geometry": LineString([(0, 0), (1, 1)])},
            {"geometry": MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])},
        ])
        profile = profile_geometry_parts(layer)
        assert profile.single_part == 1
        assert profile.multi_part == 1
        assert profile.dominant_type == "MultiPolygon"

    def test_multipolygon_parts_are_counted(self):
        profile = profile_geometry_parts(
            _frame([{"geometry": MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])}]))
        assert profile.multi_part == 1
        assert profile.type_counts["MultiPolygon"] == 1

    def test_mixed_families_are_flagged(self):
        """The mode() call that silently discarded minority types."""
        layer = _frame([
            {"geometry": Point(0, 0)},
            {"geometry": Point(1, 1)},
            {"geometry": Point(2, 2)},
            {"geometry": box(0, 0, 1, 1)},
        ])
        names = [i.problem_name for i in validate_geometry_parts(layer)]
        assert "geometry_family_mixed" in names

    def test_uniform_family_is_silent(self):
        layer = _frame([{"geometry": LineString([(0, 0), (1, 1)])},
                         {"geometry": LineString([(1, 1), (2, 0)])}])
        assert validate_geometry_parts(layer) == []

    def test_declared_polygon_rejects_multipolygon(self):
        layer = _frame([{"geometry": MultiPolygon([box(0, 0, 1, 1)])}])
        names = [i.problem_name for i in validate_geometry_parts(
            layer, declared_type="Polygon")]
        assert "geometry_declared_type_mismatch" in names

    def test_declared_multipolygon_accepts_single_polygon(self):
        layer = _frame([{"geometry": box(0, 0, 1, 1)}])
        assert validate_geometry_parts(layer, declared_type="MultiPolygon") == []

    def test_generic_geometry_accepts_anything(self):
        layer = _frame([{"geometry": MultiPolygon([box(0, 0, 1, 1)])}])
        assert validate_geometry_parts(layer, declared_type="GEOMETRY(Geometry,4326)") == []


class TestDatatypes:
    def test_float_identifier_is_flagged(self):
        layer = _frame([{"asset_id": 70677.0, "geometry": Point(0, 0)}])
        names = [i.problem_name for i in validate_datatypes(layer, id_fields=["asset_id"])]
        assert names == ["datatype_identifier_as_float"]

    def test_text_identifier_is_flagged(self):
        layer = _frame([{"asset_id": "70677", "geometry": Point(0, 0)}])
        names = [i.problem_name for i in validate_datatypes(layer, id_fields=["asset_id"])]
        assert names == ["datatype_identifier_as_text"]

    def test_integer_identifier_is_accepted(self):
        layer = _frame([{"asset_id": 70677, "geometry": Point(0, 0)}])
        assert validate_datatypes(layer, id_fields=["asset_id"]) == []

    def test_coordinate_as_text_is_flagged(self):
        """Coordinates should be real, not text. This is the rule."""
        layer = _frame([{"x": "12.5", "y": "3.25", "geometry": Point(12.5, 3.25)}])
        names = [i.problem_name for i in validate_datatypes(layer)]
        assert names.count("datatype_numeric_as_text") == 2

    def test_numeric_coordinates_are_accepted(self):
        layer = _frame([{"x": 12.5, "y": 3.25, "geometry": Point(12.5, 3.25)}])
        assert validate_datatypes(layer) == []

    def test_unparseable_text_count_is_reported(self):
        layer = _frame([{"x": "12,5", "geometry": Point(0, 0)},
                        {"x": "abc", "geometry": Point(1, 1)}])
        issues = [i for i in validate_datatypes(layer) if i.problem_name == "datatype_numeric_as_text"]
        assert issues and issues[0].extra["unparseable"] == 2

    def test_geometry_column_is_never_treated_as_numeric(self):
        layer = _frame([{"length": 5.0, "geometry": LineString([(0, 0), (1, 1)])}])
        issues = validate_datatypes(layer)
        assert all(i.extra.get("column") != "geometry" for i in issues)

    def test_profile_lists_every_column(self):
        layer = _frame([{"a": 1, "geometry": Point(0, 0)}])
        assert set(profile_datatypes(layer)) == {"a", "geometry"}


class TestPostgisExpectations:
    def test_missing_crs_is_reported(self):
        layer = gpd.GeoDataFrame([{"geometry": Point(0, 0)}])
        names = [i.problem_name for i in postgis_expectations(layer)]
        assert "postgis_crs_undeclared" in names

    def test_srid_mismatch_is_reported(self):
        layer = _frame([{"geometry": Point(0, 0)}], crs="EPSG:3857")
        names = [i.problem_name for i in postgis_expectations(layer, target_srid=4326)]
        assert "postgis_srid_mismatch" in names

    def test_matching_crs_is_silent_on_crs(self):
        layer = _frame([{"geometry": Point(0, 0)}], crs="EPSG:4326")
        names = [i.problem_name for i in postgis_expectations(layer, target_srid=4326)]
        assert "postgis_srid_mismatch" not in names
        assert "postgis_crs_undeclared" not in names

    def test_expected_geometry_type_is_passed_through(self):
        layer = _frame([{"geometry": Point(0, 0)}], crs="EPSG:4326")
        names = [i.problem_name for i in postgis_expectations(
            layer, expected_geometry_type="Polygon")]
        assert "geometry_declared_type_mismatch" in names


# --------------------------------------------------------------------------
# Sentinels
# --------------------------------------------------------------------------


class TestSentinelDetection:
    @pytest.mark.parametrize("value", ["N/A", "n/a", "NULL", "null", "unknown", "-", "TBD", "None"])
    def test_text_sentinels_are_detected(self, value):
        assert detect_sentinels(value) == "text"

    def test_empty_string_is_distinguished_from_other_text(self):
        assert detect_sentinels("  ") == "empty_string"

    def test_numeric_sentinels_are_detected(self):
        assert detect_sentinels(-999) == "numeric"
        assert detect_sentinels(-999.0) == "numeric"

    def test_zero_date_is_detected(self):
        assert detect_sentinels("0000/00/00") == "zero_date"
        assert detect_sentinels("0000-00-00") == "zero_date"

    def test_excel_errors_are_detected(self):
        assert detect_sentinels("#N/A") == "text"
        assert detect_sentinels("#DIV/0!") == "excel_error"

    def test_real_values_pass(self):
        assert detect_sentinels(1234) is None
        assert detect_sentinels("Leak") is None
        assert detect_sentinels("2026-03-21") is None
        assert detect_sentinels(0) is None

    def test_boolean_is_not_a_sentinel(self):
        assert detect_sentinels(True) is None


class TestSentinelValidation:
    def test_sentinel_column_is_reported(self):
        layer = _frame([{"reading": -999, "geometry": Point(0, 0)},
                        {"reading": 12.0, "geometry": Point(1, 1)}])
        names = [i.problem_name for i in validate_sentinels(layer)]
        assert names == ["sentinel_placeholder_value"]

    def test_clean_column_is_silent(self):
        layer = _frame([{"reading": 12.0, "geometry": Point(0, 0)},
                        {"reading": 13.0, "geometry": Point(1, 1)}])
        assert validate_sentinels(layer) == []

    def test_report_counts_by_kind(self):
        layer = _frame([{"a": "N/A", "geometry": Point(0, 0)},
                        {"a": "0000/00/00", "geometry": Point(1, 1)},
                        {"a": "ok", "geometry": Point(2, 2)}])
        report = sentinel_report(layer, fields=["a"])
        assert report["a"]["sentinel_count"] == 2
        assert report["a"]["by_kind"] == {"text": 1, "zero_date": 1}

    def test_fraction_is_reported(self):
        layer = _frame([{"a": "N/A", "geometry": Point(0, 0)},
                        {"a": "ok", "geometry": Point(1, 1)}])
        assert sentinel_report(layer, fields=["a"])["a"]["fraction"] == 0.5


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


class TestEncoding:
    def test_mojibake_is_recognised(self):
        assert looks_like_mojibake("R\xc3\xa9seau") or looks_like_mojibake("Ã©")
        assert looks_like_mojibake("â€™")

    def test_clean_text_is_not_mojibake(self):
        assert not looks_like_mojibake("Reseau")

    def test_undeclared_encoding_is_reported(self, tmp_path):
        from geoqa.validations.encoding import validate_shapefile_encoding
        path = tmp_path / "layer.shp"
        path.write_bytes(b"not really a shapefile")
        names = [i.problem_name for i in validate_shapefile_encoding(path)]
        assert "encoding_not_declared" in names

    def test_cpg_is_read_when_present(self, tmp_path):
        from geoqa.validations.encoding import read_cpg
        shp = tmp_path / "layer.shp"
        shp.write_bytes(b"x")
        (tmp_path / "layer.shp.cpg").write_text("UTF-8", encoding="utf-8")
        assert read_cpg(shp) == "UTF-8"
        assert detect_encoding(shp).declared_source == "cpg"

    def test_broken_values_are_reported(self):
        report = check_text_encoding(["ok", "Ã©"], column="name")
        assert report.has_problem
        assert report.suspicious == ["Ã©"]

    def test_clean_column_is_silent(self):
        assert not check_text_encoding(["ok", "fine"], column="name").has_problem


# --------------------------------------------------------------------------
# Containment, round trip, scale-dependent tolerance
# --------------------------------------------------------------------------


class TestContainment:
    def test_enclosing_buffer_passes(self):
        inner = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        outer = _frame([{"id": "a", "geometry": box(-1, -1, 2, 2)}])
        assert verify_containment(outer, inner, join_field="id") == []

    def test_buffer_that_misses_is_reported(self):
        inner = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        outer = _frame([{"id": "a", "geometry": box(5, 5, 6, 6)}])
        names = [i.problem_name for i in verify_containment(outer, inner, join_field="id")]
        assert "containment_not_enclosing" in names

    def test_absent_buffer_is_not_a_pass(self):
        inner = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        outer = _frame([{"id": "z", "geometry": box(0, 0, 1, 1)}])
        names = [i.problem_name for i in verify_containment(outer, inner, join_field="id")]
        assert names == ["containment_no_match"]


class TestRoundTrip:
    def test_successful_round_trip_is_silent(self, tmp_path):
        layer = _frame([{"a": 1, "geometry": Point(0, 0)},
                        {"a": 2, "geometry": Point(1, 1)}])
        assert round_trip(layer, tmp_path / "out.gpkg") == []

    def test_failure_to_write_is_reported(self, tmp_path):
        class Bad:
            def to_file(self, path, driver=None):
                raise RuntimeError("cannot write")

        layer = _frame([{"geometry": Point(0, 0)}])
        bad = Bad()
        bad.__class__ = type("Layer", (_frame([{"geometry": Point(0, 0)}]).__class__,),
                              {"to_file": lambda self, p, driver=None: (_ for _ in ()).throw(RuntimeError("no"))})
        names = [i.problem_name for i in round_trip(bad, tmp_path / "x.gpkg")]
        assert names == ["roundtrip_write_failed"]

    def test_output_is_cleaned_up(self, tmp_path):
        layer = _frame([{"geometry": Point(0, 0)}])
        destination = tmp_path / "out.gpkg"
        round_trip(layer, destination)
        assert not destination.exists()


class TestScaleDependentTolerance:
    def test_tolerance_scales_with_extent(self):
        small = scale_dependent_tolerance(1000.0, 0.01)
        large = scale_dependent_tolerance(100000.0, 0.01)
        assert small == 10.0
        assert large == 1000.0
        assert large == small * 100

    def test_minimum_is_respected(self):
        assert scale_dependent_tolerance(10.0, 0.001, minimum=5.0) == 5.0

    def test_maximum_is_respected(self):
        assert scale_dependent_tolerance(1e9, 0.5, maximum=100.0) == 100.0

    def test_negative_fraction_is_refused(self):
        with pytest.raises(ValueError):
            scale_dependent_tolerance(100.0, -0.1)

    def test_description_states_the_resolved_distance(self):
        layer = _frame([{"geometry": Point(0, 0)}, {"geometry": Point(100, 100)}])
        described = describe_tolerance(layer, 0.01)
        assert described["tolerance"] == 1.0
        assert described["basis"] == "extent"


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

_NEW_CONDITIONS = [
    "cross_layer_orphan", "cross_layer_unmatched_child", "cross_layer_unmatched_parent",
    "cross_layer_key_missing", "cross_layer_geometric_orphan",
    "geometry_family_mixed", "geometry_part_type_mixed",
    "geometry_declared_type_mismatch",
    "datatype_identifier_as_float", "datatype_identifier_as_text",
    "datatype_numeric_as_text",
    "sentinel_placeholder_value",
    "encoding_not_declared", "encoding_suspect_values",
    "containment_not_enclosing", "containment_no_match",
    "roundtrip_write_failed", "roundtrip_file_missing", "roundtrip_read_failed",
    "roundtrip_row_count_changed", "roundtrip_geometry_lost",
    "roundtrip_geometry_degraded",
    "postgis_crs_undeclared", "postgis_crs_not_epsg", "postgis_srid_mismatch",
]


class TestRegistry:
    @pytest.mark.parametrize("name", _NEW_CONDITIONS)
    def test_condition_is_registered_with_full_metadata(self, name):
        entry = get_problem_definition(name)
        assert entry is not None, name
        assert entry.description, name
        assert entry.repair_hint, name
        assert entry.default_severity in {"critical", "high", "medium", "low", "info"}, name
        assert entry.issue_class in {
            "data_issue", "evidence_condition", "governance_gap"}, name

    def test_undeclared_crs_is_a_governance_gap_not_a_defect(self):
        """Nobody recorded a decision that had to be made."""
        assert get_problem_definition("postgis_crs_undeclared").issue_class == "governance_gap"

    def test_missing_encoding_is_a_governance_gap(self):
        assert get_problem_definition("encoding_not_declared").issue_class == "governance_gap"

    def test_ambiguous_identifier_typing_is_evidence(self):
        assert get_problem_definition("datatype_identifier_as_text").issue_class == "evidence_condition"