"""Tests that the spectral validators are reachable and correctly keyed.

Two separate defects are pinned down here.

1. REACHABILITY. ``spectral.py`` existed but no profile could invoke it:
   ``_builtin_specs()`` had no ``spectral`` dataset type, so
   ``validate_layer(df, "spectral")`` raised
   ``ValueError: Unsupported dataset type``. The module was effectively dead
   code, callable only by direct import.

2. TEMPORAL ATTRIBUTION. The spike check compared row i against row i-1 of the
   whole table. For a table holding one row per site per date that compares two
   DIFFERENT sites and reports the difference between them as temporal change.
   It also misattributes: a real change at site B was reported against site A.
   The fix keys the comparison by an explicit feature id.
"""

from __future__ import annotations

import pandas as pd
import pytest

from geoqa.interactive_validation import validate_layer
from geoqa.validation_runtime import _builtin_specs
from geoqa.validations.spectral import validate_spectral_indices


# ---------------------------------------------------------------- reachability


def test_spectral_dataset_type_is_registered():
    """The failure mode this pins: ValueError, not an empty issue list."""
    names = [s.name for s in _builtin_specs("spectral", {})]
    assert "spectral_indices" in names
    assert "band_radiance" in names


def test_validate_layer_accepts_spectral():
    df = pd.DataFrame({"ndvi": [0.2], "ndwi": [0.1]})
    issues = validate_layer(df, "spectral")
    assert isinstance(issues, list)


def test_spectral_specs_declare_no_geometry():
    """_coverage_row calls list() on expected_geometry_types.

    A spectral table has no geometry column, so this must be an empty tuple.
    None raises TypeError: 'NoneType' object is not iterable.
    """
    for spec in _builtin_specs("spectral", {}):
        assert spec.expected_geometry_types == (), spec.name


def test_out_of_range_index_is_found_through_the_runtime():
    df = pd.DataFrame({"ndvi": [1.4], "ndwi": [0.2]})
    issues = validate_layer(df, "spectral")
    assert any(i.problem_name == "ndvi_out_of_range" for i in issues), \
        [i.problem_name for i in issues]


# ------------------------------------------------------------ temporal keying


def _two_sites():
    """Site A stable; site B changes by 0.40, above the 0.30 threshold."""
    return pd.DataFrame(
        {
            "site": ["A", "B", "A", "B"],
            "date": ["2022-06-01", "2022-06-01", "2025-06-01", "2025-06-01"],
            "ndvi": [0.50, 0.50, 0.50, 0.90],
        }
    )


def test_keyed_spike_attributes_to_the_changing_site():
    issues = validate_spectral_indices(
        _two_sites(), date_col="date", feature_id_col="site"
    )
    spikes = [i for i in issues if "spike" in i.problem_name]
    assert len(spikes) == 1, [i.problem_name for i in issues]
    assert (spikes[0].extra or {})["key"] == "B"


def test_unkeyed_comparison_misattributes_the_site():
    """Regression guard for the original defect.

    Without a feature key the row-order comparison fires on the same transition
    but reports it against site A, which did not change. This test documents the
    wrong behaviour so a future change cannot silently reintroduce it.
    """
    unkeyed = validate_spectral_indices(_two_sites(), date_col="date")
    spikes = [i for i in unkeyed if "spike" in i.problem_name]
    assert len(spikes) == 1
    assert (spikes[0].extra or {})["key"] is None, \
        "unkeyed comparison has no site attribution"


def test_stable_site_alone_produces_no_spike():
    """A single site that barely changes must be silent."""
    df = pd.DataFrame(
        {"site": ["A", "A"], "date": ["2022-06-01", "2025-06-01"], "ndvi": [0.50, 0.52]}
    )
    issues = validate_spectral_indices(df, date_col="date", feature_id_col="site")
    assert [i for i in issues if "spike" in i.problem_name] == []


def test_same_site_large_change_is_detected():
    """The positive case: one site changing across dates must fire."""
    df = pd.DataFrame(
        {
            "site": ["A", "A"],
            "date": ["2022-06-01", "2025-06-01"],
            "ndvi": [0.50, 0.90],
        }
    )
    issues = validate_spectral_indices(df, date_col="date", feature_id_col="site")
    assert any("spike" in i.problem_name for i in issues), \
        [i.problem_name for i in issues]


def test_no_date_col_means_no_temporal_claim():
    """Without dates GeoQA must not assert temporal change."""
    df = pd.DataFrame({"ndvi": [0.50, 0.95]})
    issues = validate_spectral_indices(df)
    assert [i for i in issues if "spike" in i.problem_name] == []


def test_band_radiance_reachable_and_flags_negative():
    df = pd.DataFrame({"b04": [0.10], "b08": [-0.02]})
    issues = validate_layer(df, "spectral")
    assert any(i.problem_name == "spectral_band_negative_radiance" for i in issues), \
        [i.problem_name for i in issues]