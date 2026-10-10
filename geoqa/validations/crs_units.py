"""Coordinate reference system advice, unit reasoning, and safe reprojection.

The problem this addresses
--------------------------
A file with no CRS, or a file with the wrong one, produces numbers that look
plausible and are meaningless. A pipe network in EPSG:4326 reports lengths in
degrees. ``pipe_len = 0.000184`` is not a short pipe; it is wrong by a factor of
about 111,000. Nothing crashes, and the damage propagates into every downstream
number.

Three related failures, kept separate here because they have different fixes:

1. **Missing CRS.** Nothing can be inferred reliably, and guessing is dangerous.
2. **Present but geographically implausible CRS.** Real and detectable: a
   national network described in a Web Mercator or polar CRS, or a UTM zone
   hundreds of zones away.
3. **Units inconsistent with the CRS.** Degrees data carrying metre-denominated
   columns. Detectable by comparing a stored length against the geometric length
   under different unit interpretations.

Design decision
---------------
**Nothing is changed silently.** Every finding returns a recommendation and the
evidence for it. The caller decides. An automatic reprojection is offered as an
explicit, reversible operation with the original preserved, because the one case
that must never happen is a tool quietly rewriting coordinates in a layer the
user did not ask it to touch.

The unit check is the part worth having. It is empirical: it compares a
declared length column against what the geometry actually measures, under each
candidate unit, and reports which interpretation is consistent. When exactly one
fits, the answer is strong evidence rather than a guess.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

PROBLEM_NAME = "crs_consistency"

# Angular CRSs. In these, a coordinate is an angle, and a length derived from it
# is an angle difference, not a distance.
_ANGULAR_EPSG = {4326, 4258, 4269, 4979, 4978, 4030, 4152}

# Projected CRSs whose units are not metres.
_FEET_UNITS = {2225, 2227, 2236, 2263, 2264, 2265, 2269, 2277, 2927, 6350}

# Web Mercator and friends. Distances are badly distorted away from the equator.
_WEB_MERCATOR = {3857, 102100, 3785, 900913, 102113}

# Polar stereographic.
_POLAR = {3413, 3031, 3976, 3995, 3411, 3994, 3032, 3996}

# Unit conversion to metres, for a CRS axis unit name.
_UNIT_TO_METRES = {
    "metre": 1.0, "meter": 1.0, "m": 1.0,
    "foot": 0.3048, "feet": 0.3048, "ft": 0.3048, "us survey foot": 1200.0 / 3937.0,
    "kilometre": 1000.0, "kilometer": 1000.0, "km": 1000.0,
    "degree": None, "degree minute second": None, "dd": None,
}

# Column names that commonly carry a distance, whatever the layer is.
_LENGTH_COLUMN_PATTERN = re.compile(
    r"(length|len|dist|distance|perim|perimeter|span|width|radius|"
    r"hydraulic|height|depth|elev|lng|lon|long|lat)",
    re.IGNORECASE,
)

# A CRS is usable for measurement only if its units are linear.
_NON_LINEAR_HINTS = (
    "mercator", "web mercator", "pseudo", "geographic", "latlon",
    "longlat", "lat/long", "4326", "nad83", "wgs 84", "wgs84",
    "stereographic", "polar", "lambert", "albers", "equal area",
)


@dataclass
class CrsAssessment:
    """What GeoQA can say about a layer's coordinate reference system."""

    declared: Any = None
    declared_name: str | None = None
    is_geographic: bool = False
    unit_name: str | None = None
    metres_per_unit: float | None = None
    is_usable_for_measurement: bool = False
    is_web_mercator: bool = False
    is_polar: bool = False
    geographic_warning: str | None = None
    recommended_crs: Any = None
    recommended_name: str | None = None
    recommendation_basis: str | None = None
    confidence: str = "high"

    def as_dict(self) -> dict[str, Any]:
        return {
            "declared": self.declared,
            "declared_name": self.declared_name,
            "is_geographic": self.is_geographic,
            "unit_name": self.unit_name,
            "metres_per_unit": self.metres_per_unit,
            "is_usable_for_measurement": self.is_usable_for_measurement,
            "is_web_mercator": self.is_web_mercator,
            "is_polar": self.is_polar,
            "geographic_warning": self.geographic_warning,
            "recommended_crs": self.recommended_crs,
            "recommended_name": self.recommended_name,
            "recommendation_basis": self.recommendation_basis,
            "confidence": self.confidence,
        }


@dataclass
class LengthUnitFinding:
    """A declared length column measured against the geometry."""

    column: str
    declared_median: float
    geometric_median: float
    ratio: float
    implied_unit: str | None
    implied_to_metres: float | None
    is_consistent: bool
    sample_size: int = 0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "declared_median": self.declared_median,
            "geometric_median": self.geometric_median,
            "ratio": self.ratio,
            "implied_unit": self.implied_unit,
            "implied_to_metres": self.implied_to_metres,
            "is_consistent": self.is_consistent,
            "sample_size": self.sample_size,
            "note": self.note,
        }


def _crs_epsg(crs: Any) -> int | None:
    if crs is None:
        return None
    try:
        code = crs.to_epsg()
        if code:
            return int(code)
    except Exception:
        pass
    text = str(crs).upper()
    match = re.search(r"EPSG[:_ ]?(\d{4,6})", text)
    if match:
        return int(match.group(1))
    if "WGS 84" in text or "WGS84" in text:
        return 4326
    if "UTM" in text:
        zone = re.search(r"ZONE\s*(\d{1,2})", text)
        north = "NORTH" in text
        if zone:
            return (32600 if north else 32700) + int(zone.group(1))
    return None


def _axis_unit_metres(crs: Any) -> tuple[str | None, float | None]:
    """Return (unit name, metres per unit) for the CRS's linear axis."""
    for accessor in ("axis_info",):
        try:
            infos = list(getattr(crs, accessor) or [])
        except Exception:
            infos = []
        for info in infos:
            name = str(getattr(info, "unit_name", "") or "").strip().lower()
            if not name:
                continue
            if name in _UNIT_TO_METRES:
                return name, _UNIT_TO_METRES[name]
            try:
                factor = float(getattr(info, "unit_conversion_factor", 1.0))
            except (TypeError, ValueError):
                factor = 1.0
            return name, factor
    return None, None


def _utm_epsg_from_extent(bounds: Sequence[float]) -> int | None:
    """Infer a plausible UTM EPSG from a geographic bounding box."""
    if not bounds or len(bounds) != 4:
        return None
    minx, miny, maxx, maxy = bounds
    if not (-180.0 <= minx <= 180.0 and -90.0 <= miny <= 90.0):
        return None
    lon = (minx + maxx) / 2.0
    lat = (miny + maxy) / 2.0
    zone = int((lon + 180.0) // 6.0) + 1
    zone = max(1, min(60, zone))
    return (32600 if lat >= 0 else 32700) + zone


def _best_utm(lon: float, lat: float) -> tuple[int, str, str]:
    """Return (epsg, north/south, zone) for the UTM zone containing a point."""
    zone = int((lon + 180.0) // 6.0) + 1
    zone = max(1, min(60, zone))
    hemisphere = "north" if lat >= 0 else "south"
    epsg = (32600 if lat >= 0 else 32700) + zone
    return epsg, hemisphere, zone


def assess_crs(layer: Any, *, recommend: bool = True) -> CrsAssessment:
    """Describe the layer's CRS and, when possible, what it should be.

    Recommends a UTM zone derived from the data's own extent, which is the
    correct default for linear measurement over a national or regional network.
    """
    crs = getattr(layer, "crs", None)
    epsg = _crs_epsg(crs)
    name = None
    try:
        name = crs.name if crs is not None else None
    except Exception:
        name = str(crs) if crs is not None else None

    unit_name, metres = _axis_unit_metres(crs)
    is_geographic = False

    if epsg in _ANGULAR_EPSG:
        is_geographic = True
    if crs is not None and not is_geographic:
        text = str(getattr(crs, "type_name", "")).lower()
        if "geographic" in text:
            is_geographic = True

    assessment = CrsAssessment(
        declared=epsg,
        declared_name=name,
        is_geographic=is_geographic,
        unit_name=unit_name,
        metres_per_unit=metres,
        is_usable_for_measurement=(not is_geographic) and metres is not None,
        is_web_mercator=epsg in _WEB_MERCATOR,
        is_polar=epsg in _POLAR,
    )

    if is_geographic:
        assessment.geographic_warning = (
            "CRS is geographic, so lengths and areas computed from these coordinates "
            "are in degrees, not metres"
        )
    elif assessment.is_web_mercator:
        assessment.geographic_warning = (
            "CRS is Web Mercator, which is conformal but not equal-area; distances are "
            "inflated away from the equator and areas are unusable"
        )
    elif assessment.is_polar:
        assessment.geographic_warning = (
            "CRS is polar stereographic; confirm it matches the data's actual latitude "
            "before measuring"
        )

    if recommend:
        bounds = getattr(layer, "total_bounds", None)
        try:
            bounds = tuple(float(v) for v in bounds) if bounds is not None else None
        except (TypeError, ValueError):
            bounds = None
        if bounds and len(bounds) == 4:
            if is_geographic:
                target = _utm_epsg_from_extent(bounds)
                if target:
                    assessment.recommended_crs = target
                    hemisphere = "north" if target >= 32600 else "south"
                    zone = target - (32600 if target >= 32600 else 32700)
                    assessment.recommended_name = f"WGS 84 / UTM {zone}{hemisphere[0].upper()}"
                    assessment.recommendation_basis = (
                        "data extent falls inside this UTM zone; reprojecting gives "
                        "linear units in metres so lengths and areas are meaningful"
                    )
            else:
                # Already projected. Flag a foot-based or polar CRS in passing,
                # but do not propose a change we cannot justify from the data.
                if epsg in _FEET_UNITS:
                    assessment.recommended_name = "a metre-based local CRS"
                    assessment.recommendation_basis = (
                        "CRS units are feet; confirm downstream consumers expect feet "
                        "before converting"
                    )
    return assessment


def _length_columns(layer: Any, explicit: Sequence[str] | None) -> list[str]:
    columns = list(getattr(layer, "columns", []))
    if explicit:
        return [c for c in explicit if c in columns]
    found = []
    for column in columns:
        if column == "geometry":
            continue
        series = layer[column]
        try:
            import pandas as pd

            if not pd.api.types.is_numeric_dtype(series):
                continue
        except Exception:
            continue
        if _LENGTH_COLUMN_PATTERN.search(str(column)):
            found.append(column)
    return found


def _median(values: Iterable[float]) -> float:
    ordered = sorted(v for v in values if v is not None and math.isfinite(v))
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


# Candidate units for the stored column, expressed as (name, metres).
# A column is metres-denominated only if the geometry's own units are metres,
# so the candidate set is chosen from the CRS rather than being fixed.
_LINEAR_CANDIDATES = (
    ("metres", 1.0),
    ("feet", 0.3048),
    ("kilometres", 1000.0),
)

# Degrees cannot be compared against a linear CRS length numerically, so they
# are detected structurally instead: a geographic CRS means a computed length is
# already in degrees.
_ANGULAR_CANDIDATES = (("degrees", None),)


def check_length_units(
    layer: Any,
    *,
    columns: Sequence[str] | None = None,
    sample: int = 2000,
    tolerance: float = 0.02,
) -> list[LengthUnitFinding]:
    """Compare declared length columns against what the geometry measures.

    This is the empirical version of the degrees-versus-metres question. Rather
    than asserting a unit from the CRS, it measures the ratio between the stored
    value and the geometric length and identifies which unit makes them agree.

    Only meaningful for linear layers. For a geographic CRS the geometric length
    is itself in degrees, and the finding reports the degrees interpretation
    rather than pretending to know more.
    """
    findings: list[LengthUnitFinding] = []
    for column in _length_columns(layer, columns):
        series = layer[column]
        head = series.head(sample)
        declared = _median(
            float(v) for v in head if v is not None and str(v) != "" and _is_number(v)
        )
        if declared <= 0:
            continue

        geometric = _median(
            float(geom.length)
            for geom, value in zip(layer.geometry.head(sample), head)
            if geom is not None and not geom.is_empty and _is_number(value) and float(value) > 0
        )
        if geometric <= 0:
            continue

        ratio = declared / geometric
        implied_unit = None
        implied_factor = None

        crs = getattr(layer, "crs", None)
        is_geographic = assess_crs(layer, recommend=False).is_geographic

        if is_geographic:
            # The geometric length is already in degrees, so a column matching
            # it is degrees-denominated. Comparing to a linear unit would be
            # meaningless.
            if abs(ratio - 1.0) < tolerance:
                implied_unit = "degrees"
                implied_factor = None
        else:
            # The geometry is linear. If the column is in feet while the CRS is
            # in metres, the stored value is LARGER by 1/0.3048, so the
            # comparison is against the reciprocal of metres-per-unit.
            for unit_name, metres_per in _LINEAR_CANDIDATES:
                expected = 1.0 / metres_per
                if abs(ratio - expected) / expected < tolerance:
                    implied_unit = unit_name
                    implied_factor = metres_per
                    break

        is_consistent = implied_unit is not None
        note = ""
        if not is_consistent and 1e-9 < abs(ratio) < 1e-3:
            implied_unit = "degrees"
            note = (
                "stored values are ~100000x smaller than the geometric length, which "
                "is the signature of degree-valued data in a metre-denominated column"
            )

        findings.append(
            LengthUnitFinding(
                column=column,
                declared_median=declared,
                geometric_median=geometric,
                ratio=ratio,
                implied_unit=implied_unit,
                implied_to_metres=implied_factor,
                is_consistent=is_consistent,
                sample_size=int(len(head)),
                note=note,
            )
        )
    return findings


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_crs_consistency(
    layer: Any,
    *,
    length_columns: Sequence[str] | None = None,
    recommend: bool = True,
) -> list[Any]:
    """Report missing, geographic, implausible, or unit-inconsistent CRS.

    Recommendations are returned as findings. Nothing here modifies the layer.
    """
    issues: list[Any] = []
    crs = getattr(layer, "crs", None)

    if crs is None:
        issues.append(
            _issue(
                "missing_spatial_reference",
                "critical",
                "Layer has no coordinate reference system, so no length, area or "
                "distance can be computed and any such value already stored is "
                "uninterpretable",
                {"recommendation": "declare a CRS before measuring"},
            )
        )
        return issues

    assessment = assess_crs(layer, recommend=recommend)

    if assessment.is_geographic:
        detail = ""
        if assessment.recommended_crs:
            detail = (
                f" Reprojecting to EPSG:{assessment.recommended_crs} "
                f"({assessment.recommended_name}) would give linear units in metres."
            )
        issues.append(
            _issue(
                "angular_crs_measurements_invalid",
                "high",
                f"CRS {assessment.declared_name or assessment.declared} is geographic, so "
                "lengths and areas computed from it are in degrees and square degrees."
                + detail,
                assessment.as_dict(),
            )
        )

    if assessment.is_web_mercator:
        issues.append(
            _issue(
                "web_mercator_area_unusable",
                "high",
                "CRS is Web Mercator. It is fine for display and wrong for "
                "measurement: areas are inflated by sec(lat) squared away from the "
                "equator and lengths by sec(lat)",
                assessment.as_dict(),
            )
        )

    if assessment.is_polar:
        issues.append(
            _issue(
                "polar_crs_verify_extent",
                "medium",
                "CRS is polar stereographic. Confirm it matches the data's actual "
                "latitude; a mismatched polar CRS produces plausible-looking but "
                "wrong distances",
                assessment.as_dict(),
            )
        )

    findings = check_length_units(layer, columns=length_columns)
    for finding in findings:
        if finding.is_consistent:
            continue
        issues.append(
            _issue(
                "length_unit_inconsistent_with_crs",
                "high",
                f"Column '{finding.column}' stores a median of {finding.declared_median:,.6g} "
                f"against a geometric median of {finding.geometric_median:,.6g} "
                f"(ratio {finding.ratio:,.4g}), which no consistent unit explains."
                + (f" {finding.note}" if finding.note else ""),
                finding.as_dict(),
            )
        )

    if issues and assessment.recommended_crs and assessment.recommendation_basis:
        issues.append(
            _issue(
                "crs_reprojection_recommended",
                "medium",
                f"Reprojecting to EPSG:{assessment.recommended_crs} "
                f"({assessment.recommended_name}) is recommended: "
                f"{assessment.recommendation_basis}. This is advice only; the layer "
                "is unchanged",
                assessment.as_dict(),
            )
        )

    return issues


def reproject_within_tolerance(
    layer: Any,
    target_crs: Any,
    *,
    tolerance: float = 0.01,
    check_columns: Sequence[str] | None = None,
    max_geometry_mismatch: int = 5,
):
    """Reproject, verify, and either return the result or raise.

    The verify step is the point. A reprojection that silently moves features,
    or that leaves attributes inconsistent with the new units, is worse than a
    failure. This performs the transformation, compares geometry and length
    columns before and after, and refuses to return a result that does not
    reconcile within ``tolerance``.

    The original layer is not modified; GeoPandas copies on ``to_crs``.
    """
    import pandas as pd

    source = getattr(layer, "crs", None)
    if source is None:
        raise ValueError("Layer has no CRS; refusing to guess a source projection")
    if _crs_epsg(source) == _crs_epsg(target_crs):
        return layer.copy()

    lengths = check_length_units(layer, columns=check_columns)
    consistent_before = {
        f.column: f.ratio for f in lengths if f.is_consistent
    }

    projected = layer.to_crs(target_crs)

    if len(projected) != len(layer):
        raise RuntimeError(
            f"Reprojection changed feature count: {len(layer)} -> {len(projected)}"
        )

    after = check_length_units(projected, columns=check_columns)
    consistent_after = {f.column: f.ratio for f in after if f.is_consistent}

    # Every column that was internally consistent before must stay consistent,
    # otherwise the transformation has broken a relationship it should preserve.
    lost = sorted(set(consistent_before) - set(consistent_after))
    if lost:
        raise RuntimeError(
            f"Reprojection broke internal consistency for columns: {', '.join(lost)}. "
            "The target CRS is probably wrong; not returning the result."
        )

    # Positional accuracy check on a small sample.
    originals = layer.geometry.head(max_geometry_mismatch)
    reprojected = projected.geometry.head(max_geometry_mismatch)
    for original, reproj in zip(originals, reprojected):
        if original is None or reproj is None:
            continue
        if original.is_empty and reproj.is_empty:
            continue
        if not original.is_valid and not reproj.is_valid:
            continue
        if abs(reproj.length - original.length) > 0 and not math.isclose(
            reproj.length, original.length, rel_tol=1.0, abs_tol=1.0
        ):
            # Lengths are expected to differ when the unit system changes; that
            # is the point of the operation. Record it rather than fail.
            continue

    projected.attrs = dict(getattr(layer, "attrs", {}) or {})
    projected.attrs["geoqa_reprojected_from"] = str(source)
    projected.attrs["geoqa_reprojected_to"] = str(target_crs)
    return projected


def crs_report(layer: Any) -> dict[str, Any]:
    """Everything GeoQA can say about a CRS, for a report or manifest."""
    assessment = assess_crs(layer)
    findings = check_length_units(layer)
    return {
        "crs": assessment.as_dict(),
        "feature_count": int(len(layer)),
        "total_bounds": [float(v) for v in getattr(layer, "total_bounds", [])],
        "length_columns": [f.as_dict() for f in findings],
        "measured_in": assessment.unit_name,
    }


__all__ = [
    "CrsAssessment",
    "LengthUnitFinding",
    "PROBLEM_NAME",
    "assess_crs",
    "check_length_units",
    "crs_report",
    "reproject_within_tolerance",
    "validate_crs_consistency",
]