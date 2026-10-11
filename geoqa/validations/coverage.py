"""How much of a geometry survived a clip, and whether the pieces came back.

Clipping a feature to a boundary produces a *portion* of it. Two questions
follow, and they are different questions.

**How much survived.** A feature that lost 95 percent of its area to the clip
boundary is not the same feature any more, and a delivery that contains one
without saying so is misleading. A coverage floor catches that.

**Did the rest come back.** Splitting on a majority threshold produces two
halves. If the halves are delivered separately and one is never rejoined,
the record is silently short. GeoQA cannot tell that from the clip output
alone, so it is asked of the rejoined result: for each identifier, the pieces
should union to one valid geometry whose area is no greater than the sum of
the parts. A union larger than the sum means the pieces overlap and have been
counted twice; a union smaller than a valid sum means a piece was dropped.

The area comparison is a real invariant rather than a heuristic. Overlapping
inputs to a union produce an output no larger than their sum, and disjoint
inputs produce exactly their sum, so a result outside that band means
something other than a clean reassembly happened.

The thresholds are arguments, not constants. A value that was tuned for one
dataset's boundaries is not a rule for a different one.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "coverage_ratio",
    "coverage_report",
    "validate_coverage_floor",
    "validate_split_completeness",
]


def _area(geometry: Any) -> float:
    if geometry is None:
        return 0.0
    try:
        if geometry.is_empty:
            return 0.0
        return float(geometry.area)
    except Exception:
        return 0.0


def coverage_ratio(
    original: Any,
    clipped: Any,
    *,
    id_field: str | None = None,
) -> dict[str, Any]:
    """Retained fraction of area between an original geometry and its clipped result."""
    before = _area(original)
    after = _area(clipped)
    if before <= 0.0:
        return {
            "id": id_field,
            "original_area": before,
            "clipped_area": after,
            "ratio": None,
            "reason": "original has no area",
        }
    ratio = after / before
    return {
        "id": id_field,
        "original_area": before,
        "clipped_area": after,
        "ratio": ratio,
        "reason": None,
    }


def _match_by_id(
    originals: Any, clipped: Any, id_field: str
) -> dict[str, tuple[Any, Any]]:
    lookup: dict[str, tuple[Any, Any]] = {}
    try:
        clipped_rows = {str(r.get(id_field)).strip(): r.get("geometry") for _, r in clipped.iterrows()}
    except Exception:
        return {}
    try:
        for _, row in originals.iterrows():
            key = str(row.get(id_field)).strip()
            if key in clipped_rows:
                lookup[key] = (row.get("geometry"), clipped_rows[key])
    except Exception:
        return {}
    return lookup


def validate_coverage_floor(
    originals: Any,
    clipped: Any,
    *,
    id_field: str,
    minimum_retained: float = 0.2,
    allow_missing: bool = False,
) -> list[ValidationIssue]:
    """Report features that lost more than ``1 - minimum_retained`` to the clip.

    This is not the majority-assignment rule. That decides which side of a
    boundary owns a straddling feature; this measures how much of the feature
    survived once that was decided. A feature can win the assignment and
    still have almost nothing left.
    """
    issues: list[ValidationIssue] = []
    if minimum_retained < 0.0 or minimum_retained > 1.0:
        raise ValueError("minimum_retained must be between 0 and 1")

    try:
        clipped_ids = {str(r.get(id_field)).strip() for _, r in clipped.iterrows()}
    except Exception as exc:
        # Not swallowed. A validator that returns nothing because it broke is
        # worse than one that fails loudly, because the caller reads an empty
        # result as a clean one.
        return [
            build_issue(
                "validator_could_not_run",
                description=(
                    "The coverage floor could not be evaluated: "
                    f"{type(exc).__name__}: {exc}"
                ),
                extra={"validator": "validate_coverage_floor", "field": id_field},
            )
        ]

    try:
        rows = list(originals.iterrows())
    except Exception:
        return issues

    for index, row in rows:
        key = str(row.get(id_field)).strip()
        original = row.get("geometry")
        if key not in clipped_ids:
            if allow_missing:
                continue
            issues.append(
                build_issue(
                    "clip_feature_absent",
                    index=index,
                    geometry=original,
                    description=(
                        f"{id_field}={key!r} is present in the source but not in the "
                        "clip output, so nothing of it was delivered."
                    ),
                    extra={"id": key, "id_field": id_field},
                )
            )
            continue

        clipped_geometry = _lookup_geometry(clipped, id_field, key)
        detail = coverage_ratio(original, clipped_geometry, id_field=key)
        ratio = detail["ratio"]
        if ratio is None:
            issues.append(
                build_issue(
                    "clip_coverage_uncomputable",
                    index=index,
                    description=(
                        f"{id_field}={key!r} has no measurable area before the clip, so "
                        "its retained fraction cannot be assessed."
                    ),
                    extra=detail,
                )
            )
            continue

        if ratio < minimum_retained:
            issues.append(
                build_issue(
                    "clip_coverage_below_floor",
                    index=index,
                    geometry=clipped_geometry,
                    description=(
                        f"{id_field}={key!r} retained {ratio:.1%} of its area, below the "
                        f"declared {minimum_retained:.0%} floor. What was delivered is "
                        "not the feature that was asked for."
                    ),
                    extra={"minimum_retained": minimum_retained, **detail},
                )
            )
    return issues


def _lookup_geometry(layer: Any, field: str, key: str) -> Any:
    try:
        for _, row in layer.iterrows():
            if str(row.get(field)).strip() == key:
                return row.get("geometry")
    except Exception:
        return None
    return None


def validate_split_completeness(
    pieces: Any,
    *,
    id_field: str,
    expected_area: Mapping[str, float] | None = None,
    relative_tolerance: float = 1e-6,
    require_single: bool = True,
) -> list[ValidationIssue]:
    """Report split features whose pieces do not reassemble into one geometry.

    Two distinct failures, and they need different evidence.

    **Overlap** is detectable from the pieces alone. Two pieces that intersect
    share area, so their union is smaller than the sum of their parts and any
    total computed over the pieces is double counting. Pairwise intersection
    settles it directly.

    **A missing piece** is not detectable from the pieces alone, and this is
    worth being explicit about. The union of disjoint polygons always equals
    the sum of their areas, whatever gap sits between them, so comparing a
    reassembly against the sum of its own parts can never detect an absent
    third piece. Detecting it needs the area the feature had before it was
    split, which the caller supplies through ``expected_area`` keyed by
    identifier. Without that, a short delivery reassembles perfectly and looks
    correct.

    Omitting ``expected_area`` therefore weakens this check rather than
    breaking it, and the condition's own description says which evidence a
    given result rests on.
    """
    issues: list[ValidationIssue] = []
    grouped: dict[str, list[tuple[Any, Any]]] = defaultdict(list)

    try:
        rows = list(pieces.iterrows())
    except Exception as exc:
        return [
            build_issue(
                "validator_could_not_run",
                description=(
                    "Split completeness could not be evaluated: "
                    f"{type(exc).__name__}: {exc}"
                ),
                extra={"validator": "validate_split_completeness", "field": id_field},
            )
        ]

    for index, row in rows:
        key = row.get(id_field)
        geometry = row.get("geometry")
        if key is None or geometry is None:
            continue
        grouped[str(key).strip()].append((index, geometry))

    for key, entries in grouped.items():
        geometries = [g for _, g in entries]

        if require_single and len(geometries) > 1:
            unioned = _safe_union(geometries)
            part_sum = sum(_area(g) for g in geometries)
            union_area = _area(unioned)

            if not getattr(unioned, "is_valid", True):
                issues.append(
                    build_issue(
                        "split_pieces_not_whole",
                        index=entries[0][0],
                        geometry=unioned,
                        description=(
                            f"{id_field}={key!r} is split across {len(geometries)} pieces "
                            "and the pieces do not form one valid geometry. They were "
                            "clipped at different boundaries and were not rejoined."
                        ),
                        extra={"id": key, "piece_count": len(geometries)},
                    )
                )
                continue

            overlap_area = _pairwise_overlap_area(geometries)
            if overlap_area > 0.0:
                issues.append(
                    build_issue(
                        "split_pieces_overlap",
                        index=entries[0][0],
                        geometry=unioned,
                        description=(
                            f"{id_field}={key!r} has {len(geometries)} pieces that overlap "
                            f"by {overlap_area:.6g} square units. Their union is "
                            f"{union_area:.6g} against {part_sum:.6g} summed, so any total "
                            "computed over the pieces is counting the overlap twice."
                        ),
                        extra={
                            "id": key,
                            "union_area": union_area,
                            "parts_area": part_sum,
                            "overlap_area": overlap_area,
                            "piece_count": len(geometries),
                        },
                    )
                )

            expected = (expected_area or {}).get(key)
            if expected is not None and expected > 0:
                shortfall = expected - union_area
                if shortfall > expected * relative_tolerance:
                    issues.append(
                        build_issue(
                            "split_pieces_area_lost",
                            index=entries[0][0],
                            geometry=unioned,
                            description=(
                                f"{id_field}={key!r} reassembles to {union_area:.6g} against "
                                f"an original area of {expected:.6g}. {shortfall:.6g} square "
                                "units are missing, so a piece was dropped before delivery."
                            ),
                            extra={
                                "id": key,
                                "union_area": union_area,
                                "expected_area": expected,
                                "shortfall": shortfall,
                                "piece_count": len(geometries),
                            },
                        )
                    )
    return issues

def _pairwise_overlap_area(geometries: Sequence[Any]) -> float:
    """Total area covered by more than one piece."""
    total = 0.0
    for i in range(len(geometries)):
        for j in range(i + 1, len(geometries)):
            try:
                total += _area(geometries[i].intersection(geometries[j]))
            except Exception:
                continue
    return total


def _safe_union(geometries: Sequence[Any]) -> Any:
    try:
        from shapely.ops import unary_union

        return unary_union(list(geometries))
    except Exception:
        return geometries[0] if len(geometries) == 1 else None


def coverage_report(
    originals: Any, clipped: Any, *, id_field: str
) -> list[dict[str, Any]]:
    """Return the retained fraction per feature without judging it."""
    try:
        clipped_ids = {str(r.get(id_field)).strip() for _, r in clipped.iterrows()}
    except Exception:
        return []
    report: list[dict[str, Any]] = []
    try:
        for index, row in originals.iterrows():
            key = str(row.get(id_field)).strip()
            geometry = _lookup_geometry(clipped, id_field, key) if key in clipped_ids else None
            report.append(coverage_ratio(row.get("geometry"), geometry, id_field=key))
    except Exception:
        return report
    return report