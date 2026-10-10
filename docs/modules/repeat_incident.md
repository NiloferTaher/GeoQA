# `repeat_incident`

Cross-period recurrence: the same finding appearing in more than one period.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_repeats` | Report recurring locations and the gaps that weaken the claim. |

## Conditions emitted

### `period_gap`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

Survey periods jump with no observation between them, so a recurrence spanning the gap cannot be shown to be continuous.

**Repair.** Treat recurrence across the gap as unproven continuity. Report which periods were actually observed.

### `period_missing`

**Severity** high &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

An expected survey period is absent. Absence of a period is not absence of a defect, so recurrence counts understate how often a location was investigated.

**Repair.** Recover the missing period or state explicitly that recurrence was measured over the periods actually available.

### `repeat_same_asset`

**Severity** high &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The same logical asset recurs across survey periods, indicating a chronic component defect.

**Repair.** Repair or replace the asset. Persistent recurrence at one component is a defect of that component.

### `repeat_same_place`

**Severity** high &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A location recurs across periods but the logical asset differs each time, so the asset is not the cause.

**Repair.** Investigate the supplying main, the boundary or an area-level condition before excavating. Replacing the component will not resolve this.

### `repeat_unattributed`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A location recurs across periods but no logical-asset key was supplied, so the cause cannot be attributed to the component or to its surroundings.

**Repair.** Supply a logical-asset identifier so chronic component defects can be told from upstream problems.

## Design notes

- **The condition**
- **Period gaps**
- **Provenance**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
