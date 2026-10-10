from __future__ import annotations

from typing import Any

from .base import GeoQAPlugin

PLUGIN_REGISTRY: dict[str, GeoQAPlugin] = {}
_BUILTINS_LOADED = False


def register_plugin(plugin: GeoQAPlugin) -> None:
    PLUGIN_REGISTRY[plugin.name] = plugin


def clear_plugins() -> None:
    global _BUILTINS_LOADED
    PLUGIN_REGISTRY.clear()
    _BUILTINS_LOADED = False


def _load_builtin_plugins() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    from geoqa.plugins import dma  # noqa: F401

    _BUILTINS_LOADED = True


def get_plugins(*, layer: Any | None = None) -> list[GeoQAPlugin]:
    _load_builtin_plugins()
    plugins = list(PLUGIN_REGISTRY.values())
    if layer is None:
        return plugins
    return [plugin for plugin in plugins if plugin.applies_to(layer)]


__all__ = ["PLUGIN_REGISTRY", "clear_plugins", "get_plugins", "register_plugin"]
