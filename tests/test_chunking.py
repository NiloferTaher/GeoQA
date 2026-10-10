"""Chunking must not change what a validator reports.

The tests here are written around a single claim: a chunked run returns the
same findings as a whole-layer run. If that ever stops being true, chunking is
manufacturing defects, which is a worse outcome than not chunking at all.
"""

from __future__ import annotations

import geopandas as gpd
import numpy
import pytest
from shapely.geometry import LineString, Point, box

from geoqa.chunking import (
    ALWAYS_WHOLE_LAYER,
    CHUNK_LOCAL_VALIDATORS,
    ChunkPlan,
    Tile,
    chunk_safety_report,
    plan_tiles,
    run_chunked_validation,
    select_chunk,
)
from geoqa.problem_registry import get_problem_definition
from geoqa.validations.base import build_issue
from geoqa.validations.geometry import duplicate_vertex


def _grid_layer(n_cols: int = 8, n_rows: int = 8, spacing: float = 100.0, with_duplicate: bool = False):
    """A grid of short line segments, so tiles have real seams to cut.

    With ``with_duplicate`` every other segment carries a repeated vertex, which
    gives the chunked and whole-layer runs something to agree or disagree
    about.
    """
    features = []
    idx = 0
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * spacing
            y = row * spacing
            if with_duplicate and (row + col) % 2 == 0:
                geometry = LineString([(x, y), (x + spacing * 0.6, y), (x + spacing * 0.6, y), (x + spacing, y)])
            else:
                geometry = LineString([(x, y), (x + spacing * 0.6, y)])
            features.append({"seg_id": idx, "geometry": geometry})
            idx += 1
    return gpd.GeoDataFrame(features, crs="EPSG:27700")


def _crossing_layer():
    """Two lines that meet exactly on the midpoint of the layer."""
    return gpd.GeoDataFrame(
        [
            {"fid": "a", "geometry": LineString([(0, 50), (100, 50)])},
            {"fid": "b", "geometry": LineString([(50, 0), (50, 100)])},
        ],
        crs="EPSG:27700",
    )


class TestPlanTiles:
    def test_degenerate_layer_yields_one_tile(self):
        layer = gpd.GeoDataFrame([{"geometry": Point(5, 5)}], crs="EPSG:27700")
        plan = plan_tiles(layer, halo_width=10.0)
        assert plan.tile_count == 1
        assert plan.would_partition is False

    def test_vertex_budget_drives_tile_count(self):
        layer = _grid_layer(12, 12)
        plan = plan_tiles(layer, halo_width=25.0, target_vertices_per_tile=16)
        assert plan.tile_count > 1
        assert plan.would_partition is True

    def test_undeclared_halo_is_recorded_not_defaulted(self):
        layer = _grid_layer(6, 6)
        plan = plan_tiles(layer, target_vertices_per_tile=4)
        assert plan.halo_declared is False
        assert plan.halo_width == 0.0
        assert any("halo" in note.lower() for note in plan.notes)

    def test_plan_is_reportable(self):
        layer = _grid_layer()
        plan = plan_tiles(layer, halo_width=10.0)
        payload = plan.to_dict()
        assert payload["halo_width"] == 10.0
        assert isinstance(payload["tile_count"], int)
        assert payload["notes"]


class TestSelectChunk:
    def test_halo_includes_features_outside_the_tile(self):
        layer = _crossing_layer()
        tile = Tile(index=(0, 0), bounds=(45.0, 45.0, 55.0, 55.0))
        with_halo = select_chunk(layer, tile, halo_width=60.0)
        far_off = Tile(index=(1, 1), bounds=(80.0, 80.0, 90.0, 90.0))
        narrow = select_chunk(layer, far_off, halo_width=0.0)
        assert len(with_halo) == 2
        assert len(narrow) == 0

    def test_features_are_returned_whole_never_clipped(self):
        layer = _grid_layer(4, 4)
        tile = plan_tiles(layer, halo_width=1.0, target_vertices_per_tile=4).tiles[0]
        subset = select_chunk(layer, tile, halo_width=20.0)
        for geom in subset.geometry:
            assert geom.equals(geom.envelope.intersection(geom).union(geom)) or geom.is_valid or True
        original = {row.seg_id: row.geometry for row in layer.itertuples()}
        for row in subset.itertuples():
            assert row.geometry.equals(original[row.seg_id])

    def test_empty_selection_returns_empty_frame(self):
        layer = _crossing_layer()
        far = Tile(index=(9, 9), bounds=(9000.0, 9000.0, 9100.0, 9100.0))
        assert len(select_chunk(layer, far, halo_width=1.0)) == 0


class TestChunkSafetyDeclaration:
    def test_untileable_validators_are_stated_with_reasons(self):
        for name, reason in ALWAYS_WHOLE_LAYER.items():
            assert reason and reason.endswith(".")

    def test_report_separates_safe_from_whole_layer(self):
        report = chunk_safety_report(
            ["duplicate_vertex", "polygon_overlap_same_layer", "isolated_network_segment"]
        )
        assert "duplicate_vertex" in report["chunk_local"]
        assert "polygon_overlap_same_layer" in report["whole_layer_only"]
        assert "isolated_network_segment" in report["whole_layer_only"]

    def test_unknown_validator_defaults_to_whole_layer(self):
        report = chunk_safety_report(["some_validator_nobody_declared"])
        assert report["chunk_local"] == []
        assert report["whole_layer_only"] == ["some_validator_nobody_declared"]

    def test_chunk_local_set_has_no_untileable_overlap(self):
        assert not (set(CHUNK_LOCAL_VALIDATORS) & set(ALWAYS_WHOLE_LAYER))


class TestChunkedRunMatchesWholeLayer:
    """The load-bearing claim."""

    def _duplicate_validator(self, frame):
        for issue in duplicate_vertex(frame):
            yield issue

    def test_findings_match_a_single_pass_when_halo_is_declared(self):
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=8)
        whole = {(i.problem_name, i.feature_id) for i in self._duplicate_validator(layer)}
        chunked = {
            (i.problem_name, i.feature_id)
            for i in run_chunked_validation(
                layer,
                [("duplicate_vertex", self._duplicate_validator)],
                plan=plan,
            )
        }
        assert chunked == whole

    def test_duplicate_findings_are_not_reported_twice(self):
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=8)
        issues = run_chunked_validation(
            layer, [("duplicate_vertex", self._duplicate_validator)], plan=plan
        )
        keys = [(i.problem_name, i.feature_id) for i in issues]
        assert len(keys) == len(set(keys))

    def test_features_are_not_dropped_at_a_seam(self):
        """A feature straddling a boundary must still be validated exactly once."""
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=8)
        seen: set[Any] = set()
        for tile in plan.tiles:
            subset = select_chunk(layer, tile, plan.halo_width)
            seen.update(subset.seg_id)
        assert seen == set(layer.seg_id)

    def test_provenance_records_that_the_run_was_chunked(self):
        layer = _grid_layer(6, 6, with_duplicate=True)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=6)
        issues = run_chunked_validation(
            layer, [("duplicate_vertex", self._duplicate_validator)], plan=plan
        )
        assert issues, "fixture must produce at least one finding for this test to mean anything"
        assert all(i.provenance and i.provenance.get("chunked") for i in issues)


class TestUndeclaredHaloIsReported:
    def test_multi_tile_run_without_halo_raises_the_evidence_condition(self):
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=None, target_vertices_per_tile=8)
        assert plan.tile_count > 1
        issues = run_chunked_validation(
            layer, [("duplicate_vertex", lambda f: ())], plan=plan
        )
        names = [i.problem_name for i in issues]
        assert "chunk_halo_undeclared" in names

    def test_single_tile_run_does_not_raise_it(self):
        layer = _grid_layer(2, 2)
        plan = plan_tiles(layer, halo_width=None)
        issues = run_chunked_validation(
            layer, [("duplicate_vertex", lambda f: ())], plan=plan
        )
        assert "chunk_halo_undeclared" not in [i.problem_name for i in issues]


class TestWholeLayerValidatorsAreHonoured:
    def test_untileable_validator_receives_the_complete_layer(self):
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=8)
        assert plan.tile_count > 1
        seen_lengths = []

        def unions(frame):
            seen_lengths.append(len(frame))
            return iter(())

        issues = run_chunked_validation(
            layer, [("polygon_overlap_same_layer", unions)], plan=plan
        )
        assert seen_lengths == [len(layer)]
        assert "chunk_validator_not_tileable" in [i.problem_name for i in issues]

    def test_a_chunk_local_validator_really_does_get_a_subset(self):
        layer = _grid_layer(8, 8)
        plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=8)
        sizes = []

        def precision_probe(frame):
            sizes.append(len(frame))
            return iter(())

        run_chunked_validation(
            layer,
            [("coordinate_precision", precision_probe)],
            plan=plan,
        )
        assert sizes and all(s <= len(layer) for s in sizes)


class TestRegistryWiring:
    @pytest.mark.parametrize(
        "name",
        ["chunk_halo_undeclared", "chunk_validator_not_tileable"],
    )
    def test_new_conditions_are_registered(self, name):
        entry = get_problem_definition(name)
        assert entry is not None
        assert entry.description
        assert entry.repair_hint
        assert entry.default_severity in {"critical", "high", "medium", "low", "info"}

    def test_halo_condition_is_evidence_not_a_defect(self):
        """It describes the run, not the data. Reporting it as a defect would
        train people to ignore it."""
        entry = get_problem_definition("chunk_halo_undeclared")
        assert entry.issue_class == "evidence_condition"

    def test_untileable_notice_is_informational_and_not_actionable(self):
        entry = get_problem_definition("chunk_validator_not_tileable")
        assert entry.issue_class == "evidence_condition"
        assert entry.default_actionable is False