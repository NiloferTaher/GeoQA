# `vertical_datum`

Vertical reference: datums, tidal references and elevation sign conventions.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_vertical_reference` | Report a vertical reference that is absent, ambiguous or contradicted. |

## Conditions emitted

### `vertical_crs_undeclared`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A horizontal CRS is declared but no vertical component. A level needs a compound CRS to mean anything.

**Repair.** Declare a compound CRS, or record the horizontal and vertical references separately and unambiguously.

### `vertical_crs_unknown`

**Severity** low &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

The declared vertical CRS is not one this module recognises. It may be entirely valid; it simply cannot be checked here.

**Repair.** Confirm the identifier against the EPSG registry. No repair is needed if the code is correct but newer than this module.

### `vertical_depth_sign_inverted`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A depth column is entirely positive. Depth below a surface is negative, so the sign convention has been flipped and the data plots as land.

**Repair.** Invert the sign at source. Do not fix it downstream, because a layer that plots as land is more dangerous than one that plots as nothing.

### `vertical_range_implausible`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Observed values fall outside the plausible range for their declared meaning, which usually indicates a unit error.

**Repair.** Check the unit before anything else. Feet on data described as metres produces values that are wrong but still plausible in many ranges, so this catches gross errors only.

### `vertical_reference_ambiguous`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Several different reference surfaces are named across the metadata or the columns, so which one applies is undecided.

**Repair.** Decide which surface the values are relative to and record only that one.

### `vertical_reference_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

Elevation values carry no stated reference surface. Mean sea level, mean higher high water, lowest astronomical tide and geoid are different surfaces, locally by more than a metre, and the file does not say which one these values are relative to.

**Repair.** Record the vertical reference and the epoch it was computed for. A consumer will otherwise assume one, and the assumption is usually wrong.

### `vertical_unit_undeclared`

**Severity** low &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No unit is recorded for an elevation column, and a value's magnitude cannot supply one. Low-lying coastal data naturally sits between 0 and 3 m, so guessing from magnitude would misfire on exactly the data that needs it most.

**Repair.** Record the unit. This matters most for coastal and near-sea-level data, where a feet/metre error is easy to make and hard to see.

## Design notes

- **Why this exists**
- **The specific trap**
- **The sign convention trap**
- **Why it is a general module and not a flood module**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
