# GeoQA Skills Reference

## Version/Date

- Version: 2026-03-18
- Python: 3.12+

## Canonical Prompt

- `codex_prompt.md` in the project root is the canonical prompt file for Codex-assisted GeoQA tasks.
- Use it as the primary instruction reference when framing or executing GeoQA coding work.

## Package Layout Notes

Core implementation lives in:
- `geoqa/validations`
- `geoqa/agent.py`
- `geoqa/fixes.py`
- `geoqa/interactive_validation.py`
- `geoai/serialization.py`
- `geoai/jax_layer`
- `geoai/qgis_layer`

Prompt-friendly wrapper layout also exists for usability and structural compliance:
- `geoqa/agents`
- `geoqa/automation`
- `geoqa/interactive`
- `geoqa/fix`
- `geoqa/serialization`
- `docs/`

Rule:
- Extend the core implementation first, then keep wrapper packages aligned rather than duplicating logic.

## Hybrid Execution Model

- GeoQA should distinguish between deterministic spatial computation and AI-assisted reasoning.
- Deterministic spatial work includes:
  - CRS reprojection
  - coordinate math
  - null geometry checks
  - duplicate vertex checks
  - direct geometry predicates such as `intersects`, `contains`, or `is_valid`
- These tasks should stay in normal Python/GIS libraries such as:
  - `pyproj`
  - `shapely`
  - `geopandas`
- AI should be reserved for higher-level tasks such as:
  - semantic interpretation of attributes
  - repair prioritization
  - workflow suggestions
  - ambiguous classification support
- Practical execution tiers:
  - Level 0: deterministic code
  - Level 1: light AI for simple semantic help
  - Level 2: heavier AI for complex reasoning or repair planning
- This separation reduces hallucination risk, lowers heat, and keeps the library safer for geospatial work.

## Core Classes/Functions

### `ValidationIssue`

Purpose:
- Standard issue object for GeoQA validation results.
- Keeps validation output consistent across geometry, attributes, CRS, topology, metadata, and future agent workflows.

Fields:
- `problem_name`
- `severity`
- `description`
- `solution_hint`
- `feature_id`
- `geometry`

Notes:
- Implemented as a lightweight dataclass in `geoqa.validations.base`.
- Use `to_dict()` when sending issues into reports or other serialized workflows.

Typical use:

```python
from geoqa.validations.base import ValidationIssue

issue = ValidationIssue(
    problem_name="null_geometry",
    severity="critical",
    description="Feature has no valid geometry.",
    solution_hint="Recreate the missing shape.",
    feature_id=123,
)
```

### `ThermalGuard`

Purpose:
- Cooperative CPU temperature guard for long-running or CPU-intensive GeoQA work.
- Pauses work near the warning threshold and raises when the hard thermal ceiling is exceeded.

Key parameters:
- `warn_temp_c=68.0`
- `max_temp_c=74.0`
- `cooldown_seconds=15.0`
- `check_interval_seconds=5.0`
- `max_wait_seconds=300.0`
- `log_path=None`

Typical use:

```python
from geoqa import ThermalGuard, ThermalLimitExceeded

guard = ThermalGuard.strict()

try:
    with guard:
        guard.wait_until_safe(stage="before_batch")
        # CPU-intensive work here
        guard.check_or_raise(stage="after_batch")
except ThermalLimitExceeded as exc:
    print(f"stopped: {exc}")
```

Best fit:
- Explicit thermal control around loops, batch jobs, validators, and transforms.

Profiles:
- `ThermalGuard()` for the default conservative policy
- `ThermalGuard.cool()` for machines that heat up quickly
- `ThermalGuard.strict()` for very conservative local runs

### `ThermalRunner`

Purpose:
- Base runner for thermal-safe iterable workloads.
- Wraps each step with pre-check and post-check temperature handling.

Key methods:
- `run_step(item, func, index=...)`
- `run_iterable(items, func)`
- `run_sequence(items, func)`

Typical use:

```python
from geoqa import ThermalGuard, ThermalRunner

guard = ThermalGuard()
runner = ThermalRunner[int](guard=guard)
results = runner.run_sequence([1, 2, 3], lambda item: item * 10)
```

Best fit:
- CPU-bound loops where each item is a natural checkpoint.

### `StepResult`

Purpose:
- Structured result container returned by `ThermalRunner`.

Fields:
- `index`
- `item`
- `result`
- `snapshot`

Typical use:

```python
from geoqa import ThermalGuard, ThermalRunner

runner = ThermalRunner[int](guard=ThermalGuard())
results = runner.run_sequence([2], lambda item: item + 1)
first = results[0]
print(first.index, first.item, first.result, first.snapshot.max_temp_c)
```

### `GeoQAScriptBase`

Purpose:
- High-level base class for GeoQA scripts.
- Handles thermal-safe execution and optional startup diagnostics.
- Subclasses only need to implement `load_items()` and `process_item()`.

Key parameters:
- `guard=None`
- `emit_thermal_diagnostic=True`
- `diagnostic_emitter=None`

Required methods:
- `load_items()`
- `process_item(item)`

Optional hooks:
- `before_run()`
- `after_run(results)`
- `before_step(index, item)`
- `after_step(step)`

Typical use:

```python
from geoqa import GeoQAScriptBase


class MyScript(GeoQAScriptBase[str, str]):
    def load_items(self) -> list[str]:
        return ["a", "b", "c"]

    def process_item(self, item: str) -> str:
        return item.upper()


results = MyScript().run()
```

Quiet startup:

```python
MyScript(emit_thermal_diagnostic=False).run()
```

Redirect diagnostic output:

```python
from pathlib import Path

from geoqa import GeoQAScriptBase
from geoqa.thermal import TemperatureDiagnostic

log_path = Path("data/thermal_diagnostic.log")


def log_diagnostic(diag: TemperatureDiagnostic) -> None:
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(diag.message + "\n")
        for option in diag.options:
            fh.write(f"option: {option}\n")
```

### `ThermalLimitExceeded`

Purpose:
- Exception raised when the measured CPU temperature exceeds the configured hard ceiling.

Typical use:

```python
from geoqa import ThermalLimitExceeded

try:
    run_job()
except ThermalLimitExceeded as exc:
    handle_stop(exc)
```

## Utility Functions

### `run_agent_workflow()`

Purpose:
- Run the GeoQA agent workflow end to end for a dataset.
- Handles dataset-type resolution, validation routing, issue reporting, optional sample-first fix review, and final agent reporting.

Typical use:

```python
from geoqa.agent import run_agent_workflow

result = run_agent_workflow(
    "path/to/dataset.geojson",
    dataset_type="water_network",
    interactive=False,
)
```

Notes:
- explicit dataset type is still preferred over inference
- inference is available as a secondary helper
- sample-first review is the intended approval path for supported auto-fixes

Related convenience functions:
- `validate_dataset(...)` for validation plus issue-report writing without the interactive fix stage
- `apply_fixes_interactively(...)` for sample-first fix review and optional full-dataset application
- `generate_final_report(...)` for writing the final issue/fix report

Useful options:
- `batch_size=...` for batched full-dataset fix application on larger datasets
- `visual_feedback=True/False` to keep or suppress lightweight sample-fix geometry previews
- `fix_log_path=...` to append fix actions to a JSONL audit log
- `recommendation_hook=...` to attach optional AI- or rules-based recommendations to the final run result

### `generate_report()`

Purpose:
- Write validation issues to a CSV or JSON report.

Typical use:

```python
from geoqa.reports.report_generator import generate_report
from geoqa.validations.base import ValidationIssue

issues = [
    ValidationIssue(
        problem_name="null_geometry",
        severity="critical",
        description="Feature has no valid geometry.",
        solution_hint="Recreate the missing shape.",
        feature_id=1,
    )
]

generate_report(issues, output_format="json", file_path="validation_report")
```

Supported outputs:
- `csv`
- `json`

Notes:
- The report utility expects `ValidationIssue` objects.
- `geometry` is included in the serialized payload, but CSV reporting is centered on the main descriptive fields.

### `annotate_layer_with_issues()` / `build_quality_feature_frame()`

Purpose:
- add ML-ready QA annotation columns to a tabular or GeoDataFrame-like layer
- expose per-feature issue counts, severities, repair hints, and simple quality scores

Use for:
- tagging records as valid vs flagged before model training
- attaching QA metadata to feature tables
- building downstream quality-aware training datasets

### `export_annotated_dataset()` / `export_issue_features()`

Purpose:
- export validation-enriched outputs into training-friendly formats

Supported dataset exports:
- `csv`
- `jsonl`
- `geoparquet`

Supported issue-feature exports:
- `jsonl`
- `csv`

Use for:
- ML ingestion
- dataset interchange
- lightweight feature engineering pipelines

### `drop_null_geometries()` / `remove_duplicate_vertices()`

Purpose:
- Reusable fix helpers for conservative geometry cleanup workflows.

Use for:
- removing records with null geometries
- deduplicating consecutive geometry vertices before rerunning validation

Notes:
- keep these fixes importable for user scripts
- `remove_duplicate_vertices()` requires Shapely-compatible geometry handling

### `make_geometries_valid()` / `apply_basic_geometry_fixes()`

Purpose:
- provide a deterministic first-pass geometry cleaning utility before more advanced validation or agent-assisted review

Use for:
- repairing simple polygon invalidity where possible
- bundling conservative cleanup steps into one reusable function

Typical sequence:
- drop null geometries
- remove duplicate vertices
- make invalid polygonal geometries valid where possible

### `load_vector_dataset()` / `export_vector_layer()` / `convert_vector_dataset()`

Purpose:
- support local vector-format conversion workflows that complement validation and fixing

Supported input patterns:
- GeoJSON
- GPKG
- KML
- CSV with longitude/latitude columns
- other formats readable through GeoPandas

Supported output formats:
- `geojson`
- `csv`
- `geoparquet`
- `gpkg`
- `kml`
- `shapefile` (exported as a zip archive)

Use for:
- format normalization before validation
- result delivery for downstream GIS tools
- UI workflows such as the Streamlit app

### Agent auditability

Prefer keeping both:
- the issue report
- the final agent report

And when workflows matter for audit or QA signoff, also write:
- a fix-action log via `fix_log_path`

This keeps validation findings, user-approved fix actions, and any downstream review traceable.

## Validation Modules

### `geoqa.validations.attributes`

Available functions:
- `required_nulls(layer, required_fields)`
- `uniqueness(layer, field)`
- `domain_range_checks(layer, field, valid_domain)`

Use for:
- required attribute completeness
- duplicate key detection
- coded-domain or numeric-range validation

### `geoqa.validations.crs`

Available functions:
- `missing_crs(layer)`
- `invalid_crs(layer, expected_crs)`

Use for:
- missing spatial reference checks
- expected CRS conformance checks

### `geoqa.validations.metadata`

Available functions:
- `missing_metadata_fields(metadata)`
- `incomplete_metadata(metadata)`

Use for:
- core metadata presence checks
- extent/lineage completeness checks

### `geoqa.validations.accuracy`

Available functions:
- `coordinate_precision(layer, max_decimal_places=...)`
- `xy_tolerance(layer, max_tolerance=...)`
- `positional_accuracy(layer, reference_layer, tolerance=...)`

Use for:
- overly precise coordinate storage
- coarse XY tolerance metadata
- distance-to-reference accuracy checks

### `geoqa.validations.integrity`

Available functions:
- `missing_spatial_index(layer)`
- `outdated_index(layer)`
- `non_rfc7946_geojson(geojson_input)`

Use for:
- missing or stale index state checks
- maintenance-state checks for indexes
- GeoJSON RFC 7946 compliance checks

### `geoqa.validations.topology`

Available functions:
- `polygon_overlap_same_layer(layer)`
- `feature_within_feature(layer)`
- `line_intersection_same_layer(layer)`

Use for:
- same-layer polygon overlap checks
- nested feature detection within a layer
- same-layer line intersection checks

### `read_cpu_temps_c()`

Purpose:
- Returns a list of CPU temperatures in Celsius.

Typical use:

```python
from geoqa import read_cpu_temps_c

temps = read_cpu_temps_c()
```

Notes:
- Returns an empty list if no backend can read CPU temperatures.

### `run_temperature_diagnostic()`

Purpose:
- Performs a live probe to determine whether GeoQA can read CPU temperatures.
- Explains the active backend or why readings are unavailable.

Return fields:
- `ok`
- `platform`
- `source`
- `temperatures_c`
- `message`
- `options`

Typical use:

```python
from geoqa import run_temperature_diagnostic

diag = run_temperature_diagnostic()
if not diag.ok:
    print(diag.message)
    for option in diag.options:
        print("-", option)
```

### `read_temperature_snapshot()`

Purpose:
- Returns summarized temperature state for the current machine.

Typical use:

```python
from geoqa.thermal import read_temperature_snapshot

snap = read_temperature_snapshot()
print(snap.max_temp_c, snap.avg_temp_c, snap.sensor_count, snap.source)
```

## Patterns/Best Practices

### Reuse `ValidationIssue` for validator output

All validators should return lists of `ValidationIssue` objects rather than ad hoc dictionaries or tuples.
This keeps report generation, filtering, and future agent orchestration consistent.

### Use catalog-backed issue metadata where practical

When a validator corresponds to a `problem_name` in `raw_problems_with_sources.json`, prefer pulling:
- `severity`
- `description`
- `repair_hint`

This keeps validator behavior aligned with the central GeoQA problem catalog.

### Organize validators by theme

Prefer modules such as:
- `geoqa.validations.geometry`
- `geoqa.validations.attributes`
- `geoqa.validations.crs`
- `geoqa.validations.topology`
- `geoqa.validations.metadata`

This keeps the validation engine modular and matches the project roadmap.

### Use `codex_prompt.md` as the canonical prompt source

When GeoQA work is being performed by Codex or another coding assistant:
- treat `codex_prompt.md` as the primary reusable prompt file
- keep examples and workflow expectations aligned with that file
- update `AGENTS.md`, `SKILLS.md`, and `codex_prompt.md` together when prompt policy changes

### Prefer `GeoQAScriptBase` for new scripts

Use `GeoQAScriptBase` when building new GeoQA workflows. It gives you:
- startup diagnostics
- runner integration
- consistent thermal-safe execution
- cleaner extension points than ad hoc loops

### Use `ThermalRunner` for CPU-intensive loops

If a task iterates over many records, features, or validation units, do not write an unconstrained raw loop when the work is CPU-heavy.

Preferred pattern:

```python
runner.run_iterable(items, process_item)
```

Note:
- `ThermalRunner` now performs an explicit post-step cooldown pass when the machine is still above the warning threshold after a step finishes.

### Keep direct printing limited

Printing is acceptable for the built-in startup diagnostic when `emit_thermal_diagnostic=True`.
For other output:
- prefer a custom `diagnostic_emitter`
- prefer logging or returned values
- avoid noisy library-side prints

### Explain missing sensors clearly

When temperature reads are unavailable:
- explain that the backend is unavailable
- state platform limitations
- suggest alternatives such as Core Temp, `psutil`, `lm-sensors`, or machine-specific tools

### Keep import paths cross-platform safe

Do not initialize Windows-only APIs at import time on non-Windows systems.
Use platform checks before touching Windows-only code.

### Preserve compatibility with current GeoQA workflows

New code should remain compatible with:
- `ThermalGuard`
- `ThermalRunner`
- `GeoQAScriptBase`

### Keep optional GIS dependencies lazy

Validation modules may depend on GeoPandas or Shapely, but the package should stay importable even when those dependencies are absent.
Guard optional imports or import them lazily inside functions where practical.

### Prefer explicit dataset type over inference

The agent can infer a likely dataset type from schema hints, but explicit user choice remains the preferred control path.
Use inference as secondary support or fallback only.

## Platform Notes

### Windows

- Preferred backend: Core Temp shared memory.
- Fallback backend: `psutil.sensors_temperatures()`.
- Core Temp is only available on Windows.
- Avoid import-time Windows API calls on non-Windows platforms.

### macOS

- Backend: `psutil` only.
- Some macOS systems do not expose CPU temperature sensors through `psutil`.
- GeoQA should remain importable and explain the limitation if no sensors are available.

### Linux

- Backend: `psutil` only.
- Sensor visibility depends on the system configuration and user access.
- `lm-sensors` or the distribution hardware monitoring stack may be required.

## Examples

### Example: geometry validation

```python
import geopandas as gpd

from geoqa.validations.geometry import null_geometry, self_intersection

layer = gpd.read_file("path/to/dataset.geojson")
issues = []
issues.extend(null_geometry(layer))
issues.extend(self_intersection(layer))
```

### Example: generate a report

```python
from geoqa.reports.report_generator import generate_report

generate_report(issues, output_format="csv", file_path="geometry_validation_report")
```

### Example: attribute validation

```python
from geoqa.validations.attributes import domain_range_checks, required_nulls, uniqueness

issues = []
issues.extend(required_nulls(layer, ["asset_id", "status"]))
issues.extend(uniqueness(layer, "asset_id"))
issues.extend(domain_range_checks(layer, "status", {"active", "retired"}))
```

### Example: metadata validation

```python
from geoqa.validations.metadata import incomplete_metadata, missing_metadata_fields

issues = []
issues.extend(missing_metadata_fields(metadata))
issues.extend(incomplete_metadata(metadata))
```

### Example: interactive validation

```python
from geoqa.interactive_validation import validate_dataset

results = validate_dataset(
    "path/to/dataset.geojson",
    "geometry",
    output_format="json",
    report_path="geometry_validation_report",
)
```

Current status:
- the interactive router supports `geometry`, `attributes`, `crs`, `metadata`, `accuracy`, `integrity`, and `topology`
- dataset-specific routing beyond those validation families is handled by the agent layer

### Example: agent workflow

```python
from geoqa.agent import run_agent_workflow

result = run_agent_workflow(
    "path/to/dataset.geojson",
    dataset_type="land_use",
    interactive=False,
)
```

Chunking notes:
- `run_agent_workflow(...)` now supports:
  - `validation_chunk_size`
  - `sleep_between_validation_chunks_seconds`
- This is intended for larger datasets where validation should pause between batches and stay aligned with GeoQA thermal safeguards.
- If a normal validation run hits thermal or runtime pressure in interactive mode, GeoQA can now offer a one-time chunked rerun with suggested settings.

### Example: reusable fixes

```python
from geoqa.fixes import drop_null_geometries, remove_duplicate_vertices

layer = drop_null_geometries(layer)
layer = remove_duplicate_vertices(layer)
```

### Example: thermal-safe script

```python
from geoqa import GeoQAScriptBase


class ValidateCatalog(GeoQAScriptBase[dict, bool]):
    def load_items(self) -> list[dict]:
        return [{"id": 1}, {"id": 2}]

    def process_item(self, item: dict) -> bool:
        return "id" in item


results = ValidateCatalog().run()
```

### Example: disable startup diagnostic

```python
ValidateCatalog(emit_thermal_diagnostic=False).run()
```

### Example: custom diagnostic emitter

```python
from geoqa import GeoQAScriptBase
from geoqa.thermal import TemperatureDiagnostic


def emitter(diag: TemperatureDiagnostic) -> None:
    send_to_logger(diag.message, extra={"source": diag.source, "options": diag.options})
```

### Example: annotate GeoQA scripts

Purpose:
- Recursively annotate Python files that subclass `GeoQAScriptBase`.
- Adds a top comment block only once per matching file.

Command:

```powershell
python scripts/annotate_geoqa_scripts.py .
```

Implementation notes:
- standard library only
- recursive directory scan
- AST-based subclass detection
- skips non-matching files

## Optional AGENTS.md Follow-Up

`AGENTS.md` now includes validation-engine rules for `ValidationIssue`, validation module layout, report generation reuse, and lazy optional GIS dependencies.
