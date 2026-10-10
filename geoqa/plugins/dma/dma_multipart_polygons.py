from __future__ import annotations

from typing import Any

from geoqa.plugins.base import GeoQAPlugin
from geoqa.validations.base import ValidationIssue, build_issue

from .common import detect_dma_layer_hints, dissolve_by_normalized_name, normalize_dma_key, row_value, safe_geometry


class DmaMultipartPolygonPlugin(GeoQAPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="dma_multipart_polygons",
            description="Detect same-name DMA layers fragmented into multipart or repeated polygon pieces.",
            version="1",
        )

    def applies_to(self, gdf: Any) -> bool:
        hints = detect_dma_layer_hints(gdf)
        return hints.looks_like_dma_layer and hints.name_field is not None

    def validate(self, gdf: Any) -> list[ValidationIssue]:
        hints = detect_dma_layer_hints(gdf)
        if not self.applies_to(gdf) or hints.name_field is None:
            return []
        issues: list[ValidationIssue] = []
        exploded = gdf.copy()
        try:
            exploded = exploded.explode(index_parts=False)
        except TypeError:
            exploded = exploded.explode()
        counts: dict[str, int] = {}
        representative: dict[str, tuple[Any, Any]] = {}
        for index, row in exploded.iterrows():
            geometry = safe_geometry(row.geometry)
            if geometry is None:
                continue
            name = row_value(row, hints.name_field)
            key = normalize_dma_key(name)
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
            representative.setdefault(key, (index, geometry))
        for key, count in counts.items():
            if count <= 1:
                continue
            index, geometry = representative[key]
            issue = build_issue(
                "dma_multipart_polygon",
                feature_id=index,
                geometry=geometry,
                description=f"DMA polygon group {key!r} is split across {count} polygon parts after explode().",
                solution_hint="Review whether the same-name polygon fragments should be dissolved into a single multipart-safe feature.",
                severity="medium",
            )
            issue.validator_name = self.name
            issue.validator_version = self.version
            issue.provenance = {
                "plugin": self.name,
                "normalized_name": key,
                "part_count": count,
            }
            issues.append(issue)
        return issues

    def fix(self, gdf: Any) -> Any:
        hints = detect_dma_layer_hints(gdf)
        if hints.name_field is None:
            return gdf
        return dissolve_by_normalized_name(gdf, hints.name_field)


__all__ = ["DmaMultipartPolygonPlugin"]
