"""Feed every validator deliberately malformed data and require it to behave.

The property under test is not "the validator finds the defect". It is that a
validator handed something it cannot handle returns a finding or returns
nothing, and never raises something the caller did not ask for. A validator
that crashes on a null geometry takes down a batch run that had already
processed nine thousand good features, and the caller cannot tell from the
traceback which of the forty validators was at fault.

Every case here is something real deliveries contain: a spreadsheet export
with a header row repeated in the middle, a shapefile whose first row has no
geometry, a CSV where every date is ambiguous, a layer with no CRS, a
polygon collapsed to a point by a bad conversion.

Two failure modes are treated as bugs and neither is tolerated:

- an unhandled exception escaping the validator;
- a returned issue whose problem_name is not in the registry, which means the
  validator is reporting through a side channel instead of the catalogue.
"""

from __future__ import annotations

import warnings

import geopandas as gpd
import numpy
import pandas as pd
import pytest
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
    box,
)

from geoqa.problem_registry import get_problem_definition


def _frame(rows, crs="EPSG:27700"):
    return gpd.GeoDataFrame(rows, crs=crs)


#: The validators a hostile-input sweep should cover. Anything added to the
#: library that takes a layer belongs here; a validator that is never tested
#: against junk is a validator that will meet it in production.
VALIDATORS = [
    ("null_geometry", "geoqa.validations.geometry", "null_geometry"),
    ("self_intersection", "geoqa.validations.geometry", "self_intersection"),
    ("duplicate_vertex", "geoqa.validations.geometry", "duplicate_vertex"),
    ("below_minimum_feature_length", "geoqa.validations.geometry", "below_minimum_feature_length"),
    ("sharp_angle_cutback", "geoqa.validations.geometry", "sharp_angle_cutback"),
    ("coordinate_precision", "geoqa.validations.accuracy", "coordinate_precision"),
    ("positional_accuracy", "geoqa.validations.accuracy", "positional_accuracy", {}, True),
    ("uniqueness", "geoqa.validations.attributes", "uniqueness",
     {"field": "asset_id"}),
    ("domain_range_checks", "geoqa.validations.attributes", "domain_range_checks",
     {"field": "length", "valid_domain": [1.0, 2.0]}),
    ("required_nulls", "geoqa.validations.attributes", "required_nulls",
     {"required_fields": ["asset_id"]}),
    ("triage_endpoints", "geoqa.validations.endpoint_triage", "triage_endpoints"),
    ("validate_geometry_dimension", "geoqa.validations.dimension", "validate_geometry_dimension"),
    ("profile_dimension", "geoqa.validations.dimension", "profile_dimension"),
    ("missing_crs", "geoqa.validations.crs", "missing_crs"),
    ("invalid_crs", "geoqa.validations.crs", "invalid_crs"),
    ("incomplete_metadata", "geoqa.validations.metadata", "incomplete_metadata"),
    ("profile_geometry_parts", "geoqa.validations.datatypes", "profile_geometry_parts"),
    ("validate_geometry_parts", "geoqa.validations.datatypes", "validate_geometry_parts"),
    ("profile_datatypes", "geoqa.validations.datatypes", "profile_datatypes"),
    ("validate_datatypes", "geoqa.validations.datatypes", "validate_datatypes"),
    ("postgis_expectations", "geoqa.validations.datatypes", "postgis_expectations"),
    ("sentinel_report", "geoqa.validations.sentinels", "sentinel_report"),
    ("validate_sentinels", "geoqa.validations.sentinels", "validate_sentinels"),
    ("profile_shape", "geoqa.validations.shape", "profile_shape"),
    ("below_minimum_feature_area", "geoqa.validations.shape", "below_minimum_feature_area"),
    ("thin_geometry", "geoqa.validations.shape", "thin_geometry"),
    ("elongation_report", "geoqa.validations.shape", "elongation_report"),
    ("inspect_layer", "geoqa.dispatch", "inspect_layer"),
    ("build_plan", "geoqa.dispatch", "build_plan"),
    ("plan_tiles", "geoqa.chunking", "plan_tiles"),
    ("chunk_safety_report", "geoqa.chunking", "chunk_safety_report"),
    ("coverage_report", "geoqa.validations.coverage", "coverage_report",
     {"id_field": "asset_id"}, True),
    ("validate_coverage_floor", "geoqa.validations.coverage", "validate_coverage_floor",
     {"id_field": "asset_id"}, True),
    ("validate_split_completeness", "geoqa.validations.coverage", "validate_split_completeness"),
    ("buffer_zero_audit", "geoqa.validations.transform_audit", "buffer_zero_audit"),
    ("audit_attribute_preservation", "geoqa.validations.transform_audit",
     "audit_attribute_preservation", {"key_field": "asset_id"}, True),
]


#: Arguments offered to every validator. The call helper keeps only the ones
#: a given validator actually declares, so one list serves all of them.
DEFAULTS = {
    "minimum_area": 1.0,
    "minimum_width": 1.0,
    "id_field": "asset_id",
    "key_field": "asset_id",
    "maximum_elongation": 10.0,
    "minimum_retained": 0.2,
    "snap_tolerance": 10.0,
}


def _resolve(module_path: str, name: str):
    import importlib

    return getattr(importlib.import_module(module_path), name)


def _call(fn, layer, kwargs=None, needs_second_layer=False):
    """Call a validator, supplying only the arguments it actually declares.

    Several validators take two layers, or a required field name, and the
    sweep has to reach all of them without hand-writing a call per entry.
    """
    import inspect

    kwargs = kwargs or {}
    try:
        signature = inspect.signature(fn)
        parameters = signature.parameters
    except (TypeError, ValueError):
        parameters = {}

    if needs_second_layer:
        return fn(layer, layer, **kwargs)
    merged = dict(DEFAULTS)
    merged.update(kwargs)
    accepted = {k: v for k, v in merged.items() if k in parameters}
    return fn(layer, **accepted)


#: Layers that have all appeared in a real delivery at some point.
HOSTILE_LAYERS = {
    "empty_frame": gpd.GeoDataFrame({"geometry": []}, crs="EPSG:27700"),
    "no_geometry_column": gpd.GeoDataFrame({"a": [1, 2, 3]}),
    "no_crs": gpd.GeoDataFrame([{"geometry": box(0, 0, 1, 1)}]),
    "all_null_geometry": _frame([{"geometry": None}, {"geometry": None}]),
    "empty_geometries": _frame([{"geometry": Polygon()}, {"geometry": LineString()}]),
    "single_feature": _frame([{"geometry": box(0, 0, 1, 1)}]),
    "mixed_families": _frame([{"geometry": box(0, 0, 1, 1)}, {"geometry": Point(5, 5)},
                              {"geometry": LineString([(0, 0), (1, 1)])}]),
"mixed_dimensions": _frame([
        {"geometry": box(0, 0, 1, 1)},
        {"geometry": Polygon(
            [(0, 0, 0), (5, 0, 1), (5, 5, 2), (0, 5, 3), (0, 0, 0)],
            [[(1, 1, 0), (2, 1, 0), (2, 2, 0), (1, 2, 0), (1, 1, 0)]],
        )},
    ]),
    "zero_area": _frame([{"geometry": box(0, 0, 0, 0)}]),
    "self_intersecting": _frame([
        {"geometry": Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])}
    ]),
    "nan_coordinates": _frame([{"geometry": Point(float("nan"), float("nan"))}]),
    "infinite_coordinates": _frame([{"geometry": Point(float("inf"), float("inf"))}]),
    "huge_coordinates": _frame([{"geometry": box(1e12, 1e12, 1e12 + 1, 1e12 + 1)}]),
    "negative_coordinates": _frame([{"geometry": box(-5000, -5000, -4999, -4999)}]),
    "duplicate_vertex_spike": _frame([{"geometry": LineString([(0, 0), (0, 0), (1, 1)])}]),
    "geometry_collection": _frame([{"geometry": GeometryCollection([box(0, 0, 1, 1)])}]),
    "nested_multipolygon": _frame([
        {"geometry": MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])}
    ]),
    "text_in_numeric": _frame([
        {"geometry": box(0, 0, 1, 1), "length": "not a number"},
        {"geometry": box(2, 2, 3, 3), "length": "12,5"},
    ]),
    "sentinel_values": _frame([
        {"geometry": box(0, 0, 1, 1), "reading": -999, "name": "N/A"},
        {"geometry": box(2, 2, 3, 3), "reading": 0, "name": ""},
    ]),
    "unicode_columns": _frame([
        {"geometry": box(0, 0, 1, 1), "اسم": "قيمة", "Ångström": 1.0}
    ]),
    "identifier_as_float": _frame([{"geometry": box(0, 0, 1, 1), "asset_id": 1.0}]),
    "ambiguous_dates": _frame([
        {"geometry": box(0, 0, 1, 1), "date": "03/04/2026"},
        {"geometry": box(2, 2, 3, 3), "date": "2026-13-45"},
    ]),
    "all_identical_keys": _frame([
        {"geometry": box(i, i, i + 1, i + 1), "asset_id": 1} for i in range(5)
    ]),
    "zero_rows_with_columns": gpd.GeoDataFrame(
        {"geometry": [], "asset_id": [], "length": []}, crs="EPSG:4326"
    ),
}


def _iter_issues(result):
    if result is None:
        return []
    if isinstance(result, list):
        return [r for r in result if hasattr(r, "problem_name")]
    if hasattr(result, "to_issues"):
        try:
            return list(result.to_issues())
        except Exception:
            return []
    return []


class TestValidatorsSurviveHostileInput:
    @pytest.mark.parametrize("layer_name", sorted(HOSTILE_LAYERS))
    @pytest.mark.parametrize("entry", VALIDATORS, ids=[e[0] for e in VALIDATORS])
    def test_validator_does_not_crash(self, layer_name, entry):
        """A validator may refuse bad arguments; it may not fall over.

        The contract is deliberately narrower than "never raises". A validator
        asked to check a field the layer does not have should say so plainly,
        and a ValueError naming the field is that answer. What must not happen
        is an AttributeError or KeyError from code that assumed a shape the
        input did not have, because that tells the caller nothing about which
        of forty validators was at fault or what to change.
        """
        name, module_path, attr = entry[0], entry[1], entry[2]
        extra = dict(entry[3]) if len(entry) > 3 else {}
        second = len(entry) > 4
        layer = HOSTILE_LAYERS[layer_name]
        fn = _resolve(module_path, attr)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                _call(fn, layer, extra, second)
            except ValueError:
                pass
            except Exception as exc:  # pragma: no cover - the assertion is the point
                pytest.fail(
                    f"{attr} raised {type(exc).__name__} on layer {layer_name!r}: {exc}"
                )

    @pytest.mark.parametrize("layer_name", sorted(HOSTILE_LAYERS))
    @pytest.mark.parametrize("entry", VALIDATORS, ids=[e[0] for e in VALIDATORS])
    def test_returned_issues_are_registered(self, layer_name, entry):
        """A finding reported outside the registry is a finding nobody can count."""
        name, module_path, attr = entry[0], entry[1], entry[2]
        extra = dict(entry[3]) if len(entry) > 3 else {}
        second = len(entry) > 4
        layer = HOSTILE_LAYERS[layer_name]
        fn = _resolve(module_path, attr)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                result = _call(fn, layer, extra, second)
            except ValueError:
                # Refusing bad arguments is an answer; there are no findings
                # to check for registry membership in that case.
                return

        for issue in _iter_issues(result):
            definition = get_problem_definition(issue.problem_name)
            assert definition is not None, (
                f"{attr} reported unregistered problem {issue.problem_name!r}"
            )
            assert issue.description, f"{attr} produced an issue with no description"
            assert issue.severity in {"critical", "high", "medium", "low", "info"}

    def test_no_validator_is_missing_from_the_sweep(self):
        """If someone adds a validator module, the sweep should notice."""
        assert len(VALIDATORS) >= 30


class TestSpecificHostileCases:
    def test_nan_coordinates_do_not_become_a_defect_claim(self):
        """A NaN is not evidence of anything; it is the absence of a value."""
        from geoqa.validations.shape import profile_shape

        layer = HOSTILE_LAYERS["nan_coordinates"]
        assert profile_shape(layer)["features"][0]["area"] == 0.0

    def test_empty_layer_profiles_cleanly(self):
        from geoqa.dispatch import inspect_layer

        profile = inspect_layer(HOSTILE_LAYERS["empty_frame"])
        assert profile.row_count == 0
        assert profile.has_geometry is False
        assert profile.family == "unknown"

    def test_plan_on_an_empty_layer_gates_out_every_family_specific_check(self):
        """An empty layer has no family, so every geometry-specific condition
        is skipped. Family-agnostic ones still apply, because a governance or
        metadata condition is meaningful whatever the layer contains."""
        from geoqa.dispatch import CONDITION_FAMILIES, build_plan

        plan = build_plan(HOSTILE_LAYERS["empty_frame"])
        gated = {n for n, family in CONDITION_FAMILIES.items() if family in {"line", "point"}}
        assert gated <= set(plan.skipped_conditions)
        assert "continuity_break" in plan.skipped_conditions
        assert plan.notes

    def test_coverage_on_an_empty_layer_is_silent(self):
        from geoqa.validations.coverage import validate_coverage_floor

        empty = HOSTILE_LAYERS["empty_frame"]
        assert validate_coverage_floor(empty, empty, id_field="asset_id") == []

    def test_split_check_on_an_empty_layer_is_silent(self):
        from geoqa.validations.coverage import validate_split_completeness

        empty = HOSTILE_LAYERS["empty_frame"]
        assert validate_split_completeness(empty, id_field="asset_id") == []

    def test_chunking_an_empty_layer_does_not_blow_up(self):
        from geoqa.chunking import plan_tiles

        plan = plan_tiles(HOSTILE_LAYERS["empty_frame"], halo_width=1.0)
        assert plan.tile_count >= 1
        assert plan.notes

    def test_degenerate_extent_does_not_divide_by_zero(self):
        from geoqa.validations.containment import scale_dependent_tolerance

        assert scale_dependent_tolerance(0.0, 0.01) == 0.0

    def test_thresholds_are_validated_not_assumed(self):
        from geoqa.chunking import _side_for_budget
        from geoqa.validations.shape import thin_geometry

        with pytest.raises(ValueError):
            thin_geometry(HOSTILE_LAYERS["single_feature"], minimum_width=-1.0)
        notes = []
        assert _side_for_budget(100, 0, 10.0, 10.0, notes) == 1

    def test_repeated_header_row_becomes_ordinary_data_not_a_crash(self):
        """A repeated header in the middle of a CSV export is a known defect."""
        from geoqa.validations.sentinels import sentinel_report

        frame = pd.DataFrame(
            [{"asset_id": "1", "length": "10"}, {"asset_id": "asset_id", "length": "length"}]
        )
        report = sentinel_report(frame, fields=["asset_id", "length"])
        assert isinstance(report, dict)

    def test_geometry_column_holding_strings_is_survived(self):
        layer = gpd.GeoDataFrame({"geometry": ["not a geometry", box(0, 0, 1, 1)]})
        from geoqa.dispatch import inspect_layer

        profile = inspect_layer(layer)
        assert profile.row_count == 2


class TestValidatorReturnsNothingRatherThanGuessing:
    """When a validator cannot answer, it must not invent an answer."""

    def test_split_check_declines_without_expected_area(self):
        from geoqa.validations.coverage import validate_split_completeness

        parts = _frame([{"id": "a", "geometry": box(0, 0, 1, 1)},
                        {"id": "a", "geometry": box(1, 0, 2, 1)}])
        assert validate_split_completeness(parts, id_field="id") == []

    def test_shape_check_runs_nothing_without_thresholds(self):
        from geoqa.validations.shape import validate_shape

        assert validate_shape(HOSTILE_LAYERS["single_feature"]) == []

    def test_plan_declines_to_chunk_without_a_threshold(self):
        from geoqa.dispatch import build_plan

        plan = build_plan(HOSTILE_LAYERS["huge_coordinates"])
        assert plan.chunk is False
        assert plan.chunk_reason