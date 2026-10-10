# `accuracy`

## Conditions emitted

### `coordinate_precision_not_fit_for_use`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** low

Coordinate precision is stored at an inappropriate level for the intended analysis or delivery format, either bloating output or truncating meaningful detail. Diagnose by reviewing driver precision settings and align export precision with use-case tolerances.

**Repair.** Adjust export precision or snap coordinates to an appropriate grid before delivery.

### `inappropriate_xy_tolerance`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** low

XY tolerance is configured too aggressively or inconsistently, causing nearby coordinates to collapse or be treated as identical. Diagnose by checking spatial reference defaults and avoid overriding XY tolerance unless there is a justified need.

**Repair.** Restore a safer XY tolerance and rerun topology or overlay operations.

### `positional_accuracy_exceeds_reference_tolerance`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

Feature locations deviate from a trusted reference layer beyond the accepted positional accuracy threshold. Diagnose by comparing to a known reference and measuring circular or linear error before accepting the dataset.

**Repair.** Compare to a trusted reference and redigitize or adjust features that exceed the accepted offset threshold.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
