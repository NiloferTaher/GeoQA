"""Vertical reference: datums, tidal references and elevation sign conventions.

Why this exists
---------------
A horizontal CRS answers "where on the planet". A vertical reference answers
"how high above what". A dataset can be perfect in the first and meaningless in
the second, and nothing in the file objects.

The specific trap
-----------------
Elevation values are only interpretable relative to a named surface. Mean sea
level, mean higher high water, lowest astronomical tide and geoid are different
surfaces, sometimes by over a metre in the same place. A coastal or mangrove
dataset carrying ``elevation`` with no vertical datum is not merely incomplete:
a consumer who assumes MSL against one that assumes LAT gets a different
mangrove zonation, and both results look equally authoritative.

The sign convention trap
------------------------
Depth is negative below a surface; elevation is positive above one. A bathymetry
layer with all-positive values has almost certainly been flipped, and it will
pass every horizontal check in this library.

Why it is a general module and not a flood module
-------------------------------------------------
The same check applies to any elevation: bathymetry, flood extent, mangrove
canopy, subsidence monitoring, building heights above a flood level, avalanche
terrain, reservoir capacity. So nothing here says flood or mangrove. The caller
supplies what the surface means and what range is plausible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "vertical_reference"

#: Named vertical reference surfaces, and what each is used for.
VERTICAL_REFERENCES: dict[str, str] = {
    "msl": "mean sea level",
    "mhhw": "mean higher high water",
    "mhw": "mean high water",
    "mllw": "mean lower low water",
    "mlw": "mean low water",
    "lat": "lowest astronomical tide",
    "hat": "highest astronomical tide",
    "msl_uk": "mean sea level, UK tidal datum",
    "odn": "Ordnance Datum Newlyn",
    "chart_datum": "chart datum, as used on Admiralty charts",
    "geoid": "geoid",
    "ellipsoid": "ellipsoidal height, not an orthometric one",
}

#: Local vertical CRS identifiers recognised without a lookup.
KNOWN_VERTICAL_CRS: dict[str, str] = {
    "epsg:5703": "NAVD88 height",
    "epsg:5773": "EGM96 geoid height",
    "epsg:3855": "EGM2008 geoid height",
    "epsg:4326+5773": "WGS 84 plus EGM96 geoid",
    "epsg:4979": "WGS 84 ellipsoidal height",
    "epsg:5714": "MSL depth, based on EGM2008",
    "epsg:5715": "MSL depth, based on EGM96",
    "epsg:6318": "NAP height",
    "crs84": "horizontal only, no vertical component",
}

#: Column names that suggest an elevation, depth or height.
ELEVATION_NAME = re.compile(
    r"(?:^|[_\s])(elevation|height|depth|level|wl|water_level|dwl|flood|"
    r"hgl|dem|dsm|dtm|canopy|crest|freeboard|top|bed|floor)(?:$|[_\s0-9])",
    re.IGNORECASE,
)

#: Column names that suggest the reference surface rather than the value.
DATUM_NAME = re.compile(
    r"(?:datum|reference|reference_level|surf|datum_name|vsr|vertical_crs|"
    r"vertical_reference|mean_sea_level|tidal)",
    re.IGNORECASE,
)

#: Value ranges that are physically implausible for a surface-referenced level.
#: ``(lowest_plausible, highest_plausible, unit, description)``
PLAUSIBLE_RANGES: dict[str, tuple[float, float, str, str]] = {
    "elevation": (-500.0, 9000.0, "m", "surface-referenced elevation"),
    "depth": (-12000.0, 0.0, "m", "depth below a surface"),
    "water_level": (-10.0, 120.0, "m", "water level"),
    "canopy": (0.0, 80.0, "m", "canopy height above ground"),
}


@dataclass
class VerticalProfile:
    """What a dataset says about its vertical reference, and what it implies."""

    columns: tuple[str, ...] = ()
    #: Elevation-like columns found.
    elevation_columns: tuple[str, ...] = ()
    #: Columns that name a reference surface.
    datum_columns: tuple[str, ...] = ()
    #: Declared vertical reference, when one could be read.
    declared_reference: str | None = None
    declared_vertical_crs: str | None = None
    declared_horizontal_crs: str | None = None
    #: Observed ranges per elevation column.
    observed_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    #: Rows whose values are all-positive where depth is expected, or similar.
    inverted_sign_rows: dict[str, int] = field(default_factory=dict)
    unit: str | None = None

    @property
    def has_elevation(self) -> bool:
        return bool(self.elevation_columns)

    @property
    def declares_its_reference(self) -> bool:
        return bool(self.declared_reference or self.declared_vertical_crs or self.datum_columns)

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": list(self.columns),
            "elevation_columns": list(self.elevation_columns),
            "datum_columns": list(self.datum_columns),
            "declared_reference": self.declared_reference,
            "declared_vertical_crs": self.declared_vertical_crs,
            "declared_horizontal_crs": self.declared_horizontal_crs,
            "declares_its_reference": self.declares_its_reference,
            "observed_ranges": {k: list(v) for k, v in self.observed_ranges.items()},
            "inverted_sign_rows": dict(self.inverted_sign_rows),
            "unit": self.unit,
        }


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _column_kind(name: Any) -> str | None:
    """Which kind of vertical quantity a column holds, if it says."""
    label = str(name).strip().lower()
    if "depth" in label or "bathymetry" in label or label.endswith("_dsl"):
        return "depth"
    if "canopy" in label or "chm" in label:
        return "canopy"
    if "water_level" in label or label in {"wl", "dwl", "level"} or "water level" in label:
        return "water_level"
    if ELEVATION_NAME.search(label):
        return "elevation"
    return None


def _read_reference(metadata: Mapping[str, Any] | None, frame: Any) -> str | None:
    """Find a declared vertical reference, from metadata or from the frame."""
    if metadata:
        for key in (
            "vertical_datum", "vertical_reference", "vertical_crs", "vdatum",
            "vertical_datum_name", "vertical_reference_system", "mean_sea_level",
            "datum", "tidal_datum",
        ):
            for candidate, value in metadata.items():
                if str(candidate).strip().lower() == key and value:
                    return str(value)
    columns = list(getattr(frame, "columns", []))
    for column in columns:
        if DATUM_NAME.search(str(column)):
            try:
                values = frame[column]
            except Exception:
                continue
            for value in values:
                if value is not None and str(value).strip():
                    return str(value)
    return None


def profile_vertical(
    frame: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    max_rows: int | None = 20_000,
) -> VerticalProfile:
    """Describe a dataset's vertical reference without judging it yet."""
    columns = tuple(str(column) for column in getattr(frame, "columns", []))
    profile = VerticalProfile(columns=columns)
    if not columns:
        return profile

    profile.elevation_columns = tuple(
        column for column in columns if _column_kind(column)
    )
    profile.datum_columns = tuple(column for column in columns if DATUM_NAME.search(column))
    profile.declared_reference = _read_reference(metadata, frame)

    horizontal = None
    if metadata:
        for key in ("crs", "horizontal_crs", "epsg", "srs"):
            for candidate, value in metadata.items():
                if str(candidate).strip().lower() == key and value:
                    horizontal = str(value)
                    break
            if horizontal:
                break
    if horizontal is None:
        crs = getattr(frame, "crs", None)
        horizontal = str(crs.to_string()) if crs is not None else None
    profile.declared_horizontal_crs = horizontal

    vertical = None
    if metadata:
        for key in ("vertical_crs", "vertical_datum", "vcrs", "compound_crs"):
            for candidate, value in metadata.items():
                if str(candidate).strip().lower() == key and value:
                    vertical = str(value)
                    break
            if vertical:
                break
    profile.declared_vertical_crs = vertical

    for column in profile.elevation_columns:
        try:
            values = [_as_float(value) for value in frame[column]]
        except Exception:
            continue
        if max_rows is not None:
            values = values[:max_rows]
        numeric = [value for value in values if value is not None]
        if not numeric:
            continue
        profile.observed_ranges[column] = (min(numeric), max(numeric))
        kind = _column_kind(column)
        if kind == "depth":
            positive = sum(1 for value in numeric if value > 0)
            if positive and positive == len(numeric):
                profile.inverted_sign_rows[column] = positive

    return profile


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_vertical_reference(
    frame: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    declared_reference: str | None = None,
    expected_range: tuple[float, float] | None = None,
    expected_unit: str = "m",
    require_reference: bool = True,
    max_rows: int | None = 20_000,
) -> list[Any]:
    """Report a vertical reference that is absent, ambiguous or contradicted.

    Conditions emitted
    ------------------
    ``vertical_reference_undeclared``
        Elevation values with no stated reference surface. High, and the most
        consequential condition here: the values are not interpretable, and a
        consumer will assume one.
    ``vertical_reference_ambiguous``
        Several different reference surfaces are named across the metadata or
        the columns, so which one applies is undecided.
    ``vertical_crs_undeclared``
        A horizontal CRS is declared but no vertical component. Medium: a
        compound CRS is needed for a level to mean anything.
    ``vertical_crs_unknown``
        The declared vertical CRS is not one this module recognises.
    ``vertical_range_implausible``
        Observed values fall outside the plausible range for their declared
        meaning and unit.
    ``vertical_depth_sign_inverted``
        A depth column is entirely positive. High: depth below a surface is
        negative, so the sign convention has been flipped.
    ``vertical_unit_undeclared``\n        No unit is recorded and magnitude cannot supply one. Magnitude is not\n        evidence: low-lying coastal data sits naturally between 0 and 3 m.
    """
    profile = profile_vertical(frame, metadata=metadata, max_rows=max_rows)
    if not profile.has_elevation:
        return []

    issues: list[Any] = []
    reference = declared_reference or profile.declared_reference

    if require_reference and not profile.declares_its_reference:
        issues.append(
            _issue(
                "vertical_reference_undeclared", "high",
                f"Elevation column(s) {', '.join(profile.elevation_columns)} carry values with no "
                "stated reference surface. Mean sea level, mean higher high water, lowest "
                "astronomical tide and geoid are different surfaces, locally by more than a "
                "metre, and the file does not say which one these values are relative to. A "
                "consumer will assume one",
                profile.as_dict(),
            )
        )
    elif reference:
        lowered = str(reference).strip().lower()
        known = [token for token in VERTICAL_REFERENCES if token in lowered]
        if len(known) > 1:
            issues.append(
                _issue(
                    "vertical_reference_ambiguous", "high",
                    f"The reference {reference!r} names more than one surface "
                    f"({', '.join(known)}). Which one applies must be decided before the values "
                    "are used",
                    {**profile.as_dict(), "candidates": known},
                )
            )

    if profile.declared_horizontal_crs and not profile.declared_vertical_crs:
        issues.append(
            _issue(
                "vertical_crs_undeclared", "medium",
                f"A horizontal CRS ({profile.declared_horizontal_crs}) is declared but no "
                "vertical component is. A level needs a compound CRS to be meaningful",
                profile.as_dict(),
            )
        )
    elif profile.declared_vertical_crs:
        key = str(profile.declared_vertical_crs).strip().lower()
        if key not in KNOWN_VERTICAL_CRS:
            issues.append(
                _issue(
                    "vertical_crs_unknown", "low",
                    f"Vertical CRS {profile.declared_vertical_crs!r} is not one this module "
                    "recognises. It may be entirely valid; it simply cannot be checked here, "
                    "so it is recorded rather than passed over",
                    profile.as_dict(),
                )
            )

    for column, count in profile.inverted_sign_rows.items():
        issues.append(
            _issue(
                "vertical_depth_sign_inverted", "high",
                f"Column {column!r} is a depth but every one of {count} sampled values is "
                "positive. Depth below a surface is negative, so the sign convention has been "
                "flipped and the data plots as land",
                {"column": column, "positive_rows": count},
            )
        )

    unit_declared = any(
        re.search(r"(?:^|[_\s])(?:unit|units|uom|elev_unit|elevation_unit)(?:$|[_\s])",
                  str(column).strip().lower())
        for column in profile.columns
    )
    for column, (low, high) in profile.observed_ranges.items():
        kind = _column_kind(column) or "elevation"
        bounds = expected_range or PLAUSIBLE_RANGES[kind][:2]
        plausible_low, plausible_high, unit, description = PLAUSIBLE_RANGES[kind]

        if expected_range is not None:
            plausible_low, plausible_high = expected_range

        if high > plausible_high or low < plausible_low:
            issues.append(
                _issue(
                    "vertical_range_implausible", "high",
                    f"Column {column!r} ranges {low:.3f} to {high:.3f}, outside the "
                    f"{plausible_low:g} to {plausible_high:g} {unit} expected for {description}. "
                    "A unit error is the usual cause: feet on data described as metres produce "
                    "values that are wrong but still plausible",
                    {
                        "column": column,
                        "observed_min": low,
                        "observed_max": high,
                        "plausible_min": plausible_low,
                        "plausible_max": plausible_high,
                        "unit": unit,
                    },
                )
            )
        elif expected_unit and not unit_declared:
            # Magnitude cannot identify a unit. Low-lying coastal and mangrove
            # data sits naturally between 0 and 3 m, and flagging that as
            # "possibly feet" would fire on exactly the data this module exists
            # to support. So the unit is asked for rather than guessed at.
            issues.append(
                _issue(
                    "vertical_unit_undeclared", "low",
                    f"Column {column!r} ranges {low:.3f} to {high:.3f}. A value's magnitude "
                    "cannot identify its unit, so the unit has to be declared rather than "
                    "inferred. This is worth recording for coastal and near-sea-level data, "
                    "where a feet/metre error is easy to make and hard to see",
                    {"column": column, "observed_min": low, "observed_max": high,
                     "assumed_unit": expected_unit},
                )
            )

    return issues


def metres_to_feet(value: float) -> float:
    return value * 3.280839895013123


def feet_to_metres(value: float) -> float:
    return value / 3.280839895013123


__all__ = [
    "DATUM_NAME",
    "ELEVATION_NAME",
    "KNOWN_VERTICAL_CRS",
    "PLAUSIBLE_RANGES",
    "PROBLEM_NAME",
    "VERTICAL_REFERENCES",
    "VerticalProfile",
    "feet_to_metres",
    "metres_to_feet",
    "profile_vertical",
    "validate_vertical_reference",
]