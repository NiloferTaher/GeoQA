"""Tests for the raster adapter.

A small synthetic GeoTIFF is built in-process, so the tests need no imagery and
no network. The fixtures include the two failure modes that produce plausible
wrong answers: bands that cannot be mapped to a wavelength, and digital numbers
with no recorded scale factor.
"""

from __future__ import annotations

import math
import os

import numpy
import pytest

rasterio = pytest.importorskip("rasterio")

# rasterio resolves EPSG codes through the PROJ pointed at by PROJ_LIB /
# PROJ_DATA. A stale PROJ_LIB in the ambient environment (a PostGIS install, for
# example) that has no proj.db makes every CRS operation fail with
# "The EPSG code is unknown", even though rasterio ships its own copy. Point both
# variables at the database rasterio actually bundled, so the tests do not
# depend on whatever happens to be exported.
_RASTERIO_PROJ = os.path.join(os.path.dirname(rasterio.__file__), "proj_data")


if os.path.isfile(os.path.join(_RASTERIO_PROJ, "proj.db")):
    # Set at import time, before any rasterio call. GDAL caches its PROJ
    # context on first use, so a fixture would run too late for tests that
    # execute earlier in the session.
    os.environ["PROJ_DATA"] = _RASTERIO_PROJ
    os.environ["PROJ_LIB"] = _RASTERIO_PROJ

from rasterio.transform import from_origin  # noqa: E402

from geoqa.validations.raster import (  # noqa: E402
    iter_windows,
    profile_raster,
    raster_report,
    raster_to_observations,
    read_window_indices,
    validate_raster,
)


DESCRIPTIONS = ("B2: 490nm Blue", "B3: 560nm Green", "B4: 665nm Red", "B8: 842nm NIR", "B11: 1609nm SWIR1")


def _write_scene(path, *, describe: bool, crs: str = "EPSG:32640", bands: int = 5, nodata=-9999.0):
    """Write a small reflectance-like scene.

    Band descriptions cannot be passed at creation time for GTiff; GDAL drops
    them. They are set afterwards in update mode, which is why the fixture is
    two-phase.
    """
    rows = cols = 64
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=bands,
        dtype="float32",
        crs=crs,
        transform=from_origin(400_000, 2_600_000, 10, 10),
        nodata=nodata,
    ) as dst:
        # blue, green, red, nir, swir1 at fixed reflectance values
        for index, value in enumerate((0.05, 0.2, 0.1, 0.4, 0.3)[:bands], start=1):
            dst.write(numpy.full((rows, cols), value, dtype="float32"), index)

    if describe:
        with rasterio.open(path, "r+") as dst:
            for index, text in enumerate(DESCRIPTIONS[:bands], start=1):
                dst.set_band_description(index, text)
    return path


@pytest.fixture(scope="module")
def tif(tmp_path_factory):
    """A 64x64 float GeoTIFF with five named bands and a nodata value."""
    return _write_scene(tmp_path_factory.mktemp("rasters") / "scene.tif", describe=True)


@pytest.fixture(scope="module")
def tif_undescribed(tmp_path_factory):
    """A scene with no band metadata, as many standalone products ship."""
    return _write_scene(
        tmp_path_factory.mktemp("rasters") / "plain.tif", describe=False
    )


@pytest.fixture(scope="module")
def geotiff_geographic(tmp_path_factory):
    path = tmp_path_factory.mktemp("rasters") / "geo.tif"
    data = numpy.full((16, 16), 0.5, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=16, width=16, count=1,
        dtype="float32", crs="EPSG:4326", transform=from_origin(55, 23, 0.001, 0.001),
    ) as dst:
        dst.write(data, 1)
    return path


def _names(issues):
    return [i.problem_name for i in issues]


# --- profiling -----------------------------------------------------------

def test_profile_reads_shape_and_bands(tif):
    profile = profile_raster(tif)
    assert (profile.height, profile.width) == (64, 64)
    assert profile.count == 5


def test_profile_maps_bands_by_description(tif):
    profile = profile_raster(tif)
    for role in ("blue", "green", "red", "nir", "swir1"):
        assert role in profile.band_names


def test_profile_reports_crs_and_nodata(tif):
    profile = profile_raster(tif)
    assert profile.crs is not None
    assert profile.nodata == -9999.0
    assert profile.is_geographic_crs is False


def test_profile_reports_geographic_crs(geotiff_geographic):
    assert profile_raster(geotiff_geographic).is_geographic_crs is True


def test_profile_reads_wavelengths(tif):
    profile = profile_raster(tif)
    assert 842 in [w for w in profile.band_wavelengths if w]


# --- indices --------------------------------------------------------------

def test_ndvi_computed_from_the_right_bands(tif):
    """NIR 0.4 and red 0.1 give (0.4-0.1)/(0.4+0.1) = 0.6."""
    result = read_window_indices(tif, indices=("ndvi",))
    value = float(numpy.nanmedian(result["indices"]["ndvi"]))
    assert value == pytest.approx(0.6, abs=1e-6)


def test_ndwi_computed(tif):
    """Green 0.2, NIR 0.4 -> (0.2-0.4)/(0.2+0.4) = -1/3."""
    result = read_window_indices(tif, indices=("ndwi",))
    assert float(numpy.nanmedian(result["indices"]["ndwi"])) == pytest.approx(-1 / 3, abs=1e-6)


def test_ndmi_computed(tif):
    """NIR 0.4, SWIR1 0.3 -> 0.1/0.7."""
    result = read_window_indices(tif, indices=("ndmi",))
    assert float(numpy.nanmedian(result["indices"]["ndmi"])) == pytest.approx(1 / 7, abs=1e-6)


def test_all_three_indices_together(tif):
    result = read_window_indices(tif, indices=("ndvi", "ndwi", "ndmi"))
    assert set(result["indices"]) == {"ndvi", "ndwi", "ndmi"}


def test_valid_pixels_counted(tif):
    result = read_window_indices(tif, indices=("ndvi",))
    assert result["valid_pixels"]["ndvi"] == 64 * 64


def test_unknown_index_is_rejected(tif):
    with pytest.raises(ValueError, match="Unsupported indices"):
        read_window_indices(tif, indices=("ndmi2",))


def test_missing_band_raises_rather_than_guessing(geotiff_geographic):
    """A single-band file cannot support NDVI and must say so."""
    with pytest.raises(ValueError, match="does not provide bands"):
        read_window_indices(geotiff_geographic, indices=("ndvi",))


def test_window_reads_a_subset(tif):
    result = read_window_indices(tif, indices=("ndvi",), window=(0, 0, 16, 16))
    assert result["valid_pixels"]["ndvi"] == 16 * 16
    assert result["window"] == (0, 0, 16, 16)


def test_explicit_band_map_is_honoured(tif):
    result = read_window_indices(
        tif, indices=("ndvi",), band_map={"nir": 4, "red": 3}
    )
    assert result["band_map"] == {"nir": 4, "red": 3}


# --- scaling ---------------------------------------------------------------

def test_scale_factor_is_reported_when_absent(tif):
    """Reflectance floats need no scale, so none should be claimed."""
    assert profile_raster(tif).scale_factor is None
    result = read_window_indices(tif, indices=("ndvi",))
    assert result["scale_applied"] is False


# --- windows ---------------------------------------------------------------

def test_windows_cover_the_whole_raster(tif):
    windows = list(iter_windows(tif, window_size=32, overlap=8))
    assert windows
    covered = {(w[0], w[1]) for w in windows}
    assert (0, 0) in covered


def test_windows_overlap(tif):
    """Overlap matters: a defect on a seam would otherwise be missed."""
    windows = list(iter_windows(tif, window_size=32, overlap=16))
    starts = sorted({w[0] for w in windows})
    assert len(starts) > 1
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(gap < 32 for gap in gaps), "windows must overlap, not tile edge to edge"


def test_single_window_for_a_small_raster(geotiff_geographic):
    windows = list(iter_windows(geotiff_geographic, window_size=512))
    assert len(windows) == 1


# --- bridge to the tabular validators ---------------------------------------

def test_observations_are_in_the_validator_shape(tif):
    frame = raster_to_observations(tif, window=(0, 0, 32, 32))
    assert set(frame.columns) >= {"feature_id", "ndvi", "valid_fraction"}
    assert not frame.empty


def test_observations_feed_the_existing_spectral_validator(tif):
    from geoqa.validations.spectral import validate_spectral_indices

    frame = raster_to_observations(tif, window=(0, 0, 32, 32))
    issues = validate_spectral_indices(frame, ndvi_col="ndvi", ndwi_col=None, ndmi_col=None)
    assert isinstance(issues, list)


def test_low_valid_fraction_windows_are_dropped(tif):
    frame = raster_to_observations(tif, window=(0, 0, 32, 32), min_valid_fraction=2.0)
    assert frame.empty


# --- validation -------------------------------------------------------------

def test_clean_raster_has_no_high_issues(tif):
    serious = [i for i in validate_raster(tif) if str(i.severity) == "high"]
    assert serious == []


def test_single_band_raster_is_reported(tif):
    assert "raster_insufficient_bands" in _names(validate_raster(tif, needed_bands=("blue", "green", "red", "nir", "swir1", "swir2")))


def test_geographic_crs_is_flagged(geotiff_geographic):
    assert "raster_geographic_crs" in _names(validate_raster(geotiff_geographic))


def test_report_includes_profile_and_issues(tif):
    report = raster_report(tif)
    assert report["profile"]["count"] == 5
    assert isinstance(report["issues"], list)


# --- band mapping must not be guessed ---------------------------------------

def test_undescribed_raster_is_flagged_not_guessed(tif_undescribed):
    """No band metadata means no indices, not index 3 as red."""
    profile = profile_raster(tif_undescribed)
    assert "red" not in profile.band_names
    assert set(profile.unmapped_needed_bands) >= {"blue", "green", "red", "nir"}
    assert "raster_band_unmapped" in _names(validate_raster(tif_undescribed))


def test_undescribed_raster_refuses_to_compute_ndvi(tif_undescribed):
    with pytest.raises(ValueError, match="does not provide bands"):
        read_window_indices(tif_undescribed, indices=("ndvi",))


def test_undescribed_raster_works_with_an_explicit_band_map(tif_undescribed):
    """The user knows the layout; GeoQA should use it rather than refuse."""
    result = read_window_indices(
        tif_undescribed, indices=("ndvi",), band_map={"nir": 4, "red": 3}
    )
    assert float(numpy.nanmedian(result["indices"]["ndvi"])) == pytest.approx(0.6, abs=1e-6)


def test_missing_file_raises():
    with pytest.raises(Exception):
        profile_raster("does_not_exist.tif")