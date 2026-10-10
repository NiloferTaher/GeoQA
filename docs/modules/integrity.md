# `integrity`

## Conditions emitted

### `missing_or_stale_spatial_index`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A feature class lacks an effective spatial index or its index is stale after heavy edits, degrading spatial query performance. Diagnose with index validation/rebuild tools and recalculate the spatial index when query performance drops.

**Repair.** Rebuild or recreate the spatial index after bulk edits or loads.

### `non_rfc7946_geojson_output`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

GeoJSON written outside RFC 7946 expectations can carry incompatible CRS assumptions, polygon winding, or antimeridian handling. Diagnose by validating export options and rewrite with RFC7946-compliant settings when interchange requires it.

**Repair.** Rewrite the file with RFC 7946-compliant export settings in GDAL, QGIS, or another writer.

### `outdated_attribute_or_spatial_indexes`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Attribute or spatial indexes become inefficient after large update, delete, or compress operations. Diagnose with database administration tools and rebuild indexes to restore query efficiency.

**Repair.** Rebuild attribute and spatial indexes as part of post-edit geodatabase maintenance.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
