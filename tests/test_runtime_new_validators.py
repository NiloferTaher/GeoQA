"""Runtime wiring for the schema, governance and EPANET validators.

These three arrived after the original runtime was written, and each needed a
decision the spectral validator already answered: how does a validator that does
not inspect geometry get called by ``validate_layer()``?

The answer used for spectral, and used here, is that it becomes its own dataset
type. That keeps ``validate_layer()`` honest -- it receives a dataset, decides
which checks apply, and runs them -- instead of bolting non-geometry checks onto
a geometry profile where they would be meaningless.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from geoqa.validation_runtime import execute_validation_plan, list_custom_validators

VENDOR_PHOTO = (
    '___json[{"pathname":"/Collected Media/2025-08/mdc_photo_812.jpg",'
    '"title":"IMG-0041.jpg"}]'
)

EWA_SOURCE = """
Unreportable Main Line Water Volume
sum("ewa_card_kpis"."unreportable_main")*(3.31*24*180)/1000000

Unreportable Main Line Water Savings
"ewa_card_kpis"."Unreportable Main Line Water Volume"*0.3*1000000

Crewdays
sum("ewa_crewmath"."owner_hours")/6.5
"""

DECK = """[JUNCTIONS]
 J1  710  10
 J2  700  20

[RESERVOIRS]
 R1  800

[PIPES]
 P1  R1  J1  400  400  100
 P2  J1  J2  500  300  100

[REACTIONS]
;Type     Pipe/C Tank  Global
 ORDER    1      0      0

[OPTIONS]
 Units SI
 Flow Units LPS
"""


def _layer(**columns) -> gpd.GeoDataFrame:
    length = max((len(v) for v in columns.values()), default=1)
    return gpd.GeoDataFrame(
        columns, geometry=[Point(i, i) for i in range(length)], crs="EPSG:4326"
    )


def test_payload_columns_runs_through_the_runtime():
    layer = _layer(photo=[VENDOR_PHOTO] * 4)
    result = execute_validation_plan(layer, "schema", return_result=True)
    assert "json_in_text_column" in {i.problem_name for i in result.issues}


def test_payload_columns_can_be_restricted_via_context():
    layer = _layer(photo=[VENDOR_PHOTO] * 4, note=["x"] * 4)
    result = execute_validation_plan(
        layer, "schema", payload_columns=["note"], return_result=True
    )
    assert result.issues == []


def test_payload_columns_clean_layer_yields_nothing():
    layer = _layer(comments=["no leaks", "wet soil", "under construction"])
    result = execute_validation_plan(layer, "schema", return_result=True)
    assert result.issues == []


def test_metric_constants_runs_through_the_runtime():
    result = execute_validation_plan(
        None, "governance", metric_source=EWA_SOURCE, return_result=True
    )
    names = [i.problem_name for i in result.issues]
    assert names.count("unlabelled_physical_constant") == 3
    constants = {i.to_dict()["constant"] for i in result.issues}
    assert constants == {"3.31", "0.3", "6.5"}


def test_metric_constants_declarations_clear_the_findings():
    result = execute_validation_plan(
        None,
        "governance",
        metric_source=EWA_SOURCE,
        constant_declarations={
            "3.31": {"meaning": "night flow main", "unit": "L/day", "source": "fitted"},
            "0.3": {"meaning": "share counted as saving", "unit": "ratio"},
            "6.5": {"meaning": "paid hours per crewday", "unit": "hours"},
        },
        return_result=True,
    )
    assert result.issues == []


def test_metric_constants_without_source_is_a_no_op():
    result = execute_validation_plan(None, "governance", return_result=True)
    assert result.issues == []


def test_epanet_runs_from_inline_text():
    result = execute_validation_plan(
        None, "epanet", inp_text=DECK, return_result=True
    )
    assert result.issues == []


def test_epanet_reports_a_broken_deck():
    broken = DECK.replace(" P2  J1  J2  500", " P2  J1  GHOST  500")
    result = execute_validation_plan(
        None, "epanet", inp_text=broken, return_result=True
    )
    assert "epanet_dangling_endpoint" in {i.problem_name for i in result.issues}


def test_epanet_without_path_or_text_is_a_no_op():
    result = execute_validation_plan(None, "epanet", return_result=True)
    assert result.issues == []


def test_epanet_reads_from_a_path(tmp_path):
    deck = tmp_path / "network.inp"
    deck.write_text(DECK, encoding="utf-8")
    result = execute_validation_plan(
        None, "epanet", inp_path=str(deck), return_result=True
    )
    assert result.issues == []


BALANCE = {
    "system_input_volume": 100_000.0,
    "supplier_water": 100_000.0,
    "billed_consumption": 70_000.0,
    "unbilled_consumption": 10_000.0,
    "real_loss_components": {"distribution_main_leakage": 16_000.0},
    "apparent_loss_components": {"unbilled_consumption": 4_000.0},
}


def test_water_balance_runs_through_the_runtime():
    result = execute_validation_plan(
        None, "water_balance", balance_inputs=BALANCE, return_result=True
    )
    serious = [i for i in result.issues if str(i.severity) in {"high", "critical"}]
    assert serious == []


def test_water_balance_reports_ili_with_its_caveat():
    result = execute_validation_plan(
        None,
        "water_balance",
        balance_inputs=BALANCE,
        days_in_period=365.0,
        uarl=8_000.0,
        return_result=True,
    )
    assert "ili_requires_context" in {i.problem_name for i in result.issues}


def test_water_balance_flags_typed_in_losses():
    result = execute_validation_plan(
        None,
        "water_balance",
        balance_inputs={**BALANCE, "declared_real_losses": 9_000.0},
        return_result=True,
    )
    mismatch = next(
        i for i in result.issues if i.problem_name == "water_balance_loss_mismatch"
    )
    assert str(mismatch.severity) == "high"


def test_water_balance_without_inputs_is_a_no_op():
    result = execute_validation_plan(None, "water_balance", return_result=True)
    assert result.issues == []


@pytest.mark.parametrize(
    "dataset_type",
    ["schema", "governance", "epanet", "spectral", "water_balance", "crs", "raster"],
)
def test_new_dataset_types_are_selectable(dataset_type):
    layer = _layer(photo=[VENDOR_PHOTO] * 4)
    result = execute_validation_plan(layer, dataset_type, return_result=True)
    assert result.validators_attempted == [] or result.validators_completed or result.issues


def test_unknown_dataset_type_still_raises():
    with pytest.raises(ValueError):
        execute_validation_plan(_layer(a=[1]), "not_a_dataset_type")


def test_custom_validator_registry_is_unaffected():
    assert list_custom_validators("crs") is not None


def test_crs_units_runs_through_the_runtime():
    import geopandas as gpd
    from shapely.geometry import LineString

    layer = gpd.GeoDataFrame(
        {"pipe_len": [0.01] * 5},
        geometry=[LineString([(0, 0), (1, 0)])] * 5,
        crs="EPSG:32640",
    )
    result = execute_validation_plan(
        layer, "crs", length_columns=["pipe_len"], return_result=True
    )
    assert "length_unit_inconsistent_with_crs" in {i.problem_name for i in result.issues}


def test_crs_units_is_silent_on_a_correct_layer():
    import geopandas as gpd
    from shapely.geometry import LineString

    layer = gpd.GeoDataFrame(
        {"pipe_len": [1.0] * 5},
        geometry=[LineString([(0, 0), (1, 0)])] * 5,
        crs="EPSG:32640",
    )
    result = execute_validation_plan(
        layer, "crs", length_columns=["pipe_len"], return_result=True
    )
    assert result.issues == []


def test_raster_runs_from_a_path(tmp_path):
    numpy = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    import os

    from rasterio.transform import from_origin

    proj = os.path.join(os.path.dirname(rasterio.__file__), "proj_data")
    previous = {k: os.environ.get(k) for k in ("PROJ_DATA", "PROJ_LIB")}
    os.environ["PROJ_DATA"] = proj
    os.environ["PROJ_LIB"] = proj
    try:
        path = tmp_path / "scene.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=8, width=8, count=4, dtype="float32",
            crs="EPSG:32640", transform=from_origin(400000, 2600000, 10, 10),
        ) as dst:
            for index in range(1, 5):
                dst.write(numpy.full((8, 8), 0.1 * index, dtype="float32"), index)
        with rasterio.open(path, "r+") as dst:
            for index, text in enumerate(
                ("B2: 490nm Blue", "B3: 560nm Green", "B4: 665nm Red", "B8: 842nm NIR"),
                start=1,
            ):
                dst.set_band_description(index, text)

        result = execute_validation_plan(
            None, "raster", raster_path=str(path), return_result=True
        )
        assert [i for i in result.issues if str(i.severity) == "high"] == []
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_raster_without_a_path_is_a_no_op():
    result = execute_validation_plan(None, "raster", return_result=True)
    assert result.issues == []
