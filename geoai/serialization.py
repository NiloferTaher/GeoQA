from __future__ import annotations

import importlib
import json
from typing import Any, Protocol


class _ToonBackend(Protocol):
    def dumps(self, obj: Any, /, **kwargs: Any) -> str: ...

    def loads(self, data: str, /, **kwargs: Any) -> Any: ...


_TOON_CANDIDATES = ("toon", "pytoon", "token_object_notation")


def _coerce_backend(module: Any) -> _ToonBackend | None:
    dumps = getattr(module, "dumps", None) or getattr(module, "serialize", None)
    loads = getattr(module, "loads", None) or getattr(module, "deserialize", None)
    if callable(dumps) and callable(loads):
        return module
    return None


def _load_toon_backend() -> tuple[_ToonBackend | None, str | None]:
    for module_name in _TOON_CANDIDATES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        backend = _coerce_backend(module)
        if backend is not None:
            return backend, module_name
    return None, None


_TOON_BACKEND, _TOON_BACKEND_NAME = _load_toon_backend()


def is_toon_available() -> bool:
    """Return True when an optional TOON backend is available."""
    return _TOON_BACKEND is not None


def available_formats() -> tuple[str, ...]:
    """
    Return the supported format names.

    `json` is always available. `toon` is always accepted as an input value, but
    it only uses a real TOON backend when an optional dependency is installed.
    """
    return ("json", "toon")


def _json_dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_load(data: str) -> Any:
    return json.loads(data)


def serialize(obj: Any, format: str = "json") -> str:
    """
    Serialize an object to JSON or TOON.

    Behavior:
    - `json`: always uses JSON.
    - `toon`: uses an optional TOON backend when available; otherwise falls back
      to compact JSON for cross-platform compatibility.
    """
    fmt = format.lower().strip()
    if fmt == "json":
        return _json_dump(obj)
    if fmt == "toon":
        if _TOON_BACKEND is not None:
            return _TOON_BACKEND.dumps(obj)
        return _json_dump(obj)
    raise ValueError(f"Unsupported serialization format: {format!r}")


def deserialize(data: str, format: str = "json") -> Any:
    """
    Deserialize an object from JSON or TOON.

    Behavior:
    - `json`: always uses JSON.
    - `toon`: uses an optional TOON backend when available; otherwise falls back
      to JSON parsing.
    """
    fmt = format.lower().strip()
    if fmt == "json":
        return _json_load(data)
    if fmt == "toon":
        if _TOON_BACKEND is not None:
            return _TOON_BACKEND.loads(data)
        return _json_load(data)
    raise ValueError(f"Unsupported serialization format: {format!r}")


__all__ = [
    "available_formats",
    "deserialize",
    "is_toon_available",
    "serialize",
]
