# `dimension`

Geometry dimension (2D / 3D) evidence, from real operational behaviour.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_geometry_dimension` | Report geometry-dimension evidence. |

## Conditions emitted

### `geometry_dimension_mismatch`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Present Z against a declared 2D requirement. The dataset is nonconforming to its own specification.

**Repair.** Either provide the required third dimension or restate the target dimension; the mismatch is in the specification, not necessarily the data.

### `geometry_z_all_zero`

**Severity** low &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

Every Z ordinate is zero, so the geometry is dimensionally 2D despite declaring Z. Low severity: worth knowing, not an error.

**Repair.** A 2D column type avoids carrying a meaningless ordinate. Confirm Z is not a deliberate datum (for example sea-level-referenced) before dropping it.

### `geometry_z_inconsistent`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Some features carry Z and others do not, making a single storage column type unsafe for the layer.

**Repair.** Normalise dimensionality across the layer, or store geometry without a fixed dimension type.

## Design notes

- **Provenance of the rule**
- **Why the condition is not simply "has_z = bad"**
- **Conditions emitted**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
