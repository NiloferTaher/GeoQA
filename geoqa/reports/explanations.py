from __future__ import annotations

from typing import Any


_TEMPLATES: dict[str, dict[str, str]] = {
    "duplicate_geometry_same_layer": {
        "what": "Multiple records share exactly the same geometry.",
        "why": "This may indicate duplicate assets, repeated imports, or multiple records representing one physical location.",
        "action": "Review the affected records and decide whether they should be merged, removed, or linked through a shared parent or location ID.",
    },
    "feature_not_split_at_intersection": {
        "what": "A line crosses another line at an interior point without a network junction.",
        "why": "Network analysis may treat this as a crossing instead of a connected junction, affecting tracing and connectivity.",
        "action": "Split the lines at the valid junction or document that the crossing is intentional.",
    },
    "line_intersection_same_layer": {
        "what": "A line intersects another line where only endpoint connections are expected.",
        "why": "Network tracing may treat the crossing incorrectly if the junction is not modeled clearly.",
        "action": "Review the crossing and split or document the feature where appropriate.",
    },
    "invalid_spatial_reference": {
        "what": "The layer CRS differs from the configured expected CRS or cannot be parsed safely.",
        "why": "CRS mismatch can cause features to appear in the wrong location or produce incorrect distance and area results.",
        "action": "Confirm the authoritative CRS with the data owner before redefining or reprojecting the layer.",
    },
    "missing_spatial_reference": {
        "what": "The layer has no declared coordinate reference system.",
        "why": "Without a CRS, GIS tools cannot reliably locate, measure, or overlay the data.",
        "action": "Confirm the authoritative CRS with the data owner and define it before analysis.",
    },
    "display_reprojection_required": {
        "what": "The layer uses a valid projected CRS and was temporarily reprojected for web map display.",
        "why": "This is normal for many engineering datasets and is not automatically a data error.",
        "action": "Keep the source CRS unchanged unless the data owner confirms a different authoritative CRS.",
    },
}


def explanation_for(problem_name: str, fallback_description: str = "", fallback_action: str = "") -> dict[str, str]:
    template = _TEMPLATES.get(problem_name)
    if template is not None:
        return dict(template)
    return {
        "what": fallback_description or problem_name.replace("_", " "),
        "why": "This finding should be reviewed before downstream GIS analysis or delivery.",
        "action": fallback_action or "Review the affected records and update the authoritative data only after confirmation.",
    }


def enrich_issue_row(row: dict[str, Any]) -> dict[str, Any]:
    explanation = explanation_for(
        str(row.get("problem_name", "")),
        fallback_description=str(row.get("description", "") or ""),
        fallback_action=str(row.get("solution_hint", "") or ""),
    )
    return {
        **row,
        "what_geoqa_found": explanation["what"],
        "why_it_matters": explanation["why"],
        "recommended_action": explanation["action"],
    }


__all__ = ["enrich_issue_row", "explanation_for"]
