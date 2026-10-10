# `payload_columns`

Detect structured payloads stored in columns declared as scalar text.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_payload_columns` | Report columns that hold a serialised structure despite a scalar text type. |

## Conditions emitted

None directly. This module implements the underlying checks; the conditions it participates in are registered under the names used by the validation runtime.

## Design notes

- **Why this exists**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
