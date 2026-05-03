# GeoQA Security Notes

This document describes the main security and safety risks relevant to GeoQA as it exists today.

It is intentionally GeoQA-specific. It is not a generic web-app checklist.

## Scope

GeoQA currently operates mainly as:
- a local Python library
- a local CLI
- a local Streamlit app
- a set of geospatial validation, conversion, and reporting workflows

Highest-priority risks:
- unsafe file handling
- malformed or hostile data inputs
- oversized or pathological datasets
- dependency issues
- accidental exposure of local paths or dataset content through logs and reports

## Current Risk Areas

### 1. File Paths and Local File Access

Relevant risks:
- path traversal or unintended file access
- opening files outside expected working areas
- treating quoted or malformed paths as valid inputs

Current mitigation direction:
- normalize and sanitize user-provided paths
- resolve paths with `pathlib.Path.resolve()`
- prefer explicit path validation instead of raw string concatenation

### 2. Malformed, Corrupt, or Hostile Geospatial Files

GeoQA processes formats such as:
- GeoJSON
- CSV
- Shapefile
- GPKG
- GeoParquet
- KML
- OSM/PBF

Relevant risks:
- corrupted files crashing loaders
- truncated downloads
- parser failures
- geometry payloads designed to trigger heavy runtime or unstable behavior
- archive-based abuse if zip handling expands further

### 3. Pathological Geometry and Resource Abuse

GeoQA is exposed to denial-of-service style behavior from:
- extremely large feature counts
- extremely dense geometries
- expensive pairwise topology checks
- repeated reruns on almost unchanged large datasets

Current mitigations already present:
- thermal guards
- chunked validation
- low-resource execution mode
- geometry-weighted adaptive chunk sizing
- validation limits for:
  - feature count
  - column count
  - source-file size
- explicit runtime limits and partial-run reporting

### 4. Input Validation and Data Integrity

GeoQA treats incoming data as untrusted until parsed and validated.

Current mitigation direction:
- validation families already exist for:
  - geometry
  - topology
  - attributes
  - CRS
  - metadata
  - accuracy
  - integrity

Important clarification:
- generic SQL injection is not central to the current GeoQA codebase because GeoQA is not currently a database product

### 5. Serialization and Deserialization

Main risks:
- malformed JSON
- unexpected structure
- excessive payload size
- unsafe assumptions about optional serialization backends

Important clarification:
- ordinary `json.loads()` is not arbitrary code execution
- the main concerns are schema validation, structure, and resource use

### 6. Logging, Reports, and Local Privacy

Reports and logs may contain:
- local paths
- feature identifiers
- geometry snippets
- schema details
- operational messages

Current mitigation direction:
- avoid logging raw dataset contents unnecessarily
- keep logs and reports purpose-specific
- keep local/private datasets anonymized in project-facing ledgers

### 7. Third-Party Dependencies

Relevant risks:
- known vulnerabilities in dependencies
- broken or partial installs
- environment drift causing misleading failures

## Current Mitigations Already Present

GeoQA already includes:
- deterministic spatial math in code rather than LLMs
- thermal guard support for hot local workflows
- chunked validation
- low-resource execution mode
- explicit partial-run reporting instead of false clean completion
- format handling that is explicit rather than fully permissive

## Gaps Still Worth Addressing

High-priority gaps:
- stronger resolved-path safety rules for local-file mode
- geometry-complexity guardrails beyond current size/count limits
- preview and upload limits that fail early and clearly
- archive/zip safety if archive support expands
- hostile-input regression tests for malformed and pathological files

Medium-priority gaps:
- explicit schema validation for more input formats
- configurable privacy levels for reports and logs
- stronger cache invalidation rules for shared/team workflows

## Responsibilities by Layer

### Library Responsibilities

GeoQA itself should:
- validate and normalize inputs
- handle malformed files safely
- provide bounded processing patterns for large datasets
- minimize accidental sensitive-data leakage in generated outputs

### App Responsibilities

The Streamlit app should:
- restrict accepted input types deliberately
- avoid misleading upload behavior
- surface actionable errors instead of raw crashes

### Environment Responsibilities

The host environment should handle:
- filesystem permissions
- encryption at rest
- network security
- endpoint protection
- user authorization in shared environments

## Recommended Near-Term Security Work

1. Add explicit path-safety helpers for local file mode.
2. Add geometry-complexity pre-checks before heavy validation starts.
3. Add dependency-audit and install-health checks to the workflow.
4. Add report/log privacy guidance for local versus shared use.
5. Add security-focused test cases for malformed files and hostile inputs.

## Final Note

GeoQA is not currently a hosted multi-tenant platform. Its most important security posture today is:
- safe local file handling
- safe parsing
- bounded heavy-data execution
- careful reporting and logging
