# `axis_order`

Coordinate axis order, and the swap that produces plausible wrong places.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_axis_order` | Check a coordinate table for swapped axes. |
| `validate_axis_order_postgis_sql` | SQL that checks a PostGIS geometry column for a latitude/longitude swap. |
| `validate_axis_order_sql` | SQL that finds swapped coordinates in a PostgreSQL/PostGIS table. |

## Conditions emitted

### `coordinate_axis_order_ambiguous`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

Both coordinate values are inside both legal ranges, so the axis order cannot be determined from the numbers. This is evidence, not a verdict.

**Repair.** Supply a declared expected extent, or compare against a reference layer, to make the ordering decidable.

### `coordinate_axis_order_declared_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Column names declare one axis order and the supplied CRS declaration says another. One of the two is wrong.

**Repair.** Decide which is authoritative, correct the other, and record the decision. Coordinates will be read in the wrong order until this is settled.

### `coordinate_axis_order_non_numeric`

**Severity** medium &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A coordinate column holds values that are not numbers. These rows cannot be checked and will disappear silently on upload.

**Repair.** Correct the values at source and re-ingest. Text in a numeric column is usually an error code or a stray delimiter.

### `coordinate_axis_order_out_of_extent`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Coordinates fall outside the legal range under either axis order, so the problem is not ordering.

**Repair.** Check the values against the source system. These are wrong independently of which axis is which.

### `coordinate_axis_order_swapped`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Coordinates place a latitude in a longitude slot. They resolve to a real but wrong location, which is why range checks alone do not catch them.

**Repair.** Swap the columns and re-ingest. Do not reproject: the coordinates are not mis-projected, they are mis-ordered, and a reprojection will produce a plausible wrong place.

### `coordinate_axis_order_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No axis order is established for these coordinates. EPSG:4326 is formally latitude/longitude while GeoJSON, PostGIS and desktop GIS are longitude/latitude, so the same pair resolves to two different places depending on an assumption nobody wrote down.

**Repair.** Declare the CRS, the format, or name the columns latitude and longitude so the order is stated rather than assumed.

## Design notes

- **Why this exists**
- **The failure this module exists to catch**
- **What this module will not do**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
