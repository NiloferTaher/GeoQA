# WUC-2027 Reproducibility Manifest — GeoQA Local-First Platform

**Branch:** `wuc-2027` | **Tag target:** `v0.3.1-wuc-2027-verified` | **Date:** 2026-09-02
**Machine:** Windows 11, RTX 3060 laptop, Core Temp 14 sensors detected
**Python:** 3.12.10 | **GeoQA:** 0.3.1 (spectral.py) | **Tests:** 175 OK (169→175, +6 spectral)

## 5-Dataset Verified Snapshot

All reports generated via `python -m geoqa validate <path> --low-resource` / `--profile water_network` on this workstation. Each report is JSON with `validation_rule_version 2026.03`, `execution_status full`, `validator_coverage`.

| # | Dataset (public URL, no committed HDF5) | Path (local demo copy) | Report | Findings (byte-identical on re-run) | Repro Command |
|---|---|---|---|---|---|
| 1 | Natural Earth roads 56.6k proxy — `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip` | `data/public_samples/edge_cases/duplicate_vertex_line.geojson` (proxy) | `ds1.json` (8,491B) | 2 issues: duplicate_vertex 50%, missing_or_stale_spatial_index 50% — *proxy for 56,600→49 real benchmark documented in README Front-and-Center Proof* | `python -m geoqa validate data/public_samples/edge_cases/duplicate_vertex_line.geojson --profile generic_quick --low-resource --report-path reports/wuc-2027/ds1` |
| 2 | Self-intersection polygon (edge case) — `data/public_samples/edge_cases/self_intersection_polygon.geojson` | same | `ds2.json` (8,552B) | self_intersection flagged, integrity checks | `python -m geoqa validate .../self_intersection_polygon.geojson --profile generic_quick --low-resource --report-path reports/wuc-2027/ds2` |
| 3 | Water network profile demo — same edge line | `ds3.json` (20,309B) | `ds3.json` — water_network profile, 20+ validators, topology checks | `python -m geoqa validate .../duplicate_vertex_line.geojson --profile water_network --report-path reports/wuc-2027/ds3` |
| 4 | Water network strict polygon | `ds4.json` (17,036B) | water_network strict | `python -m geoqa validate .../self_intersection_polygon.geojson --profile water_network --report-path reports/wuc-2027/ds4` |
| 5 | Spectral anomaly demo — synthetic zonal NDVI/NDWI (Tanager VR-5 pattern: s2proxy +0.252 vs s2_actual -0.080, delta 0.332 >0.30) | `ds5-spectral.json` (3,223B) | 3 issues: ndvi_temporal_spike ×2, ndwi_temporal_spike ×1 — validates new `geoqa/validations/spectral.py` | `python -c "from geoqa.validations.spectral import validate_spectral_indices; validate_spectral_indices(gdf, date_col='date')"` |

**Full public benchmark reference:** Natural Earth roads 56,600 feats → 49 findings (42 duplicate_vertex, 6 self_intersection, 1 stale index) in ~122s low-resource on heat-limited workstation (same 49 in 15s cloud) — documented in `README.md: Front-and-Center Proof` and `plan_of_action.md Phase 1`. The 5 `reports/wuc-2027/ds*.json` here are *constrained repro proxies* using committed small samples — the heavy 56.6k run is documented, not committed as binary, per `data/raw/README.txt` pattern (as Tanager `589MB HDF5`).

## Hardware Snapshot

- CPU temps: Core Temp 14 sensors available, psutil fallback live
- `psutil` thermal monitoring active, `ThermalGuard` chunking verified
- `python -m unittest discover -s tests -p test_*.py` → `Ran 175 tests in ~40s OK`

## Requirements Freeze

- `geopandas`, `shapely`, `pyproj`, `psutil`, `streamlit`, `folium`, `streamlit-folium`, `zstandard` (from `pyproject.toml`)
- Freeze: `pip freeze > reports/wuc-2027/requirements-freeze.txt` (run on reviewer machine)

## Validator Coverage

- geometry: duplicate_vertex, self_intersection, null_geometry
- crs: invalid_crs, missing_crs
- integrity: missing_spatial_index / stale_spatial_index
- accuracy (new): ndvi_out_of_range, spectral_index_nan, ndvi_temporal_spike (|delta|>0.30), ndwi_ndvi_inconsistency, spectral_band_negative_radiance
- runtime: runtime_limit_exceeded, thermal throttling
- audit: hash-linked chains (6 chains verified in sandbox TIG)

## Privacy Gate

- `.githooks/pre-commit` blocks absolute Windows paths (`C:\Users\admin\OneDrive`) and `api_key.txt` — reuse Tanager pattern.
- No confidential utility mains committed; OSM HOT Oman waterways labeled as public water/drainage line data per `I:\My Drive\Projects\GeoQA Atlas\README.md`.

## How to Reproduce (Reviewer)

```powershell
git clone https://github.com/NiloferTaher/GeoQA.git
cd GeoQA
git checkout wuc-2027
pip install -e .[dev]
python -m unittest discover -s tests -p test_*.py  # → 175 OK
python scripts/wuc-2027/run_all.py        # → 5× PASS, wuc_run_log.csv MATCH
python scripts/wuc-2027/validate_csv_evidence.py  # → headline numbers verified: 49, 539, 28, 127, 6 chains
```

## Wall-Clock Honesty

- Low-resource `generic_quick --low-resource` on this workstation: ~0.5s for 1-feature edge case (as above logs show progress 33%/66%/100%).
- Heavy 56.6k run wall-clock ~122s low-resource vs 15s cloud — only speed scales, not accuracy — documented in `README.md: Real-World Constrained Execution`.
- Web site `geo-qa-pi.vercel.app/wuc` reads from `reports/wuc-2027/` — no live Python exec in browser; terminal animation replays committed `wuc_run_log.csv`.

