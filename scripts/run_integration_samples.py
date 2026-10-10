from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from geoqa.agent import run_agent_workflow
from geoqa.automation import crs_validation
from geoqa.thermal import ThermalGuard


PUBLIC_SAMPLES = PROJECT_ROOT / "data" / "public_samples"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "integration_results"


PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "natural_earth_admin1_generic": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES
        / "natural_earth"
        / "ne_10m_admin_1_states_provinces"
        / "ne_10m_admin_1_states_provinces.shp",
        "expected_behavior": [
            "Larger admin-boundary shapefile should load successfully.",
            "Generic validation should complete and write both issue and agent reports for a larger polygon dataset.",
        ],
        "kwargs": {
            "dataset_type": "generic",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_admin1_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_admin1_agent"),
            "batch_size": 100,
        },
    },
    "natural_earth_admin1_gpkg_crs": {
        "kind": "crs",
        "dataset_path": PUBLIC_SAMPLES / "derived" / "ne_10m_admin_1_states_provinces.gpkg",
        "expected_behavior": [
            "Derived GeoPackage should load successfully.",
            "CRS validation should complete and write a report for GPKG input.",
        ],
        "kwargs": {
            "expected_crs": "EPSG:4326",
            "output_format": "json",
            "report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_admin1_gpkg_crs"),
            "auto_fix": False,
        },
    },
    "natural_earth_countries_generic": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES
        / "natural_earth"
        / "ne_110m_admin_0_countries"
        / "ne_110m_admin_0_countries.shp",
        "expected_behavior": [
            "Dataset should load successfully.",
            "Generic validation should complete and write both issue and agent reports.",
        ],
        "kwargs": {
            "dataset_type": "generic",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_countries_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_countries_agent"),
            "batch_size": 25,
        },
    },
    "natural_earth_countries_crs": {
        "kind": "crs",
        "dataset_path": PUBLIC_SAMPLES
        / "natural_earth"
        / "ne_110m_admin_0_countries"
        / "ne_110m_admin_0_countries.shp",
        "expected_behavior": [
            "Dataset should load successfully.",
            "CRS validation should complete and write a report even when no issues are found.",
        ],
        "kwargs": {
            "expected_crs": "EPSG:4326",
            "output_format": "json",
            "report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_countries_crs"),
            "auto_fix": False,
        },
    },
    "natural_earth_lakes_generic": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES / "natural_earth" / "ne_10m_lakes" / "ne_10m_lakes.shp",
        "expected_behavior": [
            "Physical/environment-style shapefile should load successfully.",
            "Generic validation should complete and write reports for a moderate polygon dataset.",
        ],
        "kwargs": {
            "dataset_type": "generic",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_lakes_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_lakes_agent"),
            "batch_size": 100,
        },
    },
    "natural_earth_roads_generic": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES / "natural_earth" / "ne_10m_roads" / "ne_10m_roads.shp",
        "expected_behavior": [
            "Larger line dataset should load successfully.",
            "Generic validation should attempt a full run and capture thermal interruptions as structured output if needed.",
        ],
        "kwargs": {
            "dataset_type": "generic",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_roads_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "natural_earth_roads_agent"),
            "batch_size": 250,
        },
    },
    "philly_flood_zones": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES / "data_gov" / "philadelphia_fema_flood_plain_2023.geojson",
        "expected_behavior": [
            "GeoJSON should load successfully.",
            "Flood-zone routing should complete and write reports.",
        ],
        "kwargs": {
            "dataset_type": "flood_zones",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "philly_floodplain_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "philly_floodplain_agent"),
            "batch_size": 100,
        },
    },
    "philly_zoning_land_use": {
        "kind": "agent",
        "dataset_path": PUBLIC_SAMPLES / "data_gov" / "philadelphia_zoning_base_districts.geojson",
        "expected_behavior": [
            "GeoJSON should load successfully.",
            "Land-use validation should attempt a full run and capture thermal interruptions as structured output if needed.",
        ],
        "kwargs": {
            "dataset_type": "land_use",
            "interactive": False,
            "issue_report_format": "json",
            "issue_report_path": str(DEFAULT_OUTPUT_DIR / "philly_zoning_issues"),
            "final_report_format": "json",
            "final_report_path": str(DEFAULT_OUTPUT_DIR / "philly_zoning_agent"),
            "batch_size": 100,
        },
    },
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        return value.item()
    except Exception:
        return str(value)


def _dataset_metrics(dataset_path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "dataset_path": str(dataset_path),
        "file_size_bytes": dataset_path.stat().st_size if dataset_path.exists() else None,
    }
    try:
        import geopandas as gpd
    except ImportError:
        metrics["feature_count"] = None
        metrics["column_count"] = None
        metrics["crs"] = None
        metrics["geometry_types"] = None
        return metrics

    try:
        layer = gpd.read_file(dataset_path)
    except Exception as exc:
        metrics["load_error"] = f"{type(exc).__name__}: {exc}"
        return metrics

    metrics["feature_count"] = len(layer)
    metrics["column_count"] = len(layer.columns)
    metrics["crs"] = str(layer.crs) if getattr(layer, "crs", None) is not None else None
    try:
        metrics["geometry_types"] = {str(key): int(value) for key, value in layer.geometry.geom_type.value_counts().to_dict().items()}
    except Exception:
        metrics["geometry_types"] = None
    return metrics


def _memory_mb() -> float | None:
    try:
        import psutil
    except ImportError:
        return None
    process = psutil.Process()
    return round(process.memory_info().rss / (1024 * 1024), 2)


def _summarize_agent_result(result: Any) -> dict[str, Any]:
    payload = result.to_dict()
    return {
        "dataset_type": payload["dataset_type"],
        "inferred_dataset_type": payload["inferred_dataset_type"],
        "issue_count": len(payload["issues"]),
        "fix_action_count": len(payload["fix_actions"]),
        "messages": payload["messages"],
        "issue_report_path": payload["issue_report_path"],
        "final_report_path": payload["final_report_path"],
        "fix_log_path": payload["fix_log_path"],
    }


def _run_profile(name: str, profile: dict[str, Any], *, guard: ThermalGuard) -> dict[str, Any]:
    dataset_path = Path(profile["dataset_path"])
    expected_behavior = list(profile["expected_behavior"])
    kind = str(profile["kind"])
    kwargs = dict(profile["kwargs"])

    guard.wait_until_safe(stage=f"{name}_pre")
    started = time.perf_counter()
    memory_before_mb = _memory_mb()
    status = "ok"
    result_payload: dict[str, Any] | None = None
    error_message: str | None = None

    try:
        if kind == "agent":
            result_payload = _summarize_agent_result(run_agent_workflow(dataset_path, **kwargs))
        elif kind == "crs":
            result_payload = _json_safe(crs_validation(dataset_path, **kwargs))
        else:
            raise ValueError(f"Unsupported profile kind: {kind!r}")
    except Exception as exc:
        status = "error"
        error_message = f"{type(exc).__name__}: {exc}"

    elapsed = round(time.perf_counter() - started, 3)
    memory_after_mb = _memory_mb()
    cooldown_snapshot = guard.cool_down_if_needed(stage=f"{name}_post")

    run_record: dict[str, Any] = {
        "name": name,
        "status": status,
        "run_date": time.strftime("%Y-%m-%d"),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": elapsed,
        "memory_before_mb": memory_before_mb,
        "memory_after_mb": memory_after_mb,
        "expected_behavior": expected_behavior,
        "dataset_metrics": _dataset_metrics(dataset_path),
        "thermal_snapshot_post": {
            "max_temp_c": cooldown_snapshot.max_temp_c,
            "avg_temp_c": cooldown_snapshot.avg_temp_c,
            "sensor_count": cooldown_snapshot.sensor_count,
            "source": cooldown_snapshot.source,
        },
    }
    if result_payload is not None:
        run_record["result"] = result_payload
    if error_message is not None:
        run_record["error"] = error_message
    return run_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GeoQA integration sample workflows with lightweight metrics.")
    parser.add_argument(
        "--profile",
        dest="profiles",
        action="append",
        help="Run only the named profile. May be supplied multiple times.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR / "integration_summary.json"),
        help="Path to the JSON summary file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_names = args.profiles or list(PROFILE_DEFINITIONS.keys())
    unknown = [name for name in selected_names if name not in PROFILE_DEFINITIONS]
    if unknown:
        raise SystemExit(f"Unknown profile(s): {', '.join(unknown)}")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    guard = ThermalGuard.strict(log_path=output_path.parent / "thermal_log.jsonl")
    results = [_run_profile(name, PROFILE_DEFINITIONS[name], guard=guard) for name in selected_names]

    payload = {
        "run_date": time.strftime("%Y-%m-%d"),
        "profiles": results,
    }
    output_path.write_text(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
