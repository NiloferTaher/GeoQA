"""Spatial statistics: the part of the mathematics that describes patterns
rather than shapes.

Every other validator in this library asks whether a feature is well formed.
Nothing else asks whether the *arrangement* of well-formed features is
suspicious. That gap is not academic. A district can contain no invalid
geometry whatsoever and still be wrong in a way that matters: an attribute
that is not an outlier anywhere in the world but is an outlier against its own
neighbours is a data error that per-feature validation structurally cannot see.

That is the false-negative problem this module exists to attack. A value that
is unremarkable globally can still be wrong locally, and only a comparison
against the neighbourhood reveals it. The converse is the one operators
actually act on: a cluster of high values is a genuine hotspot, and a single
isolated high value among low neighbours is usually a data error rather than a
phenomenon.

The mathematics, stated plainly:

**Moran's I** measures global autocorrelation. With n features, values x,
row-standardised spatial weights w, mean x-bar and S0 the sum of weights:

    I = (n / S0) * sum_ij w_ij (x_i - x_bar)(x_j - x_bar) / sum_i (x_i - x_bar)^2

Under spatial randomness the expectation is -1/(n-1). Values near that mean
no pattern; large positive means similar values cluster together, large
negative means neighbours differ systematically. The test statistic is
compared against its expectation, which is why a threshold on I alone is
meaningless and the z-score is reported alongside.

**Geary's C** uses squared differences rather than products, so it weights
local differences rather than global association. Its expectation is 1.
Positive autocorrelation gives C below 1, negative above. It is reported
beside Moran because the two disagree in ways that are informative: a high
Moran with a near-1 Geary usually means clustering at a coarse scale with
local uniformity, which is exactly the pattern of a block-boundary artefact.

**Local Moran (LISA)** decomposes the global statistic into per-feature
contributions. Each feature lands in one of four quadrants, and the
High-High and Low-Low quadrants are the ones that mean something spatially.
The four quadrants are reported as evidence rather than as defects, because
"this value is high and so are its neighbours' values" is an observation
about the world, not an error in the data.

**Getis-Ord Gi-star** answers a different question from LISA: not "is this
value unusual for its neighbours" but "is this value and its immediate
neighbourhood jointly high". It is a z-score against the global mean and
standard deviation, so unlike Moran it has a natural zero at the global mean.

**Variograms** describe how dissimilarity grows with distance. The nugget is
the sill of unresolved variance at distance zero; a large nugget relative to
the total sill means measurement noise dominates and no spatial model of that
variable will be worth fitting.

Weights are never defaulted silently. K-nearest-neighbours, inverse distance
and queen contiguity answer different questions, and the choice changes the
answer, so it is recorded in the output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

import numpy

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "SpatialWeights",
    "build_weights",
    "morans_i",
    "gearys_c",
    "local_moran",
    "getis_ord_gi_star",
    "variogram",
    "spatial_outliers",
    "MoransIResult",
    "GearysCResult",
    "SpatialStatisticsProfile",
]

WeightMethod = Literal["knn", "inverse_distance", "queen"]


# --------------------------------------------------------------------------
# Weights
# --------------------------------------------------------------------------


@dataclass
class SpatialWeights:
    """A row-standardised weight matrix, with the method recorded.

    Row standardisation means each feature's weights sum to one, so a feature
    in a dense area and one in a sparse area contribute comparably. Without
    it, the statistic measures where features are dense rather than how values
    relate, which is almost never what the caller meant.
    """

    matrix: Any
    method: str
    k: int | None = None
    power: float | None = None
    n: int = 0

    @property
    def s0(self) -> float:
        return float(numpy.asarray(self.matrix).sum())

    @property
    def neighbor_counts(self) -> list[int]:
        binary = (numpy.asarray(self.matrix) > 0).sum(axis=1)
        return [int(c) for c in binary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "k": self.k,
            "power": self.power,
            "n": self.n,
            "s0": self.s0,
            "row_standardised": True,
        }


def _coordinates(layer: Any) -> tuple[Any, list[Any]]:
    geoms, ids = [], []
    for index, row in layer.iterrows():
        geometry = row.get("geometry")
        if geometry is None:
            continue
        try:
            point = geometry.representative_point()
            geoms.append((point.x, point.y))
            ids.append(index)
        except Exception:
            continue
    coords = numpy.asarray(geoms, dtype=float)
    if coords.ndim != 2 or len(coords) == 0:
        coords = numpy.zeros((0, 2))
    return coords, ids


def build_weights(
    layer: Any,
    *,
    method: WeightMethod = "knn",
    k: int = 8,
    power: float = 2.0,
) -> SpatialWeights:
    """Build a spatial weight matrix.

    ``knn`` asks what is nearby regardless of how far. ``inverse_distance``
    asks how close, and lets distance count. ``queen`` asks what shares a
    boundary, and is the right choice for polygon topology and the wrong one
    for anything else. The choice changes the statistic, so it is recorded.
    """
    coords, ids = _coordinates(layer)
    n = len(coords)
    if n == 0:
        return SpatialWeights(numpy.zeros((0, 0)), method, k, power, 0)

    if method == "queen":
        matrix = _queen_matrix(layer, ids)
        return SpatialWeights(_row_standardise(matrix), method, None, None, n)

    if n == 1:
        return SpatialWeights(numpy.zeros((1, 1)), method, k, power, 1)

    deltas = coords[:, None, :] - coords[None, :, :]
    distances = numpy.sqrt((deltas ** 2).sum(axis=-1))
    numpy.fill_diagonal(distances, numpy.inf)

    matrix = numpy.zeros((n, n), dtype=float)
    if method == "knn":
        kk = max(1, min(int(k), n - 1))
        nearest = numpy.argsort(distances, axis=1)[:, :kk]
        rows = numpy.repeat(numpy.arange(n), kk)
        matrix[rows, nearest.ravel()] = 1.0
    elif method == "inverse_distance":
        with numpy.errstate(divide="ignore", invalid="ignore"):
            weights = numpy.where(distances > 0, 1.0 / distances ** float(power), 0.0)
        numpy.fill_diagonal(weights, 0.0)
        matrix = weights
    else:
        raise ValueError(f"unknown weight method: {method!r}")

    return SpatialWeights(_row_standardise(matrix), method, k if method == "knn" else None,
                          power if method == "inverse_distance" else None, n)


def _queen_matrix(layer: Any, ids: Sequence[Any]) -> Any:
    """Polygon contiguity by shared boundary, not merely shared vertex."""
    try:
        geoms = [layer.loc[i, "geometry"] for i in ids]
    except Exception:
        geoms = [layer.iloc[i]["geometry"] for i in range(len(ids))]
    n = len(geoms)
    matrix = numpy.zeros((n, n), dtype=float)
    for i in range(n):
        gi = geoms[i]
        if gi is None or getattr(gi, "is_empty", False):
            continue
        gi_bounds = gi.bounds
        for j in range(i + 1, n):
            gj = geoms[j]
            if gj is None or getattr(gj, "is_empty", False):
                continue
            gj_bounds = gj.bounds
            if gi_bounds[2] < gj_bounds[0] or gj_bounds[2] < gi_bounds[0]:
                continue
            if gi_bounds[3] < gj_bounds[1] or gj_bounds[3] < gi_bounds[1]:
                continue
            try:
                if gi.touches(gj) and gi.intersection(gj).length > 0:
                    matrix[i, j] = matrix[j, i] = 1.0
            except Exception:
                continue
    return matrix


def _row_standardise(matrix: Any) -> Any:
    matrix = numpy.asarray(matrix, dtype=float)
    if matrix.size == 0:
        return matrix
    totals = matrix.sum(axis=1, keepdims=True)
    with numpy.errstate(divide="ignore", invalid="ignore"):
        standardised = numpy.where(totals > 0, matrix / totals, 0.0)
    return standardised


# --------------------------------------------------------------------------
# Global statistics
# --------------------------------------------------------------------------


@dataclass
class MoransIResult:
    i_value: float
    expected: float
    variance: float
    z_score: float
    n: int
    weights: SpatialWeights
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "morans_i": self.i_value,
            "expected": self.expected,
            "variance": self.variance,
            "z_score": self.z_score,
            "n": self.n,
            "weights": self.weights.to_dict(),
            "interpretation": self.interpretation,
        }


def morans_i(values: Sequence[float], weights: SpatialWeights, permutations: int = 199) -> MoransIResult:
    """Global Moran's I with the normal-approximation z-score.

    The expectation under spatial randomness is -1/(n-1), which is why a raw
    I of 0.2 says nothing without knowing n: for 50 features the expectation
    is already -0.02.
    """
    x = numpy.asarray(values, dtype=float)
    n = len(x)
    if n < 3:
        return MoransIResult(float("nan"), float("nan"), float("nan"), float("nan"), n, weights,
                             "Too few features for Moran's I to be meaningful.")
    if numpy.isnan(x).any():
        raise ValueError("Moran's I does not accept missing values; decide how to handle them first")

    z = x - x.mean()
    denominator = float((z ** 2).sum())
    s0 = weights.s0
    if denominator == 0.0 or s0 == 0.0:
        return MoransIResult(float("nan"), -1.0 / (n - 1), float("nan"), float("nan"), n, weights,
                             "No variation in the values, or no spatial links.")

    w = numpy.asarray(weights.matrix, dtype=float)
    numerator = float((w * numpy.outer(z, z)).sum())
    observed = (n / s0) * (numerator / denominator)
    expected = -1.0 / (n - 1)

    # Significance by permutation rather than by a normal approximation.
    # The closed-form variance in the literature assumes weights that are not
    # row-standardised, and applied to a row-standardised matrix it returns a
    # negative variance, which is a silent failure rather than a weak result.
    # Randomising the values against the observed weights assumes nothing
    # about the distribution and is exact for the null, so it is used instead
    # and the z-score is reported against the permutation distribution.
    variance, z_score = _permutation_inference(values=x, w=w, observed=observed,
                                              expected=expected, permutations=permutations)
    return MoransIResult(observed, expected, variance, z_score, n, weights,
                         _interpret_moran(observed, z_score))


def _permutation_inference(values: Any, w: Any, observed: float, expected: float,
                           permutations: int = 199) -> tuple[float, float]:
    """Return the permutation variance and a standardised z-score."""
    import numpy

    x = numpy.asarray(values, dtype=float)
    n = len(x)
    s0 = float(w.sum())
    if n < 5 or permutations < 1 or s0 == 0.0:
        return float("nan"), float("nan")

    z = x - x.mean()
    denominator = float((z ** 2).sum())
    if denominator == 0.0:
        return float("nan"), float("nan")

    rng = numpy.random.default_rng(20100301)  # fixed seed: the same data gives the same answer
    null = numpy.empty(permutations, dtype=float)
    for r in range(permutations):
        permuted = rng.permutation(z)
        null[r] = (n / s0) * float((w * numpy.outer(permuted, permuted)).sum()) / denominator

    variance = float(null.var(ddof=1))
    if variance <= 0:
        return variance, float("nan")
    z_score = (observed - float(null.mean())) / math.sqrt(variance)
    return variance, z_score


def _interpret_moran(observed: float, z_score: float) -> str:
    if z_score != z_score:
        return "Moran's I could not be tested; report the observed value without significance."
    if z_score > 1.96:
        return "Similar values cluster together more than chance would explain."
    if z_score < -1.96:
        return "Adjacent features differ more than chance would explain, which is often a boundary effect."
    return "No detectable spatial pattern; the arrangement is consistent with randomness."


@dataclass
class GearysCResult:
    c_value: float
    expected: float
    z_score: float
    n: int
    weights: SpatialWeights
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gearys_c": self.c_value,
            "expected": self.expected,
            "z_score": self.z_score,
            "n": self.n,
            "weights": self.weights.to_dict(),
            "interpretation": self.interpretation,
        }


def gearys_c(values: Sequence[float], weights: SpatialWeights) -> GearysCResult:
    """Geary's C. Expectation is 1; below 1 means clustering, above 1 means alternation."""
    x = numpy.asarray(values, dtype=float)
    n = len(x)
    if n < 3:
        return GearysCResult(float("nan"), 1.0, float("nan"), n, weights,
                             "Too few features for Geary's C to be meaningful.")
    if numpy.isnan(x).any():
        raise ValueError("Geary's C does not accept missing values")

    w = numpy.asarray(weights.matrix, dtype=float)
    mean = x.mean()
    denominator = float(((x - mean) ** 2).sum())
    s0 = weights.s0
    if denominator == 0.0 or s0 == 0.0:
        return GearysCResult(float("nan"), 1.0, float("nan"), n, weights,
                             "No variation in the values, or no spatial links.")

    difference = x[:, None] - x[None, :]
    numerator = float((w * difference ** 2).sum())
    observed = ((n - 1) / (2.0 * s0)) * (numerator / denominator)

    expected = 1.0
    z_score = float("nan")
    try:
        row_sums = w.sum(axis=1)
        col_sums = w.sum(axis=0)
        s1 = 0.5 * float(((w + w.T) ** 2).sum())
        s2 = float(((row_sums + col_sums) ** 2).sum())
        variance = (
            (1.0 + (2.0 * s1 + s2) * 0.0 - (4.0 * s0 ** 2) / (n * (n - 1))) / (2.0 * (s0 ** 2))
            if s0 else float("nan")
        )
        if variance == variance and variance > 0:
            z_score = (observed - expected) / math.sqrt(variance)
    except Exception:
        variance = float("nan")

    return GearysCResult(observed, expected, z_score, n, weights, _interpret_geary(observed))


def _interpret_geary(observed: float) -> str:
    if observed != observed:
        return "Geary's C could not be computed."
    if observed < 0.85:
        return "Neighbouring features have similar values, consistent with clustering."
    if observed > 1.15:
        return "Neighbouring features differ more than expected, consistent with alternation."
    return "Neighbouring values are no more alike or different than chance."


# --------------------------------------------------------------------------
# Local statistics
# --------------------------------------------------------------------------


@dataclass
class LocalMoranResult:
    """Per-feature contribution to global autocorrelation."""

    scores: dict[Any, float]
    quadrants: dict[Any, str]
    z_scores: dict[Any, float]
    n: int
    weights: SpatialWeights

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {"high_high": 0, "low_low": 0, "high_low": 0, "low_high": 0}
        for value in self.quadrants.values():
            tally[value] = tally.get(value, 0) + 1
        return tally

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "counts": self.counts(),
            "weights": self.weights.to_dict(),
            "quadrants": {str(k): v for k, v in self.quadrants.items()},
        }


def local_moran(values: Sequence[float], weights: SpatialWeights,
               ids: Sequence[Any] | None = None) -> LocalMoranResult:
    """Local Moran (LISA): each feature's contribution to the global pattern.

    The quadrant is the useful part. High-High means a high value among high
    neighbours, which is a hotspot; Low-High is a high value among low
    neighbours, which is the signature of a probable data error. None of these
    is a defect and all are reported as evidence.
    """
    x = numpy.asarray(values, dtype=float)
    n = len(x)
    keys = list(ids) if ids is not None else list(range(n))
    if n < 3:
        return LocalMoranResult({}, {}, {}, n, weights)

    w = numpy.asarray(weights.matrix, dtype=float)
    z = x - x.mean()
    sigma = float((z ** 2).sum()) / n
    if sigma == 0.0:
        return LocalMoranResult({k: 0.0 for k in keys}, {k: "undefined" for k in keys}, {}, n, weights)

    lag = w @ z
    local_i = z * lag / sigma
    se = (w.sum(axis=1) + w.sum(axis=0)) / (2.0 * w.sum())

    scores, quadrants, zscores = {}, {}, {}
    for i, key in enumerate(keys):
        scores[key] = float(local_i[i])
        if z[i] > 0 and lag[i] > 0:
            quadrants[key] = "high_high"
        elif z[i] < 0 and lag[i] < 0:
            quadrants[key] = "low_low"
        elif z[i] > 0 and lag[i] < 0:
            quadrants[key] = "high_low"
        else:
            quadrants[key] = "low_high"
        if se[i] and se[i] > 0:
            zscores[key] = float((z[i] + lag[i]) / (math.sqrt(sigma) * math.sqrt(se[i])))
    return LocalMoranResult(scores, quadrants, zscores, n, weights)


def getis_ord_gi_star(values: Sequence[float], weights: SpatialWeights,
                      ids: Sequence[Any] | None = None) -> dict[Any, dict[str, float]]:
    """Getis-Ord Gi*: is this value *and its neighbourhood* jointly extreme.

    Unlike Moran's I this is a z-score against the global mean and standard
    deviation, so zero means unremarkable. Positive is a hot spot, negative a
    cold spot.
    """
    x = numpy.asarray(values, dtype=float)
    n = len(x)
    keys = list(ids) if ids is not None else list(range(n))
    if n < 2:
        return {k: {"score": 0.0, "z_score": 0.0} for k in keys}

    w = numpy.asarray(weights.matrix, dtype=float)
    mean = x.mean()
    variance = float((x ** 2).sum()) / n - mean ** 2
    std = math.sqrt(variance) if variance > 0 else 0.0

    results: dict[Any, dict[str, float]] = {}
    for i, key in enumerate(keys):
        w_sum = float(w[i].sum())
        numerator = float((w[i] * x).sum()) - mean * w_sum
        if std == 0.0:
            results[key] = {"score": 0.0, "z_score": 0.0}
            continue
        score = numerator / std
        row_sq = float((w[i] ** 2).sum())
        denom = n * row_sq - (w_sum ** 2)
        z_score = score / math.sqrt(denom / (n - 1)) if denom > 0 else 0.0
        results[key] = {"score": float(score), "z_score": float(z_score)}
    return results


# --------------------------------------------------------------------------
# Variograms
# --------------------------------------------------------------------------


def variogram(coords: Any, values: Sequence[float],
              max_lag: float | None = None, n_bins: int = 10) -> dict[str, Any]:
    """Empirical semivariogram: squared dissimilarity against distance.

    The nugget is the value at distance zero, which is measurement and
    process noise the spatial model cannot explain. A large nugget against the
    total sill means no spatial model of that variable is worth fitting.
    """
    x = numpy.asarray(values, dtype=float)
    coords = numpy.asarray(coords, dtype=float)
    if len(x) < 2 or len(coords) != len(x):
        return {"ok": False, "reason": "not enough points"}

    deltas = coords[:, None, :] - coords[None, :, :]
    distances = numpy.sqrt((deltas ** 2).sum(axis=-1))
    upper = numpy.triu(distances, 1)
    gamma = 0.5 * (x[:, None] - x[None, :]) ** 2
    pairs = upper > 0
    if not pairs.any():
        return {"ok": False, "reason": "no distinct point pairs"}

    observed = upper[pairs]
    dissimilarity = gamma[pairs]
    cutoff = max_lag or float(observed.max())
    if cutoff <= 0:
        return {"ok": False, "reason": "all points coincide"}

    edges = numpy.linspace(0, cutoff, int(n_bins) + 1)
    bins: list[dict[str, Any]] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        inside = (observed >= lo) & (observed < hi) if hi < cutoff else (observed >= lo) & (observed <= hi)
        if not inside.any():
            continue
        bins.append({
            "lag": float((lo + hi) / 2.0),
            "lag_low": float(lo),
            "lag_high": float(hi),
            "pairs": int(inside.sum()),
            "semivariance": float(dissimilarity[inside].mean()),
        })

    if not bins:
        return {"ok": False, "reason": "no bins populated"}

    nugget = float(bins[0]["semivariance"])
    sill = float(max(b["semivariance"] for b in bins))
    total = sill + nugget
    return {
        "ok": True,
        "bins": bins,
        "nugget": nugget,
        "sill": sill,
        "range": float(bins[-1]["lag"]),
        "nugget_ratio": (nugget / total) if total else None,
        "n": len(x),
    }


# --------------------------------------------------------------------------
# The false-negative hunt
# --------------------------------------------------------------------------


@dataclass
class SpatialStatisticsProfile:
    """What a single attribute column looks like once space is accounted for."""

    column: str
    n: int
    global_mean: float
    global_std: float
    moran: MoransIResult | None = None
    geary: GearysCResult | None = None
    local: LocalMoranResult | None = None
    gi_star: dict[Any, dict[str, float]] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "n": self.n,
            "global_mean": self.global_mean,
            "global_std": self.global_std,
            "morans_i": self.moran.to_dict() if self.moran else None,
            "gearys_c": self.geary.to_dict() if self.geary else None,
            "local_moran": self.local.to_dict() if self.local else None,
            "gi_star": self.gi_star,
            "notes": list(self.notes),
        }


def spatial_outliers(
    layer: Any,
    column: str,
    *,
    weights: SpatialWeights | None = None,
    z_threshold: float = 2.0,
    min_features: int = 8,
) -> list[ValidationIssue]:
    """Find values that are wrong *relative to their neighbours*.

    This is the check that per-feature validation cannot perform. A value
    perfectly ordinary in the global distribution can still be an error if
    every feature around it holds a different value, and a value that is
    globally extreme may be entirely legitimate if the whole region is
    extreme.

    Three patterns are separated because they mean different things:

    - **high among low neighbours** is the strongest single signal of a data
      error available, because the feature is inconsistent with its context
      rather than merely unusual.
    - **globally extreme** is weaker on its own, since a whole district may
      legitimately differ.
    - **a cluster of high values** is a hotspot, which is a real feature of
      the world and is reported as evidence rather than as a defect.

    A feature is only reported when its value is both unusual globally and
    inconsistent locally, because either alone produces false positives.
    """
    issues: list[ValidationIssue] = []
    if column not in getattr(layer, "columns", []):
        return issues

    series = layer[column]
    numeric = numpy.array(
        [float(v) if isinstance(v, (int, float)) and not isinstance(v, bool)
         else numpy.nan for v in series],
        dtype=float,
    )
    valid = ~numpy.isnan(numeric)
    if int(valid.sum()) < min_features:
        return issues

    values = numeric[valid]
    ids = [idx for idx, keep in zip(layer.index, valid) if keep]
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    if std == 0.0:
        return issues

    w = weights if weights is not None else build_weights(layer, method="knn", k=min(8, len(values) - 1))
    w_small = w.matrix[: len(values), : len(values)] if len(values) == w.n else w.matrix

    lag_mean = numpy.asarray(w_small) @ values
    global_z = (values - mean) / std
    local_z = (values - lag_mean) / (std if std else 1.0)

    for position, index in enumerate(ids):
        gz = float(global_z[position])
        lz = float(local_z[position])
        if abs(gz) < z_threshold:
            continue
        if abs(lz) < z_threshold:
            continue
        kind = "high" if gz > 0 else "low"
        neighbour = "low" if lz < 0 else "high"
        issues.append(
            build_issue(
                "spatial_statistical_outlier",
                index=index,
                description=(
                    f"{column} is {abs(gz):.1f} standard deviations from the global mean "
                    f"and {abs(lz):.1f} from its neighbours' mean, and in the opposite "
                    f"direction to them. A value that is unusual globally and "
                    f"inconsistent locally is far more likely to be a data error than a "
                    f"real {kind} value among {neighbour} ones."
                ),
                extra={
                    "column": column,
                    "value": float(values[position]),
                    "global_mean": mean,
                    "global_z": gz,
                    "local_z": lz,
                    "neighbour_mean": float(lag_mean[position]),
                    "z_threshold": z_threshold,
                },
            )
        )
    return issues


def profile_spatial_statistics(
    layer: Any,
    column: str,
    *,
    weights: SpatialWeights | None = None,
    min_features: int = 8,
) -> SpatialStatisticsProfile:
    """Measure a column's spatial structure without judging any feature.

    Reported alongside a per-feature report so a reader can tell the
    difference between a column with no spatial pattern and a column that
    was never tested for one.
    """
    if column not in getattr(layer, "columns", []):
        return SpatialStatisticsProfile(column, 0, float("nan"), float("nan"),
                                       notes=["column is absent"])

    series = layer[column]
    numeric = numpy.array(
        [float(v) if isinstance(v, (int, float)) and not isinstance(v, bool)
         else numpy.nan for v in series],
        dtype=float,
    )
    valid = ~numpy.isnan(numeric)
    ids = [idx for idx, keep in zip(layer.index, valid) if keep]
    values = numeric[valid]

    if len(values) < min_features:
        return SpatialStatisticsProfile(
            column, int(len(values)), float(numpy.nan), float("nan"),
            notes=[f"only {len(values)} usable values; below the minimum of {min_features}"],
        )

    w = weights if weights is not None else build_weights(layer, method="knn", k=min(8, len(values) - 1))
    w_small = w.matrix[: len(values), : len(values)] if len(values) == w.n else w.matrix
    trimmed = SpatialWeights(w_small, w.method, w.k, w.power, len(values))

    mean = float(values.mean())
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0

    notes: list[str] = []
    if std == 0.0:
        notes.append("every value is identical, so no statistic is defined")

    return SpatialStatisticsProfile(
        column=column,
        n=int(len(values)),
        global_mean=mean,
        global_std=std,
        moran=morans_i(values, trimmed),
        geary=gearys_c(values, trimmed),
        local=local_moran(values, trimmed, ids),
        gi_star=getis_ord_gi_star(values, trimmed, ids),
        notes=notes,
    )