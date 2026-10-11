"""Placeholder values that pass a null check but are not null.

``dropna`` does not drop ``"0000/00/00"``, ``"N/A"``, ``"unknown"``, ``-999`` or
an empty string that a spreadsheet filled in on export. Every one of those
reaches a database as a value, and every one of them is read back as a real
answer by whatever consumes it next.

The default sentinels are the ones that appear in exported field data, because
that is where they come from. They are configurable, and the report says which
pattern matched, so a caller who disagrees can see what was found rather than
arguing with a boolean.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "DEFAULT_TEXT_SENTINELS",
    "DEFAULT_NUMERIC_SENTINELS",
    "detect_sentinels",
    "validate_sentinels",
    "sentinel_report",
]

#: Text values meaning "no value". Matched case-insensitively after trimming.
DEFAULT_TEXT_SENTINELS: frozenset[str] = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "n.a.",
        "nan",
        "none",
        "null",
        "nil",
        "unknown",
        "not known",
        "not available",
        "not applicable",
        "not recorded",
        "missing",
        "undefined",
        "tbd",
        "tba",
        "#n/a",
        "#null!",
        "#value!",
        "#ref!",
        "#div/0!",
        "#name?",
    }
)

#: Numbers meaning "no value". Negative values are the convention because a
#: real coordinate or length is never negative, so -1 and -999 are unambiguous.
DEFAULT_NUMERIC_SENTINELS: frozenset[float] = frozenset({-1.0, -99.0, -999.0, -9999.0, -99999.0})

_ZERO_DATE = re.compile(r"^\s*0{4}[-/.]0{1,2}[-/.]0{1,2}\s*$")
_ISO_DATE = re.compile(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2})?)?\s*$")


def _is_nullish(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    return False


def detect_sentinels(
    value: Any,
    *,
    text_sentinels: Iterable[str] = DEFAULT_TEXT_SENTINELS,
    numeric_sentinels: Iterable[float] = DEFAULT_NUMERIC_SENTINELS,
) -> str | None:
    """Return the sentinel pattern this value matches, or ``None``.

    ``empty_string``, ``text``, ``zero_date``, ``numeric`` and ``excel_error``
    are distinguished because the fix differs: an empty string becomes NULL,
    a zero date is a parsing problem, an Excel error is an upstream formula.
    """
    if _is_nullish(value):
        return None

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = {float(v) for v in numeric_sentinels}
        return "numeric" if float(value) in numeric else None

    text = str(value).strip()
    if not text:
        return "empty_string"
    lowered = text.lower()
    # Excel errors are checked before the generic text set because several of
    # them, "#N/A" among them, are also listed as human-written placeholders.
    # The distinction matters: "#N/A" in a column usually means a formula
    # upstream failed, which is a different problem from someone typing N/A.
    if text.startswith("#") and text.endswith(("!", "?")):
        return "excel_error"
    if lowered in {str(s).strip().lower() for s in text_sentinels}:
        return "text"
    if _ZERO_DATE.match(text):
        return "zero_date"
    return None


def sentinel_report(
    layer: Any,
    *,
    fields: Sequence[str] | None = None,
    text_sentinels: Iterable[str] = DEFAULT_TEXT_SENTINELS,
    numeric_sentinels: Iterable[float] = DEFAULT_NUMERIC_SENTINELS,
) -> dict[str, dict[str, Any]]:
    """Count sentinel values per column without judging them."""
    columns = list(fields) if fields else [c for c in getattr(layer, "columns", []) if c != "geometry"]
    report: dict[str, dict[str, Any]] = {}
    for column in columns:
        try:
            series = layer[column]
        except Exception:
            continue
        counts: dict[str, int] = {}
        total = 0
        for value in series:
            kind = detect_sentinels(
                value, text_sentinels=text_sentinels, numeric_sentinels=numeric_sentinels
            )
            if kind:
                counts[kind] = counts.get(kind, 0) + 1
                total += 1
        if total:
            report[str(column)] = {
                "sentinel_count": total,
                "by_kind": dict(sorted(counts.items())),
                "total_rows": int(len(series)),
                "fraction": round(total / len(series), 6) if len(series) else 0.0,
            }
    return report


def validate_sentinels(
    layer: Any,
    *,
    fields: Sequence[str] | None = None,
    text_sentinels: Iterable[str] = DEFAULT_TEXT_SENTINELS,
    numeric_sentinels: Iterable[float] = DEFAULT_NUMERIC_SENTINELS,
    threshold: float = 0.0,
) -> list[ValidationIssue]:
    """Report columns whose placeholder values will be read back as answers.

    ``threshold`` is the fraction above which a column is reported. The default
    of zero reports any occurrence, because a single ``-999`` in a column of
    real measurements is more likely to be a mistake than a deliberate marker.
    """
    issues: list[ValidationIssue] = []
    report = sentinel_report(
        layer, fields=fields, text_sentinels=text_sentinels, numeric_sentinels=numeric_sentinels
    )
    for column, detail in report.items():
        if detail["fraction"] <= threshold and detail["sentinel_count"] == 0:
            continue
        if detail["sentinel_count"] == 0:
            continue
        kinds = ", ".join(f"{k} x{v}" for k, v in detail["by_kind"].items())
        issues.append(
            build_issue(
                "sentinel_placeholder_value",
                description=(
                    f"Column {column!r} contains {detail['sentinel_count']} placeholder "
                    f"value(s) ({kinds}) out of {detail['total_rows']} rows. These pass a "
                    "null check and will be read back as real values."
                ),
                extra={"column": column, **detail},
            )
        )
    return issues