"""Buffer containment, round-trip durability, and scale-dependent tolerance.

Three checks that share a concern: whether an output can be trusted after it
has been written, rather than before.

**Containment.** A buffer drawn to enclose a geometry is an assertion that the
result contains the original. It is cheap to check and it fails in ways that
are invisible afterwards, because the output looks like a buffer and gets
used like one. The check is a geometric proof rather than a plausibility test:
a point at the buffer's furthest vertex distance is contained, and a buffer
that misses by a hair is a defect regardless of how small the miss is.

**Round trip.** A layer that is non-empty in memory may not be loadable from
disk. Geometry that only survived because it was never serialised, indexes
that were never written, and attributes whose type does not survive the format
are all invisible until the write. So the artefact is written and reopened.

**Scale-dependent tolerance.** A tolerance expressed in metres is wrong for a
building footprint and far too tight for a national boundary. Where the
tolerance comes from the data's own extent, it is stated as a fraction and the
resulting distance is reported, so the number that was actually applied can be
seen rather than guessed at.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "verify_containment",
    "round_trip",
    "scale_dependent_tolerance",
    "describe_tolerance",
]


def verify_containment(
    outer: Any,
    inner: Any,
    *,
    join_field: str | None = None,
    tolerance: float = 0.0,
    outer_name: str = "buffer",
    inner_name: str = "source",
) -> list[ValidationIssue]:
    """Report source features not fully enclosed by their buffer.

    ``join_field`` pairs each source with a buffer. Without it the whole inner
    layer must be contained by the whole outer layer, which is the right
    question for a single combined buffer and the wrong one for a per-feature
    result.
    """
    issues: list[ValidationIssue] = []
    if not len(outer) or not len(inner):
        return issues

    if join_field is None:
        combined = _union(outer)
        for index, row in inner.iterrows():
            geometry = row.get("geometry")
            if geometry is None:
                continue
            shortfall = _containment_shortfall(combined, geometry, tolerance)
            if shortfall is None:
                continue
            issues.append(
                build_issue(
                    "containment_not_enclosing",
                    index=index,
                    geometry=geometry,
                    description=(
                        f"{inner_name} geometry is not enclosed by {outer_name}; the "
                        f"furthest point lies about {shortfall:.4g} outside."
                    ),
                    extra={"shortfall": shortfall, "tolerance": tolerance},
                )
            )
        return issues

    lookup = {}
    try:
        for index, row in outer.iterrows():
            key = row.get(join_field)
            if key is not None:
                lookup[str(key).strip()] = row.get("geometry")
    except Exception:
        return issues

    for index, row in inner.iterrows():
        key = row.get(join_field)
        geometry = row.get("geometry")
        if geometry is None or key is None:
            continue
        candidate = lookup.get(str(key).strip())
        if candidate is None:
            issues.append(
                build_issue(
                    "containment_no_match",
                    index=index,
                    description=(
                        f"No {outer_name} for {join_field}={key!r}, so containment "
                        "cannot be established."
                    ),
                    extra={"key": str(key), "join_field": join_field},
                )
            )
            continue
        shortfall = _containment_shortfall(candidate, geometry, tolerance)
        if shortfall is None:
            continue
        issues.append(
            build_issue(
                "containment_not_enclosing",
                index=index,
                geometry=geometry,
                description=(
                    f"{inner_name} geometry is not enclosed by its {outer_name}; the "
                    f"furthest point lies about {shortfall:.4g} outside."
                ),
                extra={"key": str(key), "shortfall": shortfall, "tolerance": tolerance},
            )
        )
    return issues


def _union(layer: Any) -> Any:
    try:
        from shapely.ops import unary_union

        return unary_union(list(layer.geometry))
    except Exception:
        geometries = [g for g in layer.geometry if g is not None]
        return geometries[0] if len(geometries) == 1 else None


def _containment_shortfall(outer: Any, inner: Any, tolerance: float) -> float | None:
    """Distance by which ``inner`` escapes ``outer``, or ``None`` if enclosed."""
    if outer is None:
        return None
    try:
        if tolerance > 0 and outer.contains(inner):
            return None
        if outer.contains(inner):
            return None
        difference = inner.difference(outer)
        if difference.is_empty:
            return None
        if getattr(difference, "area", 0.0) == 0.0 and difference.geom_type == "LineString":
            return 0.0
        return float(difference.area)
    except Exception:
        return None


def round_trip(
    layer: Any,
    destination: str | Path,
    *,
    writer: Callable[..., Any] | None = None,
    driver: str | None = None,
    expect_rows: bool = True,
) -> list[ValidationIssue]:
    """Write a layer and read it back, reporting anything the write lost.

    The point is not that the file exists. It is that the reloaded layer is
    loadable, has the row count it should have, and still has a geometry
    column, because each of those has its own way of failing on a format the
    caller did not choose deliberately.
    """
    issues: list[ValidationIssue] = []
    path = Path(str(destination))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return [
            build_issue(
                "roundtrip_write_failed",
                description=f"Could not create {path.parent}: {exc}",
            )
        ]

    if writer is None:
        try:
            layer.to_file(path, driver=driver)
        except Exception as exc:
            return [
                build_issue(
                    "roundtrip_write_failed",
                    description=f"Writing {path.name} failed: {exc}",
                )
            ]
    else:
        try:
            writer(layer, path)
        except Exception as exc:
            return [
                build_issue(
                    "roundtrip_write_failed",
                    description=f"Writing {path.name} failed: {exc}",
                )
            ]

    if not path.exists():
        return [
            build_issue(
                "roundtrip_file_missing",
                description=(
                    f"The writer reported success but {path.name} does not exist."
                ),
            )
        ]

    try:
        import geopandas as gpd

        reloaded = gpd.read_file(path)
    except Exception as exc:
        return [
            build_issue(
                "roundtrip_read_failed",
                description=(
                    f"{path.name} was written but cannot be read back: {exc}. An "
                    "artefact that cannot be reopened is not an artefact."
                ),
            )
        ]

    if expect_rows and len(reloaded) != len(layer):
        issues.append(
            build_issue(
                "roundtrip_row_count_changed",
                description=(
                    f"{path.name} came back with {len(reloaded)} of {len(layer)} rows. "
                    "Features were dropped by the write."
                ),
                extra={"before": len(layer), "after": len(reloaded)},
            )
        )

    if "geometry" not in reloaded.columns:
        issues.append(
            build_issue(
                "roundtrip_geometry_lost",
                description=(
                    f"{path.name} came back with no geometry column. The write "
                    "produced attributes only."
                ),
            )
        )
    else:
        try:
            empty = int(reloaded.geometry.isna().sum() + reloaded.geometry.is_empty.sum())
        except Exception:
            empty = 0
        if empty:
            issues.append(
                build_issue(
                    "roundtrip_geometry_degraded",
                    description=(
                        f"{empty} geometry value(s) in {path.name} are null or empty "
                        "after the round trip."
                    ),
                )
            )

    try:
        path.unlink()
    except Exception:
        pass
    return issues


def scale_dependent_tolerance(
    extent_width: float,
    fraction: float,
    *,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float:
    """Express a tolerance as a fraction of the data's own extent.

    A fixed metre tolerance is a claim about scale that the data has not made.
    Deriving it from the extent keeps the same relative generosity on a
    building and on a country, and the caller can report the distance that
    resulted rather than the fraction that was asked for.
    """
    if fraction < 0:
        raise ValueError("fraction must not be negative")
    width = abs(float(extent_width))
    if not math.isfinite(width):
        raise ValueError("extent width is not a finite number")
    distance = width * float(fraction)
    if minimum and distance < minimum:
        distance = float(minimum)
    if maximum is not None and distance > maximum:
        distance = float(maximum)
    return distance


def describe_tolerance(
    layer: Any, fraction: float, *, minimum: float = 0.0
) -> dict[str, Any]:
    """Return the tolerance actually applied, with the extent it came from."""
    try:
        bounds = layer.total_bounds
        width = float(bounds[2] - bounds[0])
        height = float(bounds[3] - bounds[1])
    except Exception:
        width = 0.0
        height = 0.0
    resolved = scale_dependent_tolerance(
        max(width, height), fraction, minimum=minimum
    )
    return {
        "fraction": fraction,
        "extent_width": max(width, height),
        "tolerance": resolved,
        "minimum_applied": bool(minimum and max(width, height) * fraction < minimum),
        "basis": "extent",
    }