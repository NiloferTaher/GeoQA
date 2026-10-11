"""Tests for the coverage, key and transform validators.

Each rule here replaced defensive code that had to work around the defect in
practice. The tests assert the defect is caught, not worked around.
"""

from __future__ import annotations

from datetime import datetime

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon, box

from geoqa.problem_registry import get_problem_definition
from geoqa.validations.coverage import (
    coverage_ratio,
    coverage_report,
    validate_coverage_floor,
    validate_split_completeness,
)
from geoqa.validations.keys import (
    bind_to_vocabulary,
    compound_key_duplicates,
    resolve_field,
    resolve_schema,
    truncate_timestamp,
    validate_vocabulary_binding,
)
from geoqa.validations.transform_audit import (
    audit_attribute_preservation,
    buffer_zero_audit,
    geometry_metrics,
)


def _frame(rows, crs="EPSG:27700"):
    return gpd.GeoDataFrame(rows, crs=crs)


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------


class TestCoverageFloor:
    def test_full_retention_passes(self):
        src = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        out = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        assert validate_coverage_floor(src, out, id_field="id") == []

    def test_slight_loss_passes(self):
        src = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        out = _frame([{"id": "a", "geometry": box(0, 0, 10, 9)}])
        assert validate_coverage_floor(src, out, id_field="id", minimum_retained=0.5) == []

    def test_severe_loss_is_reported(self):
        src = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        out = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        names = [i.problem_name for i in validate_coverage_floor(
            src, out, id_field="id", minimum_retained=0.2)]
        assert names == ["clip_coverage_below_floor"]

    def test_absent_feature_is_reported(self):
        src = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)},
                      {"id": "b", "geometry": box(20, 20, 30, 30)}])
        out = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        names = [i.problem_name for i in validate_coverage_floor(src, out, id_field="id")]
        assert "clip_feature_absent" in names

    def test_zero_area_source_is_not_silently_passed(self):
        src = _frame([{"id": "a", "geometry": LineString([(0, 0), (1, 1)])}])
        out = _frame([{"id": "a", "geometry": LineString([(0, 0), (1, 1)])}])
        names = [i.problem_name for i in validate_coverage_floor(src, out, id_field="id")]
        assert names == ["clip_coverage_uncomputable"]

    def test_threshold_out_of_range_is_refused(self):
        src = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        with pytest.raises(ValueError):
            validate_coverage_floor(src, src, id_field="id", minimum_retained=1.5)

    def test_ratio_and_report_are_numeric(self):
        detail = coverage_ratio(box(0, 0, 10, 10), box(0, 0, 5, 10))
        assert detail["ratio"] == pytest.approx(0.5)
        src = _frame([{"id": "a", "geometry": box(0, 0, 10, 10)}])
        out = _frame([{"id": "a", "geometry": box(0, 0, 5, 10)}])
        assert coverage_report(src, out, id_field="id")[0]["ratio"] == pytest.approx(0.5)


class TestSplitCompleteness:
    def test_disjoint_halves_reassemble_exactly(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(1, 0, 2, 1)}])
        assert validate_split_completeness(parts, id_field="id") == []

    def test_single_piece_is_fine(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)}])
        assert validate_split_completeness(parts, id_field="id") == []

    def test_missing_piece_needs_the_original_area(self):
        """Disjoint pieces always sum to their union, so a shortfall can only be
        seen against the area the feature had before it was split."""
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(1, 0, 2, 1)}])
        assert validate_split_completeness(parts, id_field="id") == []

        names = [i.problem_name for i in validate_split_completeness(
            parts, id_field="id", expected_area={"a": 4.0})]
        assert names == ["split_pieces_area_lost"]

    def test_gap_between_pieces_is_not_a_missing_piece(self):
        """A gap does not reduce the sum, so a gap alone is not a defect."""
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(5, 0, 6, 1)}])
        assert validate_split_completeness(parts, id_field="id") == []

    def test_expected_area_that_matches_is_silent(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(1, 0, 2, 1)}])
        assert validate_split_completeness(parts, id_field="id", expected_area={"a": 2.0}) == []

    def test_overlapping_pieces_are_reported(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(0, 0, 1, 1)}])
        names = [i.problem_name for i in validate_split_completeness(parts, id_field="id")]
        assert "split_pieces_overlap" in names

    def test_distinct_ids_are_not_mixed(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "b", "geometry": box(5, 5, 6, 6)}])
        assert validate_split_completeness(parts, id_field="id") == []

    def test_multi_requirement_can_be_waived(self):
        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(1, 0, 2, 1)}])
        assert validate_split_completeness(parts, id_field="id", require_single=False) == []


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------


class TestTimestampGranularity:
    def test_hour_truncation_discards_minutes(self):
        a = truncate_timestamp("2026-03-21T10:15:00", "hour")
        b = truncate_timestamp("2026-03-21T10:45:00", "hour")
        assert a == b == datetime(2026, 3, 21, 10, 0)

    def test_different_hours_stay_different(self):
        a = truncate_timestamp("2026-03-21T10:59:00", "hour")
        b = truncate_timestamp("2026-03-21T11:01:00", "hour")
        assert a != b

    def test_day_truncation(self):
        assert truncate_timestamp("2026-03-21T23:59:00", "day") == datetime(2026, 3, 21, 0, 0)

    def test_unknown_granularity_is_refused(self):
        with pytest.raises(ValueError):
            truncate_timestamp("2026-03-21T10:00:00", "fortnight")

    def test_unparseable_value_passes_through(self):
        assert truncate_timestamp("not a date", "hour") == "not a date"


class TestCompoundKeyDuplicates:
    def _frame_with(self, rows):
        return pd.DataFrame(rows)

    def test_same_asset_same_owner_same_hour_is_duplicate(self):
        frame = self._frame_with([
            {"asset_id": 1, "owner": "a", "ts": "2026-03-21T10:15:00"},
            {"asset_id": 1, "owner": "a", "ts": "2026-03-21T10:45:00"},
        ])
        names = [i.problem_name for i in compound_key_duplicates(
            frame, key_fields=["asset_id", "owner"], timestamp_field="ts")]
        assert set(names) == {"compound_key_duplicate"}
        assert len(names) == 2, "every member of the group must be reported"

    def test_different_owner_is_not_duplicate(self):
        frame = self._frame_with([
            {"asset_id": 1, "owner": "a", "ts": "2026-03-21T10:15:00"},
            {"asset_id": 1, "owner": "b", "ts": "2026-03-21T10:15:00"},
        ])
        assert compound_key_duplicates(
            frame, key_fields=["asset_id", "owner"], timestamp_field="ts") == []

    def test_different_hour_is_not_duplicate(self):
        frame = self._frame_with([
            {"asset_id": 1, "owner": "a", "ts": "2026-03-21T10:15:00"},
            {"asset_id": 1, "owner": "a", "ts": "2026-03-21T11:15:00"},
        ])
        assert compound_key_duplicates(
            frame, key_fields=["asset_id", "owner"], timestamp_field="ts") == []

    def test_missing_field_is_silent_not_a_crash(self):
        frame = self._frame_with([{"asset_id": 1}])
        assert compound_key_duplicates(frame, key_fields=["asset_id", "owner"]) == []


class TestFieldResolution:
    def test_single_alias_resolves(self):
        assert resolve_field(["utilis_id"], ["asset_id", "utilis_id"])["status"] == "resolved"

    def test_two_aliases_present_is_ambiguous(self):
        """First-match wins here is what hid the problem."""
        result = resolve_field(["asset_id", "utilis_id"], ["asset_id", "utilis_id"])
        assert result["status"] == "ambiguous"
        assert result["column"] is None
        assert set(result["candidates"]) == {"asset_id", "utilis_id"}

    def test_no_alias_is_missing(self):
        assert resolve_field(["other"], ["asset_id", "utilis_id"])["status"] == "missing"

    def test_schema_reports_both_failure_modes(self):
        issues = resolve_schema(
            ["asset_id", "utilis_id", "unrelated"],
            {"asset": ["asset_id", "utilis_id"], "length": ["pipe_len", "shape_len"]},
        )
        names = sorted(i.problem_name for i in issues)
        assert names == ["schema_field_ambiguous", "schema_field_missing"]


class TestVocabularyBinding:
    VOCAB = ["Northern Area", "Seabrook", "Bastion North", "Bayside"]

    def test_clear_match_binds(self):
        binding = bind_to_vocabulary(["Bayside"], self.VOCAB)[0]
        assert binding.status == "bound"
        assert binding.match == "Bayside"

    def test_unknown_name_is_unbound(self):
        binding = bind_to_vocabulary(["Nowhere"], self.VOCAB)[0]
        assert binding.status == "unbound"

    def test_two_terms_matching_is_ambiguous(self):
        """The case a convenience implementation hides by taking n=1."""
        bindings = bind_to_vocabulary(["Bayside North"], ["Bayside", "Bayside North"])
        assert bindings[0].status == "ambiguous"
        assert bindings[0].ambiguous_with

    def test_ambiguity_is_reported_as_an_issue(self):
        bindings = bind_to_vocabulary(["Bayside North"], ["Bayside", "Bayside North"])
        names = [i.problem_name for i in validate_vocabulary_binding(bindings)]
        assert names == ["vocabulary_binding_ambiguous"]

    def test_unbound_is_reported(self):
        names = [i.problem_name for i in validate_vocabulary_binding(
            bind_to_vocabulary(["Nowhere"], self.VOCAB))]
        assert names == ["vocabulary_binding_unbound"]


# --------------------------------------------------------------------------
# Transform audit
# --------------------------------------------------------------------------


def _bowtie():
    """A classic self-intersecting polygon."""
    return Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])


class TestBufferZeroAudit:
    def test_metrics_are_measured(self):
        metrics = geometry_metrics(box(0, 0, 2, 2))
        assert metrics["area"] == pytest.approx(4.0)
        assert metrics["valid"] is True

    def test_valid_geometry_is_not_reported(self):
        layer = _frame([{"geometry": box(0, 0, 2, 2)}])
        assert buffer_zero_audit(layer) == []

    def test_invalid_geometry_that_repairs_cleanly_is_reported(self):
        layer = _frame([{"geometry": _bowtie()}])
        issues = buffer_zero_audit(layer)
        assert any(i.problem_name == "repair_changed_geometry" for i in issues)

    def test_area_delta_is_quantified(self):
        layer = _frame([{"geometry": _bowtie()}])
        issues = [i for i in buffer_zero_audit(layer)
                  if i.problem_name == "repair_changed_geometry"]
        assert issues
        extra = issues[0].extra
        assert "area_delta" in extra and "before" in extra and "after" in extra

    def test_repair_can_be_measured_without_being_applied(self):
        layer = _frame([{"geometry": _bowtie()}])
        assert buffer_zero_audit(layer, repair=False) == []


class TestAttributePreservation:
    def test_dropped_feature_is_reported(self):
        src = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)},
                      {"id": "b", "status": "leak", "geometry": box(2, 2, 3, 3)}])
        out = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)}])
        issues = audit_attribute_preservation(src, out, key_field="id")
        assert [i.problem_name for i in issues] == ["transform_dropped_features"]

    def test_complete_merge_is_silent(self):
        src = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)}])
        out = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)}])
        assert audit_attribute_preservation(src, out, key_field="id") == []

    def test_changed_attribute_is_reported(self):
        src = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)}])
        out = _frame([{"id": "a", "status": "quiet", "geometry": box(0, 0, 1, 1)}])
        names = [i.problem_name for i in audit_attribute_preservation(
            src, out, key_field="id", preserved_fields=["status"])]
        assert names == ["transform_attribute_changed"]

    def test_blank_to_value_fill_is_not_reported(self):
        """Filling an empty field during a merge is legitimate."""
        src = _frame([{"id": "a", "status": "", "geometry": box(0, 0, 1, 1)}])
        out = _frame([{"id": "a", "status": "leak", "geometry": box(0, 0, 1, 1)}])
        assert audit_attribute_preservation(
            src, out, key_field="id", preserved_fields=["status"]) == []


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

_NEW = [
    "clip_coverage_below_floor", "clip_feature_absent", "clip_coverage_uncomputable",
    "split_pieces_not_whole", "split_pieces_overlap", "split_pieces_area_lost",
    "compound_key_duplicate",
    "schema_field_missing", "schema_field_ambiguous",
    "vocabulary_binding_ambiguous", "vocabulary_binding_unbound",
    "repair_changed_geometry", "repair_incomplete", "repair_buffer_zero_failed",
    "transform_dropped_features", "transform_attribute_changed",
]


class TestRegistry:
    @pytest.mark.parametrize("name", _NEW)
    def test_registered_with_metadata(self, name):
        entry = get_problem_definition(name)
        assert entry is not None, name
        assert entry.description, name
        assert entry.repair_hint, name
        assert entry.default_severity in {"critical", "high", "medium", "low", "info"}, name
        assert entry.issue_class in {"data_issue", "evidence_condition", "governance_gap"}, name

    def test_binding_outcomes_are_evidence_not_defects(self):
        assert get_problem_definition("vocabulary_binding_ambiguous").issue_class == "evidence_condition"
        assert get_problem_definition("vocabulary_binding_unbound").issue_class == "evidence_condition"

    def test_repair_change_is_a_defect_not_evidence(self):
        """A repair that moved the geometry did change the data."""
        assert get_problem_definition("repair_changed_geometry").issue_class == "data_issue"