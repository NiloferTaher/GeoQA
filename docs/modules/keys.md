# `keys`

Keys that are not a single column.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_vocabulary_binding` | Report ambiguous and unbound names as issues. |

## Conditions emitted

### `compound_key_duplicate`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Several records share the same compound natural key at the declared timestamp granularity, so the same visit is recorded more than once.

**Repair.** Decide which record is authoritative and record that decision. Keeping them all inflates every count derived from the table.

### `schema_field_ambiguous`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A required field is present under more than one name, so which column holds the data cannot be determined.

**Repair.** Establish which column is authoritative rather than taking the first match, since first-match makes the result depend on column order.

### `schema_field_missing`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A required field is absent under every name it is known by.

**Repair.** Supply the field or record that this dataset does not carry it. A file that was skipped for a missing column should be counted, not silently omitted.

### `vocabulary_binding_ambiguous`

**Severity** high &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

A name matches more than one controlled-vocabulary term above the cutoff, so it has been attached to one of several plausible terms without the choice being recorded.

**Repair.** Confirm the intended term and record it. Attaching a record to the wrong region is worse than leaving it unattached.

### `vocabulary_binding_unbound`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

A name matches no controlled-vocabulary term above the cutoff and has been left unattached.

**Repair.** Either add the term to the vocabulary or record it as a deliberate exclusion. Names that match nothing usually indicate a vocabulary that has fallen behind the data.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
