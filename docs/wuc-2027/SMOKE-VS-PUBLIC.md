# Smoke/Proxy vs Public WUC Datasets — Honest Labelling

**Date:** 2026-09-02
**Branch:** wuc-2027

## What `reports/wuc-2027/ds1..ds5` Actually Are

| File | What it is | What it is NOT |
|---|---|---|
| `ds1.json` (8,491B) | `duplicate_vertex_line.geojson` (1 feature) via `generic_quick --low-resource` → 2 issues, execution_status full (summary.execution_status) | Not Natural Earth roads 56,600 feats public run |
| `ds2.json` (8,552B) | `self_intersection_polygon.geojson` (1 feature) via `generic_quick --low-resource` → 2 issues, full | Not OSM HOT Oman waterways |
| `ds3.json` (20,309B) | same line via `water_network` profile | Not zoning polygons |
| `ds4.json` (17,036B) | same polygon via `water_network` profile | Not admin boundaries |
| `ds5-spectral.json` (3,223B) | Synthetic 4-row DataFrame with NDVI/NDWI temporal spike reflecting Tanager VR-5 (+0.252 vs -0.080, delta 0.332 >0.30) via `geoqa/validations/spectral.py` | Not flood/places data nor real raster zonal stats |

**Label:** `smoke/proxy validation cases — not the five public WUC showcase datasets`

They prove: the `python -m geoqa validate --low-resource` run path works, `wuc_run_log.csv` replay works, `validate_csv_evidence.py` read-only verification works (5× PASS). They do NOT prove the 5 WUC public URLs reproduce.

## What the Five Public WUC Showcase Datasets Are (Not Yet Executed)

As specified in `apps/wuc-atlas/README.md` and `WUC-2027-Plan-of-Action-Professor.docx`:

1. Natural Earth roads 56,600 feats — `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip` (proxy for front-center proof)
2. OSM HOT Oman waterways near Muscat — HOT HDX, provenance in `docs/water-network-source-research.md`
3. Zoning polygons (GeoQA Atlas demo)
4. Admin boundaries — Natural Earth Admin 1 + geoBoundaries FRA/USA/BRA/JPN/KEN/OMN (20 URLs in `Supplementary -TGIS.docx`)
5. Flood zones / Places — Philadelphia FEMA flood plain 2023 + places

These have public URLs but have **not yet been executed** in `reports/wuc-2027/` as full 5× byte-identical reports. Do not conflate.

## Why This Distinction Matters

WUC Abstract 29243 was rejected for lacking `detailed case studies, real-life project applications, measurable outcomes`. Claiming smoke proxies as public datasets would repeat that overclaim. The abstract now correctly states: `The broader GeoQA sandbox spans 20 public data sources; the current WUC demonstration uses five smoke/proxy validation cases — not yet five executed public-dataset validations.`

## Next Step to Verify Public Datasets

To promote from smoke to public, run for each of the 5 real public URLs:
```
python -m geoqa validate <URL> --low-resource --max-runtime-seconds 180 --report-path reports/wuc-2027/wuc-ds1-roads-56600.json
```
and commit the resulting JSONs with `execution_status full`, `feature_count 56,600`, `issue counts 42/6/1` matching `docs/benchmark_story.md` and `docs/tests.md` provenance.

Until then: **public five-dataset reproduction NOT YET ESTABLISHED**.

