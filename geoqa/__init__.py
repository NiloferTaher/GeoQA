"""GeoQA public package surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.4.0"

from . import expect, hitl, proj_env, thermal
from .api import GeoQAReport, score, validate
from .reports.geojson import errors_summary, issues_to_geojson
from .expect import *  # noqa: F401,F403
from .hitl import Gate as HITL

# PROJ repair is deliberately NOT run at import time: importing a library must
# not mutate the process environment. The repair is triggered lazily by the
# functions that actually need a CRS (geoqa.conversion.gpd_read,
# geoqa.conversion.load_vector_dataset, geoqa.validation_runtime.execute_validation_plan),
# or explicitly via geoqa.proj_env.ensure_proj().

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
    "HITL",
    "__version__",
    "GeoQAReport",
    "check",
    "errors_summary",
    "expect",
    "hitl",
    "issues_to_geojson",
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
