# GeoQA Python function and script inventory

This reference catalogs Python source in `geoqa/`, `geoqa_web/`, `geoai/`, `scripts/`, `tools/`, `examples/`, and the root `streamlit_app.py`. It includes module-level functions, class methods, and nested functions; tests and backup folders are not included.

Descriptions come from source docstrings when available. `Undocumented` means that the definition has no docstring in the current source; its name and location are listed rather than guessing its behavior. Module purposes without docstrings are inferred from their package and file names. This is an index, not a substitute for the implementation or API contracts.

## Quick orientation

- `geoqa/validations/` contains the dataset validators. The [`docs/modules/`](modules/) directory has registry-generated condition references for many validators.
- `geoqa/cli/` and `geoqa/__main__.py` implement the command-line interface; install the package and run `geoqa --help`, or use `python -m geoqa --help` from the project environment.
- `scripts/` contains repository workflows and verification utilities; see each script's `--help` (when supported) or its `main()` function before running it.
- `examples/` contains sample library usage, while `streamlit_app.py` is the optional Streamlit front end.
- `geoqa_web/` and `geoai/` provide optional presentation and GeoAI integration utilities.

## Runnable scripts and examples

| File | Purpose |
|---|---|
| `geoqa/__main__.py` | Enables `python -m geoqa` command-line use. |
| `scripts/annotate_geoqa_scripts.py` | Recursively scans a chosen directory and adds a GeoQA script header to Python files that subclass `GeoQAScriptBase`. It modifies matching files. |
| `scripts/run_evidence_suite.py` | Runs validation cases declared in a manifest, verifies results, logs evidence, and can compare against a baseline. |
| `scripts/run_integration_samples.py` | Runs GeoQA validation profiles against configured integration sample data and summarizes the results. |
| `scripts/validate_problem_catalog.py` | Checks the problem catalog for required fields, allowed categories and severities, non-empty text, and duplicate names. |
| `scripts/verify_chunking_equivalence.py` | Demonstrates whether chunked validation with a declared halo reproduces whole-layer results and what changes when the halo is removed. |
| `tools/build_capability_workbook.py` | Builds an Excel capability workbook from the live problem registry, validator functions, modules, and profiles. |
| `tools/generate_module_docs.py` | Generates registry-based Markdown reference pages under `docs/modules/`; `--check` checks whether generated pages are up to date. |
| `examples/basic_usage.py` | Shows validation, scoring, ML-row output, expected-CRS checks, and geometry expectations on a sample dataset. |
| `examples/before_after_cleaning.py` | Shows a `generic_quick` validation, conservative score, cleaning, and export workflow. |
| `examples/story_geoai_prep.py` | Shows validation and ML-ready score/export, with a fix step when the score is below its threshold. |
| `examples/thermal_guard_demo.py` | Runs a sample `GeoQAScriptBase` workflow with thermal monitoring and writes a thermal-guard log. |
| `streamlit_app.py` | Starts the optional Streamlit interface for interactive local use. |

## Source inventory

### [`examples/basic_usage.py`](../examples/basic_usage.py)

Runnable usage example.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `main` | function | 6 | Undocumented |

### [`examples/before_after_cleaning.py`](../examples/before_after_cleaning.py)

Runnable usage example.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `main` | function | 6 | Undocumented |

### [`examples/story_geoai_prep.py`](../examples/story_geoai_prep.py)

Runnable usage example.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `main` | function | 6 | Undocumented |

### [`examples/thermal_guard_demo.py`](../examples/thermal_guard_demo.py)

Runnable usage example.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DemoScript` | class | 9 | Undocumented |
| `DemoScript.__init__` | function | 10 | Undocumented |
| `DemoScript.load_items` | function | 13 | Undocumented |
| `DemoScript.process_item` | function | 16 | Undocumented |
| `DemoScript.before_step` | function | 21 | Undocumented |
| `DemoScript.after_step` | function | 24 | Undocumented |
| `main` | function | 28 | Undocumented |

### [`geoai/__init__.py`](../geoai/__init__.py)

GeoAI optional integrations and serialization helpers.

No functions or classes are defined in this file.

### [`geoai/jax_layer/__init__.py`](../geoai/jax_layer/__init__.py)

GeoAI integration and serialization utilities.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_backend` | function | 14 | Configure the numerical backend. |
| `backend_name` | function | 42 | Return the active numerical backend name. |
| `jax_available` | function | 47 | Return True when JAX is the active backend. |
| `get_array_module` | function | 52 | Return the active array module (`jax.numpy` or `numpy`). |
| `as_array` | function | 57 | Convert values into an array using the active backend. |
| `to_numpy` | function | 62 | Convert backend arrays to a NumPy array. |
| `pairwise_squared_distances` | function | 67 | Compute pairwise squared distances using the active backend. |
| `stable_softmax` | function | 80 | Compute a numerically stable softmax using the active backend. |

### [`geoai/qgis_layer/__init__.py`](../geoai/qgis_layer/__init__.py)

GeoAI integration and serialization utilities.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `is_pyqgis_available` | function | 18 | Return True when PyQGIS is importable in the current environment. |
| `_ensure_geojson_dict` | function | 23 | Undocumented |
| `geometry_to_geojson` | function | 36 | Convert a QGIS geometry or GeoJSON-compatible object into a GeoJSON dict. |
| `geometry_to_coordinate_array` | function | 49 | Return the GeoJSON `coordinates` payload for a geometry-like object. |
| `feature_to_record` | function | 55 | Convert a QGIS-like feature into a GeoJSON Feature dict. |
| `layer_to_feature_dicts` | function | 104 | Convert a QGIS-like layer into a list of GeoJSON Feature dicts. |
| `convert_qgis_layer_to_geojson` | function | 119 | Convert a QGIS-like layer into a GeoJSON FeatureCollection dict. |

### [`geoai/serialization.py`](../geoai/serialization.py)

GeoAI integration and serialization utilities.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_ToonBackend` | class | 8 | Undocumented |
| `_ToonBackend.dumps` | function | 9 | Undocumented |
| `_ToonBackend.loads` | function | 11 | Undocumented |
| `_coerce_backend` | function | 17 | Undocumented |
| `_load_toon_backend` | function | 25 | Undocumented |
| `is_toon_available` | function | 40 | Return True when an optional TOON backend is available. |
| `available_formats` | function | 45 | Return the supported format names. |
| `_json_dump` | function | 55 | Undocumented |
| `_json_load` | function | 59 | Undocumented |
| `serialize` | function | 63 | Serialize an object to JSON or TOON. |
| `deserialize` | function | 82 | Deserialize an object from JSON or TOON. |

### [`geoqa/__init__.py`](../geoqa/__init__.py)

GeoQA public package surface.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `__getattr__` | function | 53 | Undocumented |
| `__dir__` | function | 63 | Undocumented |

### [`geoqa/__main__.py`](../geoqa/__main__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/agent.py`](../geoqa/agent.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `FixSuggestion` | class | 54 | Undocumented |
| `FixAction` | class | 62 | Undocumented |
| `AgentRunResult` | class | 74 | Undocumented |
| `AgentRunResult.to_dict` | function | 86 | Undocumented |
| `_missing_input_handler` | function | 107 | Undocumented |
| `_resolve_input_func` | function | 114 | Undocumented |
| `_validation_runtime_issue` | function | 118 | Undocumented |
| `_safe_extend` | function | 129 | Undocumented |
| `_geometry_preview` | function | 145 | Undocumented |
| `_slice_layer` | function | 164 | Undocumented |
| `_slice_weighted_chunk` | function | 172 | Undocumented |
| `_iter_batches` | function | 195 | Undocumented |
| `_geometry_vertex_count` | function | 210 | Undocumented |
| `_estimate_total_vertices` | function | 237 | Undocumented |
| `_iter_weighted_batches` | function | 250 | Undocumented |
| `_iter_validation_batches` | function | 283 | Undocumented |
| `_concat_layers` | function | 295 | Undocumented |
| `_pause_between_validation_chunks` | function | 315 | Undocumented |
| `_adaptive_chunk_settings` | function | 330 | Undocumented |
| `_build_fix_preview` | function | 375 | Undocumented |
| `_suggest_validation_chunk_settings` | function | 398 | Undocumented |
| `_build_chunking_recommendation` | function | 415 | Undocumented |
| `_append_fix_log` | function | 443 | Undocumented |
| `get_dataset_type` | function | 454 | Prompt the user to select a dataset type. |
| `infer_dataset_type` | function | 466 | Infer a likely dataset type using lightweight column-name heuristics. |
| `normalize_dataset_type` | function | 480 | Resolve a user-supplied dataset type or infer one from the layer. |
| `_existing_fields` | function | 492 | Undocumented |
| `_run_geometry_checks` | function | 497 | Undocumented |
| `_validate_layer_for_dataset_type_chunked` | function | 509 | Undocumented |
| `_validate_layer_for_dataset_type_chunked.<locals>.next_chunk` | function | 533 | Undocumented |
| `_validate_layer_for_dataset_type_chunked.<locals>.finish_chunk` | function | 540 | Undocumented |
| `validate_layer_for_dataset_type` | function | 652 | Run the validation set associated with the requested dataset type. |
| `get_fix_suggestion` | function | 741 | Return a fix suggestion for a validation issue. |
| `suggest_fixes` | function | 759 | Return one fix suggestion per distinct problem name. |
| `_apply_fix` | function | 767 | Undocumented |
| `review_fixes_on_sample` | function | 784 | Review auto-fix candidates on a sample subset. |
| `apply_approved_fixes` | function | 840 | Apply approved fixes to the full layer. |
| `generate_agent_report` | function | 867 | Write an agent-oriented combined report with both issues and fix actions. |
| `fix_import_snippets` | function | 941 | Return reusable import snippets for supported fix helpers. |
| `_load_dataset` | function | 949 | Undocumented |
| `run_agent_workflow` | function | 962 | Run validation, optional sample-first fix review, and combined reporting. |
| `validate_dataset` | function | 1125 | Convenience validation-only entry point for dataset workflows. |
| `apply_fixes_interactively` | function | 1162 | Review supported fixes on a sample subset and optionally apply approved fixes to the full layer. |
| `generate_final_report` | function | 1202 | Convenience wrapper for writing the final agent issue/fix report. |
| `GeoQAAgentScript` | class | 1213 | Thermal-safe GeoQA agent entry point for dataset validation workflows. |
| `GeoQAAgentScript.__init__` | function | 1216 | Undocumented |
| `GeoQAAgentScript.load_items` | function | 1263 | Undocumented |
| `GeoQAAgentScript.process_item` | function | 1266 | Undocumented |
| `main` | function | 1293 | Undocumented |

### [`geoqa/agents/__init__.py`](../geoqa/agents/__init__.py)

Agent-oriented GeoQA scripts and wrappers.

No functions or classes are defined in this file.

### [`geoqa/agents/agentic_crsfix.py`](../geoqa/agents/agentic_crsfix.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `agentic_crsfix` | function | 6 | Reproject a layer when its CRS does not match the requested CRS. |

### [`geoqa/ai_guard.py`](../geoqa/ai_guard.py)

Guardrails for anything sent to a language model.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `RedactionPolicy` | class | 70 | What may leave, and what must be replaced. |
| `RedactionPolicy.placeholder_for` | function | 92 | Undocumented |
| `RedactionFinding` | class | 97 | One redaction or refusal, with the location and nothing of the value. |
| `RedactionFinding.as_dict` | function | 106 | Undocumented |
| `RedactionResult` | class | 117 | The safe payload, plus an account of what was taken out of it. |
| `RedactionResult.blocked` | function | 124 | Undocumented |
| `RedactionResult.clean` | function | 128 | Nothing was redacted and nothing blocked. |
| `RedactionResult.redacted_count` | function | 133 | Undocumented |
| `RedactionResult.summary` | function | 136 | Undocumented |
| `_is_sensitive_column` | function | 148 | Which sensitive class a column name belongs to, if any. |
| `_issue` | function | 159 | Undocumented |
| `_redact_literal` | function | 170 | Undocumented |
| `keep_hint` | function | 177 | Should a leading/trailing hint be kept for this value? |
| `redact_text` | function | 191 | Make a block of text safe to send. |
| `redact_mapping` | function | 254 | Redact a mapping, dropping columns the policy names. |
| `redact_frame` | function | 307 | Redact a tabular dataset before it leaves the process. |
| `redact_issues` | function | 369 | Redact validation issues before they are summarised by a model. |
| `validate_ai_disclosure` | function | 396 | Report what would be disclosed by sending ``payload`` unchanged. |
| `AiSubmissionGuard` | class | 500 | Context manager that redacts on the way in and reports on the way out. |
| `AiSubmissionGuard.__init__` | function | 512 | Undocumented |
| `AiSubmissionGuard.__enter__` | function | 517 | Undocumented |
| `AiSubmissionGuard.__exit__` | function | 520 | Undocumented |
| `AiSubmissionGuard.__call__` | function | 523 | Undocumented |
| `AiSubmissionGuard.safe` | function | 542 | Undocumented |
| `AiSubmissionGuard.summary` | function | 545 | Undocumented |

### [`geoqa/api.py`](../geoqa/api.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_max_severity` | function | 23 | Undocumented |
| `_infer_export_format` | function | 34 | Undocumented |
| `GeoQAFixedLayer` | class | 52 | Conservative fixed-layer wrapper returned by ``GeoQAReport.fix()``. |
| `GeoQAFixedLayer.export` | function | 58 | Undocumented |
| `GeoQAReport` | class | 64 | User-facing validation result wrapper. |
| `GeoQAReport.__getattr__` | function | 74 | Undocumented |
| `GeoQAReport.summary` | function | 78 | Validation summary dictionary. |
| `GeoQAReport.issues` | function | 83 | Validation issues detected for the dataset. |
| `GeoQAReport.suppressed_issues` | function | 88 | Issues suppressed by the selected profile. |
| `GeoQAReport.score` | function | 92 | Return a normalized quality score for this report. |
| `GeoQAReport.to_geojson` | function | 109 | Return errors-only GeoJSON for direct use in a web map. |
| `GeoQAReport.to_ml` | function | 119 | Return issue rows in a simple ML-friendly feature format. |
| `GeoQAReport.to_dataframe` | function | 123 | Return the issues as a pandas DataFrame. |
| `GeoQAReport.to_table` | function | 131 | Write findings to a ``.csv`` or ``.xlsx`` table for analysis. |
| `GeoQAReport.export` | function | 141 | Export the report issues using the standard GeoQA report writer. |
| `GeoQAReport.fix` | function | 160 | Apply conservative deterministic fixes to the source dataset. |
| `GeoQAReport.clean` | function | 176 | Alias for ``fix()`` for users who think in terms of data cleaning. |
| `GeoQAReport.to_dict` | function | 180 | Return the full execution result as a dictionary. |
| `GeoQAReport.__repr__` | function | 184 | Undocumented |
| `validate` | function | 191 | Validate a dataset with a named GeoQA profile. |
| `score` | function | 214 | Return a simple normalized GeoQA quality score for a dataset. |

### [`geoqa/audit_archive.py`](../geoqa/audit_archive.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `LayerInventory` | class | 26 | Undocumented |
| `AuditArchiveResult` | class | 46 | Undocumented |
| `_slug` | function | 59 | Undocumented |
| `_safe_crs` | function | 65 | Undocumented |
| `_safe_bbox` | function | 75 | Undocumented |
| `_geometry_type` | function | 83 | Undocumented |
| `_load_layer` | function | 93 | Undocumented |
| `_recommend_profile` | function | 103 | Undocumented |
| `_existing_profile_name` | function | 121 | Undocumented |
| `_inventory_layer` | function | 133 | Undocumented |
| `discover_layers` | function | 161 | Undocumented |
| `_selected_layers` | function | 234 | Undocumented |
| `_issue_rows` | function | 245 | Undocumented |
| `_plain_summary` | function | 266 | Undocumented |
| `_write_summary_text` | function | 286 | Undocumented |
| `_write_summary_pdf` | function | 291 | Undocumented |
| `_write_summary_pdf.<locals>.escape_pdf_text` | function | 299 | Undocumented |
| `_cell_value` | function | 340 | Undocumented |
| `_append_dict_rows` | function | 346 | Undocumented |
| `_style_workbook` | function | 352 | Undocumented |
| `write_excel_report` | function | 382 | Undocumented |
| `run_audit_archive` | function | 603 | Undocumented |

### [`geoqa/automation/__init__.py`](../geoqa/automation/__init__.py)

Automated non-interactive GeoQA workflow wrappers.

No functions or classes are defined in this file.

### [`geoqa/automation/crs_validation.py`](../geoqa/automation/crs_validation.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `crs_validation` | function | 11 | Validate CRS state for a dataset and optionally reproject it to the expected CRS. |

### [`geoqa/chunking.py`](../geoqa/chunking.py)

Spatial chunking that does not manufacture topology breaks.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `Tile` | class | 112 | One cell of the tiling grid, before the halo is applied. |
| `Tile.extent` | function | 119 | Undocumented |
| `ChunkPlan` | class | 124 | What chunking would do, and why. |
| `ChunkPlan.tile_count` | function | 141 | Undocumented |
| `ChunkPlan.would_partition` | function | 145 | True when the plan actually splits the layer into more than one pass. |
| `ChunkPlan.to_dict` | function | 149 | Undocumented |
| `_vertex_count` | function | 161 | Undocumented |
| `plan_tiles` | function | 176 | Propose a tiling for ``layer``. |
| `_side_for_budget` | function | 269 | Choose a grid side so the average tile holds about ``budget`` vertices. |
| `select_chunk` | function | 300 | Return the features of ``layer`` that belong to ``tile``. |
| `_select_by_intersection` | function | 318 | Undocumented |
| `_dedupe_key` | function | 331 | Undocumented |
| `run_chunked_validation` | function | 335 | Run ``validators`` over ``layer``, tiling only what is safe to tile. |
| `chunk_safety_report` | function | 424 | Partition validator names by what chunking may do to them. |

### [`geoqa/cli/__init__.py`](../geoqa/cli/__init__.py)

CLI package for GeoQA.

No functions or classes are defined in this file.

### [`geoqa/cli/commands/__init__.py`](../geoqa/cli/commands/__init__.py)

CLI command modules for GeoQA.

No functions or classes are defined in this file.

### [`geoqa/cli/commands/_common.py`](../geoqa/cli/commands/_common.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_limits` | function | 11 | Undocumented |
| `build_cache` | function | 17 | Undocumented |
| `thermal_guard_name` | function | 23 | Undocumented |
| `progress_printer` | function | 34 | Undocumented |
| `progress_printer.<locals>.emit` | function | 38 | Undocumented |
| `progress_printer_with_interval` | function | 55 | Undocumented |
| `progress_printer_with_interval.<locals>.emit` | function | 61 | Undocumented |
| `apply_low_resource_defaults` | function | 72 | Undocumented |

### [`geoqa/cli/commands/audit_archive.py`](../geoqa/cli/commands/audit_archive.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_load_expected_crs_config` | function | 10 | Undocumented |
| `configure_parser` | function | 31 | Undocumented |
| `run` | function | 50 | Undocumented |

### [`geoqa/cli/commands/benchmark.py`](../geoqa/cli/commands/benchmark.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_parser` | function | 12 | Undocumented |
| `run` | function | 34 | Undocumented |

### [`geoqa/cli/commands/convert.py`](../geoqa/cli/commands/convert.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_parser` | function | 8 | Undocumented |
| `run` | function | 17 | Undocumented |

### [`geoqa/cli/commands/profiles.py`](../geoqa/cli/commands/profiles.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_parser` | function | 9 | Undocumented |
| `run_list` | function | 23 | Undocumented |
| `run_show` | function | 47 | Undocumented |

### [`geoqa/cli/commands/report.py`](../geoqa/cli/commands/report.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_parser` | function | 9 | Undocumented |
| `run_summarize` | function | 24 | Undocumented |
| `run_stats` | function | 33 | Undocumented |

### [`geoqa/cli/commands/validate.py`](../geoqa/cli/commands/validate.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `configure_parser` | function | 12 | Undocumented |
| `run` | function | 37 | Undocumented |

### [`geoqa/cli/main.py`](../geoqa/cli/main.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_parser` | function | 8 | Undocumented |
| `run` | function | 21 | Undocumented |

### [`geoqa/confidence.py`](../geoqa/confidence.py)

How much to believe a finding.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `Evidence` | class | 86 | One observation, and how much it moves the odds. |
| `Evidence.to_dict` | function | 94 | Undocumented |
| `ConfidenceResult` | class | 104 | A finding's reliability, with the reasoning attached. |
| `ConfidenceResult.is_genuine_likely` | function | 118 | Undocumented |
| `ConfidenceResult.to_dict` | function | 121 | Undocumented |
| `confidence_band` | function | 136 | Name the band, so a number is not left to be interpreted by eye. |
| `_margin_evidence` | function | 167 | Undocumented |
| `_class_evidence` | function | 240 | Undocumented |
| `_corroboration_evidence` | function | 265 | Undocumented |
| `_prior_key` | function | 316 | Base-rate group for a condition, or None when it cannot be determined. |
| `assess_finding` | function | 335 | Assess one finding, returning the reasoning alongside the number. |
| `assess_findings` | function | 423 | Assess a batch, most credible first. |
| `calibration_report` | function | 438 | Compare predicted confidence against observed outcomes. |

### [`geoqa/conversion.py`](../geoqa/conversion.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ArchiveSafetyLimits` | class | 15 | Undocumented |
| `_load_geopandas` | function | 21 | Undocumented |
| `_guess_coordinate_columns` | function | 29 | Undocumented |
| `_guess_geometry_column` | function | 56 | Undocumented |
| `_validate_zip_member_name` | function | 64 | Undocumented |
| `_scan_zip_archive` | function | 70 | Undocumented |
| `_extract_zip_archive` | function | 100 | Undocumented |
| `_resolve_extracted_dataset` | function | 108 | Undocumented |
| `_load_las_like_dataset` | function | 142 | Undocumented |
| `list_vector_layers` | function | 164 | Undocumented |
| `vector_layer_feature_counts` | function | 190 | Return the feature count for every readable layer. |
| `_layer_has_features` | function | 211 | Cheaply check whether a layer holds any feature (reads a single row). |
| `default_vector_layer_name` | function | 221 | Pick the most useful default layer. |
| `load_all_vector_layers` | function | 264 | Load every layer of a multi-layer source as ``{layer_name: GeoDataFrame}``. |
| `gpd_read` | function | 296 | Thin geopandas.read_file wrapper so multi-layer reads stay in one place. |
| `load_vector_dataset` | function | 304 | Load a vector dataset from common local formats. |
| `convert_vector_dataset` | function | 418 | Convert a local vector dataset into another supported output format. |
| `export_vector_layer` | function | 441 | Export a loaded vector layer to a supported output format. |
| `save_uploaded_file` | function | 493 | Persist a Streamlit-uploaded file to a temporary local path. |
| `save_uploaded_files` | function | 503 | Persist multiple uploaded files into one temporary directory. |
| `resolve_uploaded_dataset` | function | 515 | Resolve one or more uploaded files into a local dataset path. |
| `layer_preview_geojson` | function | 550 | Return a small GeoJSON preview string for map display. |
| `table_preview_frame` | function | 559 | Return a Streamlit-friendly preview frame with geometry converted to WKT. |
| `summarize_vector_layer` | function | 579 | Return a small metadata summary for UI display. |

### [`geoqa/dispatch.py`](../geoqa/dispatch.py)

Decide which checks apply to a layer, and say so.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `LAYER_PROFILE` | class | 92 | What a layer is, measured rather than declared. |
| `LAYER_PROFILE.is_mixed_family` | function | 104 | Undocumented |
| `LAYER_PROFILE.to_dict` | function | 108 | Undocumented |
| `_vertex_count` | function | 121 | Undocumented |
| `inspect_layer` | function | 151 | Measure a layer: family, size, CRS. No judgement, no thresholds. |
| `ValidationPlan` | class | 188 | What will run, what will not, and why. |
| `ValidationPlan.vertex_count` | function | 201 | Undocumented |
| `ValidationPlan.to_dict` | function | 204 | Undocumented |
| `build_plan` | function | 217 | Inspect ``layer`` and return what applies to it. |
| `validate_plan` | function | 319 | Report anything about the plan the caller should know before running. |

### [`geoqa/execution.py`](../geoqa/execution.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_NoOpThermalGuard` | class | 27 | Undocumented |
| `_NoOpThermalGuard.wait_until_safe` | function | 28 | Undocumented |
| `ValidationExecutionResult` | class | 33 | Undocumented |
| `ValidationExecutionResult.to_dict` | function | 54 | Undocumented |
| `_resolve_thermal_guard` | function | 79 | Undocumented |
| `_load_layer` | function | 92 | Undocumented |
| `_existing_fields` | function | 100 | Undocumented |
| `_family_context` | function | 105 | Undocumented |
| `_apply_profile_policies` | function | 125 | Undocumented |
| `_progress_callback_for_family` | function | 189 | Undocumented |
| `_progress_callback_for_family.<locals>.wrapped` | function | 196 | Undocumented |
| `_execution_status_from_reason` | function | 217 | Undocumented |
| `_operator_next_steps` | function | 235 | Undocumented |
| `_pack_summary` | function | 265 | Undocumented |
| `_run_plugins` | function | 274 | Undocumented |
| `validate_dataset_with_profile` | function | 293 | Undocumented |

### [`geoqa/expect/__init__.py`](../geoqa/expect/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/expect/core.py`](../geoqa/expect/core.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ExpectationResult` | class | 12 | Small list-like wrapper for expectation results. |
| `ExpectationResult.count` | function | 15 | Undocumented |
| `_load_layer` | function | 19 | Undocumented |
| `_run_expectation` | function | 23 | Undocumented |
| `valid_crs` | function | 44 | Return CRS-related issues for a dataset. |
| `no_null_geometry` | function | 54 | Return null-geometry issues for a dataset. |
| `no_self_intersections` | function | 63 | Return self-intersection issues for a dataset. |
| `_GeometryExpectNamespace` | class | 72 | Expectation helpers for geometry-focused checks. |
| `_GeometryExpectNamespace.valid` | function | 75 | Undocumented |
| `_GeometryExpectNamespace.clean` | function | 82 | Undocumented |
| `_GeometryExpectNamespace.no_nulls` | function | 85 | Undocumented |
| `_GeometryExpectNamespace.no_self_intersections` | function | 88 | Undocumented |
| `_TopologyExpectNamespace` | class | 92 | Expectation helpers for same-layer topology cleanliness. |
| `_TopologyExpectNamespace.clean` | function | 95 | Undocumented |
| `_TopologyExpectNamespace.connected` | function | 106 | Undocumented |
| `_AttributesExpectNamespace` | class | 119 | Expectation helpers for attribute completeness and uniqueness. |
| `_AttributesExpectNamespace.complete` | function | 122 | Undocumented |
| `_AttributesExpectNamespace.unique` | function | 130 | Undocumented |
| `_CrsExpectNamespace` | class | 139 | Expectation helpers for CRS validity. |
| `_CrsExpectNamespace.valid` | function | 142 | Undocumented |
| `GeoQACheck` | class | 146 | Fluent expectation helper for lightweight GeoQA assertions. |
| `GeoQACheck.__init__` | function | 149 | Undocumented |
| `GeoQACheck.crs` | function | 152 | Undocumented |
| `GeoQACheck.null_geometry` | function | 155 | Undocumented |
| `GeoQACheck.self_intersections` | function | 158 | Undocumented |
| `GeoQACheck.geometry` | function | 161 | Undocumented |
| `GeoQACheck.topology` | function | 164 | Undocumented |
| `check` | function | 168 | Return a fluent checker for a dataset. |

### [`geoqa/fix/__init__.py`](../geoqa/fix/__init__.py)

Fix-function wrappers for GeoQA cleanup helpers.

No functions or classes are defined in this file.

### [`geoqa/fixes.py`](../geoqa/fixes.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `RepairProfile` | class | 10 | Undocumented |
| `register_custom_repair` | function | 20 | Undocumented |
| `clear_custom_repairs` | function | 27 | Undocumented |
| `list_custom_repairs` | function | 31 | Undocumented |
| `drop_null_geometries` | function | 35 | Return a copy of the layer without rows whose geometry is null. |
| `_dedupe_consecutive_coordinates` | function | 43 | Undocumented |
| `_dedupe_geometry` | function | 53 | Undocumented |
| `remove_duplicate_vertices` | function | 95 | Return a copy of the layer with duplicate consecutive geometry vertices removed. |
| `_make_geometry_valid` | function | 106 | Undocumented |
| `make_geometries_valid` | function | 131 | Return a copy of the layer with polygonal self-intersections or invalidity repaired where possible. |
| `apply_basic_geometry_fixes` | function | 142 | Apply a conservative deterministic geometry-cleaning sequence. |
| `apply_repair_plan` | function | 167 | Apply built-in and registered custom repairs in a predictable order. |

### [`geoqa/gpkg.py`](../geoqa/gpkg.py)

GeoPackage structure, inspection and writing.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 93 | Undocumented |
| `_connect_readonly` | function | 104 | Open a GeoPackage without any possibility of writing to it. |
| `GpkgLayer` | class | 111 | One feature table registered in ``gpkg_contents``. |
| `GpkgLayer.is_vector` | function | 135 | Undocumented |
| `GpkgLayer.is_tiled` | function | 139 | Undocumented |
| `GpkgLayer.extent` | function | 143 | Undocumented |
| `GpkgLayer.as_dict` | function | 148 | Undocumented |
| `GpkgProfile` | class | 166 | What a GeoPackage is, structurally. |
| `GpkgProfile.is_geopackage` | function | 178 | Undocumented |
| `GpkgProfile.specification` | function | 182 | Undocumented |
| `GpkgProfile.vector_layers` | function | 186 | Undocumented |
| `GpkgProfile.layer_names` | function | 190 | Undocumented |
| `GpkgProfile.as_dict` | function | 193 | Undocumented |
| `_table_names` | function | 206 | Undocumented |
| `_srs_lookup` | function | 213 | Undocumented |
| `_has_spatial_index` | function | 223 | Undocumented |
| `_table_columns` | function | 236 | Undocumented |
| `_count_rows` | function | 244 | Undocumented |
| `profile_gpkg` | function | 251 | Inspect a GeoPackage structurally. Never writes. |
| `list_gpkg_layers` | function | 339 | Names of the layers a GeoPackage declares. |
| `validate_gpkg` | function | 344 | Report structural nonconformance in a GeoPackage. |
| `_primary_keys` | function | 521 | Undocumented |
| `read_gpkg_layer` | function | 534 | Read one layer out of a GeoPackage as a GeoDataFrame. |
| `write_gpkg_bundle` | function | 541 | Write several layers into one GeoPackage with a manifest beside it. |

### [`geoqa/hardware.py`](../geoqa/hardware.py)

Hardware reality, and whether a GIS operation should be attempted on this machine.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 64 | Undocumented |
| `_import_psutil` | function | 75 | Undocumented |
| `CpuInfo` | class | 84 | Processor identity, and what it is currently doing. |
| `CpuInfo.clock_ratio` | function | 99 | Undocumented |
| `CpuInfo.as_dict` | function | 104 | Undocumented |
| `MemoryInfo` | class | 119 | Undocumented |
| `MemoryInfo.as_dict` | function | 124 | Undocumented |
| `DiskInfo` | class | 133 | Undocumented |
| `DiskInfo.as_dict` | function | 139 | Undocumented |
| `GpuInfo` | class | 149 | Graphics hardware, where a driver will report it. |
| `GpuInfo.as_dict` | function | 157 | Undocumented |
| `HardwareProfile` | class | 167 | What this machine can currently do. |
| `HardwareProfile.max_temperature_c` | function | 183 | Undocumented |
| `HardwareProfile.as_dict` | function | 186 | Undocumented |
| `_read_windows_wmi_temperatures` | function | 205 | LibreHardwareMonitor, then the ACPI thermal zone. |
| `_read_linux_hwmon_temperatures` | function | 245 | Read ``/sys/class/hwmon`` directly. |
| `_read_nvidia_smi_temperatures` | function | 282 | GPU temperature, where NVIDIA's driver exposes it. |
| `_read_core_temperature` | function | 304 | Best available core temperature, and why not when there is none. |
| `_profile_cpu` | function | 389 | Undocumented |
| `_profile_memory` | function | 435 | Undocumented |
| `_profile_disk` | function | 449 | Undocumented |
| `_profile_gpu` | function | 463 | Undocumented |
| `profile_hardware` | function | 492 | Measure this machine. Fast, non-blocking, and safe to call anywhere. |
| `validate_operation_feasible` | function | 514 | Report whether this machine can carry out a described operation. |
| `sensor_report` | function | 618 | Which temperature source answered, and what to do when none did. |

### [`geoqa/hitl.py`](../geoqa/hitl.py)

Human-in-the-loop governance gates.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_severity_rank` | function | 60 | Undocumented |
| `GateSpec` | class | 65 | One declared condition that can stop a run. |
| `GateSpec.evaluate` | function | 82 | Undocumented |
| `at_least` | function | 86 | Predicate: any issue at or above a severity, optionally name-filtered. |
| `at_least.<locals>.predicate` | function | 91 | Undocumented |
| `any_of` | function | 102 | Predicate: any occurrence of the named conditions. |
| `any_of.<locals>.predicate` | function | 106 | Undocumented |
| `count_at_least` | function | 116 | Predicate: fires once a condition occurs at least ``threshold`` times. |
| `count_at_least.<locals>.predicate` | function | 124 | Undocumented |
| `Decision` | class | 136 | One gate outcome, with everything needed to audit it later. |
| `Decision.halts` | function | 156 | Undocumented |
| `Decision.is_held` | function | 160 | Undocumented |
| `Decision.is_deterministic` | function | 164 | Undocumented |
| `Decision.hold` | function | 167 | Record a human hold on a halting decision. |
| `Decision.expect` | function | 178 | Record what this case was expected to decide. |
| `Decision.as_dict` | function | 190 | Undocumented |
| `RecallReport` | class | 211 | How a gate performed against known expectations. |
| `RecallReport.accuracy` | function | 224 | Undocumented |
| `RecallReport.halt_recall` | function | 228 | Of the cases that should have halted, how many did? |
| `RecallReport.false_halt_rate` | function | 233 | Of the cases that should have proceeded, how many halted anyway? |
| `RecallReport.as_dict` | function | 237 | Undocumented |
| `Gate` | class | 253 | A declared set of stop conditions. |
| `Gate.__init__` | function | 265 | Undocumented |
| `Gate.add` | function | 272 | Undocumented |
| `Gate.evaluate` | function | 276 | Run every declared gate and return one decision. |
| `Gate.evaluate_and_record` | function | 308 | Evaluate and append to the gate's own audit trail. |
| `Gate.record` | function | 319 | Undocumented |
| `Gate.recall` | function | 323 | Score the recorded decisions against their expectations. |
| `Gate.to_json` | function | 347 | Write the full audit trail: declarations, decisions and recall. |
| `Gate.__len__` | function | 373 | Undocumented |
| `_issue_summary` | function | 377 | Undocumented |
| `preset_gate` | function | 396 | A starting gate, declared rather than hidden. |

### [`geoqa/interactive/__init__.py`](../geoqa/interactive/__init__.py)

Interactive validation wrappers.

No functions or classes are defined in this file.

### [`geoqa/interactive/validation.py`](../geoqa/interactive/validation.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/interactive_validation.py`](../geoqa/interactive_validation.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `InteractiveValidationScript` | class | 18 | Interactive GeoQA validation entry point for dataset-level workflows. |
| `InteractiveValidationScript.__init__` | function | 21 | Undocumented |
| `InteractiveValidationScript.load_items` | function | 69 | Undocumented |
| `InteractiveValidationScript.process_item` | function | 72 | Undocumented |
| `validate_layer` | function | 110 | Route validation based on the requested dataset type. |
| `validate_dataset` | function | 168 | Convenience wrapper for interactive dataset validation. |
| `main` | function | 220 | Undocumented |

### [`geoqa/ml/__init__.py`](../geoqa/ml/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/ml/annotations.py`](../geoqa/ml/annotations.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_severity_rank` | function | 16 | Undocumented |
| `issue_summary_by_feature` | function | 22 | Group validation issues by feature id into a compact ML-friendly summary. |
| `quality_score_from_issues` | function | 57 | Return a simple normalized quality score from 0.0 to 1.0. |
| `_copy_layer` | function | 74 | Undocumented |
| `annotate_layer_with_issues` | function | 80 | Add quality-annotation columns to a tabular or GeoDataFrame-like layer. |
| `annotate_layer_with_issues.<locals>.feature_summary` | function | 103 | Undocumented |

### [`geoqa/ml/exports.py`](../geoqa/ml/exports.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_json_safe` | function | 13 | Undocumented |
| `export_annotated_dataset` | function | 30 | Export an issue-annotated dataset in a training-friendly format. |
| `export_issue_features` | function | 79 | Export issue-derived ML feature rows. |

### [`geoqa/ml/features.py`](../geoqa/ml/features.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_issue_feature_rows` | function | 10 | Convert validation issues into model-friendly feature rows. |
| `build_quality_feature_frame` | function | 27 | Return an annotated layer with additional aggregate quality feature columns. |

### [`geoqa/packs/__init__.py`](../geoqa/packs/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/packs/boundaries/__init__.py`](../geoqa/packs/boundaries/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/packs/boundaries/profile.py`](../geoqa/packs/boundaries/profile.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_families` | function | 11 | Undocumented |
| `_build_profile` | function | 50 | Undocumented |
| `build_boundaries_quick_profile` | function | 60 | Undocumented |
| `build_boundaries_strict_profile` | function | 68 | Undocumented |
| `build_boundaries_audit_profile` | function | 76 | Undocumented |
| `build_boundaries_profile` | function | 84 | Undocumented |

### [`geoqa/packs/boundaries/rules.py`](../geoqa/packs/boundaries/rules.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_boundaries_context` | function | 8 | Undocumented |
| `boundaries_problem_policies` | function | 16 | Undocumented |

### [`geoqa/packs/boundaries/thresholds.py`](../geoqa/packs/boundaries/thresholds.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `BoundaryThresholds` | class | 7 | Undocumented |
| `default_boundary_thresholds` | function | 12 | Undocumented |

### [`geoqa/packs/domains.py`](../geoqa/packs/domains.py)

Domain packs: which conditions apply to which kind of data.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `Pack` | class | 45 | A named set of requirements for one kind of data. |
| `Pack.gate` | function | 63 | A governance gate for this pack. |
| `Pack.as_dict` | function | 91 | Undocumented |
| `list_packs` | function | 286 | Undocumented |
| `get_pack` | function | 290 | Fetch a pack by name. |
| `pack_gate` | function | 300 | The governance gate for a named pack. |
| `pack_report` | function | 305 | Every pack, for the capability workbook and for documentation. |

### [`geoqa/packs/land_use/__init__.py`](../geoqa/packs/land_use/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/packs/land_use/profile.py`](../geoqa/packs/land_use/profile.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_families` | function | 11 | Undocumented |
| `_build_profile` | function | 43 | Undocumented |
| `build_land_use_quick_profile` | function | 53 | Undocumented |
| `build_land_use_strict_profile` | function | 61 | Undocumented |
| `build_land_use_audit_profile` | function | 69 | Undocumented |
| `build_land_use_profile` | function | 77 | Undocumented |

### [`geoqa/packs/land_use/rules.py`](../geoqa/packs/land_use/rules.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_land_use_context` | function | 8 | Undocumented |
| `land_use_problem_policies` | function | 18 | Undocumented |

### [`geoqa/packs/land_use/thresholds.py`](../geoqa/packs/land_use/thresholds.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `LandUseThresholds` | class | 7 | Undocumented |
| `default_land_use_thresholds` | function | 11 | Undocumented |

### [`geoqa/packs/water_network/__init__.py`](../geoqa/packs/water_network/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/packs/water_network/profile.py`](../geoqa/packs/water_network/profile.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_families` | function | 11 | Undocumented |
| `_build_profile` | function | 69 | Undocumented |
| `build_water_network_quick_profile` | function | 79 | Undocumented |
| `build_water_network_strict_profile` | function | 87 | Undocumented |
| `build_water_network_audit_profile` | function | 95 | Undocumented |
| `build_water_network_profile` | function | 103 | Undocumented |

### [`geoqa/packs/water_network/rules.py`](../geoqa/packs/water_network/rules.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_water_network_context` | function | 10 | Undocumented |
| `_linear_endpoint_pair` | function | 36 | Undocumented |
| `_linear_endpoint_pair.<locals>._coords` | function | 40 | Undocumented |
| `_normalize_endpoint` | function | 75 | Undocumented |
| `summarize_water_network_layer` | function | 83 | Undocumented |
| `_base_problem_policies` | function | 177 | Undocumented |
| `water_network_problem_policies` | function | 248 | Undocumented |

### [`geoqa/packs/water_network/schema.py`](../geoqa/packs/water_network/schema.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `WaterNetworkSchemaHints` | class | 8 | Undocumented |
| `WaterNetworkSchemaHints.required_fields` | function | 19 | Undocumented |
| `WaterNetworkSchemaHints.unique_field` | function | 23 | Undocumented |
| `_first_existing` | function | 27 | Undocumented |
| `detect_water_network_schema` | function | 34 | Undocumented |

### [`geoqa/packs/water_network/thresholds.py`](../geoqa/packs/water_network/thresholds.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_positive_number` | function | 7 | Undocumented |
| `WaterNetworkThresholds` | class | 12 | Undocumented |
| `default_water_network_thresholds` | function | 42 | Undocumented |

### [`geoqa/plugins/__init__.py`](../geoqa/plugins/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/plugins/base.py`](../geoqa/plugins/base.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `GeoQAPlugin` | class | 10 | Minimal plugin contract for additive domain- or client-specific rules. |
| `GeoQAPlugin.applies_to` | function | 24 | Return ``True`` when this plugin should run for the supplied layer. |
| `GeoQAPlugin.validate` | function | 28 | Return additional deterministic validation issues for the supplied layer. |
| `GeoQAPlugin.fix` | function | 32 | Apply an optional conservative cleanup and return the updated layer. |

### [`geoqa/plugins/dma/__init__.py`](../geoqa/plugins/dma/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/plugins/dma/common.py`](../geoqa/plugins/dma/common.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DmaLayerHints` | class | 29 | Undocumented |
| `_normalize_column_match` | function | 37 | Undocumented |
| `_first_regex_column` | function | 46 | Undocumented |
| `detect_dma_layer_hints` | function | 55 | Undocumented |
| `_is_polygon_layer` | function | 88 | Undocumented |
| `normalize_dma_key` | function | 102 | Undocumented |
| `safe_geometry` | function | 111 | Undocumented |
| `equalsish` | function | 124 | Undocumented |
| `overlap_fraction` | function | 138 | Undocumented |
| `pick_best_index` | function | 149 | Undocumented |
| `row_value` | function | 156 | Undocumented |
| `dissolve_by_normalized_name` | function | 165 | Undocumented |

### [`geoqa/plugins/dma/dma_cross_name_nested.py`](../geoqa/plugins/dma/dma_cross_name_nested.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DmaCrossNameNestedPlugin` | class | 19 | Undocumented |
| `DmaCrossNameNestedPlugin.__init__` | function | 20 | Undocumented |
| `DmaCrossNameNestedPlugin.applies_to` | function | 27 | Undocumented |
| `DmaCrossNameNestedPlugin.validate` | function | 31 | Undocumented |

### [`geoqa/plugins/dma/dma_multipart_polygons.py`](../geoqa/plugins/dma/dma_multipart_polygons.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DmaMultipartPolygonPlugin` | class | 11 | Undocumented |
| `DmaMultipartPolygonPlugin.__init__` | function | 12 | Undocumented |
| `DmaMultipartPolygonPlugin.applies_to` | function | 19 | Undocumented |
| `DmaMultipartPolygonPlugin.validate` | function | 23 | Undocumented |
| `DmaMultipartPolygonPlugin.fix` | function | 67 | Undocumented |

### [`geoqa/plugins/dma/dma_overlap_conflicts.py`](../geoqa/plugins/dma/dma_overlap_conflicts.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DmaOverlapConflictPlugin` | class | 11 | Undocumented |
| `DmaOverlapConflictPlugin.__init__` | function | 12 | Undocumented |
| `DmaOverlapConflictPlugin.applies_to` | function | 19 | Undocumented |
| `DmaOverlapConflictPlugin.validate` | function | 23 | Undocumented |

### [`geoqa/plugins/dma/dma_same_name_nested.py`](../geoqa/plugins/dma/dma_same_name_nested.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DmaSameNameNestedPlugin` | class | 20 | Undocumented |
| `DmaSameNameNestedPlugin.__init__` | function | 21 | Undocumented |
| `DmaSameNameNestedPlugin.applies_to` | function | 28 | Undocumented |
| `DmaSameNameNestedPlugin.validate` | function | 32 | Undocumented |
| `DmaSameNameNestedPlugin.fix` | function | 112 | Undocumented |

### [`geoqa/plugins/registry.py`](../geoqa/plugins/registry.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `register_plugin` | function | 11 | Undocumented |
| `clear_plugins` | function | 15 | Undocumented |
| `_load_builtin_plugins` | function | 21 | Undocumented |
| `get_plugins` | function | 30 | Undocumented |

### [`geoqa/problem_registry.py`](../geoqa/problem_registry.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ProblemDefinition` | class | 2190 | Undocumented |
| `_catalog_path` | function | 2205 | Undocumented |
| `_raw_catalog` | function | 2210 | Undocumented |
| `_iso_category` | function | 2214 | Undocumented |
| `_default_confidence` | function | 2245 | Undocumented |
| `_default_actionable` | function | 2256 | Undocumented |
| `problem_definitions` | function | 2266 | Undocumented |
| `get_problem_definition` | function | 2310 | Undocumented |
| `list_problem_definitions` | function | 2314 | Undocumented |

### [`geoqa/profile_registry.py`](../geoqa/profile_registry.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ValidationFamilyProfile` | class | 12 | Undocumented |
| `ValidationFamilyProfile.to_validation_profile` | function | 19 | Undocumented |
| `GeoQAProfile` | class | 30 | Undocumented |
| `_existing_fields` | function | 42 | Undocumented |
| `list_geoqa_profiles` | function | 250 | Undocumented |
| `get_geoqa_profile` | function | 255 | Undocumented |
| `register_geoqa_profile` | function | 260 | Undocumented |
| `clear_geoqa_profiles` | function | 264 | Undocumented |

### [`geoqa/proj_env.py`](../geoqa/proj_env.py)

Make PROJ resolvable before anything tries to build a CRS from an EPSG code.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `proj_is_usable` | function | 32 | Does this directory actually contain a PROJ database? |
| `bundled_proj_dir` | function | 46 | Locate the PROJ tree rasterio ships, if rasterio is installed. |
| `ensure_proj` | function | 80 | Make sure PROJ can find its database, repairing the environment if needed. |
| `proj_status` | function | 106 | What PROJ is pointed at, and whether that works. |

### [`geoqa/qgis_export.py`](../geoqa/qgis_export.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `validation_issues_to_geojson` | function | 10 | Undocumented |
| `build_validation_results_pyqgis_script` | function | 31 | Undocumented |
| `export_validation_results_pyqgis_script` | function | 74 | Undocumented |

### [`geoqa/qgis_integration.py`](../geoqa/qgis_integration.py)

QGIS integration: style files, layer bundles, and PyQGIS processing recipes.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_severity_of` | function | 64 | Undocumented |
| `_issue_row` | function | 69 | Undocumented |
| `issues_to_geodataframe` | function | 87 | Build a GeoDataFrame of findings, split into point and non-point. |
| `qml_style` | function | 143 | Build a QGIS QML style document that renders findings by severity. |
| `write_layer_bundle` | function | 203 | Write findings as a self-contained QGIS-ready bundle. |
| `pyqgis_recipe` | function | 272 | A runnable PyQGIS script that runs GeoQA against the open layer. |
| `arcgis_field_mapping` | function | 331 | Attribute mapping that makes a findings layer usable in ArcGIS Pro. |
| `severity_rank` | function | 362 | Rank map for a findings layer, 1 being most severe. |

### [`geoqa/reports/__init__.py`](../geoqa/reports/__init__.py)

Core GeoQA package implementation.

No functions or classes are defined in this file.

### [`geoqa/reports/aggregation.py`](../geoqa/reports/aggregation.py)

Issue aggregation: turn a stream of per-geometry findings into per-feature findings.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `AggregatedIssue` | class | 75 | One rule applied to one feature, with the findings it absorbed. |
| `AggregatedIssue.severity` | function | 90 | Highest-severity label observed across the absorbed findings. |
| `AggregatedIssue.is_pairwise` | function | 98 | Undocumented |
| `AggregatedIssue.to_dict` | function | 101 | Undocumented |
| `Cluster` | class | 119 | Adjacent per-feature findings treated as one upstream artefact. |
| `Cluster.count` | function | 129 | Undocumented |
| `Cluster.to_dict` | function | 132 | Undocumented |
| `AggregationResult` | class | 143 | Undocumented |
| `AggregationResult.distinct_features` | function | 152 | Undocumented |
| `AggregationResult.affected_feature_fraction` | function | 156 | Undocumented |
| `AggregationResult.collapse_ratio` | function | 160 | Undocumented |
| `AggregationResult.by_rule` | function | 163 | Undocumented |
| `AggregationResult.summary` | function | 173 | Undocumented |
| `AggregationResult.to_dict` | function | 210 | Undocumented |
| `_group` | function | 226 | Undocumented |
| `_feature_key` | function | 233 | Undocumented |
| `aggregate_issues` | function | 237 | Collapse per-geometry findings to per-feature, then cluster. |
| `_cluster` | function | 335 | Single-linkage clustering of per-feature records by bounding-box proximity. |
| `_get` | function | 411 | Undocumented |

### [`geoqa/reports/explanations.py`](../geoqa/reports/explanations.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `explanation_for` | function | 40 | Undocumented |
| `enrich_issue_row` | function | 51 | Undocumented |

### [`geoqa/reports/geojson.py`](../geoqa/reports/geojson.py)

Errors-only GeoJSON export for web-GIS consumption.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue_properties` | function | 23 | Map a ValidationIssue onto the Atlas ``Issue`` property contract. |
| `_clean_geometry` | function | 64 | Accept only usable GeoJSON geometry objects. |
| `issues_to_geojson` | function | 77 | Convert validation issues into an errors-only GeoJSON FeatureCollection. |
| `errors_summary` | function | 127 | Severity/problem rollup for a GeoJSON produced by ``issues_to_geojson``. |

### [`geoqa/reports/report_generator.py`](../geoqa/reports/report_generator.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_distribution_rows` | function | 32 | Undocumented |
| `_normalize_report_row` | function | 43 | Undocumented |
| `_csv_fieldnames` | function | 53 | Undocumented |
| `summarize_issues` | function | 60 | Undocumented |
| `format_summary_text` | function | 144 | Undocumented |
| `load_report` | function | 192 | Undocumented |
| `summarize_report` | function | 210 | Undocumented |
| `generate_report` | function | 245 | Generate a validation report in CSV or JSON format. |

### [`geoqa/reports/tables.py`](../geoqa/reports/tables.py)

Tabular views of GeoQA findings for analysis and DBA work.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_flatten_value` | function | 20 | Render a nested property as a single spreadsheet-friendly cell. |
| `_flatten_properties` | function | 31 | Flatten nested dicts into dotted column names. |
| `_geometry_columns` | function | 47 | Add WKT and centroid coordinates so the table is mappable and plottable. |
| `issues_to_rows` | function | 66 | Convert raw issues (geometry or not) into flat rows. |
| `features_to_rows` | function | 85 | Convert GeoJSON features into flat, analysis-ready rows. |
| `features_to_dataframe` | function | 99 | Return findings as a pandas DataFrame with a stable column order. |
| `_coerce_frame` | function | 107 | Replace list/dict cells that spreadsheet writers cannot handle natively. |
| `write_xlsx` | function | 120 | Write a DataFrame to XLSX with a frozen header and readable widths. |
| `pd_excel_writer` | function | 147 | Return a pandas ExcelWriter positioned at the output path. |
| `_normalise_source` | function | 154 | Accept a GeoJSON path, dict, GeoQAReport, or issues iterable. |
| `_issue_source` | function | 173 | Return an issues iterable when the source exposes one, else None. |
| `geojson_to_dataframe` | function | 188 | Return a GeoJSON file/dict/report as a flat analysis DataFrame. |
| `_order_columns` | function | 215 | Apply the stable column order used by ``features_to_dataframe``. |
| `geojson_to_table` | function | 247 | Write findings to ``.csv`` or ``.xlsx`` (inferred from the suffix). |
| `geojson_to_pivot` | function | 262 | Return a severity x problem pivot table for quick DBA summaries. |

### [`geoqa/runner.py`](../geoqa/runner.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `StepResult` | class | 14 | Undocumented |
| `ThermalRunner` | class | 21 | Base runner for cooperative, thermal-aware script execution. |
| `ThermalRunner.__init__` | function | 28 | Undocumented |
| `ThermalRunner.run_step` | function | 39 | Undocumented |
| `ThermalRunner.run_iterable` | function | 54 | Undocumented |
| `ThermalRunner.run_sequence` | function | 61 | Undocumented |

### [`geoqa/script_base.py`](../geoqa/script_base.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `GeoQAScriptBase` | class | 14 | Base class for thermal-aware GeoQA scripts. |
| `GeoQAScriptBase.__init__` | function | 21 | Undocumented |
| `GeoQAScriptBase.load_items` | function | 38 | Return the units of work for this script. |
| `GeoQAScriptBase.process_item` | function | 42 | Process one unit of work. |
| `GeoQAScriptBase.before_run` | function | 45 | Optional setup hook before the thermal-aware run begins. |
| `GeoQAScriptBase.after_run` | function | 48 | Optional teardown/reporting hook after the run completes. |
| `GeoQAScriptBase.before_step` | function | 51 | Optional hook before each step. |
| `GeoQAScriptBase.after_step` | function | 54 | Optional hook after each step. |
| `GeoQAScriptBase.emit_diagnostic` | function | 57 | Emit startup thermal diagnostic information for this script. |
| `GeoQAScriptBase._default_diagnostic_emitter` | function | 61 | Undocumented |
| `GeoQAScriptBase.run` | function | 68 | Undocumented |

### [`geoqa/serialization/__init__.py`](../geoqa/serialization/__init__.py)

Serialization wrappers exposing GeoAI-backed JSON/TOON helpers through GeoQA.

No functions or classes are defined in this file.

### [`geoqa/thermal.py`](../geoqa/thermal.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ThermalLimitExceeded` | class | 45 | Raised when the configured thermal ceiling is exceeded. |
| `TemperatureSnapshot` | class | 50 | Undocumented |
| `TemperatureDiagnostic` | class | 58 | Undocumented |
| `_read_coretemp_mapping` | function | 67 | Read CPU temperatures from Core Temp shared memory on Windows only. |
| `_read_psutil_temp` | function | 98 | Read CPU temperatures using psutil on Windows, macOS, or Linux when sensors are exposed. |
| `_diagnostic_options` | function | 119 | Undocumented |
| `run_temperature_diagnostic` | function | 139 | Perform a live temperature probe and explain whether GeoQA can read CPU temperatures. |
| `read_cpu_temps_c` | function | 202 | Return CPU temperatures in Celsius. |
| `read_temperature_snapshot` | function | 217 | Return a summarized temperature snapshot for the current machine. |
| `ThermalGuard` | class | 240 | Cooperative thermal guard for long-running GeoQA scripts. |
| `ThermalGuard.__init__` | function | 254 | Undocumented |
| `ThermalGuard.balanced` | function | 276 | Return a guard using the project-balanced defaults. |
| `ThermalGuard.cool` | function | 281 | Return a more conservative guard for machines that heat up quickly. |
| `ThermalGuard.strict` | function | 294 | Return a strict guard intended for heat-sensitive local runs. |
| `ThermalGuard.snapshot` | function | 306 | Undocumented |
| `ThermalGuard._append_log` | function | 309 | Undocumented |
| `ThermalGuard._log_event` | function | 316 | Undocumented |
| `ThermalGuard.wait_until_safe` | function | 332 | Undocumented |
| `ThermalGuard.check_or_raise` | function | 364 | Undocumented |
| `ThermalGuard.cool_down_if_needed` | function | 375 | Force a cooldown pass after work if the current reading is still above the warning threshold. |
| `ThermalGuard.guard_step` | function | 390 | Undocumented |
| `ThermalGuard.__enter__` | function | 396 | Undocumented |
| `ThermalGuard.__exit__` | function | 400 | Undocumented |

### [`geoqa/validation_runtime.py`](../geoqa/validation_runtime.py)

Core GeoQA package implementation.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ValidationProgressEvent` | class | 44 | Undocumented |
| `ValidationProfile` | class | 60 | Undocumented |
| `ValidationLimits` | class | 69 | Undocumented |
| `ValidationPlanResult` | class | 77 | Undocumented |
| `_ValidatorSpec` | class | 88 | Undocumented |
| `InMemoryValidationCache` | class | 96 | Undocumented |
| `InMemoryValidationCache.__init__` | function | 97 | Undocumented |
| `InMemoryValidationCache.get` | function | 100 | Undocumented |
| `InMemoryValidationCache.set` | function | 104 | Undocumented |
| `InMemoryValidationCache.clear` | function | 107 | Undocumented |
| `FileValidationCache` | class | 111 | Undocumented |
| `FileValidationCache.__init__` | function | 112 | Undocumented |
| `FileValidationCache._cache_path` | function | 116 | Undocumented |
| `FileValidationCache.get` | function | 119 | Undocumented |
| `FileValidationCache.set` | function | 155 | Undocumented |
| `FileValidationCache.clear` | function | 160 | Undocumented |
| `register_custom_validator` | function | 172 | Undocumented |
| `clear_custom_validators` | function | 181 | Undocumented |
| `list_custom_validators` | function | 185 | Undocumented |
| `register_validation_profile` | function | 191 | Undocumented |
| `clear_validation_profiles` | function | 195 | Undocumented |
| `get_validation_profile` | function | 199 | Undocumented |
| `_json_safe` | function | 207 | Undocumented |
| `_layer_signature` | function | 222 | Undocumented |
| `_source_size_mb` | function | 243 | Undocumented |
| `_geometry_vertex_count` | function | 257 | Undocumented |
| `_estimate_total_vertices` | function | 284 | Undocumented |
| `_layer_complexity_metrics` | function | 297 | Undocumented |
| `_layer_geometry_types` | function | 303 | Undocumented |
| `_geometry_types_compatible` | function | 320 | Undocumented |
| `_coverage_row` | function | 328 | Undocumented |
| `_context_signature` | function | 348 | Undocumented |
| `_enforce_validation_limits` | function | 376 | Undocumented |
| `build_validation_cache_key` | function | 414 | Undocumented |
| `_run_null_geometry` | function | 442 | Undocumented |
| `_run_duplicate_vertex` | function | 446 | Undocumented |
| `_run_below_minimum_feature_length` | function | 450 | Undocumented |
| `_run_sharp_angle_cutback` | function | 454 | Undocumented |
| `_run_self_intersection` | function | 458 | Undocumented |
| `_run_required_nulls` | function | 465 | Undocumented |
| `_run_uniqueness` | function | 469 | Undocumented |
| `_run_domain_range_checks` | function | 475 | Undocumented |
| `_run_diameter_domain` | function | 487 | Undocumented |
| `_run_material_domain` | function | 499 | Undocumented |
| `_run_status_domain` | function | 511 | Undocumented |
| `_run_missing_crs` | function | 523 | Undocumented |
| `_run_invalid_crs` | function | 527 | Undocumented |
| `_run_missing_metadata_fields` | function | 531 | Undocumented |
| `_run_incomplete_metadata` | function | 535 | Undocumented |
| `_run_coordinate_precision` | function | 539 | Undocumented |
| `_run_xy_tolerance` | function | 548 | Undocumented |
| `_run_positional_accuracy` | function | 557 | Undocumented |
| `_run_missing_spatial_index` | function | 569 | Undocumented |
| `_run_outdated_index` | function | 573 | Undocumented |
| `_run_non_rfc7946_geojson` | function | 577 | Undocumented |
| `_run_polygon_overlap_same_layer` | function | 583 | Undocumented |
| `_run_feature_within_feature` | function | 587 | Undocumented |
| `_run_line_intersection_same_layer` | function | 591 | Undocumented |
| `_run_line_dangle` | function | 595 | Undocumented |
| `_run_duplicate_geometry_same_layer` | function | 605 | Undocumented |
| `_run_feature_not_split_at_intersection` | function | 609 | Undocumented |
| `_run_isolated_network_segment` | function | 613 | Undocumented |
| `_run_suspicious_near_miss_endpoints` | function | 623 | Undocumented |
| `_run_unsnapped_endpoints_within_tolerance` | function | 640 | Undocumented |
| `_run_polygon_gap_same_layer` | function | 657 | Undocumented |
| `_run_boundary_mismatch_against_reference` | function | 661 | Undocumented |
| `_run_spectral_indices` | function | 677 | Adapter for the spectral index validator. |
| `_run_band_radiance` | function | 710 | Undocumented |
| `_run_payload_columns` | function | 721 | Adapter for structured payloads held in scalar text columns. |
| `_run_metric_constants` | function | 738 | Adapter for undeclared constants in a metric chain. |
| `_run_epanet_input` | function | 775 | Adapter for EPANET ``.inp`` decks. |
| `_run_water_balance` | function | 798 | Adapter for the IWA water balance. |
| `_run_crs_units` | function | 826 | Adapter for CRS assessment and length-unit reasoning. |
| `_run_raster` | function | 841 | Adapter for raster band, scaling and CRS checks. |
| `_run_water_loss` | function | 860 | Adapter for UARL and ILI assessment. |
| `_run_repeat_incident` | function | 880 | Adapter for cross-period recurrence. |
| `_run_archive` | function | 911 | Adapter for archive inspection before extraction. |
| `_run_tabular` | function | 935 | Adapter for CSV and Excel structure. |
| `_run_workbook_media` | function | 964 | Adapter for embedded and referenced attachments in a workbook. |
| `_run_geopackage` | function | 989 | Adapter for GeoPackage structural conformance. |
| `_run_governance` | function | 1005 | Adapter for metadata governance. |
| `_run_axis_order` | function | 1031 | Adapter for coordinate axis order. |
| `_run_credentials` | function | 1069 | Adapter for hardcoded credential detection over a file or directory. |
| `_run_clip` | function | 1085 | Adapter for clip assignment and clip completeness. |
| `_run_hyperspectral` | function | 1120 | Adapter for HDF5 hyperspectral products. |
| `_run_coefficient_reference` | function | 1147 | Adapter for the published reference cases. |
| `_run_uarl_applicability` | function | 1159 | Adapter for the UARL equation's stated applicability limits. |
| `_optional_context` | function | 1179 | Copy context keys only when a usable value is supplied. |
| `_builtin_specs` | function | 1188 | Undocumented |
| `_custom_specs` | function | 1645 | Undocumented |
| `_estimated_spec_cost` | function | 1653 | Undocumented |
| `_ordered_specs` | function | 1665 | Undocumented |
| `_ordered_specs.<locals>.key` | function | 1677 | Undocumented |
| `_apply_profile` | function | 1688 | Undocumented |
| `execute_validation_plan` | function | 1721 | Undocumented |
| `execute_validation_plan.<locals>.current_actionable_count` | function | 1791 | Undocumented |
| `execute_validation_plan.<locals>.should_stop_early` | function | 1794 | Undocumented |
| `execute_validation_plan.<locals>.emit_completed` | function | 1803 | Undocumented |

### [`geoqa/validations/__init__.py`](../geoqa/validations/__init__.py)

GeoQA validation modules.

No functions or classes are defined in this file.

### [`geoqa/validations/accuracy.py`](../geoqa/validations/accuracy.py)

Validation implementation for accuracy; see the linked module reference when available.

Validator reference: [`accuracy`](modules/accuracy.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_iter_coordinate_sequences` | function | 11 | Undocumented |
| `_decimal_places` | function | 35 | Undocumented |
| `_max_decimal_places` | function | 52 | Undocumented |
| `_layer_bounds` | function | 61 | Undocumented |
| `_crs_string` | function | 86 | Undocumented |
| `_recommended_max_decimal_places` | function | 96 | Undocumented |
| `_recommended_xy_tolerance` | function | 119 | Undocumented |
| `coordinate_precision` | function | 142 | Return issues for features whose coordinate precision exceeds the configured threshold. |
| `xy_tolerance` | function | 168 | Return a dataset-level issue when stored XY tolerance metadata exceeds a configured threshold. |
| `positional_accuracy` | function | 203 | Return issues for features farther than the allowed tolerance from the reference layer. |

### [`geoqa/validations/archive.py`](../geoqa/validations/archive.py)

Archive (ZIP) inspection and pre-extraction validation.

Validator reference: [`archive`](modules/archive.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 137 | Undocumented |
| `_normalise` | function | 148 | Lowercase extension, treating multi-part extensions such as ``.shp.xml``. |
| `_classify` | function | 157 | What kind of thing this member claims to be, from its name. |
| `looks_geospatial` | function | 165 | Is this member name one that suggests geospatial content? |
| `detect_magic` | function | 170 | Identify a file from its leading bytes. ``"unknown"`` when unrecognised. |
| `_is_plausible_for` | function | 183 | Does the detected content agree with the extension on the filename? |
| `_traversal_kind` | function | 221 | Classify a member name as unsafe. ``None`` when the name is acceptable. |
| `ArchiveMember` | class | 239 | One member of an archive, described without extracting it. |
| `ArchiveMember.extension` | function | 252 | Undocumented |
| `ArchiveMember.kind` | function | 256 | What the name claims this member is. |
| `ArchiveMember.is_geospatial` | function | 261 | Undocumented |
| `ArchiveMember.is_shapefile_sidecar` | function | 265 | Undocumented |
| `ArchiveMember.ratio` | function | 271 | Uncompressed bytes per compressed byte. 0.0 for stored members. |
| `ArchiveMember.megabytes` | function | 278 | Undocumented |
| `ArchiveMember.stem` | function | 282 | Filename without its extension, used to group shapefile sidecars. |
| `ArchiveMember.as_dict` | function | 287 | Undocumented |
| `ArchiveProfile` | class | 302 | What an archive contains, and whether it is safe to extract. |
| `ArchiveProfile.member_count` | function | 321 | Undocumented |
| `ArchiveProfile.geospatial_members` | function | 325 | Undocumented |
| `ArchiveProfile.max_ratio` | function | 329 | Undocumented |
| `ArchiveProfile.safe_to_extract` | function | 333 | No traversal, no absolute paths, no bomb, nothing unreadable. |
| `ArchiveProfile.summary` | function | 342 | Undocumented |
| `_read_magic` | function | 355 | Leading bytes of a member, or ``None`` when it genuinely cannot be read. |
| `_is_encrypted` | function | 368 | Undocumented |
| `scan_archive` | function | 372 | Inventory an archive without extracting anything. |
| `_group_shapefiles` | function | 425 | Group shapefile sidecars by stem and record what is missing. |
| `validate_archive` | function | 452 | Report archive conditions, before anything is extracted. |
| `open_member` | function | 656 | Read one member into memory. For small files only. |
| `member_suffix_candidates` | function | 667 | Other members that belong with this one, for set-based formats. |
| `plan_extraction` | function | 682 | Produce an extraction plan. Writes nothing. |

### [`geoqa/validations/attributes.py`](../geoqa/validations/attributes.py)

Validation implementation for attributes; see the linked module reference when available.

Validator reference: [`attributes`](modules/attributes.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_is_null` | function | 9 | Undocumented |
| `_field_exists` | function | 19 | Undocumented |
| `required_nulls` | function | 24 | Return issues for missing values in required fields. |
| `uniqueness` | function | 57 | Return issues for duplicate non-null values in the specified field. |
| `domain_range_checks` | function | 90 | Return issues for values that fall outside the configured domain or range. |

### [`geoqa/validations/axis_order.py`](../geoqa/validations/axis_order.py)

Coordinate axis order, and the swap that produces plausible wrong places.

Validator reference: [`axis_order`](modules/axis_order.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 73 | Undocumented |
| `canonical_order` | function | 84 | Axis order a declared CRS or format mandates. |
| `_as_float` | function | 106 | Undocumented |
| `AxisOrderFinding` | class | 123 | What one pair of coordinates implies about its ordering. |
| `AxisOrderFinding.is_ambiguous` | function | 134 | Undocumented |
| `AxisOrderFinding.as_dict` | function | 137 | Undocumented |
| `infer_axis_order` | function | 147 | Work out which axis is which from the values themselves. |
| `_column_label` | function | 210 | Undocumented |
| `_column_kind` | function | 214 | Which axis a column name refers to, if it says. |
| `_declared_from_columns` | function | 224 | Infer an axis order from column names and their left-to-right position. |
| `_pick_columns` | function | 242 | Choose which column is first and which is second, in the declared order. |
| `_pick_columns.<locals>.find` | function | 244 | Undocumented |
| `validate_axis_order` | function | 254 | Check a coordinate table for swapped axes. |
| `validate_axis_order_sql` | function | 442 | SQL that finds swapped coordinates in a PostgreSQL/PostGIS table. |
| `validate_axis_order_postgis_sql` | function | 501 | SQL that checks a PostGIS geometry column for a latitude/longitude swap. |
| `interpret_postgres_result` | function | 529 | Turn ``axis_order_sql`` output into issues. |

### [`geoqa/validations/base.py`](../geoqa/validations/base.py)

Validation implementation for base; see the linked module reference when available.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ValidationIssue` | class | 27 | Structured representation of a detected validation issue. |
| `ValidationIssue.__post_init__` | function | 53 | Undocumented |
| `ValidationIssue.to_dict` | function | 69 | Convert the issue to a report-friendly dictionary. |
| `_compute_priority_score` | function | 95 | Undocumented |
| `_build_issue_id` | function | 113 | Undocumented |
| `_json_safe_geometry` | function | 124 | Undocumented |
| `_json_safe_value` | function | 142 | Undocumented |
| `_row_has_key` | function | 155 | Undocumented |
| `_row_value` | function | 164 | Undocumented |
| `_row_geometry` | function | 173 | Undocumented |
| `_feature_id` | function | 177 | Undocumented |
| `build_issue` | function | 184 | Create a validation issue, preferring catalog-backed metadata when available. |

### [`geoqa/validations/boundary_conformance.py`](../geoqa/validations/boundary_conformance.py)

Detect geometry that was cut by another layer's boundary.

Validator reference: [`boundary_conformance`](modules/boundary_conformance.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `FragmentFinding` | class | 59 | One feature assessed against the reference layer. |
| `FragmentFinding.is_fragment` | function | 71 | Undocumented |
| `FragmentFinding.is_undeclared_cut` | function | 75 | A fragment that no boundary in the boundary layer accounts for. |
| `BoundaryConformanceProfile` | class | 81 | Undocumented |
| `BoundaryConformanceProfile.summary` | function | 90 | Undocumented |
| `_geometry` | function | 101 | Undocumented |
| `_feature_id` | function | 110 | Undocumented |
| `_reference_candidates` | function | 120 | Reference rows whose bounding box intersects the query geometry. |
| `_boundary_explains_cut` | function | 140 | Is the fragment's outer edge explained by a boundary in the boundary layer? |
| `profile_boundary_conformance` | function | 198 | Assess every feature in ``layer`` against ``reference_layer``. |
| `_bucket` | function | 314 | Undocumented |
| `validate_boundary_conformance` | function | 326 | Report features that a boundary cut, when no boundary explains it. |
| `continuity_breaks` | function | 447 | Report network features that stop and resume inside the same zone. |

### [`geoqa/validations/clip.py`](../geoqa/validations/clip.py)

Clipping: which side a straddling feature belongs to, and whether the clip

Validator reference: [`clip`](modules/clip.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 76 | Undocumented |
| `_geometry` | function | 87 | Undocumented |
| `_feature_id` | function | 96 | Undocumented |
| `StraddleRecord` | class | 107 | One feature crossing a boundary, with the measurement behind any call. |
| `StraddleRecord.dominant_side` | function | 118 | Undocumented |
| `StraddleRecord.near_half` | function | 122 | Undocumented |
| `StraddleRecord.as_dict` | function | 125 | Undocumented |
| `_resolve_geometry` | function | 142 | Undocumented |
| `profile_clip_assignment` | function | 150 | Measure how each feature splits across a boundary. |
| `validate_clip_assignment` | function | 220 | Report how features split across a boundary, under a declared threshold. |
| `ClipMatch` | class | 294 | A clipped feature matched to the source it came from. |
| `ClipMatch.is_half` | function | 304 | Undocumented |
| `ClipMatch.as_dict` | function | 307 | Undocumented |
| `ClipProfile` | class | 318 | What a clip did to the source layer. |
| `ClipProfile.summary` | function | 328 | Undocumented |
| `_match_sources` | function | 339 | Pair each clipped feature with the source it overlaps most. |
| `_source_geometry` | function | 366 | Undocumented |
| `profile_clip_completeness` | function | 373 | Compare a clipped layer against the source it was cut from. |
| `validate_clip_completeness` | function | 431 | Report features left half-formed by a clip. |

### [`geoqa/validations/cog.py`](../geoqa/validations/cog.py)

Cloud Optimized GeoTIFF conformance, and vector format currency.

Validator reference: [`cog`](modules/cog.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 66 | Undocumented |
| `_import_rasterio` | function | 77 | Undocumented |
| `CogProfile` | class | 92 | Whether a TIFF meets the Cloud Optimized GeoTIFF expectations. |
| `CogProfile.meets_cog_expectations` | function | 111 | Undocumented |
| `CogProfile.is_large` | function | 118 | Big enough that partial reads matter. |
| `CogProfile.as_dict` | function | 122 | Undocumented |
| `profile_cog` | function | 141 | Inspect a TIFF for cloud-optimized layout. Reads metadata only. |
| `_dtype_size` | function | 196 | Undocumented |
| `validate_cog` | function | 204 | Report a TIFF that is valid but not laid out for partial reading. |
| `format_support_report` | function | 283 | The formats this library can read, with their current standing. |

### [`geoqa/validations/containment.py`](../geoqa/validations/containment.py)

Buffer containment, round-trip durability, and scale-dependent tolerance.

Validator reference: [`containment`](modules/containment.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `verify_containment` | function | 41 | Report source features not fully enclosed by their buffer. |
| `_union` | function | 130 | Undocumented |
| `_containment_shortfall` | function | 140 | Distance by which ``inner`` escapes ``outer``, or ``None`` if enclosed. |
| `round_trip` | function | 159 | Write a layer and read it back, reporting anything the write lost. |
| `scale_dependent_tolerance` | function | 277 | Express a tolerance as a fraction of the data's own extent. |
| `describe_tolerance` | function | 304 | Return the tolerance actually applied, with the extent it came from. |

### [`geoqa/validations/coverage.py`](../geoqa/validations/coverage.py)

How much of a geometry survived a clip, and whether the pieces came back.

Validator reference: [`coverage`](modules/coverage.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_area` | function | 42 | Undocumented |
| `coverage_ratio` | function | 53 | Retained fraction of area between an original geometry and its clipped result. |
| `_match_by_id` | function | 80 | Undocumented |
| `validate_coverage_floor` | function | 98 | Report features that lost more than ``1 - minimum_retained`` to the clip. |
| `_lookup_geometry` | function | 193 | Undocumented |
| `validate_split_completeness` | function | 203 | Report split features whose pieces do not reassemble into one geometry. |
| `_pairwise_overlap_area` | function | 329 | Total area covered by more than one piece. |
| `_safe_union` | function | 341 | Undocumented |
| `coverage_report` | function | 350 | Return the retained fraction per feature without judging it. |

### [`geoqa/validations/credentials.py`](../geoqa/validations/credentials.py)

Hardcoded credential detection, for code and configuration.

Validator reference: [`credentials`](modules/credentials.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `is_test_path` | function | 155 | Is this file a test fixture rather than shipped code? |
| `_issue` | function | 163 | Undocumented |
| `shannon_entropy` | function | 174 | Bits per character. Credentials sit high; English words sit low. |
| `SecretFinding` | class | 188 | One place a credential appears, with enough context to judge it. |
| `SecretFinding.as_dict` | function | 201 | Undocumented |
| `redact_match` | function | 213 | A safe rendering of a secret: a hint of its shape, none of its value. |
| `_is_exempt` | function | 224 | Is this literal safe to ignore? |
| `_is_placeholder_url` | function | 238 | Is this a documentation example rather than a real credential? |
| `scan_text` | function | 252 | Find credentials in one block of text. |
| `scan_file` | function | 339 | Scan one file. Binary and oversized files are skipped rather than guessed at. |
| `iter_source_files` | function | 351 | Yield files worth scanning under ``root``, skipping caches and VCS. |
| `scan_tree` | function | 362 | Scan a directory for hardcoded credentials. |
| `validate_credentials` | function | 383 | Report hardcoded credentials in a file or directory. |

### [`geoqa/validations/cross_layer.py`](../geoqa/validations/cross_layer.py)

Referential integrity between two layers.

Validator reference: [`cross_layer`](modules/cross_layer.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `normalise_key` | function | 41 | Return a comparable text key, or ``None`` when there is no key. |
| `_keys` | function | 67 | Undocumented |
| `referential_integrity` | function | 84 | Report child rows whose key is absent from the parent. |
| `bidirectional_coverage` | function | 141 | Report key sets that disagree, in both directions. |
| `orphaned_by_geometry` | function | 209 | Report assets whose geometry meets no part of the network. |
| `declared_domain` | function | 263 | Return the observed value domain for a column. |

### [`geoqa/validations/crs.py`](../geoqa/validations/crs.py)

Validation implementation for crs; see the linked module reference when available.

Validator reference: [`crs`](modules/crs.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_normalize_crs` | function | 8 | Undocumented |
| `_parse_crs` | function | 23 | Undocumented |
| `missing_crs` | function | 34 | Return a dataset-level issue when the layer does not define a CRS. |
| `invalid_crs` | function | 47 | Return a dataset-level issue when CRS is unreadable or violates an explicit expected CRS. |

### [`geoqa/validations/crs_units.py`](../geoqa/validations/crs_units.py)

Coordinate reference system advice, unit reasoning, and safe reprojection.

Validator reference: [`crs_units`](modules/crs_units.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `CrsAssessment` | class | 81 | What GeoQA can say about a layer's coordinate reference system. |
| `CrsAssessment.as_dict` | function | 98 | Undocumented |
| `LengthUnitFinding` | class | 117 | A declared length column measured against the geometry. |
| `LengthUnitFinding.as_dict` | function | 130 | Undocumented |
| `_crs_epsg` | function | 144 | Undocumented |
| `_axis_unit_metres` | function | 167 | Return (unit name, metres per unit) for the CRS's linear axis. |
| `_utm_epsg_from_extent` | function | 188 | Infer a plausible UTM EPSG from a geographic bounding box. |
| `_best_utm` | function | 202 | Return (epsg, north/south, zone) for the UTM zone containing a point. |
| `assess_crs` | function | 211 | Describe the layer's CRS and, when possible, what it should be. |
| `_length_columns` | function | 292 | Undocumented |
| `_median` | function | 313 | Undocumented |
| `check_length_units` | function | 338 | Compare declared length columns against what the geometry measures. |
| `_is_number` | function | 423 | Undocumented |
| `_issue` | function | 431 | Undocumented |
| `validate_crs_consistency` | function | 442 | Report missing, geographic, implausible, or unit-inconsistent CRS. |
| `reproject_within_tolerance` | function | 544 | Reproject, verify, and either return the result or raise. |
| `crs_report` | function | 617 | Everything GeoQA can say about a CRS, for a report or manifest. |

### [`geoqa/validations/datatypes.py`](../geoqa/validations/datatypes.py)

Declared datatypes, geometry parts, and what a database will accept.

Validator reference: [`datatypes`](modules/datatypes.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `GeometryPartProfile` | class | 73 | What the geometry column actually contains, as distinct from what is declared. |
| `GeometryPartProfile.dominant_type` | function | 86 | Undocumented |
| `GeometryPartProfile.has_mixed` | function | 92 | Undocumented |
| `GeometryPartProfile.to_dict` | function | 95 | Undocumented |
| `_geometry_type` | function | 108 | Undocumented |
| `_part_geometries` | function | 112 | Undocumented |
| `profile_geometry_parts` | function | 122 | Describe the part structure of a layer without judging it. |
| `validate_geometry_parts` | function | 160 | Report mixed geometry part structure and a declared type that will not accept it. |
| `_declared_accepts` | function | 230 | Whether a column declared ``declared`` will accept geometry ``observed``. |
| `_looks_numeric_field` | function | 258 | Undocumented |
| `profile_datatypes` | function | 265 | Return the declared dtype per column, using text for anything unreadable. |
| `_is_text_dtype` | function | 280 | Undocumented |
| `_is_float_dtype` | function | 284 | Float only. |
| `_is_floatish` | function | 294 | Undocumented |
| `validate_datatypes` | function | 298 | Report columns whose declared type does not match what they hold. |
| `_count_unparseable` | function | 389 | Undocumented |
| `postgis_expectations` | function | 410 | Check a layer against what PostGIS will accept on insert. |

### [`geoqa/validations/dimension.py`](../geoqa/validations/dimension.py)

Geometry dimension (2D / 3D) evidence, from real operational behaviour.

Validator reference: [`dimension`](modules/dimension.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `DimensionProfile` | class | 68 | Dimensional character of a layer, independent of any requirement. |
| `DimensionProfile.is_mixed` | function | 82 | True when some features carry Z and others do not. |
| `DimensionProfile.effective_3d_features` | function | 87 | Features carrying a Z that is not identically zero. |
| `DimensionProfile.recommended_postgis_type` | function | 92 | What that pipeline would write, reproduced. |
| `DimensionProfile.to_dict` | function | 99 | Undocumented |
| `_has_z` | function | 114 | Undocumented |
| `profile_dimension` | function | 121 | Measure the dimensional character of a layer. |
| `validate_geometry_dimension` | function | 186 | Report geometry-dimension evidence. |

### [`geoqa/validations/encoding.py`](../geoqa/validations/encoding.py)

Character encoding of delivered tabular and shapefile attribute data.

Validator reference: [`encoding`](modules/encoding.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `EncodingReport` | class | 43 | What an attribute column's text looks like, and how sure we are. |
| `EncodingReport.is_declared` | function | 56 | Undocumented |
| `EncodingReport.has_problem` | function | 60 | Undocumented |
| `EncodingReport.to_dict` | function | 63 | Undocumented |
| `read_cpg` | function | 76 | Return the encoding declared by a shapefile's ``.cpg`` sidecar, if any. |
| `detect_encoding` | function | 88 | Determine the declared and usable encoding for a shapefile's attributes. |
| `looks_like_mojibake` | function | 127 | Whether a string shows the classic double-encoding signature. |
| `check_text_encoding` | function | 138 | Inspect text values for signs of an encoding that did not survive. |
| `validate_shapefile_encoding` | function | 171 | Report a shapefile whose attribute encoding is undeclared or has broken. |

### [`geoqa/validations/endpoint_triage.py`](../geoqa/validations/endpoint_triage.py)

Endpoint resolution and dangle triage.

Validator reference: [`endpoint_triage`](modules/endpoint_triage.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `NetworkCharacter` | class | 88 | Is this layer actually a connected network? |
| `NetworkCharacter.to_dict` | function | 122 | Undocumented |
| `NetworkCharacter.summary` | function | 137 | Undocumented |
| `network_character` | function | 153 | Measure how noded a line layer is, before trusting any dangle count. |
| `EndpointFinding` | class | 207 | One endpoint adjudicated by the triage. |
| `EndpointFinding.to_dict` | function | 219 | Undocumented |
| `OrphanCluster` | class | 231 | A spatial cluster of orphan endpoints. |
| `OrphanCluster.to_dict` | function | 244 | Undocumented |
| `EndpointTriage` | class | 254 | Undocumented |
| `EndpointTriage.by_cause` | function | 266 | Undocumented |
| `EndpointTriage.total` | function | 273 | Undocumented |
| `EndpointTriage.percentages` | function | 276 | Undocumented |
| `EndpointTriage.of` | function | 281 | Undocumented |
| `EndpointTriage.to_dict` | function | 285 | Undocumented |
| `EndpointTriage.summary` | function | 305 | Undocumented |
| `EndpointTriage.to_issues` | function | 349 | Convert unresolved findings to ValidationIssues for the normal report. |
| `_node_points` | function | 400 | Extract node coordinates and ids from a companion point layer. |
| `_grid_clusters` | function | 432 | Cluster points by grid-hash adjacency at the given radius. |
| `_grid_clusters.<locals>.find` | function | 451 | Undocumented |
| `_grid_clusters.<locals>.union` | function | 457 | Undocumented |
| `triage_endpoints` | function | 497 | Adjudicate every line endpoint in ``layer``. |
| `triage_endpoints.<locals>._feature_id` | function | 599 | Undocumented |

### [`geoqa/validations/epanet.py`](../geoqa/validations/epanet.py)

EPANET ``.inp`` input-file parsing and structural validation.

Validator reference: [`epanet`](modules/epanet.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `Token` | class | 92 | One whitespace-delimited field on one line. |
| `Section` | class | 102 | Undocumented |
| `Section.column_count` | function | 108 | Undocumented |
| `Section.values` | function | 111 | Undocumented |
| `Section.ids` | function | 116 | Undocumented |
| `EpanetModel` | class | 121 | A parsed ``.inp`` deck, section-keyed. |
| `EpanetModel.section` | function | 130 | Undocumented |
| `EpanetModel.node_ids` | function | 134 | Undocumented |
| `EpanetModel.link_ids` | function | 143 | Undocumented |
| `EpanetModel.pipe_rows` | function | 152 | Undocumented |
| `EpanetModel.junction_rows` | function | 157 | Undocumented |
| `_strip_comment` | function | 162 | Remove a trailing ``;`` comment, honouring quoted strings. |
| `_tokenize` | function | 173 | Undocumented |
| `parse_inp` | function | 184 | Parse EPANET input text into an :class:`EpanetModel`. |
| `_issue` | function | 256 | Undocumented |
| `validate_inp` | function | 267 | Structural and referential validation of a parsed deck. |
| `_normalize_option_key` | function | 410 | Undocumented |
| `_parse_options` | function | 417 | Read [OPTIONS], tolerating keys that span several tokens. |
| `_validate_units` | function | 465 | Undocumented |
| `_validate_topology` | function | 514 | Undocumented |
| `_disconnected_groups` | function | 632 | Undocumented |
| `_validate_losses` | function | 665 | Check [REACTIONS] consistency before a run. |
| `_storage_count` | function | 714 | Undocumented |
| `summarize_inp` | function | 723 | Counts and unit context, for a manifest or report header. |
| `summarize_inp.<locals>.count` | function | 725 | Undocumented |

### [`geoqa/validations/geometry.py`](../geoqa/validations/geometry.py)

Validation implementation for geometry; see the linked module reference when available.

Validator reference: [`geometry`](modules/geometry.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_iter_coordinate_sequences` | function | 10 | Undocumented |
| `_has_duplicate_consecutive_vertex` | function | 29 | Undocumented |
| `_run_geometry_check` | function | 40 | Undocumented |
| `null_geometry` | function | 49 | Detect features with null geometries. |
| `null_geometry.<locals>.check` | function | 52 | Undocumented |
| `self_intersection` | function | 62 | Detect self-intersecting geometries. |
| `self_intersection.<locals>.check` | function | 71 | Undocumented |
| `duplicate_vertex` | function | 88 | Detect duplicate consecutive vertices in geometries. |
| `duplicate_vertex.<locals>.check` | function | 91 | Undocumented |
| `_segment_length` | function | 101 | Undocumented |
| `_geometry_length` | function | 108 | Undocumented |
| `_crs_length_mode` | function | 124 | Return ('projected', meters_per_unit) or ('geographic', geod) for the layer CRS. |
| `_geodesic_length` | function | 159 | Undocumented |
| `_feature_length_meters` | function | 170 | Undocumented |
| `_interior_angles` | function | 179 | Undocumented |
| `below_minimum_feature_length` | function | 195 | Detect line-like features whose total length (in meters) falls below a configured minimum. |
| `below_minimum_feature_length.<locals>.check` | function | 208 | Undocumented |
| `sharp_angle_cutback` | function | 227 | Detect line or polygon vertices with suspiciously sharp angle cutbacks. |
| `sharp_angle_cutback.<locals>.check` | function | 230 | Undocumented |

### [`geoqa/validations/governance.py`](../geoqa/validations/governance.py)

Metadata governance: is this dataset safe to publish, reuse and defend?

Validator reference: [`governance`](modules/governance.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 91 | Undocumented |
| `_is_absent` | function | 102 | Is this element simply not there? |
| `_is_placeholder` | function | 113 | Is this element filled with text standing in for a decision? |
| `_is_missing` | function | 123 | Absent, or filled with a placeholder. Neither is a decision. |
| `_flatten` | function | 128 | Look a key up at the top level, then case-insensitively, then nested. |
| `_as_text` | function | 145 | Undocumented |
| `parse_metadata_date` | function | 155 | Read a metadata date in the forms INSPIRE records allow. |
| `licence_looks_open` | function | 176 | Does the recorded licence look like an open one? |
| `validate_governance_metadata` | function | 184 | Report metadata that prevents lawful, accountable use of a dataset. |
| `governance_report` | function | 363 | A short statement of what is and is not established about a dataset. |

### [`geoqa/validations/hyperspectral.py`](../geoqa/validations/hyperspectral.py)

HDF5 hyperspectral products: HDF-EOS swaths such as EMIT, and generic groups.

Validator reference: [`hyperspectral`](modules/hyperspectral.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_import_h5py` | function | 89 | Undocumented |
| `_issue` | function | 99 | Undocumented |
| `_attr` | function | 110 | Undocumented |
| `_to_list` | function | 119 | Undocumented |
| `BandMapping` | class | 127 | One named spectral role resolved to a band index. |
| `BandMapping.as_dict` | function | 134 | Undocumented |
| `HyperspectralProfile` | class | 143 | What a hyperspectral file contains, read without loading the cube. |
| `HyperspectralProfile.megabytes` | function | 169 | Undocumented |
| `HyperspectralProfile.wavelength_range_nm` | function | 173 | Undocumented |
| `HyperspectralProfile.mean_band_spacing_nm` | function | 179 | Undocumented |
| `HyperspectralProfile.band_for` | function | 186 | Index of the band nearest a named role's centre wavelength. |
| `HyperspectralProfile.resolve_bands` | function | 198 | Resolve named roles to band indices by wavelength, not by position. |
| `HyperspectralProfile.as_dict` | function | 212 | Undocumented |
| `_product_level_from_name` | function | 237 | Undocumented |
| `_cube_candidates` | function | 248 | Datasets that look like a spectral cube, best first. |
| `_cube_candidates.<locals>.collect` | function | 258 | Undocumented |
| `_cube_candidates.<locals>.rank` | function | 275 | Undocumented |
| `_product_group_path` | function | 284 | The swath-level group a dataset belongs to. |
| `profile_hyperspectral` | function | 300 | Describe an HDF5 hyperspectral file without reading the cube. |
| `_valid_mask` | function | 400 | Undocumented |
| `read_band_subset` | function | 413 | Read a wavelength-bounded window of the cube into memory. |
| `read_quality_layer` | function | 478 | Read one quality or geolocation layer by name. |
| `hyperspectral_indices` | function | 535 | Compute NDVI, NDWI and NDMI from a wavelength-bounded subset. |
| `hyperspectral_indices.<locals>.band` | function | 552 | Undocumented |
| `hyperspectral_indices.<locals>.ratio` | function | 580 | Undocumented |
| `validate_hyperspectral` | function | 611 | Report structural conditions in a hyperspectral product. |

### [`geoqa/validations/integrity.py`](../geoqa/validations/integrity.py)

Validation implementation for integrity; see the linked module reference when available.

Validator reference: [`integrity`](modules/integrity.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `missing_spatial_index` | function | 10 | Return a dataset-level issue when a spatial index is absent or explicitly marked stale. |
| `outdated_index` | function | 27 | Return a dataset-level issue when layer metadata marks indexes as outdated. |
| `_load_geojson_payload` | function | 42 | Undocumented |
| `non_rfc7946_geojson` | function | 59 | Return a dataset-level issue when GeoJSON content violates common RFC 7946 expectations. |

### [`geoqa/validations/keys.py`](../geoqa/validations/keys.py)

Keys that are not a single column.

Validator reference: [`keys`](modules/keys.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `truncate_timestamp` | function | 44 | Reduce a timestamp to its declared granularity. |
| `compound_key_duplicates` | function | 74 | Report rows sharing a compound natural key. |
| `resolve_field` | function | 142 | Resolve one logical field to a physical column, or report the ambiguity. |
| `resolve_schema` | function | 161 | Resolve a whole schema, reporting missing and ambiguous fields. |
| `VocabularyBinding` | class | 198 | Outcome of binding names to a controlled vocabulary. |
| `VocabularyBinding.status` | function | 207 | Undocumented |
| `VocabularyBinding.to_dict` | function | 214 | Undocumented |
| `bind_to_vocabulary` | function | 224 | Bind names to vocabulary terms by similarity, flagging ambiguity. |
| `bind_to_vocabulary.<locals>.similarity` | function | 243 | Undocumented |
| `bind_to_vocabulary.<locals>.prep` | function | 246 | Undocumented |
| `validate_vocabulary_binding` | function | 276 | Report ambiguous and unbound names as issues. |

### [`geoqa/validations/metadata.py`](../geoqa/validations/metadata.py)

Validation implementation for metadata; see the linked module reference when available.

Validator reference: [`metadata`](modules/metadata.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_missing_value` | function | 15 | Undocumented |
| `missing_metadata_fields` | function | 23 | Return issues for missing core metadata fields. |
| `incomplete_metadata` | function | 38 | Return issues for incomplete but expected metadata sections. |

### [`geoqa/validations/metric_constants.py`](../geoqa/validations/metric_constants.py)

Undeclared constants inside a metric or decision chain.

Validator reference: [`metric_constants`](modules/metric_constants.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_date_components` | function | 88 | Numeric literals that are part of a date rather than a multiplier. |
| `ConstantDeclaration` | class | 107 | One declared meaning for a numeric constant. |
| `ConstantDeclaration.as_dict` | function | 116 | Undocumented |
| `MetricConstantAudit` | class | 127 | One metric, its expression, and the constants found in it. |
| `MetricConstantAudit.is_declared_fully` | function | 138 | Undocumented |
| `_build_audit` | function | 142 | Undocumented |
| `parse_metric_expressions` | function | 154 | Extract metric definitions from a formula/KPI source listing. |
| `audit_constants` | function | 197 | Audit a source listing against a set of declared constants. |
| `validate_metric_constants` | function | 243 | Report undeclared constants and undeclared scope boundaries. |
| `audit_table` | function | 306 | Audit constants held as literal text inside spreadsheet cells. |

### [`geoqa/validations/night_flow.py`](../geoqa/validations/night_flow.py)

Night-flow leakage and NRW coefficients, under declared provenance.

Validator reference: [`night_flow`](modules/night_flow.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `CoefficientDeclaration` | class | 61 | A coefficient, and everything someone must state about it. |
| `CoefficientDeclaration.as_dict` | function | 75 | Undocumented |
| `CoefficientDeclaration.is_complete` | function | 87 | Undocumented |
| `ReproductionEvidence` | class | 92 | An observed figure and the inputs needed to derive the coefficient. |
| `ReproductionEvidence.relative_error` | function | 104 | Undocumented |
| `orifice_discharge` | function | 118 | Orifice discharge ``Q = Cd * A * sqrt(2 g h)`` in m3/s. |
| `favad_flow_ratio` | function | 142 | Pressure-driven flow change ``Q1 / Q0 = (P1 / P0) ^ n``. |
| `fadd` | function | 165 | Fixed-and-variable discharge split at normal operating pressure. |
| `nightly_leakage_from_night_flow` | function | 179 | Night-flow leakage in m3 over the night window. |
| `pressure_dependent_background_leakage` | function | 200 | Background leakage at night pressure, from the FAVAD relationship. |
| `apparent_losses_from_mnf` | function | 227 | Apparent losses derived from minimum night flow, in m3. |
| `_issue` | function | 264 | Undocumented |
| `validate_coefficient_declaration` | function | 275 | Check one declaration for completeness, units and reproduction. |
| `solve_fitted_night_flow_coefficient` | function | 410 | Back out the night-flow leakage rate that explains an observed volume. |
| `solve_fitted_favad_exponent` | function | 429 | Back out the FAVAD exponent implied by two observed flows. |
| `validate_coefficient_chain` | function | 443 | Validate every coefficient in a calculation chain. |

### [`geoqa/validations/osm.py`](../geoqa/validations/osm.py)

OpenStreetMap: the failure modes that come with the format's own nature.

Validator reference: [`osm`](modules/osm.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 69 | Undocumented |
| `OsmProfile` | class | 81 | What an OSM extract declares about itself. |
| `OsmProfile.as_dict` | function | 102 | Undocumented |
| `_looks_closed` | function | 118 | Is a WKT geometry a closed ring? |
| `profile_osm_layer` | function | 134 | Describe an OSM-derived layer without judging it yet. |
| `validate_osm` | function | 204 | Report the OSM-specific conditions a structural check would miss. |

### [`geoqa/validations/payload_columns.py`](../geoqa/validations/payload_columns.py)

Detect structured payloads stored in columns declared as scalar text.

Validator reference: [`payload_columns`](modules/payload_columns.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_as_text` | function | 50 | Undocumented |
| `_looks_structured` | function | 56 | Undocumented |
| `_parse_attempt` | function | 69 | Return (parsed, value). Tolerates a vendor prefix before the payload. |
| `PayloadColumnProfile` | class | 86 | What a single column's contents look like structurally. |
| `PayloadColumnProfile.structured_fraction` | function | 98 | Undocumented |
| `PayloadColumnProfile.parse_success_rate` | function | 104 | Undocumented |
| `PayloadColumnProfile.is_structured_column` | function | 110 | Structured enough to be a schema defect rather than incidental text. |
| `profile_payload_column` | function | 115 | Inspect one column's values without deciding anything about it. |
| `validate_payload_columns` | function | 148 | Report columns that hold a serialised structure despite a scalar text type. |
| `payload_columns` | function | 228 | Return profiles only, for callers that want the shape without the issues. |

### [`geoqa/validations/raster.py`](../geoqa/validations/raster.py)

Raster reading and spectral validation over real imagery.

Validator reference: [`raster`](modules/raster.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `RasterProfile` | class | 67 | What a raster contains, before any pixel is read. |
| `RasterProfile.megabytes` | function | 88 | Undocumented |
| `RasterProfile.as_dict` | function | 91 | Undocumented |
| `_import_rasterio` | function | 112 | Undocumented |
| `_normalise_band_name` | function | 122 | Undocumented |
| `_match_band_to_role` | function | 126 | Identify a band by its description, tolerating product-specific wording. |
| `profile_raster` | function | 143 | Describe a raster without reading pixels. |
| `read_window_indices` | function | 220 | Compute spectral indices over one window. |
| `_safe_divide` | function | 316 | Undocumented |
| `iter_windows` | function | 323 | Yield overlapping read windows covering the whole raster. |
| `raster_to_observations` | function | 343 | Produce a table of per-observation index values for the existing validators. |
| `_issue` | function | 396 | Undocumented |
| `validate_raster` | function | 407 | Check a raster before any index is computed from it. |
| `raster_report` | function | 481 | Full raster summary for a manifest or report. |

### [`geoqa/validations/reference_cases.py`](../geoqa/validations/reference_cases.py)

Published reference cases, so the coefficients can be checked rather than trusted.

Validator reference: [`reference_cases`](modules/reference_cases.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ReferenceCase` | class | 89 | One published worked example. |
| `ReferenceCase.as_dict` | function | 107 | Undocumented |
| `ReferenceCaseResult` | class | 122 | The outcome of running one case. |
| `ReferenceCaseResult.as_dict` | function | 131 | Undocumented |
| `aqua1999_uarl_example` | function | 149 | The end-of-paper worked example from Lambert et al. (1999). |
| `aqua1999_tirl_case` | function | 184 | TIRL and ILI from the same AQUA example, which are rounding-independent. |
| `aqua1999_ili_case` | function | 202 | ILI from the AQUA example: 202 / 42 = 4.8. |
| `iwa_taskforce_uarl_case` | function | 218 | The IWA Task Force worked example, which reproduces exactly. |
| `lambert2009_background_leakage_case` | function | 236 | Background leakage at 50 m, Lambert (2009). |
| `all_reference_cases` | function | 259 | Every published case this module can check. |
| `_coefficient` | function | 274 | Load the declared coefficient the implementation actually uses. |
| `compute_reference_case` | function | 293 | Compute the case's quantity using the library's own functions. |
| `run_reference_case` | function | 332 | Execute one case and compare against the published value. |
| `run_reference_cases` | function | 354 | Execute every case. Returns a result per case, pass or fail. |
| `check_uarl_applicability` | function | 359 | Is this network inside the range the UARL equation was derived for? |
| `_issue` | function | 397 | Undocumented |
| `validate_reference_cases` | function | 408 | Run the published cases and report any that do not reproduce. |
| `validate_uarl_applicability` | function | 457 | Report use of the UARL equation outside its stated range. |

### [`geoqa/validations/repeat_incident.py`](../geoqa/validations/repeat_incident.py)

Cross-period recurrence: the same finding appearing in more than one period.

Validator reference: [`repeat_incident`](modules/repeat_incident.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `RepeatFinding` | class | 52 | One recurring location, across two or more periods. |
| `RepeatFinding.period_count` | function | 63 | Undocumented |
| `RepeatFinding.repeats` | function | 67 | Undocumented |
| `RepeatFinding.as_dict` | function | 70 | Undocumented |
| `RepeatProfile` | class | 84 | Undocumented |
| `RepeatProfile.summary` | function | 92 | Undocumented |
| `_geometry` | function | 103 | Undocumented |
| `_asset_id` | function | 112 | Undocumented |
| `detect_period_gaps` | function | 119 | Report consecutive periods that are present but non-contiguous. |
| `_period_sort_key` | function | 143 | Undocumented |
| `_period_distance` | function | 148 | Number of nominal periods between two resolved labels. |
| `_period_key` | function | 153 | Return (year, index) for a recognisable period label, else None. |
| `profile_repeats` | function | 182 | Find locations recurring across periods, distinguishing cause. |
| `_same_place` | function | 302 | Are two geometries the same location for recurrence purposes? |
| `_issue` | function | 322 | Undocumented |
| `validate_repeats` | function | 333 | Report recurring locations and the gaps that weaken the claim. |

### [`geoqa/validations/sentinels.py`](../geoqa/validations/sentinels.py)

Placeholder values that pass a null check but are not null.

Validator reference: [`sentinels`](modules/sentinels.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_is_nullish` | function | 68 | Undocumented |
| `detect_sentinels` | function | 76 | Return the sentinel pattern this value matches, or ``None``. |
| `sentinel_report` | function | 114 | Count sentinel values per column without judging them. |
| `validate_sentinels` | function | 148 | Report columns whose placeholder values will be read back as answers. |

### [`geoqa/validations/shape.py`](../geoqa/validations/shape.py)

Slivers: thin geometry, and geometry that is simply too small.

Validator reference: [`shape`](modules/shape.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `ShapeProfile` | class | 60 | Measured shape characteristics of one geometry, or of a whole layer. |
| `ShapeProfile.to_dict` | function | 71 | Undocumented |
| `_parts` | function | 83 | Undocumented |
| `_measure` | function | 93 | Undocumented |
| `_iter_coords` | function | 135 | Yield the XY of every coordinate of any geometry, whatever its type. |
| `_max_centroid_distance` | function | 178 | Upper bound on the inward buffer that removes the geometry entirely. |
| `_erosion_width` | function | 201 | Bisect the inward buffer that removes the geometry entirely. |
| `profile_shape` | function | 242 | Measure every feature without judging any of them. |
| `below_minimum_feature_area` | function | 275 | Report features at or below a declared area floor. |
| `thin_geometry` | function | 332 | Report polygons thinner than twice ``minimum_width``, anywhere. |
| `elongation_report` | function | 413 | Report polygons whose length-to-width ratio exceeds a declared limit. |
| `validate_shape` | function | 459 | Run whichever shape checks the caller supplied thresholds for. |

### [`geoqa/validations/spatial_statistics.py`](../geoqa/validations/spatial_statistics.py)

Spatial statistics: the part of the mathematics that describes patterns

Validator reference: [`spatial_statistics`](modules/spatial_statistics.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `SpatialWeights` | class | 93 | A row-standardised weight matrix, with the method recorded. |
| `SpatialWeights.s0` | function | 109 | Undocumented |
| `SpatialWeights.neighbor_counts` | function | 113 | Undocumented |
| `SpatialWeights.to_dict` | function | 117 | Undocumented |
| `_coordinates` | function | 128 | Undocumented |
| `build_weights` | function | 146 | Build a spatial weight matrix. |
| `_queen_matrix` | function | 194 | Polygon contiguity by shared boundary, not merely shared vertex. |
| `_row_standardise` | function | 224 | Undocumented |
| `MoransIResult` | class | 240 | Undocumented |
| `MoransIResult.to_dict` | function | 249 | Undocumented |
| `morans_i` | function | 261 | Global Moran's I with the normal-approximation z-score. |
| `_permutation_inference` | function | 301 | Return the permutation variance and a standardised z-score. |
| `_interpret_moran` | function | 330 | Undocumented |
| `GearysCResult` | class | 341 | Undocumented |
| `GearysCResult.to_dict` | function | 349 | Undocumented |
| `gearys_c` | function | 360 | Geary's C. Expectation is 1; below 1 means clustering, above 1 means alternation. |
| `_interpret_geary` | function | 401 | Undocumented |
| `LocalMoranResult` | class | 417 | Per-feature contribution to global autocorrelation. |
| `LocalMoranResult.counts` | function | 426 | Undocumented |
| `LocalMoranResult.to_dict` | function | 432 | Undocumented |
| `local_moran` | function | 441 | Local Moran (LISA): each feature's contribution to the global pattern. |
| `getis_ord_gi_star` | function | 482 | Getis-Ord Gi*: is this value *and its neighbourhood* jointly extreme. |
| `variogram` | function | 521 | Empirical semivariogram: squared dissimilarity against distance. |
| `SpatialStatisticsProfile` | class | 585 | What a single attribute column looks like once space is accounted for. |
| `SpatialStatisticsProfile.to_dict` | function | 598 | Undocumented |
| `spatial_outliers` | function | 612 | Find values that are wrong *relative to their neighbours*. |
| `profile_spatial_statistics` | function | 703 | Measure a column's spatial structure without judging any feature. |

### [`geoqa/validations/spectral.py`](../geoqa/validations/spectral.py)

spectral.py — Satellite / spectral index anomaly validators for GeoQA

Validator reference: [`spectral`](modules/spectral.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_is_finite_number` | function | 52 | Undocumented |
| `validate_spectral_indices` | function | 60 | Deterministic spectral-index anomaly checks for tabular/vector layers that |
| `validate_spectral_indices.<locals>._key_for` | function | 121 | Undocumented |
| `validate_band_radiance` | function | 231 | Band-level QA for TOA radiance / reflectance tables (e.g., Tanager 426-band |

### [`geoqa/validations/tabular.py`](../geoqa/validations/tabular.py)

Tabular validation for CSV and Excel, before anything spatial touches them.

Validator reference: [`tabular`](modules/tabular.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_is_null` | function | 67 | Is this cell value one of the many ways a spreadsheet says "nothing"? |
| `_issue` | function | 85 | Undocumented |
| `_is_excel` | function | 96 | Undocumented |
| `_is_csv` | function | 100 | Undocumented |
| `_import_openpyxl` | function | 104 | Undocumented |
| `_looks_like_identifier` | function | 114 | Undocumented |
| `_looks_like_date` | function | 125 | Undocumented |
| `_looks_like_numeric_id` | function | 130 | Do these all-numeric-looking values have a leading zero or unusual length? |
| `_parse_dates` | function | 144 | Find slash or dash dates that are ambiguous between day-first and month-first. |
| `ColumnProfile` | class | 168 | One column, described without judging it. |
| `ColumnProfile.null_fraction` | function | 181 | Undocumented |
| `ColumnProfile.is_identifier_like` | function | 185 | Undocumented |
| `ColumnProfile.is_date_like` | function | 189 | Undocumented |
| `ColumnProfile.as_dict` | function | 192 | Undocumented |
| `TabularProfile` | class | 206 | What a table is, before any condition is decided. |
| `TabularProfile.column_names` | function | 226 | Undocumented |
| `TabularProfile.as_dict` | function | 229 | Undocumented |
| `_read_csv_text` | function | 251 | Undocumented |
| `_sniff_delimiter` | function | 262 | Undocumented |
| `_profile_columns` | function | 273 | Undocumented |
| `profile_tabular` | function | 297 | Describe a CSV or workbook. Reads structure, not data. |
| `_profile_csv` | function | 311 | Undocumented |
| `_profile_excel` | function | 344 | Undocumented |
| `validate_tabular` | function | 392 | Report conditions that will corrupt or hide data downstream. |
| `_looks_like_identifier_values` | function | 640 | Re-check an identifier column for leading zeros or excessive length. |
| `read_csv_rows` | function | 657 | Read a CSV as plain strings. |

### [`geoqa/validations/topology.py`](../geoqa/validations/topology.py)

Validation implementation for topology; see the linked module reference when available.

Validator reference: [`topology`](modules/topology.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_geometry` | function | 9 | Undocumented |
| `_pairwise_rows` | function | 16 | Undocumented |
| `_geometry_bounds` | function | 23 | Undocumented |
| `_query_sindex_positions` | function | 34 | Undocumented |
| `_meter_tolerance_to_degree_radius` | function | 55 | Convert a meter tolerance into a safe-inclusive degree search radius. |
| `_endpoint_candidate_provider` | function | 107 | Build a spatial candidate provider over endpoint items. |
| `_endpoint_candidate_provider.<locals>.provider` | function | 149 | Undocumented |
| `_linear_endpoint_pair` | function | 166 | Undocumented |
| `_linear_endpoint_pair.<locals>._coords_from_geom` | function | 170 | Undocumented |
| `_pairwise_rows_spatial` | function | 207 | Undocumented |
| `_reference_candidates` | function | 234 | Undocumented |
| `polygon_overlap_same_layer` | function | 245 | Detect overlapping polygon features within the same layer. |
| `feature_within_feature` | function | 284 | Detect features fully contained within another feature of the same layer. |
| `line_intersection_same_layer` | function | 323 | Detect line intersections in the same layer where only endpoint connections are expected. |
| `duplicate_geometry_same_layer` | function | 363 | Detect features whose geometry exactly duplicates another feature in the same layer. |
| `line_dangle` | function | 408 | Detect line features with endpoint degree 1 that are not explicitly allowed service endpoints. |
| `line_dangle.<locals>._normalize_point` | function | 424 | Undocumented |
| `_normalize_endpoint` | function | 469 | Undocumented |
| `_line_endpoints` | function | 477 | Undocumented |
| `_row_role_value` | function | 495 | Undocumented |
| `polygon_gap_same_layer` | function | 507 | Detect interior gaps in polygon coverage by dissolving the layer and inspecting holes. |
| `polygon_gap_same_layer.<locals>._emit_gap` | function | 534 | Undocumented |
| `polygon_gap_same_layer.<locals>._inspect_polygon` | function | 551 | Undocumented |
| `feature_not_split_at_intersection` | function | 574 | Detect lines that cross at an interior point without being split into network nodes. |
| `isolated_network_segment` | function | 614 | Detect segments whose endpoints are both isolated from the rest of the network. |
| `_endpoint_distance` | function | 641 | Undocumented |
| `_endpoint_distance_meters` | function | 645 | Undocumented |
| `_uses_geographic_distance` | function | 657 | Undocumented |
| `_row_feature_id` | function | 671 | Undocumented |
| `_nearest_endpoint_pair` | function | 685 | Undocumented |
| `_endpoint_pair_key` | function | 702 | Undocumented |
| `_endpoint_issue_extra` | function | 717 | Undocumented |
| `suspicious_near_miss_endpoints` | function | 736 | Detect endpoints that are close enough to suggest an unintended near miss. |
| `unsnapped_endpoints_within_tolerance` | function | 805 | Detect endpoints within snapping tolerance that remain disconnected. |
| `boundary_mismatch_against_reference` | function | 880 | Detect polygon features whose boundary/area differs materially from the best matching |

### [`geoqa/validations/transform_audit.py`](../geoqa/validations/transform_audit.py)

What a geometry operation actually did.

Validator reference: [`transform_audit`](modules/transform_audit.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `geometry_metrics` | function | 36 | Measure what a geometry operation can silently change. |
| `buffer_zero_audit` | function | 64 | Report what ``buffer(0)`` would change, and whether it fully repairs. |
| `audit_repair` | function | 165 | Report per-feature differences between a layer and its repaired form. |
| `audit_attribute_preservation` | function | 215 | Report source keys and attributes lost by a merge, dissolve or rewrite. |

### [`geoqa/validations/vertical_datum.py`](../geoqa/validations/vertical_datum.py)

Vertical reference: datums, tidal references and elevation sign conventions.

Validator reference: [`vertical_datum`](modules/vertical_datum.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `VerticalProfile` | class | 94 | What a dataset says about its vertical reference, and what it implies. |
| `VerticalProfile.has_elevation` | function | 113 | Undocumented |
| `VerticalProfile.declares_its_reference` | function | 117 | Undocumented |
| `VerticalProfile.as_dict` | function | 120 | Undocumented |
| `_as_float` | function | 135 | Undocumented |
| `_column_kind` | function | 149 | Which kind of vertical quantity a column holds, if it says. |
| `_read_reference` | function | 163 | Find a declared vertical reference, from metadata or from the frame. |
| `profile_vertical` | function | 187 | Describe a dataset's vertical reference without judging it yet. |
| `_issue` | function | 250 | Undocumented |
| `validate_vertical_reference` | function | 261 | Report a vertical reference that is absent, ambiguous or contradicted. |
| `metres_to_feet` | function | 412 | Undocumented |
| `feet_to_metres` | function | 416 | Undocumented |

### [`geoqa/validations/water_balance.py`](../geoqa/validations/water_balance.py)

IWA water balance and non-revenue water analysis.

Validator reference: [`water_balance`](modules/water_balance.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `WaterBalanceInputs` | class | 75 | Volumes for a reporting period, in m3. Only supply is required. |
| `WaterBalanceInputs.__post_init__` | function | 104 | Undocumented |
| `WaterBalanceResult` | class | 112 | Computed balance, with every intermediate value retained. |
| `WaterBalanceResult.as_dict` | function | 133 | Undocumented |
| `compute_water_balance` | function | 155 | Compute the IWA water balance. |
| `_issue` | function | 246 | Undocumented |
| `validate_water_balance` | function | 257 | Check that a balance is internally consistent. |
| `nrw_from_components` | function | 424 | Convenience constructor from component dictionaries. |

### [`geoqa/validations/water_loss.py`](../geoqa/validations/water_loss.py)

Unavoidable Annual Real Loss and the Infrastructure Leakage Index.

Validator reference: [`water_loss`](modules/water_loss.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `PressureFactor` | class | 45 | Average pressure in the network, and how it was established. |
| `PressureFactor.as_dict` | function | 52 | Undocumented |
| `UarlInputs` | class | 61 | Network properties required by the UARL regression. |
| `UarlInputs.__post_init__` | function | 69 | Undocumented |
| `UarlInputs.average_pressure` | function | 91 | Mean pressure in metres, or the neutral factor of one when unknown. |
| `UarlInputs.as_dict` | function | 102 | Undocumented |
| `WaterLossAssessment` | class | 112 | The index, plus everything needed to interpret it. |
| `WaterLossAssessment.as_dict` | function | 125 | Undocumented |
| `_declaration_class` | function | 141 | Undocumented |
| `compute_uarl_l_per_day` | function | 147 | Unavoidable annual real loss, L/day. |
| `infrastructure_leakage_index` | function | 183 | ILI = CARL / UARL. Returns a value, never a verdict. |
| `ili_assessment` | function | 196 | Build an ILI assessment with its interpretation attached. |
| `_issue` | function | 280 | Undocumented |
| `validate_water_loss` | function | 291 | Check a water-loss assessment for the conditions that make it unusable. |
| `lambert_coefficient_templates` | function | 382 | Starter declarations carrying their published provenance. |

### [`geoqa/validations/workbook_media.py`](../geoqa/validations/workbook_media.py)

Embedded and referenced media in a spreadsheet.

Validator reference: [`workbook_media`](modules/workbook_media.md).

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_issue` | function | 87 | Undocumented |
| `_import_openpyxl` | function | 98 | Undocumented |
| `detect_image_format` | function | 109 | Identify an image from its leading bytes, or ``None``. |
| `Attachment` | class | 118 | One artefact attached to, or referenced by, a worksheet row. |
| `Attachment.longest_side` | function | 138 | Undocumented |
| `Attachment.is_embedded` | function | 142 | Undocumented |
| `Attachment.as_dict` | function | 145 | Undocumented |
| `MediaProfile` | class | 163 | What media a workbook holds, and how it attaches to rows. |
| `MediaProfile.attachments` | function | 181 | Undocumented |
| `MediaProfile.attachment_count` | function | 185 | Undocumented |
| `MediaProfile.rows_without_attachment` | function | 188 | Data rows carrying no attachment. Row 1 is the header, not a record. |
| `MediaProfile.as_dict` | function | 195 | Undocumented |
| `_media_parts` | function | 209 | Media inside the package, with leading bytes and a content hash. |
| `_anchor_position` | function | 226 | Row and column, 1-based, that a drawing anchor points at. |
| `profile_workbook_media` | function | 239 | Inventory media in a workbook, embedded and referenced. |
| `_scan_references` | function | 324 | Find attachments referenced by path rather than embedded. |
| `validate_workbook_media` | function | 358 | Check that the artefacts a workbook's rows depend on are actually there. |

### [`geoqa_web/__init__.py`](../geoqa_web/__init__.py)

Turn GeoQA findings into a browsable web-GIS site, slides, and charts.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `storyboard_from_report` | function | 39 | Derive a camera/filter storyboard from a report. |
| `_findings` | function | 65 | Normalise a report / GeoQAReport / FeatureCollection into a collection. |
| `_summary_payload` | function | 80 | Undocumented |
| `_utc_stamp` | function | 88 | Undocumented |
| `_escape` | function | 92 | Undocumented |
| `_read_template` | function | 96 | Undocumented |

### [`geoqa_web/charts.py`](../geoqa_web/charts.py)

Chart payloads for GeoQA findings.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_collection` | function | 26 | Undocumented |
| `_counts` | function | 40 | Undocumented |
| `chart_bundle` | function | 52 | Describe the standard set of charts for a findings collection. |
| `to_plotly` | function | 68 | Render a chart spec with Plotly (interactive HTML). |
| `to_d3` | function | 96 | Render a chart spec as a self-contained D3 + SVG fragment. |
| `_d3_bar` | function | 109 | Undocumented |
| `_d3_donut` | function | 126 | Undocumented |
| `render_chart_html` | function | 164 | Render every chart in the bundle as one HTML fragment. |
| `render_plotly_html` | function | 179 | Render the bundle as Plotly figures (returns the HTML of a div per chart). |
| `save_chart_assets` | function | 190 | Write ``charts.json`` plus D3 and Plotly HTML fragments. |

### [`geoqa_web/site.py`](../geoqa_web/site.py)

Build a self-contained web-GIS site from GeoQA findings.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_utc_stamp` | function | 13 | Undocumented |
| `_escape` | function | 17 | Undocumented |
| `_json_for_script` | function | 23 | Serialise JSON for embedding inside an inline <script> block. |
| `_collection` | function | 39 | Undocumented |
| `_layer_payload` | function | 53 | Accept GeoJSON paths, dicts, or GeoDataFrames and emit inline data. |
| `build_site` | function | 71 | Write a static web-GIS site for the given findings. |
| `_default_storyboard` | function | 139 | Undocumented |
| `build_full_package` | function | 147 | Build the site, a slide deck, and the chart assets together. |

### [`geoqa_web/slides.py`](../geoqa_web/slides.py)

Generate a presentation-ready slide deck from GeoQA findings.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_collection` | function | 19 | Undocumented |
| `slide_deck_from_report` | function | 33 | Build a declarative deck: title, headline numbers, rules, actions. |
| `slide_deck_from_report.<locals>.color_for` | function | 59 | Undocumented |
| `build_slides` | function | 154 | Write a self-contained ``index.html`` slide deck. |
| `_escape` | function | 179 | Undocumented |
| `_json_for_script` | function | 185 | Serialise JSON for an inline <script> block, neutralising ``</script>``. |

### [`scripts/annotate_geoqa_scripts.py`](../scripts/annotate_geoqa_scripts.py)

Project utility script.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_base_name` | function | 16 | Undocumented |
| `_uses_geoqa_script_base` | function | 26 | Undocumented |
| `_already_annotated` | function | 41 | Undocumented |
| `annotate_file` | function | 47 | Undocumented |
| `scan_directory` | function | 58 | Undocumented |
| `main` | function | 66 | Undocumented |

### [`scripts/run_evidence_suite.py`](../scripts/run_evidence_suite.py)

Run a declared suite of validation cases, verify each, and log the results.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `load_json` | function | 64 | Read JSON tolerating a UTF-8 BOM. |
| `extract_status` | function | 78 | Pull execution_status from wherever this report version put it. |
| `extract_issue_count` | function | 89 | Undocumented |
| `run_cli_case` | function | 101 | Undocumented |
| `run_callable_case` | function | 150 | For validators with no CLI surface, e.g. the spectral dataset type. |
| `write_log` | function | 190 | Undocumented |
| `compare_baseline` | function | 219 | Undocumented |
| `main` | function | 237 | Undocumented |

### [`scripts/run_integration_samples.py`](../scripts/run_integration_samples.py)

Project utility script.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_json_safe` | function | 166 | Undocumented |
| `_dataset_metrics` | function | 181 | Undocumented |
| `_memory_mb` | function | 211 | Undocumented |
| `_summarize_agent_result` | function | 220 | Undocumented |
| `_run_profile` | function | 234 | Undocumented |
| `parse_args` | function | 286 | Undocumented |
| `main` | function | 302 | Undocumented |

### [`scripts/validate_problem_catalog.py`](../scripts/validate_problem_catalog.py)

Project utility script.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `validate_catalog` | function | 34 | Undocumented |
| `main` | function | 78 | Undocumented |

### [`scripts/verify_chunking_equivalence.py`](../scripts/verify_chunking_equivalence.py)

Demonstrate the claim chunking makes, and the failure it prevents.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `build_layer` | function | 26 | Segments separated by a real gap, so endpoints have to adjudicate. |
| `triage_issues` | function | 47 | Validator form: yields issues rather than keys. |
| `triage_keys` | function | 52 | Undocumented |
| `main` | function | 56 | Undocumented |

### [`streamlit_app.py`](../streamlit_app.py)

Python source module.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_upload_signature` | function | 46 | Undocumented |
| `_normalize_local_path_input` | function | 50 | Undocumented |
| `_local_path_signature` | function | 57 | Undocumented |
| `_fix_signature` | function | 62 | Undocumented |
| `_best_point_label` | function | 66 | Undocumented |
| `_iter_positions` | function | 88 | Undocumented |
| `_geojson_center` | function | 97 | Undocumented |
| `_geojson_bounds` | function | 102 | Undocumented |
| `_zoom_for_bounds` | function | 115 | Undocumented |
| `_preview_map` | function | 140 | Undocumented |
| `_folium_bounds` | function | 273 | Undocumented |
| `_attributes_preview_frame` | function | 279 | Undocumented |
| `_dominant_geometry` | function | 287 | Undocumented |
| `_infer_preview_theme` | function | 294 | Undocumented |
| `_render_map_legend` | function | 421 | Undocumented |
| `_preview_data_tabs` | function | 440 | Undocumented |
| `_render_download_link` | function | 453 | Undocumented |
| `_geometry_token` | function | 467 | Undocumented |
| `_count_geometry_changes` | function | 473 | Undocumented |
| `_best_identifier_column` | function | 484 | Undocumented |
| `_shorten_text` | function | 505 | Undocumented |
| `_describe_step_details` | function | 511 | Undocumented |
| `_enabled_fix_steps` | function | 566 | Undocumented |
| `_suggest_chunk_size` | function | 589 | Undocumented |
| `_concat_chunks` | function | 599 | Undocumented |
| `_base_feedback` | function | 613 | Undocumented |
| `_record_step_result` | function | 627 | Undocumented |
| `_record_skipped_step` | function | 654 | Undocumented |
| `_direct_fix_pipeline` | function | 667 | Undocumented |
| `_chunked_fix_resume` | function | 739 | Undocumented |
| `_refresh_processed_views` | function | 803 | Undocumented |
| `_infer_source_format` | function | 809 | Undocumented |
| `_effective_output_format` | function | 827 | Undocumented |
| `_supports_direct_export` | function | 831 | Undocumented |
| `_set_processing_stage` | function | 835 | Undocumented |
| `_render_processing_status` | function | 840 | Undocumented |
| `_details_preview_table` | function | 860 | Undocumented |
| `_json_safe_scalar` | function | 877 | Undocumented |
| `_json_safe_value` | function | 886 | Undocumented |
| `_change_details_geojson` | function | 895 | Undocumented |

### [`tools/build_capability_workbook.py`](../tools/build_capability_workbook.py)

Generate the GeoQA capability workbook.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_collect_registry` | function | 26 | Undocumented |
| `_collect_validator_functions` | function | 55 | Undocumented |
| `_collect_modules` | function | 85 | Undocumented |
| `_collect_profiles` | function | 112 | Undocumented |
| `_profile_purpose` | function | 137 | Undocumented |
| `_coverage_summary` | function | 152 | Where GeoQA is strong, thin, or absent. Deliberately opinionated. |
| `_roadmap` | function | 401 | Undocumented |
| `build` | function | 542 | Undocumented |
| `build.<locals>.write_sheet` | function | 566 | Undocumented |

### [`tools/generate_module_docs.py`](../tools/generate_module_docs.py)

Generate one Markdown page per validation module from the live registry.

| Definition | Kind | Line | Description |
|---|---|---:|---|
| `_first_paragraph` | function | 53 | Undocumented |
| `_sections` | function | 64 | Section headings from a module docstring, for the generated page. |
| `module_conditions` | function | 80 | Problem names this module can emit, read from its source. |
| `public_validators` | function | 108 | Public validate_* functions and their first docstring line. |
| `build_pages` | function | 122 | Undocumented |
| `main` | function | 202 | Undocumented |
| `main.<locals>.sort_key` | function | 211 | Undocumented |

## Notes

- `geoqa` is the importable library; the `geoqa` console command is registered in `pyproject.toml` and dispatches to `geoqa.cli.main:run`.
- Optional extras and external data readers are described in `pyproject.toml`; not every optional feature is available in a minimal installation.
- Inventory generated from source syntax: 143 Python files and 1393 functions, methods, nested functions, and classes.
