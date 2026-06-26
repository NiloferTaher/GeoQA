from __future__ import annotations

import math
from typing import Any

from .base import ValidationIssue, build_issue


def _geometry(row: Any) -> Any | None:
    index = getattr(row, "index", None)
    if index is not None and "geometry" in index:
        return row["geometry"]
    return getattr(row, "geometry", None)


def _pairwise_rows(layer: Any):
    records = list(layer.iterrows())
    for left_pos, (left_index, left_row) in enumerate(records):
        for right_index, right_row in records[left_pos + 1 :]:
            yield (left_index, left_row), (right_index, right_row)


def _geometry_bounds(geometry: Any) -> tuple[float, float, float, float] | None:
    bounds = getattr(geometry, "bounds", None)
    if bounds is None:
        return None
    try:
        min_x, min_y, max_x, max_y = bounds
        return float(min_x), float(min_y), float(max_x), float(max_y)
    except Exception:
        return None


def _query_sindex_positions(sindex: Any, geometry: Any) -> set[int] | None:
    bounds = _geometry_bounds(geometry)
    if bounds is None:
        return None
    try:
        if hasattr(sindex, "query"):
            result = sindex.query(geometry)
        elif hasattr(sindex, "intersection"):
            result = sindex.intersection(bounds)
        else:
            return None
        return {int(position) for position in result}
    except Exception:
        try:
            if hasattr(sindex, "intersection"):
                return {int(position) for position in sindex.intersection(bounds)}
        except Exception:
            return None
    return None


def _linear_endpoint_pair(geometry: Any) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if geometry is None:
        return None

    def _coords_from_geom(candidate: Any) -> list[Any] | None:
        try:
            coords = getattr(candidate, "coords", None)
        except Exception:
            return None
        if coords is None:
            return None
        try:
            coord_list = list(coords)
        except Exception:
            return None
        if len(coord_list) < 2:
            return None
        return coord_list

    direct_coords = _coords_from_geom(geometry)
    if direct_coords is not None:
        return direct_coords[0], direct_coords[-1]

    parts = getattr(geometry, "geoms", None)
    if parts is None:
        return None

    part_coords: list[list[Any]] = []
    try:
        for part in parts:
            coords = _coords_from_geom(part)
            if coords is not None:
                part_coords.append(coords)
    except Exception:
        return None

    if not part_coords:
        return None
    return part_coords[0][0], part_coords[-1][-1]


def _pairwise_rows_spatial(layer: Any):
    records = list(layer.iterrows())
    sindex = getattr(layer, "sindex", None)
    if sindex is None:
        yield from _pairwise_rows(layer)
        return

    emitted: set[tuple[int, int]] = set()
    for left_pos, (left_index, left_row) in enumerate(records):
        left_geom = _geometry(left_row)
        if left_geom is None:
            continue
        candidate_positions = _query_sindex_positions(sindex, left_geom)
        if candidate_positions is None:
            yield from _pairwise_rows(layer)
            return
        for right_pos in sorted(candidate_positions):
            if right_pos <= left_pos or right_pos >= len(records):
                continue
            pair_key = (left_pos, right_pos)
            if pair_key in emitted:
                continue
            emitted.add(pair_key)
            right_index, right_row = records[right_pos]
            yield (left_index, left_row), (right_index, right_row)


def _reference_candidates(reference_layer: Any, geometry: Any):
    reference_records = list(reference_layer.iterrows())
    sindex = getattr(reference_layer, "sindex", None)
    if sindex is None:
        return reference_records
    candidate_positions = _query_sindex_positions(sindex, geometry)
    if candidate_positions is None:
        return reference_records
    return [reference_records[position] for position in sorted(candidate_positions) if 0 <= position < len(reference_records)]


def polygon_overlap_same_layer(layer: Any) -> list[ValidationIssue]:
    """Detect overlapping polygon features within the same layer."""
    issues: list[ValidationIssue] = []
    flagged: set[Any] = set()
    for (left_index, left_row), (right_index, right_row) in _pairwise_rows_spatial(layer):
        left_geom = _geometry(left_row)
        right_geom = _geometry(right_row)
        if left_geom is None or right_geom is None:
            continue
        try:
            overlaps = left_geom.overlaps(right_geom)
        except Exception:
            continue
        if overlaps:
            if left_index not in flagged:
                issues.append(
                    build_issue(
                        "polygon_overlap_same_layer",
                        row=left_row,
                        index=left_index,
                        description="This polygon overlaps another feature in the same layer where overlap is not expected.",
                        solution_hint="Validate topology and reshape or clip polygons so the same layer no longer overlaps.",
                    )
                )
                flagged.add(left_index)
            if right_index not in flagged:
                issues.append(
                    build_issue(
                        "polygon_overlap_same_layer",
                        row=right_row,
                        index=right_index,
                        description="This polygon overlaps another feature in the same layer where overlap is not expected.",
                        solution_hint="Validate topology and reshape or clip polygons so the same layer no longer overlaps.",
                    )
                )
                flagged.add(right_index)
    return issues


def feature_within_feature(layer: Any) -> list[ValidationIssue]:
    """Detect features fully contained within another feature of the same layer."""
    issues: list[ValidationIssue] = []
    flagged: set[Any] = set()
    for (left_index, left_row), (right_index, right_row) in _pairwise_rows_spatial(layer):
        left_geom = _geometry(left_row)
        right_geom = _geometry(right_row)
        if left_geom is None or right_geom is None:
            continue
        try:
            left_within_right = left_geom.within(right_geom)
            right_within_left = right_geom.within(left_geom)
        except Exception:
            continue
        if left_within_right and left_index not in flagged:
            issues.append(
                build_issue(
                    "feature_within_feature",
                    row=left_row,
                    index=left_index,
                    description="This feature is fully contained inside another feature of the same layer.",
                    solution_hint="Review whether the containment is valid; otherwise split, merge, or delete the nested feature.",
                )
            )
            flagged.add(left_index)
        if right_within_left and right_index not in flagged:
            issues.append(
                build_issue(
                    "feature_within_feature",
                    row=right_row,
                    index=right_index,
                    description="This feature is fully contained inside another feature of the same layer.",
                    solution_hint="Review whether the containment is valid; otherwise split, merge, or delete the nested feature.",
                )
            )
            flagged.add(right_index)
    return issues


def line_intersection_same_layer(layer: Any) -> list[ValidationIssue]:
    """Detect line intersections in the same layer where only endpoint connections are expected."""
    issues: list[ValidationIssue] = []
    flagged: set[Any] = set()
    for (left_index, left_row), (right_index, right_row) in _pairwise_rows_spatial(layer):
        left_geom = _geometry(left_row)
        right_geom = _geometry(right_row)
        if left_geom is None or right_geom is None:
            continue
        try:
            intersects = left_geom.intersects(right_geom)
            touches = left_geom.touches(right_geom)
        except Exception:
            continue
        if intersects and not touches:
            if left_index not in flagged:
                issues.append(
                    build_issue(
                        "line_intersection_same_layer",
                        row=left_row,
                        index=left_index,
                        description="This line intersects another feature in the same layer where a simple endpoint connection is expected.",
                        solution_hint="Split features at valid junctions or correct line placement so only allowed crossings remain.",
                    )
                )
                flagged.add(left_index)
            if right_index not in flagged:
                issues.append(
                    build_issue(
                        "line_intersection_same_layer",
                        row=right_row,
                        index=right_index,
                        description="This line intersects another feature in the same layer where a simple endpoint connection is expected.",
                        solution_hint="Split features at valid junctions or correct line placement so only allowed crossings remain.",
                    )
                )
                flagged.add(right_index)
    return issues


def duplicate_geometry_same_layer(layer: Any) -> list[ValidationIssue]:
    """Detect features whose geometry exactly duplicates another feature in the same layer."""
    issues: list[ValidationIssue] = []
    seen: dict[str, tuple[Any, Any]] = {}
    flagged: set[Any] = set()
    for index, row in layer.iterrows():
        geometry = _geometry(row)
        if geometry is None:
            continue
        token = getattr(geometry, "wkb_hex", None) or getattr(geometry, "wkt", None)
        if not isinstance(token, str):
            try:
                token = geometry.wkt
            except Exception:
                continue
        previous = seen.get(token)
        if previous is None:
            seen[token] = (index, row)
            continue
        previous_index, previous_row = previous
        if previous_index not in flagged:
            issues.append(
                build_issue(
                    "duplicate_geometry_same_layer",
                    row=previous_row,
                    index=previous_index,
                    description="This geometry is duplicated by another feature in the same layer.",
                    solution_hint="Review whether duplicate features should be merged, removed, or linked by a shared identifier.",
                )
            )
            flagged.add(previous_index)
        if index not in flagged:
            issues.append(
                build_issue(
                    "duplicate_geometry_same_layer",
                    row=row,
                    index=index,
                    description="This geometry duplicates another feature in the same layer.",
                    solution_hint="Review whether duplicate features should be merged, removed, or linked by a shared identifier.",
                )
            )
            flagged.add(index)
    return issues


def line_dangle(
    layer: Any,
    *,
    role_field: str | None = None,
    allowed_endpoint_values: set[str] | None = None,
) -> list[ValidationIssue]:
    """
    Detect line features with endpoint degree 1 that are not explicitly allowed service endpoints.

    This is intentionally deterministic and profile-configured: the validator only inspects
    endpoint connectivity and the optional role field supplied by the profile/runtime layer.
    """
    endpoint_counts: dict[tuple[float, float], int] = {}
    endpoint_rows: dict[Any, tuple[Any, tuple[float, float], tuple[float, float]]] = {}
    issues: list[ValidationIssue] = []

    def _normalize_point(point: Any) -> tuple[float, float] | None:
        try:
            x, y = point
            return (round(float(x), 9), round(float(y), 9))
        except Exception:
            return None

    for index, row in layer.iterrows():
        geometry = _geometry(row)
        endpoints = _linear_endpoint_pair(geometry)
        if endpoints is None:
            continue
        start = _normalize_point(endpoints[0])
        end = _normalize_point(endpoints[1])
        if start is None or end is None:
            continue
        endpoint_rows[index] = (row, start, end)
        endpoint_counts[start] = endpoint_counts.get(start, 0) + 1
        endpoint_counts[end] = endpoint_counts.get(end, 0) + 1

    allowed = {value.strip().lower() for value in (allowed_endpoint_values or set())}
    for index, (row, start, end) in endpoint_rows.items():
        is_allowed_endpoint = False
        if role_field is not None:
            try:
                role_value = row[role_field]
            except Exception:
                role_value = None
            if role_value is not None and str(role_value).strip().lower() in allowed:
                is_allowed_endpoint = True
        if is_allowed_endpoint:
            continue
        if endpoint_counts.get(start, 0) <= 1 or endpoint_counts.get(end, 0) <= 1:
            issues.append(
                build_issue(
                    "line_dangle",
                    row=row,
                    index=index,
                    description="This line has a dangling endpoint that is not explained by the configured endpoint role rules.",
                    solution_hint="Review whether the endpoint should connect to the network, terminate at an approved service endpoint, or be excluded from the profile.",
                )
            )
    return issues


def _normalize_endpoint(point: Any) -> tuple[float, float] | None:
    try:
        x, y = point
        return (round(float(x), 9), round(float(y), 9))
    except Exception:
        return None


def _line_endpoints(layer: Any) -> tuple[dict[Any, tuple[Any, tuple[float, float], tuple[float, float]]], dict[tuple[float, float], int]]:
    endpoint_rows: dict[Any, tuple[Any, tuple[float, float], tuple[float, float]]] = {}
    endpoint_counts: dict[tuple[float, float], int] = {}
    for index, row in layer.iterrows():
        geometry = _geometry(row)
        endpoints = _linear_endpoint_pair(geometry)
        if endpoints is None:
            continue
        start = _normalize_endpoint(endpoints[0])
        end = _normalize_endpoint(endpoints[1])
        if start is None or end is None:
            continue
        endpoint_rows[index] = (row, start, end)
        endpoint_counts[start] = endpoint_counts.get(start, 0) + 1
        endpoint_counts[end] = endpoint_counts.get(end, 0) + 1
    return endpoint_rows, endpoint_counts


def _row_role_value(row: Any, role_field: str | None) -> str | None:
    if role_field is None:
        return None
    try:
        value = row[role_field]
    except Exception:
        value = None
    if value is None:
        return None
    return str(value).strip().lower()


def polygon_gap_same_layer(layer: Any, *, min_gap_area: float = 0.0) -> list[ValidationIssue]:
    """
    Detect interior gaps in polygon coverage by dissolving the layer and inspecting holes.

    This reports one issue per discovered interior gap geometry.
    """
    geometries: list[Any] = []
    try:
        for _, row in layer.iterrows():
            geometry = _geometry(row)
            if geometry is not None:
                geometries.append(geometry)
    except Exception:
        return []
    if not geometries:
        return []
    try:
        from shapely.ops import unary_union
    except Exception:
        return []
    try:
        dissolved = unary_union(geometries)
    except Exception:
        return []

    issues: list[ValidationIssue] = []

    def _emit_gap(ring: Any, feature_id: str) -> None:
        try:
            area = float(getattr(ring, "area", 0.0) or 0.0)
        except Exception:
            area = 0.0
        if area < min_gap_area:
            return
        issues.append(
            build_issue(
                "polygon_gap_same_layer",
                feature_id=feature_id,
                geometry=ring,
                description=f"An interior polygon gap was detected in the same-layer coverage. Gap area: {area:.6f}.",
                solution_hint="Review adjacent polygon boundaries and close unintended gaps or document why the gap is valid.",
            )
        )

    def _inspect_polygon(polygon: Any, prefix: str) -> None:
        interiors = getattr(polygon, "interiors", None)
        if interiors is None:
            return
        for position, ring in enumerate(interiors, start=1):
            try:
                from shapely.geometry import Polygon

                gap_geometry = Polygon(ring)
            except Exception:
                continue
            _emit_gap(gap_geometry, f"{prefix}_gap_{position}")

    geom_type = getattr(dissolved, "geom_type", None)
    if geom_type == "Polygon":
        _inspect_polygon(dissolved, "layer")
    else:
        for position, polygon in enumerate(getattr(dissolved, "geoms", []), start=1):
            if getattr(polygon, "geom_type", None) == "Polygon":
                _inspect_polygon(polygon, f"part_{position}")
    return issues


def feature_not_split_at_intersection(layer: Any) -> list[ValidationIssue]:
    """Detect lines that cross at an interior point without being split into network nodes."""
    issues: list[ValidationIssue] = []
    flagged: set[Any] = set()
    for (left_index, left_row), (right_index, right_row) in _pairwise_rows_spatial(layer):
        left_geom = _geometry(left_row)
        right_geom = _geometry(right_row)
        if left_geom is None or right_geom is None:
            continue
        try:
            intersects = left_geom.intersects(right_geom)
            touches = left_geom.touches(right_geom)
        except Exception:
            continue
        if intersects and not touches:
            if left_index not in flagged:
                issues.append(
                    build_issue(
                        "feature_not_split_at_intersection",
                        row=left_row,
                        index=left_index,
                        description="This line crosses another line at an interior point but is not split into a network junction.",
                        solution_hint="Split both features at the intersection or document why an interior crossing is valid in this network.",
                    )
                )
                flagged.add(left_index)
            if right_index not in flagged:
                issues.append(
                    build_issue(
                        "feature_not_split_at_intersection",
                        row=right_row,
                        index=right_index,
                        description="This line crosses another line at an interior point but is not split into a network junction.",
                        solution_hint="Split both features at the intersection or document why an interior crossing is valid in this network.",
                    )
                )
                flagged.add(right_index)
    return issues


def isolated_network_segment(
    layer: Any,
    *,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
) -> list[ValidationIssue]:
    """Detect segments whose endpoints are both isolated from the rest of the network."""
    endpoint_rows, endpoint_counts = _line_endpoints(layer)
    allowed = {value.strip().lower() for value in (allowed_terminal_values or set())}
    issues: list[ValidationIssue] = []
    for index, (row, start, end) in endpoint_rows.items():
        role_value = _row_role_value(row, role_field)
        if role_value is not None and role_value in allowed:
            continue
        if endpoint_counts.get(start, 0) <= 1 and endpoint_counts.get(end, 0) <= 1:
            issues.append(
                build_issue(
                    "isolated_network_segment",
                    row=row,
                    index=index,
                    description="This line segment is isolated from the rest of the network at both endpoints.",
                    solution_hint="Review whether the segment should connect to nearby infrastructure, be merged, or be classified as a valid standalone feature.",
                )
            )
    return issues


def _endpoint_distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5


def _endpoint_distance_meters(left: tuple[float, float], right: tuple[float, float]) -> float:
    lon1, lat1 = math.radians(left[0]), math.radians(left[1])
    lon2, lat2 = math.radians(right[0]), math.radians(right[1])
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371008.8 * 2 * math.asin(min(1.0, math.sqrt(haversine)))


def _uses_geographic_distance(layer: Any) -> bool:
    crs = getattr(layer, "crs", None)
    if crs is None:
        return False
    is_geographic = getattr(crs, "is_geographic", None)
    if isinstance(is_geographic, bool):
        return is_geographic
    try:
        epsg = crs.to_epsg()
    except Exception:
        epsg = None
    return epsg in {4326, 4269}


def _row_feature_id(row: Any, index: Any) -> Any:
    for field_name in ("ID", "id", "fid", "FID", "objectid", "OBJECTID"):
        try:
            if hasattr(row, "index") and field_name in row.index:
                return row[field_name]
        except Exception:
            pass
        if isinstance(row, dict) and field_name in row:
            return row[field_name]
        if hasattr(row, field_name):
            return getattr(row, field_name)
    return index


def _nearest_endpoint_pair(
    left_points: tuple[tuple[float, float], tuple[float, float]],
    right_points: tuple[tuple[float, float], tuple[float, float]],
    tolerance: float,
    distance_fn: Any = _endpoint_distance,
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    best: tuple[tuple[float, float], tuple[float, float], float] | None = None
    for left_point in left_points:
        for right_point in right_points:
            distance = distance_fn(left_point, right_point)
            if distance <= 0.0 or distance > tolerance:
                continue
            if best is None or distance < best[2]:
                best = (left_point, right_point, distance)
    return best


def _endpoint_pair_key(
    left_index: Any,
    right_index: Any,
    endpoint_a: tuple[float, float],
    endpoint_b: tuple[float, float],
) -> tuple[str, str, tuple[float, float], tuple[float, float]]:
    left_label = str(left_index)
    right_label = str(right_index)
    first_endpoint = (round(endpoint_a[0], 12), round(endpoint_a[1], 12))
    second_endpoint = (round(endpoint_b[0], 12), round(endpoint_b[1], 12))
    if (right_label, second_endpoint) < (left_label, first_endpoint):
        return right_label, left_label, second_endpoint, first_endpoint
    return left_label, right_label, first_endpoint, second_endpoint


def _endpoint_issue_extra(
    *,
    related_feature_id: Any,
    endpoint_a: tuple[float, float],
    endpoint_b: tuple[float, float],
    distance: float,
    tolerance: float,
    distance_units: str,
) -> dict[str, Any]:
    return {
        "related_feature_id": related_feature_id,
        "endpoint_a": [float(endpoint_a[0]), float(endpoint_a[1])],
        "endpoint_b": [float(endpoint_b[0]), float(endpoint_b[1])],
        "distance": float(distance),
        "tolerance": float(tolerance),
        "distance_units": distance_units,
    }


def suspicious_near_miss_endpoints(
    layer: Any,
    *,
    snap_tolerance: float = 0.0,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
) -> list[ValidationIssue]:
    """Detect endpoints that are close enough to suggest an unintended near miss."""
    endpoint_rows, _ = _line_endpoints(layer)
    allowed = {value.strip().lower() for value in (allowed_terminal_values or set())}
    distance_fn = _endpoint_distance_meters if _uses_geographic_distance(layer) else _endpoint_distance
    distance_units = "meters" if distance_fn is _endpoint_distance_meters else "source_units"
    seen_pairs: set[Any] = set()
    flagged_features: set[Any] = set()
    issues: list[ValidationIssue] = []
    items = list(endpoint_rows.items())
    for position, (left_index, (left_row, left_start, left_end)) in enumerate(items):
        left_role = _row_role_value(left_row, role_field)
        if left_role is not None and left_role in allowed:
            continue
        if left_index in flagged_features:
            continue
        for right_index, (right_row, right_start, right_end) in items[position + 1 :]:
            if right_index in flagged_features:
                continue
            right_role = _row_role_value(right_row, role_field)
            if right_role is not None and right_role in allowed:
                continue
            pair = _nearest_endpoint_pair(
                (left_start, left_end),
                (right_start, right_end),
                float(snap_tolerance),
                distance_fn,
            )
            if pair is None:
                continue
            endpoint_a, endpoint_b, distance = pair
            pair_key = _endpoint_pair_key(left_index, right_index, endpoint_a, endpoint_b)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            flagged_features.update({left_index, right_index})
            right_feature_id = _row_feature_id(right_row, right_index)
            issues.append(
                build_issue(
                    "suspicious_near_miss_endpoints",
                    row=left_row,
                    index=left_index,
                    geometry={"type": "LineString", "coordinates": [[endpoint_a[0], endpoint_a[1]], [endpoint_b[0], endpoint_b[1]]]},
                    description=(
                        "These endpoints are close enough to look connected, but their coordinates do not touch. "
                        f"Gap distance: {distance:.6g} {distance_units}. Tolerance: {float(snap_tolerance):.6g} {distance_units}."
                    ),
                    solution_hint="Inspect the endpoint pair and snap or connect only if they represent the same network connection.",
                    extra=_endpoint_issue_extra(
                        related_feature_id=right_feature_id,
                        endpoint_a=endpoint_a,
                        endpoint_b=endpoint_b,
                        distance=distance,
                        tolerance=float(snap_tolerance),
                        distance_units=distance_units,
                    ),
                )
            )
    return issues


def unsnapped_endpoints_within_tolerance(
    layer: Any,
    *,
    snap_tolerance: float = 0.0,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
) -> list[ValidationIssue]:
    """Detect endpoints within snapping tolerance that remain disconnected."""
    endpoint_rows, endpoint_counts = _line_endpoints(layer)
    allowed = {value.strip().lower() for value in (allowed_terminal_values or set())}
    distance_fn = _endpoint_distance_meters if _uses_geographic_distance(layer) else _endpoint_distance
    distance_units = "meters" if distance_fn is _endpoint_distance_meters else "source_units"
    seen_pairs: set[Any] = set()
    flagged_features: set[Any] = set()
    issues: list[ValidationIssue] = []
    items = list(endpoint_rows.items())
    for position, (left_index, (left_row, left_start, left_end)) in enumerate(items):
        left_role = _row_role_value(left_row, role_field)
        if left_role is not None and left_role in allowed:
            continue
        if left_index in flagged_features:
            continue
        for right_index, (right_row, right_start, right_end) in items[position + 1 :]:
            if right_index in flagged_features:
                continue
            right_role = _row_role_value(right_row, role_field)
            if right_role is not None and right_role in allowed:
                continue
            pair: tuple[tuple[float, float], tuple[float, float], float] | None = None
            for left_point in (left_start, left_end):
                if endpoint_counts.get(left_point, 0) > 1:
                    continue
                for right_point in (right_start, right_end):
                    if endpoint_counts.get(right_point, 0) > 1:
                        continue
                    distance = distance_fn(left_point, right_point)
                    if 0.0 < distance <= float(snap_tolerance):
                        if pair is None or distance < pair[2]:
                            pair = (left_point, right_point, distance)
                        break
            if pair is None:
                continue
            endpoint_a, endpoint_b, distance = pair
            pair_key = _endpoint_pair_key(left_index, right_index, endpoint_a, endpoint_b)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            flagged_features.update({left_index, right_index})
            right_feature_id = _row_feature_id(right_row, right_index)
            issues.append(
                build_issue(
                    "unsnapped_endpoints_within_tolerance",
                    row=left_row,
                    index=left_index,
                    geometry={"type": "LineString", "coordinates": [[endpoint_a[0], endpoint_a[1]], [endpoint_b[0], endpoint_b[1]]]},
                    description=(
                        "This endpoint pair falls within the configured snapping tolerance but remains disconnected. "
                        f"Gap distance: {distance:.6g} {distance_units}. Tolerance: {float(snap_tolerance):.6g} {distance_units}."
                    ),
                    solution_hint="Snap the endpoint pair to the nearby feature or document why the disconnected near match is valid.",
                    extra=_endpoint_issue_extra(
                        related_feature_id=right_feature_id,
                        endpoint_a=endpoint_a,
                        endpoint_b=endpoint_b,
                        distance=distance,
                        tolerance=float(snap_tolerance),
                        distance_units=distance_units,
                    ),
                )
            )
    return issues


def boundary_mismatch_against_reference(
    layer: Any,
    reference_layer: Any,
    *,
    mismatch_ratio_threshold: float = 0.02,
) -> list[ValidationIssue]:
    """
    Detect polygon features whose boundary/area differs materially from the best matching
    feature in a reference layer.

    This is intended for authoritative-reference comparison, not for comparing against a
    cartographic basemap. A feature is flagged when the symmetric-difference area divided
    by the union area exceeds the provided ratio threshold.
    """
    issues: list[ValidationIssue] = []
    for index, row in layer.iterrows():
        geometry = _geometry(row)
        if geometry is None:
            continue

        best_match = None
        best_intersection_area = 0.0
        for reference_index, reference_row in _reference_candidates(reference_layer, geometry):
            reference_geometry = _geometry(reference_row)
            if reference_geometry is None:
                continue
            try:
                intersection = geometry.intersection(reference_geometry)
                intersection_area = float(getattr(intersection, "area", 0.0) or 0.0)
            except Exception:
                intersection_area = 0.0
            if intersection_area > best_intersection_area:
                best_intersection_area = intersection_area
                best_match = (reference_index, reference_row, reference_geometry)

        if best_match is None:
            continue

        _, reference_row, reference_geometry = best_match
        try:
            symmetric_difference = geometry.symmetric_difference(reference_geometry)
            union_geometry = geometry.union(reference_geometry)
            diff_area = float(getattr(symmetric_difference, "area", 0.0) or 0.0)
            union_area = float(getattr(union_geometry, "area", 0.0) or 0.0)
        except Exception:
            continue

        if union_area <= 0.0:
            continue

        mismatch_ratio = diff_area / union_area
        if mismatch_ratio > mismatch_ratio_threshold:
            issues.append(
                build_issue(
                    "boundary_mismatch_against_reference",
                    row=row,
                    index=index,
                    description=(
                        "This polygon differs materially from the best overlapping feature in the reference layer. "
                        f"Mismatch ratio: {mismatch_ratio:.4f}."
                    ),
                    solution_hint=(
                        "Compare this feature against an authoritative reference layer and review whether the source "
                        "boundary is outdated, generalized, misclassified, or otherwise incorrect."
                    ),
                )
            )
    return issues


__all__ = [
    "boundary_mismatch_against_reference",
    "duplicate_geometry_same_layer",
    "feature_not_split_at_intersection",
    "feature_within_feature",
    "isolated_network_segment",
    "line_dangle",
    "line_intersection_same_layer",
    "polygon_gap_same_layer",
    "polygon_overlap_same_layer",
    "suspicious_near_miss_endpoints",
    "unsnapped_endpoints_within_tolerance",
]
