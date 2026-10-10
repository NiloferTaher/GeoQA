from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Any


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) > 0


@dataclass(slots=True, frozen=True)
class WaterNetworkThresholds:
    snap_tolerance: float = 50.0
    near_miss_tolerance: float = 100.0
    min_length: float = 0.1
    min_angle_degrees: float = 12.5
    allowed_terminal_values: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "service",
                "service_endpoint",
                "service_lateral",
                "service_connection",
                "customer_connection",
                "hydrant",
                "meter",
                "valve_stub",
            }
        )
    )
    diameter_domain: Callable[[Any], bool] = _positive_number
    material_domain: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"di", "ci", "pvc", "hdpe", "steel", "copper", "ac", "ductile_iron", "unknown"}
        )
    )
    status_domain: frozenset[str] = field(
        default_factory=lambda: frozenset({"active", "inactive", "abandoned", "planned", "retired", "unknown"})
    )


def default_water_network_thresholds() -> WaterNetworkThresholds:
    return WaterNetworkThresholds()


__all__ = ["WaterNetworkThresholds", "default_water_network_thresholds"]
