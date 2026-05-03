from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from geoqa.ml.annotations import annotate_layer_with_issues
from geoqa.ml.features import build_issue_feature_rows
from geoqa.validations.base import ValidationIssue


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        return value.item()
    except Exception:
        pass
    wkt = getattr(value, "wkt", None)
    if isinstance(wkt, str):
        return wkt
    return str(value)


def export_annotated_dataset(
    layer: Any,
    issues: list[ValidationIssue],
    output_path: str | Path,
    *,
    format: str = "csv",
    id_field: str = "ID",
) -> Path:
    """
    Export an issue-annotated dataset in a training-friendly format.

    Supported formats:
    - csv
    - jsonl
    - geoparquet
    """
    annotated = annotate_layer_with_issues(layer, issues, id_field=id_field)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = format.lower()

    if fmt == "csv":
        frame = annotated.copy()
        records = frame.to_dict(orient="records")
        prepared = [_json_safe(record) for record in records]
        fieldnames = list(prepared[0].keys()) if prepared else list(getattr(frame, "columns", []))
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in prepared:
                writer.writerow(record)
        return output

    if fmt == "jsonl":
        records = annotated.to_dict(orient="records")
        with output.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(_json_safe(record), ensure_ascii=False) + "\n")
        return output

    if fmt == "geoparquet":
        if not hasattr(annotated, "to_parquet"):
            raise TypeError("Layer does not support GeoParquet export.")
        annotated.to_parquet(output, index=False)
        return output

    raise ValueError(f"Unsupported export format: {format!r}")


def export_issue_features(
    issues: list[ValidationIssue],
    output_path: str | Path,
    *,
    format: str = "jsonl",
) -> Path:
    """Export issue-derived ML feature rows."""
    rows = build_issue_feature_rows(issues)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = format.lower()

    if fmt == "jsonl":
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(_json_safe(row), ensure_ascii=False) + "\n")
        return output

    if fmt == "csv":
        fieldnames = list(rows[0].keys()) if rows else []
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(_json_safe(row))
        return output

    raise ValueError(f"Unsupported issue-feature export format: {format!r}")
