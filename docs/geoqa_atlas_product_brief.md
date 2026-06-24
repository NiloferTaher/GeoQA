# GeoQA Atlas Product Brief

GeoQA Atlas is a public WebGIS demo for the GeoQA engine.
It explains the value of deterministic geospatial QA in under five minutes through maps, issue overlays, and downloadable reports.

## Product Positioning

GeoQA is the deterministic QA layer before GIS, GeoAI, ML, analysis, publishing, or delivery.
Atlas is the visual proof layer on top of that engine.

Atlas should make a non-expert user understand three things quickly.

- Bad spatial data can pass quietly into analysis.
- GeoQA turns that risk into structured findings and reports.
- The engine remains reproducible through CLI and Python workflows.

## Audience

The first audience is GIS analysts, geospatial data engineers, utility teams, municipal data teams, and technical reviewers who receive messy vector data and need defensible QA reports.

## V1 Scope

- Vite React frontend under `apps/atlas`.
- Leaflet map viewer with static demo GeoJSON.
- Precomputed GeoQA style report JSON.
- Roads, zoning polygons, water network, and places demos.
- Run QA workflow preview with local GeoJSON map preview.
- No public arbitrary validation backend in v1.
- No Streamlit.
- No ElasticSearch.
- No rewrite of GeoQA internals.

## Demo Flow

1. Open the landing page.
2. Review the three product stats.
3. Choose a demo dataset.
4. Toggle raw, issue, and cleaned layers where available.
5. Open an issue and use Show on map.
6. Copy the GeoQA command or download the report.
7. Visit Run QA to understand the future upload workflow.

## Relationship To GeoQA

Atlas consumes GeoQA outputs.
It should not own validation rules, profile behavior, cleaning logic, or report generation contracts.
Those stay in the GeoQA Python package and CLI.

## Next Backend Step

The next production step is to connect the Run QA page to a bounded FastAPI service that calls the existing GeoQA runtime, stores generated report artifacts, and returns issue overlays for the map.
