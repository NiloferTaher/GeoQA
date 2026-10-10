# `water_loss`

Unavoidable Annual Real Loss and the Infrastructure Leakage Index.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_water_loss` | Check a water-loss assessment for the conditions that make it unusable. |

## Conditions emitted

### `ili_below_possible_range`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Computed ILI is below the plausible range, which almost always indicates a unit or coefficient error rather than an unusually efficient network.

**Repair.** Re-check the CARL and UARL units and the conversion between volumetric loss and daily rate before believing the value.

### `ili_not_computable`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

ILI cannot be computed from the declared inputs, so no index should be published.

**Repair.** Supply a declared UARL, or report real losses alone rather than a derived index.

### `ili_out_of_range`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Computed ILI exceeds the plausible range, indicating a unit error, an implausible UARL, or an inflated loss estimate.

**Repair.** Re-check units and the UARL derivation. An extreme index is more often arithmetic than a genuinely catastrophic network.

### `ili_requires_context`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

An Infrastructure Leakage Index value is reported without the pressure regime, connection density and accounting period that give it meaning. A number alone is not an assessment.

**Repair.** Report ILI with its caveats and the conditions it was computed under. Two utilities with identical indices may have entirely different leakage problems.

### `nrw_exceeds_input`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Real plus apparent losses exceed the input volume over the same accounting period, which is physically impossible.

**Repair.** Reconcile the reporting periods, the sign convention and the volume units before publishing any derived index.

### `uarl_missing_connections`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The connection count is zero, so the connection term of the UARL regression contributes nothing and the index is biased low.

**Repair.** Supply the real number of service connections. A UARL computed without it is not comparable to published values.

### `uarl_pressure_factor_estimated`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

The pressure factor applied to UARL is estimated rather than measured, so the index inherits that uncertainty.

**Repair.** Use logged pressure data where available, or state the estimation method alongside the result.

## Design notes

- **Why this needs declared coefficients too**
- **Why ILI is never returned as a verdict**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
