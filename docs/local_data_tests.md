# GeoQA Local Data Tests

This document records integration testing performed against local, non-public datasets.

Important privacy note:
- local datasets are private test material
- dataset names, source paths, and organization-specific identifiers are intentionally omitted from this file
- only the operational findings, scale characteristics, and actions taken are recorded here

For the public baseline test ledger, see:
- `docs/tests.md`

For private-run artifacts, see:
- `data/integration_results/`

## Scope

Current local test corpus:
- four private vector layers used only for internal testing
- one large line-network layer
- one large point-asset layer
- one medium projected polygon layer
- one small polygon control layer

Current recorded run dates:
- `2026-03-18`
- `2026-03-19`
- `2026-03-20`

Why this file exists:
- local/internal datasets are valuable for realism, but they should stay separate from the public-sample baseline
- this keeps `docs/tests.md` easier to scan while preserving the private operational record

## Current Interpretation

These local runs remain valid and representative.

They confirm:
- real private shapefile loading
- large-dataset chunked agent workflows
- thermal-safe execution behavior on private data
- report generation against realistic operational schemas
- direct runtime-layer use on private data through:
  - `ValidationProfile`
  - `FileValidationCache`
  - `ValidationLimits`
  - progress callback events

They do not publish:
- private dataset names
- source locations
- organization-specific schema identifiers unless needed for a technical explanation

## Local Dataset Summary

| Private Dataset Alias | Shape / Use | Workflow | Status | Issues Found | Null Result | Issue Type | Chunking |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| `Private Dataset A` | large line network | `run_agent_workflow(..., dataset_type="water_network")` | successful | `17` | no | data issue | yes |
| `Private Dataset A` chunked thermal rerun | large line network | `run_agent_workflow(..., validation_chunk_size=3000, sleep=2.0)` | partially successful | n/a | n/a | operational issue | yes |
| `Private Dataset B` | large point asset layer | `run_agent_workflow(..., dataset_type="water_network")` | successful | `0` | yes | clean/null | yes |
| `Private Dataset C` | medium projected polygon layer | `run_agent_workflow(..., dataset_type="generic")` | successful | `244` | no | data issue | no |
| `Private Dataset D` | small polygon control layer | `run_agent_workflow(..., dataset_type="generic")` | successful | `50` | no | data issue | no |
| `Private Dataset D` runtime CRS rerun | small polygon control layer | `validate_layer(..., profile=ValidationProfile(...))` | successful | `0` | yes | clean/null | n/a |
| `Private Dataset E` | medium point asset layer | `python -m geoqa validate ... --profile generic_quick` | successful | `2` | no | data issue | n/a |
| `Private Dataset F` | very large point asset layer | `python -m geoqa validate ... --profile generic_quick` | successful | `4` | no | data issue | n/a |
| `Private Dataset G` | very large line network | `python -m geoqa validate ... --profile water_network` | partially successful | n/a | n/a | operational issue | yes |

## Inventory Notes

- `Private Dataset A`
  - `35,223` features
  - CRS: `EPSG:4326`
  - geometry: mostly `LineString`
- `Private Dataset B`
  - `60,047` features
  - CRS: projected
  - geometry: `Point`
- `Private Dataset C`
  - `558` features
  - CRS: projected
  - geometry: `Polygon` and `MultiPolygon`
- `Private Dataset D`
  - `49` features
  - CRS: `EPSG:4326`
  - geometry: `Polygon` and `MultiPolygon`
- `Private Dataset E`
  - `10,245` features
  - CRS: projected
  - geometry: `Point`
- `Private Dataset F`
  - `106,407` features
  - CRS: projected
  - geometry: `Point`
- `Private Dataset G`
  - `204,112` features
  - CRS: projected
  - geometry: mostly `LineString` with multipart line content present

## Detailed Runs

### 1. Private Dataset A

Workflow tested:
- water-network validation through `run_agent_workflow(...)`

What the script was testing:
- chunked validation on a large real line-network layer
- water-network dataset routing
- linework geometry checks under a realistic production-style schema
- report generation against a larger local shapefile

What was found:
- `17` issues were reported
- all reported issues were `self_intersection`
- the run completed without runtime or thermal messages

Was the test successful:
- yes

Why:
- the workflow completed as intended on a large private line-network layer
- chunked validation handled the workload without needing a rerun recommendation

### 2. Private Dataset B

Workflow tested:
- water-network validation through `run_agent_workflow(...)`

What the script was testing:
- chunked validation on a very large point-asset layer
- water-network routing on non-line features
- null-result handling on a large real private dataset

What was found:
- no issues were detected
- the run completed without runtime or thermal messages

Was the test successful:
- yes

Why:
- the workflow completed cleanly on a `60,047`-feature layer
- a null result is valid here because the targeted validators did not find reportable issues

### 3. Private Dataset C

Workflow tested:
- generic validation through `run_agent_workflow(...)`

What the script was testing:
- generic polygon validation against a projected private layer
- coordinate-precision behavior on engineering-style polygon data
- report generation on a mid-sized shapefile

What was found:
- `244` issues were reported
- `243` issues were `coordinate_precision_not_fit_for_use`
- `1` issue was `missing_or_stale_spatial_index`

Was the test successful:
- yes

Why:
- the workflow completed and produced stable reports against a projected polygon dataset
- the run broadened the real-world baseline beyond public samples into private engineering-style data

### 4. Private Dataset D

Workflow tested:
- generic validation through `run_agent_workflow(...)`

What the script was testing:
- generic polygon validation on a small private control layer
- comparison of projected-vs-geographic behavior across the local corpus
- stable report generation on a smaller polygon layer

What was found:
- `50` issues were reported
- `49` issues were `coordinate_precision_not_fit_for_use`
- `1` issue was `missing_or_stale_spatial_index`

Was the test successful:
- yes

Why:
- the workflow completed fully and produced clear reports
- this run gave a smaller polygon control case to compare against the larger projected polygon layer

### 5. Private Dataset D Runtime CRS Rerun

Workflow tested:
- direct core validation runtime through `validate_layer(...)`

Runtime features exercised:
- `ValidationProfile`
- `FileValidationCache`
- `ValidationLimits`
- progress callback events

What the script was testing:
- direct use of the new validation-runtime layer on a real private dataset
- profile-based narrowing to a lightweight CRS-only check
- persistent cache reuse between repeated calls
- limit enforcement on a file-backed layer
- progress-event emission in a real run

What was found:
- `49` features loaded successfully
- first run issue count: `0`
- second run issue count: `0`
- cache-hit events were recorded on the second run

Was the test successful:
- yes

Why:
- this confirms that the new runtime slice works on a real local dataset rather than only in unit tests
- the run verified profile filtering, file-backed cache reuse, and progress-event capture without requiring a heavy geometry pass

### 6. Private Dataset A Chunked Thermal Rerun

Workflow tested:
- chunked water-network validation through `run_agent_workflow(...)` with an explicit thermal profile

What the script was testing:
- whether a large private line-network layer could complete under a more conservative chunked thermal profile
- whether the per-chunk cooldown path remained usable over a long run on this workstation

What was found:
- the run progressed well into the chunk sequence
- the thermal log shows progress reaching at least:
  - `validation_chunk_12_pre`
- the run did not finish inside the one-hour command window used for this pass
- no final issue/agent report artifact was produced in this bounded rerun

Was the test successful:
- partially

Why:
- the chunked thermal strategy clearly improved survivability versus a monolithic hot run
- but the full end-to-end completion still exceeded the practical runtime budget for this specific pass
- this is useful operational evidence for the roadmap item around adaptive chunk sizing and better thermal/runtime balancing

### 7. Private Dataset E

Workflow tested:
- direct CLI validation through `python -m geoqa validate ...`

What the script was testing:
- CLI-first validation on a medium private point layer
- report generation through the production CLI path
- CRS and integrity reporting on an operational shapefile outside the repo sample corpus

What was found:
- `10,245` features loaded successfully
- `2` issues were reported
- the findings were:
  - `invalid_spatial_reference`
  - `missing_or_stale_spatial_index`

Was the test successful:
- yes

Why:
- the current CLI/runtime path handled the private point layer cleanly and produced a structured report without code changes

### 8. Private Dataset F

Workflow tested:
- direct CLI validation through `python -m geoqa validate ...`

What the script was testing:
- CLI/runtime validation on a very large private point layer
- behavior on private operational attributes with suspicious date-like values
- null-geometry detection at larger scale

What was found:
- `106,407` features loaded successfully
- `4` issues were reported
- the findings were:
  - `2` `null_geometry`
  - `1` `invalid_spatial_reference`
  - `1` `missing_or_stale_spatial_index`
- the source attributes also triggered out-of-bounds datetime parsing warnings from the underlying file reader; the run still completed and produced a report

Was the test successful:
- yes

Why:
- GeoQA completed the full CLI/runtime pass on a large private point layer and surfaced both real geometry/integrity findings and an input-quality warning worth reviewing upstream

### 9. Private Dataset G

Workflow tested:
- direct CLI validation through `python -m geoqa validate ... --profile water_network`

What the script was testing:
- the water-network domain pack on a very large private line layer
- bounded runtime behavior with chunking, thermal controls, cache reuse, and a runtime limit
- multipart-line compatibility in topology validators on real operational data

What was found:
- the first bounded run surfaced a real engine bug:
  - the `line_dangle` validator assumed direct `.coords` access and crashed on multipart line features
- that bug was fixed in the core topology validator
- after the fix, the large line-layer run no longer crashed at the same point
- the rerun still did not complete inside the bounded command window used for this pass
- the completed geometry stage before timeout surfaced substantial real findings, including:
  - `null_geometry`
  - `below_minimum_feature_length`
  - `sharp_angle_cutback`
  - `self_intersection`

Was the test successful:
- partially

Why:
- this pass proved that the water-network pack runs against real multipart linework and that the discovered crash is fixed
- however, the overall end-to-end runtime for this very large private line layer is still throughput-bound on this workstation

## Findings From Local Data Testing

### Code/Behavior Findings

1. Large private linework surfaced real self-intersection issues without requiring a thermal fallback.
- status: observed
- outcome:
  - chunked validation handled the large private line-network layer cleanly while still detecting reportable linework issues

2. Private polygon layers surfaced repeated coordinate-precision findings.
- status: observed
- outcome:
  - the generic validator is sensitive to high-precision projected coordinates in private engineering-style polygon layers

3. The new runtime slice works on private data, not only on fixtures.
- status: observed
- outcome:
  - a direct runtime rerun confirmed profile filtering, file-backed cache reuse, and progress-event capture on a private layer

### Operational Findings

1. Chunked validation is useful beyond public benchmark data.
- the private-data pass showed that chunking can handle large real internal layers cleanly even when the workflow does not end up needing a thermal rerun

2. A null private result can still be valuable.
- the large private point-asset run was a valid large-layer clean/null outcome rather than an empty or failed test

3. Fixed row-count chunking is still not enough for every large private run.
- the bounded chunked thermal rerun on the large line-network layer progressed substantially, but still did not finish within the allowed runtime budget
- this supports the move toward adaptive chunk sizing by geometry cost rather than row count alone

4. Private multipart linework exposed a real topology-validator bug.
- status: fixed
- outcome:
  - direct `.coords` access in `line_dangle` and shared endpoint extraction was not safe for multipart geometries
  - the validator now extracts endpoints safely from both single-part and multi-part line features

5. Large private point layers can complete through the CLI/runtime path.
- status: observed
- outcome:
  - two private point layers completed successfully through `python -m geoqa validate ...`
  - the larger run also surfaced a small number of null-geometry findings and a reader warning about suspect date-like attribute values

## Follow-up Rerun Suggestion

The next useful local rerun would be:
- one medium private layer through `validate_layer(...)` or `validate_dataset(...)` using:
  - `ValidationProfile`
  - `FileValidationCache`
  - `ValidationLimits`
  - optional `max_workers`
  - adaptive chunk sizing where relevant

That would extend this file from a private integration ledger into a stronger private runtime-capability confirmation ledger as well.
