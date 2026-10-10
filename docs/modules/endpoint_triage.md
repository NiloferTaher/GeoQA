# `endpoint_triage`

Endpoint resolution and dangle triage.

## Conditions emitted

### `endpoint_unresolved`

**Severity** medium &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** medium

A line endpoint could not be classified as a near miss, an orphan, a legitimate terminal or a node-continuation, so the reason it is free is unknown.

**Repair.** Supply the companion node layer and widen the search radius, then re-triage. An endpoint nobody can explain is not the same as one that is merely tolerated.

## Design notes

- **Why this exists**
- **Scale**
- **CRS handling**
- **Usage**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
