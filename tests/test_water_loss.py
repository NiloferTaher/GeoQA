"""Tests for UARL and the Infrastructure Leakage Index.

Two properties are load-bearing here. First, Lambert's multipliers are declared
like any other empirical coefficient, so a bare ``18`` cannot enter the
regression. Second, ILI is never returned without its caveats attached.
"""

from __future__ import annotations

import pytest

from geoqa.validations.night_flow import CoefficientDeclaration
from geoqa.validations.water_loss import (
    PressureFactor,
    UarlInputs,
    compute_uarl_l_per_day,
    ili_assessment,
    infrastructure_leakage_index,
    lambert_coefficient_templates,
    validate_water_loss,
)


MAIN = CoefficientDeclaration(18.0, "Lambert mains-length coefficient", "L/day per km", "reference")
CONN = CoefficientDeclaration(0.8, "Lambert connection coefficient", "L/day per connection", "reference")
PRIV = CoefficientDeclaration(25.0, "Lambert private-length coefficient", "L/day per km", "reference")


def _inputs(**overrides):
    defaults = dict(
        mains_length_km=1000.0,
        service_connections=5000,
        private_pipe_length_km=200.0,
        pressure_factor=PressureFactor(average_pressure_m=50.0, method="modelled", measured=False),
    )
    defaults.update(overrides)
    return UarlInputs(**defaults)


def _names(issues):
    return [i.problem_name for i in issues]


# --- declarations are mandatory --------------------------------------------

def test_bare_lambert_multiplier_is_refused():
    with pytest.raises(TypeError, match="CoefficientDeclaration"):
        compute_uarl_l_per_day(
            _inputs(), main_length_coefficient=18.0,
            connections_coefficient=CONN, private_length_coefficient=PRIV,
        )


def test_incomplete_declaration_is_refused():
    incomplete = CoefficientDeclaration(18.0, "", "")
    with pytest.raises(ValueError, match="missing a meaning"):
        compute_uarl_l_per_day(
            _inputs(), main_length_coefficient=incomplete,
            connections_coefficient=CONN, private_length_coefficient=PRIV,
        )


def test_templates_are_unpopulated_but_now_cited():
    """Still no default value, but the source is no longer unknown."""
    for template in lambert_coefficient_templates():
        assert template["constant"] is None
        assert template["source"], "a template should carry its citation"
        assert template["published_value"] in (18.0, 0.80, 25.0)


def test_templates_expose_their_role_for_lookup():
    roles = {t["role"] for t in lambert_coefficient_templates()}
    assert roles == {"mains", "connections", "private"}


# --- the regression ------------------------------------------------------------

def test_uarl_computes():
    value = compute_uarl_l_per_day(
        _inputs(),
        main_length_coefficient=MAIN,
        connections_coefficient=CONN,
        private_length_coefficient=PRIV,
    )
    # (18*1000 + 0.8*5000 + 25*200) * 50 = (18000 + 4000 + 5000) * 50
    assert value == pytest.approx(27_000 * 50)


def test_uarl_scales_linearly_with_pressure():
    low = compute_uarl_l_per_day(
        _inputs(pressure_factor=PressureFactor(30.0, "modelled")),
        main_length_coefficient=MAIN, connections_coefficient=CONN,
        private_length_coefficient=PRIV,
    )
    high = compute_uarl_l_per_day(
        _inputs(pressure_factor=PressureFactor(60.0, "modelled")),
        main_length_coefficient=MAIN, connections_coefficient=CONN,
        private_length_coefficient=PRIV,
    )
    assert high == pytest.approx(low * 2.0)


def test_zero_connections_is_allowed_but_flagged():
    inputs = _inputs(service_connections=0)
    issues = validate_water_loss(
        ili_assessment(
            annual_real_loss_m3=1_000_000.0, input_volume_m3_per_year=5_000_000.0,
            uarl_l_per_day=compute_uarl_l_per_day(
                inputs, main_length_coefficient=MAIN,
                connections_coefficient=CONN, private_length_coefficient=PRIV,
            ),
        ),
        uarl_inputs=inputs,
    )
    assert "uarl_missing_connections" in _names(issues)


def test_negative_length_is_refused():
    with pytest.raises(ValueError, match="negative"):
        _inputs(mains_length_km=-1.0)


def test_non_positive_pressure_is_refused():
    with pytest.raises(ValueError, match="positive"):
        _inputs(pressure_factor=PressureFactor(0.0, "modelled"))


# --- ILI -------------------------------------------------------------------------

def test_ili_is_the_ratio():
    assert infrastructure_leakage_index(carl_l_per_day=4_000.0, uarl_l_per_day=2_000.0) == 2.0


def test_ili_refuses_zero_uarl():
    with pytest.raises(ValueError, match="UARL must be positive"):
        infrastructure_leakage_index(carl_l_per_day=4_000.0, uarl_l_per_day=0.0)


def test_assessment_computes_carl_and_ili():
    result = ili_assessment(
        annual_real_loss_m3=730_000.0, input_volume_m3_per_year=3_650_000.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert result.carl_l_per_day == pytest.approx(2_000_000.0)
    assert result.ili == pytest.approx(1.0)
    assert result.nrw_percent == pytest.approx(20.0, abs=0.1)


def test_no_uarl_means_no_ili_and_a_recorded_gap():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=None,
    )
    assert result.ili is None
    assert any("UARL" in gap for gap in result.blocking_gaps)


def test_ili_always_carries_the_iwa_caveat():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert any("IWA Water Loss Specialist Group" in c for c in result.caveats)


def test_estimated_pressure_is_caveated():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
        pressure_factor=PressureFactor(50.0, "modelled", measured=False),
    )
    assert any("estimated rather than measured" in c for c in result.caveats)


def test_measured_pressure_is_not_caveated():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
        pressure_factor=PressureFactor(50.0, "SCADA", measured=True),
    )
    assert not any("estimated rather than measured" in c for c in result.caveats)


def test_ili_requires_context_is_reported_when_computable():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert "ili_requires_context" in _names(validate_water_loss(result))


def test_declared_threshold_adds_a_comparison_and_keeps_the_caveat():
    threshold = CoefficientDeclaration(2.5, "target ILI", "ratio", "asset strategy")
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0, ili_threshold_coefficient=threshold,
    )
    assert any("threshold" in c for c in result.caveats)
    assert any("IWA" in c for c in result.caveats)


# --- implausible results -------------------------------------------------------------

def test_very_low_ili_is_flagged():
    result = ili_assessment(
        annual_real_loss_m3=219.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert "ili_below_possible_range" in _names(validate_water_loss(result))


def test_losses_exceeding_input_are_critical():
    result = ili_assessment(
        annual_real_loss_m3=5_000.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    issue = next(i for i in validate_water_loss(result) if i.problem_name == "nrw_exceeds_input")
    assert str(issue.severity) == "critical"


def test_short_accounting_period_is_caveated():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=8_000.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert any("below 1 m3/h" in c for c in result.caveats)


def test_estimated_pressure_flagged_in_validation():
    inputs = _inputs()
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    assert "uarl_pressure_factor_estimated" in _names(validate_water_loss(result, uarl_inputs=inputs))


def test_zero_input_volume_is_refused():
    with pytest.raises(ValueError, match="input volume"):
        ili_assessment(annual_real_loss_m3=1.0, input_volume_m3_per_year=0.0, uarl_l_per_day=1.0)


def test_negative_real_losses_are_refused():
    with pytest.raises(ValueError, match="cannot be negative"):
        ili_assessment(annual_real_loss_m3=-1.0, input_volume_m3_per_year=1000.0, uarl_l_per_day=1.0)


def test_assessment_serialises_everything():
    result = ili_assessment(
        annual_real_loss_m3=730.0, input_volume_m3_per_year=3_650.0,
        uarl_l_per_day=2_000_000.0,
    )
    payload = result.as_dict()
    for key in ("ili", "carl_l_per_day", "uarl_l_per_day", "caveats", "blocking_gaps"):
        assert key in payload


# --- end to end ----------------------------------------------------------------------

def test_full_chain_from_network_to_index():
    inputs = _inputs(pressure_factor=PressureFactor(50.0, "SCADA", measured=True))
    uarl = compute_uarl_l_per_day(
        inputs, main_length_coefficient=MAIN,
        connections_coefficient=CONN, private_length_coefficient=PRIV,
    )
    result = ili_assessment(
        annual_real_loss_m3=uarl * _days / 1_000.0,
        input_volume_m3_per_year=3_650_000.0,
        uarl_l_per_day=uarl,
        pressure_factor=inputs.pressure_factor,
    )
    assert result.ili == pytest.approx(1.0, abs=1e-6)
    assert not any("estimated rather than measured" in c for c in result.caveats)


_days = 365.0