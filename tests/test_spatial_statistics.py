"""Tests for spatial statistics.

The statistics are checked against cases whose answer is known in advance.
A clustering index that returns a confident number for data with no pattern
is worse than no index at all, because it would be trusted.
"""

from __future__ import annotations

import geopandas as gpd
import numpy
import pytest
from shapely.geometry import Polygon, box

from geoqa.problem_registry import get_problem_definition
from geoqa.validations.spatial_statistics import (
    SpatialWeights,
    build_weights,
    gearys_c,
    getis_ord_gi_star,
    local_moran,
    morans_i,
    profile_spatial_statistics,
    spatial_outliers,
    variogram,
)


def _grid(value_fn, n=10, size=50.0, step=100.0):
    return gpd.GeoDataFrame(
        [{"geometry": box(c * step, r * step, c * step + size, r * step + size),
          "reading": value_fn(r, c)} for r in range(n) for c in range(n)],
        crs="EPSG:27700",
    )


# --------------------------------------------------------------------------


class TestWeights:
    def test_knn_rows_are_standardised(self):
        layer = _grid(lambda r, c: float(r + c))
        w = build_weights(layer, method="knn", k=4)
        assert numpy.allclose(numpy.asarray(w.matrix).sum(axis=1), 1.0)

    def test_method_is_recorded(self):
        layer = _grid(lambda r, c: 1.0)
        assert build_weights(layer, method="knn", k=4).to_dict()["method"] == "knn"

    def test_empty_layer_does_not_crash(self):
        empty = gpd.GeoDataFrame({"geometry": []}, crs="EPSG:27700")
        assert build_weights(empty).n == 0

    def test_unknown_method_is_refused(self):
        with pytest.raises(ValueError):
            build_weights(_grid(lambda r, c: 1.0), method="telepathy")


class TestMoransI:
    def test_clustered_data_is_strongly_positive(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.i_value > 0.5
        assert result.z_score > 3.0

    def test_checkerboard_is_strongly_negative(self):
        layer = _grid(lambda r, c: 100.0 if (r + c) % 2 == 0 else 10.0)
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.i_value < -0.5
        assert result.z_score < -3.0

    def test_random_data_gives_no_significant_pattern(self):
        rng = numpy.random.default_rng(11)
        layer = _grid(lambda r, c: float(rng.normal()))
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert abs(result.z_score) < 3.0

    def test_expectation_is_minus_one_over_n_minus_one(self):
        layer = _grid(lambda r, c: float(rng_value(r, c)))
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.expected == pytest.approx(-1.0 / (result.n - 1))

    def test_constant_values_are_reported_not_tested(self):
        """I is undefined with no variation, and saying so beats returning 0."""
        layer = _grid(lambda r, c: 42.0)
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.i_value != result.i_value  # nan
        assert "No variation" in result.interpretation

    def test_too_few_features_is_refused(self):
        layer = gpd.GeoDataFrame([{"geometry": Point_(), "reading": 1.0}], crs="EPSG:27700")
        result = morans_i(layer["reading"].values, build_weights(layer, method="knn", k=1))
        assert result.i_value != result.i_value

    def test_missing_values_are_refused_not_ignored(self):
        layer = _grid(lambda r, c: float(r + c))
        values = numpy.asarray(layer["reading"].values, dtype=float)
        values[0] = numpy.nan
        with pytest.raises(ValueError):
            morans_i(values, build_weights(layer, method="knn", k=4))


def rng_value(r, c):
    return float((r * 7 + c * 13) % 9)


def Point_():
    from shapely.geometry import Point
    return Point(0, 0)


class TestGearysC:
    def test_clustering_gives_c_below_one(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        result = gearys_c(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.c_value < 0.8
        assert result.expected == 1.0

    def test_alternation_gives_c_above_one(self):
        layer = _grid(lambda r, c: 100.0 if (r + c) % 2 == 0 else 10.0)
        result = gearys_c(layer["reading"].values, build_weights(layer, method="knn", k=4))
        assert result.c_value > 1.2

    def test_geary_agrees_with_moran_about_direction(self):
        """They weight different things but must not contradict each other."""
        for name, fn in (("cluster", lambda r, c: 100.0 if c < 5 else 10.0),
                         ("alternate", lambda r, c: 100.0 if (r + c) % 2 == 0 else 10.0)):
            layer = _grid(fn)
            w = build_weights(layer, method="knn", k=4)
            m = morans_i(layer["reading"].values, w)
            g = gearys_c(layer["reading"].values, w)
            assert (m.i_value > 0) == (g.c_value < 1.0), name


class TestLocalMoran:
    def test_quadrants_are_assigned(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        w = build_weights(layer, method="knn", k=4)
        result = local_moran(layer["reading"].values, w, layer.index.tolist())
        counts = result.counts()
        assert counts["high_high"] > 0
        assert sum(counts.values()) == len(layer)

    def test_high_among_low_is_detected_as_a_quadrant(self):
        rows = []
        for r in range(8):
            for c in range(8):
                value = 100.0 if (c, r) != (6, 6) else 10.0
                rows.append({"geometry": box(c * 100.0, r * 100.0, c * 100.0 + 50, r * 100.0 + 50),
                             "reading": value})
        layer = gpd.GeoDataFrame(rows, crs="EPSG:27700")
        w = build_weights(layer, method="knn", k=4)
        result = local_moran(layer["reading"].values, w, layer.index.tolist())
        assert result.quadrants[6 * 8 + 6] == "low_high"


class TestGetisOrd:
    def test_hot_spot_scores_positive(self):
        rows = []
        for r in range(8):
            for c in range(8):
                value = 500.0 if (c < 3 and r < 3) else 1.0
                rows.append({"geometry": box(c * 100.0, r * 100.0, c * 100.0 + 50, r * 100.0 + 50),
                             "reading": value})
        layer = gpd.GeoDataFrame(rows, crs="EPSG:27700")
        w = build_weights(layer, method="knn", k=4)
        scores = getis_ord_gi_star(layer["reading"].values, w, layer.index.tolist())
        assert scores[0]["score"] > 0

    def test_results_cover_every_feature(self):
        layer = _grid(lambda r, c: float(r + c))
        w = build_weights(layer, method="knn", k=4)
        assert len(getis_ord_gi_star(layer["reading"].values, w, layer.index.tolist())) == len(layer)


class TestVariogram:
    def test_returns_bins(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        coords = numpy.array([[g.centroid.x, g.centroid.y] for g in layer.geometry])
        result = variogram(coords, layer["reading"].values)
        assert result["ok"] is True
        assert result["bins"]

    def test_nugget_ratio_is_a_fraction(self):
        layer = _grid(lambda r, c: float(rng_value(r, c)))
        coords = numpy.array([[g.centroid.x, g.centroid.y] for g in layer.geometry])
        result = variogram(coords, layer["reading"].values)
        if result["ok"] and result["nugget_ratio"] is not None:
            assert 0.0 <= result["nugget_ratio"] <= 1.0

    def test_too_few_points_is_reported(self):
        assert variogram(numpy.zeros((1, 2)), [1.0])["ok"] is False


class TestSpatialOutliers:
    def _layer_with_planted(self):
        rows = []
        for r in range(10):
            for c in range(10):
                value = 100.0 if c < 5 else 10.0
                if c == 8 and r == 8:
                    value = 999.0
                rows.append({"geometry": box(c * 100.0, r * 100.0, c * 100.0 + 50, r * 100.0 + 50),
                             "reading": value})
        return gpd.GeoDataFrame(rows, crs="EPSG:27700")

    def test_value_inconsistent_with_its_neighbours_is_found(self):
        """This is the false-negative case: per-feature checks cannot see it."""
        layer = self._layer_with_planted()
        found = spatial_outliers(layer, "reading",
                                 weights=build_weights(layer, method="knn", k=4))
        assert len(found) == 1
        assert found[0].problem_name == "spatial_statistical_outlier"
        assert found[0].extra["value"] == 999.0

    def test_the_explanation_states_both_deviations(self):
        layer = self._layer_with_planted()
        found = spatial_outliers(layer, "reading",
                                 weights=build_weights(layer, method="knn", k=4))
        assert "standard deviations from the global mean" in found[0].description

    def test_clean_data_yields_nothing(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        assert spatial_outliers(layer, "reading",
                                weights=build_weights(layer, method="knn", k=4)) == []

    def test_absent_column_is_silent(self):
        assert spatial_outliers(_grid(lambda r, c: 1.0), "nope") == []

    def test_too_few_features_is_silent(self):
        small = gpd.GeoDataFrame([{"geometry": box(0, 0, 1, 1), "reading": 1.0}], crs="EPSG:27700")
        assert spatial_outliers(small, "reading") == []


class TestProfile:
    def test_profile_reports_both_statistics(self):
        layer = _grid(lambda r, c: 100.0 if c < 5 else 10.0)
        profile = profile_spatial_statistics(layer, "reading")
        assert profile.moran is not None and profile.geary is not None
        assert profile.local is not None and profile.gi_star is not None
        payload = profile.to_dict()
        assert payload["column"] == "reading"
        assert payload["n"] == len(layer)

    def test_absent_column_is_reported_with_a_reason(self):
        profile = profile_spatial_statistics(_grid(lambda r, c: 1.0), "nope")
        assert profile.notes and "absent" in profile.notes[0]

    def test_constant_column_is_reported(self):
        profile = profile_spatial_statistics(_grid(lambda r, c: 7.0), "reading")
        assert any("identical" in note for note in profile.notes)


class TestRegistry:
    @pytest.mark.parametrize("name", [
        "spatial_statistical_outlier", "spatial_cluster_detected",
        "spatial_autocorrelation_absent", "spatial_hotspot_detected",
        "spatial_variogram_noise_dominated",
    ])
    def test_registered(self, name):
        entry = get_problem_definition(name)
        assert entry is not None
        assert entry.description and entry.repair_hint
        assert entry.default_severity in {"critical", "high", "medium", "low", "info"}

    def test_a_cluster_is_evidence_not_a_defect(self):
        """Clustering is a property of the world, not an error in the data."""
        assert get_problem_definition("spatial_cluster_detected").issue_class == "evidence_condition"
        assert get_problem_definition("spatial_cluster_detected").default_actionable is False

    def test_an_inconsistent_value_is_a_defect(self):
        assert get_problem_definition("spatial_statistical_outlier").issue_class == "data_issue"