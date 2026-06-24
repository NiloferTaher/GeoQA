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
The water-network, administrative-boundary, and flood-zone demos are synthetic GeoQA samples made to show QA behavior without claiming public source provenance.

## Backend Note

The Run QA page previews the upload workflow and can display a local GeoJSON layer in the browser.
Full validation requires a backend service that calls the GeoQA Python package.

## Root Project

See the root [README](../../README.md) for the GeoQA engine, CLI, Python API, and contributor guidance.
