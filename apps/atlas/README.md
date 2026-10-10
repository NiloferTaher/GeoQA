# GeoQA Atlas

GeoQA Atlas is the public WebGIS demo layer for GeoQA.
It presents precomputed GeoQA reports through a polished dark interface with a landing page, dataset gallery, map workspace, issue drawer, report download, and Run QA workflow preview.

Atlas is not the validation engine.
The GeoQA Python package and CLI remain responsible for validation logic, profiles, report generation, and conservative fixes.

### Visual overview

See the root README and [../../docs/assets/GeoQA_Atlas_preview.pdf](../../docs/assets/GeoQA_Atlas_preview.pdf) for screenshots and a walkthrough of Atlas features.

## Run Locally

```powershell
cd apps/atlas
npm install
npm run dev
```

Build the production bundle.

```powershell
npm run build
```

Preview the built app.

```powershell
npm run preview
```

## Static Demo Data

The v1 app uses static demo data in `public/demo-data`.
It includes roads, zoning polygons, administrative boundaries, flood risk polygons, OSM water and drainage lines, and places samples.
Reports and issue overlays are precomputed JSON files shaped like GeoQA outputs.
The administrative-boundary demo uses a compact Natural Earth Admin 1 states and provinces preview.
The flood-zone demo uses a compact Philadelphia FEMA flood plain 2023 preview.
The water-network demo now uses an OSM-derived HOTOSM HDX Oman waterways sample near Muscat and is labeled as public water and drainage line data rather than official utility mains.
Third-party demo datasets retain their original source licenses and attribution requirements.
See `docs/demo-data.md` for source-specific provenance.
Cleaned previews appear only when a meaningful visible cleaned geometry output exists.
Coordinate precision, spatial index, CRS, metadata, and operational findings do not imply a visible cleaned shape.
Runtime errors are operational findings in Atlas, not normal defect overlays.
Curated dataset pages render the full static demo layer and full precomputed issue overlay.
Run QA sampling never applies to these dataset workspaces.
GeoQA issue and selected feature overlays render above basemap labels so points stay visible.
Water-network near-miss endpoint findings draw endpoint markers and a short gap connector instead of highlighting the full source line.
Show on map focuses the endpoint gap when endpoint metadata is available.
The water source search and ODbL provenance are recorded in `docs/water-network-source-research.md`.

## Idle Safe Performance

Atlas is designed to be cheap at rest.
The landing page and dataset gallery load metadata only.
They do not import Leaflet, mount maps, parse demo GeoJSON, parse report JSON, or load issue overlays.
Dataset detail pages lazy load only the selected dataset raw layer, report, and issue overlay.
Cleaned GeoJSON waits until the cleaned layer toggle is available and requested.
Run QA does not parse files, scan ZIP archives, call preview endpoints, poll thermal status, or run validation until the user selects a file or starts a run.
Permanent rules for this contract live in `PERFORMANCE.md` and `AGENTS.md`.

## Backend Note

The Run QA page previews the upload workflow and can display a local GeoJSON layer in the browser.
Full validation requires a backend service that calls the GeoQA Python package.
Atlas preview supports GeoJSON and zipped Shapefile where browser parsing is available.
Large zipped Shapefile archives can use the local Atlas backend preview endpoint when the desktop app or FastAPI API is running.
Full GeoQA validation through the Python backend can support additional GeoPandas-readable formats such as Shapefile, GeoPackage, CSV, GeoJSON, and GeoParquet.

## Deploy on Vercel

GeoQA Atlas is a Vite frontend under `apps/atlas`.

Recommended Vercel settings:

- Repository `NiloferTaher/GeoQA`
- Root Directory `apps/atlas`
- Build Command `npm run build`
- Output Directory `dist`
- Install Command `npm install`

The public web demo uses sampled Run QA limits.
Full GeoQA validation should be run locally through the Python CLI/API or through a separately hosted backend.

## Public Demo Mode

Public demo mode is enabled unless `VITE_ATLAS_PUBLIC_DEMO=false` is set.
Uploaded layers keep a muted raw preview on the map, then Atlas sends only the highlighted GeoQA-analyzed subset to the validation path.
Point and MultiPoint uploads analyze up to twenty features.
LineString, MultiLineString, Polygon, MultiPolygon, mixed, and unknown uploads analyze up to five features.
The UI says how many features were loaded and how many were analyzed so sampled runs are not mistaken for full-layer validation.
Issue overlays only reflect the analyzed subset.
These public demo limits apply only to the Run QA upload page.
Curated dataset pages continue to render the full precomputed demo layers and issue overlays.
The Run QA map legend rows act as layer toggles for the raw uploaded preview, GeoQA-analyzed subset, and issue overlay.
Issue cards, top issue type rows, and issue overlay features focus the map on the issue location when spatial geometry is available.
If an issue does not include its own geometry, Atlas uses the matching analyzed feature geometry for focus.
Layer-level findings focus the analyzed layer context and show the status in the selected issue panel beside the map.
Duplicate geometry findings show a row comparison table so matching coordinates can be reviewed against source attributes before edits.
Run notes include selected layer context and practical suggestions for multi-layer ZIPs and utility layer context.
Malformed or empty coordinates are guarded before sampled validation so the public UI does not expose raw Python type errors.
Atlas uses one default readable dark CARTO basemap with a separate label layer.
Deployments can override the dark tile URLs with the `VITE_ATLAS_DARK_*` environment variables.
The legacy `VITE_ATLAS_TILE_URL`, `VITE_ATLAS_LABEL_TILE_URL`, and `VITE_ATLAS_TILE_ATTRIBUTION` settings still override the default basemap.
Labels are rendered without CSS blur and GeoQA issue overlays render above labels.
Repeated issue examples are grouped by affected feature so the drawer stays useful.
The CPU temperature card is hidden by default and is available only for local developer review when `VITE_ATLAS_SHOW_THERMAL=true` is set.

## Maintainer Links

GeoQA Atlas keeps public maintainer links in the top navigation.

```text
Datasets · Run QA · GitHub · LinkedIn
```

GitHub links to the GeoQA repository.
LinkedIn links to Nilofer Taher's public profile.
The footer stays copyright focused.

```text
Built by Nilofer Taher · © 2026 GeoQA
```

It is not fixed or sticky, so it stays below map and issue review content.

## Root Project

See the root [README](../../README.md) for the GeoQA engine, CLI, Python API, and contributor guidance.
