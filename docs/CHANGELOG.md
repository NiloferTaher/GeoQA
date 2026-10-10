# Changelog

User-facing changes to GeoQA. Internal planning notes, test ledgers and
working documents are kept outside the repository and are not listed here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses semantic versioning.

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