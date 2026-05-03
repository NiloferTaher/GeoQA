# GeoQA Execution Plan (Stage-Based System Build)

You are a senior systems engineer.

This project (GeoQA) already has:

- a working Python validation engine
- plugin system (DMA rules)
- API (`geoqa.validate`, `GeoQAReport`)
- tests and documentation

Your task is NOT to redesign the system.

Your task is to execute a staged implementation plan.

## Core Principle

GeoQA Python implementation is the single source of truth.

All other environments (PyQGIS, PostGIS) must:

- replicate the same logic
- be validated against GeoQA outputs
- never diverge from core behavior

## Overall Goal

Build a multi-environment geospatial QA system:

```text
GeoQA (Python)
-> AI-generated execution scripts
-> PyQGIS / PostGIS
-> validated outputs
-> Streamlit demo interface
```

## Phase 1 — Demo (Python Only)

### Goal

Prove GeoQA works clearly.

### Tasks

- Create demo dataset:
  - small GeoJSON (5-10 features)
  - include:
    - duplicate geometries
    - nested polygons
    - overlapping polygons
    - inconsistent names
- Create example script:
  - `examples/demo_dma.py`
- Script must:
  - run `geoqa.validate()`
  - print summary
  - print issues
  - export cleaned dataset
- Create:
  - `docs/before_after.md`
- Must show:
  - before (bad data)
  - after (cleaned data)
- Update README:
  - one-line description
  - minimal example
  - link to demo

## Phase 2 — Script Generation (Controlled)

### Goal

Generate PyQGIS and PostGIS scripts from GeoQA logic.

### Tasks

For a given dataset:

- run GeoQA
- capture expected result

Use AI to generate:

- PyQGIS script
- PostGIS SQL script

Save generated scripts under:

```text
geoqa-generated/
  pygis/
  postgis/
```

### Rules

- DO NOT create new logic
- ONLY translate existing GeoQA logic
- DO NOT simplify rules
- DO NOT modify behavior

## Phase 3 — Validation Layer

### Goal

Ensure generated scripts match GeoQA output.

### Tasks

Create comparison module:

- `geoqa/validation/compare.py`

Compare:

- issue count
- geometry output
- attribute values

Output:

- `MATCH`
- `MISMATCH`

If mismatch:

- flag script as invalid
- do not promote to reusable script

## Phase 4 — Streamlit Demo

### Goal

Make the system visible and testable.

### UI Flow

User uploads dataset OR selects demo.

Run:

- GeoQA (Python)
- generated script (PyQGIS/PostGIS)

Show:

- before
- after (GeoQA)
- after (generated)

Show:

- comparison result (`MATCH` / `MISMATCH`)

## Phase 5 — Adapter Preparation (Not AI Rewrite)

### Goal

Prepare for future direct execution.

### Tasks

Define adapters (no implementation yet):

- `GeoPandasAdapter`
- `PostGISAdapter`
- `PyQGISAdapter`

Adapters should:

- load data
- execute logic
- return results in GeoQA format

## Phase 6 — Safe Auto-Fixing (Later)

### Goal

Enable automated fixes.

### Rules

ONLY allow safe operations:

- remove duplicate geometries
- dissolve identical polygons
- normalize names
- repair invalid geometry

DO NOT automate:

- ownership decisions
- cross-layer semantic fixes
- uncertain topology edits

## Phase 7 — Future Extensions

- QGIS plugin
- WebGIS interface
- domain packs:
  - hydrants
  - valves
  - pipe status validation
  - cross-layer validation

## Success Criteria

- GeoQA demo runs clearly in Python
- generated scripts match GeoQA output
- system is understandable in under 2 minutes
- no logic duplication across environments
- core engine remains unchanged

## Final Rule

Do NOT expand features.

Focus on:

- clarity
- correctness
- proof

## What This Plan Enforces

This is not just a plan.

It enforces:

- sequence (no jumping ahead)
- single source of truth
- verification loop
- no overengineering

## Why This Is Strong

Most systems drift into:

```text
code -> more code -> more features -> confusion
```

This plan instead builds:

```text
engine -> proof -> translation -> validation -> interface
```

That is how a real system becomes understandable and adoptable.

## One Sentence To Remember

Don't build everything. Build in order.
