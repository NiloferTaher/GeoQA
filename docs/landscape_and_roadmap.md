# GIS QA Landscape — Coverage Analysis and Implementation Plan

**Prepared:** 2026-10-09 · **For:** GeoQA `tool-core-2026-10` · **Nothing here is implemented yet**

Every claim below is sourced. Where a source could not be retrieved, it is marked
**[UNVERIFIED]** rather than filled in. Several widely-repeated API names turned out
not to exist; those are recorded in §6 because they are actively misleading.

---

## 0. Two corrections before anything else

### 0.1 GISAssert does not exist

Verified three independent ways:

| Check | Endpoint | Result |
|---|---|---|
| GitHub repo search | `api.github.com/search/repositories?q=gisassert` | `total_count: 0` |
| PyPI | `pypi.org/pypi/gisassert/json` | HTTP 404 |
| Web search | `"GISAssert" spatial data quality` | no such tool |

Do not design around it. If it was described to you as an existing library, that
description was wrong.

### 0.2 GeoLint exists but is thin, and the name is heavily squatted

| Project | What | Activity |
|---|---|---|
| **`CONFUZ3/geolint`** — the relevant one | Python QA/lint toolkit: CLI, Streamlit, SARIF, pre-commit hook | MIT, v0.2.1, released 2026-06-22, **0 GitHub stars** |
| `bl-dpt/geolint` | Validates **Ordnance Survey GB/NI GML/NTF only** | Apache-2.0, archived 2014 |
| `VADERASU/geolinter` | Lints **choropleth visualisations**, not geometry (IEEE TVCG 2023) | last push 2024 |
| `jajego/geolint` | ESLint-style GeoJSON linter | unrelated |

`CONFUZ3/geolint` is worth borrowing *from* — it is small and readable, and its
rule names are a useful cross-check on our own. It is not a threat and not a
dependency.

---

## 1. The most important architectural finding

**ISO 19157 does not enumerate defect types.** It defines *what to measure*
(characteristics) and Annex C defines *measures*. There is no clause mapping
"dangles" or "slivers" or "overshoots" onto an ISO characteristic.

The defect vocabulary lives in **implementations**, not in the standard:

| Source | What it contributes |
|---|---|
| **OGC Simple Features** | Authoritative *polygon* invalidity semantics |
| **GEOS / JTS** (`TopologyValidationError`) | 12 named validity error codes |
| **PostGIS `ValidateTopology()`** | 14 named errors on an explicit topogeometry model |
| **QGIS Geometry Checker** | 22 checks + 13 Topology Checker rules |
| **ArcGIS Data Reviewer** | ~50 checks across 8 categories |

**Implication for GeoQA:** the ISO mapping on our 49 problems is correct and worth
keeping as the *reporting* framework. But the *rule vocabulary* is borrowed by
necessity. That is the same position QGIS and PostGIS occupy, and it should be
stated plainly rather than implied.

### 1.1 ISO 19157-1:2023 changed the thing that matters most for a rule engine

Confirmed to exist (ISO catalogue #78900, 2023-04-19, supersedes 19157:2013).

The six quality categories are **structurally unchanged** — no re-mapping needed.
What changed:

1. **`thematic accuracy` → `thematic quality`** (8.3.6).
2. **New clause 8.4 "Extending the data quality information model."** ISO/TC 211:
   *"ISO 19157-1 is now extensible, which provides producers with the capability to
   define their own domain specific quality descriptors and measures… while
   providing an ISO 19157-1 compliant assurance for their quality metadata."*

   **This is the single most consequential change for GeoQA.** Our domain profiles
   (`water_network`, `boundaries`, `land_use`, `spectral`) can now be presented as
   conformant extensions rather than as a private taxonomy bolted onto a standard.
   That is a citation-strength and positioning win, and it is cheap.
3. Annex C measure dictionary moved out to **ISO 19157-3** (a machine-actionable
   register). **[UNVERIFIED]** whether 19157-3 published — expected 2025, not checked.
4. One element dropped — the footnote attributing this is ambiguous. **[UNVERIFIED]**
   which. Candidates on structural grounds: metaquality (lineage, usability).

---

## 2. The gap that actually matters: GEOS cannot load a whole class of broken geometry

This is the most actionable finding in the entire survey.

QGIS's internal validator catches things **GEOS explicitly will not**:

| QGIS internal check | Error string | GEOS status |
|---|---|---|
| Ring not closed | `ring %1 not closed` | **cannot even load it** |
| Ring has < 4 points | `ring %1 with less than four points` | **cannot even load it** |
| Ring not closed in Z only | `ring %1 not closed, Z mismatch` | no equivalent |
| Duplicate consecutive nodes | `line %1 contains %n duplicate node(s)…` | **permitted** — GEOS explicitly allows repeated points |
| Segment self-intersection | `segments %1 and %2 of line %3 intersect` | *valid*, but non-simple |
| Polygon with no rings | `Polygon %1 has no rings` | no equivalent |
| Unknown geometry type | `Unknown geometry type %1` | no equivalent |

Both the duplicate-node and segment-intersection checks use epsilon **1E-8**.

**Two consequences:**

1. GeoQA currently cannot report these at all, because Shapely raises on them
   before any validator runs. A dataset containing an unclosed ring will either
   crash the load or be silently dropped — and we have no idea which, because we
   have never tested it.
2. OGC is explicit that **"non-simple (self-intersecting) lines are valid"** — so a
   bowtie LineString is OGC-valid. QGIS flags it as a network-model defect. Our
   reports must distinguish these, not conflate them.

**Verified against our own stack:** QGIS's *Fix geometries* is a thin wrapper over
`GEOSMakeValid`. So `QgsGeometry.makeValid` ≡ `shapely.make_valid(method="linework")`.
There is nothing to replicate there.

---

## 3. Implementation candidates

Columns: **Effort** (S ≤ half day, M ≈ 1 day, L multi-day) · **Value** · **Risk** ·
**Shapely 2.1.2 / GDAL 3.11.4 API actually used**

### Tier 1 — Cheap, high value, no meaningful risk

| # | Check | How | E | Value | Risk |
|---|---|---|---|---|---|
| 1 | **Unclosed ring** | `geom.exterior.is_ring` → `False`. *Must run before* GEOS validity, because GEOS cannot load the geometry | S | **Critical** — currently unreachable | none |
| 2 | **Ring with < 4 points** | `len(exterior.coords) < 4` | S | High | none |
| 3 | **Z-mismatch on ring closure** | compare `coords[0]` vs `coords[-1]` across x, y **and z** | S | Medium — QGIS has it | none |
| 4 | **Duplicate node** | detect on `shapely.get_coordinates(g)`, consecutive-pair distance < 1e-8. Repair via `shapely.remove_repeated_points(g, tolerance=1e-8)` | S | **High** — GEOS permits these, so nothing else catches them | none |
| 5 | **Polygon sliver** | thinness = `area(minimum_rotated_rectangle) / area(polygon)`. QGIS default `MAX_THINNESS=20` | S | High — ArcGIS, QGIS and GeoLint all have it; we don't | none |
| 6 | **Cutbacks / minimum angle** | vectorised `atan2` over `get_coordinates`; QGIS `minAngle` default 0°, osmlint uses 30°, JOSM 45° | S | High — classic digitising error | none |
| 7 | **Minimal segment length** | explode segments, `shapely.length` per segment | S | Medium — QGIS `Minimal segment length` | none |
| 8 | **Minimal polygon area** | `shapely.area` | S | Medium | none |
| 9 | **Part count outside range** | `shapely.get_num_geometries(g)`; ArcGIS `Evaluate Part Count` | S | Medium | none |
| 10 | **Vertex count outside range** | `shapely.get_num_coordinates(g)`; ArcGIS `Evaluate Vertex Count` | S | Low–medium | none |
| 11 | **Polyline closes on self** | endpoint coords equal; ArcGIS `Polyline or Path Closes on Self` | S | Medium | none |

### Tier 2 — The "unnecessary" checks (ArcGIS's best idea, nobody else has it)

| # | Check | How | E | Value | Risk |
|---|---|---|---|---|---|
| 12 | **Unnecessary nodes** | two polylines share a node **and** all editable attributes match → they should be one feature | M | **High** — a real data-management error no geometry validator catches | needs attribute-column config |
| 13 | **Unnecessary polygon boundaries** | two polygons share a boundary **and** all attributes match → should be dissolved | M | **High** — same logic, polygon case | same |

These are the strongest *conceptual* addition. ArcGIS's `Duplicate Feature` check
folds this in. Nobody in the open-source world appears to do it, and it is the
check that catches "the same asset modelled twice".

### Tier 3 — Coverage checks, largely solved by Shapely 2.1

| # | Check | How | E | Value | Risk |
|---|---|---|---|---|---|
| 14 | **Gap between polygons** | `shapely.coverage_is_valid(gdf.geometry, gap_width=…)`, then `shapely.coverage_invalid_edges(gdf.geometry)` | S–M | **High** — administrative-boundary integrity | `gap_width` is in map units, so CRS discipline is mandatory |
| 15 | **Missing vertex / coverage noding** | same two functions | S | High | same |
| 16 | **Partial overlap** | `coverage_invalid_edges`; QGIS uses `MIN_OVERLAP_AREA` | S | High | same |

Shapely 2.1.0 added the coverage functions and we run 2.1.2, so items 14–16 are
close to free — this was the part the survey expected to be hardest.

### Tier 4 — Schema validation (nobody else does this well)

| # | Check | How | E | Value | Risk |
|---|---|---|---|---|---|
| 17 | **Not-null violations** | `OGR_F_Validate(hFeat, OGR_F_VAL_NULL, TRUE)` | S | **High** | needs `osgeo`; **not exposed in pyogrio** |
| 18 | **String width overflow** | `OGR_F_VAL_WIDTH` | S | High — truncated fields are silent corruption | same |
| 19 | **Geometry-column type violation** | `OGR_F_VAL_GEOM_TYPE` | S | Medium | same |
| 20 | **Missing CRS** | `gdf.crs is None` | S | **High** — GDAL treats a missing/unknown CRS as `None` **with no error** | none |

**Neither QGIS nor Shapely checks any of 17–19.** ArcGIS checks all of them, via
`Domain`, `Subtype`, `Unique Field Value`, `Regular Expression`. This is a genuine
white-space opportunity.

Caveat: item 20 matters more than it looks. GDAL silently yields a layer with **no
CRS and no warning** when a `.prj` is unrecognised. Separately, axis order can
silently swap x/y for authority-defined CRSs unless `OAMS_TRADITIONAL_GIS_ORDER`
is set.

### Tier 5 — Network checks worth considering

| # | Check | How | E | Value | Risk |
|---|---|---|---|---|---|
| 21 | **Orphan** | feature not connected to any other; ArcGIS `Orphan`, KeepRight *floating islands* | M | High — overlaps our triage | duplicates `isolated_network_segment` |
| 22 | **Valency / node degree rules** | ArcGIS `Valency`, `RoundaboutValenceCheck`, `ValenceOneImportantRoadCheck` | M–L | Medium–high for routing | needs domain semantics; high false-positive risk without them |
| 23 | **Disconnected components** | STRtree + union-find over endpoint adjacency | M | High — our triage clusters, this counts components | none |
| 24 | **Z-value checks** | ArcGIS has a Z-value category | M | Low for most GIS work | niche |

**Skip:** ArcGIS Event checks (linear referencing), Monotonicity, Nonlinear Segment.
These are transport-model specific and would pad the engine with rules nothing uses.

---

## 4. The reference check-lists, for gap analysis

### QGIS Geometry Checker — all 22, with our status

| QGIS check | Shapely/GEOS equivalent | Status |
|---|---|---|
| Is Valid | `shapely.is_valid` | **have** |
| Self intersection (polygon) | `shapely.is_valid` | **have** |
| Self intersection (line) | `shapely.is_simple` | **have** |
| **Segment self-intersection (internal engine)** | — | **MISSING** — O(n²) segment pairing |
| **Duplicate node** | — | **MISSING** — GEOS permits these |
| **Polygon with < 3 nodes** | trivial | **MISSING** |
| **Ring not closed** | trivial, but must precede GEOS | **MISSING** |
| Polygon with hole | legal by design | policy |
| Multipart with one part | trivial | **MISSING** |
| Dangle | endpoint-within-ε | **have** (triage) |
| Minimal segment length | trivial | **MISSING** |
| Minimal angle | trivial | **MISSING** |
| Minimal area | trivial | **MISSING** |
| Duplicate | `shapely.equals_exact` + STRtree | **have** (`duplicate_geometry_same_layer`) |
| Geometry type | trivial | **MISSING** |
| Point not covered by line | `shapely.covered_by` | **MISSING** |
| Point not in polygon | `shapely.intersects` | **MISSING** |
| Within | `shapely.within` | **have** (`feature_within_feature`) |
| Intersection (line self) | `shapely.is_simple` | **have** |
| Intersection (vs other layer) | `STRtree.query(predicate="intersects")` | **have** |
| Polygon does not follow boundaries | `shapely.symmetric_difference` | **MISSING** |
| Overlap | `coverage_is_valid` | partial |
| Gap | `coverage_invalid_edges` | **MISSING** |
| Missing Vertex | `coverage_is_valid` | **MISSING** |

QGIS **Topology Checker** adds 13 layer-level rules, including `must not have
pseudos` (pseudo-node = exactly two line parts meeting end to end) which we do not
have. Note: QGIS Topology Checker is GUI-only C++ with no Python API and no
Processing algorithm.

### ArcGIS Data Reviewer — 8 categories

Attribute: Domain · Duplicate Row · Query Attributes · Regular Expression ·
Relationship · Subtype · Table to Table Attribute · Unique Field Value
Event: Event on Event · Find Orphan Events · Find Event Gaps · Find Event Overlaps · Invalid Event Measures
Feature integrity: Check Geometry · Cutbacks · Duplicate Vertex · Evaluate Part Count · Evaluate Vertex Count · Nonlinear Segment
Polygon: Evaluate Polygon Perimeter and Area · Find Polygons with Holes · Polygon Gap is Sliver · Polygon Overlap is Sliver · Polygon Sliver · Unclosed Polygon · Unnecessary Polygon Boundaries
Polyline: Evaluate Polyline Length · Find Dangles · Monotonicity · Orphan · Polyline or Path Closes on Self · Unnecessary Nodes
Spatial relationship: Composite · Duplicate Feature · Evaluate Intersection Count · Feature on Feature · Valency
Plus Duplicate Geometry and Z-value categories.

**Three ArcGIS ideas worth stealing outright:**
- **Unnecessary Nodes / Unnecessary Polygon Boundaries** — shared geometry *and*
  matching attributes means the features should be one. Nobody open-source does this.
- **Duplicate Vertex** with an explicit tolerance, distinct from duplicate geometry.
- **Domain / Subtype / Regular Expression** as first-class checks rather than
  bolt-ons.

---

## 5. Deliberately not doing

| Idea | Why not |
|---|---|
| Mimic ArcGIS or QGIS check **names** | Creates a false impression of parity and invites "why is your `Find Dangles` different?" Keep our own vocabulary, cross-reference in docs |
| `make_valid(method="structure")` as a default repair | **Not idempotent on valid input.** GDAL documents that already-valid geometries may be altered ("duplicated point removal, change in ring winding order") |
| Auto-strip lower-dimensional sub-geometries | `removeLowerDimensionSubGeoms` **deletes data** — `GEOMETRYCOLLECTION(POLYGON, LINESTRING)` → `POLYGON`. GDAL's `ogr2ogr -makevalid` does this by default; QGIS does not. Must be an explicit, opt-in choice |
| Port Osmose's ~200 analyzers | Wrong shape: Osmose is OSM-specific and needs a full-history PBF. Our per-rule engine would not fit it |
| ArcGIS Event / linear-referencing checks | Domain-specific, low reuse |
| ML-based scoring | We are deterministic by design; a confidence score from a model undermines that |

---

## 6. APIs that do NOT exist — recorded because they are actively misleading

Anyone (including me, previously) may cite these. They are wrong.

| Non-existent API | Reality |
|---|---|
| `OGR_G_ValidateGeometry` | Does not exist. Use `OGR_G_IsValid` + `OGR_G_GetInvalidityReason` |
| `OGRGeometry::MakeValidCurve` | Does not exist in GDAL 3.11 or 3.13 |
| GEOS `UndoMakeValid` | GEOS 3.7-rc1 prerelease only, removed before 3.8 final |
| `OGR_G_IsValidReason` | Commented out in `ogr_api.h` — dead declaration |
| `IsValid()` returning `OGRErr` codes | Wrong model. Returns `OGRBoolean`; reasons are GEOS strings, not an enum |
| QGIS error vs warning tiers in Geometry Checker | Do not exist. Flat error list, with per-check *resolution methods* instead |
| `ogrinfo` validity flag | No validity option in `ogrinfo` at all |
| `gdalinfo -checksum` for vectors | Raster/band only |
| `gdal vector check-geometry` | **GDAL 3.12+.** We run 3.11.4 |
| `OGRGeometry::IsValid(&reason)` | 3.13+. On 3.11.4 use `OGR_G_GetInvalidityReason` |

**Silent-behaviour traps, all verified:**

1. `ogr2ogr -makevalid` = `MakeValid()` **then** `removeLowerDimensionSubGeoms()`.
   No `--keep-lower-dim` equivalent.
2. `KEEP_COLLAPSED` is **only honoured** when `METHOD=STRUCTURE`; silently ignored
   for `LINEWORK`.
3. **GDAL 3.10 changed type preservation** — a 3.9 build returns a different
   geometry type for identical input.
4. `IsValid()` returns **FALSE if OGR was built without GEOS**. Check
   `OGRGeometryFactory::haveGEOS()` if shipping wheels.
5. GEOS `IsValidOp` **throws** on SQL/MM curved types: `"Curved types not supported
   in IsValidOp."`

---

## 7. Recommended sequence

Ordered by value-per-hour, with the caveat that items 1–4 are **prerequisites**,
not enhancements.

**Phase 1 — make the engine robust (do these first)**
1. Ring closure + <4 points, detected *before* any GEOS call
2. Duplicate node detection
3. Graceful handling when GEOS cannot load a geometry at all — **we have never
   tested this path**, and it is the single largest unknown
4. Tests using deliberately malformed input

**Phase 2 — cheap rule wins**
5. Sliver, cutbacks, segment length, area, part count, vertex count, closes-on-self

**Phase 3 — coverage**
6. Gap, missing vertex, partial overlap via the Shapely 2.1 coverage functions

**Phase 4 — the differentiated checks**
7. Unnecessary nodes / unnecessary polygon boundaries
8. `OGR_F_Validate` schema checks; missing-CRS check

**Phase 5 — positioning**
9. Map the existing profiles onto **ISO 19157-1:2023 clause 8.4** as declared
   extensions. Cheap, and materially strengthens the standards story.

## 8. Sources

ISO 19157-1:2023 · `https://www.iso.org/standard/78900.html` ·
`https://committee.iso.org/sites/tc211/home/projects/projects---complete-list/iso-19157-1.html` ·
ISO/TC 211 2023 announcement (extensibility, 19157-3 register) ·
OGC SFA `https://portal.ogc.org/files/?artifact_id=25355` · PostGIS geometry
validation `https://postgis.net/docs/using_postgis_dbmanagement.html` ·
`https://postgis.net/docs/ValidateTopology.html` · GEOS
`TopologyValidationError.h` · QGIS 3.44 source
`src/analysis/vector/geometry_checker/`, `src/core/qgsgeometryvalidator.cpp`,
`src/plugins/topology/` · GDAL `ogr/ogr_api.h`, `ogr/ogr_geometry.h`,
`ogr/ogrgeometry.cpp` (release/3.11) · ArcGIS Data Reviewer checks
`https://doc.esri.com/en/arcgis-pro/latest/help/data/validating-data/an-overview-of-data-reviewer-checks-in-arcgis-pro.html` ·
Barron, Neis & Zipf 2014 *T GIS* 18(6) 877–895 `https://doi.org/10.1111/tgis.12073` ·
Guptill & Morrison (eds) 1995 *Elements of Spatial Data Quality* ·
`CONFUZ3/geolint` `https://github.com/CONFUZ3/geolint`