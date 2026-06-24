# GeoQA - Deterministic Geospatial QA Engine

GeoQA prepares geospatial datasets for AI by detecting, explaining, and fixing data quality issues.

GeoQA can also load additive domain plugins for real-world client rules. In the current repo, DMA-specific polygon QA logic from legacy operational scripts is available through the normal `geoqa.validate(...)` path without changing the core engine.

Future-only architecture notes and staged build plans live under `docs/future/` so they stay separate from shipped operator guidance.

More precisely: GeoQA validates, audits, and prepares geospatial datasets for reliable GIS and GeoAI workflows using deterministic rules, not guesswork.

GeoQA is designed for imperfect machines and imperfect data.
It prioritizes useful results over complete runs when necessary.

## GeoQA Atlas

GeoQA Atlas is the public WebGIS demo layer for this engine.
It lives in `apps/atlas` and shows GeoQA reports through a dark map-first interface with demo datasets, issue overlays, report downloads, and an upload workflow preview.

Atlas does not replace the GeoQA internals.
The deterministic CLI and Python package remain the source of validation logic, profiles, reports, and conservative fixes.

Run the Atlas demo with these commands.

```powershell
cd apps/atlas
npm install
npm run dev
```

The v1 app serves precomputed reports and static GeoJSON previews for public demo use.
The Run QA page previews the upload workflow and clearly marks full validation as a backend-connected step.
Current demo cards cover roads, zoning polygons, administrative boundaries, flood risk zones, synthetic water utility lines, and places.
Screenshots can be added under `docs/assets/` after the Atlas preview is captured.

## Front-and-Center Proof

One of the clearest current proof points is already in the repo:
- Natural Earth roads
- `56,600` features
- low-resource CLI benchmark
- completed successfully on the maintainer workstation
- `49` structured findings

That matters because GeoQA is designed for real constrained operator environments, not idealized cloud hardware only.

## Real-World Constrained Execution

GeoQA validated a `56,600`-feature road dataset in about `122` seconds
on a heat-limited workstation using low-resource mode.

Result:
- execution status: `full`
- issues found: `49`
- prioritized, actionable output

This is not a cloud benchmark.
This is a real constrained-machine result.

## Where GeoQA Fits

GeoQA is:
- the data-quality layer before downstream GIS or GeoAI work
- a deterministic QA engine
- a repeatable CLI and Python workflow

GeoQA is not:
- desktop GIS software
- a machine-learning framework
- a hydraulic or network simulation engine

## Reading Order

Start here:
1. `README.md`
2. `docs/START_HERE.md`
3. `docs/user_guide.md`
4. `docs/api_policy.md`
5. `docs/tests.md`

Contributor-oriented docs:
- `CONTRIBUTING.md`
- `ARCHITECTURE.md`
- `docs/security.md`
- `docs/solo_operator_guide.md`

## Quick Start

Install runtime dependencies:

```powershell
pip install -r requirements.txt
```

Run the CLI:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry
```

Low-resource first run on a weak or heat-limited machine:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --report-path data/integration_results/quick_low_resource_demo
```

Editable development install:

```powershell
pip install -e .[dev]
```

## Python API

GeoQA now has a simple public Python API on top of the existing engine:

```python
import geoqa

report = geoqa.validate("data/public_samples/edge_cases/duplicate_vertex_line.geojson")
print(report.summary)
print(report.score())
print(report.to_ml())

score = geoqa.score("data/public_samples/edge_cases/duplicate_vertex_line.geojson")
print(score)

crs_issues = geoqa.expect.valid_crs(
    "data/public_samples/edge_cases/duplicate_vertex_line.geojson",
    expected_crs="EPSG:3857",
)
print(crs_issues)
```

This API is intentionally flat at the top and object-shaped after validation:
- `geoqa.validate(...)`
- `geoqa.score(...)`
- `geoqa.expect.valid_crs(...)`
- `geoqa.expect.crs.valid(...)`
- `geoqa.expect.geometry.clean(...)`
- `geoqa.expect.topology.connected(...)`
- `geoqa.check(path).self_intersections()`
- `GeoQAReport.summary`
- `GeoQAReport.score()`
- `GeoQAReport.to_ml()`
- `GeoQAReport.export(...)`

## Signature Workflow

```python
import geoqa

report = geoqa.validate("data.shp")

print(report.summary)
print(report.score(method="conservative"))

if report.score() < 0.8:
    fixed = report.clean()
    fixed.export("cleaned.geojson")
```

GeoQA is meant to feel like one concept:
- validate a dataset
- get back a report
- inspect, score, export, or transform it

## Story-Driven Examples

The examples folder now focuses on workflow stories, not just syntax:
- `examples/basic_usage.py`
- `examples/story_geoai_prep.py`
- `examples/before_after_cleaning.py`

These show GeoQA as:
- a validator
- a report object
- a conservative cleaning/export loop

Additional docs:
- `docs/before_after_showcase.md`
- `docs/workflows/water_network_ml_prep.md`

## Example Output

```text
Loaded 1 features
Detected 1 issues
Execution status: full
Report written to data/integration_results/demo.json
```

## CLI Usage

Validate a dataset:

```powershell
python -m geoqa validate data.shp --profile water_network --output-format json --report-path reports/pipes
```

List profiles:

```powershell
python -m geoqa profiles list
python -m geoqa profiles show water_network
```

Convert a dataset:

```powershell
python -m geoqa convert input.geojson output.parquet --format geoparquet
```

Summarize a report:

```powershell
python -m geoqa report summarize reports/pipes.json
```

Run a benchmark:

```powershell
python -m geoqa benchmark data.shp --profile generic_quick
```

Use runtime controls when needed:

```powershell
python -m geoqa validate data.shp --profile water_network --max-workers 4 --chunk-size 3000 --sleep 2.0 --thermal-profile cool --cache .geoqa_cache --cache-tag run_a --progress --max-runtime-seconds 1800
```

Use explicit low-resource mode when the machine is the constraint:

```powershell
python -m geoqa validate data.shp --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag low_resource_demo --progress
```

## Core Concepts

- Validation profiles select and tune deterministic checks for a dataset family.
- Domain packs provide profile behavior for dataset families such as water networks, boundaries, and land use without duplicating validator logic.
- Water-network pack variants currently include:
  - `water_network_quick`
  - `water_network`
  - `water_network_strict`
  - `water_network_audit`
- The water-network pack is the current flagship domain pack and should be read as deterministic utility-network QA, not hydraulic modeling.
- Runtime controls support chunking, bounded parallelism, cache reuse, and thermal safety.
- Runtime feedback now includes validator-stage progress metadata and supports bounded wall-clock execution.
- Low-resource mode now applies a conservative execution profile automatically for weak or heat-limited machines.
- Reported issues now include a computed `priority_score` to help triage actionable findings first.
- Profiles now support explicit downgrade and suppression rules in addition to per-problem policy overrides.
- Agent/runtime chunking now supports geometry-weighted adaptive resizing under thermal or runtime pressure.
- Reports are structured outputs that can be consumed by GIS, ML, or downstream QA workflows.
- The Streamlit app is a local shell around the engine, not the primary product surface.

## Architecture

```text
CLI / Scripts / App
        |
     Runtime
        |
 Validators / Profiles / Reports
        |
   GeoPandas / Shapely / PyProj
```

## Feature Maturity

| Feature | Status |
| --- | --- |
| Validation engine | Stable |
| CSV / JSON reporting | Stable |
| CLI surface | Stable |
| Validation profiles and domain packs | Partial / strong first slice |
| Runtime caching | Partial |
| Chunking / thermal controls | Partial |
| Adaptive runtime feedback and stop controls | Partial |
| Issue prioritization and actionable reporting | Partial / stronger |
| Signal calibration fields and profile policies | Partial / stronger |
| Low-resource execution mode | Partial / strong operator slice |
| Spatial-index acceleration | Partial |
| Water-network domain pack | Partial / implemented first pack |
| Streamlit app | Experimental |
| Wider GIS format expansion | Planned / Partial by format |
| ArcGIS integration | Planned |

## When to Use GeoQA

- QA before ML or GeoAI training
- validating contractor or vendor-delivered GIS data
- auditing administrative boundaries, utility networks, or land-use layers
- sanity checking larger datasets before GIS analysis or publication

## Current Priority Order

GeoQA should advance in this order:
1. stability and scale
2. enterprise and standards hardening
3. GeoAI maturity
4. ecosystem integrations

Practical implication:
- thermal and large-run completion problems come before new AI-facing features
- ArcGIS-facing work is later-stage and contributor-oriented unless it can be verified in a real ArcGIS environment

## What GeoQA Is Not

- not a GIS editor
- not an LLM-driven geometry engine
- not automatic truth-repair against a basemap
- not a full ArcGIS/QGIS plugin suite yet

## Current Product Identity

GeoQA is primarily:
- a deterministic geospatial QA engine
- a runtime and reporting layer for repeatable validation

GeoQA is secondarily:
- a local app shell
- a GeoAI preparation helper
- a future integration surface for other GIS tools

## Constrained Hardware

GeoQA is built with the assumption that some operators are running on weak or heat-limited local machines.

Current support includes:
- `--low-resource` CLI mode
- chunking and adaptive chunk resizing
- thermal profiles
- runtime budget limits
- explicit partial-run reporting instead of silent aborts

Current limitation:
- the heaviest public workloads still do not always complete on the maintainer workstation within bounded runtime windows
- GeoQA now reports that honestly instead of pretending those runs are clean full validations

## Stable vs Partial vs Experimental

See:
- `docs/api_policy.md`
- `docs/user_guide.md`

Those documents distinguish:
- stable public APIs
- partial runtime features
- experimental/UI surfaces

## Testing

Run the automated suite:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

See:
- `docs/tests.md`
- `docs/local_data_tests.md`
- `docs/benchmark_story.md`

Current automated baseline:
- `python -m unittest discover -s tests -p 'test_*.py'`
- result: `OK` (`144` tests)

## Security

GeoQA-specific risks and mitigations are documented in:
- `docs/security.md`

## Streamlit

The Streamlit app remains available as a local inspection shell:

```powershell
streamlit run streamlit_app.py
```

But the recommended order is:
1. CLI
2. library/runtime APIs
3. app
