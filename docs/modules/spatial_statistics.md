# `spatial_statistics`

Spatial statistics: the part of the mathematics that describes patterns rather than shapes.

## Conditions emitted

### `spatial_statistical_outlier`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A value is unusual across the whole dataset and inconsistent with the values immediately around it.

**Repair.** Check the source measurement before assuming the feature is wrong. A value that contradicts its own context is far more likely to be an error than a real value surrounded by dissimilar ones, but a genuine local anomaly will look identical and has to be excluded by the analyst.

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
