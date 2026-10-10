from __future__ import annotations

import importlib
from typing import Any

import numpy as np


_BACKEND_NAME = "numpy"
_HAS_JAX = False
xp: Any = np


def configure_backend(prefer_jax: bool = True) -> str:
    """
    Configure the numerical backend.

    If JAX is installed and `prefer_jax` is True, JAX is used. Otherwise NumPy is
    used as a safe fallback.
    """
    global _BACKEND_NAME, _HAS_JAX, xp

    if prefer_jax:
        try:
            importlib.import_module("jax")
            xp = importlib.import_module("jax.numpy")
            _BACKEND_NAME = "jax"
            _HAS_JAX = True
            return _BACKEND_NAME
        except ImportError:
            pass

    xp = np
    _BACKEND_NAME = "numpy"
    _HAS_JAX = False
    return _BACKEND_NAME


configure_backend(prefer_jax=True)


def backend_name() -> str:
    """Return the active numerical backend name."""
    return _BACKEND_NAME


def jax_available() -> bool:
    """Return True when JAX is the active backend."""
    return _HAS_JAX


def get_array_module() -> Any:
    """Return the active array module (`jax.numpy` or `numpy`)."""
    return xp


def as_array(values: Any, dtype: Any = None) -> Any:
    """Convert values into an array using the active backend."""
    return xp.asarray(values, dtype=dtype)


def to_numpy(values: Any) -> np.ndarray:
    """Convert backend arrays to a NumPy array."""
    return np.asarray(values)


def pairwise_squared_distances(points_a: Any, points_b: Any | None = None) -> Any:
    """
    Compute pairwise squared distances using the active backend.

    This is useful for clustering, nearest-neighbor screening, and embedding-space
    comparisons in GeoAI workflows.
    """
    a = as_array(points_a, dtype=float)
    b = a if points_b is None else as_array(points_b, dtype=float)
    diff = a[:, None, :] - b[None, :, :]
    return xp.sum(diff * diff, axis=-1)


def stable_softmax(values: Any, axis: int = -1) -> Any:
    """Compute a numerically stable softmax using the active backend."""
    arr = as_array(values, dtype=float)
    shifted = arr - xp.max(arr, axis=axis, keepdims=True)
    exp_values = xp.exp(shifted)
    return exp_values / xp.sum(exp_values, axis=axis, keepdims=True)


__all__ = [
    "as_array",
    "backend_name",
    "configure_backend",
    "get_array_module",
    "jax_available",
    "pairwise_squared_distances",
    "stable_softmax",
    "to_numpy",
]
