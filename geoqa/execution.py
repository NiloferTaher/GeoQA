from __future__ import annotations

import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from geoqa.conversion import load_vector_dataset
from geoqa.problem_registry import VALIDATION_RULE_VERSION, get_problem_definition
from geoqa.profile_registry import GeoQAProfile, ValidationFamilyProfile, get_geoqa_profile
from geoqa.reports.report_generator import generate_report, summarize_issues
from geoqa.thermal import ThermalGuard, read_temperature_snapshot
from geoqa.plugins.registry import get_plugins
from geoqa.validation_runtime import (
    FileValidationCache,
    InMemoryValidationCache,
    ValidationLimits,
    ValidationPlanResult,
    ValidationProgressEvent,
)
from geoqa.validations.base import ValidationIssue

ProgressPrinter = Callable[[ValidationProgressEvent], None]


class _NoOpThermalGuard:
    def wait_until_safe(self, *, stage: str) -> None:
        return None


@dataclass(slots=True)
class ValidationExecutionResult:
    dataset_path: str
    profile_name: str
    issues: list[ValidationIssue]
    suppressed_issues: list[ValidationIssue]
    report_path: str | None
    duration_seconds: float
    feature_count: int
    messages: list[str]
    summary: dict[str, Any]
    thermal_summary: dict[str, Any] | None = None
    completed: bool = True
    execution_status: str = "full"
    execution_reason: str | None = None
    validators_attempted: list[str] | None = None
    validators_completed: list[str] | None = None
    validators_deferred: list[str] | None = None
    validator_coverage: list[dict[str, Any]] | None = None
    partial_result: bool = False
    operator_next_steps: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "profile_name": self.profile_name,
            "validation_rule_version": VALIDATION_RULE_VERSION,
            "issue_count": len(self.issues),
            "suppressed_issue_count": len(self.suppressed_issues),
            "report_path": self.report_path,
            "duration_seconds": self.duration_seconds,
            "feature_count": self.feature_count,
            "messages": self.messages,
            "summary": self.summary,
            "thermal_summary": self.thermal_summary,
            "completed": self.completed,
            "execution_status": self.execution_status,
            "execution_reason": self.execution_reason,
            "validators_attempted": self.validators_attempted or [],
            "validators_completed": self.validators_completed or [],
            "validators_deferred": self.validators_deferred or [],
            "validator_coverage": self.validator_coverage or [],
            "partial_result": self.partial_result,
            "operator_next_steps": self.operator_next_steps or [],
        }


def _resolve_thermal_guard(profile_name: str) -> ThermalGuard:
    if os.environ.get("GEOQA_DISABLE_THERMAL_GUARD", "").strip().lower() in {"1", "true", "yes", "on"}:
        return _NoOpThermalGuard()  # type: ignore[return-value]
    normalized = profile_name.strip().lower()
    if normalized == "strict":
        return ThermalGuard.strict()
    if normalized == "cool":
        return ThermalGuard.cool()
    if normalized == "balanced":
        return ThermalGuard.balanced()
    raise ValueError(f"Unsupported thermal profile: {profile_name!r}")


def _load_layer(path: str | Path, *, ogr_layer: str | None = None) -> Any:
    layer = load_vector_dataset(path, ogr_layer=ogr_layer)
    layer.attrs["source_path"] = str(Path(path).resolve())
    if ogr_layer is not None:
        layer.attrs["layer_name"] = ogr_layer
    return layer


def _existing_fields(layer: Any, candidates: list[str]) -> list[str]:
    columns = {str(column) for column in getattr(layer, "columns", [])}
    return [candidate for candidate in candidates if candidate in columns]


def _family_context(
    family: ValidationFamilyProfile,
    layer: Any,
    *,
    metadata: dict[str, Any] | None,
    expected_crs: Any,
    reference_layer: Any | None,
    geojson_input: Any | None,
) -> dict[str, Any]:
    context = {
        "metadata": metadata,
        "expected_crs": expected_crs,
        "reference_layer": reference_layer,
        "geojson_input": geojson_input,
    }
    if family.context_builder is not None:
        context.update(family.context_builder(layer))
    return context


def _apply_profile_policies(
    issues: list[ValidationIssue],
    profile: GeoQAProfile,
    *,
    family_name: str,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    kept: list[ValidationIssue] = []
    suppressed: list[ValidationIssue] = []
    suppressed_names = {name.lower() for name in profile.suppressed_problems}
    severity_overrides = {name.lower(): severity for name, severity in profile.severity_overrides.items()}
    downgrade_rules = {name.lower(): severity for name, severity in profile.downgrade_rules.items()}
    suppression_rules = {name.lower(): dict(rule) for name, rule in profile.suppression_rules.items()}
    problem_policies = {name.lower(): dict(policy) for name, policy in profile.problem_policies.items()}

    for issue in issues:
        issue.validator_name = issue.validator_name or family_name
        issue.validator_version = issue.validator_version or "1"
        issue.provenance = {
            **(issue.provenance or {}),
            "profile": profile.name,
            "family": family_name,
        }
        problem_definition = get_problem_definition(issue.problem_name)
        if problem_definition is not None and issue.iso_category is None:
            issue.iso_category = problem_definition.iso_category
        if problem_definition is not None and not issue.confidence:
            issue.confidence = problem_definition.default_confidence
        if problem_definition is not None and issue.actionable is None:
            issue.actionable = problem_definition.default_actionable
        override = severity_overrides.get(issue.problem_name.lower())
        if override is not None:
            issue.severity = override
        downgrade = downgrade_rules.get(issue.problem_name.lower())
        if downgrade is not None:
            issue.severity = downgrade
        policy = {
            **suppression_rules.get(issue.problem_name.lower(), {}),
            **problem_policies.get(issue.problem_name.lower(), {}),
        }
        if "severity" in policy:
            issue.severity = str(policy["severity"])
        if "confidence" in policy:
            issue.confidence = str(policy["confidence"])
        if "actionable" in policy:
            issue.actionable = bool(policy["actionable"])
        if "issue_class" in policy:
            issue.issue_class = str(policy["issue_class"])
        if "iso_category" in policy:
            issue.iso_category = str(policy["iso_category"])
        if "priority_score" in policy:
            issue.priority_score = int(policy["priority_score"])
        suppressed_by_policy = bool(policy.get("suppress", False))
        if issue.problem_name.lower() in suppressed_names or suppressed_by_policy:
            issue.suppression = {
                "status": "suppressed",
                "profile": profile.name,
                "reason": str(policy.get("suppression_reason", "Suppressed by profile configuration.")),
            }
            suppressed.append(issue)
            continue
        kept.append(issue)
    return kept, suppressed


def _progress_callback_for_family(
    family_name: str,
    callback: ProgressPrinter | None,
) -> ProgressPrinter | None:
    if callback is None:
        return None

    def wrapped(event: ValidationProgressEvent) -> None:
        callback(
            ValidationProgressEvent(
                dataset_type=event.dataset_type,
                validator_name=f"{family_name}:{event.validator_name}",
                status=event.status,
                index=event.index,
                total=event.total,
                issue_count=event.issue_count,
                cache_hit=event.cache_hit,
                message=event.message,
                progress_percent=event.progress_percent,
                eta_seconds=event.eta_seconds,
                chunk_index=event.chunk_index,
                chunk_total=event.chunk_total,
            )
        )

    return wrapped


def _execution_status_from_reason(reason: str | None, *, completed: bool, input_limited: bool = False) -> tuple[str, str | None]:
    if input_limited:
        return "input-limited", reason
    if completed and not reason:
        return "full", None
    if reason == "runtime_limit":
        return "budget-limited", "runtime budget reached"
    if reason == "max_issues_reached":
        return "partial", "issue ceiling reached"
    if reason == "actionable_target_reached":
        return "partial", "actionable target reached"
    if reason == "thermal_limit":
        return "thermal-limited", "thermal ceiling reached"
    if reason:
        return "partial", reason.replace("_", " ")
    return "partial", "partial execution"


def _operator_next_steps(
    *,
    execution_status: str,
    profile_name: str,
    summary: dict[str, Any],
    cache_enabled: bool,
    low_resource: bool,
) -> list[str]:
    steps: list[str] = []
    if execution_status in {"budget-limited", "partial"}:
        steps.append(f"Rerun with cache enabled and the same profile ({profile_name}) to reuse completed validator results.")
        steps.append("Use a narrower quick profile or a larger runtime budget if you need broader coverage.")
    if execution_status == "thermal-limited":
        steps.append("Retry with --low-resource or a cooler thermal profile to reduce workstation heat pressure.")
    top_issues = summary.get("top_issues", [])
    if top_issues:
        steps.append(f"Review the highest-volume issue first: {top_issues[0]['problem_name']}.")
    if summary.get("actionable", 0) == 0:
        steps.append("This run found no actionable issues; review informational findings before widening the profile.")
    if not cache_enabled:
        steps.append("Enable a cache directory on repeated runs to reduce redundant validator work.")
    if low_resource:
        steps.append("Low-resource mode favors actionable checks first; rerun without it if you need the fullest audit signal.")
    deduped: list[str] = []
    for step in steps:
        if step not in deduped:
            deduped.append(step)
    return deduped[:5]


def _pack_summary(profile_name: str, layer: Any, summary: dict[str, Any]) -> dict[str, Any] | None:
    normalized = profile_name.strip().lower()
    if not normalized.startswith("water_network"):
        return None
    from geoqa.packs.water_network import summarize_water_network_layer

    return summarize_water_network_layer(layer, summary)


def _run_plugins(layer: Any) -> tuple[list[ValidationIssue], list[str], list[str]]:
    plugin_issues: list[ValidationIssue] = []
    attempted: list[str] = []
    completed: list[str] = []
    for plugin in get_plugins(layer=layer):
        attempted.append(plugin.name)
        issues = plugin.validate(layer)
        for issue in issues:
            issue.validator_name = issue.validator_name or plugin.name
            issue.validator_version = issue.validator_version or plugin.version
            issue.provenance = {
                **(issue.provenance or {}),
                "plugin": plugin.name,
            }
        plugin_issues.extend(issues)
        completed.append(plugin.name)
    return plugin_issues, attempted, completed


def validate_dataset_with_profile(
    dataset_path: str | Path,
    *,
    profile: str | GeoQAProfile,
    metadata: dict[str, Any] | None = None,
    expected_crs: Any = None,
    reference_path: str | Path | None = None,
    ogr_layer: str | None = None,
    output_format: str | None = None,
    report_path: str | Path | None = None,
    max_workers: int | None = None,
    validation_chunk_size: int | None = None,
    sleep_between_validation_chunks_seconds: float = 0.0,
    thermal_profile: str = "balanced",
    limits: ValidationLimits | None = None,
    cache: InMemoryValidationCache | FileValidationCache | None = None,
    cache_tag: str | None = None,
    progress_callback: ProgressPrinter | None = None,
    max_runtime_seconds: float | None = None,
    max_issues: int | None = None,
    stop_after_actionable: int | None = None,
    prefer_high_priority: bool = False,
) -> ValidationExecutionResult:
    from geoqa.interactive_validation import validate_layer

    resolved_profile = get_geoqa_profile(profile) if isinstance(profile, str) else profile
    if resolved_profile is None:
        raise ValueError(f"Unknown GeoQA profile: {profile!r}")

    dataset_path = Path(dataset_path)
    layer = _load_layer(dataset_path, ogr_layer=ogr_layer)
    reference_layer = _load_layer(reference_path) if reference_path is not None else None
    guard = _resolve_thermal_guard(thermal_profile)
    messages: list[str] = []
    all_issues: list[ValidationIssue] = []
    suppressed_issues: list[ValidationIssue] = []
    validators_attempted: list[str] = []
    validators_completed: list[str] = []
    validators_deferred: list[str] = []
    validator_coverage: list[dict[str, Any]] = []
    started = time.perf_counter()
    completed = True
    execution_reason: str | None = None
    input_limited = False

    for family in resolved_profile.families:
        if max_runtime_seconds is not None and (time.perf_counter() - started) >= max_runtime_seconds:
            messages.append(
                f"Validation stopped before family {family.dataset_type!r} because max_runtime_seconds={max_runtime_seconds} was reached."
            )
            all_issues.append(
                ValidationIssue(
                    problem_name="runtime_limit_exceeded",
                    severity="medium",
                    description="Validation stopped early because the configured runtime ceiling was reached.",
                    solution_hint="Rerun with a larger runtime budget, narrower profile, or adaptive chunking.",
                    feature_id=None,
                    geometry=None,
                    issue_class="runtime_issue",
                    validator_name="runtime",
                    validator_version="1",
                    confidence="high",
                    actionable=True,
                    provenance={"profile": resolved_profile.name, "family": family.dataset_type},
                )
            )
            completed = False
            execution_reason = "runtime_limit"
            validators_deferred.extend(list(family.enabled_validators))
            current_family_index = resolved_profile.families.index(family)
            for later_family in resolved_profile.families[current_family_index + 1 :]:
                validators_deferred.extend(list(later_family.enabled_validators))
            break
        guard.wait_until_safe(stage=f"profile_{resolved_profile.name}_{family.dataset_type}_pre")
        context = _family_context(
            family,
            layer,
            metadata=metadata,
            expected_crs=expected_crs,
            reference_layer=reference_layer,
            geojson_input=dataset_path,
        )
        runtime_profile = family.to_validation_profile(name=f"{resolved_profile.name}:{family.dataset_type}")
        remaining_runtime = None
        if max_runtime_seconds is not None:
            remaining_runtime = max(max_runtime_seconds - (time.perf_counter() - started), 0.0)
        try:
            family_result = validate_layer(
                layer,
                family.dataset_type,
                profile=runtime_profile,
                progress_callback=_progress_callback_for_family(family.dataset_type, progress_callback),
                cache=cache,
                cache_tag=cache_tag,
                max_workers=max_workers,
                limits=limits,
                max_runtime_seconds=remaining_runtime,
                max_issues=max_issues,
                stop_after_actionable=stop_after_actionable,
                prefer_high_priority=prefer_high_priority,
                problem_policies=resolved_profile.problem_policies,
                return_result=True,
                **context,
            )
        except ValueError as exc:
            messages.append(str(exc))
            completed = False
            input_limited = True
            execution_reason = "input_limit"
            remaining_families = resolved_profile.families[resolved_profile.families.index(family) :]
            for deferred_family in remaining_families:
                validators_deferred.extend(list(deferred_family.enabled_validators))
            break
        assert isinstance(family_result, ValidationPlanResult)
        family_issues = family_result.issues
        validators_attempted.extend(list(family_result.validators_attempted))
        validators_completed.extend(list(family_result.validators_completed))
        validators_deferred.extend(list(family_result.validators_deferred))
        for row in family_result.validator_coverage:
            validator_coverage.append(
                {
                    **row,
                    "family": family.dataset_type,
                    "layer_name": dataset_path.stem,
                    "layer_path": str(dataset_path),
                    "geometry_type": row.get("layer_geometry_type"),
                }
            )
        kept, suppressed = _apply_profile_policies(family_issues, resolved_profile, family_name=family.dataset_type)
        all_issues.extend(kept)
        suppressed_issues.extend(suppressed)
        if family_result.partial_result:
            completed = False
            execution_reason = family_result.stop_reason or "partial_execution"
            messages.append(
                f"Validation stopped during family {family.dataset_type!r} because {execution_reason.replace('_', ' ')}."
            )
            current_family_index = resolved_profile.families.index(family)
            for later_family in resolved_profile.families[current_family_index + 1 :]:
                validators_deferred.extend(list(later_family.enabled_validators))
            break
        if sleep_between_validation_chunks_seconds > 0:
            time.sleep(sleep_between_validation_chunks_seconds)

    plugin_attempted: list[str] = []
    plugin_completed: list[str] = []
    if completed and not input_limited:
        plugin_issues, plugin_attempted, plugin_completed = _run_plugins(layer)
        if plugin_issues:
            kept, suppressed = _apply_profile_policies(plugin_issues, resolved_profile, family_name="plugins")
            all_issues.extend(kept)
            suppressed_issues.extend(suppressed)
            messages.append(f"Plugin validation added {len(kept)} issues from {len(plugin_completed)} applicable plugin(s).")
    duration = time.perf_counter() - started
    thermal_snapshot = read_temperature_snapshot()
    thermal_summary = {
        "source": thermal_snapshot.source,
        "max_temp_c": thermal_snapshot.max_temp_c,
        "avg_temp_c": thermal_snapshot.avg_temp_c,
        "sensor_count": thermal_snapshot.sensor_count,
        "runtime_seconds": round(duration, 4),
    }
    summary = summarize_issues(all_issues)
    summary["suppressed_issue_count"] = len(suppressed_issues)
    execution_status, normalized_reason = _execution_status_from_reason(
        execution_reason,
        completed=completed,
        input_limited=input_limited,
    )
    summary["execution_status"] = execution_status
    summary["execution_reason"] = normalized_reason
    summary["validators_attempted"] = validators_attempted
    summary["validators_completed"] = validators_completed
    summary["validators_deferred"] = validators_deferred
    summary["validator_coverage"] = validator_coverage
    summary["plugin_validators_attempted"] = plugin_attempted
    summary["plugin_validators_completed"] = plugin_completed
    summary["partial_result"] = execution_status != "full"
    summary["operator_next_steps"] = _operator_next_steps(
        execution_status=execution_status,
        profile_name=resolved_profile.name,
        summary=summary,
        cache_enabled=cache is not None,
        low_resource=prefer_high_priority,
    )
    pack_summary = _pack_summary(resolved_profile.name, layer, summary)
    if pack_summary is not None:
        summary["pack_summary"] = pack_summary
    written_report: str | None = None
    if output_format is not None and report_path is not None:
        written_report = str(generate_report(all_issues, output_format=output_format, file_path=str(report_path), summary=summary))
    return ValidationExecutionResult(
        dataset_path=str(dataset_path),
        profile_name=resolved_profile.name,
        issues=all_issues,
        suppressed_issues=suppressed_issues,
        report_path=written_report,
        duration_seconds=duration,
        feature_count=len(layer) if hasattr(layer, "__len__") else 0,
        messages=messages,
        summary=summary,
        thermal_summary=thermal_summary,
        completed=completed,
        execution_status=execution_status,
        execution_reason=normalized_reason,
        validators_attempted=validators_attempted,
        validators_completed=validators_completed,
        validators_deferred=validators_deferred,
        validator_coverage=validator_coverage,
        partial_result=execution_status != "full",
        operator_next_steps=summary["operator_next_steps"],
    )


__all__ = ["ValidationExecutionResult", "validate_dataset_with_profile"]
