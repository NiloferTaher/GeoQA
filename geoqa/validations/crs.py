from __future__ import annotations

from typing import Any

from .base import ValidationIssue, build_issue


def _normalize_crs(crs: Any) -> str | None:
    if crs is None:
        return None

    try:
        from pyproj import CRS

        return CRS.from_user_input(crs).to_string()
    except Exception:
        try:
            return crs.to_string()
        except Exception:
            return str(crs)


def missing_crs(layer: Any) -> list[ValidationIssue]:
    """Return a dataset-level issue when the layer does not define a CRS."""
    if getattr(layer, "crs", None) is None:
        return [
            build_issue(
                "missing_spatial_reference",
                description="The layer does not have a spatial reference or CRS assigned.",
                solution_hint="Define the correct CRS for the layer before projection, overlay, or analysis.",
            )
        ]
    return []


def invalid_crs(layer: Any, expected_crs: Any) -> list[ValidationIssue]:
    """Return a dataset-level issue when the layer CRS does not match the expected CRS."""
    actual_crs = getattr(layer, "crs", None)
    if actual_crs is None:
        return []

    normalized_actual = _normalize_crs(actual_crs)
    normalized_expected = _normalize_crs(expected_crs)
    if normalized_actual != normalized_expected:
        return [
            build_issue(
                "invalid_spatial_reference",
                description=f"The layer CRS is {normalized_actual}, but the expected CRS is {normalized_expected}.",
                solution_hint="Reproject or redefine the layer so it uses the expected authoritative CRS.",
            )
        ]
    return []


__all__ = ["invalid_crs", "missing_crs"]
