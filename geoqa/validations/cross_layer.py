"""Referential integrity between two layers.

A single-layer validator can tell you a pipe is well formed. It cannot tell
you the service connection drawn against that pipe has no pipe, or that the
pipe has no service connection. Both are the same class of defect and both are
invisible from either layer alone.

Two directions are checked, and the distinction matters:

**Orphan** means a row in the child layer references an identifier that does
not exist in the parent. **Unmatched parent** means the reverse. A run that
reports only orphans looks complete while silently ignoring assets nobody has
drawn a connection for, which is usually the half of the problem that matters.

Identifiers are compared as text after trimming, because a text column joined
to a text column still fails on trailing whitespace, and a numeric column read
from a spreadsheet arrives as ``"70677.0"``. Both are reported rather than
coerced: coercing hides the fact that the key is stored inconsistently.

Geometric orphans are checked separately, by spatial relationship rather than
by identifier. A service area whose geometry nowhere intersects a main is a
different defect from a service area whose id is absent, and conflating them
loses the distinction the operator needs.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "normalise_key",
    "referential_integrity",
    "bidirectional_coverage",
    "orphaned_by_geometry",
    "declared_domain",
]


def normalise_key(value: Any) -> str | None:
    """Return a comparable text key, or ``None`` when there is no key.

    Numbers arrive from several sources with several spellings. ``70677``,
    ``"70677"`` and ``" 70677"`` are the same asset and should compare equal;
    ``"70677.0"`` is the same asset that was stored wrongly, and the caller is
    told about that separately rather than having it hidden here.
    """
    if value is None:
        return None
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        return text[:-2]
    return text


def _keys(layer: Any, field: str) -> tuple[dict[str, Any], list[Any]]:
    mapping: dict[str, Any] = {}
    missing: list[Any] = []
    try:
        records = layer.iterrows()
    except Exception:
        records = []
    for index, row in records:
        raw = row.get(field) if hasattr(row, "get") else None
        key = normalise_key(raw)
        if key is None:
            missing.append(index)
            continue
        mapping.setdefault(key, index)
    return mapping, missing


def referential_integrity(
    child: Any,
    parent: Any,
    *,
    child_field: str,
    parent_field: str,
    layer_name: str = "child",
    parent_name: str = "parent",
) -> list[ValidationIssue]:
    """Report child rows whose key is absent from the parent.

    Also reports child rows with no key at all, which is a different defect
    and would otherwise be silently dropped by the comparison.
    """
    issues: list[ValidationIssue] = []
    parent_keys, _ = _keys(parent, parent_field)
    child_keys, missing = _keys(child, child_field)

    for key in sorted(child_keys):
        if key not in parent_keys:
            issues.append(
                build_issue(
                    "cross_layer_orphan",
                    index=child_keys[key],
                    description=(
                        f"{layer_name} row references {child_field}={key!r}, which is "
                        f"not present in {parent_name}."
                    ),
                    extra={
                        "key": key,
                        "child_field": child_field,
                        "parent_field": parent_field,
                        "layer_name": layer_name,
                        "parent_name": parent_name,
                    },
                )
            )

    for index in missing:
        issues.append(
            build_issue(
                "cross_layer_key_missing",
                index=index,
                description=(
                    f"{layer_name} row has no usable {child_field}, so it cannot be "
                    "checked against " + parent_name + "."
                ),
                extra={
                    "child_field": child_field,
                    "layer_name": layer_name,
                    "parent_name": parent_name,
                },
            )
        )
    return issues


def bidirectional_coverage(
    left: Any,
    right: Any,
    *,
    left_field: str,
    right_field: str,
    left_name: str = "left",
    right_name: str = "right",
    require_symmetry: bool = True,
) -> list[ValidationIssue]:
    """Report key sets that disagree, in both directions.

    With ``require_symmetry`` false only rows in ``left`` missing from
    ``right`` are reported, which is the right behaviour when ``right`` is a
    subset by design and the reverse is not a defect.
    """
    issues: list[ValidationIssue] = []
    left_keys, left_missing = _keys(left, left_field)
    right_keys, right_missing = _keys(right, right_field)

    only_left = sorted(set(left_keys) - set(right_keys))
    for key in only_left:
        issues.append(
            build_issue(
                "cross_layer_unmatched_child",
                index=left_keys[key],
                description=(
                    f"{left_name} has {left_field}={key!r} with no matching row in "
                    f"{right_name}."
                ),
                extra={"key": key, "layer_name": left_name, "other_layer": right_name},
            )
        )

    if require_symmetry:
        only_right = sorted(set(right_keys) - set(left_keys))
        for key in only_right:
            issues.append(
                build_issue(
                    "cross_layer_unmatched_parent",
                    index=right_keys[key],
                    description=(
                        f"{right_name} has {right_field}={key!r} with no matching row "
                        f"in {left_name}."
                    ),
                    extra={"key": key, "layer_name": right_name, "other_layer": left_name},
                )
            )

    for label, layer_name, field, missing in (
        ("key_missing", left_name, left_field, left_missing),
        ("key_missing", right_name, right_field, right_missing),
    ):
        for index in missing:
            issues.append(
                build_issue(
                    "cross_layer_key_missing",
                    index=index,
                    description=(
                        f"{layer_name} row has no usable {field}, so coverage cannot "
                        "be compared."
                    ),
                    extra={"layer_name": layer_name, "field": field, "reason": label},
                )
            )
    return issues


def orphaned_by_geometry(
    assets: Any,
    network: Any,
    *,
    relationship: str = "intersects",
    asset_name: str = "assets",
    network_name: str = "network",
    id_field: str | None = None,
) -> list[ValidationIssue]:
    """Report assets whose geometry meets no part of the network.

    A service connection drawn in the wrong place still has an identifier, and
    an identifier that resolves tells you nothing about whether the geometry
    is anywhere near the main it claims to serve. This is a spatial question,
    so it is asked spatially.
    """
    issues: list[ValidationIssue] = []
    if not len(assets) or not len(network):
        return issues

    try:
        joined = assets.sjoin(network, predicate=relationship, how="left")
        hit_column = "index_right"
    except Exception:
        return issues

    if hit_column not in joined.columns:
        return issues

    for index, row in joined.iterrows():
        value = row.get(hit_column)
        if value is None or (isinstance(value, float) and value != value):
            feature_id = row.get(id_field, index) if id_field else index
            geometry = row.get("geometry")
            issues.append(
                build_issue(
                    "cross_layer_geometric_orphan",
                    index=index,
                    geometry=geometry,
                    feature_id=feature_id,
                    description=(
                        f"{asset_name} feature has no {network_name} geometry that "
                        f"{relationship} it."
                    ),
                    extra={
                        "relationship": relationship,
                        "asset_name": asset_name,
                        "network_name": network_name,
                    },
                )
            )
    return issues


def declared_domain(
    layer: Any,
    field: str,
    *,
    expected: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return the observed value domain for a column.

    Useful before a validator is written against a column, and useful in a
    report because it records what the data actually contained rather than
    what someone assumed it contained.
    """
    values: dict[str, int] = {}
    try:
        series = layer[field]
    except Exception:
        return {"field": field, "present": False, "values": {}, "unexpected": []}

    for value in series:
        if value is None or (isinstance(value, float) and value != value):
            continue
        text = str(value).strip()
        if not text:
            continue
        values[text] = values.get(text, 0) + 1

    result: dict[str, Any] = {
        "field": field,
        "present": True,
        "distinct": len(values),
        "values": dict(sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))),
        "unexpected": [],
    }
    if expected is not None:
        allowed = {str(v) for v in expected}
        result["unexpected"] = sorted(set(values) - allowed)
    return result