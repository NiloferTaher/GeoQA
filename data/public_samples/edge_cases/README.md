# GeoQA Edge-Case Samples

This folder holds small synthetic datasets for targeted integration testing that should not depend on external downloads.

Current samples:
- `self_intersection_polygon.geojson`
- `duplicate_vertex_line.geojson`

Purpose:
- keep repeatable regression cases for common geometry failures
- provide fast local fixtures for integration-style tests
- reduce dependence on public network downloads for every edge-case scenario

Planned additions:
- mismatched or missing CRS fixtures
- multipart oddities
- higher-complexity polygon fixtures
- larger synthetic stress-test inputs kept separate from the normal default run path
