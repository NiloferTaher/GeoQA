"""Detect geometry that was cut by another layer's boundary.

The condition
-------------
Clipping a feature to a second layer produces fragments. That is the intended
effect at a real boundary, and an accident everywhere else. When an asset falls
between two administrative areas and is clipped to each, the result looks like
two legitimately separate features. Nothing in the geometry says otherwise.

This module answers the question the geometry cannot: **is this feature a
fragment of something larger, and was it split by a boundary?**

It compares a layer against a reference layer and distinguishes three outcomes,
which are genuinely different and were previously conflated:

1. **Covered.** The feature matches a reference feature closely. Correct.
2. **Fragment of a reference feature.** The feature sits inside a reference
   feature but covers materially less of it, and there is no boundary between
   the two. This is the cut case: something split it, and the cut is not a
   declared boundary.
3. **Legitimate boundary case.** A reference feature is genuinely subdivided, and
   the cut coincides with a linework boundary in the boundary layer. Correct
   behaviour, reported so it can be confirmed rather than assumed.

Distinguishing 2 from 3 is the whole point. Without the boundary layer you
cannot tell an accidental cut from a correct clip, and reporting both as errors
makes the tool useless on any layer that was legitimately clipped.

Provenance of the rule
----------------------
From real delivery pipelines: assets clipped against administrative boundaries
were later found split across two regions, and the repair was to restore the
full geometry rather than accept the fragment. The 50% majority rule, the
0.5 m and 2.0 m inward buffers, and the smaller-polygon denominator all came
from the same pipeline. What was missing was a check that would have caught the
split before it reached the database.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .base import ValidationIssue, build_issue

PROBLEM_NAME = "boundary_condition_conformance"

# A fragment covering less than this fraction of its reference is reported.
DEFAULT_COVERAGE_THRESHOLD = 0.995

# A cut is only "undeclared" when the fragment's neighbours in the reference
# layer do not already explain it. This is the gap fraction used to decide
# whether the boundary layer accounts for the split.
DEFAULT_UNDECLARED_THRESHOLD = 0.02


@dataclass
class FragmentFinding:
    """One feature assessed against the reference layer."""

    index: Any
    feature_id: Any
    coverage: float
    reference_index: Any
    reference_id: Any
    overlaps_other_fragments: bool
    boundary_explains_cut: bool

    @property
    def is_fragment(self) -> bool:
        return self.coverage < DEFAULT_COVERAGE_THRESHOLD

    @property
    def is_undeclared_cut(self) -> bool:
        """A fragment that no boundary in the boundary layer accounts for."""
        return self.is_fragment and not self.boundary_explains_cut


@dataclass
class BoundaryConformanceProfile:
    features: int = 0
    covered: int = 0
    fragments: int = 0
    undeclared_cuts: int = 0
    findings: list[FragmentFinding] = field(default_factory=list)
    unexplained: list[FragmentFinding] = field(default_factory=list)
    coverage_histogram: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def summary(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "covered": self.covered,
            "fragments": self.fragments,
            "undeclared_cuts": self.undeclared_cuts,
            "fragments_explained_by_boundary": len(self.findings) - len(self.unexplained),
            "coverage_buckets": dict(self.coverage_histogram),
        }


def _geometry(row: Any) -> Any:
    try:
        if "geometry" in row.index:
            return row["geometry"]
    except Exception:
        pass
    return getattr(row, "geometry", None)


def _feature_id(row: Any, index: Any) -> Any:
    for column in ("ogc_fid", "fid", "id", "asset_id", "objectid", "OBJECTID"):
        try:
            if column in row.index and row[column] is not None:
                return row[column]
        except Exception:
            continue
    return index


def _reference_candidates(reference_layer: Any, geometry: Any) -> Iterable[Any]:
    """Reference rows whose bounding box intersects the query geometry."""
    sindex = getattr(reference_layer, "sindex", None)
    if sindex is None:
        for index, row in reference_layer.iterrows():
            yield index, row
        return
    try:
        positions = sindex.query(geometry)
    except Exception:
        for index, row in reference_layer.iterrows():
            yield index, row
        return
    for position in positions:
        try:
            yield reference_layer.index[int(position)], reference_layer.iloc[int(position)]
        except Exception:
            continue


def _boundary_explains_cut(
    fragment: Any,
    reference_geometry: Any,
    *,
    other_fragments: list[Any],
    boundary_layer: Any | None,
    boundary_tolerance: float,
) -> bool:
    """Is the fragment's outer edge explained by a boundary in the boundary layer?

    Two ways a cut can be legitimate:

    - the reference feature is already subdivided elsewhere, so this fragment is
      one of several pieces and the subdivision is intentional;
    - a linework boundary runs along the fragment's outer edge.
    """
    if other_fragments:
        # Something else already claims part of the same reference feature, so
        # the reference is genuinely subdivided rather than accidentally cut.
        return True

    if boundary_layer is None:
        return False

    difference = reference_geometry.difference(fragment)
    if difference is None or difference.is_empty:
        return True

    # The cut edge is where the fragment meets what was taken away from it,
    # NOT the fragment's own outer perimeter. Using the perimeter would let any
    # nearby linework explain any cut.
    if not hasattr(fragment, "boundary"):
        return False
    cut_edge = fragment.boundary.intersection(difference.boundary)
    if cut_edge is None or cut_edge.is_empty:
        return False

    search = cut_edge.buffer(boundary_tolerance)
    sindex = getattr(boundary_layer, "sindex", None)
    if sindex is None:
        return any(
            _geometry(row) is not None and _geometry(row).intersects(search)
            for _, row in boundary_layer.iterrows()
        )
    try:
        positions = sindex.query(search)
    except Exception:
        return False
    for position in positions:
        try:
            candidate = _geometry(boundary_layer.iloc[int(position)])
        except Exception:
            continue
        if candidate is not None and candidate.intersects(search):
            return True
    return False


def profile_boundary_conformance(
    layer: Any,
    reference_layer: Any,
    *,
    boundary_layer: Any | None = None,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    boundary_tolerance: float = 0.5,
) -> BoundaryConformanceProfile:
    """Assess every feature in ``layer`` against ``reference_layer``.

    ``boundary_layer`` is optional but materially changes the answer: with it,
    a cut that follows a declared boundary is distinguished from one that does
    not. Without it, every fragment is reported, because there is no way to tell
    a correct clip from an accidental cut.
    """
    profile = BoundaryConformanceProfile()

    # First pass: which reference features are claimed by more than one feature.
    claims: dict[Any, list[Any]] = defaultdict(list)
    best_for_row: dict[Any, tuple[Any, Any, Any, float]] = {}

    for index, row in layer.iterrows():
        geometry = _geometry(row)
        if geometry is None or geometry.is_empty:
            continue
        profile.features += 1

        best_reference_index = None
        best_reference_row = None
        best_reference_geometry = None
        best_intersection = 0.0

        for reference_index, reference_row in _reference_candidates(reference_layer, geometry):
            reference_geometry = _geometry(reference_row)
            if reference_geometry is None or reference_geometry.is_empty:
                continue
            try:
                intersection_area = float(geometry.intersection(reference_geometry).area)
            except Exception:
                intersection_area = 0.0
            if intersection_area > best_intersection:
                best_intersection = intersection_area
                best_reference_index = reference_index
                best_reference_row = reference_row
                best_reference_geometry = reference_geometry

        if best_reference_geometry is None or best_intersection <= 0.0:
            profile.coverage_histogram["no_reference_match"] += 1
            continue

        try:
            reference_area = float(best_reference_geometry.area)
        except Exception:
            reference_area = 0.0
        if reference_area <= 0.0:
            continue

        coverage = best_intersection / reference_area
        profile.coverage_histogram[_bucket(coverage)] += 1

        row_key = index
        best_for_row[row_key] = (
            best_reference_index,
            best_reference_row,
            best_reference_geometry,
            coverage,
        )
        claims[best_reference_index].append((index, geometry))

    # Second pass: classify, now that competing claims are known.
    for index, (reference_index, _, reference_geometry, coverage) in best_for_row.items():
        row = layer.loc[index]
        # Only OTHER FRAGMENTS count as a competing subdivision. A feature that
        # fully covers the reference is not evidence that the reference was
        # split, so it must not excuse this one.
        others = [
            geometry
            for (other_index, geometry) in claims.get(reference_index, [])
            if other_index != index
            and best_for_row.get(other_index, (None, None, None, 1.0))[3] < coverage_threshold
        ]

        geometry = _geometry(row)
        explained = _boundary_explains_cut(
            geometry,
            reference_geometry,
            other_fragments=others,
            boundary_layer=boundary_layer,
            boundary_tolerance=boundary_tolerance,
        )

        finding = FragmentFinding(
            index=index,
            feature_id=_feature_id(row, index),
            coverage=coverage,
            reference_index=reference_index,
            reference_id=_feature_id(
                reference_layer.loc[reference_index], reference_index
            ) if reference_index is not None else None,
            overlaps_other_fragments=bool(others),
            boundary_explains_cut=explained,
        )

        if coverage >= coverage_threshold:
            profile.covered += 1
            continue

        profile.fragments += 1
        profile.findings.append(finding)
        if not finding.boundary_explains_cut:
            profile.undeclared_cuts += 1
            profile.unexplained.append(finding)

    return profile


def _bucket(coverage: float) -> str:
    if coverage >= 0.995:
        return "covered"
    if coverage >= 0.90:
        return "mostly_covered"
    if coverage >= 0.50:
        return "partial"
    if coverage > 0.0:
        return "fragment"
    return "none"


def validate_boundary_conformance(
    layer: Any,
    reference_layer: Any,
    *,
    boundary_layer: Any | None = None,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    boundary_tolerance: float = 0.5,
) -> list[ValidationIssue]:
    """Report features that a boundary cut, when no boundary explains it.

    The important distinction is made by severity:

    - **high** when no boundary layer explains the cut. This is the accidental
      case, and it is the one that reached a database in production.
    - **low** when other features claim the same reference feature. That is a
      legitimate subdivision and is recorded rather than alarmed about.
    - **info** when a declared boundary does explain the cut. Correct behaviour,
      surfaced so it can be confirmed.
    """
    profile = profile_boundary_conformance(
        layer,
        reference_layer,
        boundary_layer=boundary_layer,
        coverage_threshold=coverage_threshold,
        boundary_tolerance=boundary_tolerance,
    )

    issues: list[ValidationIssue] = []

    # A fragment that something already explains is correct behaviour: either a
    # declared boundary follows the cut edge, or other features claim the same
    # reference, which means it was deliberately subdivided. Either way the
    # finding is recorded at low severity rather than asserted as a defect.
    for finding in profile.findings:
        if finding in profile.unexplained:
            continue
        row = layer.loc[finding.index]
        explained_by = (
            "a declared boundary follows the cut edge"
            if finding.boundary_explains_cut and boundary_layer is not None
            else "other features claim the same reference, so it was subdivided"
        )
        issues.append(
            build_issue(
                problem_name=PROBLEM_NAME,
                row=row,
                index=finding.index,
                feature_id=finding.feature_id,
                severity="low" if finding.overlaps_other_fragments else "info",
                description=(
                    f"Feature covers {finding.coverage:.1%} of reference "
                    f"{finding.reference_id} and the clip is explained: {explained_by}"
                ),
                extra={
                    "coverage": round(finding.coverage, 4),
                    "reference_id": finding.reference_id,
                    "boundary_explains_cut": finding.boundary_explains_cut,
                    "shares_reference": finding.overlaps_other_fragments,
                },
            )
        )

    for finding in profile.unexplained:
        row = layer.loc[finding.index]
        if finding.overlaps_other_fragments:
            issues.append(
                build_issue(
                    problem_name=PROBLEM_NAME,
                    row=row,
                    index=finding.index,
                    feature_id=finding.feature_id,
                    severity="low",
                    description=(
                        f"Feature covers {finding.coverage:.1%} of reference "
                        f"{finding.reference_id} and shares it with other features; "
                        "the reference is subdivided, so this looks like an intended clip"
                    ),
                    extra={
                        "coverage": round(finding.coverage, 4),
                        "reference_id": finding.reference_id,
                        "boundary_explains_cut": finding.boundary_explains_cut,
                        "shares_reference": True,
                    },
                )
            )
            continue

        severity = "high"
        explanation = (
            "no boundary in the boundary layer follows the cut edge; supply "
            "boundary_layer to confirm this is an accidental cut rather than a "
            "correct clip"
            if boundary_layer is not None
            else "the cut cannot be attributed to a boundary because no "
            "boundary_layer was supplied"
        )
        issues.append(
            build_issue(
                problem_name=PROBLEM_NAME,
                row=row,
                index=finding.index,
                feature_id=finding.feature_id,
                severity=severity,
                description=(
                    f"Feature covers only {finding.coverage:.1%} of reference "
                    f"{finding.reference_id}, so it may be a fragment of a geometry "
                    f"cut by another layer's boundary: {explanation}"
                ),
                extra={
                    "coverage": round(finding.coverage, 4),
                    "reference_id": finding.reference_id,
                    "boundary_explains_cut": finding.boundary_explains_cut,
                    "shares_reference": False,
                    "boundary_layer_supplied": boundary_layer is not None,
                },
            )
        )

    return issues


def continuity_breaks(
    layer: Any,
    *,
    key_column: str | None = None,
    tolerance: float = 1e-6,
    max_gap_ratio: float = 0.5,
) -> list[ValidationIssue]:
    """Report network features that stop and resume inside the same zone.

    The condition that pairs with boundary cutting: a pipe that crosses an
    administrative boundary and does not reappear on the other side, or a gap
    between two pieces of what should be one continuous run. Comparing against
    another layer alone cannot see this; it needs the logical identity of the
    asset.

    With ``key_column`` supplied, only features sharing that key are compared.
    Without it, ``continuity_breaks`` reports end points that fall inside the
    overall extent but have no neighbour within ``tolerance``, which is the
    generic dangling case and is already covered by ``line_dangle``. The key
    column is what makes this check specific.
    """
    from shapely.geometry import Point

    issues: list[ValidationIssue] = []
    reported_gaps: set[tuple[str, str]] = set()
    if key_column is None:
        return issues

    if key_column not in getattr(layer, "columns", []):
        return issues

    groups: dict[Any, list[Any]] = defaultdict(list)
    for index, row in layer.iterrows():
        geometry = _geometry(row)
        if geometry is None or geometry.is_empty:
            continue
        groups[row[key_column]].append((index, geometry))

    for key, entries in groups.items():
        if len(entries) < 2:
            continue

        # Endpoints, each tagged with the feature it belongs to.
        endpoints: list[tuple[Any, Point]] = []
        for index, geometry in entries:
            try:
                coords = list(geometry.coords)
            except AttributeError:
                continue
            endpoints.append((index, Point(coords[0])))
            endpoints.append((index, Point(coords[-1])))

        # A break is a *mutually nearest* pair of ends, in different features,
        # separated by more than the tolerance. Mutuality is what separates a
        # genuine gap from a network terminus: the free end of a run is nearest
        # to something, but that something is not nearest back to it.
        partners: dict[tuple[Any, int], tuple[float, Any, int]] = {}
        for slot, (index, point) in enumerate(endpoints):
            best: tuple[float, Any, int] | None = None
            for other_slot, (other_index, other_point) in enumerate(endpoints):
                if other_index == index:
                    continue
                distance = point.distance(other_point)
                if best is None or distance < best[0]:
                    best = (distance, other_index, other_slot)
            if best is not None:
                partners[(index, slot)] = best

        for (index, slot), (distance, other_index, other_slot) in partners.items():
            back = partners.get((other_index, other_slot))
            if back is None or back[1] != index:
                continue
            if distance <= tolerance:
                continue
            # A cut is a *small* gap. Two ends that are far apart are two
            # different runs, not one run with a hole in it. Without this the
            # check reports every pair of neighbouring features.
            own_length = float(_geometry(row).length) if _geometry(row) is not None else 0.0
            partner_length = float(_geometry(layer.loc[other_index]).length) if _geometry(row) is not None else 0.0
            smallest = min(own_length, partner_length) if partner_length else own_length
            if smallest > 0 and distance > smallest * max_gap_ratio:
                continue
            # One issue per gap, not one per end of it.
            gap_key = tuple(sorted((str(index), str(other_index))))
            if gap_key in reported_gaps:
                continue
            reported_gaps.add(gap_key)
            row = layer.loc[index]
            issues.append(
                build_issue(
                    problem_name="continuity_break",
                    row=row,
                    index=index,
                    feature_id=_feature_id(row, index),
                    geometry=_geometry(row),
                    severity="medium",
                    description=(
                        f"Feature with {key_column}={key!r} is {distance:.3g} m from the "
                        "nearest other part of itself at both ends, which is the signature "
                        "of a run that was cut rather than one that ended"
                    ),
                    extra={
                        "key": key,
                        "gap_distance": distance,
                        "key_column": key_column,
                        "partner_index": other_index,
                    },
                )
            )

    return issues


__all__ = [
    "BOUNDARY_CONFORMANCE_HELP",
    "DEFAULT_COVERAGE_THRESHOLD",
    "PROBLEM_NAME",
    "BoundaryConformanceProfile",
    "FragmentFinding",
    "continuity_breaks",
    "profile_boundary_conformance",
    "validate_boundary_conformance",
]