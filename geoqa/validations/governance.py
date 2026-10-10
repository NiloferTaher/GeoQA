"""Metadata governance: is this dataset safe to publish, reuse and defend?

The gap this fills
------------------
Existing validators check that a dataset is internally sound. This one checks
whether anyone is *allowed* to do anything with it, and whether anybody can be
held responsible for it.

The distinction matters because the two failures look identical in the data. A
layer with no licence and a layer with a correct licence are byte-identical.
The first cannot lawfully be reused, the second can, and nothing in the file
tells a reader which they are holding. So it has to be recorded somewhere, and
"somewhere" is metadata. This module checks that somewhere.

Provenance
----------
The required elements and their multiplicities come from Commission Regulation
(EC) No 1205/2008, the implementing rules for the INSPIRE Directive 2007/2/EC,
which fixes the minimum metadata a spatial dataset must carry. The open-by-
default principle comes from Directive (EU) 2019/1024 (Open Data Directive),
which requires public sector data to be reusable under standard open terms. The
broader governance frame — data stewardship, sharing agreements, quality
assurance — comes from Regulation (EU) 2022/868 (Data Governance Act) and
Regulation (EU) 2024/903 (Interoperable Europe Act).

Nothing here is jurisdiction-specific. INSPIRE is used as a *complete, citable
checklist* because it is one of the few that specifies multiplicities, which is
what makes "missing" decidable rather than a matter of taste. A caller who is
not under INSPIRE can still use it as a baseline and ignore what does not apply.

The element that matters most
-----------------------------
**Licence.** Regulation 1205/2008 reference 8.1 requires conditions applying to
access and use, multiplicity 1..*. A dataset without a recorded licence is not
publishable and not defensibly reusable. It is reported as high rather than
critical, because a dataset that has never been published cannot breach a term
that was never agreed. It becomes critical the moment anyone acts on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "governance_metadata"

#: Elements required by Regulation (EC) No 1205/2008, with their references.
#: ``(reference, description, multiplicity)``
INSPIRE_ELEMENTS: dict[str, tuple[str, str, str]] = {
    "title": ("1.1", "Resource title", "1"),
    "abstract": ("1.2", "Resource abstract", "1"),
    "resource_type": ("1.3", "Resource type", "1"),
    "unique_identifier": ("1.5", "Unique resource identifier", "1..*"),
    "topic_category": ("2.1", "Topic category", "1..*"),
    "keyword": ("3", "Keyword", "1..*"),
    "geographic_extent": ("4.1", "Geographic bounding box", "1..*"),
    "temporal_reference": ("5", "Temporal reference", "1..*"),
    "lineage": ("6.1", "Lineage", "1"),
    "conformity": ("7", "Conformity with the implementing rules", "1..*"),
    "conditions_for_access_and_use": ("8.1", "Conditions for access and use", "1..*"),
    "limitations_on_public_access": ("8.2", "Limitations on public access", "1..*"),
    "responsible_organisation": ("9", "Responsible organisation", "1..*"),
    "metadata_point_of_contact": ("10.1", "Metadata point of contact", "1..*"),
    "metadata_date": ("10.2", "Metadata date", "1"),
    "metadata_language": ("10.3", "Metadata language", "1"),
}

#: The elements that decide whether anyone may lawfully use the data.
RIGHTS_ELEMENTS = ("conditions_for_access_and_use", "limitations_on_public_access")

#: The elements that decide who answers for it.
ACCOUNTABILITY_ELEMENTS = ("responsible_organisation", "metadata_point_of_contact")

#: Licence terms treated as open by default under Directive (EU) 2019/1024.
OPEN_LICENCE_MARKERS = (
    "cc0", "cc-by", "cc by", "odbl", "odc-by", "open data commons",
    "mit", "bsd", "apache", "unlicense", "public domain", "open licence", "open license",
)

#: Text that is a placeholder rather than a decision.
PLACEHOLDER_MARKERS = (
    "tbd", "todo", "n/a", "na", "none", "unknown", "pending", "xxx", "???",
    "to be confirmed", "to be decided", "see later", "-",
)

#: Metadata older than this is treated as needing review, in days.
DEFAULT_STALE_DAYS = 365 * 2


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _is_absent(value: Any) -> bool:
    """Is this element simply not there?"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _is_placeholder(value: Any) -> bool:
    """Is this element filled with text standing in for a decision?

    Kept separate from :func:`_is_absent` because the two need different
    findings: a blank field and a field reading ``TBD`` both block publication,
    but only one of them tells you nobody wrote anything down.
    """
    return isinstance(value, str) and value.strip().lower() in PLACEHOLDER_MARKERS


def _is_missing(value: Any) -> bool:
    """Absent, or filled with a placeholder. Neither is a decision."""
    return _is_absent(value) or _is_placeholder(value)


def _flatten(metadata: Mapping[str, Any], key: str) -> Any:
    """Look a key up at the top level, then case-insensitively, then nested."""
    if key in metadata:
        return metadata[key]
    lowered = key.lower()
    for candidate, value in metadata.items():
        if str(candidate).strip().lower() == lowered:
            return value
    for container in ("metadata", "identification", "contact", "distribution"):
        nested = metadata.get(container)
        if isinstance(nested, Mapping):
            for candidate, value in nested.items():
                if str(candidate).strip().lower() == lowered:
                    return value
    return None


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return " ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_as_text(item) for item in value)
    return str(value)


def parse_metadata_date(value: Any) -> date | None:
    """Read a metadata date in the forms INSPIRE records allow."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%Y/%m/%d", "%Y"):
        try:
            parsed = datetime.strptime(text[: len(pattern) + 6].strip(), pattern)
        except ValueError:
            continue
        return parsed.date()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def licence_looks_open(conditions: Any) -> bool:
    """Does the recorded licence look like an open one?"""
    if _is_missing(conditions):
        return False
    text = _as_text(conditions).lower()
    return any(marker in text for marker in OPEN_LICENCE_MARKERS)


def validate_governance_metadata(
    metadata: Mapping[str, Any],
    *,
    required_elements: Sequence[str] | None = None,
    require_open_licence: bool = False,
    stale_after_days: int | None = DEFAULT_STALE_DAYS,
    today: date | None = None,
) -> list[Any]:
    """Report metadata that prevents lawful, accountable use of a dataset.

    Conditions emitted
    ------------------
    ``governance_licence_not_declared``
        No conditions for access and use are recorded. High: the file and the
        data are indistinguishable from one that may not be reused at all.
    ``governance_licence_not_open``
        A licence is recorded but is not an open one. Medium, and only raised
        when ``require_open_licence`` is set, because a restricted licence is
        a legitimate choice.
    ``governance_accountability_unassigned``
        No responsible organisation or point of contact. High: nobody is
        answerable for the dataset.
    ``governance_lineage_undeclared``
        No lineage statement. High: the processing history is unknown, so
        positional accuracy cannot be interpreted.
    ``governance_conformity_undeclared``
        No conformity declaration against a specification. Medium.
    ``governance_unique_identifier_missing``
        No unique resource identifier, so the dataset cannot be cited or
        versioned unambiguously.
    ``governance_temporal_reference_missing``
        No temporal reference, so the dataset has no stated currency.
    ``governance_metadata_stale``
        The metadata date is older than ``stale_after_days``.
    ``governance_metadata_element_missing``
        Any other required element is absent.
    ``governance_metadata_element_placeholder``
        A required element holds placeholder text rather than a value.
    """
    if metadata is None:
        raise ValueError("metadata is required; pass the record being assessed")

    issues: list[Any] = []
    elements = tuple(required_elements) if required_elements else tuple(INSPIRE_ELEMENTS)
    present: dict[str, Any] = {}

    for key in elements:
        value = _flatten(metadata, key)
        present[key] = value

        if _is_absent(value):
            reference, description, multiplicity = INSPIRE_ELEMENTS.get(
                key, ("", key.replace("_", " "), "1..*")
            )
            if key in RIGHTS_ELEMENTS:
                issues.append(
                    _issue(
                        "governance_licence_not_declared", "high",
                        f"No {description} is recorded (INSPIRE {reference}, multiplicity "
                        f"{multiplicity}). A dataset with no recorded terms cannot lawfully "
                        "be reused, and nothing in the data distinguishes it from one that "
                        "may not be",
                        {"element": key, "reference": reference, "multiplicity": multiplicity},
                    )
                )
            elif key in ACCOUNTABILITY_ELEMENTS:
                issues.append(
                    _issue(
                        "governance_accountability_unassigned", "high",
                        f"No {description} is recorded (INSPIRE {reference}). Nobody is "
                        "named as answerable for this dataset, so a question about it has no "
                        "recipient",
                        {"element": key, "reference": reference},
                    )
                )
            elif key == "lineage":
                issues.append(
                    _issue(
                        "governance_lineage_undeclared", "high",
                        "No lineage statement is recorded (INSPIRE 6.1, multiplicity 1). "
                        "Without the processing history, a declared positional accuracy "
                        "cannot be interpreted and a known error cannot be traced",
                        {"element": key, "reference": "6.1"},
                    )
                )
            elif key == "conformity":
                issues.append(
                    _issue(
                        "governance_conformity_undeclared", "medium",
                        "No conformity declaration is recorded (INSPIRE 7). A consumer cannot "
                        "tell whether a specification applies or was checked against",
                        {"element": key, "reference": "7"},
                    )
                )
            elif key == "unique_identifier":
                issues.append(
                    _issue(
                        "governance_unique_identifier_missing", "medium",
                        "No unique resource identifier is recorded (INSPIRE 1.5, multiplicity "
                        "1..*). The dataset cannot be cited or versioned unambiguously",
                        {"element": key, "reference": "1.5"},
                    )
                )
            elif key == "temporal_reference":
                issues.append(
                    _issue(
                        "governance_temporal_reference_missing", "medium",
                        "No temporal reference is recorded (INSPIRE 5, multiplicity 1..*). The "
                        "dataset has no stated currency, so nobody can tell whether it is current",
                        {"element": key, "reference": "5"},
                    )
                )
            else:
                issues.append(
                    _issue(
                        "governance_metadata_element_missing", "medium",
                        f"{description} is absent (INSPIRE {reference}, multiplicity "
                        f"{multiplicity})",
                        {"element": key, "reference": reference, "multiplicity": multiplicity},
                    )
                )
            continue

        if _is_placeholder(value):
            if key in RIGHTS_ELEMENTS:
                issues.append(
                    _issue(
                        "governance_licence_not_declared", "high",
                        f"Conditions for access and use is recorded as {str(value).strip()!r}, "
                        "which is a placeholder rather than a decision. A dataset with no "
                        "agreed terms cannot lawfully be reused",
                        {"element": key, "value": str(value).strip()},
                    )
                )
            else:
                issues.append(
                    _issue(
                        "governance_metadata_element_placeholder", "medium",
                        f"{key.replace('_', ' ')} is recorded as {str(value).strip()!r}, which is "
                        "a placeholder rather than a decision",
                        {"element": key, "value": str(value).strip()},
                    )
                )

    conditions = present.get("conditions_for_access_and_use")
    if not _is_missing(conditions) and require_open_licence and not licence_looks_open(conditions):
        issues.append(
            _issue(
                "governance_licence_not_open", "medium",
                f"Conditions for access and use are recorded as {_as_text(conditions)!r}, which "
                "is not an open licence. Under Directive (EU) 2019/1024 public sector data "
                "should be open by default, so confirm this restriction is intended",
                {"element": "conditions_for_access_and_use", "value": _as_text(conditions)},
            )
        )

    if stale_after_days is not None:
        recorded = parse_metadata_date(present.get("metadata_date"))
        if recorded is not None:
            reference_day = today or datetime.now(timezone.utc).date()
            age = (reference_day - recorded).days
            if age > stale_after_days:
                issues.append(
                    _issue(
                        "governance_metadata_stale", "medium",
                        f"Metadata was last reviewed on {recorded.isoformat()}, {age} days ago. "
                        f"The review threshold is {stale_after_days} days. A stale record still "
                        "looks authoritative to a consumer",
                        {
                            "metadata_date": recorded.isoformat(),
                            "age_days": age,
                            "threshold_days": stale_after_days,
                        },
                    )
                )

    return issues


def governance_report(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """A short statement of what is and is not established about a dataset."""
    elements = tuple(INSPIRE_ELEMENTS)
    present = {key: not _is_missing(_flatten(metadata, key)) for key in elements}

    conditions = _flatten(metadata, "conditions_for_access_and_use")
    return {
        "elements_required": len(elements),
        "elements_present": sum(1 for value in present.values() if value),
        "missing": [key for key, value in present.items() if not value],
        "licence_recorded": not _is_missing(conditions),
        "licence_appears_open": licence_looks_open(conditions),
        "accountability_assigned": all(
            present.get(key, False) for key in ACCOUNTABILITY_ELEMENTS
        ),
        "publishable": all(
            present.get(key, False) for key in RIGHTS_ELEMENTS + ACCOUNTABILITY_ELEMENTS
        ),
    }


__all__ = [
    "ACCOUNTABILITY_ELEMENTS",
    "DEFAULT_STALE_DAYS",
    "INSPIRE_ELEMENTS",
    "OPEN_LICENCE_MARKERS",
    "PLACEHOLDER_MARKERS",
    "PROBLEM_NAME",
    "RIGHTS_ELEMENTS",
    "governance_report",
    "licence_looks_open",
    "parse_metadata_date",
    "validate_governance_metadata",
]