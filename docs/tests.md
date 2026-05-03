# GeoQA Tests

This document records what testing has been performed, which datasets were used, what the scripts were intended to verify, what was found, and whether each run should be considered successful.

For raw artifacts from the first real-dataset integration pass, see:
- `data/integration_results/`

For local/internal dataset runs, see:
- `docs/local_data_tests.md`

For a shorter credibility narrative based only on the public benchmark runs already recorded in this repository, see:
- `docs/benchmark_story.md`

## Test Status Legend

- `successful`: the workflow completed as intended
- `partially successful`: the workflow produced useful output but did not complete fully
- `failed`: the workflow did not complete as intended
- `null result`: the targeted check found no issues; this can still be a successful test

## Environment

Run environment for the current recorded test pass:
- date: `2026-03-21`
- Python: `3.12.10`
- `geopandas`: `1.1.3`
- `shapely`: `2.1.2`
- `pyproj`: `3.7.2`
- machine note: heat-sensitive workstation using GeoQA thermal guards during heavier runs

## Test Summary

| Dataset / Scope | Workflow | Status | Issues Found | Null Result | Fixes Applied | Interactive | Issue Type | Thermal Event |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| Unit test suite | `unittest discover` | successful | n/a | n/a | no | no | n/a | no |
| CLI smoke tests | `tests.test_cli` | successful | n/a | n/a | no | no | n/a | no |
| Execution/runtime tests | `tests.test_execution` | successful | n/a | n/a | no | no | n/a | no |
| Report generator tests | `tests.test_report_generator` | successful | n/a | n/a | no | no | n/a | no |
| Validation runtime tests | `tests.test_validation_runtime` | successful | n/a | n/a | no | no | n/a | no |
| DMA plugin tests | `tests.test_plugins_dma` | successful | n/a | n/a | no | no | n/a | no |
| Water network pack tests | `tests.test_water_network_pack` | successful | n/a | n/a | no | no | n/a | no |
| ML helper tests | `tests.test_ml` | successful | n/a | n/a | no | no | n/a | no |
| Conversion helper tests | `tests.test_conversion` | successful | n/a | n/a | no | no | n/a | no |
| Natural Earth countries | `run_agent_workflow(..., dataset_type="generic")` | successful | `178` | no | no | no | data issue | no |
| Natural Earth countries CRS rerun | `crs_validation(...)` | successful | `0` | yes | no | no | clean/null | no |
| Natural Earth countries CRS | `crs_validation(...)` | successful | `0` | yes | no | no | clean/null | no |
| Philadelphia FEMA flood plain 2023 | `run_agent_workflow(..., dataset_type="flood_zones")` | successful | `1` | no | no | no | data issue | no |
| Philadelphia zoning base districts | `run_agent_workflow(..., dataset_type="land_use")` | partially successful | `1` | no | no | no | operational issue | yes |
| Natural Earth admin-1 states/provinces | `run_agent_workflow(..., dataset_type="generic")` | successful | `4598` | no | no | no | data issue | no |
| Natural Earth admin-1 states/provinces GPKG | `crs_validation(...)` | successful | `0` | yes | no | no | clean/null | no |
| Natural Earth lakes | `run_agent_workflow(..., dataset_type="generic")` | successful | `1375` | no | no | no | data issue | yes |
| Natural Earth roads | `run_agent_workflow(..., dataset_type="generic")` | partially successful | `56602` | no | no | no | mixed | yes |
| Natural Earth roads strict chunked rerun | `run_agent_workflow(..., validation_chunk_size=750, sleep=3.0)` | partially successful | n/a | n/a | no | no | operational issue | yes |
| Natural Earth roads adaptive rerun | `run_agent_workflow(..., validation_chunk_size=750, target_vertices=60000, cool thermal profile)` | partially successful | n/a | n/a | no | no | operational issue | no |
| Natural Earth roads low-resource benchmark | `python -m geoqa benchmark ... --low-resource --max-runtime-seconds 180` | successful | `49` | no | no | no | data issue | no |
| Philadelphia zoning adaptive rerun | `run_agent_workflow(..., validation_chunk_size=500, target_vertices=40000, cool thermal profile)` | partially successful | n/a | n/a | no | no | operational issue | no |

## Evidence Tiers

### 1. Automated Suite Evidence

What this proves:
- public API stability for the tested surface
- runtime behavior for profiles, caching, limits, partial execution, and report summaries
- CLI coverage for the common operator paths

Current baseline:
- `python -m unittest discover -s tests -p 'test_*.py'`
- result: `OK` (`159` tests)

### 2. Public Benchmark Evidence

What this proves:
- GeoQA has been run on real public vector data
- the recorded issue counts and partial-run behavior are based on actual repo fixtures and open datasets

See:
- `docs/benchmark_story.md`

### 3. Local / Private Anonymized Evidence

What this proves:
- GeoQA has also been exercised on real non-public operational data
- the ledger records findings and operational behavior without naming those datasets

See:
- `docs/local_data_tests.md`

### 4. Heavy Partial-Run Evidence

What this proves:
- GeoQA handles thermal and runtime pressure honestly
- heavy public runs can still be throughput-limited on the maintainer workstation
- adaptive runtime behavior is helping, but does not yet make the heaviest runs trivial

## Rerun Guidance

Common rerun commands:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python -m unittest tests.test_validation_runtime
python -m unittest tests.test_ml
python -m unittest tests.test_conversion
python scripts/validate_problem_catalog.py
python scripts/run_integration_samples.py --profile natural_earth_countries_crs --output data/integration_results/integration_summary_metrics.json
python scripts/run_integration_samples.py --profile natural_earth_admin1_gpkg_crs --profile natural_earth_lakes_generic --profile natural_earth_admin1_generic --output data/integration_results/integration_summary_expanded_safe.json
python scripts/run_integration_samples.py --profile natural_earth_roads_generic --output data/integration_results/integration_summary_roads.json
```

Integration outputs are written under:
- `data/integration_results/`

## Test Categories

### Unit Tests

Purpose:
- verify validators, fix helpers, reporting, wrapper imports, and agent logic in isolation

Run date:
- `2026-03-20`

Command used:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Latest result:
- `OK`

What this means:
- the current unit and lightweight integration-style test suite passed in this environment after the core validation-runtime extensions, bounded parallel execution, spatial-index-aware topology/reference checks, runtime hardening, signal-calibration fields, profile policy application, and adaptive chunking slice
- the suite now also covers the `geoqa.ml` annotation, feature, and export helpers
- the suite now also covers chunked validation orchestration in the agent layer
- the suite now also covers chunking recommendation and interactive rerun behavior
- the suite now also covers:
  - custom validator registration
  - validation profiles
  - progress callback events
  - in-memory and file-backed validation caching
  - preflight validation limits
  - spatial-index-aware topology/reference candidate selection

Latest suite count:
- `144` tests

### Validation Runtime Tests

Purpose:
- verify the new core validation-runtime layer directly
- confirm custom validator registration, profile filtering, progress events, bounded parallelism, cache reuse, and validation limits

Command used:

```powershell
python -m unittest tests.test_validation_runtime
```

Latest result:
- `OK`

What was verified:
- custom validators can be registered and executed
- profiles can narrow validator execution
- progress callbacks emit started/completed events
- progress callbacks now also carry:
  - progress percent
  - ETA
  - chunk index / chunk total placeholders for chunk-aware paths
- bounded parallel execution works through `max_workers`
- `InMemoryValidationCache` reuses results within a process
- `FileValidationCache` reuses results across repeated calls
- `ValidationLimits` fail early on oversized feature counts or source-file sizes
- runtime context now supports additional domain-pack wiring such as role-aware endpoint handling
- constrained runs can now prioritize high-value validators first and defer lower-priority work once actionable targets are reached

### Water Network Pack Tests

Purpose:
- verify the first fuller domain-pack slice rather than only generic profile routing

Command used:

```powershell
python -m unittest tests.test_water_network_pack
```

Latest result:
- `OK`

What was verified:
- structured schema detection for water-network-like layers
- dangle vs allowed terminal/service-endpoint distinction
- isolated segment detection
- suspicious near-miss endpoint detection
- unsnapped endpoint detection within tolerance
- schema-aware attribute checks
- profile suppression behavior for precision-related noise
- pack summaries now include junction counts, terminal-endpoint counts, thresholds, and clearer schema explanations

### Accuracy Validation Tests

Purpose:
- verify that precision and XY-tolerance findings are less noisy on broad datasets
- confirm CRS-aware and scale-aware defaults behave differently from local small-extent checks

Command used:

```powershell
python -m unittest tests.test_accuracy_validation
```

Latest result:
- `OK`

What was verified:
- broad geographic extents now get a more permissive adaptive coordinate-precision threshold
- local small-extent geographic features still trigger precision findings when over-precise
- broad projected extents now get a more realistic adaptive XY tolerance threshold

### CLI Tests

Purpose:
- verify the CLI is a working operational surface rather than documentation only

Command used:

```powershell
python -m unittest tests.test_cli
```

Latest result:
- `OK`

What was verified:
- `python -m geoqa validate ...` writes a real report
- `python -m geoqa validate ... --fail-on-error` now has explicit CLI coverage for non-zero exit behavior when issues are present
- `python -m geoqa validate ...` now has explicit end-to-end CLI coverage for:
  - `--max-workers`
  - `--chunk-size`
  - `--sleep`
  - `--thermal-profile`
  - `--low-resource`
  - `--max-features`
  - `--max-size-mb`
  - `--cache`
  - `--cache-tag`
  - `--max-runtime-seconds`
  - `--max-issues`
  - `--stop-after-actionable`
  - `--progress`
- `python -m geoqa benchmark ...` now also has human-readable CLI coverage, not only JSON-path smoke coverage
- cache reuse through the CLI is now verified by a second run showing `cache-hit` in progress output
- `python -m geoqa profiles list` exposes the built-in profiles
- `python -m geoqa report summarize ...` now emits a readable operator summary by default
- `python -m geoqa report stats ...` now has explicit CLI coverage for row-count output and operator summary text
- `python -m geoqa profiles show ...` now exposes downgrade and suppression fields as part of the profile contract
- `python -m geoqa benchmark ...` now has an automated smoke test that verifies the structured benchmark summary payload
- low-resource mode now has automated CLI coverage for constrained-runtime operator behavior
- CLI smoke tests now run with a dedicated thermal-guard bypass flag so automated verification stays deterministic on warm machines

### Execution Tests

Purpose:
- verify the higher-level profile execution layer that sits above the runtime and below the CLI

Command used:

```powershell
python -m unittest tests.test_execution
```

Latest result:
- `OK`

What was verified:
- `validate_dataset_with_profile(...)` executes a full profile against a real sample dataset
- report writing works through the execution layer
- structured execution summary data is returned
- profile-level validator options now tune runtime thresholds correctly
- suppression and calibration behavior still hold after the richer report/output changes
- domain-pack profiles now exercise pack-specific topology behavior
- `max_runtime_seconds` can stop an execution cleanly while still producing a structured result
- structured execution summaries now expose:
  - `execution_status`
  - `execution_reason`
  - `validators_completed`
  - `validators_deferred`
  - `partial_result`
  - `operator_next_steps`
- profile policies can also override issue priority score for domain-specific triage
- downgrade rules can now be expressed explicitly at the profile level
- suppression rules can now be expressed explicitly at the profile level

### Report Generator Tests

Purpose:
- verify richer machine-readable summaries for decision-ready reports

Command used:

```powershell
python -m unittest tests.test_report_generator
```

Latest result:
- `OK`

What was verified:
- summaries now include:
  - `total_issues`
  - `actionable`
  - `informational`
  - `actionable_ratio`
  - `severity_distribution`
  - `problem_breakdown`
  - `by_root_cause`
  - `by_priority_band`
  - `top_actionable`
  - `top_issues`
- a human-readable summary formatter now produces operator-oriented output for the CLI
- report reloading now preserves provenance and suppression metadata for JSON-backed summaries
- the human-readable summary now also surfaces root-cause groups when provenance exists
- report loading remains backward-compatible with earlier payload shapes

### Agent Runtime Tests

Purpose:
- verify chunk-aware orchestration and adaptive runtime behavior in the agent layer

Command used:

```powershell
python -m unittest tests.test_agent
```

Latest result:
- `OK`

What was verified:
- geometry-weighted chunking still works
- thermal pressure can trigger adaptive chunk-size reduction
- runtime messages record chunk-downsizing decisions
- low-resource execution defaults now have CLI-level verification

### ML Helper Tests

Purpose:
- verify that QA annotations can be attached to datasets
- verify that issue-derived feature rows can be generated
- verify ML-ready exports in CSV and JSONL formats

Command used:

```powershell
python -m unittest tests.test_ml
```

Latest result:
- `OK`

What was verified:
- annotated layers include expected QA columns
- quality feature frames include per-problem indicator columns
- issue feature rows include severity-rank information
- annotated dataset export works for:
  - CSV
  - JSONL
- issue-feature export works for:
  - JSONL

### Conversion Helper Tests

Purpose:
- verify local vector-format conversion helpers
- verify CSV point loading
- verify preview and metadata summaries

Command used:

```powershell
python -m unittest tests.test_conversion
```

Latest result:
- `OK`

What was verified:
- GeoJSON export works from a loaded GeoDataFrame
- CSV point datasets can be loaded into a GeoDataFrame-like layer
- preview GeoJSON and layer-summary helpers produce usable output

### Catalog Validation

Purpose:
- verify the curated problem catalog still satisfies the required schema and uniqueness rules

Command used:

```powershell
python scripts/validate_problem_catalog.py
```

Latest result:
- `Catalog validation passed.`

What was verified:
- catalog JSON parses successfully
- required fields remain present
- `problem_name` values remain unique

### Fresh Public Baseline Rerun

Purpose:
- confirm that at least one public baseline workflow still runs cleanly after the newest runtime changes

Run date:
- `2026-03-19`

Command used:

```python
crs_validation(
    "data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp",
    expected_crs="EPSG:4326",
    output_format="json",
    report_path="data/integration_results/natural_earth_countries_crs_2026_03_19",
    auto_fix=False,
)
```

What was found:
- zero CRS issues
- output written successfully as:
  - `data/integration_results/natural_earth_countries_crs_2026_03_19.json`

Was the test successful:
- yes

Why:
- it confirms that the core validation/runtime changes did not break a lightweight public baseline workflow

### Fresh Public Stress Rerun

Purpose:
- retry one of the previously heat-sensitive large public datasets using explicit chunking plus a conservative thermal profile

Run date:
- `2026-03-19`

Command shape used:

```python
run_agent_workflow(
    "data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp",
    dataset_type="generic",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/natural_earth_roads_chunked_issues_2026_03_19",
    final_report_format="json",
    final_report_path="data/integration_results/natural_earth_roads_chunked_agent_2026_03_19",
    batch_size=250,
    validation_chunk_size=750,
    sleep_between_validation_chunks_seconds=3.0,
    thermal_guard=ThermalGuard.strict(
        log_path="data/integration_results/natural_earth_roads_chunked_thermal_2026_03_19.jsonl"
    ),
)
```

What was found:
- the run did enter the chunked-validation path
- it did not complete successfully
- the conservative thermal guard remained the limiting factor during the first chunk cooldown stage
- the recorded thermal log shows the guard eventually aborted at:
  - `73.0 C`
  - above the configured hard limit of `70.0 C`

Generated artifact:
- `data/integration_results/natural_earth_roads_chunked_thermal_2026_03_19.jsonl`

Was the test successful:
- partially

Why:
- the rerun confirms that chunking alone is not enough for this dataset under a strict thermal profile on the current workstation
- it also gives a concrete current baseline for the roadmap item around adaptive chunk sizing and smarter thermal backoff

### Fresh Public Adaptive Reruns

Purpose:
- retry the heaviest public workloads after the newer adaptive chunking and runtime work
- determine whether the current limiter is still thermal failure or overall runtime cost

Run date:
- `2026-03-20`

Profiles tested:
- Natural Earth roads with:
  - `validation_chunk_size=750`
  - `validation_target_vertices_per_chunk=60000`
  - `sleep_between_validation_chunks_seconds=3.0`
  - `ThermalGuard.cool(...)`
- Philadelphia zoning base districts with:
  - `validation_chunk_size=500`
  - `validation_target_vertices_per_chunk=40000`
  - `sleep_between_validation_chunks_seconds=2.0`
  - `ThermalGuard.cool(...)`

What was found:
- both reruns advanced deep into the chunked-validation path
- neither rerun completed within the one-hour execution budget used for this pass
- neither rerun showed a thermal-limit trip in the recorded logs
- the roads rerun reached at least:
  - `validation_chunk_1009_*`
- the zoning rerun reached at least:
  - `validation_chunk_1686_*`
- recorded temperatures remained comfortably below the configured hard limit during the tail of both runs

Generated artifacts:
- `data/integration_results/natural_earth_roads_adaptive_thermal_2026_03_20.jsonl`
- `data/integration_results/philly_zoning_adaptive_thermal_2026_03_20.jsonl`

Was the test successful:
- partially

Why:
- these reruns do show a real improvement over the earlier heat-triggered runs:
  - the immediate failure mode has shifted away from thermal trips
  - the remaining blocker is throughput / validator cost on this workstation
- they do not yet count as full success because neither heavy run completed inside the allotted wall-clock budget

### Fresh Low-Resource Public Benchmark Rerun

Purpose:
- verify that the new low-resource operator path is useful on a heavier public dataset
- confirm that a constrained run can complete honestly on the maintainer workstation instead of only producing partial heavy-run evidence

Run date:
- `2026-03-20`

Command used:

```powershell
python -m geoqa benchmark data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag roads_low_resource_2026_03_20 --progress
```

What was found:
- the benchmark completed successfully
- duration: about `121.9` seconds
- feature count: `56,600`
- issue count: `49`
- execution status: `full`
- dominant findings were:
  - `duplicate_vertex`: `42`
  - `self_intersection`: `6`
  - `missing_or_stale_spatial_index`: `1`

Was the test successful:
- yes

Why:
- this is the first heavier public proof that low-resource mode is not only a runtime concept
- the run completed within the bounded runtime window on the maintainer workstation
- the output still remained actionable and structured

### Streamlit App Note

The Streamlit app entry point was added as a user interface layer, but it is not currently exercised in the automated unit suite.

Why:
- the current automated testing focus remains on the deterministic library functions underneath the app
- the app mostly composes existing conversion and fix helpers rather than introducing separate spatial logic

Related coverage:
- the underlying conversion tests now include Shapefile upload-bundle reconstruction logic
- this covers the new app behavior where users can upload either a zipped Shapefile or the full `.shp` / `.dbf` / `.shx` set together
- the conversion tests now also cover a geometry-safe table-preview helper used by the app

### Integration Runner Infrastructure

Purpose:
- provide a repeatable script for running selected public-sample workflows
- capture timing, dataset size, geometry mix, and thermal snapshot data
- make future integration checks easier to compare against a documented baseline

Script:
- `scripts/run_integration_samples.py`

Supporting sample area:
- `data/public_samples/edge_cases/`

Verified lightweight runner command:

```powershell
python scripts/run_integration_samples.py --profile natural_earth_countries_crs --output data/integration_results/integration_summary_metrics.json
```

Verified result:
- `OK`

What was recorded:
- run duration
- dataset file size
- feature count
- column count
- CRS
- geometry type counts
- post-run thermal snapshot

Example verified metrics from the lightweight CRS profile:
- duration: `4.194` seconds
- feature count: `177`
- geometry types:
  - `Polygon: 148`
  - `MultiPolygon: 29`
- post-run max CPU temperature: `61.0 C`

## Real-Dataset Integration Runs

### 1. Natural Earth Countries

Dataset:
- `data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp`

Run date:
- `2026-03-18`

Workflow tested:
- generic validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- data issue

Command used:

```python
run_agent_workflow(
    "data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp",
    dataset_type="generic",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/natural_earth_countries_issues",
    final_report_format="json",
    final_report_path="data/integration_results/natural_earth_countries_agent",
    batch_size=25,
)
```

What the script was testing:
- end-to-end dataset loading
- generic validation routing
- report generation
- JSON serialization of issue payloads

Expected behavior:
- the dataset should load successfully
- the generic validation path should complete
- reports should be written even if issues are found

What was found:
- `178` issues were reported
- the dominant findings were coordinate-precision-style issues on a large number of features
- report files were written successfully

Was the test successful:
- yes

Why:
- the workflow executed fully and produced issue and agent reports
- this run also verified that geometry payloads can now be serialized safely in JSON reports

Was the dataset null / no-problem:
- no

Why not:
- the generic validator flagged multiple issues, especially precision-related findings

Generated outputs:
- `data/integration_results/natural_earth_countries_issues.json`
- `data/integration_results/natural_earth_countries_agent.json`

### 2. Natural Earth Countries CRS Automation

Dataset:
- `data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp`

Run date:
- `2026-03-18`

Workflow tested:
- `geoqa.automation.crs_validation(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- clean/null

Command used:

```python
crs_validation(
    "data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp",
    expected_crs="EPSG:4326",
    output_format="json",
    report_path="data/integration_results/natural_earth_countries_crs",
    auto_fix=False,
)
```

What the script was testing:
- CRS loading
- missing/invalid CRS checks
- CRS report generation

Expected behavior:
- the dataset should load successfully
- CRS checks should run cleanly
- the workflow should produce a report even if zero issues are found

What was found:
- no CRS issues were detected

Was the test successful:
- yes

Why:
- the script ran correctly and produced a clean result
- a null result is still a valid success when the purpose of the test is to confirm that a dataset passes the targeted check

Was the dataset null / no-problem:
- yes

Why:
- this dataset already matched the expected CRS and did not need fixing

Generated output:
- `data/integration_results/natural_earth_countries_crs.json`

### 3. Philadelphia FEMA Flood Plain 2023

Dataset:
- `data/public_samples/data_gov/philadelphia_fema_flood_plain_2023.geojson`

Run date:
- `2026-03-18`

Workflow tested:
- flood-zone validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- data issue

Command used:

```python
run_agent_workflow(
    "data/public_samples/data_gov/philadelphia_fema_flood_plain_2023.geojson",
    dataset_type="flood_zones",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/philly_floodplain_issues",
    final_report_format="json",
    final_report_path="data/integration_results/philly_floodplain_agent",
    batch_size=100,
)
```

What the script was testing:
- GeoJSON loading
- flood-zone routing
- attribute and geometry validation path for a real city open-data dataset
- report generation

Expected behavior:
- the GeoJSON should load successfully
- flood-zone validation should complete
- the workflow should write reports and surface any real issues found

What was found:
- `1` issue was reported
- the run completed without runtime messages

Was the test successful:
- yes

Why:
- the workflow completed end to end and wrote the expected reports
- the presence of one issue does not mean the test failed; the script is supposed to detect issues when they exist

Was the dataset null / no-problem:
- no

Why not:
- one issue was detected by the flood-zone validation path

Generated outputs:
- `data/integration_results/philly_floodplain_issues.json`
- `data/integration_results/philly_floodplain_agent.json`

### 4. Philadelphia Zoning Base Districts

Dataset:
- `data/public_samples/data_gov/philadelphia_zoning_base_districts.geojson`

Run date:
- `2026-03-18`

Workflow tested:
- land-use validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- operational issue

Command used:

```python
run_agent_workflow(
    "data/public_samples/data_gov/philadelphia_zoning_base_districts.geojson",
    dataset_type="land_use",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/philly_zoning_issues",
    final_report_format="json",
    final_report_path="data/integration_results/philly_zoning_agent",
    batch_size=100,
)
```

What the script was testing:
- larger GeoJSON loading
- land-use routing
- report generation under a heavier workload
- structured runtime-error capture during validation
- thermal-limit handling behavior

Expected behavior:
- the GeoJSON should load successfully
- the land-use validation path should start and attempt full report generation
- if the system gets too hot, the workflow should capture that condition instead of failing silently

What was found:
- `1` issue was reported
- the run recorded this message:
  - `geometry validation failed and was captured as an issue: CPU temperature is 79.0 C, above limit 74.0 C.`

Was the test successful:
- partially yes

Why:
- the script did not crash
- it wrote issue and agent reports
- it demonstrated that the thermal guard can interrupt a hot validation path and convert that event into a structured message instead of hard-failing silently

Why not fully:
- the geometry validation phase did not complete normally because the CPU hit the configured thermal limit
- this means the run is operationally useful, but not a full clean validation pass yet

Was the dataset null / no-problem:
- no

Why not:
- the reported result is not a clean pass; it includes a thermal-triggered validation interruption captured as an issue/message

Generated outputs:
- `data/integration_results/philly_zoning_issues.json`
- `data/integration_results/philly_zoning_agent.json`

### 5. Natural Earth Admin-1 States / Provinces

Dataset:
- `data/public_samples/natural_earth/ne_10m_admin_1_states_provinces/ne_10m_admin_1_states_provinces.shp`

Run date:
- `2026-03-18`

Workflow tested:
- larger polygon generic validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- data issue

Command used:

```python
run_agent_workflow(
    "data/public_samples/natural_earth/ne_10m_admin_1_states_provinces/ne_10m_admin_1_states_provinces.shp",
    dataset_type="generic",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/natural_earth_admin1_issues",
    final_report_format="json",
    final_report_path="data/integration_results/natural_earth_admin1_agent",
    batch_size=100,
)
```

What the script was testing:
- larger shapefile loading
- generic validation routing on a denser polygon dataset
- report generation on a bigger attribute and geometry payload

Expected behavior:
- the shapefile should load successfully
- generic validation should complete
- reports should be written for a larger admin-boundary layer

What was found:
- `4598` issues were reported
- the run completed without thermal interruption
- report files were written successfully

Was the test successful:
- yes

Why:
- the larger polygon dataset completed end to end
- this extended the baseline beyond the earlier smaller admin-0 countries layer

Was the dataset null / no-problem:
- no

Why not:
- the generic validator reported a large number of issues on the admin-1 layer

Generated outputs:
- `data/integration_results/natural_earth_admin1_issues.json`
- `data/integration_results/natural_earth_admin1_agent.json`

### 6. Natural Earth Admin-1 States / Provinces GeoPackage CRS Automation

Dataset:
- `data/public_samples/derived/ne_10m_admin_1_states_provinces.gpkg`

Run date:
- `2026-03-18`

Workflow tested:
- `geoqa.automation.crs_validation(...)` on GeoPackage input

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- clean/null

Command used:

```python
crs_validation(
    "data/public_samples/derived/ne_10m_admin_1_states_provinces.gpkg",
    expected_crs="EPSG:4326",
    output_format="json",
    report_path="data/integration_results/natural_earth_admin1_gpkg_crs",
    auto_fix=False,
)
```

What the script was testing:
- GeoPackage loading
- CRS validation on non-shapefile vector input
- report generation for format-coverage expansion

Expected behavior:
- the GeoPackage should load successfully
- CRS validation should complete and write a report

What was found:
- no CRS issues were detected

Was the test successful:
- yes

Why:
- the derived GeoPackage loaded successfully
- this confirms that the CRS automation path works on GPKG as well as shapefile input

Was the dataset null / no-problem:
- yes

Why:
- the derived dataset already matched the expected CRS and required no correction

Generated output:
- `data/integration_results/natural_earth_admin1_gpkg_crs.json`

### 7. Natural Earth Lakes

Dataset:
- `data/public_samples/natural_earth/ne_10m_lakes/ne_10m_lakes.shp`

Run date:
- `2026-03-18`

Workflow tested:
- physical/environment-style generic validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- data issue

Command used:

```python
run_agent_workflow(
    "data/public_samples/natural_earth/ne_10m_lakes/ne_10m_lakes.shp",
    dataset_type="generic",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/natural_earth_lakes_issues",
    final_report_format="json",
    final_report_path="data/integration_results/natural_earth_lakes_agent",
    batch_size=100,
)
```

What the script was testing:
- physical/environment-style shapefile loading
- generic validation on a moderate polygon dataset
- cooldown handling after a hotter run phase

Expected behavior:
- the shapefile should load successfully
- generic validation should complete and write reports
- if the system warms up, the post-run cooldown path should remain cooperative

What was found:
- `1375` issues were reported
- the run completed successfully
- the post-run cooldown path triggered after the maximum observed temperature reached `73.0 C`

Was the test successful:
- yes

Why:
- the validation completed and wrote reports
- the thermal guard handled the hotter post-run state without causing workflow failure

Was the dataset null / no-problem:
- no

Why not:
- the generic validation path reported issues on the lakes dataset

Generated outputs:
- `data/integration_results/natural_earth_lakes_issues.json`
- `data/integration_results/natural_earth_lakes_agent.json`
- `data/integration_results/integration_summary_expanded_safe.json`

### 8. Natural Earth Roads

Dataset:
- `data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp`

Run date:
- `2026-03-18`

Workflow tested:
- larger network-style generic validation through `run_agent_workflow(...)`

Interactive:
- no

Fixes applied:
- no

Issue type classification:
- mixed

Command used:

```python
run_agent_workflow(
    "data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp",
    dataset_type="generic",
    interactive=False,
    issue_report_format="json",
    issue_report_path="data/integration_results/natural_earth_roads_issues",
    final_report_format="json",
    final_report_path="data/integration_results/natural_earth_roads_agent",
    batch_size=250,
)
```

What the script was testing:
- larger line/network-style shapefile loading
- generic validation behavior on a much larger feature count
- structured thermal-interruption capture on a heavy line dataset

Expected behavior:
- the shapefile should load successfully
- generic validation should attempt a full run
- if the system gets too hot, the workflow should capture that condition as structured output

What was found:
- `56602` issues were reported
- the run recorded this message:
  - `geometry validation failed and was captured as an issue: CPU temperature is 77.0 C, above limit 74.0 C.`
- the post-run cooldown path also engaged after the maximum observed temperature reached `73.0 C`

Was the test successful:
- partially yes

Why:
- the larger network-style dataset loaded successfully
- the workflow produced issue and agent reports instead of crashing
- the run demonstrated that the thermal guard still works on a substantially larger line dataset

Why not fully:
- the geometry-validation phase did not complete normally because the CPU exceeded the configured limit
- the final report therefore reflects both data findings and an operational interruption

Was the dataset null / no-problem:
- no

Why not:
- this was not a clean pass; the run included a thermal-triggered validation runtime issue

Generated outputs:
- `data/integration_results/natural_earth_roads_issues.json`
- `data/integration_results/natural_earth_roads_agent.json`
- `data/integration_results/integration_summary_roads.json`

## Findings From Testing

### Code-level Findings

1. JSON report serialization originally failed on live geometry objects.
- status: fixed
- outcome:
  - `ValidationIssue.to_dict()` now converts geometry payloads into JSON-safe values

2. Self-crossing linework was not reliably detected by the geometry validator.
- status: fixed
- outcome:
  - line self-intersection detection now also uses non-simple line checks

3. The first downloaded copies of the Philadelphia GeoJSON files were truncated.
- status: fixed
- outcome:
  - the files were re-downloaded successfully with a more reliable transfer method

### Operational Findings

1. Real-dataset testing is now working in this environment.
- `geopandas`, `shapely`, and `pyproj` had to be installed first

2. Thermal limits can still interrupt heavier validation runs.
- this is not hidden anymore
- GeoQA now captures that condition as a structured message instead of failing silently

3. Local/internal dataset runs are tracked separately.
- see `docs/local_data_tests.md` for the anonymized private local-data integration record and future local-data additions

3. Larger real datasets now expose a clearer distinction between:
- clean larger runs
- successful runs with guarded cooldown
- partial runs with structured thermal interruption

## How to Read Null Results

In GeoQA testing, a null result means:
- the test itself succeeded
- the targeted validator did not find any issues for that dataset and workflow

Example:
- the Natural Earth CRS automation run was null because there were no CRS problems to report

That should be recorded as:
- test successful
- dataset clean for that specific check
