"""Coordinate axis order, and the swap that produces plausible wrong places.

Why this exists
---------------
The same coordinate has two official orders and they disagree.

- ``EPSG:4326`` is formally defined **latitude, longitude** (north, east).
- ``OGC:CRS84``, RFC 7946 GeoJSON, PostGIS geometry and every mainstream GIS
  desktop are **longitude, latitude** (east, north).
- WFS 1.0.0 delivered longitude/latitude; WFS 1.1.0 and 2.0.0 respect the EPSG
  definition and therefore deliver latitude/longitude.

So a pair read under the wrong convention is not obviously wrong. Take Muscat.
The city is roughly 23.6 N, 58.2 E. Written longitude-first it is ``58.2, 23.6``.
Read latitude-first it is ``23.6, 58.2``. Both are in range, both look like a
coordinate, and the second lands in open water. Nothing downstream complains.

The failure this module exists to catch
---------------------------------------
The characteristic case is a coordinate written with the latitude in the
longitude slot. Two sub-cases behave differently:

**Out of range.** A longitude slot holding a value above 90 cannot be a latitude
anywhere on Earth. That is unambiguous.

**In range but wrong.** Both values are inside their legal ranges, so range
checks pass and the point simply lands somewhere else. This is caught by
comparing against a declared expected extent, a reference layer, or a known
bounding region. Without one of those, the module reports the ambiguity as
evidence rather than inventing a verdict.

What this module will not do
----------------------------
It will not guess. Given ``24, 53`` and nothing else, it cannot say which order
was intended; both readings are legal. It reports the declared order, the
reading under that order, and what would be needed to confirm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "coordinate_axis_order"

#: The order each authority formally defines.
CANONICAL_ORDERS: dict[str, tuple[str, str]] = {
    "EPSG:4326": ("latitude", "longitude"),
    "urn:ogc:def:crs:EPSG::4326": ("latitude", "longitude"),
    "urn:ogc:def:crs:OGC:1.3:CRS84": ("longitude", "latitude"),
    "OGC:CRS84": ("longitude", "latitude"),
    "CRS84": ("longitude", "latitude"),
    "urn:ogc:def:crs:OGC::CRS84": ("longitude", "latitude"),
    "urn:ogc:def:crs:EPSG:6.6:4326": ("longitude", "latitude"),
}

#: Orders that apply to storage formats rather than to a CRS definition.
FORMAT_ORDERS: dict[str, tuple[str, str]] = {
    "geojson": ("longitude", "latitude"),
    "postgis": ("longitude", "latitude"),
    "wkb": ("longitude", "latitude"),
    "wfs-1.0": ("longitude", "latitude"),
    "wfs-1.1": ("latitude", "longitude"),
    "wfs-2.0": ("latitude", "longitude"),
    "csv": ("longitude", "latitude"),
    "excel": ("longitude", "latitude"),
}

LATITUDE_LIMIT = 90.0
LONGITUDE_LIMIT = 180.0


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def canonical_order(declared: str | None) -> tuple[str, str] | None:
    """Axis order a declared CRS or format mandates.

    Normalised case-insensitively. Returns ``None`` when nothing is declared,
    which is itself reportable: an undeclared axis order is the root cause of
    most swap incidents.
    """
    if not declared:
        return None
    key = str(declared).strip()
    if key in CANONICAL_ORDERS:
        return CANONICAL_ORDERS[key]
    lowered = key.lower()
    for known, order in CANONICAL_ORDERS.items():
        if known.lower() == lowered:
            return order
    for known, order in FORMAT_ORDERS.items():
        if known in lowered:
            return order
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass
class AxisOrderFinding:
    """What one pair of coordinates implies about its ordering."""

    first: float
    second: float
    declared_order: tuple[str, str] | None
    #: ``"latitude_first"``, ``"longitude_first"`` or ``"ambiguous"``.
    inference: str
    reason: str

    @property
    def is_ambiguous(self) -> bool:
        return self.inference == "ambiguous"

    def as_dict(self) -> dict[str, Any]:
        return {
            "first": self.first,
            "second": self.second,
            "declared_order": list(self.declared_order) if self.declared_order else None,
            "inference": self.inference,
            "reason": self.reason,
        }


def infer_axis_order(
    first: float,
    second: float,
    *,
    declared_order: tuple[str, str] | None = None,
    expected_extent: tuple[float, float, float, float] | None = None,
) -> AxisOrderFinding:
    """Work out which axis is which from the values themselves.

    ``expected_extent`` is ``(min_x, min_y, max_x, max_y)`` in longitude,
    latitude. Supplying it is what turns an ambiguity into a verdict.
    """
    first_in_latitude_range = abs(first) <= LATITUDE_LIMIT
    second_in_latitude_range = abs(second) <= LATITUDE_LIMIT

    # A value above 90 cannot be a latitude anywhere on Earth, so one such
    # value settles the question outright.
    if not first_in_latitude_range and second_in_latitude_range:
        return AxisOrderFinding(
            first, second, declared_order, "longitude_first",
            "the first value exceeds 90, so it cannot be a latitude",
        )
    if not second_in_latitude_range and first_in_latitude_range:
        return AxisOrderFinding(
            first, second, declared_order, "latitude_first",
            "the second value exceeds 90, so it cannot be a latitude",
        )
    if not first_in_latitude_range and not second_in_latitude_range:
        return AxisOrderFinding(
            first, second, declared_order, "out_of_extent",
            "both values exceed 90, so at least one is outside the legal range "
            "for either axis",
        )

    if expected_extent is not None:
        min_x, min_y, max_x, max_y = expected_extent
        lon_first = min_x <= first <= max_x and min_y <= second <= max_y
        lat_first = min_y <= first <= max_y and min_x <= second <= max_x
        if lon_first and not lat_first:
            return AxisOrderFinding(
                first, second, declared_order, "longitude_first",
                f"only longitude-first falls inside the declared extent "
                f"{expected_extent}",
            )
        if lat_first and not lon_first:
            return AxisOrderFinding(
                first, second, declared_order, "latitude_first",
                f"only latitude-first falls inside the declared extent "
                f"{expected_extent}",
            )
        if not lon_first and not lat_first:
            return AxisOrderFinding(
                first, second, declared_order, "out_of_extent",
                "neither ordering falls inside the declared extent",
            )

    return AxisOrderFinding(
        first, second, declared_order, "ambiguous",
        "both values are inside both legal ranges, so the order cannot be "
        "determined from the numbers alone",
    )


def _column_label(name: Any) -> str:
    return str(name).strip().lower()


def _column_kind(name: Any) -> str | None:
    """Which axis a column name refers to, if it says."""
    label = _column_label(name)
    if label in {"lat", "latitude", "y", "ycoord", "y_coord", "northing"} or "latitude" in label:
        return "latitude"
    if label in {"lon", "lng", "long", "longitude", "x", "xcoord", "x_coord", "easting"} or "longitude" in label:
        return "longitude"
    return None


def _declared_from_columns(columns: Sequence[str]) -> tuple[str, str] | None:
    """Infer an axis order from column names and their left-to-right position.

    A table with ``latitude`` before ``longitude`` is declaring latitude first,
    however both columns are labelled. Position is the declaration.
    """
    kinds = [(index, _column_kind(column)) for index, column in enumerate(columns)]
    lat_at = next((index for index, kind in kinds if kind == "latitude"), None)
    lon_at = next((index for index, kind in kinds if kind == "longitude"), None)
    if lat_at is None and lon_at is None:
        return None
    if lat_at is None or lon_at is None:
        # Only one axis named. That half-declaration is real but incomplete, so
        # it is reported rather than completed by assumption.
        return None
    return ("latitude", "longitude") if lat_at < lon_at else ("longitude", "latitude")


def _pick_columns(columns: Sequence[str], declared: tuple[str, str] | None) -> tuple[str | None, str | None]:
    """Choose which column is first and which is second, in the declared order."""
    def find(kind: str) -> str | None:
        for column in columns:
            if _column_kind(column) == kind:
                return column
        return None

    order = declared or ("longitude", "latitude")
    return find(order[0]), find(order[1])


def validate_axis_order(
    frame: Any,
    *,
    declared_crs: str | None = None,
    declared_format: str | None = None,
    declared_order: tuple[str, str] | None = None,
    expected_extent: tuple[float, float, float, float] | None = None,
    first_column: str | None = None,
    second_column: str | None = None,
    max_rows: int | None = 5000,
) -> list[Any]:
    """Check a coordinate table for swapped axes.

    Accepts a mapping of column name to values rather than requiring a specific
    dataframe type, so it works equally on a CSV loaded by pandas and on rows
    handed over from a ZIP member.

    Conditions emitted
    ------------------
    ``coordinate_axis_order_undeclared``
        Neither a CRS, a format, nor a column naming convention establishes the
        axis order. High, because this is the precondition for every swap.
    ``coordinate_axis_order_swapped``
        A value above 90 sits in a longitude slot, or the pair falls outside the
        declared extent under the declared order. Critical: the coordinates
        resolve to a real but wrong place.
    ``coordinate_axis_order_ambiguous``
        Values are in range but the order cannot be confirmed. Medium. Reported
        as evidence, not a verdict.
    ``coordinate_axis_order_out_of_extent``
        The pair falls outside the declared extent under either order.
    ``coordinate_axis_order_non_numeric``
        A coordinate column holds a value that is not a number.
    ``coordinate_axis_order_declared_mismatch``
        Column names declare one order and the supplied declaration says another.
    """
    columns = list(frame.keys()) if hasattr(frame, "keys") else []
    if not columns:
        return []

    order = declared_order or canonical_order(declared_crs) or canonical_order(declared_format)
    column_implied = _declared_from_columns(columns)

    if order is None and column_implied is None:
        return [
            _issue(
                "coordinate_axis_order_undeclared",
                "high",
                "No axis order is established. EPSG:4326 is formally latitude/longitude "
                "while GeoJSON, PostGIS and desktop GIS are longitude/latitude, so the "
                "same pair means two different places depending on an assumption nobody "
                "wrote down. Declare the CRS, the format, or name the columns lat/lon",
                {"columns": columns},
            )
        ]

    if order is not None and column_implied is not None and order != column_implied:
        return [
            _issue(
                "coordinate_axis_order_declared_mismatch",
                "high",
                f"Columns imply {column_implied[0]}/{column_implied[1]} but the declaration "
                f"says {order[0]}/{order[1]}. One of the two is wrong and coordinates "
                "will be read in the wrong order",
                {
                    "declared_order": list(order),
                    "column_order": list(column_implied),
                    "columns": columns,
                },
            )
        ]

    effective_order = order or column_implied
    first_col = first_column or _pick_columns(columns, effective_order)[0]
    second_col = second_column or _pick_columns(columns, effective_order)[1]

    if first_col is None or second_col is None or first_col == second_col:
        return [
            _issue(
                "coordinate_axis_order_undeclared",
                "medium",
                f"Axis order is {'known' if effective_order else 'unknown'} but two "
                f"coordinate columns could not be identified from {columns}. Name them, or "
                "pass first_column and second_column",
                {"columns": columns, "axis_order": list(effective_order) if effective_order else None},
            )
        ]

    first_values = list(frame[first_col])
    second_values = list(frame[second_col])
    if max_rows is not None:
        first_values = first_values[:max_rows]
        second_values = second_values[:max_rows]

    issues: list[Any] = []
    non_numeric = 0
    swapped_rows: list[int] = []
    ambiguous_rows: list[int] = []
    out_of_extent_rows: list[int] = []

    for row_index, (raw_first, raw_second) in enumerate(zip(first_values, second_values)):
        first = _as_float(raw_first)
        second = _as_float(raw_second)
        if first is None or second is None:
            non_numeric += 1
            continue
        finding = infer_axis_order(
            first, second,
            declared_order=effective_order,
            expected_extent=expected_extent,
        )
        # ``inference`` names what the first value actually is. A swap is when
        # that contradicts the declaration, not when it agrees with it.
        if finding.inference == "latitude_first" and effective_order == ("longitude", "latitude"):
            swapped_rows.append(row_index)
        elif finding.inference == "longitude_first" and effective_order == ("latitude", "longitude"):
            swapped_rows.append(row_index)
        elif finding.inference == "out_of_extent":
            out_of_extent_rows.append(row_index)
        elif finding.is_ambiguous:
            ambiguous_rows.append(row_index)

    if non_numeric:
        issues.append(
            _issue(
                "coordinate_axis_order_non_numeric",
                "medium",
                f"{non_numeric} of {len(first_values)} rows have a non-numeric coordinate. "
                "These rows cannot be checked and will silently disappear on upload",
                {
                    "column": first_col if non_numeric else second_col,
                    "rows": non_numeric,
                    "checked": len(first_values),
                },
            )
        )

    if swapped_rows:
        sample = swapped_rows[:5]
        issues.append(
            _issue(
                "coordinate_axis_order_swapped",
                "critical",
                f"{len(swapped_rows)} rows place a latitude where a longitude belongs "
                f"(declared {effective_order[0]}/{effective_order[1]}). These coordinates "
                "resolve to a real but wrong location, which is why range checks alone "
                "do not catch them",
                {
                    "column": first_col if effective_order == ("longitude", "latitude") else second_col,
                    "columns": [first_col, second_col],
                    "declared_order": list(effective_order),
                    "rows_affected": len(swapped_rows),
                    "sample_rows": sample,
                },
            )
        )

    if out_of_extent_rows:
        issues.append(
            _issue(
                "coordinate_axis_order_out_of_extent",
                "high",
                f"{len(out_of_extent_rows)} rows fall outside the declared extent under "
                "either axis order, so the coordinates are wrong in a way unrelated to "
                "ordering",
                {"extent": list(expected_extent) if expected_extent else None, "rows": len(out_of_extent_rows)},
            )
        )

    if ambiguous_rows and not swapped_rows:
        issues.append(
            _issue(
                "coordinate_axis_order_ambiguous",
                "medium",
                f"{len(ambiguous_rows)} of {len(first_values)} rows have both values inside "
                "both legal ranges, so the axis order cannot be confirmed from the data. "
                "Supply expected_extent or a reference layer to make this decidable",
                {
                    "rows_affected": len(ambiguous_rows),
                    "checked": len(first_values),
                    "declared_order": list(effective_order),
                },
            )
        )

    return issues


def validate_axis_order_sql(
    *,
    table: str,
    x_column: str,
    y_column: str,
    declared_order: str = "longitude_first",
    sample_limit: int | None = None,
) -> str:
    """SQL that finds swapped coordinates in a PostgreSQL/PostGIS table.

    Returned rather than executed, because this module takes no database
    connection. Run it, then hand the result to :func:`interpret_postgres_result`.

    The check is deliberately narrow: it counts rows whose ``x`` cannot be a
    longitude, and rows whose latitude exceeds the latitude limit. Anything
    subtler needs the extent comparison below it.
    """
    if not table or not x_column or not y_column:
        raise ValueError("table, x_column and y_column are all required")
    limit = f" LIMIT {int(sample_limit)}" if sample_limit else ""
    return f"""
-- Axis order for {table}: declared {declared_order}
-- Reported in three parts: unambiguous violations, then the ambiguous remainder.
WITH checked AS (
    SELECT
        {x_column}::double precision AS axis_a,
        {y_column}::double precision AS axis_b
    FROM {table}
    WHERE {x_column} IS NOT NULL AND {y_column} IS NOT NULL
)
SELECT
    'axis_a_out_of_latitude_range' AS finding,
    count(*) AS rows
FROM checked
WHERE abs(axis_a) > 90
UNION ALL
SELECT
    'axis_b_out_of_latitude_range',
    count(*)
FROM checked
WHERE abs(axis_b) > 90
UNION ALL
SELECT
    'undecidable_within_legal_ranges',
    count(*)
FROM checked
WHERE abs(axis_a) <= 90 AND abs(axis_b) <= 90
UNION ALL
SELECT
    'outside_declared_extent',
    count(*)
FROM checked
WHERE NOT (
    (axis_a BETWEEN -180 AND 180 AND axis_b BETWEEN -90 AND 90)
    OR (axis_b BETWEEN -180 AND 180 AND axis_a BETWEEN -90 AND 90)
){limit};
""".strip()


def validate_axis_order_postgis_sql(*, table: str, geometry_column: str = "geom") -> str:
    """SQL that checks a PostGIS geometry column for a latitude/longitude swap.

    For an EPSG:4326 geometry column PostGIS always stores longitude first, so a
    swap shows up as ordinates outside the legal range, or as a point that fails
    a containment test against the expected region.
    """
    if not table or not geometry_column:
        raise ValueError("table and geometry_column are both required")
    return f"""
-- PostGIS axis check for {table}.{geometry_column}
-- PostGIS stores (x=longitude, y=latitude) regardless of the EPSG axis order,
-- so a swapped import shows as ordinates outside the legal ranges.
SELECT
    ST_SRID({geometry_column}) AS srid,
    count(*)                                                     AS total,
    count(*) FILTER (WHERE ST_X({geometry_column}) NOT BETWEEN -180 AND 180) AS x_out_of_range,
    count(*) FILTER (WHERE ST_Y({geometry_column}) NOT BETWEEN -90 AND 90)   AS y_out_of_range,
    count(*) FILTER (
        WHERE ST_X({geometry_column}) BETWEEN -90 AND 90
          AND ST_Y({geometry_column}) BETWEEN -90 AND 90
    ) AS undecidable_within_legal_ranges
FROM {table}
WHERE {geometry_column} IS NOT NULL
GROUP BY 1;
""".strip()


def interpret_postgres_result(rows: Iterable[Sequence[Any]]) -> list[Any]:
    """Turn ``axis_order_sql`` output into issues.

    ``rows`` are ``(finding, rows)`` pairs in any order.
    """
    counts = {str(finding): int(count) for finding, count in rows}
    issues: list[Any] = []

    violations = counts.get("axis_a_out_of_latitude_range", 0) + counts.get(
        "axis_b_out_of_latitude_range", 0
    )
    if violations:
        issues.append(
            _issue(
                "coordinate_axis_order_swapped",
                "critical",
                f"{violations} rows carry a value above 90 in a latitude slot, so the "
                "axes are swapped. PostGIS will still accept these; they simply plot in "
                "the wrong country",
                {"violating_rows": violations},
            )
        )

    outside = counts.get("outside_declared_extent", 0)
    if outside:
        issues.append(
            _issue(
                "coordinate_axis_order_out_of_extent",
                "high",
                f"{outside} rows fall outside the legal coordinate ranges under either "
                "ordering",
                {"rows": outside},
            )
        )

    undecidable = counts.get("undecidable_within_legal_ranges", 0)
    if undecidable and not violations:
        issues.append(
            _issue(
                "coordinate_axis_order_ambiguous",
                "medium",
                f"All {undecidable} rows are inside both legal ranges, so SQL alone "
                "cannot confirm the axis order. Add an extent or containment test",
                {"rows": undecidable},
            )
        )

    return issues


__all__ = [
    "CANONICAL_ORDERS",
    "FORMAT_ORDERS",
    "LATITUDE_LIMIT",
    "LONGITUDE_LIMIT",
    "PROBLEM_NAME",
    "AxisOrderFinding",
    "canonical_order",
    "infer_axis_order",
    "interpret_postgres_result",
    "validate_axis_order",
    "validate_axis_order_postgis_sql",
    "validate_axis_order_sql",
]