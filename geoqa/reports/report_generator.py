from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from geoqa.problem_registry import VALIDATION_RULE_VERSION
from geoqa.validations.base import ValidationIssue


_BASE_FIELD_ORDER = [
    "issue_id",
    "validation_rule_version",
    "problem_name",
    "severity",
    "confidence",
    "actionable",
    "issue_class",
    "validator_name",
    "validator_version",
    "description",
    "solution_hint",
    "feature_id",
    "geometry",
    "iso_category",
    "suppression",
    "provenance",
]


def _distribution_rows(counts: dict[str, int], total: int) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "count": count,
            "percent": round((count / total) * 100, 2) if total else 0.0,
        }
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _normalize_report_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            normalized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            normalized[key] = value
    return normalized


def _csv_fieldnames(issue_rows: list[dict[str, Any]]) -> list[str]:
    discovered = {key for row in issue_rows for key in row}
    ordered = [name for name in _BASE_FIELD_ORDER if name in discovered]
    extras = sorted(discovered - set(ordered))
    return ordered + extras


def summarize_issues(issues: Iterable[ValidationIssue]) -> dict[str, Any]:
    issue_list = list(issues)
    by_problem: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_issue_class: dict[str, int] = {}
    by_validator: dict[str, int] = {}
    by_iso_category: dict[str, int] = {}
    by_root_cause: dict[str, int] = {}
    by_priority_band: dict[str, int] = {}
    actionable_count = 0
    informational_count = 0

    for issue in issue_list:
        by_problem[issue.problem_name] = by_problem.get(issue.problem_name, 0) + 1
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        by_issue_class[issue.issue_class] = by_issue_class.get(issue.issue_class, 0) + 1
        if issue.validator_name:
            by_validator[issue.validator_name] = by_validator.get(issue.validator_name, 0) + 1
        if issue.iso_category:
            by_iso_category[issue.iso_category] = by_iso_category.get(issue.iso_category, 0) + 1
        root_cause = None
        if issue.provenance:
            root_cause = issue.provenance.get("catalog_category") or issue.provenance.get("family")
        if root_cause:
            root_cause = str(root_cause)
            by_root_cause[root_cause] = by_root_cause.get(root_cause, 0) + 1
        priority_score = int(issue.priority_score or 0)
        if priority_score >= 80:
            band = "critical"
        elif priority_score >= 60:
            band = "high"
        elif priority_score >= 35:
            band = "medium"
        else:
            band = "low"
        by_priority_band[band] = by_priority_band.get(band, 0) + 1
        if issue.actionable:
            actionable_count += 1
        else:
            informational_count += 1

    top_issues = sorted(by_problem.items(), key=lambda item: (-item[1], item[0]))[:5]
    top_actionable = sorted(
        (issue for issue in issue_list if issue.actionable),
        key=lambda issue: (-(issue.priority_score or 0), issue.problem_name, str(issue.feature_id)),
    )[:5]
    total = len(issue_list)
    return {
        "validation_rule_version": VALIDATION_RULE_VERSION,
        "issue_count": total,
        "total_issues": total,
        "actionable": actionable_count,
        "informational": informational_count,
        "actionable_ratio": round((actionable_count / total), 4) if total else 0.0,
        "by_problem": dict(sorted(by_problem.items())),
        "problem_breakdown": _distribution_rows(by_problem, total),
        "by_severity": dict(sorted(by_severity.items())),
        "severity_distribution": _distribution_rows(by_severity, total),
        "by_issue_class": dict(sorted(by_issue_class.items())),
        "by_validator": dict(sorted(by_validator.items())),
        "by_iso_category": dict(sorted(by_iso_category.items())),
        "by_root_cause": dict(sorted(by_root_cause.items())),
        "by_priority_band": dict(sorted(by_priority_band.items())),
        "top_issues": [
            {
                "problem_name": name,
                "count": count,
                "percent": round((count / total) * 100, 2) if total else 0.0,
            }
            for name, count in top_issues
        ],
        "top_actionable": [
            {
                "problem_name": issue.problem_name,
                "feature_id": issue.feature_id,
                "severity": issue.severity,
                "confidence": issue.confidence,
                "priority_score": issue.priority_score,
            }
            for issue in top_actionable
        ],
    }


def format_summary_text(summary: dict[str, Any]) -> str:
    actionable_ratio = float(summary.get("actionable_ratio", 0.0) or 0.0)
    lines = [
        f"Validation rule version: {summary.get('validation_rule_version', 'unknown')}",
        f"Execution status: {summary.get('execution_status', 'full')}",
        f"Total issues: {summary.get('total_issues', summary.get('issue_count', 0))}",
        f"Actionable: {summary.get('actionable', 0)}",
        f"Informational: {summary.get('informational', 0)}",
        f"Actionable ratio: {round(actionable_ratio * 100, 2)}%",
    ]
    if summary.get("execution_reason"):
        lines.append(f"Execution reason: {summary.get('execution_reason')}")
    validators_completed = summary.get("validators_completed", [])
    validators_deferred = summary.get("validators_deferred", [])
    if validators_completed or validators_deferred:
        lines.append(f"Validators completed: {len(validators_completed)}")
        lines.append(f"Validators deferred: {len(validators_deferred)}")
    lines.extend(["", "Severity distribution:"])
    for item in summary.get("severity_distribution", []):
        lines.append(f"- {item['name']}: {item['count']} ({item['percent']}%)")
    lines.append("")
    lines.append("Top issues:")
    for item in summary.get("top_issues", []):
        lines.append(f"- {item['problem_name']}: {item['count']} ({item['percent']}%)")
    root_causes = summary.get("by_root_cause", {})
    if root_causes:
        lines.append("")
        lines.append("Root-cause groups:")
        for name, count in sorted(root_causes.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {name}: {count}")
    top_actionable = summary.get("top_actionable", [])
    if top_actionable:
        lines.append("")
        lines.append("Top actionable findings:")
        for item in top_actionable:
            lines.append(
                f"- {item['problem_name']} feature={item.get('feature_id')} severity={item.get('severity')} "
                f"confidence={item.get('confidence')} priority={item.get('priority_score')}"
            )
    next_steps = summary.get("operator_next_steps", [])
    if next_steps:
        lines.append("")
        lines.append("Next steps:")
        for step in next_steps:
            lines.append(f"- {step}")
    return "\n".join(lines)


def load_report(report_path: str | Path) -> list[dict[str, Any]]:
    path = Path(report_path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict):
            issues = payload.get("issues")
            if isinstance(issues, list):
                return [dict(item) for item in issues]
        raise ValueError("JSON report payload must be a list or an object containing an 'issues' list.")
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    raise ValueError(f"Unsupported report format for loading: {suffix!r}")


def summarize_report(report_path: str | Path) -> dict[str, Any]:
    path = Path(report_path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
            summary = dict(payload["summary"])
            summary["report_path"] = str(path)
            return summary
    rows = load_report(path)
    issues = [
        ValidationIssue(
            issue_id=row.get("issue_id"),
            problem_name=str(row.get("problem_name", "")),
            severity=str(row.get("severity", "medium")),
            description=str(row.get("description", "")),
            solution_hint=str(row.get("solution_hint", "")),
            feature_id=row.get("feature_id"),
            geometry=row.get("geometry"),
            validator_name=row.get("validator_name"),
            validator_version=row.get("validator_version"),
            issue_class=str(row.get("issue_class", "data_issue")),
            iso_category=row.get("iso_category"),
            suppression=row.get("suppression"),
            provenance=row.get("provenance"),
            confidence=str(row.get("confidence", "medium")),
            actionable=str(row.get("actionable", "True")).lower() != "false",
            priority_score=int(row.get("priority_score", 0)) if str(row.get("priority_score", "")).strip() else None,
        )
        for row in rows
    ]
    summary = summarize_issues(issues)
    summary["report_path"] = str(path)
    return summary


def generate_report(
    issues: Iterable[ValidationIssue],
    output_format: str = "csv",
    file_path: str = "validation_report",
    summary: dict[str, Any] | None = None,
) -> Path:
    """
    Generate a validation report in CSV or JSON format.

    Returns the path of the written report file.
    """
    issue_rows = [issue.to_dict() for issue in issues]
    output_path = Path(f"{file_path}.{output_format.lower()}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format.lower() == "csv":
        fieldnames = _csv_fieldnames(issue_rows)
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for row in issue_rows:
                writer.writerow(_normalize_report_row(row))
        return output_path

    if output_format.lower() == "json":
        resolved_summary = summary or summarize_issues(
            ValidationIssue(
                issue_id=row.get("issue_id"),
                problem_name=str(row.get("problem_name", "")),
                severity=str(row.get("severity", "medium")),
                description=str(row.get("description", "")),
                solution_hint=str(row.get("solution_hint", "")),
                feature_id=row.get("feature_id"),
                geometry=row.get("geometry"),
                validator_name=row.get("validator_name"),
                validator_version=row.get("validator_version"),
                issue_class=str(row.get("issue_class", "data_issue")),
                suppression=row.get("suppression"),
                provenance=row.get("provenance"),
                iso_category=row.get("iso_category"),
                confidence=str(row.get("confidence", "medium")),
                actionable=bool(row.get("actionable", True)),
                priority_score=int(row.get("priority_score", 0)) if row.get("priority_score") is not None else None,
            )
            for row in issue_rows
        )
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "validation_rule_version": VALIDATION_RULE_VERSION,
                    "issue_count": len(issue_rows),
                    "summary": resolved_summary,
                    "issues": issue_rows,
                },
                file,
                indent=2,
                ensure_ascii=False,
            )
        return output_path

    raise ValueError(f"Unsupported output format: {output_format!r}")


__all__ = ["format_summary_text", "generate_report", "load_report", "summarize_issues", "summarize_report"]
