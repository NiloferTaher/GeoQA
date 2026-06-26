# Demo Data

GeoQA Atlas v1 uses curated public preview data for domain-specific demos.
All reports are precomputed JSON files for a read-only public demo.
Third-party demo datasets retain their original source licenses and attribution requirements.
The Apache-2.0 project license applies to GeoQA code and project-authored docs, not to third-party public data sources.

## Sources

- Roads / line network
  - Natural Earth roads.
  - The app uses a regional line preview so the browser stays responsive.

- Parcels or zoning polygons
  - City of Philadelphia zoning data from OpenDataPhilly.
  - The app uses a bounded polygon preview for fast map rendering.

- OSM water / drainage lines
  - OpenStreetMap-derived Muscat waterway lines from the HOTOSM HDX Oman waterways export.
  - Source organization is OpenStreetMap contributors via HOTOSM HDX.
  - License is Open Database License ODbL 1.0.
  - Atlas uses a compact sixty-feature LineString sample near Muscat.
  - It demonstrates disconnected endpoints, near-miss endpoints, short segments, and delivery readiness.
  - Near-miss endpoint findings include endpoint A, endpoint B, related feature id, gap distance, tolerance, and a short gap geometry.
  - The water report now uses meter-based endpoint distances for geographic CRS data.
  - Repeated endpoint pair findings are grouped so A-B and B-A are not counted as separate near-miss findings.
  - This is not official utility mains data and Atlas does not label it that way.
  - Source research is recorded in `apps/atlas/docs/water-network-source-research.md`.

- Administrative boundaries / area polygons
  - Natural Earth Admin 1 states and provinces sample.
  - Atlas uses a compact four-feature preview around Pennsylvania, New Jersey, Delaware, and Maryland.
  - It demonstrates boundary QA, CRS metadata review, spatial-index review, and precision readiness.

- Flood zones / risk polygons
  - Philadelphia FEMA flood plain 2023 sample from the public data fixture already in this repo.
  - Atlas uses four simplified risk-zone polygons so the browser map remains responsive.
  - It demonstrates risk-zone QA, CRS metadata review, spatial-index review, and planning-data readiness.

- Places or facilities points
  - Natural Earth populated places.
  - The compact point sample is included for point-layer review.

## Report Generation

The demo report files follow GeoQA report shapes and use the commands shown in each workspace.

Example command.

```text
geoqa validate public-samples/roads-line-network.geojson --profile generic_quick --output-format json --report-path reports/roads-line-network
```

Cleaned preview layers are shown only when a meaningful visible cleaned geometry output exists.
Coordinate precision, spatial index, CRS, metadata, and operational findings do not produce visible cleaned geometry previews.
The current roads and zoning cleaned files differ at a coordinate level but do not demonstrate a visible geometry fix for their displayed issue types, so Atlas disables the cleaned toggle for those demos.
All demos currently show a disabled cleaned layer toggle unless a future dataset adds a meaningful cleaned output.
Runtime errors are shown as operational findings in the drawer and are not drawn as normal defect geometries.

## Public Demo Limits

- Static reports only in v1.
- No Streamlit.
- No ElasticSearch.
- No GeoQA internals rewritten for the app.
- The Run QA page is an upload workflow preview until connected to the GeoQA Python backend.
- Atlas preview supports GeoJSON and zipped Shapefile where browser parsing is available.
- Full GeoQA validation through the Python backend can support additional GeoPandas-readable formats such as Shapefile, GeoPackage, CSV, GeoJSON, and GeoParquet.
