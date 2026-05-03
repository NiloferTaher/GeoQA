from __future__ import annotations

from functools import partial

from geoqa.profile_registry import GeoQAProfile, ValidationFamilyProfile

from .rules import build_land_use_context, land_use_problem_policies
from .thresholds import default_land_use_thresholds


def _families(variant: str) -> tuple[ValidationFamilyProfile, ...]:
    thresholds = default_land_use_thresholds()
    context_builder = partial(build_land_use_context, thresholds=thresholds)
    families: list[ValidationFamilyProfile] = [
        ValidationFamilyProfile(
            dataset_type="geometry",
            enabled_validators=("null_geometry", "self_intersection") if variant == "quick" else ("null_geometry", "duplicate_vertex", "self_intersection"),
        ),
        ValidationFamilyProfile(
            dataset_type="attributes",
            enabled_validators=("domain_range_checks",),
            context_builder=context_builder,
        ),
        ValidationFamilyProfile(
            dataset_type="topology",
            enabled_validators=("polygon_overlap_same_layer",) if variant == "quick" else ("polygon_overlap_same_layer", "feature_within_feature"),
        ),
        ValidationFamilyProfile(
            dataset_type="crs",
            enabled_validators=("missing_crs", "invalid_crs"),
        ),
    ]
    if variant == "audit":
        families.append(
            ValidationFamilyProfile(
                dataset_type="integrity",
                enabled_validators=("missing_spatial_index",),
            )
        )
    return tuple(families)


def _build_profile(name: str, variant: str, description: str) -> GeoQAProfile:
    return GeoQAProfile(
        name=name,
        description=description,
        families=_families(variant),
        problem_policies=land_use_problem_policies(),
        maturity="partial",
    )


def build_land_use_quick_profile() -> GeoQAProfile:
    return _build_profile(
        "land_use_quick",
        "quick",
        "Fast land-use QA for geometry, zoning-domain, and overlap checks on constrained hardware.",
    )


def build_land_use_strict_profile() -> GeoQAProfile:
    return _build_profile(
        "land_use_strict",
        "strict",
        "Balanced land-use QA for serious operational review.",
    )


def build_land_use_audit_profile() -> GeoQAProfile:
    return _build_profile(
        "land_use_audit",
        "audit",
        "Audit-grade land-use QA with broader structural signal.",
    )


def build_land_use_profile() -> GeoQAProfile:
    profile = build_land_use_strict_profile()
    return GeoQAProfile(
        name="land_use",
        description=profile.description,
        families=profile.families,
        problem_policies=profile.problem_policies,
        maturity=profile.maturity,
    )


__all__ = [
    "build_land_use_audit_profile",
    "build_land_use_profile",
    "build_land_use_quick_profile",
    "build_land_use_strict_profile",
]
