# Water Network Source Research

Date accessed: 2026-06-25

## Goal

Replace the synthetic Atlas water network demo with a real public line dataset when licensing and provenance are clear.

## Search Summary

### GCC official sources

- Oman open data and GIS searches did not produce a small redistributable public water utility line layer during this pass.
- UAE, Dubai, Abu Dhabi, Qatar, Bahrain, Kuwait, and Saudi Arabia searches did not produce a clearly downloadable and redistributable potable water, sewer, stormwater, or drainage line GIS layer during this pass.
- Public utility networks are often not released as line GIS because infrastructure data can be sensitive.

### India official sources

- A quick search did not identify a small legally redistributable municipal water or drainage line GeoJSON suitable for bundling in Atlas.

### OSM derived fallback

- OpenStreetMap data is available under the Open Database License.
- The HOTOSM HDX Oman waterways export provides a GeoJSON download sourced from OpenStreetMap contributors.
- The package records OpenStreetMap contributors as the dataset source and ODC ODbL as the license.
- The downloaded GeoJSON contained public waterway features including streams, rivers, canals, drains, ditches, and related water features.
- Atlas derives a compact LineString sample near Muscat from this export.

## Decision

Replace the synthetic GeoQA water demo with an OSM-derived public waterways sample.

Atlas must label the dataset as OSM-derived water and drainage lines. Do not call it official utility data or potable water mains.

## Current Demo Provenance

- Source organization: OpenStreetMap contributors via HOTOSM HDX
- Source dataset: HOTOSM Oman waterways
- Source URL: https://data.humdata.org/dataset/hotosm_omn_waterways
- License: Open Database License ODbL 1.0
- License URL: https://opendatacommons.org/licenses/odbl/1-0/
- Date accessed: 2026-06-25
- Source caveat: OpenStreetMap data is crowd sourced and completeness varies by region
- Derived sample: sixty longer LineString waterways near Muscat
- Transformation steps: downloaded the HOTOSM GeoJSON ZIP, selected LineString waterway features near Muscat, prioritized longer features for readable public demo mapping, and wrote a compact GeoJSON sample
- Redistribution: accepted as an ODbL-derived public demo sample with OSM attribution preserved in Atlas copy and docs
- Purpose: demonstrate line QA behavior including disconnected endpoints, near-miss endpoints, short segments, and delivery readiness

## Rejected Candidate Notes

- Official GCC utility line data was not accepted because no clearly redistributable public line GIS source was found in this pass.
- Earlier direct Overpass extracts were rejected because the attempted requests did not complete successfully.
- The HOTOSM HDX OSM-derived export was accepted because the source, license, download, and derived sample were verified.

## Future Acceptance Criteria

A replacement can be accepted when all of these are true.

- The data is a vector line layer.
- The license allows redistribution in this repository.
- The source organization and access date are recorded.
- The dataset is small enough for the public demo or has a small derived sample.
- The Atlas card labels the source honestly, including OSM derived wording when applicable.
