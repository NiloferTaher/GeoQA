# Contributing to GeoQA

## Project Focus

GeoQA is primarily a deterministic geospatial QA engine.

When contributing:
- prioritize validation correctness
- prefer runtime and reporting improvements over UI expansion
- keep spatial math deterministic

## Expected Contribution Areas

- validators
- profiles
- reporting
- CLI behavior
- runtime controls
- tests
- docs

## Before Opening a Change

Run:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python scripts/validate_problem_catalog.py
```

If you touch runtime or CLI behavior, also smoke test:

```powershell
python -m geoqa profiles list
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile geometry
```

If the change affects constrained execution, also smoke test:

```powershell
python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --max-runtime-seconds 180 --cache .geoqa_cache --cache-tag contrib_low_resource --progress --report-path data/integration_results/contrib_low_resource
```

## Validator Contributions

A new validator should include:
- clear intended dataset types
- severity rationale
- tests
- report-compatible issue outputs
- practical runtime-cost awareness on weak hardware

## Docs

If you add or materially change a public feature, update:
- `README.md`
- `docs/user_guide.md`
- `docs/tests.md` if coverage changed
- `docs/CHANGELOG.md`
- `journal.md`
