# `crs_units`

Coordinate reference system advice, unit reasoning, and safe reprojection.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_crs_consistency` | Report missing, geographic, implausible, or unit-inconsistent CRS. |

## Conditions emitted

### `angular_crs_measurements_invalid`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Measurements were attempted in a geographic CRS, so distances and areas are in degrees rather than metres.

**Repair.** Reproject to a projected CRS, or use geodesic measurement. Degrees are not a length and must never be reported as one.

### `crs_reprojection_recommended`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The dataset is in a CRS that is valid but unsuitable for the stated measurement, so results will be misleading.

**Repair.** Reproject to a projected CRS appropriate to the area and declare the target before doing so. The advisory does not change the data.

### `length_unit_inconsistent_with_crs`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The CRS linear unit is inconsistent with a declared or implied measurement unit, so lengths will not agree with the projection.

**Repair.** Reconcile the CRS unit with the units actually used. A projected CRS in feet with metric measurements produces plausible but wrong distances.

### `missing_spatial_reference`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A dataset has an unknown or undefined coordinate system, preventing correct overlay and projection.

**Repair.** Define the correct coordinate system from authoritative metadata before projecting or overlaying the data.

### `polar_crs_verify_extent`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

The dataset uses a polar projection, where extent, scale and wrap-around need checking before any spatial measurement.

**Repair.** Confirm the data falls on the intended polar side and that extents are not crossing the antimeridian or a pole.

### `web_mercator_area_unusable`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Areas and lengths are being computed in Web Mercator, where scale distortion grows with latitude and area values are not comparable.

**Repair.** Reproject to a projected CRS before measuring area or length, or measure in geodesic units. Web Mercator is a display projection.

## Design notes

- **The problem this addresses**
- **Design decision**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
