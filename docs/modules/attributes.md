# `attributes`

## Conditions emitted

### `domain_violation`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

An attribute value falls outside the allowed coded or range domain for the field.

**Repair.** Clean invalid values by enforcing coded-value or range domains during edit and import workflows.

### `non_unique_attribute`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Values expected to be unique are duplicated across records.

**Repair.** Deduplicate or rekey the records so fields that must be unique contain unique values.

### `null_attribute_in_required_field`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A required attribute is missing even though the field is expected to contain a value.

**Repair.** Populate required values from source systems, lookup tables, or QA review before release.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
