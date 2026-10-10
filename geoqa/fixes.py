from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RepairCallable = callable


@dataclass(slots=True, frozen=True)
class RepairProfile:
    name: str
    enabled_repairs: tuple[str, ...] = ()
    disabled_repairs: tuple[str, ...] = ()
    repair_options: dict[str, dict[str, Any]] = field(default_factory=dict)


_CUSTOM_REPAIRS: dict[str, Any] = {}


def register_custom_repair(name: str, func: Any) -> None:
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("Repair name must be non-empty.")
    _CUSTOM_REPAIRS[normalized_name] = func


def clear_custom_repairs() -> None:
    _CUSTOM_REPAIRS.clear()


def list_custom_repairs() -> list[str]:
    return sorted(_CUSTOM_REPAIRS.keys())


def drop_null_geometries(layer: Any) -> Any:
    """Return a copy of the layer without rows whose geometry is null."""
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        return layer.copy()
    return layer.loc[layer["geometry"].notna()].copy()


def _dedupe_consecutive_coordinates(coords: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    if not coords:
        return coords
    deduped = [coords[0]]
    for coord in coords[1:]:
        if coord != deduped[-1]:
            deduped.append(coord)
    return deduped


def _dedupe_geometry(geometry: Any) -> Any:
    geom_type = getattr(geometry, "geom_type", "")
    if geometry is None or getattr(geometry, "is_empty", False):
        return geometry
    if geom_type == "Point":
        return geometry

    try:
        from shapely.geometry import LineString, LinearRing, MultiLineString, MultiPolygon, Polygon
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Removing duplicate vertices requires Shapely.") from exc

    if geom_type in {"LineString", "LinearRing"}:
        coords = _dedupe_consecutive_coordinates([tuple(coord) for coord in geometry.coords])
        if len(coords) < 2:
            return geometry
        return LineString(coords) if geom_type == "LineString" else LinearRing(coords)

    if geom_type == "Polygon":
        exterior = _dedupe_consecutive_coordinates([tuple(coord) for coord in geometry.exterior.coords])
        if len(exterior) < 4:
            return geometry
        interiors = []
        for ring in geometry.interiors:
            ring_coords = _dedupe_consecutive_coordinates([tuple(coord) for coord in ring.coords])
            if len(ring_coords) >= 4:
                interiors.append(ring_coords)
        return Polygon(exterior, interiors)

    if geom_type == "MultiLineString":
        return MultiLineString([_dedupe_geometry(part) for part in geometry.geoms])

    if geom_type == "MultiPolygon":
        return MultiPolygon([_dedupe_geometry(part) for part in geometry.geoms])

    if hasattr(geometry, "geoms"):
        rebuilt = [_dedupe_geometry(part) for part in geometry.geoms]
        return type(geometry)(rebuilt)

    return geometry


def remove_duplicate_vertices(layer: Any) -> Any:
    """Return a copy of the layer with duplicate consecutive geometry vertices removed."""
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        return layer.copy()

    fixed = layer.copy()
    fixed["geometry"] = fixed["geometry"].apply(_dedupe_geometry)
    return fixed


def _make_geometry_valid(geometry: Any) -> Any:
    if geometry is None or getattr(geometry, "is_empty", False):
        return geometry
    try:
        from shapely import make_valid
    except ImportError:
        make_valid = None
    except Exception:
        make_valid = None

    if make_valid is not None:
        try:
            return make_valid(geometry)
        except Exception:
            pass

    geom_type = getattr(geometry, "geom_type", "")
    if geom_type in {"Polygon", "MultiPolygon"}:
        try:
            return geometry.buffer(0)
        except Exception:
            return geometry
    return geometry


def make_geometries_valid(layer: Any) -> Any:
    """Return a copy of the layer with polygonal self-intersections or invalidity repaired where possible."""
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        return layer.copy()

    fixed = layer.copy()
    fixed["geometry"] = fixed["geometry"].apply(_make_geometry_valid)
    return fixed


def apply_basic_geometry_fixes(
    layer: Any,
    *,
    drop_null: bool = True,
    dedupe_vertices: bool = True,
    make_valid: bool = True,
) -> Any:
    """
    Apply a conservative deterministic geometry-cleaning sequence.

    Order:
    1. drop null geometries
    2. remove duplicate consecutive vertices
    3. make polygonal geometries valid where possible
    """
    fixed = layer.copy()
    if drop_null:
        fixed = drop_null_geometries(fixed)
    if dedupe_vertices:
        fixed = remove_duplicate_vertices(fixed)
    if make_valid:
        fixed = make_geometries_valid(fixed)
    return fixed


def apply_repair_plan(
    layer: Any,
    *,
    profile: RepairProfile | None = None,
    include_builtin: bool = True,
) -> Any:
    """Apply built-in and registered custom repairs in a predictable order."""
    ordered_repairs: list[tuple[str, Any, dict[str, Any]]] = []

    if include_builtin:
        ordered_repairs.extend(
            [
                ("drop_null_geometries", drop_null_geometries, {}),
                ("remove_duplicate_vertices", remove_duplicate_vertices, {}),
                ("make_geometries_valid", make_geometries_valid, {}),
            ]
        )

    for name in list_custom_repairs():
        ordered_repairs.append((name, _CUSTOM_REPAIRS[name], {}))

    if profile is not None:
        enabled = {item.lower() for item in profile.enabled_repairs}
        disabled = {item.lower() for item in profile.disabled_repairs}
        filtered: list[tuple[str, Any, dict[str, Any]]] = []
        for name, func, options in ordered_repairs:
            normalized_name = name.lower()
            if enabled and normalized_name not in enabled:
                continue
            if normalized_name in disabled:
                continue
            overrides = profile.repair_options.get(name) or profile.repair_options.get(normalized_name) or {}
            filtered.append((name, func, {**options, **overrides}))
        ordered_repairs = filtered

    fixed = layer.copy()
    for _name, func, options in ordered_repairs:
        fixed = func(fixed, **options)
    return fixed


__all__ = [
    "apply_basic_geometry_fixes",
    "apply_repair_plan",
    "RepairProfile",
    "clear_custom_repairs",
    "drop_null_geometries",
    "list_custom_repairs",
    "make_geometries_valid",
    "remove_duplicate_vertices",
    "register_custom_repair",
]
