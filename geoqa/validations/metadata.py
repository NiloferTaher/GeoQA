from __future__ import annotations

from typing import Any

from .base import ValidationIssue, build_issue


_FIELD_TO_PROBLEM = {
    "title": "missing_metadata_title",
    "abstract": "missing_metadata_abstract",
    "extent": "missing_metadata_extent",
}


def _missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def missing_metadata_fields(metadata: dict[str, Any]) -> list[ValidationIssue]:
    """Return issues for missing core metadata fields."""
    issues: list[ValidationIssue] = []
    for field in ("title", "abstract", "extent"):
        if _missing_value(metadata.get(field)):
            issues.append(
                build_issue(
                    _FIELD_TO_PROBLEM[field],
                    description=f"Metadata field '{field}' is missing.",
                    solution_hint=f"Populate the '{field}' metadata field with authoritative dataset information.",
                )
            )
    return issues


def incomplete_metadata(metadata: dict[str, Any]) -> list[ValidationIssue]:
    """Return issues for incomplete but expected metadata sections."""
    issues: list[ValidationIssue] = []
    if _missing_value(metadata.get("extent")):
        issues.append(
            build_issue(
                "missing_metadata_extent",
                description="Metadata extent is missing.",
                solution_hint="Add the dataset geographic extent or bounding box to the metadata record.",
            )
        )
    if _missing_value(metadata.get("lineage")):
        issues.append(
            build_issue(
                "missing_metadata_lineage",
                description="Metadata lineage is missing.",
                solution_hint="Document the source inputs and process history in the metadata lineage section.",
            )
        )
    return issues


__all__ = ["incomplete_metadata", "missing_metadata_fields"]
