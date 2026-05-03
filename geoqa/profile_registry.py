from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from geoqa.validation_runtime import ValidationProfile

LayerContextBuilder = Callable[[Any], dict[str, Any]]


@dataclass(slots=True, frozen=True)
class ValidationFamilyProfile:
    dataset_type: str
    enabled_validators: tuple[str, ...]
    disabled_validators: tuple[str, ...] = ()
    validator_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    context_builder: LayerContextBuilder | None = None

    def to_validation_profile(self, *, name: str) -> ValidationProfile:
        return ValidationProfile(
            name=name,
            dataset_type=self.dataset_type,
            enabled_validators=self.enabled_validators,
            disabled_validators=self.disabled_validators,
            validator_options=self.validator_options,
        )


@dataclass(slots=True, frozen=True)
class GeoQAProfile:
    name: str
    description: str
    families: tuple[ValidationFamilyProfile, ...]
    severity_overrides: dict[str, str] = field(default_factory=dict)
    downgrade_rules: dict[str, str] = field(default_factory=dict)
    suppression_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    suppressed_problems: tuple[str, ...] = ()
    problem_policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    maturity: str = "partial"


def _existing_fields(layer: Any, candidates: tuple[str, ...]) -> list[str]:
    columns = {str(column) for column in getattr(layer, "columns", [])}
    return [candidate for candidate in candidates if candidate in columns]


from geoqa.packs import (
    build_boundaries_audit_profile,
    build_boundaries_profile,
    build_boundaries_quick_profile,
    build_boundaries_strict_profile,
    build_land_use_audit_profile,
    build_land_use_profile,
    build_land_use_quick_profile,
    build_land_use_strict_profile,
    build_water_network_audit_profile,
    build_water_network_profile,
    build_water_network_quick_profile,
    build_water_network_strict_profile,
)

_BUILTIN_PROFILES: dict[str, GeoQAProfile] = {
    "geometry": GeoQAProfile(
        name="geometry",
        description="Focused geometry-only validation for fast structural QA.",
        families=(
            ValidationFamilyProfile(
                dataset_type="geometry",
                enabled_validators=("null_geometry", "duplicate_vertex", "self_intersection"),
            ),
        ),
        maturity="stable",
    ),
    "generic_quick": GeoQAProfile(
        name="generic_quick",
        description="Fast generic QA pass for common geometry, CRS, and integrity checks.",
        families=(
            ValidationFamilyProfile(
                dataset_type="geometry",
                enabled_validators=("null_geometry", "duplicate_vertex", "self_intersection"),
            ),
            ValidationFamilyProfile(
                dataset_type="crs",
                enabled_validators=("missing_crs", "invalid_crs"),
            ),
            ValidationFamilyProfile(
                dataset_type="integrity",
                enabled_validators=("missing_spatial_index", "outdated_index"),
            ),
        ),
        maturity="stable",
    ),
    "generic_strict": GeoQAProfile(
        name="generic_strict",
        description="Broader generic QA pass including accuracy and topology checks.",
        families=(
            ValidationFamilyProfile(
                dataset_type="geometry",
                enabled_validators=("null_geometry", "duplicate_vertex", "self_intersection"),
            ),
            ValidationFamilyProfile(
                dataset_type="crs",
                enabled_validators=("missing_crs", "invalid_crs"),
            ),
            ValidationFamilyProfile(
                dataset_type="accuracy",
                enabled_validators=("coordinate_precision", "xy_tolerance"),
                validator_options={
                    "coordinate_precision": {"max_decimal_places": 12},
                    "xy_tolerance": {"max_tolerance": 0.05},
                },
            ),
            ValidationFamilyProfile(
                dataset_type="integrity",
                enabled_validators=("missing_spatial_index", "outdated_index"),
            ),
            ValidationFamilyProfile(
                dataset_type="topology",
                enabled_validators=("polygon_overlap_same_layer", "feature_within_feature", "line_intersection_same_layer"),
            ),
        ),
        problem_policies={
            "coordinate_precision_not_fit_for_use": {
                "severity": "low",
                "confidence": "low",
                "actionable": False,
                "suppression_reason": "Precision warning downgraded for generic strict audit output.",
            },
            "inappropriate_xy_tolerance": {
                "severity": "low",
                "confidence": "low",
                "actionable": False,
            },
            "missing_or_stale_spatial_index": {
                "severity": "medium",
                "confidence": "medium",
                "actionable": True,
            },
        },
        maturity="partial",
    ),
    "generic_audit": GeoQAProfile(
        name="generic_audit",
        description="Fuller generic QA intended for slower review-oriented runs with more informational signal.",
        families=(
            ValidationFamilyProfile(
                dataset_type="geometry",
                enabled_validators=("null_geometry", "duplicate_vertex", "below_minimum_feature_length", "sharp_angle_cutback", "self_intersection"),
            ),
            ValidationFamilyProfile(
                dataset_type="crs",
                enabled_validators=("missing_crs", "invalid_crs"),
            ),
            ValidationFamilyProfile(
                dataset_type="accuracy",
                enabled_validators=("coordinate_precision", "xy_tolerance", "positional_accuracy"),
                validator_options={
                    "coordinate_precision": {"max_decimal_places": 12},
                    "xy_tolerance": {"max_tolerance": 0.05},
                },
            ),
            ValidationFamilyProfile(
                dataset_type="integrity",
                enabled_validators=("missing_spatial_index", "outdated_index"),
            ),
            ValidationFamilyProfile(
                dataset_type="topology",
                enabled_validators=("polygon_overlap_same_layer", "polygon_gap_same_layer", "feature_within_feature", "line_intersection_same_layer"),
            ),
        ),
        problem_policies={
            "coordinate_precision_not_fit_for_use": {
                "severity": "medium",
                "confidence": "low",
                "actionable": False,
                "priority_score": 3,
            },
            "inappropriate_xy_tolerance": {
                "severity": "medium",
                "confidence": "low",
                "actionable": False,
                "priority_score": 3,
            },
        },
        maturity="partial",
    ),
    "water_network": build_water_network_profile(),
    "water_network_quick": build_water_network_quick_profile(),
    "water_network_strict": build_water_network_strict_profile(),
    "water_network_audit": build_water_network_audit_profile(),
    "boundaries_quick": build_boundaries_quick_profile(),
    "boundaries": build_boundaries_profile(),
    "boundaries_strict": build_boundaries_strict_profile(),
    "boundaries_audit": build_boundaries_audit_profile(),
    "land_use_quick": build_land_use_quick_profile(),
    "land_use": build_land_use_profile(),
    "land_use_strict": build_land_use_strict_profile(),
    "land_use_audit": build_land_use_audit_profile(),
}

_CUSTOM_PROFILES: dict[str, GeoQAProfile] = {}


def list_geoqa_profiles() -> list[GeoQAProfile]:
    combined = {**_BUILTIN_PROFILES, **_CUSTOM_PROFILES}
    return [combined[name] for name in sorted(combined)]


def get_geoqa_profile(name: str) -> GeoQAProfile | None:
    normalized = name.strip().lower()
    return _CUSTOM_PROFILES.get(normalized) or _BUILTIN_PROFILES.get(normalized)


def register_geoqa_profile(profile: GeoQAProfile) -> None:
    _CUSTOM_PROFILES[profile.name.strip().lower()] = profile


def clear_geoqa_profiles() -> None:
    _CUSTOM_PROFILES.clear()


__all__ = [
    "GeoQAProfile",
    "ValidationFamilyProfile",
    "clear_geoqa_profiles",
    "get_geoqa_profile",
    "list_geoqa_profiles",
    "register_geoqa_profile",
]
