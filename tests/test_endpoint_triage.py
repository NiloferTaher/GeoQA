"""Tests for endpoint triage.

The behaviour under test is the one that matters in practice: when a network
uses separated line/node topology, an endpoint that terminates at a node in a
companion layer must NOT be reported as an orphan. Without the companion layer
the same data must report it as unresolved, and the report must say so.

Fixtures are deliberately simple so each expected count is obvious by
inspection. Everything is in EPSG:4326 around 10E/45N so that metre tolerances
exercise the geographic-CRS conversion path.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from geoqa.validations.endpoint_triage import (
    CAUSE_NEAR_MISS,
    CAUSE_ORPHAN,
    CAUSE_RESOLVED_BY_NODE,
    CAUSE_ROLE_TERMINAL,
    triage_endpoints,
)

ORIGIN = (10.0, 45.0)


def _lines(features, crs="EPSG:4326"):
    return gpd.GeoDataFrame(
        {"id": list(range(len(features)))}, geometry=features, crs=crs
    )


def _nodes(points, crs="EPSG:4326"):
    return gpd.GeoDataFrame(
        {"node_id": list(range(len(points)))}, geometry=points, crs=crs
    )


def _m(deg):
    """Degrees to metres at 45N."""
    return deg * 111_320.0 * 0.70710678


# --------------------------------------------------------------------------


def test_closed_ring_reports_nothing():
    """A closed ring shares every endpoint internally: no findings at all.

    Note an open two-segment chain is NOT the right fixture here - a chain has
    two free ends, and a free end with no companion node IS an orphan. That is
    correct behaviour, asserted separately in
    test_single_segment_both_ends_orphan.
    """
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    b = LineString([(10.001, 45.0), (10.001, 45.001)])
    c = LineString([(10.001, 45.001), (10.0, 45.001)])
    d = LineString([(10.0, 45.001), (10.0, 45.0)])
    t = triage_endpoints(_lines([a, b, c, d]))
    assert t.total == 0, t.summary()


def test_single_segment_both_ends_orphan():
    """One segment in isolation: both endpoints are orphans."""
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    t = triage_endpoints(_lines([a]))
    assert t.by_cause() == {CAUSE_ORPHAN: 2}, t.summary()


def test_companion_node_resolves_endpoint():
    """The separated-topology case: a node layer supplies the connection.

    Without the companion layer both ends are orphans. With it, the end that
    lands on a node is explained, leaving only the genuinely free end.
    """
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    lines = _lines([a])

    before = triage_endpoints(lines)
    assert before.by_cause() == {CAUSE_ORPHAN: 2}

    nodes = _nodes([Point(10.001, 45.0)])
    after = triage_endpoints(lines, companion_layer=nodes, snap_tolerance=1.0)
    assert after.by_cause() == {CAUSE_RESOLVED_BY_NODE: 1, CAUSE_ORPHAN: 1}, \
        after.summary()

    resolved = after.of(CAUSE_RESOLVED_BY_NODE)[0]
    assert resolved.companion_id == 0


def test_companion_node_outside_tolerance_does_not_resolve():
    """Tolerance must be respected, not just proximity."""
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    nodes = _nodes([Point(10.0011, 45.0)])  # ~11 m away
    t = triage_endpoints(_lines([a]), companion_layer=nodes, snap_tolerance=1.0)
    assert t.by_cause() == {CAUSE_ORPHAN: 2}, t.summary()


def test_role_terminal_is_reported_separately_not_dropped():
    """A declared terminal must be counted, and never counted as an orphan."""
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    gdf = gpd.GeoDataFrame(
        {"id": [0], "asset_type": ["outfall"]}, geometry=[a], crs="EPSG:4326"
    )
    t = triage_endpoints(
        gdf, role_field="asset_type", allowed_endpoint_values={"outfall"}
    )
    counts = t.by_cause()
    assert counts.get(CAUSE_ROLE_TERMINAL) == 2, t.summary()
    assert CAUSE_ORPHAN not in counts


def test_near_miss_detected_at_small_gap():
    """Two endpoints close but not shared: the classic unconnected-way defect.

    The two chain ends far from the gap are genuinely orphans and must still be
    reported. What this test pins down is that the two endpoints flanking the
    gap are classified near-miss rather than orphan.
    """
    gap = 1.0 / 111_320.0  # ~1 m in degrees at the equator
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    b = LineString([(10.001 + gap, 45.0), (10.002, 45.0)])
    t = triage_endpoints(_lines([a, b]), snap_tolerance=5.0)
    counts = t.by_cause()
    assert counts.get(CAUSE_NEAR_MISS) == 2, t.summary()
    # the remote ends of the same chain are orphans, by design
    assert counts.get(CAUSE_ORPHAN) == 2, t.summary()


def test_far_apart_segments_are_orphans_not_near_miss():
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    b = LineString([(10.05, 45.0), (10.051, 45.0)])
    t = triage_endpoints(_lines([a, b]), snap_tolerance=1.0)
    assert t.by_cause() == {CAUSE_ORPHAN: 4}, t.summary()


def test_orphan_clusters_detect_one_upstream_cause():
    """Many orphans in one place is an extraction artefact, not N defects."""
    feats = []
    # 12 short segments scattered along one line, each an orphan, tightly
    # clustered - mimics a clipped or badly-noded extraction.
    for i in range(12):
        y = 45.0 + i * 1e-5
        feats.append(LineString([(10.0, y), (10.0005, y)]))
    t = triage_endpoints(
        _lines(feats), snap_tolerance=1.0, cluster_radius=50.0
    )
    assert t.by_cause().get(CAUSE_ORPHAN) == 24, t.summary()
    assert len(t.orphan_clusters) == 1
    assert t.orphan_clusters[0].count == 24
    # and the report must say so
    assert any("upstream cause" in w for w in t.warnings), t.warnings


def test_missing_companion_layer_is_warned_about():
    """Silent absence of the companion layer is the main false-positive trap."""
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    t = triage_endpoints(_lines([a]))
    assert any("companion" in w.lower() for w in t.warnings), t.warnings


def test_percentages_sum_to_100():
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    b = LineString([(10.05, 45.0), (10.051, 45.0)])
    t = triage_endpoints(_lines([a, b]), snap_tolerance=1.0)
    pct = t.percentages()
    assert len(pct) > 0
    assert abs(sum(pct.values()) - 100.0) < 0.05, pct


def test_to_issues_excludes_explained_endpoints():
    """Only unresolved causes reach the report."""
    a = LineString([(10.0, 45.0), (10.001, 45.0)])
    gdf = gpd.GeoDataFrame(
        {"id": [0], "asset_type": ["outfall"]}, geometry=[a], crs="EPSG:4326"
    )
    t = triage_endpoints(
        gdf, role_field="asset_type", allowed_endpoint_values={"outfall"}
    )
    assert t.to_issues() == []


def test_projected_crs_tolerances_are_crs_units():
    """In a projected layer the tolerance is in CRS units, not degrees."""
    line = LineString([(500000.0, 4500000.0), (500010.0, 4500000.0)])
    gdf = gpd.GeoDataFrame({"id": [0]}, geometry=[line], crs="EPSG:32632")
    nodes = gpd.GeoDataFrame(
        {"node_id": [7]}, geometry=[Point(500010.0, 4500000.0)], crs="EPSG:32632"
    )
    t = triage_endpoints(gdf, companion_layer=nodes, snap_tolerance=5.0)
    assert t.by_cause() == {CAUSE_RESOLVED_BY_NODE: 1, CAUSE_ORPHAN: 1}, t.summary()


def test_multipart_lines_are_handled():
    """MultiLineString inputs must not crash the triage."""
    multi = LineString([(10.0, 45.0), (10.001, 45.0)])
    from shapely.geometry import MultiLineString

    gdf = gpd.GeoDataFrame(
        {"id": [0]}, geometry=[MultiLineString([multi])], crs="EPSG:4326"
    )
    t = triage_endpoints(gdf)
    assert t.total == 2, t.summary()