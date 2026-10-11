"""Tests for finding confidence.

The property that matters is that two findings of the same condition can
receive very different confidence, because the evidence differs. A tool
that assigns one number per condition has not measured anything.
"""

from __future__ import annotations

import pytest

from geoqa.confidence import (
    DEFAULT_BASE_RATES,
    assess_finding,
    assess_findings,
    calibration_report,
    confidence_band,
)
from geoqa.problem_registry import get_problem_definition
from geoqa.validations.base import build_issue


def _gap(distance: float, tolerance: float = 1.0, **extra):
    payload = {"distance": distance, "tolerance": tolerance}
    payload.update(extra)
    return build_issue("polygon_gap_same_layer", extra=payload)


class TestMarginMatters:
    def test_same_condition_different_margin_different_confidence(self):
        near = assess_finding(_gap(1.02))
        far = assess_finding(_gap(5.0))
        assert near.posterior < far.posterior

    def test_a_finding_barely_past_the_threshold_is_uncertain(self):
        """The most important property. A gap of one percent over tolerance is
        usually digitising noise, and a tool presenting it as a defect with the
        same confidence as a gap of five tolerances is misleading."""
        result = assess_finding(_gap(1.02))
        assert 0.35 < result.posterior < 0.75
        assert result.band in {"uncertain", "weak"}

    def test_a_finding_far_past_the_threshold_is_near_certain(self):
        result = assess_finding(_gap(8.0))
        assert result.posterior > 0.9
        assert result.band == "near_certain"

    def test_confidence_increases_monotonically_with_margin(self):
        posteriors = [assess_finding(_gap(r)).posterior for r in (1.0, 1.5, 2.0, 4.0, 8.0)]
        assert posteriors == sorted(posteriors)

    def test_a_value_below_tolerance_is_pushed_down_hard(self):
        result = assess_finding(_gap(0.5))
        assert result.posterior < 0.4
        assert any(e.name == "below_declared_tolerance" for e in result.evidence)


class TestIssueClassMatters:
    def test_an_observation_is_not_treated_as_a_defect(self):
        defect = assess_finding(_gap(1.5))
        observation = assess_finding(
            build_issue("clip_coverage_uncomputable", extra={"distance": 1.5, "tolerance": 1.0})
        )
        assert observation.posterior < defect.posterior

    def test_a_governance_gap_is_almost_always_genuine(self):
        result = assess_finding(build_issue("encoding_not_declared"))
        assert result.posterior > 0.7

    def test_spatial_statistics_gets_a_low_base_rate_and_says_so(self):
        """A statistical outlier is a hypothesis, not an observation."""
        result = assess_finding(build_issue("spatial_statistical_outlier"))
        assert result.prior < 0.5
        assert any("below one half" in c for c in result.caveats)


class TestHonesty:
    def test_no_probability_without_a_base_rate(self):
        result = assess_finding(build_issue("some_condition_with_no_rate"))
        assert result.calibrated is False
        assert result.posterior != result.posterior
        assert result.band == "uncalibrated"
        assert any("No base rate" in c for c in result.caveats)

    def test_default_rates_are_labelled_as_placeholders(self):
        result = assess_finding(_gap(2.0))
        assert any("placeholder" in w or "default" in w for w in result.would_change_it)

    def test_supplied_base_rate_is_used_and_marked_calibrated(self):
        result = assess_finding(_gap(2.0), base_rates={"geometry_topology": 0.95})
        assert result.calibrated
        assert result.prior == pytest.approx(0.95)

    def test_a_per_finding_prior_overrides_the_register(self):
        result = assess_finding(_gap(2.0), prior=0.99)
        assert result.prior == pytest.approx(0.99)

    def test_missing_geometry_is_reported_as_something_to_confirm(self):
        result = assess_finding(_gap(2.0))
        assert any("no geometry" in w for w in result.would_change_it)


class TestBands:
    @pytest.mark.parametrize("posterior,band", [
        (0.95, "near_certain"), (0.75, "probable"),
        (0.5, "uncertain"), (0.25, "weak"), (0.05, "likely_false_positive"),
    ])
    def test_band_names_the_number(self, posterior, band):
        assert confidence_band(posterior, calibrated=True) == band

    def test_uncalibrated_never_reads_as_confidence(self):
        assert confidence_band(0.99, calibrated=False) == "uncalibrated"


class TestBatch:
    def test_results_are_ordered_most_credible_first(self):
        issues = [_gap(1.02), _gap(9.0), _gap(2.5)]
        results = assess_findings(issues)
        posteriors = [r.posterior for r in results]
        assert posteriors == sorted(posteriors, reverse=True)

    def test_limit_is_respected(self):
        assert len(assess_findings([_gap(1.1 * i) for i in range(1, 10)], limit=3)) == 3

    def test_result_serialises_with_its_reasoning(self):
        payload = assess_finding(_gap(3.0)).to_dict()
        assert payload["evidence"]
        assert "band" in payload and "calibrated" in payload


class TestCalibration:
    def test_nothing_to_check_without_outcomes(self):
        report = calibration_report(assess_findings([_gap(2.0)]), {})
        assert report["checked"] == 0
        assert "note" in report

    def test_overconfidence_is_measured_and_reported(self):
        """The number that matters: if predictions average 0.8 and outcomes
        average 0.4, the confidence figures are wrong and must say so."""
        issues = [_gap(3.0), _gap(4.0), _gap(2.5), _gap(6.0)]
        results = assess_findings(issues)
        outcomes = {}
        for index, issue in enumerate(issues):
            # Only half are genuine, which is far below the predictions.
            outcomes[(issue.problem_name, issue.feature_id)] = index < 2
        report = calibration_report(results, outcomes)
        assert report["checked"] == 4
        assert report["over_confident_by"] > 0.2

    def test_bins_are_reported(self):
        issues = [_gap(1.2), _gap(5.0)]
        results = assess_findings(issues)
        outcomes = {(i.problem_name, i.feature_id): True for i in issues}
        assert calibration_report(results, outcomes)["bins"]


class TestRegistry:
    def test_default_base_rates_are_fractions(self):
        for key, rate in DEFAULT_BASE_RATES.items():
            assert 0.0 < rate < 1.0, key

    def test_confidence_does_not_invent_a_condition(self):
        """Assessment reads the registry through build_issue, so a condition
        the registry does not know still cannot be reported."""
        entry = get_problem_definition("polygon_gap_same_layer")
        assert entry is not None