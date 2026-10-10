# `cog`

Cloud Optimized GeoTIFF conformance, and vector format currency.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_cog` | Report a TIFF that is valid but not laid out for partial reading. |

## Conditions emitted

### `raster_block_size_small`

**Severity** low &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** medium

Tiles are smaller than the 512 px convention, increasing metadata overhead without improving access, since a partial read still costs a whole tile.

**Repair.** Use 512 px tiles unless a specific workload justifies otherwise.

### `raster_deprecated_format_flagged`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The file uses a format whose standards standing has changed. Nothing is wrong with the file; this is recorded so the interchange choice is deliberate rather than inherited.

**Repair.** Confirm the format is the intended interchange choice. Formats at draft or in-development status can change incompatibly.

### `raster_missing_overviews`

**Severity** medium &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

A large TIFF has no reduced-resolution overview levels, so a consumer must read full resolution to draw a thumbnail.

**Repair.** Build overviews when writing. This is the main reason cloud-optimized layouts exist.

### `raster_not_cloud_optimized`

**Severity** medium &nbsp;|&nbsp; **Class** `runtime_issue` &nbsp;|&nbsp; **Confidence** high

A large TIFF is stored in strips rather than tiles. It is valid and opens everywhere, but a reader cannot fetch a small part of it, so anything serving it over a network must move the whole file.

**Repair.** Rewrite as a Cloud Optimized GeoTIFF. Legacy readers still open a COG, so there is no compatibility cost.

## Design notes

- **Why this exists**
- **Other formats, and why they are not replacements**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
