from __future__ import annotations

from functools import partial

from geoqa.profile_registry import GeoQAProfile, ValidationFamilyProfile

from .rules import build_water_network_context, water_network_problem_policies
from .thresholds import default_water_network_thresholds


def _families(variant: str) -> tuple[ValidationFamilyProfile, ...]:
    thresholds = default_water_network_thresholds()
    context_builder = partial(build_water_network_context, thresholds=thresholds)
    families: list[ValidationFamilyProfile] = [
        ValidationFamilyProfile(
            dataset_type="geometry",
            enabled_validators=(
                "null_geometry",
                "duplicate_vertex",
                "self_intersection",
                "below_minimum_feature_length",
                "sharp_angle_cutback",
            ),
            context_builder=context_builder,
        ),
        ValidationFamilyProfile(
            dataset_type="topology",
            enabled_validators=(
                "line_dangle",
                "line_intersection_same_layer",
                "duplicate_geometry_same_layer",
                "feature_not_split_at_intersection",
                "isolated_network_segment",
                "suspicious_near_miss_endpoints",
                "unsnapped_endpoints_within_tolerance",
            ),
            context_builder=context_builder,
        ),
        ValidationFamilyProfile(
            dataset_type="attributes",
            enabled_validators=(
                "required_nulls",
                "uniqueness",
                "diameter_domain",
                "material_domain",
                "status_domain",
            ),
            context_builder=context_builder,
        ),
        ValidationFamilyProfile(
            dataset_type="crs",
            enabled_validators=("missing_crs", "invalid_crs"),
        ),
    ]
    if variant in {"quick", "strict", "audit"}:
        families.append(
            ValidationFamilyProfile(
                dataset_type="accuracy",
                enabled_validators=("coordinate_precision", "xy_tolerance"),
                validator_options={
                    "coordinate_precision": {"max_decimal_places": 10 if variant == "quick" else 12},
                    "xy_tolerance": {"max_tolerance": 0.1 if variant == "quick" else 0.05},
                },
            )
        )
    return tuple(families)


def _build_profile(name: str, variant: str, description: str) -> GeoQAProfile:
    return GeoQAProfile(
        name=name,
        description=description,
        families=_families(variant),
        problem_policies=water_network_problem_policies(variant),
        maturity="partial",
    )


def build_water_network_quick_profile() -> GeoQAProfile:
    return _build_profile(
        "water_network_quick",
        "quick",
        "Fast water-network QA with connectivity, schema-aware attributes, and suppressed precision noise.",
    )


def build_water_network_strict_profile() -> GeoQAProfile:
    return _build_profile(
        "water_network_strict",
        "strict",
        "Balanced water-network QA with geometry, topology, attribute, CRS, and calibrated accuracy checks.",
    )


def build_water_network_audit_profile() -> GeoQAProfile:
    return _build_profile(
        "water_network_audit",
        "audit",
        "Audit-grade water-network QA with stricter issue surfacing and full topology scrutiny.",
    )


def build_water_network_profile() -> GeoQAProfile:
    profile = build_water_network_strict_profile()
    return GeoQAProfile(
        name="water_network",
        description=profile.description,
        families=profile.families,
        problem_policies=profile.problem_policies,
        maturity=profile.maturity,
    )


__all__ = [
    "build_water_network_audit_profile",
    "build_water_network_profile",
    "build_water_network_quick_profile",
    "build_water_network_strict_profile",
]
