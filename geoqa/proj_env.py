"""Make PROJ resolvable before anything tries to build a CRS from an EPSG code.

Why this module exists
----------------------
PROJ finds its coordinate database through ``PROJ_LIB`` or ``PROJ_DATA``. If
either points somewhere that exists but has no ``proj.db`` in it, every call
that needs a CRS fails with an error that names neither the variable nor the
file: ``Cannot find proj.db``.

That is a common state on a Windows machine that has had PostGIS and rasterio
installed at different times, because each ships its own PROJ tree and whichever
was configured last wins.

The fix is to point the variables at a tree that actually contains the
database. rasterio bundles a complete one and is a dependency of the raster
paths, so it is the reliable fallback. Setting these only happens when the
current value is broken, so a correctly configured machine is left alone.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Where rasterio keeps the PROJ tree it ships.
_RASTERIO_PROJ_SUFFIX = ("proj_data", "proj")

#: Set once a repair has been attempted, so the work happens at most once.
_resolved = False


def proj_is_usable(proj_dir: str | None = None) -> bool:
    """Does this directory actually contain a PROJ database?"""
    candidate = proj_dir or os.environ.get("PROJ_LIB") or os.environ.get("PROJ_DATA")
    if not candidate:
        return False
    path = Path(candidate)
    if not path.is_dir():
        return False
    for name in ("proj.db", "proj.db-wal"):
        if (path / name).exists():
            return True
    return (path / "share" / "proj" / "proj.db").exists()


def bundled_proj_dir() -> str | None:
    """Locate the PROJ tree rasterio ships, if rasterio is installed."""
    try:
        import rasterio
    except ImportError:
        return None

    base = Path(rasterio.__file__).resolve().parent
    candidates = [base / suffix for suffix in _RASTERIO_PROJ_SUFFIX]
    try:
        import rasterio.proj as _  # noqa: F401
    except ImportError:
        pass
    try:
        import pyproj
    except ImportError:
        pyproj = None
    if pyproj is not None:
        data_dir = getattr(getattr(pyproj, "datadir", None), "__get__", None)
        try:
            if pyproj.datadir:
                candidates.append(Path(pyproj.datadir))
        except Exception:
            pass

    for candidate in candidates:
        if candidate.is_dir() and (candidate / "proj.db").exists():
            return str(candidate)
        nested = candidate / "share" / "proj"
        if nested.is_dir() and (nested / "proj.db").exists():
            return str(nested)
    return None


def ensure_proj(*, force: bool = False) -> str | None:
    """Make sure PROJ can find its database, repairing the environment if needed.

    Returns the directory now in use, or ``None`` when no repair was needed or
    none was possible. Safe to call repeatedly; it does the work once.
    """
    global _resolved

    if _resolved and not force:
        return os.environ.get("PROJ_LIB") or os.environ.get("PROJ_DATA")

    if proj_is_usable():
        _resolved = True
        return os.environ.get("PROJ_LIB") or os.environ.get("PROJ_DATA")

    bundled = bundled_proj_dir()
    if bundled:
        os.environ["PROJ_LIB"] = bundled
        os.environ["PROJ_DATA"] = bundled
        _resolved = True
        return bundled

    _resolved = True
    return None


def proj_status() -> dict[str, object]:
    """What PROJ is pointed at, and whether that works."""
    return {
        "PROJ_LIB": os.environ.get("PROJ_LIB"),
        "PROJ_DATA": os.environ.get("PROJ_DATA"),
        "usable": proj_is_usable(),
        "bundled_available": bundled_proj_dir() is not None,
    }


__all__ = ["bundled_proj_dir", "ensure_proj", "proj_is_usable", "proj_status"]