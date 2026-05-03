**DMA Plugin Analysis**

This note records the Phase 1 analysis used to convert the legacy DMA correction
scripts into additive GeoQA plugins.

## Problem Categories

- Same-name equal or nested polygons
  - Solved by the legacy same-name duplicate script.
  - Detection: normalize the DMA name, compare same-name polygon pairs, classify equal geometry or near-total containment.
  - Inputs: polygon geometry, name field, optional created/admin fields.
  - Output: duplicate/nested issue records keyed to the smaller or representative feature.
  - Edge cases preserved: name-field detection, zero-area skip, light geometry repair, best-pair de-duplication.

- Cross-name equal or nested polygons
  - Solved by the legacy cross-name duplicate script.
  - Detection: compare different normalized names, optionally within the same admin/office grouping, and classify equal or near-contained geometry.
  - Inputs: polygon geometry, name field, optional admin field.
  - Output: cross-name conflict issues with overlap fraction and name provenance.
  - Edge cases preserved: admin grouping, exact-equality fallback, nested-fraction thresholding.

- Cross-name overlap conflicts
  - Solved by the legacy overlap subtraction script.
  - Detection: compute polygon intersections across different names and classify partial overlap where the overlap is not just equality or full nesting.
  - Inputs: polygon geometry, name field, optional admin field.
  - Output: overlap issues with intersection area and relative overlap fractions.
  - Edge cases preserved: micro-overlap suppression and relation classification.

- Multipart / fragmented DMA polygons
  - Solved by the legacy multipart dissolve script.
  - Detection: explode multipart geometry and count repeated normalized names that expand into more than one polygon piece.
  - Inputs: polygon geometry, name field.
  - Output: fragmentation issues and an optional conservative dissolve fix.
  - Edge cases preserved: explode fallback and dissolve-by-largest-attribute retention.

## Reused Rule Logic

- Heuristic detection of DMA name fields
- Optional admin/office grouping
- DMA name normalization
- Light geometry repair using `buffer(0)` when needed
- Equal-geometry and near-containment checks
- Intersection-area / overlap-fraction logic
- Dissolve-by-name while retaining attributes from the largest feature

## Duplicated Logic Identified in Legacy Scripts

- Name-field discovery
- Created/admin-field discovery
- Geometry cleanup before spatial comparisons
- Pairwise intersection and containment calculations
- Normalization of inconsistent DMA names
- Dissolve/merge of same-name fragments

These patterns were centralized under `geoqa/plugins/dma/common.py` so the
individual plugins stay deterministic without re-implementing the same geometry
helpers.
