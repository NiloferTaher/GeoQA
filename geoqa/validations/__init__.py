"""GeoQA validation modules."""

from .accuracy import coordinate_precision, positional_accuracy, xy_tolerance
from .attributes import domain_range_checks, required_nulls, uniqueness
from .base import ValidationIssue
from .crs import invalid_crs, missing_crs
from .geometry import duplicate_vertex, null_geometry, self_intersection
from .integrity import missing_spatial_index, non_rfc7946_geojson, outdated_index
from .metadata import incomplete_metadata, missing_metadata_fields
from .topology import (
    boundary_mismatch_against_reference,
    feature_within_feature,
    line_intersection_same_layer,
    polygon_overlap_same_layer,
)

__all__ = [
    "ValidationIssue",
    "coordinate_precision",
    "boundary_mismatch_against_reference",
    "domain_range_checks",
    "duplicate_vertex",
    "incomplete_metadata",
    "invalid_crs",
    "line_intersection_same_layer",
    "missing_crs",
    "missing_metadata_fields",
    "missing_spatial_index",
    "null_geometry",
    "non_rfc7946_geojson",
    "outdated_index",
    "positional_accuracy",
    "polygon_overlap_same_layer",
    "required_nulls",
    "self_intersection",
    "feature_within_feature",
    "uniqueness",
    "xy_tolerance",
]
