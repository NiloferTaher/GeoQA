import pytest

from geoqa.validations.reference_cases import _aqua_coefficient_declarations
from geoqa.validations.water_loss import (
    PressureFactor,
    UarlInputs,
    compute_uarl_l_per_day,
    ili_assessment,
    validate_water_loss,
)


def _coefficients():
    declarations = _aqua_coefficient_declarations()
    return {
        "main_length_coefficient": declarations["mains"],
        "connections_coefficient": declarations["connections"],
        "private_length_coefficient": declarations["private"],
    }


def _inputs(pressure_factor=None):
    return UarlInputs(
        mains_length_km=1500,
        service_connections=60_000,
        private_pipe_length_km=360,
        pressure_factor=pressure_factor,
    )


def _assessment():
    return ili_assessment(
        annual_real_loss_m3=4_000_000,
        input_volume_m3_per_year=20_000_000,
        uarl_l_per_day=2_520_000,
        accounting_days=328.5,
    )


def test_uarl_computes_with_declared_measured_pressure() -> None:
    inputs = _inputs(PressureFactor(30, "measured", measured=True))

    assert compute_uarl_l_per_day(inputs, **_coefficients()) == 2_520_000


def test_uarl_requires_declared_pressure() -> None:
    with pytest.raises(ValueError, match="Average pressure was not declared"):
        compute_uarl_l_per_day(_inputs(), **_coefficients())


def test_uarl_inputs_serializes_missing_pressure_as_none() -> None:
    assert _inputs().as_dict()["pressure_factor"] is None


def test_validation_reports_missing_or_estimated_pressure() -> None:
    missing_issues = validate_water_loss(_assessment(), uarl_inputs=_inputs())
    missing_pressure = next(
        issue for issue in missing_issues
        if issue.problem_name == "uarl_pressure_factor_estimated"
    )
    assert str(missing_pressure.severity) == "high"
    assert "average pressure was not declared" in missing_pressure.description.lower()

    estimated_issues = validate_water_loss(
        _assessment(),
        uarl_inputs=_inputs(PressureFactor(30, "estimated", measured=False)),
    )
    assert any(
        issue.problem_name == "uarl_pressure_factor_estimated"
        for issue in estimated_issues
    )

    measured_issues = validate_water_loss(
        _assessment(),
        uarl_inputs=_inputs(PressureFactor(30, "measured", measured=True)),
    )
    assert not any(
        issue.problem_name == "uarl_pressure_factor_estimated"
        for issue in measured_issues
    )
