# GeoQA Journal

- Author: Nilofer Taher
- Started: 2026-03-18 14:26:51 +04:00
- Project note: Substantive project changes should be logged here with both the change itself and the reasoning behind it.

## 2026-03-21 12:10:00 +04:00

### Planning update: best-effort plugin execution on partial runs

- Recorded a later runtime refinement in the planning docs:
  - explicit `run_plugins_on_partial=True`
- Reasoning:
  - current default is intentionally conservative: plugins run only after a clean core validation completion path
  - on constrained workstations, a runtime-/thermal-limited partial run may still benefit from domain-specific best-effort plugin findings
  - this should be explicit behavior, not silent fallback
- Guardrails captured in the planning docs:
  - allow only when the layer loaded successfully
  - allow only for runtime / thermal / budget stop reasons
  - do not run for invalid-input or hard-limit failures
  - report the result clearly as partial core validation with best-effort plugin coverage

## 2026-03-21 12:25:00 +04:00

### Future-doc cleanup

- Created `docs/future/` to separate future-only architecture and staged execution plans from shipped user/operator documentation.
- Moved the adapter architecture note into `docs/future/adapter_architecture_plan.md`.
- Added `docs/future/plan_of_action_codex.md` as a staged execution brief for later work.
- Updated main docs to point future planning into `docs/future/` so current guidance stays easier to scan.

## 2026-03-20 16:40:00 +04:00

### Public API layer added on top of the existing engine

- Added a new flat Python API in `geoqa/api.py`:
  - `geoqa.validate(...)`
  - `geoqa.score(...)`
- `geoqa.validate(...)` now returns a first-class `GeoQAReport` wrapper instead of exposing the raw execution result directly.
- `GeoQAReport` now provides:
  - `summary()`
  - `score()`
  - `to_ml()`
  - `to_dataframe()`
  - `export(...)`
- Added a lightweight expectation layer in:
  - `geoqa/expect/__init__.py`
  - `geoqa/expect/core.py`
- Added:
  - `geoqa.expect.valid_crs(...)`
  - `geoqa.expect.no_null_geometry(...)`
  - `geoqa.expect.no_self_intersections(...)`
  - `geoqa.check(path)` fluent helper
- Expanded `expect` into small namespaces so it starts to read more like a language than a bag of wrappers:
  - `geoqa.expect.geometry.valid(...)`
  - `geoqa.expect.topology.clean(...)`
  - `geoqa.expect.attributes.complete(...)`
  - `geoqa.expect.attributes.unique(...)`
- Simplified the top-level package surface in `geoqa/__init__.py` so the obvious entry points are now the user-facing API rather than internal runtime/reporting modules.
- Kept backward compatibility for existing top-level imports used by current tests and examples through a small compatibility bridge for:
  - thermal helpers
  - script base
  - execution entry points
- Removed direct `input()` prompts from the core-library `main()` entrypoints in:
  - `geoqa/interactive_validation.py`
  - `geoqa/agent.py`
- Replaced hardcoded `input` defaults in the agent workflow with explicit input-handler resolution, so interactivity is no longer silently baked into the core module.
- Added:
  - `examples/basic_usage.py`
  - `examples/story_geoai_prep.py`
  - `tests/test_public_api.py`

### Verification

- Ran:
  - `python -m py_compile geoqa\\api.py geoqa\\expect\\__init__.py geoqa\\expect\\core.py geoqa\\__init__.py geoqa\\interactive_validation.py geoqa\\agent.py tests\\test_public_api.py`
  - `python -m unittest tests.test_public_api tests.test_thermal_guard tests.test_layout_wrappers`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
  - `python -c "import geoqa; print(hasattr(geoqa, 'validate'), hasattr(geoqa, 'score'), hasattr(geoqa, 'expect'))"`
  - `python -c "import geoqa; r=geoqa.validate('data/public_samples/edge_cases/duplicate_vertex_line.geojson', profile='geometry'); print(type(r).__name__); print(r.summary()['issue_count']); print(round(r.score(),4)); print(len(r.to_ml()))"`
- Result:
  - targeted tests passed
  - full suite `OK` (`153` tests)
  - catalog validation passed
  - top-level import and object-style API smoke checks passed

### Why this change was made

- The engine, CLI, Streamlit app, runtime, and pack system already existed, but the Python entry points were still too internal-facing.
- The goal of this pass was not to rewrite GeoQA. It was to make `import geoqa` feel obvious for a new user while keeping the internal engine intact.
- This gives the project a simpler public face without flattening the underlying architecture.

## 2026-03-21 09:20:00 +04:00

### Final public-API polish: report object, conservative fix loop, and shallow expectation language

- Tightened `GeoQAReport` so it now behaves more like a data object than a service wrapper:
  - `report.summary` is now a property
  - `report.issues` and `report.suppressed_issues` are explicit properties
  - `report.score(method=...)` still remains a method because it is parameterized
  - added `__repr__` in the form:
    - `<GeoQAReport issues=... score=... profile='...'>`
- Added `GeoQAReport.fix(auto=True)` as a minimal conservative loop-closer:
  - loads the original dataset
  - applies existing safe geometry-fix helpers
  - returns a `GeoQAFixedLayer`
- Added `GeoQAFixedLayer.export(...)` with format inference from path suffix so users can do:
  - `report.fix().export("cleaned.geojson")`
- Kept the scoring modes explicit and lightweight:
  - `conservative`
  - `ml_ready`
- Expanded the expectation layer carefully, without turning it into a giant function dump:
  - `geoqa.expect.geometry.valid(...)`
  - `geoqa.expect.geometry.clean(...)`
  - `geoqa.expect.topology.clean(...)`
  - `geoqa.expect.topology.connected(...)`
  - `geoqa.expect.attributes.complete(...)`
  - `geoqa.expect.attributes.unique(...)`
  - `geoqa.expect.crs.valid(...)`
- Wrapped expectation results in a small list-like `ExpectationResult` so they still behave like issue lists but also support:
  - `.count()`

### Verification

- Kept this pass intentionally light because the workstation had previously reached extreme CPU temperatures.
- Ran:
  - `python -m py_compile geoqa\\api.py geoqa\\expect\\core.py tests\\test_public_api.py`
  - `python -m unittest tests.test_public_api`
  - `python -c "import geoqa; r=geoqa.validate('data/public_samples/edge_cases/duplicate_vertex_line.geojson', profile='geometry'); f=r.fix(); print(r.summary['issue_count']); print(round(r.score(method='ml_ready'),4)); print(type(geoqa.expect.crs.valid('data/public_samples/edge_cases/duplicate_vertex_line.geojson', expected_crs='EPSG:3857')).__name__)"`
- Result:
  - targeted public API tests `OK` (`10` tests)
  - object-style API smoke checks passed

### Why this change was made

- The previous API pass made GeoQA usable.
- This pass makes it feel more natural:
  - one report object
  - one minimal fix loop
  - one shallow expectation language
- It intentionally stops short of overbuilding a second subsystem on top of the engine.

## 2026-03-21 09:45:00 +04:00

### Positioning and story pass: clearer definition, stronger examples, lighter public story

- Tightened the project positioning around one short sentence:
  - GeoQA prepares geospatial datasets for AI by detecting, explaining, and fixing data quality issues.
- Kept the longer deterministic GIS-QA framing immediately after it so the project does not drift into vague GeoAI language.
- Added a true story-driven example:
  - `examples/before_after_cleaning.py`
- Updated the homepage-style workflow so the public signature path now reads:
  - validate
  - inspect the report
  - clean conservatively
  - export the cleaned layer
- Added `report.clean()` as a readable alias for `report.fix()`.
- Kept this intentionally small:
  - no new validators
  - no new packs
  - no runtime work
  - no broader expect-layer explosion

### Verification

- Because workstation temperature had already been a concern, kept verification lightweight and targeted.
- Added one more public API test for the `clean()` alias and relied on the targeted API suite rather than another full high-heat rerun.

### Why this change was made

- The project no longer needed more power.
- It needed a clearer public story:
  - what GeoQA is
  - why it matters
  - what a user should do first
- This pass makes the repo read more like an adoptable product and less like a collection of strong internal systems.

## 2026-03-21 10:05:00 +04:00

### Product-story pass: clearer positioning, before/after proof, and one real workflow

- Added a dedicated public before/after showcase in:
  - `docs/before_after_showcase.md`
- Added a real workflow doc in:
  - `docs/workflows/water_network_ml_prep.md`
- Tightened the top-level positioning in `README.md` so GeoQA reads more clearly as:
  - the data-quality layer before downstream GIS / GeoAI / ML work
- Added a quiet “where GeoQA fits” section instead of loud competitor framing.
- Updated `docs/START_HERE.md` so new readers are pushed toward:
  - one before/after proof
  - one benchmark story
  - one real workflow

### Verification

- Verified the before/after showcase claim directly on the existing public edge-case sample:
  - before clean: `1` issue under the `geometry` profile
  - after conservative `report.clean().export(...)`: `0` issues under the same profile

### Why this change was made

- The project no longer mainly needs more technical breadth.
- It needs faster comprehension:
  - what GeoQA is
  - where it fits
  - why it matters
  - what a credible workflow looks like

## 2026-03-20 11:55:00 +04:00

### Final hardening pass: stronger story, throughput ordering, and precision calibration

- Strengthened the engine around the remaining "last 5%" concerns instead of widening the project.
- Added cost-aware validator ordering in `geoqa/validation_runtime.py` for constrained runs so low-resource execution can attempt cheaper, higher-value checks first.
- Added broader cost hints to built-in validators across:
  - geometry
  - attributes
  - CRS
  - metadata
  - accuracy
  - topology
  - integrity
- Extended `geoqa/validations/accuracy.py` with CRS-aware and scale-aware defaults for:
  - coordinate precision
  - XY tolerance
- Also improved `positional_accuracy(...)` so it now attempts to use a reference-layer spatial index before falling back to full scans.
- Strengthened the water-network pack summary in `geoqa/packs/water_network/rules.py`:
  - junction count
  - terminal endpoint count
  - multipart segment count
  - explicit threshold echo
  - clearer schema explanation
- Simplified `geoqa.execution._pack_summary(...)` so pack-summary logic now lives in the water-network pack instead of being hand-built in the execution layer.
- Added regression coverage in:
  - `tests/test_accuracy_validation.py`
  - `tests/test_water_network_pack.py`
  - `tests/test_validation_runtime.py`

### Verification

- Ran:
  - `python -m py_compile geoqa\\validation_runtime.py geoqa\\validations\\accuracy.py geoqa\\packs\\water_network\\rules.py geoqa\\packs\\water_network\\__init__.py geoqa\\execution.py tests\\test_accuracy_validation.py tests\\test_water_network_pack.py tests\\test_validation_runtime.py`
  - `python -m unittest tests.test_accuracy_validation tests.test_water_network_pack tests.test_validation_runtime`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - targeted tests passed
  - full suite `OK` (`144` tests)
  - catalog validation passed

### Why this change was made

- The remaining critique was fair: GeoQA had strong substance, but the strongest public success case was still too buried, throughput still needed engineering, and precision noise still needed more context-aware handling.
- This pass keeps the project moving inward:
  - stronger engine behavior
  - clearer water-network pack value
  - stronger public proof
  - no sideways UI expansion

### Planning and governance doc consolidation

- Reworked the main planning/governance files so they align with the current shipped engine instead of layering more roadmap history on top of old text.
- Rewrote:
  - `plan_of_action.md`
  - `docs/checklist.md`
  - `docs/security.md`
  - `ARCHITECTURE.md`
  - `docs/api_policy.md`
  - `CONTRIBUTING.md`
- Main goals of the rewrite:
  - remove stale contradictions
  - distinguish shipped vs partial vs missing work more clearly
  - make low-resource / constrained-hardware operation a visible current reality
  - keep the project centered on the deterministic QA engine rather than the app shell

### Why this change was made

- The project docs had become accurate in pieces but uneven as a whole.
- Some files were reflecting current engine behavior, while others were still carrying older stacked roadmap notes.
- It was better to replace those with cleaner current-state documents than keep patching increasingly inconsistent planning text.

### Heavier public low-resource benchmark verification

- Ran a fresh low-resource CLI benchmark against the heavier public Natural Earth roads sample:
  - `python -m geoqa benchmark data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag roads_low_resource_2026_03_20 --progress`
- Result:
  - completed successfully
  - duration: about `121.9` seconds
  - features: `56,600`
  - issues: `49`
  - execution status: `full`
- Dominant findings:
  - `duplicate_vertex`: `42`
  - `self_intersection`: `6`
  - `missing_or_stale_spatial_index`: `1`
- Why this matters:
  - the project now has a real heavier public success case for low-resource mode, not only partial heavy-run evidence
  - this does not make the full heavy-run problem solved, but it does prove the constrained operator path can be useful on a non-trivial public dataset

### Low-resource hardening and honest partial-run pass

- Added a first-class low-resource execution mode to the CLI for:
  - `validate`
  - `benchmark`
- The low-resource path now applies conservative defaults automatically:
  - lower worker count
  - smaller starting chunk size
  - cooler thermal posture
  - bounded runtime defaults
  - more operator-facing progress output
- Extended runtime execution to support early-stop constraints without lying about completion:
  - `max_runtime_seconds`
  - `max_issues`
  - `stop_after_actionable`
- Added `ValidationPlanResult` so the runtime can return:
  - issues
  - validators attempted
  - validators completed
  - validators deferred
  - partial-result state
  - stop reason
- Updated the higher execution layer so reports now distinguish:
  - full
  - partial
  - budget-limited
  - thermal-limited
  - input-limited
- Added operator next-step hints to execution summaries rather than leaving the user with raw counts only.
- Added pack-specific water-network operator rollups to the execution summary so the strongest domain pack is easier to understand in practice.
- Expanded the profile story to make quick/strict/audit behavior more explicit for:
  - generic
  - boundaries
  - land use
- Switched `geoqa profiles list` and `geoqa profiles show` to human-readable defaults, with `--json` retained for scripting.
- Added `docs/solo_operator_guide.md` so constrained-hardware operation now has a dedicated maintainer/operator guide instead of being scattered across docs.

### Verification

- Ran:
  - `python -m py_compile geoqa\\validation_runtime.py geoqa\\interactive_validation.py geoqa\\execution.py geoqa\\reports\\report_generator.py geoqa\\cli\\commands\\_common.py geoqa\\cli\\commands\\validate.py geoqa\\cli\\commands\\benchmark.py geoqa\\cli\\commands\\profiles.py geoqa\\profile_registry.py geoqa\\packs\\__init__.py geoqa\\packs\\boundaries\\profile.py geoqa\\packs\\land_use\\profile.py geoqa\\validations\\topology.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
  - `python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag final_low_resource_demo --progress --report-path data/integration_results/final_low_resource_demo`
- Result:
  - full suite `OK` (`140` tests)
  - catalog validation passed
  - low-resource CLI smoke run succeeded and wrote a structured report with explicit execution metadata

### Why this change was made

- The remaining problem was no longer a lack of features; it was operator trust on a weak workstation.
- GeoQA needed to make constrained execution a first-class supported path instead of an implied collection of knobs.
- Partial work also needed to become genuinely useful and explicit rather than only being visible deep in runtime internals.

### Private external water-network folder verification and multipart-line fix

- Tested the current CLI/runtime path against three private external shapefile layers from a user-supplied folder outside the repository:
  - one medium point asset layer
  - one very large point asset layer
  - one very large line-network layer
- Kept the ledger anonymized by recording only scale, geometry type, and findings rather than dataset names or source organization details.
- Findings from the two point layers:
  - both completed successfully through `python -m geoqa validate ...`
  - the medium point layer reported:
    - `invalid_spatial_reference`
    - `missing_or_stale_spatial_index`
  - the very large point layer reported:
    - `2` `null_geometry`
    - `invalid_spatial_reference`
    - `missing_or_stale_spatial_index`
  - the larger point-layer run also exposed suspicious date-like attribute values through reader warnings, but GeoQA still completed and produced a report
- The first bounded run on the very large line-network layer exposed a real engine bug:
  - `line_dangle` and shared endpoint extraction assumed direct `.coords` access
  - multipart line geometries raised `NotImplementedError`
- Fixed `geoqa/validations/topology.py` by adding a shared linear-endpoint extractor that handles both single-part and multi-part line geometries safely.
- Added regression coverage in `tests/test_additional_validations.py` for `MultiLineString` dangle handling.
- Verification after the fix:
  - `python -m unittest tests.test_additional_validations`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Verification result:
  - targeted topology regression suite `OK`
  - full suite `OK` (`136` tests)
- Re-ran the very large line-network layer after the fix:
  - it no longer failed at the previous multipart-line topology step
  - it still did not complete within a bounded 30-minute CLI run on this workstation
- Reason:
  - this pass was meant to answer a real operational question with real external data, not fixtures
  - it also improved the engine by fixing a topology crash that only surfaced on multipart linework in a large operational network layer

## 2026-03-20 04:55:00 +04:00

### Task Group 3 benchmark story and verification pass

- Added `docs/benchmark_story.md` as a public, credibility-focused benchmark narrative using only recorded public benchmark runs already present in the repository.
- Added a CLI smoke test for `python -m geoqa benchmark ...` so the benchmark interface is exercised automatically rather than only documented.
- Linked the benchmark story from:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `plan_of_action.md`
- Re-ran verification for this task group:
  - `python -m py_compile tests\\test_cli.py`
  - `python -m unittest tests.test_cli`
  - `python scripts\\validate_problem_catalog.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Verification result:
  - full suite `OK` (`131` tests)
  - catalog validation passed
- Reason:
  - The benchmark story needed to be backed by real smoke coverage and a fresh repo-wide baseline so it reads as evidence, not marketing copy.

## 2026-03-20 05:20:00 +04:00

### Task Group 4 reporting and CLI completion pass

- Tightened the human-readable report formatter to show actionable ratio as a percentage and include root-cause groups when provenance is available.
- Fixed `summarize_report(...)` so JSON-backed report reloads preserve stored provenance and suppression metadata instead of dropping them during summary reconstruction.
- Added CLI coverage for:
  - `python -m geoqa validate ... --fail-on-error`
  - `python -m geoqa report stats ...`
- Re-ran verification for this pass:
  - `python -m py_compile geoqa\\reports\\report_generator.py tests\\test_report_generator.py tests\\test_cli.py`
  - `python -m unittest tests.test_report_generator tests.test_cli`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Verification result:
  - full suite `OK` (`134` tests)
- Reason:
  - Reporting needed to be decision-ready at the CLI surface, and that required both clearer operator summaries and proof that report reloads preserve the metadata needed for grouping and triage.

## 2026-03-20 05:45:00 +04:00

### Task Group 5 CLI completeness verification pass

- Added a broader CLI runtime test that exercises `python -m geoqa validate ...` with the production-style runtime flags together:
  - `--max-workers`
  - `--chunk-size`
  - `--sleep`
  - `--thermal-profile`
  - `--max-features`
  - `--max-size-mb`
  - `--cache`
  - `--cache-tag`
  - `--max-runtime-seconds`
  - `--progress`
- Verified cache reuse through the CLI by rerunning the same command and asserting `cache-hit` appears in the progress output.
- Re-ran verification for this pass:
  - `python -m py_compile tests\\test_cli.py`
  - `python -m unittest tests.test_cli`
  - `python scripts\\validate_problem_catalog.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Verification result:
  - full suite `OK` (`135` tests)
  - catalog validation passed
- Reason:
  - The CLI surface needed proof that the runtime contract is not only documented, but actually exercised end to end with the production flags combined in one path.

## 2026-03-20 10:20:00 +04:00

### Heavy public adaptive-rerun verification

- Re-ran the heaviest public samples through the chunked agent path using the newer adaptive runtime settings instead of the original baseline paths.
- Tested:
  - Natural Earth roads with weighted chunking and a cool thermal profile
  - Philadelphia zoning with weighted chunking and a cool thermal profile
- Both runs exceeded the one-hour execution budget for this pass and were terminated externally.
- Neither run showed a thermal-limit trip in the recorded tail of the thermal logs.
- This is a meaningful shift in the runtime story:
  - the dominant failure mode is no longer immediate heat-triggered abort
  - the dominant remaining issue is throughput / total validator cost on the current workstation
- Recorded artifacts:
  - `data/integration_results/natural_earth_roads_adaptive_thermal_2026_03_20.jsonl`
  - `data/integration_results/philly_zoning_adaptive_thermal_2026_03_20.jsonl`
- Reason:
  - The recent adaptive runtime work needed a real public-dataset check, not just unit coverage. The result is honest: thermal behavior improved, but large-run completion is still not solved.

## 2026-03-18 14:26:51 +04:00

### Project initialization

- Created the GeoQA project root and initial scaffold:
  - `geoqa/`
  - `data/`
  - `tests/`
  - `docs/`
  - `examples/`
  - `README.md`
  - `raw_problems_with_sources.json`
- Reason:
  - Establish a clean library layout before adding code or datasets.
  - Keep package code, examples, documentation, tests, and data separate from the start.

### Geospatial problem catalog

- Collected and saved a curated geospatial data quality problem catalog in `raw_problems_with_sources.json`.
- Added 58 unique, source-backed problems.
- Sources used across the catalog included:
  - ArcGIS Pro documentation
  - ArcGIS Desktop / geodatabase topology documentation
  - QGIS documentation
  - FME documentation
  - ArcGIS support and metadata references
  - USGS FGDC metadata references
- Reason:
  - The library needs a grounded, non-invented reference list of common QA and validation issues.
  - Using authoritative sources reduces noise and makes later validator design more defensible.

### Python package bootstrap

- Added `geoqa/__init__.py`.
- Reason:
  - Mark `geoqa` as an importable Python package.
  - Provide a stable package entry point for exported APIs.

### Initial thermal monitoring capability

- Added `geoqa/thermal.py`.
- Initial design included:
  - Core Temp shared-memory reads on Windows
  - `psutil.sensors_temperatures()` fallback
  - `ThermalGuard`
  - `TemperatureSnapshot`
  - `ThermalLimitExceeded`
- Reason:
  - Your workstation heat constraint is a real operational issue.
  - GeoQA needed a built-in way to protect local runs from sustained high CPU temperature.

### Thermal-safe runner layer

- Added `geoqa/runner.py`.
- Added:
  - `ThermalRunner`
  - `StepResult`
- Reason:
  - Thermal safety should not rely on handwritten guard calls scattered across scripts.
  - A reusable runner keeps pre-check and post-check logic consistent for CPU-intensive loops.

### Script base for GeoQA workflows

- Added `geoqa/script_base.py`.
- Added:
  - `GeoQAScriptBase`
- Reason:
  - New GeoQA scripts should only need to define `load_items()` and `process_item()`.
  - This reduces repetition and standardizes startup behavior, per-step handling, and thermal governance.

### Demo and tests

- Added example script:
  - `examples/thermal_guard_demo.py`

## 2026-03-19

### CLI-first product surface

- Added a first-class CLI package under:
  - `geoqa/cli/`
  - `geoqa/__main__.py`
- Implemented commands for:
  - `validate`
  - `profiles`
  - `convert`
  - `report`
  - `benchmark`
- Reason:
  - GeoQA needed an operational surface that reflects the core engine more clearly than the app.
  - This reduces friction for repeatable use, CI, and contributor testing.

### Problem and profile registries

- Added:
  - `geoqa/problem_registry.py`
  - `geoqa/profile_registry.py`
  - `geoqa/execution.py`
- Reason:
  - `raw_problems_with_sources.json` should remain the canonical ontology/source-backed problem catalog.
  - Runtime behavior, profile execution, suppression, and severity tuning needed their own operational layer.

### Richer report model

- Extended report generation and summaries in:
  - `geoqa/reports/report_generator.py`
- Added:
  - `load_report(...)`
  - `summarize_issues(...)`
  - `summarize_report(...)`
- CSV output now preserves richer issue metadata instead of assuming the original minimal field set.
- Reason:
  - the CLI and execution layer needed report summaries and a more durable issue schema.

## 2026-03-20

### Task Group 2 signal calibration and reporting clarity

- Extended `geoqa.profile_registry.GeoQAProfile` with:
  - `downgrade_rules`
  - `suppression_rules`
- Updated `geoqa.execution._apply_profile_policies(...)` so those fields become real runtime behavior instead of only documentation concepts.
- Extended report summaries in `geoqa/reports/report_generator.py` with:
  - `severity_distribution`
  - `problem_breakdown`
- Added `format_summary_text(...)` so report summaries can be emitted as readable CLI output instead of raw JSON only.
- Updated `geoqa/cli/commands/report.py` so:
  - `geoqa report summarize ...` prints a human-readable operational summary by default
  - `--json` remains available when machine-readable output is preferred
  - `geoqa report stats ...` also supports human-readable output plus row count
- Updated `geoqa/cli/commands/profiles.py` so profile inspection now shows:
  - downgrade rules
  - suppression rules

### Why this change was made

- The runtime already had the core issue fields, but the calibration model was still too implicit and the CLI reporting surface was still too raw.
- Explicit downgrade/suppression fields make profile intent easier to author, inspect, and test.
- Human-readable summaries are necessary if the CLI is meant to be a real operator surface rather than just a JSON transport.

### Verification

- Ran:
  - `python -m py_compile geoqa\\profile_registry.py geoqa\\execution.py geoqa\\reports\\report_generator.py geoqa\\cli\\commands\\report.py geoqa\\cli\\commands\\profiles.py tests\\test_execution.py tests\\test_report_generator.py tests\\test_cli.py`
  - `python -m unittest tests.test_execution tests.test_report_generator tests.test_cli`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - targeted tests passed
  - full suite passed: `OK` (`130` tests)
  - catalog validation passed

### Task Group 1 domain-pack implementation completed

- Replaced the earlier flat pack modules with structured package directories:
  - `geoqa/packs/water_network/`
  - `geoqa/packs/boundaries/`
  - `geoqa/packs/land_use/`
- Added a fuller water-network pack implementation including:
  - `profile.py`
  - `rules.py`
  - `thresholds.py`
  - `schema.py`
  - `README.md`
- Added water-network profiles:
  - `water_network_quick`
  - `water_network`
  - `water_network_strict`
  - `water_network_audit`
- Added geometry validators for:
  - `below_minimum_feature_length`
  - `sharp_angle_cutback`
- Added topology/connectivity validators for:
  - `feature_not_split_at_intersection`
  - `isolated_network_segment`
  - `suspicious_near_miss_endpoints`
  - `unsnapped_endpoints_within_tolerance`
- Added structured water-network schema detection that returns field and domain hints instead of booleans.
- Centralized water-network thresholds for:
  - snap tolerance
  - near-miss tolerance
  - minimum length
  - angle thresholds
  - allowed terminal values
- Extended runtime context handling so pack/profile context can flow through the execution layer without moving logic into CLI or UI surfaces.
- Added regression coverage in:
  - `tests/test_water_network_pack.py`
- Updated:
  - `tests/test_cli.py`
  - `tests/test_validation_runtime.py`

### Why this change was made

- The earlier domain-pack slice was directionally correct but too thin and too flat to count as a serious first industry-facing pack implementation.
- Water-network behavior needed to become real profile-driven behavior with centralized thresholds, schema hints, and connectivity-aware detection rather than a static validator bundle.
- The pack refactor also sets the shape for later packs without duplicating validator logic or leaking pack behavior into the CLI/app layers.

### Verification

- Ran:
  - `python -m py_compile geoqa\\packs\\water_network\\__init__.py geoqa\\packs\\water_network\\schema.py geoqa\\packs\\water_network\\thresholds.py geoqa\\packs\\water_network\\rules.py geoqa\\packs\\water_network\\profile.py geoqa\\packs\\boundaries\\__init__.py geoqa\\packs\\boundaries\\thresholds.py geoqa\\packs\\boundaries\\rules.py geoqa\\packs\\boundaries\\profile.py geoqa\\packs\\land_use\\__init__.py geoqa\\packs\\land_use\\thresholds.py geoqa\\packs\\land_use\\rules.py geoqa\\packs\\land_use\\profile.py geoqa\\validations\\geometry.py geoqa\\validations\\topology.py geoqa\\validation_runtime.py geoqa\\interactive_validation.py geoqa\\profile_registry.py tests\\test_water_network_pack.py tests\\test_cli.py tests\\test_validation_runtime.py`
  - `python -m unittest tests.test_water_network_pack tests.test_cli tests.test_execution`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - targeted tests passed
  - full suite passed: `OK` (`126` tests)
  - catalog validation passed

### Rule-versioned reporting and precision-policy hardening

- Added `VALIDATION_RULE_VERSION = "2026.03"` in `geoqa/problem_registry.py`.
- Updated `ValidationIssue.to_dict()` and report generation so outputs now carry:
  - `validation_rule_version`
  - `confidence`
  - `actionable`
- Updated JSON report generation to write a structured payload:
  - top-level `validation_rule_version`
  - top-level `issue_count`
  - top-level `issues`
- Kept report loading backward-compatible with older JSON list payloads.
- Tightened noisy precision behavior in built-in profiles:
  - `generic_strict` now passes explicit options to `coordinate_precision` and `xy_tolerance`
  - `boundaries` now suppresses generic precision/tolerance findings by default
- Fixed the runtime wrappers so profile-level validator options are actually honored by:
  - `coordinate_precision`
  - `xy_tolerance`
  - `positional_accuracy`
- Removed direct thermal-runner coupling from `geoqa/validations/geometry.py`.
- Added a test-safe CLI thermal bypass using:
  - `GEOQA_DISABLE_THERMAL_GUARD=1`
- Updated CLI tests to match the current structured JSON report shape.

### Why this change was made

- The earlier criticism was correct: some roadmap items were still recorded as “next steps” without the corresponding implementation details being fully wired through the actual runtime.
- Validation rule versioning needed to be a real part of the output contract, not just a planning note, so auditability and reproducibility can improve from here.
- The precision-related policy work also needed to move from “profile intent” into actual runtime behavior, otherwise the project would still generate noisy results despite the new profile layer.
- The execution-test hang exposed a design problem: validators should not carry their own thermal wait logic. Thermal controls belong in runtime/orchestration, not inside the validator loop itself.

### Verification

- Ran:
  - `python -m py_compile geoqa\\execution.py geoqa\\validations\\geometry.py geoqa\\validation_runtime.py geoqa\\reports\\report_generator.py tests\\test_cli.py tests\\test_execution.py tests\\test_report_generator.py`
  - `python -m unittest tests.test_execution tests.test_report_generator`
  - `python -m unittest tests.test_cli`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - full suite passed: `OK` (`111` tests)

### Full verification and private-ledger cleanup

- Re-ran the full automated suite again:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Re-ran:
  - `python scripts\\validate_problem_catalog.py`
  - `python -m geoqa profiles list`
  - `python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry --output-format json --report-path data/integration_results/manual_cli_verify_2026_03_20`
  - `python -m geoqa report summarize .\\data\\integration_results\\manual_cli_verify_2026_03_20.json`
  - `python -m geoqa report stats .\\data\\integration_results\\manual_cli_verify_2026_03_20.json`
  - `python -m geoqa benchmark data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry`
  - `python -m geoqa convert data/public_samples/edge_cases/duplicate_vertex_line.geojson data/integration_results/manual_cli_convert_2026_03_20.csv --format csv`
- Result:
  - automated suite: `OK` (`111` tests)
  - catalog validation: passed
  - CLI smoke path: passed for `profiles`, `validate`, `report summarize`, `report stats`, `benchmark`, and `convert`
- Updated project-facing docs so private local datasets are now described only by:
  - role
  - geometry type
  - scale
  - observed findings
- Removed dataset names and source paths from:
  - `docs/local_data_tests.md`
  - `docs/tests.md`
  - `data/integration_results/README.md`
  - selected roadmap/history references in `docs/checklist.md`, `plan_of_action.md`, `docs/CHANGELOG.md`, and this journal

### Why this change was made

- The user asked for a true end-to-end verification pass rather than only unit-level confirmation.
- The user also asked that local test materials be clearly treated as private testing inputs, with project-facing notes focusing on findings and operational behavior instead of dataset names.

### Signal calibration and adaptive chunking

- Extended `geoqa.validations.base.ValidationIssue` with:
  - `confidence`
  - `actionable`
- Extended `geoqa.problem_registry.ProblemDefinition` with:
  - `default_confidence`
  - `default_actionable`
- Updated the runtime/cache layer so those fields survive serialization and cache reuse.
- Added per-problem policy support to `geoqa.profile_registry.GeoQAProfile` and applied it in `geoqa.execution`.
- Strengthened the built-in profiles:
  - `generic_strict`
  - `water_network`
  - `boundaries`
- Added geometry-weighted adaptive chunking to `geoqa.agent`, allowing validation slices to be formed by target vertex budget instead of row count only.
- Updated the agent recommendation path so suggested chunk settings can include a target-vertices-per-chunk value.
- Reason:
  - The next credible step toward industry-grade GeoQA is not more UI; it is better triage quality and more reliable large-run behavior.
  - Confidence/actionable fields are needed to distinguish noisy informational findings from findings that should block workflows.
  - Fixed row-count chunking is not enough for heavy polygon or dense linework datasets, so geometry-weighted chunking needed to become a first-class execution option.

### Phased roadmap correction

- Collapsed the forward plan into four clearer phases:
  - Immediate Stability and Scale
  - Enterprise and Standards
  - GeoAI Maturity
  - Ecosystem and Integration
- Re-emphasized that thermal/scale completion is the top priority before deeper GeoAI-facing work.
- Marked ArcGIS integration as a later contributor-facing item because it cannot be verified meaningfully in the current local environment.
- Reason:
  - the roadmap had become too wide for near-term execution.
  - the strongest corrective move is to make thermal stability, reproducibility, and signal quality the gating priorities.

### Public API and contributor docs

- Rewrote:
  - `README.md`
  - `docs/START_HERE.md`
  - `docs/user_guide.md`
- Added:
  - `docs/api_policy.md`
  - `CONTRIBUTING.md`
  - `ARCHITECTURE.md`
- Reason:
  - the project had too much surface ambiguity.
  - The docs now center GeoQA as a deterministic geospatial QA engine with a CLI-first entry path.

### Verification

- Ran:
  - `python -m py_compile` on the new CLI, execution, registry, and report modules
  - `python -m unittest tests.test_report_generator tests.test_execution tests.test_cli`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python -m geoqa profiles list`
  - `python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry --output-format json --report-path data/integration_results/cli_geometry_demo_2026_03_19`
- Result:
  - full suite passed: `OK` (`107` tests)
- Added unit tests:
  - `tests/test_thermal_guard.py`
- Reason:
  - The demo provides a concrete pattern for how the runner and script base are meant to be used.
  - The tests protect the main thermal control behavior while the API evolves.

### Cross-platform import safety fix

## 2026-03-20

### Issue prioritization and adaptive chunk resizing

- Extended `geoqa.validations.base.ValidationIssue` with:
  - `priority_score`
- Added default priority computation from:
  - severity
  - confidence
  - actionable state
  - issue class
- Updated report generation in:
  - `geoqa/reports/report_generator.py`
- Summaries now include:
  - `by_priority_band`
  - `top_actionable`
- Updated profile-policy application in:
  - `geoqa.execution`
- Profiles can now override:
  - `priority_score`
- Updated cache restore in:
  - `geoqa.validation_runtime`
- Cached issues now preserve:
  - `priority_score`
- Upgraded chunk orchestration in:
  - `geoqa.agent`
- Chunked validation can now:
  - reduce chunk size under thermal pressure
  - reduce chunk size after slow chunk runtimes
  - cautiously increase chunk size again when the machine is cool and chunks are fast
- Added tests in:
  - `tests/test_execution.py`
  - `tests/test_report_generator.py`
  - `tests/test_agent.py`

### Why this change was made

- The previous runtime and profile slices were useful, but they still left two practical gaps:
  - issue triage quality
  - large-run behavior under thermal pressure
- `severity`, `confidence`, and `actionable` were already present, but the engine still needed a simple deterministic way to rank findings for operators and reports.
- Geometry-weighted chunking was a real step forward, but fixed chunk sizes were still too rigid once the machine heated up or chunk runtimes became uneven.
- This pass moves both concerns further down into the engine/runtime layer where they belong, instead of solving them in CLI or UI code.

### Verification

- Ran:
  - `python -m py_compile geoqa\\validations\\base.py geoqa\\reports\\report_generator.py geoqa\\execution.py geoqa\\validation_runtime.py geoqa\\agent.py tests\\test_execution.py tests\\test_report_generator.py tests\\test_agent.py`
  - `python -m unittest tests.test_execution tests.test_report_generator tests.test_agent`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - targeted suite passed
  - full suite passed: `OK` (`119` tests)
  - catalog validation passed

- Refactored `geoqa/thermal.py` so Windows-only API setup happens only when `sys.platform == "win32"`.
- Kept platform behavior as:
  - Windows + Core Temp: prefer Core Temp
  - Windows without Core Temp: fallback to `psutil`
  - macOS/Linux: `psutil` only
- Reason:
  - The original structure would fail on non-Windows imports because `ctypes.WinDLL("kernel32", ...)` was evaluated at import time.
  - This change made the module safely importable on Windows, macOS, and Linux.

### Temperature diagnostics

- Added `TemperatureDiagnostic` and `run_temperature_diagnostic()` to `geoqa/thermal.py`.
- Added platform-specific explanation messages and suggested options when readings are unavailable.
- Exported the diagnostic through `geoqa/__init__.py`.
- Reason:
  - A user should know immediately whether live temperature reads are available.
  - Missing-sensor cases need explanation, not silent failure.
  - Different operating systems fail for different reasons, so alternatives need to be explicit.

### Optional startup diagnostic emission

- Extended `GeoQAScriptBase` to emit a startup thermal diagnostic by default.
- Added:
  - `emit_thermal_diagnostic=True`
  - `diagnostic_emitter=...`
  - default diagnostic printing behavior
- Reason:
  - It is useful for every run to report which backend is active: `coretemp`, `psutil`, or `unavailable`.
  - The emitter hook avoids hardwiring everything to stdout and allows logging/file routing.

### Script annotation utility

- Added `scripts/annotate_geoqa_scripts.py`.
- Behavior:
  - recursively scans `.py` files
  - uses the standard-library `ast` module
  - detects classes that subclass `GeoQAScriptBase`
  - prepends a GeoQA comment block only once
  - skips non-matching files
- Reason:
  - This improves onboarding and makes GeoQA script intent obvious to future readers.
  - AST detection is safer than plain text matching.

### README expansion

- Expanded `README.md` substantially.
- Added documentation for:
  - `ThermalGuard`
  - `ThermalRunner`
  - `GeoQAScriptBase`
  - startup diagnostics
  - custom diagnostic emitters
  - cross-platform behavior
  - annotator script usage
- Reason:
  - The library grew beyond a simple scaffold and needed user-facing guidance.
  - Startup diagnostics and platform behavior are not obvious without written documentation.

### Project governance files

- Added `AGENTS.md`.
- Added `SKILLS.md`.
- Added `codex_prompt.md`.
- Then aligned them so `codex_prompt.md` is treated as the canonical prompt file for GeoQA Codex tasks.
- Reason:
  - The project now has a defined assistant workflow and coding policy.
  - `AGENTS.md` acts as the rulebook.
  - `SKILLS.md` acts as the practical reference for classes, functions, and patterns.
  - `codex_prompt.md` acts as the reusable canonical prompt for task framing.

### AGENTS.md improvements

- Added:
  - version/date section
  - reference example
  - future-rules placeholder
- Reason:
  - Makes the policy file easier to maintain over time.
  - Leaves a clean place for future task-specific rule additions.

### SKILLS.md improvements

- Added:
  - version/date
  - canonical prompt section
  - thermal-safe patterns and examples
  - platform notes
  - optional AGENTS follow-up note
- Reason:
  - GeoQA now has enough internal structure that a lightweight skill/reference document is useful.

### Validation and verification work

- Repeatedly ran the test suite:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Also performed targeted verification steps such as:
  - checking project layout
  - parsing the JSON catalog
  - verifying unique problem names
  - confirming the thermal diagnostic backend on this machine
  - testing the annotator on a temporary directory tree
- Reason:
  - The project was built iteratively and several files were added in sequence.
  - Frequent verification reduced the risk of drift between implementation and documentation.

### Current project direction

- GeoQA now has:
  - a curated QA problem catalog
  - a thermal-safe execution layer
  - cross-platform temperature support
  - startup diagnostics
  - a reusable script base
  - tests, examples, onboarding docs, and assistant policy files
- Why this matters:
  - The project is no longer just a folder scaffold; it has a reusable execution model and documented operating conventions.

### Notes for future journal entries

- Continue recording:
  - new validators or geospatial QA modules
  - schema changes
  - test additions
  - major API changes
  - documentation updates
  - rationale for architecture decisions

## 2026-03-18 14:31:01 +04:00

### Version 0.2.0

- Added a new sibling `geoai/` package for optional AI-oriented extensions inside the GeoQA repository.

### JSON and TOON serialization support

- Added `geoai/serialization.py`.
- Added:
  - `serialize(obj, format="json")`
  - `deserialize(data, format="json")`
  - TOON backend detection through optional imports
  - graceful fallback to compact JSON when TOON support is unavailable
- Reason:
  - JSON remains the universal format.
  - TOON support was requested as an optional prompt-oriented serialization path.
  - Optional dependency handling keeps the package portable and avoids breaking environments that do not install a TOON backend.

### Optional JAX acceleration layer

- Added `geoai/jax_layer/__init__.py`.
- Added:
  - optional JAX backend configuration
  - NumPy fallback when JAX is missing
  - accelerated helper functions such as pairwise squared distances and stable softmax
- Reason:
  - GeoAI workflows may benefit from numerical acceleration, but JAX should remain optional.
  - The library needs to continue working on systems without JAX installed.

### Optional PyQGIS integration helpers

- Added `geoai/qgis_layer/__init__.py`.
- Added helpers to:
  - detect PyQGIS availability
  - convert geometry-like objects to GeoJSON
  - convert feature-like objects to feature dict records
  - convert layer-like objects to collections of feature dicts
- Reason:
  - GeoAI workflows often need QGIS interoperability, but PyQGIS availability is highly environment-dependent.
  - Duck-typed helper design allows limited utility even without a full QGIS runtime.

### Tests added

- Added:
  - `tests/test_geoai_serialization.py`
  - `tests/test_geoai_optional_layers.py`
- Coverage includes:
  - JSON round-trip
  - TOON round-trip with a mocked backend
  - TOON fallback behavior when no backend exists
  - JAX available vs missing behavior
  - PyQGIS absence handling
  - feature/layer conversion using feature-like test doubles
- Reason:
  - These modules depend on optional backends, so explicit fallback testing is necessary.

### Documentation updates

- Updated `README.md` with:
  - JSON/TOON serialization notes
  - optional JAX acceleration guidance
  - optional PyQGIS helper notes and environment expectations
- Reason:
  - These features are optional and environment-sensitive; they need documentation to avoid confusion.

## 2026-03-18 14:31:01 +04:00

### Version 0.2.0a

- Expanded `raw_problems_with_sources.json` from 58 entries to 73 entries.
- Added new categories and themes, including:
  - `integrity`
  - `accuracy`
  - additional `topology`, `spatial_logic`, `attributes`, and `geometry` checks

### Catalog expansion details

- Added new integrity-oriented checks such as:
  - missing or stale spatial index
  - outdated indexes
  - database geometry without required spatial index
  - non-RFC7946 GeoJSON output
- Added new accuracy-oriented checks such as:
  - coordinate precision not fit for use
  - precision loss from coarse XY resolution
  - inappropriate XY tolerance
  - positional accuracy exceeding reference tolerance
- Added new topology and spatial logic checks such as:
  - non-edge-matched polygon coverage
  - narrow invalid coverage gaps
  - unsnapped vertices within tolerance
  - features not split at intersections
- Added additional attribute and geometry checks such as:
  - attribute value missing from reference tables
  - sharp angle cutbacks
  - below-minimum feature length

### Why the catalog was expanded

- The original catalog covered a strong core of geometry, topology, CRS, attribute, and metadata issues, but it was still missing several high-value QA themes needed for more practical validation workflows.
- The expanded entries improved coverage for:
  - database and file integrity concerns
  - positional and coordinate accuracy issues
  - coverage-style topology problems
  - more actionable dataset validation scenarios
- This matters for the future GeoQA agent because validation routing and report generation become more useful when the catalog reflects a broader range of real GIS QA cases.

### Validation work for the catalog expansion

- Programmatically merged the new entries into the catalog.
- Verified that all `problem_name` values remained unique after expansion.
- Confirmed the resulting JSON remained valid and parseable.


## 2026-03-18 14:31:01 +04:00

### Version 0.2.1

- Expanded `raw_problems_with_sources.json` so every problem now carries:
  - `severity`
  - `repair_hint`
- Added `scripts/validate_problem_catalog.py`.
- Added `tests/test_problem_catalog.py`.
- Updated `README.md` with catalog validation guidance and the new schema fields.

### Why this change was made

- `severity` makes the catalog more useful for prioritization and future GeoAI triage workflows.
- `repair_hint` makes the catalog more actionable for automated assistants, PyQGIS tooling, and validation dashboards.
- Programmatic validation protects the catalog against duplicate names, missing fields, and category drift.

## 2026-03-18 14:59:06 +04:00

### Plan of Action Update

- Added `plan_of_action.md`.
- Removed the older `plan_of_action.txt` after confirming the Markdown version had absorbed and improved the content.

### Why the roadmap changed from TXT to MD

- The original text plan was useful as an early outline, but it had become too large and detailed for plain-text maintenance.
- Markdown is a better format for:
  - sectioning
  - headings
  - future edits
  - roadmap readability
  - long-term project planning
- Keeping both `.txt` and `.md` versions would create unnecessary duplication and drift risk, so the plain-text file was removed once the Markdown version was in place.

### What changed in the new plan

- The new Markdown roadmap is not just a copy of the old text file.
- The agent workflow section was improved to reflect a better design choice:
  - user-guided dataset type selection is now the preferred primary workflow
  - automatic dataset-type deduction was moved to a future optional enhancement instead of being the main path
- The updated plan now emphasizes:
  - modular validation routing by dataset type
  - generic fallback validation
  - explicit user choice between reporting and auto-fix workflows
  - milestone-style structure that is easier to track over time

### Why this matters

- This change reduces ambiguity in the future agent design.
- It also matches the practical direction of the project better:
  - simpler user workflow
  - lower maintenance burden
  - fewer misclassification risks
  - cleaner roadmap for future implementation work

## 2026-03-18 15:00:00 +04:00

### Validation Engine Foundation

- Added `geoqa/validations/base.py` with `ValidationIssue`.
- Added `geoqa/validations/geometry.py` with:
  - `null_geometry`
  - `self_intersection`
  - `duplicate_vertex`
- Added `geoqa/reports/report_generator.py`.
- Added `geoqa/interactive_validation.py`.
- Added tests:
  - `tests/test_geometry_validation.py`
  - `tests/test_report_generator.py`
- Updated `README.md` with validation engine usage notes.

### Why this change was made

- The project framework was in place, but the actual validation engine had not yet started.
- `ValidationIssue` establishes a standard result object that can be reused across geometry, topology, CRS, attributes, metadata, and future agent workflows.
- Starting with geometry validation gives immediate practical value while keeping the first implementation bounded and testable.
- The interactive validation entry point provides a working path from dataset input to issue detection to report generation.
- The validation engine was connected to the existing thermal-safe framework so new workflows remain aligned with GeoQA operating rules.

## 2026-03-18 15:00:00 +04:00

### Documentation and Policy Sync for Validation Engine

- Updated `AGENTS.md` with validation-engine-specific rules.
- Updated `SKILLS.md` to document:
  - `ValidationIssue`
  - report generation usage
  - geometry validation usage
  - interactive validation usage
  - lazy optional GIS dependency guidance

### Why this change was made

- The validation engine introduced new project conventions that needed to be reflected in the project rulebook and skills reference.
- Keeping implementation, assistant rules, and skills documentation aligned reduces drift and makes future extension work more consistent.

## 2026-03-18 15:05:00 +04:00

### Skills and Roadmap Alignment

- Updated `SKILLS.md` to reflect the current validation-engine implementation more precisely.
- Added notes covering:
  - `ValidationIssue` as a dataclass-based standard issue object
  - report generator expectations and supported output formats
  - catalog-backed issue metadata reuse
  - the fact that the interactive validation router currently starts with `geometry` support first
- Updated `plan_of_action.md` with implementation-status notes for:
  - validation engine foundation
  - implemented geometry checks
  - implemented report output support

### Why this change was made

- The skills reference should describe the actual codebase, not only the intended architecture.
- The roadmap needed a light status update so it shows that implementation has started rather than reading as entirely future work.
- This keeps the three layers aligned:
  - implementation
  - operational reference
  - forward plan

## 2026-03-18 15:20:00 +04:00

### Validation Engine Expansion Beyond Geometry

- Added new validation modules:
  - `geoqa/validations/attributes.py`
  - `geoqa/validations/crs.py`
  - `geoqa/validations/metadata.py`
  - `geoqa/validations/accuracy.py`
  - `geoqa/validations/integrity.py`
- Added coverage tests in:
  - `tests/test_additional_validations.py`
- Updated shared validation plumbing:
  - centralized catalog-backed issue construction in `geoqa/validations/base.py`
  - updated `geoqa/validations/__init__.py` exports
- Updated documentation:
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`

### Implemented validation coverage

- Attributes:
  - required null checks
  - uniqueness checks
  - domain/range checks
- CRS:
  - missing CRS detection
  - invalid or unexpected CRS detection
- Metadata:
  - missing core metadata fields
  - incomplete extent/lineage checks
- Accuracy:
  - coordinate precision threshold checks
  - XY tolerance metadata checks
  - positional accuracy checks against a reference layer
- Integrity:
  - missing spatial index checks
  - outdated index checks
  - non-RFC7946 GeoJSON checks

### Why this change was made

- The geometry-only starting point was useful, but GeoQA needed broader validator coverage to match the problem catalog and the active roadmap.
- Moving common issue construction into `base.py` reduces duplication and keeps severity, descriptions, and repair guidance aligned with the central problem catalog.
- Adding tests with lightweight fake layer and geometry objects keeps the non-geometry validator suite fast and less dependent on a full GIS runtime.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 15:45:00 +04:00

### Agent System Foundation

- Added:
  - `geoqa/agent.py`
  - `geoqa/fixes.py`
- Updated:
  - `geoqa/__init__.py`
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`
- Added tests:
  - `tests/test_agent.py`

### Implemented agent capabilities

- explicit dataset-type prompting with schema-based inference as secondary support
- routing for:
  - water network
  - flood zones
  - land use
  - environmental
  - generic
- sample-first review workflow for supported auto-fixes
- combined reporting of:
  - detected issues
  - fix actions taken or rejected
- reusable fix helper exports for user scripts

### Implemented built-in fixes

- `drop_null_geometries`
- `remove_duplicate_vertices`

### Why this change was made

- The validation modules were in place, but GeoQA still needed the actual agent layer that ties dataset-type selection, validation routing, report generation, and controlled fixing into one workflow.
- The implementation keeps explicit user choice as the primary path while still allowing lightweight inference when no dataset type is provided.
- Auto-fixes were kept conservative on purpose so the first agent version does not silently make broad or risky edits.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 16:05:00 +04:00

### Thermal Hardening Pass

- Updated `geoqa/thermal.py` to use more conservative default thresholds and cooldown timing.
- Added explicit thermal profiles:
  - `ThermalGuard.balanced()`
  - `ThermalGuard.cool()`
  - `ThermalGuard.strict()`
- Updated `geoqa/runner.py` so each step now performs a post-step cooldown pass when the CPU is still above the warning threshold.
- Updated `geoqa/agent.py` so `GeoQAAgentScript` now defaults to `ThermalGuard.strict()`.
- Updated tests in `tests/test_thermal_guard.py` to pin their own thresholds explicitly rather than depending on older defaults.
- Updated documentation:
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`

### Why this change was made

- The earlier thermal guard was cooperative but too loose for a heat-sensitive workstation, especially when defaults still allowed the machine to stay in a relatively hot operating band.
- The user requirement is clear: local GeoQA runs should aim for a much cooler operating range and should not casually drift toward extreme temperatures.
- Adding stricter profiles and a post-step cooldown pass reduces the chance of launching the next chunk of work while the CPU is already hot.
- This still does not create a hard physical guarantee, but it materially improves the default safety posture of the library.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 16:20:00 +04:00

### Topology and Interactive Validation Completion Pass

- Added a dedicated topology validation module:
  - `geoqa/validations/topology.py`
- Added topology checks for:
  - same-layer polygon overlap
  - feature-within-feature containment
  - same-layer line intersection
- Expanded `geoqa/interactive_validation.py` so the interactive validation entry point now supports:
  - `geometry`
  - `attributes`
  - `crs`
  - `metadata`
  - `accuracy`
  - `integrity`
  - `topology`
- Added convenience wrappers in `geoqa/agent.py` for:
  - validation-only dataset runs
  - interactive fix application
  - final issue/fix report generation
- Added a prompt-friendly GeoJSON conversion wrapper to `geoai/qgis_layer/__init__.py`.
- Added and expanded tests in:
  - `tests/test_additional_validations.py`
  - `tests/test_agent.py`
- Updated documentation:
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`

### Why this change was made

- The library already had strong coverage across multiple validation domains, but it still lacked a dedicated topology module and a fully broadened interactive validation path.
- Completing those pieces makes the library more coherent for real use: the modules now exist, the interactive entry point can reach them, and the agent surface has clearer convenience APIs.
- Adding the QGIS wrapper also closes a small usability gap between the robust existing PyQGIS helpers and the simpler function shape users may expect.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 16:35:00 +04:00

### Agent Workflow Usability and Auditability Pass

- Extended `geoqa/agent.py` with:
  - lightweight geometry-preview feedback for sample fixes
  - batched full-dataset fix application
  - fix-action JSONL logging
  - safer dataset loading error handling
  - validator error capture as structured issues/messages
  - optional recommendation and post-fix hooks for future AI or rules-based integrations
- Expanded tests in `tests/test_agent.py` for:
  - batched fix application
  - preview handling
  - agent result serialization shape
- Updated documentation:
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`

### Why this change was made

- The earlier agent version was functional but still sparse in a few practical areas: large-dataset workflows, audit logging, sample-fix feedback, and extension points for future recommendation logic.
- These additions make the agent more usable in real QA workflows without forcing full GIS UI work or hardwiring AI behavior into the validation core.
- Capturing validator failures as structured issues also makes the workflow more resilient when datasets, drivers, or optional dependencies behave unexpectedly.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 16:40:00 +04:00

### Governance Sync for Completed GeoQA System

- Updated `AGENTS.md` to reflect the current completed project state.
- Added rule sections covering:
  - validation and agent completion conventions
  - conservative fix-policy expectations
  - audit logging and structured failure handling
  - extension-point guidance for optional AI recommendations

### Why this change was made

- The implementation had moved beyond the earlier validation-engine and thermal-only rule sections.
- The project rulebook needed to reflect the broader completed system so future work extends the existing architecture instead of drifting into parallel patterns.
- `SKILLS.md` and `plan_of_action.md` were already aligned with the latest implementation, so only `AGENTS.md` required a new sync pass.

## 2026-03-18 16:50:00 +04:00

### Structural Compliance Wrapper Pass

- Added wrapper package structure to better match the intended GeoQA layout:
  - `geoqa/agents/`
  - `geoqa/automation/`
  - `geoqa/interactive/`
  - `geoqa/fix/`
  - `geoqa/serialization/`
- Added user-facing wrapper modules:
  - `geoqa/agents/agentic_crsfix.py`
  - `geoqa/automation/crs_validation.py`
  - `geoqa/interactive/validation.py`
- Added documentation-oriented files in `docs/`:
  - `docs/README.md`
  - `docs/agents.md`
  - `docs/skills.md`
  - `docs/plan_of_action.md`
  - `docs/user_guide.md`
- Added wrapper tests in:
  - `tests/test_layout_wrappers.py`
- Updated:
  - `README.md`
  - `SKILLS.md`
  - `plan_of_action.md`
  - `AGENTS.md`

### Why this change was made

- The core GeoQA implementation was already functionally strong, but the repository still did not reflect the fuller package-and-doc layout described in the target design.
- Adding lightweight wrappers preserves the stronger existing implementation while making the structure easier to understand for users expecting dedicated `agents`, `automation`, `interactive`, `fix`, and `serialization` entry points.
- The wrapper approach avoids duplicating core logic and reduces the risk of implementation drift between parallel code paths.

### Verification

- Ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK (skipped=3)`

## 2026-03-18 17:00:00 +04:00

### Documentation Duplicate Cleanup

- Removed duplicate mirror files from `docs/`:
  - `docs/README.md`
  - `docs/agents.md`
  - `docs/skills.md`
  - `docs/plan_of_action.md`
- Kept the root files as the single canonical set:
  - `README.md`
  - `AGENTS.md`
  - `SKILLS.md`
  - `plan_of_action.md`
  - `journal.md`
  - `codex_prompt.md`
- Updated `docs/user_guide.md` to point users to the canonical root documentation files.

### Why this change was made

- The earlier wrapper/docs pass created unnecessary duplication between the repository root and the `docs/` folder.
- For GeoQA, the root governance and reference files are part of the working project conventions, so keeping them canonical at the root is safer than moving them and maintaining parallel copies.
- Removing the duplicates reduces drift risk and makes the documentation layout easier to reason about.

## 2026-03-18 17:05:00 +04:00

### Public Changelog Added

- Added `docs/CHANGELOG.md` as a public-facing summary of notable project changes.

### Why this change was made

- `journal.md` is useful for internal development history and reasoning, but it is too detailed and implementation-oriented for release-style communication.
- A dedicated changelog makes the project easier to scan for users, collaborators, and future release review without replacing the journal's role.

## 2026-03-18 17:10:00 +04:00

### Changelog Maintenance Rule Added

- Updated `AGENTS.md` so future user-visible changes should update `docs/CHANGELOG.md` alongside `journal.md` where relevant.

### Why this change was made

- Once the changelog exists, it should not fall behind the maintained project files.
- Making that expectation explicit in the project rulebook reduces the chance that the journal stays current while the public release summary drifts.

## 2026-03-18 17:20:00 +04:00

### User Guide Improvement Pass

- Expanded `docs/user_guide.md` with:
  - short workflow context ahead of the core usage examples
  - guidance on when to use interactive versus non-interactive agent runs
  - clearer explanations of reusable fix helpers
  - an additional CRS automation example with `auto_fix=True`
  - a short custom agentic script example for user-specific workflows
- Updated `docs/CHANGELOG.md` to reflect the user-guide expansion.

### Why this change was made

- The earlier user guide showed valid entry points, but it was still sparse in the areas where new users usually need judgment support: choosing the right workflow, understanding what helper functions are for, and deciding when automation should stay review-oriented versus auto-fixing.
- Adding a little more explanation without turning the guide into a long manual improves adoption and makes the existing library surface easier to use correctly.
- Recording the change in both the journal and changelog keeps the internal reasoning and the public-facing documentation summary aligned.

## 2026-03-18 17:30:00 +04:00

### Testing Guidance and Next-Phase Planning

- Expanded `docs/user_guide.md` with a dedicated testing section covering:
  - unit testing
  - integration testing
  - real-dataset testing priorities
  - suggested public dataset sources
- Updated `plan_of_action.md` to state that the immediate next phase is real-dataset integration testing.
- Updated `docs/CHANGELOG.md` to reflect the testing-guidance expansion.

### Why this change was made

- The core framework is now in place, so the next meaningful milestone is not more architecture work but testing the system under realistic conditions.
- Adding explicit testing guidance helps turn the current codebase from framework-complete into something that can be validated operationally across real schemas, formats, and dataset sizes.
- Capturing this in the roadmap makes the next phase concrete instead of leaving testing as an implied follow-up.

## 2026-03-18 17:40:00 +04:00

### Public Test Dataset Acquisition

- Downloaded public sample datasets into `data/public_samples/` for real-dataset testing:
  - Natural Earth admin-0 countries
  - Natural Earth populated places
  - Philadelphia FEMA Flood Plain 2023 GeoJSON from Data.gov-linked infrastructure
  - Philadelphia zoning base districts GeoJSON
  - a small OpenStreetMap API extract around Lower Manhattan
- Added `data/public_samples/README.md` documenting source links and intended testing use.
- Updated `docs/user_guide.md` and `docs/CHANGELOG.md` to reflect the local sample-data staging area.

### Why this change was made

- The project had already reached the point where real-dataset testing is the next practical milestone, so downloading a small, diverse public sample set removes the setup friction for that phase.
- The chosen files cover multiple source styles and formats that are useful for GeoQA:
  - Natural Earth for broadly stable administrative and point layers
  - city open-data GeoJSON for attribute- and policy-style checks
  - OpenStreetMap raw extract data for network-style and conversion-oriented experiments
- Keeping a small manifest in the data folder makes the provenance of the downloaded assets explicit and easier to maintain.

## 2026-03-18 18:05:00 +04:00

### First Real-Dataset Integration Pass

- Installed missing runtime dependencies needed for real geospatial execution in this environment:
  - `geopandas`
  - `shapely`
  - `pyproj`
- Fixed JSON report serialization so `ValidationIssue` geometry payloads are converted into JSON-safe values instead of breaking on live Shapely geometry objects.
- Tightened geometry validation so self-crossing linework is detected through non-simple line checks in addition to polygon-style self-intersection validity messages.
- Re-downloaded the Philadelphia GeoJSON samples with a more reliable transfer method after the first copies proved truncated.
- Ran real integration workflows against downloaded public datasets and wrote outputs under `data/integration_results/`.
- Added `data/integration_results/README.md` summarizing the datasets used and generated outputs.

### Integration run outcomes

- Natural Earth countries:
  - generic validation run completed successfully
  - CRS automation run completed successfully with no CRS issues
- Philadelphia FEMA flood plain:
  - flood-zone validation run completed successfully
- Philadelphia zoning:
  - land-use validation run completed and wrote reports
  - geometry validation also demonstrated the structured thermal-limit handling path when the CPU reached 79 C

### Why this change was made

- The project had already reached the point where framework quality was less important than real operational proof, so running GeoQA against public datasets was the next meaningful validation step.
- The serialization fix and line self-intersection fix were both uncovered or confirmed in the process of exercising the real workflows rather than staying inside mocked unit tests.
- Saving the generated reports gives the project a concrete baseline for future regression checks against real data instead of only synthetic fixtures.

## 2026-03-18 18:15:00 +04:00

### Dedicated Test Ledger Added

- Added `docs/tests.md`.
- Recorded:
  - unit-test execution status
  - real-dataset integration runs
  - datasets used
  - the purpose of each test
  - what was found
  - whether the test was successful
  - whether the result was effectively null because no issues were found
- Updated `docs/user_guide.md` and `docs/CHANGELOG.md` to reference the new test ledger.

### Why this change was made

- The integration outputs and journal entries were useful, but they did not yet provide a single clean place to answer practical QA questions such as:
  - what exactly was tested
  - what dataset was used
  - whether the script behaved correctly for its intended purpose
  - whether a no-issue result should be treated as a successful null case
- A dedicated test ledger makes the project easier to review, extend, and audit without forcing readers to reconstruct testing history from raw JSON artifacts and journal prose alone.

## 2026-03-18 18:20:00 +04:00

### Test Ledger Refinement

- Expanded `docs/tests.md` to add:
  - run dates
  - command snippets for each real integration run
  - expected behavior notes for each recorded workflow
- Updated `docs/CHANGELOG.md` to reflect the refinement.

### Why this change was made

- The first version of the test ledger already captured outcomes well, but it still benefited from a little more execution context so future reviews can see not just what happened, but what command shape and expected behavior were being evaluated.
- This makes the testing record easier to reuse as a regression checklist and reduces ambiguity when comparing future runs against the first documented baseline.

## 2026-03-18 18:35:00 +04:00

### Integration Runner and Edge-Case Fixture Setup

- Added `scripts/run_integration_samples.py`.
- The runner:
  - executes selected public-sample workflows
  - records duration
  - records dataset size and feature-count metrics
  - records geometry-type counts
  - records a post-run thermal snapshot
  - writes a JSON summary for later comparison
- Added a local synthetic edge-case sample area:
  - `data/public_samples/edge_cases/`
- Added initial edge-case fixtures:
  - `self_intersection_polygon.geojson`
  - `duplicate_vertex_line.geojson`
- Verified the runner on the lightweight CRS profile and wrote:
  - `data/integration_results/integration_summary_metrics.json`
- Updated:
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `docs/CHANGELOG.md`
  - `plan_of_action.md`

### Why this change was made

- The next testing phase needed more than prose guidance; it needed a repeatable execution path that could capture simple operational metrics without immediately escalating into heavy stress testing.
- Adding a small synthetic edge-case area reduces dependence on network downloads for common regression scenarios such as self-intersection and duplicate-vertex detection.
- Verifying the runner on a low-risk CRS profile kept the CPU load modest while still proving that the metrics-capture path works in this environment.

## 2026-03-18 18:45:00 +04:00

### Hybrid Execution Model Guidance Added

- Updated project guidance to formalize a hybrid execution model:
  - Level 0: deterministic code
  - Level 1: light AI semantic assistance
  - Level 2: heavier AI reasoning and planning
- Updated `AGENTS.md` to explicitly forbid using LLMs for coordinate math, CRS reprojection, or other deterministic spatial transformations.
- Updated `SKILLS.md`, `plan_of_action.md`, and `README.md` to explain that geometry and CRS operations should remain in `pyproj`, `shapely`, `geopandas`, or similar deterministic tooling.
- Updated `docs/CHANGELOG.md` to reflect the new architectural guidance.

### Why this change was made

- The distinction is important for geospatial safety: coordinate transformations and geometry math are not reasoning tasks and should not be delegated to probabilistic models.
- Formalizing the split between deterministic spatial computation and AI-assisted reasoning reduces hallucination risk, improves correctness, and fits the project's thermal constraints well because most routine validation remains cheap code execution instead of heavier model work.

## 2026-03-18 19:00:00 +04:00

### ML-Ready QA Output Layer Added

- Added a new `geoqa/ml/` package with:
  - `annotations.py`
  - `features.py`
  - `exports.py`
  - `__init__.py`
- Implemented:
  - per-feature QA annotation helpers
  - simple quality-score generation from issue severity and count
  - issue-derived feature-row generation
  - ML-ready dataset exports for CSV, JSONL, and GeoParquet
- Updated `geoqa/__init__.py` to export the new ML helpers.
- Added tests in:
  - `tests/test_ml.py`
- Updated:
  - `README.md`
  - `SKILLS.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- GeoQA already had strong validation and reporting layers, but it did not yet provide a clean bridge from validation output into ML-ready training data preparation.
- Adding QA annotations and export helpers makes it possible to carry validation knowledge directly into downstream model pipelines through explicit features rather than forcing users to reconstruct that logic themselves.
- Keeping this work in a dedicated `geoqa.ml` layer preserves the architectural split between deterministic spatial validation and downstream data-preparation tasks.

## 2026-03-18 19:20:00 +04:00

### Conversion Layer and Streamlit App Added

- Added `geoqa/conversion.py` for deterministic vector-format loading and export workflows.
- Added new deterministic fix helpers:
  - `make_geometries_valid`
  - `apply_basic_geometry_fixes`
- Updated the fix wrapper exports in `geoqa/fix/__init__.py`.
- Added `streamlit_app.py` as a first local UI entry point for:
  - dataset upload
  - vector format conversion
  - deterministic geometry cleaning
  - tabular preview
  - optional Folium-based map preview when supported
- Added tests in:
  - `tests/test_conversion.py`
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `SKILLS.md`
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- A practical local app becomes more useful when it can normalize data formats and apply a deterministic cleanup pass before deeper validation or review.
- These functions fit GeoQA well because they are still deterministic spatial/data operations, not AI reasoning tasks.
- Keeping the Streamlit app as a thin composition layer over the underlying library functions preserves the architecture while making the system more accessible for local users who do not want to jump between multiple tools.

## 2026-03-18 19:35:00 +04:00

### Test Ledger Structure Improved

- Updated `docs/tests.md` to add:
  - a test-status legend
  - environment details for the recorded test pass
  - a top summary table for quick scanning
  - rerun guidance
  - explicit per-run notes for:
    - `interactive`
    - `fixes applied`
    - issue-type classification
- Updated `docs/CHANGELOG.md`.

### Why this change was made

- The testing ledger already had strong detail, but it was becoming harder to scan quickly.
- Adding a compact summary and a small amount of structured metadata makes the document more useful for both internal review and future reruns without changing the underlying test results.

## 2026-03-18 19:50:00 +04:00

### Lightweight Onboarding Assets Added

- Added `docs/START_HERE.md` as a minimal first-stop guide for new users.
- Added `examples/geoqa_quickstart.ipynb` as a small deterministic notebook walkthrough covering:
  - loading a local sample dataset
  - running one geometry validator
  - writing a JSON report
  - reading the report back
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `plan_of_action.md`
  - `AGENTS.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The project already had strong reference documentation, but new users still benefited from a lower-friction entry point that shows one complete GeoQA path end to end.
- A lightweight guide and notebook reduce activation energy without adding a heavy new subsystem or pushing users immediately into the broader agent workflow.
- Keeping the quickstart deterministic and sample-based also fits the workstation's thermal constraints better than using a heavier first-run example.

## 2026-03-18 20:30:00 +04:00

### Start-Here Guide Polished for Adoption

- Renamed the onboarding entry file to `docs/START_HERE.md`.
- Expanded the guide to add:
  - a short why-this-example section
  - a setup/install step
  - example output
  - a what-just-happened explanation
- Updated references in:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/checklist.md`
  - `plan_of_action.md`
  - `AGENTS.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The earlier guide was structurally useful, but it still assumed too much readiness and jumped into code too quickly for true first-time users.
- Adding a little context, setup guidance, and output expectation makes the first-run path more comparable to strong open-source quickstarts and lowers adoption friction without making the guide long.

## 2026-03-18 20:00:00 +04:00

### Dedicated Checklist Added

- Added `docs/checklist.md` to track practical remaining work outside the main roadmap.
- Updated `docs/user_guide.md` and `docs/CHANGELOG.md` to reference the checklist.

### Why this change was made

- `plan_of_action.md` is better kept as the strategic roadmap rather than a dense punch list.
- A dedicated checklist makes it easier to scan what is already done, what is next, and what is later without mixing that status layer into the broader planning document.

## 2026-03-18 20:10:00 +04:00

### Spreadsheet Project Schedule Added

- Added `docs/project_schedule.xlsx`.
- The workbook includes:
  - a `Schedule` sheet
  - a `Legend` sheet
  - task rows grouped across completed, next, and later work
  - status, priority, target window, dependency, deliverable, and notes columns
- Updated:
  - `docs/checklist.md`
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- A spreadsheet view is easier to use as a lightweight project-management artifact than prose alone, especially when someone wants a fast view of what is complete versus what remains.
- Keeping it in `docs/` makes it easy to share while leaving `plan_of_action.md` as the strategic roadmap and `docs/checklist.md` as the text-first status view.

## 2026-03-18 20:15:00 +04:00

### Project Schedule Workbook Styling Improved

- Updated `docs/project_schedule.xlsx` to improve scanability with:
  - color-coded status cells
  - color-coded workstream cells
  - color-coded priority cells
  - icon-style status markers
  - a clearer legend sheet

### Why this change was made

- A project-management workbook is more useful when people can read status quickly without scanning every row in detail.
- Adding simple visual coding makes the schedule easier to review during planning and status checks while keeping the underlying task content unchanged.

## 2026-03-18 20:20:00 +04:00

### Project Schedule Status Labels Cleaned

- Updated `docs/project_schedule.xlsx` so the status column now shows a single status label:
  - `Done`
  - `Next`
  - `Later`
- Kept the color-coding and legend styling in place.
- Updated `docs/CHANGELOG.md`.

### Why this change was made

- The earlier formatting used a marker prefix plus the status word, which made the cells read redundantly.
- Removing the duplicated wording keeps the sheet easier to scan while preserving the visual status cues.

## 2026-03-18 21:00:00 +04:00

### Real-Dataset Integration Coverage Expanded

- Downloaded additional larger public datasets into `data/public_samples/`:
  - `natural_earth/ne_10m_admin_1_states_provinces`
  - `natural_earth/ne_10m_roads`
  - `natural_earth/ne_10m_lakes`
- Added a derived local GeoPackage sample:
  - `derived/ne_10m_admin_1_states_provinces.gpkg`
- Expanded `scripts/run_integration_samples.py` with new profiles for:
  - larger admin-boundary generic validation
  - GeoPackage CRS validation
  - lakes generic validation
  - roads generic validation
- Ran the new integration profiles and wrote:
  - `data/integration_results/integration_summary_expanded_safe.json`
  - `data/integration_results/integration_summary_roads.json`
- Updated:
  - `data/public_samples/README.md`
  - `data/integration_results/README.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The top next-step item in the checklist was to expand real-dataset integration coverage, so the most useful move was to add larger datasets rather than continuing to discuss the gap abstractly.
- Using a mix of larger polygon, line, and GeoPackage inputs gives GeoQA a more meaningful operational baseline across both dataset type and format.
- The new runs also helped separate three important behaviors:
  - clean larger runs
  - larger runs that complete but require cooldown
  - larger runs that trigger structured thermal-interruption messages

## 2026-03-18 21:15:00 +04:00

### Large Staged Datasets Added for Future Chunking Work

- Added a new staging area:
  - `data/large_public_samples/`
- Downloaded larger Geofabrik OSM extracts:
  - `new-jersey-latest.osm.pbf`
  - `pennsylvania-latest.osm.pbf`
  - `new-york-latest.osm.pbf`
- Added `data/large_public_samples/README.md` documenting source, size, and intended use.
- Updated:
  - `docs/checklist.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The user plans to add chunking with sleep for larger datasets, so staging genuinely larger files now removes later setup friction.
- Keeping these assets in a separate folder makes it clear they are future chunking and throughput targets rather than lightweight baseline samples for ordinary validation runs.
- The downloads themselves are low-CPU work, so they are a safe preparatory step even on a heat-sensitive machine.

## 2026-03-18 21:35:00 +04:00

### Chunked Validation Added for Larger Dataset Workflows

- Updated `geoqa/agent.py` to support:
  - `validation_chunk_size`
  - `sleep_between_validation_chunks_seconds`
  - guard-aware pauses between validation chunks
- Kept correctness-sensitive checks such as uniqueness and CRS-style full-layer checks outside the per-chunk path where needed.
- Added tests in:
  - `tests/test_agent.py`
- Re-ran:
  - `python -m unittest tests.test_agent`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `SKILLS.md`
  - `docs/checklist.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `AGENTS.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The next practical step after staging genuinely larger datasets was to make standard validation capable of running in smaller slices instead of one long hot pass.
- Adding chunking and optional sleeps directly to the agent workflow preserves the existing architecture and reporting model while making large-dataset validation more realistic on a heat-sensitive local machine.
- Keeping full-layer checks out of the chunked path where needed helps avoid silently breaking correctness just to gain batching.

## 2026-03-18 21:50:00 +04:00

### Chunking Recommendation and Interactive Rerun Added

- Updated `geoqa/agent.py` so a non-chunked validation run can now:
  - detect thermal/runtime pressure
  - recommend chunking settings
  - offer a one-time chunked rerun in interactive mode
- Added tests in `tests/test_agent.py` for:
  - non-interactive chunking recommendation output
  - interactive acceptance of a chunked rerun
- Re-ran:
  - `python -m unittest tests.test_agent`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `SKILLS.md`
  - `docs/checklist.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `AGENTS.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- Chunking is useful, but users should not have to guess when they need it.
- Offering a one-time rerun after an actual problem preserves simple default behavior while giving users guided recovery when the initial validation path proves too hot or too fragile for the current machine and dataset combination.

## 2026-03-18 22:00:00 +04:00

### Chunking Guidance Added to Onboarding Docs

- Updated `docs/START_HERE.md` to explain:
  - when chunking is not needed
  - when chunking becomes useful
  - that GeoQA can now suggest and offer a chunked rerun after thermal/runtime pressure
- Updated `docs/user_guide.md` with a short chunking guidance section for the agent workflow.
- Updated `docs/CHANGELOG.md`.

### Why this change was made

- Once chunking and rerun guidance existed in code, the user-facing onboarding docs also needed a simple explanation so new users do not assume chunking is always required.
- This keeps the entry path simpler: normal runs stay normal, and chunking is framed as a recovery and scaling tool rather than a default burden.

## 2026-03-18 22:25:00 +04:00

### Local Private-Data Integration Pass

- Scanned a private local dataset folder used only for internal testing.
- Identified usable real layers across:
  - large water-network line assets
  - large water-network point assets
  - projected polygon layers
  - smaller polygon control layers
- Wrote an inventory manifest:
  - `data/integration_results/training_data_inventory.json`
- Ran GeoQA integration workflows against four local shapefiles and wrote a run summary:
  - `data/integration_results/training_data_summary.json`
- Added detailed result records for the private local runs, while keeping the dataset names out of the project-facing ledger.
- Updated:
  - `data/integration_results/README.md`
  - `docs/tests.md`
  - `docs/checklist.md`
  - `docs/CHANGELOG.md`

### Integration run outcomes

- Private Dataset A:
  - `35,223` features
  - `water_network` workflow
  - chunked validation with `validation_chunk_size=4000`
  - `17` issues detected
  - all reported issues were `self_intersection`
- Private Dataset B:
  - `60,047` features
  - `water_network` workflow
  - chunked validation with `validation_chunk_size=5000`
  - `0` issues detected
  - valid null result
- Private Dataset C:
  - `558` features
  - `generic` workflow
  - `244` issues detected
  - mostly `coordinate_precision_not_fit_for_use`
- Private Dataset D:
  - `49` features
  - `generic` workflow
  - `50` issues detected
  - mostly `coordinate_precision_not_fit_for_use`

### Why this change was made

- The user asked to test GeoQA against private local shapefiles and CSV-adjacent data rather than only public samples.
- This pass expands the real-world baseline with data that is closer to likely operational use: local utility-network and engineering-style layers.
- The larger private line and point runs also gave a practical test of the new chunked validation path on substantial internal shapefiles without triggering a thermal fallback.

## 2026-03-18 22:40:00 +04:00

### Local Test Ledger Split

- Added:
  - `docs/local_data_tests.md`
- Moved the private local-data integration record out of:
  - `docs/tests.md`
- Kept `docs/tests.md` focused on the public/baseline test track.
- Updated:
  - `docs/user_guide.md`
  - `docs/START_HERE.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The private local-data pass is useful, but it should not crowd the main public-facing test ledger.
- Splitting the records keeps the public baseline easier to scan while giving local/internal datasets a dedicated place for future additions.

## 2026-03-18 23:00:00 +04:00

### Streamlit Shapefile Upload Fix

- Updated `geoqa/conversion.py` with upload-resolution helpers for:
  - single uploaded datasets
  - complete multi-file Shapefile uploads
  - clearer errors when a user uploads only a bare `.shp`
- Updated `streamlit_app.py` to:
  - accept multiple uploaded files
  - allow `.shp`, `.dbf`, `.shx`, `.prj`, and `.cpg` parts
  - reconstruct a Shapefile dataset from the uploaded file set
  - continue supporting single-file uploads such as GeoJSON, GPKG, KML, CSV, and `.zip`
- Expanded `tests/test_conversion.py` to cover:
  - rejection of bare `.shp` uploads
  - successful reconstruction of a complete Shapefile upload bundle
  - failure on incomplete Shapefile bundles
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The first Streamlit version only handled one uploaded object, which is a bad fit for Shapefiles because a valid Shapefile dataset depends on multiple companion files.
- Allowing either a zipped bundle or a full uploaded sidecar set makes the app much more realistic for actual GIS usage without moving Shapefile-specific complexity into the UI itself.

## 2026-03-19 00:05:00 +04:00

### Streamlit Preview Fallback Hardened

- Updated `streamlit_app.py` so the preview path now:
  - checks whether `folium` exposes the expected `Map` and `GeoJson` API
  - falls back to a GeoJSON text preview with a warning instead of crashing the app
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Confirmed the local environment issue:
  - `import folium` succeeds
  - `folium.__file__` is `None`
  - `folium.Map` is missing
- Updated:
  - `docs/CHANGELOG.md`

### Why this change was made

- The earlier Streamlit preview only guarded the `folium` import step, but the real failure happened later when the imported module did not actually provide the expected mapping API.
- Falling back to a text preview keeps the app usable even in partially broken or unusual Python environments.

## 2026-03-19 00:50:00 +04:00

### Streamlit Rerun and Table-Preview Fixes

- Updated `geoqa/conversion.py` to add:
  - `table_preview_frame(...)`
- Updated `streamlit_app.py` to:
  - cache the loaded layer in session state by upload signature
  - cache the cleaned working layer by fix-option signature
  - reuse cached previews during download-triggered reruns
  - render the table preview from a geometry-safe WKT-based frame
- Expanded `tests/test_conversion.py` to verify the new table-preview helper.
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- Streamlit reruns the script on many UI actions, including downloads, so the earlier app structure could re-trigger the geometry-fix pass unnecessarily.
- The table preview also needed to stop feeding raw geometry objects into Streamlit's Arrow-oriented display path because that can fail on geometry dtype handling.
- Caching the working layer and converting preview geometry to WKT makes the app more stable and much less annoying in real use.

## 2026-03-19 01:05:00 +04:00

### Streamlit Preview Tabs Added

- Updated `streamlit_app.py` so the preview section now uses tabs for:
  - `Map`
  - `GeoJSON`
- Added GeoJSON sub-tabs for:
  - parsed GeoJSON
  - raw GeoJSON text
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The raw preview payload was still annoying to inspect when shown as one long horizontal line.
- Tabs give the app a much more usable fallback when the interactive map is unavailable or when a user wants to inspect the preview payload directly.

## 2026-03-19 01:20:00 +04:00

### GeoParquet Upload Support Added

- Updated `geoqa/conversion.py` so `load_vector_dataset(...)` now reads:
  - `.parquet` via `geopandas.read_parquet(...)`
- Updated `streamlit_app.py` so the uploader now accepts:
  - `.parquet`
- Added a regression test in:
  - `tests/test_conversion.py`
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The app already exported GeoParquet, so rejecting `.parquet` at upload time was an obvious gap.
- Adding explicit GeoParquet input support makes the conversion layer more symmetrical and avoids forcing users to round-trip through a different format just to re-open an exported layer.

## 2026-03-19 01:40:00 +04:00

### Streamlit Map Backend Simplified and GeoParquet Export Hardened

- Updated `streamlit_app.py` so the preview map now uses:
  - `pydeck`
  - a simple `GeoJsonLayer`
  - automatic center estimation from the preview GeoJSON coordinates
- Removed the map preview's dependency on `folium` for the normal preview path.
- Updated `geoqa/conversion.py` so GeoParquet export now uses:
  - `compression=None`
- Expanded `tests/test_conversion.py` with a GeoParquet export/load round-trip check.
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The earlier preview path still depended on Folium even though Streamlit already carries a map-capable frontend path through PyDeck.
- Moving to PyDeck reduces environment fragility for the app preview.
- GeoParquet export also needed to stop depending on optional compression codec support, so uncompressed output is the safer default for this local workflow.

## 2026-03-19 02:05:00 +04:00

### CSV Export Warning Cleanup

- Updated `geoqa/conversion.py` so CSV export now converts GeoDataFrame content through a plain pandas frame before rewriting geometry to WKT.
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Updated:
  - `docs/CHANGELOG.md`

### Why this change was made

- The CSV export path still worked, but it emitted a confusing GeoPandas warning about the geometry column not containing geometry after the column was intentionally converted to WKT text.
- That warning looked too much like a real failure during app use, so the export path was cleaned up to keep the terminal output clearer.

## 2026-03-19 02:20:00 +04:00

### Runtime `zstandard` Dependency Added

- Installed:
  - `zstandard`
- Updated:
  - `requirements.txt`
  - `pyproject.toml`
  - `docs/CHANGELOG.md`

### Why this change was made

- The export error persisted even on `CSV`, which showed the failure was not GeoParquet-specific.
- The actual issue was a missing runtime codec dependency in the Streamlit download/export environment, so `zstandard` was added explicitly to the project runtime requirements.

## 2026-03-19 01:55:00 +04:00

### Prioritized Next-Sprint Plan Added

- Updated:
  - `docs/checklist.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`
- Recorded the agreed next-sprint priority order as:
  - adaptive chunking for thermal stability
  - end-to-end ML training-prep demo
  - CI/CD quality gate
  - ISO 19157 alignment
  - Streamlit advanced controls

### Why this change was made

- The current real-dataset results already provide enough evidence to prioritize the next round of work more explicitly.
- This plan is project-wide rather than UI-only; only the final item is Streamlit-specific.
- Capturing the priority order now helps keep the next implementation pass focused on the highest-value gaps instead of expanding sideways.

## 2026-03-19 00:20:00 +04:00

### Basic Dependency Manifest Added

- Added:
  - `requirements.txt`
- Included current runtime dependencies for:
  - the core geospatial library path
  - thermal support
  - the Streamlit app and map preview path
- Updated:
  - `README.md`
  - `docs/START_HERE.md`
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The project had already grown past the point where ad hoc install commands were enough.
- A basic dependency manifest lowers setup friction, especially for first-time users trying the Streamlit app or onboarding docs.
- Optional `geoai` backends remain intentionally separate because JAX, PyQGIS, and TOON availability still depends on the target environment.

## 2026-03-19 00:35:00 +04:00

### Packaging and Dev-Install Metadata Added

- Added:
  - `pyproject.toml`
  - `requirements-dev.txt`
- Updated `geoqa/__init__.py` to export:
  - `__version__ = "0.3.0"`
- Kept:
  - `requirements.txt` as the simple runtime install path
- Updated:
  - `README.md`
  - `docs/START_HERE.md`
  - `docs/user_guide.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The project had reached the point where a runtime requirements file alone was not enough; editable installs and package metadata also needed a standard place.
- `pyproject.toml` provides a cleaner baseline for packaging, local editable installs, and future release discipline.
- Keeping `requirements.txt` and `requirements-dev.txt` alongside it preserves a simple setup path for users who do not want to think about packaging details.

## 2026-03-19 02:15:00 +04:00

### Streamlit Export Delivery Fallback

- Updated `streamlit_app.py` so exported files are now offered through a direct browser download link instead of `st.download_button`.
- Kept the existing export-file generation path in `geoqa/conversion.py`.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The export writers themselves were already working in plain Python, but the Streamlit app was still surfacing an environment-specific `zstandard` failure during the final download-widget path, even for `CSV` exports.
- Switching to a direct browser download link bypasses that widget/runtime path while preserving the exported file contents and format support.

## 2026-03-19 02:35:00 +04:00

### CSV WKT Reload Support Added

- Updated `geoqa/conversion.py` so CSV loading now supports geometry stored as WKT text in:
  - `geometry`
  - `geom`
  - `wkt`
- Added tests in `tests/test_conversion.py` for:
  - direct CSV WKT loading
  - `GeoParquet -> CSV -> reload` round-trip behavior
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The app could export a cleaned dataset to `CSV`, but re-uploading that exported CSV failed because the loader only knew how to build geometry from longitude/latitude columns.
- Supporting WKT geometry makes GeoQA-exported CSV files round-trip correctly in the app and aligns the CSV import path with the library's own CSV export behavior.

## 2026-03-19 02:45:00 +04:00

### Streamlit Processing Feedback Panel Added

- Updated `streamlit_app.py` so fix execution is now surfaced before the dataset summary through a dedicated feedback section.
- The app now runs the deterministic fix sequence step-by-step in the UI layer and records:
  - which steps were requested
  - which steps were skipped
  - which steps ran without changes
  - row-removal counts
  - geometry-change counts
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier UI applied automatic fix options, but it did not clearly show what the app had actually done.
- Adding a visible feedback panel makes the automatic behavior inspectable before users look at the preview or export the result.

## 2026-03-19 03:35:00 +04:00

### Streamlit Workflow Split and Chunk-Resume Path Added

- Restructured `streamlit_app.py` into two user-facing modes:
  - `Inspect / Fix`
  - `Convert / Export`
- Kept preview and cleaning available without forcing conversion.
- Added clearer preview messaging so the GeoJSON-based preview is explicitly treated as inspection data rather than the chosen export format.
- Added a thermal-stop recovery path in the app:
  - when a direct fix pass is stopped by thermal safety, the UI can offer chunked continuation
  - chunked continuation resumes from the last completed step or chunk
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier app mixed inspection and conversion too tightly, which made it feel like conversion was mandatory even when the user only wanted preview or cleaning.
- The thermal feedback also needed a practical next step in the UI, not just a stop message.
- Splitting the workflow and adding resumable chunking makes the app closer to the intended local productivity model for larger datasets.

## 2026-03-19 03:55:00 +04:00

### Streamlit Row-Level Fix Feedback Added

- Updated `streamlit_app.py` so per-step fix feedback can now include row-level detail for changed or removed features.
- Each detailed entry can now show:
  - row index
  - a best-effort feature identifier
  - changed column (`geometry`)
  - change type
  - a short why/explanation
  - before/after geometry snippets
- Added a map-note explanation clarifying that apparent boundary mismatch against the basemap is usually a source-data or reference-data issue rather than something GeoQA or AI should invent automatically.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- Aggregate counts were useful, but they were not enough to answer the practical question of which feature changed and why.
- The map note was added because geometry validity repair and cartographic/reference mismatch are different problems and should not be conflated.

## 2026-03-19 04:00:00 +04:00

### Streamlit Map Fit and Before/After Change Preview Added

- Updated `streamlit_app.py` so the preview map now derives its initial zoom from layer bounds instead of using a fixed zoom level.
- Added before/after map tabs inside row-level fix detail expanders when geometry changes are available.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- A fixed zoom made the preview map too blunt for larger or smaller layers and could leave the user looking at the wrong scale on first load.
- The earlier map was also not helpful enough for actual fix inspection because it only showed the current layer state.
- Adding per-step before/after previews makes the map serve the intended review purpose rather than acting as a generic display widget.

## 2026-03-19 04:15:00 +04:00

### Reference Boundary Mismatch Validator Added

- Added `boundary_mismatch_against_reference(...)` to `geoqa/validations/topology.py`.
- Exported the new validator through `geoqa/validations/__init__.py`.
- Added regression coverage in `tests/test_additional_validations.py`.
- Re-ran:
  - `python -m unittest tests.test_additional_validations`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- A visual mismatch against a basemap can be meaningful, but a basemap is not a defensible source of truth for QA by itself.
- The better validation pattern is to compare a dataset against an authoritative reference layer and quantify the mismatch, which is what this new validator provides.

## 2026-03-19 04:30:00 +04:00

### Streamlit OSM/PBF Upload Support Added

- Updated `geoqa/conversion.py` to support:
  - listing available vector layers for multi-layer OGR sources
  - choosing a default preferred layer name for OSM/PBF-style datasets
  - loading `.pbf` / `.osm` inputs through an explicit `ogr_layer` selection when needed
- Updated `streamlit_app.py` so the app now:
  - accepts `.pbf` and `.osm` uploads
  - inspects available internal source layers before opening the working layer
  - exposes a `Source layer` selector for multi-layer inputs such as OSM PBF
  - warns when `keep original` export is requested for a raw OSM/PBF source, since that direct export path is not currently supported
- Added conversion-layer regression coverage in `tests/test_conversion.py` for:
  - default OSM/PBF layer selection preference
  - empty-layer fallback
  - graceful handling of non-dataset files when listing layers
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The conversion layer could already read OSM/PBF through GeoPandas/OGR, but the Streamlit uploader still blocked those files before GeoQA had a chance to inspect them.
- OSM/PBF datasets often expose multiple internal layers, so simply allowing the extension was not enough; the app also needed a clean way to choose whether the user wanted `multipolygons`, `lines`, `points`, or another source layer.
- Adding an explicit warning for unsupported raw-format export avoids implying that `keep original` can round-trip a raw OSM/PBF source when the current export layer only supports the established vector output formats.

## 2026-03-19 04:40:00 +04:00

### Streamlit Processing Status Indicator Added

- Updated `streamlit_app.py` so the app now surfaces a visible progress/status indicator around:
  - upload resolution
  - source-layer inspection
  - selected-layer opening
  - deterministic fix execution
  - preview refresh
- The status bar is shown near the source-layer area so larger datasets no longer appear idle while the app is working.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- Larger datasets and multi-layer sources can take long enough that the earlier UI felt unresponsive, especially around the new source-layer selection step.
- A small visible progress indicator is better than relying only on spinners because it gives the user a stable place to look while the app moves through its internal phases.

## 2026-03-19 04:45:00 +04:00

### Streamlit Change-Map JSON Serialization Fix

- Updated `streamlit_app.py` so row-level before/after change-map previews now coerce NumPy-style scalar values into plain Python scalars before building preview GeoJSON.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The row-level change table can carry identifiers or indexes backed by NumPy scalar types such as `int32`.
- Those values are fine for tables, but they can fail when the app tries to serialize the same detail rows into GeoJSON for before/after map previews.
- Normalizing those values up front keeps the per-step map previews stable without changing the visible fix-detail content.

## 2026-03-19 04:55:00 +04:00

### Streamlit Change-Map Normalization and Width Cleanup

- Updated `streamlit_app.py` so before/after change-map previews now recursively normalize the full preview GeoJSON payload, including nested geometry coordinate values, before calling `json.dumps(...)`.
- Replaced the deprecated Streamlit dataframe argument `use_container_width=True` with `width="stretch"` in the row-level fix-detail table.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier fix only normalized scalar values in feature properties, but NumPy-backed values can also appear deeper in the GeoJSON payload and still break serialization.
- Streamlit also emitted a deprecation warning for `use_container_width`, so the fix-detail table needed to move to the newer width API to keep the UI output clean.

## 2026-03-19 05:05:00 +04:00

### Streamlit Local-Path Dataset Mode Added

- Updated `streamlit_app.py` so datasets can now be opened either by:
  - browser upload
  - direct local filesystem path
- The app now records the active source path/label in the dataset summary and keeps the same downstream layer-inspection, fix, preview, and export flow for both source modes.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The failing `census_places_national_2025_real_20260227_024144.csv` file was confirmed to be only about 4 MB and structurally valid, so the observed `AxiosError: Network Error` was not a GeoQA parser problem.
- That failure happens in the browser-to-Streamlit upload path before GeoQA gets the file, so adding a direct local-path mode is the correct way to support larger or otherwise troublesome local datasets without depending on frontend upload behavior.

## 2026-03-19 05:10:00 +04:00

### Streamlit Quoted Local-Path Input Support Added

- Updated `streamlit_app.py` so local-path mode now strips matching leading/trailing single or double quotes from pasted filesystem paths before resolving them.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- Windows paths are often pasted with surrounding quotes from terminals, editors, or shell snippets.
- The earlier local-path mode treated those quotes literally, which made valid paths appear missing even though the underlying file existed.

## 2026-03-19 05:20:00 +04:00

### Public CSV Integrity Check and Loader Hardening

- Checked the public CSV datasets under:
  - `GIS-Department/GIS-Prototype/Sandbox-TIG/data/real/`
- Verified that the `census_places_national_2025_real_20260227_024144.csv` file is structurally sound and now loads through `geoqa.conversion.load_vector_dataset(...)`.
- Confirmed that this Census file contains:
  - `718` rows
  - `1` row with missing coordinate values, now represented as null geometry instead of causing a loader failure
- Updated `geoqa/conversion.py` so CSV point loading now:
  - recognizes additional public-data coordinate columns such as `INTPTLAT`, `INTPTLONG`, `INTPTLAT_num`, `INTPTLONG_num`, and centroid-style names
  - preserves rows with missing coordinates as null geometry rather than failing on `float(None)`
- Added regression coverage in `tests/test_conversion.py` for:
  - Census-style coordinate-column naming
  - rows with missing coordinate values
- Re-ran:
  - `python -m unittest tests.test_conversion`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Integrity findings

- Most of the public CSV files in the sandbox folder are structurally readable.
- One of the large GeoBoundaries CSV variants appears genuinely malformed or truncated:
  - `geoboundaries_global_adm1_geoms_20260225_025619.csv`
  - observed failure:
    - `EOF inside string`
- The alternate GeoBoundaries export with the nearby timestamp should be treated as the healthier candidate unless re-downloaded verification suggests otherwise:
  - `geoboundaries_global_adm1_geoms_20260225_025253.csv`

### Why this change was made

- The immediate app failure on the Census places CSV was not caused by a corrupt dataset; it was caused by GeoQA's CSV loader being too strict about coordinate-column naming and missing-coordinate handling.
- Public datasets often use agency-specific field names and occasionally include one or two incomplete records, so the loader needed to be more tolerant without pretending those rows are clean.

## 2026-03-19 05:30:00 +04:00

### Streamlit Point-Preview Visibility Improved

- Updated `streamlit_app.py` so the PyDeck `GeoJsonLayer` now renders point geometries with an explicit circle point type and visible point radius settings.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- Point datasets were loading correctly, but the preview map could still look empty because the generic GeoJSON layer configuration made points too subtle to notice at normal zoom.
- Giving point features an explicit visible radius makes the map behave like an inspection tool rather than a blank background for point-based datasets.

## 2026-03-19 05:45:00 +04:00

### Streamlit Preview Theme, Legend, and Attribute Tab Added

- Updated `streamlit_app.py` so the preview area now:
  - uses a darker basemap style
  - shows an inferred preview label such as `Cities / Places`, `Roads`, `Water Network`, or `Boundaries / Areas`
  - adds a simple legend panel describing the inferred theme and geometry mix
  - adds an attributes-only preview tab alongside the map and raw preview-data tabs
  - keeps a separate full-table preview with geometry in WKT form
- Added schema/geometry-based point-symbol hints for common point-style datasets in the preview map and legend.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier map preview was functional but still read too much like a debugging pane rather than an inspection surface.
- Adding a darker basemap, a clearer legend, a dedicated attributes view, and an inferred preview label makes it much easier to understand what kind of dataset is being shown before the user drops into raw JSON or WKT-heavy tables.

## 2026-03-19 05:50:00 +04:00

### Streamlit Preview Indentation Regression Fixed

- Corrected an indentation error in `streamlit_app.py` that had broken the row-level before/after preview tab block inside the fix-feedback expander.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The preview-theme update introduced a simple block-indentation mistake in the Streamlit UI code.
- The fix restores normal script execution without changing the intended before/after preview behavior.

## 2026-03-19 06:05:00 +04:00

### Streamlit Preview Contrast and Table Simplification

- Updated `streamlit_app.py` so the main preview map now uses a lighter road-style basemap instead of the earlier very dark theme.
- Strengthened point rendering in the preview map with a dedicated point layer so point datasets are easier to see at normal zoom.
- Removed the duplicate `Attributes` preview tab from the upper preview area.
- Kept a single combined attribute/geometry table below the preview area as the canonical table surface.
- Re-ran:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The darker map style looked too heavy against the existing Streamlit UI and made point datasets harder to read.
- Showing both an attributes-only tab and a lower table preview was redundant and made the inspection workflow less clear than it should be.

## 2026-03-19 06:20:00 +04:00

### Streamlit Point Labels and Framed Map Styling

- Updated `streamlit_app.py` so point-based preview layers now show feature labels when a useful name-like field is available.
- Strengthened point rendering with a slightly larger point marker and label offset styling for easier inspection.
- Added a brighter white border around the preview map frame.
- Added a mild darkening filter so the road basemap reads as dark gray instead of a bright cream tone while still staying lighter than the earlier near-black map style.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The previous map revision improved point visibility, but it still lacked readable labels and did not frame the map strongly enough against the surrounding dark UI.
- The revised styling keeps the map readable while making it feel more intentional and visually integrated with the Streamlit app.

## 2026-03-19 06:30:00 +04:00

### Streamlit Dense-Point Label Cleanup

- Updated `streamlit_app.py` so dense point datasets no longer render permanent label boxes for every feature.
- Small point sets can still show direct labels, but larger point sets now use hover tooltips instead.
- Kept the stronger point markers, gray-toned map appearance, and white-framed map container from the previous styling pass.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- Rendering direct labels for every point works for sparse datasets but quickly becomes unreadable for denser place layers.
- Switching large point sets to hover-based labels preserves readability while still allowing users to inspect feature names.

## 2026-03-19 06:40:00 +04:00

### Streamlit Click-Selection Map Details

- Updated `streamlit_app.py` so the preview map now uses Streamlit/PyDeck selection state with `on_select="rerun"` and `selection_mode="single-object"`.
- Added a selected-feature details panel below the map that appears when the user clicks a feature.
- Kept permanent map labels only for very small point sets; denser point layers now rely on click selection instead of always-on labels or hover-only tooltips.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier tooltip-only or always-labeled point behavior was not a good fit for dense point layers.
- Click-based selection gives the user a clearer inspection workflow without turning the map into a wall of label boxes.

## 2026-03-19 06:50:00 +04:00

### Streamlit Point Label Control and Clearer Selection Panel

- Added a sidebar `Point labels` control with `On`, `Auto`, and `Off` modes.
- Made the selected-feature section permanently visible below the map so users can immediately see where clicked-point details should appear.
- Relaxed the selection-state parsing logic so click results from the PyDeck/Streamlit event object are handled more defensively.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier point-label threshold was too opaque for users who wanted direct control over labels.
- The selection-details panel also needed a more obvious persistent location so map clicks feel connected to a visible result area.

## 2026-03-19 07:40:00 +04:00

### Streamlit Preview Switched to Folium/Leaflet Interaction

- Reworked the main Streamlit preview map in `streamlit_app.py` to use Folium/Leaflet interaction for inspection instead of the earlier PyDeck click-selection path.
- Point features now render as clickable `CircleMarker` objects with real popups that show feature attributes.
- Point labels now use Leaflet permanent tooltips when enabled, which makes them much more reliable than the earlier WebGL text-layer approach.
- Kept geometry styling inference and preview legends, but moved the actual interaction model closer to the TIG sandbox behavior that felt more natural during testing.
- Added `streamlit-folium` to `requirements.txt` and `pyproject.toml` as a direct runtime dependency.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

## 2026-03-19 13:10:00 +04:00

### Core GeoAI / GIS-Integration Improvement Track Added to the Roadmap

- Updated `docs/checklist.md` and `plan_of_action.md` to add a broader improvement track focused on core-library growth rather than Streamlit-specific work.
- The agreed roadmap additions cover:
  - spatial indexing
  - bounded parallel validation
  - caching of repeat validation runs
  - real-time progress and runtime feedback
  - stronger thermal telemetry and adaptive workload handling
  - broader GIS format-support planning
  - custom validator and repair-rule registration
  - configuration-driven validation profiles
  - PyQGIS-first integration work
  - exploratory ArcGIS integration planning
- Updated `docs/CHANGELOG.md` to reflect the new roadmap direction.

### Why this change was made

- The requested improvement set is directionally strong, but too broad to treat as a flat implementation promise.
- Capturing it as a structured roadmap keeps the project aligned with that ambition while preserving realistic sequencing, dependency boundaries, and deterministic-geometry guardrails.
- This also makes it explicit that most of the requested work is core-library and ecosystem work, not merely UI work.

## 2026-03-19 13:25:00 +04:00

### GeoQA-Specific Security Notes Added

- Added `docs/security.md` as a GeoQA-specific security and hardening reference.
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/checklist.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`
- The new security document focuses on the risks most relevant to GeoQA today, including:
  - local file-path handling
  - malformed geospatial files
  - oversized and pathological datasets
  - serialization safety
  - logging/report privacy
  - dependency health

### Why this change was made

- The earlier security notes were directionally good but too generic for the current GeoQA project shape.
- GeoQA is still primarily a local library and local app, so the most important concerns right now are safe parsing, bounded execution, and careful file/report handling rather than generic enterprise web-app controls.
- Capturing that explicitly reduces ambiguity and gives future hardening work a clearer target.

### Why this change was made

- The earlier PyDeck-based point interaction remained too fragile for practical inspection: clicking was difficult, labels were inconsistent, and the UX did not match the TIG sandbox behavior the user expected.
- Folium/Leaflet is a better fit here because the task is interactive inspection rather than high-volume WebGL rendering.
- Repaired the `streamlit-folium` package installation after discovering the environment only had a partial namespace package without the importable Python module.
- Updated `streamlit_app.py` so the Folium preview uses `use_container_width=True` instead of the incompatible `width="stretch"` argument expected by native Streamlit widgets.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`
- Fixed a bug in the Folium preview-map bounds logic where assignment expressions inside the conditional could leave `min_lon` undefined for polygon layers.
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

## 2026-03-19 13:40:00 +04:00

### Folium Bounds Hardening

- Updated `streamlit_app.py` again to simplify the Folium fit-bounds path:
  - the preview map now builds one explicit `bounds` object from `min_x`, `min_y`, `max_x`, and `max_y`
  - `fit_bounds(...)` now uses that object directly instead of relying on separate intermediate variables
- Re-ran:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The earlier fix addressed the visible failure mode, but the bounds block was still more fragile than it needed to be.
- Converting it to a single explicit object removes the possibility of branch-dependent local-state errors in that part of the preview renderer.

## 2026-03-19 14:05:00 +04:00

### First Core Validation-Runtime Slice Implemented

- Added `geoqa/validation_runtime.py`.
- Implemented:
  - custom validator registration
  - named validation profiles
  - progress callback events
  - conservative in-memory cache hooks
- Wired the runtime into:
  - `geoqa/interactive_validation.py`
  - `geoqa/interactive/validation.py`
  - `geoqa/__init__.py`
- Added tests in:
  - `tests/test_validation_runtime.py`

### Verification

- Ran:
  - `python -m unittest tests.test_validation_runtime`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK`

### Why this change was made

- The roadmap criticism was fair: too much of the requested improvement work existed only as direction and not as shipped code.
- This slice turns the first part of that roadmap into real library behavior without overreaching into half-designed parallelism, GIS plugin work, or unsafe caching semantics.
- It also creates a cleaner place to add later work such as spatial indexing, bounded parallel execution, and richer cache backends.

## 2026-03-19 14:30:00 +04:00

### Performance Slice Extended with Spatial Indexing and Bounded Parallel Execution

- Extended `geoqa/validation_runtime.py` to support bounded parallel validator execution through `max_workers`.
- Updated `geoqa/interactive_validation.py` so `validate_layer(...)` and `validate_dataset(...)` can pass `max_workers` through to the runtime layer.
- Updated `geoqa/validations/topology.py` to use spatial-index-aware candidate selection when a layer exposes a usable spatial index.
- Kept safe fallback behavior:
  - no spatial index -> existing pairwise/reference scan still works
  - `max_workers` omitted or `<= 1` -> existing serial behavior still works
- Added and expanded tests in:
  - `tests/test_validation_runtime.py`
  - `tests/test_additional_validations.py`

### Verification

- Ran:
  - `python -m unittest tests.test_validation_runtime tests.test_additional_validations`
  - `python -m py_compile geoqa\\validation_runtime.py geoqa\\validations\\topology.py geoqa\\interactive_validation.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
  - inline smoke script for:
    - custom validator registration
    - validation profile execution
    - progress callbacks
    - cache use
- Result:
  - `OK`

### Why this change was made

- The next most justified roadmap step after the first runtime slice was performance, not more UI work.
- Topology/reference comparisons were still brute-force even when the underlying layer backend could expose a spatial index.
- The runtime also still executed all validators serially, which limited its usefulness on broader validation plans.
- This change keeps the behavior opt-in and bounded rather than pretending the entire roadmap is finished.

## 2026-03-19 14:50:00 +04:00

### Runtime Hardening Slice Added

- Extended `geoqa/validation_runtime.py` with:
  - `FileValidationCache`
  - `ValidationLimits`
- Added preflight dataset checks for:
  - feature count
  - column count
  - source file size when `attrs["source_path"]` is available
- Updated `geoqa/interactive_validation.py` so the interactive/core validation entry points can pass:
  - persistent cache backends
  - validation limits
- Updated `geoqa/interactive/validation.py` and `geoqa/__init__.py` exports.
- Updated `geoqa/interactive_validation.py` to attach `source_path` into layer attributes when datasets are loaded from filesystem paths, so file-size guardrails can work in normal dataset runs.
- Added regression tests in `tests/test_validation_runtime.py` for:
  - file-backed cache reuse
  - feature-limit failure
  - source-file-size failure

### Verification

- Ran:
  - `python -m py_compile geoqa\\validation_runtime.py geoqa\\interactive_validation.py geoqa\\interactive\\validation.py geoqa\\__init__.py tests\\test_validation_runtime.py`
  - `python -m unittest tests.test_validation_runtime`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - `OK`

### Why this change was made

- The previous runtime slice already had useful extensibility, but repeated runs still required redoing work across processes and there were still no hard preflight bounds for oversized datasets.
- Adding a file-backed cache turns part of the roadmap into actual reusable code instead of leaving caching as a concept only.
- Adding explicit validation limits aligns GeoQA with the bounded-execution and safe-parsing direction already documented in `docs/security.md`.

## 2026-03-19 15:05:00 +04:00

### Test Ledger Sync for New Runtime Slices

- Updated `docs/tests.md` to reflect the current verification baseline:
  - run date advanced to `2026-03-19`
  - latest suite count recorded as `96`
  - added a dedicated `Validation Runtime Tests` section
  - added catalog-validation coverage
- Updated `docs/local_data_tests.md` to clarify that the recorded local/internal runs are still valid, but they predate the newest runtime slices and therefore do not yet exercise:
  - custom validator registration
  - validation profiles
  - bounded parallel validator execution
  - file-backed cache reuse
  - preflight validation limits
- Added a suggested next local rerun path so the local-data ledger can later confirm the new runtime features explicitly.

### Why this change was made

- The code had advanced beyond what the testing ledgers were saying.
- Before asking for manual testing, the public and local test records needed to distinguish between:
  - what has already been verified in automated/runtime tests
  - what remains to be re-run on local operational datasets
- This keeps the docs honest and reduces the risk of overstating what the local-data ledger currently proves.

## 2026-03-19 15:30:00 +04:00

### Fresh Public and Local Ledger Reruns Recorded

- Re-ran a lightweight public baseline CRS workflow directly against:
  - `data/public_samples/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp`
- Result:
  - `0` issues
  - output written to `data/integration_results/natural_earth_countries_crs_2026_03_19.json`
- Re-ran a local runtime-capability check directly against a private small polygon control layer.
- Used:
  - `ValidationProfile`
  - `FileValidationCache`
  - `ValidationLimits`
  - progress callback capture
- Result:
  - `49` features loaded
  - first run issue count `0`
  - second run issue count `0`
  - cache-hit events recorded on the second run
  - summary written to `data/integration_results/training_dma_runtime_crs_summary.json`
- Updated:
  - `docs/tests.md`
  - `docs/local_data_tests.md`

### Why this change was made

- The user specifically asked for the ledgers to reflect fresh real runs, not only updated interpretation.
- These reruns provide a clean current baseline for:
  - one public workflow
  - one local internal workflow
  - the new runtime slice working on real data

## 2026-03-19 20:05:00 +04:00

### Fresh Chunked Thermal Reruns on Larger Datasets

- Re-ran the large public `ne_10m_roads.shp` workflow through `run_agent_workflow(...)` using:
  - `validation_chunk_size=750`
  - `sleep_between_validation_chunks_seconds=3.0`
  - `ThermalGuard.strict(...)`
- Result:
  - chunked validation started
  - run still stopped under the strict thermal profile
  - thermal log recorded a final blocked state at `73.0 C` against a `70.0 C` hard limit
  - artifact written:
    - `data/integration_results/natural_earth_roads_chunked_thermal_2026_03_19.jsonl`

- Re-ran the large private line-network workflow through `run_agent_workflow(...)` using:
  - `validation_chunk_size=3000`
  - `sleep_between_validation_chunks_seconds=2.0`
  - `ThermalGuard.cool(...)`
- Result:
  - the rerun progressed through multiple chunk stages
  - thermal log recorded progress reaching `validation_chunk_12_pre`
  - the run did not finish within the one-hour command budget used for this pass
  - artifact written:
    - `data/integration_results/training_main_pipes_chunked_thermal_2026_03_19.jsonl`

- Updated:
  - `docs/tests.md`
  - `docs/local_data_tests.md`

### Why this change was made

- The user explicitly asked for another attempt on the larger datasets using chunking plus temperature-aware handling.
- Even though these were not clean full completions, they are important operational results:
  - they show the current chunking path is real and active
  - they show where thermal/runtime limits still dominate
  - they provide concrete evidence for the next roadmap step around adaptive chunk sizing and smarter thermal balancing

## 2026-03-19 20:25:00 +04:00

### Roadmap Status Clarification Added

- Updated the project docs to distinguish more clearly between:
  - roadmap initiatives that now have first working slices in code
  - larger features that are still not fully implemented
- Clarified that the following are only partially implemented so far:
  - spatial indexing
  - parallel validation
  - caching
  - runtime progress feedback
  - custom validation extensibility
- Clarified that the following still remain open work:
  - broader GIS format support such as DXF, LAS/LAZ, KMZ/KML expansion, FileGDB, and raster-oriented paths
  - fuller PyQGIS export/plugin integration
  - ArcGIS integration
  - archive hardening such as ZIP-bomb protection
  - stronger geometry-complexity limits
- Updated:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/checklist.md`
  - `plan_of_action.md`
  - `docs/CHANGELOG.md`

### Why this change was made

- The criticism was fair in one important sense:
  - several large roadmap items had been documented, but not yet fully delivered in code
- At the same time, the criticism was too coarse because some first runtime slices already do exist.
- The docs needed to say both things clearly:
  - GeoQA has made real progress on some runtime capabilities
  - GeoQA still does not fully implement the larger platform and integration goals yet

## 2026-03-19 21:20:00 +04:00

### Streamlit map preview verification

- Rechecked the current `streamlit_app.py` after a browser warning that referenced an older `min_lon` bounds bug.
- Confirmed the checked-in source no longer contains that stale bounds path.
- Re-verified from the GeoQA repo root:
  - `python -m py_compile streamlit_app.py`
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `OK` (`102` tests)

### Why this note was added

- The warning shown in the browser was consistent with a stale Streamlit process rather than the current repository state.
- Recording the verification makes that distinction explicit in the project history.

## 2026-03-20 17:35:00 +04:00

### Domain-pack runtime and reporting slice

- Added first-class domain packs under:
  - `geoqa/packs/water_network.py`
  - `geoqa/packs/boundaries.py`
  - `geoqa/packs/land_use.py`
- Added deterministic topology validators for:
  - `duplicate_geometry_same_layer`
  - `line_dangle`
  - `polygon_gap_same_layer`
- Extended the runtime layer so progress events now include:
  - `progress_percent`
  - `eta_seconds`
  - `chunk_index`
  - `chunk_total`
- Added bounded runtime-stop support through `max_runtime_seconds`.
- Extended report summaries with:
  - actionable vs informational split
  - actionable ratio
  - root-cause grouping
  - top-issue percentages
- Extended the CLI so:
  - `validate` supports `--max-runtime-seconds`
  - `benchmark` supports `--max-runtime-seconds`
  - `profiles show` exposes richer profile configuration detail

### Why this change was made

- The next step after the CLI and first profile system was to make GeoQA behave more like a domain-aware QA engine rather than only a validator collection.
- Water-network, boundaries, and land-use behavior needed to move into real pack modules instead of remaining implied by static profile names.
- Reports also needed to become more decision-ready so users can distinguish actionable findings from informational noise more quickly.

### Verification

- Ran:
  - `python -m py_compile geoqa\\validations\\topology.py geoqa\\problem_registry.py geoqa\\profile_registry.py geoqa\\validation_runtime.py geoqa\\interactive_validation.py geoqa\\execution.py geoqa\\reports\\report_generator.py geoqa\\cli\\commands\\validate.py geoqa\\cli\\commands\\benchmark.py geoqa\\cli\\commands\\profiles.py tests\\test_additional_validations.py tests\\test_execution.py tests\\test_report_generator.py tests\\test_cli.py`
  - `python -m unittest tests.test_additional_validations tests.test_execution tests.test_report_generator tests.test_cli`
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - `python scripts\\validate_problem_catalog.py`
- Result:
  - full suite passed: `OK` (`117` tests)
  - catalog validation passed
## 2026-03-21 Plugin pass

- Analyzed the legacy DMA correction scripts before coding:
  - same-name duplicate/nested polygons
  - cross-name duplicate/nested polygons
  - overlap subtraction logic
  - multipart dissolve logic
- Extracted the repeated helpers instead of duplicating them again:
  - DMA field detection
  - name normalization
  - light geometry repair
  - overlap fraction checks
  - dissolve-by-name behavior
- Added `geoqa.plugins` as an additive layer rather than altering validator internals.
- Hooked plugins into `validate_dataset_with_profile(...)` only after core validation completes, so the engine remains the center and plugin rules stay optional/additive.

## 2026-06-24 12 50 +04 GeoQA Atlas product layer

### What changed

- Added GeoQA Atlas under `apps/atlas` as the public WebGIS demo layer for the existing GeoQA engine.
- Added a Vite React and Leaflet interface with landing, dataset gallery, dataset workspace, issue drawer, layer toggles, report downloads, GitHub links, and static demo fallback data.
- Added a Run QA workflow preview page with GeoJSON upload preview, profile selection, and the command users would run through the GeoQA CLI.
- Added a water-network utility-line demo using `water_network_quick` with self-intersection, near-miss endpoint, unsnapped endpoint, and spatial-index issue examples.
- Added reusable frontend geometry bounds handling for selected issue focus so polygon and parcel issue zoom uses the actual feature coordinates.
- Improved Medium severity badge readability with bright yellow background, near-black text, and heavier type.
- Added root and app documentation for Atlas, including `docs/geoqa_atlas_product_brief.md` and `apps/atlas/docs/demo-data.md`.
- Kept GeoQA validation logic inside the Python engine and treated Atlas as a report and workflow presentation layer.

### Why this change was made

- The project needed a public-facing product demo that explains GeoQA quickly without replacing internals or making Streamlit the lead experience.
- Atlas gives reviewers a map-first way to understand GeoQA reports, while the CLI and Python package remain the authoritative validation surface.

## 2026-06-24 13 45 +04 GeoQA Atlas parcel focus and badge readability

### What changed

- Tightened parcel issue focus behavior so very small polygon findings zoom to the selected feature center at a higher level.
- Switched selected issue focus updates to clone the GeoJSON feature so clicking Show on map again can retrigger the map movement.
- Increased map and tile maximum zoom settings for detailed parcel review.
- Narrowed the issue detail span selector so severity badge text is not affected by muted feature-label styling.
- Forced Medium severity badge text to near-black with a bright yellow badge background.

### Why this change was made

- The parcel workspace still felt too broad after clicking Show on map for a selected polygon issue.
- The Medium badge was not readable enough in the issue drawer screenshot because surrounding muted text styles could visually dominate the label.

## 2026-06-24 14 27 +04 GeoQA Atlas six-card demo gallery

### What changed

- Verified the water-network demo provenance from the Atlas metadata and docs.
- Confirmed it is synthetic GeoQA demo data and kept the source label as `Synthetic GeoQA water network demo`.
- Added two small synthetic Atlas demo datasets.
- Added `Administrative boundaries / area polygons` with the `boundaries_quick` profile.
- Added `Flood zones / risk polygons` with the `boundaries_quick` profile.
- Added precomputed report JSON, issue overlay GeoJSON, raw layer GeoJSON, source labels, and reproducible commands for both new demos.
- Improved the dataset gallery layout so desktop shows three columns by two rows, tablet shows two columns, and mobile shows one column.
- Kept the Run QA page preview-only and clarified the backend-connected validation path.
- Updated the Atlas product brief, app demo data docs, README Atlas note, and changelog.
- Confirmed `AGENTS.md` already contains the GeoQA Atlas rules.
- Verified the Atlas app with `npm run build`.
- Verified the lightweight Python public API suite with `python -m unittest tests.test_public_api`.

### Why this change was made

- The gallery needed to feel complete and more marketable.
- Demo provenance needed to stay honest, especially for the synthetic water-network sample.
- Atlas should stay visually compelling without moving validation logic out of GeoQA.
