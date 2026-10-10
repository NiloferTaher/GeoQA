# `osm`

OpenStreetMap: the failure modes that come with the format's own nature.

## Entry points

| Function | Purpose |
| --- | --- |
| `validate_osm` | Report the OSM-specific conditions a structural check would miss. |

## Conditions emitted

### `osm_attribution_absent`

**Severity** high &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No licence or attribution field accompanies OSM-derived data. The Open Database License requires attribution and share-alike for derived databases, so extracting the geometry and discarding the attribution is a licence breach rather than a metadata omission.

**Repair.** Carry the licence and attribution through to the derived dataset, and record the extract date. No structural check can detect this, which is why it is reported here.

### `osm_completeness_unknown`

**Severity** info &nbsp;|&nbsp; **Class** `evidence_condition` &nbsp;|&nbsp; **Confidence** high

OSM carries no completeness measure, so a missing feature cannot be distinguished from one that was never mapped. Coverage is uneven between places and between feature types, and every derived result inherits that limitation.

**Repair.** No repair is possible by validation. Record the limitation alongside any result, and corroborate findings against a second source where completeness matters.

### `osm_single_ring_with_holes`

**Severity** medium &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** medium

A feature that may contain holes is represented by a single ring, so any holes are filled rather than excluded.

**Repair.** Use a multipolygon relation where inner rings exist. A courtyard inside a building footprint is the common case.

### `osm_unclosed_area`

**Severity** high &nbsp;|&nbsp; **Class** `data_issue` &nbsp;|&nbsp; **Confidence** high

A feature tagged as an area has geometry that is not closed. In OSM an area is an emergent property of ways and relations rather than a stored polygon, so a ring that does not close will not render, and renderers differ in what they substitute.

**Repair.** Resolve the way or relation. If the data is exported as polygons, close the rings during export rather than relying on the renderer.

### `osm_version_metadata_absent`

**Severity** medium &nbsp;|&nbsp; **Class** `governance_gap` &nbsp;|&nbsp; **Confidence** high

No version, timestamp or changeset field accompanies the data, so a row cannot be tied to a point in the OSM history.

**Repair.** Carry version, timestamp and changeset through. This matters more for OSM than for a curated export because the data is edited continuously by many people, and a disputed edit cannot be contested without them.

## Design notes

- **Why OSM needs its own conditions**
- **What is deliberately not here**
- **Provenance**

---

Generated from the live registry by `tools/generate_module_docs.py`. Do not edit by hand; the severity and wording here are the strings the validator actually emits.
