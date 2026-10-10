from __future__ import annotations

from functools import partial

from geoqa.profile_registry import GeoQAProfile, ValidationFamilyProfile

from .rules import boundaries_problem_policies, build_boundaries_context
from .thresholds import default_boundary_thresholds


def _families(variant: str) -> tuple[ValidationFamilyProfile, ...]:
    thresholds = default_boundary_thresholds()
    context_builder = partial(build_boundaries_context, thresholds=thresholds)
    families: list[ValidationFamilyProfile] = [
        ValidationFamilyProfile(
            dataset_type="geometry",
            enabled_validators=("null_geometry", "self_intersection") if variant == "quick" else ("null_geometry", "duplicate_vertex", "self_intersection"),
        ),
        ValidationFamilyProfile(
            dataset_type="topology",
            enabled_validators=(
                "polygon_overlap_same_layer",
                "polygon_gap_same_layer",
                "boundary_mismatch_against_reference",
            )
            if variant == "quick"
            else (
                "polygon_overlap_same_layer",
                "polygon_gap_same_layer",
                "feature_within_feature",
                "boundary_mismatch_against_reference",
            ),
            context_builder=context_builder,
        ),
        ValidationFamilyProfile(
            dataset_type="crs",
            enabled_validators=("missing_crs", "invalid_crs"),
        ),
    ]
    if variant in {"strict", "audit"}:
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
        problem_policies=boundaries_problem_policies(),
        maturity="partial",
    )


def build_boundaries_quick_profile() -> GeoQAProfile:
    return _build_profile(
        "boundaries_quick",
        "quick",
        "Fast boundary QA for overlap, gap, and reference mismatch checks with reduced noise.",
    )


def build_boundaries_strict_profile() -> GeoQAProfile:
    return _build_profile(
        "boundaries_strict",
        "strict",
        "Balanced boundary QA for serious operational review.",
    )


def build_boundaries_audit_profile() -> GeoQAProfile:
    return _build_profile(
        "boundaries_audit",
        "audit",
        "Audit-grade boundary QA with fuller structural and integrity signal.",
    )


def build_boundaries_profile() -> GeoQAProfile:
    profile = build_boundaries_strict_profile()
    return GeoQAProfile(
        name="boundaries",
        description=profile.description,
        families=profile.families,
        problem_policies=profile.problem_policies,
        maturity=profile.maturity,
    )


__all__ = [
    "build_boundaries_audit_profile",
    "build_boundaries_profile",
    "build_boundaries_quick_profile",
    "build_boundaries_strict_profile",
]
