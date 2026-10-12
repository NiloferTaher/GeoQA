# Changelog

User-facing changes to GeoQA. Internal planning notes, test ledgers and
working documents are kept outside the repository and are not listed here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses semantic versioning.

## 0.4.0

### Added

- Spatial statistics: Moran's I, Geary's C, local Moran (LISA), Getis-Ord
  Gi*, and empirical variograms, with permutation-based inference and an
  interpretation string attached to each result. These describe the pattern
  in data the validators have already cleared, rather than shapes.
- No-code reporting outputs (`geoqa_web`): `build_site` writes an interactive
  web-GIS page, `build_slides` a presentation deck, and `save_chart_assets`
  chart definitions served to d3, Plotly or matplotlib from one definition.
- `GeoQAReport.to_table()` and `geoqa.reports.tables` flatten findings to
  CSV/Excel with WKT and centroids. Findings without geometry are kept, with
  `has_geometry = False`, rather than dropped.
- `py.typed` marker, so type checkers read the annotations the package ships
  (PEP 561).
- A `parquet` extra (`pyarrow`) for GeoParquet read/write, also included in the
  `all` extra. GeoParquet support existed but was previously undeclared.

### Changed

- The PROJ repair no longer runs at import. Importing a library must not
  mutate the process environment; the repair is now triggered lazily by the
  functions that need a CRS (`geoqa.conversion.gpd_read`,
  `geoqa.conversion.load_vector_dataset`,
  `geoqa.validation_runtime.execute_validation_plan`) or explicitly through
  `geoqa.proj_env.ensure_proj()`.
- `requirements.txt` and `requirements-dev.txt` now mirror the dependency
  sets declared in `pyproject.toml`. The Streamlit/folium stack is an extra,
  not a core dependency; it was never imported by the library itself.
- Dependencies now declare upper bounds (for example `pandas>=2,<4`,
  `shapely>=2,<3`) so a future major release does not silently break an
  install.

### Fixed

- Water-loss CARL: the m³ to L/day conversion factor was wrong, and the tests
  that encoded the old factor were updated with it.
- Validators that could not run are reported as skipped, with a reason, in the
  coverage rows instead of producing an empty result that read as "clean".
- Validation cache keys now include the threshold context, so two runs with
  different tolerances no longer share a cache entry.
- Duplicate-line detection treats a reversed-direction line as a duplicate.
- `info` findings sort below `low` findings rather than above them.
- Reference cases call the library functions rather than asserting against
  hardcoded outputs, and an end-to-end ILI case was added.
- UARL no longer defaults average pressure to 1 m; a `PressureFactor` must be
  declared.
- Confidence on a finding backed only by a default prior is marked
  uncalibrated instead of presented as calibrated.
- The preset gate counts repeated high-severity conditions only, and
  `is_genuine_likely` requires calibration.
- Robustness against newer pandas/numpy/shapely, which surfaced on CI only:
  a missing (null/NaN) geometry is skipped by repeat-incident detection instead
  of raising `AttributeError`; a missing payload cell reads as empty rather than
  as the string `"nan"`; and AI-guard redaction treats pandas 3.x string columns
  as text (`dtype == object` missed them, so they were sent unredacted).

## 0.3.0

### Added

**Hydraulic and non-revenue water**

- IWA water balance decomposition with supply and loss reconciliation.
- Night-flow module: orifice discharge, the FAVAD power law, FADD dependence and
  minimum night flow, all driven by declared coefficients.
- UARL and ILI with the IWA caveat always attached, and enforcement of the
  UARL equation's stated applicability limits.
- Published reference cases for Lambert 1999, the IWA Task Force manual and
  Lambert 2009, executable as tests or as a runtime dataset type.
- EPANET `.inp` structural, referential, unit and topological validation.
- Clip conformance with a caller-supplied majority-assignment threshold, which is
  reported alongside the result rather than fixed in the library.
- Cross-period recurrence: the same asset across periods is distinguished from
  the same place with a different asset, with period gaps made explicit.

**Imagery**

- HDF-EOS hyperspectral reader with band selection by wavelength interval,
  QA and geolocation reads, and fill masking. Built against a 426-band EMIT
  surface-reflectance granule, where a 90-band window reads 1.4 MB against
  655 MB for the whole cube.
- Cloud-optimized GeoTIFF layout checks.

**Data sources and formats**

- Archive inspection that enumerates members before extracting: zip-slip,
  decompression bombs, content-versus-extension mismatches and shapefile
  sidecar completeness.
- CSV and Excel validation, and workbook attachment validation covering
  embedded and referenced media, legibility and attribution.
- GeoPackage structural conformance helpers and a bundle writer.
- Axis-order checks across CSV, Excel, PostgreSQL and PostGIS, which report a
  genuinely ambiguous coordinate pair as ambiguous rather than guessing.
- OSM licence, version and completeness checks.
- Vertical datum, compound CRS and depth-sign checks.

**Governance**

- `geoqa.hitl`: declared, recorded release gates. `llm_involved` is a class
  constant rather than a setting, a gate proposes and a person disposes, every
  decision carries its reasons, and recall is computed rather than remembered.
- Credential detection and disclosure screening before data is sent onward.
- Hardware feasibility checks for CPU temperature, memory, disk and GPU.

### Changed

- PROJ database resolution moved to a single central repair point, so raster and
  vector paths cannot disagree about which PROJ tree is in use.
- Optional readers are imported lazily and raise a message naming the extra
  that provides them, so a missing dependency degrades one capability rather
  than breaking the package.
- Dependencies now reflect what the library imports. The Streamlit and folium
  stack moved to an optional extra; `pandas`, `numpy`, `rasterio`, `openpyxl`
  and `h5py` are declared as extras rather than being undeclared.
- Module documentation under `docs/modules/` is generated from the live
  registry by `tools/generate_module_docs.py`, so the severity and wording shown
  are the strings the validator emits. `--check` fails if a page drifts.

### Fixed

- Endpoint triage: `endpoint_unresolved` was emitted but never registered, so it
  fell back to a default severity and a generic description.
- Band selection no longer depends on index order, which differs between
  products for the same nominal band number.
- Coordinates, units, CRS, identifiers and coefficients are never silently
  repaired; ambiguity is reported as ambiguity.

## 0.2.0

### Added

- Dataset-type dispatch and profiles in the validation runtime.
- Domain packs declaring which conditions apply to which data.
- QGIS interoperability: severity QML, GeoPackage output bundles, run manifests
  and a PyQGIS recipe.
- Capability workbook generated from source rather than maintained by hand.

## 0.1.0

### Added

- Initial geometry, topology, attribute, CRS and dimension validators.
- Conservative repair operations and GeoPackage reporting.