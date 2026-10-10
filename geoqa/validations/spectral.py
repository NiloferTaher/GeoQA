"""
spectral.py — Satellite / spectral index anomaly validators for GeoQA

Adds deterministic checks for common multi-spectral derived indices
(NDVI, NDWI, NDBI, NDMI) and band-level radiometric QA, mirroring the
Tanager Level-3 discrepancy pattern:

  - Level-3 actual-Sentinel-2 vs proxy NDVI/NIR-green/SWIR-NIR pairwise
    direction agreement was near-random 2/6, 2/6, 3/6 (CF Tanager
    experiments/sentinel2_information_loss/QA.md and VR_AUDIT.md VR-5).
    Example: NDVI vegetation s2proxy +0.252 vs s2_actual -0.080.
  - VR-5 flagged this as *controlled negative result*: cross-acquisition
    TOA radiance vs L2A surface reflectance + 40-day separation makes
    quantitative comparison invalid — not a bug, but a governance guardrail
    to enforce.

This validator does not invent satellite physics; it flags *actionable*
anomalies that downstream GeoAI should not silently consume: out-of-range
indices, temporal spikes, implausible land-cover/index combos, and band-
level QA (e.g., negative TOA radiance in Tanager 376 nm band).

Usage (expects raster layer with index bands or a GeoDataFrame with
pre-computed index columns — works in both low-resource and full modes):

  from geoqa.validations.spectral import validate_spectral_indices

Design follows GeoQA conventions: ValidationIssue via build_issue(),
catalog-backed problem_name, thermal-safe loops via ThermalGuard when
iterating large arrays. See base.py for the shared validation contract.

Planned catalog entries (add to problem_registry.py):
  - ndvi_out_of_range, ndwi_out_of_range, ndmi_out_of_range
  - ndvi_temporal_spike, ndwi_ndvi_inconsistency
  - spectral_band_negative_radiance, spectral_index_nan
"""
from __future__ import annotations

from typing import Any

from .base import ValidationIssue, build_issue

# Thresholds are intentionally conservative — domain packs may override.
NDVI_RANGE = (-1.0, 1.0)
NDWI_RANGE = (-1.0, 1.0)
NDMI_RANGE = (-1.0, 1.0)
# NDBI similarly bounded but often cited -1..1; keep same.
TEMPORAL_SPIKE_ABS = 0.30  # delta that triggers review (e.g., NDVI 0.252 -> -0.080 = 0.332, Tanager VR-5)
# Tanager anomaly reference: desert-lagoon hardest pair SAM 3.13deg vs proxy 2.82deg —
# small absolute shifts matter when decision threshold is tight.


def _is_finite_number(v: Any) -> bool:
    try:
        fv = float(v)
        return fv == fv and fv not in (float("inf"), float("-inf"))
    except Exception:
        return False


def validate_spectral_indices(
      layer: Any,
      *,
      ndvi_col: str = "ndvi",
      ndwi_col: str = "ndwi",
      ndmi_col: str = "ndmi",
      ndbi_col: str | None = None,
      date_col: str | None = None,
      feature_id_col: str | None = None,
  ) -> list[ValidationIssue]:
    """
    Deterministic spectral-index anomaly checks for tabular/vector layers that
    carry pre-computed indices (from raster stats, zonal means, or Tanager-like
    band math). For raster-array inputs, caller should first extract per-feature
    zonal means and pass as a GeoDataFrame — this keeps GeoQA vector-first
    while adding satellite-aware QA.

    Checks:
      1. Out-of-range (-1..1) — flags sensor/calibration or math error.
      2. NaN / non-finite — flags missing band or QA mask gap.
      3. Temporal spike — if date_col present and previous value exists,
         flags |delta| > TEMPORAL_SPIKE_ABS (mimics Tanager cross-acquisition
         NDVI sign flip that was correctly treated as non-comparable).
      4. Inconsistency — NDWI high but NDVI also high on same feature may
         indicate mis-registered water/vegetation (actionable review, not auto-fix).

    Returns list[ValidationIssue] — empty if no index columns present (no-op).
    """
    issues: list[ValidationIssue] = []

    # Detect which index columns actually exist on this layer.
    try:
        cols = set(list(getattr(layer, "columns", [])))
    except Exception:
        cols = set()
    # Support plain DataFrames and GeoDataFrames alike.
    has_any = any(c in cols for c in [ndvi_col, ndwi_col, ndmi_col] + ([ndbi_col] if ndbi_col else []))
    if not has_any:
        # Graceful no-op: this is a pure vector dataset (roads, etc.). Let
        # geometry/topology validators handle it; spectral is irrelevant.
        return issues

    # For temporal spike we need ordering. When feature_id_col is supplied the
    # comparison is keyed to the SAME location across dates; sorting is then by
    # (feature_id, date) so consecutive rows of a key are its own epochs.
    # Without it we fall back to the historical behaviour of comparing row i to
    # row i-1 of the whole table, which is only correct if the caller has
    # already ordered the table that way.
    keyed = bool(feature_id_col and feature_id_col in cols)
    try:
        if date_col and date_col in cols:
            by = [feature_id_col, date_col] if keyed else [date_col]
            ordered = layer.sort_values(by=by)
        else:
            ordered = layer
    except Exception:
        ordered = layer

    # Single shared scalar: the previous value for that column for that key.
    prev: dict[Any, dict[str, float | None]] = {}

    def _key_for(row: Any) -> Any:
        if keyed:
            try:
                return str(row[feature_id_col])
            except Exception:
                return None
        return "__all__"

    for idx, row in ordered.iterrows():
        key = _key_for(row)
        row_prev = prev.setdefault(
            key, {ndvi_col: None, ndwi_col: None, ndmi_col: None}
        )

    for idx, row in ordered.iterrows():
        # Row-level checks per index col
        for col, valid_range in [
            (ndvi_col, NDVI_RANGE),
            (ndwi_col, NDWI_RANGE),
            (ndmi_col, NDMI_RANGE),
        ]:
            if col not in cols:
                continue
            val = row[col] if col in row else None
            lo, hi = valid_range

            # NaN / non-finite
            if val is None or (isinstance(val, float) and (val != val)):
                issues.append(
                    build_issue(
                        "spectral_index_nan",
                        row=row, index=idx,
                        description=f"{col} is NaN/missing for feature {idx} — band QA mask or calculation gap.",
                        solution_hint="Inspect source raster QA band / cloud mask; recompute index only on valid pixels.",
                        severity="high",
                        extra={"index": col, "value": str(val), "anomaly_type": "missing"},
                    )
                )
                continue
            if not _is_finite_number(val):
                issues.append(
                    build_issue(
                        "spectral_index_nan",
                        row=row, index=idx,
                        description=f"{col} is non-finite ({val}) for feature {idx}.",
                        solution_hint="Clamp or mask invalid radiances before band math.",
                        severity="high",
                        extra={"index": col, "value": str(val)},
                    )
                )
                continue

            fv = float(val)
            # Out-of-range
            if fv < lo - 1e-6 or fv > hi + 1e-6:
                issues.append(
                    build_issue(
                        f"{col}_out_of_range" if col in ("ndvi","ndwi","ndmi") else "spectral_index_out_of_range",
                        row=row, index=idx,
                        description=f"{col}={fv:.4f} out of expected range [{lo}, {hi}] for feature {idx}.",
                        solution_hint="Verify band order (e.g., NIR/SWIR swap) and scaling (reflectance 0-10000 vs 0-1); check for negative radiance.",
                        severity="high",
                        extra={"index": col, "value": fv, "expected_range": [lo, hi]},
                    )
                )

            # Temporal spike (needs ordered layer)
            if date_col and date_col in cols:
                pval = row_prev.get(col)
                if pval is not None and _is_finite_number(pval):
                    delta = abs(fv - float(pval))
                    # Mimic Tanager NDVI sign-flip detection: 0.252 vs -0.08 => delta 0.332
                    if delta > TEMPORAL_SPIKE_ABS:
                        issues.append(
                            build_issue(
                                f"{col}_temporal_spike",
                                row=row, index=idx,
                                description=f"{col} temporal spike |delta|={delta:.3f} ({pval:.3f} -> {fv:.3f}) for feature {idx}{'' if not keyed else f' (key {key})'} — cross-acquisition change exceeds {TEMPORAL_SPIKE_ABS}.",
                                solution_hint="Treat cross-date TOA vs SR and seasonal differences as non-comparable (cf. Tanager VR-5 Level-3 2/6 negative result); add acquisition-date and product-level to provenance before comparing.",
                                severity="medium",
                                extra={"index": col, "delta": delta, "prev": float(pval), "curr": fv, "key": key if keyed else None},
                            )
                        )
                row_prev[col] = fv
            else:
                # Still track for next row even without date (sequential rows as proxy)
                row_prev[col] = fv

        # Cross-index inconsistency: e.g., NDWI > 0.3 (water-like) but NDVI > 0.4 (vegetation-like) on same feature
        try:
            ndvi_v = float(row[ndvi_col]) if ndvi_col in cols and _is_finite_number(row[ndvi_col]) else None
            ndwi_v = float(row[ndwi_col]) if ndwi_col in cols and _is_finite_number(row[ndwi_col]) else None
            if ndvi_v is not None and ndwi_v is not None:
                if ndwi_v > 0.30 and ndvi_v > 0.40:
                    issues.append(
                        build_issue(
                            "ndwi_ndvi_inconsistency",
                            row=row, index=idx,
                            description=f"NDWI={ndwi_v:.3f} (water-like) and NDVI={ndvi_v:.3f} (vegetation-like) both high for feature {idx} — possible mis-registered land/water or mixed pixel.",
                            solution_hint="Review against high-res imagery or use sub-pixel unmixing; flag for human review, do not auto-reclassify.",
                            severity="medium",
                            extra={"ndvi": ndvi_v, "ndwi": ndwi_v},
                        )
                    )
        except Exception:
            pass

    return issues


def validate_band_radiance(
    layer: Any,
    *,
    band_cols: list[str] | None = None,
) -> list[ValidationIssue]:
    """
    Band-level QA for TOA radiance / reflectance tables (e.g., Tanager 426-band
    per-pixel extracts). Flags negative radiance (cf. Tanager band 376 nm QA) and
    all-NaN rows that indicate QA mask leaks.
    """
    issues: list[ValidationIssue] = []
    try:
        cols = list(getattr(layer, "columns", []))
    except Exception:
        cols = []
    candidates = band_cols if band_cols is not None else [c for c in cols if c.lower().startswith("band") or c.lower().startswith("b")]
    if not candidates:
        return issues
    for idx, row in layer.iterrows():
        vals = []
        for c in candidates:
            try:
                v = float(row[c])
                vals.append(v)
                if v < -1e-9:
                    issues.append(
                        build_issue(
                            "spectral_band_negative_radiance",
                            row=row, index=idx,
                            description=f"Band {c} negative radiance {v:.4f} for feature {idx} — sensor/QA anomaly.",
                            solution_hint="Mask negative TOA radiance pixels before index math; check band calibration.",
                            severity="medium",
                            extra={"band": c, "value": v},
                        )
                    )
                    break  # one per feature is enough
            except Exception:
                continue
        # all-NaN row
        if vals and all(v != v for v in vals):
            issues.append(
                build_issue(
                    "spectral_index_nan",
                    row=row, index=idx,
                    description=f"All band values NaN for feature {idx}.",
                    solution_hint="Check QA mask and nodata handling.",
                    severity="high",
                )
            )
    return issues
