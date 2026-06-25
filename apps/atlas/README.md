# GeoQA Atlas

GeoQA Atlas is the public WebGIS demo layer for GeoQA.
It presents precomputed GeoQA reports through a polished dark interface with a landing page, dataset gallery, map workspace, issue drawer, report download, and Run QA workflow preview.

Atlas is not the validation engine.
The GeoQA Python package and CLI remain responsible for validation logic, profiles, report generation, and conservative fixes.

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
It includes roads, zoning polygons, administrative boundaries, flood risk polygons, water utility lines, and places samples.
Reports and issue overlays are precomputed JSON files shaped like GeoQA outputs.
The administrative-boundary demo uses a compact Natural Earth Admin 1 states and provinces preview.
The flood-zone demo uses a compact Philadelphia FEMA flood plain 2023 preview.
The water-network demo is a synthetic GeoQA sample made to show utility-network QA behavior without claiming public source provenance.
Cleaned previews appear only when a real cleaned layer file exists.
Runtime errors are operational findings in Atlas, not normal defect overlays.

## Backend Note

The Run QA page previews the upload workflow and can display a local GeoJSON layer in the browser.
Full validation requires a backend service that calls the GeoQA Python package.
Atlas preview supports GeoJSON and zipped Shapefile where browser parsing is available.
Large zipped Shapefile archives can use the local Atlas backend preview endpoint when the desktop app or FastAPI API is running.
Full GeoQA validation through the Python backend can support additional GeoPandas-readable formats such as Shapefile, GeoPackage, CSV, GeoJSON, and GeoParquet.

## Root Project

See the root [README](../../README.md) for the GeoQA engine, CLI, Python API, and contributor guidance.
