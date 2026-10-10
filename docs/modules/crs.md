# `crs`

## Conditions emitted

### `invalid_spatial_reference`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The spatial reference definition stored with data is invalid and must be detected or repaired.

**Repair.** Repair or redefine the spatial reference using authoritative CRS information and revalidate the dataset.

### `missing_spatial_reference`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A dataset has an unknown or undefined coordinate system, preventing correct overlay and projection.

**Repair.** Define the correct coordinate system from authoritative metadata before projecting or overlaying the data.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
