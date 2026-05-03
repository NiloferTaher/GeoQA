from __future__ import annotations

from collections import Counter
from typing import Any

from .schema import WaterNetworkSchemaHints, detect_water_network_schema
from .thresholds import WaterNetworkThresholds, default_water_network_thresholds


def build_water_network_context(
    layer: Any,
    *,
    thresholds: WaterNetworkThresholds | None = None,
) -> dict[str, Any]:
    schema = detect_water_network_schema(layer)
    resolved_thresholds = thresholds or default_water_network_thresholds()
    return {
        "required_fields": list(schema.required_fields),
        "unique_field": schema.unique_field,
        "role_field": schema.role_field,
        "allowed_endpoint_values": set(resolved_thresholds.allowed_terminal_values),
        "allowed_terminal_values": set(resolved_thresholds.allowed_terminal_values),
        "snap_tolerance": resolved_thresholds.snap_tolerance,
        "near_miss_tolerance": resolved_thresholds.near_miss_tolerance,
        "min_length": resolved_thresholds.min_length,
        "min_angle_degrees": resolved_thresholds.min_angle_degrees,
        "diameter_field": schema.diameter_field,
        "diameter_domain": resolved_thresholds.diameter_domain if schema.diameter_field else None,
        "material_field": schema.material_field,
        "material_domain": set(resolved_thresholds.material_domain) if schema.material_field else None,
        "status_field": schema.status_field,
        "status_domain": set(resolved_thresholds.status_domain) if schema.status_field else None,
    }


def _linear_endpoint_pair(geometry: Any) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if geometry is None:
        return None

    def _coords(candidate: Any) -> list[Any] | None:
        try:
            coords = getattr(candidate, "coords", None)
        except Exception:
            return None
        if coords is None:
            return None
        try:
            items = list(coords)
        except Exception:
            return None
        if len(items) < 2:
            return None
        return items

    direct = _coords(geometry)
    if direct is not None:
        return direct[0], direct[-1]

    parts = getattr(geometry, "geoms", None)
    if parts is None:
        return None
    part_coords: list[list[Any]] = []
    try:
        for part in parts:
            coords = _coords(part)
            if coords is not None:
                part_coords.append(coords)
    except Exception:
        return None
    if not part_coords:
        return None
    return part_coords[0][0], part_coords[-1][-1]


def _normalize_endpoint(point: Any) -> tuple[float, float] | None:
    try:
        x, y = point
        return round(float(x), 9), round(float(y), 9)
    except Exception:
        return None


def summarize_water_network_layer(
    layer: Any,
    summary: dict[str, Any],
    *,
    thresholds: WaterNetworkThresholds | None = None,
) -> dict[str, Any]:
    schema = detect_water_network_schema(layer)
    resolved_thresholds = thresholds or default_water_network_thresholds()
    endpoint_degree: Counter[tuple[float, float]] = Counter()
    segment_count = 0
    multipart_segments = 0
    for _, row in layer.iterrows():
        geometry = row["geometry"] if "geometry" in row.index else None
        endpoints = _linear_endpoint_pair(geometry)
        if endpoints is None:
            continue
        segment_count += 1
        if getattr(geometry, "geom_type", None) == "MultiLineString":
            multipart_segments += 1
        start = _normalize_endpoint(endpoints[0])
        end = _normalize_endpoint(endpoints[1])
        if start is not None:
            endpoint_degree[start] += 1
        if end is not None:
            endpoint_degree[end] += 1

    junction_count = sum(1 for degree in endpoint_degree.values() if degree >= 3)
    terminal_endpoint_count = sum(1 for degree in endpoint_degree.values() if degree == 1)
    by_problem = summary.get("by_problem", {})
    enabled_checks = [
        name
        for name, field in (
            ("asset_id uniqueness", schema.asset_id_field),
            ("diameter domain", schema.diameter_field),
            ("material domain", schema.material_field),
            ("status domain", schema.status_field),
            ("endpoint role classification", schema.role_field),
        )
        if field is not None
    ]
    disabled_checks = [
        name
        for name, field in (
            ("asset_id uniqueness", schema.asset_id_field),
            ("diameter domain", schema.diameter_field),
            ("material domain", schema.material_field),
            ("status domain", schema.status_field),
            ("endpoint role classification", schema.role_field),
        )
        if field is None
    ]
    return {
        "pack": "water_network",
        "schema": {
            "strength": schema.schema_strength,
            "recognized_fields": list(schema.present_fields),
            "missing_hints": list(schema.missing_fields),
            "enabled_attribute_checks": enabled_checks,
            "disabled_attribute_checks": disabled_checks,
            "explanation": (
                "Schema-aware checks were enabled only for recognized water-network fields. "
                "Missing fields reduce attribute coverage but do not block linework or connectivity QA."
            ),
        },
        "thresholds": {
            "snap_tolerance": resolved_thresholds.snap_tolerance,
            "near_miss_tolerance": resolved_thresholds.near_miss_tolerance,
            "minimum_length": resolved_thresholds.min_length,
            "minimum_angle_degrees": resolved_thresholds.min_angle_degrees,
        },
        "network_metrics": {
            "segment_count": segment_count,
            "multipart_segment_count": multipart_segments,
            "junction_count": junction_count,
            "terminal_endpoint_count": terminal_endpoint_count,
        },
        "counts": {
            "disconnected_endpoints": int(by_problem.get("line_dangle", 0)),
            "isolated_segments": int(by_problem.get("isolated_network_segment", 0)),
            "near_miss_endpoints": int(by_problem.get("suspicious_near_miss_endpoints", 0)),
            "unsnapped_endpoints": int(by_problem.get("unsnapped_endpoints_within_tolerance", 0)),
            "self_intersections": int(by_problem.get("self_intersection", 0)),
            "short_segments": int(by_problem.get("below_minimum_feature_length", 0)),
            "sharp_cutbacks": int(by_problem.get("sharp_angle_cutback", 0)),
            "duplicate_geometries": int(by_problem.get("duplicate_geometry_same_layer", 0)),
            "intersection_splits_needed": int(by_problem.get("feature_not_split_at_intersection", 0)),
        },
        "limitations": [
            "Deterministic linework and schema QA only; no hydraulic simulation, demand modeling, or flow direction logic.",
            "Connectivity findings depend on configured tolerances and recognized endpoint-role fields.",
        ],
    }


def _base_problem_policies() -> dict[str, dict[str, Any]]:
    return {
        "self_intersection": {"severity": "high", "confidence": "high", "actionable": True, "priority_score": 9},
        "duplicate_vertex": {"severity": "medium", "confidence": "high", "actionable": True, "priority_score": 7},
        "below_minimum_feature_length": {
            "severity": "medium",
            "confidence": "medium",
            "actionable": True,
            "priority_score": 6,
        },
        "sharp_angle_cutback": {"severity": "medium", "confidence": "medium", "actionable": True, "priority_score": 6},
        "line_intersection_same_layer": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "duplicate_geometry_same_layer": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "feature_not_split_at_intersection": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "isolated_network_segment": {
            "severity": "high",
            "confidence": "medium",
            "actionable": True,
            "priority_score": 8,
        },
        "suspicious_near_miss_endpoints": {
            "severity": "medium",
            "confidence": "medium",
            "actionable": True,
            "priority_score": 7,
        },
        "unsnapped_endpoints_within_tolerance": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "line_dangle": {"severity": "high", "confidence": "medium", "actionable": True, "priority_score": 7},
        "non_unique_attribute": {"severity": "high", "confidence": "high", "actionable": True, "priority_score": 8},
        "null_attribute_in_required_field": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "domain_violation": {"severity": "medium", "confidence": "medium", "actionable": True, "priority_score": 6},
        "coordinate_precision_not_fit_for_use": {
            "severity": "low",
            "confidence": "low",
            "actionable": False,
            "priority_score": 2,
        },
        "inappropriate_xy_tolerance": {
            "severity": "low",
            "confidence": "low",
            "actionable": False,
            "priority_score": 2,
        },
    }


def water_network_problem_policies(variant: str) -> dict[str, dict[str, Any]]:
    policies = _base_problem_policies()
    normalized = variant.strip().lower()
    if normalized == "quick":
        policies["line_dangle"] = {
            "severity": "medium",
            "confidence": "medium",
            "actionable": True,
            "priority_score": 6,
        }
        policies["coordinate_precision_not_fit_for_use"] = {
            "suppress": True,
            "suppression_reason": "Water network quick suppresses generic precision noise by default.",
        }
        policies["inappropriate_xy_tolerance"] = {
            "suppress": True,
            "suppression_reason": "Water network quick suppresses generic XY tolerance warnings by default.",
        }
    elif normalized == "audit":
        policies["line_dangle"] = {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        }
        policies["coordinate_precision_not_fit_for_use"] = {
            "severity": "medium",
            "confidence": "medium",
            "actionable": False,
            "priority_score": 4,
        }
        policies["inappropriate_xy_tolerance"] = {
            "severity": "medium",
            "confidence": "medium",
            "actionable": False,
            "priority_score": 4,
        }
    return policies


__all__ = [
    "build_water_network_context",
    "summarize_water_network_layer",
    "water_network_problem_policies",
    "WaterNetworkSchemaHints",
    "detect_water_network_schema",
]
