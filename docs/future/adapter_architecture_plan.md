# GeoQA Adapter Architecture Plan

## Purpose

This note defines a future implementation plan for running the same GeoQA rule logic across multiple execution environments without rewriting the rules themselves.

Core idea:

- one rule system
- one issue model
- one reporting model
- multiple adapters

This is the preferred architecture over:

- environment-specific rewrites
- AI-generated rule translations
- duplicated validation logic in GeoPandas, PostGIS, and PyQGIS codepaths

## Guiding Principle

GeoQA rules should describe **what** is being validated.

Adapters should describe **how** the data is accessed and processed in a specific environment.

That means:

- validators remain deterministic
- rule semantics stay identical
- only backend operations vary

## Target Environments

### 1. GeoPandas Adapter

Initial/default adapter.

Responsibility:

- load and expose vector data from files
- provide geometry and attribute access
- support current GeoQA runtime behavior

Status:

- effectively the current baseline backend

### 2. PostGIS Adapter

Future adapter for database-backed execution.

Responsibility:

- push filtering and spatial operations into SQL where appropriate
- preserve rule semantics from the GeoPandas version
- support large operational datasets without file export first

### 3. PyQGIS Adapter

Later adapter for QGIS-integrated execution.

Responsibility:

- operate on active QGIS layers
- expose features/fields/geometries through a stable adapter interface
- keep QGIS-specific behavior out of the rule layer

## Architecture Shape

```text
CLI / API / App
        |
      runtime
        |
   adapter chooser
        |
   adapter interface
        |
   rule execution
        |
  issues / reports / fixes
```

## Proposed Module Layout

```text
geoqa/
  adapters/
    __init__.py
    base.py
    geopandas_adapter.py
    postgis_adapter.py
    pyqgis_adapter.py
    factory.py
```

## Base Adapter Interface

Proposed direction:

```python
class GeoQADataAdapter:
    name: str

    def feature_count(self) -> int: ...
    def fields(self) -> list[str]: ...
    def crs(self): ...
    def iter_features(self): ...
    def geometry_series(self): ...
    def get_field_values(self, field_name: str): ...
    def filter_valid_geometry(self): ...
    def spatial_index(self): ...
    def explode_multipart(self): ...
    def dissolve(self, by: str): ...
    def subset(self, feature_ids): ...
```

This should remain minimal at first.

Do not design a giant abstraction layer before proving which methods rules actually need.

## Rule Design Contract

Rules must not depend directly on:

- GeoPandas-specific dataframe behavior
- raw SQL
- QGIS layer objects

Rules should depend on:

- adapter methods
- stable geometry behavior
- shared issue and report models

## Runtime Responsibilities

The runtime should:

- choose the adapter based on source type or explicit config
- pass the adapter into rule execution
- preserve the same profile/rule ordering logic
- preserve the same issue output structure

The runtime should not:

- rewrite rules per backend
- special-case every validator unless unavoidable

## AI's Role

AI should not rewrite validation logic per environment.

If AI is used at all, it should help with:

- adapter selection
- scaffolding integration code
- migration planning
- documentation

It should not decide:

- geometry semantics
- topology semantics
- rule correctness

## Phased Implementation Plan

## Phase 1: Interface Design

Goal:

- define a small adapter contract
- document which existing validators need what operations

Tasks:

- inventory current validator dependencies
- identify common geometry/attribute operations
- design `GeoQADataAdapter`
- document unsupported operations explicitly

Success condition:

- a clear adapter interface exists without changing rule semantics

## Phase 2: GeoPandas Adapter Extraction

Goal:

- wrap the existing file/GeoDataFrame path behind the adapter interface

Tasks:

- implement `GeoPandasAdapter`
- keep current behavior unchanged
- make runtime call adapter methods instead of raw dataframe assumptions where feasible

Success condition:

- current GeoQA workflows still pass while running through the adapter contract

## Phase 3: Rule Migration

Goal:

- move the most important validators onto adapter-based access

Suggested order:

1. CRS validators
2. geometry validators
3. topology validators
4. attribute validators

Tasks:

- migrate incrementally
- do not convert everything at once
- preserve existing tests

Success condition:

- a meaningful subset of validators no longer depends directly on GeoPandas internals

## Phase 4: PostGIS Adapter

Goal:

- run the same rule semantics against PostGIS-backed datasets

Tasks:

- design connection/config layer
- implement database feature access
- support spatial filtering and indexing through SQL
- match GeoPandas outputs for the same test cases

Success condition:

- selected rules produce equivalent issues across GeoPandas and PostGIS test fixtures

## Phase 5: PyQGIS Adapter

Goal:

- support QGIS-integrated operator workflows without moving rule logic into the plugin/UI layer

Tasks:

- wrap QGIS layer access
- expose stable feature iteration
- connect adapter to future QGIS-facing surfaces

Success condition:

- the same rules can be executed against a QGIS layer through the adapter contract

## Validation Strategy

The adapter architecture must be verified by equivalence testing.

For the same controlled dataset:

- GeoPandasAdapter result
- PostGISAdapter result
- PyQGISAdapter result

should match on:

- problem names
- severities
- affected features
- report summaries

Minor ordering differences may be acceptable.

Semantic differences are not.

## Risks

### 1. Over-abstraction

Risk:

- designing too many adapter methods before they are needed

Mitigation:

- start small
- expand only when a rule requires it

### 2. Performance mismatch

Risk:

- a rule that is cheap in GeoPandas may be expensive in PostGIS or vice versa

Mitigation:

- preserve semantics first
- optimize adapter implementations later

### 3. Silent rule drift

Risk:

- the same rule behaves differently across environments

Mitigation:

- require equivalence tests
- keep issue model identical

### 4. UI contamination

Risk:

- putting adapter logic into Streamlit or QGIS integration code

Mitigation:

- adapters stay in core library
- UI only calls runtime

## Explicit Non-Goals

This architecture does not mean:

- AI should translate rules automatically
- every backend must be supported immediately
- validators should be rewritten wholesale now

This is a controlled refactor path, not a broad rewrite.

## Recommended Immediate Next Step

Do not implement all adapters immediately.

Start with:

1. document current validator data dependencies
2. define a minimal adapter interface
3. extract the GeoPandas path first

That gives GeoQA a stable foundation for later PostGIS and PyQGIS support without destabilizing the engine.

## Short Positioning Statement

GeoQA should use one deterministic QA rule system across multiple GIS backends by introducing adapters, not by rewriting rule logic per environment.
