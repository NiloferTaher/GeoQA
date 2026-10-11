# `encoding`

Character encoding of delivered tabular and shapefile attribute data.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_shapefile_encoding` | Report a shapefile whose attribute encoding is undeclared or has broken. |

## Conditions emitted

### `encoding_not_declared`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

A shapefile has no .cpg sidecar, so its attribute encoding is whatever the reader guesses.

**Repair.** Write a .cpg beside the shapefile declaring the encoding the attributes were written in. Guessing is right until it is not, and the failure is silent.

### `encoding_suspect_values`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Attribute values do not survive the declared encoding, which is characteristic of a file that has been through the wrong decode at least once.

**Repair.** Recover the original bytes from the source of truth. Re-encoding an already damaged file compounds the damage rather than repairing it.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
