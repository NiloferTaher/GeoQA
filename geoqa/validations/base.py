from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Any

from geoqa.problem_registry import VALIDATION_RULE_VERSION, get_problem_definition

_DEFAULT_ID_FIELDS = ("ID", "id", "fid", "FID", "objectid", "OBJECTID")

_SEVERITY_SCORES = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "low": 25,
}

_CONFIDENCE_SCORES = {
    "high": 1.0,
    "medium": 0.8,
    "low": 0.6,
}


@dataclass(slots=True)
class ValidationIssue:
    """
    Structured representation of a detected validation issue.

    This object is intentionally lightweight so it can be serialized directly into
    reports or transformed into AI- or GIS-oriented workflows later.
    """

    problem_name: str
    severity: str
    description: str
    solution_hint: str
    feature_id: Any
    geometry: Any | None = None
    issue_id: str | None = None
    validator_name: str | None = None
    validator_version: str | None = None
    issue_class: str = "data_issue"
    suppression: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    iso_category: str | None = None
    confidence: str = "medium"
    actionable: bool = True
    priority_score: int | None = None

    def __post_init__(self) -> None:
        if self.issue_id is None:
            self.issue_id = _build_issue_id(
                self.problem_name,
                self.feature_id,
                self.geometry,
                self.description,
            )
        if self.priority_score is None:
            self.priority_score = _compute_priority_score(
                severity=self.severity,
                confidence=self.confidence,
                actionable=self.actionable,
                issue_class=self.issue_class,
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert the issue to a report-friendly dictionary."""
        return {
            "problem_name": _json_safe_value(self.problem_name),
            "severity": _json_safe_value(self.severity),
            "description": _json_safe_value(self.description),
            "solution_hint": _json_safe_value(self.solution_hint),
            "feature_id": _json_safe_value(self.feature_id),
            "geometry": _json_safe_geometry(self.geometry),
            "issue_id": _json_safe_value(self.issue_id),
            "validation_rule_version": VALIDATION_RULE_VERSION,
            "validator_name": _json_safe_value(self.validator_name),
            "validator_version": _json_safe_value(self.validator_version),
            "issue_class": _json_safe_value(self.issue_class),
            "suppression": _json_safe_value(self.suppression),
            "provenance": _json_safe_value(self.provenance),
            "iso_category": _json_safe_value(self.iso_category),
            "confidence": _json_safe_value(self.confidence),
            "actionable": _json_safe_value(self.actionable),
            "priority_score": _json_safe_value(self.priority_score),
        }


def _compute_priority_score(
    *,
    severity: str,
    confidence: str,
    actionable: bool,
    issue_class: str,
) -> int:
    severity_score = _SEVERITY_SCORES.get(str(severity).lower(), 40)
    confidence_score = _CONFIDENCE_SCORES.get(str(confidence).lower(), 0.75)
    actionable_multiplier = 1.0 if actionable else 0.45
    issue_class_multiplier = 1.0
    if issue_class == "runtime_issue":
        issue_class_multiplier = 0.9
    elif issue_class == "warning":
        issue_class_multiplier = 0.75
    return int(round(severity_score * confidence_score * actionable_multiplier * issue_class_multiplier))


def _build_issue_id(problem_name: str, feature_id: Any, geometry: Any | None, description: str) -> str:
    geometry_token = _json_safe_geometry(geometry)
    payload = {
        "problem_name": problem_name,
        "feature_id": _json_safe_value(feature_id),
        "geometry": geometry_token,
        "description": description,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _json_safe_geometry(value: Any) -> Any:
    if value is None:
        return None
    try:
        wkt = getattr(value, "wkt", None)
        if isinstance(wkt, str):
            return wkt
    except Exception:
        pass
    try:
        geo = getattr(value, "__geo_interface__", None)
        if geo is not None:
            return geo
    except Exception:
        pass
    return _json_safe_value(value)


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_value(item) for item in value]
    try:
        return value.item()
    except Exception:
        return str(value)


def _row_has_key(row: Any, key: str) -> bool:
    index = getattr(row, "index", None)
    if index is not None:
        return key in index
    if isinstance(row, dict):
        return key in row
    return hasattr(row, key)


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if _row_has_key(row, key):
        try:
            return row[key]
        except Exception:
            return getattr(row, key, default)
    return default


def _row_geometry(row: Any) -> Any | None:
    return _row_value(row, "geometry")


def _feature_id(row: Any, index: Any = None) -> Any:
    for field_name in _DEFAULT_ID_FIELDS:
        if _row_has_key(row, field_name):
            return _row_value(row, field_name)
    return index


def build_issue(
    problem_name: str,
    *,
    row: Any | None = None,
    index: Any = None,
    feature_id: Any = None,
    geometry: Any | None = None,
    description: str | None = None,
    solution_hint: str | None = None,
    severity: str | None = None,
) -> ValidationIssue:
    """Create a validation issue, preferring catalog-backed metadata when available."""
    catalog_entry = get_problem_definition(problem_name)
    resolved_geometry = geometry if geometry is not None else (_row_geometry(row) if row is not None else None)
    resolved_feature_id = feature_id if feature_id is not None else (_feature_id(row, index) if row is not None else index)
    category = catalog_entry.category if catalog_entry is not None else ""
    iso_category = catalog_entry.iso_category if catalog_entry is not None else None
    return ValidationIssue(
        problem_name=problem_name,
        severity=severity or (catalog_entry.default_severity if catalog_entry is not None else "medium"),
        description=description or (catalog_entry.description if catalog_entry is not None else problem_name.replace("_", " ")),
        solution_hint=solution_hint
        or (
            catalog_entry.repair_hint
            if catalog_entry is not None
            else "Inspect the record and correct the issue using GIS validation or data-cleaning tools."
        ),
        feature_id=resolved_feature_id,
        geometry=resolved_geometry,
        validator_name=problem_name,
        validator_version="1",
        issue_class=catalog_entry.issue_class if catalog_entry is not None else "data_issue",
        provenance={"catalog_category": category or None},
        iso_category=iso_category,
        confidence=catalog_entry.default_confidence if catalog_entry is not None else "medium",
        actionable=catalog_entry.default_actionable if catalog_entry is not None else True,
    )


__all__ = ["ValidationIssue", "build_issue"]
