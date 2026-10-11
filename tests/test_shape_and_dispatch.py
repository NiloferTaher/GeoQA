"""Tests for sliver detection and layer dispatch."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon, box

from geoqa.dispatch import (
    CONDITION_FAMILIES,
    build_plan,
    inspect_layer,
    validate_plan,
)
from geoqa.problem_registry import get_problem_definition, list_problem_definitions
from geoqa.validations.shape import (
    below_minimum_feature_area,
    elongation_report,
    profile_shape,
    thin_geometry,
    validate_shape,
)


def _frame(rows, crs="EPSG:27700"):
    return gpd.GeoDataFrame(rows, crs=crs)


def _sliver(length=200.0, width=0.5):
    """A long thin strip: the case an area threshold cannot see."""
    return box(0, 0, length, width)


def _compact(size=10.0):
    return box(0, 0, size, size)


class TestShapeProfile:
    def test_measures_a_circle_as_unit_elongation(self):
        from shapely.geometry import Point as P

        circle = P(0, 0).buffer(10, quad_segs=256)
        profile = profile_shape(_frame([{"geometry": circle}]))
        elongation = profile["features"][0]["elongation"]
        assert elongation == pytest.approx(1.0, abs=0.02)

    def test_measures_a_slab_as_high_elongation(self):
        profile = profile_shape(_frame([{"geometry": _sliver(200, 1)}]))
        assert profile["features"][0]["elongation"] > 30, "a 200x1 strip must score far above a circle"

    def test_area_percentiles_are_reported(self):
        layer = _frame([{"geometry": box(0, 0, s, s)} for s in (1, 2, 3, 4)])
        stats = profile_shape(layer)["area_stats"]
        assert stats["min"] == pytest.approx(1.0)
        assert stats["max"] == pytest.approx(16.0)

    def test_elongation_is_dimensionless(self):
        """Same shape, different units, same score."""
        metres = profile_shape(_frame([{"geometry": box(0, 0, 100, 1)}]))
        feet = profile_shape(_frame([{"geometry": box(0, 0, 300, 3)}], crs="EPSG:2263"))
        assert metres["features"][0]["elongation"] == pytest.approx(
            feet["features"][0]["elongation"]
        )


class TestMinimumArea:
    def test_small_feature_is_reported(self):
        layer = _frame([{"geometry": box(0, 0, 1, 1)}])
        names = [i.problem_name for i in below_minimum_feature_area(layer, minimum_area=10.0)]
        assert names == ["below_minimum_feature_area"]

    def test_large_feature_is_silent(self):
        layer = _frame([{"geometry": _compact(50)}])
        assert below_minimum_feature_area(layer, minimum_area=10.0) == []

    def test_zero_area_is_reported(self):
        layer = _frame([{"geometry": Polygon()}])
        assert [i.problem_name for i in below_minimum_feature_area(layer, minimum_area=10.0)] == [
            "feature_zero_area"
        ]

    def test_area_threshold_does_not_see_a_sliver(self):
        """The reason the width check exists: a big thin strip passes any area floor."""
        layer = _frame([{"geometry": _sliver(5000, 2)}])
        assert below_minimum_feature_area(layer, minimum_area=100.0) == []

    def test_negative_threshold_is_refused(self):
        with pytest.raises(ValueError):
            below_minimum_feature_area(_frame([{"geometry": _compact()}]), minimum_area=-1)


class TestThinGeometry:
    def test_sliver_is_caught(self):
        layer = _frame([{"geometry": _sliver(200, 0.5)}])
        names = [i.problem_name for i in thin_geometry(layer, minimum_width=2.0)]
        assert names == ["geometry_thin_sliver"]

    def test_compact_polygon_passes(self):
        layer = _frame([{"geometry": _compact(50)}])
        assert thin_geometry(layer, minimum_width=2.0) == []

    def test_width_check_is_scale_correct(self):
        """A metre-wide strip is a metre wide whether it is 20 m or 5 km long."""
        short = _frame([{"geometry": _sliver(20, 1)}])
        long = _frame([{"geometry": _sliver(5000, 1)}])
        assert thin_geometry(short, minimum_width=2.0)
        assert thin_geometry(long, minimum_width=2.0)

    def test_lines_are_not_treated_as_polygons(self):
        layer = _frame([{"geometry": LineString([(0, 0), (1000, 0)])}])
        assert thin_geometry(layer, minimum_width=2.0) == []

    def test_measurements_can_be_requested(self):
        layer = _frame([{"geometry": _compact(50)}])
        names = [i.problem_name for i in thin_geometry(
            layer, minimum_width=2.0, report_all_measurements=True)]
        assert names == ["geometry_width_measured"]

    def test_zero_or_negative_width_is_refused(self):
        layer = _frame([{"geometry": _compact()}])
        with pytest.raises(ValueError):
            thin_geometry(layer, minimum_width=0)


class TestElongation:
    def test_strip_is_reported(self):
        layer = _frame([{"geometry": _sliver(200, 1)}])
        assert [i.problem_name for i in elongation_report(layer, maximum_elongation=50)] == [
            "geometry_elongated"
        ]

    def test_square_is_silent(self):
        layer = _frame([{"geometry": _compact(10)}])
        assert elongation_report(layer, maximum_elongation=50) == []

    def test_no_threshold_means_no_judgement(self):
        layer = _frame([{"geometry": _sliver(200, 1)}])
        assert elongation_report(layer) == []

    def test_ratio_below_one_is_refused(self):
        with pytest.raises(ValueError):
            elongation_report(_frame([{"geometry": _compact()}]), maximum_elongation=0.5)


class TestValidateShape:
    def test_runs_only_what_was_supplied(self):
        layer = _frame([{"geometry": _sliver(200, 0.5)}])
        assert validate_shape(layer, minimum_width=2.0)
        assert validate_shape(layer, minimum_area=100.0) == []

    def test_nothing_supplied_is_silent(self):
        layer = _frame([{"geometry": _sliver(200, 0.5)}])
        assert validate_shape(layer) == []


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------


class TestInspectLayer:
    def test_polygon_layer_is_identified(self):
        profile = inspect_layer(_frame([{"geometry": _compact()}, {"geometry": _compact(20)}]))
        assert profile.family == "polygon"
        assert profile.row_count == 2
        assert profile.vertex_count > 0

    def test_line_layer_is_identified(self):
        profile = inspect_layer(_frame([{"geometry": LineString([(0, 0), (1, 1)])}]))
        assert profile.family == "line"

    def test_point_layer_is_identified(self):
        profile = inspect_layer(_frame([{"geometry": Point(0, 0)}]))
        assert profile.family == "point"

    def test_mixed_family_is_flagged(self):
        profile = inspect_layer(
            _frame([{"geometry": _compact()}, {"geometry": _compact(20)},
                    {"geometry": Point(5, 5)}])
        )
        assert profile.is_mixed_family
        assert profile.family == "polygon"

    def test_crs_is_recorded(self):
        profile = inspect_layer(_frame([{"geometry": _compact()}], crs="EPSG:4326"))
        assert "4326" in profile.crs

    def test_no_geometry_column_is_handled(self):
        profile = inspect_layer(gpd.GeoDataFrame([{"a": 1}]))
        assert profile.has_geometry is False
        assert profile.family == "unknown"


class TestPlanGating:
    def test_polygon_checks_run_for_polygons(self):
        plan = build_plan(_frame([{"geometry": _compact()}]))
        assert "polygon_overlap_same_layer" in plan.applicable_conditions

    def test_polygon_checks_are_skipped_for_points_with_a_reason(self):
        plan = build_plan(_frame([{"geometry": Point(0, 0)}]))
        assert "polygon_overlap_same_layer" not in plan.applicable_conditions
        assert "polygon_overlap_same_layer" in plan.skipped_conditions
        assert "point" in plan.skipped_conditions["polygon_overlap_same_layer"]

    def test_line_checks_run_for_lines(self):
        plan = build_plan(_frame([{"geometry": LineString([(0, 0), (1, 1)])}]))
        assert "line_dangle" in plan.applicable_conditions

    def test_family_agnostic_conditions_always_apply(self):
        plan = build_plan(_frame([{"geometry": Point(0, 0)}]))
        assert "governance_licence_not_declared" in plan.applicable_conditions

    def test_every_registered_condition_is_accounted_for(self):
        """Nothing may fall through the gate unexamined."""
        plan = build_plan(_frame([{"geometry": _compact()}]))
        registered = {item.problem_name for item in list_problem_definitions()}
        accounted = set(plan.applicable_conditions) | set(plan.skipped_conditions)
        assert registered == accounted

    def test_mixed_layer_keeps_both_families(self):
        plan = build_plan(
            _frame([{"geometry": _compact()}, {"geometry": LineString([(0, 0), (1, 1)])}])
        )
        assert "polygon_overlap_same_layer" in plan.applicable_conditions
        assert "line_dangle" in plan.applicable_conditions
        assert any("mixed" in note for note in plan.notes)

    def test_plan_is_serialisable(self):
        payload = build_plan(_frame([{"geometry": _compact()}]), packs=["boundaries"]).to_dict()
        assert payload["profile"]["family"] == "polygon"
        assert "skipped_conditions" in payload


class TestChunkingDecision:
    def _big(self, n=200):
        return _frame([{"geometry": _sliver(n * 0.1, 0.5)} for _ in range(n)])

    def test_no_threshold_means_no_chunking(self):
        plan = build_plan(self._big())
        assert plan.chunk is False
        assert "No chunking threshold" in plan.chunk_reason

    def test_below_threshold_stays_whole(self):
        plan = build_plan(self._big(20), chunk_above_vertices=100000)
        assert plan.chunk is False
        assert "at or below" in plan.chunk_reason

    def test_above_threshold_without_halo_declines(self):
        plan = build_plan(self._big(), chunk_above_vertices=10)
        assert plan.chunk is True
        assert "halo" in plan.chunk_reason

    def test_above_threshold_with_halo_chunks(self):
        plan = build_plan(
            self._big(), chunk_above_vertices=10, chunk_halo_width=5.0,
            chunk_target_vertices=50,
        )
        assert plan.chunk is True
        assert plan.chunk_plan.tile_count > 1

    def test_plan_exposes_the_thresholds_it_used(self):
        plan = build_plan(self._big(), chunk_above_vertices=1000000)
        payload = plan.to_dict()
        assert "chunk" in payload and "chunk_reason" in payload


class TestValidatePlan:
    def test_skipped_checks_are_reported_when_asked_for(self):
        plan = build_plan(_frame([{"geometry": Point(0, 0)}]))
        assert "condition_not_applicable" not in [i.problem_name for i in validate_plan(plan)]
        names = [i.problem_name for i in validate_plan(plan, report_skipped=True)]
        assert "condition_not_applicable" in names

    def test_mixed_family_is_reported(self):
        plan = build_plan(
            _frame([{"geometry": _compact()}, {"geometry": Point(1, 1)}])
        )
        assert "geometry_family_mixed" in [i.problem_name for i in validate_plan(plan)]

    def test_unhaloed_chunking_is_reported(self):
        big = _frame([{"geometry": _sliver(20, 0.5)} for _ in range(200)])
        plan = build_plan(big, chunk_above_vertices=10, chunk_target_vertices=20)
        assert "chunk_halo_undeclared" in [i.problem_name for i in validate_plan(plan)]

    def test_clean_plan_is_silent(self):
        plan = build_plan(_frame([{"geometry": _compact()}]))
        assert validate_plan(plan) == []


class TestRegistry:
    @pytest.mark.parametrize(
        "name",
        ["feature_zero_area", "below_minimum_feature_area", "geometry_thin_sliver",
         "geometry_width_measured", "geometry_elongated", "condition_not_applicable"],
    )
    def test_registered(self, name):
        entry = get_problem_definition(name)
        assert entry is not None
        assert entry.description and entry.repair_hint
        assert entry.default_severity in {"critical", "high", "medium", "low", "info"}

    def test_a_skipped_check_is_evidence_not_a_defect(self):
        assert get_problem_definition("condition_not_applicable").issue_class == "evidence_condition"
        assert get_problem_definition("condition_not_applicable").default_actionable is False

    def test_a_measurement_is_not_actionable(self):
        assert get_problem_definition("geometry_width_measured").default_actionable is False

    def test_area_floor_is_evidence_because_it_is_blunt(self):
        assert get_problem_definition("below_minimum_feature_area").issue_class == "evidence_condition"

    def test_family_map_only_names_real_families(self):
        assert set(CONDITION_FAMILIES.values()) <= {"polygon", "line", "point", "any"}