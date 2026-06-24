# Demo Data

GeoQA Atlas v1 uses curated public preview data and one synthetic water-network sample.
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

- Places or facilities points
  - Natural Earth populated places.
  - The compact point sample is included for point-layer review.

## Report Generation

The demo report files follow GeoQA report shapes and use the commands shown in each workspace.

Example command.

```text
geoqa validate public-samples/roads-line-network.geojson --profile generic_quick --output-format json --report-path reports/roads-line-network
```

## Public Demo Limits

- Static reports only in v1.
- No Streamlit.
- No ElasticSearch.
- No GeoQA internals rewritten for the app.
- The Run QA page is an upload workflow preview until connected to the GeoQA Python backend.
