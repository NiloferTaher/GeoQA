# `cross_layer`

Referential integrity between two layers.

## Conditions emitted

### `cross_layer_geometric_orphan`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A feature's geometry has no spatial relationship with any geometry in the layer it is meant to relate to, even though its identifier resolves.

**Repair.** The identifier is present but the geometry is not where the identifier says it is. Check the projection of both layers before assuming the feature was drawn in the wrong place.

### `cross_layer_key_missing`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row has no usable join key, so it is excluded from any comparison and silently disappears from the result.

**Repair.** Populate the key or record explicitly that the row is out of scope. A row with no key cannot be shown to be correct.

### `cross_layer_orphan`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row references an identifier that does not exist in the layer it is supposed to resolve against.

**Repair.** Establish whether the parent record was never created, was deleted, or was loaded under a different identifier. Do not create the parent to silence this.

### `cross_layer_unmatched_child`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row in one layer has no counterpart in the layer it is joined to, in the child-to-parent direction.

**Repair.** Determine whether the join key is correct for this pair of layers before assuming a record is missing.

### `cross_layer_unmatched_parent`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row in one layer has no counterpart in the layer it is joined to, in the parent-to-child direction.

**Repair.** Reported separately from the child direction because an orphan-only check reports half the problem and looks complete while doing so.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
