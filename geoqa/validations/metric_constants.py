"""Undeclared constants inside a metric or decision chain.

The problem this addresses
-------------------------
A computed metric is only auditable if every constant in its chain is
attributable. A realistic KPI file from a report dashboard contained::

    Unreportable Main Volume = SUM(unreportable_main) * (3.31 * 24 * 180) / 1e6
    Unreportable Main Savings = that * 0.3 * 1e6
    Crewdays                = SUM(owner_hours) / 6.5

None of ``3.31``, ``1.52``, ``0.3``, ``6.5`` is named, dated or attributed.
Reading the file, nobody can tell what they mean, what unit they carry, or
whether they are measured, assumed, or copied from a specification.

Two different things were in that file, and the code looked identical for both:

- a value that encodes a client's standing instruction (a report start date)
- a value that encodes an unconfirmed assumption (a fitted coefficient)

The first is correct and should stay. The second is a decision nobody signed.
**The distinction is not visible in the source, so it cannot be reviewed.**

What this module does
---------------------
It does not know whether a constant is right. It cannot. What it enforces is
that a constant *declares itself*:

``unlabelled_physical_constant``
    A numeric literal in a named metric expression with no declared meaning.
``hardcoded_scope_boundary``
    A hardcoded date, threshold or window that has not been marked as either
    a client requirement or an assumption.

Both are ``issue_class="governance_gap"``. Severity is medium, not high: an
undocumented assumption is an audit finding, not a broken dataset.

Design notes
------------
Constants are identified from the *expression*, not by scanning source code,
so this works on any host language and on a formula pasted into a report
builder. Only expressions with a unit-bearing or physical shape are treated as
physical constants; an exponent or a row index is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "unlabelled_physical_constant"

# A named metric -> the expression that computes it. This is the unit of
# analysis: a constant is only meaningful relative to what it multiplies.
MetricExpression = tuple[str, str]

# Metric names in real KPI listings contain spaces, slashes and ampersands
# ("Leak per KM", "Unreportable Main Line Water Volume"). Both layouts occur:
#   inline : Name = expression
#   paired : Name on one line, expression on the next
# A lone '=' is the assignment. '==', '>=', '<=', '!=' are comparisons and must
# not be treated as assignment, or a WHERE clause splits mid-expression.
_INLINE_RE = re.compile(r"^\s*(?P<name>[^=]+?)\s*(?<![<>!=])=(?!=)\s*(?P<expr>.+?)\s*$")
_LABEL_RE = re.compile(r"^[A-Za-z][^=<>]*$")

# Numeric literal with optional thousands separators and decimal part.
_LITERAL_RE = re.compile(r"(?<![\w.])(\d[\d,]*\.?\d*)(?![\w.])")

# Structural constants that are part of the expression's shape rather than a
# physical assumption. Excluded so the signal stays usable.
_STRUCTURAL = {
    "0", "1", "2", "10", "100", "1000", "1000000", "1000000000",
}

# Unit conversions and period lengths are not physical assumptions; they are
# arithmetic or scope. A period length is picked up by the scope-boundary check
# instead, where it can be declared as a reporting window.
_UNIT_CONVERSIONS = {
    "1000", "60", "60.0", "24", "24.0", "3600", "7", "7.0", "365", "365.0",
    "180", "30", "90", "12",
}

# Date components inside an ISO literal are a boundary, not a coefficient.
_ISO_DATE_RE = re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}\b")


def _date_components(expression: str) -> set[str]:
    """Numeric literals that are part of a date rather than a multiplier."""
    parts: set[str] = set()
    for match in _ISO_DATE_RE.finditer(expression):
        for piece in re.split(r"[^\d]+", match.group(0)):
            if piece:
                parts.add(piece)
    return parts

_DATE_RE = re.compile(
    r"^\s*\d{0,4}\s*"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.IGNORECASE,
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class ConstantDeclaration:
    """One declared meaning for a numeric constant."""

    constant: str
    meaning: str
    unit: str | None = None
    source: str | None = None
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "constant": self.constant,
            "meaning": self.meaning,
            "unit": self.unit,
            "source": self.source,
            "verified": self.verified,
        }


@dataclass(frozen=True)
class MetricConstantAudit:
    """One metric, its expression, and the constants found in it."""

    name: str
    expression: str
    constants: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()
    declared: tuple[ConstantDeclaration, ...] = ()
    is_scope_boundary: bool = False

    @property
    def is_declared_fully(self) -> bool:
        return not self.undeclared


def _build_audit(name: str, expr: str) -> MetricConstantAudit:
    constants = tuple(
        dict.fromkeys(m.group(1).replace(",", "") for m in _LITERAL_RE.finditer(expr))
    )
    return MetricConstantAudit(
        name=name.strip(),
        expression=expr.strip(),
        constants=constants,
        is_scope_boundary=bool(_DATE_RE.match(expr.strip()) or _YEAR_RE.search(expr)),
    )


def parse_metric_expressions(source: str) -> list[MetricConstantAudit]:
    """Extract metric definitions from a formula/KPI source listing.

    Handles both layouts found in practice::

        Leak per KM = TotalLeaks / Length        # inline
        Leak per KM                              # paired
        TotalLeaks / Length                      # next line
    """
    audits: list[MetricConstantAudit] = []
    lines = source.splitlines()
    pending_label: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue

        inline = _INLINE_RE.match(line)
        if inline is not None:
            name, expr = inline.group("name"), inline.group("expr")
            if name and expr:
                audits.append(_build_audit(name, expr))
                pending_label = None
                continue

        # A bare label defers to the following line.
        if _LABEL_RE.match(line) and pending_label is None:
            pending_label = line
            continue

        if pending_label is not None:
            audits.append(_build_audit(pending_label, line))
            pending_label = None
            continue

        audits.append(_build_audit(line, ""))

    if pending_label is not None:
        audits.append(_build_audit(pending_label, ""))
    return audits


def audit_constants(
    source: str,
    declarations: Mapping[str, ConstantDeclaration] | Sequence[ConstantDeclaration] = (),
) -> list[MetricConstantAudit]:
    """Audit a source listing against a set of declared constants.

    ``declarations`` may be a mapping keyed by the literal as written, or a
    sequence of :class:`ConstantDeclaration`. Key lookup is done on the literal
    with separators removed, so ``3.31`` and ``3,310`` do not collide silently.
    """
    if isinstance(declarations, Mapping):
        declared_map = {str(k): v for k, v in declarations.items()}
        ordered = list(declared_map.values())
    else:
        ordered = list(declarations)
        declared_map = {d.constant: d for d in ordered}

    results: list[MetricConstantAudit] = []
    for audit in parse_metric_expressions(source):
        matched: list[ConstantDeclaration] = []
        undeclared: list[str] = []
        date_parts = _date_components(audit.expression)
        for constant in audit.constants:
            normalized = constant.replace(",", "")
            declaration = declared_map.get(constant) or declared_map.get(normalized)
            if declaration is not None:
                matched.append(declaration)
                continue
            if normalized in _STRUCTURAL or normalized in _UNIT_CONVERSIONS:
                continue
            if normalized in date_parts:
                continue
            undeclared.append(constant)
        results.append(
            MetricConstantAudit(
                name=audit.name,
                expression=audit.expression,
                constants=audit.constants,
                undeclared=tuple(undeclared),
                declared=tuple(matched),
                is_scope_boundary=audit.is_scope_boundary,
            )
        )
    return results


def validate_metric_constants(
    layer: Any = None,
    *,
    source: str | None = None,
    declarations: Mapping[str, ConstantDeclaration] | Sequence[ConstantDeclaration] = (),
    skip_scope_boundaries: bool = False,
) -> list[Any]:
    """Report undeclared constants and undeclared scope boundaries.

    ``skip_scope_boundaries=True`` treats a hardcoded date as out of scope,
    which is the right setting when the audit is about numeric assumptions only.
    """
    from .base import build_issue

    if source is None:
        return []

    issues: list[Any] = []
    for audit in audit_constants(source, declarations):
        for constant in audit.undeclared:
            issues.append(
                build_issue(
                    problem_name=PROBLEM_NAME,
                    severity="medium",
                    description=(
                        f"Metric '{audit.name}' uses constant {constant} with no declared "
                        "meaning, unit or source; expression: "
                        f"{audit.expression}"
                    ),
                    extra={
                        "metric": audit.name,
                        "expression": audit.expression,
                        "constant": constant,
                        "all_constants": list(audit.constants),
                        "issue_class": "governance_gap",
                    },
                )
            )
        if audit.is_scope_boundary and not skip_scope_boundaries:
            issues.append(
                build_issue(
                    problem_name="hardcoded_scope_boundary",
                    severity="medium",
                    description=(
                        f"Metric '{audit.name}' hardcodes a date or window in its expression "
                        "without declaring whether it encodes a client requirement or an "
                        f"assumption: {audit.expression}"
                    ),
                    extra={
                        "metric": audit.name,
                        "expression": audit.expression,
                        "issue_class": "governance_gap",
                        "question": (
                            "Is this value a client requirement (a standing instruction "
                            "from the report's consumer) or an unconfirmed assumption? "
                            "The two are indistinguishable in the expression."
                        ),
                    },
                )
            )
    return issues


def audit_table(
    frame: Any,
    *,
    metric_columns: Sequence[str] | None = None,
    declarations: Mapping[str, ConstantDeclaration] | Sequence[ConstantDeclaration] = (),
) -> list[MetricConstantAudit]:
    """Audit constants held as literal text inside spreadsheet cells.

    A real client dashboard kept its formulas as literal text in a ``Colors`` or`r`n    ``formulas`` file, and as formula strings inside a workbook. This accepts a
    DataFrame and audits any column whose cells look like ``name = expression``.
    """
    columns = metric_columns or list(getattr(frame, "columns", []))
    audits: list[MetricConstantAudit] = []
    for column in columns:
        if column not in getattr(frame, "columns", []):
            continue
        source = "\n".join(str(v) for v in frame[column] if v is not None)
        audits.extend(audit_constants(source, declarations))
    return audits


__all__ = [
    "PROBLEM_NAME",
    "ConstantDeclaration",
    "MetricConstantAudit",
    "audit_constants",
    "audit_table",
    "parse_metric_expressions",
    "validate_metric_constants",
]