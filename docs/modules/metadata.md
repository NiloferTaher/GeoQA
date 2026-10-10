# `metadata`

## Conditions emitted

### `missing_metadata_extent`

**Severity** low &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

The metadata omits the geographic extent needed to communicate where the dataset applies.

**Repair.** Add the geographic extent or bounding box to metadata from the dataset footprint.

### `missing_metadata_lineage`

**Severity** low &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

The metadata does not explain source inputs and processing history used to build the dataset.

**Repair.** Document source inputs and process steps in the metadata lineage section.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
