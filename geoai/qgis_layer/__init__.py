from __future__ import annotations

import json
from typing import Any


try:
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer  # type: ignore

    HAS_PYQGIS = True
except ImportError:
    QgsFeature = Any  # type: ignore[assignment]
    QgsGeometry = Any  # type: ignore[assignment]
    QgsVectorLayer = Any  # type: ignore[assignment]
    HAS_PYQGIS = False


def is_pyqgis_available() -> bool:
    """Return True when PyQGIS is importable in the current environment."""
    return HAS_PYQGIS


def _ensure_geojson_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    if hasattr(value, "asJson"):
        return json.loads(value.asJson())
    raise RuntimeError(
        "PyQGIS is not available and the provided object is not already a GeoJSON "
        "dict, JSON string, or geometry-like object exposing asJson()."
    )


def geometry_to_geojson(geometry: Any) -> dict[str, Any]:
    """
    Convert a QGIS geometry or GeoJSON-compatible object into a GeoJSON dict.

    Works with:
    - `QgsGeometry`
    - GeoJSON dicts
    - JSON strings
    - geometry-like objects exposing `asJson()`
    """
    return _ensure_geojson_dict(geometry)


def geometry_to_coordinate_array(geometry: Any) -> Any:
    """Return the GeoJSON `coordinates` payload for a geometry-like object."""
    geojson = geometry_to_geojson(geometry)
    return geojson.get("coordinates")


def feature_to_record(feature: Any) -> dict[str, Any]:
    """
    Convert a QGIS-like feature into a GeoJSON Feature dict.

    The function also accepts duck-typed objects that expose the same feature
    methods used by PyQGIS (`geometry`, `fields`, `attributes`, `id`).
    """
    if not hasattr(feature, "geometry"):
        raise RuntimeError(
            "PyQGIS feature conversion requires a feature-like object exposing geometry()."
        )

    geometry = feature.geometry()
    geometry_dict = geometry_to_geojson(geometry) if geometry is not None else None

    field_names: list[str] = []
    if hasattr(feature, "fields"):
        try:
            field_names = [field.name() for field in feature.fields()]
        except Exception:
            field_names = []

    attributes: list[Any] = []
    if hasattr(feature, "attributes"):
        try:
            attributes = list(feature.attributes())
        except Exception:
            attributes = []

    if field_names and attributes:
        properties = {name: attributes[idx] if idx < len(attributes) else None for idx, name in enumerate(field_names)}
    else:
        properties = {f"field_{idx}": value for idx, value in enumerate(attributes)}

    feature_id = None
    if hasattr(feature, "id"):
        try:
            feature_id = feature.id()
        except Exception:
            feature_id = None

    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": geometry_dict,
        "properties": properties,
    }


def layer_to_feature_dicts(layer: Any) -> list[dict[str, Any]]:
    """
    Convert a QGIS-like layer into a list of GeoJSON Feature dicts.

    Works with:
    - `QgsVectorLayer`
    - layer-like objects exposing `getFeatures()`
    """
    if not hasattr(layer, "getFeatures"):
        raise RuntimeError(
            "PyQGIS layer conversion requires a layer-like object exposing getFeatures()."
        )
    return [feature_to_record(feature) for feature in layer.getFeatures()]


def convert_qgis_layer_to_geojson(qgis_layer: Any) -> dict[str, Any]:
    """
    Convert a QGIS-like layer into a GeoJSON FeatureCollection dict.

    This complements `layer_to_feature_dicts` with a more direct, prompt-friendly
    wrapper for end users expecting a single GeoJSON payload.
    """
    return {
        "type": "FeatureCollection",
        "features": layer_to_feature_dicts(qgis_layer),
    }


__all__ = [
    "HAS_PYQGIS",
    "convert_qgis_layer_to_geojson",
    "feature_to_record",
    "geometry_to_coordinate_array",
    "geometry_to_geojson",
    "is_pyqgis_available",
    "layer_to_feature_dicts",
]
