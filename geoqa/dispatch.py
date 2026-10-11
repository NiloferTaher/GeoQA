"""Decide which checks apply to a layer, and say so.

The pieces needed for this already existed separately. There was a runtime
that dispatched by dataset type, domain packs that adjusted the severity of
conditions once they had been selected, cost estimation that knew how big a
layer was, and a chunker that refused to run without a halo. What was
missing was the join: nothing looked at a layer and decided, out loud, which
of those applied to it.

So a caller had to choose a pack, choose whether to chunk, and choose the
thresholds, before running anything. Every one of those choices is defensible
and none of them was recorded.

This module makes the choices and returns them as a value. Three rules hold
it to the library's existing commitments.

**It reports rather than decides silently.** If a polygon check is skipped
because the data is points, the plan says which check and why. A check that
did not run and a check that found nothing must not look the same in a
report, because only one of them is good news.

**Thresholds are arguments.** A vertex count at which chunking switches on is
the same mistake as a hardcoded tiny-area constant: it is a claim about one
dataset's size that gets applied to another. The default is therefore to
report the measurement and decline to chunk, and to chunk only when asked.

**A family mismatch is evidence, not an error.** A polygon layer with three
stray linestrings should say so and then run the polygon checks against the
polygons. Refusing to run would be defensible and useless.

The plan is a plain object so it can be logged, diffed against a baseline,
and asserted on in a test without executing a single validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from geoqa.chunking import ALWAYS_WHOLE_LAYER, CHUNK_LOCAL_VALIDATORS, plan_tiles
from geoqa.validations.base import ValidationIssue, build_issue
from geoqa.validations.datatypes import GEOMETRY_FAMILY

__all__ = [
    "LAYER_PROFILE",
    "CONDITION_FAMILIES",
    "ValidationPlan",
    "inspect_layer",
    "build_plan",
]


#: Which geometry families each condition can say anything useful about.
#: A condition that is absent from this mapping is not family-gated, which
#: is the correct default: a metadata or governance condition applies to a
#: layer whatever it contains.
#:
#: Every key here must be a registered condition name. A key that names
#: something unregistered silently gates nothing, which looks identical to
#: working and is worse, so tests/test_shape_and_dispatch.py asserts the two
#: sets agree.
CONDITION_FAMILIES: dict[str, str] = {
    # polygon-only
    "polygon_overlap_same_layer": "polygon",
    "polygon_overlap_other_layer": "polygon",
    "small_polygon_overlap": "polygon",
    "small_polygon_gap": "polygon",
    "polygon_gap_same_layer": "polygon",
    "feature_within_feature": "polygon",
    "polygon_boundary_mismatch": "polygon",
    "polygon_boundary_not_covered_by_lines": "polygon",
    "below_minimum_feature_area": "polygon",
    "geometry_thin_sliver": "polygon",
    "geometry_elongated": "polygon",
    # line-only
    "line_dangle": "line",
    "epanet_dangling_endpoint": "line",
    "line_intersection_same_layer": "line",
    "continuity_break": "line",
    "isolated_network_segment": "line",
    "below_minimum_feature_length": "line",
    "sharp_angle_cutback": "line",
    "unsnapped_endpoints_within_tolerance": "line",
    "unsnapped_vertices_within_tolerance": "line",
    # Any: the condition needs more than one layer, and the layers supply the
    # families themselves.
    "clip_straddles_boundary": "any",
}


@dataclass
class LAYER_PROFILE:
    """What a layer is, measured rather than declared."""

    family: str = "unknown"
    family_counts: dict[str, int] = field(default_factory=dict)
    dominant_geom_type: str | None = None
    row_count: int = 0
    vertex_count: int = 0
    crs: str | None = None
    has_geometry: bool = False

    @property
    def is_mixed_family(self) -> bool:
        real = {k for k in self.family_counts if k != "unknown"}
        return len(real) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "family_counts": dict(self.family_counts),
            "dominant_geom_type": self.dominant_geom_type,
            "row_count": self.row_count,
            "vertex_count": self.vertex_count,
            "crs": self.crs,
            "has_geometry": self.has_geometry,
            "is_mixed_family": self.is_mixed_family,
        }


def _vertex_count(geometry: Any) -> int:
    if geometry is None:
        return 0
    try:
        if geometry.is_empty:
            return 0
    except Exception:
        pass
    try:
        return max(1, len(geometry.coords))
    except Exception:
        pass
    parts = getattr(geometry, "geoms", None)
    if parts is not None:
        try:
            return sum(_vertex_count(part) for part in parts)
        except Exception:
            return 0
    # A polygon has no .coords and no .geoms; its vertices live on the
    # exterior ring and any interior rings, and counting zero here would make
    # every polygon layer look free.
    try:
        total = len(geometry.exterior.coords)
        for interior in geometry.interiors:
            total += len(interior.coords)
        return max(total, 4)
    except Exception:
        return 0


def inspect_layer(layer: Any) -> LAYER_PROFILE:
    """Measure a layer: family, size, CRS. No judgement, no thresholds."""
    profile = LAYER_PROFILE()
    try:
        profile.crs = str(layer.crs) if getattr(layer, "crs", None) is not None else None
    except Exception:
        profile.crs = None

    try:
        rows = list(layer.iterrows())
    except Exception:
        return profile

    profile.row_count = len(rows)
    type_counts: dict[str, int] = {}

    for _, row in rows:
        geometry = row.get("geometry") if hasattr(row, "get") else None
        if geometry is None:
            continue
        profile.has_geometry = True
        geom_type = str(getattr(geometry, "geom_type", "") or "Unknown")
        type_counts[geom_type] = type_counts.get(geom_type, 0) + 1
        family = GEOMETRY_FAMILY.get(geom_type, "unknown")
        profile.family_counts[family] = profile.family_counts.get(family, 0) + 1
        profile.vertex_count += _vertex_count(geometry)

    if type_counts:
        profile.dominant_geom_type = max(type_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]

    real = {k: v for k, v in profile.family_counts.items() if k != "unknown" and v}
    if real:
        profile.family = max(real.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return profile


@dataclass
class ValidationPlan:
    """What will run, what will not, and why."""

    profile: LAYER_PROFILE
    applicable_conditions: list[str] = field(default_factory=list)
    skipped_conditions: dict[str, str] = field(default_factory=dict)
    packs: list[str] = field(default_factory=list)
    chunk: bool = False
    chunk_reason: str = ""
    chunk_plan: Any | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return self.profile.vertex_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "applicable_conditions": sorted(self.applicable_conditions),
            "skipped_conditions": dict(sorted(self.skipped_conditions.items())),
            "packs": sorted(self.packs),
            "chunk": self.chunk,
            "chunk_reason": self.chunk_reason,
            "chunk_plan": self.chunk_plan.to_dict() if self.chunk_plan is not None else None,
            "notes": list(self.notes),
        }


def build_plan(
    layer: Any,
    *,
    packs: Sequence[str] = (),
    chunk_above_vertices: int | None = None,
    chunk_halo_width: float | None = None,
    chunk_target_vertices: int | None = None,
    conditions: Iterable[str] | None = None,
) -> ValidationPlan:
    """Inspect ``layer`` and return what applies to it.

    ``chunk_above_vertices`` is the opt-in. Left as ``None``, the plan
    measures the layer and declines to chunk, because a vertex count at which
    chunking switches on is a claim about this dataset that does not transfer
    to the next one. Set it, and the plan chunks above it and says by how much
    it exceeded.

    ``conditions`` narrows the universe further. Left as ``None``, every
    registered condition is considered, so a newly registered condition is
    picked up without editing anything here.
    """
    from geoqa.problem_registry import list_problem_definitions

    profile = inspect_layer(layer)
    plan = ValidationPlan(profile=profile, packs=list(packs))
    notes = plan.notes

    if conditions is None:
        try:
            universe = {item.problem_name for item in list_problem_definitions()}
        except Exception:
            universe = set()
    else:
        universe = set(conditions)

    for name in sorted(universe):
        required = CONDITION_FAMILIES.get(name)
        if required in (None, "any"):
            plan.applicable_conditions.append(name)
            continue
        if required == profile.family:
            plan.applicable_conditions.append(name)
        elif profile.is_mixed_family and required in profile.family_counts:
            plan.applicable_conditions.append(name)
            notes.append(
                f"{name} applies to the {required} features in a mixed layer; the "
                "validator is expected to skip features of other families itself."
            )
        else:
            plan.skipped_conditions[name] = (
                f"requires {required} geometry; this layer is {profile.family}"
            )

    if profile.is_mixed_family:
        notes.append(
            "The layer mixes geometry families: "
            + ", ".join(f"{k}={v}" for k, v in sorted(profile.family_counts.items()) if k != "unknown")
            + ". The dominant family is used for gating."
        )
    if not profile.has_geometry:
        notes.append("No geometry column was found, so no geometry condition applies.")

    if chunk_above_vertices is None:
        plan.chunk = False
        plan.chunk_reason = (
            "No chunking threshold was supplied. The layer was measured "
            f"({profile.vertex_count} vertices) and left whole."
        )
    elif profile.vertex_count <= chunk_above_vertices:
        plan.chunk = False
        plan.chunk_reason = (
            f"{profile.vertex_count} vertices is at or below the declared threshold of "
            f"{chunk_above_vertices}, so the layer is validated whole."
        )
    else:
        plan.chunk = True
        plan.chunk_plan = plan_tiles(
            layer,
            halo_width=chunk_halo_width,
            target_vertices_per_tile=chunk_target_vertices,
        )
        if chunk_halo_width is None:
            plan.chunk_reason = (
                f"{profile.vertex_count} vertices exceeds the threshold of "
                f"{chunk_above_vertices}, but no halo was supplied, so tiling would "
                "exchange features across a boundary and topology findings would be "
                "unreliable. Supply chunk_halo_width."
            )
            notes.append(
                "Chunking was requested above the threshold but not enabled, because a "
                "halo is what makes a tiled run agree with a whole-layer run."
            )
        else:
            plan.chunk_reason = (
                f"{profile.vertex_count} vertices exceeds the threshold of "
                f"{chunk_above_vertices}; tiling into {plan.chunk_plan.tile_count} tile(s) "
                f"with a halo of {chunk_halo_width:g}."
            )

    return plan


def validate_plan(
    plan: ValidationPlan,
    *,
    report_skipped: bool = False,
) -> list[ValidationIssue]:
    """Report anything about the plan the caller should know before running.

    ``report_skipped`` is off by default. A polygon layer legitimately skips
    every line and point condition, and emitting an informational issue for
    each would bury the findings that matter. It is on when a report has to
    prove which checks were considered, because then a check that did not run
    and a check that ran and found nothing must not look the same.
    """
    issues: list[ValidationIssue] = []
    profile = plan.profile

    if profile.is_mixed_family:
        issues.append(
            build_issue(
                "geometry_family_mixed",
                description=(
                    "The layer mixes geometry families ("
                    + ", ".join(
                        f"{k}={v}" for k, v in sorted(profile.family_counts.items())
                        if k != "unknown"
                    )
                    + "). Validation was planned against the dominant family, so "
                    "features of other families may not have been examined."
                ),
                extra=profile.to_dict(),
            )
        )

    if report_skipped:
        for condition, reason in sorted(plan.skipped_conditions.items()):
            issues.append(
                build_issue(
                    "condition_not_applicable",
                    description=(
                        f"{condition} was not run: {reason}. This is a fact about the "
                        "plan, not a pass."
                    ),
                    extra={"condition": condition, "reason": reason},
                )
            )

    if plan.chunk_plan is not None and plan.chunk_plan.halo_width <= 0:
        issues.append(
            build_issue(
                "chunk_halo_undeclared",
                description=(
                    "The layer exceeded the chunking threshold and was tiled, but no halo "
                    "was supplied. Features either side of a tile boundary were not "
                    "validated together, so topology findings from this run cannot be "
                    "trusted."
                ),
                extra={
                    "reason": plan.chunk_reason,
                    "vertex_count": plan.vertex_count,
                    "tile_count": plan.chunk_plan.tile_count,
                },
            )
        )
    return issues