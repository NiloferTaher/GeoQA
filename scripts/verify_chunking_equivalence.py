"""Demonstrate the claim chunking makes, and the failure it prevents.

Run directly for readable output:

    python scripts/verify_chunking_equivalence.py

The question this answers is narrow and falsifiable: does a chunked run return
the same findings as a whole-layer run, and does removing the halo change that?
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
from shapely.geometry import LineString  # noqa: E402

from geoqa.chunking import plan_tiles, run_chunked_validation  # noqa: E402
from geoqa.validations.endpoint_triage import triage_endpoints  # noqa: E402
from geoqa.validations.geometry import duplicate_vertex  # noqa: E402


def build_layer(n: int = 12, spacing: float = 100.0) -> gpd.GeoDataFrame:
    """Segments separated by a real gap, so endpoints have to adjudicate.

    Every third row carries a duplicated vertex so the per-feature check has
    something to find as well.
    """
    rows = []
    idx = 0
    for r in range(n):
        for c in range(n):
            x, y = c * spacing, r * spacing
            end = x + spacing * 0.5
            if (r + c) % 3 == 0:
                geom = LineString([(x, y), (end, y), (end, y), (end + 5.0, y)])
            else:
                geom = LineString([(x, y), (end, y)])
            rows.append({"seg_id": idx, "geometry": geom})
            idx += 1
    return gpd.GeoDataFrame(rows, crs="EPSG:27700")


def triage_issues(layer):
    """Validator form: yields issues rather than keys."""
    return triage_endpoints(layer, snap_tolerance=30.0).to_issues()


def triage_keys(layer):
    return {(issue.problem_name, issue.feature_id) for issue in triage_issues(layer)}


def main() -> int:
    layer = build_layer()
    print(f"layer: {len(layer)} features, bounds {tuple(round(v) for v in layer.total_bounds)}")
    print()

    print("--- per-feature check: duplicate_vertex ---")
    base = {(i.problem_name, i.feature_id) for i in duplicate_vertex(layer)}
    plan = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=20)
    got = {
        (i.problem_name, i.feature_id)
        for i in run_chunked_validation(layer, [("duplicate_vertex", duplicate_vertex)], plan=plan)
    }
    print(f"  whole layer            : {len(base)}")
    print(f"  chunked, halo {plan.halo_width:g}, {plan.tile_count} tiles : {len(got)}")
    print(f"  identical              : {got == base}")
    print()

    print("--- neighbour-dependent check: endpoint triage ---")
    base2 = triage_keys(layer)
    print(f"  whole layer            : {len(base2)}")

    haloed = plan_tiles(layer, halo_width=150.0, target_vertices_per_tile=20)
    got2 = {
        (i.problem_name, i.feature_id)
        for i in run_chunked_validation(
            layer,
            [("unsnapped_endpoints_within_tolerance", triage_issues)],
            plan=haloed,
        )
    }
    print(f"  chunked, halo 150      : {len(got2)} across {haloed.tile_count} tiles")
    print(f"    identical to whole   : {got2 == base2}")
    print(f"    lost                 : {len(base2 - got2)}")
    print(f"    invented             : {len(got2 - base2)}")

    bare = plan_tiles(layer, halo_width=0.0, target_vertices_per_tile=20)
    got3 = {
        (i.problem_name, i.feature_id)
        for i in run_chunked_validation(
            layer,
            [("unsnapped_endpoints_within_tolerance", triage_issues)],
            plan=bare,
        )
    }
    print(f"  chunked, halo 0        : {len(got3)} across {bare.tile_count} tiles")
    print(f"    identical to whole   : {got3 == base2}")
    print(f"    lost                 : {len(base2 - got3)}")
    print(f"    invented             : {len(got3 - base2)}")
    print()

    print("--- notes the planner attaches ---")
    for note in plan_tiles(layer, halo_width=None, target_vertices_per_tile=20).notes:
        print(f"  - {note}")
    print()

    faithful = got2 == base2
    invented = got3 - base2
    lost = base2 - got3
    print(f"haloed run reproduces the whole-layer answer : {faithful}")
    print(f"unhaloed run invents findings               : {len(invented)}")
    print(f"unhaloed run loses findings                 : {len(lost)}")

    if faithful and invented:
        print()
        print("CONCLUSION: the halo is load-bearing.")
        print()
        print("With a declared halo, the chunked run returns exactly the findings the")
        print("whole-layer run returns: no finding added, none dropped, across")
        print(f"{haloed.tile_count} tiles.")
        print()
        print(f"Remove the halo and the same run invents {len(invented)} finding(s) that a")
        print("whole-layer run correctly does not report. A feature sitting on a tile")
        print("boundary loses the neighbour it was being compared against, and a QA tool")
        print("that invents a defect is worse than one that runs slowly: the operator")
        print("spends a day chasing geometry that was never wrong.")
        print()
        print("This is why no validator is tiled unless it has declared itself")
        print("chunk-local, and why an undeclared halo on a multi-tile run is reported")
        print("as evidence rather than passing silently.")
        return 0

    print()
    print("CONCLUSION: inconclusive on this fixture. See the numbers above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())