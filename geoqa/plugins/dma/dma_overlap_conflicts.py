from __future__ import annotations

from typing import Any

from geoqa.plugins.base import GeoQAPlugin
from geoqa.validations.base import ValidationIssue, build_issue

from .common import detect_dma_layer_hints, normalize_dma_key, row_value, safe_geometry


class DmaOverlapConflictPlugin(GeoQAPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="dma_overlap_conflicts",
            description="Detect overlapping cross-name DMA polygons including partial overlaps.",
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
        records: list[tuple[Any, Any, str, Any, Any]] = []
        for index, row in gdf.iterrows():
            geometry = safe_geometry(row.geometry)
            if geometry is None or getattr(geometry, "area", 0.0) <= 0:
                continue
            name = row_value(row, hints.name_field)
            admin_value = row_value(row, hints.admin_field)
            records.append((index, name, normalize_dma_key(name), admin_value, geometry))

        for left_pos, (left_index, left_name, left_key, left_admin, left_geom) in enumerate(records):
            for right_index, right_name, right_key, right_admin, right_geom in records[left_pos + 1 :]:
                if not left_key or not right_key or left_key == right_key:
                    continue
                if hints.admin_field and left_admin not in {None, ""} and right_admin not in {None, ""} and left_admin != right_admin:
                    continue
                try:
                    overlap = left_geom.intersection(right_geom)
                except Exception:
                    continue
                overlap_area = getattr(overlap, "area", 0.0)
                if overlap is None or getattr(overlap, "is_empty", True) or overlap_area < 1.0:
                    continue
                left_fraction = overlap_area / left_geom.area if left_geom.area else 0.0
                right_fraction = overlap_area / right_geom.area if right_geom.area else 0.0
                if max(left_fraction, right_fraction) >= 0.995:
                    continue
                issue = build_issue(
                    "dma_cross_name_overlap",
                    feature_id=left_index,
                    geometry=overlap,
                    description=(
                        f"Cross-name DMA polygons {left_index!r} ({left_name}) and {right_index!r} ({right_name}) "
                        f"partially overlap by area {overlap_area:.4f}."
                    ),
                    solution_hint="Review which polygon should own the overlap and resolve it by subtraction or controlled merge.",
                    severity="high",
                )
                issue.validator_name = self.name
                issue.validator_version = self.version
                issue.provenance = {
                    "plugin": self.name,
                    "left_name": str(left_name),
                    "right_name": str(right_name),
                    "relation": "PARTIAL",
                    "admin_group": left_admin if hints.admin_field else None,
                    "intersection_area": round(overlap_area, 6),
                    "left_fraction": round(left_fraction, 6),
                    "right_fraction": round(right_fraction, 6),
                }
                issues.append(issue)
        return issues


__all__ = ["DmaOverlapConflictPlugin"]
