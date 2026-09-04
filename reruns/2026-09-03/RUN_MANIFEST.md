# Run Manifest — 2026-09-03 GeoQA rerun (CRWASH evidence)

GeoQA version: **0.3.0** (validation_rule_version "2026.03")
Purpose: regenerate owned, verifiable, **public-data-only** GeoQA evidence for the
CRWASH abstract under the "no proof, no write" rule.

## Outcome: Code-of-Earth water shapefiles REJECTED (corrupted)
Full detail in `README.md`. Summary: the 4 target OSM water/waterways `.shp` files
contain only a small fraction of the geometry their DBF/SHX claim (e.g. Riyadh
`water_a` DBF=11,713 records but `.shp` has **151** real geometries; Amman
`waterways` DBF=7,857 but `.shp` has **80**). Three of four DBFs are unreadable by
pyogrio, and Riyadh `waterways` has a corrupt SHX. These are partial
Google-Drive-sync artifacts, **not** trustworthy datasets. No CRWASH claim is made
from them.

## Runs actually executed (both on the intact public OSM water sample)
Input: `Sandbox-TIG\data\real\public_pack\osm_water_network_global_sample.csv`
(row count matches `..._20260225_025619.csv`, which is the same file content).
SHA-256 of both = `BEA4985BC9EC12F66771A214E57A173FBD54F4467E9ABE2EBB230AEC219BACDE`
(025252 = `175D5F309401E793539DFAD291A3A15DB51DA0B80B5BF36B0EA5DBC586D0C763`).
ODbL (OpenStreetMap), public.

| Profile | Report | Loaded | Issues | Actionable | Ratio | Severity | Root cause |
|---|---|---|---|---|---|---|---|
| `water_network_quick` | `osm_water_sample_q25x2.json` | 126 | 0 | 0 | 0.0 | — | — |
| `generic_quick` | `osm_water_sample_generic.json` | 126 | 1 | 1 | 1.0 | medium | missing spatial index (integrity) |

Validation rule version: 2026.03. Geometry type read as **Point** (CSV is lat/lon
attribute rows; **no line geometry**). Runs completed in **full** status; no
deferred validators. Date: 2026-09-03.

## Interpretation for CRWASH (ledger read-across)
- The OSM water CSV carries **no line geometry**, so it cannot demonstrate
  line/topology breakage. The `water_network_quick` run reports **0 issues** on it
  when read as points.
- The earlier "≈15% null cells / 0 geometry parsed" figures came from the **GeoAI
  (LLM)** layer in `Sandbox-TIG\AI-empirical\runs\geoai_dataset_results.csv`, not
  from this deterministic validator. Do NOT conflate the two in the abstract.
- Net: **we currently have NO strong, intact, public line-level water dataset on
  disk** to underwrite a "widespread line misclassification would propagate"
  claim. Any such claim must be (a) reframed as motivation/proposition 🟡, or
  (b) dropped 🟢-absent, until a genuinely intact public water extract is obtained
  (e.g. a fresh Geofabrik `*-latest-free.shp.zip` re-download verified by
  SHA + full-feature round-trip read).

## Action noted for next steps
Obtain a verified, complete public water extract (re-download from Geofabrik and
verify every record's geometry reads and that DBF == SHX == SHP record counts
before trusting), then rerun `water_network` + `water_network_strict` here.

---

## ✔ RESOLVED LATER SAME DAY: Amman layers recovered & validated (strong CRWASH receipt)

**Root cause of the earlier corruption:** the on-disk `jordan-latest-free.shp.zip`
was **intact**; only the *extracted* `.shp/.dbf` files were partial Google-Drive
sync artifacts. Re-extracted the water files from the intact Jordan zip, verified
full round-trip (DBF == SHX == SHP record counts match, 0 null geometry), and
replaced the corrupt in-place copies. Corrupt originals preserved for the record at
`C:\Users\admin\AppData\Local\Temp\opencode\jordan_osm_CORRUPT_backup\`.

**Riyadh (GCC-states) — DEFERRED (per user, 2026-09-03):** the on-disk
`gcc-states-latest-free.shp.zip` is itself corrupt (`BadZipFile: Bad magic number
for central directory`) and needs a 499 MB re-download from Geofabrik
(`gcc-states-260901-free.shp.zip`). Not performed today; Amman-only evidence used.

### Verified inputs (in-place, Amman)
| File | Rows | Geometry | CRS | null geom | SHA-256 (.shp) |
|---|---|---|---|---|---|
| `amman\jordan_osm\gis_osm_water_a_free_1.shp` | 1,358 | Polygon | EPSG:4326 | 0 | `FA0D88849C28B03F348162B6DBC7EAFDAD984FBC73FDE866A9180F54DFB1E19C` |
| `amman\jordan_osm\gis_osm_waterways_free_1.shp` | 7,857 | LineString | EPSG:4326 | 0 | `9BA2CFB98749171D4BA057E76F8EEFB0E259DC45EDB3E8398E8BA6EB4F0DA43D` |

Source: Geofabrik OSM "Jordan" extract (`jordan-latest-free.shp.zip`), ODbL,
public. GeoQA 0.3.0, rule 2026.03. Date 2026-09-03.

### GeoQA results (both profiles agree exactly)
| Profile/Report | Loaded | Issues | Actionable | Ratio | Severity | Root cause |
|---|---|---|---|---|---|---|
| `water_a` `water_network` / `_strict` | 1,358 | **10** | 10 | 1.0 | 10 high | topology |
| `waterways` `water_network` / `_strict` | 7,857 | **22,226** | 22,226 | 1.0 | 12,412 high + 9,814 medium | 14,652 topology + 7,574 geometry |

waterways problem breakdown (both profiles): below_minimum_feature_length 7,571;
line_dangle 6,683; isolated_network_segment 5,044;
suspicious_near_miss_endpoints 2,241; unsnapped_endpoints_within_tolerance 406;
feature_not_split_at_intersection 139; line_intersection_same_layer 139;
sharp_angle_cutback 2; self_intersection 1. All ISO category "Logical Consistency".

### CRWASH implication (ledger read-across, updated)
This is now a **genuine, verifiable, public-data line-level receipt**:
- **water_a** (polygon layer): 10 duplicate-geometry issues (topology).
- **waterways** (line layer): 22,226 topology/geometry issues across 7,857
  features (~2.8 issues/feature; 100% actionable; 56% high) — dominated by
  sub-minimum-length features, line dangles, and isolated segments.
- These are real OSM (ODbL) Amman water features, SHA-linked, rerun here today.
- It does **not** license claims about the author's former-employer Oman mains
  (still 🔴 excluded) — it underwrites the CRWASH *proposition* that
  real-world public water network data carries substantial, predominantly
  topology-class, largely high-severity data-integrity issues that an AI-driven
  QA layer must handle. Wording must stay tied to THIS dataset, not generalised
  beyond it.

---

# CROSS-COUNTRY EXTENSION — Malta, Djibouti, Cyprus (verified 2026-09-03)

To broaden the evidence beyond Jordan, three additional **public (ODbL) Geofabrik
OSM extracts** were downloaded, integrity-verified (testzip OK; DBF == SHX == SHP
record counts all match; 0 null geometry), and validated under `water_network`
(GeoQA 0.3.0, rule 2026.03, status full). **Permanent copies (hash-verified
identical): `Projects\Code-of-Earth\data\{malta,djibouti,cyprus}\{country}-latest-free.shp.zip`
+ `{country}_osm\` extract folders.** Original download staging was under
`C:\Users\admin\AppData\Local\Temp\opencode\geofabrik_countries\`.
Raw per-run summaries: `country_runs.json` (with .shp SHA-256).

## Verified inputs (rows; geometry; null geom; results)
| Country | Layer | Features | Issues | Actionable | Ratio | Severity | Root cause |
|---|---|---|---|---|---|---|---|
| Malta | water_a | 1,154 | **0** | 0 | 0.0 | — | — |
| Malta | waterways | 192 | **438** | 438 | 1.0 | 151 high + 287 med | 192 geom + 246 topo |
| Djibouti | water_a | 201 | **0** | 0 | 0.0 | — | — |
| Djibouti | waterways | 4,876 | **13,843** | 13,843 | 1.0 | 7,568 high + 6,275 med | 4,710 geom + 9,133 topo |
| Cyprus | water_a | 1,208 | **0** | 0 | 0.0 | — | — |
| Cyprus | waterways | 13,865 | **34,914** | 34,914 | 1.0 | 14,856 high + 20,058 med | 13,824 geom + 21,090 topo |

waterways SHP SHA-256: Malta `4880c188...`; Djibouti `8bed71f2...`;
Cyprus `3e8f0997...`. water_a SHAs: Malta `23b18b0a...`; Djibouti `cc7bcedd...`;
Cyprus `c3a00cc0...`.

## GeoQA sanity check (proves the tool, not just the data)
Two synthetic edge-case fixtures under `data\public_samples\edge_cases\` were run
to confirm GeoQA detects planted errors:
- `self_intersection_polygon.geojson` → **1 issue, `self_intersection`, high** ✔
- `duplicate_vertex_line.geojson` → **3 issues incl. `duplicate_vertex`, high** ✔
So GeoQA is functioning correctly; the large issue counts on real data are genuine
detections, not a broken validator.

## Consolidated CRWASH takeaway (public, cross-country, line-level)
Across **4 countries** (Jordan/Amman + Malta + Djibouti + Cyprus), the **waterways
(line) layers consistently show high issue density, 100% actionable,
topology-dominated**, while the **water_a (polygon) layers are clean (0 issues)**:
- Amman water_a 10 / waterways 22,226; Malta water_a 0 / waterways 438;
  Djibouti water_a 0 / waterways 13,843; Cyprus water_a 0 / waterways 34,914.
- Total waterways issues across the 3 new countries: **49,195** (≈2.6–2.8
  issues/feature), dominated by below-minimum-length, line dangles, and isolated
  segments.
This is a reproducible, public, SHA-linked, multi-country receipt supporting the
CRWASH proposition that **line-level water-network data carries substantial
topology/data-integrity issues that a deterministic pre-AI QA layer surfaces**.
It does NOT license claims about the excluded private Oman mains or about any
downstream demand/loss propagation (not modeled). Keep wording tied to these
public OSM water/waterways datasets.

---

# RIYADH (GCC-states) + NATURAL EARTH BASE-VECTOR (2026-09-04)

## Riyadh (GCC-states, Saudi)
The earlier on-disk `gcc-states-latest-free.shp.zip` was corrupt; a fresh
Geofabrik re-download was secured and fully verified:
- Zip: `gcc-states-260901-free.shp.zip`, **499,351,132 bytes**, `testzip()` ALL OK,
  SHA-256 `b16f14f9bc2e0362b03220ac94f3d1ea14f712ca32b6090b32ab4e8a9466b749`.
- Water layers under `riyadh\saudi_osm\`, all EPSG:4326, all DBF==SHX==SHP
  consistent (no truncation):
  - `gis_osm_water_a_free_1.shp` — **11,918** Polygon features, **2 null-geom**,
    SHA `630696364d74c9dcf7229c0d12e8e9f7a2895ac56d9b53abf8db693c599e31ee`.
  - `gis_osm_waterways_free_1.shp` — **147,590** LineString features, 0 null-geom,
    SHA `6a14cf89e371096d1250faf06bef7721eadbe9a7dc8431a4cb7e4704121ef6cc`.

GeoQA (`water_network`, rule 2026.03, status full):
- `water_a` → **8 issues**, all **high**, `duplicate_geometry_same_layer`,
  ISO Logical Consistency, 100% actionable (8 topology).

  > Note: the 2 null-geometry features in `water_a` are provenance-level
  > observations (present at data load); they do not appear as GeoQA issues in
  > this run's summary.
- `waterways` (147,590 features) → **COMPLETED 2026-09-04** ✅ after scalability fix (see below).
  Verified layer on disk (SHA `6a14cf89...`, 63,412,260 bytes, EPSG:4326, 0 null-geom).
  - **Load:** 259 s; **topology validators:** 106 s; **full `water_network` (topology+geometry+attributes+crs):**
    **408,595 issues, 100% actionable**, 238,325 high / 170,270 medium, 140,390 geometry / 268,205 topology.
  - By problem: `below_minimum_feature_length` 140,366; `line_dangle` 130,382;
    `isolated_network_segment` 102,051; `suspicious_near_miss_endpoints` 29,884 (100 m);
    `unsnapped_endpoints_within_tolerance` 4,412 (50 m); `line_intersection_same_layer` 738;
    `feature_not_split_at_intersection` 738; `sharp_angle_cutback` 20; `self_intersection` 4.
  - **Scalability fix:** `geoqa/validations/topology.py:55-160, 749-756, 818-825`
    — `suspicious_near_miss_endpoints` and `unsnapped_endpoints_within_tolerance`
    replaced O(n²) brute-force endpoint comparison with spatial-index candidate
    generation (Shapely `STRtree` over endpoint `Point`s, degree search radius
    derived from dataset max |latitude| as a safe-inclusive upper bound of the
    meter tolerance, 5% safety factor; **exact Haversine (`_endpoint_distance_meters`)
    retained as authoritative final distance test**; tolerances unchanged at 50/100 m;
    brute-force fallback when no `sindex` (preserves `SimpleLayer` test semantics)).
    Candidate pairs vs brute-force: 147,590 features → old 10,891,330,255 pairs per
    validator → new **92,669 (0.00085%) near-miss** / **61,637 (0.00057%) snap** candidates.
    Full 147,590 run now completes (vs intractable before); memory flat ~150 MB for validators,
    no chunking or tolerance change, no unrelated validator edits, no new dependency
    beyond existing Shapely/GeoPandas.
  - **Semantic preservation:** synthetic GeoDataFrame harness (5 seeds, 400 scattered fars) —
    fast-path ≡ brute-force reference on identical data; real OSM subsamples (Amman/Cyprus
    n=500/2000) — near 136/495/115/938 and snap 17/145/16/38 all **PASS** vs reference;
    all **175 tests pass**, fixtures validated (including multipart 55.6 m within 100 m).
  - Benchmark scaling (Riyadh subsamples, measured):
    10k: 49,995,000 → 9,768 (0.0195%) in 7.8/7.1 s; 25k: 312M → 23,866 (0.0076%) in 18.3/16.6 s;
    50k: 1.25B → 43,514 (0.0035%) in 35.3/35.1 s; 100k: 5B → 67,040 (0.0013%) —; 147,590: 10.89B →
    92,669 (0.00085%) / 61,637 (0.00057%) in 101.3/102.3 s isolated (203 s both), vs
    **old O(n²) never completed even Amman 7,857 (≈31M pairs) within >20 min**.
  - `country_runs.json` now has 12 entries (added `riyadh/gis_osm_waterways_free_1`);
    `baseline_optimized.json` records optimized fingerprints (fixtures + Amman 2,241/406
    in 6.2/5.7 s, Cyprus 6,234/392 in 10.2/10.1 s — vs old intractable).
  - Result is **public OSM waterways only**; still 🔴 excluded: private Oman mains,
    NRW/demand/loss. Wording stays tied to this dataset.

## Natural Earth 50m base-vector (public, see ne_ data)
Downloaded from the Natural Earth S3 backing store
(`naturalearth.s3.amazonaws.com`, public domain via Natural Earth), zips
`testzip()`-verified, stored under permanent
`Code-of-Earth\data\base_vector\` (+ `extracted\`). All layers EPSG:4326, 0
null-geom (except rivers has 1 null of 478), DBF==SHX==SHP consistent.

GeoQA `water_network` (rule 2026.03, status full):

| Layer | Features | Issues | Actionable | Severity | Note |
|---|---|---|---|---|---|
| `ne_50m_lakes` | 412 | **818** | 412 | 12 high + 400 med + 406 low | 12 duplicate_geometry (topology); 400 duplicate_vertex; 406 coord-precision (info) |
| `ne_50m_rivers_lake_centerlines` | 478 | **1,291** | 814 | 1 crit + 789 high + 24 med + 477 low | dominated by 426 line_dangle + 244 isolated_segment; 1 null_geometry |
| `ne_50m_admin_0_countries` | 242 | 242 | 0 | 242 low | all coord-precision informational |
| `ne_50m_geography_marine_polys` | 118 | 118 | 0 | 118 low | all coord-precision informational |

Interpretation: Natural Earth's 50m layers are **deliberately generalized** (low
precision), so the `coordinate_precision_not_fit_for_use` flags are expected
informational markers, not actionable defects. They add geospatial base-vector
breadth + a reproducible public testbed, but polygon boundary layers show no
actionable issues; the line waterway layer surfaces real topology anomalies even
at this coarse scale.

### CRWASH implication (ledger read-across, updated)
- Riyadh is the 5th public OSM water-region evidence case. Its **water_a polygon
  layer again shows few topology anomalies (8 duplicate-geometry issues)**, in
  line with the 4-country pattern where polygon layers are near-clean while
  **line (waterways) layers dominate the actionable topology issue load**.
- Natural Earth base-vector layers are supporting/breadth context only, not a
  replacement for the OSM water-network evidence; no claim is made from them
  beyond what the (public, SHA-linked) GeoQA runs show.
- Still 🔴 excluded: private Oman mains, DMA CSVs, `test_fieldwork.csv`, and any
  NRW/demand/loss quantification (not modeled). Wording stays tied to these
  public datasets.
