from __future__ import annotations

import ctypes
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


FILE_MAP_READ = 0x0004
if sys.platform == "win32":
    from ctypes import wintypes

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _OPEN_FILE_MAPPING = _KERNEL32.OpenFileMappingW
    _MAP_VIEW_OF_FILE = _KERNEL32.MapViewOfFile
    _UNMAP_VIEW_OF_FILE = _KERNEL32.UnmapViewOfFile
    _CLOSE_HANDLE = _KERNEL32.CloseHandle

    _OPEN_FILE_MAPPING.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _OPEN_FILE_MAPPING.restype = wintypes.HANDLE
    _MAP_VIEW_OF_FILE.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_size_t,
    ]
    _MAP_VIEW_OF_FILE.restype = ctypes.c_void_p
    _UNMAP_VIEW_OF_FILE.argtypes = [ctypes.c_void_p]
    _UNMAP_VIEW_OF_FILE.restype = wintypes.BOOL
    _CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _CLOSE_HANDLE.restype = wintypes.BOOL
else:
    _KERNEL32 = None
    _OPEN_FILE_MAPPING = None
    _MAP_VIEW_OF_FILE = None
    _UNMAP_VIEW_OF_FILE = None
    _CLOSE_HANDLE = None


class ThermalLimitExceeded(RuntimeError):
    """Raised when the configured thermal ceiling is exceeded."""


@dataclass(slots=True)
class TemperatureSnapshot:
    max_temp_c: float | None
    avg_temp_c: float | None
    sensor_count: int
    source: str


@dataclass(slots=True)
class TemperatureDiagnostic:
    ok: bool
    platform: str
    source: str
    temperatures_c: list[float]
    message: str
    options: list[str]


def _read_coretemp_mapping() -> list[float]:
    """Read CPU temperatures from Core Temp shared memory on Windows only."""
    if sys.platform != "win32":
        return []

    handle = _OPEN_FILE_MAPPING(FILE_MAP_READ, False, "CoreTempMappingObject")
    if not handle:
        return []

    ptr = _MAP_VIEW_OF_FILE(handle, FILE_MAP_READ, 0, 0, 4096)
    if not ptr:
        _CLOSE_HANDLE(handle)
        return []

    try:
        buf = ctypes.string_at(ptr, 4096)
        ints = [struct.unpack_from("<i", buf, i * 4)[0] for i in range(1024)]
        n = ints[384] if len(ints) > 384 else 0
        if not (1 <= n <= 128):
            n = 32
        vals: list[float] = []
        for i in range(386, min(386 + n + 8, 1024)):
            temp_c = struct.unpack_from("<f", buf, i * 4)[0]
            if 0.0 < temp_c < 130.0:
                vals.append(float(temp_c))
        return vals
    finally:
        _UNMAP_VIEW_OF_FILE(ctypes.c_void_p(ptr))
        _CLOSE_HANDLE(handle)


def _read_psutil_temp() -> list[float]:
    """Read CPU temperatures using psutil on Windows, macOS, or Linux when sensors are exposed."""
    try:
        import psutil  # type: ignore
    except Exception:
        return []

    try:
        sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
    except Exception:
        return []

    vals: list[float] = []
    for entries in sensors.values():
        for entry in entries:
            current = getattr(entry, "current", None)
            if isinstance(current, (int, float)) and 0.0 < float(current) < 130.0:
                vals.append(float(current))
    return vals


def _diagnostic_options() -> list[str]:
    options: list[str] = []
    if sys.platform == "win32":
        options.append("Start Core Temp so GeoQA can read the Core Temp shared-memory mapping.")
        options.append("If Core Temp is not available, install psutil and use OS-exposed CPU sensors.")
        options.append("Some Windows systems do not expose CPU package temperatures to psutil.")
        return options

    if sys.platform == "darwin":
        options.append("Install psutil if it is not already installed.")
        options.append("macOS often does not expose CPU temperature sensors through psutil by default.")
        options.append("If no sensors are exposed, use a machine-specific monitoring tool and keep GeoQA in cooperative guard mode.")
        return options

    options.append("Install psutil if it is not already installed.")
    options.append("On Linux, confirm that system temperature sensors are exposed to the current user.")
    options.append("If needed, enable sensors with lm-sensors or your distribution's hardware monitoring stack.")
    return options


def run_temperature_diagnostic() -> TemperatureDiagnostic:
    """
    Perform a live temperature probe and explain whether GeoQA can read CPU temperatures.

    Platform behavior:
    - Windows with Core Temp: checks Core Temp shared memory first.
    - Windows without Core Temp: checks psutil sensor readings.
    - macOS/Linux: checks psutil sensor readings only.
    """
    coretemp_vals = _read_coretemp_mapping()
    if coretemp_vals:
        return TemperatureDiagnostic(
            ok=True,
            platform=sys.platform,
            source="coretemp",
            temperatures_c=coretemp_vals,
            message=(
                f"Live CPU temperature reads are available via Core Temp "
                f"({len(coretemp_vals)} sensor reading(s) detected)."
            ),
            options=["Continue using the thermal guard with Core Temp as the preferred backend."],
        )

    psutil_vals = _read_psutil_temp()
    if psutil_vals:
        return TemperatureDiagnostic(
            ok=True,
            platform=sys.platform,
            source="psutil",
            temperatures_c=psutil_vals,
            message=(
                f"Live CPU temperature reads are available via psutil "
                f"({len(psutil_vals)} sensor reading(s) detected)."
            ),
            options=["Continue using the thermal guard with psutil-backed sensor reads."],
        )

    if sys.platform == "win32":
        message = (
            "No live CPU temperature readings are available. Core Temp was not detected and "
            "psutil did not return any CPU temperature sensors."
        )
    elif sys.platform == "darwin":
        message = (
            "No live CPU temperature readings are available. psutil did not return any CPU "
            "temperature sensors on this macOS machine."
        )
    else:
        message = (
            "No live CPU temperature readings are available. psutil did not return any CPU "
            "temperature sensors on this Linux/Unix machine."
        )

    return TemperatureDiagnostic(
        ok=False,
        platform=sys.platform,
        source="unavailable",
        temperatures_c=[],
        message=message,
        options=_diagnostic_options(),
    )


def read_cpu_temps_c() -> list[float]:
    """
    Return CPU temperatures in Celsius.

    Platform behavior:
    - Windows with Core Temp: uses Core Temp shared memory first.
    - Windows without Core Temp: falls back to psutil sensor readings.
    - macOS/Linux: uses psutil sensor readings only.
    """
    vals = _read_coretemp_mapping()
    if vals:
        return vals
    return _read_psutil_temp()


def read_temperature_snapshot() -> TemperatureSnapshot:
    """
    Return a summarized temperature snapshot for the current machine.

    Platform behavior:
    - Windows with Core Temp: prefers Core Temp shared memory.
    - Windows without Core Temp: uses psutil.
    - macOS/Linux: uses psutil only.
    """
    vals = _read_coretemp_mapping()
    source = "coretemp" if vals else "psutil"
    if not vals:
        vals = _read_psutil_temp()
    if not vals:
        return TemperatureSnapshot(max_temp_c=None, avg_temp_c=None, sensor_count=0, source="unavailable")
    return TemperatureSnapshot(
        max_temp_c=max(vals),
        avg_temp_c=sum(vals) / len(vals),
        sensor_count=len(vals),
        source=source,
    )


class ThermalGuard:
    """
    Cooperative thermal guard for long-running GeoQA scripts.

    This reduces thermal pressure by pausing before expensive work and aborting
    if the CPU is already beyond the configured hard ceiling. It cannot provide
    a physical guarantee that the machine will never spike above the limit.

    Platform behavior:
    - Windows with Core Temp: prefers Core Temp shared memory.
    - Windows without Core Temp: uses psutil sensor readings.
    - macOS/Linux: uses psutil sensor readings only.
    """

    def __init__(
        self,
        *,
        warn_temp_c: float = 68.0,
        max_temp_c: float = 74.0,
        cooldown_seconds: float = 15.0,
        check_interval_seconds: float = 5.0,
        max_wait_seconds: float = 300.0,
        log_path: str | Path | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if warn_temp_c >= max_temp_c:
            raise ValueError("warn_temp_c must be lower than max_temp_c")
        self.warn_temp_c = float(warn_temp_c)
        self.max_temp_c = float(max_temp_c)
        self.cooldown_seconds = float(cooldown_seconds)
        self.check_interval_seconds = float(check_interval_seconds)
        self.max_wait_seconds = float(max_wait_seconds)
        self.log_path = Path(log_path) if log_path else None
        self._sleep = sleep_fn

    @classmethod
    def balanced(cls, **kwargs: object) -> "ThermalGuard":
        """Return a guard using the project-balanced defaults."""
        return cls(**kwargs)

    @classmethod
    def cool(cls, **kwargs: object) -> "ThermalGuard":
        """Return a more conservative guard for machines that heat up quickly."""
        defaults = {
            "warn_temp_c": 66.0,
            "max_temp_c": 72.0,
            "cooldown_seconds": 20.0,
            "check_interval_seconds": 6.0,
            "max_wait_seconds": 600.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)

    @classmethod
    def strict(cls, **kwargs: object) -> "ThermalGuard":
        """Return a strict guard intended for heat-sensitive local runs."""
        defaults = {
            "warn_temp_c": 64.0,
            "max_temp_c": 70.0,
            "cooldown_seconds": 25.0,
            "check_interval_seconds": 8.0,
            "max_wait_seconds": 900.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)

    def snapshot(self) -> TemperatureSnapshot:
        return read_temperature_snapshot()

    def _append_log(self, event: dict[str, object]) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=True) + "\n")

    def _log_event(self, action: str, snapshot: TemperatureSnapshot, *, stage: str, waited_seconds: float) -> None:
        self._append_log(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "action": action,
                "stage": stage,
                "waited_seconds": round(waited_seconds, 2),
                "warn_temp_c": self.warn_temp_c,
                "max_temp_c": self.max_temp_c,
                "max_observed_temp_c": snapshot.max_temp_c,
                "avg_observed_temp_c": snapshot.avg_temp_c,
                "sensor_count": snapshot.sensor_count,
                "source": snapshot.source,
            }
        )

    def wait_until_safe(self, *, stage: str = "preflight") -> TemperatureSnapshot:
        waited = 0.0
        while True:
            snap = self.snapshot()
            current = snap.max_temp_c

            if current is None:
                self._log_event("sensor_unavailable", snap, stage=stage, waited_seconds=waited)
                return snap

            if current >= self.max_temp_c:
                self._log_event("blocked", snap, stage=stage, waited_seconds=waited)
                if waited >= self.max_wait_seconds:
                    raise ThermalLimitExceeded(
                        f"CPU temperature is {current:.1f} C, still above hard limit {self.max_temp_c:.1f} C "
                        f"after waiting {waited:.1f}s."
                    )
                self._sleep(self.cooldown_seconds)
                waited += self.cooldown_seconds
                continue

            if current >= self.warn_temp_c:
                self._log_event("throttle_wait", snap, stage=stage, waited_seconds=waited)
                if waited >= self.max_wait_seconds:
                    return snap
                self._sleep(self.check_interval_seconds)
                waited += self.check_interval_seconds
                continue

            self._log_event("continue", snap, stage=stage, waited_seconds=waited)
            return snap

    def check_or_raise(self, *, stage: str = "runtime") -> TemperatureSnapshot:
        snap = self.snapshot()
        current = snap.max_temp_c
        if current is not None and current >= self.max_temp_c:
            self._log_event("raise", snap, stage=stage, waited_seconds=0.0)
            raise ThermalLimitExceeded(
                f"CPU temperature is {current:.1f} C, above limit {self.max_temp_c:.1f} C."
            )
        self._log_event("checked", snap, stage=stage, waited_seconds=0.0)
        return snap

    def cool_down_if_needed(self, *, stage: str = "cooldown") -> TemperatureSnapshot:
        """
        Force a cooldown pass after work if the current reading is still above the warning threshold.

        This is still cooperative, but it reduces the chance of immediately starting the next chunk
        while the CPU is already running hot.
        """
        snap = self.snapshot()
        current = snap.max_temp_c
        if current is None or current < self.warn_temp_c:
            self._log_event("cooldown_not_needed", snap, stage=stage, waited_seconds=0.0)
            return snap
        self._log_event("cooldown_begin", snap, stage=stage, waited_seconds=0.0)
        return self.wait_until_safe(stage=stage)

    def guard_step(self, func: Callable[..., object], /, *args: object, stage: str = "step", **kwargs: object) -> object:
        self.wait_until_safe(stage=stage)
        result = func(*args, **kwargs)
        self.check_or_raise(stage=f"{stage}_post")
        return result

    def __enter__(self) -> "ThermalGuard":
        self.wait_until_safe(stage="enter")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._log_event("exit", self.snapshot(), stage="exit", waited_seconds=0.0)
        return None


__all__ = [
    "TemperatureDiagnostic",
    "TemperatureSnapshot",
    "ThermalGuard",
    "ThermalLimitExceeded",
    "read_cpu_temps_c",
    "read_temperature_snapshot",
    "run_temperature_diagnostic",
]
