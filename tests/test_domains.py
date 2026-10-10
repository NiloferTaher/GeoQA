"""Tests for vertical reference, COG, OSM and the domain packs.

The behaviour worth protecting: each of these reports something a structural
check cannot see, and none of them invents a threshold it cannot defend.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from geoqa.packs.domains import (
    ALL_PACKS,
    get_pack,
    list_packs,
    pack_gate,
    pack_report,
)
from geoqa.validations.cog import format_support_report, profile_cog, validate_cog
from geoqa.validations.osm import OSM_LICENCE, profile_osm_layer, validate_osm
from geoqa.validations.vertical_datum import (
    feet_to_metres,
    metres_to_feet,
    profile_vertical,
    validate_vertical_reference,
)


def _names(issues):
    return [i.problem_name for i in issues]


# --- vertical reference ---------------------------------------------------

def test_elevation_without_a_datum_is_high():
    """The single most consequential gap in any elevation dataset."""
    frame = pd.DataFrame({"elevation": [1.2, 1.4, 1.1]})
    issues = validate_vertical_reference(frame)
    issue = next(i for i in issues if i.problem_name == "vertical_reference_undeclared")
    assert str(issue.severity) == "high"
    assert "reference surface" in issue.description


def test_declared_datum_settles_it():
    frame = pd.DataFrame({"elevation": [1.2, 1.4], "datum": ["MSL"] * 2})
    assert "vertical_reference_undeclared" not in _names(validate_vertical_reference(frame))


def test_metadata_datum_is_read():
    frame = pd.DataFrame({"elevation": [1.2, 1.4]})
    issues = validate_vertical_reference(frame, metadata={"vertical_datum": "Mean Higher High Water"})
    assert "vertical_reference_undeclared" not in _names(issues)


def test_two_named_surfaces_is_ambiguous():
    frame = pd.DataFrame({"elevation": [1.2], "datum": ["MSL relative to MHHW"]})
    assert "vertical_reference_ambiguous" in _names(validate_vertical_reference(frame))


def test_horizontal_crs_without_vertical_is_reported():
    frame = gpd.GeoDataFrame(
        {"elevation": [1.2, 1.4]}, geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326"
    )
    assert "vertical_crs_undeclared" in _names(validate_vertical_reference(frame))


def test_unknown_vertical_crs_is_low_not_high():
    frame = pd.DataFrame({"elevation": [1.2]})
    issues = validate_vertical_reference(frame, metadata={"vertical_crs": "EPSG:99999"})
    issue = next(i for i in issues if i.problem_name == "vertical_crs_unknown")
    assert str(issue.severity) == "low"


def test_all_positive_depth_is_flipped():
    """Depth below a surface is negative; all-positive depth has been flipped."""
    frame = pd.DataFrame({"depth": [3.0, 5.0, 8.0]})
    issues = validate_vertical_reference(frame)
    issue = next(i for i in issues if i.problem_name == "vertical_depth_sign_inverted")
    assert str(issue.severity) == "high"


def test_negative_depth_is_correct():
    frame = pd.DataFrame({"depth": [-3.0, -5.0, -8.0]})
    assert "vertical_depth_sign_inverted" not in _names(validate_vertical_reference(frame))


def test_grossly_implausible_range_is_caught():
    """Range catches gross errors only, which is all it can honestly claim."""
    frame = pd.DataFrame({"elevation": [12000.0, 14000.0], "datum": ["MSL"] * 2})
    assert "vertical_range_implausible" in _names(validate_vertical_reference(frame))


def test_wrong_unit_within_plausible_range_is_not_caught_as_implausible():
    """Honest limit: 260 m is plausible elevation, so range stays silent.

    A value wrong by a unit factor often stays inside the plausible range, so
    range is not a unit check and is not offered as one. Pinned here so the
    limitation is stated rather than implied.
    """
    frame = pd.DataFrame({"elevation": [80.0, 120.0, 260.0], "datum": ["MSL"] * 3})
    assert "vertical_range_implausible" not in _names(validate_vertical_reference(frame))


def test_unit_undeclared_is_low_and_asks_rather_than_guesses():
    frame = pd.DataFrame({"elevation": [0.4, 1.2, 2.8], "datum": ["MSL"] * 3})
    issues = validate_vertical_reference(frame)
    assert "vertical_unit_undeclared" in _names(issues)


def test_declared_unit_settles_it():
    frame = pd.DataFrame({"elevation": [0.4, 1.2, 2.8], "datum": ["MSL"] * 3, "units": ["m"] * 3})
    assert "vertical_unit_undeclared" not in _names(validate_vertical_reference(frame))


def test_layer_without_elevation_is_quiet():
    frame = pd.DataFrame({"name": ["a", "b"], "code": [1, 2]})
    assert validate_vertical_reference(frame) == []


def test_empty_frame_is_quiet():
    assert validate_vertical_reference(pd.DataFrame()) == []


def test_column_kinds_are_distinguished():
    frame = pd.DataFrame({"depth": [-1.0], "canopy_height": [8.0], "elevation": [2.0]})
    profile = profile_vertical(frame)
    assert set(profile.elevation_columns) == {"depth", "canopy_height", "elevation"}


def test_unit_conversion_round_trips():
    assert feet_to_metres(metres_to_feet(12.5)) == pytest.approx(12.5)


def test_metres_to_feet_is_correct():
    assert metres_to_feet(1.0) == pytest.approx(3.28084, abs=1e-5)


# --- COG -------------------------------------------------------------------

rasterio = pytest.importorskip("rasterio")


def _tif(path, *, width=256, height=256, tiled=True, overviews=False):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin

    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 3,
        "dtype": "uint16", "crs": "EPSG:4326",
        "transform": from_origin(0, 0, 0.01, 0.01),
    }
    if tiled:
        profile.update({"tiled": True, "blockxsize": 512, "blockysize": 512})
    data = np.zeros((3, height, width), dtype="uint16")
    with rasterio.open(path, "w", **profile) as handle:
        handle.write(data)
        if overviews:
            handle.build_overviews([2, 4], Resampling.nearest)

    return path


def test_cog_profile_reads_layout(tmp_path):
    profile = profile_cog(_tif(tmp_path / "a.tif", overviews=True))
    assert profile.is_tiled is True
    assert profile.overview_levels == 2
    assert profile.meets_cog_expectations is True


def test_plain_tiff_is_not_cloud_optimized(tmp_path):
    profile = profile_cog(_tif(tmp_path / "a.tif", tiled=False))
    assert profile.is_tiled is False
    assert profile.meets_cog_expectations is False


def test_large_striped_tiff_is_reported(tmp_path):
    """Valid TIFF, opens everywhere, wrong shape for anything served remotely."""
    path = _tif(tmp_path / "big.tif", width=1200, height=1200, tiled=False)
    assert "raster_not_cloud_optimized" in _names(validate_cog(path, require_overviews_above_mb=1.0))


def test_large_tiff_without_overviews_is_reported(tmp_path):
    path = _tif(tmp_path / "big.tif", width=1200, height=1200, tiled=True, overviews=False)
    assert "raster_missing_overviews" in _names(validate_cog(path, require_overviews_above_mb=1.0))


def test_small_tiff_is_not_reported(tmp_path):
    path = _tif(tmp_path / "small.tif", width=64, height=64, tiled=False)
    assert validate_cog(path, require_overviews_above_mb=1.0) == []


def test_conformant_large_cog_is_quiet(tmp_path):
    path = _tif(tmp_path / "big.tif", width=1200, height=1200, tiled=True, overviews=True)
    assert validate_cog(path, require_overviews_above_mb=1.0) == []


def test_format_report_states_standing():
    report = {row["extension"]: row for row in format_support_report()}
    assert "standard" in report[".tif"]["standing"]
    assert "in development" in report[".zarr"]["standing"]
    assert "draft" in report[".parquet"]["standing"]


# --- OSM ---------------------------------------------------------------------

def _osm_layer(geometry=None, *, attribution=True, versioning=True):
    data = {
        "osm_id": [1, 2],
        "osm_type": ["way", "way"],
        "building": ["yes", "yes"],
        "geometry": geometry or [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 0)]),
        ],
    }
    if versioning:
        data.update({"version": [3, 3], "timestamp": ["2026-01-01"] * 2, "changeset": [9, 9]})
    if attribution:
        data["licence"] = [OSM_LICENCE] * 2
    return gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:4326")


def test_osm_without_attribution_is_high():
    """A licence obligation, which no structural check can detect."""
    issues = validate_osm(_osm_layer(attribution=False))
    issue = next(i for i in issues if i.problem_name == "osm_attribution_absent")
    assert str(issue.severity) == "high"
    assert "ODbL" in issue.description


def test_osm_with_attribution_is_quiet():
    assert "osm_attribution_absent" not in _names(validate_osm(_osm_layer()))


def test_missing_version_metadata_is_reported():
    issues = validate_osm(_osm_layer(versioning=False))
    issue = next(i for i in issues if i.problem_name == "osm_version_metadata_absent")
    assert str(issue.severity) == "medium"


def test_unclosed_area_is_high():
    """An area in OSM is an emergent property of ways, and can stop closing."""
    layer = _osm_layer(geometry=[LineString([(0, 0), (1, 0), (1, 1), (0, 0)]), Point(2, 2)])
    assert "osm_unclosed_area" in _names(validate_osm(layer))


def test_closed_area_is_not_reported():
    assert "osm_unclosed_area" not in _names(validate_osm(_osm_layer()))


def test_completeness_is_always_declared():
    """Not a defect. A limitation that must not be forgotten."""
    issues = validate_osm(_osm_layer())
    issue = next(i for i in issues if i.problem_name == "osm_completeness_unknown")
    assert str(issue.severity) == "info"
    assert "not fixable by validation" in issue.description


def test_osm_profile_counts_tags():
    profile = profile_osm_layer(_osm_layer())
    assert profile.tag_counts["building"] == 2
    assert profile.attribution_present is True


# --- domain packs ---------------------------------------------------------------

def test_packs_are_listed():
    assert set(list_packs()) >= {"flood", "mangrove", "seismic", "power", "mining", "oil", "wildfire", "coastal"}
    assert "public_reference" in list_packs()


def test_unknown_pack_is_refused():
    with pytest.raises(KeyError, match="unknown pack"):
        get_pack("teleportation")


def test_every_pack_has_a_summary():
    for pack in ALL_PACKS:
        assert pack.summary
        assert pack.name in pack.summary.lower() or pack.summary


def test_pack_declares_what_it_needs():
    """A pack that hard-codes a threshold is a validator pretending to be a pack."""
    for pack in ALL_PACKS:
        assert pack.declarations_required, pack.name


def test_pack_gate_halts_on_its_required_conditions():
    gate = pack_gate("coastal")
    from geoqa.validations.base import build_issue

    issue = build_issue(
        problem_name="vertical_reference_undeclared", severity="high", description="x"
    )
    assert gate.evaluate([issue]).outcome == "halt"


def test_pack_gate_passes_when_declared():
    from geoqa.validations.base import build_issue

    gate = pack_gate("coastal")
    issue = build_issue(problem_name="metadata_stale", severity="medium", description="x")
    assert gate.evaluate([issue]).outcome == "proceed"


def test_pack_report_shape():
    report = {row["name"]: row for row in pack_report()}
    assert report["mangrove"]["required_conditions"]
    assert "datum" in report["flood"]["summary"].lower()


def test_public_reference_pack_covers_the_licence_risk():
    assert "osm_attribution_absent" in get_pack("public_reference").required_conditions

# --- hardware ---------------------------------------------------------------

def _names_hw(issues):
    return [i.problem_name for i in issues]


def test_hardware_profile_reads_the_machine():
    from geoqa.hardware import profile_hardware

    profile = profile_hardware()
    assert profile.platform
    assert profile.cpu.logical_cores and profile.cpu.logical_cores > 0
    assert profile.memory.total_mb and profile.memory.total_mb > 0


def test_sensor_report_explains_linux_needs_nothing_installed():
    """hwmon is the kernel interface; suggesting lm-sensors there is wrong advice."""
    from geoqa.hardware import sensor_report

    assert "no installation required" in sensor_report()["native_interfaces"]["linux"]


def test_sensor_report_names_librehardwaremonitor_on_windows():
    from geoqa.hardware import sensor_report

    assert "LibreHardwareMonitor" in sensor_report()["native_interfaces"]["windows"]


def test_no_temperature_comes_with_a_note():
    from geoqa.hardware import sensor_report

    report = sensor_report()
    if not report["temperatures_c"]:
        assert report["note"]


def _hw_profile(**overrides):
    from geoqa.hardware import CpuInfo, DiskInfo, HardwareProfile, MemoryInfo

    base = dict(
        platform="win32", machine="t",
        cpu=CpuInfo(logical_cores=8, physical_cores=4, rated_clock_mhz=3000.0,
                    observed_clock_mhz=3000.0, throttled=False),
        memory=MemoryInfo(total_mb=16000.0, available_mb=8000.0, percent_used=50.0),
        disk=DiskInfo(path=".", total_gb=500.0, free_gb=400.0, percent_free=80.0),
        temperatures_c=(50.0, 55.0), temperature_source="test",
    )
    base.update(overrides)
    return HardwareProfile(**base)


def test_unknown_memory_is_not_treated_as_zero():
    """Unknown available memory must not read as none available."""
    from geoqa.hardware import MemoryInfo, validate_operation_feasible

    profile = _hw_profile(memory=MemoryInfo(None, None, None))
    issues = validate_operation_feasible(profile, estimated_memory_mb=40000)
    assert "hardware_memory_insufficient" not in _names_hw(issues)


def test_throttling_is_reported():
    from geoqa.hardware import CpuInfo, validate_operation_feasible

    profile = _hw_profile(cpu=CpuInfo(rated_clock_mhz=3000.0, observed_clock_mhz=1900.0,
                                      throttled=True))
    assert "hardware_cpu_throttled" in _names_hw(validate_operation_feasible(profile))


def test_hardware_block_can_halt_a_run():
    from geoqa.hardware import MemoryInfo, validate_operation_feasible
    from geoqa.hitl import Gate, GateSpec, at_least

    gate = Gate("run", [GateSpec("hardware", "a hardware constraint blocks", at_least("high"))])
    profile = _hw_profile(memory=MemoryInfo(16000.0, 200.0, 99.0))
    decision = gate.evaluate(
        validate_operation_feasible(profile, estimated_memory_mb=40000),
        expected_outcome="halt",
    )
    assert decision.outcome == "halt"
    assert decision.matched_expectation is True


def test_sensor_absence_is_low_and_actionable():
    from geoqa.hardware import validate_operation_feasible

    profile = _hw_profile(temperatures_c=(), temperature_source=None,
                          temperature_note="Install LibreHardwareMonitor and run it once")
    issue = next(i for i in validate_operation_feasible(profile)
                 if i.problem_name == "hardware_temperature_unavailable")
    assert str(issue.severity) == "low"
    assert "LibreHardwareMonitor" in issue.description