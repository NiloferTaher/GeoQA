# Benchmark Story

GeoQA is a deterministic geospatial QA engine. This benchmark story is not a performance marketing page. It is a compact, public record of what the engine has actually been run against inside this repository and what those runs honestly show.

## Why GeoQA Exists

GeoQA exists because ad hoc desktop GIS QA on a weak workstation is expensive in the worst way:
- long validations freeze or heat the machine
- reruns waste time because the operator cannot tell what completed
- issue review becomes manual and inconsistent
- downstream GIS or GeoAI work starts without a trustworthy QA record

GeoQA tries to improve that by being:
- deterministic
- reportable
- restart-friendly
- explicit about partial execution

Typical desktop GIS workflow:
- long run freezes
- no partial insight
- rerun from scratch

GeoQA:
- bounded runtime
- partial results preserved
- actionable findings surfaced early

## What GeoQA Is

GeoQA prepares geospatial datasets for AI by detecting, explaining, and fixing data quality issues.

More precisely: GeoQA validates, audits, and prepares geospatial datasets for reliable GIS and GeoAI workflows using deterministic rules. It is not a GIS editor, not an LLM geometry engine, and not a benchmark suite built around synthetic perfection claims.

## Benchmark Setup

Recorded public benchmark runs used the repository's real public sample data and the same runtime controls documented elsewhere in the project:

- Date window: `2026-03-18` to `2026-03-20`
- Python: `3.12.10`
- `geopandas`: `1.1.3`
- `shapely`: `2.1.2`
- `pyproj`: `3.7.2`
- Machine note: heat-sensitive workstation using GeoQA thermal guards during heavier runs

Runs came from:

- `scripts/run_integration_samples.py`
- direct `run_agent_workflow(...)` executions
- direct CRS automation checks
- CLI smoke runs such as `python -m geoqa benchmark ...`

Artifacts are stored under:

- `data/integration_results/`

## Dataset Table

| Dataset | Workflow | Status | Issues Found | Notes |
| --- | --- | --- | ---: | --- |
| Natural Earth countries | generic validation | successful | `178` | Completed end to end with structured reports |
| Natural Earth countries | CRS validation | successful | `0` | Null result; dataset passed the targeted CRS check |
| Natural Earth admin-1 states/provinces | generic validation | successful | `4598` | Larger polygon layer completed without thermal interruption |
| Natural Earth admin-1 GeoPackage | CRS validation | successful | `0` | Confirms non-shapefile CRS path works |
| Natural Earth lakes | generic validation | successful | `1375` | Completed with guarded cooldown after a hotter run |
| Natural Earth roads | generic validation | partially successful | `56602` | Thermal interruption captured as structured output |
| Natural Earth roads | strict chunked rerun | partially successful | n/a | Chunking started, but strict thermal guard still prevented full completion |
| Natural Earth roads | low-resource CLI benchmark | successful | `49` | Completed on the same workstation in low-resource mode within a bounded runtime window |
| Philadelphia FEMA flood plain 2023 | flood-zone validation | successful | `1` | Real city open-data GeoJSON completed cleanly |
| Philadelphia zoning base districts | land-use validation | partially successful | `1` | Thermal interruption converted into a structured runtime issue |

## Key Findings

1. GeoQA handles real public vector data, not only toy fixtures.

2. Clean targeted checks are possible.

   The CRS validation runs on Natural Earth countries and the derived admin-1 GeoPackage both returned `0` issues and still produced useful reports.

3. Larger datasets expose both data signal and runtime stress.

   The admin-1 and lakes runs completed and surfaced large issue counts. The roads and zoning runs showed that thermal pressure is still the main limiting factor on this workstation.

4. Low-resource mode is not just a flag. It now has one real heavier public success case.

   A low-resource CLI benchmark against the Natural Earth roads layer completed on the maintainer workstation in about `122` seconds and surfaced `49` high-value findings instead of trying to force the fullest signal path.

5. The newer adaptive chunking work is helping, but it is not the end of the story.

   Fresh adaptive reruns on the heaviest public road and zoning samples no longer showed thermal-limit trips in the recorded logs, but they still did not finish inside a one-hour execution window. That is meaningful progress, because it shifts the dominant problem from immediate heat failure to total runtime cost.

6. Partial success is explicit, not hidden.

   When thermal guards trip, GeoQA records the event as structured output instead of silently crashing or pretending validation completed.

7. Low-resource operation is now part of the real operator story.

   GeoQA now exposes an explicit low-resource CLI mode so constrained machines can favor conservative execution and honest partial results instead of brittle full-run assumptions.

## Example Issue Types

Observed on the recorded public runs:

- coordinate-precision-style findings on boundary layers
- flood-zone data issues on city open data
- structured thermal/runtime issues on heavier land-use and road layers

These examples matter because they show both sides of the engine:

- data findings
- operational/runtime findings

GeoQA needs both to be credible on real workloads.

## What GeoQA Does Better Than Ad Hoc Desktop Workflows

- structured issue output instead of transient UI messages
- explicit partial-run handling
- CLI repeatability
- cache reuse
- domain-aware profiles
- actionable vs informational separation
- operator-facing next-step hints

## Honest Limitations

These runs also show what is not finished yet:

- thermal limits can still stop large validations on this workstation
- chunking helps, and the newer adaptive path appears to improve thermal stability, but the heaviest datasets are still not completing quickly enough on this workstation
- issue-count magnitude still needs continued calibration for noisy validators
- successful completion on a workstation should not be confused with cloud-scale throughput

This is why GeoQA now emphasizes:

- adaptive runtime behavior
- calibrated profiles
- actionable vs informational reporting
- low-resource execution for constrained hardware

## Headline Benchmark

If you only remember one public result from this repository, it should be this one:

- dataset: Natural Earth roads
- size: `56,600` features
- command path: `python -m geoqa benchmark ... --profile generic_quick --low-resource --max-runtime-seconds 180`
- result: full completion
- findings: `49`

That is the clearest current proof that GeoQA is not only a validator library. It is also a constrained-hardware operator tool that can finish a meaningful public workload without pretending the machine is stronger than it is.

## Why It Matters

A skeptical GIS engineer should be able to look at these results and conclude:

- the engine is real
- the tests are real
- the failures are documented honestly
- the reports are structured enough to use downstream

That is more valuable than a polished benchmark chart with invented perfection.

## Reproducibility Commands

Examples you can run from the repo root:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python scripts/validate_problem_catalog.py
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag benchmark_demo --progress --report-path data/integration_results/benchmark_low_resource_demo
python scripts/run_integration_samples.py --profile natural_earth_countries_crs --output data/integration_results/integration_summary_metrics.json
python scripts/run_integration_samples.py --profile natural_earth_admin1_gpkg_crs --profile natural_earth_lakes_generic --profile natural_earth_admin1_generic --output data/integration_results/integration_summary_expanded_safe.json
python scripts/run_integration_samples.py --profile natural_earth_roads_generic --output data/integration_results/integration_summary_roads.json
python -m geoqa benchmark data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry
```

For the detailed ledger behind these summaries, see:

- [tests.md](/g:/My%20Drive/Python-G-drive/GeoQA/docs/tests.md)
