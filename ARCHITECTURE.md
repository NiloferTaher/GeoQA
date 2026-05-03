# GeoQA Architecture

## Core Shape

```text
CLI / Scripts / App
        |
     Runtime
        |
 Validators / Profiles / Reports
        |
   GeoPandas / Shapely / PyProj
```

## 1. Validators

Deterministic checks live under:
- `geoqa/validations/`

Validators should:
- detect
- return structured issues
- avoid orchestration logic
- avoid UI concerns

## 2. Runtime

Validation orchestration lives under:
- `geoqa/validation_runtime.py`
- `geoqa/profile_registry.py`
- `geoqa/problem_registry.py`
- `geoqa/execution.py`

This layer handles:
- profiles
- progress
- cache reuse
- validation limits
- bounded parallel execution
- low-resource execution defaults
- honest partial-run outcomes
- operator next-step hints

## 3. Reporting

Structured output lives under:
- `geoqa/reports/`

This layer summarizes:
- actionable vs informational findings
- priority bands
- severity distribution
- problem breakdown
- execution completeness
- top actionable findings

## 4. Operational Surfaces

- CLI: `geoqa/cli/`
- library wrappers: `geoqa/interactive/`, `geoqa/automation/`
- app shell: `streamlit_app.py`

## Current Preferred Operator Path

1. `python -m geoqa validate ...`
2. `python -m geoqa report summarize ...`
3. `python -m geoqa benchmark ...`
4. `streamlit_app.py` only when a local shell is useful

## Current Strongest Domain Pack

The strongest current pack is:
- `water_network`

Why:
- deepest schema detection
- meaningful quick/strict/audit differences
- pack-specific connectivity summaries

## Design Rule

Logic should move downward:
- app and CLI orchestrate
- runtime coordinates
- validators detect
- reports summarize

Business logic should not grow inside the UI.
