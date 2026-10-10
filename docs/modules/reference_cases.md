# `reference_cases`

Published reference cases, so the coefficients can be checked rather than trusted.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_reference_cases` | Run the published cases and report any that do not reproduce. |
| `validate_uarl_applicability` | Report use of the UARL equation outside its stated range. |

## Conditions emitted

### `coefficient_reference_case_failed`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The implementation does not reproduce a published worked example. A formula that cannot reproduce its own source figure should not be used, whatever else it looks right about.

**Repair.** Do not use this result. Reconcile the arithmetic and units against the publication until the case reproduces, then re-run every case.

### `coefficient_reference_case_passed`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The implementation reproduces a published worked example within tolerance. Recorded as evidence rather than as a defect.

**Repair.** No repair needed. Retain the citation with the result so the check can be repeated after any change to the formula.

### `coefficient_uarl_outside_applicability`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

The UARL equation is being applied outside the network size, connection density and pressure range it was derived for. It still returns a number, and that number is not an estimate of unavoidable losses for a network of this character.

**Repair.** Either supply a UARL derived by a method valid for this network, or state that the equation is being used outside its stated limits and report the result with that caveat attached.

## Design notes

- **What this module is for**
- **Where the numbers come from**
- **Honest note on the AQUA example**
- **Applicability**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
