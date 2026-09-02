# WUC Atlas — WUC-2027 Mode for GeoQA

This folder is the WUC-2027 extension of the existing GeoQA Atlas (`apps/atlas`, live at https://geo-qa-pi.vercel.app/).

**Do not rebuild Tanager cinematic.** This reuses:

- `apps/atlas` dark map, dataset gallery, map workspace, issue drawer, report download, Run QA preview (sampled 20 points / 5 lines-polygons)
- Tanager cinematic pattern `cinematic/src/components/SceneStage.tsx` intro→data→take + `director.ts` timeline, but swapped for operational tabs

## One-Page Layout — Code → Run → Map → Table + Peace Story

For WUC judges — 5 datasets, each different aspect + “what if not caught” true story from `C:\Users\admin\Python\Ethics\Papers\GeoAI-Incident.md`.

```
[Left: Code Terminal (animated replay)] [Center: Map (DMA polygons + issue overlays red)] [Right: Results Table + Story]
python -m geoqa validate dataset_3.shp --profile water_network --low-resource → 49 issues (42 dup-vertex, 6 self-intersection, 1 stale index)
Provenance: dataset: Natural Earth roads | 56,600 feats | CRS EPSG:4326 | URL: https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip | SHA: 940BEA... | Repro: python -m geoqa validate <URL> --low-resource
Why this matters + What if not caught — true story: Slide 2 Annexation HALT / Slide 5 No pipe / Slide 6 Sunday dry tap / Slide 7 50% majority-area rule / Slide 8 Hydrant missing
```

## 5 Datasets — Different Aspect Each

| # | Dataset (public URL) | Aspect / GeoQA Check | True Story (Peace Slide) | Findings (precomputed `reports/wuc-2027/`) |
|---|---|---|---|---|
| 1 | Natural Earth roads 56,600 feats — naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip | Duplicate vertices + stale spatial index | Slide 1 GPS lost trust — network tracing fails | ds1.json: 2 issues (proxy for 49) |
| 2 | Self-intersection polygon (edge case) | Self-intersection polygon | Slide 3 Annexation halt | ds2.json: 2 issues |
| 3 | Water network — duplicate_vertex_line with water_network profile | Topology + attribute QA | Slide 2 Bulk clipping misassignment | ds3.json: water_network profile |
| 4 | Water network strict — self_intersection | Strict water network | Slide 7 Boundary dispute 50% rule | ds4.json |
| 5 | Spectral anomaly demo — synthetic zonal NDVI/NDWI (Tanager VR-5 pattern) | ndvi_temporal_spike (|delta|>0.30 catches +0.252→-0.080), ndwi_ndvi_inconsistency | Spectral guardrail for satellite QA | ds5-spectral.json: 3 issues |

All public, committed as committed tables (as Tanager `tanager/tables`). No confidential utility mains — OSM HOT Oman waterways labeled as public water/drainage line data per `Atlas README`.

## WUC Mode Flag

- Development: `VITE_WUC_MODE=true` in `apps/wuc-atlas/.env.local` enables WUC tabs and terminal animation.
- Production: `https://geo-qa-pi.vercel.app/wuc` reads from `reports/wuc-2027/` (no live Python exec in browser; terminal animation replays committed `wuc_run_log.csv`).
- Existing `https://geo-qa-pi.vercel.app/` remains stable — WUC mode is feature-flagged, not a fork.

## Component to Build

- `WucStoryBeats.tsx` — reuse `cinematic/src/components/StoryBeats.tsx` + `SceneStage.tsx` intro→data→take
- `WucTerminal.tsx` — animated playback of `wuc_run_log.csv`
- `WucDatasetTabs.tsx` — 5 tabs → map pulse + table + story panel

## Deploy

- Branch: `wuc-2027`
- Vercel: Root Directory `apps/wuc-atlas`, Build `npm run build`, Output `dist`
- QR code for WUC slides points to preview URL + GitHub commit tag `v0.3.1-wuc-2027-verified`
- Fallback: recorded walkthrough video `wuc-demo-5tabs.mp4` for offline conference WiFi

## Relationship to Existing Atlas

- Keep `apps/atlas` stable for public demo
- `apps/wuc-atlas` imports map components, issue drawer, and report download from `apps/atlas/src`
- No duplication of validator logic — `geoqa` Python package remains source of truth

See `G:\My Drive\Nilofer-Docs\WUC\WUC-2027\WUC-2027-Plan-of-Action-Professor.docx` Phase 2-4 for full scaffold spec.
