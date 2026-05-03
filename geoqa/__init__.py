"""GeoQA public package surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.3.0"

from . import expect, thermal
from .api import GeoQAReport, score, validate
from .expect import *  # noqa: F401,F403

_COMPAT_EXPORTS = {
    "GeoQAScriptBase": ("geoqa.script_base", "GeoQAScriptBase"),
    "ThermalGuard": ("geoqa.thermal", "ThermalGuard"),
    "ThermalLimitExceeded": ("geoqa.thermal", "ThermalLimitExceeded"),
    "read_cpu_temps_c": ("geoqa.thermal", "read_cpu_temps_c"),
    "run_temperature_diagnostic": ("geoqa.thermal", "run_temperature_diagnostic"),
    "ThermalRunner": ("geoqa.runner", "ThermalRunner"),
    "StepResult": ("geoqa.runner", "StepResult"),
    "ValidationExecutionResult": ("geoqa.execution", "ValidationExecutionResult"),
    "validate_dataset_with_profile": ("geoqa.execution", "validate_dataset_with_profile"),
    "get_plugins": ("geoqa.plugins.registry", "get_plugins"),
}

__all__ = [
    "__version__",
    "GeoQAReport",
    "check",
    "expect",
    "no_null_geometry",
    "no_self_intersections",
    "score",
    "valid_crs",
    "validate",
]


def __getattr__(name: str) -> Any:
    if name in _COMPAT_EXPORTS:
        module_name, attribute_name = _COMPAT_EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'geoqa' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(list(globals()) + list(__all__) + list(_COMPAT_EXPORTS)))
