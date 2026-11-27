"""Shared utilities for GeoQA Atlas Vercel API handlers."""

from __future__ import annotations

import json
import math
import os
os.environ.setdefault("OSM_USE_CUSTOM_INDEXING", "NO")
import struct
import sys
import tempfile
import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make the vendored geoqa engine importable
# ---------------------------------------------------------------------------

_API_DIR = Path(__file__).resolve().parent
_ENGINE_DIR = _API_DIR / "_engine"
for _candidate in (_ENGINE_DIR, _API_DIR / "api", _API_DIR, Path(__file__).resolve().parents[1]):
    _candidate_str = str(_candidate)
    if _candidate.exists() and _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)

try:
    import geoqa  # noqa: F401
    from geoqa.execution import validate_dataset_with_profile
    from geoqa.conversion import (
        default_vector_layer_name,
        list_vector_layers,
        load_vector_dataset,
    )
    from geoqa.api import GeoQAReport
    from geoqa.thermal import read_temperature_snapshot
    _GEOQA_AVAILABLE = True
except Exception:  # pragma: no cover - engine missing in some environments
    validate_dataset_with_profile = None  # type: ignore[assignment]
    default_vector_layer_name = None  # type: ignore[assignment]
    list_vector_layers = None  # type: ignore[assignment]
    load_vector_dataset = None  # type: ignore[assignment]
    GeoQAReport = None  # type: ignore[assignment]
    read_temperature_snapshot = None  # type: ignore[assignment]
    _GEOQA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.getenv("GEOQA_ATLAS_DATA", APP_ROOT / "public" / "demo-data")).resolve()
CONFIG_PATH = _API_DIR / "datasets.json"
MAX_PREVIEW_FEATURES = 5000
MAX_UPLOAD_BYTES = 1200 * 1024 * 1024
UPLOAD_REPORT_LIMIT = 200
UPLOAD_RUNTIME_SECONDS = 75.0

ATLAS_THERMAL_WARN_TEMP_C = float(os.getenv("GEOQA_ATLAS_THERMAL_WARN_C", "78"))
ATLAS_THERMAL_HARD_TEMP_C = float(os.getenv("GEOQA_ATLAS_THERMAL_HARD_C", "88"))

PREFERRED_LAYER_TERMS = ("pipes", "network", "assets", "hps", "dma", "aio", "boundaries", "parcels")

SHAPE_TYPE_NAMES = {
    0: "Null", 1: "Point", 3: "PolyLine", 5: "Polygon", 8: "MultiPoint",
    11: "PointZ", 13: "PolyLineZ", 15: "PolygonZ", 18: "MultiPointZ",
    21: "PointM", 23: "PolyLineM", 25: "PolygonM", 28: "MultiPointM", 31: "MultiPatch",
}


def _json_response(payload: Any, status: int = 200) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
        "body": json.dumps(payload, default=str, allow_nan=False),
    }


def _error_response(message: str, status: int = 400) -> dict[str, Any]:
    return _json_response({"detail": message}, status=status)


def _options_response() -> dict[str, Any]:
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        },
        "body": "",
    }


# ---------------------------------------------------------------------------
# Dataset config
# ---------------------------------------------------------------------------

def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"datasets": []}
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    datasets = payload.get("datasets", [])
    if not isinstance(datasets, list):
        return {"datasets": []}
    return {"datasets": datasets}


def _safe_data_path(relative_path: str) -> Path:
    path = (DATA_ROOT / relative_path).resolve()
    try:
        path.relative_to(DATA_ROOT)
    except ValueError:
        raise ValueError("Dataset asset path is invalid.")
    if not path.exists():
        raise FileNotFoundError("Dataset asset is missing.")
    return path


def _public_dataset(dataset: dict[str, Any], *, include_summary: bool = False) -> dict[str, Any]:
    cleaned_path = dataset.get("cleaned_geojson") or dataset.get("cleanedGeoJsonPath")
    has_cleaned_layer = bool(dataset.get("has_cleaned_layer", dataset.get("hasCleanedLayer", cleaned_path)))
    cleaned_note = dataset.get("cleaned_layer_note") or dataset.get("cleanedLayerNote")
    if not cleaned_note:
        cleaned_note = (
            "Cleaned preview available for supported geometry fixes only."
            if has_cleaned_layer
            else "No cleaned layer is available for this demo."
        )
    payload = {
        "id": dataset["id"],
        "name": dataset["name"],
        "short_name": dataset.get("short_name", dataset["name"]),
        "description": dataset["description"],
        "feature_count": dataset["feature_count"],
        "geometry_type": dataset["geometry_type"],
        "profile": dataset["profile"],
        "issue_count": dataset["issue_count"],
        "has_cleaned_layer": has_cleaned_layer,
        "hasCleanedLayer": has_cleaned_layer,
        "cleaned_layer_note": cleaned_note,
        "cleanedLayerNote": cleaned_note,
        "command": dataset["command"],
        "github_url": dataset["github_url"],
        "source_label": dataset["source_label"],
        "source_url": dataset["source_url"],
        "bounds": dataset.get("bounds"),
        "geojson": dataset.get("geojson"),
        "report": dataset.get("report"),
        "issues": dataset.get("issues"),
        "cleaned_geojson": cleaned_path,
        "cleanedGeoJsonPath": cleaned_path,
    }
    if cleaned_path:
        payload["cleaned_geojson"] = cleaned_path
        payload["cleanedGeoJsonPath"] = cleaned_path
    if include_summary:
        try:
            payload["summary"] = read_summary(_safe_data_path(dataset["report"]))
        except Exception:
            payload["summary"] = {"issue_count": dataset.get("issue_count", 0)}
    return payload


# ---------------------------------------------------------------------------
# Thermal
# ---------------------------------------------------------------------------

def _read_atlas_thermal_status() -> dict[str, Any]:
    try:
        if read_temperature_snapshot is not None:
            snapshot = read_temperature_snapshot()
        else:
            raise ImportError("geoqa thermal not available")
    except Exception:
        return {
            "source": "unavailable",
            "max_temp_c": None,
            "avg_temp_c": None,
            "sensor_count": 0,
            "warn_temp_c": ATLAS_THERMAL_WARN_TEMP_C,
            "hard_temp_c": ATLAS_THERMAL_HARD_TEMP_C,
            "status": "unavailable",
            "can_run": True,
            "message": "CPU temperature is unavailable. Atlas can run QA but cannot show live heat.",
        }

    max_temp = snapshot.max_temp_c
    if max_temp is None:
        status = "unavailable"
        can_run = True
        message = "CPU temperature is unavailable. Atlas can run QA but cannot show live heat."
    elif max_temp >= ATLAS_THERMAL_HARD_TEMP_C:
        status = "hot"
        can_run = False
        message = (
            f"CPU temperature is {max_temp:.0f} C. Run QA is paused until the CPU cools below "
            f"{ATLAS_THERMAL_HARD_TEMP_C:.0f} C."
        )
    elif max_temp >= ATLAS_THERMAL_WARN_TEMP_C:
        status = "warm"
        can_run = True
        message = f"CPU temperature is {max_temp:.0f} C. Atlas will run carefully and keep showing live heat."
    else:
        status = "ok"
        can_run = True
        message = f"CPU temperature is {max_temp:.0f} C. Atlas is clear to run QA."

    return {
        "source": snapshot.source,
        "max_temp_c": max_temp,
        "avg_temp_c": snapshot.avg_temp_c,
        "sensor_count": snapshot.sensor_count,
        "warn_temp_c": ATLAS_THERMAL_WARN_TEMP_C,
        "hard_temp_c": ATLAS_THERMAL_HARD_TEMP_C,
        "status": status,
        "can_run": can_run,
        "message": message,
    }


# ---------------------------------------------------------------------------
# GeoJSON / shapefile preview helpers
# ---------------------------------------------------------------------------

def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    try:
        json.dumps(value, allow_nan=False)
        return value
    except TypeError:
        return str(value)
    except ValueError:
        return None


def _json_safe_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in properties.items()}


def _issue_feature(issue: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from shapely import wkt
        from shapely.geometry import mapping
    except Exception:
        return None
    geometry_value = issue.get("geometry")
    geometry_payload = None
    if isinstance(geometry_value, dict):
        geometry_payload = geometry_value
    elif isinstance(geometry_value, str) and geometry_value.strip():
        try:
            geometry_payload = mapping(wkt.loads(geometry_value))
        except Exception:
            geometry_payload = None
    if geometry_payload is None:
        return None
    return {
        "type": "Feature",
        "properties": {
            "issue_id": issue.get("issue_id"),
            "problem_name": issue.get("problem_name"),
            "severity": issue.get("severity"),
            "feature_id": issue.get("feature_id"),
            "description": issue.get("description"),
            "solution_hint": issue.get("solution_hint"),
            "issue_class": issue.get("issue_class"),
        },
        "geometry": geometry_payload,
    }


def _issue_overlay(issues: list[dict[str, Any]]) -> dict[str, Any]:
    features = [feature for issue in issues if (feature := _issue_feature(issue)) is not None]
    return {"type": "FeatureCollection", "features": features}


def _limit_feature_collection(collection: dict[str, Any]) -> dict[str, Any]:
    features = collection.get("features")
    if not isinstance(features, list) or len(features) <= MAX_PREVIEW_FEATURES:
        return collection
    limited = dict(collection)
    limited["features"] = features[:MAX_PREVIEW_FEATURES]
    return limited


def _preview_geojson(data: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except Exception:
        raise ValueError("Upload a GeoJSON FeatureCollection or zipped Shapefile.")
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("Upload a GeoJSON FeatureCollection or zipped Shapefile.")
    total = len(payload["features"])
    collection = _limit_feature_collection(payload)
    shown = len(collection.get("features", []))
    note = f"Preview limited to {shown:,} features for map speed." if shown < total else ""
    return {
        "collection": collection,
        "label": f"{shown:,} features loaded from GeoJSON.",
        "note": note,
    }


# ---------------------------------------------------------------------------
# Shapefile helpers (pyshp)
# ---------------------------------------------------------------------------

def _coordinate_transformer(path: Path):
    prj_path = path.with_suffix(".prj")
    if not prj_path.exists():
        return None
    try:
        from pyproj import CRS, Transformer
        source_crs = CRS.from_wkt(prj_path.read_text(encoding="utf-8", errors="ignore"))
        target_crs = CRS.from_epsg(4326)
        if source_crs.equals(target_crs):
            return None
        return Transformer.from_crs(source_crs, target_crs, always_xy=True)
    except Exception:
        return None


def _transform_coordinates(value: Any, transformer):
    if (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        x, y = transformer.transform(value[0], value[1])
        if len(value) > 2:
            return [x, y, *value[2:]]
        return [x, y]
    if isinstance(value, (list, tuple)):
        return [_transform_coordinates(item, transformer) for item in value]
    return value


def _transform_geometry(geometry: dict[str, Any], transformer):
    if transformer is None:
        return geometry
    transformed = dict(geometry)
    if transformed.get("type") == "GeometryCollection":
        geometries = transformed.get("geometries")
        if isinstance(geometries, list):
            transformed["geometries"] = [
                _transform_geometry(item, transformer) if isinstance(item, dict) else item
                for item in geometries
            ]
        return transformed
    if "coordinates" in transformed:
        transformed["coordinates"] = _transform_coordinates(transformed["coordinates"], transformer)
    return transformed


def _feature_collection_preview(path: Path):
    import shapefile
    reader = None
    try:
        reader = shapefile.Reader(str(path), encoding="utf-8", encodingErrors="replace")
        field_names = [field[0] for field in reader.fields if field[0] != "DeletionFlag"]
        features: list[dict[str, Any]] = []
        geometry_types: dict[str, int] = {}
        total = len(reader)
        skipped_preview_features = 0
        transformer = _coordinate_transformer(path)
        for index in range(total):
            if len(features) >= MAX_PREVIEW_FEATURES:
                break
            try:
                shape = reader.shape(index)
                geometry = shape.__geo_interface__
            except Exception:
                skipped_preview_features += 1
                continue
            if not geometry or geometry.get("type") == "Null":
                skipped_preview_features += 1
                continue
            geometry_type = str(geometry.get("type", "Unknown"))
            geometry_types[geometry_type] = geometry_types.get(geometry_type, 0) + 1
            try:
                properties = _json_safe_properties(dict(zip(field_names, list(reader.record(index)))))
            except Exception:
                properties = {"feature_id": index}
            geometry = _transform_geometry(geometry, transformer)
            features.append({"type": "Feature", "properties": properties, "geometry": geometry})
        ranked_types = sorted(geometry_types.items(), key=lambda item: (-item[1], item[0]))
        fallback_type = getattr(reader, "shapeTypeName", None)
        geometry_type = ranked_types[0][0] if ranked_types else str(fallback_type) if fallback_type else None
        collection: dict[str, Any] = {"type": "FeatureCollection", "features": features}
        if skipped_preview_features:
            collection["preview_skipped_features"] = skipped_preview_features
        return collection, total, geometry_type
    finally:
        if reader is not None:
            reader.close()


def _inspect_zipped_shapefile_header(archive: zipfile.ZipFile, name: str, lower_names: dict[str, str]):
    lower = name.lower()
    base = lower[:-4]
    geometry_type = None
    feature_count = None
    try:
        with archive.open(name) as handle:
            header = handle.read(36)
        if len(header) >= 36:
            shape_type = struct.unpack("<i", header[32:36])[0]
            geometry_type = SHAPE_TYPE_NAMES.get(shape_type, f"ShapeType {shape_type}")
    except Exception:
        geometry_type = None
    shx_member = lower_names.get(f"{base}.shx")
    if shx_member:
        try:
            shx_info = archive.getinfo(shx_member)
            if shx_info.file_size >= 100:
                feature_count = int((shx_info.file_size - 100) / 8)
        except Exception:
            feature_count = None
    return feature_count, geometry_type


def _recommended_profile(layer_name: str, geometry_type: str | None):
    normalized_name = layer_name.lower()
    normalized_geometry = (geometry_type or "").lower()
    if normalized_geometry in {"point", "pointz", "pointm", "multipoint", "multipointz", "multipointm"}:
        if any(term in normalized_name for term in ("meter", "valve", "hydrant", "chamber", "asset", "customer", "leak", "sensor", "flow")):
            return "point_asset_quick", "Point asset layer name matched asset delivery terms."
        return "generic_quick", "Point layer without a specialized name uses generic quick QA."
    if normalized_geometry in {"polyline", "polylinez", "polylinem", "linestring", "multilinestring"}:
        if any(term in normalized_name for term in ("pipe", "network", "main", "service", "line", "route", "road", "lateral")):
            return "water_network_quick", "Line layer name matched water network delivery terms."
        return "line_network_quick", "Line layer uses line network quick QA."
    if normalized_geometry in {"polygon", "polygonz", "polygonm", "multipolygon"}:
        if any(term in normalized_name for term in ("dma", "boundary", "zone", "parcel", "aoi", "district", "admin", "hps")):
            return "boundaries_quick", "Polygon layer name matched boundary or zone delivery terms."
        return "generic_quick", "Polygon layer without a specialized name uses generic quick QA."
    return "generic_quick", "Unknown geometry type uses generic quick QA."


def _shapefile_layers(archive: zipfile.ZipFile):
    names = [name for name in archive.namelist() if not name.endswith("/")]
    lower_names = {name.lower(): name for name in names}
    layers: list[dict[str, Any]] = []
    for name in sorted((item for item in names if item.lower().endswith(".shp")), key=str.lower):
        lower = name.lower()
        base = lower[:-4]
        has_required_sidecars = f"{base}.dbf" in lower_names and f"{base}.shx" in lower_names
        info: dict[str, Any] = {
            "name": Path(name).with_suffix("").as_posix(),
            "path": name,
            "is_valid": has_required_sidecars,
            "feature_count": None,
            "geometry_type": None,
        }
        if has_required_sidecars:
            try:
                feature_count, geometry_type = _inspect_zipped_shapefile_header(archive, name, lower_names)
                info["feature_count"] = feature_count
                info["geometry_type"] = geometry_type
            except Exception:
                info["is_valid"] = False
        recommended_profile, profile_reason = _recommended_profile(str(info["name"]), info.get("geometry_type"))
        info["recommended_profile"] = recommended_profile
        info["profile_reason"] = profile_reason
        layers.append(info)
    return layers, lower_names


def _layer_score(layer: dict[str, Any]):
    feature_count = int(layer.get("feature_count") or 0)
    normalized_name = f"{layer.get('name', '')} {layer.get('path', '')}".lower()
    preferred_name_score = 1 if any(term in normalized_name for term in PREFERRED_LAYER_TERMS) else 0
    return (
        1 if layer.get("is_valid") else 0,
        1 if feature_count > 0 else 0,
        feature_count,
        preferred_name_score,
    )


def _default_layer_name(layers: list[dict[str, Any]]):
    usable = [layer for layer in layers if layer.get("is_valid")]
    if not usable:
        raise ValueError("This zip did not include a readable Shapefile layer.")
    return str(max(usable, key=_layer_score)["name"])


def _resolve_layer_name(layers: list[dict[str, Any]], requested: str | None):
    if requested:
        for layer in layers:
            if requested == layer.get("name") or requested == layer.get("path"):
                if not layer.get("is_valid"):
                    raise ValueError("The selected Shapefile layer is not readable.")
                return str(layer["name"])
        raise ValueError("The selected Shapefile layer was not found in this ZIP.")
    return _default_layer_name(layers)


def _extract_layer(archive: zipfile.ZipFile, layer_name: str, lower_names: dict[str, str], target_root: Path):
    selected = None
    for member in archive.namelist():
        if member.endswith("/"):
            continue
        if Path(member).with_suffix("").as_posix() == layer_name and member.lower().endswith(".shp"):
            selected = member
            break
    if selected is None:
        raise ValueError("The selected Shapefile layer was not found in this ZIP.")
    selected_base = selected.lower()[:-4]
    layer_dir = target_root / "selected_shapefile"
    layer_dir.mkdir(parents=True, exist_ok=True)
    selected_shp = layer_dir / Path(selected).name
    for extension in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        member = lower_names.get(f"{selected_base}{extension}")
        if member:
            (layer_dir / Path(member).name).write_bytes(archive.read(member))
    return selected_shp


def _write_geojson_upload(data: bytes, filename: str, upload_root: Path):
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except Exception:
        raise ValueError("Upload a GeoJSON FeatureCollection or zipped Shapefile.")
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("Upload a GeoJSON FeatureCollection or zipped Shapefile.")
    suffix = ".geojson" if filename.lower().endswith(".geojson") else ".json"
    target = upload_root / f"uploaded{suffix}"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _preview_shapefile_zip(data: bytes, filename: str, layer: str | None = None):
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("Upload a valid zipped Shapefile.")
    layers, lower_names = _shapefile_layers(archive)
    if not layers:
        raise ValueError("This zip did not include any .shp layers.")
    if layer is None and len(layers) > 1:
        return {
            "collection": {"type": "FeatureCollection", "features": []},
            "label": "Choose a Shapefile layer to preview.",
            "note": f"Detected {len(layers)} Shapefile layers in this ZIP. Select one layer before Atlas loads it on the map.",
            "layers": layers,
            "detected_layer_count": len(layers),
            "selected_layer": "",
            "can_run_all_layers": False,
        }
    selected_name = _resolve_layer_name(layers, layer)
    with tempfile.TemporaryDirectory(prefix="geoqa_atlas_preview_") as temp_dir:
        temp_root = Path(temp_dir)
        selected_path = _extract_layer(archive, selected_name, lower_names, temp_root)
        try:
            collection, total, _ = _feature_collection_preview(selected_path)
        except Exception:
            raise ValueError("GeoQA Atlas could not read this Shapefile layer.")
    shown = len(collection.get("features", []))
    skipped = int(collection.get("preview_skipped_features", 0))
    layer_count = len(layers)
    note = f"Detected {layer_count} Shapefile layers in this ZIP. Atlas is previewing selected layer {selected_name}."
    if shown < total:
        note = f"{note} Preview limited to {shown:,} features for map speed."
    if skipped:
        note = f"{note} {skipped:,} empty or unreadable preview records were skipped."
    return {
        "collection": collection,
        "label": f"{shown:,} features loaded from selected Shapefile layer.",
        "note": note,
        "layers": layers,
        "detected_layer_count": layer_count,
        "selected_layer": selected_name,
        "can_run_all_layers": False,
    }


def _materialize_upload(data: bytes, filename: str, upload_root: Path, layer: str | None):
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("This file is too large for the local Atlas QA demo.")
    lower = filename.lower()
    if lower.endswith(".zip"):
        import shapefile  # noqa: F401
        archive = zipfile.ZipFile(BytesIO(data))
        layers, lower_names = _shapefile_layers(archive)
        if not layers:
            raise ValueError("This zip did not include any .shp layers.")
        selected_name = _resolve_layer_name(layers, layer)
        selected_path = _extract_layer(archive, selected_name, lower_names, upload_root)
        return selected_path, f"Validated selected layer {selected_name} from {len(layers)} detected Shapefile layers."
    if lower.endswith(".csv") or lower.endswith(".osm") or lower.endswith(".pbf") or lower.endswith(".osm.pbf"):
        suffix = Path(filename).suffix or ".csv"
        target = upload_root / f"uploaded{suffix}"
        target.write_bytes(data)
        return target, f"Validated uploaded {suffix.lstrip('.').upper()} layer."
    target = _write_geojson_upload(data, filename, upload_root)
    return target, "Validated uploaded GeoJSON layer."


def _load_geoqa_runner():
    if validate_dataset_with_profile is None:
        raise ValueError("The local GeoQA Python engine is not available to this Atlas build.")
    return validate_dataset_with_profile


def _atlas_validation_error_message(exc: Exception) -> str:
    message = str(exc)
    if "float() argument must be a string or a real number, not 'NoneType'" in message:
        return (
            "GeoQA validation could not complete because sampled features include malformed or empty coordinates. "
            "Try another layer or run GeoQA locally for full-layer diagnostics."
        )
    return f"GeoQA validation could not complete. {message}"


def read_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {
            "issue_count": len(payload),
            "summary": _fallback_summary(payload),
            "issues": payload,
        }
    return payload


def read_issues(path: Path) -> list[dict[str, Any]]:
    payload = read_report(path)
    issues = payload.get("issues", [])
    if isinstance(issues, list):
        return [dict(issue) for issue in issues]
    return []


def read_summary(path: Path) -> dict[str, Any]:
    payload = read_report(path)
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return dict(summary)
    return _fallback_summary(payload.get("issues", []))


def _fallback_summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    by_problem: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for issue in issues:
        problem = str(issue.get("problem_name", "unknown"))
        severity = str(issue.get("severity", "unknown"))
        by_problem[problem] = by_problem.get(problem, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    total = len(issues)
    top_issues = [
        {"problem_name": name, "count": count, "percent": round((count / total) * 100, 2) if total else 0}
        for name, count in sorted(by_problem.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    severity_distribution = [
        {"name": name, "count": count, "percent": round((count / total) * 100, 2) if total else 0}
        for name, count in sorted(by_severity.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "issue_count": total,
        "total_issues": total,
        "by_problem": by_problem,
        "by_severity": by_severity,
        "top_issues": top_issues,
        "severity_distribution": severity_distribution,
    }


# ---------------------------------------------------------------------------
# Vercel runtime adapter
# ---------------------------------------------------------------------------

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


def _make_vercel_handler(handle_func):
    class _VercelHandler(BaseHTTPRequestHandler):
        def _request(self):
            parsed = urlparse(self.path)
            query_map = parse_qs(parsed.query)

            class _Query:
                def get(self, key, default=None):
                    values = query_map.get(key)
                    if not values:
                        return default
                    return values[0]

            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""

            class _Request:
                method = self.command
                path = self.path
                query = _Query()
                body = body

            return _Request()

        def _dispatch(self):
            request = self._request()
            result = handle_func(request) or {}
            status = int(result.get("statusCode", 200))
            headers = result.get("headers") or {}
            body = result.get("body", "")
            if isinstance(body, str):
                body_bytes = body.encode("utf-8")
            else:
                body_bytes = body or b""
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(str(key), str(value))
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            if body_bytes:
                self.wfile.write(body_bytes)

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_OPTIONS(self):
            self._dispatch()

        def log_message(self, *args, **kwargs):
            return

    return _VercelHandler



from urllib.parse import urlparse, parse_qs


def _parse_vercel_request(vercel_handler):
    parsed = urlparse(vercel_handler.path)
    query_map = parse_qs(parsed.query)

    class _Query:
        def get(self, key, default=None):
            values = query_map.get(key)
            if not values:
                return default
            return values[0]

    length = int(vercel_handler.headers.get("Content-Length") or 0)
    body = vercel_handler.rfile.read(length) if length > 0 else b""

    class _Request:
        method = vercel_handler.command
        path = vercel_handler.path
        query = _Query()

    request = _Request()
    request.body = body
    return request


def _write_vercel_response(vercel_handler, result):
    result = result or {}
    status = int(result.get("statusCode", 200))
    headers = result.get("headers") or {}
    body = result.get("body", "")
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body or b""
    vercel_handler.send_response(status)
    for key, value in headers.items():
        vercel_handler.send_header(str(key), str(value))
    vercel_handler.send_header("Content-Length", str(len(body_bytes)))
    vercel_handler.end_headers()
    if body_bytes:
        vercel_handler.wfile.write(body_bytes)

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args, **kwargs):
        return
