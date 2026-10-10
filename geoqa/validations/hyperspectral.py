"""HDF5 hyperspectral products: HDF-EOS swaths such as EMIT, and generic groups.

Why a separate reader
---------------------
The GeoTIFF reader stops at GeoTIFF. Delivered hyperspectral imagery is often
not GeoTIFF at all: NASA EMIT ships HDF5 in the HDF-EOS swath layout, where the
cube sits under a three-level path, the band axis leads the shape, and the
wavelengths live in a dataset attribute rather than in any TIFF tag. Reading one
with the other reader is not a matter of tolerance; it fails outright.

The case this was built against
-------------------------------
EMIT surface reflectance: ``HDFEOS/SWATHS/HYP/Data Fields/surface_reflectance``
at shape ``(426, 664, 607)``, float32, with ``wavelengths`` (nm, 376 onwards)
and ``fwhm`` as attributes, ``_FillValue`` of -9999, and companion
``nodata_pixels``, ``beta_cloud_mask`` and ``beta_cirrus_mask`` uint8 layers.
The file is 1.07 GB and each cube member is 655 MB, so nothing is read whole.

Design constraints
------------------
**Bands are selected by wavelength, never by index.** Index 100 means nothing
across sensors. Every band selection here takes a wavelength interval and
returns the bands that fall inside it, with the wavelengths attached.

**Product level is stated, not inferred.** Surface reflectance and top-of-
atmosphere radiance are both "reflectance-ish" numbers with different meanings
and different valid ranges. A radiance file read as reflectance produces
plausible-looking wrong indices, so the product is read from the dataset name
and attributes and reported.

**Fill values are removed before any statistic.** A -9999 left in a mean moves
it by an amount no one notices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

PROBLEM_NAME = "hyperspectral"

#: Groups that mark an HDF-EOS file, with the swath container beneath them.
HDF_EOS_ROOT = "HDFEOS"
SWATH_CONTAINERS = ("SWATHS", "GRANULES")

#: Dataset names that identify a product level, and what it means.
PRODUCT_LEVELS: dict[str, str] = {
    "surface_reflectance": "surface_reflectance",
    "radiance": "top_of_atmosphere_radiance",
    "toa_radiance": "top_of_atmosphere_radiance",
    "surface_bidirectional_reflectance": "surface_bidirectional_reflectance",
    "surface_emissivity": "surface_emissivity",
}

#: Fill values seen in delivered products.
COMMON_FILL_VALUES = (-9999.0, -999.0, -99999.0)

#: Sentinel names for quality layers, mapped to the flag they carry.
QUALITY_LAYERS: dict[str, str] = {
    "nodata_pixels": "no_data",
    "beta_cloud_mask": "cloud",
    "beta_cirrus_mask": "cirrus",
    "cloud_mask": "cloud",
    "water_mask": "water",
    "snow_mask": "snow",
    "spectral_saturation_flag": "saturation",
}

#: Named reflectance bands by wavelength centre. Sensor-agnostic where possible.
#: Keys are roles; values are the centre in nanometres.
REFLECTANCE_BAND_CENTRES: dict[str, float] = {
    "blue": 490.0,
    "green": 560.0,
    "red": 665.0,
    "red_edge_1": 705.0,
    "red_edge_2": 740.0,
    "nir": 842.0,
    "nir_2": 865.0,
    "swir_1": 1610.0,
    "swir_2": 2200.0,
}

#: Search half-width, in nanometres, when matching a role to a band centre.
DEFAULT_BAND_TOLERANCE_NM = 20.0


def _import_h5py():
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "h5py is required for HDF5 access. Install with: pip install 'geoqa[hyperspectral]'"
        ) from exc
    return h5py


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _attr(dataset: Any, name: str, default: Any = None) -> Any:
    try:
        if name in dataset.attrs:
            return dataset.attrs[name]
    except Exception:
        return default
    return default


def _to_list(value: Any) -> list[float] | None:
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


@dataclass
class BandMapping:
    """One named spectral role resolved to a band index."""

    role: str
    band_index: int
    wavelength_nm: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "band_index": self.band_index,
            "wavelength_nm": round(self.wavelength_nm, 2),
        }


@dataclass
class HyperspectralProfile:
    """What a hyperspectral file contains, read without loading the cube."""

    path: str
    dataset_path: str
    product_level: str
    band_count: int
    height: int
    width: int
    wavelengths_nm: tuple[float, ...] = ()
    fwhm_nm: tuple[float, ...] = ()
    wavelength_units: str | None = None
    fill_value: float | None = None
    #: Quality layers found, by name.
    quality_layers: tuple[str, ...] = ()
    #: Geolocation layer names present.
    geolocation_layers: tuple[str, ...] = ()
    is_hdf_eos: bool = False
    granule_id: str | None = None
    created_at: str | None = None
    #: Set when wavelengths are absent, which is why band selection needs care.
    wavelengths_declared: bool = True
    #: Cube size in bytes, from the shape and dtype.
    cube_bytes: int = 0

    @property
    def megabytes(self) -> float:
        return self.cube_bytes / 1_048_576.0

    @property
    def wavelength_range_nm(self) -> tuple[float, float] | None:
        if not self.wavelengths_nm:
            return None
        return (min(self.wavelengths_nm), max(self.wavelengths_nm))

    @property
    def mean_band_spacing_nm(self) -> float | None:
        if len(self.wavelengths_nm) < 2:
            return None
        ordered = sorted(self.wavelengths_nm)
        gaps = [b - a for a, b in zip(ordered, ordered[1:])]
        return sum(gaps) / len(gaps)

    def band_for(self, role: str, tolerance_nm: float = DEFAULT_BAND_TOLERANCE_NM) -> int | None:
        """Index of the band nearest a named role's centre wavelength."""
        centre = REFLECTANCE_BAND_CENTRES.get(role)
        if centre is None or not self.wavelengths_nm:
            return None
        best_index, best_distance = None, float("inf")
        for index, wavelength in enumerate(self.wavelengths_nm):
            distance = abs(wavelength - centre)
            if distance < best_distance:
                best_index, best_distance = index, distance
        return best_index if best_distance <= tolerance_nm else None

    def resolve_bands(
        self,
        roles: Iterable[str],
        *,
        tolerance_nm: float = DEFAULT_BAND_TOLERANCE_NM,
    ) -> dict[str, BandMapping]:
        """Resolve named roles to band indices by wavelength, not by position."""
        mapping: dict[str, BandMapping] = {}
        for role in roles:
            index = self.band_for(role, tolerance_nm)
            if index is not None:
                mapping[role] = BandMapping(role, index, self.wavelengths_nm[index])
        return mapping

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "dataset": self.dataset_path,
            "product_level": self.product_level,
            "bands": self.band_count,
            "height": self.height,
            "width": self.width,
            "wavelength_units": self.wavelength_units,
            "wavelength_range_nm": list(self.wavelength_range_nm) if self.wavelength_range_nm else None,
            "mean_band_spacing_nm": self.mean_band_spacing_nm,
            "fill_value": self.fill_value,
            "quality_layers": list(self.quality_layers),
            "geolocation_layers": list(self.geolocation_layers),
            "is_hdf_eos": self.is_hdf_eos,
            "granule_id": self.granule_id,
            "cube_megabytes": round(self.megabytes, 1),
            "wavelengths_declared": self.wavelengths_declared,
        }


# --------------------------------------------------------------------------
# Locating the cube
# --------------------------------------------------------------------------

def _product_level_from_name(name: str, attrs: Mapping[str, Any]) -> str:
    lowered = str(name).lower()
    for token, level in PRODUCT_LEVELS.items():
        if token in lowered:
            return level
    unit = str(attrs.get("Unit", attrs.get("units", ""))).lower()
    if "w/m" in unit or "radiance" in unit:
        return "top_of_atmosphere_radiance"
    return "unknown"


def _cube_candidates(handle: Any) -> list[tuple[str, Any]]:
    """Datasets that look like a spectral cube, best first.

    Prefers three-dimensional datasets: the band axis leads, so shape
    ``(bands, rows, columns)`` is the hyperspectral signature and a plain image
    is not.
    """
    found: list[tuple[str, Any]] = []
    names: list[str] = []

    def collect(name: str, obj: Any) -> None:
        if isinstance(obj, type(handle)) or hasattr(obj, "shape") and hasattr(obj, "dtype"):
            names.append(name)

    try:
        handle.visititems(collect)
    except Exception:
        pass

    for name in names:
        try:
            dataset = handle[name]
        except Exception:
            continue
        if len(dataset.shape) == 3:
            found.append((name, dataset))

    def rank(item: tuple[str, Any]) -> tuple[int, int]:
        name = item[0].lower()
        preferred = any(token in name for token in ("surface_reflectance", "radiance"))
        return (0 if preferred else 1, len(item[0]))

    found.sort(key=rank)
    return found


def _product_group_path(dataset_path: str) -> str:
    """The swath-level group a dataset belongs to.

    Quality and geolocation layers sit in *sibling* groups of the data fields,
    for example ``Geolocation Fields`` beside ``Data Fields``. Searching only
    the dataset's own directory would miss every geolocation layer, so this
    climbs to the granule under ``SWATHS`` or ``GRANULES``.
    """
    parts = dataset_path.split("/")
    for container in SWATH_CONTAINERS:
        if container in parts:
            index = parts.index(container)
            return "/".join(parts[: index + 2])
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def profile_hyperspectral(
    path: str | Path,
    *,
    dataset_path: str | None = None,
) -> HyperspectralProfile:
    """Describe an HDF5 hyperspectral file without reading the cube.

    Only attributes, shapes and small metadata datasets are touched, so this is
    safe on a multi-gigabyte file.
    """
    h5py = _import_h5py()
    target = Path(path)

    with h5py.File(target, "r") as handle:
        candidates = _cube_candidates(handle)
        if not candidates and dataset_path is None:
            raise ValueError(
                f"{target.name!r} contains no three-dimensional dataset. A hyperspectral "
                "cube has shape (bands, rows, columns); this file does not have one"
            )
        if dataset_path:
            chosen_path, dataset = dataset_path, handle[dataset_path]
        else:
            chosen_path, dataset = candidates[0]

        wavelengths = _to_list(_attr(dataset, "wavelengths")) or _to_list(
            _attr(dataset, "wavelength_nm")
        )
        fwhm = _to_list(_attr(dataset, "fwhm"))
        fill = _attr(dataset, "_FillValue", None)
        fill_value = None
        if fill is not None:
            try:
                fill_value = float(fill)
            except (TypeError, ValueError):
                fill_value = None

        parent_path = _product_group_path(chosen_path)
        search_root = handle[parent_path] if parent_path in handle else handle

        quality: list[str] = []
        geolocation: list[str] = []
        def collect(group_name: str, obj: Any) -> None:
            key = group_name.rsplit("/", 1)[-1].lower()
            if key in QUALITY_LAYERS and key not in quality:
                quality.append(key)
            if key in {"latitude", "longitude", "time"} and key not in geolocation:
                geolocation.append(key)

        try:
            search_root.visititems(collect)
        except Exception:
            pass

        is_hdf_eos = HDF_EOS_ROOT in handle
        granule_id = None
        created_at = None
        # Granule attributes live on the swath group itself in some products
        # and on the container in others, so both are checked.
        for candidate in (
            handle.get(parent_path) if parent_path else None,
            handle.get(f"{HDF_EOS_ROOT}/GRANULES") if f"{HDF_EOS_ROOT}/GRANULES" in handle else None,
        ):
            if candidate is None:
                continue
            for key in ("granule_id", "strip_id", "identifier"):
                value = _attr(candidate, key)
                if value is not None and granule_id is None:
                    granule_id = str(value)
            if created_at is None:
                created_at = _attr(candidate, "created_at")
        if created_at is None:
            created_at = _attr(handle, "created_at")

        profile = HyperspectralProfile(
            path=str(target),
            dataset_path=chosen_path,
            product_level=_product_level_from_name(chosen_path, dict(dataset.attrs)),
            band_count=int(dataset.shape[0]),
            height=int(dataset.shape[1]),
            width=int(dataset.shape[2]),
            wavelengths_nm=tuple(wavelengths) if wavelengths else (),
            fwhm_nm=tuple(fwhm) if fwhm else (),
            wavelength_units=_attr(dataset, "wavelengths_units", _attr(dataset, "wavelength_units")),
            fill_value=fill_value,
            quality_layers=tuple(quality),
            geolocation_layers=tuple(geolocation),
            is_hdf_eos=is_hdf_eos,
            granule_id=granule_id,
            created_at=str(created_at) if created_at else None,
            wavelengths_declared=bool(wavelengths),
            cube_bytes=int(dataset.size) * int(dataset.dtype.itemsize),
        )
    return profile


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def _valid_mask(dataset: Any, fill_value: float | None) -> Any:
    import numpy

    values = dataset[...]
    if fill_value is not None:
        return values != fill_value
    if numpy.issubdtype(values.dtype, numpy.floating):
        finite = numpy.isfinite(values)
        big = numpy.abs(values) > 1e6
        return finite & ~big
    return numpy.ones(values.shape, dtype=bool)


def read_band_subset(
    path: str | Path,
    *,
    wavelength_range_nm: tuple[float, float] | None = None,
    bands: Sequence[int] | None = None,
    row_slice: slice | None = None,
    column_slice: slice | None = None,
    max_pixels: int = 2_000_000,
    drop_fill: bool = True,
) -> dict[str, Any]:
    """Read a wavelength-bounded window of the cube into memory.

    ``wavelength_range_nm`` is the primary selector, because band index means
    nothing across sensors. The result carries the wavelengths it actually read
    alongside the data, so nothing downstream has to re-derive them.

    ``max_pixels`` bounds the returned array. A full 426-band granule is 655 MB
    and does not belong in a validation run.
    """
    h5py = _import_h5py()
    import numpy

    profile = profile_hyperspectral(path)
    with h5py.File(path, "r") as handle:
        dataset = handle[profile.dataset_path]

        if bands is None:
            if wavelength_range_nm is None:
                indices = list(range(profile.band_count))
            else:
                low, high = wavelength_range_nm
                indices = [
                    index for index, wavelength in enumerate(profile.wavelengths_nm)
                    if low <= wavelength <= high
                ]
        else:
            indices = [int(index) for index in bands]

        rows = row_slice or slice(0, profile.height)
        columns = column_slice or slice(0, profile.width)

        block = numpy.asarray(dataset[indices, rows, columns])

        if drop_fill and profile.fill_value is not None:
            block = numpy.where(block == profile.fill_value, numpy.nan, block)

        valid = numpy.isfinite(block)
        if valid.any():
            per_band = valid.reshape(block.shape[0], -1).sum(axis=1)
        else:
            per_band = numpy.zeros(block.shape[0], dtype=int)

    return {
        "data": block,
        "band_indices": indices,
        "wavelengths_nm": [profile.wavelengths_nm[i] for i in indices] if profile.wavelengths_nm else [],
        "product_level": profile.product_level,
        "fill_value": profile.fill_value,
        "valid_per_band": per_band,
        "shape": list(block.shape),
        "megabytes": block.nbytes / 1_048_576.0,
        "truncated": block.size > max_pixels,
    }


def read_quality_layer(
    path: str | Path,
    layer_name: str,
    *,
    row_slice: slice | None = None,
    column_slice: slice | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Read one quality or geolocation layer by name."""
    h5py = _import_h5py()
    import numpy

    profile = profile_hyperspectral(path)
    product_group = _product_group_path(profile.dataset_path)

    with h5py.File(path, "r") as handle:
        found = None
        root = handle[product_group] if product_group in handle else handle

        def locate(name: str, obj: Any) -> None:
            # ``visititems`` reports names relative to the visited group, so
            # the match has to be re-anchored before it can be opened.
            nonlocal found
            if name.rsplit("/", 1)[-1].lower() == layer_name.lower():
                found = f"{product_group}/{name}" if product_group else name

        try:
            root.visititems(locate)
        except Exception:
            pass
        if found is None or found not in handle:
            def locate_any(name: str, obj: Any) -> None:
                nonlocal found
                if found is None and name.rsplit("/", 1)[-1].lower() == layer_name.lower():
                    found = name

            try:
                handle.visititems(locate_any)
            except Exception:
                pass
        if found is None or found not in handle:
            raise KeyError(
                f"layer {layer_name!r} not found in {Path(path).name}; "
                f"available: {', '.join(profile.quality_layers + profile.geolocation_layers)}"
            )
        dataset = handle[found]
        rows = row_slice or slice(0, min(profile.height, dataset.shape[0]))
        columns = column_slice or slice(0, min(profile.width, dataset.shape[1]))
        data = numpy.asarray(dataset[rows, columns])
        attributes = {str(key): str(value)[:120] for key, value in dataset.attrs.items()}

    return data, {"path": found, "dtype": str(data.dtype), "attributes": attributes}


# --------------------------------------------------------------------------
# Spectral indices over a hyperspectral cube
# --------------------------------------------------------------------------

def hyperspectral_indices(
    subset: Mapping[str, Any],
    *,
    tolerance_nm: float = DEFAULT_BAND_TOLERANCE_NM,
) -> dict[str, Any]:
    """Compute NDVI, NDWI and NDMI from a wavelength-bounded subset.

    Every band is resolved by wavelength. Nothing is indexed positionally,
    because the same index means a different wavelength in every product.
    """
    import numpy

    wavelengths = list(subset.get("wavelengths_nm") or ())
    data = subset["data"]
    if not wavelengths or data.ndim != 3:
        return {"available": False, "reason": "no wavelengths or wrong dimensionality"}

    def band(role: str):
        centre = REFLECTANCE_BAND_CENTRES[role]
        best_index, best_distance = None, float("inf")
        for index, wavelength in enumerate(wavelengths):
            distance = abs(wavelength - centre)
            if distance < best_distance:
                best_index, best_distance = index, distance
        if best_distance > tolerance_nm:
            return None
        return data[best_index].astype("float64")

    nir = band("nir")
    red = band("red")
    green = band("green")
    swir1 = band("swir_1")

    result: dict[str, Any] = {
        "available": True,
        "product_level": subset.get("product_level"),
        "bands_used": {},
    }
    for name, value in (("nir", nir), ("red", red), ("green", green), ("swir_1", swir1)):
        if value is not None:
            role = name
            result["bands_used"][role] = round(
                min(wavelengths, key=lambda w: abs(w - REFLECTANCE_BAND_CENTRES[name])), 2
            )

    def ratio(numerator, denominator):
        with numpy.errstate(invalid="ignore", divide="ignore"):
            return numerator / denominator

    if nir is not None and red is not None:
        result["ndvi"] = ratio(nir - red, nir + red)
    if green is not None and nir is not None:
        result["ndwi"] = ratio(green - nir, green + nir)
    if swir1 is not None and nir is not None:
        result["ndmi"] = ratio(nir - swir1, nir + swir1)

    for key in ("ndvi", "ndwi", "ndmi"):
        values = result.get(key)
        if values is None:
            continue
        finite = numpy.isfinite(values)
        if not finite.any():
            result[f"{key}_valid_fraction"] = 0.0
            continue
        result[f"{key}_valid_fraction"] = round(float(finite.mean()), 6)
        result[f"{key}_min"] = float(numpy.nanmin(values))
        result[f"{key}_max"] = float(numpy.nanmax(values))
        result[f"{key}_mean"] = float(numpy.nanmean(values))

    return result


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_hyperspectral(
    path: str | Path,
    *,
    dataset_path: str | None = None,
    expected_product_level: str | None = None,
    require_quality_layers: bool = True,
    max_rows: int | None = 128,
) -> list[Any]:
    """Report structural conditions in a hyperspectral product.

    Conditions emitted
    ------------------
    ``hyperspectral_wavelengths_undeclared``
        The cube carries no wavelength attribute. Critical: without it, no band
        can be identified and any index computed from this file is positional
        guesswork.
    ``hyperspectral_product_level_unknown``
        The product level could not be established from the dataset name or
        attributes. High: surface reflectance and top-of-atmosphere radiance
        have different valid ranges.
    ``hyperspectral_product_level_mismatch``
        The file is a different product level from the one expected. Critical,
        because the indices are computed the same way and mean different things.
    ``hyperspectral_fill_value_undeclared``
        No fill value, so instrument no-data will enter any statistic.
    ``hyperspectral_quality_layers_absent``
        No quality or cloud mask accompanies the cube, so unusable pixels cannot
        be excluded.
    ``hyperspectral_band_count_sparse``
        Fewer than three bands. Any spectral index needs at least the pair.
    ``hyperspectral_geolocation_absent``
        No latitude and longitude layer, so pixels cannot be located.
    ``hyperspectral_nodata_fraction_high``
        A large share of the sampled window is no-data, which usually means the
        swath boundary or a sensor dropout rather than real observations.
    """
    profile = profile_hyperspectral(path, dataset_path=dataset_path)
    issues: list[Any] = []

    if not profile.wavelengths_declared:
        issues.append(
            _issue(
                "hyperspectral_wavelengths_undeclared", "critical",
                f"{Path(profile.path).name!r} carries no wavelength attribute on "
                f"{profile.dataset_path}. Band index alone cannot identify a band across "
                "products, so any index computed from this file would be positional guesswork",
                profile.as_dict(),
            )
        )

    if profile.product_level == "unknown":
        issues.append(
            _issue(
                "hyperspectral_product_level_unknown", "high",
                f"Could not establish whether {profile.dataset_path} is surface reflectance "
                "or top-of-atmosphere radiance. The two have different valid ranges, so "
                "mixing them silently produces plausible wrong indices",
                profile.as_dict(),
            )
        )
    elif expected_product_level and profile.product_level != expected_product_level:
        issues.append(
            _issue(
                "hyperspectral_product_level_mismatch", "critical",
                f"Expected {expected_product_level} but this file is "
                f"{profile.product_level}. Radiance is not a small scale difference from "
                "reflectance; the indices would be computed identically and mean "
                "something else",
                {**profile.as_dict(), "expected": expected_product_level},
            )
        )

    if profile.fill_value is None:
        issues.append(
            _issue(
                "hyperspectral_fill_value_undeclared", "high",
                "The cube declares no _FillValue. Instrument no-data such as -9999 is an "
                "ordinary number and will enter any mean or index without complaint",
                profile.as_dict(),
            )
        )

    if require_quality_layers and not profile.quality_layers:
        issues.append(
            _issue(
                "hyperspectral_quality_layers_absent", "high",
                "No quality, cloud or no-data mask accompanies the cube, so unusable "
                "pixels cannot be excluded from an index",
                profile.as_dict(),
            )
        )

    if profile.band_count < 3:
        issues.append(
            _issue(
                "hyperspectral_band_count_sparse", "high",
                f"The cube has {profile.band_count} band(s). A spectral index needs at "
                "least a numerator and a denominator band",
                profile.as_dict(),
            )
        )

    has_geo = {"latitude", "longitude"} <= set(profile.geolocation_layers)
    if not has_geo:
        issues.append(
            _issue(
                "hyperspectral_geolocation_absent", "high",
                "No latitude and longitude layer was found, so a pixel cannot be located "
                "on the ground and the swath cannot be joined to any vector layer",
                profile.as_dict(),
            )
        )

    if max_rows and profile.fill_value is not None:
        try:
            window = read_band_subset(
                path,
                bands=(0,),
                row_slice=slice(0, min(max_rows, profile.height)),
                column_slice=slice(0, min(max_rows, profile.width)),
                drop_fill=True,
            )
            valid = window["valid_per_band"][0]
            total = window["shape"][1] * window["shape"][2]
            fraction = float(valid) / total if total else 0.0
            if fraction < 0.5:
                issues.append(
                    _issue(
                        "hyperspectral_nodata_fraction_high", "medium",
                        f"Only {fraction:.0%} of the sampled corner is valid data. A high "
                        "no-data share usually means the swath boundary or a sensor "
                        "dropout rather than real observations",
                        {"valid_fraction": round(fraction, 4), "sampled": total},
                    )
                )
        except Exception:
            # A window that cannot be read is not evidence about no-data share.
            pass

    return issues


__all__ = [
    "COMMON_FILL_VALUES",
    "DEFAULT_BAND_TOLERANCE_NM",
    "HDF_EOS_ROOT",
    "PRODUCT_LEVELS",
    "PROBLEM_NAME",
    "QUALITY_LAYERS",
    "REFLECTANCE_BAND_CENTRES",
    "SWATH_CONTAINERS",
    "BandMapping",
    "HyperspectralProfile",
    "hyperspectral_indices",
    "profile_hyperspectral",
    "read_band_subset",
    "read_quality_layer",
    "validate_hyperspectral",
]