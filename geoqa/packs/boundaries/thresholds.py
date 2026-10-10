from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BoundaryThresholds:
    min_gap_area: float = 0.0
    mismatch_ratio_threshold: float = 0.02


def default_boundary_thresholds() -> BoundaryThresholds:
    return BoundaryThresholds()


__all__ = ["BoundaryThresholds", "default_boundary_thresholds"]
