from __future__ import annotations

from typing import Any

from .thresholds import BoundaryThresholds, default_boundary_thresholds


def build_boundaries_context(layer: Any, *, thresholds: BoundaryThresholds | None = None) -> dict[str, Any]:
    resolved = thresholds or default_boundary_thresholds()
    return {
        "min_gap_area": resolved.min_gap_area,
        "mismatch_ratio_threshold": resolved.mismatch_ratio_threshold,
    }


def boundaries_problem_policies() -> dict[str, dict[str, Any]]:
    return {
        "self_intersection": {"severity": "critical", "confidence": "high", "actionable": True, "priority_score": 9},
        "polygon_overlap_same_layer": {"severity": "critical", "confidence": "high", "actionable": True, "priority_score": 9},
        "polygon_gap_same_layer": {"severity": "high", "confidence": "medium", "actionable": True, "priority_score": 8},
        "feature_within_feature": {"severity": "high", "confidence": "medium", "actionable": True, "priority_score": 8},
        "boundary_mismatch_against_reference": {
            "severity": "high",
            "confidence": "high",
            "actionable": True,
            "priority_score": 8,
        },
        "coordinate_precision_not_fit_for_use": {
            "suppress": True,
            "suppression_reason": "Boundary profile suppresses generic precision warnings by default.",
        },
        "inappropriate_xy_tolerance": {
            "suppress": True,
            "suppression_reason": "Boundary profile suppresses generic XY tolerance warnings by default.",
        },
    }


__all__ = ["boundaries_problem_policies", "build_boundaries_context"]
