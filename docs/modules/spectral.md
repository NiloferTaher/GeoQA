# `spectral`

spectral.py — Satellite / spectral index anomaly validators for GeoQA

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_band_radiance` | Band-level QA for TOA radiance / reflectance tables (e.g., Tanager 426-band |
| `validate_spectral_indices` | Deterministic spectral-index anomaly checks for tabular/vector layers that |

## Conditions emitted

### `ndwi_ndvi_inconsistency`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

NDWI (water-like) and NDVI (vegetation-like) are both high on the same feature, indicating mis-registered land/water or mixed pixel.

**Repair.** Review against high-res imagery or use sub-pixel unmixing; flag for human review, do not auto-reclassify.

### `spectral_band_negative_radiance`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

TOA radiance band value is negative, indicating sensor or QA anomaly (cf. Tanager 376 nm band).

**Repair.** Mask negative TOA radiance pixels before index math; check band calibration.

### `spectral_index_nan`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Spectral index (NDVI/NDWI/NDMI) is NaN or non-finite indicating missing band or QA mask gap.

**Repair.** Inspect source raster QA band / cloud mask; recompute index only on valid pixels.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
