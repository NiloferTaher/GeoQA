"""Tests for the QGIS integration layer.

The property worth protecting: the bundle is self-contained and loadable without
QGIS installed, and the style document is well-formed enough that QGIS applies
it on load rather than ignoring it.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from geoqa.qgis_integration import (
    SEVERITY_COLOURS,
    SEVERITY_ORDER,
    arcgis_field_mapping,
    issues_to_geodataframe,
    pyqgis_recipe,
    qml_style,
    severity_rank,
    write_layer_bundle,
)
from geoqa.validation_runtime import execute_validation_plan


def _issues():
    layer = gpd.GeoDataFrame(
        {"a": [1, 1, 2]},
        geometry=[Point(0, 0), Point(0.001, 0.001), LineString([(0, 0), (0.01, 0.01)])],
        crs="EPSG:4326",
    )
    return execute_validation_plan(layer, "topology", return_result=True).issues


# --- QML -----------------------------------------------------------------

def test_qml_is_well_formed_xml():
    root = ET.fromstring(qml_style())
    assert root.tag == "qgis"


def test_qml_has_one_range_per_severity():
    root = ET.fromstring(qml_style())
    renderer = root.find("renderer-v2")
    assert renderer is not None
    assert len(renderer.findall("range")) == len(SEVERITY_ORDER)


def test_qml_renderer_classifies_on_the_severity_field():
    root = ET.fromstring(qml_style(field="sev"))
    assert root.find("renderer-v2").get("attr") == "sev"


def test_qml_colours_match_the_severity_map():
    text = qml_style()
    for severity, colour in SEVERITY_COLOURS.items():
        assert colour in text


def test_qml_escapes_a_hostile_layer_name():
    text = qml_style(layer_name="Findings & <report>")
    root = ET.fromstring(text)
    assert root.find("title").text == "Findings & <report>"


def test_qml_carries_labels():
    root = ET.fromstring(qml_style())
    assert root.find("labeling") is not None


# --- issue to layer ---------------------------------------------------------

def test_points_and_geometries_are_split():
    points, other = issues_to_geodataframe(_issues())
    assert set(points.geometry.geom_type) <= {"Point"}
    if not other.empty:
        assert "Point" not in set(other.geometry.geom_type)


def test_null_geometry_rows_are_dropped():
    layer = gpd.GeoDataFrame({"a": [1]}, geometry=[None], crs="EPSG:4326")
    issues = execute_validation_plan(layer, "geometry", return_result=True).issues
    _, other = issues_to_geodataframe(issues)
    assert other.empty


def test_severity_is_ordered_low_to_high():
    points, _ = issues_to_geodataframe(_issues())
    if not points.empty:
        assert list(points["severity"].cat.categories) == [
            s for s in SEVERITY_ORDER if s in set(points["severity"])
        ]


def test_extra_is_flattened_to_json():
    points, _ = issues_to_geodataframe(_issues())
    if not points.empty:
        assert isinstance(points["extra"].iloc[0], str)
        json.loads(points["extra"].iloc[0])


def test_no_issues_gives_empty_frames():
    empty = gpd.GeoDataFrame({"a": []}, geometry=[], crs="EPSG:4326")
    points, other = issues_to_geodataframe([])
    assert points.empty and other.empty


# --- bundle -----------------------------------------------------------------

def test_bundle_writes_geopackage_style_and_manifest(tmp_path):
    result = write_layer_bundle(_issues(), tmp_path)
    assert (tmp_path / "geoqa_findings.gpkg").exists()
    assert (tmp_path / "geoqa_findings.qml").exists()
    assert (tmp_path / "manifest.json").exists()
    assert result["geopackage"].endswith(".gpkg")


def test_manifest_records_the_run(tmp_path):
    write_layer_bundle(_issues(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["issue_count"] >= 1
    assert manifest["validation_rule_version"]
    assert manifest["generated_utc"].endswith("+00:00")


def test_manifest_records_severity_counts(tmp_path):
    write_layer_bundle(_issues(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert sum(manifest["severity_counts"].values()) == manifest["issue_count"]


def test_manifest_carries_supplied_metadata(tmp_path):
    write_layer_bundle(_issues(), tmp_path, manifest={"input": "network.gpkg"})
    assert json.loads((tmp_path / "manifest.json").read_text())["input"] == "network.gpkg"


def test_empty_run_still_writes_a_bundle(tmp_path):
    """A run that found nothing must leave evidence, not silence."""
    result = write_layer_bundle([], tmp_path)
    assert (tmp_path / "geoqa_findings.gpkg").exists()
    assert result["issue_count"] == 0


def test_bundle_geopackage_reopens(tmp_path):
    write_layer_bundle(_issues(), tmp_path)
    reopened = gpd.read_file(tmp_path / "geoqa_findings.gpkg", layer="findings_points")
    assert "severity" in reopened.columns


def test_bundle_creates_the_directory(tmp_path):
    target = tmp_path / "nested" / "run01"
    write_layer_bundle(_issues(), target)
    assert target.exists()


def test_style_can_be_suppressed(tmp_path):
    result = write_layer_bundle(_issues(), tmp_path, write_style=False)
    assert result["style"] is None
    assert not (tmp_path / "geoqa_findings.qml").exists()


# --- PyQGIS recipe ----------------------------------------------------------

def test_recipe_is_valid_python():
    recipe = pyqgis_recipe(
        input_path="C:/data/network.gpkg",
        dataset_type="water_network",
        output_directory="C:/out",
    )
    compile(recipe, "recipe", "exec")


def test_recipe_carries_the_paths():
    recipe = pyqgis_recipe(
        input_path="C:/data/network.gpkg",
        dataset_type="water_network",
        output_directory="C:/out",
    )
    assert "C:/data/network.gpkg" in recipe
    assert "water_network" in recipe


def test_recipe_embeds_context_as_json():
    recipe = pyqgis_recipe(
        input_path="a.gpkg",
        dataset_type="geometry",
        output_directory="o",
        context={"expected_crs": "EPSG:32640"},
    )
    assert "EPSG:32640" in recipe
    compile(recipe, "recipe", "exec")


# --- ArcGIS -----------------------------------------------------------------

def test_arcgis_mapping_covers_every_severity():
    mapping = arcgis_field_mapping()
    assert set(mapping["severity_rank"]) == set(SEVERITY_ORDER)


def test_arcgis_rank_one_is_most_severe():
    assert severity_rank(())[SEVERITY_ORDER[0]] == 1


def test_arcgis_mapping_has_the_columns_a_renderer_needs():
    fields = arcgis_field_mapping()["attribute_map"]
    assert "severity_rank" in fields
    assert "severity" in fields
    assert fields["severity"].get("domain")