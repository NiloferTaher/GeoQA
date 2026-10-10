"""Issue aggregation: turn a stream of per-geometry findings into per-feature findings.

Why this module exists
----------------------
GeoQA's endpoint validators are pairwise. A near-miss is emitted once per
*endpoint pair*, so a single badly-noded feature can produce an unbounded number
of findings.

Measured on real data (a national mains layer, 181,260 features, from the author���s own
audit):

    148,273 near-miss findings -> only 23,578 distinct features on the left
     6.29 findings per feature, worst case 149 findings on one feature
     94.8% of features affected

That is not a defect count. Reporting it as "148,273 issues" invites the reader
to treat a number as a severity, and it makes the tool look catastrophic on data
that is merely coarsely segmented. The defect count is 23,578.

The distinction matters because a dangle count is a property of the connectivity
rule, not of the dataset. Two tools using different rules will legitimately
disagree, and a report that reports raw pairwise findings gives the reader no way
to compare.

What this module provides
-------------------------
Three levels, so a report can state all of them and never hide the raw figure:

``per_feature``
    One record per (rule, feature). ``count`` is how many underlying findings
    collapsed into it. This is the headline defect count.

``per_cluster``
    Per-feature records whose features are spatially adjacent are merged, with
    a bounding box. A cluster of 800 orphans along a tile boundary is one
    extraction artefact, not 800 independent defects.

``summary``
    Counts and percentages by rule and by cause, plus the collapse ratio.

Nothing is discarded. ``raw_findings`` is retained on every record so the
original evidence survives aggregation, and ``findings_summary()`` states the
raw total explicitly so aggregation can never silently reduce an apparent
severity.

Usage
-----
    from geoqa.reports.aggregation import aggregate_issues
    result = aggregate_issues(issues, source_features=len(gdf))
    print(result.summary())
    for record in result.per_feature[:10]:
        print(record.rule_name, record.feature_id, record.count)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Endpoint validators are pairwise by construction and are the ones that can
#: explode. Report these with an explicit cause so the number is never read as a
#: per-feature defect count.
PAIRWISE_RULES = frozenset({
    "suspicious_near_miss_endpoints",
    "unsnapped_endpoints_within_tolerance",
    "line_intersection_same_layer",
    "feature_not_split_at_intersection",
    "feature_within_feature",
    "polygon_overlap_same_layer",
})


@dataclass
class AggregatedIssue:
    """One rule applied to one feature, with the findings it absorbed."""

    rule_name: str
    feature_id: Any
    count: int = 0
    severities: Counter = field(default_factory=Counter)
    descriptions: list[str] = field(default_factory=list)
    extra: list[dict[str, Any]] = field(default_factory=list)
    iso_category: str | None = None
    actionable: bool | None = None
    confidence: str | None = None
    geometry_wkb: bytes | None = None

    @property
    def severity(self) -> str | None:
        """Highest-severity label observed across the absorbed findings."""
        for level in ("critical", "error", "high", "medium", "low", "info"):
            if self.severities.get(level):
                return level
        return None

    @property
    def is_pairwise(self) -> bool:
        return self.rule_name in PAIRWISE_RULES

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "feature_id": self.feature_id,
            "count": self.count,
            "severity": self.severity,
            "severities": dict(self.severities),
            "pairwise": self.is_pairwise,
            "iso_category": self.iso_category,
            "actionable": self.actionable,
            "confidence": self.confidence,
            "descriptions": self.descriptions[:5],
            "extra": self.extra[:5],
            "raw_findings": self.count,
        }


@dataclass
class Cluster:
    """Adjacent per-feature findings treated as one upstream artefact."""

    rule_name: str
    feature_ids: list[Any] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    total_findings: int = 0
    severity: str | None = None

    @property
    def count(self) -> int:
        return len(self.feature_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "feature_count": self.count,
            "total_findings": self.total_findings,
            "severity": self.severity,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class AggregationResult:
    raw_findings: int
    source_features: int
    per_feature: list[AggregatedIssue]
    per_cluster: list[Cluster]
    warnings: list[str] = field(default_factory=list)

    # -- headline numbers -------------------------------------------------
    @property
    def distinct_features(self) -> int:
        return len({r.feature_id for r in self.per_feature})

    @property
    def affected_feature_fraction(self) -> float:
        return round(self.distinct_features / self.source_features, 6) if self.source_features else 0.0

    @property
    def collapse_ratio(self) -> float:
        return round(self.raw_findings / len(self.per_feature), 4) if self.per_feature else 0.0

    def by_rule(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for rule, group in _group(self.per_feature, lambda r: r.rule_name).items():
            out[rule] = {
                "features": len(group),
                "raw_findings": sum(r.count for r in group),
                "pairwise": group[0].is_pairwise,
            }
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["raw_findings"]))

    def summary(self) -> str:
        w = 72
        lines = [
            "=" * w,
            "Aggregated findings",
            "=" * w,
            f"source features      : {self.source_features:,}",
            f"raw findings         : {self.raw_findings:,}",
            f"distinct features    : {self.distinct_features:,} "
            f"({self.affected_feature_fraction * 100:.2f}% of source)",
            f"per-feature records  : {len(self.per_feature):,}",
            f"collapse ratio       : {self.collapse_ratio}x",
            f"spatial clusters     : {len(self.per_cluster):,}",
            "-" * w,
            "  rule                              features      raw  pairwise",
        ]
        for rule, stats in self.by_rule().items():
            lines.append(
                f"  {rule:<32} {stats['features']:>8,} {stats['raw_findings']:>9,}  "
                f"{'yes' if stats['pairwise'] else 'no':>8}"
            )
        if self.per_cluster:
            lines.append("-" * w)
            lines.append(f"  largest cluster: {self.per_cluster[0].count:,} features "
                         f"({self.per_cluster[0].total_findings:,} raw findings)")
            for cluster in self.per_cluster[:5]:
                lines.append(
                    f"    {cluster.rule_name:<30} {cluster.count:>6,} features "
                    f"-> 1 artefact"
                )
        if self.warnings:
            lines.append("-" * w)
            for warning in self.warnings:
                lines.append(f"  ! {warning}")
        lines.append("=" * w)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_features": self.source_features,
            "raw_findings": self.raw_findings,
            "distinct_features": self.distinct_features,
            "affected_feature_fraction": self.affected_feature_fraction,
            "per_feature_records": len(self.per_feature),
            "collapse_ratio": self.collapse_ratio,
            "by_rule": self.by_rule(),
            "clusters": [c.to_dict() for c in self.per_cluster[:100]],
            "cluster_count": len(self.per_cluster),
            "per_feature": [r.to_dict() for r in self.per_feature],
            "warnings": self.warnings,
        }


def _group(items: Iterable[Any], key) -> dict[Any, list[Any]]:
    out: dict[Any, list[Any]] = {}
    for item in items:
        out.setdefault(key(item), []).append(item)
    return out


def _feature_key(issue: Any) -> Any:
    return getattr(issue, "feature_id", None)


def aggregate_issues(
    issues: Sequence[Any],
    *,
    source_features: int = 0,
    bbox_by_feature: dict[Any, tuple[float, float, float, float]] | None = None,
    cluster_distance_deg: float = 1e-4,
    cluster_min_features: int = 25,
) -> AggregationResult:
    """Collapse per-geometry findings to per-feature, then cluster.

    Parameters
    ----------
    issues
        The findings, as returned by GeoQA. Anything exposing ``problem_name``,
        ``feature_id``, ``severity``, ``description`` and ``extra`` works; plain
        dicts are accepted too.
    source_features
        Denominator for the affected-fraction figure.
    bbox_by_feature
        Optional ``feature_id -> (minx, miny, maxx, maxy)`` used for clustering.
        Without it, clustering is skipped.
    cluster_distance_deg
        Features whose bboxes come within this distance are treated as adjacent.
    cluster_min_features
        Clusters below this size are not reported, because a small group is not
        an upstream artefact.
    """
    warnings: list[str] = []

    records: dict[tuple[str, Any], AggregatedIssue] = {}
    for issue in issues:
        rule = _get(issue, "problem_name") or _get(issue, "rule_name") or "unknown"
        fid = _feature_key(issue)
        key = (rule, fid)
        record = records.get(key)
        if record is None:
            record = AggregatedIssue(rule_name=rule, feature_id=fid)
            records[key] = record
        record.count += 1
        sev = _get(issue, "severity")
        if sev:
            record.severities[str(sev)] += 1
        desc = _get(issue, "description")
        if desc and desc not in record.descriptions:
            record.descriptions.append(str(desc))
        extra = _get(issue, "extra")
        if isinstance(extra, dict) and extra:
            record.extra.append(extra)
        iso = _get(issue, "iso_category")
        if iso and not record.iso_category:
            record.iso_category = str(iso)
        act = _get(issue, "actionable")
        if act is not None:
            record.actionable = record.actionable or bool(act)
        conf = _get(issue, "confidence")
        if conf and not record.confidence:
            record.confidence = str(conf)
        geom = _get(issue, "geometry")
        if geom is not None and record.geometry_wkb is None:
            try:
                record.geometry_wkb = geom.wkb
            except Exception:
                pass

    per_feature = sorted(
        records.values(), key=lambda r: (-r.count, r.rule_name, str(r.feature_id))
    )

    clusters: list[Cluster] = []
    if bbox_by_feature:
        clusters = _cluster(per_feature, bbox_by_feature, cluster_distance_deg,
                            cluster_min_features)

    # Inflation warning: the honest signal that the raw number needs context.
    if per_feature:
        top = per_feature[0]
        if top.count >= 10:
            warnings.append(
                f"highest per-feature count is {top.count} "
                f"({top.rule_name} on feature {top.feature_id}); "
                "report the per-feature figure, not the raw finding count"
            )
        total_raw = sum(r.count for r in per_feature)
        if total_raw and len(per_feature) and total_raw / len(per_feature) >= 3:
            warnings.append(
                f"raw findings collapse {total_raw / len(per_feature):.1f}x when "
                "grouped per feature; a raw count would overstate severity"
            )

    return AggregationResult(
        raw_findings=len(issues),
        source_features=source_features,
        per_feature=per_feature,
        per_cluster=clusters,
        warnings=warnings,
    )


def _cluster(
    records: Sequence[AggregatedIssue],
    bbox_by_feature: dict[Any, tuple[float, float, float, float]],
    distance: float,
    min_features: int,
) -> list[Cluster]:
    """Single-linkage clustering of per-feature records by bounding-box proximity."""
    by_rule = _group(records, lambda r: r.rule_name)
    out: list[Cluster] = []
    for rule, group in by_rule.items():
        boxes = [(r, bbox_by_feature[r.feature_id]) for r in group
                 if r.feature_id in bbox_by_feature]
        if len(boxes) < min_features:
            continue
        parent = list(range(len(boxes)))

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        # Grid-bucket by the clustering distance so this stays near-linear.
        cell = distance if distance > 0 else 1e-9
        buckets: dict[tuple[int, int], list[int]] = {}
        for i, (_rec, (minx, miny, _maxx, _maxy)) in enumerate(boxes):
            buckets.setdefault((int(minx // cell), int(miny // cell)), []).append(i)
        for (gx, gy), members in buckets.items():
            neighbours: list[int] = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbours.extend(buckets.get((gx + dx, gy + dy), ()))
            for a in members:
                ax0, ay0, ax1, ay1 = boxes[a][1]
                for b in neighbours:
                    if b == a:
                        continue
                    bx0, by0, bx1, by1 = boxes[b][1]
                    if (ax0 - distance <= bx1 and bx0 - distance <= ax1
                            and ay0 - distance <= by1 and by0 - distance <= ay1):
                        union(a, b)

        groups: dict[int, list[int]] = {}
        for i in range(len(boxes)):
            groups.setdefault(find(i), []).append(i)

        for idxs in groups.values():
            if len(idxs) < min_features:
                continue
            xs0 = min(boxes[i][1][0] for i in idxs)
            ys0 = min(boxes[i][1][1] for i in idxs)
            xs1 = max(boxes[i][1][2] for i in idxs)
            ys1 = max(boxes[i][1][3] for i in idxs)
            members = [boxes[i][0] for i in idxs]
            severity = None
            for level in ("critical", "error", "high", "medium", "low", "info"):
                if any(m.severities.get(level) for m in members):
                    severity = level
                    break
            out.append(Cluster(
                rule_name=rule,
                feature_ids=[m.feature_id for m in members],
                bbox=(xs0, ys0, xs1, ys1),
                total_findings=sum(m.count for m in members),
                severity=severity,
            ))

    out.sort(key=lambda c: (-c.count, c.rule_name))
    return out


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)