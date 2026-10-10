# `governance`

Metadata governance: is this dataset safe to publish, reuse and defend?

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_governance_metadata` | Report metadata that prevents lawful, accountable use of a dataset. |

## Conditions emitted

### `governance_accountability_unassigned`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No responsible organisation and no point of contact are recorded, so nobody is answerable for the dataset.

**Repair.** Name the responsible organisation and a contact point. Required by Regulation (EC) No 1205/2008 references 9 and 10.1.

### `governance_conformity_undeclared`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No conformity declaration is recorded, so a consumer cannot tell whether a specification applies or was checked against.

**Repair.** State the specification, the degree of conformity, and whether it was validated. Required by Regulation (EC) No 1205/2008 reference 7.

### `governance_licence_not_declared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No conditions for access and use are recorded, and no limitations on public access are stated. A dataset with no recorded terms cannot lawfully be reused, and nothing in the data distinguishes it from one that may not be.

**Repair.** Record the licence and the access conditions. Required by Commission Regulation (EC) No 1205/2008 reference 8.1, multiplicity 1..*.

### `governance_licence_not_open`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** medium

A licence is recorded but is not an open one. Under Directive (EU) 2019/1024 public sector data should be reusable under standard open terms by default.

**Repair.** Confirm the restriction is intended and record why. A restricted licence is a legitimate choice; an unexamined one is not.

### `governance_lineage_undeclared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No lineage statement is recorded. Without the processing history, a declared positional accuracy cannot be interpreted and a known error cannot be traced.

**Repair.** Record how the data was produced, from what sources, with what processing. Required by Regulation (EC) No 1205/2008 reference 6.1, multiplicity 1.

### `governance_metadata_element_missing`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A metadata element required by Regulation (EC) No 1205/2008 is absent.

**Repair.** Record the element. The required set and multiplicities are in the INSPIRE implementing rules.

### `governance_metadata_element_placeholder`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A required metadata element is recorded with placeholder text rather than a decision.

**Repair.** Replace the placeholder with an actual value, or remove the element if it genuinely does not apply.

### `governance_metadata_stale`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The metadata date is older than the declared review threshold. A stale record still looks authoritative to a consumer.

**Repair.** Review the metadata and update the date, or state why it has not been reviewed.

### `governance_temporal_reference_missing`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No temporal reference is recorded, so the dataset has no stated currency and nobody can tell whether it is current.

**Repair.** Record the reference date, or the range over which the data is valid. Required by Regulation (EC) No 1205/2008 reference 5.

### `governance_unique_identifier_missing`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No unique resource identifier is recorded, so the dataset cannot be cited or versioned unambiguously.

**Repair.** Assign a persistent identifier. Required by Regulation (EC) No 1205/2008 reference 1.5, multiplicity 1..*.

## Design notes

- **The gap this fills**
- **Provenance**
- **The element that matters most**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
