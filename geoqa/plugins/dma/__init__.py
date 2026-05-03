from __future__ import annotations

from geoqa.plugins.registry import register_plugin

from .dma_cross_name_nested import DmaCrossNameNestedPlugin
from .dma_multipart_polygons import DmaMultipartPolygonPlugin
from .dma_overlap_conflicts import DmaOverlapConflictPlugin
from .dma_same_name_nested import DmaSameNameNestedPlugin

_PLUGINS = (
    DmaSameNameNestedPlugin(),
    DmaCrossNameNestedPlugin(),
    DmaOverlapConflictPlugin(),
    DmaMultipartPolygonPlugin(),
)

for plugin in _PLUGINS:
    register_plugin(plugin)

__all__ = [
    "DmaCrossNameNestedPlugin",
    "DmaMultipartPolygonPlugin",
    "DmaOverlapConflictPlugin",
    "DmaSameNameNestedPlugin",
]
