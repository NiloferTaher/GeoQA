from __future__ import annotations

from typing import Any

from geoqa.plugins.base import GeoQAPlugin
from geoqa.validations.base import ValidationIssue, build_issue

from .common import (
    detect_dma_layer_hints,
    equalsish,
    normalize_dma_key,
    overlap_fraction,
    pick_best_index,
    row_value,
    safe_geometry,
)


class DmaCrossNameNestedPlugin(GeoQAPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="dma_cross_name_nested",
            description="Detect cross-name DMA polygons that are effectively equal or nested.",
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
        seen_small_ids: set[Any] = set()
        records: list[tuple[Any, Any, str, Any, Any, Any]] = []
        for index, row in gdf.iterrows():
            name = row_value(row, hints.name_field)
            geometry = safe_geometry(row.geometry)
            if geometry is None or getattr(geometry, "area", 0.0) <= 0:
                continue
            admin_value = row_value(row, hints.admin_field)
            records.append((index, name, normalize_dma_key(name), admin_value, geometry, row))

        for left_pos, (left_index, left_name, left_key, left_admin, left_geom, left_row) in enumerate(records):
            for right_index, right_name, right_key, right_admin, right_geom, right_row in records[left_pos + 1 :]:
                if not left_key or not right_key or left_key == right_key:
                    continue
                if hints.admin_field and left_admin not in {None, ""} and right_admin not in {None, ""} and left_admin != right_admin:
                    continue
                small_index = pick_best_index(left_index, right_index)
                if equalsish(left_geom, right_geom):
                    if small_index in seen_small_ids:
                        continue
                    seen_small_ids.add(small_index)
                    issue = build_issue(
                        "dma_cross_name_equal_geometry",
                        feature_id=small_index,
                        geometry=left_geom,
                        description=(
                            f"Cross-name DMA polygons {left_index!r} ({left_name}) and {right_index!r} ({right_name}) "
                            "are geometrically equal."
                        ),
                        solution_hint="Review whether the names represent the same DMA and reconcile the naming conflict before retaining one geometry.",
                        severity="high",
                    )
                    issue.validator_name = self.name
                    issue.validator_version = self.version
                    issue.provenance = {
                        "plugin": self.name,
                        "left_name": str(left_name),
                        "right_name": str(right_name),
                        "relation": "EQUAL",
                        "admin_group": left_admin if hints.admin_field else None,
                    }
                    issues.append(issue)
                    continue

                left_in_right = overlap_fraction(left_geom, right_geom)
                right_in_left = overlap_fraction(right_geom, left_geom)
                nested_fraction = max(left_in_right, right_in_left)
                if nested_fraction < 0.995:
                    continue
                if small_index in seen_small_ids:
                    continue
                seen_small_ids.add(small_index)
                issue = build_issue(
                    "dma_cross_name_nested_polygon",
                    feature_id=small_index,
                    geometry=left_geom if left_in_right >= right_in_left else right_geom,
                    description=(
                        f"Cross-name DMA polygons {left_index!r} ({left_name}) and {right_index!r} ({right_name}) "
                        f"are nested at {nested_fraction:.4f} overlap."
                    ),
                    solution_hint="Inspect the naming conflict and nested geometry before merging, subtracting, or retiring one polygon.",
                    severity="high",
                )
                issue.validator_name = self.name
                issue.validator_version = self.version
                issue.provenance = {
                    "plugin": self.name,
                    "left_name": str(left_name),
                    "right_name": str(right_name),
                    "relation": "NESTED",
                    "admin_group": left_admin if hints.admin_field else None,
                    "overlap_fraction": round(nested_fraction, 6),
                }
                issues.append(issue)
        return issues


__all__ = ["DmaCrossNameNestedPlugin"]
