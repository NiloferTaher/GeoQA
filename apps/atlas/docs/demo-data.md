# Demo Data

GeoQA Atlas v1 uses curated public preview data and one synthetic GeoQA sample for domain-specific demos.
All reports are precomputed JSON files for a read-only public demo.

## Sources

- Roads / line network
  - Natural Earth roads.
  - The app uses a regional line preview so the browser stays responsive.

- Parcels or zoning polygons
  - City of Philadelphia zoning data from OpenDataPhilly.
  - The app uses a bounded polygon preview for fast map rendering.

- Water network / utility lines
  - Synthetic utility-line sample made for GeoQA Atlas.
  - It demonstrates self-intersections, near-miss endpoints, unsnapped endpoints, and spatial-index review.

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

Cleaned preview layers are available only when a static cleaned GeoJSON file exists.
The roads and zoning demos include cleaned previews for supported geometry fixes.
The other demos show a disabled cleaned layer toggle with the message `No cleaned layer is available for this demo.`
Runtime errors are shown as operational findings in the drawer and are not drawn as normal defect geometries.

## Public Demo Limits

- Static reports only in v1.
- No Streamlit.
- No ElasticSearch.
- No GeoQA internals rewritten for the app.
- The Run QA page is an upload workflow preview until connected to the GeoQA Python backend.
- Atlas preview supports GeoJSON and zipped Shapefile where browser parsing is available.
- Full GeoQA validation through the Python backend can support additional GeoPandas-readable formats such as Shapefile, GeoPackage, CSV, GeoJSON, and GeoParquet.
