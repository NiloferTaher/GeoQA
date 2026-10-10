"""Hardware reality, and whether a GIS operation should be attempted on this machine.

Why this exists
---------------
Some failures are not data quality. They are the machine saying no. Running a
full-cube read of a 655 MB raster variable needs memory that a laptop does not
have; writing a 4 GB bundle needs disk that a nearly-full volume does not have;
a long validation run can be thermally throttled into taking twice as long, and
the result is then a timeout that looks like a bug.

Those are all knowable in advance, and all of them are cheaper to discover before
the operation than after it.

What is measured
----------------
``memory``      available and total, which is the constraint that actually bites
``disk``        free space on the volume a run will write to
``cpu``         logical cores, physical cores, and the observed clock, which
                reveals throttling
``thermal``     delegated to :mod:`geoqa.thermal`, which owns the sensors
``gpu``         presence and reported memory, where a driver exposes it

What is not measured
--------------------
Load average, page-fault behaviour and I/O contention. These matter on a shared
machine, but a library that samples them invites its own conclusions to be
over-read. Where they matter they belong in the orchestrator.

Design constraints
------------------
**Never blocks.** Nothing here waits, retries or throttles. Measurement is fast
and advisory; :class:`geoqa.thermal.ThermalGuard` is the component that acts.

**Degrades to unknowns, not zeroes.** A sensor that cannot be read returns
``None``, which is different from zero degrees and must not be averaged with it.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .problem_registry import VALIDATION_RULE_VERSION

PROBLEM_NAME = "hardware_constraint"

#: Megabytes below which a memory warning is raised for a large operation.
DEFAULT_MEMORY_HEADROOM_MB = 1024

#: Fraction of the volume that must remain free before a write is discouraged.
DEFAULT_DISK_HEADROOM_FRACTION = 0.10

#: Ratio of observed clock to rated clock below which throttling is suspected.
THROTTLE_RATIO = 0.85

_GIB = 1024 ** 3


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .validations.base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _import_psutil():
    try:
        import psutil
    except ImportError:  # pragma: no cover - environment dependent
        return None
    return psutil


@dataclass
class CpuInfo:
    """Processor identity, and what it is currently doing."""

    logical_cores: int | None = None
    physical_cores: int | None = None
    architecture: str | None = None
    processor_name: str | None = None
    rated_clock_mhz: float | None = None
    observed_clock_mhz: float | None = None
    #: True when the observed clock is materially below the rated one.
    throttled: bool | None = None
    #: Set when the machine is thermally limited. Owned by ThermalGuard.
    thermally_limited: bool | None = None

    @property
    def clock_ratio(self) -> float | None:
        if not self.rated_clock_mhz or not self.observed_clock_mhz:
            return None
        return self.observed_clock_mhz / self.rated_clock_mhz

    def as_dict(self) -> dict[str, Any]:
        return {
            "logical_cores": self.logical_cores,
            "physical_cores": self.physical_cores,
            "architecture": self.architecture,
            "processor": self.processor_name,
            "rated_clock_mhz": self.rated_clock_mhz,
            "observed_clock_mhz": self.observed_clock_mhz,
            "clock_ratio": round(self.clock_ratio, 3) if self.clock_ratio else None,
            "throttled": self.throttled,
            "thermally_limited": self.thermally_limited,
        }


@dataclass
class MemoryInfo:
    total_mb: float | None = None
    available_mb: float | None = None
    percent_used: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_mb": round(self.total_mb, 1) if self.total_mb else None,
            "available_mb": round(self.available_mb, 1) if self.available_mb else None,
            "percent_used": round(self.percent_used, 1) if self.percent_used else None,
        }


@dataclass
class DiskInfo:
    path: str
    total_gb: float | None = None
    free_gb: float | None = None
    percent_free: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "total_gb": round(self.total_gb, 2) if self.total_gb else None,
            "free_gb": round(self.free_gb, 2) if self.free_gb else None,
            "percent_free": round(self.percent_free, 1) if self.percent_free else None,
        }


@dataclass
class GpuInfo:
    """Graphics hardware, where a driver will report it."""

    present: bool = False
    count: int = 0
    names: tuple[str, ...] = ()
    total_memory_mb: tuple[float, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "count": self.count,
            "names": list(self.names),
            "total_memory_mb": [round(value, 1) for value in self.total_memory_mb],
        }


@dataclass
class HardwareProfile:
    """What this machine can currently do."""

    platform: str = ""
    machine: str = ""
    cpu: CpuInfo = field(default_factory=CpuInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    disk: DiskInfo = field(default_factory=lambda: DiskInfo(path=""))
    gpu: GpuInfo = field(default_factory=GpuInfo)
    #: Temperatures in Celsius, or empty when no source is available.
    temperatures_c: tuple[float, ...] = ()
    temperature_source: str | None = None
    #: Populated when a sensor source was expected and none answered.
    temperature_note: str | None = None

    @property
    def max_temperature_c(self) -> float | None:
        return max(self.temperatures_c) if self.temperatures_c else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "machine": self.machine,
            "cpu": self.cpu.as_dict(),
            "memory": self.memory.as_dict(),
            "disk": self.disk.as_dict(),
            "gpu": self.gpu.as_dict(),
            "temperatures_c": [round(value, 1) for value in self.temperatures_c],
            "temperature_source": self.temperature_source,
            "temperature_note": self.temperature_note,
            "validation_rule_version": VALIDATION_RULE_VERSION,
        }


# --------------------------------------------------------------------------
# Temperature sources
# --------------------------------------------------------------------------

def _read_windows_wmi_temperatures() -> tuple[list[float], str | None]:
    """LibreHardwareMonitor, then the ACPI thermal zone.

    LibreHardwareMonitor exposes its readings in a WMI namespace and is the
    maintained choice on Windows. CoreTemp's shared-memory approach is still
    supported in :mod:`geoqa.thermal` but has not been maintained for years.

    The ACPI thermal zone is a motherboard sensor, not a core sensor, so it is
    reported separately rather than mixed in.
    """
    if sys.platform != "win32":
        return [], None

    try:
        import win32com.client  # type: ignore
    except ImportError:
        return [], "LibreHardwareMonitor requires pywin32 (pip install pywin32) to read its WMI namespace"

    for namespace in ("root\\LibreHardwareMonitor", "root\\WMI"):
        try:
            wmi = win32com.client.GetObject(f"Win32_object://{namespace.replace(chr(92), '/')}")
        except Exception:
            continue
        values: list[float] = []
        try:
            for sensor in wmi.ExporterData():
                for entry in sensor:
                    if str(getattr(entry, "SensorType", "")).lower() == "temperature":
                        try:
                            values.append(float(entry.Value))
                        except Exception:
                            continue
        except Exception:
            continue
        if values:
            return values, f"librehardwaremonitor:{namespace}"

    return [], "LibreHardwareMonitor not found; install and run it once to expose the WMI namespace"


def _read_linux_hwmon_temperatures() -> tuple[list[float], str | None]:
    """Read ``/sys/class/hwmon`` directly.

    This is the interface psutil uses on Linux, and it needs nothing installed.
    The ``sensors`` command from lm-sensors is a convenience wrapper over the
    same files, so suggesting lm-sensors when hwmon is readable is wrong.
    """
    if not sys.platform.startswith("linux"):
        return [], None

    values: list[float] = []
    base = Path("/sys/class/hwmon")
    if not base.is_dir():
        return [], "No /sys/class/hwmon; sensors may not be exposed to this user"

    try:
        entries = sorted(base.glob("hwmon*"))
    except OSError:
        return [], "/sys/class/hwmon is not readable by this user"

    for entry in entries:
        name_file = entry / "name"
        label = name_file.read_text().strip() if name_file.exists() else entry.name
        if label.lower() not in {"coretemp", "k10temp", "cpu_thermal", "zenpower", "soc_thermal"}:
            continue
        for item in entry.glob("temp*_input"):
            try:
                millidegrees = float(item.read_text().strip())
            except (OSError, ValueError):
                continue
            values.append(millidegrees / 1000.0)

    if values:
        return values, "sysfs_hwmon"
    return [], "hwmon present but no CPU temperature chip exposed; install lm-sensors and run sensors-detect"


def _read_nvidia_smi_temperatures() -> tuple[list[float], str | None]:
    """GPU temperature, where NVIDIA's driver exposes it."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return [], None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return [], None
    if result.returncode != 0:
        return [], None
    values = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            values.append(float(line))
    return (values, "nvidia_smi") if values else ([], None)


def _read_core_temperature() -> tuple[list[float], str | None, str | None]:
    """Best available core temperature, and why not when there is none.

    Returns ``(values, source, note)``. The note is actionable, because
    "no temperature" with no explanation is the least useful diagnostic there
    is.
    """
    if sys.platform == "win32":
        from .thermal import _read_coretemp_mapping

        coretemp = _read_coretemp_mapping()
        if coretemp:
            return coretemp, "coretemp", None

        psutil = _import_psutil()
        if psutil is not None:
            try:
                sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
            except Exception:
                sensors = {}
            values = [
                float(entry.current)
                for group in sensors.values()
                for entry in group
                if getattr(entry, "current", None) is not None
            ]
            if values:
                return values, "psutil", None

        values, note = _read_windows_wmi_temperatures()
        if values:
            return values, "librehardwaremonitor", None
        return [], None, note or (
            "Windows exposes no core temperature. Install LibreHardwareMonitor and run it "
            "once so its WMI namespace exists; psutil alone often cannot see CPU package "
            "temperature on Windows."
        )

    if sys.platform.startswith("linux"):
        values, source = _read_linux_hwmon_temperatures()
        if values:
            return values, source, None

        psutil = _import_psutil()
        if psutil is not None:
            try:
                sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
            except Exception:
                sensors = {}
            values = [
                float(entry.current)
                for group in sensors.values()
                for entry in group
                if getattr(entry, "current", None) is not None
            ]
            if values:
                return values, "psutil", None

        return [], None, source or (
            "No CPU temperature found. /sys/class/hwmon is the native interface and needs "
            "nothing installed; install lm-sensors only if the kernel exposes no CPU chip."
        )

    psutil = _import_psutil()
    if psutil is not None:
        try:
            sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
            values = [
                float(entry.current)
                for group in sensors.values()
                for entry in group
                if getattr(entry, "current", None) is not None
            ]
            if values:
                return values, "psutil", None
        except Exception:
            pass

    return [], None, f"No temperature source available on {platform.system()}"


# --------------------------------------------------------------------------
# Profiling
# --------------------------------------------------------------------------

def _profile_cpu(psutil) -> CpuInfo:
    info = CpuInfo(architecture=platform.machine())
    if psutil is None:
        return info

    try:
        count = psutil.cpu_count(logical=True)
        info.logical_cores = int(count) if count else None
    except Exception:
        pass
    try:
        physical = psutil.cpu_count(logical=False)
        info.physical_cores = int(physical) if physical else None
    except Exception:
        pass
    try:
        frequency = psutil.cpu_freq()
        if frequency is not None:
            if frequency.max:
                info.rated_clock_mhz = float(frequency.max)
            if frequency.current:
                info.observed_clock_mhz = float(frequency.current)
    except Exception:
        pass

    ratio = info.clock_ratio
    if ratio is not None:
        info.throttled = ratio < THROTTLE_RATIO

    if sys.platform == "win32" and not info.processor_name:
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            info.processor_name = str(value)
        except Exception:
            info.processor_name = platform.processor() or None
    elif not info.processor_name:
        info.processor_name = platform.processor() or None

    return info


def _profile_memory(psutil) -> MemoryInfo:
    if psutil is None:
        return MemoryInfo()
    try:
        virtual = psutil.virtual_memory()
        return MemoryInfo(
            total_mb=float(virtual.total) / 1_048_576,
            available_mb=float(virtual.available) / 1_048_576,
            percent_used=float(virtual.percent),
        )
    except Exception:
        return MemoryInfo()


def _profile_disk(path: str | Path) -> DiskInfo:
    target = Path(path)
    try:
        usage = shutil.disk_usage(target)
    except (OSError, ValueError):
        return DiskInfo(path=str(target))
    return DiskInfo(
        path=str(target),
        total_gb=usage.total / _GIB,
        free_gb=usage.free / _GIB,
        percent_free=100.0 * usage.free / usage.total if usage.total else None,
    )


def _profile_gpu() -> GpuInfo:
    gpu = GpuInfo()
    values, _source = _read_nvidia_smi_temperatures()
    executable = shutil.which("nvidia-smi")
    if not executable:
        return gpu
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return gpu
    if result.returncode != 0:
        return gpu
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if not parts or not parts[0]:
            continue
        gpu.names = gpu.names + (parts[0],)
        try:
            gpu.total_memory_mb = gpu.total_memory_mb + (float(parts[1]),)
        except (IndexError, ValueError):
            gpu.total_memory_mb = gpu.total_memory_mb + (0.0,)
    gpu.count = len(gpu.names)
    gpu.present = gpu.count > 0
    return gpu


def profile_hardware(path: str | Path = ".") -> HardwareProfile:
    """Measure this machine. Fast, non-blocking, and safe to call anywhere."""
    psutil = _import_psutil()
    temperatures, source, note = _read_core_temperature()

    return HardwareProfile(
        platform=sys.platform,
        machine=platform.node(),
        cpu=_profile_cpu(psutil),
        memory=_profile_memory(psutil),
        disk=_profile_disk(path),
        gpu=_profile_gpu(),
        temperatures_c=tuple(temperatures),
        temperature_source=source,
        temperature_note=note,
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_operation_feasible(
    profile: HardwareProfile | None = None,
    *,
    estimated_memory_mb: float | None = None,
    estimated_write_mb: float | None = None,
    write_path: str | Path | None = None,
    operation: str = "operation",
    memory_headroom_mb: int = DEFAULT_MEMORY_HEADROOM_MB,
    disk_headroom_fraction: float = DEFAULT_DISK_HEADROOM_FRACTION,
) -> list[Any]:
    """Report whether this machine can carry out a described operation.

    Conditions emitted
    ------------------
    ``hardware_memory_insufficient``
        The operation needs more memory than is available, leaving less than
        the declared headroom. High: this fails partway through rather than at
        the start, which is the worst time.
    ``hardware_disk_space_insufficient``
        The write would leave the volume below the declared free fraction.
        High, for the same reason.
    ``hardware_cpu_throttled``
        The observed clock is materially below the rated one, so the operation
        will take longer than a timing measured elsewhere suggests. Medium.
    ``hardware_temperature_unavailable``
        No core temperature could be read, so nothing in this library can
        enforce a thermal limit. Low, and it names the fix.
    """
    resolved = profile or profile_hardware(write_path or ".")
    issues: list[Any] = []

    if estimated_memory_mb and resolved.memory.available_mb is not None:
        required = estimated_memory_mb + memory_headroom_mb
        if resolved.memory.available_mb < required:
            issues.append(
                _issue(
                    "hardware_memory_insufficient", "high",
                    f"{operation} needs about {estimated_memory_mb:.0f} MB and only "
                    f"{resolved.memory.available_mb:.0f} MB is available, short of the "
                    f"{memory_headroom_mb} MB headroom. This will fail partway through rather "
                    "than at the start. Read the data in windows, or lower the resolution",
                    {
                        **resolved.as_dict(),
                        "estimated_memory_mb": estimated_memory_mb,
                        "available_mb": resolved.memory.available_mb,
                        "headroom_mb": memory_headroom_mb,
                    },
                )
            )

    target = write_path or resolved.disk.path or "."
    if estimated_write_mb:
        disk = _profile_disk(target) if str(target) != resolved.disk.path else resolved.disk
        if disk.free_gb is not None:
            needed_gb = estimated_write_mb / 1024.0
            if disk.free_gb - needed_gb < disk.total_gb * disk_headroom_fraction if disk.total_gb else False:
                issues.append(
                    _issue(
                        "hardware_disk_space_insufficient", "high",
                        f"{operation} would write about {needed_gb:.2f} GB to {disk.path}, which "
                        f"has {disk.free_gb:.2f} GB free. Writing this would leave the volume "
                        f"below {disk_headroom_fraction:.0%} free, which tends to break other "
                        "software on the machine at the same time",
                        {
                            **disk.as_dict(),
                            "estimated_write_mb": estimated_write_mb,
                            "headroom_fraction": disk_headroom_fraction,
                        },
                    )
                )

    if resolved.cpu.throttled:
        ratio = resolved.cpu.clock_ratio
        issues.append(
            _issue(
                "hardware_cpu_throttled", "medium",
                f"The processor is running at about {ratio:.0%} of its rated clock. Whatever "
                "runtime you measured elsewhere does not apply here, so an apparent timeout is "
                "more likely to be this than a bug",
                resolved.cpu.as_dict(),
            )
        )

    if not resolved.temperatures_c and resolved.temperature_note:
        issues.append(
            _issue(
                "hardware_temperature_unavailable", "low",
                f"No core temperature could be read, so no thermal limit can be enforced for "
                f"this run. {resolved.temperature_note}",
                {"platform": resolved.platform, "note": resolved.temperature_note},
            )
        )

    return issues


#: How each platform natively exposes temperature, and what that implies for advice.
NATIVE_INTERFACES: dict[str, str] = {
    "linux": "/sys/class/hwmon (no installation required)",
    "windows": "LibreHardwareMonitor WMI namespace; CoreTemp shared memory also supported",
    "darwin": "psutil, which often exposes nothing",
}


def sensor_report() -> dict[str, Any]:
    """Which temperature source answered, and what to do when none did."""
    profile = profile_hardware()
    family = {
        "win32": "windows", "cygwin": "windows", "linux": "linux", "darwin": "darwin",
    }.get(profile.platform, "unknown")
    return {
        "platform": profile.platform,
        "source": profile.temperature_source,
        "temperatures_c": [round(value, 1) for value in profile.temperatures_c],
        "note": profile.temperature_note,
        "native_interface": NATIVE_INTERFACES.get(family, "unknown"),
        "native_interfaces": dict(NATIVE_INTERFACES),
    }


__all__ = [
    "DEFAULT_DISK_HEADROOM_FRACTION",
    "DEFAULT_MEMORY_HEADROOM_MB",
    "PROBLEM_NAME",
    "THROTTLE_RATIO",
    "CpuInfo",
    "DiskInfo",
    "GpuInfo",
    "HardwareProfile",
    "MemoryInfo",
    "profile_hardware",
    "sensor_report",
    "validate_operation_feasible",
]