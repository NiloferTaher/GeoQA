# GeoQA Public Demo Audit

This demo uses public and synthetic data to show how GeoQA reports can be used for stakeholder-facing geospatial QA review. No private delivery data is included.

## Contents

- `source_data/point_assets.*` is a synthetic projected point asset Shapefile in EPSG:32640 with an intentional duplicate point location.
- `source_data/line_network.geojson` is a synthetic line network layer with an intentional crossing line example.
- `reports/point_assets_geoqa_report.json` is the machine-readable GeoQA report for the point layer.
- `reports/line_network.geojson_geoqa_report.json` is the machine-readable GeoQA report for the line layer.
- `reports/GeoQA_Audit_Summary.pdf` is a compact PDF summary.
- `GeoQA_Public_Demo_Report.xlsx` is the combined public demo workbook for human QA review.

## Command

```bash
geoqa audit-archive examples/public_demo/source_data --out examples/public_demo/reports --profiles auto --all-layers --excel --json --expected-crs EPSG:4326 --public-demo-mode
```

## What The Demo Shows

- Duplicate point locations on a point asset layer.
- A CRS review case where the point layer source CRS is EPSG:32640 and the configured expected CRS is EPSG:4326.
- A line-network topology example with crossing lines.
- Validator coverage showing line validators skipped for point layers where they are not applicable.

GeoQA does not modify the source data in this workflow. The Excel fix plan is a human review plan and all applied values default to `no`.
