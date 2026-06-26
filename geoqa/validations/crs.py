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


def _parse_crs(crs: Any) -> Any | None:
    if crs is None:
        return None
    try:
        from pyproj import CRS

        return CRS.from_user_input(crs)
    except Exception:
        return None


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


def invalid_crs(layer: Any, expected_crs: Any = None) -> list[ValidationIssue]:
    """Return a dataset-level issue when CRS is unreadable or violates an explicit expected CRS."""
    actual_crs = getattr(layer, "crs", None)
    if actual_crs is None:
        return []

    parsed_actual = _parse_crs(actual_crs)
    normalized_actual = parsed_actual.to_string() if parsed_actual is not None else _normalize_crs(actual_crs)
    if parsed_actual is None:
        return [
            build_issue(
                "invalid_spatial_reference",
                description="The layer CRS could not be parsed or used safely.",
                solution_hint="Confirm the authoritative CRS with the data owner before redefining or reprojecting the layer.",
            )
        ]

    if expected_crs is None:
        return []

    parsed_expected = _parse_crs(expected_crs)
    normalized_expected = parsed_expected.to_string() if parsed_expected is not None else _normalize_crs(expected_crs)
    if parsed_expected is None:
        return [
            build_issue(
                "invalid_spatial_reference",
                description=f"The configured expected CRS could not be parsed: {normalized_expected}.",
                solution_hint="Correct the expected CRS configuration before auditing this layer.",
            )
        ]

    if not parsed_actual.equals(parsed_expected):
        issue = build_issue(
            "invalid_spatial_reference",
            description=f"The layer CRS is {normalized_actual}, but the configured expected CRS is {normalized_expected}.",
            solution_hint="Confirm the authoritative CRS with the data owner before redefining or reprojecting the layer.",
        )
        issue.provenance = {
            **(issue.provenance or {}),
            "source_crs": normalized_actual,
            "expected_crs": normalized_expected,
            "transformation_available": True,
        }
        return [issue]
    return []


__all__ = ["invalid_crs", "missing_crs"]
