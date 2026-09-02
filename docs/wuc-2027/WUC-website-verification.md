# WUC Website Verification — 11 Criteria (Professor Acceptance Checklist)

**Status: Phase 4 scaffold — NOT VERIFIED**
**File:** `apps/wuc-atlas/` on branch `wuc-2027` at `G:\My Drive\Python-G-drive\GeoQA`
**Date checked:** 2026-09-02
**Reviewer rule:** Do not claim functional until all 11 pass. `Todo completed` ≠ verification.

| # | Criterion | Required | Actual Result (2026-09-02) | Verdict |
|---|---|---|---|---|
| 1 | `apps/wuc-atlas` builds successfully with `npm run build` | `npm run build` exits 0, `dist/` produced | **NOT TESTED** — `package.json` does not exist in `apps/wuc-atlas` (only in `apps/atlas`). Build would fail: missing `tsc -b && vite build` config. No `dist/` | **FAIL — NOT VERIFIED** |
| 2 | The WUC route/component actually renders | `WucStoryBeats.tsx` renders at `/wuc` route | **NOT VERIFIED** — file exists `WucStoryBeats.tsx` (31 lines stub) but not imported into any router (`apps/atlas/src` router not extended), no `/wuc` route defined | **FAIL** |
| 3 | Five dataset tabs/cards render | 5 tabs visible, each with name/URL | **NOT VERIFIED** — `WUC_DATASETS` array exists in stub, but no `WucDatasetTabs.tsx`, no tabs mounted, no UI test | **FAIL** |
| 4 | Each tab displays its actual committed provenance | Source URL, SHA-256, feature count, CRS, report path | **PARTIAL** — `WUC_DATASETS` has name + URL strings, but SHA, feature count, CRS are placeholder strings, not read from `reports/wuc-2027/*.json` or `dataset_provenance.csv` (which does not exist yet) | **FAIL** |
| 5 | Terminal animation replays committed `wuc_run_log.csv` | Animated playback, not pretending to execute | **NOT VERIFIED** — No `WucTerminal.tsx`, no log replay. `wuc_run_log.csv` exists at `reports/wuc-2027/wuc_run_log.csv` but not consumed by any component | **FAIL** |
| 6 | Result tables populated from committed reports | Table rows from `ds1.json` etc. | **NOT VERIFIED** — No table component, no `fetch/reports/wuc-2027/ds*.json` | **FAIL** |
| 7 | Map issue highlighting actually works | `duplicate_vertex`, `self_intersection`, `near-miss gap connector` highlights | **NOT VERIFIED** — No map integration; `apps/atlas` map exists but `apps/wuc-atlas` has no map component, no issue overlay wiring | **FAIL** |
| 8 | Story panel contains only evidence-backed text | True stories from `GeoAI-Incident.md` with provenance | **NOT VERIFIED** — Stories described in `apps/wuc-atlas/README.md` but no `Peace Slide 2-8` text committed to component; risk of aspirational narrative | **FAIL** |
| 9 | Vercel preview deployment exists and is accessible | `https://...vercel.app/wuc` returns 200 | **NOT VERIFIED** — Existing site `https://geo-qa-pi.vercel.app/` is production `apps/atlas`, not `apps/wuc-atlas`. No preview deployment for `wuc-2027` branch exists | **FAIL** |
| 10 | Screenshots of each verified tab captured and stored | `docs/wuc-2027/WUC-website-verification.md` + `docs/assets/wuc-*.png` | **NOT VERIFIED** — This file is the checklist itself; no screenshots exist | **FAIL** |
| 11 | Preview URL recorded in `reports/wuc-2027/REPRODUCIBILITY.md` | URL string in manifest | **NOT VERIFIED** — `REPRODUCIBILITY.md` does not contain a preview URL (contains only local repro steps) | **FAIL** |

**Overall Phase 4:** `SCAFFOLD ONLY / NOT VERIFIED` — 0/11 pass, 1/11 partial. This matches the instruction to label Phase 4 as `scaffold — not verified` until all 11 pass.

**Next steps to verify:**
1. Create `apps/wuc-atlas/package.json` (copy from `apps/atlas/package.json` + add `wuc` route), 2. Implement `WucStoryBeats.tsx` → `WucDatasetTabs.tsx` + `WucTerminal.tsx` wired to `reports/wuc-2027/`, 3. Run `npm run build` and capture `dist/`, 4. Deploy Vercel preview, 5. Screenshot 5 tabs, 6. Update this file to PASS rows and write URL into `reports/wuc-2027/REPRODUCIBILITY.md`.

**Honesty note:** Do not create fake map behavior or fake execution results to satisfy visual requirement — as per instruction. Until this file shows 11 PASS, Phase 4 remains NOT VERIFIED in `journal.md` and `todo`.

