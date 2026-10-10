# GeoQA Plan of Action

## Version

- Date: 2026-03-20
- Status: Active

## Product Direction

GeoQA is a deterministic geospatial QA engine.

Primary order of importance:
1. engine correctness
2. runtime reliability on constrained hardware
3. calibrated reporting
4. CLI usability
5. secondary app shell

Architecture to preserve:

```text
CLI -> runtime -> validators -> reports
```

Current architectural rule:
- freeze surface-area growth unless it improves performance, calibration, bug-fixing, or reporting clarity
- no new UI-first features
- no speculative new packs unless they materially deepen an existing core operator path
- keep future-only design notes under `docs/future/` so shipped guidance stays separate from speculative architecture work

## Current Shipped Core

Implemented today:
- validation families for:
  - geometry
  - topology
  - attributes
  - CRS
  - metadata
  - accuracy
  - integrity
- profile-driven execution
- problem and profile registries
- CLI commands for:
  - `validate`
  - `profiles`
  - `convert`
  - `report`
  - `benchmark`
- JSON and CSV reports
- runtime controls for:
  - chunking
  - thermal profiles
  - bounded parallelism
  - file-backed cache reuse
  - validation limits
  - runtime budgets
  - low-resource mode
  - cost-aware validator ordering for constrained runs
- partial-run reporting with:
  - execution status
  - execution reason
  - validator coverage
  - operator next-step hints
- domain packs for:
  - water network
  - boundaries
  - land use

## Current Strongest Areas

- deterministic validation core
- CLI-first operator path
- water-network pack
- runtime honesty under heat/runtime pressure
- test and benchmark ledgers
- one heavier public low-resource success case on Natural Earth roads

## Current Partial Areas

- adaptive runtime on the heaviest datasets
- validator signal calibration for noisy precision-style findings
- deeper water-network semantics beyond deterministic linework/connectivity QA
- deeper domain semantics beyond first pack slices
- richer runtime throughput prediction
- broader format support
- GIS desktop integrations

## Phase 1: Immediate Stability and Scale

Priority:
- highest

Focus:
- finish heavy-run reliability
- strengthen low-resource operation
- keep partial-run behavior honest and useful
- add CI quality gates

Concrete targets:
- convert remaining heavy public and private line reruns from partial to successful where feasible
- improve throughput on the heaviest datasets, not just thermal survival
- expand cost-based scheduling and indexing where it matters most
- add an explicit best-effort plugin execution mode for constrained runs:
  - proposed flag/option: `run_plugins_on_partial=True`
  - allowed only when the layer loaded successfully and the stop reason is runtime, thermal, or budget related
  - disallowed for invalid-input and hard-limit failures
  - must be reported clearly in the execution summary as partial core validation plus best-effort plugin coverage
- add lightweight CI for:
  - unit suite
  - runtime suite
  - CLI smoke
  - one public sample smoke path
- keep low-resource mode as a first-class operator path

## Phase 2: Enterprise and Standards

Focus:
- security hardening
- standards alignment
- cache maturity

Concrete targets:
- ISO 19157-oriented mapping and export options
- hostile-input regression tests
- stronger geometry-complexity guards
- safer cache invalidation strategy for repeated team workflows

## Phase 3: GeoAI Maturity

Focus:
- prove downstream usefulness without mixing AI into deterministic spatial math

Concrete targets:
- end-to-end ML prep demo
- active-learning loop from validated corrections
- optional semantic suggestions outside geometry correctness logic

## Phase 4: Ecosystem and Integration

Focus:
- broader interoperability after the engine is boringly reliable

Concrete targets:
- broader format support
- QGIS integration
- optional distributed runtime path
- ArcGIS work only as a contributor-facing later track

Important note:
- ArcGIS integration remains later-stage because it cannot be verified in the current environment.

## What Is Already No Longer Just Roadmap

These are real, not theoretical:
- geometry-weighted adaptive chunking
- cost-aware validator ordering for constrained runs
- low-resource CLI mode
- priority scoring
- actionable vs informational reporting
- profile downgrades and suppressions
- water-network quick / strict / audit profiles
- CRS-aware / scale-aware precision tuning
- structured partial-run summaries

## Immediate Next Technical Work

1. Throughput improvement on the heaviest line and polygon runs
2. Better severity/threshold tuning for noisy validators
3. Explicit best-effort plugin execution on partial runtime stops
4. CI quality gates
5. Security hardening around hostile inputs and archive safety

Explicit non-priorities for the next pass:
- UI expansion
- random new validators without calibration need
- broad new domain-pack expansion before the current flagship pack is deeper

## Guardrails

- Do not move business logic into CLI or Streamlit
- Do not imply full support where only first slices exist
- Do not broaden sideways before Phase 1 is genuinely stronger
- Prefer honest partial execution over fragile full-run claims
