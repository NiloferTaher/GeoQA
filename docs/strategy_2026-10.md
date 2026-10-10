# GeoQA — Competitive Landscape, Water-Network Extension, and Scale Architecture

**Prepared:** 2026-10-09 · **For:** `tool-core-2026-10` · **Decisions, not just research**

---

## 1. The benchmark you remember does not exist — and that is an opportunity

You asked whether GeoQA was benchmarked against comparable tools. **I searched for a
head-to-head comparison of geometry validation tools and could not find one.** No
academic paper, benchmark suite, or comparison article evaluating QGIS Geometry
Checker vs ArcGIS Data Reviewer vs Osmose vs JOSM vs KeepRight vs GEOS/JTS/GeoTools.

That is a publishable gap, not just a marketing one.

### 1.1 But there ARE close competitors, and one is a near-twin

| Tool | What | Activity |
|---|---|---|
| **`roy232355/geoqa`** — **QGIS plugin, "GeoQA – GIS Data Quality Auditor", v1.3.4, GPLv3** | Rules **G001–G005** (geometry), **C001–C002** (CRS), **A001–A007** (attribute), **T001–T004** (topology); A–F scoring; HTML report; auto-fix; redlines layer; 32 offline tests; published to QGIS Plugin Repo | 0★, pushed 2026-07 |
| `geojson-validator` 0.7.0 | Validates **and fixes** GeoJSON: unclosed rings, winding, self-intersection, antimeridian crossing. JSON-path + feature index. Streamlit demo | 2026-08 |
| Osmose | **200+ rules**, frontend/backend split, **documented JSON API v0.3**. MapCSS + Python + PostGIS analysers | 100★, GPL-3.0, 108 contributors |
| QGIS Data Reviewer plugin | "modeled after ArcGIS Data Reviewer", background runs, status mgmt, report export | 1.0.2 |
| `geoutils` 0.2.5 | `is_valid` / `make_valid` / CRS checks — but an **analysis wrapper**, no rule engine, no report | 113★, Apache-2.0 |
| gvSIG Topology Framework | Mature rule catalogue from GSoC 2019/2020 | OSGeo |

**`roy232355/geoqa` is the one that matters.** Same name, same problem, QGIS-hosted,
GPLv3. It is behind (no spectral, no reports-as-data, no water semantics, no
triage), but it exists and is published in the QGIS Plugin Repository.

The nearest thing to a benchmark table that does exist is the OSM community's
validator comparison — `https://wiki.openstreetmap.org/wiki/Validator`. It is
OSM-tag-specific but it is a good structural model for our own positioning.

### 1.2 Dead ends worth knowing

- **`pygeos` is dead** (v0.14, 2022-12-12). Merged into Shapely 2.0. Do not build on it.
- **`fiona` is dormant** (last release 2024-09-16).
- `geopandas`, `pyshp` — **I/O only, no validation**.
- `pandera` / `great-expectations` — real rule engines with JSON reports, but
  **tabular only, no geometry**.

**Nothing in Python does a broad geometry + topology + attribute sweep with a
report.** That is the whitespace.

---

## 2. Naming — `geoqa` is taken, and you have a functional twin under it

### 2.1 PyPI is blocked

| Field | Value |
|---|---|
| Name | `geoqa` |
| Version | 0.1.0, uploaded **2026-02-11**, never updated |
| Summary | *"GeoQA: A Python package for geospatial data quality assessment and interactive profiling"* |
| Owner | `AmmarYasser455` / GitHub `AmmarYasser455/geoqa` (MIT, 3★) |
| Dependencies | geopandas, shapely, **folium**, matplotlib, **jinja2**, click, rich, branca |

**This is a direct functional collision** — same domain, same stack, and the same
"interactive profiling report" idea. Its README badge points at `github.com/geoqa/geoqa`
which does not exist. PyPI names cannot be reclaimed while the package exists.

### 2.2 GitHub is crowded

14 exact-name repos. Two matter:
- `chen-judge/GeoQA` — **77★**, ACL 2021 geometric QA benchmark. It is **NLP, not GIS**,
  and it will dominate search results regardless.
- `roy232355/geoqa` — the QGIS plugin above.

Plus your own `NiloferTaher/GeoQA` (Apache-2.0).

### 2.3 Options

| Name | PyPI | GitHub exact | Verdict |
|---|---|---|---|
| `geoqa` | **TAKEN** | 14 | blocked |
| **`geoqa-core`** | free | **0** | clean; keeps the family |
| **`geoqa-tools`** | free | **0** | clean |
| **`geoqa-cli`** / `geoqa-py` | free | **0** | clean |
| **`geosure`** | free | **0** | cleanest standalone name |
| `geovalidate` | free | 3 | **avoid** — active maintainer, May 2026 |
| `geoguard` | free | 76 | **avoid** — NASA-IMPACT, Apache-2.0 |

**Recommendation:** do **not** rename the GitHub repo now. It costs you nothing and
you already have the name, the star history and the Vercel deployment behind it.
Decide the **PyPI distribution name** at publish time — `geoqa-core` keeps the family
recognisable and costs one string.

---

## 3. Water networks — the genuine white space

### 3.1 What already exists

| Package | Version | License | Status |
|---|---|---|---|
| **`wntr`** | **1.5.0**, 2026-07 | **Revised BSD** | **Actively maintained**, commit 2026-09-08 |
| `epyt` | 2.3.5.2 | **EUPL-1.2 (copyleft)** | active — **licensing problem** |
| `epanet-utils` | 0.3.2, 2026-10 | MIT | fresh but 3★, immature |
| `epanet` / `epanet2` / `epanettools` | — | GPLv3 | abandoned (2014/2018) |

EPANET itself: 2.2.0 (2020-07, EPA, public domain); OpenWaterAnalytics **2.3.5**
(2026-02, MIT, actively developed). **EPANET 3.0 does not exist** — the line went
2.2 → 2.3 → 2.3.5.

**Four names in my earlier brief do not exist:** `epanet-python`, `pyepanet`,
`epanet-toolkit`, `epanet-python-devkit` all 404 on PyPI. (`pyepanet` was the
pre-0.1.2 name; WNTR's own changelog records *"Removed pyepanet package."*)

### 3.2 The three properties that make WNTR the right dependency

1. **`wntr.network.read_inpfile()` is pure Python.** Verified: `InpFile.read()`
   contains zero ctypes/toolkit calls. **A validation tool can parse `.inp` with no
   DLL, no ctypes, no platform matrix, fully deterministic.** That is a big deal.
2. **It bundles the engine for win-x64 / linux-x64 / mac-x64 / mac-arm.** No Linux
   ARM branch — `toolkit.py:23-30` falls through to x64.
3. **Revised BSD is clean.** Avoid EPyT (EUPL copyleft) and the GPLv3 dead packages.

### 3.3 What WNTR does NOT have

- **No NRW / water balance / leakage accounting.** Grepped: zero hits. The only
  leakage API is physics-based (`Junction.add_leak()` — it *simulates* a leak by
  emitting a demand; it performs no accounting).
- **No validation capability whatsoever.** `Registry.orphaned()` catches dangling
  in-memory references, not imported-data topology. `check_valves()` is a
  misnamed *generator yielding pipes with a check valve* — it validates nothing.
- **No sensitivity analysis, ever.** `wntr/sensitivity.py` is absent at tags 0.2.3,
  0.5.0, 1.0.0, 1.3.2 and 1.5.0.

### 3.4 The genuine white space — three separate gaps

**Gap A — no NRW package exists.** WNTR, EPANET, and the whole Python ecosystem
have nothing. Everything is web calculators or Excel: AWWA Free Water Audit
Software v6.0, World Bank WB-EasyCalc, IWA manuals.

**Gap B — no machine-readable NRW schema exists.** Every authoritative artefact is
Excel or PDF. AWWA M36 (5th ed. 2024) is **paywalled at US$199**.

**Gap C — no EPANET `.inp` linter exists.** Not in WNTR, not in EPANET, not in the
community.

Framework for what we'd implement (IWA/AWWA Level 2):
```
System Input Volume = Revenue Water + NRW
NRW = Unbilled Authorised Consumption + Water Losses
Water Losses = Apparent Losses + Real Losses      <- DERIVED BY ELIMINATION, never entered
Real Losses (CARL) = Water Losses - Apparent Losses
NRW % = (unbilled metered + unbilled unmetered + real losses) / System Input Volume
UARL (Lambert) = (18 x Lm + 0.5 x Nc) x P
```
The critical modelling rule: **Water Losses and Real Losses are derived by
elimination, never entered by the auditor.** An implementation that lets a user type
them in is wrong.

⚠️ **"IWA/PNIS" does not exist.** No standard or body by that name. The nearest real
referent is the IWA *Performance Indicators for Water Supply Services* manual
(3rd ed. 2016). Do not cite "PNIS" without checking the original document.

### 3.5 What to wrap rather than rebuild

```python
wntr.network.to_graph(wn)                              # NetworkX for all connectivity work
wntr.metrics.topographic.valve_segments(G, valve_layer)   # ISOLATED VALVES - combinatorial, nobody does this in Python
wntr.metrics.topographic.valve_segment_attributes(...)
wntr.metrics.topographic.terminal_nodes(G) / bridges(G)
wntr.metrics.topographic.algebraic_connectivity(G) / spectral_gap(G)
wntr.metrics.hydraulic.expected_demand(wn)             # negative & zero demand
wntr.network.valid_gis_names(wn, ...)                  # GIS ID/name conformance
```

### 3.6 Water-specific defects a generic GIS check cannot catch

**Structural / graph** — geometry is valid but hydraulically meaningless:
disconnected components · orphaned pipes · hydraulic dead ends · unintended loops ·
**isolated valves** (a valve that on closure strands a segment — combinatorial, not geometric) · connectivity redundancy

**Attribute / semantic:**
missing elevation on junctions → wrong pressure and wrong PRV behaviour · pumps without energy curves (EPANET 216/217) · tanks with init level < min or > max · negative demands · duplicate IDs (EPANET 215) · self-loops · **PRV/PSV/PBV illegally on a reservoir or tank** (EPANET 219)

**Design intent:**
air valves absent at local elevation maxima · check valves with wrong orientation · pumps pulling from a disconnected node

**Hydraulic** (require running the model):
negative pressure anywhere · velocity above threshold · headloss/km above threshold · pumps outside curve range · dry-running · **mass-balance error** — EPANET reports this directly in the `.rpt`

**Free shortcut:** run `EpanetSimulator`, parse the `.rpt` for 200-series codes
(201 syntax, 215 duplicate IDs, 216 undefined pump energy, 217 invalid pump energy,
219 illegal valve connection) plus the mass-balance error. That is real coverage for
almost nothing.

⚠️ **Scope boundary:** the hydraulic group requires simulation, which makes
GeoQA's "deterministic validation engine" gain an optional simulation stage. Groups
1–3 are pure-Python/NetworkX and stay fast and deterministic. Keep them separable.

---

## 4. Chunking — yes, possible, but naive chunking will produce false positives

This is the question with a trap in it, so the trap comes first.

### 4.1 Why naive chunking breaks GeoQA

Several validators are **inherently global**. They need the whole layer to compute a
correct answer:

| Validator | What it needs | What chunking does |
|---|---|---|
| `line_dangle` | endpoint degree across the **entire** layer | endpoint at a chunk edge looks degree-1 → **false dangle** |
| `polygon_overlap_same_layer` | all pairs | overlap straddling the boundary is missed |
| `duplicate_geometry_same_layer` | all geometries | duplicates across the boundary are missed |
| `polygon_gap_same_layer` | `unary_union` of the whole layer | gaps at the boundary are fabricated |
| endpoint triage clustering | global adjacency | clusters fragment at boundaries |

**Chunk a dangle network naively and you manufacture tens of thousands of false
positives at every internal boundary.** That is precisely the failure mode we are
already fighting with the OSM waterways.

### 4.2 The correct pattern: buffered chunks with halo discard

Standard distributed-geometry processing (this is what Dask-GeoPandas does):

```
1. Partition   : tile the extent into chunks on a regular grid
2. Halo        : read each chunk EXPANDED by a margin M
3. Validate    : run validators on the expanded chunk
4. Discard     : drop findings whose anchor falls inside the margin
5. Dedupe      : key surviving findings by global (feature_id, rule) and dedupe
```

M must be ≥ the largest distance any validator reasons over — the snap tolerance, the
gap width, the overlap-area threshold. For global validators (degree, union) there is
no finite M; those must either be computed once globally, or replaced by an
equivalent local formulation.

**Practical rule:** partition only the validators that are provably local. Anything
touching global degree or a whole-layer union runs once, globally, and the chunked
pass handles the rest. For 132,965 features a single global pass costs seconds
(our triage ran in 24 s), so **the win only appears well above ~1M features.**

### 4.3 Where GeoParquet and DuckDB genuinely help

Not for chunking per se — for **I/O and spatial filtering**:

| Tool | Use |
|---|---|
| **GeoParquet** | Columnar vector storage with a spatial partition column. Hive-style partitioning by a coarse grid cell (`x=12&y=34`) makes chunks *cohesive*, which maximises halo efficiency. The right intermediate format. |
| **DuckDB + spatial extension** | Reads GeoParquet natively, has spatial predicates and predicates pushdown. Lets you answer "which features are in this tile" in-database without materialising a GeoDataFrame. Excellent for driving the partition step. |

**Suggested architecture:**

```sql
-- DuckDB: decide the tiling from data, not from guesswork
SELECT floor(ST_XMin/50000) AS tx, floor(ST_YMin/50000) AS ty,
       count(*) AS n, min(id) AS id_lo, max(id) AS id_hi
FROM read_geo_parquet('layer.parquet')
GROUP BY 1,2 ORDER BY 3 DESC;
```
Then for each occupied tile, read `layer.parquet` with a **halo predicate**, validate,
discard the margin, dedupe on `id`.

This is genuinely better than the current `gpd.read_file` + full-layer approach:
it skips empty space, gives balanced work units, and produces reproducible
provenance (which tile, which halo, which rules).

### 4.4 Recommendation

**Do not build this now.** It is an optimisation for a scale we have not reached —
the largest layer tested is 132,965 features and validates in 24 s. Build it when a
real dataset forces the issue. But **write the validators to be chunk-safe now**:
keep feature identity global, never trust a row index across chunks, and make
tolerances explicit parameters. Retrofitting that later is much harder than
designing for it.

---

## 5. The website generator — yes, and it is the highest personal-value item

You described: generate a local review website with a basemap, drop a flawed dataset
in, see the problems on a map. That is buildable, and it is genuinely useful to your
own research, not just a demo.

### 5.1 The 2026 constraint you need to know

**MapLibre GL JS v6 is ESM-only, WebGL2-only, and requires a separate worker file.**

From the v6 changelog: *"The UMD bundles (`maplibre-gl.js`, `maplibre-gl-csp.js`)
are no longer published… Consumers using `<script src="...maplibre-gl.js">` must
switch to `<script type="module">`."* And WebGL1 support is dropped (Safari 15+,
Chrome 56+, Firefox 51+).

**There is also no MapLibre static-image API.** Static images are proprietary
(Mapbox Static Images, MapTiler, Stadia).

So "inline MapLibre into one HTML file" **no longer works**, and was never going to
give you server-side tiles.

### 5.2 Stack options

| Stack | Self-contained | Vector layers | Filtering | Notes |
|---|---|---|---|---|
| **Plotly** `to_html(include_plotlyjs=True)` | **yes, truly** | ✅ | legend clicks | **Best fit.** And `plotly.js` v4.0.0 (2026-08-24) **removed all Mapbox traces** — every map trace now renders through **MapLibre GL v6**. Leaflet-free, MapLibre-native. |
| **Folium** 0.20.0 | CDN by default | ✅ | LayerControl only | 7.4k★, active; 1.0.0rc1 in flight. But it is Leaflet + `branca` macro elements — **not a templating system**. Limited looping, CDN-coupled, Canvas renderer struggles with large feature counts. |
| Pydeck `html_renderer` | CDN | ✅ | ✅ | GPU layers, pickable |
| Panel / Holoviews / ipyleaflet | **no** | — | — | need a Jupyter runtime |
| Hand-rolled Vite + React + MapLibre | ✅ via your own build | ✅ | ✅ custom | **Highest ceiling** — you already run exactly this stack for Tanager |

### 5.3 What I'd build

Two tiers, because they serve different purposes:

**Tier 1 — `geoqa.report.build_site(report, out_dir)`. Pure Python, one command,
self-contained HTML.** Uses Plotly's MapLibre-v6 rendering with an embedded
GeoJSON issue layer. Works with no build step, no npm, no server. This is what you
want when you are tired of rebuilding maps: one call, open the file, look at it.
Default basemap, but the basemap source is a parameter.

**Tier 2 — `geoqa.report.emit_bundle(...)`. Python emits JSON + issue GeoJSON; your
existing Vite/React stack renders it.** Same data, the cinematic Tanager treatment.
This is the Lindwood conference artefact.

Tier 1 is small and unblocks your daily work. Tier 2 is the public face.

### 5.4 The design decisions that matter

- **Never write raw data to a shared HTML by default.** Findings + geometry only, and
  make the "include full geometry" flag explicit. Given your constraint about
  confidential datasets, that flag should be opt-in and loud.
- **Every finding needs a stable global identity** — `issue_id` — so the same finding
  can be deep-linked, diffed across runs, and referenced in a response letter. You
  already emit a 16-char SHA-1 `issue_id`. Use it as the primary key everywhere.
- **Severity must be visible on the map**, not just in a table.
- **Ship a "bad bundle"** — a deliberately flawed dataset with known findings — as
  the built-in demo. That makes the tool teach without you writing docs.

---

## 6. Recommended build order

Given that "2 days" has become "make it genuinely unique," and that the paper still
has to happen, here is the honest ordering.

**Do first — these are prerequisites, not features:**
1. Ring closure + <4 points detected **before** GEOS (GEOS cannot load them)
2. Graceful handling when GEOS cannot load a geometry — **never tested**
3. Water-network semantic checks (§3.6, groups 1–3). **This is the actual
   differentiation** and nothing else in the ecosystem has it.
4. `geoqa.report.build_site()` — Tier 1. Your daily productivity win.

**Then:** the Tier 1–3 GIS rule sweep from `landscape_and_roadmap.md`; the companion
node resolution and triage work already built.

**Only after:** NRW water balance (define the schema yourself — nobody has); chunked
execution via GeoParquet + DuckDB; Atlas v2.

**Defer until you are publishing:** the PyPI name decision.