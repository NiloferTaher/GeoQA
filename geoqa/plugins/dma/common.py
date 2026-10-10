from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from shapely.geometry.base import BaseGeometry


_DMA_NAME_CANDIDATES = (
    "DMA",
    "DMA_NAME",
    "DMA_NM",
    "DMA_LABEL",
    "name",
    "Name",
    "NAME",
    "district",
    "District",
    "zone",
    "Zone",
)

_CREATED_CANDIDATES = ("created", "created_at", "creation_date", "date_created", "timestamp")
_ADMIN_CANDIDATES = ("admin", "admin_name", "office", "district", "region", "governorate")


@dataclass(slots=True, frozen=True)
class DmaLayerHints:
    name_field: str | None
    created_field: str | None
    admin_field: str | None
    looks_like_dma_layer: bool
    polygon_like: bool


def _normalize_column_match(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        matched = lowered.get(candidate.lower())
        if matched:
            return matched
    return None


def _first_regex_column(columns: list[str], patterns: tuple[str, ...]) -> str | None:
    for column in columns:
        lowered = column.lower()
        for pattern in patterns:
            if re.search(pattern, lowered):
                return column
    return None


def detect_dma_layer_hints(gdf: Any) -> DmaLayerHints:
    columns = [str(column) for column in getattr(gdf, "columns", [])]
    source_path = str((getattr(gdf, "attrs", {}) or {}).get("source_path", "")).lower()
    name_field = _normalize_column_match(columns, _DMA_NAME_CANDIDATES) or _first_regex_column(
        columns,
        (r"dma", r"\bname\b"),
    )
    created_field = _normalize_column_match(columns, _CREATED_CANDIDATES) or _first_regex_column(
        columns,
        (r"created", r"date", r"time"),
    )
    admin_field = _normalize_column_match(columns, _ADMIN_CANDIDATES) or _first_regex_column(
        columns,
        (r"admin", r"office", r"district", r"region", r"govern"),
    )
    polygon_like = _is_polygon_layer(gdf)
    looks_like_dma_layer = bool(
        polygon_like
        and (
            "dma" in source_path
            or any("dma" in column.lower() for column in columns)
            or (name_field is not None and "dma" in name_field.lower())
        )
    )
    return DmaLayerHints(
        name_field=name_field,
        created_field=created_field,
        admin_field=admin_field,
        looks_like_dma_layer=looks_like_dma_layer,
        polygon_like=polygon_like,
    )


def _is_polygon_layer(gdf: Any) -> bool:
    if "geometry" not in getattr(gdf, "columns", []):
        return False
    try:
        for geometry in gdf["geometry"]:
            if geometry is None or getattr(geometry, "is_empty", False):
                continue
            geom_type = getattr(geometry, "geom_type", "")
            return geom_type in {"Polygon", "MultiPolygon"}
    except Exception:
        return False
    return False


def normalize_dma_key(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    normalized = re.sub(r"[_\-\s]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9 ]+", "", normalized)
    return normalized.strip()


def safe_geometry(geometry: BaseGeometry | None) -> BaseGeometry | None:
    if geometry is None:
        return None
    if getattr(geometry, "is_empty", False):
        return None
    try:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
    except Exception:
        return geometry
    return geometry


def equalsish(left: BaseGeometry | None, right: BaseGeometry | None) -> bool:
    if left is None or right is None:
        return False
    try:
        if left.equals(right):
            return True
    except Exception:
        return False
    try:
        return left.symmetric_difference(right).area == 0
    except Exception:
        return False


def overlap_fraction(smaller: BaseGeometry | None, larger: BaseGeometry | None) -> float:
    if smaller is None or larger is None:
        return 0.0
    try:
        if smaller.area <= 0:
            return 0.0
        return float(smaller.intersection(larger).area / smaller.area)
    except Exception:
        return 0.0


def pick_best_index(left_index: Any, right_index: Any) -> Any:
    try:
        return min(left_index, right_index)
    except Exception:
        return left_index


def row_value(row: Any, key: str | None, default: Any = None) -> Any:
    if not key:
        return default
    try:
        return row[key]
    except Exception:
        return getattr(row, key, default)


def dissolve_by_normalized_name(gdf: Any, name_field: str) -> Any:
    import geopandas as gpd

    working = gdf.copy()
    working["_geoqa_dma_norm_name"] = working[name_field].map(normalize_dma_key)
    output_rows: list[dict[str, Any]] = []
    for _, group in working.groupby("_geoqa_dma_norm_name", dropna=False):
        if group.empty:
            continue
        largest_index = group.geometry.area.fillna(0).idxmax()
        base_row = dict(group.loc[largest_index].drop(labels=["_geoqa_dma_norm_name"]))
        geometries = [safe_geometry(geom) for geom in group.geometry]
        geometries = [geom for geom in geometries if geom is not None]
        if not geometries:
            continue
        union_geometry = geometries[0]
        for geometry in geometries[1:]:
            union_geometry = union_geometry.union(geometry)
        base_row["geometry"] = union_geometry
        output_rows.append(base_row)
    return gpd.GeoDataFrame(output_rows, geometry="geometry", crs=getattr(gdf, "crs", None))


__all__ = [
    "DmaLayerHints",
    "detect_dma_layer_hints",
    "dissolve_by_normalized_name",
    "equalsish",
    "normalize_dma_key",
    "overlap_fraction",
    "pick_best_index",
    "row_value",
    "safe_geometry",
]
