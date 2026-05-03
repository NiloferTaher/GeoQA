from __future__ import annotations

from typing import Any

from geoqa.plugins.base import GeoQAPlugin
from geoqa.validations.base import ValidationIssue, build_issue

from .common import (
    detect_dma_layer_hints,
    dissolve_by_normalized_name,
    equalsish,
    normalize_dma_key,
    overlap_fraction,
    pick_best_index,
    row_value,
    safe_geometry,
)


class DmaSameNameNestedPlugin(GeoQAPlugin):
    def __init__(self) -> None:
        super().__init__(
            name="dma_same_name_nested",
            description="Detect same-name DMA polygon duplicates and near-contained variants.",
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
        records: list[tuple[Any, Any, Any, Any, Any]] = []
        for index, row in gdf.iterrows():
            name = row_value(row, hints.name_field)
            geometry = safe_geometry(row.geometry)
            if geometry is None or getattr(geometry, "area", 0.0) <= 0:
                continue
            records.append((index, name, normalize_dma_key(name), geometry, row))

        for left_pos, (left_index, left_name, left_key, left_geom, left_row) in enumerate(records):
            if not left_key:
                continue
            for right_index, right_name, right_key, right_geom, right_row in records[left_pos + 1 :]:
                if left_key != right_key:
                    continue
                small_index = pick_best_index(left_index, right_index)
                if equalsish(left_geom, right_geom):
                    if small_index in seen_small_ids:
                        continue
                    seen_small_ids.add(small_index)
                    issue = build_issue(
                        "dma_same_name_equal_geometry",
                        feature_id=small_index,
                        geometry=left_geom,
                        description=(
                            f"Same-name DMA polygons {left_index!r} and {right_index!r} are geometrically equal "
                            f"for normalized key {left_key!r}."
                        ),
                        solution_hint="Review whether the same-name polygons should be dissolved into a single retained feature.",
                        severity="high",
                    )
                    issue.validator_name = self.name
                    issue.validator_version = self.version
                    issue.provenance = {
                        "plugin": self.name,
                        "left_name": str(left_name),
                        "right_name": str(right_name),
                        "relation": "EQUAL",
                        "normalized_name": left_key,
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
                    "dma_same_name_nested_polygon",
                    feature_id=small_index,
                    geometry=left_geom if left_in_right >= right_in_left else right_geom,
                    description=(
                        f"Same-name DMA polygons {left_index!r} and {right_index!r} are nested at "
                        f"{nested_fraction:.4f} overlap for normalized key {left_key!r}."
                    ),
                    solution_hint="Inspect the duplicate same-name polygons and dissolve or remove the smaller duplicate if appropriate.",
                    severity="high",
                )
                issue.validator_name = self.name
                issue.validator_version = self.version
                issue.provenance = {
                    "plugin": self.name,
                    "left_name": str(left_name),
                    "right_name": str(right_name),
                    "relation": "NESTED",
                    "normalized_name": left_key,
                    "overlap_fraction": round(nested_fraction, 6),
                }
                issues.append(issue)
        return issues

    def fix(self, gdf: Any) -> Any:
        hints = detect_dma_layer_hints(gdf)
        if hints.name_field is None:
            return gdf
        return dissolve_by_normalized_name(gdf, hints.name_field)


__all__ = ["DmaSameNameNestedPlugin"]
