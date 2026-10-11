# `transform_audit`

What a geometry operation actually did.

## Conditions emitted

### `repair_buffer_zero_failed`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

buffer(0) could not be applied at all, so the repair ladder has no remaining step.

**Repair.** The geometry is malformed beyond what the standard remedy can address. Inspect it directly.

### `repair_changed_geometry`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A repair produced a valid geometry that is measurably different from the one supplied.

**Repair.** The repaired geometry is not the original one. Decide whether that is acceptable for the measurement being made, and record the change rather than treating the repair as neutral.

### `repair_incomplete`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

buffer(0) did not produce a valid geometry, so the repair did not work and the next step in the ladder is required.

**Repair.** Escalate rather than proceeding. An invalid geometry that survived the standard remedy needs a cause, not another attempt.

### `transform_attribute_changed`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

An operation intended to change geometry also changed an attribute value.

**Repair.** Establish whether the change was intended. A geometry operation that alters data has changed something nobody agreed to change.

### `transform_dropped_features`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A merge, dissolve or rewrite omitted features that were present in the source.

**Repair.** Record which features were discarded and why. A dissolve that reduces duplicates must say so; one that silently loses rows must not be called a dissolve.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
