# `workbook_media`

Embedded and referenced media in a spreadsheet.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_workbook_media` | Check that the artefacts a workbook's rows depend on are actually there. |

## Conditions emitted

### `workbook_attachment_without_key`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

An attachment is anchored to a row with no value in the key column, so the evidence cannot be attributed to a record.

**Repair.** Populate the identifier, or move the attachment to the row it belongs to.

### `workbook_media_below_legibility_threshold`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

An attachment is too small on its longest side to show the detail its row claims, so the row looks evidenced and is not readable.

**Repair.** Replace with a legible capture, or lower the threshold if the claim genuinely does not need detail.

### `workbook_media_duplicate`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Identical attachment content appears more than once, usually a copy-paste artefact, and usually two records pointing at one piece of evidence.

**Repair.** Confirm each record has its own evidence. Two rows sharing one attachment is a finding about the data, not about the file.

### `workbook_media_missing_reference`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row references its attachment by path and that file does not exist. A path to a file on someone else's machine does not survive the workbook being sent anywhere.

**Repair.** Embed the attachment rather than referencing it, so the evidence travels with the record.

### `workbook_media_orphaned`

**Severity** medium &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

An attachment is embedded but anchored to no row, so it documents nothing.

**Repair.** Anchor the attachment to the row it belongs to, or remove it.

### `workbook_media_undecodable`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

An attachment is in a format that cannot be inspected here, so it is unverified rather than checked.

**Repair.** Convert to a format that can be validated, or verify it by another means and record that it was verified.

### `workbook_media_unverifiable`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

The key column is absent, so no attachment can be traced back to a record.

**Repair.** Supply or restore the identifier column.

### `workbook_no_attachments`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

The workbook holds no attachments at all.

**Repair.** Establish this before concluding that supporting evidence is missing.

### `workbook_row_missing_attachment`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A row carries no attachment although attachments are declared expected on every row. Either the evidence was never captured or it was lost.

**Repair.** Establish which rows were intended to carry evidence and recover or re-capture it.

## Design notes

- **The general problem**
- **Design constraints**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
