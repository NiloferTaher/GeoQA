"""Tabular views of GeoQA findings for analysis and DBA work.

GeoJSON is a poor analysis format: properties arrive nested, every feature
repeats the same keys, and geometry is opaque. These helpers flatten a
FeatureCollection into a flat, spreadsheet-ready table with WKT plus
centroid longitude/latitude, and write CSV or XLSX.

Works on a GeoJSON file, a FeatureCollection dict, or a ``GeoQAReport``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

_SCALAR_PREFIX = "attr_"


def _flatten_value(value: Any) -> Any:
    """Render a nested property as a single spreadsheet-friendly cell."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _flatten_properties(properties: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts into dotted column names."""
    row: dict[str, Any] = {}
    for key, value in properties.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            nested = _flatten_properties(value, prefix=f"{name}.")
            if nested:
                row.update(nested)
            else:
                row[name] = "{}"
        else:
            row[name] = _flatten_value(value)
    return row


def _geometry_columns(geometry: Any) -> dict[str, Any]:
    """Add WKT and centroid coordinates so the table is mappable and plottable."""
    if not isinstance(geometry, dict):
        return {"geometry": None, "wkt": None, "centroid_lon": None, "centroid_lat": None}
    try:
        from shapely.geometry import shape

        geom = shape(geometry)
    except Exception:
        return {"geometry": json.dumps(geometry), "wkt": None, "centroid_lon": None, "centroid_lat": None}
    centroid = geom.centroid
    return {
        "geometry": None,
        "wkt": geom.wkt,
        "centroid_lon": round(centroid.x, 8),
        "centroid_lat": round(centroid.y, 8),
    }


def issues_to_rows(issues: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert raw issues (geometry or not) into flat rows.

    Findings without geometry are still real findings. Dropping them would make
    an otherwise successful run look like an empty table, so they are kept with
    blank spatial columns and ``has_geometry = False``.
    """
    rows: list[dict[str, Any]] = []
    for index, issue in enumerate(issues):
        payload = issue.to_dict() if hasattr(issue, "to_dict") else dict(issue)
        geometry = payload.pop("geometry", None)
        row: dict[str, Any] = {"feature_index": index}
        row.update(_flatten_properties(payload))
        row.update(_geometry_columns(geometry))
        row["has_geometry"] = isinstance(geometry, dict) and bool(geometry.get("type"))
        rows.append(row)
    return rows


def features_to_rows(features: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert GeoJSON features into flat, analysis-ready rows."""
    rows: list[dict[str, Any]] = []
    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        row: dict[str, Any] = {"feature_index": index}
        row.update(_flatten_properties(properties))
        geometry_columns = _geometry_columns(feature.get("geometry"))
        geometry_columns["has_geometry"] = geometry_columns["wkt"] is not None
        row.update(geometry_columns)
        rows.append(row)
    return rows


def features_to_dataframe(features: Iterable[dict[str, Any]]) -> Any:
    """Return findings as a pandas DataFrame with a stable column order."""
    import pandas as pd

    rows = features_to_rows(features)
    return _order_columns(pd.DataFrame(rows))


def _coerce_frame(frame: Any) -> Any:
    """Replace list/dict cells that spreadsheet writers cannot handle natively."""
    frame = frame.copy()
    for column in frame.columns:
        if frame[column].map(lambda v: isinstance(v, (dict, list, tuple))).any():
            frame[column] = frame[column].map(
                lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False)
                if isinstance(v, (dict, list, tuple))
                else v
            )
    return frame


def write_xlsx(frame: Any, path: str | Path, *, sheet_name: str = "geoqa_findings") -> Path:
    """Write a DataFrame to XLSX with a frozen header and readable widths."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _coerce_frame(frame)

    try:
        import xlsxwriter  # noqa: F401

        with pd_excel_writer(target, engine="xlsxwriter") as writer:
            payload.to_excel(writer, sheet_name=sheet_name, index=False)
            workbook = writer.book
            header = workbook.add_format({"bold": True, "bg_color": "#1F2937", "font_color": "white"})
            worksheet = writer.sheets[sheet_name]
            for column_index, name in enumerate(payload.columns):
                worksheet.write(0, column_index, str(name), header)
                values = payload[name].map(str).head(200)
                widest = max([len(str(name))] + [len(v) for v in values])
                worksheet.set_column(column_index, column_index, min(max(widest + 2, 10), 60))
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(payload), 1), max(len(payload.columns) - 1, 0))
        return target
    except ImportError:
        payload.to_excel(target, sheet_name=sheet_name, index=False)
        return target


def pd_excel_writer(path: str | Path, engine: str) -> Any:
    """Return a pandas ExcelWriter positioned at the output path."""
    import pandas as pd

    return pd.ExcelWriter(path, engine=engine)


def _normalise_source(source: Any) -> dict[str, Any]:
    """Accept a GeoJSON path, dict, GeoQAReport, or issues iterable."""
    if isinstance(source, dict) and source.get("type") == "FeatureCollection":
        return source
    if hasattr(source, "to_geojson"):
        return source.to_geojson()
    if isinstance(source, (str, Path)):
        return json.loads(Path(source).read_text(encoding="utf-8"))
    if hasattr(source, "issues"):
        from .geojson import issues_to_geojson

        return issues_to_geojson(source.issues)
    if isinstance(source, Iterable):
        from .geojson import issues_to_geojson

        return issues_to_geojson(source)
    raise TypeError(f"Unsupported GeoQA table source: {type(source)!r}")


def _issue_source(source: Any) -> list[Any] | None:
    """Return an issues iterable when the source exposes one, else None."""
    if hasattr(source, "issues"):
        return list(source.issues)
    if hasattr(source, "to_geojson"):
        return None
    if isinstance(source, (str, Path)):
        return None
    if isinstance(source, Iterable) and not isinstance(source, dict):
        items = list(source)
        if items and (hasattr(items[0], "to_dict") or isinstance(items[0], dict)):
            return items
    return None


def geojson_to_dataframe(source: Any, *, include_unmapped: bool = True) -> Any:
    """Return a GeoJSON file/dict/report as a flat analysis DataFrame.

    When no finding carries geometry the table is built from the raw issues
    instead, so attribute-only findings (CRS problems, missing indexes, schema
    issues) are never silently dropped.
    """
    collection = _normalise_source(source)
    features = collection.get("features", [])
    if not features and include_unmapped:
        import pandas as pd

        embedded = (collection.get("geoqa") or {}).get("unmapped_issues") or []
        if embedded:
            frame = pd.DataFrame(issues_to_rows(embedded))
            return _order_columns(frame)
        issues = _issue_source(source)
        if issues is None and isinstance(source, (str, Path)):
            loaded = json.loads(Path(source).read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("type") != "FeatureCollection":
                issues = [loaded]
        if issues:
            frame = pd.DataFrame(issues_to_rows(issues))
            return _order_columns(frame)
    return features_to_dataframe(features)


def _order_columns(frame: Any) -> Any:
    """Apply the stable column order used by ``features_to_dataframe``."""
    if frame.empty:
        return frame
    leading = [
        column
        for column in (
            "feature_index",
            "issue_id",
            "problem_name",
            "severity",
            "confidence",
            "priority_score",
            "actionable",
            "suppressed",
            "what_geoqa_found",
            "why_it_matters",
            "recommended_action",
            "description",
            "solution_hint",
        )
        if column in frame.columns
    ]
    trailing = [
        column
        for column in ("geometry_type", "feature_id", "has_geometry", "wkt", "centroid_lon", "centroid_lat", "geometry")
        if column in frame.columns
    ]
    middle = [column for column in frame.columns if column not in leading + trailing]
    return frame[leading + middle + trailing]


def geojson_to_table(source: Any, path: str | Path, *, sheet_name: str = "geoqa_findings") -> Path:
    """Write findings to ``.csv`` or ``.xlsx`` (inferred from the suffix)."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise ValueError(f"Unsupported table format {suffix!r}; use .csv or .xlsx.")

    frame = _coerce_frame(geojson_to_dataframe(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".csv":
        frame.to_csv(target, index=False, encoding="utf-8-sig")
        return target
    return write_xlsx(frame, target, sheet_name=sheet_name)


def geojson_to_pivot(
    source: Any,
    *,
    index: str = "problem_name",
    columns: str = "severity",
    values: str = "count",
) -> Any:
    """Return a severity x problem pivot table for quick DBA summaries."""
    frame = geojson_to_dataframe(source)
    if frame.empty:
        return frame
    for column in (index, columns):
        if column not in frame.columns:
            raise ValueError(f"Column {column!r} is not present in the findings table.")
    frame = frame.copy()
    frame["count"] = 1
    return frame.pivot_table(index=index, columns=columns, values=values, aggfunc="sum", fill_value=0)


__all__ = [
    "features_to_dataframe",
    "features_to_rows",
    "geojson_to_dataframe",
    "geojson_to_pivot",
    "geojson_to_table",
    "write_xlsx",
]