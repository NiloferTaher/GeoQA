"""Tests for the human-in-the-loop gate.

The behaviour worth protecting: the gate can halt, it can be measured, and it
cannot be made to consult a model. Each of those is a claim the Ethics paper
depends on, so each has a test that would fail if the claim stopped being true.
"""

from __future__ import annotations

import json

import pytest

from geoqa import HITL
from geoqa.hitl import (
    HALT,
    PROCEED,
    PROCEED_WITH_WARNINGS,
    Gate,
    GateSpec,
    any_of,
    at_least,
    count_at_least,
    preset_gate,
)
from geoqa.validations.base import build_issue


def _critical(name="critical_problem"):
    return build_issue(problem_name=name, severity="critical", description="bad", feature_id=1)


def _high(name="high_problem"):
    return build_issue(problem_name=name, severity="high", description="not great", feature_id=2)


def _info(name="info_problem"):
    return build_issue(problem_name=name, severity="info", description="note", feature_id=3)


# --- the decision ------------------------------------------------------------

def test_no_issues_proceeds():
    gate = Gate("g", [GateSpec("c", "no critical", at_least("critical"))])
    assert gate.evaluate([]).outcome == PROCEED


def test_critical_halts():
    gate = Gate("g", [GateSpec("c", "no critical", at_least("critical"))])
    decision = gate.evaluate([_critical()])
    assert decision.outcome == HALT
    assert decision.halts is True


def test_reasons_and_issues_are_recorded():
    """A halt with no reason is indistinguishable from a crash."""
    gate = Gate("g", [GateSpec("c", "no critical", at_least("critical"))])
    decision = gate.evaluate([_critical("my_problem")])
    assert decision.reasons == ["c: no critical"]
    assert decision.gates_fired == ["c"]
    assert decision.triggering_issues[0]["problem_name"] == "my_problem"
    assert decision.triggering_issues[0]["severity"] == "critical"


def test_any_firing_gate_halts():
    """Gates are OR-ed; one blocking condition is never cancelled by another."""
    gate = Gate("g", [
        GateSpec("a", "first", at_least("critical")),
        GateSpec("b", "second", any_of("never_fires")),
    ])
    assert gate.evaluate([_critical()]).outcome == HALT


def test_warnings_outcome_is_distinct_from_halt():
    gate = Gate("g", [
        GateSpec("w", "repeated", count_at_least(3), outcome=PROCEED_WITH_WARNINGS),
    ])
    issues = [_high()] * 3
    decision = gate.evaluate(issues)
    assert decision.outcome == PROCEED_WITH_WARNINGS
    assert decision.halts is False


def test_repeat_count_respects_the_threshold():
    gate = Gate("g", [GateSpec("w", "repeated", count_at_least(3), outcome=PROCEED_WITH_WARNINGS)])
    assert gate.evaluate([_high()] * 2).outcome == PROCEED
    assert gate.evaluate([_high()] * 3).outcome == PROCEED_WITH_WARNINGS


def test_problem_name_filter():
    gate = Gate("g", [GateSpec("n", "specific", any_of("governance_licence_not_declared"))])
    assert gate.evaluate([_critical("something_else")]).outcome == PROCEED
    assert gate.evaluate([_critical("governance_licence_not_declared")]).outcome == HALT


def test_severity_floor_is_inclusive():
    gate = Gate("g", [GateSpec("s", "at least high", at_least("high"))])
    assert gate.evaluate([_high()]).outcome == HALT
    assert gate.evaluate([_info()]).outcome == PROCEED


def test_gates_evaluated_is_recorded_even_when_quiet():
    """Knowing which gates ran is what makes a proceed meaningful."""
    gate = Gate("g", [GateSpec("a", "one", at_least("critical"))])
    assert gate.evaluate([]).gates_evaluated == ["a"]
    assert gate.evaluate([]).gates_fired == []


# --- the architectural claim ---------------------------------------------------

def test_gate_never_claims_llm_involvement():
    """The paper's claim is architectural, so it must not be a setting."""
    assert Gate("g").llm_involved is False
    assert Gate("g", [GateSpec("a", "x", at_least("critical"))]).llm_involved is False
    decision = Gate("g").evaluate([_critical()])
    assert decision.as_dict()["llm_involved"] is False
    assert decision.as_dict()["deterministic"] is True


def test_decision_path_has_no_model_call():
    import inspect

    from geoqa import hitl

    source = inspect.getsource(hitl)
    for forbidden in ("openai", "anthropic", "requests.post", "httpx", "urllib"):
        assert forbidden not in source.lower(), forbidden


def test_same_input_gives_same_decision():
    """Determinism is checkable, not merely asserted."""
    gate = Gate("g", [GateSpec("a", "x", at_least("critical"))])
    issues = [_critical(), _high()]
    outcomes = {gate.evaluate(issues).outcome for _ in range(5)}
    assert outcomes == {HALT}


# --- human disposition ----------------------------------------------------------

def test_hold_records_who_decided():
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    decision = gate.evaluate([_critical()])
    decision.hold(by="engineer@example.org", note="checked the field record")
    assert decision.reviewed_by == "engineer@example.org"
    assert decision.is_held is True
    assert decision.reviewed_utc.endswith("+00:00")


def test_hold_is_not_resolved_automatically():
    """A hold that resolves itself is not a hold."""
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    decision = gate.evaluate([_critical()])
    decision.hold(by="someone")
    re_evaluated = gate.evaluate([_critical()])
    assert re_evaluated.outcome == HALT
    assert re_evaluated.reviewed_by is None


def test_proceed_is_not_a_hold():
    assert Gate("g").evaluate([]).is_held is False


# --- measurability ---------------------------------------------------------------

def test_recall_measures_halt_detection():
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    for _ in range(12):
        gate.evaluate_and_record([_critical()], expected_outcome=HALT)
    report = gate.recall()
    assert report.halt_expected == 12
    assert report.halt_detected == 12
    assert report.halt_recall == 1.0
    assert report.as_dict()["halt_recall_pct"] == 100.0


def test_false_halt_is_measured_on_clean_cases():
    """A gate that halts on everything has no measured value."""
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    for _ in range(3):
        gate.evaluate_and_record([_info()], expected_outcome=PROCEED)
    report = gate.recall()
    assert report.clean_cases == 3
    assert report.false_halt_on_clean == 0
    assert report.false_halt_rate == 0.0


def test_recall_with_no_expectations_reports_nothing_rather_than_100_percent():
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    for _ in range(5):
        gate.evaluate_and_record([_critical()])
    report = gate.recall()
    assert report.total == 0
    assert report.halt_recall is None


def test_expectation_mismatch_is_recorded():
    gate = Gate("g", [GateSpec("c", "x", at_least("critical"))])
    decision = gate.evaluate([_info()], expected_outcome=HALT)
    assert decision.matched_expectation is False
    assert gate.recall().correct == 0


def test_invalid_expectation_is_refused():
    with pytest.raises(ValueError, match="expected outcome"):
        Gate("g").evaluate([], expected_outcome="maybe")


# --- audit trail --------------------------------------------------------------------

def test_json_audit_records_declarations_and_decisions(tmp_path):
    gate = preset_gate("release")
    gate.evaluate_and_record([_critical()], expected_outcome=HALT)
    path = gate.to_json(tmp_path / "audit.json")
    payload = json.loads(path.read_text())
    assert payload["llm_involved"] is False
    assert payload["deterministic"] is True
    assert len(payload["declared_gates"]) == 2
    assert payload["decisions"][0]["outcome"] == HALT
    assert payload["recall"]["halt_recall_pct"] == 100.0


def test_json_audit_names_the_requirements(tmp_path):
    """The requirement text is the governance statement; it must survive."""
    path = preset_gate().to_json(tmp_path / "a.json")
    payload = json.loads(path.read_text())
    requirements = [g["requirement"] for g in payload["declared_gates"]]
    assert any("critical" in r for r in requirements)


# --- preset -------------------------------------------------------------------------

def test_preset_gate_halts_on_critical():
    assert preset_gate().evaluate([_critical()]).outcome == HALT


def test_preset_gate_warns_on_repeats():
    assert preset_gate().evaluate([_high()] * 4).outcome == PROCEED_WITH_WARNINGS


def test_preset_gate_quiet_on_clean():
    assert preset_gate().evaluate([_info()]).outcome == PROCEED


def test_unnamed_gate_is_refused():
    with pytest.raises(ValueError, match="needs a name"):
        Gate("")


# --- the import the user asked for ---------------------------------------------------

def test_public_import_surface():
    import geoqa

    assert "HITL" in geoqa.__all__
    assert geoqa.HITL is Gate


def test_end_to_end_use():
    """The shape a caller actually writes."""
    gate = Gate("release", gates=[
        GateSpec(
            "no_licence_gap", "no dataset ships without recorded terms",
            any_of("governance_licence_not_declared"),
        )
    ])
    from geoqa.validations.governance import validate_governance_metadata

    issues = validate_governance_metadata({"title": "x"})
    decision = gate.evaluate_and_record(issues, expected_outcome=HALT)
    assert decision.halts
    decision.hold(by="gis@example.org", note="licence confirmed offline")
    assert decision.is_held
    assert gate.recall().halt_recall == 1.0