# GeoQA

Deterministic geospatial data-quality validation for research and delivery.

GeoQA checks whether a spatial dataset is fit for the purpose it is about to be
put to. It reports **named, registered conditions** rather than ad-hoc warnings,
and it separates *defects*, *evidence* and *governance gaps* so that a reviewer
can tell the difference between "this is wrong", "this might be wrong" and
"nobody recorded who decided this".

```python
from geoqa.validation_runtime import execute_validation_plan
import geopandas as gpd

layer = gpd.read_file("boundaries.gpkg")
result = execute_validation_plan(
    layer, "topology",
    metadata={"licence": "CC BY 4.0", "lineage": "Digitised 2026 from survey."},
    return_result=True,
)

for issue in result.issues:
    print(issue.severity, issue.problem_name, "-", issue.description)
```

---

## Design commitments

These are the rules the library holds itself to. They are what make a GeoQA
report citable.

**Named conditions, not generic warnings.** Every finding carries a
`problem_name` from a registry of 253 conditions, each with a description, a
repair hint, a severity, a confidence and an issue class. A report can be
diffed, counted and audited because the vocabulary is fixed.

**Defects and evidence are different things.** `data_issue` means wrong.
`evidence_condition` means "here is what we observed, you decide".
`governance_gap` means nobody recorded a decision that had to be made. A
validator that reports a value as a defect when it is really an unstated
assumption trains people to ignore it.

**No silent repair, and no silent assumptions.** Empirical coefficients must be
declared with a meaning, a unit and a source. A number cannot enter a
water-loss calculation unaccompanied. Bands in a raster are identified by
wavelength, never by index. Axis order must be declared, never guessed.

**Ambiguity is reported as ambiguity.** When a pair of coordinates is legal in
both axis orders, GeoQA says so and asks for a declared extent. It does not
pick one and move on.

**Deterministic.** The same input produces the same output. Validation is
measurement, not interpretation.

---

## Install

```bash
pip install -e .
```

Python 3.12+. Core dependencies are `geopandas`, `shapely`, `pyproj` and
`psutil`. Optional readers are imported lazily, so a missing one degrades a
single capability rather than breaking the package: `rasterio` for GeoTIFF,
`h5py` for HDF5 hyperspectral, `openpyxl` for Excel.

---

## What it validates

Full per-module detail is in [`docs/modules/`](docs/modules/). The Python source
and function index is in [`docs/python_api_inventory.md`](docs/python_api_inventory.md).
Summary:

| Area | Module | What it does |
|---|---|---|
| Geometry | `validations/geometry.py` | Validity, self-intersection, duplicate vertices, minimum length, sharp cutbacks |
| Topology | `validations/topology.py` | Dangles, overlaps, gaps, isolated segments, unsplit features, cross-name nesting |
| Attributes | `validations/attributes.py` | Domains, nulls, uniqueness, field constraints |
| Integrity | `validations/integrity.py` | Missing and stale spatial indexes, RFC 7946 conformance |
| CRS | `validations/crs.py`, `crs_units.py` | Missing, invalid, datum mismatch, unit reasoning, guarded reprojection |
| Dimension | `validations/dimension.py` | 2D/3D conformance and all-zero-Z evidence |
| Endpoints | `validations/endpoint_triage.py` | Separates near-miss endpoints from genuine orphans and terminal roles |
| Raster | `validations/raster.py` | Band roles, nodata, scale factor, windowed spectral indices |
| Hyperspectral | `validations/hyperspectral.py` | HDF-EOS swath products, band selection by wavelength, product level, QA masks |
| COG | `validations/cog.py` | Cloud-optimized layout, overviews, tile size, format standing |
| Archive | `validations/archive.py` | Zip-slip, decompression bombs, content-versus-extension, shapefile sidecar sets |
| Tabular | `validations/tabular.py` | Headers, ragged rows, leading-zero loss, ambiguous dates, sentinels, keys |
| Workbook | `validations/workbook_media.py` | Embedded and referenced attachments, legibility, attribution |
| Axis order | `validations/axis_order.py` | Latitude/longitude swaps, ambiguity, declaration conflicts, PostgreSQL SQL |
| OSM | `validations/osm.py` | Licence and attribution, version metadata, emergent geometry |
| Vertical | `validations/vertical_datum.py` | Reference surfaces, depth sign, compound CRS requirements |
| Boundary | `validations/boundary_conformance.py` | Undeclared cuts, explained clips, continuity |
| Clip | `validations/clip.py` | Assignable boundary straddles, halved features, truncation |
| Recurrence | `validations/repeat_incident.py` | Same-asset versus same-place recurrence, period gaps |
| Water | `water_balance.py`, `night_flow.py`, `water_loss.py`, `reference_cases.py` | IWA balance, MNF/FAVAD/FADD, UARL and ILI, published reference cases |
| EPANET | `validations/epanet.py` | Structural, referential, unit and topological checks on `.inp` decks |
| Governance | `validations/governance.py` | Licence, accountability, lineage, conformity, currency |
| Provenance | `metric_constants.py`, `payload_columns.py` | Undeclared constants, structured payloads in text columns |
| Security | `validations/credentials.py`, `ai_guard.py` | Hardcoded credentials; disclosure screening before sending data onward |
| Hardware | `hardware.py` | Whether this machine can carry out the operation |

---

## Governance gates

A validator produces findings. Something has to decide whether they permit the
next step. GeoQA makes that an explicit, declared, recorded act.

```python
from geoqa import HITL
from geoqa.hitl import GateSpec, any_of, at_least

gate = HITL("release", gates=[
    GateSpec("no_licence_gap",
             "no dataset ships without recorded terms",
             any_of("governance_licence_not_declared")),
    GateSpec("no_critical", "no critical finding", at_least("critical")),
])

decision = gate.evaluate_and_record(issues, expected_outcome="halt")
decision.hold(by="reviewer@example.org", note="licence confirmed offline")
gate.recall().halt_recall
```

Four properties, each covered by a test that fails if it stops being true:

- **`llm_involved` is a class constant, not a setting.** A gate cannot be
  constructed that claims not to consult a model while doing so. There is a test
  that greps the decision path for HTTP clients.
- **The gate proposes, a person disposes.** `hold()` records a human decision
  and nothing resolves it automatically.
- **Every decision carries its reasons**, which gates fired, which issues
  triggered them, and who decided.
- **Recall is computed, not remembered.** Scored against expected outcomes, so
  "12 of 12 halts caught, 0 false halts on clean input" is a number the library
  produces rather than a number someone recalled.

---

## Evidence runs

Reproducibility harnesses accumulate hardcoded paths and hardcoded headline
numbers, which makes them valid for one submission and not the next.
`scripts/run_evidence_suite.py` takes a manifest instead:

```bash
python scripts/run_evidence_suite.py --manifest cases.yaml --log-dir reports/
```

It runs each declared case, verifies it, logs the result, and can diff against a
recorded baseline.

---

## No-code reporting: site, slides, charts, tables

`geoqa_web` turns a validation result into finished outputs without opening
QGIS, Folium, or a browser console. Everything it produces is a self-contained
static file.

```python
import geoqa, geoqa_web

report = geoqa.validate("mains.osm.pbf")          # OSM loads directly
geoqa_web.build_site(report, "out/site")           # interactive web-GIS
geoqa_web.build_slides(report, "out/slides")       # presentation deck
```

`build_site` writes an `index.html` where every finding is a map feature. Click
one for a popup carrying the rule, severity, confidence, measured distance or
tolerance, and the recommended fix. The legend toggles severity bands, the
search box filters across rules and features, and the sites carry no third-party
branding. A copy of the findings (`findings.geojson`) and a rollup
(`summary.json`) are written alongside it.

Pass `base_layers` to draw reference data beneath the findings, and
`storyboard` to supply your own guided tour. GeoQA generates a default
storyboard that opens on the full extent and narrows to each severity band.

### Charts

Chart descriptions are emitted as plain data, so the renderer is your choice:

```python
from geoqa_web.charts import save_chart_assets
save_chart_assets(report, "out/charts")
```

This writes `charts.json` (the shared definition), `charts_d3.html`,
`charts_plotly.html`, and `charts.png` via matplotlib. The same definition serves
a web page and a journal figure.

### Tables for analysis

GeoJSON is a poor input for a database. Convert findings to a flat,
spreadsheet-ready table with WKT and centroid coordinates:

```python
report.to_table("out/findings.xlsx")     # or .csv
```

Or from an existing file:

```python
from geoqa.reports.tables import geojson_to_table, geojson_to_pivot
geojson_to_table("findings.geojson", "out/findings.xlsx")
geojson_to_pivot("findings.geojson")     # severity x rule
```

Findings that carry no geometry are **not** dropped. They appear with blank
coordinates and `has_geometry = False`, so CRS problems, missing indexes, and
schema findings stay visible instead of silently vanishing from the table.

## GeoQA Atlas

The library is the product. **Atlas** is the interface to it: a browser front
end for running a validation, reading the findings against the geometry that
produced them, and exporting the result.

Live: **[geo-qa-pi.vercel.app](https://geo-qa-pi.vercel.app)**

Source lives in [`apps/atlas/`](apps/atlas/) and is a Vite + React + MapLibre
front end. It talks to the same `geoqa` package the CLI does; there is no second
implementation of any rule. Screenshots are in
[`docs/assets/`](docs/assets/), and the product brief is in
[`docs/geoqa_atlas_product_brief.md`](docs/geoqa_atlas_product_brief.md).

```bash
cd apps/atlas
npm install
npm run dev        # http://localhost:5173
npm test           # demo limits and idle-safety checks
npm run build      # production bundle
```

Basemaps use Esri's keyless endpoints. The previous CARTO endpoint began
returning watermarked tiles and now requires an API key, so it is not usable
for a public demo; `npm test` fails if a watermarking provider is reintroduced.

The Atlas front end is published here but is not imported by the library, so
the web stack is an optional extra (`pip install -e ".[app]"`) rather than a
dependency of `geoqa` itself.

---

## Package layout

```
geoqa/                  the library
  problem_registry.py   309 named conditions with severity, class and repair hints
  validation_runtime.py dataset-type dispatch, profiles, limits, cost ordering
  chunking.py           halo-buffered spatial tiling
  confidence.py         posterior confidence and calibration
  conversion.py         loaders, including OSM and multi-layer sources
  reports/              summaries, explanations, GeoJSON, tables
  validations/          one module per concern
  packs/                domain packs declaring which conditions apply where
  qgis_integration.py   QML, GeoPackage bundles, run manifests
  gpkg.py               GeoPackage structural conformance
  hitl.py               governance gates
  hardware.py           feasibility of an operation on this machine
  proj_env.py           PROJ database resolution
  ai_guard.py           disclosure screening
geoai/                  the optional GeoAI layer
geoqa_web/              no-code outputs: site, slides, charts
apps/atlas/             the Atlas browser front end (not imported by the library)
docs/modules/           one generated page per validation module
docs/literature/        research notes with sources and verification status
docs/assets/            Atlas screenshots
tools/                  capability workbook and module documentation generators
scripts/                evidence suite runner
tests/                  3074 tests
```

---

## Tests

```bash
python -m pytest -q
```

969 tests. Tests that need real multi-gigabyte imagery read their location from
an environment variable and skip when it is absent:

```bash
GEOQA_EMIT_GRANULE=/path/to/granule.h5 python -m pytest tests/test_hyperspectral.py
```

---

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.