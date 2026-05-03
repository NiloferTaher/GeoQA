# GeoQA Agent Instructions

These instructions define how coding assistants should work when modifying or generating code for the GeoQA library.

## Version

2026-03-18

## Scope

Apply these rules to work performed inside this GeoQA project.

`codex_prompt.md` in the project root is the canonical prompt file for Codex-assisted GeoQA tasks. When there is prompt-related guidance to reuse directly, prefer `codex_prompt.md` as the primary source.
Substantive project changes should be recorded in `journal.md` with the reasoning behind the change, not just the outcome.

## Core Rules

1. All new code must respect thermal safety.
   - Use `ThermalGuard` and `ThermalRunner` for CPU-intensive loops.
   - Run optional thermal diagnostics at script startup via `GeoQAScriptBase`.
   - On platforms without temperature sensors, explain why readings may be unavailable and suggest alternatives.

2. Code must remain cross-platform.
   - Windows + Core Temp is preferred when available.
   - Fall back to `psutil` for Windows, macOS, and Linux.
   - Avoid import-time errors on non-Windows platforms.

3. Python version must be 3.12 or higher.
   - If the current machine uses a higher version, code should still work.

4. Code style must follow existing GeoQA patterns.
   - Use type hints consistently.
   - Use docstrings consistently.
   - Avoid printing directly unless `emit_thermal_diagnostic=True`.

## Task Behavior

When asked to add or modify GeoQA code:

- Generate or modify the requested GeoQA library code as specified.
- Keep compatibility with existing `ThermalGuard`, `ThermalRunner`, and `GeoQAScriptBase` workflows unless a change is explicitly requested.
- Use [codex_prompt.md](/g:/My%20Drive/Python-G-drive/GeoQA/codex_prompt.md) as the canonical prompt reference for GeoQA task framing and coding expectations.
- Record meaningful project changes in [journal.md](/g:/My%20Drive/Python-G-drive/GeoQA/journal.md), including why the change was made.
- At the end of the task, offer to update this `AGENTS.md` file if new rules or patterns were introduced.
- Ask exactly: `Do you want to update AGENTS.md with these changes? (yes/no)`
- If the answer is yes, append the new rules under a clearly marked section.

## Input Template

```text
{describe what code you want to add or modify, e.g., new GeoQA script base, validator, runner improvements, etc.}
```

## Expected Output

- The updated code block(s) in full, ready to insert into the library.
- Optional `AGENTS.md` update snippet if the user chooses yes.

## Reference Example

Use the startup diagnostic flag when quieter script execution is needed:

```python
from geoqa import GeoQAScriptBase


class MyScript(GeoQAScriptBase[str, str]):
    def load_items(self) -> list[str]:
        return ["a"]

    def process_item(self, item: str) -> str:
        return item.upper()


MyScript(emit_thermal_diagnostic=False).run()
```

## Future Rules

<!-- New rules introduced by tasks can be appended here -->

## 2026-03-18 Validation Engine Rules

- Reuse `geoqa.validations.base.ValidationIssue` as the standard issue object for validation results.
- New validation modules should return lists of `ValidationIssue` objects rather than ad hoc dicts or tuples.
- Prefer extending `geoqa/validations/` by theme, such as `geometry`, `attributes`, `crs`, `topology`, or `metadata`.
- When adding user-facing validation workflows, prefer `GeoQAScriptBase` or the existing thermal-safe execution patterns instead of standalone unconstrained loops.
- Report writing should go through reusable report utilities such as `geoqa.reports.report_generator` where practical.
- Optional GIS dependencies such as Shapely or GeoPandas should not break importability of the package; import them lazily or guard them where needed.

## 2026-03-18 Thermal Hardening Rules

- Treat GeoQA thermal control as cooperative risk reduction, not a hard physical guarantee.
- Prefer conservative thermal defaults for local workstation safety; do not loosen thermal thresholds casually.
- For heat-sensitive local workflows, prefer `ThermalGuard.cool()` or `ThermalGuard.strict()` over custom looser guards.
- When building new long-running workflows, keep work chunked into smaller guarded steps instead of one large CPU-bound block.
- Prefer passing an explicit guard into user-facing scripts when the workflow is expected to run heavy GIS operations for a long time.
- If changing thermal behavior, update `README.md`, `SKILLS.md`, and `journal.md` so the operational expectations stay aligned with the implementation.
- If changing thermal behavior in a user-visible way, also update `docs/CHANGELOG.md`.

## 2026-03-18 Agent and Validation Completion Rules

- GeoQA now has first-class validation modules for `geometry`, `topology`, `attributes`, `crs`, `metadata`, `accuracy`, and `integrity`; prefer extending those modules before inventing new one-off validation locations.
- Keep `geoqa.interactive_validation` as the generic validation-family entry point and `geoqa.agent` as the dataset-type and fix-review workflow entry point.
- Prefer explicit dataset type selection as the primary control path; schema-based inference is secondary support only.
- Reusable fix helpers belong in `geoqa.fixes` so users can import them in their own scripts.
- Built-in auto-fixes should remain conservative unless a new fix is demonstrably low-risk and well-tested.
- When adding new fixable issue types, update:
  - `SUPPORTED_FIXES` in `geoqa.agent`
  - user-facing import snippets
  - fix-review tests
  - documentation and journal entries
- Convenience wrappers in `geoqa.agent` should stay aligned:
  - `run_agent_workflow(...)`
  - `validate_dataset(...)`
  - `apply_fixes_interactively(...)`
  - `generate_final_report(...)`

## 2026-03-18 Auditability and Extension Rules

- Agent workflows should preserve auditability by keeping issue reporting, final reporting, and optional fix-action logging consistent.
- When fix actions are materially important for review or signoff, prefer writing a separate fix log via `fix_log_path`.
- Validator failures that arise from bad inputs, missing dependencies, or unsupported dataset structures should be captured as structured issues or messages when practical rather than crashing the whole workflow.
- Optional AI or recommendation behavior should enter through hook-style extension points, not by hardwiring model dependencies into the validation core.
- PyQGIS helpers should remain import-safe and expose both low-level conversion helpers and prompt-friendly convenience wrappers where useful.

## 2026-03-18 Structural Wrapper Rules

- The primary implementation remains in the core modules, such as:
  - `geoqa/validations`
  - `geoqa/agent.py`
  - `geoqa/fixes.py`
  - `geoqa/interactive_validation.py`
  - `geoai/serialization.py`
- Wrapper packages such as `geoqa/agents`, `geoqa/automation`, `geoqa/interactive`, `geoqa/fix`, and `geoqa/serialization` should delegate to the core implementation rather than reimplementing logic.
- When adding new user-facing entry points, prefer thin wrappers that call the tested core modules.
- If the wrapper layout changes, keep `README.md`, `SKILLS.md`, `plan_of_action.md`, and `journal.md` aligned with the new structure.
- If the wrapper layout changes in a user-visible way, also update `docs/CHANGELOG.md`.

## 2026-03-18 Changelog Maintenance Rules

- `journal.md` remains the internal development history with reasoning.
- `docs/CHANGELOG.md` is the public-facing summary of notable user-visible changes.
- When behavior, structure, workflows, or public APIs change in a way users would care about, update both:
  - `journal.md`
  - `docs/CHANGELOG.md`

## 2026-03-18 Testing Infrastructure Rules

- Keep repeatable public-sample integration runs in `scripts/run_integration_samples.py` rather than scattering one-off commands across notes or ad hoc scripts.
- Prefer low-risk verification profiles first when checking new test infrastructure on a heat-sensitive machine.
- Integration-run summaries should capture practical execution metadata when available, including:
  - duration
  - dataset size
  - feature count
  - geometry mix
  - thermal snapshot
- Small synthetic regression fixtures belong in `data/public_samples/edge_cases/`.
- Prefer synthetic edge-case fixtures for common geometry regressions before relying on large external downloads.
- When testing infrastructure or test assets change, update:
  - `docs/tests.md`
  - `journal.md`
  - `docs/CHANGELOG.md`

## 2026-03-18 Hybrid Execution Rules

- Treat CRS transformation, coordinate math, geometry validity checks, and direct topology predicates as deterministic code tasks, not AI tasks.
- Never use LLMs for coordinate reprojection, geometry-repair math, or other numeric spatial transformations that should be handled by `pyproj`, `shapely`, `geopandas`, or equivalent deterministic tooling.
- Prefer a three-level execution model:
  - Level 0: deterministic code for geometry, CRS, topology, and direct data checks
  - Level 1: light AI for semantic labeling, attribute normalization, and concise summaries
  - Level 2: heavier AI only for ambiguous reasoning, repair planning, or multi-step workflow suggestions
- When the machine is thermally constrained, prefer continuing Level 0 work and defer Level 2 work rather than pushing heavy reasoning through a hot system.
- AI in GeoQA should stay in the reasoning and recommendation layer unless a future task explicitly introduces a tightly bounded and well-tested exception.

## 2026-03-18 Conversion and UI Rules

- Keep format conversion and basic geometry-cleaning logic in deterministic library code, not inside the Streamlit UI itself.
- Prefer `geoqa/conversion.py` for vector-format loading/export helpers and keep the Streamlit app as a thin composition layer over tested library functions.
- Basic geometry-fix workflows exposed in the UI should remain conservative and deterministic:
  - drop null geometries
  - remove duplicate vertices
  - repair invalid polygonal geometry where possible
- Do not present raster conversion as a fully supported GeoQA core feature until a real raster-processing layer exists in code and tests.
- When user-facing local app capabilities change, update:
  - `README.md`
  - `docs/user_guide.md`
  - `docs/tests.md`
  - `journal.md`
  - `docs/CHANGELOG.md`

## 2026-03-18 Onboarding Documentation Rules

- Keep first-time-user onboarding lightweight and deterministic before introducing broader workflows.
- Prefer small onboarding assets such as:
  - `docs/START_HERE.md`
  - `examples/geoqa_quickstart.ipynb`
- Quickstart materials should demonstrate one complete path with minimal heat and dependency risk:
  - load a local sample
  - run one validator or lightweight workflow
  - write one report
  - inspect one output
- When onboarding assets change in a user-visible way, update:
  - `README.md`
  - `docs/user_guide.md`
  - `plan_of_action.md`
  - `journal.md`
  - `docs/CHANGELOG.md`

## 2026-03-18 Large-Dataset Validation Rules

- Prefer chunked validation over one long monolithic validation pass when datasets are large enough to create heat or responsiveness concerns.
- Use agent-level chunking controls rather than inventing a separate large-dataset workflow when the goal is still standard validation:
  - `validation_chunk_size`
  - `sleep_between_validation_chunks_seconds`
- Keep chunking conservative:
  - run full-layer checks only where chunking would change correctness
  - use chunking primarily for row-local or feature-local validation work
- When a normal validation run hits thermal or runtime pressure in interactive mode, prefer offering a one-time chunked rerun with suggested settings rather than silently switching behavior.
- When large-dataset handling changes in a user-visible way, update:
  - `README.md`
  - `SKILLS.md`
  - `docs/tests.md`
  - `plan_of_action.md`
  - `journal.md`
  - `docs/CHANGELOG.md`
