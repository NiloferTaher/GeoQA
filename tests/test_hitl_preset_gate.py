from geoqa.hitl import PROCEED, PROCEED_WITH_WARNINGS, count_at_least, preset_gate
from geoqa.validations.base import build_issue


def _issue(name: str, severity: str):
    return build_issue(problem_name=name, severity=severity, description="finding", feature_id=1)


def test_three_high_findings_for_same_condition_warn() -> None:
    decision = preset_gate().evaluate([_issue("same_condition", "high")] * 3)

    assert decision.outcome == PROCEED_WITH_WARNINGS


def test_three_info_findings_for_same_condition_do_not_warn() -> None:
    decision = preset_gate().evaluate([_issue("same_condition", "info")] * 3)

    assert decision.outcome == PROCEED


def test_three_low_findings_for_same_condition_do_not_warn() -> None:
    decision = preset_gate().evaluate([_issue("same_condition", "low")] * 3)

    assert decision.outcome == PROCEED


def test_high_findings_for_different_conditions_do_not_warn() -> None:
    issues = [
        _issue("condition_a", "high"),
        _issue("condition_a", "high"),
        _issue("condition_b", "high"),
    ]

    assert preset_gate().evaluate(issues).outcome == PROCEED


def test_count_at_least_defaults_to_total_counting() -> None:
    issues = [
        _issue("condition_a", "info"),
        _issue("condition_b", "low"),
        _issue("condition_c", "medium"),
    ]

    assert count_at_least(3)(issues) == issues
