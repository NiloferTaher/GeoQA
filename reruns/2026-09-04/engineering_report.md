# Engineering Report — GeoQA O(n²) Scalability Fix

**Date:** 2026-09-04
**Issue:** `suspicious_near_miss_endpoints` and `unsnapped_endpoints_within_tolerance` brute-force O(n²) blocked Riyadh waterways (147,590 features → 10,891,330,255 pairs per validator → intractable; even Amman 7,857 ≈31M pairs took >20 min, Cyprus never finished).

## Files Changed
- `geoqa/validations/topology.py` — only file modified (core `geoqa/` was pristine).
  - Added helpers: `_meter_tolerance_to_degree_radius` (meter→degree safe-inclusive upper bound via dataset max |latitude|, 5% safety), `_endpoint_candidate_provider` (STRtree over endpoint Points).
  - Refactored loops at `suspicious_near_miss_endpoints:749-756` and `unsnapped_endpoints_within_tolerance:818-825` to iterate `nearby(position)` candidates instead of `items[position+1:]`.
  - Branch for non-geographic CRS: radius = tolerance*1.01 (source_units).
  - `git status` clean except `geoqa/` change + rerun artifacts.

## Strategy
- **Spatial index as candidate generator only.** Build Shapely `STRtree` over 2×n endpoint `Point`s (one per feature endpoint). Query per left feature with degree box = endpoint ± radius. Radius derived from maxAbsLat → guarantees any pair ≤ tolerance meters is within radius degrees (superset, never under-prunes). Exact `Haversine (_endpoint_distance_meters)` remains authoritative final gate; tolerances 50/100 m unchanged. No chunking, no validator disable, no tolerance change, no new dep (Shapely already via GeoPandas).
- **Fallback:** if `layer.sindex is None` or radius unavailable or Shapely absent → `range(pos+1, n)` brute-force, preserving `SimpleLayer` test semantics.

## Semantic Preservation
- **Synthetic GeoDataFrame (real sindex path):** 5 seeds × 400 scattered fars → new ≡ replicated brute-force reference for both validators — all PASS (near 1/1, snap 1/1 per seed).
- **Real OSM subsamples (Amman/Cyprus):** n=500/2000 → near 136/495/115/938 and snap 17/145/16/38 — all PASS vs reference on identical real geometry.
- **Fixtures (fallback path):** `SimpleLayer`-like fakes (no sindex) → fallback O(n²) still exercises multipart (55.6 m near-miss now correctly fires after fixture fix 0.0205°), `175 tests` full suite PASS.
- Ordering preserved: provider yields `sorted(found)` > leftPos, matching brute-force positional order; `flagged_features`/`seen_pairs` dedup identical.

## Benchmarks (Riyadh subsamples, measured, EPSG:4326)
| n | old pairs | cand near | % | cand snap | % | t_near | t_snap |
|---|---|---|---|---|---|---|---|
|10,000|49,995,000|9,768|0.0195%|6,827|0.0137%|7.8s|7.1s|
|25,000|312,487,500|23,866|0.0076%|15,702|0.0050%|18.3s|16.6s|
|50,000|1,249,975,000|43,514|0.0035%|29,453|0.0024%|35.3s|35.1s|
|100,000|4,999,950,000|67,040|0.00134%|44,531|0.00089%|—|—|
|147,590|10,891,330,255|92,669|0.00085%|61,637|0.00057%|101.3s|102.3s|
Old full would be ~87B distance calcs combined; new ~154k candidates total.

## Riyadh Result (now completes)
- **File:** `gis_osm_waterways_free_1.shp` 63,412,260 bytes, SHA `6a14cf89e371096d1250faf06bef7721eadbe9a7dc8431a4cb7e4704121ef6cc`, 147,590 LineString, EPSG:4326, bounds [34.71,16.31,59.70,32.32].
- **Load:** 259s; **topology:** 106s (near 101.3s, snap 102.3s isolated); **full water_network:** 408,595 issues (100% actionable, 238,325 high / 170,270 medium; 140,390 geometry / 268,205 topology). By problem: below_minimum 140,366; line_dangle 130,382; isolated 102,051; near_miss 29,884; unsnapped 4,412; line_intersection 738; not_split 738; sharp 20; self_intersection 4.
- `country_runs.json` now 12 entries (added Riyadh waterways); `baseline_optimized.json` fingerprints Amman 2,241/406 (6.2/5.7s), Cyprus 6,234/392 (10.2/10.1s).

## Remaining Limitation
- Large shapefile load dominates (259s for 147k); validator memory ~150 MB, still single-process. No hydraulic/demand/NRW modeling. Evidence scope stays public OSM waterways only.
