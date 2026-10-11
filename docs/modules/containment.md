# `containment`

Buffer containment, round-trip durability, and scale-dependent tolerance.

## Conditions emitted

### `containment_no_match`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A source feature has no corresponding buffer, so its containment cannot be established either way.

**Repair.** Resolve the join first. An absent result is not a passing result.

### `containment_not_enclosing`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A buffer does not enclose the geometry it was built to enclose.

**Repair.** The buffer was drawn from a different or earlier version of the source geometry. Rebuild it from the current geometry rather than widening it until it fits.

### `roundtrip_file_missing`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The writer reported success but produced no file.

**Repair.** Treat a silent write as a failure until the file is confirmed. Nothing downstream can tell the difference.

### `roundtrip_geometry_degraded`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Geometry values became null or empty across a write and read-back.

**Repair.** Determine which geometries the format cannot represent before re-running the operation.

### `roundtrip_geometry_lost`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The written file came back with no geometry column.

**Repair.** The write produced attributes only. Check that the geometry column was addressed by its real name.

### `roundtrip_read_failed`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The written file cannot be read back, so the output is not a usable artefact.

**Repair.** Do not report the operation as complete. An artefact that cannot be reopened will fail for whoever receives it.

### `roundtrip_row_count_changed`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The number of rows changed across a write and read-back, so features were dropped by the format.

**Repair.** Identify which features were dropped before retrying. Formats that cannot represent the layer's geometry type will drop them again.

### `roundtrip_write_failed`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Writing the layer to its destination format failed.

**Repair.** Check the writer against the format and the geometry types present. A shapefile writer cannot store a mixed-family layer.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
