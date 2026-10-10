from __future__ import annotations

from pathlib import Path
from typing import Any

from geoqa.agents.agentic_crsfix import agentic_crsfix
from geoqa.reports.report_generator import generate_report
from geoqa.validations.crs import invalid_crs, missing_crs


def crs_validation(
    dataset_path: str | Path,
    *,
    expected_crs: Any = "EPSG:4326",
    output_format: str = "csv",
    report_path: str = "crs_validation_report",
    auto_fix: bool = False,
) -> dict[str, Any]:
    """
    Validate CRS state for a dataset and optionally reproject it to the expected CRS.
    """
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("CRS automation requires GeoPandas. Install geopandas to use this workflow.") from exc

    layer = gpd.read_file(dataset_path)
    issues = []
    issues.extend(missing_crs(layer))
    issues.extend(invalid_crs(layer, expected_crs))
    report = generate_report(issues, output_format=output_format, file_path=report_path)

    fixed = False
    fixed_layer = None
    if auto_fix and getattr(layer, "crs", None) is not None:
        fixed_layer = agentic_crsfix(layer, crs_format=expected_crs)
        fixed = fixed_layer is not layer

    return {
        "issues": [issue.to_dict() for issue in issues],
        "report_path": str(report),
        "fixed": fixed,
        "expected_crs": str(expected_crs),
    }


__all__ = ["crs_validation"]
