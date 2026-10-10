# `water_balance`

IWA water balance and non-revenue water analysis.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_water_balance` | Check that a balance is internally consistent. |

## Conditions emitted

### `ili_not_computable`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

ILI cannot be computed from the declared inputs, so no index should be published.

**Repair.** Supply a declared UARL, or report real losses alone rather than a derived index.

### `ili_requires_context`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

An Infrastructure Leakage Index value is reported without the pressure regime, connection density and accounting period that give it meaning. A number alone is not an assessment.

**Repair.** Report ILI with its caveats and the conditions it was computed under. Two utilities with identical indices may have entirely different leakage problems.

### `water_balance_loss_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The balance closes on total input but not on system input volume.

**Repair.** Reconcile the balance components and confirm the unaccounted-for term is recorded rather than omitted.

### `water_balance_negative_component`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A balance component is negative, so the balance cannot represent a physical quantity.

**Repair.** Correct the sign or source table. Negative volumes usually indicate a mis-mapped column rather than a genuine balance.

### `water_balance_night_flow_residual`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

The night-time residual exceeds the declared leakage threshold.

**Repair.** Check for legitimate night flow, such as industrial or irrigation demand, before treating the residual as leakage. The threshold itself must be declared.

### `water_balance_nrw_exceeds_input`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Real plus apparent losses exceed the input volume that produced them.

**Repair.** Re-check the reporting periods of the two figures and the sign convention of each loss term. A physically impossible balance invalidates every index derived from it.

### `water_balance_nrw_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Reported non-revenue water does not equal real losses plus apparent losses.

**Repair.** Correct either the NRW figure or the loss components; both are usually quoted together and must agree.

### `water_balance_supply_mismatch`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The balance closes on system input volume but not on the sum of the individual supply components.

**Repair.** Reconcile the component volumes against the published total. One of the two is wrong; the balance shows which.

## Design notes

- **What this computes**
- **The design decision that matters**
- **On ILI**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
