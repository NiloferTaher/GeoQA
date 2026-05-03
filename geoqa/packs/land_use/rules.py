from __future__ import annotations

from typing import Any

from .thresholds import LandUseThresholds, default_land_use_thresholds


def build_land_use_context(layer: Any, *, thresholds: LandUseThresholds | None = None) -> dict[str, Any]:
    columns = {str(column) for column in getattr(layer, "columns", [])}
    field = next((candidate for candidate in ("land_use", "landuse", "zoning") if candidate in columns), None)
    resolved = thresholds or default_land_use_thresholds()
    return {
        "domain_field": field,
        "valid_domain": set(resolved.valid_domain) if field is not None else None,
    }


def land_use_problem_policies() -> dict[str, dict[str, Any]]:
    return {
        "domain_violation": {"severity": "high", "confidence": "high", "actionable": True, "priority_score": 8},
        "polygon_overlap_same_layer": {"severity": "high", "confidence": "high", "actionable": True, "priority_score": 8},
    }


__all__ = ["build_land_use_context", "land_use_problem_policies"]
