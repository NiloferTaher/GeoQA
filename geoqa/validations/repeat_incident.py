"""Cross-period recurrence: the same finding appearing in more than one period.

The condition
-------------
A leak position that recurs across survey periods is not one leak. It is a
persistent problem area, and it is the single most useful signal for repair
prioritisation. Two cases matter and they mean different things:

``repeat_same_asset``
    The same logical asset keeps failing. Chronic asset defect: the pipe or
    fitting itself needs replacing.

``repeat_same_place``
    A location recurs but the logical asset differs. The asset is not the
    problem, so replacing it will not help. The cause is upstream: a main, a
    boundary, an area-level condition.

Reporting a single "repeated" count would collapse those two, and the second
is the one that saves an excavation.

Period gaps
-----------
Absence of a period is not absence of a defect. If a survey period is missing,
"appeared in 3 of 4 periods" and "appeared in 3 of 3 periods" are different
claims, and only one of them is supported. A gap is therefore reported
separately rather than being silently absorbed.

Provenance
----------
The pattern is observed in operational reporting where field layers arrive as
fragments across months rather than as one complete history, so recurrence is
assembled from accumulated periods. That history can be incomplete, which is
why the period list is reported alongside every recurrence finding.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "repeat_incident"

#: A location separated by less than this is treated as the same place.
DEFAULT_LOCATION_TOLERANCE_M = 25.0

#: Overlap fraction above which two geometries are considered the same location.
DEFAULT_OVERLAP_FRACTION = 0.5


@dataclass
class RepeatFinding:
    """One recurring location, across two or more periods."""

    location_id: int
    periods: tuple[str, ...]
    asset_ids: tuple[str, ...]
    overlap_area_m2: float
    overlap_fraction: float
    kind: str  # "repeat_same_asset" | "repeat_same_place"

    @property
    def period_count(self) -> int:
        return len(self.periods)

    @property
    def repeats(self) -> int:
        return max(0, self.period_count - 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "periods": list(self.periods),
            "asset_ids": list(self.asset_ids),
            "period_count": self.period_count,
            "repeats": self.repeats,
            "overlap_area_m2": self.overlap_area_m2,
            "overlap_fraction": round(self.overlap_fraction, 4),
            "kind": self.kind,
        }


@dataclass
class RepeatProfile:
    occurrences: int = 0
    findings: list[RepeatFinding] = field(default_factory=list)
    same_asset: int = 0
    same_place: int = 0
    periods_seen: tuple[str, ...] = ()
    period_gaps: tuple[tuple[str, str], ...] = ()

    def summary(self) -> dict[str, Any]:
        return {
            "occurrences": self.occurrences,
            "repeat_findings": len(self.findings),
            "repeat_same_asset": self.same_asset,
            "repeat_same_place": self.same_place,
            "periods_seen": list(self.periods_seen),
            "period_gaps": [list(gap) for gap in self.period_gaps],
        }


def _geometry(row: Any) -> Any:
    try:
        if "geometry" in row.index:
            return row["geometry"]
    except Exception:
        pass
    return getattr(row, "geometry", None)


def _asset_id(row: Any, key_column: str | None, index: Any) -> str | None:
    if key_column and key_column in getattr(row, "index", []):
        value = row[key_column]
        return str(value) if value is not None else None
    return None


def detect_period_gaps(periods: Sequence[str]) -> list[tuple[str, str]]:
    """Report consecutive periods that are present but non-contiguous.

    Period labels are compared as strings. A gap means a period is missing
    between two observed ones, which weakens any recurrence claim that spans it.
    """
    ordered = sorted({str(p) for p in periods}, key=_period_sort_key)
    gaps: list[tuple[str, str]] = []
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier == later:
            continue
        # Only treat a jump as a gap when both labels resolve to the same
        # convention. Otherwise the labels mean different things and no
        # inference is safe.
        before = _period_key(earlier)
        after = _period_key(later)
        if before is None or after is None:
            continue
        steps = _period_distance(before, after)
        if steps > 1:
            gaps.append((earlier, later))
    return gaps


def _period_sort_key(period: str):
    key = _period_key(period)
    return (key is None, key or (0, 0), str(period))


def _period_distance(before: tuple[int, int], after: tuple[int, int]) -> int:
    """Number of nominal periods between two resolved labels."""
    return (after[0] - before[0]) * 12 + (after[1] - before[1])


def _period_key(period: str):
    """Return (year, index) for a recognisable period label, else None.

    Accepts a label with the year anywhere in it, so both ``2025-03`` and
    ``Mar2025`` resolve to the same ordinal.
    """
    import re

    text = str(period).strip()
    year_match = re.search(r"(\d{4})", text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    rest = (text[: year_match.start()] + text[year_match.end():]).strip()
    rest = rest.strip("-_/ ").lower()
    if not rest:
        return (year, 0)
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    if rest in months:
        return (year, months[rest])
    if rest.isdigit():
        index = int(rest)
        return (year, index if index <= 12 else 0)
    return None


def profile_repeats(
    layer: Any,
    *,
    period_column: str,
    key_column: str | None = None,
    location_tolerance_m: float = DEFAULT_LOCATION_TOLERANCE_M,
    overlap_fraction: float = DEFAULT_OVERLAP_FRACTION,
    expected_periods: Sequence[str] | None = None,
) -> RepeatProfile:
    """Find locations recurring across periods, distinguishing cause.

    ``period_column`` names the survey period. ``key_column`` names the logical
    asset; supply it and recurrence is separated into chronic-asset and
    something-else, which is the distinction that changes what gets repaired.
    Without it, only the location is known and the kind is reported as
    ``repeat_unattributed``.
    """
    if period_column not in getattr(layer, "columns", []):
        raise KeyError(f"period column {period_column!r} is not in the layer")

    profile = RepeatProfile()
    observations: list[dict[str, Any]] = []

    for index, row in layer.iterrows():
        geometry = _geometry(row)
        period = row[period_column]
        if geometry is None or period is None or getattr(geometry, "is_empty", True):
            continue
        observations.append(
            {
                "index": index,
                "geometry": geometry,
                "period": str(period),
                "asset": _asset_id(row, key_column, index),
            }
        )

    profile.occurrences = len(observations)
    seen_periods = sorted({o["period"] for o in observations})
    if expected_periods:
        observed_set = set(seen_periods)
        for period in expected_periods:
            if str(period) not in observed_set:
                profile.periods_seen = tuple(sorted(set(seen_periods) | {str(period)}))
                break
        else:
            profile.periods_seen = tuple(seen_periods)
    else:
        profile.periods_seen = tuple(seen_periods)

    profile.period_gaps = tuple(detect_period_gaps(seen_periods))
    if expected_periods:
        expected_set = {str(p) for p in expected_periods}
        for period in sorted(expected_set - set(seen_periods)):
            profile.period_gaps = profile.period_gaps + ((str(period), "<absent>"),)

    if len(observations) < 2:
        return profile

    # Group observations into locations by spatial coincidence within tolerance.
    locations: list[dict[str, Any]] = []
    for observation in observations:
        placed = False
        for location in locations:
            if _same_place(
                location["geometry"], observation["geometry"],
                tolerance=location_tolerance_m, fraction=overlap_fraction,
            ):
                location["members"].append(observation)
                if location["geometry"] is None:
                    location["geometry"] = observation["geometry"]
                placed = True
                break
        if not placed:
            locations.append(
                {"geometry": observation["geometry"], "members": [observation]}
            )

    for location_id, location in enumerate(locations):
        members = location["members"]
        periods = sorted({m["period"] for m in members})
        if len(periods) < 2:
            continue
        assets = tuple(
            sorted({m["asset"] for m in members if m["asset"] is not None})
        )
        union = None
        for member in members:
            union = member["geometry"] if union is None else union.union(member["geometry"])
        area = float(getattr(union, "area", 0.0) or 0.0)
        smallest = min(
            float(getattr(m["geometry"], "area", 0.0) or 0.0) for m in members
        )
        fraction = (area / smallest) if smallest > 0 else 1.0

        if key_column is None or not assets:
            kind = "repeat_unattributed"
        elif len(assets) == 1:
            kind = "repeat_same_asset"
        else:
            kind = "repeat_same_place"

        finding = RepeatFinding(
            location_id=location_id,
            periods=tuple(periods),
            asset_ids=assets,
            overlap_area_m2=area,
            overlap_fraction=fraction,
            kind=kind,
        )
        profile.findings.append(finding)
        if kind == "repeat_same_asset":
            profile.same_asset += 1
        elif kind == "repeat_same_place":
            profile.same_place += 1

    profile.findings.sort(key=lambda f: (-f.period_count, f.location_id))
    return profile


def _same_place(a: Any, b: Any, *, tolerance: float, fraction: float) -> bool:
    """Are two geometries the same location for recurrence purposes?"""
    if a is None or b is None:
        return False
    try:
        if a.intersects(b):
            inter = float(getattr(a.intersection(b), "area", 0.0) or 0.0)
            smallest = min(
                float(getattr(a, "area", 0.0) or 0.0),
                float(getattr(b, "area", 0.0) or 0.0),
            )
            if smallest > 0 and inter / smallest >= fraction:
                return True
        if a.distance(b) <= tolerance:
            return True
    except Exception:
        return False
    return False


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_repeats(
    layer: Any,
    *,
    period_column: str,
    key_column: str | None = None,
    location_tolerance_m: float = DEFAULT_LOCATION_TOLERANCE_M,
    overlap_fraction: float = DEFAULT_OVERLAP_FRACTION,
    expected_periods: Sequence[str] | None = None,
    min_periods: int = 2,
) -> list[Any]:
    """Report recurring locations and the gaps that weaken the claim."""
    profile = profile_repeats(
        layer,
        period_column=period_column,
        key_column=key_column,
        location_tolerance_m=location_tolerance_m,
        overlap_fraction=overlap_fraction,
        expected_periods=expected_periods,
    )

    issues: list[Any] = []

    for finding in profile.findings:
        payload = finding.as_dict()
        period_list = ", ".join(finding.periods)

        if finding.kind == "repeat_same_asset":
            issues.append(
                _issue(
                    "repeat_same_asset",
                    "high",
                    f"Location recurs in {finding.period_count} periods ({period_list}) "
                    f"for the same asset {', '.join(finding.asset_ids)}. A chronic asset "
                    "defect: replacing or repairing this component is the indicated action",
                    payload,
                )
            )
        elif finding.kind == "repeat_same_place":
            issues.append(
                _issue(
                    "repeat_same_place",
                    "high",
                    f"Location recurs in {finding.period_count} periods ({period_list}) "
                    f"but the logical asset differs across them "
                    f"({', '.join(finding.asset_ids)}). The asset is not the cause; "
                    "investigate the supplying main, the boundary, or the area condition "
                    "before excavating",
                    payload,
                )
            )
        else:
            issues.append(
                _issue(
                    "repeat_unattributed",
                    "medium",
                    f"Location recurs in {finding.period_count} periods ({period_list}). "
                    "Supply a logical-asset key to separate a chronic asset defect from a "
                    "location problem, which change what should be repaired",
                    payload,
                )
            )

    for earlier, later in profile.period_gaps:
        if later == "<absent>":
            issues.append(
                _issue(
                    "period_missing",
                    "high",
                    f"Expected period {earlier} is absent. Recurrence counts across the "
                    "remaining periods understate the number of periods a location was "
                    "actually investigated",
                    {"missing_period": earlier, "periods_seen": list(profile.periods_seen)},
                )
            )
        else:
            issues.append(
                _issue(
                    "period_gap",
                    "medium",
                    f"Periods jump from {earlier} to {later} with no survey between them, "
                    "so a recurrence spanning the gap cannot be shown to be continuous",
                    {"from": earlier, "to": later},
                )
            )

    return issues


__all__ = [
    "DEFAULT_LOCATION_TOLERANCE_M",
    "DEFAULT_OVERLAP_FRACTION",
    "PROBLEM_NAME",
    "RepeatFinding",
    "RepeatProfile",
    "detect_period_gaps",
    "profile_repeats",
    "validate_repeats",
]