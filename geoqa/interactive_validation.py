from __future__ import annotations

from pathlib import Path
from typing import Any

from geoqa.reports.report_generator import generate_report
from geoqa.script_base import GeoQAScriptBase
from geoqa.validation_runtime import (
    FileValidationCache,
    InMemoryValidationCache,
    ValidationLimits,
    ValidationPlanResult,
    ValidationProfile,
    execute_validation_plan,
)


class InteractiveValidationScript(GeoQAScriptBase[Path, list[dict[str, Any]]]):
    """Interactive GeoQA validation entry point for dataset-level workflows."""

    def __init__(
        self,
        *,
        dataset_path: str | Path,
        dataset_type: str,
        output_format: str = "csv",
        report_path: str | Path = "validation_report",
        metadata: dict[str, Any] | None = None,
        expected_crs: Any = None,
        reference_path: str | Path | None = None,
        required_fields: list[str] | None = None,
        unique_field: str | None = None,
        domain_field: str | None = None,
        valid_domain: Any = None,
        role_field: str | None = None,
        allowed_endpoint_values: set[str] | None = None,
        geojson_input: Any | None = None,
        profile: str | ValidationProfile | None = None,
        progress_callback: Any | None = None,
        cache: InMemoryValidationCache | FileValidationCache | None = None,
        cache_tag: str | None = None,
        max_workers: int | None = None,
        limits: ValidationLimits | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.dataset_path = Path(dataset_path)
        self.dataset_type = dataset_type.strip().lower()
        self.output_format = output_format.strip().lower()
        self.report_path = str(report_path)
        self.metadata = metadata
        self.expected_crs = expected_crs
        self.reference_path = Path(reference_path) if reference_path is not None else None
        self.required_fields = required_fields or []
        self.unique_field = unique_field
        self.domain_field = domain_field
        self.valid_domain = valid_domain
        self.role_field = role_field
        self.allowed_endpoint_values = allowed_endpoint_values
        self.geojson_input = geojson_input
        self.profile = profile
        self.progress_callback = progress_callback
        self.cache = cache
        self.cache_tag = cache_tag
        self.max_workers = max_workers
        self.limits = limits
        self.extra_context = extra_context or {}

    def load_items(self) -> list[Path]:
        return [self.dataset_path]

    def process_item(self, item: Path) -> list[dict[str, Any]]:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise RuntimeError(
                "Interactive dataset validation requires GeoPandas. Install geopandas to use this workflow."
            ) from exc

        layer = gpd.read_file(item)
        layer.attrs["source_path"] = str(item.resolve())
        reference_layer = gpd.read_file(self.reference_path) if self.reference_path is not None else None
        if reference_layer is not None and self.reference_path is not None:
            reference_layer.attrs["source_path"] = str(self.reference_path.resolve())
        issues = validate_layer(
            layer,
            self.dataset_type,
            metadata=self.metadata,
            expected_crs=self.expected_crs,
            reference_layer=reference_layer,
            required_fields=self.required_fields,
            unique_field=self.unique_field,
            domain_field=self.domain_field,
            valid_domain=self.valid_domain,
            role_field=self.role_field,
            allowed_endpoint_values=self.allowed_endpoint_values,
            geojson_input=self.geojson_input or item,
            profile=self.profile,
            progress_callback=self.progress_callback,
            cache=self.cache,
            cache_tag=self.cache_tag,
            max_workers=self.max_workers,
            limits=self.limits,
            **self.extra_context,
        )
        generate_report(issues, output_format=self.output_format, file_path=self.report_path)
        return [issue.to_dict() for issue in issues]


def validate_layer(
    layer: Any,
    dataset_type: str,
    *,
    metadata: dict[str, Any] | None = None,
    expected_crs: Any = None,
    reference_layer: Any | None = None,
    required_fields: list[str] | None = None,
    unique_field: str | None = None,
    domain_field: str | None = None,
    valid_domain: Any = None,
    role_field: str | None = None,
    allowed_endpoint_values: set[str] | None = None,
    geojson_input: Any | None = None,
    profile: str | ValidationProfile | None = None,
    progress_callback: Any | None = None,
    cache: InMemoryValidationCache | FileValidationCache | None = None,
    cache_tag: str | None = None,
    max_workers: int | None = None,
    limits: ValidationLimits | None = None,
    max_runtime_seconds: float | None = None,
    max_issues: int | None = None,
    stop_after_actionable: int | None = None,
    prefer_high_priority: bool = False,
    problem_policies: dict[str, dict[str, Any]] | None = None,
    return_result: bool = False,
    **extra_context: Any,
) -> list[Any] | ValidationPlanResult:
    """Route validation based on the requested dataset type."""
    return execute_validation_plan(
        layer,
        dataset_type,
        metadata=metadata,
        expected_crs=expected_crs,
        reference_layer=reference_layer,
        required_fields=required_fields,
        unique_field=unique_field,
        domain_field=domain_field,
        valid_domain=valid_domain,
        role_field=role_field,
        allowed_endpoint_values=allowed_endpoint_values,
        geojson_input=geojson_input,
        profile=profile,
        progress_callback=progress_callback,
        cache=cache,
        cache_tag=cache_tag,
        max_workers=max_workers,
        limits=limits,
        max_runtime_seconds=max_runtime_seconds,
        max_issues=max_issues,
        stop_after_actionable=stop_after_actionable,
        prefer_high_priority=prefer_high_priority,
        problem_policies=problem_policies,
        return_result=return_result,
        **extra_context,
    )


def validate_dataset(
    dataset_path: str | Path,
    dataset_type: str,
    *,
    output_format: str = "csv",
    report_path: str | Path = "validation_report",
    metadata: dict[str, Any] | None = None,
    expected_crs: Any = None,
    reference_path: str | Path | None = None,
    required_fields: list[str] | None = None,
    unique_field: str | None = None,
    domain_field: str | None = None,
    valid_domain: Any = None,
    role_field: str | None = None,
    allowed_endpoint_values: set[str] | None = None,
    geojson_input: Any | None = None,
    profile: str | ValidationProfile | None = None,
    progress_callback: Any | None = None,
    cache: InMemoryValidationCache | FileValidationCache | None = None,
    cache_tag: str | None = None,
    max_workers: int | None = None,
    limits: ValidationLimits | None = None,
    **extra_context: Any,
) -> list[dict[str, Any]]:
    """Convenience wrapper for interactive dataset validation."""
    script = InteractiveValidationScript(
        dataset_path=dataset_path,
        dataset_type=dataset_type,
        output_format=output_format,
        report_path=report_path,
        metadata=metadata,
        expected_crs=expected_crs,
        reference_path=reference_path,
        required_fields=required_fields,
        unique_field=unique_field,
        domain_field=domain_field,
        valid_domain=valid_domain,
        role_field=role_field,
        allowed_endpoint_values=allowed_endpoint_values,
        geojson_input=geojson_input,
        profile=profile,
        progress_callback=progress_callback,
        cache=cache,
        cache_tag=cache_tag,
        max_workers=max_workers,
        limits=limits,
        extra_context=extra_context,
    )
    results = script.run()
    return results[0].result


def main() -> None:
    raise SystemExit("Interactive prompts were removed from the core library. Use `python -m geoqa ...` or call the Python API directly.")


if __name__ == "__main__":
    main()
