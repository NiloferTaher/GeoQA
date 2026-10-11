"""Slivers: thin geometry, and geometry that is simply too small.

A sliver is not a small polygon. A 4 m2 square is small; a 4 m2 strip two
hundred metres long is a sliver, and only the second causes the problems
that matter. It breaks topology, fails to buffer, produces unusable network
geometry, and survives every area threshold set high enough to be useful.

Three tests, because each misses what the others catch.

**Minimum area** is the blunt one. It catches debris and failed dissolves,
and it says nothing about shape. A caller who wants to be conservative sets
it high and discards legitimate small features along with the slivers, so it
is an argument and the resolved value is reported.

**Minimum width by erosion** is the one that actually identifies a sliver.
Buffering a polygon inwards by half the required width and finding nothing
left proves the polygon is thinner than twice that width everywhere. It is
scale-correct by construction: a 1 m strip in a building footprint and a 1 m
strip spanning a county are both caught, while a large compact polygon is
not caught at all. No area threshold can do that.

**Elongation ratio** is the scale-free shape measure. Dividing perimeter
squared by area gives a quantity that is dimensionless, so a long thin strip
scores the same whether it is measured in metres or feet, and a compact shape
scores low whatever its size. It is reported rather than thresholded by
default, because what counts as too elongated depends entirely on whether
the layer is being used for routing, for area statistics, or for display.

The width check is the expensive one, because erosion is a real geometric
operation on every polygon. It is therefore reported separately from the
cheap tests rather than being folded into them, so a caller who only needs
the cheap pass can skip it and know they skipped it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from shapely.geometry import Point

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "ShapeProfile",
    "profile_shape",
    "below_minimum_feature_area",
    "thin_geometry",
    "elongation_report",
    "validate_shape",
]

#: Dimensionless. A circle of any radius scores 1; a square scores about
#: 1.27; a strip approaches the square of its length-to-width ratio.
_CIRCLE_CONSTANT = 4.0 * math.pi


@dataclass
class ShapeProfile:
    """Measured shape characteristics of one geometry, or of a whole layer."""

    area: float = 0.0
    perimeter: float = 0.0
    length: float = 0.0
    elongation: float | None = None
    compactness: float | None = None
    width: float | None = None
    parts: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "perimeter": self.perimeter,
            "length": self.length,
            "elongation": self.elongation,
            "compactness": self.compactness,
            "estimated_width": self.width,
            "parts": self.parts,
        }


def _parts(geometry: Any) -> list[Any]:
    pieces = getattr(geometry, "geoms", None)
    if pieces is None:
        return [geometry]
    try:
        return list(pieces)
    except Exception:
        return [geometry]


def _measure(geometry: Any) -> ShapeProfile:
    profile = ShapeProfile(parts=len(_parts(geometry)))
    if geometry is None:
        return profile
    try:
        if geometry.is_empty:
            return profile
    except Exception:
        pass
    try:
        profile.area = float(geometry.area)
    except Exception:
        profile.area = 0.0
    try:
        profile.perimeter = float(getattr(geometry, "length", 0.0))
    except Exception:
        profile.perimeter = 0.0
    try:
        profile.length = float(geometry.length)
    except Exception:
        profile.length = 0.0

    if profile.area > 0:
        # Compactness ratio, perimeter^2 / (4*pi*area). Dimensionless, and a
        # circle of any size scores exactly 1 because its perimeter is the
        # circumference. It is the standard form rather than a bare
        # length^2/area because the constant is what makes "1.0" mean
        # something a reader can hold on to.
        profile.elongation = (
            profile.length * profile.length / (_CIRCLE_CONSTANT * profile.area)
        )
        # The reciprocal runs to 0 as a feature becomes a strip, which is the
        # more natural direction to read a thinness measure in.
        profile.compactness = (
            _CIRCLE_CONSTANT * profile.area / (profile.length * profile.length)
            if profile.length
            else None
        )
        profile.width = _erosion_width(geometry, max(profile.elongation, 1.0) ** 0.5)
    return profile


def _iter_coords(geometry: Any):
    """Yield every coordinate of any geometry, whatever its type.

    A polygon exposes no ``.coords`` and no ``.geoms``; its vertices live on
    the exterior ring and any interior rings. An iterator that forgets this
    silently reports a polygon as having no coordinates, which turns every
    measurement derived from them into zero.
    """
    if geometry is None:
        return
    try:
        yield from geometry.coords
        return
    except Exception:
        pass
    exterior = getattr(geometry, "exterior", None)
    if exterior is not None:
        try:
            yield from exterior.coords
        except Exception:
            pass
        try:
            for interior in geometry.interiors:
                yield from interior.coords
        except Exception:
            pass
        return
    parts = getattr(geometry, "geoms", None)
    if parts is not None:
        try:
            for part in parts:
                yield from _iter_coords(part)
        except Exception:
            return


def _max_centroid_distance(geometry: Any) -> float:
    """Upper bound on the inward buffer that removes the geometry entirely.

    Any point of the geometry is within this distance of the centroid, so
    eroding by it necessarily erases the whole thing. Used as the starting
    bracket so the search never has to assume a shape is thin enough to
    disappear inside the first guess.
    """
    try:
        centroid = geometry.centroid
    except Exception:
        return 0.0
    farthest = 0.0
    for x, y in _iter_coords(geometry):
        try:
            distance = centroid.distance(Point(x, y))
        except Exception:
            continue
        if distance > farthest:
            farthest = distance
    return farthest


def _erosion_width(geometry: Any, start: float | None = None) -> float | None:
    """Bisect the inward buffer that removes the geometry entirely.

    That buffer distance is half the widest inscribed width, which is the
    sliver measure. The search finds the *smallest* distance that empties the
    geometry, so an empty result at ``mid`` means ``mid`` is too large and the
    answer lies below it, and a non-empty result means the opposite.

    The bracket starts from the distance to the furthest vertex rather than
    from an estimate, so a compact polygon is measured rather than declared
    unmeasurable.
    """
    high = _max_centroid_distance(geometry)
    if high <= 0:
        return None
    if start:
        high = min(high, max(float(start), high * 1.0))

    try:
        if not geometry.buffer(-high).is_empty:
            high = high * 2.0
            if not geometry.buffer(-high).is_empty:
                return None
    except Exception:
        return None

    low = 0.0
    for _ in range(30):
        mid = (low + high) / 2.0
        try:
            if geometry.buffer(-mid).is_empty:
                # Too aggressive: the answer lies below mid.
                high = mid
            else:
                # Not aggressive enough: the answer lies above mid.
                low = mid
        except Exception:
            break
    return low * 2.0


def profile_shape(layer: Any) -> dict[str, Any]:
    """Measure every feature without judging any of them."""
    rows: list[dict[str, Any]] = []
    try:
        iterator = layer.iterrows()
    except Exception:
        return {"features": rows, "count": 0}

    for index, row in iterator:
        profile = _measure(row.get("geometry"))
        rows.append({"index": index, **profile.to_dict()})

    areas = sorted(r["area"] for r in rows if r["area"] > 0)
    summary: dict[str, Any] = {"features": rows, "count": len(rows)}
    if areas:
        def percentile(fraction: float) -> float:
            position = min(len(areas) - 1, max(0, int(round(fraction * (len(areas) - 1)))))
            return areas[position]

        summary["area_stats"] = {
            "min": areas[0],
            "p05": percentile(0.05),
            "median": percentile(0.5),
            "p95": percentile(0.95),
            "max": areas[-1],
        }
    elongations = [r["elongation"] for r in rows if r["elongation"] is not None]
    if elongations:
        summary["elongation_max"] = max(elongations)
        summary["elongation_median"] = sorted(elongations)[len(elongations) // 2]
    return summary


def below_minimum_feature_area(
    layer: Any,
    *,
    minimum_area: float,
    include_zero_area: bool = True,
) -> list[ValidationIssue]:
    """Report features at or below a declared area floor.

    Blunt by design. It catches debris and failed dissolves and it says
    nothing about shape, so a caller who needs to identify slivers should use
    :func:`thin_geometry` as well.
    """
    issues: list[ValidationIssue] = []
    if minimum_area < 0:
        raise ValueError("minimum_area must not be negative")

    try:
        iterator = layer.iterrows()
    except Exception:
        return issues

    for index, row in iterator:
        geometry = row.get("geometry")
        if geometry is None:
            continue
        area = _measure(geometry).area
        if area <= 0.0:
            if include_zero_area:
                issues.append(
                    build_issue(
                        "feature_zero_area",
                        index=index,
                        geometry=geometry,
                        description=(
                            "This feature has no area. It is debris, or the residue "
                            "of an operation that did not complete."
                        ),
                        extra={"area": 0.0, "minimum_area": minimum_area},
                    )
                )
            continue
        if area < minimum_area:
            issues.append(
                build_issue(
                    "below_minimum_feature_area",
                    index=index,
                    geometry=geometry,
                    description=(
                        f"This feature has area {area:.6g}, below the declared floor of "
                        f"{minimum_area:.6g}."
                    ),
                    extra={"area": area, "minimum_area": minimum_area},
                )
            )
    return issues


def thin_geometry(
    layer: Any,
    *,
    minimum_width: float,
    report_all_measurements: bool = False,
) -> list[ValidationIssue]:
    """Report polygons thinner than twice ``minimum_width``, anywhere.

    This is the test that identifies a sliver rather than merely a small
    polygon. A feature that disappears when buffered inwards by half the
    required width is thinner than that width along its whole extent, which
    no area threshold can establish and which is unaffected by the units the
    data happens to be in.

    Costs a geometric operation per feature, so it is separate from the cheap
    area test rather than folded into it.
    """
    issues: list[ValidationIssue] = []
    if minimum_width <= 0:
        raise ValueError("minimum_width must be positive")

    half = minimum_width / 2.0
    try:
        iterator = layer.iterrows()
    except Exception:
        return issues

    for index, row in iterator:
        geometry = row.get("geometry")
        if geometry is None:
            continue
        geom_type = str(getattr(geometry, "geom_type", ""))
        if geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        profile = _measure(geometry)
        if profile.area <= 0:
            continue

        try:
            eroded = geometry.buffer(-half)
            vanished = eroded.is_empty
        except Exception:
            continue

        if vanished:
            issues.append(
                build_issue(
                    "geometry_thin_sliver",
                    index=index,
                    geometry=geometry,
                    description=(
                        f"This polygon disappears when buffered inwards by {half:.6g}, so it "
                        f"is thinner than {minimum_width:.6g} everywhere. A feature this thin "
                        "breaks topology, cannot be buffered meaningfully, and will not "
                        "route."
                    ),
                    extra={
                        "minimum_width": minimum_width,
                        "buffer_used": -half,
                        **profile.to_dict(),
                    },
                )
            )
        elif report_all_measurements:
            issues.append(
                build_issue(
                    "geometry_width_measured",
                    index=index,
                    geometry=geometry,
                    description=(
                        f"This polygon survives a {half:.6g} inward buffer. Measured width "
                        f"is about {profile.width:.6g}."
                    )
                    if profile.width
                    else "This polygon survives the inward buffer; its width could not be measured.",
                    extra={"minimum_width": minimum_width, **profile.to_dict()},
                )
            )
    return issues


def elongation_report(layer: Any, *, maximum_elongation: float | None = None) -> list[ValidationIssue]:
    """Report polygons whose length-to-width ratio exceeds a declared limit.

    ``maximum_elongation`` is left optional because what counts as too
    elongated depends on the use. A drainage catchment and a cable run are
    both legitimately elongated, and neither should be flattened by a default.
    The measurement is therefore available without a judgement, and a
    judgement is made only when the caller supplies one.
    """
    issues: list[ValidationIssue] = []
    if maximum_elongation is None:
        return issues
    if maximum_elongation <= 1.0:
        raise ValueError("maximum_elongation is a length-to-width ratio and must exceed 1")

    try:
        iterator = layer.iterrows()
    except Exception:
        return issues

    for index, row in iterator:
        geometry = row.get("geometry")
        if geometry is None:
            continue
        if str(getattr(geometry, "geom_type", "")) not in {"Polygon", "MultiPolygon"}:
            continue
        profile = _measure(geometry)
        if profile.area <= 0 or profile.elongation is None:
            continue
        if profile.elongation > maximum_elongation:
            issues.append(
                build_issue(
                    "geometry_elongated",
                    index=index,
                    geometry=geometry,
                    description=(
                        f"This polygon has a length-to-width ratio of "
                        f"{profile.elongation:.4g}, above the declared "
                        f"{maximum_elongation:.4g}."
                    ),
                    extra={"maximum_elongation": maximum_elongation, **profile.to_dict()},
                )
            )
    return issues


def validate_shape(
    layer: Any,
    *,
    minimum_area: float | None = None,
    minimum_width: float | None = None,
    maximum_elongation: float | None = None,
) -> list[ValidationIssue]:
    """Run whichever shape checks the caller supplied thresholds for.

    Each threshold is opt-in because each answers a different question, and
    the layer's own size distribution is the right thing to set them from:
    :func:`profile_shape` returns the area percentiles and the elongation
    distribution for exactly that purpose.
    """
    issues: list[ValidationIssue] = []
    if minimum_area is not None:
        issues.extend(below_minimum_feature_area(layer, minimum_area=minimum_area))
    if minimum_width is not None:
        issues.extend(thin_geometry(layer, minimum_width=minimum_width))
    if maximum_elongation is not None:
        issues.extend(elongation_report(layer, maximum_elongation=maximum_elongation))
    return issues