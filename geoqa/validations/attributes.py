from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import ValidationIssue, build_issue


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        # Works for pandas/NumPy NA values without importing pandas eagerly.
        return bool(value != value)
    except Exception:
        return False


def _field_exists(layer: Any, field: str) -> bool:
    columns = getattr(layer, "columns", None)
    return columns is not None and field in columns


def required_nulls(layer: Any, required_fields: Iterable[str]) -> list[ValidationIssue]:
    """Return issues for missing values in required fields."""
    issues: list[ValidationIssue] = []

    for field in required_fields:
        if not _field_exists(layer, field):
            for index, row in layer.iterrows():
                issues.append(
                    build_issue(
                        "null_attribute_in_required_field",
                        row=row,
                        index=index,
                        description=f"The required attribute '{field}' is missing from the dataset schema.",
                        solution_hint=f"Add the required field '{field}' and populate it from source systems, lookup tables, or QA review.",
                    )
                )
            continue

        for index, row in layer.iterrows():
            if _is_null(row[field]):
                issues.append(
                    build_issue(
                        "null_attribute_in_required_field",
                        row=row,
                        index=index,
                        description=f"The required attribute '{field}' is missing.",
                        solution_hint="Populate required values from source systems, lookup tables, or QA review before release.",
                    )
                )

    return issues


def uniqueness(layer: Any, field: str) -> list[ValidationIssue]:
    """Return issues for duplicate non-null values in the specified field."""
    if not _field_exists(layer, field):
        raise ValueError(f"Field {field!r} does not exist in the provided layer.")

    value_counts: dict[Any, int] = {}
    for _, row in layer.iterrows():
        value = row[field]
        if _is_null(value):
            continue
        value_counts[value] = value_counts.get(value, 0) + 1

    duplicate_values = {value for value, count in value_counts.items() if count > 1}
    issues: list[ValidationIssue] = []
    if not duplicate_values:
        return issues

    for index, row in layer.iterrows():
        value = row[field]
        if value in duplicate_values:
            issues.append(
                build_issue(
                    "non_unique_attribute",
                    row=row,
                    index=index,
                    description=f"Duplicate value {value!r} found in the field '{field}'.",
                    solution_hint=f"Ensure values in '{field}' are unique or use a field that permits duplicates.",
                )
            )

    return issues


def domain_range_checks(layer: Any, field: str, valid_domain: Any) -> list[ValidationIssue]:
    """Return issues for values that fall outside the configured domain or range."""
    if not _field_exists(layer, field):
        raise ValueError(f"Field {field!r} does not exist in the provided layer.")

    if callable(valid_domain):
        is_valid = valid_domain
    elif isinstance(valid_domain, tuple) and len(valid_domain) == 2:
        minimum, maximum = valid_domain

        def is_valid(value: Any) -> bool:
            return minimum <= value <= maximum

    else:
        allowed_values = set(valid_domain)

        def is_valid(value: Any) -> bool:
            return value in allowed_values

    issues: list[ValidationIssue] = []
    for index, row in layer.iterrows():
        value = row[field]
        if _is_null(value):
            continue
        if not is_valid(value):
            issues.append(
                build_issue(
                    "domain_violation",
                    row=row,
                    index=index,
                    description=f"Attribute value {value!r} in field '{field}' is outside the valid domain or range.",
                    solution_hint=f"Ensure the value in '{field}' matches the permitted domain or range for this dataset.",
                )
            )

    return issues


__all__ = ["domain_range_checks", "required_nulls", "uniqueness"]
