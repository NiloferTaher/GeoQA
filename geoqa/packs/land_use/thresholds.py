from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class LandUseThresholds:
    valid_domain: frozenset[int] = field(default_factory=lambda: frozenset({1, 2, 3}))


def default_land_use_thresholds() -> LandUseThresholds:
    return LandUseThresholds()


__all__ = ["LandUseThresholds", "default_land_use_thresholds"]
