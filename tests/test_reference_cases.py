"""Tests for the published coefficient reference cases.

The behaviour worth protecting: these cases must actually run, and must fail
when the arithmetic they check is broken. A reference case that always passes is
worse than none, because it manufactures confidence.
"""

from __future__ import annotations

import pytest

from geoqa.validations.reference_cases import (
    UARL_APPLICABILITY_LIMITS,
    ReferenceCase,
    all_reference_cases,
    aqua1999_ili_case,
    aqua1999_tirl_case,
    aqua1999_uarl_example,
    check_uarl_applicability,
    compute_reference_case,
    iwa_taskforce_uarl_case,
    lambert2009_background_leakage_case,
    run_reference_case,
    run_reference_cases,
    validate_reference_cases,
    validate_uarl_applicability,
)


def _names(issues):
    return [i.problem_name for i in issues]


# --- the cases reproduce the publications ---------------------------------

@pytest.mark.parametrize("case", all_reference_cases(), ids=lambda c: c.name)
def test_case_reproduces_its_published_value(case):
    result = run_reference_case(case)
    assert result.passed, (
        f"{case.name} computed {result.computed_value} against a published "
        f"{case.published_value} {case.published_units}"
    )


def test_iwa_case_reproduces_to_five_significant_figures():
    """The IWA example is exact: (18*603 + 0.8*16359 + 0) * 65 / 1000 = 1556.178."""
    result = run_reference_case(iwa_taskforce_uarl_case())
    assert result.computed_value == pytest.approx(1556.178)
    assert result.relative_error < 0.0002


def test_background_leakage_case_is_exact():
    result = run_reference_case(lambert2009_background_leakage_case())
    assert result.computed_value == pytest.approx(3.25)


def test_ili_case_reproduces():
    assert compute_reference_case(aqua1999_ili_case()) == pytest.approx(4.8095, abs=1e-4)


def test_tirl_case_reproduces():
    """202 l/conn/day from 4,000,000 m3/yr over 60,000 connections at 90 percent."""
    assert compute_reference_case(aqua1999_tirl_case()) == pytest.approx(202.94, abs=0.1)


def test_aqua_uarl_components_are_reproducible():
    """The published mains and connections components match the arithmetic exactly."""
    from geoqa.validations.reference_cases import AQUA_DAYS_PRESSURISED

    inputs = aqua1999_uarl_example().inputs
    mains = 18.0 * inputs["mains_length_km"] * inputs["average_pressure_m"] * AQUA_DAYS_PRESSURISED / 1e6
    connections = 0.8 * inputs["service_connections"] * inputs["average_pressure_m"] * AQUA_DAYS_PRESSURISED / 1e6
    assert mains == pytest.approx(266.0, abs=1.0)
    assert connections == pytest.approx(473.0, abs=1.0)


def test_aqua_discrepancy_is_documented_not_hidden():
    """The 2 percent private-pipe gap is recorded, not absorbed by a loose tolerance."""
    case = aqua1999_uarl_example()
    assert case.rounding_note is not None
    assert "88.7" in case.rounding_note
    assert case.tolerance < 0.02


# --- the harness must be capable of failing ---------------------------------

def test_a_broken_case_fails():
    """If the check cannot fail, it is not a check."""
    case = ReferenceCase(
        name="deliberately_wrong",
        citation="none",
        quantity="nothing",
        inputs={},
        published_value=1.0,
        published_units="units",
    )
    # No implementation exists for this name.
    result = run_reference_case(case)
    assert result.passed is False
    assert "no implementation" in (result.detail or "")


def test_wrong_published_value_is_caught():
    case = ReferenceCase(
        name="iwa_taskforce_uarl_case",
        citation="x",
        quantity="UARL",
        inputs={
            "mains_length_km": 603.0, "service_connections": 16_359.0,
            "private_length_km": 0.0, "average_pressure_m": 65.0,
        },
        published_value=9999.0,
        published_units="m3/day",
        tolerance=0.001,
    )
    assert run_reference_case(case).passed is False


def test_out_of_range_arithmetic_would_be_caught():
    """A wrong coefficient must not silently pass."""
    from geoqa.validations import reference_cases as module

    inputs = iwa_taskforce_uarl_case().inputs
    wrong = (17.0 * inputs["mains_length_km"] + 0.8 * inputs["service_connections"]) * inputs["average_pressure_m"] / 1000
    correct = compute_reference_case(iwa_taskforce_uarl_case())
    assert abs(wrong - correct) / correct > module.iwa_taskforce_uarl_case().tolerance


# --- reporting --------------------------------------------------------------

def test_all_cases_pass_and_are_reported_as_evidence():
    issues = validate_reference_cases()
    assert _names(issues) == ["coefficient_reference_case_passed"] * 5
    assert all(str(i.severity) == "info" for i in issues)


def test_failure_is_critical():
    case = ReferenceCase(
        name="iwa_taskforce_uarl_case", citation="x", quantity="UARL",
        inputs={"mains_length_km": 1.0, "service_connections": 0.0,
                "private_length_km": 0.0, "average_pressure_m": 65.0},
        published_value=9999.0, published_units="m3/day", tolerance=0.001,
    )
    issues = validate_reference_cases([case])
    assert _names(issues) == ["coefficient_reference_case_failed"]
    assert str(issues[0].severity) == "critical"


def test_results_carry_the_citation():
    result = run_reference_case(iwa_taskforce_uarl_case())
    assert "IWA Water Balance Task Force" in result.case.citation


# --- applicability ------------------------------------------------------------

def test_network_inside_the_limits():
    report = check_uarl_applicability(
        service_connections=60_000, mains_length_km=1500, average_pressure_m=30
    )
    assert report["within_limits"] is True
    assert validate_uarl_applicability(
        service_connections=60_000, mains_length_km=1500, average_pressure_m=30
    ) == []


def test_small_network_is_reported():
    """A 300-connection system is far below the stated minimum."""
    issues = validate_uarl_applicability(
        service_connections=300, mains_length_km=20, average_pressure_m=30
    )
    issue = next(i for i in issues if i.problem_name == "coefficient_uarl_outside_applicability")
    assert str(issue.severity) == "high"
    assert "300" in issue.description


def test_low_density_is_reported():
    issues = validate_uarl_applicability(
        service_connections=6000, mains_length_km=1000, average_pressure_m=30
    )
    assert "connection density" in " ".join(i.description for i in issues)


def test_low_pressure_is_reported():
    issues = validate_uarl_applicability(
        service_connections=60_000, mains_length_km=1500, average_pressure_m=10
    )
    assert "pressure" in " ".join(i.description for i in issues)


def test_zero_length_does_not_divide_by_zero():
    report = check_uarl_applicability(
        service_connections=60_000, mains_length_km=0, average_pressure_m=30
    )
    assert report["connection_density_per_km"] == 0.0
    assert report["within_limits"] is False


def test_limits_come_from_the_source():
    assert UARL_APPLICABILITY_LIMITS["min_service_connections"] == 5000
    assert UARL_APPLICABILITY_LIMITS["min_connection_density_per_km"] == 20
    assert UARL_APPLICABILITY_LIMITS["min_average_pressure_m"] == 25


def test_relaxation_is_recorded_rather_than_assumed():
    from geoqa.validations.reference_cases import UARL_LIMITS_RELAXED_2009

    assert "Lambert (2009)" in UARL_LIMITS_RELAXED_2009["note"]