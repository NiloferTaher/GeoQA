"""Spatial chunking that does not manufacture topology breaks.

Chunking exists because a whole layer does not fit in memory at once. The
danger is that splitting a layer changes the answer: a pipe whose two ends sit
in different tiles becomes two orphan endpoints, and a network that was one
connected component becomes several. A chunked run that reports those as
defects has invented findings, which is worse than not running at all.

Two mechanisms prevent that here.

**The halo.** Each tile selects every feature whose geometry intersects the
tile *expanded by a halo*, not merely the tile. A feature crossing a boundary
is therefore present, whole, on both sides. It is not clipped at the seam, so
a validator run on that tile sees the same geometry it would have seen in a
whole-layer run. The halo must exceed the largest distance at which two
features can interact, which for topology means the largest gap the caller is
prepared to call a break; that distance has to be declared rather than assumed.

**The opt-in.** Chunking is unsafe by default. A validator runs on a whole
layer unless it is declared chunk-local in :data:`CHUNK_LOCAL_VALIDATORS`. The
reasoning is that whole-layer correctness is the default expectation and
chunking is an optimisation: it should have to earn the right to change what a
validator can see. Validators that reason about the layer as a single object,
such as union, component count or degree, cannot be tiled at all and are
excluded structurally rather than by convention.

Findings are deduplicated on ``(problem_name, feature_id)`` because a feature
inside two halos is genuinely validated twice. Both runs are correct; only one
is reported.

The module deliberately does not decide how large a chunk should be. That
depends on the caller's memory budget and is set through
:func:`plan_tiles`, which reports what it did so the choice stays visible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "ChunkPlan",
    "Tile",
    "plan_tiles",
    "select_chunk",
    "run_chunked_validation",
    "chunk_safety_report",
    "CHUNK_LOCAL_VALIDATORS",
    "ALWAYS_WHOLE_LAYER",
    "MAX_GRID_SIDE",
]

#: Ceiling on the grid side. Past this the halo overlap grows faster than the
#: memory saved, because every tile re-reads the features in its halo.
MAX_GRID_SIDE = 32


#: Validators whose result depends only on the features present, not on what is
#: absent. A duplicate vertex, a missing attribute, an invalid geometry and a
#: coordinate precision problem are all decidable from one feature at a time,
#: so a halo-buffered tile gives the same answer as the whole layer.
#:
#: Anything not listed here runs on the whole layer.
CHUNK_LOCAL_VALIDATORS: frozenset[str] = frozenset(
    {
        # accuracy
        "coordinate_precision",
        "positional_accuracy",
        # attributes
        "domain_range_checks",
        "required_nulls",
        "uniqueness",
        # geometry
        "null_geometry",
        "self_intersection",
        "duplicate_vertex",
        "below_minimum_feature_length",
        "sharp_angle_cutback",
        # endpoint triage, where the interaction distance is bounded by the
        # caller's declared search radius and the halo is set to exceed it
        "unsnapped_endpoints_within_tolerance",
        # metadata
        "incomplete_metadata",
        "missing_metadata_fields",
        # integrity
        "non_rfc7946_geojson",
    }
)

#: Structural reasons a validator cannot be tiled. These are properties of the
#: question, not of an implementation, so they are stated rather than inferred.
ALWAYS_WHOLE_LAYER: dict[str, str] = {
    "polygon_overlap_same_layer": "Whether two polygons overlap depends on both being present, wherever they are.",
    "polygon_gap_same_layer": "A gap between two polygons cannot be found if the other polygon is in another tile.",
    "line_intersection_same_layer": "A crossing between two lines requires both lines to be present.",
    "feature_within_feature": "Containment is only decidable against the full extent.",
    "duplicate_geometry_same_layer": "A duplicate may sit arbitrarily far away in a different tile.",
    "continuity_breaks": "A line is continuous only with regard to its whole declared extent.",
    "isolated_network_segment": "Connectivity is a property of the whole network.",
    "feature_not_split_at_intersection": "Whether a line was split at a crossing needs every crossing present.",
    "line_dangle": "A dangle is defined against the whole network, not a neighbourhood.",
    "boundary_mismatch_against_reference": "A boundary must be compared against the complete reference.",
    "profile_clip_assignment": "A clip result depends on the complete layer being cut once.",
    "validate_repeats": "Recurrence is defined across periods, not within a tile.",
}


@dataclass(frozen=True)
class Tile:
    """One cell of the tiling grid, before the halo is applied."""

    index: tuple[int, int]
    bounds: tuple[float, float, float, float]

    @property
    def extent(self) -> tuple[float, float, float, float]:
        return self.bounds


@dataclass
class ChunkPlan:
    """What chunking would do, and why.

    Kept as a value rather than executed on the spot so a caller can inspect
    the tile count and the halo before paying for the run, and so a report can
    state the tiling it was produced under.
    """

    tiles: list[Tile]
    halo_width: float
    halo_declared: bool
    target_vertices_per_tile: int | None
    bounds: tuple[float, float, float, float]
    whole_layer_vertex_count: int
    notes: list[str] = field(default_factory=list)

    @property
    def tile_count(self) -> int:
        return len(self.tiles)

    @property
    def would_partition(self) -> bool:
        """True when the plan actually splits the layer into more than one pass."""
        return self.tile_count > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_count": self.tile_count,
            "halo_width": self.halo_width,
            "halo_declared": self.halo_declared,
            "target_vertices_per_tile": self.target_vertices_per_tile,
            "bounds": list(self.bounds),
            "whole_layer_vertex_count": self.whole_layer_vertex_count,
            "notes": list(self.notes),
        }


def _vertex_count(layer: Any) -> int:
    try:
        total = 0
        for geom in layer.geometry:
            if geom is None:
                continue
            try:
                total += len(geom.geoms) if hasattr(geom, "geoms") else 1
            except Exception:
                total += 1
        return total
    except Exception:
        return len(layer)


def plan_tiles(
    layer: Any,
    *,
    halo_width: float | None = None,
    target_vertices_per_tile: int | None = None,
    max_tiles: int = 4096,
) -> ChunkPlan:
    """Propose a tiling for ``layer``.

    ``halo_width`` is the distance outside a tile within which a feature is
    still considered to belong to it. Passing ``None`` is recorded as an
    undeclared halo rather than silently defaulting to zero, because a halo of
    zero is the exact condition that produces false topology breaks and it
    should not arrive by accident.
    """
    notes: list[str] = []
    try:
        bounds_obj = layer.total_bounds
        bounds = (
            float(bounds_obj[0]),
            float(bounds_obj[1]),
            float(bounds_obj[2]),
            float(bounds_obj[3]),
        )
    except Exception:
        # No geometry column, or an empty frame. Tiling has nothing to work
        # from, and saying so is more useful than the AttributeError that
        # reading total_bounds raises on a non-spatial frame.
        notes.append(
            "The layer has no readable geometry bounds, so no tiling was "
            "attempted and the layer is validated whole."
        )
        empty = ChunkPlan([Tile(index=(0, 0), bounds=(0.0, 0.0, 0.0, 0.0))], 0.0,
                          False, target_vertices_per_tile, (0.0, 0.0, 0.0, 0.0), 0, notes)
        return empty
    vertices = _vertex_count(layer)

    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny

    halo = 0.0 if halo_width is None else float(halo_width)
    if halo_width is None:
        notes.append(
            "No halo was declared. Tiles will not exchange features across a "
            "boundary, so topology findings on a multi-tile run are unreliable."
        )

    if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
        notes.append("Layer bounds are degenerate; a single tile covers everything.")
        tile = Tile(index=(0, 0), bounds=bounds)
        return ChunkPlan([tile], halo, halo_width is not None, target_vertices_per_tile, bounds, vertices, notes)

    if target_vertices_per_tile is None:
        # No budget declared. Tiling is an optimisation that changes what a
        # validator can see, so it does not happen on a guess. A single tile
        # covering the whole layer is returned and the reason is recorded.
        side = 1
        notes.append(
            "No vertex budget was declared, so no tiling was performed. Pass "
            "target_vertices_per_tile to opt in to chunking."
        )
    else:
        side = _side_for_budget(vertices, int(target_vertices_per_tile), width, height, notes)

    tile_width = width / side
    tile_height = height / side

    tiles: list[Tile] = []
    for row in range(side):
        for col in range(side):
            tiles.append(
                Tile(
                    index=(row, col),
                    bounds=(
                        minx + col * tile_width,
                        miny + row * tile_height,
                        minx + (col + 1) * tile_width,
                        miny + (row + 1) * tile_height,
                    ),
                )
            )

    if halo > 0:
        notes.append(
            f"Every tile is searched over its bounds plus {halo:g} in each "
            "direction, so a feature crossing a boundary is validated whole on "
            "both sides."
        )

    return ChunkPlan(tiles, halo, halo_width is not None, target_vertices_per_tile, bounds, vertices, notes)


def _side_for_budget(
    vertices: int,
    budget: int,
    width: float,
    height: float,
    notes: list[str],
) -> int:
    """Choose a grid side so the average tile holds about ``budget`` vertices.

    The result is capped because a very fine grid on a very large layer costs
    more in repeated halo overlap than it saves in memory, and because every
    tile re-reads the source layer.
    """
    if budget <= 0:
        notes.append("Vertex budget was zero or negative; running as a single tile.")
        return 1
    wanted = max(1, math.ceil(vertices / budget))
    side = max(1, min(wanted, MAX_GRID_SIDE))
    if wanted > MAX_GRID_SIDE:
        notes.append(
            f"The requested budget implies a {wanted}x{wanted} grid, which was "
            f"capped at {MAX_GRID_SIDE}x{MAX_GRID_SIDE}. Tiles will hold more "
            "than the budget asked for."
        )
    notes.append(
        f"Averaging {vertices} vertices over a {side}x{side} grid puts roughly "
        f"{max(1, vertices // (side * side))} vertices in a tile before the halo."
    )
    return side


def select_chunk(layer: Any, tile: Tile, halo_width: float) -> Any:
    """Return the features of ``layer`` that belong to ``tile``.

    A feature qualifies when its geometry intersects the tile grown by
    ``halo_width``. Geometries are returned whole. Clipping them to the tile
    would reintroduce the very seams this is meant to remove.
    """
    minx, miny, maxx, maxy = tile.bounds
    window = (minx - halo_width, miny - halo_width, maxx + halo_width, maxy + halo_width)
    try:
        subset = layer.cx[window[0] : window[2], window[1] : window[3]]
        if len(subset):
            return subset
    except Exception:
        pass
    return _select_by_intersection(layer, window)


def _select_by_intersection(layer: Any, window: tuple[float, float, float, float]) -> Any:
    try:
        from shapely.geometry import box

        clip = box(*window)
    except Exception:
        return layer
    try:
        return layer[layer.geometry.intersects(clip)]
    except Exception:
        return layer


def _dedupe_key(issue: ValidationIssue) -> tuple[str, Any]:
    return (issue.problem_name, issue.feature_id)


def run_chunked_validation(
    layer: Any,
    validators: Sequence[tuple[str, Callable[..., Iterable[ValidationIssue]]]],
    *,
    plan: ChunkPlan | None = None,
    halo_width: float | None = None,
    target_vertices_per_tile: int | None = None,
) -> list[ValidationIssue]:
    """Run ``validators`` over ``layer``, tiling only what is safe to tile.

    Returns the deduplicated findings. Validators named in
    :data:`ALWAYS_WHOLE_LAYER` are run once against the complete layer
    regardless of the plan, and a warning issue is added when a plan with more
    than one tile is used for them, because the caller asked for something that
    cannot be delivered and should not have to discover that from a silent
    absence.
    """
    resolved_plan = plan or plan_tiles(
        layer,
        halo_width=halo_width,
        target_vertices_per_tile=target_vertices_per_tile,
    )
    halo = resolved_plan.halo_width
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, Any]] = set()

    chunk_local = [(name, fn) for name, fn in validators if name in CHUNK_LOCAL_VALIDATORS]
    whole_layer = [(name, fn) for name, fn in validators if name not in CHUNK_LOCAL_VALIDATORS]

    if resolved_plan.would_partition and halo <= 0:
        issues.append(
            build_issue(
                "chunk_halo_undeclared",
                description=(
                    "A multi-tile run was performed with no halo, so features "
                    "either side of a tile boundary were not validated together."
                ),
                extra={
                    "tile_count": resolved_plan.tile_count,
                    "halo_width": halo,
                },
            )
        )

    for name, fn in chunk_local:
        if resolved_plan.would_partition:
            for tile in resolved_plan.tiles:
                subset = select_chunk(layer, tile, halo)
                if not len(subset):
                    continue
                for issue in fn(subset):
                    key = _dedupe_key(issue)
                    if key in seen:
                        continue
                    seen.add(key)
                    issue.provenance = dict(issue.provenance or {})
                    issue.provenance.setdefault("chunk_index", list(tile.index))
                    issue.provenance["chunked"] = True
                    issues.append(issue)
        else:
            for issue in fn(layer):
                key = _dedupe_key(issue)
                if key in seen:
                    continue
                seen.add(key)
                issues.append(issue)

    for name, fn in whole_layer:
        if resolved_plan.would_partition and name in ALWAYS_WHOLE_LAYER:
            issues.append(
                build_issue(
                    "chunk_validator_not_tileable",
                    description=(
                        f"'{name}' was run on the whole layer because it cannot be "
                        "tiled: " + ALWAYS_WHOLE_LAYER[name]
                    ),
                    extra={"validator": name, "tile_count": resolved_plan.tile_count},
                )
            )
        for issue in fn(layer):
            key = _dedupe_key(issue)
            if key in seen:
                continue
            seen.add(key)
            issues.append(issue)

    return issues


def chunk_safety_report(validators: Sequence[str]) -> dict[str, list[str]]:
    """Partition validator names by what chunking may do to them.

    Provided so a caller can ask the question before running anything, rather
    than discovering the answer by finding a topology finding that vanished.
    """
    safe: list[str] = []
    whole: list[str] = []
    for name in validators:
        if name in ALWAYS_WHOLE_LAYER:
            whole.append(name)
        elif name in CHUNK_LOCAL_VALIDATORS:
            safe.append(name)
        else:
            whole.append(name)
    return {"chunk_local": safe, "whole_layer_only": whole}