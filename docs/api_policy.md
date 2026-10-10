# GeoQA API Policy

## Stable Public Surface

Prefer these imports and entry points:
- `python -m geoqa ...`
- `geoqa`
- `geoqa.interactive.validation`
- `geoqa.conversion`
- `geoqa.reports.report_generator`

Stable in current practice:
- `ValidationIssue`
- `ValidationProfile`
- `ValidationLimits`
- `InMemoryValidationCache`
- `FileValidationCache`
- `validate_dataset_with_profile(...)`
- CLI commands under `python -m geoqa ...`

## Partial / Evolving Surface

These exist and work, but may still change as runtime hardening continues:
- `geoqa.validation_runtime`
- `geoqa.profile_registry`
- `geoqa.problem_registry`
- `geoqa.execution`
- low-resource runtime defaults
- partial-run execution metadata details
- pack-specific summary blocks

## Experimental Surface

These should not be treated as stable public contracts:
- `streamlit_app.py`
- app-specific preview helpers
- ad hoc internal wrappers used only for UI composition

## Stability Note

GeoQA is stable enough for:
- CLI-first local operation
- profile-driven validation
- structured report generation

GeoQA is not yet claiming long-term frozen contracts for:
- every runtime event field
- every pack-specific summary field
- every app behavior

## Deprecation Guidance

When refactoring:
- keep stable imports working where practical
- prefer wrapper-layer compatibility over abrupt removal
- document moved or renamed entry points in `CHANGELOG.md`

## Contributor Rule

Do not add new public APIs casually.

If a new function is intended for external use, it should be:
1. exported intentionally
2. covered by tests
3. documented in `README.md` or `docs/user_guide.md`
