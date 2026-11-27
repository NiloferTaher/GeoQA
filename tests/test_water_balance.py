"""Tests for the IWA water balance.

The behaviour worth protecting is the one that makes this a balance rather than
a spreadsheet: losses are derived from components, and a caller who types in a
loss total alongside the components that should produce it gets told they
disagree.

Every fixture here closes exactly. A test that does not close would be testing
arithmetic on bad inputs.
"""

from __future__ import annotations

import pytest

from geoqa.validations.water_balance import (
    APPARENT_LOSS_COMPONENTS,
    REAL_LOSS_COMPONENTS,
    WaterBalanceInputs,
    compute_water_balance,
    nrw_from_components,
    validate_water_balance,
)


def _closing_inputs(**overrides) -> WaterBalanceInputs:
    """A balance where SOV == SIV exactly.

    SIV 100000. Authorised 80000, real losses 16000, apparent 4000.
    """
    defaults = dict(
        system_input_volume=100_000.0,
        supplier_water=100_000.0,
        billed_consumption=70_000.0,
        unbilled_consumption=10_000.0,
        real_loss_components={"distribution_main_leakage": 16_000.0},
        apparent_loss_components={"unbilled_consumption": 4_000.0},
    )
    defaults.update(overrides)
    return WaterBalanceInputs(**defaults)


def _names(issues) -> list[str]:
    return [i.problem_name for i in issues]


def test_components_all_present_after_construction():
    inputs = WaterBalanceInputs(system_input_volume=1000.0)
    for name in REAL_LOSS_COMPONENTS:
        assert name in inputs.real_loss_components
    for name in APPARENT_LOSS_COMPONENTS:
        assert name in inputs.apparent_loss_components


def test_balances_exactly():
    result = compute_water_balance(_closing_inputs())
    assert result.supply_total == 100_000.0
    assert result.authorised_consumption == 80_000.0
    assert result.real_losses == 16_000.0
    assert result.apparent_losses == 4_000.0
    assert result.non_revenue_water == 20_000.0
    assert result.system_output_volume == 100_000.0
    assert result.closure_error == 0.0


def test_nrw_percentage():
    result = compute_water_balance(_closing_inputs())
    assert result.nrw_percentage == pytest.approx(20.0)


def test_a_closing_balance_produces_no_high_issues():
    issues = validate_water_balance(_closing_inputs())
    assert [i for i in issues if str(i.severity) in {"high", "critical"}] == []


def test_supply_mismatch_is_high():
    inputs = _closing_inputs(supplier_water=90_000.0)
    issues = validate_water_balance(inputs)
    mismatch = next(i for i in issues if i.problem_name == "water_balance_supply_mismatch")
    assert str(mismatch.severity) == "high"
    assert mismatch.to_dict()["difference"] == pytest.approx(-10_000.0)


def test_exported_water_counts_toward_supply():
    inputs = _closing_inputs(
        supplier_water=80_000.0, exported_water=20_000.0
    )
    result = compute_water_balance(inputs)
    assert result.closure_error == 0.0


def test_declared_real_losses_must_agree_with_components():
    inputs = _closing_inputs(declared_real_losses=16_000.0)
    names = _names(validate_water_balance(inputs))
    assert "water_balance_loss_mismatch" not in names


def test_typed_in_real_losses_that_disagree_are_flagged():
    """The core protection: losses are derived, never entered."""
    inputs = _closing_inputs(declared_real_losses=9_000.0)
    issue = next(
        i for i in validate_water_balance(inputs)
        if i.problem_name == "water_balance_loss_mismatch"
    )
    assert str(issue.severity) == "high"
    assert issue.to_dict()["declared_real_losses"] == 9_000.0
    assert issue.to_dict()["derived_real_losses"] == 16_000.0


def test_declared_nrw_must_agree():
    inputs = _closing_inputs(declared_nrw=25_000.0)
    issue = next(i for i in validate_water_balance(inputs) if i.problem_name == "water_balance_nrw_mismatch")
    assert issue.to_dict()["difference"] == pytest.approx(5_000.0)


def test_negative_real_loss_component_is_flagged():
    inputs = _closing_inputs(
        real_loss_components={"distribution_main_leakage": 20_000.0, "storage_losses": -4_000.0}
    )
    assert "water_balance_negative_component" in _names(validate_water_balance(inputs))


def test_nrw_above_input_is_critical():
    inputs = WaterBalanceInputs(
        system_input_volume=10_000.0,
        supplier_water=10_000.0,
        billed_consumption=1_000.0,
        real_loss_components={"distribution_main_leakage": 12_000.0},
    )
    issue = next(i for i in validate_water_balance(inputs) if i.problem_name == "water_balance_nrw_exceeds_input")
    assert str(issue.severity) == "critical"


def test_ili_computed_when_uarl_supplied():
    result = compute_water_balance(
        _closing_inputs(), days_in_period=365.0, uarl=8_000.0
    )
    assert result.ili is not None
    # 16000 m3 over 365 days -> CARL in L/day
    assert result.cawl == pytest.approx(1_000.0 * 16_000 / 365)


def test_ili_not_computed_without_uarl():
    result = compute_water_balance(_closing_inputs(), days_in_period=365.0)
    assert result.ili is None
    assert "ili_not_computable" in _names(validate_water_balance(_closing_inputs(), result))


def test_ili_is_never_a_verdict():
    """IWA is explicit: ILI must not be used alone for target setting."""
    inputs = _closing_inputs()
    result = compute_water_balance(inputs, days_in_period=365.0, uarl=8_000.0)
    issue = next(i for i in validate_water_balance(inputs, result) if i.problem_name == "ili_requires_context")
    assert str(issue.severity) == "medium"
    assert "not be used in isolation" in issue.description


def test_ili_note_is_recorded_in_the_result():
    result = compute_water_balance(_closing_inputs(), days_in_period=365.0, uarl=8_000.0)
    assert any("Water Loss Specialist Group" in note for note in result.notes)


def test_carl_can_be_supplied_directly():
    result = compute_water_balance(
        _closing_inputs(), days_in_period=365.0, uarl=8_000.0, cawl=20_000.0
    )
    assert result.ili == pytest.approx(2.5)


def test_night_flow_apparent_losses_take_precedence_and_are_flagged():
    inputs = _closing_inputs(night_flow_apparent_losses=6_000.0)
    result = compute_water_balance(inputs)
    assert result.apparent_losses == 6_000.0
    assert result.derived_apparent_losses is True
    assert result.apparent_loss_components["night_flow_residual"] == pytest.approx(2_000.0)
    assert "water_balance_night_flow_residual" in _names(validate_water_balance(inputs, result))


def test_small_night_flow_residual_is_tolerated():
    inputs = _closing_inputs(night_flow_apparent_losses=4_050.0)
    result = compute_water_balance(inputs)
    assert "water_balance_night_flow_residual" not in _names(validate_water_balance(inputs, result))


def test_revenue_water_includes_unbilled_billed():
    inputs = _closing_inputs(unbilled_billed=1_000.0)
    result = compute_water_balance(inputs)
    assert result.revenue_water == pytest.approx(71_000.0)


def test_result_serialises_every_intermediate():
    result = compute_water_balance(_closing_inputs())
    payload = result.as_dict()
    for key in (
        "system_input_volume_m3",
        "authorised_consumption_m3",
        "real_losses_m3",
        "apparent_losses_m3",
        "non_revenue_water_m3",
        "system_output_volume_m3",
        "nrw_percent",
    ):
        assert key in payload


def test_convenience_constructor_closes():
    result = nrw_from_components(
        system_input_volume=100_000.0,
        supplier_water=100_000.0,
        real_losses={"distribution_main_leakage": 16_000.0},
        apparent_losses={"unbilled_consumption": 4_000.0},
        billed_consumption=70_000.0,
        unbilled_consumption=10_000.0,
    )
    assert result.system_output_volume == result.system_input_volume


def test_zero_input_volume_does_not_divide_by_zero():
    inputs = WaterBalanceInputs(system_input_volume=0.0)
    result = compute_water_balance(inputs)
    assert result.nrw_percentage == 0.0
    assert validate_water_balance(inputs) is not None


def test_all_zero_balance_is_valid():
    inputs = WaterBalanceInputs(system_input_volume=100_000.0, supplier_water=100_000.0)
    issues = validate_water_balance(inputs)
    assert [i for i in issues if str(i.severity) == "high"] == []


def test_real_loss_components_sum_rather_than_overwrite():
    inputs = WaterBalanceInputs(
        system_input_volume=100_000.0,
        supplier_water=100_000.0,
        real_loss_components={
            "distribution_main_leakage": 10_000.0,
            "service_connection_leakage": 4_000.0,
            "transmission_main_leakage": 2_000.0,
        },
    )
    assert compute_water_balance(inputs).real_losses == 16_000.0