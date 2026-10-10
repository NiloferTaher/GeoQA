# GeoQA User Guide

## Recommended Entry Points

Use GeoQA in this order:
1. CLI
2. library/runtime APIs
3. Streamlit app

Why:
- the CLI is the cleanest operational surface
- the library is the real engine
- the app is a local shell, not the product center

For constrained local workstations, also see:
- `docs/solo_operator_guide.md`

## Capability Status

Stable:
- core validators
- JSON and CSV reports
- CLI validate / profiles / convert / report / benchmark
- deterministic conversion helpers

Partial:
- runtime profiles
- cache reuse
- chunking and thermal-aware execution
- geometry-weighted adaptive chunking
- cost-aware validator ordering for constrained runs
- low-resource execution mode
- signal calibration through profile policies
- CRS-aware / scale-aware precision tuning
- spatial-index-aware acceleration
- domain-specific validation packs
- water-network connectivity/domain-pack behavior

Experimental:
- Streamlit app
- some interactive preview behaviors

Planned:
- broader GIS integrations
- ArcGIS tooling
- wider format support beyond current implemented paths

## CLI Workflows

### Validate

```powershell
python -m geoqa validate data.shp --profile generic_quick --output-format json --report-path reports/data
```

Weak-machine example:

```powershell
python -m geoqa validate data.shp --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag low_resource_run --progress
```

Useful flags:
- `--profile`
- `--output-format`
- `--report-path`
- `--max-workers`
- `--chunk-size`
- `--sleep`
- `--thermal-profile`
- `--max-features`
- `--max-size-mb`
- `--cache`
- `--cache-tag`
- `--max-runtime-seconds`
- `--max-issues`
- `--stop-after-actionable`
- `--progress-interval-seconds`
- `--low-resource`
- `--progress`
- `--fail-on-error`

### Profiles

```powershell
python -m geoqa profiles list
python -m geoqa profiles show boundaries
```

`profiles show` now exposes:
- severity overrides
- downgrade rules
- suppression rules
- per-problem policies

### Convert

```powershell
python -m geoqa convert input.geojson output.parquet --format geoparquet
```

### Reports

```powershell
python -m geoqa report summarize reports/data.json
python -m geoqa report stats reports/data.json
python -m geoqa report summarize reports/data.json --json
```

### Benchmark

```powershell
python -m geoqa benchmark data.shp --profile generic_quick
```

Low-resource benchmark example:

```powershell
python -m geoqa benchmark data.shp --profile generic_quick --low-resource --max-runtime-seconds 120
```

## Runtime Layer

Use the runtime layer when you want to build repeatable custom workflows in Python.

Current runtime features:
- `ValidationProfile`
- `ValidationLimits`
- `InMemoryValidationCache`
- `FileValidationCache`
- custom validator registration
- progress callbacks
- bounded parallel validator execution
- partial-run execution summaries

Example:

```python
from geoqa.interactive.validation import (
    FileValidationCache,
    ValidationLimits,
    ValidationProfile,
    register_custom_validator,
    validate_layer,
)

profile = ValidationProfile(
    name="geometry_quick",
    dataset_type="geometry",
    enabled_validators=("null_geometry", "duplicate_vertex"),
)

issues = validate_layer(
    layer,
    "geometry",
    profile=profile,
    cache=FileValidationCache(".geoqa_cache"),
    cache_tag="demo",
    max_workers=2,
    limits=ValidationLimits(max_features=100000),
)
```

## Profiles

Current built-in GeoQA profiles:
- `geometry`
- `generic_quick`
- `generic_audit`
- `generic_strict`
- `boundaries_quick`
- `water_network`
- `water_network_quick`
- `water_network_strict`
- `water_network_audit`
- `boundaries`
- `boundaries_strict`
- `boundaries_audit`
- `land_use_quick`
- `land_use`
- `land_use_strict`
- `land_use_audit`

These are the first slice of context-aware behavior. They are not yet the final industry-grade domain-pack system.

Practical intent:
- `*_quick`: lower-noise, high-value, weak-hardware-friendly
- `*_strict`: broader operational QA
- `*_audit`: fullest signal, slower, review-oriented

The water-network pack now includes profile-driven handling for:
- dangles vs allowed service or terminal endpoints
- isolated segments
- suspicious near-miss endpoints
- unsnapped endpoints within tolerance
- optional schema-aware attribute checks when useful fields exist
- operator rollups for junctions, terminal endpoints, and recognized schema coverage

What the water-network pack does not claim:
- hydraulic simulation
- flow modeling
- pressure analysis
- full utility network semantics

## Reports

Reports can be written as:
- JSON
- CSV

For a concise public-run credibility narrative built from recorded repo results, see:
- `docs/benchmark_story.md`

Reports now include richer issue metadata such as:
- issue id
- severity
- confidence
- actionable
- issue class
- validator name/version
- ISO category where available

Profiles can now also apply:
- per-problem severity overrides
- per-problem downgrade rules
- per-problem confidence overrides
- per-problem actionable/informational overrides
- per-problem suppression policies

CLI report summaries now default to a human-readable operator summary showing:
- execution status and execution reason
- validators completed vs deferred
- actionable vs informational split
- severity distribution
- top issues by percentage
- top actionable findings
- root-cause groups when provenance is present
- operator next-step hints

`geoqa report stats ...` also includes:
- the operator summary above
- row count for the loaded report

## Streamlit App

The Streamlit app is still available:

```powershell
streamlit run streamlit_app.py
```

Use it when you want:
- local visual inspection
- quick format conversion
- conservative fix review

Do not treat it as the primary interface for validating the engine.
