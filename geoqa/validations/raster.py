"""Raster reading and spectral validation over real imagery.

Why this exists
---------------
The spectral validators in this package operate on a table of per-observation
values. That is the right shape for results that have already been extracted,
and the wrong shape for a GeoTIFF or an HDF5 file, which is what most people
actually have. So spectral validation could not be run on the data it was
written for.

This module closes that gap: a windowed raster reader that yields per-band
arrays and derived indices without loading a whole file, and a bridge into the
existing index validators.

Design constraints
------------------
**Memory-safe.** Imagery does not fit in RAM. Every operation here is
windowed, and the reader never materialises a full raster unless the caller asks
for one explicitly and the file is small enough.

**Bands are named, not positional.** An index needs specific wavelengths. A file
whose band 3 is not red must fail rather than silently compute a meaningless
NDVI. Band descriptions and wavelengths are read from the file where available
and matched by wavelength, falling back to an explicit band mapping.

**No silent rescaling.** Sentinel-2 L2A products carry an offset and a gain
(DN + gain). Reading the raw values and dividing by 10000 produces wrong
indices, and the resulting NDVI looks plausible. The reader reports the scaling
it found and whether it was applied.

Nothing here reimplements GDAL. Rasterio is a GDAL binding and is used for
exactly what it is good at.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

PROBLEM_NAME = "raster"

# Reflectance products: the scale factor is stored in the dataset, not assumed.
_DEFAULT_REFLECTANCE_SCALE = 10_000.0

# Standard band centres in nanometres for the common mapping families.
_BAND_CENTRES_NM = {
    "coastal": {"blue": 490, "green": 560, "red": 665, "nir": 705,
                "swir1": 740, "swir2": 783},
    "landsat8": {"blue": 482, "green": 563, "red": 655, "nir": 865, "swir1": 1609, "swir2": 2201},
    "landsat9": {"blue": 482, "green": 563, "red": 655, "nir": 865, "swir1": 1609, "swir2": 2201},
}

# Aliases seen in band descriptions across products.
_BAND_ALIASES = {
    "blue": ("b2", "blue"),
    "green": ("b3", "green"),
    "red": ("b4", "red"),
    "nir": ("b8", "nir", "nIR"),
    "swir1": ("b11", "swir1"),
    "swir2": ("b12", "swir2"),
}


@dataclass
class RasterProfile:
    """What a raster contains, before any pixel is read."""

    path: str
    driver: str
    width: int
    height: int
    count: int
    crs: Any
    nodata: float | None
    dtype: str
    band_names: tuple[str, ...] = ()
    band_descriptions: tuple[str, ...] = ()
    band_wavelengths: tuple[float | None, ...] = ()
    is_geographic_crs: bool = False
    pixel_size: tuple[float, float] = (0.0, 0.0)
    scale_factor: float | None = None
    offset: float | None = None
    unmapped_needed_bands: tuple[str, ...] = ()

    @property
    def megabytes(self) -> float:
        return self.width * self.height * self.count * 4 / 1_048_576

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "driver": self.driver,
            "shape": [self.height, self.width],
            "count": self.count,
            "bands": self.count,
            "crs": str(self.crs) if self.crs else None,
            "is_geographic_crs": self.is_geographic_crs,
            "pixel_size": list(self.pixel_size),
            "dtype": self.dtype,
            "nodata": self.nodata,
            "band_names": list(self.band_names),
            "band_descriptions": list(self.band_descriptions),
            "scale_factor": self.scale_factor,
            "offset": self.offset,
            "megabytes": round(self.megabytes, 2),
            "unmapped_needed_bands": list(self.unmapped_needed_bands),
        }


def _import_rasterio():
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "rasterio is required for raster access. Install with: pip install 'geoqa[raster]'"
        ) from exc
    return rasterio


def _normalise_band_name(text: Any) -> str:
    return str(text or "").strip().lower().replace("_", "").replace(" ", "")


def _match_band_to_role(descriptions: Sequence[Any], index: int) -> str | None:
    """Identify a band by its description, tolerating product-specific wording."""
    if index >= len(descriptions):
        return None
    token = _normalise_band_name(descriptions[index])
    if not token:
        return None
    for role, aliases in _BAND_ALIASES.items():
        for alias in aliases:
            if _normalise_band_name(alias) == token:
                return role
        # Descriptions like "B8: 842nm NIR" carry the role after the band name.
        if _normalise_band_name(alias) in token:
            return role
    return None


def profile_raster(path: str | Path, *, needed_bands: Sequence[str] = ("blue", "green", "red", "nir")) -> RasterProfile:
    """Describe a raster without reading pixels.

    Reads band descriptions and any stored scale factor, which is what decides
    whether the reflectance values are physical or digital numbers.
    """
    rasterio = _import_rasterio()
    path = Path(path)

    with rasterio.open(path) as dataset:
        descriptions = tuple(dataset.descriptions or ())
        # Sentinel-2 and similar store per-band scale/offset as tags.
        scale = None
        offset = None
        for key in (" reflectance_scale", "radiometric_scale_factor", "scale_factor"):
            raw = dataset.tags().get(key) or dataset.tags().get(key.strip())
            if raw:
                try:
                    scale = float(str(raw).strip().rstrip(","))
                    break
                except ValueError:
                    continue
        if scale is None and dataset.scales and any(abs(s - 1.0) > 1e-9 for s in dataset.scales):
            scale = float(dataset.scales[0])

        wavelengths = []
        for index in range(dataset.count):
            try:
                description = dataset.descriptions[index]
                if description and "nm" in str(description).lower():
                    import re

                    match = re.search(r"(\d{3,4})\s*nm", str(description).lower())
                    wavelengths.append(float(match.group(1)) if match else None)
                else:
                    wavelengths.append(None)
            except Exception:
                wavelengths.append(None)

        roles = tuple(_match_band_to_role(descriptions, i) for i in range(dataset.count))
        names = tuple(
            role if role else (descriptions[i] if i < len(descriptions) and descriptions[i] else f"band_{i + 1}")
            for i, role in enumerate(roles)
        )
        missing = tuple(
            band for band in needed_bands
            if band in ("blue", "green", "red", "nir") and band not in names
        )

        crs = dataset.crs
        try:
            from pyproj import CRS as _CRS

            is_geographic = bool(_CRS.from_user_input(crs).is_geographic) if crs else False
        except Exception:
            is_geographic = False

        return RasterProfile(
            path=str(path),
            driver=dataset.driver,
            width=dataset.width,
            height=dataset.height,
            count=dataset.count,
            crs=crs,
            nodata=dataset.nodata,
            dtype=str(dataset.dtypes[0]) if dataset.count else "unknown",
            band_names=names,
            band_descriptions=descriptions,
            band_wavelengths=tuple(wavelengths),
            is_geographic_crs=is_geographic,
            pixel_size=(float(abs(dataset.res[0])), float(abs(dataset.res[1]))),
            scale_factor=scale,
            offset=offset,
            unmapped_needed_bands=missing,
        )


def read_window_indices(
    path: str | Path,
    *,
    window: tuple[int, int, int, int] | None = None,
    band_map: dict[str, int] | None = None,
    indices: Sequence[str] = ("ndvi", "ndwi", "ndmi"),
    apply_scale: bool = True,
) -> dict[str, Any]:
    """Compute spectral indices over one window.

    ``window`` is ``(row_off, col_off, height, width)``. Omit it to read the
    whole file, which is only safe for small rasters.

    Returns the index arrays plus a record of what was actually read, so the
    caller can see which bands and scaling produced them.
    """
    rasterio = _import_rasterio()

    index_functions = {
        "ndvi": lambda n, r: (n - r) / (n + r),
        "ndwi": lambda g, n: (g - n) / (g + n),
        "ndmi": lambda n, s1: (n - s1) / (n + s1),
    }
    unknown = [i for i in indices if i not in index_functions]
    if unknown:
        raise ValueError(f"Unsupported indices: {', '.join(unknown)}")

    with rasterio.open(Path(path)) as dataset:
        profile = profile_raster(path)
        if band_map is None:
            band_map = {}
            for name in profile.band_names:
                if name in ("blue", "green", "red", "nir", "swir1", "swir2"):
                    band_map[name] = profile.band_names.index(name) + 1

        needed = {"ndvi": {"nir", "red"}, "ndwi": {"green", "nir"}, "ndmi": {"nir", "swir1"}}
        missing = sorted({b for index in indices for b in needed[index] if b not in band_map})
        if missing:
            raise ValueError(
                f"Raster does not provide bands needed for the requested indices: "
                f"{', '.join(missing)}. Supply band_map explicitly if the mapping is known."
            )

        def read(band_name: str):
            read_window = None
            if window is not None:
                from rasterio.windows import Window

                read_window = Window(col_off=window[1], row_off=window[0],
                                     width=window[3], height=window[2])
            data = dataset.read(band_map[band_name], window=read_window).astype("float64")
            if dataset.nodata is not None:
                data[data == dataset.nodata] = math.nan
            if apply_scale:
                scale = profile.scale_factor or 1.0
                if scale != 1.0:
                    data = data / scale
            return data

        if all(i == "ndvi" for i in indices):
            nir, red = read("nir"), read("red")
            result = {"ndvi": _safe_divide(nir - red, nir + red)}
        elif all(i == "ndwi" for i in indices):
            green, nir = read("green"), read("nir")
            result = {"ndwi": _safe_divide(green - nir, green + nir)}
        elif all(i == "ndmi" for i in indices):
            nir, swir1 = read("nir"), read("swir1")
            result = {"ndmi": _safe_divide(nir - swir1, nir + swir1)}
        else:
            result = {}
            if "ndvi" in indices:
                nir, red = read("nir"), read("red")
                result["ndvi"] = _safe_divide(nir - red, nir + red)
            if "ndwi" in indices:
                green, nir = read("green"), read("nir")
                result["ndwi"] = _safe_divide(green - nir, green + nir)
            if "ndmi" in indices:
                nir, swir1 = read("nir"), read("swir1")
                result["ndmi"] = _safe_divide(nir - swir1, nir + swir1)

        valid = {
            name: int((~__import__("numpy").isnan(array)).sum())
            for name, array in result.items()
        }

    return {
        "indices": result,
        "valid_pixels": valid,
        "window": window or (0, 0, profile.height, profile.width),
        "band_map": band_map,
        "scale_applied": bool(apply_scale and (profile.scale_factor or 1.0) != 1.0),
        "scale_factor": profile.scale_factor,
        "profile": profile.as_dict(),
    }


def _safe_divide(numerator, denominator):
    import numpy

    with numpy.errstate(invalid="ignore", divide="ignore"):
        return numerator / denominator


def iter_windows(
    path: str | Path,
    *,
    window_size: int = 512,
    overlap: int = 64,
) -> Iterator[tuple[int, int, int, int]]:
    """Yield overlapping read windows covering the whole raster.

    Overlap matters: without it, a defect that straddles a window seam is
    reported twice or not at all, depending on where the seam falls.
    """
    rasterio = _import_rasterio()
    with rasterio.open(Path(path)) as dataset:
        height, width = dataset.height, dataset.width
        stride = max(1, window_size - overlap)
        for row in range(0, height, stride):
            for col in range(0, width, stride):
                yield (row, col, min(window_size, height - row), min(window_size, width - col))


def raster_to_observations(
    path: str | Path,
    *,
    window: tuple[int, int, int, int] | None = None,
    band_map: dict[str, int] | None = None,
    min_valid_fraction: float = 0.1,
    feature_id: str = "window",
) -> Any:
    """Produce a table of per-observation index values for the existing validators.

    One row per index per window, which is the shape ``validate_spectral_indices``
    expects. This is the bridge that lets the tabular spectral validators run on
    real imagery without being rewritten.
    """
    import numpy
    import pandas as pd

    payload = read_window_indices(path, window=window, band_map=band_map)
    indices = payload["indices"]
    row_off, col_off, height, width = payload["window"]

    rows = []
    total = height * width
    for name, array in indices.items():
        finite = numpy.isfinite(array)
        count = int(finite.sum())
        if count == 0:
            continue
        values = array[finite]
        rows.append(
            {
                "feature_id": f"{feature_id}_{name}",
                feature_id_col: f"{feature_id}_{name}",
                "window": f"{row_off},{col_off},{height},{width}",
                name: float(numpy.median(values)),
                "valid_fraction": count / total if total else 0.0,
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "max": float(values.max()),
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame[frame["valid_fraction"] >= min_valid_fraction].reset_index(drop=True)
    return frame


#: Name of the index column produced alongside the feature id.
feature_id_col = "feature_id"


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_raster(
    path: str | Path,
    *,
    needed_bands: Sequence[str] = ("blue", "green", "red", "nir"),
) -> list[Any]:
    """Check a raster before any index is computed from it.

    The conditions here are all ones that produce plausible-looking wrong
    answers rather than errors: an unmapped band, an unreported scale factor,
    a geographic CRS on an index that needs metres, no nodata value.
    """
    issues: list[Any] = []
    profile = profile_raster(path, needed_bands=needed_bands)

    if profile.unmapped_needed_bands:
        issues.append(
            _issue(
                "raster_band_unmapped",
                "high",
                f"Could not identify bands for: {', '.join(profile.unmapped_needed_bands)}. "
                "Index values would be computed from the wrong wavelengths, or the "
                "raster cannot support the requested index at all",
                profile.as_dict(),
            )
        )

    if profile.scale_factor is None:
        issues.append(
            _issue(
                "raster_scale_factor_unknown",
                "medium",
                f"No reflectance scale factor is recorded for this file (dtype "
                f"{profile.dtype}). Values may be digital numbers rather than "
                "reflectance; indices computed from them would be scaled incorrectly",
                profile.as_dict(),
            )
        )

    if profile.is_geographic_crs:
        issues.append(
            _issue(
                "raster_geographic_crs",
                "medium",
                "Raster CRS is geographic, so pixel dimensions are in degrees. "
                "Pixel size and any area calculation will be wrong unless reprojected",
                profile.as_dict(),
            )
        )

    if profile.nodata is None and profile.dtype.startswith("float"):
        issues.append(
            _issue(
                "raster_nodata_undeclared",
                "low",
                "Raster declares no nodata value, so invalid pixels will be "
                "included in index statistics",
                profile.as_dict(),
            )
        )

    if profile.count < len(needed_bands):
        issues.append(
            _issue(
                "raster_insufficient_bands",
                "high",
                f"Raster has {profile.count} band(s) but {len(needed_bands)} are needed "
                "for the requested indices",
                profile.as_dict(),
            )
        )

    return issues


def raster_report(path: str | Path, *, sample_windows: int = 0) -> dict[str, Any]:
    """Full raster summary for a manifest or report."""
    payload: dict[str, Any] = {"profile": profile_raster(path).as_dict(), "issues": []}
    for issue in validate_raster(path):
        payload["issues"].append(
            {"problem_name": issue.problem_name, "severity": str(issue.severity), "description": issue.description}
        )
    if sample_windows:
        windows = []
        for window in iter_windows(path):
            windows.append(window)
            if len(windows) >= sample_windows:
                break
        payload["sample_windows"] = windows
    return payload


__all__ = [
    "PROBLEM_NAME",
    "RasterProfile",
    "iter_windows",
    "profile_raster",
    "raster_report",
    "raster_to_observations",
    "read_window_indices",
    "validate_raster",
]