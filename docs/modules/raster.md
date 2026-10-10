# `raster`

Raster reading and spectral validation over real imagery.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_raster` | Check a raster before any index is computed from it. |

## Conditions emitted

### `raster_band_unmapped`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Raster bands carry no description, so their roles cannot be established from the file.

**Repair.** Supply an explicit band map and record where it came from. Band order in a delivered raster is a convention, not metadata.

### `raster_geographic_crs`

**Severity** low &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The raster is in a geographic CRS. That is valid, but area, distance and shape statistics over it are distorted.

**Repair.** Reproject to an equal-area projection before computing area or shape statistics. Keep the geographic raster for display.

### `raster_insufficient_bands`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The raster has fewer bands than the declared analysis requires.

**Repair.** Supply the missing bands or reduce the declared analysis to what the file actually contains.

### `raster_nodata_undeclared`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

The raster declares no nodata value, so valid-zero pixels cannot be told from no-data.

**Repair.** Declare nodata explicitly. Statistics computed without it treat fill values as observations.

### `raster_scale_factor_unknown`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Pixel values are physical units such as reflectance rather than raw integers, but no scale or offset is declared.

**Repair.** Record the scale and offset. Without them, indices computed from the file are wrong by a constant factor that is easy to miss.

## Design notes

- **Why this exists**
- **Design constraints**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
