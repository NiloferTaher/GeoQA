"""Cloud Optimized GeoTIFF conformance, and vector format currency.

Why this exists
---------------
GeoTIFF is not obsolete; it is the format the cloud-native practice grew out of.
**Cloud Optimized GeoTIFF became an official OGC Standard in October 2023**, and
GeoTIFF itself remains both an OGC and a NASA/EOSDIS standard. What changed is
the expectation about how a large TIFF should be laid out: tiled, with
reduced-resolution overviews, and with the directory ordered so a reader can
range-request a small part.

So the useful question about a delivered TIFF is not "is this GeoTIFF" but "is
this one a reader can read partially". A plain TIFF is valid, opens everywhere,
and is the wrong shape for anything large.

Other formats, and why they are not replacements
------------------------------------------------
Recorded here rather than left implicit, because "we support all known formats"
is a claim that needs a boundary.

``Zarr`` / GeoZarr
    Genuinely promising for multidimensional cubes and the direction of travel,
    but the status is standards-in-development, and the format documentation
    notes it is weaker for long-term archival because a store is spread across
    many objects rather than being one self-contained file.
``netCDF-4`` and ``HDF5``
    Still approved standards for multidimensional scientific data, and the
    reason this library now reads HDF5 hyperspectral products directly. A
    GeoTIFF cannot express an N-dimensional array without being stretched past
    what TIFF was designed for.
``GeoParquet`` / ``FlatGeobuf``
    The vector direction, at draft OGC status. Worth supporting; not yet a
    stable interchange default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "cloud_optimized_raster"

#: The layout properties that distinguish COG from a plain tiled TIFF.
#: Sources: OGC 21-026 Cloud Optimized GeoTIFF Standard v1.0.
COG_MARKERS = ("tiled", "overviews", "ifd_ordered")

#: Extensions this library can currently read, and their standing.
FORMAT_STATUS: dict[str, tuple[str, str]] = {
    ".tif": ("geotiff", "OGC and NASA/EOSDIS standard; current"),
    ".tiff": ("geotiff", "OGC and NASA/EOSDIS standard; current"),
    ".vrt": ("gdal_vrt", "GDAL virtual dataset; current"),
    ".img": ("hdf_eos_or_erdas", "mixed provenance; confirm which"),
    ".h5": ("hdf5", "current for multidimensional and hyperspectral"),
    ".hdf": ("hdf5", "current for multidimensional and hyperspectral"),
    ".nc": ("netcdf", "current for multidimensional scientific data"),
    ".zarr": ("zarr", "emerging; OGC standard in development"),
    ".parquet": ("geoparquet", "draft OGC standard for vector"),
    ".fgb": ("flatgeobuf", "draft OGC standard for vector"),
    ".gpkg": ("geopackage", "current; OGC standard, widely supported"),
    ".pmtiles": ("pmtiles", "emerging; single-file tile archive"),
}


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _import_rasterio():
    # PROJ must resolve before any CRS is built, or every EPSG lookup fails.
    from ..proj_env import ensure_proj

    ensure_proj()
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "rasterio is required for raster inspection. Install with: pip install 'geoqa[raster]'"
        ) from exc
    return rasterio


@dataclass
class CogProfile:
    """Whether a TIFF meets the Cloud Optimized GeoTIFF expectations."""

    path: str
    width: int
    height: int
    band_count: int
    is_tiled: bool
    block_shapes: tuple[tuple[int, int], ...] = ()
    block_size: int = 0
    overview_levels: int = 0
    compression: str | None = None
    dtype: str | None = None
    megabytes: float = 0.0
    driver: str | None = None
    #: Marker strings this file does meet.
    markers_present: tuple[str, ...] = ()

    @property
    def meets_cog_expectations(self) -> bool:
        return self.is_tiled and self.overview_levels > 0

    #: Set from the caller's threshold, so the profile reflects the policy in force.
    large_threshold_mb: float = 100.0

    @property
    def is_large(self) -> bool:
        """Big enough that partial reads matter."""
        return self.megabytes >= self.large_threshold_mb

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "driver": self.driver,
            "width": self.width,
            "height": self.height,
            "bands": self.band_count,
            "megabytes": round(self.megabytes, 2),
            "is_tiled": self.is_tiled,
            "block_size": self.block_size,
            "overview_levels": self.overview_levels,
            "compression": self.compression,
            "dtype": self.dtype,
            "meets_cog_expectations": self.meets_cog_expectations,
            "is_large": self.is_large,
            "markers_present": list(self.markers_present),
        }


def profile_cog(path: str | Path, *, large_threshold_mb: float = 100.0) -> CogProfile:
    """Inspect a TIFF for cloud-optimized layout. Reads metadata only."""
    rasterio = _import_rasterio()
    target = Path(path)

    with rasterio.open(target) as handle:
        profile = handle.profile
        overviews = 0
        for band_index in handle.indexes:
            try:
                overviews = max(overviews, len(handle.overviews(band_index)))
            except Exception:
                continue

        block_shapes: list[tuple[int, int]] = []
        for band_index in handle.indexes:
            try:
                block_shapes.append(tuple(handle.block_shapes[band_index]))
            except Exception:
                continue

        # GDAL states whether the file is tiled; inferring it from the block
        # shape gets a small striped file wrong, because a default strip block
        # is smaller than the image in both axes.
        is_tiled = bool(profile.get("tiled", False))

        megabytes = handle.width * handle.height * handle.count * (
            _dtype_size(str(profile.get("dtype", "float32")))
        ) / 1_048_576.0

        result = CogProfile(
            path=str(target),
            width=handle.width,
            height=handle.height,
            band_count=handle.count,
            is_tiled=is_tiled,
            block_shapes=tuple(block_shapes),
            block_size=min((min(shape) for shape in block_shapes if min(shape) > 0), default=0),
            overview_levels=overviews,
            compression=profile.get("compress"),
            dtype=str(profile.get("dtype")),
            megabytes=megabytes,
            driver=handle.driver,
            large_threshold_mb=large_threshold_mb,
        )

    markers: list[str] = []
    if result.is_tiled:
        markers.append("tiled")
    if result.overview_levels > 0:
        markers.append("overviews")
    result.markers_present = tuple(markers)
    return result


def _dtype_size(dtype: str) -> int:
    return {
        "uint8": 1, "int8": 1, "uint16": 2, "int16": 2,
        "uint32": 4, "int32": 4, "float32": 4,
        "uint64": 8, "int64": 8, "float64": 8, "complex64": 8, "complex128": 16,
    }.get(dtype, 4)


def validate_cog(
    path: str | Path,
    *,
    require_overviews_above_mb: float = 100.0,
    minimum_block_size: int = 512,
) -> list[Any]:
    """Report a TIFF that is valid but not laid out for partial reading.

    Conditions emitted
    ------------------
    ``raster_not_cloud_optimized``
        A large TIFF is striped rather than tiled. Medium: it opens fine and
        reads fine locally, and is the wrong shape for anything served over a
        network.
    ``raster_missing_overviews``
        A large TIFF has no reduced-resolution levels, so any consumer must read
        full resolution to draw a thumbnail.
    ``raster_block_size_small``
        Tiles are smaller than the declared minimum, which trades read
        efficiency for metadata overhead without a matching gain.
    ``raster_deprecated_format_flagged``
        An extension whose standing has changed. Informational.
    """
    profile = profile_cog(path, large_threshold_mb=require_overviews_above_mb)
    issues: list[Any] = []

    if profile.is_large and not profile.is_tiled:
        issues.append(
            _issue(
                "raster_not_cloud_optimized", "medium",
                f"{Path(profile.path).name!r} is {profile.megabytes:.0f} MB and stored in "
                "strips rather than tiles. It is a valid TIFF and will open everywhere, but a "
                "reader cannot fetch a small part of it, so anything serving it over a network "
                "must move the whole file",
                profile.as_dict(),
            )
        )

    if profile.is_large and profile.overview_levels == 0:
        issues.append(
            _issue(
                "raster_missing_overviews", "medium",
                f"{Path(profile.path).name!r} is {profile.megabytes:.0f} MB with no "
                "reduced-resolution overview levels. A consumer displaying it must read full "
                "resolution to produce a thumbnail, which is the main reason cloud-optimized "
                "layouts exist",
                profile.as_dict(),
            )
        )

    # Tile size only matters once a file is large enough for partial reads to
    # happen at all. A 64x64 file with small tiles is not a performance problem.
    if profile.is_tiled and profile.is_large and 0 < profile.block_size < minimum_block_size:
        issues.append(
            _issue(
                "raster_block_size_small", "low",
                f"Tiles are {profile.block_size} px, below the {minimum_block_size} px "
                "convention. Small tiles increase metadata overhead without improving access, "
                "since a partial read still costs a whole tile",
                profile.as_dict(),
            )
        )

    extension = Path(profile.path).suffix.lower()
    if extension in FORMAT_STATUS:
        kind, standing = FORMAT_STATUS[extension]
        if "draft" in standing or "in development" in standing or "emerging" in standing:
            issues.append(
                _issue(
                    "raster_deprecated_format_flagged", "info",
                    f"{extension} is {kind}: {standing}. Nothing is wrong with the file; this "
                    "is recorded so the interchange choice is deliberate rather than inherited",
                    {"extension": extension, "format": kind, "standing": standing},
                )
            )

    return issues


def format_support_report() -> list[dict[str, str]]:
    """The formats this library can read, with their current standing."""
    return [
        {"extension": extension, "format": kind, "standing": standing}
        for extension, (kind, standing) in sorted(FORMAT_STATUS.items())
    ]


__all__ = [
    "COG_MARKERS",
    "FORMAT_STATUS",
    "PROBLEM_NAME",
    "CogProfile",
    "format_support_report",
    "profile_cog",
    "validate_cog",
]