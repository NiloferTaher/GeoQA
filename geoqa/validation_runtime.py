from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from geoqa.validations.accuracy import coordinate_precision, positional_accuracy, xy_tolerance
from geoqa.validations.attributes import domain_range_checks, required_nulls, uniqueness
from geoqa.validations.base import ValidationIssue
from geoqa.validations.crs import invalid_crs, missing_crs
from geoqa.validations.geometry import (
    below_minimum_feature_length,
    duplicate_vertex,
    null_geometry,
    self_intersection,
    sharp_angle_cutback,
)
from geoqa.validations.integrity import missing_spatial_index, non_rfc7946_geojson, outdated_index
from geoqa.validations.metadata import incomplete_metadata, missing_metadata_fields
from geoqa.validations.topology import (
    boundary_mismatch_against_reference,
    duplicate_geometry_same_layer,
    feature_not_split_at_intersection,
    feature_within_feature,
    isolated_network_segment,
    line_dangle,
    line_intersection_same_layer,
    polygon_gap_same_layer,
    polygon_overlap_same_layer,
    suspicious_near_miss_endpoints,
    unsnapped_endpoints_within_tolerance,
)

ValidatorCallable = Callable[..., list[ValidationIssue]]
ProgressCallback = Callable[["ValidationProgressEvent"], None]


@dataclass(slots=True, frozen=True)
class ValidationProgressEvent:
    dataset_type: str
    validator_name: str
    status: str
    index: int
    total: int
    issue_count: int | None = None
    cache_hit: bool = False
    message: str | None = None
    progress_percent: float | None = None
    eta_seconds: float | None = None
    chunk_index: int | None = None
    chunk_total: int | None = None


@dataclass(slots=True, frozen=True)
class ValidationProfile:
    name: str
    dataset_type: str | None = None
    enabled_validators: tuple[str, ...] = ()
    disabled_validators: tuple[str, ...] = ()
    validator_options: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ValidationLimits:
    max_features: int | None = None
    max_columns: int | None = None
    max_source_size_mb: float | None = None
    max_total_vertices: int | None = None


@dataclass(slots=True, frozen=True)
class ValidationPlanResult:
    issues: list[ValidationIssue]
    validators_attempted: tuple[str, ...]
    validators_completed: tuple[str, ...]
    validators_deferred: tuple[str, ...]
    partial_result: bool
    stop_reason: str | None = None
    validator_coverage: tuple[dict[str, Any], ...] = ()


@dataclass(slots=True)
class _ValidatorSpec:
    name: str
    func: ValidatorCallable
    context: dict[str, Any]
    base_cost: int = 5
    expected_geometry_types: tuple[str, ...] = ()


class InMemoryValidationCache:
    def __init__(self) -> None:
        self._store: dict[str, list[ValidationIssue]] = {}

    def get(self, key: str) -> list[ValidationIssue] | None:
        value = self._store.get(key)
        return deepcopy(value) if value is not None else None

    def set(self, key: str, value: list[ValidationIssue]) -> None:
        self._store[key] = deepcopy(value)

    def clear(self) -> None:
        self._store.clear()


class FileValidationCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> list[ValidationIssue] | None:
        cache_path = self._cache_path(key)
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, list):
            return None
        issues: list[ValidationIssue] = []
        for item in payload:
            if not isinstance(item, dict):
                return None
            issues.append(
                ValidationIssue(
                    issue_id=item.get("issue_id"),
                    problem_name=str(item.get("problem_name", "")),
                    severity=str(item.get("severity", "medium")),
                    description=str(item.get("description", "")),
                    solution_hint=str(item.get("solution_hint", "")),
                    feature_id=item.get("feature_id"),
                    geometry=item.get("geometry"),
                    validator_name=item.get("validator_name"),
                    validator_version=item.get("validator_version"),
                    issue_class=str(item.get("issue_class", "data_issue")),
                    suppression=item.get("suppression"),
                    provenance=item.get("provenance"),
                    iso_category=item.get("iso_category"),
                    confidence=str(item.get("confidence", "medium")),
                    actionable=bool(item.get("actionable", True)),
                    priority_score=int(item.get("priority_score", 0)) if item.get("priority_score") is not None else None,
                )
            )
        return issues

    def set(self, key: str, value: list[ValidationIssue]) -> None:
        cache_path = self._cache_path(key)
        payload = [issue.to_dict() for issue in value]
        cache_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def clear(self) -> None:
        for cache_path in self.cache_dir.glob("*.json"):
            try:
                cache_path.unlink()
            except FileNotFoundError:
                continue


_CUSTOM_VALIDATORS: dict[str, dict[str, ValidatorCallable]] = {}
_VALIDATION_PROFILES: dict[str, ValidationProfile] = {}


def register_custom_validator(dataset_type: str, name: str, func: ValidatorCallable) -> None:
    normalized_dataset_type = dataset_type.strip().lower()
    normalized_name = name.strip().lower()
    if not normalized_dataset_type or not normalized_name:
        raise ValueError("Dataset type and validator name must be non-empty.")
    registry = _CUSTOM_VALIDATORS.setdefault(normalized_dataset_type, {})
    registry[normalized_name] = func


def clear_custom_validators() -> None:
    _CUSTOM_VALIDATORS.clear()


def list_custom_validators(dataset_type: str | None = None) -> dict[str, list[str]] | list[str]:
    if dataset_type is None:
        return {name: sorted(items) for name, items in ((key, value.keys()) for key, value in _CUSTOM_VALIDATORS.items())}
    return sorted(_CUSTOM_VALIDATORS.get(dataset_type.strip().lower(), {}).keys())


def register_validation_profile(profile: ValidationProfile) -> None:
    _VALIDATION_PROFILES[profile.name.strip().lower()] = profile


def clear_validation_profiles() -> None:
    _VALIDATION_PROFILES.clear()


def get_validation_profile(profile: str | ValidationProfile | None) -> ValidationProfile | None:
    if profile is None:
        return None
    if isinstance(profile, ValidationProfile):
        return profile
    return _VALIDATION_PROFILES.get(profile.strip().lower())


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "to_string"):
        try:
            return value.to_string()
        except Exception:
            pass
    return repr(value)


def _layer_signature(layer: Any) -> dict[str, Any]:
    attrs = getattr(layer, "attrs", {}) or {}
    geometry_types: dict[str, int] = {}
    if "geometry" in getattr(layer, "columns", []):
        try:
            for geometry in layer["geometry"]:
                geometry_name = getattr(geometry, "geom_type", None) if geometry is not None else "None"
                if geometry_name is None:
                    geometry_name = type(geometry).__name__
                geometry_types[str(geometry_name)] = geometry_types.get(str(geometry_name), 0) + 1
        except Exception:
            geometry_types = {}
    return {
        "row_count": len(layer) if hasattr(layer, "__len__") else None,
        "columns": [str(column) for column in getattr(layer, "columns", [])],
        "crs": _json_safe(getattr(layer, "crs", None)),
        "source_path": _json_safe(attrs.get("source_path")),
        "geometry_types": geometry_types,
    }


def _source_size_mb(layer: Any) -> float | None:
    attrs = getattr(layer, "attrs", {}) or {}
    source_path = attrs.get("source_path")
    if not source_path:
        return None
    try:
        resolved = Path(str(source_path)).resolve()
        if resolved.is_file():
            return resolved.stat().st_size / (1024 * 1024)
    except Exception:
        return None
    return None


def _geometry_vertex_count(geometry: Any) -> int:
    if geometry is None:
        return 0
    if hasattr(geometry, "coords"):
        try:
            return len(list(geometry.coords))
        except Exception:
            return 0
    total = 0
    try:
        exterior = getattr(geometry, "exterior", None)
        if exterior is not None and hasattr(exterior, "coords"):
            total += len(list(exterior.coords))
        interiors = getattr(geometry, "interiors", None)
        if interiors is not None:
            for ring in interiors:
                if hasattr(ring, "coords"):
                    total += len(list(ring.coords))
        geoms = getattr(geometry, "geoms", None)
        if geoms is not None:
            for part in geoms:
                total += _geometry_vertex_count(part)
    except Exception:
        return total
    return total


def _estimate_total_vertices(layer: Any) -> int | None:
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        return None
    total = 0
    try:
        for geometry in layer["geometry"]:
            total += _geometry_vertex_count(geometry)
    except Exception:
        return None
    return total


def _layer_complexity_metrics(layer: Any) -> dict[str, int]:
    row_count = len(layer) if hasattr(layer, "__len__") else 0
    total_vertices = _estimate_total_vertices(layer) or 0
    return {"row_count": int(row_count), "total_vertices": int(total_vertices)}


def _layer_geometry_types(layer: Any) -> tuple[str, ...]:
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        return ()
    geometry_types: set[str] = set()
    try:
        for geometry in layer["geometry"]:
            if geometry is None or getattr(geometry, "is_empty", False):
                continue
            geometry_name = getattr(geometry, "geom_type", None)
            if geometry_name:
                geometry_types.add(str(geometry_name))
    except Exception:
        return ()
    return tuple(sorted(geometry_types))


def _geometry_types_compatible(actual: tuple[str, ...], expected: tuple[str, ...]) -> bool:
    if not expected:
        return True
    if not actual:
        return True
    return bool(set(actual) & set(expected))


def _coverage_row(
    spec: _ValidatorSpec,
    status: str,
    *,
    reason: str | None,
    layer_geometry_types: tuple[str, ...],
    profile: ValidationProfile | None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "validator_name": spec.name,
        "status": status,
        "reason": reason,
        "layer_geometry_type": ", ".join(layer_geometry_types) if layer_geometry_types else "unknown",
        "expected_geometry_types": list(spec.expected_geometry_types),
        "profile": profile.name if profile is not None else None,
        "notes": notes,
    }


def _context_signature(context: dict[str, Any]) -> dict[str, Any]:
    reference_layer = context.get("reference_layer")
    return {
        "expected_crs": _json_safe(context.get("expected_crs")),
        "metadata_keys": sorted((context.get("metadata") or {}).keys()),
        "required_fields": _json_safe(context.get("required_fields") or []),
        "unique_field": _json_safe(context.get("unique_field")),
        "role_field": _json_safe(context.get("role_field")),
        "allowed_endpoint_values": _json_safe(sorted(context.get("allowed_endpoint_values") or [])),
        "domain_field": _json_safe(context.get("domain_field")),
        "valid_domain": _json_safe(context.get("valid_domain")),
        "diameter_field": _json_safe(context.get("diameter_field")),
        "diameter_domain": _json_safe(context.get("diameter_domain")),
        "material_field": _json_safe(context.get("material_field")),
        "material_domain": _json_safe(context.get("material_domain")),
        "status_field": _json_safe(context.get("status_field")),
        "status_domain": _json_safe(context.get("status_domain")),
        "min_length": _json_safe(context.get("min_length")),
        "min_angle_degrees": _json_safe(context.get("min_angle_degrees")),
        "snap_tolerance": _json_safe(context.get("snap_tolerance")),
        "near_miss_tolerance": _json_safe(context.get("near_miss_tolerance")),
        "allowed_terminal_values": _json_safe(sorted(context.get("allowed_terminal_values") or [])),
        "has_reference_layer": reference_layer is not None,
        "reference_layer": _layer_signature(reference_layer) if reference_layer is not None else None,
        "geojson_input": _json_safe(context.get("geojson_input")),
    }


def _enforce_validation_limits(
    layer: Any,
    dataset_type: str,
    limits: ValidationLimits | None,
    *,
    label: str,
) -> None:
    if limits is None:
        return
    row_count = len(layer) if hasattr(layer, "__len__") else None
    column_count = len(getattr(layer, "columns", []))
    source_size_mb = _source_size_mb(layer)
    total_vertices = _estimate_total_vertices(layer)

    if limits.max_features is not None and row_count is not None and row_count > limits.max_features:
        raise ValueError(
            f"{label} for {dataset_type!r} has {row_count} features, above the configured limit of "
            f"{limits.max_features}. Use chunking, profile narrowing, or raise ValidationLimits.max_features."
        )
    if limits.max_columns is not None and column_count > limits.max_columns:
        raise ValueError(
            f"{label} for {dataset_type!r} has {column_count} columns, above the configured limit of "
            f"{limits.max_columns}. Trim the schema or raise ValidationLimits.max_columns."
        )
    if limits.max_source_size_mb is not None and source_size_mb is not None and source_size_mb > limits.max_source_size_mb:
        raise ValueError(
            f"{label} source file is {source_size_mb:.2f} MB, above the configured limit of "
            f"{limits.max_source_size_mb:.2f} MB. Use a smaller extract, chunked workflow, or raise "
            "ValidationLimits.max_source_size_mb."
        )
    if limits.max_total_vertices is not None and total_vertices is not None and total_vertices > limits.max_total_vertices:
        raise ValueError(
            f"{label} for {dataset_type!r} has an estimated {total_vertices} geometry vertices, above the configured "
            f"limit of {limits.max_total_vertices}. Use chunking, simplify the dataset, or raise "
            "ValidationLimits.max_total_vertices."
        )


def build_validation_cache_key(
    layer: Any,
    dataset_type: str,
    validator_name: str,
    *,
    context: dict[str, Any],
    profile: ValidationProfile | None = None,
    cache_tag: str | None = None,
) -> str:
    payload = {
        "dataset_type": dataset_type,
        "validator_name": validator_name,
        "layer": _layer_signature(layer),
        "context": _context_signature(context),
        "profile": {
            "name": profile.name,
            "dataset_type": profile.dataset_type,
            "enabled_validators": list(profile.enabled_validators),
            "disabled_validators": list(profile.disabled_validators),
            "validator_options": _json_safe(profile.validator_options),
        }
        if profile
        else None,
        "cache_tag": cache_tag,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _run_null_geometry(layer: Any, **_: Any) -> list[ValidationIssue]:
    return null_geometry(layer)


def _run_duplicate_vertex(layer: Any, **_: Any) -> list[ValidationIssue]:
    return duplicate_vertex(layer)


def _run_below_minimum_feature_length(layer: Any, *, min_length: float = 0.0, **_: Any) -> list[ValidationIssue]:
    return below_minimum_feature_length(layer, min_length=min_length)


def _run_sharp_angle_cutback(layer: Any, *, min_angle_degrees: float = 15.0, **_: Any) -> list[ValidationIssue]:
    return sharp_angle_cutback(layer, min_angle_degrees=min_angle_degrees)


def _run_self_intersection(layer: Any, **_: Any) -> list[ValidationIssue]:
    try:
        return self_intersection(layer)
    except (RuntimeError, TypeError, AttributeError):
        return []


def _run_required_nulls(layer: Any, *, required_fields: list[str] | None = None, **_: Any) -> list[ValidationIssue]:
    return required_nulls(layer, required_fields or [])


def _run_uniqueness(layer: Any, *, unique_field: str | None = None, **_: Any) -> list[ValidationIssue]:
    if not unique_field:
        return []
    return uniqueness(layer, unique_field)


def _run_domain_range_checks(
    layer: Any,
    *,
    domain_field: str | None = None,
    valid_domain: Any = None,
    **_: Any,
) -> list[ValidationIssue]:
    if not domain_field or valid_domain is None:
        return []
    return domain_range_checks(layer, domain_field, valid_domain)


def _run_diameter_domain(
    layer: Any,
    *,
    diameter_field: str | None = None,
    diameter_domain: Any = None,
    **_: Any,
) -> list[ValidationIssue]:
    if not diameter_field or diameter_domain is None:
        return []
    return domain_range_checks(layer, diameter_field, diameter_domain)


def _run_material_domain(
    layer: Any,
    *,
    material_field: str | None = None,
    material_domain: Any = None,
    **_: Any,
) -> list[ValidationIssue]:
    if not material_field or material_domain is None:
        return []
    return domain_range_checks(layer, material_field, material_domain)


def _run_status_domain(
    layer: Any,
    *,
    status_field: str | None = None,
    status_domain: Any = None,
    **_: Any,
) -> list[ValidationIssue]:
    if not status_field or status_domain is None:
        return []
    return domain_range_checks(layer, status_field, status_domain)


def _run_missing_crs(layer: Any, **_: Any) -> list[ValidationIssue]:
    return missing_crs(layer)


def _run_invalid_crs(layer: Any, *, expected_crs: Any = None, **_: Any) -> list[ValidationIssue]:
    return invalid_crs(layer, expected_crs)


def _run_missing_metadata_fields(layer: Any, *, metadata: dict[str, Any] | None = None, **_: Any) -> list[ValidationIssue]:
    return missing_metadata_fields(metadata or {})


def _run_incomplete_metadata(layer: Any, *, metadata: dict[str, Any] | None = None, **_: Any) -> list[ValidationIssue]:
    return incomplete_metadata(metadata or {})


def _run_coordinate_precision(
    layer: Any,
    *,
    max_decimal_places: int = 9,
    **_: Any,
) -> list[ValidationIssue]:
    return coordinate_precision(layer, max_decimal_places=max_decimal_places)


def _run_xy_tolerance(
    layer: Any,
    *,
    max_tolerance: float | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    return xy_tolerance(layer, max_tolerance=max_tolerance)


def _run_positional_accuracy(
    layer: Any,
    *,
    reference_layer: Any | None = None,
    tolerance: float = 10.0,
    **_: Any,
) -> list[ValidationIssue]:
    if reference_layer is None:
        return []
    return positional_accuracy(layer, reference_layer, tolerance=tolerance)


def _run_missing_spatial_index(layer: Any, **_: Any) -> list[ValidationIssue]:
    return missing_spatial_index(layer)


def _run_outdated_index(layer: Any, **_: Any) -> list[ValidationIssue]:
    return outdated_index(layer)


def _run_non_rfc7946_geojson(layer: Any, *, geojson_input: Any | None = None, **_: Any) -> list[ValidationIssue]:
    if geojson_input is None:
        return []
    return non_rfc7946_geojson(geojson_input)


def _run_polygon_overlap_same_layer(layer: Any, **_: Any) -> list[ValidationIssue]:
    return polygon_overlap_same_layer(layer)


def _run_feature_within_feature(layer: Any, **_: Any) -> list[ValidationIssue]:
    return feature_within_feature(layer)


def _run_line_intersection_same_layer(layer: Any, **_: Any) -> list[ValidationIssue]:
    return line_intersection_same_layer(layer)


def _run_line_dangle(
    layer: Any,
    *,
    role_field: str | None = None,
    allowed_endpoint_values: set[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    return line_dangle(layer, role_field=role_field, allowed_endpoint_values=allowed_endpoint_values)


def _run_duplicate_geometry_same_layer(layer: Any, **_: Any) -> list[ValidationIssue]:
    return duplicate_geometry_same_layer(layer)


def _run_feature_not_split_at_intersection(layer: Any, **_: Any) -> list[ValidationIssue]:
    return feature_not_split_at_intersection(layer)


def _run_isolated_network_segment(
    layer: Any,
    *,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    return isolated_network_segment(layer, role_field=role_field, allowed_terminal_values=allowed_terminal_values)


def _run_suspicious_near_miss_endpoints(
    layer: Any,
    *,
    snap_tolerance: float = 0.0,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    resolved_tolerance = 0.0 if snap_tolerance is None else snap_tolerance
    return suspicious_near_miss_endpoints(
        layer,
        snap_tolerance=resolved_tolerance,
        role_field=role_field,
        allowed_terminal_values=allowed_terminal_values,
    )


def _run_unsnapped_endpoints_within_tolerance(
    layer: Any,
    *,
    snap_tolerance: float = 0.0,
    role_field: str | None = None,
    allowed_terminal_values: set[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    resolved_tolerance = 0.0 if snap_tolerance is None else snap_tolerance
    return unsnapped_endpoints_within_tolerance(
        layer,
        snap_tolerance=resolved_tolerance,
        role_field=role_field,
        allowed_terminal_values=allowed_terminal_values,
    )


def _run_polygon_gap_same_layer(layer: Any, *, min_gap_area: float = 0.0, **_: Any) -> list[ValidationIssue]:
    return polygon_gap_same_layer(layer, min_gap_area=min_gap_area)


def _run_boundary_mismatch_against_reference(
    layer: Any,
    *,
    reference_layer: Any | None = None,
    mismatch_ratio_threshold: float = 0.02,
    **_: Any,
) -> list[ValidationIssue]:
    if reference_layer is None:
        return []
    return boundary_mismatch_against_reference(
        layer,
        reference_layer,
        mismatch_ratio_threshold=mismatch_ratio_threshold,
    )


def _run_spectral_indices(
    layer: Any,
    *,
    ndvi_col: str = "ndvi",
    ndwi_col: str = "ndwi",
    ndmi_col: str = "ndmi",
    feature_id_col: str | None = None,
    date_col: str | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for the spectral index validator.

    ``feature_id_col`` is the fix for the temporal comparison. The original
    implementation compared row i against row i-1 of the whole table. For a
    table holding one row per observation per location, that compares two
    DIFFERENT locations and reports the difference between them as temporal
    change. With ``feature_id_col`` supplied, the comparison is keyed to the
    same location across dates. Without it the behaviour degrades to the
    original sequential-row comparison, which is only meaningful if the caller
    has already sorted the table so consecutive rows are the same location.
    """
    from .validations.spectral import validate_spectral_indices

    return validate_spectral_indices(
        layer,
        ndvi_col=ndvi_col,
        ndwi_col=ndwi_col,
        ndmi_col=ndmi_col,
        date_col=date_col,
        feature_id_col=feature_id_col,
    )


def _run_band_radiance(
    layer: Any,
    *,
    band_cols: list[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    from .validations.spectral import validate_band_radiance

    return validate_band_radiance(layer, band_cols=band_cols)


def _run_payload_columns(
    layer: Any,
    *,
    columns: list[str] | None = None,
    require_structured: bool = True,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for structured payloads held in scalar text columns."""
    from .validations.payload_columns import validate_payload_columns

    return validate_payload_columns(
        layer,
        columns=columns,
        require_structured=require_structured,
    )


def _run_metric_constants(
    layer: Any,
    *,
    metric_source: str | None = None,
    declarations: dict[str, Any] | None = None,
    skip_scope_boundaries: bool = False,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for undeclared constants in a metric chain.

    ``metric_source`` is the literal formula listing or KPI definition text.
    ``declarations`` maps a constant, as written, to its declared meaning, so a
    declared constant stops being reported. Both are supplied by the caller; the
    layer itself is not consulted, because a formula chain is not a geometry.
    """
    from .validations.metric_constants import ConstantDeclaration, validate_metric_constants

    parsed = None
    if declarations:
        parsed = [
            ConstantDeclaration(
                constant=str(key),
                meaning=str(entry.get("meaning", "")) if isinstance(entry, dict) else str(entry),
                unit=entry.get("unit") if isinstance(entry, dict) else None,
                source=entry.get("source") if isinstance(entry, dict) else None,
                verified=bool(entry.get("verified", False)) if isinstance(entry, dict) else False,
            )
            for key, entry in declarations.items()
        ]

    return validate_metric_constants(
        source=metric_source,
        declarations=parsed or (),
        skip_scope_boundaries=skip_scope_boundaries,
    )


def _run_epanet_input(
    layer: Any,
    *,
    inp_path: str | None = None,
    inp_text: str | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for EPANET ``.inp`` decks.

    Accepts either a path or literal deck text. A deck is not a GeoDataFrame,
    so ``layer`` is accepted only for signature compatibility and is ignored.
    """
    from pathlib import Path as _Path

    from .validations.epanet import parse_inp, validate_inp

    if inp_text is None:
        if inp_path is None:
            return []
        inp_text = _Path(inp_path)
    return validate_inp(parse_inp(inp_text, source_name=getattr(inp_text, "name", None)))


def _run_water_balance(
    layer: Any,
    *,
    balance_inputs: Mapping[str, Any] | None = None,
    days_in_period: float | None = None,
    uarl: float | None = None,
    cawl: float | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for the IWA water balance.

    ``balance_inputs`` is a mapping of component name to volume in m3, matching
    :class:`WaterBalanceInputs`. ``layer`` is accepted for signature
    compatibility and ignored: a water balance is arithmetic on stated volumes,
    not a geometry check.
    """
    from .validations.water_balance import WaterBalanceInputs, compute_water_balance, validate_water_balance

    if not balance_inputs:
        return []

    inputs = WaterBalanceInputs(**dict(balance_inputs))
    result = compute_water_balance(
        inputs, days_in_period=days_in_period, uarl=uarl, cawl=cawl
    )
    return validate_water_balance(inputs, result)


def _run_crs_units(
    layer: Any,
    *,
    length_columns: list[str] | None = None,
    recommend: bool = True,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for CRS assessment and length-unit reasoning."""
    from .validations.crs_units import validate_crs_consistency

    return validate_crs_consistency(
        layer, length_columns=length_columns, recommend=recommend
    )


def _run_raster(
    layer: Any,
    *,
    raster_path: str | None = None,
    needed_bands: list[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for raster band, scaling and CRS checks.

    ``layer`` is ignored: a raster is not a GeoDataFrame. ``raster_path`` is the
    file to inspect.
    """
    from .validations.raster import validate_raster

    if not raster_path:
        return []
    return validate_raster(raster_path, needed_bands=tuple(needed_bands or ("blue", "green", "red", "nir")))


def _run_water_loss(
    layer: Any,
    *,
    assessment: Any = None,
    uarl_inputs: Any = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for UARL and ILI assessment.

    ``layer`` is ignored: the assessment is computed from network totals rather
    than from features. ``assessment`` is a
    :class:`~geoqa.validations.water_loss.WaterLossAssessment`.
    """
    from .validations.water_loss import validate_water_loss

    if assessment is None:
        return []
    return validate_water_loss(assessment, uarl_inputs=uarl_inputs)


def _run_repeat_incident(
    layer: Any,
    *,
    period_column: str | None = None,
    key_column: str | None = None,
    location_tolerance_m: float | None = None,
    overlap_fraction: float | None = None,
    expected_periods: list[str] | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for cross-period recurrence.

    Unlike the raster adapter this one does read ``layer``: recurrence is
    assembled from accumulated survey periods held as features.
    """
    from .validations.repeat_incident import validate_repeats

    if not period_column:
        return []
    kwargs: dict[str, Any] = {"period_column": period_column}
    if key_column is not None:
        kwargs["key_column"] = key_column
    if location_tolerance_m is not None:
        kwargs["location_tolerance_m"] = location_tolerance_m
    if overlap_fraction is not None:
        kwargs["overlap_fraction"] = overlap_fraction
    if expected_periods is not None:
        kwargs["expected_periods"] = expected_periods
    return validate_repeats(layer, **kwargs)


def _run_archive(
    layer: Any,
    *,
    archive_path: str | None = None,
    check_content: bool = True,
    require_crs_sidecar: bool = False,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for archive inspection before extraction.

    ``layer`` is ignored: an archive is not a GeoDataFrame. Nothing is written,
    so this is safe to run over a directory of downloads unattended.
    """
    from .validations.archive import validate_archive

    if not archive_path:
        return []
    return validate_archive(
        archive_path,
        check_content=check_content,
        require_crs_sidecar=require_crs_sidecar,
    )


def _run_tabular(
    layer: Any,
    *,
    table_path: str | None = None,
    sheet: str | None = None,
    expected_columns: list[str] | None = None,
    key_column: str | None = None,
    require_key: bool = False,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for CSV and Excel structure.

    Falls back to ``layer`` being a path when ``table_path`` is not supplied, so
    a caller holding a file path alone still gets the check.
    """
    from .validations.tabular import validate_tabular

    target = table_path or (layer if isinstance(layer, (str, Path)) else None)
    if not target:
        return []
    return validate_tabular(
        target,
        sheet=sheet,
        expected_columns=expected_columns,
        key_column=key_column,
        require_key=require_key,
    )


def _run_workbook_media(
    layer: Any,
    *,
    table_path: str | None = None,
    sheet: str | None = None,
    key_column: str | None = None,
    expect_attachment_every_row: bool = False,
    reference_root: str | Path | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for embedded and referenced attachments in a workbook."""
    from .validations.workbook_media import validate_workbook_media

    target = table_path or (layer if isinstance(layer, (str, Path)) else None)
    if not target:
        return []
    return validate_workbook_media(
        target,
        sheet=sheet,
        key_column=key_column,
        expect_attachment_every_row=expect_attachment_every_row,
        reference_root=reference_root,
    )


def _run_geopackage(
    layer: Any,
    *,
    geopackage_path: str | None = None,
    require_spatial_index: bool = False,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for GeoPackage structural conformance."""
    from .gpkg import validate_gpkg

    target = geopackage_path or (layer if isinstance(layer, (str, Path)) else None)
    if not target:
        return []
    return validate_gpkg(target, require_spatial_index=require_spatial_index)


def _run_governance(
    layer: Any,
    *,
    metadata: dict[str, Any] | None = None,
    required_elements: list[str] | None = None,
    require_open_licence: bool = False,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for metadata governance.

    ``layer`` is ignored: governance attaches to a record, not to features.
    """
    from .validations.governance import validate_governance_metadata

    record = metadata if metadata is not None else (
        layer if isinstance(layer, Mapping) else None
    )
    if record is None:
        return []
    return validate_governance_metadata(
        record,
        required_elements=required_elements,
        require_open_licence=require_open_licence,
    )


def _run_axis_order(
    layer: Any,
    *,
    coordinates: dict[str, Any] | None = None,
    declared_crs: str | None = None,
    declared_format: str | None = None,
    expected_extent: tuple[float, float, float, float] | None = None,
    first_column: str | None = None,
    second_column: str | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for coordinate axis order.

    ``coordinates`` is a mapping of column name to values. When it is absent,
    a ``layer`` that behaves like a dataframe is used instead.
    """
    from .validations.axis_order import validate_axis_order, _declared_from_columns

    frame = coordinates
    if frame is None:
        # Only fall back to ``layer`` when it actually looks like a coordinate
        # table. Running this over an arbitrary layer would manufacture an
        # "undeclared" finding for every dataset that has no x/y columns.
        candidate = layer if hasattr(layer, "columns") and hasattr(layer, "keys") else None
        if candidate is not None and _declared_from_columns(list(candidate.columns)) is not None:
            frame = candidate
    if frame is None:
        return []
    return validate_axis_order(
        frame,
        declared_crs=declared_crs,
        declared_format=declared_format,
        expected_extent=expected_extent,
        first_column=first_column,
        second_column=second_column,
    )


def _run_credentials(
    layer: Any,
    *,
    scan_path: str | None = None,
    min_entropy: float = 3.0,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for hardcoded credential detection over a file or directory."""
    from .validations.credentials import validate_credentials

    target = scan_path or (layer if isinstance(layer, (str, Path)) else None)
    if not target:
        return []
    return validate_credentials(target, min_entropy=min_entropy)


def _run_clip(
    layer: Any,
    *,
    clipped_layer: Any = None,
    source_layer: Any = None,
    boundary: Any = None,
    assignment_threshold: float | None = None,
    half_fraction: float | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for clip assignment and clip completeness.

    Two independent checks sharing one dataset type, because both answer
    "is this clipped layer what I think it is". The boundary check runs when a
    boundary is supplied; the completeness check runs when a source layer is.
    """
    from .validations.clip import validate_clip_assignment, validate_clip_completeness

    issues: list[ValidationIssue] = []
    clipped = clipped_layer if clipped_layer is not None else layer

    if clipped is not None and boundary is not None:
        issues.extend(
            validate_clip_assignment(clipped, boundary, assignment_threshold=assignment_threshold)
        )

    if clipped is not None and source_layer is not None:
        kwargs: dict[str, Any] = {}
        if half_fraction is not None:
            kwargs["half_fraction"] = half_fraction
        issues.extend(validate_clip_completeness(clipped, source_layer, **kwargs))

    return issues


def _run_hyperspectral(
    layer: Any,
    *,
    hyperspectral_path: str | None = None,
    dataset_path: str | None = None,
    expected_product_level: str | None = None,
    require_quality_layers: bool = True,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for HDF5 hyperspectral products.

    ``layer`` is ignored. Only attributes and shapes are read, so this is safe
    on a multi-gigabyte granule.
    """
    from .validations.hyperspectral import validate_hyperspectral

    target = hyperspectral_path or (layer if isinstance(layer, (str, Path)) else None)
    if not target:
        return []
    return validate_hyperspectral(
        target,
        dataset_path=dataset_path,
        expected_product_level=expected_product_level,
        require_quality_layers=require_quality_layers,
    )


def _run_coefficient_reference(layer: Any, **_: Any) -> list[ValidationIssue]:
    """Adapter for the published reference cases.

    Takes no input and consults no layer. It exists as a dataset type so a run
    can include it deliberately, because a formula that cannot reproduce its own
    source figure is a reason to stop rather than a footnote.
    """
    from .validations.reference_cases import validate_reference_cases

    return validate_reference_cases()


def _run_uarl_applicability(
    layer: Any,
    *,
    service_connections: float | None = None,
    mains_length_km: float | None = None,
    average_pressure_m: float | None = None,
    **_: Any,
) -> list[ValidationIssue]:
    """Adapter for the UARL equation's stated applicability limits."""
    from .validations.reference_cases import validate_uarl_applicability

    if None in (service_connections, mains_length_km, average_pressure_m):
        return []
    return validate_uarl_applicability(
        service_connections=float(service_connections),
        mains_length_km=float(mains_length_km),
        average_pressure_m=float(average_pressure_m),
    )


def _optional_context(context: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Copy context keys only when a usable value is supplied.

    Validators whose options are absent (e.g. a profile enabling them without options)
    then run at their declared defaults instead of receiving an explicit None.
    """
    return {key: context[key] for key in keys if context.get(key) is not None}


def _builtin_specs(dataset_type: str, context: dict[str, Any]) -> list[_ValidatorSpec]:
    metadata = context.get("metadata")
    specs_by_type: dict[str, list[_ValidatorSpec]] = {
        "geometry": [
            _ValidatorSpec("null_geometry", _run_null_geometry, {}, base_cost=1),
            _ValidatorSpec("duplicate_vertex", _run_duplicate_vertex, {}, base_cost=2),
            _ValidatorSpec(
                "below_minimum_feature_length",
                _run_below_minimum_feature_length,
                _optional_context(context, "min_length"),
                base_cost=2,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "sharp_angle_cutback",
                _run_sharp_angle_cutback,
                _optional_context(context, "min_angle_degrees"),
                base_cost=3,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "self_intersection",
                _run_self_intersection,
                {},
                base_cost=4,
                expected_geometry_types=("LineString", "MultiLineString", "Polygon", "MultiPolygon"),
            ),
        ],
        "attributes": [
            _ValidatorSpec("required_nulls", _run_required_nulls, {"required_fields": context.get("required_fields")}, base_cost=1),
            _ValidatorSpec("uniqueness", _run_uniqueness, {"unique_field": context.get("unique_field")}, base_cost=2),
            _ValidatorSpec(
                "domain_range_checks",
                _run_domain_range_checks,
                {
                    "domain_field": context.get("domain_field"),
                    "valid_domain": context.get("valid_domain"),
                },
                base_cost=2,
            ),
            _ValidatorSpec(
                "diameter_domain",
                _run_diameter_domain,
                {"diameter_field": context.get("diameter_field"), "diameter_domain": context.get("diameter_domain")},
                base_cost=2,
            ),
            _ValidatorSpec(
                "material_domain",
                _run_material_domain,
                {"material_field": context.get("material_field"), "material_domain": context.get("material_domain")},
                base_cost=2,
            ),
            _ValidatorSpec(
                "status_domain",
                _run_status_domain,
                {"status_field": context.get("status_field"), "status_domain": context.get("status_domain")},
                base_cost=2,
            ),
        ],
        "crs": [
            _ValidatorSpec("missing_crs", _run_missing_crs, {}, base_cost=1),
            _ValidatorSpec("invalid_crs", _run_invalid_crs, {"expected_crs": context.get("expected_crs")}, base_cost=1),
            # CRS and unit advice sits with the conformance checks rather than
            # beside them: ``invalid_crs`` decides conformance, ``crs_units``
            # reads length columns and recommends a reprojection.
            _ValidatorSpec(
                "crs_units",
                _run_crs_units,
                {
                    "length_columns": context.get("length_columns"),
                    "recommend": context.get("recommend_crs", True),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        "metadata": [
            _ValidatorSpec("missing_metadata_fields", _run_missing_metadata_fields, {"metadata": metadata}, base_cost=1),
            _ValidatorSpec("incomplete_metadata", _run_incomplete_metadata, {"metadata": metadata}, base_cost=1),
        ],
        "accuracy": [
            _ValidatorSpec("coordinate_precision", _run_coordinate_precision, {}, base_cost=3),
            _ValidatorSpec("xy_tolerance", _run_xy_tolerance, {}, base_cost=1),
            _ValidatorSpec("positional_accuracy", _run_positional_accuracy, {"reference_layer": context.get("reference_layer")}, base_cost=8),
        ],
        "integrity": [
            _ValidatorSpec("missing_spatial_index", _run_missing_spatial_index, {}, base_cost=1),
            _ValidatorSpec("outdated_index", _run_outdated_index, {}, base_cost=1),
            _ValidatorSpec("non_rfc7946_geojson", _run_non_rfc7946_geojson, {"geojson_input": context.get("geojson_input")}, base_cost=1),
        ],
        "topology": [
            _ValidatorSpec(
                "polygon_overlap_same_layer",
                _run_polygon_overlap_same_layer,
                {},
                base_cost=8,
                expected_geometry_types=("Polygon", "MultiPolygon"),
            ),
            _ValidatorSpec(
                "polygon_gap_same_layer",
                _run_polygon_gap_same_layer,
                {},
                base_cost=9,
                expected_geometry_types=("Polygon", "MultiPolygon"),
            ),
            _ValidatorSpec(
                "feature_within_feature",
                _run_feature_within_feature,
                {},
                base_cost=7,
                expected_geometry_types=("Polygon", "MultiPolygon"),
            ),
            _ValidatorSpec(
                "line_intersection_same_layer",
                _run_line_intersection_same_layer,
                {},
                base_cost=7,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "line_dangle",
                _run_line_dangle,
                {
                    "role_field": context.get("role_field"),
                    "allowed_endpoint_values": context.get("allowed_endpoint_values"),
                },
                base_cost=3,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec("duplicate_geometry_same_layer", _run_duplicate_geometry_same_layer, {}, base_cost=4),
            _ValidatorSpec(
                "feature_not_split_at_intersection",
                _run_feature_not_split_at_intersection,
                {},
                base_cost=7,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "isolated_network_segment",
                _run_isolated_network_segment,
                {"role_field": context.get("role_field"), "allowed_terminal_values": context.get("allowed_terminal_values")},
                base_cost=3,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "suspicious_near_miss_endpoints",
                _run_suspicious_near_miss_endpoints,
                {
                    "snap_tolerance": context.get("near_miss_tolerance", context.get("snap_tolerance")),
                    "role_field": context.get("role_field"),
                    "allowed_terminal_values": context.get("allowed_terminal_values"),
                },
                base_cost=5,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "unsnapped_endpoints_within_tolerance",
                _run_unsnapped_endpoints_within_tolerance,
                {
                    "snap_tolerance": context.get("snap_tolerance"),
                    "role_field": context.get("role_field"),
                    "allowed_terminal_values": context.get("allowed_terminal_values"),
                },
                base_cost=5,
                expected_geometry_types=("LineString", "MultiLineString"),
            ),
            _ValidatorSpec(
                "boundary_mismatch_against_reference",
                _run_boundary_mismatch_against_reference,
                {"reference_layer": context.get("reference_layer")},
                base_cost=8,
                expected_geometry_types=("Polygon", "MultiPolygon"),
            ),
        ],
        # Spectral validation operates on a table of per-observation band or
        # index values, not on geometry. It is registered as its own dataset
        # type so the validators in geoqa/validations/spectral.py are reachable
        # through validate_layer() and any profile, rather than only by direct
        # import. See _run_spectral_indices / _run_band_radiance above, which
        # absorb the surrounding context the way the other runners do.
        "spectral": [
            _ValidatorSpec(
                "spectral_indices",
                _run_spectral_indices,
                {
                    "ndvi_col": context.get("ndvi_col", "ndvi"),
                    "ndwi_col": context.get("ndwi_col", "ndwi"),
                    "ndmi_col": context.get("ndmi_col", "ndmi"),
                    "feature_id_col": context.get("feature_id_col"),
                    "date_col": context.get("date_col"),
                },
                base_cost=2,
                # Spectral validators inspect values, not geometry. An empty
                # tuple, not None: _coverage_row calls list() on this field.
                expected_geometry_types=(),
            ),
            _ValidatorSpec(
                "band_radiance",
                _run_band_radiance,
                {"band_cols": context.get("band_cols")},
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
        # Schema and governance conditions. These do not inspect geometry either:
        # one reads attribute cell contents, the other reads a metric definition.
        # They are registered as their own dataset types so they are reachable
        # through validate_layer() and any profile rather than only by import.
        "schema": [
            _ValidatorSpec(
                "payload_columns",
                _run_payload_columns,
                {
                    "columns": context.get("payload_columns"),
                    "require_structured": context.get("require_structured", True),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        "governance": [
            _ValidatorSpec(
                "metric_constants",
                _run_metric_constants,
                {
                    "metric_source": context.get("metric_source"),
                    "declarations": context.get("constant_declarations"),
                    "skip_scope_boundaries": context.get("skip_scope_boundaries", False),
                },
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
        "epanet": [
            _ValidatorSpec(
                "epanet_input",
                _run_epanet_input,
                {
                    "inp_path": context.get("inp_path"),
                    "inp_text": context.get("inp_text"),
                },
                base_cost=3,
                expected_geometry_types=(),
            ),
        ],
        "water_balance": [
            _ValidatorSpec(
                "water_balance",
                _run_water_balance,
                {
                    "balance_inputs": context.get("balance_inputs"),
                    "days_in_period": context.get("days_in_period"),
                    "uarl": context.get("uarl"),
                    "cawl": context.get("cawl"),
                },
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
        "raster": [
            _ValidatorSpec(
                "raster_bands",
                _run_raster,
                {
                    "raster_path": context.get("raster_path"),
                    "needed_bands": context.get("needed_bands"),
                },
                base_cost=3,
                expected_geometry_types=(),
            ),
        ],
        "water_loss": [
            _ValidatorSpec(
                "water_loss_indicator",
                _run_water_loss,
                {
                    "assessment": context.get("assessment"),
                    "uarl_inputs": context.get("uarl_inputs"),
                },
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
        "repeat_incident": [
            _ValidatorSpec(
                "repeat_incident",
                _run_repeat_incident,
                {
                    "period_column": context.get("period_column"),
                    "key_column": context.get("key_column"),
                    "location_tolerance_m": context.get("location_tolerance_m"),
                    "overlap_fraction": context.get("overlap_fraction"),
                    "expected_periods": context.get("expected_periods"),
                },
                base_cost=4,
                expected_geometry_types=("Point", "MultiPoint"),
            ),
        ],
        "archive": [
            _ValidatorSpec(
                "archive_safety",
                _run_archive,
                {
                    "archive_path": context.get("archive_path"),
                    "check_content": context.get("check_content", True),
                    "require_crs_sidecar": context.get("require_crs_sidecar", False),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        "tabular": [
            _ValidatorSpec(
                "tabular_structure",
                _run_tabular,
                {
                    "table_path": context.get("table_path"),
                    "sheet": context.get("sheet"),
                    "expected_columns": context.get("expected_columns"),
                    "key_column": context.get("key_column"),
                    "require_key": context.get("require_key", False),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        "workbook_media": [
            _ValidatorSpec(
                "workbook_attachments",
                _run_workbook_media,
                {
                    "table_path": context.get("table_path"),
                    "sheet": context.get("sheet"),
                    "key_column": context.get("key_column"),
                    "expect_attachment_every_row": context.get(
                        "expect_attachment_every_row", False
                    ),
                    "reference_root": context.get("reference_root"),
                },
                base_cost=3,
                expected_geometry_types=(),
            ),
        ],
        "geopackage": [
            _ValidatorSpec(
                "geopackage_structure",
                _run_geopackage,
                {
                    "geopackage_path": context.get("geopackage_path"),
                    "require_spatial_index": context.get("require_spatial_index", False),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        # Named distinctly from "governance", which holds the undeclared-constant
        # checks on a metric chain. This one assesses a dataset's metadata record.
        "metadata_governance": [
            _ValidatorSpec(
                "governance_metadata",
                _run_governance,
                {
                    "metadata": context.get("metadata"),
                    "required_elements": context.get("required_elements"),
                    "require_open_licence": context.get("require_open_licence", False),
                },
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
        "axis_order": [
            _ValidatorSpec(
                "coordinate_axis_order",
                _run_axis_order,
                {
                    "coordinates": context.get("coordinates"),
                    "declared_crs": context.get("declared_crs"),
                    "declared_format": context.get("declared_format"),
                    "expected_extent": context.get("expected_extent"),
                    "first_column": context.get("first_column"),
                    "second_column": context.get("second_column"),
                },
                base_cost=2,
                expected_geometry_types=(),
            ),
        ],
        "credentials": [
            _ValidatorSpec(
                "hardcoded_credential",
                _run_credentials,
                {
                    "scan_path": context.get("scan_path"),
                    "min_entropy": context.get("min_entropy", 3.0),
                },
                base_cost=3,
                expected_geometry_types=(),
            ),
        ],
        "clip": [
            _ValidatorSpec(
                "clip_conformance",
                _run_clip,
                {
                    "clipped_layer": context.get("clipped_layer"),
                    "source_layer": context.get("source_layer"),
                    "boundary": context.get("boundary"),
                    "assignment_threshold": context.get("assignment_threshold"),
                    "half_fraction": context.get("half_fraction"),
                },
                base_cost=6,
                expected_geometry_types=("Polygon", "MultiPolygon"),
            ),
        ],
        # HDF5 is registered separately from "raster" because the two are not
        # interchangeable: an HDF-EOS cube is (bands, rows, columns) with
        # wavelengths in an attribute, which the GeoTIFF reader cannot express.
        "hyperspectral": [
            _ValidatorSpec(
                "hyperspectral_structure",
                _run_hyperspectral,
                {
                    "hyperspectral_path": context.get("hyperspectral_path"),
                    "dataset_path": context.get("dataset_path"),
                    "expected_product_level": context.get("expected_product_level"),
                    "require_quality_layers": context.get("require_quality_layers", True),
                },
                base_cost=3,
                expected_geometry_types=(),
            ),
        ],
        "coefficient_reference": [
            _ValidatorSpec(
                "coefficient_reference_case",
                _run_coefficient_reference,
                {},
                base_cost=1,
                expected_geometry_types=(),
            ),
            _ValidatorSpec(
                "uarl_applicability",
                _run_uarl_applicability,
                {
                    "service_connections": context.get("service_connections"),
                    "mains_length_km": context.get("mains_length_km"),
                    "average_pressure_m": context.get("average_pressure_m"),
                },
                base_cost=1,
                expected_geometry_types=(),
            ),
        ],
    }
    try:
        return specs_by_type[dataset_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported dataset type: {dataset_type!r}") from exc


def _custom_specs(dataset_type: str, context: dict[str, Any]) -> list[_ValidatorSpec]:
    items: list[_ValidatorSpec] = []
    for scope in (dataset_type, "*"):
        for name, func in _CUSTOM_VALIDATORS.get(scope, {}).items():
            items.append(_ValidatorSpec(name, func, dict(context)))
    return items


def _estimated_spec_cost(
    spec: _ValidatorSpec,
    *,
    layer_metrics: dict[str, int],
) -> int:
    row_count = layer_metrics.get("row_count", 0)
    total_vertices = layer_metrics.get("total_vertices", 0)
    row_factor = max(1, row_count // 5000)
    vertex_factor = max(1, total_vertices // 50000) if total_vertices > 0 else 1
    return int(spec.base_cost * max(row_factor, vertex_factor))


def _ordered_specs(
    specs: list[_ValidatorSpec],
    *,
    prefer_high_priority: bool,
    problem_policies: dict[str, dict[str, Any]] | None,
    layer_metrics: dict[str, int],
) -> list[_ValidatorSpec]:
    if not prefer_high_priority:
        return specs
    policies = {name.lower(): dict(policy) for name, policy in (problem_policies or {}).items()}
    confidence_rank = {"high": 3, "medium": 2, "low": 1}

    def key(spec: _ValidatorSpec) -> tuple[int, int, int, str]:
        policy = policies.get(spec.name.lower(), {})
        actionable = 1 if bool(policy.get("actionable", True)) else 0
        priority_score = int(policy.get("priority_score", 0) or 0)
        confidence = confidence_rank.get(str(policy.get("confidence", "medium")).lower(), 2)
        estimated_cost = _estimated_spec_cost(spec, layer_metrics=layer_metrics)
        return (-actionable, -priority_score, estimated_cost, -confidence, spec.name)

    return sorted(specs, key=key)


def _apply_profile(
    specs: list[_ValidatorSpec],
    profile: ValidationProfile | None,
    dataset_type: str,
) -> list[_ValidatorSpec]:
    if profile is None:
        return specs
    if profile.dataset_type and profile.dataset_type != dataset_type:
        raise ValueError(
            f"Validation profile {profile.name!r} targets dataset type {profile.dataset_type!r}, not {dataset_type!r}."
        )
    enabled = {item.lower() for item in profile.enabled_validators}
    disabled = {item.lower() for item in profile.disabled_validators}
    filtered: list[_ValidatorSpec] = []
    for spec in specs:
        normalized_name = spec.name.lower()
        if enabled and normalized_name not in enabled:
            continue
        if normalized_name in disabled:
            continue
        overrides = profile.validator_options.get(spec.name) or profile.validator_options.get(normalized_name) or {}
        filtered.append(
            _ValidatorSpec(
                spec.name,
                spec.func,
                {**spec.context, **overrides},
                base_cost=spec.base_cost,
                expected_geometry_types=spec.expected_geometry_types,
            )
        )
    return filtered


def execute_validation_plan(
    layer: Any,
    dataset_type: str,
    *,
    metadata: dict[str, Any] | None = None,
    expected_crs: Any = None,
    reference_layer: Any | None = None,
    required_fields: list[str] | None = None,
    unique_field: str | None = None,
    role_field: str | None = None,
    allowed_endpoint_values: set[str] | None = None,
    domain_field: str | None = None,
    valid_domain: Any = None,
    geojson_input: Any | None = None,
    profile: str | ValidationProfile | None = None,
    progress_callback: ProgressCallback | None = None,
    cache: InMemoryValidationCache | None = None,
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
) -> list[ValidationIssue] | ValidationPlanResult:
    normalized_dataset_type = dataset_type.strip().lower()
    _enforce_validation_limits(layer, normalized_dataset_type, limits, label="Primary layer")
    if reference_layer is not None:
        _enforce_validation_limits(reference_layer, normalized_dataset_type, limits, label="Reference layer")
    context = {
        "metadata": metadata,
        "expected_crs": expected_crs,
        "reference_layer": reference_layer,
        "required_fields": required_fields,
        "unique_field": unique_field,
        "role_field": role_field,
        "allowed_endpoint_values": allowed_endpoint_values,
        "domain_field": domain_field,
        "valid_domain": valid_domain,
        "geojson_input": geojson_input,
        **extra_context,
    }
    resolved_profile = get_validation_profile(profile)
    layer_metrics = _layer_complexity_metrics(layer)
    layer_geometry_types = _layer_geometry_types(layer)
    specs = _apply_profile(
        _builtin_specs(normalized_dataset_type, context) + _custom_specs(normalized_dataset_type, context),
        resolved_profile,
        normalized_dataset_type,
    )
    specs = _ordered_specs(
        specs,
        prefer_high_priority=prefer_high_priority,
        problem_policies=problem_policies,
        layer_metrics=layer_metrics,
    )

    total = len(specs)
    issues: list[ValidationIssue] = []
    validators_attempted: list[str] = []
    validators_completed: list[str] = []
    validator_coverage: list[dict[str, Any]] = []
    pending_parallel: list[tuple[int, _ValidatorSpec, str | None]] = []
    started_at = time.perf_counter()
    partial_result = False
    stop_reason: str | None = None

    def current_actionable_count() -> int:
        return sum(1 for issue in issues if issue.actionable)

    def should_stop_early() -> str | None:
        if max_runtime_seconds is not None and (time.perf_counter() - started_at) >= max_runtime_seconds:
            return "runtime_limit"
        if max_issues is not None and len(issues) >= max_issues:
            return "max_issues_reached"
        if stop_after_actionable is not None and current_actionable_count() >= stop_after_actionable:
            return "actionable_target_reached"
        return None

    def emit_completed(index: int, spec: _ValidatorSpec, result: list[ValidationIssue], *, cache_hit: bool) -> None:
        if progress_callback is not None:
            elapsed = max(time.perf_counter() - started_at, 0.0001)
            progress_percent = (index / total) * 100 if total else 100.0
            avg_seconds = elapsed / index
            eta_seconds = max((total - index) * avg_seconds, 0.0)
            progress_callback(
                ValidationProgressEvent(
                    dataset_type=normalized_dataset_type,
                    validator_name=spec.name,
                    status="completed",
                    index=index,
                    total=total,
                    issue_count=len(result),
                    cache_hit=cache_hit,
                    progress_percent=progress_percent,
                    eta_seconds=eta_seconds,
                )
            )

    for index, spec in enumerate(specs, start=1):
        if not _geometry_types_compatible(layer_geometry_types, spec.expected_geometry_types):
            validator_coverage.append(
                _coverage_row(
                    spec,
                    "skipped",
                    reason="incompatible_geometry_type",
                    layer_geometry_types=layer_geometry_types,
                    profile=resolved_profile,
                )
            )
            if progress_callback is not None:
                progress_callback(
                    ValidationProgressEvent(
                        dataset_type=normalized_dataset_type,
                        validator_name=spec.name,
                        status="skipped",
                        index=index,
                        total=total,
                        issue_count=0,
                        message="incompatible_geometry_type",
                    )
                )
            continue

        stop_reason = should_stop_early()
        if stop_reason is not None:
            partial_result = True
            break

        validators_attempted.append(spec.name)
        if progress_callback is not None:
            elapsed = max(time.perf_counter() - started_at, 0.0)
            progress_percent = ((index - 1) / total) * 100 if total else 0.0
            eta_seconds = (elapsed / max(index - 1, 1)) * (total - index + 1) if total else 0.0
            progress_callback(
                ValidationProgressEvent(
                    dataset_type=normalized_dataset_type,
                    validator_name=spec.name,
                    status="started",
                    index=index,
                    total=total,
                    progress_percent=progress_percent,
                    eta_seconds=eta_seconds,
                )
            )

        cache_key = None
        cached_result = None
        if cache is not None:
            cache_key = build_validation_cache_key(
                layer,
                normalized_dataset_type,
                spec.name,
                context=spec.context,
                profile=resolved_profile,
                cache_tag=cache_tag,
            )
            cached_result = cache.get(cache_key)

        if cached_result is not None:
            issues.extend(cached_result)
            validators_completed.append(spec.name)
            validator_coverage.append(
                _coverage_row(
                    spec,
                    "completed",
                    reason=None,
                    layer_geometry_types=layer_geometry_types,
                    profile=resolved_profile,
                    notes="cache_hit",
                )
            )
            emit_completed(index, spec, cached_result, cache_hit=True)
            stop_reason = should_stop_early()
            if stop_reason is not None:
                partial_result = True
                break
            continue

        if (
            max_workers is not None
            and max_workers > 1
            and max_runtime_seconds is None
            and max_issues is None
            and stop_after_actionable is None
        ):
            pending_parallel.append((index, spec, cache_key))
            continue

        validator_result = spec.func(layer, **spec.context)
        if cache is not None and cache_key is not None:
            cache.set(cache_key, validator_result)
        issues.extend(validator_result)
        validators_completed.append(spec.name)
        validator_coverage.append(
            _coverage_row(
                spec,
                "completed",
                reason=None,
                layer_geometry_types=layer_geometry_types,
                profile=resolved_profile,
            )
        )
        emit_completed(index, spec, validator_result, cache_hit=False)
        stop_reason = should_stop_early()
        if stop_reason is not None:
            partial_result = True
            break

    if pending_parallel:
        ordered_results: dict[int, tuple[_ValidatorSpec, list[ValidationIssue], str | None]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(spec.func, layer, **spec.context): (index, spec, cache_key)
                for index, spec, cache_key in pending_parallel
            }
            for future in as_completed(futures):
                index, spec, cache_key = futures[future]
                validator_result = future.result()
                if cache is not None and cache_key is not None:
                    cache.set(cache_key, validator_result)
                ordered_results[index] = (spec, validator_result, cache_key)
                validator_coverage.append(
                    _coverage_row(
                        spec,
                        "completed",
                        reason=None,
                        layer_geometry_types=layer_geometry_types,
                        profile=resolved_profile,
                    )
                )
                emit_completed(index, spec, validator_result, cache_hit=False)

        for index in sorted(ordered_results):
            spec, validator_result, _ = ordered_results[index]
            issues.extend(validator_result)
            validators_completed.append(spec.name)

    if stop_reason is None and partial_result:
        stop_reason = "partial_execution"

    skipped_names = {str(row["validator_name"]) for row in validator_coverage if row.get("status") == "skipped"}
    deferred = [spec.name for spec in specs if spec.name not in validators_completed and spec.name not in skipped_names]
    for spec in specs:
        if spec.name in validators_completed:
            continue
        if any(row["validator_name"] == spec.name and row["status"] == "skipped" for row in validator_coverage):
            continue
        validator_coverage.append(
            _coverage_row(
                spec,
                "deferred",
                reason=stop_reason or "not_run",
                layer_geometry_types=layer_geometry_types,
                profile=resolved_profile,
            )
        )
    result = ValidationPlanResult(
        issues=issues,
        validators_attempted=tuple(validators_attempted),
        validators_completed=tuple(validators_completed),
        validators_deferred=tuple(deferred),
        partial_result=partial_result,
        stop_reason=stop_reason,
        validator_coverage=tuple(validator_coverage),
    )
    if return_result:
        return result
    return result.issues


__all__ = [
    "FileValidationCache",
    "InMemoryValidationCache",
    "ValidationLimits",
    "ValidationPlanResult",
    "ValidationProfile",
    "ValidationProgressEvent",
    "build_validation_cache_key",
    "clear_custom_validators",
    "clear_validation_profiles",
    "execute_validation_plan",
    "get_validation_profile",
    "list_custom_validators",
    "register_custom_validator",
    "register_validation_profile",
]
