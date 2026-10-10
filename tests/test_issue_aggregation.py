"""Tests for per-feature issue aggregation.

The behaviour pinned here was measured on real data before it was written: on
a national mains layer (181,260 features) the near-miss validator emitted 148,273
findings across only 23,578 distinct features, 6.29 per feature and 149 on the
worst one. Reporting the raw count as a defect count overstates severity by
6.29x on that dataset.

Aggregation must therefore collapse correctly, must never discard evidence, and
must state the raw total so a reader can see what was collapsed.
"""

from __future__ import annotations

import pytest

from geoqa.reports.aggregation import (
    AggregationResult,
    aggregate_issues,
)


class _Issue:
    """Minimal stand-in for a ValidationIssue."""

    def __init__(self, problem_name, feature_id, severity="medium", description="d",
                 extra=None, geometry=None):
        self.problem_name = problem_name
        self.feature_id = feature_id
        self.severity = severity
        self.description = description
        self.confidence = "high"
        self.actionable = True
        self.iso_category = "Logical Consistency"
        self.extra = extra or {}
        self.geometry = geometry


def test_single_finding_passes_through_unchanged():
    result = aggregate_issues([_Issue("line_dangle", 7)], source_features=10)
    assert result.raw_findings == 1
    assert len(result.per_feature) == 1
    assert result.per_feature[0].count == 1
    assert result.collapse_ratio == 1.0


def test_repeated_findings_collapse_to_one_record():
    """The core fix: 149 findings on one feature become one record with count 149."""
    issues = [_Issue("suspicious_near_miss_endpoints", 42) for _ in range(149)]
    result = aggregate_issues(issues, source_features=100)
    assert result.raw_findings == 149
    assert len(result.per_feature) == 1
    record = result.per_feature[0]
    assert record.count == 149
    # the raw evidence is retained, not discarded
    assert record.to_dict()["raw_findings"] == 149
    assert result.collapse_ratio == 149.0


def test_distinct_features_is_not_finding_count():
    """Reproduces the measured mains-layer shape: many findings, fewer features."""
    issues = []
    for feature in range(50):
        for _ in range(6):
            issues.append(_Issue("suspicious_near_miss_endpoints", feature))
    result = aggregate_issues(issues, source_features=181_260)
    assert result.raw_findings == 300
    assert result.distinct_features == 50
    assert len(result.per_feature) == 50
    # affected_feature_fraction is rounded to 6 dp for a readable report figure
    assert result.affected_feature_fraction == pytest.approx(50 / 181_260, abs=5e-7)


def test_different_rules_on_same_feature_stay_separate():
    issues = [
        _Issue("suspicious_near_miss_endpoints", 1),
        _Issue("suspicious_near_miss_endpoints", 1),
        _Issue("line_dangle", 1),
    ]
    result = aggregate_issues(issues, source_features=5)
    keys = sorted((r.rule_name, r.feature_id) for r in result.per_feature)
    assert keys == [("line_dangle", 1), ("suspicious_near_miss_endpoints", 1)]


def test_severity_takes_the_highest_observed():
    issues = [
        _Issue("line_dangle", 1, severity="low"),
        _Issue("line_dangle", 1, severity="high"),
        _Issue("line_dangle", 1, severity="medium"),
    ]
    result = aggregate_issues(issues, source_features=5)
    assert result.per_feature[0].severity == "high"


def test_pairwise_rules_are_flagged():
    result = aggregate_issues(
        [_Issue("suspicious_near_miss_endpoints", 1)], source_features=1
    )
    assert result.per_feature[0].is_pairwise is True
    result2 = aggregate_issues([_Issue("self_intersection", 1)], source_features=1)
    assert result2.per_feature[0].is_pairwise is False


def test_inflation_warning_fires_on_blowup():
    issues = [_Issue("suspicious_near_miss_endpoints", i % 10) for i in range(100)]
    result = aggregate_issues(issues, source_features=10)
    assert any("overstate severity" in w for w in result.warnings), result.warnings


def test_worst_offender_warning_fires():
    issues = [_Issue("suspicious_near_miss_endpoints", 1) for _ in range(149)]
    issues += [_Issue("suspicious_near_miss_endpoints", i) for i in range(2, 20)]
    result = aggregate_issues(issues, source_features=20)
    assert any("highest per-feature count" in w for w in result.warnings), result.warnings


def test_dicts_are_accepted_as_issues():
    """Report JSON round-trips through dicts, so aggregation must handle them."""
    issues = [{"problem_name": "line_dangle", "feature_id": 3, "severity": "high"}] * 4
    result = aggregate_issues(issues, source_features=10)
    assert len(result.per_feature) == 1
    assert result.per_feature[0].count == 4


def test_clustering_merges_adjacent_features():
    """A tiled group of adjacent features is one upstream artefact."""
    issues = [_Issue("suspicious_near_miss_endpoints", i) for i in range(40)]
    boxes = {i: (0.0 + i * 1e-5, 0.0, 0.0 + i * 1e-5 + 1e-6, 1e-6)
             for i in range(40)}
    result = aggregate_issues(
        issues, source_features=40, bbox_by_feature=boxes,
        cluster_distance_deg=1e-4, cluster_min_features=10,
    )
    assert len(result.per_cluster) == 1
    cluster = result.per_cluster[0]
    assert cluster.count == 40
    assert cluster.total_findings == 40
    assert cluster.bbox is not None


def test_clustering_skips_small_groups():
    issues = [_Issue("line_dangle", i) for i in range(5)]
    boxes = {i: (float(i), 0.0, float(i) + 1e-9, 1e-9) for i in range(5)}
    result = aggregate_issues(
        issues, source_features=5, bbox_by_feature=boxes,
        cluster_distance_deg=1e-4, cluster_min_features=25,
    )
    assert result.per_cluster == []


def test_clustering_requires_bboxes():
    issues = [_Issue("line_dangle", i) for i in range(60)]
    result = aggregate_issues(issues, source_features=60)
    assert result.per_cluster == []


def test_empty_input_is_safe():
    result = aggregate_issues([], source_features=0)
    assert result.raw_findings == 0
    assert result.per_feature == []
    assert result.collapse_ratio == 0.0
    assert "0" in result.summary()


def test_to_dict_is_json_serialisable():
    import json
    issues = [_Issue("suspicious_near_miss_endpoints", 1, extra={"distance_m": 12.5})]
    result = aggregate_issues(issues, source_features=10)
    payload = json.dumps(result.to_dict())
    assert "raw_findings" in payload


def test_summary_states_raw_and_collapsed():
    issues = [_Issue("suspicious_near_miss_endpoints", 1) for _ in range(30)]
    result = aggregate_issues(issues, source_features=5)
    text = result.summary()
    assert "raw findings" in text
    assert "distinct features" in text
    assert "collapse ratio" in text