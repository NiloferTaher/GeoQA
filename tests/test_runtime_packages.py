"""Runtime tests for the package, tabular, media, governance, axis-order,
credential and clip dataset types.

Each adapter must be a clean no-op when its required context is absent. A
runtime that invents a finding from a missing argument is worse than one that
finds nothing.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from geoqa.validation_runtime import execute_validation_plan


def _names(issues):
    return [i.problem_name for i in issues]


def _run(dataset_type, context, layer=None):
    return execute_validation_plan(
        layer if layer is not None else gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326"),
        dataset_type,
        return_result=True,
        **context,
    )


@pytest.fixture
def shapefile_zip(tmp_path):
    path = tmp_path / "data.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("roads.shp", b"\x00\x00\x27\x0a" + b"\x00" * 64)
        archive.writestr("readme.txt", b"hello")
    return path


@pytest.fixture
def travel_zip(tmp_path):
    path = tmp_path / "evil.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../../escape.txt", b"x")
    return path


@pytest.fixture
def account_csv(tmp_path):
    path = tmp_path / "accounts.csv"
    path.write_text("account_no,region\n007123,north\n007124,south\n", encoding="utf-8")
    return path


@pytest.fixture
def secret_file(tmp_path):
    path = tmp_path / "config.py"
    path.write_text('aws_key = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    return path


@pytest.fixture
def licensed_metadata():
    return {
        "title": "Boundaries",
        "abstract": "Service areas.",
        "resource_type": "dataset",
        "unique_identifier": "urn:example:1",
        "topic_category": ["boundaries"],
        "keyword": ["b"],
        "geographic_extent": "0,0,1,1",
        "temporal_reference": "2026-01-01",
        "lineage": "Digitised.",
        "conformity": "Checked.",
        "conditions_for_access_and_use": "CC BY 4.0",
        "limitations_on_public_access": "None.",
        "responsible_organisation": "Example unit",
        "metadata_point_of_contact": "gis@example.org",
        "metadata_date": "2026-09-01",
        "metadata_language": "en",
    }


@pytest.fixture
def sample_gpkg(tmp_path):
    path = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326").to_file(
        path, layer="pts", driver="GPKG"
    )
    return path


# --- archive ---------------------------------------------------------------

def test_archive_type_finds_traversal(travel_zip):
    issues = _run("archive", {"archive_path": str(travel_zip)}).issues
    assert "archive_path_traversal" in _names(issues)


def test_archive_type_reports_incomplete_shapefile(shapefile_zip):
    issues = _run("archive", {"archive_path": str(shapefile_zip)}).issues
    assert "archive_incomplete_shapefile" in _names(issues)


def test_archive_without_path_is_a_no_op():
    assert _run("archive", {}).issues == []


def test_archive_does_not_write_anything(shapefile_zip):
    before = shapefile_zip.read_bytes()
    _run("archive", {"archive_path": str(shapefile_zip)})
    assert shapefile_zip.read_bytes() == before


# --- tabular ---------------------------------------------------------------

def test_tabular_type_finds_leading_zero(account_csv):
    issues = _run("tabular", {"table_path": str(account_csv)}).issues
    assert "tabular_identifier_leading_zero" in _names(issues)


def test_tabular_accepts_a_path_as_the_layer(account_csv):
    result = execute_validation_plan(
        str(account_csv), "tabular", return_result=True
    )
    assert "tabular_identifier_leading_zero" in _names(result.issues)


def test_tabular_without_path_is_a_no_op():
    assert _run("tabular", {}).issues == []


def test_tabular_missing_key_is_reported(account_csv):
    issues = _run("tabular", {"table_path": str(account_csv), "key_column": "id",
                              "require_key": True}).issues
    assert "tabular_missing_key" in _names(issues)


# --- geopackage ------------------------------------------------------------

def test_geopackage_type_accepts_a_conformant_file(sample_gpkg):
    issues = _run("geopackage", {"geopackage_path": str(sample_gpkg)}).issues
    assert [i for i in issues if str(i.severity) == "critical"] == []


def test_geopackage_without_path_is_a_no_op():
    assert _run("geopackage", {}).issues == []


# --- governance ------------------------------------------------------------

def test_governance_type_reports_missing_licence(licensed_metadata):
    metadata = dict(licensed_metadata)
    metadata.pop("conditions_for_access_and_use")
    issues = _run("metadata_governance", {"metadata": metadata}).issues
    assert "governance_licence_not_declared" in _names(issues)


def test_governance_type_accepts_a_mapping_as_the_layer(licensed_metadata):
    result = execute_validation_plan(
        licensed_metadata, "metadata_governance", return_result=True
    )
    assert [i for i in result.issues if str(i.severity) == "high"] == []


def test_governance_without_metadata_is_a_no_op():
    assert _run("metadata_governance", {}).issues == []


# --- axis order -------------------------------------------------------------

def test_axis_order_type_detects_a_swap():
    issues = _run(
        "axis_order",
        {"coordinates": {"longitude": [58.2], "latitude": [121.5]},
         "declared_crs": "OGC:CRS84"},
    ).issues
    assert "coordinate_axis_order_swapped" in _names(issues)


def test_axis_order_without_coordinates_is_a_no_op():
    assert _run("axis_order", {}).issues == []


# --- credentials -------------------------------------------------------------

def test_credentials_type_finds_a_literal(secret_file):
    issues = _run("credentials", {"scan_path": str(secret_file)}).issues
    assert _names(issues) == ["hardcoded_credential"]


def test_credentials_without_a_path_is_a_no_op():
    assert _run("credentials", {}).issues == []


def test_credentials_type_exempts_environment_references(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text('password = os.environ["PW"]\n', encoding="utf-8")
    assert _run("credentials", {"scan_path": str(path)}).issues == []


# --- clip ---------------------------------------------------------------------

def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _poly_layer(geometries, ids):
    return gpd.GeoDataFrame({"id": ids}, geometry=geometries, crs="EPSG:32640")


def test_clip_type_reports_a_halved_feature():
    source = _poly_layer([_box(0, 0, 10, 10)], ["p"])
    clipped = _poly_layer([_box(0, 0, 5, 10)], ["p_half"])
    issues = _run("clip", {"source_layer": source}, layer=clipped).issues
    assert "clip_feature_half_area" in _names(issues)


def test_clip_type_reports_an_unresolved_assignment():
    boundary = _box(-100, -100, 5, 100)
    layer = _poly_layer([_box(0, 0, 10, 10)], ["p"])
    issues = _run(
        "clip", {"boundary": boundary, "assignment_threshold": None}, layer=layer
    ).issues
    assert "clip_assignment_unresolved" in _names(issues)


def test_clip_without_a_boundary_or_source_is_a_no_op():
    assert _run("clip", {}).issues == []


# --- workbook media ------------------------------------------------------------

@pytest.fixture
def workbook_with_images(tmp_path):
    from PIL import Image as PILImage
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage

    book = Workbook()
    worksheet = book.active
    worksheet.append(("ref", "note"))
    worksheet.append(("R1", "ok"))
    worksheet.append(("R2", "ok"))
    buffer = io.BytesIO()
    PILImage.new("RGB", (30, 30), (10, 10, 10)).save(buffer, format="PNG")
    buffer.seek(0)
    worksheet.add_image(XLImage(buffer), anchor="A2")
    path = tmp_path / "book.xlsx"
    book.save(path)
    return path


def test_workbook_media_type_finds_a_small_attachment(workbook_with_images):
    issues = _run("workbook_media", {"table_path": str(workbook_with_images)}).issues
    assert "workbook_media_below_legibility_threshold" in _names(issues)


def test_workbook_media_type_accepts_a_path_as_the_layer(workbook_with_images):
    result = execute_validation_plan(
        str(workbook_with_images), "workbook_media", return_result=True
    )
    assert result.issues


def test_workbook_media_without_a_path_is_a_no_op():
    assert _run("workbook_media", {}).issues == []


# --- every new type is reachable -----------------------------------------------

@pytest.mark.parametrize(
    "dataset_type",
    [
        "archive", "tabular", "workbook_media", "geopackage",
        "metadata_governance", "axis_order", "credentials", "clip",
    ],
)
def test_dataset_type_is_registered(dataset_type):
    assert _run(dataset_type, {}).partial_result is False


def test_governance_key_still_runs_metric_constants():
    """The metadata module must not have displaced the metric-constant checks."""
    result = _run(
        "governance",
        {"metric_source": "index = (a * 0.75 + b) / c", "constant_declarations": {}},
    )
    assert any(i.problem_name == "unlabelled_physical_constant" for i in result.issues)