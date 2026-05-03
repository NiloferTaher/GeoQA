from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from geoqa.fixes import drop_null_geometries, remove_duplicate_vertices
from geoqa.reports.report_generator import generate_report
from geoqa.script_base import GeoQAScriptBase
from geoqa.thermal import ThermalGuard
from geoqa.validations.accuracy import coordinate_precision, positional_accuracy, xy_tolerance
from geoqa.validations.attributes import domain_range_checks, required_nulls, uniqueness
from geoqa.validations.base import ValidationIssue
from geoqa.validations.crs import invalid_crs, missing_crs
from geoqa.validations.geometry import duplicate_vertex, null_geometry, self_intersection
from geoqa.validations.integrity import missing_spatial_index, non_rfc7946_geojson, outdated_index
from geoqa.validations.metadata import incomplete_metadata, missing_metadata_fields


DATASET_TYPE_LABELS = {
    "water_network": "Water Network",
    "flood_zones": "Flood Zones",
    "land_use": "Land Use",
    "environmental": "Environmental",
    "generic": "Generic",
}

DATASET_TYPE_ALIASES = {
    "1": "water_network",
    "water network": "water_network",
    "water_network": "water_network",
    "water": "water_network",
    "2": "flood_zones",
    "flood zones": "flood_zones",
    "flood_zones": "flood_zones",
    "flood": "flood_zones",
    "3": "land_use",
    "land use": "land_use",
    "land_use": "land_use",
    "4": "environmental",
    "environmental": "environmental",
    "environment": "environmental",
    "5": "generic",
    "generic": "generic",
    "other": "generic",
    "custom": "generic",
}


@dataclass(slots=True)
class FixSuggestion:
    problem_name: str
    suggestion: str
    auto_fix_available: bool
    fix_function_name: str | None = None


@dataclass(slots=True)
class FixAction:
    problem_name: str
    scope: str
    action: str
    status: str
    rows_before: int | None = None
    rows_after: int | None = None
    notes: str | None = None
    preview: dict[str, Any] | None = None


@dataclass(slots=True)
class AgentRunResult:
    dataset_path: str
    dataset_type: str
    inferred_dataset_type: str | None
    issues: list[ValidationIssue]
    fix_actions: list[FixAction]
    messages: list[str]
    recommendations: list[dict[str, Any]] | None = None
    issue_report_path: str | None = None
    final_report_path: str | None = None
    fix_log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "dataset_type": self.dataset_type,
            "inferred_dataset_type": self.inferred_dataset_type,
            "issues": [issue.to_dict() for issue in self.issues],
            "fix_actions": [asdict(action) for action in self.fix_actions],
            "messages": self.messages,
            "recommendations": self.recommendations,
            "issue_report_path": self.issue_report_path,
            "final_report_path": self.final_report_path,
            "fix_log_path": self.fix_log_path,
        }


SUPPORTED_FIXES: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "null_geometry": ("drop_null_geometries", drop_null_geometries),
    "duplicate_vertex": ("remove_duplicate_vertices", remove_duplicate_vertices),
}


def _missing_input_handler(prompt: str) -> str:
    raise RuntimeError(
        "Interactive prompting is not available in the core GeoQA library. "
        "Use the CLI for interactive workflows or pass an explicit input handler."
    )


def _resolve_input_func(input_func: Callable[[str], str] | None) -> Callable[[str], str]:
    return input_func or _missing_input_handler


def _validation_runtime_issue(problem_space: str, exc: Exception) -> ValidationIssue:
    return ValidationIssue(
        problem_name="validation_runtime_error",
        severity="high",
        description=f"{problem_space} validation failed: {exc}",
        solution_hint="Review the dataset structure, dependencies, and validator inputs before retrying.",
        feature_id=None,
        geometry=None,
    )


def _safe_extend(
    issues: list[ValidationIssue],
    problem_space: str,
    func: Callable[..., list[ValidationIssue]],
    *args: Any,
    messages: list[str] | None = None,
    **kwargs: Any,
) -> None:
    try:
        issues.extend(func(*args, **kwargs))
    except Exception as exc:
        issues.append(_validation_runtime_issue(problem_space, exc))
        if messages is not None:
            messages.append(f"{problem_space} validation failed and was captured as an issue: {exc}")


def _geometry_preview(geometry: Any) -> dict[str, Any] | None:
    if geometry is None:
        return None
    preview: dict[str, Any] = {"geom_type": getattr(geometry, "geom_type", type(geometry).__name__)}
    bounds = getattr(geometry, "bounds", None)
    if bounds is not None:
        try:
            preview["bounds"] = list(bounds)
        except Exception:
            pass
    try:
        wkt = getattr(geometry, "wkt", None)
        if isinstance(wkt, str):
            preview["wkt_preview"] = wkt[:120]
    except Exception:
        pass
    return preview


def _slice_layer(layer: Any, start: int, stop: int) -> Any:
    if hasattr(layer, "iloc"):
        return layer.iloc[start:stop].copy()
    if hasattr(layer, "head") and start == 0:
        return layer.head(stop - start).copy()
    return layer.copy()


def _slice_weighted_chunk(layer: Any, start: int, target_vertices_per_chunk: int) -> tuple[Any, int]:
    if not hasattr(layer, "__len__") or not hasattr(layer, "iloc"):
        return layer.copy(), len(layer) if hasattr(layer, "__len__") else start
    total = len(layer)
    if "geometry" not in getattr(layer, "columns", []):
        stop = min(start + max(target_vertices_per_chunk, 1), total)
        return _slice_layer(layer, start, stop), stop
    current_weight = 0
    stop = start
    try:
        for offset, geometry in enumerate(layer["geometry"].iloc[start:], start=start):
            weight = max(_geometry_vertex_count(geometry), 1)
            if stop > start and current_weight + weight > target_vertices_per_chunk:
                break
            current_weight += weight
            stop = offset + 1
        if stop <= start:
            stop = min(start + 1, total)
    except Exception:
        stop = min(start + 1, total)
    return _slice_layer(layer, start, stop), stop


def _iter_batches(layer: Any, batch_size: int | None):
    if batch_size is None or batch_size <= 0:
        yield layer.copy()
        return
    if not hasattr(layer, "__len__"):
        yield layer.copy()
        return
    total = len(layer)
    if total <= batch_size:
        yield layer.copy()
        return
    for start in range(0, total, batch_size):
        yield _slice_layer(layer, start, min(start + batch_size, total))


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
            total += max(_geometry_vertex_count(geometry), 1)
    except Exception:
        return None
    return total


def _iter_weighted_batches(layer: Any, target_vertices_per_chunk: int | None):
    if target_vertices_per_chunk is None or target_vertices_per_chunk <= 0:
        yield layer.copy()
        return
    if not hasattr(layer, "__len__") or not hasattr(layer, "iloc"):
        yield layer.copy()
        return
    columns = getattr(layer, "columns", [])
    if "geometry" not in columns:
        yield layer.copy()
        return
    total = len(layer)
    if total == 0:
        yield layer.copy()
        return

    start = 0
    current_weight = 0
    try:
        for position, geometry in enumerate(layer["geometry"]):
            weight = max(_geometry_vertex_count(geometry), 1)
            if position > start and current_weight + weight > target_vertices_per_chunk:
                yield _slice_layer(layer, start, position)
                start = position
                current_weight = 0
            current_weight += weight
        if start < total:
            yield _slice_layer(layer, start, total)
    except Exception:
        yield layer.copy()
        return


def _iter_validation_batches(
    layer: Any,
    *,
    batch_size: int | None,
    target_vertices_per_chunk: int | None,
):
    if target_vertices_per_chunk is not None and target_vertices_per_chunk > 0:
        yield from _iter_weighted_batches(layer, target_vertices_per_chunk)
        return
    yield from _iter_batches(layer, batch_size)


def _concat_layers(chunks: list[Any], original_layer: Any) -> Any:
    if not chunks:
        return original_layer.copy()
    if len(chunks) == 1:
        return chunks[0]
    try:
        import pandas as pd
    except ImportError:
        return chunks[0]
    concatenated = pd.concat(chunks, ignore_index=True)
    if hasattr(original_layer, "geometry") and hasattr(original_layer, "crs"):
        try:
            import geopandas as gpd

            return gpd.GeoDataFrame(concatenated, geometry="geometry", crs=getattr(original_layer, "crs", None))
        except Exception:
            return concatenated
    return concatenated


def _pause_between_validation_chunks(
    *,
    chunk_index: int,
    sleep_seconds: float,
    thermal_guard: Any | None,
    sleep_fn: Callable[[float], None],
) -> None:
    if thermal_guard is not None:
        thermal_guard.cool_down_if_needed(stage=f"validation_chunk_{chunk_index}_cooldown")
    if sleep_seconds > 0:
        sleep_fn(sleep_seconds)
    if thermal_guard is not None:
        thermal_guard.wait_until_safe(stage=f"validation_chunk_{chunk_index + 1}_pre")


def _adaptive_chunk_settings(
    *,
    chunk_size: int,
    target_vertices_per_chunk: int | None,
    chunk_runtime_seconds: float,
    thermal_guard: Any | None,
) -> tuple[int, int | None, str | None]:
    if thermal_guard is None or not hasattr(thermal_guard, "snapshot"):
        return chunk_size, target_vertices_per_chunk, None
    try:
        snapshot = thermal_guard.snapshot()
    except Exception:
        return chunk_size, target_vertices_per_chunk, None

    max_temp = getattr(snapshot, "max_temp_c", None)
    warn_temp = getattr(thermal_guard, "warn_temp_c", None)
    hard_limit = getattr(thermal_guard, "max_temp_c", None)
    new_chunk_size = chunk_size
    new_target_vertices = target_vertices_per_chunk
    reason: str | None = None

    if max_temp is not None and hard_limit is not None and max_temp >= (hard_limit - 1.0):
        new_chunk_size = max(100, int(chunk_size * 0.7))
        if target_vertices_per_chunk is not None:
            new_target_vertices = max(5_000, int(target_vertices_per_chunk * 0.7))
        reason = f"Thermal pressure observed at {max_temp:.1f} C; reducing chunk size."
    elif chunk_runtime_seconds >= 8.0:
        new_chunk_size = max(100, int(chunk_size * 0.8))
        if target_vertices_per_chunk is not None:
            new_target_vertices = max(5_000, int(target_vertices_per_chunk * 0.8))
        reason = f"Chunk runtime {chunk_runtime_seconds:.1f}s was high; reducing chunk size."
    elif (
        max_temp is not None
        and warn_temp is not None
        and max_temp < (warn_temp - 4.0)
        and chunk_runtime_seconds <= 1.5
    ):
        new_chunk_size = max(chunk_size + 1, int(chunk_size * 1.2))
        if target_vertices_per_chunk is not None:
            new_target_vertices = max(target_vertices_per_chunk + 1, int(target_vertices_per_chunk * 1.2))
        reason = f"Thermals are cool and chunk runtime {chunk_runtime_seconds:.1f}s was light; increasing chunk size."

    return new_chunk_size, new_target_vertices, reason


def _build_fix_preview(before_layer: Any, after_layer: Any, *, max_features: int = 5) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "rows_before": len(before_layer) if hasattr(before_layer, "__len__") else None,
        "rows_after": len(after_layer) if hasattr(after_layer, "__len__") else None,
        "examples": [],
    }
    if not hasattr(before_layer, "iterrows") or not hasattr(after_layer, "iterrows"):
        return preview
    before_rows = list(before_layer.iterrows())[:max_features]
    after_rows = list(after_layer.iterrows())[:max_features]
    for position, before in enumerate(before_rows):
        _, before_row = before
        after_row = after_rows[position][1] if position < len(after_rows) else None
        example = {
            "before_geometry": _geometry_preview(before_row["geometry"]) if "geometry" in before_row.index else None,
            "after_geometry": (
                _geometry_preview(after_row["geometry"]) if after_row is not None and "geometry" in after_row.index else None
            ),
        }
        preview["examples"].append(example)
    return preview


def _suggest_validation_chunk_settings(layer: Any) -> tuple[int, float, int | None]:
    total = len(layer) if hasattr(layer, "__len__") else 0
    total_vertices = _estimate_total_vertices(layer)
    if total_vertices is not None:
        if total_vertices >= 1_000_000:
            return 500, 3.0, 40_000
        if total_vertices >= 250_000:
            return 750, 2.0, 60_000
        if total_vertices >= 50_000:
            return 1000, 1.0, 80_000
    if total >= 100000:
        return 2000, 3.0, None
    if total >= 25000:
        return 1000, 2.0, None
    return 500, 1.0, None


def _build_chunking_recommendation(
    layer: Any,
    issues: list[ValidationIssue],
    messages: list[str],
    *,
    validation_chunk_size: int | None,
) -> dict[str, Any] | None:
    if validation_chunk_size is not None and validation_chunk_size > 0:
        return None

    thermal_or_runtime = any(issue.problem_name == "validation_runtime_error" for issue in issues) or any(
        "CPU temperature" in message or "validation failed" in message for message in messages
    )
    if not thermal_or_runtime:
        return None

    suggested_chunk_size, suggested_sleep_seconds, suggested_target_vertices_per_chunk = _suggest_validation_chunk_settings(
        layer
    )
    return {
        "kind": "chunking_recommended",
        "reason": "Validation encountered thermal or runtime pressure during a non-chunked run.",
        "suggested_validation_chunk_size": suggested_chunk_size,
        "suggested_sleep_seconds": suggested_sleep_seconds,
        "suggested_target_vertices_per_chunk": suggested_target_vertices_per_chunk,
    }


def _append_fix_log(fix_actions: list[FixAction], log_path: str | Path | None) -> str | None:
    if log_path is None:
        return None
    output_path = Path(log_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        for action in fix_actions:
            handle.write(json.dumps(asdict(action), ensure_ascii=False) + "\n")
    return str(output_path)


def get_dataset_type(input_func: Callable[[str], str] | None = None) -> str:
    """Prompt the user to select a dataset type."""
    input_func = _resolve_input_func(input_func)
    print("Please select the dataset type:")
    print("1. Water Network (e.g., pipes, hydrants, valves)")
    print("2. Flood Zones (e.g., flood risk areas, elevation models)")
    print("3. Land Use (e.g., zoning, land classification)")
    print("4. Environmental (e.g., habitats, protected areas)")
    print("5. Generic / Other")
    return input_func("Enter the number corresponding to your dataset type: ").strip()


def infer_dataset_type(layer: Any) -> str:
    """Infer a likely dataset type using lightweight column-name heuristics."""
    columns = {str(column).lower() for column in getattr(layer, "columns", [])}
    if {"pipe_diameter", "valve_id", "hydrant_id", "asset_id"} & columns:
        return "water_network"
    if {"flood_zone_id", "fema_zone", "base_flood_elev", "flood_risk"} & columns:
        return "flood_zones"
    if {"land_use", "zoning", "parcel_use", "landuse"} & columns:
        return "land_use"
    if {"habitat_type", "species", "protected_area", "conservation_status"} & columns:
        return "environmental"
    return "generic"


def normalize_dataset_type(selection: str | None, layer: Any | None = None) -> tuple[str, str | None]:
    """Resolve a user-supplied dataset type or infer one from the layer."""
    if selection:
        normalized = DATASET_TYPE_ALIASES.get(selection.strip().lower())
        if normalized is not None:
            return normalized, None
    if layer is not None:
        inferred = infer_dataset_type(layer)
        return inferred, inferred
    raise ValueError(f"Unsupported dataset type: {selection!r}")


def _existing_fields(layer: Any, candidates: list[str]) -> list[str]:
    columns = {str(column) for column in getattr(layer, "columns", [])}
    return [candidate for candidate in candidates if candidate in columns]


def _run_geometry_checks(layer: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(null_geometry(layer))
    issues.extend(duplicate_vertex(layer))
    try:
        issues.extend(self_intersection(layer))
    except RuntimeError:
        # Keep the agent usable when Shapely is not available.
        pass
    return issues


def _validate_layer_for_dataset_type_chunked(
    layer: Any,
    dataset_type: str,
    *,
    expected_crs: Any,
    metadata: dict[str, Any] | None,
    reference_layer: Any | None,
    messages: list[str] | None,
    validation_chunk_size: int,
    validation_target_vertices_per_chunk: int | None,
    sleep_between_validation_chunks_seconds: float,
    thermal_guard: Any | None,
    sleep_fn: Callable[[float], None],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dataset_type = DATASET_TYPE_ALIASES.get(dataset_type.strip().lower(), dataset_type.strip().lower())
    total_rows = len(layer) if hasattr(layer, "__len__") else 0
    start = 0
    adaptive_chunk_size = max(int(validation_chunk_size), 1)
    adaptive_target_vertices = (
        int(validation_target_vertices_per_chunk) if validation_target_vertices_per_chunk is not None else None
    )
    chunk_index = 0

    def next_chunk() -> tuple[Any, int]:
        nonlocal start
        if adaptive_target_vertices is not None and adaptive_target_vertices > 0:
            return _slice_weighted_chunk(layer, start, adaptive_target_vertices)
        stop = min(start + adaptive_chunk_size, total_rows)
        return _slice_layer(layer, start, stop), stop

    def finish_chunk(chunk_started: float) -> None:
        nonlocal adaptive_chunk_size, adaptive_target_vertices, start
        new_size, new_vertices, reason = _adaptive_chunk_settings(
            chunk_size=adaptive_chunk_size,
            target_vertices_per_chunk=adaptive_target_vertices,
            chunk_runtime_seconds=time.perf_counter() - chunk_started,
            thermal_guard=thermal_guard,
        )
        if reason and messages is not None and (
            new_size != adaptive_chunk_size or new_vertices != adaptive_target_vertices
        ):
            message = reason
            if new_size != adaptive_chunk_size:
                message += f" Next chunk_size={new_size}."
            if new_vertices != adaptive_target_vertices and new_vertices is not None:
                message += f" Next target_vertices_per_chunk={new_vertices}."
            messages.append(message)
        adaptive_chunk_size = new_size
        adaptive_target_vertices = new_vertices
        if start < total_rows:
            _pause_between_validation_chunks(
                chunk_index=chunk_index,
                sleep_seconds=sleep_between_validation_chunks_seconds,
                thermal_guard=thermal_guard,
                sleep_fn=sleep_fn,
            )

    if dataset_type == "water_network":
        required_fields = _existing_fields(layer, ["asset_id", "pipe_diameter", "status"])
        unique_fields = _existing_fields(layer, ["asset_id", "pipe_id"])
        if unique_fields:
            _safe_extend(issues, "uniqueness", uniqueness, layer, unique_fields[0], messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        while start < total_rows:
            chunk, stop = next_chunk()
            chunk_index += 1
            chunk_started = time.perf_counter()
            _safe_extend(issues, "geometry", _run_geometry_checks, chunk, messages=messages)
            if required_fields:
                _safe_extend(issues, "required attribute", required_nulls, chunk, required_fields, messages=messages)
            start = stop
            finish_chunk(chunk_started)
        return issues

    if dataset_type == "flood_zones":
        required_fields = _existing_fields(layer, ["flood_zone_id"])
        if required_fields:
            _safe_extend(issues, "uniqueness", uniqueness, layer, required_fields[0], messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        while start < total_rows:
            chunk, stop = next_chunk()
            chunk_index += 1
            chunk_started = time.perf_counter()
            _safe_extend(issues, "geometry", _run_geometry_checks, chunk, messages=messages)
            if required_fields:
                _safe_extend(issues, "required attribute", required_nulls, chunk, required_fields, messages=messages)
            start = stop
            finish_chunk(chunk_started)
        return issues

    if dataset_type == "land_use":
        land_use_fields = _existing_fields(layer, ["land_use", "landuse", "zoning"])
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        while start < total_rows:
            chunk, stop = next_chunk()
            chunk_index += 1
            chunk_started = time.perf_counter()
            _safe_extend(issues, "geometry", _run_geometry_checks, chunk, messages=messages)
            if land_use_fields:
                _safe_extend(issues, "domain", domain_range_checks, chunk, land_use_fields[0], {1, 2, 3}, messages=messages)
            start = stop
            finish_chunk(chunk_started)
        return issues

    if dataset_type == "environmental":
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        _safe_extend(issues, "expected crs", invalid_crs, layer, expected_crs, messages=messages)
        if metadata is not None:
            _safe_extend(issues, "metadata", missing_metadata_fields, metadata, messages=messages)
            _safe_extend(issues, "metadata completeness", incomplete_metadata, metadata, messages=messages)
        while start < total_rows:
            chunk, stop = next_chunk()
            chunk_index += 1
            chunk_started = time.perf_counter()
            _safe_extend(issues, "geometry", _run_geometry_checks, chunk, messages=messages)
            start = stop
            finish_chunk(chunk_started)
        return issues

    if dataset_type == "generic":
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        if metadata is not None:
            _safe_extend(issues, "metadata", missing_metadata_fields, metadata, messages=messages)
            _safe_extend(issues, "metadata completeness", incomplete_metadata, metadata, messages=messages)
        _safe_extend(issues, "xy tolerance", xy_tolerance, layer, messages=messages)
        _safe_extend(issues, "spatial index", missing_spatial_index, layer, messages=messages)
        _safe_extend(issues, "index maintenance", outdated_index, layer, messages=messages)
        while start < total_rows:
            chunk, stop = next_chunk()
            chunk_index += 1
            chunk_started = time.perf_counter()
            _safe_extend(issues, "geometry", _run_geometry_checks, chunk, messages=messages)
            _safe_extend(issues, "accuracy", coordinate_precision, chunk, messages=messages)
            if reference_layer is not None:
                _safe_extend(issues, "positional accuracy", positional_accuracy, chunk, reference_layer, messages=messages)
            start = stop
            finish_chunk(chunk_started)
        return issues

    raise ValueError(f"Unsupported dataset type: {dataset_type!r}")


def validate_layer_for_dataset_type(
    layer: Any,
    dataset_type: str,
    *,
    expected_crs: Any = "EPSG:4326",
    metadata: dict[str, Any] | None = None,
    reference_layer: Any | None = None,
    messages: list[str] | None = None,
    validation_chunk_size: int | None = None,
    validation_target_vertices_per_chunk: int | None = None,
    sleep_between_validation_chunks_seconds: float = 0.0,
    thermal_guard: Any | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[ValidationIssue]:
    """Run the validation set associated with the requested dataset type."""
    if (validation_chunk_size is not None and validation_chunk_size > 0) or (
        validation_target_vertices_per_chunk is not None and validation_target_vertices_per_chunk > 0
    ):
        return _validate_layer_for_dataset_type_chunked(
            layer,
            dataset_type,
            expected_crs=expected_crs,
            metadata=metadata,
            reference_layer=reference_layer,
            messages=messages,
            validation_chunk_size=validation_chunk_size or len(layer),
            validation_target_vertices_per_chunk=validation_target_vertices_per_chunk,
            sleep_between_validation_chunks_seconds=sleep_between_validation_chunks_seconds,
            thermal_guard=thermal_guard,
            sleep_fn=sleep_fn,
        )

    issues: list[ValidationIssue] = []
    dataset_type = DATASET_TYPE_ALIASES.get(dataset_type.strip().lower(), dataset_type.strip().lower())

    if dataset_type == "water_network":
        _safe_extend(issues, "geometry", _run_geometry_checks, layer, messages=messages)
        required_fields = _existing_fields(layer, ["asset_id", "pipe_diameter", "status"])
        if required_fields:
            _safe_extend(issues, "required attribute", required_nulls, layer, required_fields, messages=messages)
        unique_fields = _existing_fields(layer, ["asset_id", "pipe_id"])
        if unique_fields:
            _safe_extend(issues, "uniqueness", uniqueness, layer, unique_fields[0], messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        return issues

    if dataset_type == "flood_zones":
        _safe_extend(issues, "geometry", _run_geometry_checks, layer, messages=messages)
        required_fields = _existing_fields(layer, ["flood_zone_id"])
        if required_fields:
            _safe_extend(issues, "required attribute", required_nulls, layer, required_fields, messages=messages)
            _safe_extend(issues, "uniqueness", uniqueness, layer, required_fields[0], messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        return issues

    if dataset_type == "land_use":
        _safe_extend(issues, "geometry", _run_geometry_checks, layer, messages=messages)
        land_use_fields = _existing_fields(layer, ["land_use", "landuse", "zoning"])
        if land_use_fields:
            _safe_extend(issues, "domain", domain_range_checks, layer, land_use_fields[0], {1, 2, 3}, messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        return issues

    if dataset_type == "environmental":
        _safe_extend(issues, "geometry", _run_geometry_checks, layer, messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        _safe_extend(issues, "expected crs", invalid_crs, layer, expected_crs, messages=messages)
        if metadata is not None:
            _safe_extend(issues, "metadata", missing_metadata_fields, metadata, messages=messages)
            _safe_extend(issues, "metadata completeness", incomplete_metadata, metadata, messages=messages)
        return issues

    if dataset_type == "generic":
        _safe_extend(issues, "geometry", _run_geometry_checks, layer, messages=messages)
        _safe_extend(issues, "crs", missing_crs, layer, messages=messages)
        if metadata is not None:
            _safe_extend(issues, "metadata", missing_metadata_fields, metadata, messages=messages)
            _safe_extend(issues, "metadata completeness", incomplete_metadata, metadata, messages=messages)
        _safe_extend(issues, "accuracy", coordinate_precision, layer, messages=messages)
        _safe_extend(issues, "xy tolerance", xy_tolerance, layer, messages=messages)
        _safe_extend(issues, "spatial index", missing_spatial_index, layer, messages=messages)
        _safe_extend(issues, "index maintenance", outdated_index, layer, messages=messages)
        if reference_layer is not None:
            _safe_extend(issues, "positional accuracy", positional_accuracy, layer, reference_layer, messages=messages)
        return issues

    raise ValueError(f"Unsupported dataset type: {dataset_type!r}")


def get_fix_suggestion(issue: ValidationIssue) -> FixSuggestion:
    """Return a fix suggestion for a validation issue."""
    if issue.problem_name in SUPPORTED_FIXES:
        function_name, _ = SUPPORTED_FIXES[issue.problem_name]
        return FixSuggestion(
            problem_name=issue.problem_name,
            suggestion=issue.solution_hint,
            auto_fix_available=True,
            fix_function_name=function_name,
        )
    return FixSuggestion(
        problem_name=issue.problem_name,
        suggestion=issue.solution_hint,
        auto_fix_available=False,
        fix_function_name=None,
    )


def suggest_fixes(issues: list[ValidationIssue]) -> list[FixSuggestion]:
    """Return one fix suggestion per distinct problem name."""
    suggestions: dict[str, FixSuggestion] = {}
    for issue in issues:
        suggestions.setdefault(issue.problem_name, get_fix_suggestion(issue))
    return list(suggestions.values())


def _apply_fix(layer: Any, problem_name: str, scope: str) -> tuple[Any, FixAction]:
    function_name, fix_function = SUPPORTED_FIXES[problem_name]
    before_count = len(layer)
    fixed_layer = fix_function(layer)
    after_count = len(fixed_layer)
    preview = _build_fix_preview(layer, fixed_layer) if scope == "sample" else None
    return fixed_layer, FixAction(
        problem_name=problem_name,
        scope=scope,
        action=function_name,
        status="applied",
        rows_before=before_count,
        rows_after=after_count,
        preview=preview,
    )


def review_fixes_on_sample(
    layer: Any,
    issues: list[ValidationIssue],
    *,
    sample_size: int = 50,
    visual_feedback: bool = True,
    input_func: Callable[[str], str] | None = None,
) -> tuple[Any, list[str], list[FixAction]]:
    """
    Review auto-fix candidates on a sample subset.

    Returns the sampled fixed layer, the approved problem names, and recorded actions.
    """
    input_func = _resolve_input_func(input_func)
    sample_layer = layer.head(sample_size).copy()
    approved_problem_names: list[str] = []
    actions: list[FixAction] = []

    distinct_suggestions = suggest_fixes(issues)
    for suggestion in distinct_suggestions:
        if not suggestion.auto_fix_available:
            actions.append(
                FixAction(
                    problem_name=suggestion.problem_name,
                    scope="sample",
                    action="manual_review",
                    status="skipped",
                    notes=suggestion.suggestion,
                )
            )
            continue

        response = input_func(
            f"Apply sample fix for '{suggestion.problem_name}' using {suggestion.fix_function_name}? (y/n): "
        ).strip().lower()
        if response != "y":
            actions.append(
                FixAction(
                    problem_name=suggestion.problem_name,
                    scope="sample",
                    action=suggestion.fix_function_name or "unknown_fix",
                    status="rejected",
                    notes="User rejected the sample fix.",
                )
            )
            continue

        sample_layer, action = _apply_fix(sample_layer, suggestion.problem_name, "sample")
        if not visual_feedback:
            action.preview = None
        approved_problem_names.append(suggestion.problem_name)
        actions.append(action)

    return sample_layer, approved_problem_names, actions


def apply_approved_fixes(
    layer: Any,
    approved_problem_names: list[str],
    *,
    batch_size: int | None = None,
) -> tuple[Any, list[FixAction]]:
    """Apply approved fixes to the full layer."""
    actions: list[FixAction] = []
    if batch_size is None or batch_size <= 0:
        fixed_layer = layer.copy()
        for problem_name in approved_problem_names:
            fixed_layer, action = _apply_fix(fixed_layer, problem_name, "full_dataset")
            actions.append(action)
        return fixed_layer, actions

    chunks = list(_iter_batches(layer, batch_size))
    fixed_chunks: list[Any] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        fixed_chunk = chunk.copy()
        for problem_name in approved_problem_names:
            fixed_chunk, action = _apply_fix(fixed_chunk, problem_name, "full_dataset_batch")
            action.notes = f"Applied in batch {chunk_index}."
            actions.append(action)
        fixed_chunks.append(fixed_chunk)
    return _concat_layers(fixed_chunks, layer), actions


def generate_agent_report(
    issues: list[ValidationIssue],
    fix_actions: list[FixAction],
    *,
    messages: list[str] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    output_format: str = "json",
    file_path: str = "agent_validation_report",
) -> Path:
    """Write an agent-oriented combined report with both issues and fix actions."""
    output_path = Path(f"{file_path}.{output_format.lower()}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "issues": [issue.to_dict() for issue in issues],
        "fix_actions": [asdict(action) for action in fix_actions],
        "messages": messages or [],
        "recommendations": recommendations or [],
    }

    if output_format.lower() == "json":
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_path

    if output_format.lower() == "csv":
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "row_type",
                    "problem_name",
                    "severity",
                    "description",
                    "solution_hint",
                    "feature_id",
                    "scope",
                    "action",
                    "status",
                    "rows_before",
                    "rows_after",
                    "notes",
                    "preview",
                ],
            )
            writer.writeheader()
            for issue in issues:
                writer.writerow(
                    {
                        "row_type": "issue",
                        "problem_name": issue.problem_name,
                        "severity": issue.severity,
                        "description": issue.description,
                        "solution_hint": issue.solution_hint,
                        "feature_id": issue.feature_id,
                    }
                )
            for action in fix_actions:
                writer.writerow(
                    {
                        "row_type": "fix_action",
                        "problem_name": action.problem_name,
                        "scope": action.scope,
                        "action": action.action,
                        "status": action.status,
                        "rows_before": action.rows_before,
                        "rows_after": action.rows_after,
                        "notes": action.notes,
                        "preview": json.dumps(action.preview, ensure_ascii=False) if action.preview is not None else None,
                    }
                )
        return output_path

    raise ValueError(f"Unsupported output format: {output_format!r}")


def fix_import_snippets() -> dict[str, str]:
    """Return reusable import snippets for supported fix helpers."""
    return {
        "drop_null_geometries": "from geoqa.fixes import drop_null_geometries",
        "remove_duplicate_vertices": "from geoqa.fixes import remove_duplicate_vertices",
    }


def _load_dataset(dataset_path: str | Path) -> Any:
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("GeoQA agent workflows require GeoPandas. Install geopandas to use the agent.") from exc
    try:
        return gpd.read_file(dataset_path)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to read dataset {dataset_path!r}. Confirm the file exists, the format is supported, and the driver is available."
        ) from exc


def run_agent_workflow(
    dataset_path: str | Path,
    dataset_type: str | None = None,
    *,
    metadata: dict[str, Any] | None = None,
    reference_path: str | Path | None = None,
    expected_crs: Any = "EPSG:4326",
    issue_report_format: str = "csv",
    issue_report_path: str = "validation_report",
    final_report_format: str = "json",
    final_report_path: str = "agent_validation_report",
    sample_size: int = 50,
    batch_size: int | None = None,
    validation_chunk_size: int | None = None,
    validation_target_vertices_per_chunk: int | None = None,
    sleep_between_validation_chunks_seconds: float = 0.0,
    visual_feedback: bool = True,
    fix_log_path: str | Path | None = None,
    recommendation_hook: Callable[[list[ValidationIssue], dict[str, Any]], list[dict[str, Any]] | None] | None = None,
    post_fix_hook: Callable[[dict[str, Any]], None] | None = None,
    interactive: bool = True,
    input_func: Callable[[str], str] | None = None,
    thermal_guard: Any | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> AgentRunResult:
    """Run validation, optional sample-first fix review, and combined reporting."""
    input_func = _resolve_input_func(input_func) if interactive else _missing_input_handler
    messages: list[str] = []
    layer = _load_dataset(dataset_path)
    reference_layer = _load_dataset(reference_path) if reference_path is not None else None

    if dataset_type is None and interactive:
        dataset_type = get_dataset_type(input_func)

    resolved_dataset_type, inferred_dataset_type = normalize_dataset_type(dataset_type, layer)
    issues = validate_layer_for_dataset_type(
        layer,
        resolved_dataset_type,
        expected_crs=expected_crs,
        metadata=metadata,
        reference_layer=reference_layer,
        messages=messages,
        validation_chunk_size=validation_chunk_size,
        validation_target_vertices_per_chunk=validation_target_vertices_per_chunk,
        sleep_between_validation_chunks_seconds=sleep_between_validation_chunks_seconds,
        thermal_guard=thermal_guard,
        sleep_fn=sleep_fn,
    )

    recommendations = recommendation_hook(issues, {"dataset_type": resolved_dataset_type, "dataset_path": str(dataset_path)}) if recommendation_hook else None
    chunking_recommendation = _build_chunking_recommendation(
        layer,
        issues,
        messages,
        validation_chunk_size=validation_chunk_size,
    )
    if chunking_recommendation is not None:
        recommendations = list(recommendations or [])
        recommendations.append(chunking_recommendation)
        if interactive:
            response = input_func(
                "Validation hit thermal/runtime pressure. Re-run with chunking and cooldown pauses? (y/n): "
            ).strip().lower()
            if response == "y":
                suggested_chunk_size = int(chunking_recommendation["suggested_validation_chunk_size"])
                suggested_sleep = float(chunking_recommendation["suggested_sleep_seconds"])
                suggested_target_vertices = chunking_recommendation.get("suggested_target_vertices_per_chunk")
                messages.append(
                    "Re-running validation with chunking after detecting thermal/runtime pressure."
                )
                issues = validate_layer_for_dataset_type(
                    layer,
                    resolved_dataset_type,
                    expected_crs=expected_crs,
                    metadata=metadata,
                    reference_layer=reference_layer,
                    messages=messages,
                    validation_chunk_size=suggested_chunk_size,
                    validation_target_vertices_per_chunk=(
                        int(suggested_target_vertices) if suggested_target_vertices is not None else None
                    ),
                    sleep_between_validation_chunks_seconds=suggested_sleep,
                    thermal_guard=thermal_guard,
                    sleep_fn=sleep_fn,
                )
                messages.append(
                    f"Chunked rerun used validation_chunk_size={suggested_chunk_size} and "
                    f"sleep_between_validation_chunks_seconds={suggested_sleep}."
                )
                recommendations.append(
                    {
                        "kind": "chunking_rerun_applied",
                        "validation_chunk_size": suggested_chunk_size,
                        "validation_target_vertices_per_chunk": suggested_target_vertices,
                        "sleep_between_validation_chunks_seconds": suggested_sleep,
                    }
                )
            else:
                messages.append("Chunked validation rerun was offered and declined.")

    issue_report = generate_report(issues, output_format=issue_report_format, file_path=issue_report_path)
    fix_actions: list[FixAction] = []

    if interactive:
        _, approved_problem_names, sample_actions = review_fixes_on_sample(
            layer,
            issues,
            sample_size=sample_size,
            visual_feedback=visual_feedback,
            input_func=input_func,
        )
        fix_actions.extend(sample_actions)

        if approved_problem_names:
            apply_full = input_func("Apply approved fixes to the full dataset? (y/n): ").strip().lower()
            if apply_full == "y":
                fixed_layer, full_actions = apply_approved_fixes(layer, approved_problem_names, batch_size=batch_size)
                fix_actions.extend(full_actions)
                if post_fix_hook is not None:
                    post_fix_hook(
                        {
                            "dataset_path": str(dataset_path),
                            "dataset_type": resolved_dataset_type,
                            "approved_problem_names": approved_problem_names,
                            "fixed_layer": fixed_layer,
                        }
                    )
            else:
                for problem_name in approved_problem_names:
                    fix_actions.append(
                        FixAction(
                            problem_name=problem_name,
                            scope="full_dataset",
                            action=SUPPORTED_FIXES[problem_name][0],
                            status="rejected",
                            notes="User declined to apply approved sample fix to the full dataset.",
                        )
                    )
    fix_log_file = _append_fix_log(fix_actions, fix_log_path)

    final_report = generate_agent_report(
        issues,
        fix_actions,
        messages=messages,
        recommendations=recommendations,
        output_format=final_report_format,
        file_path=final_report_path,
    )

    return AgentRunResult(
        dataset_path=str(dataset_path),
        dataset_type=resolved_dataset_type,
        inferred_dataset_type=inferred_dataset_type,
        issues=issues,
        fix_actions=fix_actions,
        messages=messages,
        recommendations=recommendations,
        issue_report_path=str(issue_report),
        final_report_path=str(final_report),
        fix_log_path=fix_log_file,
    )


def validate_dataset(
    dataset_path: str | Path,
    dataset_type: str | None = None,
    *,
    metadata: dict[str, Any] | None = None,
    reference_path: str | Path | None = None,
    expected_crs: Any = "EPSG:4326",
    output_format: str = "csv",
    report_path: str = "validation_report",
    validation_chunk_size: int | None = None,
    validation_target_vertices_per_chunk: int | None = None,
    sleep_between_validation_chunks_seconds: float = 0.0,
) -> list[ValidationIssue]:
    """
    Convenience validation-only entry point for dataset workflows.

    This runs the agent routing logic and writes the issue report, but it does not
    run the interactive fix-approval flow.
    """
    result = run_agent_workflow(
        dataset_path,
        dataset_type,
        metadata=metadata,
        reference_path=reference_path,
        expected_crs=expected_crs,
        issue_report_format=output_format,
        issue_report_path=report_path,
        final_report_format="json",
        final_report_path=f"{report_path}_agent",
        validation_chunk_size=validation_chunk_size,
        validation_target_vertices_per_chunk=validation_target_vertices_per_chunk,
        sleep_between_validation_chunks_seconds=sleep_between_validation_chunks_seconds,
        interactive=False,
    )
    return result.issues


def apply_fixes_interactively(
    layer: Any,
    issues: list[ValidationIssue],
    *,
    sample_size: int = 50,
    batch_size: int | None = None,
    visual_feedback: bool = True,
    input_func: Callable[[str], str] | None = None,
) -> tuple[Any, list[FixAction]]:
    """
    Review supported fixes on a sample subset and optionally apply approved fixes to the full layer.
    """
    input_func = _resolve_input_func(input_func)
    _, approved_problem_names, sample_actions = review_fixes_on_sample(
        layer,
        issues,
        sample_size=sample_size,
        visual_feedback=visual_feedback,
        input_func=input_func,
    )
    fix_actions = list(sample_actions)
    if approved_problem_names:
        apply_full = input_func("Apply approved fixes to the full dataset? (y/n): ").strip().lower()
        if apply_full == "y":
            fixed_layer, full_actions = apply_approved_fixes(layer, approved_problem_names, batch_size=batch_size)
            fix_actions.extend(full_actions)
            return fixed_layer, fix_actions
        for problem_name in approved_problem_names:
            fix_actions.append(
                FixAction(
                    problem_name=problem_name,
                    scope="full_dataset",
                    action=SUPPORTED_FIXES[problem_name][0],
                    status="rejected",
                    notes="User declined to apply approved sample fix to the full dataset.",
                )
            )
    return layer.copy(), fix_actions


def generate_final_report(
    issues: list[ValidationIssue],
    fix_actions: list[FixAction],
    *,
    output_format: str = "json",
    file_path: str = "final_fix_report",
) -> Path:
    """Convenience wrapper for writing the final agent issue/fix report."""
    return generate_agent_report(issues, fix_actions, output_format=output_format, file_path=file_path)


class GeoQAAgentScript(GeoQAScriptBase[Path, dict[str, Any]]):
    """Thermal-safe GeoQA agent entry point for dataset validation workflows."""

    def __init__(
        self,
        *,
        dataset_path: str | Path,
        dataset_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        reference_path: str | Path | None = None,
        expected_crs: Any = "EPSG:4326",
        issue_report_format: str = "csv",
        issue_report_path: str = "validation_report",
        final_report_format: str = "json",
        final_report_path: str = "agent_validation_report",
        sample_size: int = 50,
        batch_size: int | None = None,
        validation_chunk_size: int | None = None,
        validation_target_vertices_per_chunk: int | None = None,
        sleep_between_validation_chunks_seconds: float = 0.0,
        visual_feedback: bool = True,
        fix_log_path: str | Path | None = None,
        recommendation_hook: Callable[[list[ValidationIssue], dict[str, Any]], list[dict[str, Any]] | None] | None = None,
        post_fix_hook: Callable[[dict[str, Any]], None] | None = None,
        interactive: bool = True,
        input_func: Callable[[str], str] | None = None,
        guard: ThermalGuard | None = None,
    ) -> None:
        super().__init__(guard=guard or ThermalGuard.strict())
        self.dataset_path = Path(dataset_path)
        self.dataset_type = dataset_type
        self.metadata = metadata
        self.reference_path = reference_path
        self.expected_crs = expected_crs
        self.issue_report_format = issue_report_format
        self.issue_report_path = issue_report_path
        self.final_report_format = final_report_format
        self.final_report_path = final_report_path
        self.sample_size = sample_size
        self.batch_size = batch_size
        self.validation_chunk_size = validation_chunk_size
        self.validation_target_vertices_per_chunk = validation_target_vertices_per_chunk
        self.sleep_between_validation_chunks_seconds = sleep_between_validation_chunks_seconds
        self.visual_feedback = visual_feedback
        self.fix_log_path = fix_log_path
        self.recommendation_hook = recommendation_hook
        self.post_fix_hook = post_fix_hook
        self.interactive = interactive
        self.input_func = _resolve_input_func(input_func) if interactive else _missing_input_handler

    def load_items(self) -> list[Path]:
        return [self.dataset_path]

    def process_item(self, item: Path) -> dict[str, Any]:
        result = run_agent_workflow(
            item,
            self.dataset_type,
            metadata=self.metadata,
            reference_path=self.reference_path,
            expected_crs=self.expected_crs,
            issue_report_format=self.issue_report_format,
            issue_report_path=self.issue_report_path,
            final_report_format=self.final_report_format,
            final_report_path=self.final_report_path,
            sample_size=self.sample_size,
            batch_size=self.batch_size,
            validation_chunk_size=self.validation_chunk_size,
            validation_target_vertices_per_chunk=self.validation_target_vertices_per_chunk,
            sleep_between_validation_chunks_seconds=self.sleep_between_validation_chunks_seconds,
            visual_feedback=self.visual_feedback,
            fix_log_path=self.fix_log_path,
            recommendation_hook=self.recommendation_hook,
            post_fix_hook=self.post_fix_hook,
            interactive=self.interactive,
            input_func=self.input_func,
            thermal_guard=self.guard,
        )
        return result.to_dict()


def main() -> None:
    raise SystemExit("Interactive prompts were removed from the core library. Use `python -m geoqa ...` or call the Python API directly.")


__all__ = [
    "AgentRunResult",
    "DATASET_TYPE_LABELS",
    "FixAction",
    "FixSuggestion",
    "GeoQAAgentScript",
    "apply_fixes_interactively",
    "apply_approved_fixes",
    "fix_import_snippets",
    "generate_final_report",
    "generate_agent_report",
    "get_dataset_type",
    "get_fix_suggestion",
    "infer_dataset_type",
    "normalize_dataset_type",
    "review_fixes_on_sample",
    "run_agent_workflow",
    "suggest_fixes",
    "validate_dataset",
    "validate_layer_for_dataset_type",
]


if __name__ == "__main__":
    main()
