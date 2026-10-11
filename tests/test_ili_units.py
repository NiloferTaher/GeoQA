from geoqa.validations.water_balance import WaterBalanceInputs, compute_water_balance
from geoqa.validations.water_loss import ili_assessment


def test_ili_assessment_converts_cubic_meters_to_liters_per_day() -> None:
    assessment = ili_assessment(
        annual_real_loss_m3=4_000_000,
        input_volume_m3_per_year=20_000_000,
        uarl_l_per_day=2_520_000,
        accounting_days=328.5,
    )

    assert assessment.ili is not None
    assert abs(assessment.ili - 4.83) / 4.83 < 0.01


def test_compute_water_balance_converts_cubic_meters_to_liters_per_day() -> None:
    result = compute_water_balance(
        WaterBalanceInputs(
            system_input_volume=20_000_000,
            real_loss_components={"distribution_main_leakage": 4_000_000},
        ),
        days_in_period=328.5,
        uarl=2_520_000,
    )

    assert result.ili is not None
    assert abs(result.ili - 4.83) / 4.83 < 0.01
