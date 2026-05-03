from __future__ import annotations

from collections import Counter
from typing import Any

from geoqa.ml.annotations import annotate_layer_with_issues, issue_summary_by_feature
from geoqa.validations.base import ValidationIssue


def build_issue_feature_rows(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    """Convert validation issues into model-friendly feature rows."""
    rows: list[dict[str, Any]] = []
    for issue in issues:
        rows.append(
            {
                "feature_id": issue.feature_id,
                "problem_name": issue.problem_name,
                "severity": issue.severity,
                "severity_rank": {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(issue.severity, 0),
                "has_repair_hint": bool(issue.solution_hint),
                "repair_hint": issue.solution_hint,
            }
        )
    return rows


def build_quality_feature_frame(layer: Any, issues: list[ValidationIssue], *, id_field: str = "ID") -> Any:
    """
    Return an annotated layer with additional aggregate quality feature columns.

    This extends the basic annotation layer with issue-type counts so models can
    use quality metadata as input features.
    """
    annotated = annotate_layer_with_issues(layer, issues, id_field=id_field)
    summary = issue_summary_by_feature(issues)

    all_problem_names = sorted({issue.problem_name for issue in issues})
    if not all_problem_names:
        return annotated

    counts_by_feature: dict[Any, Counter[str]] = {}
    for feature_id, entry in summary.items():
        counts_by_feature[feature_id] = Counter(entry["qa_problem_names"])

    for problem_name in all_problem_names:
        column = f"qa_problem_{problem_name}"
        annotated[column] = annotated[id_field].apply(
            lambda feature_id, problem_name=problem_name: int(problem_name in counts_by_feature.get(feature_id, Counter()))
        )

    return annotated
