"""Regression tests for stable feature identification across GeoQA results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoqa.execution import validate_dataset_with_profile


def _write_dataset(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"osm_id": 1001, "name": "A"},
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
            },
            {
                "type": "Feature",
                "properties": {"osm_id": 1002, "name": "B"},
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
            },
            {
                "type": "Feature",
                "properties": {"osm_id": 1003, "name": "C"},
                "geometry": {"type": "Point", "coordinates": [3.0, 4.0]},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_duplicate_issue_uses_source_id(tmp_path: Path) -> None:
    dataset = tmp_path / "dup.geojson"
    _write_dataset(dataset)
    result = validate_dataset_with_profile(
        dataset,
        profile="point_asset_quick",
        max_runtime_seconds=30,
        max_issues=50,
    )
    dup_issues = [i for i in result.issues if "duplicate" in i.problem_name.lower()]
    assert dup_issues, "Expected at least one duplicate geometry issue"
    feature_ids = {str(i.feature_id) for i in dup_issues}
    # feature_id must come from the source osm_id, not a positional index
    assert feature_ids.issubset({"1001", "1002"}), f"Unexpected feature_ids: {feature_ids}"


def test_issue_feature_id_is_stable_string(tmp_path: Path) -> None:
    dataset = tmp_path / "dup.geojson"
    _write_dataset(dataset)
    result = validate_dataset_with_profile(
        dataset,
        profile="point_asset_quick",
        max_runtime_seconds=30,
        max_issues=50,
    )
    feature_issues = [i for i in result.issues if i.feature_id is not None]
    assert feature_issues, "Expected at least one feature-level issue"
    for issue in feature_issues:
        assert str(issue.feature_id).isdigit()
