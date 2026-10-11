# `sentinels`

Placeholder values that pass a null check but are not null.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_sentinels` | Report columns whose placeholder values will be read back as answers. |

## Conditions emitted

### `sentinel_placeholder_value`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A column contains placeholder values such as zero dates, N/A, or negative sentinels that pass a null check and are read back as real answers.

**Repair.** Convert the placeholders to genuine nulls before the data is loaded, and establish at source where they come from. A sentinel in a measure column becomes an outlier in every analysis that follows.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
