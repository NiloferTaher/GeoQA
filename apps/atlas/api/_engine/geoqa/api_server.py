"""GeoQA backend API server for the Atlas frontend.

Implements the HTTP endpoints consumed by ``apps/atlas/src/api.ts``:

- ``GET /api/datasets``          - list demo datasets
- ``GET /api/datasets/{id}``     - get dataset metadata
- ``GET /api/datasets/{id}/geojson`` - dataset GeoJSON
- ``GET /api/datasets/{id}/cleaned-geojson`` - cleaned layer GeoJSON
- ``GET /api/datasets/{id}/report`` - validation report
- ``GET /api/datasets/{id}/issues`` - validation issues
- ``GET /api/thermal``           - CPU thermal status
- ``POST /api/preview-layer``    - preview an uploaded vector file
- ``POST /api/run-qa``           - run GeoQA validation on an uploaded file

Run locally:

    pip install fastapi uvicorn python-multipart
    python -m geoqa.api_server

Or via the console script:

    geoqa-server
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from geoqa.api import GeoQAReport, validate, score
from geoqa.conversion import (
    default_vector_layer_name,
    export_vector_layer,
    layer_preview_geojson,
    list_vector_layers,
    load_vector_dataset,
    table_preview_frame,
)
from geoqa.execution import ValidationExecutionResult
from geoqa.fixes import apply_basic_geometry_fixes
from geoqa.thermal import (
    TemperatureSnapshot,
    ThermalGuard,
    read_temperature_snapshot,
)
from geoqa.validations.base import ValidationIssue


app = FastAPI(title="GeoQA Backend API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "geoqa_api_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _save_upload_body(request: Request, filename: str) -> Path:
    body = await request.body()
    suffix = Path(filename or "upload").suffix
    dest = _UPLOAD_DIR / f"{int(time.time() * 1000)}_{os.getpid()}{suffix}"
    dest.write_bytes(body)
    return dest, filename


def _geom_to_geojson(geom: Any) -> Any:
    if geom is None:
        return None
    try:
        return geom.__geo_interface__
    except Exception:
        return None


def _issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "issue_id": getattr(issue, "issue_id", None),
        "problem_name": getattr(issue, "problem_name", ""),
        "severity": getattr(issue, "severity", ""),
        "description": getattr(issue, "description", ""),
        "solution_hint": getattr(issue, "solution_hint", None),
        "feature_id": getattr(issue, "feature_id", None),
        "related_feature_id": getattr(issue, "related_feature_id", None),
        "endpoint_a": getattr(issue, "endpoint_a", None),
        "endpoint_b": getattr(issue, "endpoint_b", None),
        "distance": getattr(issue, "distance", None),
        "tolerance": getattr(issue, "tolerance", None),
        "distance_units": getattr(issue, "distance_units", None),
        "label": getattr(issue, "label", None),
        "geometry": _geom_to_geojson(getattr(issue, "geometry", None)),
        "issue_class": getattr(issue, "issue_class", None),
        "provenance": getattr(issue, "provenance", None),
        "priority_score": getattr(issue, "priority_score", None),
    }


def _thermal_status() -> dict[str, Any]:
    try:
        snapshot: TemperatureSnapshot = read_temperature_snapshot()
    except Exception:
        return {
            "source": "unavailable",
            "max_temp_c": None,
            "avg_temp_c": None,
            "sensor_count": 0,
            "warn_temp_c": 78.0,
            "hard_temp_c": 88.0,
            "status": "unavailable",
            "can_run": True,
            "message": "CPU temperature is unavailable. Atlas can run QA but cannot show live heat.",
        }
    max_temp = snapshot.max_temp_c
    warn_temp = 78.0
    hard_temp = 88.0
    if max_temp is None:
        status = "unavailable"
        can_run = True
        message = "CPU temperature is unavailable. Atlas can run QA but cannot show live heat."
    elif max_temp >= hard_temp:
        status = "hot"
        can_run = False
        message = f"CPU is hot ({round(max_temp)} C). QA runs are paused until it cools."
    elif max_temp >= warn_temp:
        status = "warm"
        can_run = True
        message = f"CPU is warm ({round(max_temp)} C). QA can run but monitor heat."
    else:
        status = "ok"
        can_run = True
        message = f"CPU clear ({round(max_temp)} C)."
    return {
        "source": snapshot.source,
        "max_temp_c": max_temp,
        "avg_temp_c": snapshot.avg_temp_c,
        "sensor_count": snapshot.sensor_count,
        "warn_temp_c": warn_temp,
        "hard_temp_c": hard_temp,
        "status": status,
        "can_run": can_run,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Demo dataset endpoints (static / read-only)
# ---------------------------------------------------------------------------

_DEMO_DATASETS: list[dict[str, Any]] = []


@app.get("/api/datasets")
def list_datasets() -> dict[str, Any]:
    # Demo datasets are shipped as static files by the Atlas frontend. Returning
    # 404 lets the frontend fall back to its bundled demo data instead of
    # rendering an empty catalog.
    raise HTTPException(status_code=404, detail="Demo datasets are served as static files by GeoQA Atlas.")


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")


@app.get("/api/datasets/{dataset_id}/geojson")
def get_dataset_geojson(dataset_id: str):
    raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")


@app.get("/api/datasets/{dataset_id}/cleaned-geojson")
def get_cleaned_geojson(dataset_id: str):
    raise HTTPException(status_code=404, detail=f"Cleaned layer for {dataset_id} not found.")


@app.get("/api/datasets/{dataset_id}/report")
def get_report(dataset_id: str):
    raise HTTPException(status_code=404, detail=f"Report for {dataset_id} not found.")


@app.get("/api/datasets/{dataset_id}/issues")
def get_issues(dataset_id: str):
    raise HTTPException(status_code=404, detail=f"Issues for {dataset_id} not found.")


# ---------------------------------------------------------------------------
# Thermal
# ---------------------------------------------------------------------------

@app.get("/api/thermal")
def thermal() -> dict[str, Any]:
    return _thermal_status()


# ---------------------------------------------------------------------------
# Upload + validation
# ---------------------------------------------------------------------------

@app.post("/api/preview-layer")
async def preview_layer(
    request: Request,
    filename: str = Query(default=""),
    layer: str = Query(default=""),
) -> dict[str, Any]:
    name = filename or "upload"
    saved, _ = await _save_upload_body(request, name)
    try:
        available_layers = list_vector_layers(saved)
        if not available_layers:
            raise HTTPException(
                status_code=400,
                detail="No readable vector layers found in this file.",
            )

        selected = layer or default_vector_layer_name(available_layers)
        if selected not in available_layers:
            selected = available_layers[0]

        gdf = load_vector_dataset(saved, ogr_layer=selected)

        features = []
        for _, row in gdf.iterrows():
            geom = row.get("geometry")
            if geom is None:
                continue
            try:
                gj = geom.__geo_interface__
            except Exception:
                continue
            props = {k: v for k, v in row.items() if k != "geometry"}
            features.append(
                {
                    "type": "Feature",
                    "geometry": gj,
                    "properties": props,
                }
            )

        collection = {"type": "FeatureCollection", "features": features}

        layer_infos = []
        for idx, layer_name in enumerate(available_layers):
            layer_infos.append(
                {
                    "name": layer_name,
                    "path": layer_name,
                    "feature_count": len(gdf),
                    "geometry_type": None,
                    "is_valid": True,
                }
            )

        return {
            "collection": collection,
            "label": f"{len(features)} features loaded from {name}.",
            "note": f"Detected {len(available_layers)} layer(s).",
            "layers": layer_infos,
            "detected_layer_count": len(available_layers),
            "selected_layer": selected,
            "can_run_all_layers": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read layer preview: {exc}")


@app.post("/api/run-qa")
async def run_qa(
    request: Request,
    filename: str = Query(default=""),
    profile: str = Query(default="generic_quick"),
    layer: str = Query(default=""),
) -> dict[str, Any]:
    name = filename or "upload"
    saved, _ = await _save_upload_body(request, name)
    start = time.perf_counter()

    try:
        ogr_layer = layer or None
        gdf = load_vector_dataset(saved, ogr_layer=ogr_layer)

        report = validate(saved, profile=profile, ogr_layer=ogr_layer)
        assert isinstance(report, GeoQAReport)

        issues = [_issue_to_dict(issue) for issue in report.issues]
        feature_count = len(gdf) if hasattr(gdf, "__len__") else 0

        geometry_type = None
        try:
            geometry_values = getattr(gdf, "geometry", None)
            if geometry_values is not None and len(geometry_values):
                geometry_type = str(geometry_values.geom_type.value_counts().index[0])
        except Exception:
            geometry_type = None

        issue_overlay = {
            "type": "FeatureCollection",
            "features": [],
        }
        for issue in report.issues:
            geom = getattr(issue, "geometry", None)
            if geom is None:
                continue
            issue_overlay["features"].append(
                {
                    "type": "Feature",
                    "geometry": _geom_to_geojson(geom),
                    "properties": {
                        "issue_id": getattr(issue, "issue_id", None),
                        "problem_name": getattr(issue, "problem_name", ""),
                        "severity": getattr(issue, "severity", ""),
                        "feature_id": getattr(issue, "feature_id", None),
                        "description": getattr(issue, "description", ""),
                    },
                }
            )

        summary = report.summary or {}
        top_issues = summary.get("top_issues", [])
        if isinstance(top_issues, list):
            top_issues = [
                {"problem_name": t.get("problem_name", ""), "count": t.get("count", 0), "percent": t.get("percent", 0)}
                for t in top_issues
            ]

        thermal = _thermal_status()

        duration = round(time.perf_counter() - start, 4)

        return {
            "profile": profile,
            "feature_count": feature_count,
            "issue_count": len(issues),
            "analysisMode": "full_loaded_layer",
            "featuresLoaded": feature_count,
            "featuresAnalyzed": feature_count,
            "analysisLimit": feature_count,
            "fullLayerValidated": True,
            "geometryType": geometry_type,
            "samplePolicy": "full_layer",
            "summary": {
                "total_issues": len(issues),
                "issue_count": len(issues),
                "actionable": sum(1 for i in issues if i.get("severity") in {"critical", "high"}),
                "informational": 0,
                "actionable_ratio": 0.0,
                "top_issues": top_issues,
                "severity_distribution": [],
                "by_problem": {},
            },
            "thermal": thermal,
            "issues": issues,
            "issue_overlay": issue_overlay,
            "report": {
                "dataset_id": name,
                "issue_count": len(issues),
                "summary": summary,
                "issues": issues,
            },
            "messages": [],
            "completed": True,
            "execution_status": "full",
            "operator_next_steps": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"GeoQA validation failed: {exc}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


def main() -> None:
    """Console script entry point: ``geoqa-server``."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
