"""Errors-only GeoJSON export for web-GIS consumption.

Produces a ``FeatureCollection`` of *error* features (one per actionable
validation issue that carries geometry) with Atlas-compatible ``Issue``
properties, ready to drop into a MapLibre map. This is the bridge that lets a
researcher view findings on a web site instead of opening QGIS or Folium.

The emitted properties match ``apps/atlas/src/types.ts`` (``Issue``) and the
Python ``ValidationIssue`` fields exactly, so the same file powers the map, the
Atlas UI, and any downstream statistics.
"""

from __future__ import annotations

from typing import Any, Iterable

from .explanations import explanation_for


_WGS84 = "EPSG:4326"


def _issue_properties(issue: Any) -> dict[str, Any]:
    """Map a ValidationIssue onto the Atlas ``Issue`` property contract."""
    if hasattr(issue, "to_dict"):
        row = dict(issue.to_dict())
    else:
        row = dict(issue)

    explanation = explanation_for(
        str(row.get("problem_name", "")),
        fallback_description=str(row.get("description", "") or ""),
        fallback_action=str(row.get("solution_hint", "") or ""),
    )

    geometry = row.pop("geometry", None)
    properties: dict[str, Any] = {
        "issue_id": row.get("issue_id"),
        "problem_name": row.get("problem_name"),
        "severity": row.get("severity"),
        "description": row.get("description"),
        "solution_hint": row.get("solution_hint"),
        "feature_id": row.get("feature_id"),
        "geometry_type": (geometry or {}).get("type") if isinstance(geometry, dict) else None,
        "validator_name": row.get("validator_name"),
        "validator_version": row.get("validator_version"),
        "issue_class": row.get("issue_class"),
        "iso_category": row.get("iso_category"),
        "confidence": row.get("confidence"),
        "actionable": bool(row.get("actionable", True)),
        "priority_score": row.get("priority_score"),
        "suppressed": bool(row.get("suppression")),
        # Human-readable fields already used by Atlas IssueDrawer / popups.
        "what_geoqa_found": explanation["what"],
        "why_it_matters": explanation["why"],
        "recommended_action": explanation["action"],
    }
    for key, value in row.items():
        if key not in properties:
            properties[key] = value
    return properties


def _clean_geometry(geometry: Any) -> dict[str, Any] | None:
    """Accept only usable GeoJSON geometry objects."""
    if not isinstance(geometry, dict):
        return None
    gtype = geometry.get("type")
    if gtype not in {"Point", "MultiPoint", "LineString", "MultiLineString",
                     "Polygon", "MultiPolygon", "GeometryCollection"}:
        return None
    if gtype == "GeometryCollection" and "geometries" not in geometry:
        return None
    return geometry


def issues_to_geojson(
    issues: Iterable[Any],
    *,
    keep_non_actionable: bool = True,
) -> dict[str, Any]:
    """Convert validation issues into an errors-only GeoJSON FeatureCollection.

    Only issues that carry usable geometry can be mapped; the rest are skipped
    (they remain available in the CSV/JSON reports). Suppressed issues are
    included but flagged so the map can grey them out, which helps a researcher
    see what was deliberately hidden.

    Args:
        issues: Iterable of ValidationIssue (or dicts with the same keys).
        keep_non_actionable: When False, drop issues flagged ``actionable=False``.

    Returns:
        A GeoJSON ``FeatureCollection`` dict (WGS84 per RFC 7946).
    """
    features: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    for issue in issues:
        row = issue.to_dict() if hasattr(issue, "to_dict") else dict(issue)
        if not keep_non_actionable and not bool(row.get("actionable", True)):
            continue
        geometry = _clean_geometry(row.get("geometry"))
        if geometry is None:
            unmapped.append(_issue_properties(issue))
            continue
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": _issue_properties(issue),
        })

    collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "name": "geoqa_errors",
        "crs": {"type": "name", "properties": {"name": _WGS84}},
        "features": features,
    }
    # Foreign member: keeps attribute-only findings recoverable for analysis
    # without breaking RFC 7946 validity. GeoJSON readers ignore it.
    collection["geoqa"] = {
        "unmapped_count": len(unmapped),
        "unmapped_issues": unmapped,
    }
    return collection


def errors_summary(geojson: dict[str, Any]) -> dict[str, Any]:
    """Severity/problem rollup for a GeoJSON produced by ``issues_to_geojson``."""
    severity: dict[str, int] = {}
    problem: dict[str, int] = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        sev = str(props.get("severity", "unknown"))
        prob = str(props.get("problem_name", "unknown"))
        severity[sev] = severity.get(sev, 0) + 1
        problem[prob] = problem.get(prob, 0) + 1
    return {
        "feature_count": len(geojson.get("features", [])),
        "by_severity": dict(sorted(severity.items(), key=lambda kv: -kv[1])),
        "by_problem": dict(sorted(problem.items(), key=lambda kv: -kv[1])),
    }


__all__ = ["errors_summary", "issues_to_geojson"]