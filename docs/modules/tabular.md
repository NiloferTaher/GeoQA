# `tabular`

Tabular validation for CSV and Excel, before anything spatial touches them.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_tabular` | Report conditions that will corrupt or hide data downstream. |

## Conditions emitted

### `tabular_ambiguous_date`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A date column holds values that mean a different day depending on whether they are read day-first or month-first. Nothing in the file states which, so every such row is wrong under one convention.

**Repair.** Store dates in ISO 8601 (YYYY-MM-DD). The ambiguity is a property of the written form, not of the reader.

### `tabular_blank_header`

**Severity** medium &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A column has no name and will be imported as an unnamed column, so its values have nothing to be referred to by.

**Repair.** Name the column. Where the values were never meant to be data, remove the column.

### `tabular_duplicate_header`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

Two or more columns share a name, so a lookup by that name returns an arbitrary one of them.

**Repair.** Rename to unique names before any automated processing.

### `tabular_duplicate_key`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A key column repeats a value, so a one-to-one join against it fans out and multiplies records.

**Repair.** Resolve the duplicates at source, or declare the join as one-to-many and aggregate deliberately.

### `tabular_empty_column`

**Severity** low &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A column is empty in every row.

**Repair.** Remove the column, or populate it. Either way, confirm it was not meant to carry data.

### `tabular_formula_cells`

**Severity** medium &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

Cells hold formulas. A reader that does not evaluate them sees the last cached value, which may be out of date.

**Repair.** Paste as values before processing, or read the cached results knowingly as potentially stale.

### `tabular_hidden_rows`

**Severity** medium &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

Rows are hidden and will not appear in a default read.

**Repair.** Confirm whether the hidden rows are excluded deliberately or were hidden to hide an error.

### `tabular_hidden_sheet`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A sheet is hidden and will not appear in a default read, so whatever corrections it holds look as though they were never made.

**Repair.** Read every sheet explicitly, or unhide the sheets that carry data.

### `tabular_identifier_leading_zero`

**Severity** critical &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

An identifier-like column holds all-numeric values with a leading zero. Reading it as a number destroys the identifier and the records will never match the source system.

**Repair.** Force the column to text at export and at every read. A repair that re-pads the number cannot know whether the original had the zero.

### `tabular_identifier_numeric`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

An identifier is held as a number with enough digits that spreadsheet software renders it in scientific notation and rounds the low digits.

**Repair.** Store identifiers as text. Precision loss in an identifier is silent and permanent.

### `tabular_merged_cells`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

Merged cells store their value only on the top-left cell, so every other row reads as empty and any group-by or filter over that column drops them.

**Repair.** Unmerge and repeat the value on each row before any automated processing.

### `tabular_missing_expected_column`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

A column the caller expected is absent from the file.

**Repair.** Check the export configuration. A renamed column changes every reference to it.

### `tabular_missing_header`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

The file has no readable header row, so columns will be named positionally and every downstream reference to a column name fails.

**Repair.** Add a header row and re-export. Positional column names cannot be joined against anything.

### `tabular_missing_key`

**Severity** critical &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

The declared key column is absent, so records cannot be matched to anything and nothing downstream can be reconciled.

**Repair.** Restore the identifier, or declare what is to be used as the key in its place.

### `tabular_ragged_rows`

**Severity** high &nbsp;|&nbsp; **Class** `schema_defect` &nbsp;|&nbsp; **Confidence** high

Some rows have a different column count from the header. The surplus or missing values shift into neighbouring columns without raising an error.

**Repair.** Re-export with a consistent column count, and find the source of the unescaped delimiter before doing so.

### `tabular_sentinel_values`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

Instrument sentinel values such as -9999 are present. They are ordinary numbers and will enter a mean or a total unless excluded explicitly.

**Repair.** Record the sentinel and exclude it at read time. Treat it as missing, never as a measurement.

## Design notes

- **Why this exists**
- **Scope**
- **Design constraints**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
