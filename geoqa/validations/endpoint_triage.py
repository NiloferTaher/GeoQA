"""Endpoint resolution and dangle triage.

Why this exists
---------------
``line_dangle`` reports every line endpoint whose degree is 1. On utility
networks that is frequently correct: an unconnected stub IS a defect. On raw
crowdsourced or extracted vector data it is frequently not, for reasons the
validator cannot see from the line layer alone:

1. **Separated line/node topology.** In PostGIS utility models, OSM and most
   network formats, the feature that terminates a line may be a POINT in a
   companion layer. A line ending at a valve, hydrant or outfall node looks
   perfectly dangling when only the line layer is loaded. This is the single
   largest source of false positives in practice, and it is invisible unless a
   second layer is supplied.

2. **Declared terminal roles.** Some endpoints are legitimately terminal by
   design. ``line_dangle`` already honours ``role_field`` / allowed values, but
   it silently drops those features, so a triage report cannot show how many
   findings were suppressed by role rather than absent.

3. **Clipped extraction boundaries.** A shapefile cut to an extent boundary
   produces hundreds of "dangles" along that boundary. Individually each is a
   finding; collectively they are one extraction artefact. Clustering them
   changes the fix from "repair 800 features" to "re-extract the tile".

This module produces that triage. It is a diagnostic complement to
``line_dangle``: it does not replace it, and it does not decide what is a
defect. It tells a reviewer how the findings decompose, so a report of 13,000
dangles becomes an actionable statement.

Scale
-----
Every spatial query uses an STRtree built once over the endpoint set and, when
supplied, the companion node layer. The whole triage is O(n log n) in the
number of endpoints. This deliberately reuses the same index-prune-then-exact
pattern as ``_endpoint_candidate_provider`` in topology.py: the index narrows
candidates, the exact distance test is authoritative.

CRS handling
------------
Tolerances are expressed in METRES. For a geographic CRS they are converted to
a degree radius using the layer's own helpers, so callers never have to think
in degrees. For a projected CRS the tolerance is assumed to already be in the
CRS linear unit, which matches the existing near-miss validators.

Usage
-----
    from geoqa.validations.endpoint_triage import triage_endpoints
    t = triage_endpoints(lines, snap_tolerance=50.0,
                         companion_layer=nodes,
                         role_field="asset_type",
                         allowed_endpoint_values={"outfall", "hydrant"})
    print(t.summary())
    for c in t.orphan_clusters[:5]:
        print(c.bbox, c.count)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .base import ValidationIssue, build_issue
from .topology import (
    _endpoint_distance_meters,
    _geometry,
    _linear_endpoint_pair,
    _line_endpoints,
    _meter_tolerance_to_degree_radius,
    _row_role_value,
    _uses_geographic_distance,
)

# Cause codes. Kept as plain strings so they serialise into reports unchanged.
CAUSE_NEAR_MISS = "near_miss"
CAUSE_ORPHAN = "orphan"
CAUSE_ROLE_TERMINAL = "role_terminal"
CAUSE_RESOLVED_BY_NODE = "resolved_by_companion_node"

#: Below this shared-endpoint fraction a layer is better described as a
#: collection of segments than as a network, and per-feature dangle counts
#: cannot be read as per-feature defect counts.
NETWORK_SHARED_THRESHOLD = 0.50


@dataclass
class NetworkCharacter:
    """Is this layer actually a connected network?

    This is the diagnostic that has to come BEFORE any dangle triage. A dangle
    count is only meaningful when the layer is sufficiently noded. On a layer
    stored as many short segments - which is how crowdsourced and most
    exchange data arrives - the great majority of endpoints are legitimately
    free, and a raw dangle count reads as a defect count when it is really a
    measure of how the data was cut up.

    Attributes
    ----------
    line_features
        Features contributing at least one endpoint pair.
    endpoint_positions
        Distinct endpoint coordinates.
    degree_distribution
        degree -> number of positions with that degree.
    shared_positions
        Positions shared by two or more features, i.e. genuinely noded.
    shared_fraction
        ``shared_positions / endpoint_positions``.
    is_network
        ``shared_fraction >= NETWORK_SHARED_THRESHOLD``.
    """

    line_features: int
    endpoint_positions: int
    degree_distribution: dict[int, int]
    shared_positions: int
    shared_fraction: float
    is_network: bool = False
    guidance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_features": self.line_features,
            "endpoint_positions": self.endpoint_positions,
            "degree_distribution": {str(k): v for k, v in
                                    sorted(self.degree_distribution.items())},
            "shared_positions": self.shared_positions,
            "shared_fraction": round(self.shared_fraction, 6),
            "shared_fraction_pct": round(100.0 * self.shared_fraction, 3),
            "degree1_positions": self.degree_distribution.get(1, 0),
            "is_network": self.is_network,
            "threshold": NETWORK_SHARED_THRESHOLD,
            "guidance": self.guidance,
        }

    def summary(self) -> str:
        dist = "  ".join(f"d{k}={v:,}" for k, v in sorted(self.degree_distribution.items()))
        return (
            "\n".join([
                "Network character",
                f"  line features        : {self.line_features:,}",
                f"  endpoint positions   : {self.endpoint_positions:,}",
                f"  degree distribution  : {dist}",
                f"  shared (noded)       : {self.shared_positions:,} "
                f"({100.0 * self.shared_fraction:.2f}%)",
                f"  verdict              : "
                f"{'treated as a connected network' if self.is_network else 'NOT a connected network'}",
            ])
        )


def network_character(layer: Any) -> NetworkCharacter:
    """Measure how noded a line layer is, before trusting any dangle count."""
    endpoint_rows, endpoint_counts = _line_endpoints(layer)
    n_pos = len(endpoint_counts)
    if n_pos == 0:
        return NetworkCharacter(
            line_features=0, endpoint_positions=0, degree_distribution={},
            shared_positions=0, shared_fraction=0.0, is_network=False,
            guidance=["layer produced no line endpoints; nothing to triage"],
        )

    distribution: dict[int, int] = {}
    for degree in endpoint_counts.values():
        distribution[degree] = distribution.get(degree, 0) + 1
    shared = sum(1 for d in endpoint_counts.values() if d > 1)
    frac = shared / n_pos

    guidance: list[str] = []
    if frac < NETWORK_SHARED_THRESHOLD:
        guidance.append(
            f"only {100.0 * frac:.1f}% of endpoint positions are shared, so most "
            "endpoints are free by construction. A per-feature dangle count here "
            "measures how the data was segmented, not how many defects exist."
        )
        guidance.append(
            "supply companion_layer if the continuation lives in a separate "
            "line/node topology"
        )
        guidance.append(
            "supply role_field + allowed_endpoint_values if terminals are "
            "declared by attribute (outfall, source, intake, culdesac)"
        )
        guidance.append(
            "consider re-deriving a noded network, or restricting topology "
            "checks to an explicit region of interest"
        )
    else:
        guidance.append(
            "layer is sufficiently noded for per-feature topology findings to "
            "be read individually"
        )

    return NetworkCharacter(
        line_features=len(endpoint_rows),
        endpoint_positions=n_pos,
        degree_distribution=distribution,
        shared_positions=shared,
        shared_fraction=frac,
        is_network=frac >= NETWORK_SHARED_THRESHOLD,
        guidance=guidance,
    )


@dataclass(frozen=True)
class EndpointFinding:
    """One endpoint adjudicated by the triage."""

    feature_id: Any
    endpoint: str            # "start" | "end"
    coordinate: tuple[float, float]
    cause: str
    #: For near-miss, the distance in metres to the nearest other endpoint.
    distance_m: float | None = None
    #: For resolved_by_companion_node, the node id that supplied the connection.
    companion_id: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "endpoint": self.endpoint,
            "coordinate": list(self.coordinate),
            "cause": self.cause,
            "distance_m": self.distance_m,
            "companion_id": self.companion_id,
        }


@dataclass
class OrphanCluster:
    """A spatial cluster of orphan endpoints.

    A tight cluster of many orphans is almost always one upstream cause -
    clipped extraction, missing companion layer, or a systematic snapping
    failure - rather than that many independent defects.
    """

    count: int
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    feature_ids: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "centroid": list(self.centroid),
            "bbox": list(self.bbox),
            "feature_ids": self.feature_ids[:50],
        }


@dataclass
class EndpointTriage:
    findings: list[EndpointFinding]
    cluster_radius_m: float
    snap_tolerance_m: float
    max_search_radius_m: float
    companion_supplied: bool
    role_field: str | None
    character: NetworkCharacter | None = None
    orphan_clusters: list[OrphanCluster] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # -- counts ---------------------------------------------------------
    def by_cause(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.cause] = counts.get(f.cause, 0) + 1
        return counts

    @property
    def total(self) -> int:
        return len(self.findings)

    def percentages(self) -> dict[str, float]:
        counts = self.by_cause()
        total = self.total or 1
        return {k: round(100.0 * v / total, 2) for k, v in counts.items()}

    def of(self, cause: str) -> list[EndpointFinding]:
        return [f for f in self.findings if f.cause == cause]

    # -- reporting ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        counts = self.by_cause()
        return {
            "total_endpoints_examined": self.total,
            "snap_tolerance_m": self.snap_tolerance_m,
            "max_search_radius_m": self.max_search_radius_m,
            "cluster_radius_m": self.cluster_radius_m,
            "companion_layer_supplied": self.companion_supplied,
            "role_field": self.role_field,
            "counts": counts,
            "percentages": self.percentages(),
            "orphan_cluster_count": len(self.orphan_clusters),
            "largest_orphan_cluster": (
                self.orphan_clusters[0].count if self.orphan_clusters else 0
            ),
            "orphan_clusters": [c.to_dict() for c in self.orphan_clusters[:25]],
            "network_character": self.character.to_dict() if self.character else None,
            "warnings": self.warnings,
        }

    def summary(self) -> str:
        counts = self.by_cause()
        pct = self.percentages()
        width = 62
        lines = []
        if self.character is not None:
            lines.append("=" * width)
            lines.append("Endpoint triage")
            lines.append("=" * width)
            for line in self.character.summary().splitlines():
                lines.append(line)
            lines.append("-" * width)
        else:
            lines += ["=" * width, "Endpoint triage", "=" * width]
        lines += [
            f"endpoints examined : {self.total}",
            f"snap tolerance     : {self.snap_tolerance_m} m",
            f"max search radius  : {self.max_search_radius_m} m",
            f"companion layer    : "
            f"{'supplied' if self.companion_supplied else 'NONE - line layer only'}",
            f"role field         : {self.role_field or '(none)'}",
            "-" * width,
        ]
        for cause in (CAUSE_RESOLVED_BY_NODE, CAUSE_ROLE_TERMINAL,
                      CAUSE_NEAR_MISS, CAUSE_ORPHAN):
            if counts.get(cause):
                lines.append(f"  {cause:<28} {counts[cause]:>8}  {pct[cause]:>6.2f}%")
        if self.orphan_clusters:
            lines.append("-" * width)
            lines.append(
                f"  orphan clusters (r={self.cluster_radius_m} m): "
                f"{len(self.orphan_clusters)}"
            )
            lines.append(f"  largest cluster: {self.orphan_clusters[0].count} orphans")
        guidance = list(self.warnings)
        if self.character is not None:
            guidance = self.character.guidance + guidance
        if guidance:
            lines.append("-" * width)
            for w in guidance:
                lines.append(f"  ! {w}")
        lines.append("=" * width)
        return "\n".join(lines)

    def to_issues(self, *, limit: int | None = None) -> list[ValidationIssue]:
        """Convert unresolved findings to ValidationIssues for the normal report.

        Role terminals and companion-resolved endpoints are NOT emitted: they
        are explained, not defective. Only near_miss and orphan reach the
        report, each carrying its cause in the description.
        """
        out: list[ValidationIssue] = []
        for f in self.findings:
            if f.cause in (CAUSE_ROLE_TERMINAL, CAUSE_RESOLVED_BY_NODE):
                continue
            if limit is not None and len(out) >= limit:
                break
            if f.cause == CAUSE_NEAR_MISS:
                desc = (
                    "Endpoint is a near-miss: another line endpoint lies within "
                    f"{f.distance_m:.2f} m but shares no node. These two "
                    "features probably belong connected."
                )
                hint = (
                    "Snap the two endpoints to a shared node, or confirm the "
                    "gap is intentional before treating it as a defect."
                )
            else:
                desc = (
                    "Endpoint is an orphan: no other line endpoint and no "
                    "companion node lies within "
                    f"{self.max_search_radius_m} m."
                )
                hint = (
                    "Check whether the continuation lives in a companion layer "
                    "that was not supplied, whether this is a real break, or "
                    "whether the feature is a legitimate terminal."
                )
            out.append(
                build_issue(
                    "endpoint_unresolved",
                    feature_id=f.feature_id,
                    description=desc,
                    solution_hint=hint,
                    extra={
                        "cause": f.cause,
                        "endpoint": f.endpoint,
                        "coordinate": list(f.coordinate),
                        "distance_m": f.distance_m,
                    },
                )
            )
        return out


def _node_points(companion_layer: Any) -> tuple[list[tuple[float, float]], list[Any]]:
    """Extract node coordinates and ids from a companion point layer."""
    coords: list[tuple[float, float]] = []
    ids: list[Any] = []
    for index, row in companion_layer.iterrows():
        geometry = _geometry(row)
        if geometry is None:
            continue
        gtype = getattr(geometry, "geom_type", "")
        if gtype == "Point":
            pt = (geometry.x, geometry.y)
        elif gtype == "MultiPoint" and len(geometry.geoms):
            p = geometry.geoms[0]
            pt = (p.x, p.y)
        elif hasattr(geometry, "representative_point"):
            rp = geometry.representative_point()
            pt = (rp.x, rp.y)
        else:
            continue
        fid = None
        for cand in ("node_id", "osmid", "osm_id", "id", "asset_id", "point_id"):
            try:
                if cand in companion_layer.columns:
                    fid = row[cand]
                    break
            except Exception:
                continue
        coords.append((float(pt[0]), float(pt[1])))
        ids.append(fid if fid is not None else index)
    return coords, ids


def _grid_clusters(
    points: list[tuple[tuple[float, float], Any]],
    radius_deg: float,
) -> list[OrphanCluster]:
    """Cluster points by grid-hash adjacency at the given radius.

    A uniform grid keyed on cell size == radius, with a 3x3 neighbourhood
    search, gives single-linkage clustering without the O(n^2) of naive
    agglomeration or a dependency on scikit-learn. It is deterministic.
    """
    if not points or radius_deg <= 0:
        return []
    cell = radius_deg
    buckets: dict[tuple[int, int], list[int]] = {}
    for i, ((x, y), _fid) in enumerate(points):
        buckets.setdefault((int(x // cell), int(y // cell)), []).append(i)

    parent = list(range(len(points)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for (gx, gy), members in buckets.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                other = buckets.get((gx + dx, gy + dy))
                if not other:
                    continue
                for a in members:
                    ax, ay = points[a][0]
                    for b in other:
                        bx, by = points[b][0]
                        if abs(ax - bx) <= cell and abs(ay - by) <= cell:
                            union(a, b)

    groups: dict[int, list[int]] = {}
    for i in range(len(points)):
        groups.setdefault(find(i), []).append(i)

    clusters: list[OrphanCluster] = []
    for idxs in groups.values():
        xs = [points[i][0][0] for i in idxs]
        ys = [points[i][0][1] for i in idxs]
        clusters.append(
            OrphanCluster(
                count=len(idxs),
                centroid=(sum(xs) / len(xs), sum(ys) / len(ys)),
                bbox=(min(xs), min(ys), max(xs), max(ys)),
                feature_ids=[points[i][1] for i in idxs],
            )
        )
    clusters.sort(key=lambda c: (-c.count, c.centroid))
    return clusters


def triage_endpoints(
    layer: Any,
    *,
    snap_tolerance: float | None = 50.0,
    max_search_radius: float | None = None,
    role_field: str | None = None,
    allowed_endpoint_values: Iterable[str] | None = None,
    companion_layer: Any | None = None,
    cluster_radius: float | None = None,
) -> EndpointTriage:
    """Adjudicate every line endpoint in ``layer``.

    Parameters
    ----------
    layer
        The line layer to triage.
    snap_tolerance
        Metres. An endpoint within this distance of ANOTHER line endpoint
        (but not sharing a node) is a near-miss. This is the classic OSM
        "unconnected ways" defect.
    max_search_radius
        Metres. An endpoint with no other endpoint inside this radius is an
        orphan. Defaults to ``snap_tolerance * 4``. Larger values are more
        forgiving of sparse networks but risk merging genuinely separate
        features.
    role_field
        Column carrying a terminal-role value, e.g. ``asset_type``.
    allowed_endpoint_values
        Role values that legitimately terminate. Reported separately rather
        than silently dropped.
    companion_layer
        Point/node layer supplying the other half of a separated topology.
        This is the highest-value input: supplying it converts large numbers of
        false dangles into explained connections.
    cluster_radius
        Metres for orphan clustering. Defaults to ``snap_tolerance / 2``.

    Returns
    -------
    EndpointTriage
    """
    warnings: list[str] = []
    snap = float(snap_tolerance) if snap_tolerance else 0.0
    max_r = float(max_search_radius) if max_search_radius else snap * 4.0
    if max_r <= 0:
        max_r = snap
    cl_r = float(cluster_radius) if cluster_radius else max(snap / 2.0, 1e-9)

    endpoint_rows, endpoint_counts = _line_endpoints(layer)

    if _uses_geographic_distance(layer):
        snap_deg = _meter_tolerance_to_degree_radius(layer, snap) or 0.0
        max_deg = _meter_tolerance_to_degree_radius(layer, max_r) or 0.0
        cluster_deg = _meter_tolerance_to_degree_radius(layer, cl_r) or 0.0
    else:
        # Projected layer: caller tolerance is already in CRS linear units.
        snap_deg = snap
        max_deg = max_r
        cluster_deg = cl_r

    if cluster_deg <= 0:
        cluster_deg = max_deg if max_deg > 0 else 1.0
        warnings.append(
            "cluster radius resolved to zero; clustering used the search radius"
        )

    # -- spatial indices -------------------------------------------------
    from shapely.geometry import Point, box
    from shapely.strtree import STRtree

    items = [
        (index, (row, start, end))
        for index, (row, start, end) in endpoint_rows.items()
    ]
    points: list[Point] = []
    for _index, (_row, start, end) in items:
        points.append(Point(start))
        points.append(Point(end))
    endpoint_tree = STRtree(points) if points else None

    companion_coords: list[tuple[float, float]] = []
    companion_ids: list[Any] = []
    companion_tree = None
    if companion_layer is not None:
        companion_coords, companion_ids = _node_points(companion_layer)
        if companion_coords:
            companion_tree = STRtree([Point(c) for c in companion_coords])
        if not companion_coords:
            warnings.append(
                "companion_layer supplied but contained no point geometries"
            )
    else:
        warnings.append(
            "no companion layer supplied - endpoints that terminate at a node "
            "in a separate layer will be reported as orphans"
        )

    allowed = {str(v).strip().lower() for v in (allowed_endpoint_values or set())}

    findings: list[EndpointFinding] = []
    orphan_points: list[tuple[tuple[float, float], Any]] = []

    def _feature_id(row: Any, index: Any) -> Any:
        for cand in ("node_id", "osmid", "osm_id", "id", "asset_id", "feature_id"):
            try:
                if cand in getattr(layer, "columns", []):
                    return row[cand]
            except Exception:
                continue
        return index

    for pos, (index, (row, start, end)) in enumerate(items):
        fid = _feature_id(row, index)
        role_value = _row_role_value(row, role_field)
        role_ok = role_value is not None and role_value in allowed

        for label, coord in (("start", start), ("end", end)):
            if endpoint_counts.get(coord, 0) > 1:
                # Connected to another endpoint in this layer. Not a finding.
                continue

            if role_ok:
                findings.append(
                    EndpointFinding(
                        feature_id=fid, endpoint=label, coordinate=coord,
                        cause=CAUSE_ROLE_TERMINAL,
                    )
                )
                continue

            # 1. companion node within snap tolerance wins: it supplies the
            #    other half of a separated line/node topology.
            if companion_tree is not None:
                p = Point(coord)
                qbox = box(coord[0] - snap_deg, coord[1] - snap_deg,
                           coord[0] + snap_deg, coord[1] + snap_deg)
                hit = False
                for idx in companion_tree.query(qbox):
                    node_pt = Point(companion_coords[int(idx)])
                    d_m = _endpoint_distance_meters(coord, (node_pt.x, node_pt.y))
                    if _uses_geographic_distance(layer):
                        if d_m <= snap:
                            hit = True
                            findings.append(
                                EndpointFinding(
                                    feature_id=fid, endpoint=label,
                                    coordinate=coord,
                                    cause=CAUSE_RESOLVED_BY_NODE,
                                    distance_m=round(d_m, 3),
                                    companion_id=companion_ids[int(idx)],
                                )
                            )
                            break
                    else:
                        if abs(node_pt.x - coord[0]) <= snap_deg and \
                           abs(node_pt.y - coord[1]) <= snap_deg:
                            hit = True
                            findings.append(
                                EndpointFinding(
                                    feature_id=fid, endpoint=label,
                                    coordinate=coord,
                                    cause=CAUSE_RESOLVED_BY_NODE,
                                    distance_m=round(d_m, 3),
                                    companion_id=companion_ids[int(idx)],
                                )
                            )
                            break
                if hit:
                    continue

            # 2. near-miss: another endpoint within snap_tolerance.
            nearest = None
            nearest_m = None
            if endpoint_tree is not None:
                p = Point(coord)
                qbox = box(coord[0] - snap_deg, coord[1] - snap_deg,
                           coord[0] + snap_deg, coord[1] + snap_deg)
                for idx in endpoint_tree.query(qbox):
                    ep = points[int(idx)]
                    if abs(ep.x - coord[0]) > snap_deg or \
                       abs(ep.y - coord[1]) > snap_deg:
                        continue
                    other_pos = int(idx) // 2
                    if other_pos == pos:
                        continue
                    d_m = _endpoint_distance_meters(coord, (ep.x, ep.y))
                    if nearest_m is None or d_m < nearest_m:
                        nearest_m = d_m
                        nearest = (ep.x, ep.y)
            if nearest_m is not None and nearest_m <= snap:
                findings.append(
                    EndpointFinding(
                        feature_id=fid, endpoint=label, coordinate=coord,
                        cause=CAUSE_NEAR_MISS, distance_m=round(nearest_m, 3),
                    )
                )
                continue

            # 3. orphan
            findings.append(
                EndpointFinding(
                    feature_id=fid, endpoint=label, coordinate=coord,
                    cause=CAUSE_ORPHAN,
                )
            )
            orphan_points.append((coord, f"{fid}:{label}"))

    clusters = _grid_clusters(orphan_points, cluster_deg) if orphan_points else []
    if len(clusters) == 1 and clusters[0].count >= 10:
        warnings.append(
            f"{clusters[0].count} orphans form a single spatial cluster - this "
            "is usually one upstream cause (clipped extraction, missing "
            "companion layer, or a snapping threshold problem), not "
            f"{clusters[0].count} independent defects"
        )

    return EndpointTriage(
        findings=findings,
        cluster_radius_m=cl_r,
        snap_tolerance_m=snap,
        max_search_radius_m=max_r,
        companion_supplied=companion_layer is not None,
        role_field=role_field,
        character=network_character(layer),
        orphan_clusters=clusters,
        warnings=warnings,
    )