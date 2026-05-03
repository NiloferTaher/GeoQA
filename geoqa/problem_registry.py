from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

VALIDATION_RULE_VERSION = "2026.03"

_SUPPLEMENTAL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "dma_same_name_equal_geometry": {
        "category": "topology",
        "description": "Two same-name DMA polygons are geometrically equal and likely duplicate one another.",
        "severity": "high",
        "repair_hint": "Inspect the duplicate same-name polygons and dissolve or retire the redundant feature if the duplication is unintended.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "dma_same_name_nested_polygon": {
        "category": "topology",
        "description": "Two same-name DMA polygons are almost fully nested, indicating duplicate or fragmented coverage.",
        "severity": "high",
        "repair_hint": "Review the nested same-name polygons and dissolve or remove the smaller duplicate if appropriate.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "dma_cross_name_equal_geometry": {
        "category": "topology",
        "description": "Two different DMA names map to effectively the same polygon geometry.",
        "severity": "high",
        "repair_hint": "Resolve the naming conflict before deciding which geometry or label should be retained.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "dma_cross_name_nested_polygon": {
        "category": "topology",
        "description": "A DMA polygon is nearly fully nested inside a differently named DMA polygon.",
        "severity": "high",
        "repair_hint": "Inspect the naming conflict and nested coverage before merging, subtracting, or retiring one polygon.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "dma_cross_name_overlap": {
        "category": "topology",
        "description": "Two differently named DMA polygons partially overlap.",
        "severity": "high",
        "repair_hint": "Review which polygon should own the overlap and resolve it using subtraction or a controlled merge.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "dma_multipart_polygon": {
        "category": "topology",
        "description": "A DMA is split across multiple polygon parts after explode(), indicating fragmentation or multipart coverage.",
        "severity": "medium",
        "repair_hint": "Inspect whether the same-name polygon fragments should be dissolved into a single retained feature.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "below_minimum_feature_length": {
        "category": "geometry",
        "description": "A line feature is shorter than the configured domain minimum length.",
        "severity": "medium",
        "repair_hint": "Review whether the feature is a drafting artifact, should be merged, or requires a lower domain threshold.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "sharp_angle_cutback": {
        "category": "geometry",
        "description": "A line or polygon contains a suspiciously sharp angle cutback or spike.",
        "severity": "medium",
        "repair_hint": "Inspect the digitized geometry for spikes, overshoots, or cutbacks and simplify or redigitize if needed.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "line_dangle": {
        "category": "topology",
        "description": "A line endpoint is dangling where the active profile expects network connectivity.",
        "severity": "high",
        "repair_hint": "Review endpoint connectivity, service-endpoint rules, and intended network termination behavior.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "duplicate_geometry_same_layer": {
        "category": "topology",
        "description": "A feature duplicates the geometry of another feature in the same layer.",
        "severity": "medium",
        "repair_hint": "Review whether duplicate features should be merged, deleted, or linked by shared identifiers.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "polygon_gap_same_layer": {
        "category": "topology",
        "description": "An interior gap exists within same-layer polygon coverage.",
        "severity": "high",
        "repair_hint": "Review adjacent polygon boundaries and close unintended gaps or document valid voids.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "feature_not_split_at_intersection": {
        "category": "topology",
        "description": "A line crosses another feature at an interior point without being split into a network node.",
        "severity": "high",
        "repair_hint": "Split the intersecting features at the node or document why the crossing is valid in this network.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "isolated_network_segment": {
        "category": "topology",
        "description": "A line segment is isolated from the surrounding network at both endpoints.",
        "severity": "high",
        "repair_hint": "Review whether the segment should connect to nearby infrastructure or be classified as a valid standalone feature.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "suspicious_near_miss_endpoints": {
        "category": "topology",
        "description": "Endpoints are close enough to suggest an unintended near miss but are not snapped together.",
        "severity": "medium",
        "repair_hint": "Inspect nearby endpoints and snap them if the separation is unintended or below network tolerance.",
        "issue_class": "data_issue",
        "default_confidence": "medium",
        "default_actionable": True,
    },
    "unsnapped_endpoints_within_tolerance": {
        "category": "topology",
        "description": "Disconnected endpoints fall within the configured snap tolerance.",
        "severity": "high",
        "repair_hint": "Snap the endpoints or document why the disconnected near match is valid.",
        "issue_class": "data_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
    "runtime_limit_exceeded": {
        "category": "runtime",
        "description": "Validation stopped early because the configured runtime ceiling was reached.",
        "severity": "medium",
        "repair_hint": "Rerun with a larger runtime budget, narrower profile, or smaller/adaptive chunks.",
        "issue_class": "runtime_issue",
        "default_confidence": "high",
        "default_actionable": True,
    },
}


@dataclass(slots=True, frozen=True)
class ProblemDefinition:
    problem_name: str
    category: str
    description: str
    example: str | None
    source_name: str | None
    source_link: str | None
    default_severity: str
    repair_hint: str
    iso_category: str | None = None
    issue_class: str = "data_issue"
    default_confidence: str = "medium"
    default_actionable: bool = True


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "raw_problems_with_sources.json"


@lru_cache(maxsize=1)
def _raw_catalog() -> list[dict[str, Any]]:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


def _iso_category(problem_name: str, category: str) -> str | None:
    by_problem = {
        "self_intersection": "Logical Consistency",
        "below_minimum_feature_length": "Logical Consistency",
        "sharp_angle_cutback": "Logical Consistency",
        "coordinate_precision_not_fit_for_use": "Positional Accuracy",
        "null_geometry": "Completeness",
        "missing_spatial_reference": "Positional Accuracy",
        "invalid_spatial_reference": "Positional Accuracy",
        "line_dangle": "Logical Consistency",
        "duplicate_geometry_same_layer": "Logical Consistency",
        "polygon_gap_same_layer": "Logical Consistency",
        "feature_not_split_at_intersection": "Logical Consistency",
        "isolated_network_segment": "Logical Consistency",
        "suspicious_near_miss_endpoints": "Logical Consistency",
        "unsnapped_endpoints_within_tolerance": "Logical Consistency",
    }
    if problem_name in by_problem:
        return by_problem[problem_name]
    by_category = {
        "geometry": "Logical Consistency",
        "topology": "Logical Consistency",
        "accuracy": "Positional Accuracy",
        "crs": "Positional Accuracy",
        "attributes": "Thematic Accuracy",
        "metadata": "Completeness",
        "integrity": "Logical Consistency",
    }
    return by_category.get(category)


def _default_confidence(problem_name: str, category: str) -> str:
    lower_name = problem_name.lower()
    if "coordinate_precision" in lower_name or "xy_tolerance" in lower_name:
        return "low"
    if category in {"geometry", "topology", "crs"}:
        return "high"
    if category in {"integrity", "attributes"}:
        return "medium"
    return "medium"


def _default_actionable(problem_name: str, category: str) -> bool:
    lower_name = problem_name.lower()
    if "coordinate_precision" in lower_name or "xy_tolerance" in lower_name:
        return False
    if category in {"geometry", "topology", "crs", "integrity"}:
        return True
    return True


@lru_cache(maxsize=1)
def problem_definitions() -> dict[str, ProblemDefinition]:
    definitions: dict[str, ProblemDefinition] = {}
    for entry in _raw_catalog():
        name = str(entry.get("problem_name", "")).strip()
        if not name:
            continue
        category = str(entry.get("category", "")).strip().lower()
        definitions[name] = ProblemDefinition(
            problem_name=name,
            category=category,
            description=str(entry.get("description", name.replace("_", " "))),
            example=str(entry.get("example")) if entry.get("example") else None,
            source_name=str(entry.get("source_name")) if entry.get("source_name") else None,
            source_link=str(entry.get("source_link")) if entry.get("source_link") else None,
            default_severity=str(entry.get("severity", "medium")),
            repair_hint=str(
                entry.get(
                    "repair_hint",
                    "Inspect the record and correct the issue using GIS validation or data-cleaning tools.",
                )
            ),
            iso_category=_iso_category(name, category),
            default_confidence=_default_confidence(name, category),
            default_actionable=_default_actionable(name, category),
        )
    for name, entry in _SUPPLEMENTAL_DEFINITIONS.items():
        category = str(entry.get("category", "")).strip().lower()
        definitions[name] = ProblemDefinition(
            problem_name=name,
            category=category,
            description=str(entry.get("description", name.replace("_", " "))),
            example=str(entry.get("example")) if entry.get("example") else None,
            source_name=str(entry.get("source_name")) if entry.get("source_name") else None,
            source_link=str(entry.get("source_link")) if entry.get("source_link") else None,
            default_severity=str(entry.get("severity", "medium")),
            repair_hint=str(entry.get("repair_hint", "Inspect and correct the issue.")),
            iso_category=_iso_category(name, category),
            issue_class=str(entry.get("issue_class", "data_issue")),
            default_confidence=str(entry.get("default_confidence", _default_confidence(name, category))),
            default_actionable=bool(entry.get("default_actionable", _default_actionable(name, category))),
        )
    return definitions


def get_problem_definition(problem_name: str) -> ProblemDefinition | None:
    return problem_definitions().get(problem_name)


def list_problem_definitions(*, category: str | None = None) -> list[ProblemDefinition]:
    values = list(problem_definitions().values())
    if category is None:
        return sorted(values, key=lambda item: item.problem_name)
    normalized = category.strip().lower()
    return sorted((item for item in values if item.category == normalized), key=lambda item: item.problem_name)


__all__ = [
    "ProblemDefinition",
    "VALIDATION_RULE_VERSION",
    "get_problem_definition",
    "list_problem_definitions",
    "problem_definitions",
]
