# Public Sample Datasets

Downloaded on 2026-03-18 for GeoQA integration and real-dataset testing.

## Natural Earth
- Source: https://www.naturalearthdata.com/
- Files:
  - ne_110m_admin_0_countries.zip
  - ne_110m_populated_places.zip
  - ne_10m_admin_1_states_provinces.zip
  - ne_10m_roads.zip
  - ne_10m_lakes.zip
  - extracted shapefile folders for both datasets

Additional notes:
- `ne_10m_admin_1_states_provinces` provides a larger admin-boundary polygon dataset.
- `ne_10m_roads` provides a larger global line/network-style dataset.
- `ne_10m_lakes` provides a moderate physical/environment-style polygon dataset.

## Derived Local Formats

- `derived/ne_10m_admin_1_states_provinces.gpkg`
  - locally converted from the Natural Earth admin-1 shapefile
  - used to extend format-coverage testing to GeoPackage

## Data.gov / Philadelphia Open Data
- FEMA Flood Plain 2023 GeoJSON
  - Catalog: https://catalog.data.gov/dataset/fema-flood-plain
  - Download: https://hub.arcgis.com/api/v3/datasets/16fe94b76e49481dae55702b2a8d671a_0/downloads/data?format=geojson&spatialRefId=4326&where=1%3D1
- Zoning Base Districts GeoJSON
  - Download: https://opendata.arcgis.com/datasets/0bdb0b5f13774c03abf8dc2f1aa01693_0.geojson

## OpenStreetMap
- Source: https://www.openstreetmap.org/
- API extract:
  - https://api.openstreetmap.org/api/0.6/map?bbox=-74.012,40.707,-74.009,40.709
- Notes:
  - This is a small raw OSM XML extract around Lower Manhattan for roads/buildings/network-style experiments.
