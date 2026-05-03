from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoqa.validations.base import ValidationIssue


def validation_issues_to_geojson(issues: list[ValidationIssue]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for issue in issues:
        geometry = issue.to_dict().get("geometry")
        feature: dict[str, Any] = {
            "type": "Feature",
            "geometry": geometry if isinstance(geometry, dict) else None,
            "properties": {
                "problem_name": issue.problem_name,
                "severity": issue.severity,
                "description": issue.description,
                "solution_hint": issue.solution_hint,
                "feature_id": issue.feature_id,
            },
        }
        if geometry is None and isinstance(issue.geometry, str):
            feature["properties"]["geometry_wkt"] = issue.geometry
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def build_validation_results_pyqgis_script(
    issues: list[ValidationIssue],
    *,
    layer_name: str = "GeoQA Validation Results",
) -> str:
    payload = validation_issues_to_geojson(issues)
    payload_json = json.dumps(payload, ensure_ascii=True, indent=2)
    return f"""from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsProject, QgsVectorLayer
from PyQt5.QtCore import QVariant
import json

payload = json.loads(r'''{payload_json}''')
layer = QgsVectorLayer("None?crs=EPSG:4326", {layer_name!r}, "memory")
provider = layer.dataProvider()
provider.addAttributes([
    QgsField("problem", QVariant.String),
    QgsField("severity", QVariant.String),
    QgsField("feature_id", QVariant.String),
    QgsField("description", QVariant.String),
    QgsField("solution", QVariant.String),
    QgsField("geometry_wkt", QVariant.String),
])
layer.updateFields()

for item in payload["features"]:
    feat = QgsFeature(layer.fields())
    props = item.get("properties", {{}})
    feat["problem"] = str(props.get("problem_name", ""))
    feat["severity"] = str(props.get("severity", ""))
    feat["feature_id"] = str(props.get("feature_id", ""))
    feat["description"] = str(props.get("description", ""))
    feat["solution"] = str(props.get("solution_hint", ""))
    feat["geometry_wkt"] = str(props.get("geometry_wkt", ""))
    geometry = item.get("geometry")
    if geometry:
        feat.setGeometry(QgsGeometry.fromGeoJson(json.dumps(geometry).encode("utf-8")))
    provider.addFeature(feat)

layer.updateExtents()
QgsProject.instance().addMapLayer(layer)
"""


def export_validation_results_pyqgis_script(
    issues: list[ValidationIssue],
    output_path: str | Path,
    *,
    layer_name: str = "GeoQA Validation Results",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_validation_results_pyqgis_script(issues, layer_name=layer_name), encoding="utf-8")
    return path


__all__ = [
    "build_validation_results_pyqgis_script",
    "export_validation_results_pyqgis_script",
    "validation_issues_to_geojson",
]
