# GeoQA Solo Operator Guide

This guide is for running GeoQA on a constrained local workstation.

## Use This First

If the machine is weak, hot, or unreliable under GIS workloads, start with:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag solo_smoke --progress --report-path data/integration_results/solo_smoke
```

Why:
- conservative worker count
- smaller starting chunks
- stronger thermal caution
- clearer operator-facing progress

## Safe Rerun Commands

Quick smoke validation:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --report-path data/integration_results/smoke_demo
```

Low-resource public run:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag low_resource_demo --progress --report-path data/integration_results/low_resource_demo
```

Cached rerun:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --cache .geoqa_cache --cache-tag repeat_demo --report-path data/integration_results/repeat_demo
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --cache .geoqa_cache --cache-tag repeat_demo --progress --report-path data/integration_results/repeat_demo
```

Benchmark smoke:

```powershell
python -m geoqa benchmark data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 120
```

## How To Read a Partial Run

A partial run is still useful if GeoQA says so explicitly.

Look for:
- `Execution status`
- `Execution reason`
- `validators_completed`
- `validators_deferred`
- `partial_result`
- `operator_next_steps`

What it means:
- the engine stopped honestly
- some findings are still usable
- the report is not pretending to be a full clean validation

## Profile Selection

Use:
- `*_quick` for weak hardware and first triage
- `*_strict` for fuller operational QA
- `*_audit` for broadest review when time and heat budget allow it

If uncertain, start with:
- `generic_quick`
- `water_network_quick`
- `boundaries_quick`
- `land_use_quick`

## When To Stop Expanding

Do not add a new validator or pack just because it sounds useful.

Add one only if you can answer:
- does it improve actionable signal on real data?
- does it have a bounded runtime story?
- does it fit a real profile?
- does it have tests?

If not, harden what exists first.
