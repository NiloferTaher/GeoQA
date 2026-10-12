from geoqa.confidence import DEFAULT_BASE_RATES, assess_finding
from geoqa.validations.base import build_issue


def _finding():
    return build_issue("polygon_gap_same_layer", extra={"distance": 2.0, "tolerance": 1.0})


def test_default_base_rate_is_marked_uncalibrated_with_posterior() -> None:
    result = assess_finding(_finding())

    assert result.calibrated is False
    assert result.band == "uncalibrated"
    assert result.prior == DEFAULT_BASE_RATES["geometry_topology"]
    assert isinstance(result.posterior, float)
    assert 0.0 <= result.posterior <= 1.0


def test_caller_supplied_base_rate_is_marked_calibrated() -> None:
    result = assess_finding(_finding(), base_rates={"geometry_topology": 0.95})

    assert result.calibrated is True
    assert result.band != "uncalibrated"


def test_per_finding_prior_is_marked_calibrated() -> None:
    result = assess_finding(_finding(), prior=0.95)

    assert result.calibrated is True


def test_is_genuine_likely_requires_calibration() -> None:
    default_result = assess_finding(_finding())
    supplied_result = assess_finding(
        _finding(), base_rates={"geometry_topology": 0.95}
    )

    assert default_result.posterior > 0.5
    assert default_result.is_genuine_likely is False
    assert supplied_result.posterior > 0.5
    assert supplied_result.is_genuine_likely is True
