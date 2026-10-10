from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from geoqa.validations.base import ValidationIssue


@dataclass(slots=True)
class GeoQAPlugin:
    """
    Minimal plugin contract for additive domain- or client-specific rules.

    Plugins are intentionally narrow:
    - ``applies_to`` decides whether the plugin should run on a layer
    - ``validate`` returns additional ``ValidationIssue`` objects
    - ``fix`` optionally applies a conservative cleanup
    """

    name: str
    description: str = ""
    version: str = "1"

    def applies_to(self, gdf: Any) -> bool:
        """Return ``True`` when this plugin should run for the supplied layer."""
        return True

    def validate(self, gdf: Any) -> list[ValidationIssue]:
        """Return additional deterministic validation issues for the supplied layer."""
        raise NotImplementedError

    def fix(self, gdf: Any) -> Any:
        """Apply an optional conservative cleanup and return the updated layer."""
        return gdf


__all__ = ["GeoQAPlugin"]
