"""Tests for the HDF5 hyperspectral reader.

The behaviour worth protecting: bands are resolved by wavelength, never by
index, and the cube is never read whole. Both matter more than they look —
index 100 is a different wavelength in every product, and the granule these were
built against holds a 655 MB cube per variable.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from geoqa.validations.hyperspectral import (  # noqa: E402
    REFLECTANCE_BAND_CENTRES,
    _product_group_path,
    hyperspectral_indices,
    profile_hyperspectral,
    read_band_subset,
    read_quality_layer,
    validate_hyperspectral,
)


DATA_FIELDS = "HDFEOS/SWATHS/HYP/Data Fields"
GEO_FIELDS = "HDFEOS/SWATHS/HYP/Geolocation Fields"


def _emission_centre(center, spacing=5.0):
    return np.arange(center - 5 * spacing, center + 5 * spacing, spacing)


def _write_h5(path, *, name="surface_reflectance", bands=None, rows=8, cols=8,
              wavelengths=None, fill_value=-9999.0, unit="Unitless", with_geo=True,
              with_quality=True):
    """Write a file shaped like an HDF-EOS swath product.

    ``bands`` follows ``wavelengths`` when one is supplied, because a cube whose
    band count disagrees with its wavelength list is not a product any sensor
    would deliver.
    """
    rng = np.random.default_rng(7)
    if wavelengths is None:
        bands = bands or 40
        wavelengths = np.arange(400.0, 400.0 + bands * 5.0, 5.0)
    else:
        wavelengths = np.asarray(wavelengths, dtype="float64")
        bands = bands or len(wavelengths)

    data = rng.uniform(0.05, 0.45, size=(bands, rows, cols)).astype("float32")
    data[0, 0, 0] = fill_value

    with h5py.File(path, "w") as handle:
        group = handle.create_group(f"{DATA_FIELDS.rsplit('/', 1)[0]}/Data Fields")
        dataset = group.create_dataset(name, data=data)
        dataset.attrs["wavelengths"] = wavelengths
        dataset.attrs["wavelengths_units"] = "nm"
        dataset.attrs["Unit"] = unit
        dataset.attrs["_FillValue"] = fill_value

        if with_quality:
            qgroup = handle[f"{DATA_FIELDS.rsplit('/', 1)[0]}/Data Fields"]
            qgroup.create_dataset("nodata_pixels", data=np.zeros((rows, cols), dtype="uint8"))
            qgroup.create_dataset("beta_cloud_mask", data=np.zeros((rows, cols), dtype="uint8"))

        if with_geo:
            ggroup = handle.create_group(f"{DATA_FIELDS.rsplit('/', 1)[0]}/Geolocation Fields")
            ggroup.create_dataset("Latitude", data=np.full((rows, cols), 27.5))
            ggroup.create_dataset("Longitude", data=np.full((rows, cols), 33.6))

        handle[f"{DATA_FIELDS.rsplit('/', 1)[0]}"].attrs["created_at"] = "2026-01-01T00:00:00Z"
    return path


def _names(issues):
    return [i.problem_name for i in issues]


# --- structure --------------------------------------------------------------

def test_profiles_an_eos_swath(tmp_path):
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5"))
    assert profile.is_hdf_eos is True
    assert profile.band_count == 40
    assert profile.height == 8 and profile.width == 8
    assert profile.product_level == "surface_reflectance"


def test_radiance_product_level_is_distinguished(tmp_path):
    """Radiance is not a scale difference from reflectance."""
    profile = profile_hyperspectral(_write_h5(tmp_path / "r.h5", name="radiance"))
    assert profile.product_level == "top_of_atmosphere_radiance"


def test_geolocation_is_found_in_a_sibling_group(tmp_path):
    """Geolocation Fields sits beside Data Fields, not inside it."""
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5"))
    assert "latitude" in profile.geolocation_layers
    assert "longitude" in profile.geolocation_layers


def test_quality_layers_are_found(tmp_path):
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5"))
    assert "nodata_pixels" in profile.quality_layers


def test_product_group_path_climbs_to_the_granule():
    assert _product_group_path(f"{DATA_FIELDS}/surface_reflectance") == "HDFEOS/SWATHS/HYP"


def test_fill_value_is_read(tmp_path):
    assert profile_hyperspectral(_write_h5(tmp_path / "a.h5")).fill_value == -9999.0


def test_wavelength_range_and_spacing(tmp_path):
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5"))
    assert profile.wavelength_range_nm[0] == pytest.approx(400.0)
    assert profile.mean_band_spacing_nm == pytest.approx(5.0)


def test_cube_size_is_known_without_reading(tmp_path):
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5", bands=100, rows=50, cols=50))
    assert profile.megabytes == pytest.approx(100 * 50 * 50 * 4 / 1_048_576)


def test_file_without_a_cube_raises(tmp_path):
    path = tmp_path / "flat.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("image", data=np.zeros((4, 4)))
    with pytest.raises(ValueError, match="three-dimensional"):
        profile_hyperspectral(path)


# --- band selection by wavelength -------------------------------------------

def test_bands_resolved_by_wavelength_not_index(tmp_path):
    profile = profile_hyperspectral(_write_h5(tmp_path / "a.h5", wavelengths=np.arange(400.0, 2500.0, 5.0)))
    mapping = profile.resolve_bands(["blue", "green", "red", "nir"])
    assert mapping["red"].wavelength_nm == pytest.approx(665.0, abs=20.0)
    assert mapping["nir"].wavelength_nm > mapping["red"].wavelength_nm


def test_missing_wavelengths_make_selection_impossible(tmp_path):
    """No wavelengths means no band can be identified, so it is critical."""
    path = tmp_path / "a.h5"
    _write_h5(path)
    with h5py.File(path, "r+") as handle:
        del handle[f"{DATA_FIELDS}/surface_reflectance"].attrs["wavelengths"]

    profile = profile_hyperspectral(path)
    assert profile.wavelengths_declared is False
    assert profile.resolve_bands(["red"]) == {}

    issues = validate_hyperspectral(path)
    finding = next(i for i in issues if i.problem_name == "hyperspectral_wavelengths_undeclared")
    assert str(finding.severity) == "critical"


def test_band_out_of_range_is_not_matched(tmp_path):
    """A visible-only file cannot provide NIR, and must not pretend to."""
    path = _write_h5(tmp_path / "vis.h5", wavelengths=np.arange(400.0, 700.0, 5.0))
    profile = profile_hyperspectral(path)
    assert "nir" not in profile.resolve_bands(["nir", "red"])


def test_subset_reads_only_the_requested_window(tmp_path):
    path = _write_h5(tmp_path / "a.h5", wavelengths=np.arange(400.0, 900.0, 5.0))
    subset = read_band_subset(path, wavelength_range_nm=(600.0, 700.0))
    assert len(subset["band_indices"]) == 21
    assert subset["wavelengths_nm"][0] == pytest.approx(600.0)
    assert subset["wavelengths_nm"][-1] == pytest.approx(700.0)


def test_subset_carries_the_wavelengths_it_read(tmp_path):
    """Downstream must not have to re-derive which band is which."""
    subset = read_band_subset(_write_h5(tmp_path / "a.h5"), wavelength_range_nm=(500.0, 800.0))
    assert subset["wavelengths_nm"]
    assert all(500.0 <= w <= 800.0 for w in subset["wavelengths_nm"])


def test_fill_values_become_nan(tmp_path):
    subset = read_band_subset(_write_h5(tmp_path / "a.h5"), bands=(0,))
    assert np.isnan(subset["data"][0, 0, 0])


def test_fill_can_be_kept(tmp_path):
    subset = read_band_subset(_write_h5(tmp_path / "a.h5"), bands=(0,), drop_fill=False)
    assert subset["data"][0, 0, 0] == -9999.0


def test_valid_count_excludes_fill(tmp_path):
    subset = read_band_subset(_write_h5(tmp_path / "a.h5"), bands=(0,))
    assert int(subset["valid_per_band"][0]) == 8 * 8 - 1


def test_row_and_column_window_limits_the_read(tmp_path):
    subset = read_band_subset(
        _write_h5(tmp_path / "a.h5"), bands=(0, 1),
        row_slice=slice(0, 2), column_slice=slice(0, 3),
    )
    assert subset["shape"] == [2, 2, 3]


# --- quality and geolocation reads -------------------------------------------

def test_read_quality_layer_by_name(tmp_path):
    path = _write_h5(tmp_path / "a.h5")
    data, meta = read_quality_layer(path, "nodata_pixels")
    assert data.shape == (8, 8)
    assert meta["path"].endswith("nodata_pixels")


def test_read_geolocation_layer(tmp_path):
    data, _ = read_quality_layer(_write_h5(tmp_path / "a.h5"), "Latitude")
    assert float(data[0, 0]) == pytest.approx(27.5)


def test_unknown_layer_raises_with_the_available_list(tmp_path):
    with pytest.raises(KeyError, match="nodata_pixels"):
        read_quality_layer(_write_h5(tmp_path / "a.h5"), "does_not_exist")


# --- indices ------------------------------------------------------------------

def test_indices_from_real_bands(tmp_path):
    path = _write_h5(tmp_path / "a.h5", wavelengths=np.arange(400.0, 2500.0, 5.0))
    subset = read_band_subset(path, wavelength_range_nm=(450.0, 2300.0), drop_fill=True)
    result = hyperspectral_indices(subset)
    assert result["available"] is True
    assert set(result["bands_used"]) == {"nir", "red", "green", "swir_1"}
    for key in ("ndvi", "ndwi", "ndmi"):
        assert -1.0 <= result[f"{key}_min"] <= 1.0
        assert -1.0 <= result[f"{key}_max"] <= 1.0


def test_indices_need_wavelengths(tmp_path):
    result = hyperspectral_indices({"data": np.zeros((3, 4, 4)), "wavelengths_nm": []})
    assert result["available"] is False


def test_indices_report_only_bands_the_file_has(tmp_path):
    path = _write_h5(tmp_path / "vis.h5", wavelengths=np.arange(400.0, 700.0, 5.0))
    subset = read_band_subset(path, wavelength_range_nm=(400.0, 700.0))
    result = hyperspectral_indices(subset)
    assert "red" in result["bands_used"]
    assert "swir_1" not in result["bands_used"]
    assert "ndmi" not in result


def test_ndvi_of_equal_bands_is_zero(tmp_path):
    """A sanity check on the arithmetic itself, independent of the file."""
    path = _write_h5(tmp_path / "flat.h5", wavelengths=np.arange(400.0, 2500.0, 5.0))
    subset = read_band_subset(path, wavelength_range_nm=(450.0, 2300.0), drop_fill=True)
    subset["data"] = np.full_like(subset["data"], 0.2)
    result = hyperspectral_indices(subset)
    assert result["ndvi_mean"] == pytest.approx(0.0, abs=1e-9)
    assert result["ndwi_mean"] == pytest.approx(0.0, abs=1e-9)


# --- validation ------------------------------------------------------------------

def test_well_formed_file_is_clean(tmp_path):
    issues = validate_hyperspectral(_write_h5(tmp_path / "a.h5", wavelengths=np.arange(400.0, 2500.0, 5.0)))
    assert issues == []


def test_product_level_mismatch_is_critical(tmp_path):
    path = _write_h5(tmp_path / "r.h5", name="radiance", wavelengths=np.arange(400.0, 2500.0, 5.0))
    issues = validate_hyperspectral(path, expected_product_level="surface_reflectance")
    finding = next(i for i in issues if i.problem_name == "hyperspectral_product_level_mismatch")
    assert str(finding.severity) == "critical"


def test_missing_fill_value_is_high(tmp_path):
    path = _write_h5(tmp_path / "a.h5")
    with h5py.File(path, "r+") as handle:
        del handle[f"{DATA_FIELDS}/surface_reflectance"].attrs["_FillValue"]
    assert "hyperspectral_fill_value_undeclared" in _names(validate_hyperspectral(path))


def test_missing_quality_layers_are_high(tmp_path):
    path = _write_h5(tmp_path / "a.h5", with_quality=False, wavelengths=np.arange(400.0, 2500.0, 5.0))
    assert "hyperspectral_quality_layers_absent" in _names(validate_hyperspectral(path))


def test_missing_geolocation_is_high(tmp_path):
    path = _write_h5(tmp_path / "a.h5", with_geo=False, wavelengths=np.arange(400.0, 2500.0, 5.0))
    assert "hyperspectral_geolocation_absent" in _names(validate_hyperspectral(path))


def test_two_bands_is_reported(tmp_path):
    path = _write_h5(tmp_path / "few.h5", bands=2)
    assert "hyperspectral_band_count_sparse" in _names(validate_hyperspectral(path))


# --- against the real granule -------------------------------------------------------
#
# The granule is ~1 GB and lives outside the repository, so its location comes
# from an environment variable rather than a hardcoded path. A hardcoded one
# would leak a username and a directory layout into a public repository, and
# would fail on every other machine.
#
#   set GEOQA_EMIT_GRANULE=D:\path\to\granule.h5   (Windows)
#   export GEOQA_EMIT_GRANULE=/data/granule.h5     (Linux/macOS)

REAL_GRANULE = os.environ.get("GEOQA_EMIT_GRANULE", "")


def _granule_available() -> bool:
    return bool(REAL_GRANULE) and Path(REAL_GRANULE).exists()


requires_granule = pytest.mark.skipif(
    not _granule_available(),
    reason="set GEOQA_EMIT_GRANULE to a hyperspectral granule to run these",
)


@requires_granule
def test_real_granule_profiles():
    profile = profile_hyperspectral(REAL_GRANULE)
    assert profile.is_hdf_eos is True
    assert profile.product_level == "surface_reflectance"
    assert profile.band_count == 426
    assert profile.fill_value == -9999.0
    low, high = profile.wavelength_range_nm
    assert low == pytest.approx(376.4, abs=1.0)
    assert high == pytest.approx(2500.0, abs=20.0)


@requires_granule
def test_real_granule_resolves_named_bands_by_wavelength():
    mapping = profile_hyperspectral(REAL_GRANULE).resolve_bands(
        ["blue", "green", "red", "nir", "swir_1", "swir_2"]
    )
    assert mapping["red"].wavelength_nm == pytest.approx(665, abs=15)
    assert mapping["nir"].wavelength_nm == pytest.approx(842, abs=15)
    assert mapping["swir_2"].wavelength_nm > 2000


@requires_granule
def test_real_granule_window_read_is_small():
    """90 bands from a 655 MB cube must cost about a megabyte."""
    subset = read_band_subset(
        REAL_GRANULE, wavelength_range_nm=(450.0, 900.0),
        row_slice=slice(0, 64), column_slice=slice(0, 64),
    )
    assert len(subset["band_indices"]) == 90
    assert subset["megabytes"] < 3.0