# GeoQA Checklist

This file tracks practical project status.

Use:
- `plan_of_action.md` for direction
- `docs/checklist.md` for what is done vs next
- `docs/tests.md` for verification evidence
- `journal.md` for implementation history
- `docs/future/` for future-only architecture and staged execution notes

## Done

- Core validation engine established
- Validation families implemented for:
  - geometry
  - topology
  - attributes
  - CRS
  - metadata
  - accuracy
  - integrity
- Shared `ValidationIssue` model implemented
- JSON and CSV report generation implemented
- CLI surface implemented for:
  - `validate`
  - `profiles`
  - `convert`
  - `report`
  - `benchmark`
- Runtime layer implemented with:
  - validation profiles
  - custom validator registration
  - progress callbacks
  - in-memory cache
  - file-backed cache
  - validation limits
  - bounded parallel execution
  - runtime budgets
  - low-resource mode
  - structured partial-run results
- Signal calibration implemented with:
  - confidence
  - actionable
  - priority score
  - profile downgrades
  - profile suppressions
- Domain packs implemented for:
  - water network
  - boundaries
  - land use
- Water-network pack strengthened with:
  - quick / strict / audit profiles
  - schema detection
  - centralized thresholds
  - connectivity-oriented checks
  - operator rollups
- Cost-aware validator ordering for constrained runs
- CRS-aware / scale-aware precision tuning
- Benchmark story documented from real recorded runs
- Solo operator guide added
- Public and private anonymized test ledgers maintained

## Next

- Improve throughput on the heaviest public and private line/polygon runs
- Add CI quality gates
- Tune remaining noisy validators beyond the first CRS/scale-aware precision pass
- Add stronger geometry-complexity guards
- Add hostile-input regression tests
- Improve cache invalidation strategy
- Add an explicit `run_plugins_on_partial` runtime option for best-effort domain validation on budget-/thermal-limited runs
  - only for runtime/thermal/budget stops
  - not for invalid-input or hard-limit failures
  - must be reported clearly as best-effort plugin coverage

## Partial But Real

- spatial indexing
  - first meaningful slices exist
  - broader validator coverage still needed
- parallel processing
  - bounded runtime support exists
  - not every validation family is parallelized
- adaptive runtime
  - real and useful
  - still not enough to guarantee every heavy run completes on this workstation
- throughput engineering
  - low-resource ordering and indexing are better
  - the heaviest runs are still throughput-bound on this workstation
- domain packs
  - real first slices
  - not yet full industry-grade semantics
- reporting
  - strong operator summaries now exist
  - richer standards/export surfaces still remain
- plugin execution on partial runs
  - current behavior is conservative: plugins run after clean core completion
  - later option should allow explicit best-effort plugin execution on partial runtime stops

## Still Missing

- broader format support for DXF, KMZ/KML expansion, LAS/LAZ, FileGDB, and raster-oriented paths
- QGIS plugin packaging
- ArcGIS integration
- archive-bomb protection
- fuller contributor performance benchmarking workflow

## Notes

- GeoQA should remain CLI-first.
- Streamlit is secondary.
- Local/private dataset names stay out of public-facing docs.
- The project should get better before it gets broader.
- Future-only design notes should live under `docs/future/`, not beside shipped operator docs.
