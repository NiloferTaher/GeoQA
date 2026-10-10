# `clip`

Clipping: which side a straddling feature belongs to, and whether the clip left halves behind.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_clip_assignment` | Report how features split across a boundary, under a declared threshold. |
| `validate_clip_completeness` | Report features left half-formed by a clip. |

## Conditions emitted

### `clip_assignment_near_threshold`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A feature's split sits within the near-threshold band of the configured percentage, so the assignment is effectively a coin-flip.

**Repair.** Review this feature individually rather than accepting the automatic assignment.

### `clip_assignment_unresolved`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A feature straddles a boundary and no assignment rule was supplied. The percentage that decides it is a policy, so it is not defaulted.

**Repair.** Supply the percentage your organisation assigns on. It is a decision, and this module will not make it for you.

### `clip_feature_absent_from_source`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A clipped feature overlaps no source feature, so the two layers may not correspond or may come from different vintages.

**Repair.** Establish which vintage each layer comes from before comparing them.

### `clip_feature_half_area`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A clipped feature retains almost exactly one half of its source. This is the signature of a centreline or mid-block clip rather than a boundary the data was drawn to.

**Repair.** Confirm the clip line was a real administrative boundary. If it was a road or a tile edge, the halves are not meaningful units.

### `clip_feature_heavily_truncated`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A clipped feature retains less than the declared minimum fraction of its source area, so it is largely gone and will under-count anything derived from it.

**Repair.** Decide whether a remainder this small should be kept at all, or absorbed into its neighbour deliberately.

### `clip_feature_missing_after_clip`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A source feature has no overlapping counterpart in the clipped layer. Either it fell entirely outside the clip area, or it was dropped.

**Repair.** Confirm the clip area covers the full extent of the source. A silent drop looks identical to a legitimate exclusion.

### `clip_straddles_boundary`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A feature crosses a boundary, with a measured split between the two sides. Evidence, not a defect: the point is that the decision is visible.

**Repair.** Confirm the assigned side is the intended one under the declared threshold.

## Design notes

- **Two questions, one module**
- **What this module reports**
- **Conditions emitted**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
