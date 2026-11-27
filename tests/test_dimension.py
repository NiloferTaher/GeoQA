"""Tests for geometry-dimension evidence.

The all-zero-Z rule is the one worth pinning hardest. It is not obvious: a
geometry with Z on every vertex is dimensionally 2D, but a naive dimensionality
check treats it as 3D and pushes an unnecessary 3D column type into the
database. The rule came from the author's own production PostGIS loader
(``layer_z_summary`` / ``infer_pg_type_from_gdf``), where the column type is
derived as ``GEOMETRYZ if effective_3d else GEOMETRY``.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from geoqa.validations.dimension import (
    profile_dimension,
    validate_geometry_dimension,
)


def _layer(*lines, crs="EPSG:4326"):
    return gpd.GeoDataFrame(
        {"id": list(range(len(lines)))}, geometry=list(lines), crs=crs
    )


def test_true_3d_is_detected():
    profile = profile_dimension(_layer(LineString([(0, 0, 10), (1, 0, 20)])))
    assert profile.with_z == 1
    assert profile.all_zero_z == 0
    assert profile.effective_3d_features == 1
    assert profile.recommended_postgis_type == "GEOMETRYZ"


def test_all_zero_z_resolves_to_2d_column():
    """The non-obvious operational rule, pinned."""
    profile = profile_dimension(_layer(LineString([(0, 0, 0), (1, 0, 0)])))
    assert profile.with_z == 1
    assert profile.all_zero_z == 1
    assert profile.effective_3d_features == 0
    # despite declaring Z, the column type is 2D
    assert profile.recommended_postgis_type == "GEOMETRY"


def test_pure_2d_layer():
    profile = profile_dimension(_layer(LineString([(0, 0), (1, 0)])))
    assert profile.no_z == 1
    assert profile.with_z == 0
    assert profile.recommended_postgis_type == "GEOMETRY"


def test_mixed_dimension_is_detected():
    layer = _layer(
        LineString([(0, 0, 5), (1, 0, 6)]),
        LineString([(0, 1), (1, 1)]),
    )
    profile = profile_dimension(layer)
    assert profile.is_mixed is True
    names = {i.problem_name for i in validate_geometry_dimension(layer)}
    assert "geometry_z_inconsistent" in names


def test_z_range_is_reported():
    profile = profile_dimension(_layer(
        LineString([(0, 0, -3), (1, 0, 12)]),
    ))
    assert profile.z_min == -3
    assert profile.z_max == 12


def test_all_zero_z_is_flagged_as_low_severity():
    """It is worth reporting, but it is not an error."""
    layer = _layer(LineString([(0, 0, 0), (1, 0, 0)]))
    issues = validate_geometry_dimension(layer)
    zero = [i for i in issues if i.problem_name == "geometry_z_all_zero"]
    assert len(zero) == 1
    assert str(zero[0].severity) == "low"


def test_no_target_means_three_d_is_not_a_defect():
    """The key design decision: 3D data is not defective per se."""
    layer = _layer(LineString([(0, 0, 10), (1, 0, 20)]))
    issues = validate_geometry_dimension(layer, target_dimension=None)
    assert [i for i in issues if i.problem_name == "geometry_dimension_mismatch"] == []


def test_target_2d_against_real_3d_is_nonconforming():
    layer = _layer(LineString([(0, 0, 10), (1, 0, 20)]))
    issues = validate_geometry_dimension(layer, target_dimension=2)
    mismatch = [i for i in issues if i.problem_name == "geometry_dimension_mismatch"]
    assert len(mismatch) == 1
    assert str(mismatch[0].severity) == "medium"


def test_target_3d_against_all_zero_z_is_nonconforming():
    """The mirror case: all-zero Z does not satisfy a 3D requirement."""
    layer = _layer(LineString([(0, 0, 0), (1, 0, 0)]))
    issues = validate_geometry_dimension(layer, target_dimension=3)
    names = [i.problem_name for i in issues]
    assert "geometry_dimension_mismatch" in names


def test_target_3d_against_real_3d_is_conforming():
    layer = _layer(LineString([(0, 0, 10), (1, 0, 20)]))
    issues = validate_geometry_dimension(layer, target_dimension=3)
    assert [i for i in issues if i.problem_name == "geometry_dimension_mismatch"] == []


def test_conforming_2d_against_no_target_is_silent():
    layer = _layer(LineString([(0, 0), (1, 0)]))
    assert validate_geometry_dimension(layer) == []


def test_empty_layer_is_safe():
    empty = gpd.GeoDataFrame({"id": []}, geometry=[], crs="EPSG:4326")
    profile = profile_dimension(empty)
    assert profile.features == 0
    assert validate_geometry_dimension(empty) == []


def test_near_zero_noise_treated_as_zero():
    """Float noise from round-tripping must not promote a 2D layer to 3D."""
    layer = _layer(LineString([(0, 0, 1e-12), (1, 0, -1e-12)]))
    profile = profile_dimension(layer)
    assert profile.all_zero_z == 1
    assert profile.recommended_postgis_type == "GEOMETRY"


def test_mixed_can_be_suppressed():
    layer = _layer(
        LineString([(0, 0, 5), (1, 0, 6)]),
        LineString([(0, 1), (1, 1)]),
    )
    issues = validate_geometry_dimension(layer, flag_mixed=False)
    assert [i for i in issues if i.problem_name == "geometry_z_inconsistent"] == []


def test_extra_payload_carries_the_profile():
    layer = _layer(LineString([(0, 0, 5), (1, 0, 6)]), LineString([(0, 1), (1, 1)]))
    issue = validate_geometry_dimension(layer)[0]
    payload = issue.to_dict()
    assert "recommended_postgis_type" in str(payload)
    assert "mixed" in str(payload)


def test_projected_crs_still_detects_z():
    layer = _layer(
        LineString([(500000.0, 4500000.0, 10), (500010.0, 4500000.0, 20)]),
        crs="EPSG:32632",
    )
    assert profile_dimension(layer).recommended_postgis_type == "GEOMETRYZ"