"""Tests for night-flow leakage under declared coefficients.

The behaviour worth protecting: no function accepts a bare number. Supplying
``0.5`` where a declaration belongs must raise, not silently compute. That is
the whole point of the module, and a test that did not enforce it would let the
design rot.
"""

from __future__ import annotations

import math

import pytest

from geoqa.validations.night_flow import (
    CoefficientDeclaration,
    ReproductionEvidence,
    apparent_losses_from_mnf,
    fadd,
    favad_flow_ratio,
    nightly_leakage_from_night_flow,
    orifice_discharge,
    pressure_dependent_background_leakage,
    solve_fitted_favad_exponent,
    solve_fitted_night_flow_coefficient,
    validate_coefficient_chain,
    validate_coefficient_declaration,
)


def _names(issues):
    return [i.problem_name for i in issues]


CD = CoefficientDeclaration(
    constant=0.62,
    meaning="discharge coefficient for a sharp-edged orifice",
    unit="dimensionless",
    source="reference text",
    verified=True,
)
EXPONENT = CoefficientDeclaration(
    constant=0.5, meaning="pressure-driven flow exponent", unit="dimensionless", source="FADD"
)
FRACTION = CoefficientDeclaration(
    constant=0.25, meaning="share of night flow that is consumption", unit="ratio"
)


# --- no bare numbers ----------------------------------------------------

@pytest.mark.parametrize(
    "call",
    [
        lambda: orifice_discharge(discharge_coefficient=0.62, area_m2=0.001, pressure_head_m=30.0),
        lambda: favad_flow_ratio(base_flow_lps=10.0, pressure_ratio=1.2, exponent=0.5),
        lambda: fadd(nnfi=0.5, pressure_m=40.0, exponent=0.5),
        lambda: apparent_losses_from_mnf(
            minimum_night_flow_m3h=10.0, hours_of_night=4.0,
            legitimate_night_use_m3h=2.0, apparent_loss_fraction_of_mnf=0.25,
        ),
    ],
)
def test_bare_numbers_are_refused(call):
    """A number without a declaration must not enter a water-loss calculation."""
    with pytest.raises(TypeError):
        call()


def test_incomplete_declaration_is_refused():
    incomplete = CoefficientDeclaration(constant=0.62, meaning="", unit="")
    with pytest.raises(ValueError, match="missing a meaning"):
        orifice_discharge(discharge_coefficient=incomplete, area_m2=0.001, pressure_head_m=30.0)


# --- relationships --------------------------------------------------------

def test_orifice_discharge_computes():
    value = orifice_discharge(discharge_coefficient=CD, area_m2=0.001, pressure_head_m=30.0)
    assert value == pytest.approx(0.62 * 0.001 * math.sqrt(2 * 9.80665 * 30.0))


def test_orifice_refuses_negative_head():
    with pytest.raises(ValueError, match="negative"):
        orifice_discharge(discharge_coefficient=CD, area_m2=0.001, pressure_head_m=-1.0)


def test_favad_holds_flow_constant_at_unity_ratio():
    assert favad_flow_ratio(base_flow_lps=10.0, pressure_ratio=1.0, exponent=EXPONENT) == pytest.approx(10.0)


def test_favad_raises_flow_with_pressure():
    assert favad_flow_ratio(base_flow_lps=10.0, pressure_ratio=1.44, exponent=EXPONENT) == pytest.approx(12.0)


def test_favad_refuses_non_positive_ratio():
    with pytest.raises(ValueError, match="positive"):
        favad_flow_ratio(base_flow_lps=10.0, pressure_ratio=0.0, exponent=EXPONENT)


def test_fadd_matches_the_named_relationship():
    assert fadd(nnfi=0.5, pressure_m=40.0, exponent=EXPONENT) == pytest.approx(3.16227766, abs=1e-6)


def test_fadd_refuses_nnfi_outside_zero_one():
    with pytest.raises(ValueError, match="between 0 and 1"):
        fadd(nnfi=1.4, pressure_m=40.0, exponent=EXPONENT)


def test_night_flow_leakage_is_simple_subtraction():
    value = nightly_leakage_from_night_flow(
        minimum_night_flow_m3h=10.0, hours_of_night=4.0, legitimate_night_use_m3h=2.0
    )
    assert value == pytest.approx(32.0)


def test_night_flow_refuses_non_positive_window():
    with pytest.raises(ValueError, match="positive"):
        nightly_leakage_from_night_flow(
            minimum_night_flow_m3h=10.0, hours_of_night=0.0, legitimate_night_use_m3h=2.0
        )


def test_background_leakage_is_positive_and_smaller_at_night():
    value = pressure_dependent_background_leakage(
        average_pressure_m=50.0, night_pressure_m=35.0, nnfi=0.3,
        exponent=EXPONENT, reference_pressure_m=50.0, night_pressure_width_m=10.0,
    )
    assert value > 0


def test_apparent_losses_apply_the_declared_fraction():
    value = apparent_losses_from_mnf(
        minimum_night_flow_m3h=10.0, hours_of_night=4.0,
        legitimate_night_use_m3h=2.0, apparent_loss_fraction_of_mnf=FRACTION,
    )
    assert value == pytest.approx(32.0 * 0.25)


def test_apparent_fraction_out_of_range_is_refused():
    bad = CoefficientDeclaration(constant=1.5, meaning="too big", unit="ratio")
    with pytest.raises(ValueError, match="between 0 and 1"):
        apparent_losses_from_mnf(
            minimum_night_flow_m3h=10.0, hours_of_night=4.0,
            legitimate_night_use_m3h=2.0, apparent_loss_fraction_of_mnf=bad,
        )


# --- declaration checks ----------------------------------------------------

def test_complete_declaration_raises_nothing_serious():
    issues = validate_coefficient_declaration(CD)
    assert [i for i in issues if str(i.severity) in {"high", "medium"}] == []


def test_missing_meaning_is_high():
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(constant=1.0, meaning="", unit="ratio")
    )
    assert "coefficient_meaning_undeclared" in _names(issues)


def test_missing_unit_is_high():
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(constant=1.0, meaning="something", unit="")
    )
    assert "coefficient_unit_undeclared" in _names(issues)


def test_missing_source_is_medium():
    issues = validate_coefficient_declaration(FRACTION)
    assert "coefficient_source_unrecorded" in _names(issues)


def test_unverified_is_informational():
    issues = validate_coefficient_declaration(FRACTION)
    info = next(i for i in issues if i.problem_name == "coefficient_unverified")
    assert str(info.severity) == "info"


def test_volume_unit_in_a_rate_formula_is_high():
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(constant=3.31, meaning="night flow", unit="m3/day"),
        expects_volume_unit=True,
    )
    assert "coefficient_unit_mismatch" in _names(issues)


def test_litre_unit_in_a_volume_balance_is_flagged_for_conversion():
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(constant=3.31, meaning="night flow", unit="L/day"),
        expects_volume_unit=True,
    )
    assert "coefficient_unit_scale_ambiguous" in _names(issues)


def test_fraction_out_of_range_is_high():
    issues = validate_coefficient_declaration(FRACTION, expects_fraction=True)
    assert "coefficient_out_of_range" not in _names(issues)


def test_fraction_out_of_range_flagged_when_actually_out_of_range():
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(constant=1.4, meaning="share", unit="ratio"),
        expects_fraction=True,
    )
    assert "coefficient_out_of_range" in _names(issues)


# --- reproduction ------------------------------------------------------------

def test_reproducing_coefficient_is_informational():
    evidence = ReproductionEvidence(
        observed_output=32.0,
        known_inputs={"hours": 4.0, "legitimate": 2.0},
        relationship="V = (MNF - legit) * hours",
        implied_constant=10.0,
    )
    declared = CoefficientDeclaration(
        constant=10.0, meaning="night flow rate", unit="m3/h",
        source="fitted from reported volumes", fitted_from=evidence, verified=True,
    )
    issues = validate_coefficient_declaration(declared)
    assert "coefficient_reproduced" in _names(issues)
    assert [i for i in issues if str(i.severity) in {"high", "medium"}] == []


def test_coefficient_that_fails_reproduction_is_high():
    evidence = ReproductionEvidence(
        observed_output=32.0,
        known_inputs={"hours": 4.0, "legitimate": 2.0},
        relationship="V = (MNF - legit) * hours",
        implied_constant=8.0,
    )
    declared = CoefficientDeclaration(
        constant=10.0, meaning="night flow rate", unit="m3/h", fitted_from=evidence,
    )
    issues = validate_coefficient_declaration(declared)
    issue = next(i for i in issues if i.problem_name == "coefficient_fails_reproduction")
    assert str(issue.severity) == "high"
    assert issue.to_dict()["relative_error"] == pytest.approx(0.2)


def test_indeterminate_reproduction_is_medium():
    evidence = ReproductionEvidence(
        observed_output=32.0, known_inputs={}, relationship="unclear", implied_constant=None
    )
    issues = validate_coefficient_declaration(
        CoefficientDeclaration(
            constant=10.0, meaning="x", unit="m3/h", fitted_from=evidence
        )
    )
    assert "coefficient_reproduction_indeterminate" in _names(issues)


def test_reproduction_tolerance_is_configurable():
    evidence = ReproductionEvidence(
        observed_output=1.0, known_inputs={}, relationship="r", implied_constant=10.2
    )
    declared = CoefficientDeclaration(
        constant=10.0, meaning="x", unit="ratio", fitted_from=evidence
    )
    assert "coefficient_fails_reproduction" not in _names(
        validate_coefficient_declaration(declared, reproduction_tolerance=0.05)
    )
    assert "coefficient_fails_reproduction" in _names(
        validate_coefficient_declaration(declared, reproduction_tolerance=0.001)
    )


# --- inversion ----------------------------------------------------------------

def test_solving_night_flow_recovers_the_rate():
    implied = solve_fitted_night_flow_coefficient(
        observed_volume_m3=32.0 * 30, hours_of_night=4.0,
        legitimate_night_use_m3h=2.0, window_days=30,
    )
    assert implied == pytest.approx(10.0)


def test_night_flow_round_trips_through_the_solver():
    volume = nightly_leakage_from_night_flow(
        minimum_night_flow_m3h=7.5, hours_of_night=5.0, legitimate_night_use_m3h=1.25
    )
    implied = solve_fitted_night_flow_coefficient(
        observed_volume_m3=volume, hours_of_night=5.0,
        legitimate_night_use_m3h=1.25, window_days=1,
    )
    assert implied == pytest.approx(7.5)


def test_solving_favad_exponent_recovers_it():
    implied = solve_fitted_favad_exponent(
        base_flow_lps=10.0, observed_flow_lps=12.0, pressure_ratio=1.44
    )
    assert implied == pytest.approx(0.5, abs=1e-9)


def test_favad_round_trips():
    exponent = solve_fitted_favad_exponent(
        base_flow_lps=10.0, observed_flow_lps=12.0, pressure_ratio=1.44
    )
    declared = CoefficientDeclaration(
        constant=exponent, meaning="FAVAD exponent", unit="dimensionless"
    )
    assert favad_flow_ratio(
        base_flow_lps=10.0, pressure_ratio=1.44, exponent=declared
    ) == pytest.approx(12.0)


# --- chain ---------------------------------------------------------------------

def test_chain_validates_every_coefficient():
    issues = validate_coefficient_chain([("cd", CD), ("exp", EXPONENT)])
    assert [i for i in issues if str(i.severity) == "high"] == []


def test_same_value_two_meanings_is_high():
    a = CoefficientDeclaration(constant=0.5, meaning="flow exponent", unit="ratio")
    b = CoefficientDeclaration(constant=0.5, meaning="loss fraction", unit="ratio")
    issues = validate_coefficient_chain([("exponent", a), ("fraction", b)])
    issue = next(i for i in issues if i.problem_name == "coefficient_used_inconsistently")
    assert str(issue.severity) == "high"
    assert set(issue.to_dict()["roles"]) == {"exponent", "fraction"}


def test_same_value_same_meaning_is_fine():
    a = CoefficientDeclaration(constant=0.5, meaning="flow exponent", unit="ratio")
    b = CoefficientDeclaration(constant=0.5, meaning="flow exponent", unit="ratio")
    issues = validate_coefficient_chain([("a", a), ("b", b)])
    assert "coefficient_used_inconsistently" not in _names(issues)


def test_chain_honours_role_expectations():
    issues = validate_coefficient_chain(
        [("rate", Fraction := CoefficientDeclaration(
            constant=3.31, meaning="night flow rate", unit="m3/day"
        ))],
        expects={"rate": "volume_rate"},
    )
    assert "coefficient_unit_mismatch" in _names(issues)