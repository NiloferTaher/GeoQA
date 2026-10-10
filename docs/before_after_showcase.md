# Before / After Showcase

This is the simplest public GeoQA showcase in the repository.

It uses the existing public sample:
- `data/public_samples/edge_cases/duplicate_vertex_line.geojson`

The point of this example is not scale. The point is clarity:
- one known issue
- one deterministic fix path
- one clean exported output

## Why This Matters

Typical desktop GIS cleanup is often:
- inspect manually
- repair manually
- rerun manually
- hope nothing else changed

GeoQA turns that into:
- validate
- inspect a structured report
- apply conservative fixes
- export the cleaned result

## The Workflow

```python
import geoqa

report = geoqa.validate(
    "data/public_samples/edge_cases/duplicate_vertex_line.geojson",
    profile="geometry",
)

print(report.summary)

cleaned = report.clean()
cleaned.export("data/integration_results/duplicate_vertex_line_cleaned.geojson")
```

## Observed Result

This flow was verified in the repository:

- before cleaning:
  - profile: `geometry`
  - issue count: `1`
  - issue type: `duplicate_vertex`
- after conservative cleaning and export:
  - profile: `geometry`
  - issue count: `0`

## What Changed

GeoQA used the existing conservative geometry-fix path:
- remove duplicate consecutive vertices
- preserve the rest of the workflow structure

This is intentionally modest.
It is a QA-and-cleaning loop, not automatic semantic reconstruction.

## What This Showcase Proves

- GeoQA can detect a real geometry issue on public sample data
- GeoQA can return a structured report object
- GeoQA can apply a conservative deterministic clean
- GeoQA can export the cleaned result
- GeoQA can reduce the issue count in a reproducible way

## What It Does Not Prove

- large-scale throughput
- domain-specific utility semantics
- hydraulic or network simulation
- full automatic correction of complex data defects

For the heavier constrained-machine benchmark story, see:
- [benchmark_story.md](benchmark_story.md)
