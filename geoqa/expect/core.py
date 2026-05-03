from __future__ import annotations

from pathlib import Path
from typing import Any

from geoqa.conversion import load_vector_dataset
from geoqa.interactive_validation import validate_layer
from geoqa.validation_runtime import ValidationProfile
from geoqa.validations.base import ValidationIssue


class ExpectationResult(list):
    """Small list-like wrapper for expectation results."""

    def count(self) -> int:  # type: ignore[override]
        return len(self)


def _load_layer(dataset_path: str | Path) -> Any:
    return load_vector_dataset(dataset_path)


def _run_expectation(
    dataset_path: str | Path,
    *,
    dataset_type: str,
    enabled_validators: tuple[str, ...],
    **context: Any,
) -> list[ValidationIssue]:
    layer = _load_layer(dataset_path)
    issues = validate_layer(
        layer,
        dataset_type,
        profile=ValidationProfile(
            name=f"expect:{dataset_type}",
            dataset_type=dataset_type,
            enabled_validators=enabled_validators,
        ),
        **context,
    )
    return ExpectationResult(issues)


def valid_crs(dataset_path: str | Path, *, expected_crs: Any = "EPSG:4326") -> list[ValidationIssue]:
    """Return CRS-related issues for a dataset."""
    return _run_expectation(
        dataset_path,
        dataset_type="crs",
        enabled_validators=("missing_crs", "invalid_crs"),
        expected_crs=expected_crs,
    )


def no_null_geometry(dataset_path: str | Path) -> list[ValidationIssue]:
    """Return null-geometry issues for a dataset."""
    return _run_expectation(
        dataset_path,
        dataset_type="geometry",
        enabled_validators=("null_geometry",),
    )


def no_self_intersections(dataset_path: str | Path) -> list[ValidationIssue]:
    """Return self-intersection issues for a dataset."""
    return _run_expectation(
        dataset_path,
        dataset_type="geometry",
        enabled_validators=("self_intersection",),
    )


class _GeometryExpectNamespace:
    """Expectation helpers for geometry-focused checks."""

    def valid(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return _run_expectation(
            dataset_path,
            dataset_type="geometry",
            enabled_validators=("null_geometry", "duplicate_vertex", "self_intersection"),
        )

    def clean(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return self.valid(dataset_path)

    def no_nulls(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return no_null_geometry(dataset_path)

    def no_self_intersections(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return no_self_intersections(dataset_path)


class _TopologyExpectNamespace:
    """Expectation helpers for same-layer topology cleanliness."""

    def clean(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return _run_expectation(
            dataset_path,
            dataset_type="topology",
            enabled_validators=(
                "polygon_overlap_same_layer",
                "feature_within_feature",
                "line_intersection_same_layer",
            ),
        )

    def connected(self, dataset_path: str | Path) -> list[ValidationIssue]:
        return _run_expectation(
            dataset_path,
            dataset_type="topology",
            enabled_validators=(
                "line_dangle",
                "isolated_network_segment",
                "suspicious_near_miss_endpoints",
                "unsnapped_endpoints_within_tolerance",
            ),
        )


class _AttributesExpectNamespace:
    """Expectation helpers for attribute completeness and uniqueness."""

    def complete(self, dataset_path: str | Path, *, required_fields: list[str]) -> list[ValidationIssue]:
        return _run_expectation(
            dataset_path,
            dataset_type="attributes",
            enabled_validators=("required_nulls",),
            required_fields=required_fields,
        )

    def unique(self, dataset_path: str | Path, *, field: str) -> list[ValidationIssue]:
        return _run_expectation(
            dataset_path,
            dataset_type="attributes",
            enabled_validators=("uniqueness",),
            unique_field=field,
        )


class _CrsExpectNamespace:
    """Expectation helpers for CRS validity."""

    def valid(self, dataset_path: str | Path, *, expected_crs: Any = "EPSG:4326") -> list[ValidationIssue]:
        return valid_crs(dataset_path, expected_crs=expected_crs)


class GeoQACheck:
    """Fluent expectation helper for lightweight GeoQA assertions."""

    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = dataset_path

    def crs(self, *, expected_crs: Any = "EPSG:4326") -> list[ValidationIssue]:
        return valid_crs(self.dataset_path, expected_crs=expected_crs)

    def null_geometry(self) -> list[ValidationIssue]:
        return no_null_geometry(self.dataset_path)

    def self_intersections(self) -> list[ValidationIssue]:
        return no_self_intersections(self.dataset_path)

    def geometry(self) -> list[ValidationIssue]:
        return geometry.valid(self.dataset_path)

    def topology(self) -> list[ValidationIssue]:
        return topology.clean(self.dataset_path)


def check(dataset_path: str | Path) -> GeoQACheck:
    """Return a fluent checker for a dataset."""
    return GeoQACheck(dataset_path)


geometry = _GeometryExpectNamespace()
topology = _TopologyExpectNamespace()
attributes = _AttributesExpectNamespace()
crs = _CrsExpectNamespace()


__all__ = [
    "GeoQACheck",
    "attributes",
    "check",
    "crs",
    "geometry",
    "no_null_geometry",
    "no_self_intersections",
    "topology",
    "valid_crs",
]
