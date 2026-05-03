# GeoQA Start Here

This is the shortest path to understanding GeoQA as a tool, not just a codebase.

## What GeoQA Is

GeoQA is a deterministic geospatial QA engine.

One-line definition:
- GeoQA prepares geospatial datasets for AI by detecting, explaining, and fixing data quality issues.

Use it to:
- validate geospatial data
- generate structured issue reports
- prepare datasets for downstream GIS or GeoAI workflows

If you want the shortest public proof path after this page, read:
- `docs/before_after_showcase.md`
- `docs/benchmark_story.md`
- `docs/workflows/water_network_ml_prep.md`

Do not start with the Streamlit app. Start with the CLI or library.

## First Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the simplest CLI example:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry --output-format json --report-path data/integration_results/start_here_geometry
```

Expected outcome:
- GeoQA loads the sample dataset
- GeoQA detects one `duplicate_vertex` issue
- GeoQA writes:
  - `data/integration_results/start_here_geometry.json`

## Weak-Machine First Run

If the machine is small, hot, or unreliable under GIS workloads, use low-resource mode first:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --report-path data/integration_results/start_here_low_resource
```

Expected outcome:
- GeoQA uses a conservative execution profile
- progress output is more operator-facing
- if the run is cut short, the report says so explicitly

## Why This Matters

This is the canonical GeoQA story:
1. validate a known imperfect dataset
2. get structured findings
3. write a reusable report
4. use that report in QA, GIS review, or ML prep

That is GeoQA's primary value.

If you prefer the Python API, the signature workflow now looks like this:

```python
import geoqa

report = geoqa.validate("data/public_samples/edge_cases/duplicate_vertex_line.geojson")
print(report.summary)

if report.score() < 0.8:
    report.clean().export("cleaned.geojson")
```

GeoQA also now has one heavier public constrained-hardware success case already recorded:
- Natural Earth roads
- `56,600` features
- low-resource CLI benchmark
- `49` findings
- full completion on the maintainer workstation

## Next Commands

List available profiles:

```powershell
python -m geoqa profiles list
python -m geoqa profiles show generic_quick
```

Summarize a report:

```powershell
python -m geoqa report summarize data/integration_results/start_here_geometry.json
```

Run the unit suite:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

## How To Read a Partial Run

GeoQA can now stop honestly when runtime or safety limits are reached.

Look for:
- `Execution status`
- `Execution reason`
- `validators_completed`
- `validators_deferred`
- `partial_result`
- `operator_next_steps`

That means:
- partial output is usable
- partial output is not misrepresented as a full clean validation

## When to Use the App

Use `streamlit run streamlit_app.py` only after:
- the CLI path works
- you understand the profile you want
- you want a local inspection shell

The app is not the core product surface.
Future-facing design notes are kept under `docs/future/`.
Use those for later architecture work, not for current shipped capability.
