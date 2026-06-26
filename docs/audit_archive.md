# GeoQA Archive Audit

GeoQA can run a local audit over a ZIP, folder, Shapefile, GeoJSON, or GeoPackage and write JSON, Excel, text, and PDF review outputs.

## Command

```bash
geoqa audit-archive path/to/archive_or_folder --out reports --profiles auto --all-layers --excel --json
```

Useful options include:

- `--selected-layer layer/path` to validate one layer from a multi-layer archive.
- `--all-layers` to validate every detected layer.
- `--expected-crs EPSG:32640` to enforce an authoritative CRS.
- `--expected-crs-config expected_crs.yaml` to read a simple expected CRS config.
- `--sanitize` and `--no-coordinates` for shareable review outputs.
- `--public-demo-mode` for public demo reporting.
- `--write-fix-plan` to include a human review fix plan note.

Default mode is audit only. GeoQA does not modify source data. Safe fixes are reserved for an explicit future workflow and must write to a separate output copy.

## Multi-layer ZIPs

GeoQA detects actual `.shp` files as layers, not sidecar files. The layer inventory records the layer path, layer name, feature count, geometry type, source CRS, bounding box, fields, recommended profile, and recommendation reason.

When one layer is selected, reports say that only the selected layer was validated. When all-layer mode is used, reports say how many layers were validated.

## Geometry-aware validators

Validators are guarded by geometry type. Line and network validators run only on line layers. Polygon topology validators run only on polygon layers. Point layers can still run null geometry, CRS, duplicate point location, coordinate precision, attribute, uniqueness, domain, and point asset checks.

Skipped validators are reported in the Validator Coverage sheet with:

- `validator_name`
- `status`
- `reason`
- `layer_geometry_type`
- `expected_geometry_types`
- `profile`

## CRS policy

GeoQA no longer assumes uploaded source data must be EPSG:4326.

- Missing CRS is reported as missing spatial reference.
- Unreadable CRS is reported as invalid spatial reference.
- Valid projected or local CRS is not invalid by default.
- If `--expected-crs` is configured, GeoQA compares the source CRS to that expected CRS.
- Web maps may use a temporary EPSG:4326 preview copy, but source data CRS is not changed.

## Public demo

See `examples/public_demo/` for synthetic data and a generated client-facing workbook named `GeoQA_Public_Demo_Report.xlsx`.
