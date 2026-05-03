from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from .base import ValidationIssue, build_issue


def _iter_coordinate_sequences(geometry: Any) -> Iterable[list[tuple[float, ...]]]:
    geom_type = getattr(geometry, "geom_type", "")

    if geometry is None:
        return
    if geom_type == "Point":
        yield [tuple(geometry.coords[0])]
        return
    if geom_type in {"LineString", "LinearRing"}:
        yield [tuple(coord) for coord in geometry.coords]
        return
    if geom_type == "Polygon":
        yield [tuple(coord) for coord in geometry.exterior.coords]
        for ring in geometry.interiors:
            yield [tuple(coord) for coord in ring.coords]
        return
    if hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _iter_coordinate_sequences(part)
        return
    if hasattr(geometry, "coords"):
        yield [tuple(coord) for coord in geometry.coords]


def _decimal_places(value: float) -> int:
    normalized = Decimal(str(value)).normalize()
    exponent = normalized.as_tuple().exponent
    return max(0, -exponent)


def _max_decimal_places(geometry: Any) -> int:
    max_places = 0
    for coords in _iter_coordinate_sequences(geometry):
        for coord in coords:
            for value in coord:
                max_places = max(max_places, _decimal_places(float(value)))
    return max_places


def _layer_bounds(layer: Any) -> tuple[float, float, float, float] | None:
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    try:
        for _, row in layer.iterrows():
            geometry = row["geometry"] if "geometry" in row.index else None
            if geometry is None:
                continue
            bounds = getattr(geometry, "bounds", None)
            if bounds is None:
                continue
            left, bottom, right, top = bounds
            min_x = left if min_x is None else min(min_x, left)
            min_y = bottom if min_y is None else min(min_y, bottom)
            max_x = right if max_x is None else max(max_x, right)
            max_y = top if max_y is None else max(max_y, top)
    except Exception:
        return None
    if None in {min_x, min_y, max_x, max_y}:
        return None
    return float(min_x), float(min_y), float(max_x), float(max_y)


def _crs_string(layer: Any) -> str:
    crs = getattr(layer, "crs", None)
    if crs is None:
        return ""
    try:
        return crs.to_string().upper()
    except Exception:
        return str(crs).upper()


def _recommended_max_decimal_places(layer: Any) -> int:
    crs_text = _crs_string(layer)
    bounds = _layer_bounds(layer)
    span = None
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        span = max(abs(max_x - min_x), abs(max_y - min_y))

    if "4326" in crs_text or "WGS84" in crs_text or "WGS 84" in crs_text:
        if span is not None and span >= 20:
            return 12
        if span is not None and span >= 5:
            return 11
        return 9
    if crs_text:
        if span is not None and span >= 1_000_000:
            return 4
        if span is not None and span >= 100_000:
            return 3
        return 3
    return 9


def _recommended_xy_tolerance(layer: Any) -> float:
    crs_text = _crs_string(layer)
    bounds = _layer_bounds(layer)
    span = None
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        span = max(abs(max_x - min_x), abs(max_y - min_y))

    if "4326" in crs_text or "WGS84" in crs_text or "WGS 84" in crs_text:
        if span is not None and span >= 20:
            return 1e-4
        if span is not None and span >= 5:
            return 5e-5
        return 1e-6
    if crs_text:
        if span is not None and span >= 1_000_000:
            return 5.0
        if span is not None and span >= 100_000:
            return 0.5
        return 0.01
    return 0.01


def coordinate_precision(layer: Any, max_decimal_places: int | None = None) -> list[ValidationIssue]:
    """Return issues for features whose coordinate precision exceeds the configured threshold."""
    resolved_max_decimal_places = (
        _recommended_max_decimal_places(layer) if max_decimal_places is None else int(max_decimal_places)
    )
    issues: list[ValidationIssue] = []
    for index, row in layer.iterrows():
        geometry = row["geometry"] if "geometry" in row.index else None
        if geometry is None:
            continue
        if _max_decimal_places(geometry) > resolved_max_decimal_places:
            issues.append(
                build_issue(
                    "coordinate_precision_not_fit_for_use",
                    row=row,
                    index=index,
                    description=(
                        f"Feature coordinates exceed the configured precision threshold of {resolved_max_decimal_places} "
                        "decimal places."
                    ),
                    solution_hint="Reduce coordinate precision or snap the geometry to an appropriate grid for delivery.",
                )
            )
    return issues


def xy_tolerance(layer: Any, max_tolerance: float | None = None) -> list[ValidationIssue]:
    """Return a dataset-level issue when stored XY tolerance metadata exceeds a configured threshold."""
    attrs = getattr(layer, "attrs", {})
    tolerance = attrs.get("xy_tolerance", attrs.get("XY_TOLERANCE"))
    if tolerance is None:
        return []

    try:
        tolerance_value = float(tolerance)
    except (TypeError, ValueError):
        return []

    if max_tolerance is None:
        crs = getattr(layer, "crs", None)
        crs_string = ""
        if crs is not None:
            try:
                crs_string = crs.to_string().upper()
            except Exception:
                crs_string = str(crs).upper()
        max_tolerance = _recommended_xy_tolerance(layer)

    if tolerance_value > max_tolerance:
        return [
            build_issue(
                "inappropriate_xy_tolerance",
                description=(
                    f"Layer XY tolerance is {tolerance_value}, which exceeds the configured maximum of {max_tolerance}."
                ),
                solution_hint="Use a finer XY tolerance or restore the dataset's safer default tolerance.",
            )
        ]
    return []


def positional_accuracy(layer: Any, reference_layer: Any, tolerance: float = 10.0) -> list[ValidationIssue]:
    """Return issues for features farther than the allowed tolerance from the reference layer."""
    reference_geometries = []
    reference_sindex = getattr(reference_layer, "sindex", None)
    for _, reference_row in reference_layer.iterrows():
        geometry = reference_row["geometry"] if "geometry" in reference_row.index else None
        if geometry is not None:
            reference_geometries.append(geometry)

    issues: list[ValidationIssue] = []
    if not reference_geometries:
        return issues

    for index, row in layer.iterrows():
        geometry = row["geometry"] if "geometry" in row.index else None
        if geometry is None:
            continue
        candidate_geometries = reference_geometries
        if reference_sindex is not None:
            try:
                query_geometry = geometry.buffer(tolerance) if hasattr(geometry, "buffer") else geometry
                candidate_positions = reference_sindex.query(query_geometry)
                bounded_candidates = [
                    reference_geometries[int(position)]
                    for position in candidate_positions
                    if 0 <= int(position) < len(reference_geometries)
                ]
                if bounded_candidates:
                    candidate_geometries = bounded_candidates
            except Exception:
                candidate_geometries = reference_geometries
        distances = [geometry.distance(reference_geometry) for reference_geometry in candidate_geometries]
        if distances and min(distances) > tolerance:
            issues.append(
                build_issue(
                    "positional_accuracy_exceeds_reference_tolerance",
                    row=row,
                    index=index,
                    description=(
                        f"Feature is {min(distances):.3f} units away from the nearest reference feature, "
                        f"which exceeds the tolerance of {tolerance}."
                    ),
                    solution_hint="Compare the feature to the trusted reference and adjust or redigitize it if needed.",
                )
            )
    return issues


__all__ = ["coordinate_precision", "positional_accuracy", "xy_tolerance"]
