# GeoQA Atlas Agent Rules

GeoQA Atlas lives under `apps/atlas` as the visual demo and product layer for GeoQA.

## Source Of Truth

- GeoQA remains the deterministic Python validation engine and source of truth.
- Do not duplicate validation logic in the Atlas frontend.
- User uploaded validation must call the GeoQA Python backend, not reimplement validators in TypeScript or JavaScript.
- Atlas may use static demo data and precomputed GeoQA reports for public demos.

## Idle Safe Rule

Atlas must remain idle safe. Opening the app, landing page, gallery, or Run QA page must not perform heavy geospatial parsing, validation, polling, or map rendering. Heavy work must be user triggered and bounded.

## Performance Guardrails

- Landing and gallery routes must load metadata only.
- Do not import or parse full GeoJSON, report files, Shapefile parsers, or Leaflet maps on startup.
- Dataset detail routes may fetch only the selected dataset data.
- Cleaned geometry must load only when available and requested.
- Run QA must not parse uploads, scan ZIP files, poll backend endpoints, or call validation until the user selects a file or starts a run.
- Map components must be lazy loaded and mounted only when visible.
- Backend or thermal polling must be opt in, slow, and cleaned up.
- Do not add CSS blur, glow, pulse, or animation to many map features.
- Toggling layers should change visibility, not refetch or reparse data.

## Documentation

- Atlas changes that affect user visible behavior must update `journal.md` and `docs/CHANGELOG.md`.
- Atlas demo, report, and product positioning docs must stay aligned with `README.md`.
- Future features touching maps, uploads, or reports must include a performance note.

## Generated Files

- Do not commit generated frontend folders such as `node_modules`, build outputs, caches, or temporary bundles.
- Do not commit private ZIP files or large generated local artifacts.
