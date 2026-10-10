# `hyperspectral`

HDF5 hyperspectral products: HDF-EOS swaths such as EMIT, and generic groups.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_hyperspectral` | Report structural conditions in a hyperspectral product. |

## Conditions emitted

### `hyperspectral_band_count_sparse`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The cube has too few bands for a spectral index, which needs at least a numerator and a denominator band.

**Repair.** Confirm the file is the product intended. A two-band cube is usually a derived preview rather than the delivered product.

### `hyperspectral_fill_value_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The cube declares no fill value. Instrument no-data such as -9999 is an ordinary number and will enter any mean or index without complaint.

**Repair.** Record the fill value and exclude it before any statistic. This is the most common way a raster average is silently wrong.

### `hyperspectral_geolocation_absent`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

No latitude and longitude layer was found, so a pixel cannot be located on the ground and the swath cannot be joined to any vector layer.

**Repair.** Obtain the geolocation layers. Without them the raster is a picture with no position.

### `hyperspectral_nodata_fraction_high`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

A large share of the sampled window is no-data, which usually means the swath boundary or a sensor dropout rather than real observations.

**Repair.** Check the footprint and the acquisition geometry before drawing any conclusion from the remaining valid pixels.

### `hyperspectral_product_level_mismatch`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The file is a different product level from the one the analysis expects. The indices would be computed identically and mean something else.

**Repair.** Use the product the method was defined for. Surface reflectance and radiance products cannot be substituted for one another.

### `hyperspectral_product_level_unknown`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Could not establish whether the cube is surface reflectance or top-of-atmosphere radiance. The two have different valid ranges, so mixing them silently produces plausible wrong indices.

**Repair.** Record the product level. Radiance is not a scale difference from reflectance; it is a different quantity with a different meaning.

### `hyperspectral_quality_layers_absent`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

No quality, cloud or no-data mask accompanies the cube, so unusable pixels cannot be excluded from an index.

**Repair.** Obtain the quality layers delivered with the product. Applying an index over cloud and no-data produces a map of the instrument, not the ground.

### `hyperspectral_wavelengths_undeclared`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The spectral cube carries no wavelength attribute. Band index alone cannot identify a band across products, so any index computed from this file would be positional guesswork.

**Repair.** Obtain the wavelength table from the product metadata. Do not assume band order matches another product from the same sensor family.

## Design notes

- **Why a separate reader**
- **The case this was built against**
- **Design constraints**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
