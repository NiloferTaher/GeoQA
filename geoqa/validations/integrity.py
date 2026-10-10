from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import ValidationIssue, build_issue


def missing_spatial_index(layer: Any) -> list[ValidationIssue]:
    """Return a dataset-level issue when a spatial index is absent or explicitly marked stale."""
    attrs = getattr(layer, "attrs", {})
    index_state = attrs.get("spatial_index_status", attrs.get("index_status"))
    has_sindex = getattr(layer, "has_sindex", None)

    if index_state in {"missing", "stale", "needs_rebuild"} or has_sindex is False:
        return [
            build_issue(
                "missing_or_stale_spatial_index",
                description="The layer does not appear to have a usable spatial index.",
                solution_hint="Create or rebuild the spatial index before running large spatial queries or overlays.",
            )
        ]
    return []


def outdated_index(layer: Any) -> list[ValidationIssue]:
    """Return a dataset-level issue when layer metadata marks indexes as outdated."""
    attrs = getattr(layer, "attrs", {})
    index_state = attrs.get("spatial_index_status", attrs.get("index_status"))
    if index_state in {"outdated", "stale", "needs_rebuild"}:
        return [
            build_issue(
                "outdated_attribute_or_spatial_indexes",
                description="Layer metadata indicates that attribute or spatial indexes are outdated.",
                solution_hint="Rebuild the affected indexes as part of dataset maintenance.",
            )
        ]
    return []


def _load_geojson_payload(geojson_input: Any) -> dict[str, Any] | None:
    if isinstance(geojson_input, dict):
        return geojson_input
    if isinstance(geojson_input, str):
        try:
            path = Path(geojson_input)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        try:
            return json.loads(geojson_input)
        except json.JSONDecodeError:
            return None
    return None


def non_rfc7946_geojson(geojson_input: Any) -> list[ValidationIssue]:
    """Return a dataset-level issue when GeoJSON content violates common RFC 7946 expectations."""
    payload = _load_geojson_payload(geojson_input)
    if payload is not None:
        if "crs" in payload:
            return [
                build_issue(
                    "non_rfc7946_geojson_output",
                    description="GeoJSON contains a legacy 'crs' member, which is not part of RFC 7946 output.",
                    solution_hint="Rewrite the GeoJSON using RFC 7946-compliant export settings.",
                )
            ]
        return []

    crs = getattr(geojson_input, "crs", None)
    if crs is None:
        return []

    try:
        epsg = crs.to_epsg()
    except Exception:
        epsg = None
    crs_string = ""
    try:
        crs_string = crs.to_string().upper()
    except Exception:
        crs_string = str(crs).upper()

    if epsg not in {None, 4326} and "WGS84" not in crs_string and "WGS 84" not in crs_string:
        return [
            build_issue(
                "non_rfc7946_geojson_output",
                description="GeoJSON output uses a non-WGS84 CRS and may not comply with RFC 7946 expectations.",
                solution_hint="Rewrite the export with RFC 7946-compliant settings and WGS84 coordinates.",
            )
        ]
    return []


__all__ = ["missing_spatial_index", "non_rfc7946_geojson", "outdated_index"]
