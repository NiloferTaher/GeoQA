"""Detect structured payloads stored in columns declared as scalar text.

Why this exists
---------------
A real vendor stores a JSON array inside a column declared ``text``::

    ___json[{"pathname": "/Collected Media/2025-08/mdc_photo_812.jpg",
             "title": "IMG-0041.jpg"}, {...}]

The pipeline that reads it works, because it was written with a hand-rolled
tolerant parser: strip the ``___json`` marker, retry on ``[`` then ``{``,
coalesce two candidate columns, extract basenames, drop query strings, dedupe.

That parser is the tell. Nobody writes a tolerant parser for a well-typed
column. The parsing logic exists precisely *because* the schema is wrong, and
it lives in application code where nothing validates it. When the vendor changes
the prefix, the parser breaks silently: it stops raising and starts returning
empty lists, and the only symptom is a report with missing photographs.

The condition is therefore not "this column looks odd". It is:

1. a column whose declared type is scalar text,
2. containing a serialised structure,
3. whose correctness currently depends on unwritten application logic.

No mainstream QA tool reports this class. ArcGIS Data Reviewer, GeoLint and the
OGC validity concepts all treat a populated text column as conforming.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

PROBLEM_NAME = "json_in_text_column"

# A JSON object or array, allowing for a vendor prefix such as ___json or __json.
_STRUCTURED_RE = re.compile(
    r"^\s*_*\s*json\s*[\[\{]",
    re.IGNORECASE,
)

# Vendor prefix markers seen in the wild, recorded rather than hardcoded into
# the parser so the detection does not depend on one vendor's spelling.
_VENDOR_MARKERS = ("___json", "__json", "json:")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        # NaN, NaT and pandas' NA scalars are all self-unequal. A missing cell
        # must read as empty, not as the string "nan".
        if value != value:
            return ""
    except (TypeError, ValueError):
        # Non-scalar (array) or ambiguous comparison; treat as opaque text.
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "<na>"}:
        return ""
    return text


def _looks_structured(value: Any) -> bool:
    text = _as_text(value)
    if not text:
        return False
    lowered = text.lower()
    if any(marker in lowered[:16] for marker in _VENDOR_MARKERS):
        return True
    if text[0] in "[{" and _STRUCTURED_RE.match(text):
        return True
    # Bare JSON that already starts with the delimiter, no vendor marker.
    return text[0] in "[{"


def _parse_attempt(text: str) -> tuple[bool, Any]:
    """Return (parsed, value). Tolerates a vendor prefix before the payload."""
    candidate = text
    if not candidate:
        return False, None
    for opener in ("[", "{"):
        idx = candidate.find(opener)
        if idx > 0:
            candidate = candidate[idx:]
            break
    try:
        return True, json.loads(candidate)
    except (ValueError, TypeError):
        return False, None


@dataclass(frozen=True)
class PayloadColumnProfile:
    """What a single column's contents look like structurally."""

    column: str
    rows: int
    nonempty: int
    structured: int
    parsed_ok: int
    parse_failures: int
    vendor_markers: tuple[str, ...]

    @property
    def structured_fraction(self) -> float:
        if not self.nonempty:
            return 0.0
        return self.structured / self.nonempty

    @property
    def parse_success_rate(self) -> float:
        if not self.structured:
            return 1.0
        return self.parsed_ok / self.structured

    @property
    def is_structured_column(self) -> bool:
        """Structured enough to be a schema defect rather than incidental text."""
        return self.structured >= 3 and self.structured_fraction >= 0.5


def profile_payload_column(column: str, values: Iterable[Any]) -> PayloadColumnProfile:
    """Inspect one column's values without deciding anything about it."""
    rows = nonempty = structured = parsed_ok = 0
    markers: set[str] = set()

    for value in values:
        rows += 1
        text = _as_text(value)
        if not text:
            continue
        nonempty += 1
        lowered = text.lower()
        for marker in _VENDOR_MARKERS:
            if marker in lowered[:16]:
                markers.add(marker)
        if not _looks_structured(value):
            continue
        structured += 1
        ok, _ = _parse_attempt(text)
        if ok:
            parsed_ok += 1

    return PayloadColumnProfile(
        column=column,
        rows=rows,
        nonempty=nonempty,
        structured=structured,
        parsed_ok=parsed_ok,
        parse_failures=structured - parsed_ok,
        vendor_markers=tuple(sorted(markers)),
    )


def validate_payload_columns(
    layer: Any,
    columns: Sequence[str] | None = None,
    *,
    require_structured: bool = True,
) -> list[Any]:
    """Report columns that hold a serialised structure despite a scalar text type.

    ``columns`` restricts the scan. ``require_structured=False`` reports any
    column containing even one structured value, which is useful when auditing a
    narrow, known-suspect field set.
    """
    from .base import build_issue

    if columns is None:
        columns = [c for c in getattr(layer, "columns", []) if c != "geometry"]

    issues: list[Any] = []
    for column in columns:
        if column not in getattr(layer, "columns", []):
            continue
        profile = profile_payload_column(column, layer[column])
        if profile.structured == 0:
            continue
        is_defect = profile.is_structured_column if require_structured else True

        # A column that is structured but has rows that will not parse is worse
        # than one that is merely mis-typed, because consumers cannot tell which.
        if is_defect:
            issues.append(
                build_issue(
                    problem_name=PROBLEM_NAME,
                    severity="medium",
                    description=(
                        f"Column '{profile.column}' holds a serialised structure in "
                        f"{profile.structured}/{profile.nonempty} non-empty rows "
                        f"({profile.structured_fraction:.0%})"
                        + (
                            f"; markers seen: {', '.join(profile.vendor_markers)}"
                            if profile.vendor_markers
                            else ""
                        )
                    ),
                    extra={
                        "column": profile.column,
                        "structured_rows": profile.structured,
                        "nonempty_rows": profile.nonempty,
                        "structured_fraction": round(profile.structured_fraction, 4),
                        "parse_success_rate": round(profile.parse_success_rate, 4),
                        "vendor_markers": list(profile.vendor_markers),
                        "declared_type": "text",
                        "actual_shape": "json",
                    },
                )
            )

        # Only escalate a parse failure once the column is established as a
        # structured one. A single stray brace in free text is not a broken
        # vendor payload, and reporting it as high severity would be noise.
        if profile.parse_failures > 0 and profile.structured >= 3:
            issues.append(
                build_issue(
                    problem_name="json_in_text_unparseable",
                    severity="high",
                    description=(
                        f"Column '{profile.column}' looks structured but "
                        f"{profile.parse_failures}/{profile.structured} rows fail to parse; "
                        "downstream readers cannot be trusted until this is resolved"
                    ),
                    extra={
                        "column": profile.column,
                        "parse_failures": profile.parse_failures,
                        "structured_rows": profile.structured,
                    },
                )
            )

    return issues


def payload_columns(
    layer: Any,
    columns: Sequence[str] | None = None,
) -> list[PayloadColumnProfile]:
    """Return profiles only, for callers that want the shape without the issues."""
    if columns is None:
        columns = [c for c in getattr(layer, "columns", []) if c != "geometry"]
    return [
        profile_payload_column(column, layer[column])
        for column in columns
        if column in getattr(layer, "columns", [])
    ]


__all__ = [
    "PROBLEM_NAME",
    "PayloadColumnProfile",
    "payload_columns",
    "profile_payload_column",
    "validate_payload_columns",
]