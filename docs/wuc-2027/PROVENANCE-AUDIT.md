# Provenance Audit — Natural Earth 56,600 / 49 and 745-Script Inventory

**Date:** 2026-09-02 | **Branch:** wuc-2027 | **Reviewer:** Evidence-first checklist per task §§5-7

## 1. Natural Earth 56,600 features → 49 findings (42 duplicate_vertex, 6 self_intersection, 1 stale index)

**Claim as corrected in abstract:** `The Natural Earth 56,600-feature/49-finding benchmark is cited from existing GeoQA documentation and remains needs-evidence until a committed artifact provides URL, SHA, feature count, issue counts, execution status, and runtime.`

**What committed evidence currently exists:**

| Element | Required | Actual artifact (2026-09-02) | Verdict |
|---|---|---|---|
| Source URL | URL to Natural Earth roads download | `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip` — listed in `apps/wuc-atlas/README.md` table and `WUC-website-verification.md`, but **not** in a committed `reports/wuc-2027/wuc-ds1-roads-56600.json` SHA field | **Needs evidence — URL exists but not in committed WUC report** |
| SHA-256 | Hash of downloaded dataset | **Not present** in any `reports/wuc-2027/*.json` — Tanager pattern publishes `940BEA...` for Scene B, but GeoQA roads SHA not recorded in `docs/benchmark_story.md` or `docs/tests.md` | **Needs evidence** |
| Feature count | 56,600 | Documented in `docs/benchmark_story.md: Headline Benchmark — size: 56,600 features` and `docs/tests.md: Fresh Low-Resource Public Benchmark Rerun — feature count: 56,600` and `README.md Front-and-Center Proof: 56,600` | **Evidence exists — but in docs, not in WUC report** |
| Issue counts | 49 (42/6/1) | Documented in `docs/tests.md` Fresh Low-Resource Rerun — `issue count: 49, dominant findings were: duplicate_vertex: 42, self_intersection: 6, missing_or_stale_spatial_index: 1` and `README.md` | **Evidence exists — docs, not WUC report** |
| Execution status | full | Documented in `docs/tests.md` — `execution status: full` and `docs/benchmark_story.md` — `result: full completion` | **Evidence exists — docs** |
| Runtime | ~122 seconds (and ~121.9s) | Documented in `docs/tests.md` — `duration: about 121.9 seconds` and `README.md` — `about 122 seconds on a heat-limited workstation` | **Evidence exists — docs, range 121.9–122s** |

**Conclusion:** The `56,600 → 49 (42/6/1)` is **cited from existing GeoQA documentation** (`docs/benchmark_story.md`, `docs/tests.md`, `README.md`), but **no committed `reports/wuc-2027/wuc-ds1-roads-56600.json` under `wuc-2027` branch** yet contains all six fields together with SHA and URL. Therefore the WUC abstract correctly labels it `needs-evidence` and the `reports/wuc-2027/ds1.json` smoke proxy must not be presented as that benchmark. To promote to evidence-backed, create `reports/wuc-2027/wuc-ds1-roads-56600.json` via `python -m geoqa benchmark data/public_samples/natural_earth/ne_10m_roads/ne_10m_roads.shp --profile generic_quick --low-resource --max-runtime-seconds 180` and commit with `dataset provenance: URL + SHA-256` in `dataset_provenance.csv`.

---

## 2. 745-Script Inventory — Precise Documentation

**Authoritative inventory artifact:** `G:\My Drive\Python-G-drive\GIS-Department\GIS-Department\scripts\python_script_inventory.txt`

**Precise description (for abstract/paper):**

- **What was counted:** 745 Python scripts catalogued by inventory generator
- **Date of inventory:** `2025-11-12 08:08:24` (first line of file)
- **Base folder:** `C:/Users/admin/OneDrive/Nilofer-Private/Coding/Python` (line 2 of file) — Note: this is the private OneDrive Python mirror, not `G:\My Drive\Python-G-drive\GIS-Department` alone
- **What was excluded:** `env/cache directories excluded` (line 4, parenthetical)
- **Major categories represented (sample from file):**
  - `AI\Local-RAG` (file_loaders, ollama_client, query_engine, rag_engine, text_splitter)
  - `Automation` (Bulk-Emailing, GIS-Cloud-Automation, SEWA-Reports, WVT-Login-Details)
  - `DBA-Scripts` (Benchmarking, EOQ, Hypothese-N streamlit pages)
  - `EWA\EWA-Weekly-Report` (EWA-field_work_weekly_report.py, EWA-Filling-Weekly-Report.py 158 lines, Leak-Investigation, etc.)
  - `GIS-Department\modules` (add_columns_manager, agent_memory 452 lines, dma_utils, gis_downloader, etc.)
  - `GIS-API-Multiply-Files.py`, `EWA-DMA-Extract-Convert-Info.py`, etc.
- **Where stored:** `G:\My Drive\Python-G-drive\GIS-Department\GIS-Department\scripts\python_script_inventory.txt` (also noted as `C:/Users/admin/OneDrive/Nilofer-Private/Coding/Python` generation base)
- **What it is NOT:** Validation or impact by itself — it is an *inventoried body of automation scripts* spanning 3.9-year solo GIS department build, not a claim of 745 distinct contributions.

**Wording in corrected abstract:** `an inventoried body of 745 Python automation scripts (2025-11-12 inventory, env/cache excluded, GIS-Department/scripts/python_script_inventory.txt)` — matches this audit.

---

## 3. 4h → 12min Operational Result — Not Yet Verified

**Claim examined:** `weekly report 4h manual → 12 min automated` and `HALT prevention of a bulk boundary misassignment`

**Evidence search (2026-09-02):**

- No committed artifact in `G:\My Drive\Python-G-drive\GeoQA\reports\wuc-2027\` contains paired measurements `4h` and `12min` for the same workflow.
- No log file in `G:\My Drive\Python-G-drive\GIS-Department\` was found with explicit `4h` manual timing and `12min` automated timing for comparable scope.
- The weekly report automation is real: `EWA-Filling-Weekly-Report.py` (158 lines, purpose: automatically fills weekly and complete project report for Oman), `EWA-Weekly-Report.py`, `Leak-Investigation.py`, etc., demonstrate the automated side, but the manual baseline `4h` is not logged with date/environment.
- The HALT prevention narrative is supported by `C:\Users\admin\Python\Ethics\Papers\GeoAI-Incident.md:1` Incident 1 *Administrative Boundary Misassignment (Bulk Clipping)* — `What happened: bulk clipping assigned water asset leak records to incorrect administrative boundaries` — but the `4h→12min` number itself is **memory, not measured comparison**.

**Conclusion:** Label `4h → 12min` as **`not yet verified`** and **removed from abstract** per instruction. If comparable evidence exists (e.g., dated manual timesheet vs automated run log for same weekly report scope), record:

- workflow name (e.g., `EWA Weekly Report — Oman DMA/Wilayat`)
- scope (e.g., `3 utilities, 2,000 DMAs`)
- source of 4h measurement (timesheet, dated)
- source of 12min measurement (run log timestamp)
- measurement method (wall-clock with `time` or `psutil`)
- date/environment (workstation, Python version)

Until then, do not claim the number.

