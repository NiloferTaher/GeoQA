from __future__ import annotations

from typing import Any


def agentic_crsfix(layer: Any, crs_format: Any = "EPSG:4326") -> Any:
    """
    Reproject a layer when its CRS does not match the requested CRS.

    This is a lightweight wrapper for user-facing agentic cleanup workflows.
    """
    current_crs = getattr(layer, "crs", None)
    if current_crs == crs_format:
        return layer
    if not hasattr(layer, "to_crs"):
        raise RuntimeError("CRS fixing requires a layer-like object exposing to_crs().")
    return layer.to_crs(crs_format)


__all__ = ["agentic_crsfix"]
