# GeoQA Integration Results

This folder contains outputs from the real-dataset integration passes run on 2026-03-18.

## Datasets Used

- Natural Earth admin-0 countries shapefile
- Natural Earth admin-1 states/provinces shapefile
- Natural Earth admin-1 states/provinces GeoPackage
- Natural Earth lakes shapefile
- Natural Earth roads shapefile
- Philadelphia FEMA Flood Plain 2023 GeoJSON
- Philadelphia zoning base districts GeoJSON
- Private local test shapefiles used only for internal verification
- These local datasets are intentionally anonymized in project-facing documentation

## Generated Outputs

- `integration_summary.json`
- `integration_summary_expanded_safe.json`
- `integration_summary_roads.json`
- `training_data_inventory.json`
- `training_data_summary.json`
- `natural_earth_countries_issues.json`
- `natural_earth_countries_agent.json`
- `natural_earth_countries_crs.json`
- `natural_earth_admin1_issues.json`
- `natural_earth_admin1_agent.json`
- `natural_earth_admin1_gpkg_crs.json`
- `natural_earth_lakes_issues.json`
- `natural_earth_lakes_agent.json`
- `natural_earth_roads_issues.json`
- `natural_earth_roads_agent.json`
- `philly_floodplain_issues.json`
- `philly_floodplain_agent.json`
- `philly_zoning_issues.json`
- `philly_zoning_agent.json`
- private local-run artifacts

## Notes

- The Natural Earth generic validation run completed successfully.
- The larger Natural Earth admin-1 generic validation run completed successfully.
- CRS automation against a derived Natural Earth admin-1 GeoPackage completed successfully with no CRS issues.
- The Natural Earth lakes generic validation run completed successfully, but the post-run cooldown path engaged after a hotter phase.
- The larger Natural Earth roads generic validation run completed and wrote reports, but the geometry-validation phase also recorded a structured thermal-limit message after the CPU reached 77 C.
- The Philadelphia flood-zone run completed successfully.
- The Philadelphia zoning run completed, but the geometry-validation step recorded a structured thermal-limit message after the CPU reached 79 C. The workflow still wrote reports instead of crashing.
- CRS automation against the Natural Earth countries sample completed successfully with no CRS issues detected.
- A private local integration pass completed against four internal layers.
- The large private line-network run completed successfully and reported `17` self-intersection issues across `35,223` features.
- The large private point-asset run completed successfully with a valid null result across `60,047` features.
- The private polygon validation runs completed successfully and reported repeated coordinate-precision findings plus a spatial-index integrity finding.
