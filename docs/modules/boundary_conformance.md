# `boundary_conformance`

Detect geometry that was cut by another layer's boundary.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_boundary_conformance` | Report features that a boundary cut, when no boundary explains it. |

## Conditions emitted

None directly. This module implements the underlying checks; the conditions it participates in are registered under the names used by the validation runtime.

## Design notes

- **The condition**
- **Provenance of the rule**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
