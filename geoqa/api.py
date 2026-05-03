from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geoqa.conversion import export_vector_layer, load_vector_dataset
from geoqa.execution import ValidationExecutionResult, validate_dataset_with_profile
from geoqa.fixes import apply_basic_geometry_fixes, apply_repair_plan
from geoqa.ml.annotations import quality_score_from_issues
from geoqa.ml.features import build_issue_feature_rows
from geoqa.reports.report_generator import generate_report

_SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _max_severity(result: ValidationExecutionResult) -> str | None:
    highest: str | None = None
    highest_rank = -1
    for issue in result.issues:
        rank = _SEVERITY_ORDER.get(str(issue.severity).lower(), 0)
        if rank > highest_rank:
            highest = issue.severity
            highest_rank = rank
    return highest


def _infer_export_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    mapping = {
        ".geojson": "geojson",
        ".json": "geojson",
        ".csv": "csv",
        ".parquet": "geoparquet",
        ".gpkg": "gpkg",
        ".kml": "kml",
        ".zip": "shapefile",
        ".shp": "shapefile",
    }
    if suffix not in mapping:
        raise ValueError(f"Unable to infer export format from path: {path!r}")
    return mapping[suffix]


@dataclass(slots=True)
class GeoQAFixedLayer:
    """Conservative fixed-layer wrapper returned by ``GeoQAReport.fix()``."""

    layer: Any
    source_path: str | None = None

    def export(self, path: str | Path, *, output_format: str | None = None) -> Path:
        resolved_format = output_format or _infer_export_format(path)
        return export_vector_layer(self.layer, path, output_format=resolved_format)


@dataclass(slots=True)
class GeoQAReport:
    """
    User-facing validation result wrapper.

    This keeps the underlying engine result intact while presenting a simpler,
    product-shaped Python API.
    """

    _result: ValidationExecutionResult

    def __getattr__(self, name: str) -> Any:
        return getattr(self._result, name)

    @property
    def summary(self) -> dict[str, Any]:
        """Validation summary dictionary."""
        return dict(self._result.summary)

    @property
    def issues(self) -> list[Any]:
        """Validation issues detected for the dataset."""
        return list(self._result.issues)

    @property
    def suppressed_issues(self) -> list[Any]:
        """Issues suppressed by the selected profile."""
        return list(self._result.suppressed_issues)

    def score(self, *, method: str = "conservative") -> float:
        """
        Return a normalized quality score for this report.

        Supported methods:
        - ``conservative``: emphasizes the most severe findings
        - ``ml_ready``: discounts non-actionable findings
        """
        method_normalized = method.strip().lower()
        if method_normalized == "conservative":
            issues = self._result.issues
        elif method_normalized == "ml_ready":
            issues = [issue for issue in self._result.issues if issue.actionable]
        else:
            raise ValueError(f"Unsupported score method: {method!r}")
        return quality_score_from_issues(len(issues), _max_severity(self._result) if issues else None)

    def to_ml(self) -> list[dict[str, Any]]:
        """Return issue rows in a simple ML-friendly feature format."""
        return build_issue_feature_rows(self.issues)

    def to_dataframe(self) -> Any:
        """Return the issues as a pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pandas is required for GeoQAReport.to_dataframe().") from exc
        return pd.DataFrame([issue.to_dict() for issue in self._result.issues])

    def export(self, file_path: str | Path, *, output_format: str = "json") -> Path:
        """Export the report issues using the standard GeoQA report writer."""
        resolved_format = output_format or _infer_export_format(file_path)
        return generate_report(
            self.issues,
            output_format=resolved_format,
            file_path=str(file_path),
            summary=self._result.summary,
        )

    def fix(self, *, auto: bool = True, repair_profile: Any | None = None) -> GeoQAFixedLayer:
        """
        Apply conservative deterministic fixes to the source dataset.

        This is intentionally limited to safe geometry-cleaning helpers rather
        than broad automatic remediation.
        """
        if not auto:
            raise ValueError("GeoQAReport.fix() currently supports only auto=True.")
        layer = load_vector_dataset(self._result.dataset_path)
        if repair_profile is not None:
            fixed = apply_repair_plan(layer, profile=repair_profile)
        else:
            fixed = apply_basic_geometry_fixes(layer)
        return GeoQAFixedLayer(fixed, source_path=self._result.dataset_path)

    def clean(self, *, auto: bool = True, repair_profile: Any | None = None) -> GeoQAFixedLayer:
        """Alias for ``fix()`` for users who think in terms of data cleaning."""
        return self.fix(auto=auto, repair_profile=repair_profile)

    def to_dict(self) -> dict[str, Any]:
        """Return the full execution result as a dictionary."""
        return self._result.to_dict()

    def __repr__(self) -> str:
        return (
            f"<GeoQAReport issues={len(self.issues)} "
            f"score={self.score():.2f} profile={self._result.profile_name!r}>"
        )


def validate(
    dataset_path: str | Path,
    profile: str = "generic_quick",
    *,
    return_summary: bool = False,
    **kwargs: Any,
) -> GeoQAReport | dict[str, Any]:
    """
    Validate a dataset with a named GeoQA profile.

    Examples:
        >>> import geoqa
        >>> report = geoqa.validate("data.geojson")
        >>> report.summary
        >>> report.score()
    """
    result = validate_dataset_with_profile(dataset_path, profile=profile, **kwargs)
    report = GeoQAReport(result)
    if return_summary:
        return report.summary
    return report


def score(
    dataset_path: str | Path,
    profile: str = "generic_quick",
    *,
    method: str = "conservative",
    **kwargs: Any,
) -> float:
    """
    Return a simple normalized GeoQA quality score for a dataset.

    Examples:
        >>> import geoqa
        >>> geoqa.score("data.geojson")
        >>> geoqa.score("data.geojson", method="ml_ready")
    """
    report = validate(dataset_path, profile=profile, **kwargs)
    assert isinstance(report, GeoQAReport)
    return report.score(method=method)


__all__ = ["GeoQAFixedLayer", "GeoQAReport", "score", "validate"]
