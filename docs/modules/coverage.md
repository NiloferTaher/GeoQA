# `coverage`

How much of a geometry survived a clip, and whether the pieces came back.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_coverage_floor` | Report features that lost more than ``1 - minimum_retained`` to the clip. |
| `validate_split_completeness` | Report split features whose pieces do not reassemble into one geometry. |

## Conditions emitted

### `clip_coverage_below_floor`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A feature retained less of its area through a clip than the declared floor allows, so what was delivered is not the feature that was asked for.

**Repair.** Establish whether the boundary is correct for this feature or whether the feature genuinely straddles it. Widening the clip to hide this removes the evidence rather than the cause.

### `clip_coverage_uncomputable`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A feature has no measurable area before clipping, so its retained fraction cannot be assessed.

**Repair.** A zero-area feature is a defect in itself. Establish why it has no area before asking how much of it survived.

### `clip_feature_absent`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A feature present in the source is entirely absent from the clip output.

**Repair.** Confirm the clip covered the feature's extent. An absent feature is not the same as one that failed a threshold.

### `split_pieces_area_lost`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Split pieces reassemble to less area than their sum, so a piece is missing.

**Repair.** Find the missing piece. A silent short record is the failure this exists to catch, and it is invisible without the comparison.

### `split_pieces_not_whole`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A feature split across pieces by a clip does not reassemble into one valid geometry, so the halves were never rejoined.

**Repair.** Rejoin the pieces for this identifier, or state that the delivery is split by design so the receiver knows not to sum the parts.

### `split_pieces_overlap`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Split pieces union to more area than the sum of their parts, which means they overlap and are being counted more than once.

**Repair.** Determine whether the overlap is genuine in the source or an artefact of clipping the same feature against two boundaries. Any total computed over the pieces will be wrong either way.

### `validator_could_not_run`

**Severity** high &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A validator could not complete and is reporting that fact rather than returning an empty result.

**Repair.** Fix the validator or the input it was given. An empty result from a validator that did not run is indistinguishable from a clean one.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
