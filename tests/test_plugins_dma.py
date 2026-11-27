from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Polygon

import geoqa
from geoqa.plugins.dma.common import detect_dma_layer_hints
from geoqa.plugins.registry import get_plugins


class _NoOpGuard:
    def wait_until_safe(self, *, stage: str) -> None:
        return None


def _dma_layer(rows: list[dict[str, object]]) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:3857")
    gdf.attrs["source_path"] = "C:/tmp/dma_demo.shp"
    return gdf


class DmaPluginTests(unittest.TestCase):
    def test_detect_dma_hints_finds_name_and_admin_fields(self) -> None:
        gdf = _dma_layer(
            [
                {"DMA_NAME": "Alpha", "office": "North", "geometry": Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])},
            ]
        )
        hints = detect_dma_layer_hints(gdf)
        self.assertEqual(hints.name_field, "DMA_NAME")
        self.assertEqual(hints.admin_field, "office")
        self.assertTrue(hints.looks_like_dma_layer)

    def test_dma_plugins_detect_same_name_and_cross_name_conflicts(self) -> None:
        gdf = _dma_layer(
            [
                {"DMA_NAME": "Alpha", "office": "North", "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])},
                {"DMA_NAME": "Alpha", "office": "North", "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])},
                {"DMA_NAME": "Beta", "office": "North", "geometry": Polygon([(0.2, 0.2), (3.8, 0.2), (3.8, 3.8), (0.2, 3.8)])},
                {"DMA_NAME": "Gamma", "office": "North", "geometry": Polygon([(3, 1), (6, 1), (6, 4), (3, 4)])},
            ]
        )
        plugins = get_plugins(layer=gdf)
        problem_names: list[str] = []
        for plugin in plugins:
            problem_names.extend(issue.problem_name for issue in plugin.validate(gdf))
        self.assertIn("dma_same_name_equal_geometry", problem_names)
        self.assertIn("dma_cross_name_nested_polygon", problem_names)
        self.assertIn("dma_cross_name_overlap", problem_names)

    def test_dma_multipart_plugin_fix_dissolves_same_name_group(self) -> None:
        gdf = _dma_layer(
            [
                {"DMA_NAME": "Alpha", "geometry": Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])},
                {"DMA_NAME": "Alpha", "geometry": Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])},
            ]
        )
        multipart_plugin = next(plugin for plugin in get_plugins(layer=gdf) if plugin.name == "dma_multipart_polygons")
        fixed = multipart_plugin.fix(gdf)
        self.assertEqual(len(fixed), 1)

    def test_geoqa_validate_includes_dma_plugin_issues(self) -> None:
        gdf = _dma_layer(
            [
                {"DMA_NAME": "Alpha", "office": "North", "geometry": Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])},
                {"DMA_NAME": "Beta", "office": "North", "geometry": Polygon([(0.2, 0.2), (3.8, 0.2), (3.8, 3.8), (0.2, 3.8)])},
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "dma.geojson"
            gdf.to_file(dataset_path, driver="GeoJSON")
            with patch("geoqa.execution._resolve_thermal_guard", return_value=_NoOpGuard()):
                report = geoqa.validate(dataset_path, profile="generic_quick")
        self.assertTrue(any(issue.problem_name == "dma_cross_name_nested_polygon" for issue in report.issues))
        self.assertIn("plugin_validators_completed", report.summary)
        self.assertTrue(report.summary["plugin_validators_completed"])


if __name__ == "__main__":
    unittest.main()
