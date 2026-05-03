from __future__ import annotations

from collections.abc import Iterable
import math
from typing import Any

from .base import ValidationIssue, build_issue


def _iter_coordinate_sequences(geometry: Any) -> Iterable[list[tuple[float, ...]]]:
    geom_type = getattr(geometry, "geom_type", "")

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


def _has_duplicate_consecutive_vertex(geometry: Any) -> bool:
    if geometry is None or getattr(geometry, "is_empty", False):
        return False

    for coords in _iter_coordinate_sequences(geometry):
        for previous, current in zip(coords, coords[1:]):
            if previous == current:
                return True
    return False


def _run_geometry_check(layer: Any, predicate) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for record in layer.iterrows():
        result = predicate(record)
        if result is not None:
            issues.append(result)
    return issues


def null_geometry(layer: Any) -> list[ValidationIssue]:
    """Detect features with null geometries."""

    def check(record: tuple[Any, Any]) -> ValidationIssue | None:
        index, row = record
        geometry = row.geometry if "geometry" in row.index else None
        if geometry is None:
            return build_issue("null_geometry", row=row, index=index)
        return None

    return _run_geometry_check(layer, check)


def self_intersection(layer: Any) -> list[ValidationIssue]:
    """Detect self-intersecting geometries."""
    try:
        from shapely.validation import explain_validity
    except ImportError as exc:
        raise RuntimeError(
            "Self-intersection validation requires Shapely. Install shapely to use this validator."
        ) from exc

    def check(record: tuple[Any, Any]) -> ValidationIssue | None:
        index, row = record
        geometry = row.geometry if "geometry" in row.index else None
        if geometry is None or getattr(geometry, "is_empty", False):
            return None
        geom_type = getattr(geometry, "geom_type", "")
        if geom_type in {"LineString", "LinearRing", "MultiLineString"} and hasattr(geometry, "is_simple"):
            if not geometry.is_simple:
                return build_issue("self_intersection", row=row, index=index)
        validity_text = explain_validity(geometry)
        if "Self-intersection" in validity_text or "Ring Self-intersection" in validity_text:
            return build_issue("self_intersection", row=row, index=index)
        return None

    return _run_geometry_check(layer, check)


def duplicate_vertex(layer: Any) -> list[ValidationIssue]:
    """Detect duplicate consecutive vertices in geometries."""

    def check(record: tuple[Any, Any]) -> ValidationIssue | None:
        index, row = record
        geometry = row.geometry if "geometry" in row.index else None
        if _has_duplicate_consecutive_vertex(geometry):
            return build_issue("duplicate_vertex", row=row, index=index)
        return None

    return _run_geometry_check(layer, check)


def _segment_length(start: tuple[float, ...], end: tuple[float, ...]) -> float:
    total = 0.0
    for left, right in zip(start, end):
        total += (float(right) - float(left)) ** 2
    return total ** 0.5


def _geometry_length(geometry: Any) -> float:
    if geometry is None:
        return 0.0
    length = getattr(geometry, "length", None)
    if length is not None:
        try:
            return float(length)
        except Exception:
            pass
    total = 0.0
    for coords in _iter_coordinate_sequences(geometry):
        for start, end in zip(coords, coords[1:]):
            total += _segment_length(start, end)
    return total


def _interior_angles(coords: list[tuple[float, ...]]) -> Iterable[float]:
    for left, middle, right in zip(coords, coords[1:], coords[2:]):
        try:
            vec_a = (float(left[0]) - float(middle[0]), float(left[1]) - float(middle[1]))
            vec_b = (float(right[0]) - float(middle[0]), float(right[1]) - float(middle[1]))
            len_a = math.hypot(*vec_a)
            len_b = math.hypot(*vec_b)
            if len_a == 0.0 or len_b == 0.0:
                continue
            dot = (vec_a[0] * vec_b[0]) + (vec_a[1] * vec_b[1])
            cosine = max(-1.0, min(1.0, dot / (len_a * len_b)))
            yield math.degrees(math.acos(cosine))
        except Exception:
            continue


def below_minimum_feature_length(layer: Any, *, min_length: float = 0.0) -> list[ValidationIssue]:
    """Detect line-like features whose total length falls below a configured minimum."""

    def check(record: tuple[Any, Any]) -> ValidationIssue | None:
        index, row = record
        geometry = row.geometry if "geometry" in row.index else None
        geom_type = getattr(geometry, "geom_type", "")
        if geometry is None or geom_type not in {"LineString", "LinearRing", "MultiLineString"}:
            return None
        if _geometry_length(geometry) < float(min_length):
            return build_issue(
                "below_minimum_feature_length",
                row=row,
                index=index,
                description=f"This feature is shorter than the configured minimum length threshold ({min_length}).",
                solution_hint="Review whether the segment is a drafting artifact, an undersized feature, or should be merged into an adjacent line.",
            )
        return None

    return _run_geometry_check(layer, check)


def sharp_angle_cutback(layer: Any, *, min_angle_degrees: float = 15.0) -> list[ValidationIssue]:
    """Detect line or polygon vertices with suspiciously sharp angle cutbacks."""

    def check(record: tuple[Any, Any]) -> ValidationIssue | None:
        index, row = record
        geometry = row.geometry if "geometry" in row.index else None
        if geometry is None:
            return None
        for coords in _iter_coordinate_sequences(geometry):
            if len(coords) < 3:
                continue
            for angle in _interior_angles(coords):
                if angle < float(min_angle_degrees):
                    return build_issue(
                        "sharp_angle_cutback",
                        row=row,
                        index=index,
                        description=f"A vertex angle ({angle:.2f} degrees) is sharper than the configured minimum of {min_angle_degrees}.",
                        solution_hint="Inspect the feature for digitizing cutbacks, spikes, or overshoots and simplify or redigitize the affected geometry if needed.",
                    )
        return None

    return _run_geometry_check(layer, check)


__all__ = [
    "below_minimum_feature_length",
    "duplicate_vertex",
    "null_geometry",
    "self_intersection",
    "sharp_angle_cutback",
]
