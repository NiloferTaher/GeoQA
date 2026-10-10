"""Geometry dimension (2D / 3D) evidence, from real operational behaviour.

Provenance of the rule
----------------------
This is not an invented test case. The author's own production PostGIS
ingestion pipeline carried an explicit dimensional policy:

    # Z checksum -> drop Z iff all zero
    has_z, all_zero = layer_z_summary(gdf)
    keep_3d = has_z and (not all_zero)
    if has_z and all_zero:
        gdf["geometry"] = gdf.geometry.apply(force_2d)
        print("   Z-check: ALL Z=0 -> writing 2D.")

and the PostGIS column type was then derived from the decision:

    def infer_pg_type_from_gdf(gdf, keep_3d):
        return base + ("Z" if keep_3d else "")

Why the condition is not simply "has_z = bad"
--------------------------------------------
A 3D geometry is not defective. The operational rule was conditional on a
*declared requirement*, so the engine separates the three facts:

    condition_detected   : geometry carries Z
    declared_requirement : target dimension, when configured
    conformance          : conforming / nonconforming / not_applicable

That distinction is the whole point. Without ``target_dimension`` this reports
the condition as informational, because a dataset may legitimately be 3D.

The one genuinely surprising part of the operational rule, and the reason this
module is worth having: **all-zero Z is treated as no Z.** A layer carrying
``Z = 0.0`` on every vertex is, for a 2D consumer, spatially 2D, but it will
still fail a naive dimensionality check and will push a 3D column type into
PostGIS for no benefit. That heuristic is preserved here because it came from a
system that had to interoperate with a real database.

Conditions emitted
------------------
``geometry_has_z``
    The geometry carries a Z ordinate on at least one vertex.
``geometry_z_all_zero``
    Every Z ordinate is zero within tolerance, so the geometry is
    dimensionally 2D despite declaring Z.
``geometry_dimension_mismatch``
    Present Z (real, not all-zero) while a 2D target was required.
    Nonconforming.
``geometry_z_inconsistent``
    Some features in the layer carry Z and others do not, which makes a single
    column type choice unsafe.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .base import ValidationIssue, build_issue

#: Z below this is treated as zero, matching the operational ``eps=0.0`` default
#: with a guard for float noise introduced by round-tripping.
ZERO_TOLERANCE = 1e-9


@dataclass
class DimensionProfile:
    """Dimensional character of a layer, independent of any requirement."""

    features: int = 0
    with_z: int = 0
    all_zero_z: int = 0
    mixed_z_values: int = 0
    no_z: int = 0
    z_min: float | None = None
    z_max: float | None = None
    geom_types: Counter = field(default_factory=Counter)
    per_feature: dict[Any, str] = field(default_factory=dict)

    @property
    def is_mixed(self) -> bool:
        """True when some features carry Z and others do not."""
        return self.with_z > 0 and self.no_z > 0

    @property
    def effective_3d_features(self) -> int:
        """Features carrying a Z that is not identically zero."""
        return self.with_z - self.all_zero_z

    @property
    def recommended_postgis_type(self) -> str:
        """What that pipeline would write, reproduced.

        ``keep_3d = has_z and (not all_zero)`` applied at layer level.
        """
        return "GEOMETRYZ" if self.effective_3d_features > 0 else "GEOMETRY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "with_z": self.with_z,
            "all_zero_z": self.all_zero_z,
            "effective_3d_features": self.effective_3d_features,
            "no_z": self.no_z,
            "mixed": self.is_mixed,
            "z_min": self.z_min,
            "z_max": self.z_max,
            "geom_types": dict(self.geom_types),
            "recommended_postgis_type": self.recommended_postgis_type,
        }


def _has_z(geometry: Any) -> bool:
    try:
        return bool(getattr(geometry, "has_z", False))
    except Exception:
        return False


def profile_dimension(layer: Any) -> DimensionProfile:
    """Measure the dimensional character of a layer.

    Mirrors that pipeline's ``layer_z_summary`` helper, but returns a full profile
    including per-feature classification, because a validator has to attribute
    a finding to a feature.
    """
    profile = DimensionProfile()
    zmin: float | None = None
    zmax: float | None = None

    try:
        from shapely import get_coordinates
    except Exception:  # pragma: no cover - shapely always present in practice
        get_coordinates = None

    for index, row in layer.iterrows():
        geometry = getattr(row, "geometry", None)
        profile.features += 1
        if geometry is None or geometry.is_empty:
            profile.per_feature[index] = "empty"
            continue
        profile.geom_types[getattr(geometry, "geom_type", "?")] += 1

        if not _has_z(geometry):
            profile.no_z += 1
            profile.per_feature[index] = "2d"
            continue

        profile.with_z += 1
        zs: list[float] = []
        if get_coordinates is not None:
            try:
                arr = get_coordinates(geometry, include_z=True)
                if arr.ndim == 2 and arr.shape[1] >= 3 and arr.size:
                    zs = [float(v) for v in arr[:, 2]]
            except Exception:
                zs = []
        if not zs:
            # fall back on WKT inspection rather than guessing
            try:
                zs = [float(p[2]) for p in geometry.coords] if geometry.geom_type == "LineString" else []
            except Exception:
                zs = []

        if not zs:
            profile.mixed_z_values += 1
            profile.per_feature[index] = "z_unknown"
            continue

        lo, hi = min(zs), max(zs)
        zmin = lo if zmin is None else min(zmin, lo)
        zmax = hi if zmax is None else max(zmax, hi)

        if abs(lo) <= ZERO_TOLERANCE and abs(hi) <= ZERO_TOLERANCE:
            profile.all_zero_z += 1
            profile.per_feature[index] = "z_all_zero"
        else:
            profile.per_feature[index] = "3d"

    profile.z_min = zmin
    profile.z_max = zmax
    return profile


def validate_geometry_dimension(
    layer: Any,
    *,
    target_dimension: int | None = None,
    flag_all_zero_z: bool = True,
    flag_mixed: bool = True,
) -> list[ValidationIssue]:
    """Report geometry-dimension evidence.

    Parameters
    ----------
    target_dimension
        2 or 3. When given, a real Z against a 2D requirement becomes
        ``geometry_dimension_mismatch`` at medium severity, which is the
        condition the pipeline acted on. When ``None`` the condition is
        reported informationally, because 3D data is not defective per se.
    flag_all_zero_z
        Report Z-carrying geometries whose Z is identically zero. These are
        dimensionally 2D but will force a 3D column type downstream.
    flag_mixed
        Report a layer where some features carry Z and others do not, which
        makes a single column type unsafe.
    """
    profile = profile_dimension(layer)
    issues: list[ValidationIssue] = []

    if profile.features == 0:
        return issues

    if flag_mixed and profile.is_mixed:
        issues.append(build_issue(
            "geometry_z_inconsistent",
            severity="medium",
            description=(
                f"Layer mixes dimensional representations: {profile.with_z:,} features "
                f"carry Z and {profile.no_z:,} do not. A single geometry column type "
                "cannot represent both safely."
            ),
            solution_hint=(
                "Split the layer, or normalise every feature to the intended "
                "dimension before loading. the production PostGIS loader chose "
                f"'{profile.recommended_postgis_type}' for this layer."
            ),
            extra=profile.to_dict(),
        ))

    for index, state in profile.per_feature.items():
        row = layer.loc[index] if index in layer.index else None
        if row is None:
            continue

        if state == "z_all_zero":
            if flag_all_zero_z:
                issues.append(build_issue(
                    "geometry_z_all_zero",
                    row=row,
                    index=index,
                    severity="low",
                    description=(
                        "Geometry declares Z but every ordinate is zero, so it is "
                        "dimensionally 2D while advertising 3D."
                    ),
                    solution_hint=(
                        "Drop the Z ordinate before ingestion, or the target will "
                        "require a 3D column for data that carries no elevation "
                        "information."
                    ),
                    extra={"state": state},
                ))
            if target_dimension == 3:
                issues.append(build_issue(
                    "geometry_dimension_mismatch",
                    row=row,
                    index=index,
                    severity="medium",
                    description=(
                        "A 3D target was required but this feature carries no "
                        "non-zero Z."
                    ),
                    solution_hint="Supply elevation, or relax the declared target dimension.",
                    extra={"state": state, "target_dimension": target_dimension},
                ))
            continue

        if state == "3d":
            if target_dimension == 2:
                issues.append(build_issue(
                    "geometry_dimension_mismatch",
                    row=row,
                    index=index,
                    severity="medium",
                    description=(
                        f"Geometry carries Z (layer range "
                        f"{profile.z_min}..{profile.z_max}) while a 2D target was "
                        "declared for this target."
                    ),
                    solution_hint=(
                        "Transform to 2D before ingestion, or declare a 3D target. "
                        "This is a conformance condition, not a defect."
                    ),
                    extra={
                        "state": state,
                        "target_dimension": target_dimension,
                        "z_min": profile.z_min,
                        "z_max": profile.z_max,
                    },
                ))
            continue

        # state == "2d" and no target requirement: nothing to report
    return issues


#: Register alongside the other validators so profiles can name it.
PROBLEM_NAME = "geometry_dimension"