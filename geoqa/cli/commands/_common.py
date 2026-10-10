from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from geoqa.thermal import ThermalGuard
from geoqa.validation_runtime import FileValidationCache, ValidationLimits, ValidationProgressEvent


def build_limits(args: Any) -> ValidationLimits | None:
    if args.max_features is None and args.max_size_mb is None:
        return None
    return ValidationLimits(max_features=args.max_features, max_source_size_mb=args.max_size_mb)


def build_cache(args: Any) -> FileValidationCache | None:
    if not getattr(args, "cache", None):
        return None
    return FileValidationCache(Path(args.cache))


def thermal_guard_name(name: str) -> ThermalGuard:
    normalized = name.strip().lower()
    if normalized == "balanced":
        return ThermalGuard.balanced()
    if normalized == "cool":
        return ThermalGuard.cool()
    if normalized == "strict":
        return ThermalGuard.strict()
    raise ValueError(f"Unsupported thermal profile: {name!r}")


def progress_printer(enabled: bool):
    if not enabled:
        return None

    def emit(event: ValidationProgressEvent) -> None:
        cache_suffix = " cache-hit" if event.cache_hit else ""
        issue_suffix = f" issues={event.issue_count}" if event.issue_count is not None else ""
        progress_suffix = f" progress={event.progress_percent:.1f}%" if event.progress_percent is not None else ""
        eta_suffix = f" eta={event.eta_seconds:.1f}s" if event.eta_seconds is not None else ""
        chunk_suffix = ""
        if event.chunk_index is not None and event.chunk_total is not None:
            chunk_suffix = f" chunk={event.chunk_index}/{event.chunk_total}"
        if event.message:
            issue_suffix += f" note={event.message}"
        print(
            f"[{event.index}/{event.total}] {event.status} {event.validator_name}{cache_suffix}{issue_suffix}{progress_suffix}{eta_suffix}{chunk_suffix}"
        )

    return emit


def progress_printer_with_interval(enabled: bool, interval_seconds: float | None):
    printer = progress_printer(enabled)
    if printer is None:
        return None
    last_emit = {"time": 0.0}

    def emit(event: ValidationProgressEvent) -> None:
        now = time.perf_counter()
        if interval_seconds and interval_seconds > 0 and event.status == "started" and last_emit["time"] > 0:
            if (now - last_emit["time"]) < interval_seconds:
                return
        printer(event)
        last_emit["time"] = now

    return emit


def apply_low_resource_defaults(args: Any, *, command_name: str) -> None:
    if not getattr(args, "low_resource", False):
        return
    if getattr(args, "max_workers", None) is None:
        args.max_workers = 1
    if getattr(args, "chunk_size", None) is None:
        args.chunk_size = 750 if command_name == "validate" else 500
    if getattr(args, "sleep", 0.0) == 0.0:
        args.sleep = 1.5
    if getattr(args, "thermal_profile", None) == "balanced":
        args.thermal_profile = "cool"
    if getattr(args, "max_runtime_seconds", None) is None:
        args.max_runtime_seconds = 180.0 if command_name == "validate" else 120.0
    if getattr(args, "progress", False) is False:
        args.progress = True
    if getattr(args, "progress_interval_seconds", None) is None:
        args.progress_interval_seconds = 5.0


__all__ = [
    "apply_low_resource_defaults",
    "build_cache",
    "build_limits",
    "progress_printer",
    "progress_printer_with_interval",
    "thermal_guard_name",
]
