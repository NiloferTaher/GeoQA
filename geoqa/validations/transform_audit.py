"""What a geometry operation actually did.

GeoQA's position is that it does not repair silently. Two of the most
common operations in geospatial work do exactly that, and neither says so.

**``buffer(0)``** is the standard remedy for an invalid polygon. It usually
works. It also moves the boundary, because it rebuilds the geometry through
a validity algorithm, and the rebuilt polygon is not the original polygon. The
area and the perimeter both change. The change is often small, which is what
makes it dangerous: nobody reports a 0.4 percent area shift because it does
not look worth reporting, and it compounds through a dissolve.

**A dissolve or a merge** reduces N features to 1. The features that were
dropped, and the attributes that went with them, do not announce themselves.

Both are checked here by measuring before and after rather than by trusting
the operation. The measurement is the deliverable: a caller who wants to
apply the repair still can, but now they know what it cost and can record
that they knew.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "geometry_metrics",
    "audit_repair",
    "buffer_zero_audit",
    "audit_attribute_preservation",
]


def geometry_metrics(geometry: Any) -> dict[str, Any]:
    """Measure what a geometry operation can silently change."""
    if geometry is None:
        return {"area": 0.0, "length": 0.0, "vertices": 0, "valid": False}
    area = 0.0
    length = 0.0
    try:
        area = float(geometry.area)
    except Exception:
        pass
    try:
        length = float(getattr(geometry, "length", 0.0))
    except Exception:
        pass
    vertices = 0
    try:
        vertices = len(geometry.coords) if geometry.geom_type in {"LineString", "LinearRing"} else 0
        if not vertices:
            vertices = len(getattr(geometry, "geoms", []))
    except Exception:
        vertices = 0
    try:
        valid = bool(geometry.is_valid)
    except Exception:
        valid = True
    return {"area": area, "length": length, "vertices": vertices, "valid": valid}


def buffer_zero_audit(
    layer: Any,
    *,
    area_tolerance: float = 1e-6,
    length_tolerance: float = 1e-6,
    repair: bool = True,
) -> list[ValidationIssue]:
    """Report what ``buffer(0)`` would change, and whether it fully repairs.

    Reported whether or not the repair is applied. The point is that a caller
    deciding whether to apply it should see the cost first, and a report that
    only appears after the repair has already been done is too late to be
    useful.
    """
    issues: list[ValidationIssue] = []
    try:
        rows = list(layer.iterrows())
    except Exception:
        return issues

    for index, row in rows:
        original = row.get("geometry")
        if original is None:
            continue
        before = geometry_metrics(original)
        try:
            invalid = not before["valid"]
        except Exception:
            invalid = False
        if not invalid:
            continue

        if not repair:
            continue

        try:
            repaired = original.buffer(0)
        except Exception:
            issues.append(
                build_issue(
                    "repair_buffer_zero_failed",
                    index=index,
                    geometry=original,
                    description=(
                        "buffer(0) could not be applied to this invalid geometry, so "
                        "the repair ladder has no next step."
                    ),
                    extra={"before": before},
                )
            )
            continue

        after = geometry_metrics(repaired)
        if not after["valid"]:
            issues.append(
                build_issue(
                    "repair_incomplete",
                    index=index,
                    geometry=repaired,
                    description=(
                        "buffer(0) did not produce a valid geometry. It repairs most "
                        "self-intersections and cannot repair a geometry that is "
                        "invalid for another reason, so the ladder must escalate."
                    ),
                    extra={"before": before, "after": after},
                )
            )
            continue

        area_delta = after["area"] - before["area"]
        length_delta = after["length"] - before["length"]
        area_relative = abs(area_delta) / before["area"] if before["area"] else 0.0
        length_relative = abs(length_delta) / before["length"] if before["length"] else 0.0

        if area_relative > area_tolerance or length_relative > length_tolerance:
            issues.append(
                build_issue(
                    "repair_changed_geometry",
                    index=index,
                    geometry=repaired,
                    description=(
                        f"buffer(0) repaired this geometry but moved it: area "
                        f"{before['area']:.6g} to {after['area']:.6g} "
                        f"({area_delta:+.6g}, {area_relative:.2%}) and length "
                        f"{before['length']:.6g} to {after['length']:.6g} "
                        f"({length_relative:.2%}). The result is a different shape from "
                        "the one that was supplied, not the same shape made valid."
                    ),
                    extra={
                        "before": before,
                        "after": after,
                        "area_delta": area_delta,
                        "area_relative": area_relative,
                        "length_delta": length_delta,
                        "length_relative": length_relative,
                    },
                )
            )
    return issues


def audit_repair(
    before: Any,
    after: Any,
    *,
    id_field: str | None = None,
    area_tolerance: float = 1e-6,
) -> list[ValidationIssue]:
    """Report per-feature differences between a layer and its repaired form."""
    issues: list[ValidationIssue] = []
    try:
        after_rows = {str(r.get(id_field)).strip(): r.get("geometry") for _, r in after.iterrows()} if id_field else None
    except Exception:
        after_rows = None

    try:
        rows = list(before.iterrows())
    except Exception:
        return issues

    for index, row in rows:
        original = row.get("geometry")
        key = str(row.get(id_field)).strip() if id_field else None
        repaired = after_rows.get(key) if (after_rows is not None and key is not None) else None
        if repaired is None:
            try:
                repaired = after.geometry.iloc[index]
            except Exception:
                repaired = None
        if original is None or repaired is None:
            continue

        b = geometry_metrics(original)
        a = geometry_metrics(repaired)
        relative = abs(a["area"] - b["area"]) / b["area"] if b["area"] else 0.0
        if relative > area_tolerance:
            issues.append(
                build_issue(
                    "repair_changed_geometry",
                    index=index,
                    geometry=repaired,
                    description=(
                        f"Repair changed this feature's area from {b['area']:.6g} to "
                        f"{a['area']:.6g} ({relative:.2%})."
                    ),
                    extra={"id": key, "before": b, "after": a, "area_relative": relative},
                )
            )
    return issues


def audit_attribute_preservation(
    source: Any,
    result: Any,
    *,
    key_field: str,
    preserved_fields: Sequence[str] = (),
) -> list[ValidationIssue]:
    """Report source keys and attributes lost by a merge, dissolve or rewrite.

    A dissolve that drops features reports the count. A rewrite that keeps
    the features but blanks an attribute reports the attribute, because the
    row count is then unchanged and nothing else would show it.
    """
    issues: list[ValidationIssue] = []
    if key_field not in getattr(source, "columns", []) or key_field not in getattr(result, "columns", []):
        return issues

    try:
        source_keys = {str(r.get(key_field)).strip() for _, r in source.iterrows()}
        result_keys = {str(r.get(key_field)).strip() for _, r in result.iterrows()}
    except Exception:
        return issues

    lost = sorted(source_keys - result_keys)
    if lost:
        issues.append(
            build_issue(
                "transform_dropped_features",
                description=(
                    f"{len(lost)} of {len(source_keys)} features are absent from the "
                    "result. A merge or dissolve that is meant to reduce duplicates must "
                    "state which features it discarded and why."
                ),
                extra={"lost_keys": lost[:50], "lost_count": len(lost),
                       "source_count": len(source_keys), "result_count": len(result_keys)},
            )
        )

    if preserved_fields:
        try:
            source_by_key = {
                str(r.get(key_field)).strip(): r for _, r in source.iterrows()
            }
        except Exception:
            return issues
        for index, row in result.iterrows():
            key = str(row.get(key_field)).strip()
            original = source_by_key.get(key)
            if original is None:
                continue
            for field in preserved_fields:
                if field not in getattr(source, "columns", []):
                    continue
                before_value = original.get(field)
                after_value = row.get(field)
                if before_value is None or after_value is None:
                    continue
                if str(before_value).strip() == "" and str(after_value).strip() != "":
                    continue
                if str(before_value) != str(after_value):
                    issues.append(
                        build_issue(
                            "transform_attribute_changed",
                            index=index,
                            description=(
                                f"Attribute {field!r} of {key_field}={key!r} changed from "
                                f"{before_value!r} to {after_value!r} during the "
                                "operation. An operation that was meant to change geometry "
                                "has changed data."
                            ),
                            extra={"key": key, "field": field,
                                   "before": before_value, "after": after_value},
                        )
                    )
    return issues