# `night_flow`

Night-flow leakage and NRW coefficients, under declared provenance.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_coefficient_chain` | Validate every coefficient in a calculation chain. |
| `validate_coefficient_declaration` | Check one declaration for completeness, units and reproduction. |

## Conditions emitted

### `coefficient_fails_reproduction`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A coefficient failed to reproduce its own reference case within tolerance, so the implementation or the coefficient is wrong.

**Repair.** Do not use the result. Reconcile the formula, units and inputs against the reference until the case reproduces.

### `coefficient_meaning_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A coefficient is supplied without stating what it means, so the result cannot be interpreted.

**Repair.** Record the quantity, its units and the quantity it multiplies. An unlabelled number in a regression is not reproducible evidence.

### `coefficient_out_of_range`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A coefficient falls outside a physically plausible range for its declared meaning.

**Repair.** Confirm the unit and the derivation. A value outside range usually indicates a unit error rather than an unusual network.

### `coefficient_reproduced`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

A coefficient reproduced a published reference case within tolerance. This is recorded as evidence, not as a defect.

**Repair.** No repair needed. Retain the reference case with the result so the check can be repeated.

### `coefficient_reproduction_indeterminate`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Reproduction was attempted but the outcome is inconclusive, so the coefficient remains unverified.

**Repair.** Supply the missing reference inputs, or state plainly that the coefficient is unverified and treat downstream results accordingly.

### `coefficient_source_unrecorded`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A coefficient is used without a recorded source, so nobody can later confirm what it was meant to represent.

**Repair.** Record the publication, standard or measurement campaign the coefficient came from, and the conditions it was derived under.

### `coefficient_unit_mismatch`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A coefficient unit is incompatible with the units of the variables it multiplies.

**Repair.** Convert either the coefficient or the inputs. A mismatch produces a number with a real-looking magnitude but no physical meaning.

### `coefficient_unit_scale_ambiguous`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A declared unit is ambiguous between order-of-magnitude interpretations, such as L/day against m3/day, or km against m.

**Repair.** Use an unambiguous unit symbol. Where the ambiguity cannot be resolved, convert explicitly rather than relying on convention.

### `coefficient_unit_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A coefficient has no units, so it may be correct by orders of magnitude or entirely wrong.

**Repair.** Declare the units and confirm the input variables share them. Unit ambiguity in a hydraulic coefficient is the most common silent error.

### `coefficient_unverified`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A coefficient is declared but carries no verification evidence, so the result is an assertion rather than a measurement.

**Repair.** Attach either reproduction evidence from a known case, a field measurement, or an explicit statement that the value is unverified.

### `coefficient_used_inconsistently`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

The same named coefficient is declared with different values within one analysis.

**Repair.** Reconcile to one declared value, or rename them if genuinely different coefficients are intended.

## Design notes

- **The design problem**
- **What can and cannot be verified**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
