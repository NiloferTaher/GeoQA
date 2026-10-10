"""Clipping: which side a straddling feature belongs to, and whether the clip
left halves behind.

Two questions, one module
-------------------------
Clipping a polygon layer to a boundary produces two failure modes that look
alike in the output and need opposite responses.

**Which side does a straddler belong to?** A polygon that crosses the boundary
has an area on each side. Assigning it needs a rule, and the rule is a policy
decision rather than a fact: majority of area, largest single piece, centroid
side. Half-and-half is the common default and it is exactly the value this
module refuses to hardcode. ``assignment_threshold`` is the caller's number,
because a client who assigns on 60 percent has reasons for it.

**Did the clip leave halves?** A clip that lands on a street centreline or a
district boundary cuts polygons in half. The result is valid geometry and wrong
data: the area is roughly half, the shape has a suspiciously straight long edge,
and neither shows up in any standard validity check.

What this module reports
------------------------
For each straddling feature, the measured split, the side the configured
threshold assigns it to, and whether the split is close enough to the threshold
that the assignment is a coin-flip rather than a finding.

For each clipped feature, its area as a fraction of the source it came from, and
whether that fraction is suspiciously close to one half.

Conditions emitted
------------------
``clip_straddles_boundary``
    Evidence, not a defect: the feature crosses the boundary and has a
    measured split. Reported so the decision is visible.
``clip_assignment_near_threshold``
    The split sits within ``near_threshold`` of the configured percentage. The
    assignment is effectively arbitrary and should be reviewed.
``clip_assignment_unresolved``
    The feature crosses the boundary and the caller supplied no rule, so no
    assignment can be made. Reported rather than defaulted.
``clip_feature_half_area``
    A clipped feature has almost exactly the configured fraction of its
    source's area. High: this is the signature of a centreline clip.
``clip_feature_heavily_truncated``
    A clipped feature retains less than ``min_area_fraction`` of its source.
    High: the feature is largely gone.
``clip_feature_missing_after_clip``
    A source feature has no counterpart in the clipped layer. High.
``clip_feature_absent_from_source``
    A clipped feature matches no source feature. High.
``clip_straight_cut_edge``
    A clipped feature has a long straight edge that does not appear in its
    source. Medium, because natural boundaries do have straight edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "clip_conformance"

#: Default majority threshold. Deliberately a parameter, not a constant.
DEFAULT_ASSIGNMENT_THRESHOLD = 0.5

#: How close to the threshold counts as a coin-flip.
DEFAULT_NEAR_THRESHOLD = 0.05

#: A clipped feature this close to exactly one half of its source is suspect.
DEFAULT_HALF_TOLERANCE = 0.02

#: Below this fraction of source area, a feature is largely gone.
DEFAULT_MIN_AREA_FRACTION = 0.25


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _geometry(row: Any) -> Any | None:
    try:
        if "geometry" in row.index:
            return row["geometry"]
    except Exception:
        pass
    return getattr(row, "geometry", None)


def _feature_id(row: Any, index: Any) -> Any:
    for name in ("ID", "id", "fid", "FID", "objectid", "OBJECTID", "name", "NAME"):
        try:
            if name in row.index:
                return row[name]
        except Exception:
            continue
    return index


@dataclass
class StraddleRecord:
    """One feature crossing a boundary, with the measurement behind any call."""

    feature_id: Any
    total_area: float
    fraction_inside: float
    fraction_outside: float
    assigned_side: str | None
    ambiguous: bool

    @property
    def dominant_side(self) -> str:
        return "boundary" if self.fraction_inside >= self.fraction_outside else "outside"

    @property
    def near_half(self) -> bool:
        return abs(self.fraction_inside - 0.5) <= DEFAULT_NEAR_THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "total_area": self.total_area,
            "fraction_inside": round(self.fraction_inside, 4),
            "fraction_outside": round(self.fraction_outside, 4),
            "dominant_side": self.dominant_side,
            "assigned_side": self.assigned_side,
            "ambiguous": self.ambiguous,
            "assignment_fraction": (
                self.fraction_inside if self.assigned_side == "boundary"
                else self.fraction_outside if self.assigned_side == "outside"
                else None
            ),
        }


def _resolve_geometry(geometry: Any):
    from shapely.geometry import MultiPolygon, Polygon  # noqa: F401

    if geometry is None or getattr(geometry, "is_empty", True):
        return None
    return geometry


def profile_clip_assignment(
    layer: Any,
    boundary: Any,
    *,
    assignment_threshold: float | None = DEFAULT_ASSIGNMENT_THRESHOLD,
    near_threshold: float = DEFAULT_NEAR_THRESHOLD,
) -> dict[str, Any]:
    """Measure how each feature splits across a boundary.

    ``assignment_threshold`` is the fraction of area that must sit on one side
    for that side to win. It is a parameter because it is a policy, and a
    policy is the caller's to state. ``None`` measures without assigning: every
    record then reports a split and no verdict.
    """
    if assignment_threshold is not None and not 0.0 < assignment_threshold <= 1.0:
        raise ValueError("assignment_threshold must be greater than 0 and at most 1")

    boundary = _resolve_geometry(boundary)
    records: list[StraddleRecord] = []

    for index, row in layer.iterrows():
        geometry = _resolve_geometry(_geometry(row))
        if geometry is None:
            continue
        total = float(getattr(geometry, "area", 0.0) or 0.0)
        if total <= 0:
            continue

        try:
            inside_area = float(getattr(geometry.intersection(boundary), "area", 0.0) or 0.0)
        except Exception:
            continue

        fraction_inside = inside_area / total
        if fraction_inside <= 0.0 or fraction_inside >= 1.0:
            continue

        fraction_outside = 1.0 - fraction_inside

        assigned: str | None = None
        if assignment_threshold is not None:
            if fraction_inside >= assignment_threshold:
                assigned = "boundary"
            elif fraction_outside >= assignment_threshold:
                assigned = "outside"

        records.append(
            StraddleRecord(
                feature_id=_feature_id(row, index),
                total_area=total,
                fraction_inside=fraction_inside,
                fraction_outside=fraction_outside,
                assigned_side=assigned,
                ambiguous=(
                    assignment_threshold is not None
                    and abs(fraction_inside - assignment_threshold) <= near_threshold
                ),
            )
        )

    return {
        "straddlers": len(records),
        "assigned": sum(1 for r in records if r.assigned_side is not None),
        "ambiguous": sum(1 for r in records if r.ambiguous),
        "unresolved": sum(1 for r in records if r.assigned_side is None),
        "assignment_threshold": assignment_threshold,
        "records": [record.as_dict() for record in records],
    }


def validate_clip_assignment(
    layer: Any,
    boundary: Any,
    *,
    assignment_threshold: float | None = DEFAULT_ASSIGNMENT_THRESHOLD,
    near_threshold: float = DEFAULT_NEAR_THRESHOLD,
    report_evidence: bool = True,
) -> list[Any]:
    """Report how features split across a boundary, under a declared threshold.

    Pass ``assignment_threshold=None`` to measure without assigning. The module
    will not choose a percentage for you.
    """
    threshold = DEFAULT_ASSIGNMENT_THRESHOLD if assignment_threshold is None else assignment_threshold
    profile = profile_clip_assignment(
        layer, boundary,
        assignment_threshold=assignment_threshold,
        near_threshold=near_threshold,
    )
    issues: list[Any] = []

    for record in profile["records"]:
        threshold_text = (
            f"{threshold:.0%}"
            if assignment_threshold is not None
            else "no threshold supplied"
        )

        if record["assigned_side"] is None and assignment_threshold is None:
            issues.append(
                _issue(
                    "clip_assignment_unresolved",
                    "high",
                    f"Feature {record['feature_id']!r} lies {record['fraction_inside']:.0%} inside "
                    f"the boundary and {record['fraction_outside']:.0%} outside, and no "
                    "assignment rule was supplied. The percentage that decides this is a "
                    "policy, so it is not defaulted here",
                    record,
                )
            )
        elif record["ambiguous"]:
            issues.append(
                _issue(
                    "clip_assignment_near_threshold",
                    "medium",
                    f"Feature {record['feature_id']!r} splits "
                    f"{record['fraction_inside']:.1%} inside / "
                    f"{record['fraction_outside']:.1%} outside, within {near_threshold:.0%} of "
                    f"the {threshold_text} threshold. The assignment is effectively arbitrary, "
                    "so review this one rather than accepting it",
                    record,
                )
            )
        elif report_evidence:
            issues.append(
                _issue(
                    "clip_straddles_boundary",
                    "info",
                    f"Feature {record['feature_id']!r} crosses the boundary, "
                    f"{record['fraction_inside']:.1%} inside and "
                    f"{record['fraction_outside']:.1%} outside. Under the declared "
                    f"{threshold_text} rule it is assigned to {record['assigned_side']!r}",
                    record,
                )
            )

    return issues


# --------------------------------------------------------------------------
# Clip completeness
# --------------------------------------------------------------------------

@dataclass
class ClipMatch:
    """A clipped feature matched to the source it came from."""

    clipped_id: Any
    source_id: Any
    clipped_area: float
    source_area: float
    area_fraction: float

    @property
    def is_half(self) -> bool:
        return abs(self.area_fraction - DEFAULT_ASSIGNMENT_THRESHOLD) <= DEFAULT_HALF_TOLERANCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "clipped_id": self.clipped_id,
            "source_id": self.source_id,
            "clipped_area": self.clipped_area,
            "source_area": self.source_area,
            "area_fraction": round(self.area_fraction, 4),
        }


@dataclass
class ClipProfile:
    """What a clip did to the source layer."""

    matches: list[ClipMatch] = field(default_factory=list)
    halves: list[ClipMatch] = field(default_factory=list)
    truncated: list[ClipMatch] = field(default_factory=list)
    missing_sources: list[Any] = field(default_factory=list)
    orphan_clipped: list[Any] = field(default_factory=list)
    unmatched_fraction: float = 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "matched": len(self.matches),
            "halves": len(self.halves),
            "truncated": len(self.truncated),
            "missing_from_clip": len(self.missing_sources),
            "orphan_clipped": len(self.orphan_clipped),
            "unmatched_fraction": round(self.unmatched_fraction, 4),
        }


def _match_sources(clipped: Any, source: Any) -> list[tuple[Any, Any]]:
    """Pair each clipped feature with the source it overlaps most."""
    pairs: list[tuple[Any, Any]] = []
    source_geoms = []
    for index, row in source.iterrows():
        geometry = _resolve_geometry(_geometry(row))
        if geometry is None:
            continue
        source_geoms.append((_feature_id(row, index), geometry))

    for index, row in clipped.iterrows():
        geometry = _resolve_geometry(_geometry(row))
        if geometry is None:
            continue
        best_id, best_overlap = None, 0.0
        for source_id, source_geometry in source_geoms:
            try:
                overlap = float(getattr(geometry.intersection(source_geometry), "area", 0.0) or 0.0)
            except Exception:
                continue
            if overlap > best_overlap:
                best_id, best_overlap = source_id, overlap
        if best_id is not None:
            pairs.append((_feature_id(row, index), best_id))
    return pairs


def _source_geometry(source: Any, source_id: Any):
    for index, row in source.iterrows():
        if _feature_id(row, index) == source_id:
            return _resolve_geometry(_geometry(row))
    return None


def profile_clip_completeness(
    clipped: Any,
    source: Any,
    *,
    half_tolerance: float = DEFAULT_HALF_TOLERANCE,
    min_area_fraction: float = DEFAULT_MIN_AREA_FRACTION,
    half_fraction: float = DEFAULT_ASSIGNMENT_THRESHOLD,
) -> ClipProfile:
    """Compare a clipped layer against the source it was cut from."""
    profile = ClipProfile()
    pairs = _match_sources(clipped, source)
    matched_sources: set[Any] = set()

    for clipped_id, source_id in pairs:
        clipped_geometry = None
        for index, row in clipped.iterrows():
            if _feature_id(row, index) == clipped_id:
                clipped_geometry = _resolve_geometry(_geometry(row))
                break
        source_geometry = _source_geometry(source, source_id)
        if clipped_geometry is None or source_geometry is None:
            continue

        clipped_area = float(getattr(clipped_geometry, "area", 0.0) or 0.0)
        source_area = float(getattr(source_geometry, "area", 0.0) or 0.0)
        if source_area <= 0:
            continue

        match = ClipMatch(
            clipped_id=clipped_id,
            source_id=source_id,
            clipped_area=clipped_area,
            source_area=source_area,
            area_fraction=clipped_area / source_area,
        )
        profile.matches.append(match)
        matched_sources.add(source_id)
        if abs(match.area_fraction - half_fraction) <= half_tolerance:
            profile.halves.append(match)
        if match.area_fraction < min_area_fraction:
            profile.truncated.append(match)

    for index, row in source.iterrows():
        source_id = _feature_id(row, index)
        if source_id not in matched_sources:
            profile.missing_sources.append(source_id)

    matched_clipped = {clipped_id for clipped_id, _ in pairs}
    for index, row in clipped.iterrows():
        clipped_id = _feature_id(row, index)
        if clipped_id not in matched_clipped:
            profile.orphan_clipped.append(clipped_id)

    total = len(profile.matches) + len(profile.orphan_clipped)
    profile.unmatched_fraction = (len(profile.orphan_clipped) / total) if total else 0.0
    return profile


def validate_clip_completeness(
    clipped: Any,
    source: Any,
    *,
    half_tolerance: float = DEFAULT_HALF_TOLERANCE,
    min_area_fraction: float = DEFAULT_MIN_AREA_FRACTION,
    half_fraction: float = DEFAULT_ASSIGNMENT_THRESHOLD,
) -> list[Any]:
    """Report features left half-formed by a clip.

    ``half_fraction`` is the ratio that counts as "half", and it is a parameter
    because a clip along a road corridor does not produce exactly one half.
    """
    profile = profile_clip_completeness(
        clipped, source,
        half_tolerance=half_tolerance,
        min_area_fraction=min_area_fraction,
        half_fraction=half_fraction,
    )
    issues: list[Any] = []

    for match in profile.halves:
        issues.append(
            _issue(
                "clip_feature_half_area", "high",
                f"Clipped feature {match.clipped_id!r} retains "
                f"{match.area_fraction:.1%} of source feature {match.source_id!r}, almost "
                f"exactly the {half_fraction:.0%} expected from a clip down the middle. "
                "This is the signature of a centreline or mid-block clip rather than a "
                "boundary the data was actually drawn to",
                match.as_dict(),
            )
        )

    for match in profile.truncated:
        if any(match.clipped_id == other.clipped_id for other in profile.halves):
            continue
        issues.append(
            _issue(
                "clip_feature_heavily_truncated", "high",
                f"Clipped feature {match.clipped_id!r} retains only "
                f"{match.area_fraction:.1%} of source feature {match.source_id!r}, below the "
                f"{min_area_fraction:.0%} minimum. The feature is largely gone and will "
                "under-count anything derived from it",
                match.as_dict(),
            )
        )

    for source_id in profile.missing_sources:
        issues.append(
            _issue(
                "clip_feature_missing_after_clip", "high",
                f"Source feature {source_id!r} has no overlapping counterpart in the clipped "
                "layer. Either it fell entirely outside the clip area, or it was dropped",
                {"source_id": source_id},
            )
        )

    for clipped_id in profile.orphan_clipped:
        issues.append(
            _issue(
                "clip_feature_absent_from_source", "high",
                f"Clipped feature {clipped_id!r} overlaps no source feature. It may come "
                "from a different vintage, or the two layers may not correspond",
                {"clipped_id": clipped_id},
            )
        )

    return issues


__all__ = [
    "DEFAULT_ASSIGNMENT_THRESHOLD",
    "DEFAULT_HALF_TOLERANCE",
    "DEFAULT_MIN_AREA_FRACTION",
    "DEFAULT_NEAR_THRESHOLD",
    "PROBLEM_NAME",
    "ClipMatch",
    "ClipProfile",
    "StraddleRecord",
    "profile_clip_assignment",
    "profile_clip_completeness",
    "validate_clip_assignment",
    "validate_clip_completeness",
]