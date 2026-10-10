"""Human-in-the-loop governance gates.

What this is for
-----------------
A validator produces findings. Something has to decide whether those findings
permit the next step. Doing that automatically is the default in most tooling,
which means the decision is made by a threshold nobody chose and nobody can
audit. This module makes the decision an explicit, declared, recorded act.

    from geoqa import HITL

    gate = HITL.Gate(name="release", gates=[gate_spec])
    decision = gate.evaluate(issues)
    if decision.halts:
        decision.reviewed_by = "engineer@example.org"
        decision.review_note = "confirmed against field record"
        gate.record(decision)

Four properties, and they are the point
---------------------------------------
**No model in the decision path.** ``Gate.llm_involved`` is a class-level
constant, not a setting. There is nothing to configure into a model being
consulted. A gate whose decision could vary between runs is not a gate, it is a
weather system.

**The gate proposes, a person disposes.** :meth:`Decision.hold` records a human
hold. Nothing in this module resolves a hold automatically, because a hold that
resolves itself is not a hold.

**Every decision carries its reasons.** Not just the outcome, but which gates
fired, which issues triggered them, and who decided. A halt with no reason is
indistinguishable from a failure.

**Recall is measurable.** A governance gate that has never been measured cannot
be claimed to work. :meth:`Gate.recall` scores decisions against expected
outcomes, so "12 of 12 halts caught, 0 false halts on clean input" is a number
this library produces rather than a number somebody remembered.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

#: Outcome vocabulary. Fixed, because a decision taxonomy that varies per call
#: site cannot be audited across sites.
PROCEED = "proceed"
PROCEED_WITH_WARNINGS = "proceed_with_warnings"
HALT = "halt"

OUTCOMES = (PROCEED, PROCEED_WITH_WARNINGS, HALT)

#: Severity ordering used when a gate needs "anything at or above".
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _severity_rank(value: Any) -> int:
    return SEVERITY_RANK.get(str(value).lower(), 0)


@dataclass(frozen=True)
class GateSpec:
    """One declared condition that can stop a run.

    ``predicate`` receives the issue list and returns the issues that should
    stop it. Naming it in the spec means the rule is visible in the gate
    declaration rather than buried in a function body.
    """

    name: str
    #: Human-readable statement of what the gate requires.
    requirement: str
    predicate: Callable[[Sequence[Any]], Sequence[Any]]
    #: Optional explicit outcome. Defaults to halt when the predicate fires.
    outcome: str = HALT
    #: Whether this gate can be waived by a human without editing code.
    waivable: bool = True

    def evaluate(self, issues: Sequence[Any]) -> list[Any]:
        return list(self.predicate(issues))


def at_least(severity: str, *, problem_names: Iterable[str] | None = None) -> Callable[[Sequence[Any]], Sequence[Any]]:
    """Predicate: any issue at or above a severity, optionally name-filtered."""
    floor = _severity_rank(severity)
    allowed = {str(name) for name in problem_names} if problem_names else None

    def predicate(issues: Sequence[Any]) -> list[Any]:
        return [
            issue for issue in issues
            if _severity_rank(getattr(issue, "severity", None)) >= floor
            and (allowed is None or str(getattr(issue, "problem_name", "")) in allowed)
        ]

    predicate.__name__ = f"at_least_{severity}"
    return predicate


def any_of(*problem_names: str) -> Callable[[Sequence[Any]], Sequence[Any]]:
    """Predicate: any occurrence of the named conditions."""
    wanted = {str(name) for name in problem_names}

    def predicate(issues: Sequence[Any]) -> list[Any]:
        return [
            issue for issue in issues
            if str(getattr(issue, "problem_name", "")) in wanted
        ]

    predicate.__name__ = "any_of_" + "_".join(sorted(wanted))[:40]
    return predicate


def count_at_least(threshold: int, *, problem_names: Iterable[str] | None = None) -> Callable[[Sequence[Any]], Sequence[Any]]:
    """Predicate: fires once a condition occurs at least ``threshold`` times.

    Single occurrences are often noise. A repeated condition is a pattern, and
    a pattern is what a gate should stop for.
    """
    allowed = {str(name) for name in problem_names} if problem_names else None

    def predicate(issues: Sequence[Any]) -> list[Any]:
        matched = [
            issue for issue in issues
            if allowed is None or str(getattr(issue, "problem_name", "")) in allowed
        ]
        return matched if len(matched) >= threshold else []

    predicate.__name__ = f"count_at_least_{threshold}"
    return predicate


@dataclass
class Decision:
    """One gate outcome, with everything needed to audit it later."""

    gate: str
    outcome: str
    reasons: list[str] = field(default_factory=list)
    triggering_issues: list[dict[str, Any]] = field(default_factory=list)
    gates_fired: list[str] = field(default_factory=list)
    gates_evaluated: list[str] = field(default_factory=list)
    #: Set when a person has held the run. A hold is never auto-resolved.
    reviewed_by: str | None = None
    review_note: str | None = None
    reviewed_utc: str | None = None
    #: The outcome expected by whoever set the exercise, when known.
    expected_outcome: str | None = None
    #: Whether the gate's decision matched that expectation.
    matched_expectation: bool | None = None
    timestamp_utc: str = ""

    @property
    def halts(self) -> bool:
        return self.outcome == HALT

    @property
    def is_held(self) -> bool:
        return self.reviewed_by is not None and self.outcome == HALT

    @property
    def is_deterministic(self) -> bool:
        return True

    def hold(self, *, by: str, note: str = "") -> "Decision":
        """Record a human hold on a halting decision.

        Raising here rather than in the caller keeps the hold attached to the
        decision it belongs to, where the audit trail can find it.
        """
        self.reviewed_by = str(by)
        self.review_note = note
        self.reviewed_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self

    def expect(self, outcome: str) -> "Decision":
        """Record what this case was expected to decide.

        This is what makes recall measurable. Without it the gate produces
        outcomes but no claim about whether they were right.
        """
        if outcome not in OUTCOMES:
            raise ValueError(f"expected outcome must be one of {OUTCOMES}, got {outcome!r}")
        self.expected_outcome = outcome
        self.matched_expectation = outcome == self.outcome
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "outcome": self.outcome,
            "halts": self.halts,
            "reasons": list(self.reasons),
            "gates_fired": list(self.gates_fired),
            "gates_evaluated": list(self.gates_evaluated),
            "triggering_issues": list(self.triggering_issues),
            "reviewed_by": self.reviewed_by,
            "review_note": self.review_note,
            "reviewed_utc": self.reviewed_utc,
            "expected_outcome": self.expected_outcome,
            "matched_expectation": self.matched_expectation,
            "deterministic": True,
            "llm_involved": False,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class RecallReport:
    """How a gate performed against known expectations."""

    gate: str
    total: int
    correct: int
    halt_expected: int
    halt_detected: int
    false_halt: int
    clean_cases: int
    false_halt_on_clean: int

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.total if self.total else None

    @property
    def halt_recall(self) -> float | None:
        """Of the cases that should have halted, how many did?"""
        return self.halt_detected / self.halt_expected if self.halt_expected else None

    @property
    def false_halt_rate(self) -> float | None:
        """Of the cases that should have proceeded, how many halted anyway?"""
        return self.false_halt_on_clean / self.clean_cases if self.clean_cases else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "total": self.total,
            "correct": self.correct,
            "accuracy_pct": round(self.accuracy * 100, 2) if self.accuracy is not None else None,
            "halt_expected": self.halt_expected,
            "halt_detected": self.halt_detected,
            "halt_recall_pct": round(self.halt_recall * 100, 2) if self.halt_recall is not None else None,
            "false_halt": self.false_halt,
            "clean_cases": self.clean_cases,
            "false_halt_on_clean": self.false_halt_on_clean,
            "false_halt_rate_pct": round(self.false_halt_rate * 100, 2) if self.false_halt_rate is not None else None,
        }


class Gate:
    """A declared set of stop conditions.

    ``llm_involved`` is fixed at ``False`` and is a class attribute. It is not a
    constructor argument, so a gate cannot be constructed that consults a model
    while claiming not to.
    """

    #: A governance gate never consults a model. This is the architectural
    #: claim the whole approach rests on, so it is not configurable.
    llm_involved: bool = False

    def __init__(self, name: str, gates: Sequence[GateSpec] | None = None) -> None:
        if not name:
            raise ValueError("a gate needs a name; an unnamed decision cannot be audited")
        self.name = name
        self.gates: list[GateSpec] = list(gates or [])
        self.decisions: list[Decision] = []

    def add(self, spec: GateSpec) -> "Gate":
        self.gates.append(spec)
        return self

    def evaluate(self, issues: Sequence[Any], *, expected_outcome: str | None = None) -> Decision:
        """Run every declared gate and return one decision.

        The gates are OR-ed for halting: any one of them firing halts the run.
        A gate set that AND-ed would let one permissive condition cancel a
        blocking one, which is how stops get lost.
        """
        decision = Decision(
            gate=self.name,
            outcome=PROCEED,
            timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        decision.gates_evaluated = [spec.name for spec in self.gates]

        for spec in self.gates:
            triggered = spec.evaluate(issues)
            if not triggered:
                continue
            decision.gates_fired.append(spec.name)
            decision.reasons.append(f"{spec.name}: {spec.requirement}")
            decision.triggering_issues.extend(
                _issue_summary(issue) for issue in triggered
            )
            if spec.outcome == HALT:
                decision.outcome = HALT
            elif decision.outcome == PROCEED:
                decision.outcome = spec.outcome

        if expected_outcome is not None:
            decision.expect(expected_outcome)
        return decision

    def evaluate_and_record(
        self,
        issues: Sequence[Any],
        *,
        expected_outcome: str | None = None,
    ) -> Decision:
        """Evaluate and append to the gate's own audit trail."""
        decision = self.evaluate(issues, expected_outcome=expected_outcome)
        self.record(decision)
        return decision

    def record(self, decision: Decision) -> "Gate":
        self.decisions.append(decision)
        return self

    def recall(self) -> RecallReport:
        """Score the recorded decisions against their expectations.

        Only decisions carrying an expectation are scored. A gate that has not
        been told what it was supposed to decide has not been measured, and
        this returns zeros rather than a flattering number.
        """
        scored = [d for d in self.decisions if d.expected_outcome is not None]
        halt_expected = [d for d in scored if d.expected_outcome == HALT]
        clean = [d for d in scored if d.expected_outcome == PROCEED]
        halt_detected = sum(1 for d in halt_expected if d.outcome == HALT)
        false_halt = sum(1 for d in clean if d.outcome == HALT)

        return RecallReport(
            gate=self.name,
            total=len(scored),
            correct=sum(1 for d in scored if d.matched_expectation),
            halt_expected=len(halt_expected),
            halt_detected=halt_detected,
            false_halt=false_halt,
            clean_cases=len(clean),
            false_halt_on_clean=false_halt,
        )

    def to_json(self, path: str | Path) -> Path:
        """Write the full audit trail: declarations, decisions and recall."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "gate": self.name,
            "llm_involved": self.llm_involved,
            "deterministic": True,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "declared_gates": [
                {
                    "name": spec.name,
                    "requirement": spec.requirement,
                    "outcome": spec.outcome,
                    "waivable": spec.waivable,
                }
                for spec in self.gates
            ],
            "decisions": [decision.as_dict() for decision in self.decisions],
            "recall": self.recall().as_dict(),
        }
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
        )
        return target

    def __len__(self) -> int:
        return len(self.gates)


def _issue_summary(issue: Any) -> dict[str, Any]:
    if hasattr(issue, "to_dict"):
        payload = issue.to_dict()
        return {
            "problem_name": payload.get("problem_name"),
            "severity": payload.get("severity"),
            "description": str(payload.get("description", ""))[:300],
            "feature_id": payload.get("feature_id"),
        }
    if isinstance(issue, Mapping):
        return {
            "problem_name": issue.get("problem_name"),
            "severity": issue.get("severity"),
            "description": str(issue.get("description", ""))[:300],
            "feature_id": issue.get("feature_id"),
        }
    return {"problem_name": str(issue), "severity": None, "description": "", "feature_id": None}


def preset_gate(name: str = "default") -> Gate:
    """A starting gate, declared rather than hidden.

    Two conditions, both of which are things a person would want to stop for
    and neither of which is a machine judgement about quality: a critical
    finding, and a repeated high-severity finding.
    """
    return Gate(
        name=name,
        gates=[
            GateSpec(
                name="no_critical_findings",
                requirement="a critical finding must not proceed without review",
                predicate=at_least("critical"),
            ),
            GateSpec(
                name="no_repeated_high_severity",
                requirement="the same high-severity condition three times is a pattern, not noise",
                predicate=count_at_least(3, problem_names=None),
                outcome=PROCEED_WITH_WARNINGS,
            ),
        ],
    )


__all__ = [
    "HALT",
    "OUTCOMES",
    "PROCEED",
    "PROCEED_WITH_WARNINGS",
    "SEVERITY_RANK",
    "Decision",
    "Gate",
    "GateSpec",
    "RecallReport",
    "any_of",
    "at_least",
    "count_at_least",
    "preset_gate",
]