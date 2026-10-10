# Workflow: Prepare Water Network Data for Model Training

This workflow shows where GeoQA fits in a practical pipeline.

GeoQA is not the hydraulic model.
GeoQA is not the ML model.
GeoQA is the data-quality layer between raw network data and downstream modeling.

## Goal

Use GeoQA to:
- validate utility linework
- surface actionable issues first
- produce a structured QA report
- optionally apply conservative fixes
- export a cleaner dataset for downstream feature engineering or model training

## Where GeoQA Fits

Raw utility data often arrives with problems such as:
- disconnected endpoints
- duplicate vertices
- self-intersections
- suspicious near-miss endpoints
- inconsistent or missing key attributes

GeoQA helps before training or scoring by answering:
- what is wrong?
- what is actionable?
- what can be cleaned conservatively?
- what still needs analyst review?

## Step-by-Step

### 1. Run a water-network validation

```powershell
python -m geoqa validate data.shp --profile water_network_quick --output-format json --report-path reports/water_network
```

For weaker or hotter machines:

```powershell
python -m geoqa validate data.shp --profile water_network_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag water_network_demo --report-path reports/water_network_low_resource
```

### 2. Review the summary

Useful signals to inspect first:
- execution status
- actionable findings
- top issue types
- water-network pack summary

Typical water-network operator questions:
- how many dangling or disconnected endpoints exist?
- are there isolated segments?
- are there near-miss endpoints that should probably snap?
- did schema-aware checks run, or were they skipped because key fields were missing?

### 3. Use the Python API when you want a report object

```python
import geoqa

report = geoqa.validate("data.shp", profile="water_network_quick")

print(report.summary)
print(report.score(method="conservative"))
```

### 4. Export or clean conservatively

```python
fixed = report.clean()
fixed.export("cleaned_water_network.geojson")
```

This conservative clean step is useful for geometry hygiene.
It is not a substitute for network engineering review.

### 5. Feed downstream ML or analytics

GeoQA can then help produce issue-oriented training features:

```python
rows = report.to_ml()
print(rows[:5])
```

That gives you a structured QA-derived layer you can join into a broader ML or analytics pipeline.

## What GeoQA Does Well Here

- deterministic linework and connectivity QA
- actionable vs informational split
- conservative cleaning
- repeatable CLI and Python workflows
- honest partial-run handling on constrained machines

## What GeoQA Does Not Claim Here

- hydraulic simulation
- pressure or flow modeling
- full utility network semantics
- asset lifecycle management

The water-network pack should be understood as:
- deterministic utility-network QA

not:
- a full water utility model

## Recommended Profile Strategy

- `water_network_quick`
  - first pass
  - weak hardware
  - high-value checks first
- `water_network`
  - normal working profile
- `water_network_strict`
  - broader operational QA
- `water_network_audit`
  - slowest, fullest signal, review-oriented

## Why This Workflow Matters

If a dataset enters GeoAI or ML workflows without QA:
- model features inherit data defects
- analyst time shifts downstream
- debugging gets harder

GeoQA exists to move that quality work earlier, make it explicit, and keep it reproducible.
