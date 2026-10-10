"""Runtime tests for the water_loss and repeat_incident dataset types."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoqa.validation_runtime import execute_validation_plan
from geoqa.validations.night_flow import CoefficientDeclaration
from geoqa.validations.water_loss import PressureFactor, UarlInputs, compute_uarl_l_per_day, ili_assessment


MAIN = CoefficientDeclaration(18.0, "Lambert mains", "L/day per km", "reference")
CONN = CoefficientDeclaration(0.8, "Lambert connection", "L/day per connection", "reference")
PRIV = CoefficientDeclaration(25.0, "Lambert private", "L/day per km", "reference")


def _layer():
    rows = [
        {"period": "2025-01", "asset": "P1", "geometry": Point(0, 0)},
        {"period": "2025-02", "asset": "P1", "geometry": Point(0, 0)},
        {"period": "2025-01", "asset": "P7", "geometry": Point(900, 900)},
        {"period": "2025-02", "asset": "P8", "geometry": Point(900, 900)},
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:32640")


# --- water_loss ---------------------------------------------------------------

def test_water_loss_type_runs_and_reports_context():
    inputs = UarlInputs(
        mains_length_km=1000.0,
        service_connections=5000,
        private_pipe_length_km=200.0,
        pressure_factor=PressureFactor(50.0, "modelled", measured=False),
    )
    assessment = ili_assessment(
        annual_real_loss_m3=730_000.0,
        input_volume_m3_per_year=3_650_000.0,
        uarl_l_per_day=compute_uarl_l_per_day(
            inputs, main_length_coefficient=MAIN,
            connections_coefficient=CONN, private_length_coefficient=PRIV,
        ),
    )
    result = execute_validation_plan(
        _layer(), dataset_type="water_loss",
        return_result=True, assessment=assessment, uarl_inputs=inputs,
    )
    names = {i.problem_name for i in result.issues}
    assert "ili_requires_context" in names
    assert "uarl_pressure_factor_estimated" in names
    assert result.partial_result is False


def test_water_loss_without_assessment_is_a_clean_no_op():
    result = execute_validation_plan(
        _layer(), dataset_type="water_loss", return_result=True
    )
    assert result.issues == []
    assert result.partial_result is False


# --- repeat_incident ----------------------------------------------------------

def test_repeat_incident_type_separates_the_two_causes():
    result = execute_validation_plan(
        _layer(), dataset_type="repeat_incident",
        return_result=True, period_column="period", key_column="asset",
    )
    names = {i.problem_name for i in result.issues}
    assert "repeat_same_asset" in names
    assert "repeat_same_place" in names


def test_repeat_incident_reports_missing_period():
    result = execute_validation_plan(
        _layer(), dataset_type="repeat_incident",
        return_result=True,
        period_column="period", key_column="asset",
        expected_periods=["2025-01", "2025-02", "2025-03"],
    )
    missing = next(i for i in result.issues if i.problem_name == "period_missing")
    assert missing.to_dict()["missing_period"] == "2025-03"


def test_repeat_incident_without_period_column_is_a_clean_no_op():
    result = execute_validation_plan(
        _layer(), dataset_type="repeat_incident", return_result=True
    )
    assert result.issues == []
    assert result.partial_result is False


def test_repeat_incident_unattributed_without_key_column():
    result = execute_validation_plan(
        _layer(), dataset_type="repeat_incident",
        return_result=True, period_column="period",
    )
    assert any(i.problem_name == "repeat_unattributed" for i in result.issues)