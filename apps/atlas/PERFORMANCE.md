# GeoQA Atlas Performance Rules

GeoQA Atlas must remain idle safe. Opening the app, landing page, gallery, or Run QA page must not perform heavy geospatial parsing, validation, polling, or map rendering. Heavy work must be user triggered and bounded.

## Required Rules

1. Atlas landing and gallery routes must load metadata only.
2. Do not import or parse full GeoJSON or report files on startup.
3. Dataset GeoJSON, report, and issue files must be lazy loaded by the selected route.
4. Run QA must do nothing heavy until the user uploads or selects a layer.
5. Map components must be lazy loaded and mounted only when visible.
6. Backend and thermal polling must be opt in, slow, and cleaned up on unmount.
7. Do not add CSS blur, glow, or animation to many map features.
8. Do not remount Leaflet maps on unrelated state changes.
9. Toggling layers should change visibility, not refetch or reparse data.
10. Any future feature touching maps, uploads, or reports must include a performance note in `journal.md` and `docs/CHANGELOG.md`.

## Current Idle Safe Shape

- The app shell route loads page chunks lazily.
- Landing and gallery call dataset metadata only.
- Dataset workspace fetches only the selected dataset raw layer, report, and issue overlay.
- Cleaned layer GeoJSON waits until the cleaned layer toggle is requested.
- Run QA does not import `shpjs`, parse uploads, call preview endpoints, or call validation endpoints until a user selects a file.
- Leaflet CSS and React Leaflet code live with the lazy loaded map component rather than the app entry.
- CPU temperature UI and polling stay disabled in public and default mode unless `VITE_ATLAS_SHOW_THERMAL=true` is set.

## Regression Check

Run the idle safety checks from `apps/atlas`.

```powershell
npm test --if-present
```

The test command includes `scripts/check-idle-safety.mjs`, which checks for common eager import and startup fetch regressions.
