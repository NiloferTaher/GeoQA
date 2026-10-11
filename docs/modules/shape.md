# `shape`

Slivers: thin geometry, and geometry that is simply too small.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_shape` | Run whichever shape checks the caller supplied thresholds for. |

## Conditions emitted

### `feature_zero_area`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A feature has no area at all, which is debris or the residue of an operation that did not complete.

**Repair.** Identify what produced it. A zero-area feature carries no measurement and will silently distort any area total it joins.

### `geometry_elongated`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

A polygon has a length-to-width ratio above the declared limit.

**Repair.** Decide whether elongation is intended. A catchment and a cable run are both legitimately elongated, so this is only a defect when the layer has one purpose.

### `geometry_thin_sliver`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A polygon is thinner than the declared width along its whole extent, because it disappears when buffered inwards by half that width.

**Repair.** Geometry this thin breaks topology, cannot be buffered meaningfully and will not route. Determine whether it is a failed clip, a failed dissolve, or a genuinely narrow feature that should have been a line.

### `geometry_width_measured`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A polygon survived the inward buffer, and its measured width has been reported because measurement was requested rather than judgement.

**Repair.** No action. This is a measurement, included only when the caller asked for measurements rather than findings.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
