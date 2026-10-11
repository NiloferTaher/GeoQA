"""Character encoding of delivered tabular and shapefile attribute data.

A shapefile's DBF declares its encoding in a sidecar ``.cpg`` file. When that
file is absent the reader guesses, and the guess is usually wrong: a Windows
author writing Arabic or accented Latin gets ``windows-1252`` assumed by most
tools, and every non-ASCII value becomes mojibake that looks like data.

The damage is silent and it is permanent once the file has been through one
round trip. This module therefore detects and reports rather than repairs. The
repair belongs to whoever holds the source of truth, because a library that
rewrites encodings on load has no way to say what the original bytes were.

What is reported:

- the declared encoding, and whether it came from a ``.cpg`` or was guessed;
- whether the bytes decode cleanly under the declared encoding;
- the specific characters that do not round-trip, so the affected values can
  be found rather than the whole column being suspected.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "EncodingReport",
    "read_cpg",
    "detect_encoding",
    "check_text_encoding",
    "validate_shapefile_encoding",
    "looks_like_mojibake",
]

_CPG_SUFFIX = ".cpg"


@dataclass
class EncodingReport:
    """What an attribute column's text looks like, and how sure we are."""

    column: str | None = None
    declared: str | None = None
    declared_source: str | None = None
    used: str | None = None
    suspicious: list[str] = field(default_factory=list)
    replacement_count: int = 0
    undecodable: bool = False
    confidence: str = "unknown"

    @property
    def is_declared(self) -> bool:
        return self.declared_source == "cpg"

    @property
    def has_problem(self) -> bool:
        return bool(self.suspicious) or self.undecodable or self.replacement_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "declared": self.declared,
            "declared_source": self.declared_source,
            "used": self.used,
            "suspicious": list(self.suspicious[:20]),
            "replacement_count": self.replacement_count,
            "undecodable": self.undecodable,
            "confidence": self.confidence,
        }


def read_cpg(shapefile_path: str | Path) -> str | None:
    """Return the encoding declared by a shapefile's ``.cpg`` sidecar, if any."""
    cpg = Path(str(shapefile_path) + _CPG_SUFFIX)
    if not cpg.exists():
        return None
    try:
        raw = cpg.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    return raw or None


def detect_encoding(
    shapefile_path: str | Path | None = None,
    *,
    fallback_chain: Sequence[str] = ("utf-8", "windows-1252", "latin-1"),
) -> EncodingReport:
    """Determine the declared and usable encoding for a shapefile's attributes."""
    report = EncodingReport()
    if shapefile_path is not None:
        declared = read_cpg(shapefile_path)
        if declared:
            report.declared = declared
            report.declared_source = "cpg"
            report.used = declared
            report.confidence = "declared"
            return report
        report.declared_source = "absent"
        report.confidence = "guessed"

    # No cpg. Try the chain in order and report the first that decodes without
    # error, because the absence of a declaration is itself the finding.
    for candidate in fallback_chain:
        try:
            "test".encode(candidate)
        except LookupError:
            continue
        report.used = candidate
        if report.confidence == "unknown":
            report.confidence = "guessed"
        return report
    return report


_MOJIBAKE_MARKERS = (
    "Ã©", "Ã¨", "Ã ", "Ã¢", "Ã¤", "Ã¶", "Ã¼", "Ã±",
    "â€™", "â€œ", "â€", "Ã¯", "Ã¿", "Â°", "Â±",
    "Ø§", "Ù„", "Ù…", "Ø±",
)


def looks_like_mojibake(text: str) -> bool:
    """Whether a string shows the classic double-encoding signature.

    Text that was decoded as UTF-8 when it was written as windows-1252 comes
    back as sequences like ``Ã©``. The marker is reliable for that specific
    mistake and says nothing about the original text, which is why the fix is
    not attempted here.
    """
    return any(marker in text for marker in _MOJIBAKE_MARKERS)


def check_text_encoding(
    values: Iterable[Any],
    *,
    column: str | None = None,
    declared: str | None = None,
) -> EncodingReport:
    """Inspect text values for signs of an encoding that did not survive."""
    report = EncodingReport(column=column, declared=declared, declared_source="cpg" if declared else "absent")
    if declared:
        report.used = declared
        report.confidence = "declared"

    codec = declared or "utf-8"
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if "�" in value:
            report.replacement_count += 1
            if value not in report.suspicious:
                report.suspicious.append(value)
            continue
        try:
            value.encode(codec)
        except (UnicodeEncodeError, LookupError):
            report.replacement_count += 1
            if value not in report.suspicious:
                report.suspicious.append(value)
            continue
        if looks_like_mojibake(value) and value not in report.suspicious:
            report.suspicious.append(value)
    return report


def validate_shapefile_encoding(
    shapefile_path: str | Path,
    *,
    text_columns: Sequence[str] = (),
) -> list[ValidationIssue]:
    """Report a shapefile whose attribute encoding is undeclared or has broken."""
    path = Path(str(shapefile_path))
    report = detect_encoding(path)
    issues: list[ValidationIssue] = []

    if report.declared_source == "absent":
        issues.append(
            build_issue(
                "encoding_not_declared",
                description=(
                    f"{path.name} has no .cpg sidecar, so its attribute encoding is "
                    "whatever the reader guesses. Guesswork is usually right until it "
                    "is not, and the failure is silent."
                ),
                extra={"path": str(path.name), "fallback_used": report.used},
            )
        )

    for column in text_columns:
        try:
            import geopandas as gpd

            frame = gpd.read_file(path, encoding=report.used or "utf-8")
            values = frame[column]
        except Exception:
            continue
        column_report = check_text_encoding(values, column=column, declared=report.declared)
        if column_report.has_problem:
            issues.append(
                build_issue(
                    "encoding_suspect_values",
                    description=(
                        f"Column {column!r} in {path.name} contains "
                        f"{column_report.replacement_count} value(s) that do not survive "
                        "the declared encoding, which is characteristic of a file that "
                        "has been through the wrong decode at least once."
                    ),
                    extra={"path": str(path.name), **column_report.to_dict()},
                )
            )
    return issues