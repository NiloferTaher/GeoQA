from __future__ import annotations

from collections import defaultdict
from typing import Any

from geoqa.validations.base import ValidationIssue

SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _severity_rank(severity: str | None) -> int:
    if severity is None:
        return 0
    return SEVERITY_ORDER.get(str(severity).lower(), 0)


def issue_summary_by_feature(issues: list[ValidationIssue]) -> dict[Any, dict[str, Any]]:
    """Group validation issues by feature id into a compact ML-friendly summary."""
    grouped: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {
            "qa_has_issue": True,
            "qa_issue_count": 0,
            "qa_problem_names": [],
            "qa_repair_hints": [],
            "qa_max_severity": None,
        }
    )

    for issue in issues:
        feature_id = issue.feature_id
        if feature_id is None:
            continue
        entry = grouped[feature_id]
        entry["qa_issue_count"] += 1
        if issue.problem_name not in entry["qa_problem_names"]:
            entry["qa_problem_names"].append(issue.problem_name)
        if issue.solution_hint and issue.solution_hint not in entry["qa_repair_hints"]:
            entry["qa_repair_hints"].append(issue.solution_hint)
        current = entry["qa_max_severity"]
        if current is None or _severity_rank(issue.severity) > _severity_rank(current):
            entry["qa_max_severity"] = issue.severity

    for entry in grouped.values():
        entry["qa_quality_score"] = quality_score_from_issues(
            entry["qa_issue_count"],
            entry["qa_max_severity"],
        )

    return dict(grouped)


def quality_score_from_issues(issue_count: int, max_severity: str | None) -> float:
    """
    Return a simple normalized quality score from 0.0 to 1.0.

    This is intentionally conservative and explainable rather than statistically tuned.
    """
    severity_penalty = {
        None: 0.0,
        "low": 0.15,
        "medium": 0.35,
        "high": 0.6,
        "critical": 0.85,
    }.get(max_severity, 0.35)
    count_penalty = min(issue_count * 0.05, 0.5)
    return max(0.0, round(1.0 - severity_penalty - count_penalty, 4))


def _copy_layer(layer: Any) -> Any:
    if hasattr(layer, "copy"):
        return layer.copy()
    raise TypeError("Layer must support copy() for annotation.")


def annotate_layer_with_issues(
    layer: Any,
    issues: list[ValidationIssue],
    *,
    id_field: str = "ID",
) -> Any:
    """
    Add quality-annotation columns to a tabular or GeoDataFrame-like layer.

    Added columns:
    - qa_has_issue
    - qa_issue_count
    - qa_problem_names
    - qa_repair_hints
    - qa_max_severity
    - qa_quality_score
    """
    annotated = _copy_layer(layer)
    summary = issue_summary_by_feature(issues)

    if not hasattr(annotated, "__setitem__"):
        raise TypeError("Layer must support column assignment for annotation.")

    def feature_summary(feature_id: Any) -> dict[str, Any]:
        return summary.get(
            feature_id,
            {
                "qa_has_issue": False,
                "qa_issue_count": 0,
                "qa_problem_names": [],
                "qa_repair_hints": [],
                "qa_max_severity": None,
                "qa_quality_score": 1.0,
            },
        )

    if hasattr(annotated, "apply") and hasattr(annotated, "columns"):
        annotated["qa_has_issue"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_has_issue"])
        annotated["qa_issue_count"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_issue_count"])
        annotated["qa_problem_names"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_problem_names"])
        annotated["qa_repair_hints"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_repair_hints"])
        annotated["qa_max_severity"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_max_severity"])
        annotated["qa_quality_score"] = annotated[id_field].apply(lambda value: feature_summary(value)["qa_quality_score"])
        return annotated

    raise TypeError("Unsupported layer type for annotation.")

