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
- Six demo datasets covering roads, zoning polygons, public administrative boundaries, public flood risk polygons, OSM water and drainage lines, and places.
- Run QA workflow preview with local GeoJSON and zipped Shapefile map preview.
- No public arbitrary validation backend in v1.
- No Streamlit.
- No ElasticSearch.
- No rewrite of GeoQA internals.

## Demo Dataset Set

- Roads / line network
- Parcels or zoning polygons
- Administrative boundaries / area polygons
- Flood zones / risk polygons
- OSM water / drainage lines
- Places or facilities points

The administrative-boundary sample uses Natural Earth Admin 1 states and provinces.
The flood-zone sample uses the Philadelphia FEMA flood plain 2023 public fixture.
The water-network sample now uses an OSM-derived HOTOSM HDX Oman waterways sample near Muscat and is labeled as public water and drainage line data, not official utility mains.

## Current Status

- Static demo gallery works with six balanced cards.
- Selected-feature issue review works through map overlays and the problem drawer.
- Runtime errors are labeled operational and are not drawn as normal defect geometries.
- Cleaned layer controls are enabled only where static cleaned output exists.
- Large zipped Shapefile previews can use the local Atlas backend when packaged in the desktop app.
- Run QA public demo mode analyzes a clearly highlighted subset of uploaded features.
- Public demo sampling is scoped only to Run QA uploads and does not affect curated dataset workspaces.
- Point uploads analyze up to twenty features.
- Line, polygon, mixed, and unknown uploads analyze up to five features.
- Dataset demo pages render the full curated demo layer and full curated issue overlay from precomputed files.
- Curated dataset pages exclude operational runtime notices from feature issue examples.
- Run QA sampling remains isolated to uploaded layers only.
- GeoQA issue overlays and selected point markers render above map labels.
- Water-network near-miss endpoint findings now show endpoint markers, gap connectors, related feature ids, distances, and tolerances.
- Show on map for near-miss endpoint findings focuses the endpoint gap rather than the whole line.
- Repeated issue examples are grouped by affected feature while total finding counts remain unchanged.
- Duplicate geometry findings now include row comparison context and coordinate summaries in the issue drawer.
- Run notes now include selected layer context and suggestions for utility layer context.
- Cleaned preview toggles require meaningful visible cleaned geometry output.
- Coordinate precision, spatial index, CRS, and metadata findings do not imply visible cleaned geometry.
- Run QA issue browsing now shows the selected issue beside the map.
- Layer-level Run QA findings focus the analyzed layer context instead of showing a disconnected no-location warning.
- The water network demo now uses a verified OSM-derived HOTOSM HDX Oman waterways sample with ODbL attribution.
- The full uploaded preview remains visible as muted context when safe.
- Run QA map legend rows toggle raw preview, analyzed subset, and issue overlay visibility without rerunning validation.
- Issue cards and top issue type rows focus the map on the first spatial issue, with analyzed feature geometry used as the fallback location.
- Sampled Run QA results use exact issue count copy and label subset runs as `demo sample`.
- Malformed sampled coordinates are handled before validation so Atlas shows a product level error instead of a raw Python type message.
- Atlas uses a single default readable dark CARTO basemap with optional deployment overrides.
- The CPU temperature card is local developer-only and hidden from public users by default.
- Atlas is idle-safe by default. Landing and gallery routes load metadata only, map code is lazy-loaded, cleaned layers load only when requested, and Run QA does not parse uploads or call backend validation before user action.
- Atlas shows GitHub and LinkedIn in the top navigation and keeps a compact footer with maintainer and copyright text.
- GeoQA Python remains the validation source of truth.

## Demo Flow

1. Open the landing page.
2. Review the three product stats.
3. Choose a demo dataset.
4. Toggle raw, issue, and cleaned layers where available.
5. Open an issue and use Show on map.
6. Copy the GeoQA command or download the report.
7. Visit Run QA to understand the future upload workflow.
8. Confirm how many uploaded features were analyzed by GeoQA before reading sampled results.

## Relationship To GeoQA

Atlas consumes GeoQA outputs.
It should not own validation rules, profile behavior, cleaning logic, or report generation contracts.
Those stay in the GeoQA Python package and CLI.

## Next Backend Step

The next production step is to connect the Run QA page to a bounded FastAPI service that calls the existing GeoQA runtime, stores generated report artifacts, and returns issue overlays for the map.
