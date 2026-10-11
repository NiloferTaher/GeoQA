"""Keys that are not a single column.

Three things a data-quality library needs from keys, and none of them is
"is this column unique".

**Compound natural keys.** Real records are identified by a combination: an
asset, an inspector, and an hour. Two rows matching all three is a duplicate
visit. Matching only the asset is not a duplicate, because the same asset is
legitimately inspected repeatedly. The timestamp has to be truncated to its
declared granularity first, or two records two minutes apart read as two
different hours.

**Field aliases.** The same quantity arrives under several names. Resolving
an asset identifier to whichever of its two historical names is present is necessary.
Resolving to the *first* match is not, because a layer carrying both names is
ambiguous and first-match hides it. Ambiguity is reported rather than
resolved.

**Fuzzy binding.** Matching a filename to a controlled-vocabulary term by
similarity is unavoidable when the names are human-entered. Taking the best
match alone hides the case where two terms both match well, which is exactly
the case where the file gets attached to the wrong region. Both the ambiguous
and the unbound cases are reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "truncate_timestamp",
    "compound_key_duplicates",
    "resolve_field",
    "resolve_schema",
    "bind_to_vocabulary",
    "VocabularyBinding",
]


def truncate_timestamp(value: Any, granularity: str = "hour") -> Any:
    """Reduce a timestamp to its declared granularity.

    ``second``, ``minute``, ``hour``, ``day``. Anything finer than the
    declared granularity is discarded, because the key is meant to express
    "this visit in this hour" and two records ninety seconds apart are one
    visit, not two.
    """
    if value is None:
        return None
    stamp: datetime
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            stamp = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except Exception:
            return value

    if granularity == "second":
        return stamp.replace(microsecond=0)
    if granularity == "minute":
        return stamp.replace(second=0, microsecond=0)
    if granularity == "hour":
        return stamp.replace(minute=0, second=0, microsecond=0)
    if granularity == "day":
        return stamp.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"unknown granularity: {granularity!r}")


def compound_key_duplicates(
    frame: Any,
    *,
    key_fields: Sequence[str],
    timestamp_field: str | None = None,
    granularity: str = "hour",
) -> list[ValidationIssue]:
    """Report rows sharing a compound natural key.

    Every member of a duplicate group is reported, not just the repeats,
    because the operator has to decide which row survives and cannot do that
    from a list of extras.
    """
    issues: list[ValidationIssue] = []
    missing = [f for f in key_fields if f not in getattr(frame, "columns", [])]
    if timestamp_field and timestamp_field not in getattr(frame, "columns", []):
        missing = missing + [timestamp_field]
    if missing:
        return issues

    fields = list(key_fields) + ([timestamp_field] if timestamp_field else [])
    counts: dict[tuple, list[Any]] = {}
    try:
        rows = frame[fields].iterrows()
    except Exception:
        return issues

    for index, row in rows:
        parts = []
        usable = True
        for field in fields:
            value = row.get(field)
            if field == timestamp_field:
                value = truncate_timestamp(value, granularity)
            if value is None or (isinstance(value, float) and value != value):
                usable = False
                break
            parts.append(str(value).strip())
        if not usable:
            continue
        counts.setdefault(tuple(parts), []).append(index)

    for key, members in sorted(counts.items()):
        if len(members) < 2:
            continue
        rendered = ", ".join(f"{f}={v!r}" for f, v in zip(fields, key))
        for index in members:
            issues.append(
                build_issue(
                    "compound_key_duplicate",
                    index=index,
                    description=(
                        f"{len(members)} records share the compound key ({rendered}) at "
                        f"{granularity} granularity. The same visit recorded more than "
                        "once inflates every count derived from it."
                    ),
                    extra={
                        "key_fields": fields,
                        "key": list(key),
                        "granularity": granularity,
                        "group_size": len(members),
                        "members": [str(m) for m in members],
                    },
                )
            )
    return issues


def resolve_field(
    columns: Iterable[str], aliases: Sequence[str]
) -> dict[str, Any]:
    """Resolve one logical field to a physical column, or report the ambiguity.

    Returns ``column`` when exactly one alias is present, ``candidates`` when
    more than one is, and ``missing`` when none is. Picking one of several
    would make the result depend on iteration order, which is not a property
    anyone can reason about.
    """
    present = {str(c) for c in columns}
    found = [alias for alias in aliases if alias in present]
    if len(found) == 1:
        return {"status": "resolved", "column": found[0], "candidates": found}
    if len(found) > 1:
        return {"status": "ambiguous", "column": None, "candidates": found}
    return {"status": "missing", "column": None, "candidates": []}


def resolve_schema(
    columns: Iterable[str], schema: Mapping[str, Sequence[str]]
) -> list[ValidationIssue]:
    """Resolve a whole schema, reporting missing and ambiguous fields."""
    issues: list[ValidationIssue] = []
    present = list(columns)
    for logical, aliases in schema.items():
        result = resolve_field(present, aliases)
        if result["status"] == "missing":
            issues.append(
                build_issue(
                    "schema_field_missing",
                    description=(
                        f"Required field {logical!r} is absent. It was looked for under "
                        + ", ".join(repr(a) for a in aliases)
                        + "."
                    ),
                    extra={"field": logical, "aliases": list(aliases)},
                )
            )
        elif result["status"] == "ambiguous":
            issues.append(
                build_issue(
                    "schema_field_ambiguous",
                    description=(
                        f"Field {logical!r} is present under more than one name ("
                        + ", ".join(repr(c) for c in result["candidates"])
                        + "). Which one holds the data cannot be determined, so the "
                        "field is not read."
                    ),
                    extra={"field": logical, "candidates": result["candidates"]},
                )
            )
    return issues


@dataclass
class VocabularyBinding:
    """Outcome of binding names to a controlled vocabulary."""

    query: str
    match: str | None = None
    score: float = 0.0
    ambiguous_with: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.ambiguous_with:
            return "ambiguous"
        if self.match is None:
            return "unbound"
        return "bound"

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "match": self.match,
            "score": self.score,
            "status": self.status,
            "ambiguous_with": list(self.ambiguous_with),
        }


def bind_to_vocabulary(
    names: Iterable[str],
    vocabulary: Sequence[str],
    *,
    cutoff: float = 0.7,
    normalise: Any = None,
) -> list[VocabularyBinding]:
    """Bind names to vocabulary terms by similarity, flagging ambiguity.

    A single best match is what a convenience implementation returns, and it
    is exactly what hides the failure: when two terms both score above the
    cutoff, choosing the higher one attaches the record to the wrong one of
    two plausible candidates without any indication that a choice was made.
    """
    try:
        from difflib import SequenceMatcher
    except Exception:
        return []

    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def prep(value: str) -> str:
        return normalise(value) if normalise else str(value).strip().lower()

    prepared = [(term, prep(term)) for term in vocabulary]
    bindings: list[VocabularyBinding] = []

    for name in names:
        query = prep(name)
        scored = [
            (term, similarity(query, term_prepared))
            for term, term_prepared in prepared
        ]
        above = [(term, score) for term, score in scored if score >= cutoff]
        if not above:
            bindings.append(VocabularyBinding(query=str(name), match=None, score=0.0))
            continue

        best_term, best_score = max(above, key=lambda kv: (kv[1], kv[0]))
        others = sorted(term for term, _ in above if term != best_term)
        bindings.append(
            VocabularyBinding(
                query=str(name),
                match=best_term,
                score=round(best_score, 4),
                ambiguous_with=others,
            )
        )
    return bindings


def validate_vocabulary_binding(bindings: Sequence[VocabularyBinding]) -> list[ValidationIssue]:
    """Report ambiguous and unbound names as issues."""
    issues: list[ValidationIssue] = []
    for binding in bindings:
        if binding.status == "ambiguous":
            issues.append(
                build_issue(
                    "vocabulary_binding_ambiguous",
                    description=(
                        f"{binding.query!r} matches {binding.match!r} at "
                        f"{binding.score:.2f} but also "
                        + ", ".join(repr(t) for t in binding.ambiguous_with)
                        + ". It has been attached to one of several plausible terms, "
                        "which is a choice that was not recorded."
                    ),
                    extra=binding.to_dict(),
                )
            )
        elif binding.status == "unbound":
            issues.append(
                build_issue(
                    "vocabulary_binding_unbound",
                    description=(
                        f"{binding.query!r} matches no vocabulary term above the "
                        "declared cutoff and has been left unattached."
                    ),
                    extra=binding.to_dict(),
                )
            )
    return issues