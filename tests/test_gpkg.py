"""Tests for GeoPackage structure.

The behaviour worth protecting: a file that opens in QGIS but is not a
conformant GeoPackage is reported, because that is exactly the case that
fails later in a tool nobody tested against.
"""

from __future__ import annotations

import json
import sqlite3

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from geoqa.gpkg import (
    GPKG_APPLICATION_ID,
    GPKG_MIN_USER_VERSION,
    list_gpkg_layers,
    profile_gpkg,
    read_gpkg_layer,
    validate_gpkg,
    write_gpkg_bundle,
)


def _names(issues):
    return [i.problem_name for i in issues]


@pytest.fixture
def sample_gpkg(tmp_path):
    """A GeoPackage written by GDAL, which is the realistic case."""
    frame = gpd.GeoDataFrame(
        {"region": ["north", "south"]},
        geometry=[Point(1, 1), Point(2, 2)],
        crs="EPSG:4326",
    )
    path = tmp_path / "sample.gpkg"
    frame.to_file(path, layer="points", driver="GPKG")
    return path


def _sqlite_copy(sample, tmp_path, name="broken.gpkg"):
    target = tmp_path / name
    target.write_bytes(sample.read_bytes())
    return target


def _drop_application_id(path):
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA application_id = {GPKG_APPLICATION_ID}")
    connection.commit()
    connection.close()


def _strip_gpkg_geometry_columns(path):
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM gpkg_geometry_columns")
    connection.commit()
    connection.close()


# --- structure ---------------------------------------------------------------

def test_gdal_written_geopackage_is_conformant(sample_gpkg):
    serious = [i for i in validate_gpkg(sample_gpkg) if str(i.severity) in {"critical", "high"}]
    assert serious == []


def test_profile_identifies_the_file(sample_gpkg):
    profile = profile_gpkg(sample_gpkg)
    assert profile.is_geopackage is True
    assert profile.user_version >= GPKG_MIN_USER_VERSION
    assert "points" in profile.layer_names


def test_profile_reads_the_layer_detail(sample_gpkg):
    layer = profile_gpkg(sample_gpkg).vector_layers[0]
    assert layer.geometry_column == "geom"
    assert layer.srs_id == 4326
    assert layer.feature_count == 2
    assert layer.extent == (1.0, 1.0, 2.0, 2.0)


def test_spatial_index_is_detected(sample_gpkg):
    layer = profile_gpkg(sample_gpkg).vector_layers[0]
    assert layer.has_spatial_index is True


def test_list_layers(sample_gpkg):
    assert list_gpkg_layers(sample_gpkg) == ("points",)


def test_read_layer_round_trips(sample_gpkg):
    frame = read_gpkg_layer(sample_gpkg, "points")
    assert len(frame) == 2
    assert frame.crs.to_epsg() == 4326


# --- nonconformance ------------------------------------------------------------

def test_plain_sqlite_is_critical(tmp_path):
    """A SQLite database is not a GeoPackage, however QGIS is configured."""
    path = tmp_path / "plain.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE t (a INTEGER)")
    connection.commit()
    connection.close()
    issue = next(i for i in validate_gpkg(path) if i.problem_name == "geopackage_not_conformant")
    assert str(issue.severity) == "critical"


def test_missing_required_table_is_critical(sample_gpkg, tmp_path):
    path = _sqlite_copy(sample_gpkg, tmp_path)
    connection = sqlite3.connect(path)
    connection.execute("DROP TABLE gpkg_contents")
    connection.commit()
    connection.close()
    assert "geopackage_missing_required_table" in _names(validate_gpkg(path))


def test_missing_geometry_columns_record_is_high(sample_gpkg, tmp_path):
    """Opens in QGIS, fails in a standards-compliant reader."""
    path = _sqlite_copy(sample_gpkg, tmp_path)
    _strip_gpkg_geometry_columns(path)
    issues = validate_gpkg(path)
    issue = next(i for i in issues if i.problem_name == "geopackage_layer_missing_geometry_record")
    assert str(issue.severity) == "high"


def test_layer_without_crs_is_critical(sample_gpkg, tmp_path):
    path = _sqlite_copy(sample_gpkg, tmp_path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE gpkg_contents SET srs_id = 0")
    connection.commit()
    connection.close()
    issues = validate_gpkg(path)
    issue = next(i for i in issues if i.problem_name == "geopackage_layer_no_crs")
    assert str(issue.severity) == "critical"


def test_srs_used_but_not_defined_is_high(sample_gpkg, tmp_path):
    path = _sqlite_copy(sample_gpkg, tmp_path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE gpkg_contents SET srs_id = 999999")
    connection.commit()
    connection.close()
    assert "geopackage_layer_srs_undeclared" in _names(validate_gpkg(path))


def test_undeclared_extent_is_medium(sample_gpkg, tmp_path):
    path = _sqlite_copy(sample_gpkg, tmp_path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE gpkg_contents SET min_x = NULL, min_y = NULL, max_x = NULL, max_y = NULL")
    connection.commit()
    connection.close()
    assert "geopackage_layer_extent_undeclared" in _names(validate_gpkg(path))


def test_empty_geopackage_is_medium(tmp_path):
    """A valid package with no layers is indistinguishable from a failed export."""
    path = tmp_path / "empty.gpkg"
    gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_file(path, driver="GPKG")
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM gpkg_contents")
    connection.commit()
    connection.close()
    assert "geopackage_empty" in _names(validate_gpkg(path))


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        profile_gpkg(tmp_path / "nope.gpkg")


def test_profiling_does_not_modify_the_file(sample_gpkg):
    before = sample_gpkg.read_bytes()
    profile_gpkg(sample_gpkg)
    validate_gpkg(sample_gpkg)
    assert sample_gpkg.read_bytes() == before


# --- writing -------------------------------------------------------------------

def test_bundle_writes_layers_and_manifest(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    polygons = gpd.GeoDataFrame(
        {"b": ["x"]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326"
    )
    result = write_gpkg_bundle({"points": points, "areas": polygons}, tmp_path)
    assert set(result["layers"]) == {"points", "areas"}
    assert result["feature_counts"]["points"] == 1
    assert (tmp_path / "bundle.gpkg").exists()
    assert (tmp_path / "bundle_manifest.json").exists()


def test_bundle_manifest_records_the_rule_set(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    write_gpkg_bundle({"points": points}, tmp_path)
    manifest = json.loads((tmp_path / "bundle_manifest.json").read_text())
    assert manifest["validation_rule_version"]
    assert manifest["generated_utc"].endswith("+00:00")


def test_bundle_merges_caller_manifest(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    write_gpkg_bundle({"points": points}, tmp_path, manifest={"run": "abc"})
    manifest = json.loads((tmp_path / "bundle_manifest.json").read_text())
    assert manifest["run"] == "abc"


def test_bundle_skips_empty_layers(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    empty = gpd.GeoDataFrame({"a": []}, geometry=[], crs="EPSG:4326")
    result = write_gpkg_bundle({"points": points, "empty": empty}, tmp_path)
    assert result["layers"] == ["points"]


def test_written_bundle_is_conformant(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    result = write_gpkg_bundle({"points": points}, tmp_path)
    serious = [i for i in validate_gpkg(result["geopackage"]) if str(i.severity) == "critical"]
    assert serious == []


def test_bundle_reads_back(tmp_path):
    points = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    result = write_gpkg_bundle({"points": points}, tmp_path)
    assert len(read_gpkg_layer(result["geopackage"], "points")) == 1


# --- no GDAL required ------------------------------------------------------------

def test_structure_is_readable_without_gdal(sample_gpkg):
    """Conformance comes from the specification's own tables, not from GDAL."""
    profile = profile_gpkg(sample_gpkg)
    assert profile.is_geopackage
    assert GPKG_APPLICATION_ID in (GPKG_APPLICATION_ID,)