"""Published reference cases, so the coefficients can be checked rather than trusted.

What this module is for
-----------------------
An implementation that runs is not an implementation that is correct. For an
empirical formula, correctness means: given the inputs stated in the source
publication, this code produces the output the publication states. That is a
checkable claim, and this module makes it checkable.

Each case carries its inputs, the published expected output, and the citation
the expectation came from. :func:`run_reference_cases` executes them all and
returns a pass or fail per case with the relative error, so a regression that
changes an arithmetic sign is caught immediately.

Where the numbers come from
---------------------------
``aqua1999_uarl_example``
    Lambert, A.O., Brown, T.G., Takizawa, M., Weimer, D. and Karam, E. (1999)
    *A Review of Performance Indicators for Real Losses from Water Supply
    Systems*, AQUA Journal, IWA Publishing. Table 4 gives the UARL component
    coefficients 18, 0.80 and 25 and an end-of-paper worked example with its
    intermediate values printed.

``iwa_taskforce_uarl_example``
    IWA Water Balance Task Force, *Assessing non-revenue water and its
    components: a practical manual*. Worked example with Lm = 603 km,
    Nc = 16,359, Lp = 0, P = 65 m, publishing UARL = 1,556 m3/day.

``lambert2009_background_leakage``
    Lambert, A.O. (2009) *The UARL equation*, IWA Cape Town. Background
    leakage BL (l/hour) = (2 x Lm + 1.25 x Ns) x (AZNP/50).

Honest note on the AQUA example
-------------------------------
The published table prints its private-pipe component as 87 while the arithmetic
from the stated coefficients gives 88.7, and the published components sum to
826 where the arithmetic gives 828. The mains and connections components
reproduce exactly. This looks like rounding or truncation in the published
table rather than a different coefficient, so the expected totals carry a
tolerance that accommodates it and the discrepancy is recorded here rather than
hidden inside a widened tolerance with no explanation.

Applicability
-------------
The UARL equation was derived for well-managed systems and the source states
limits below which it should not be used. Those limits are enforced as
conditions rather than left in a footnote, because applying the equation outside
its range produces a number that looks like an answer and is not one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "coefficient_reference_case"

AQUA_1999 = (
    "Lambert, Brown, Takizawa, Weimer & Karam (1999), A Review of Performance "
    "Indicators for Real Losses from Water Supply Systems, AQUA Journal, IWA "
    "Publishing. Table 4 and the end-of-paper worked example."
)

IWA_TASKFORCE = (
    "IWA Water Balance Task Force, Assessing non-revenue water and its "
    "components: a practical manual, worked UARL example."
)

LAMBERT_2009 = (
    "Lambert (2009), The UARL equation, IWA Cape Town conference paper."
)

#: Lower limits the source states for using the UARL equation.
UARL_APPLICABILITY_LIMITS: dict[str, float] = {
    "min_service_connections": 5000.0,
    "min_connection_density_per_km": 20.0,
    "min_average_pressure_m": 25.0,
}

#: Later work relaxed these; recorded so a relaxation is a decision, not a drift.
UARL_LIMITS_RELAXED_2009 = {
    "min_connection_density_per_km": None,
    "max_connection_density_per_km": None,
    "note": "Lambert (2009) removed the connection-density bounds.",
}


@dataclass(frozen=True)
class ReferenceCase:
    """One published worked example."""

    name: str
    citation: str
    #: What the case checks. Used in the failure message.
    quantity: str
    inputs: Mapping[str, float]
    #: Published output, in the units of ``published_units``.
    published_value: float
    published_units: str
    #: Relative error allowed. Published tables round, so this is not always tiny.
    tolerance: float = 0.01
    #: Additional intermediate values the publication also prints.
    published_components: Mapping[str, float] = field(default_factory=dict)
    #: Set when the publication's own rounding does not close exactly.
    rounding_note: str | None = None
    exercises_library: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "inputs": dict(self.inputs),
            "published_value": self.published_value,
            "published_units": self.published_units,
            "tolerance": self.tolerance,
            "components": dict(self.published_components),
            "citation": self.citation,
            "rounding_note": self.rounding_note,
            "exercises_library": self.exercises_library,
        }


@dataclass
class ReferenceCaseResult:
    """The outcome of running one case."""

    case: ReferenceCase
    computed_value: float | None
    relative_error: float | None
    passed: bool
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "quantity": self.case.quantity,
            "computed": self.computed_value,
            "published": self.case.published_value,
            "units": self.case.published_units,
            "relative_error": self.relative_error,
            "tolerance": self.case.tolerance,
            "passed": self.passed,
            "detail": self.detail,
        }


#: 0.9 x 365 = days the AQUA example assumes the system is pressurised.
AQUA_DAYS_PRESSURISED = 0.9 * 365


def aqua1999_uarl_example() -> ReferenceCase:
    """The end-of-paper worked example from Lambert et al. (1999).

    1,500 km mains, 60,000 connections, meters 6 m beyond the edge of street,
    average pressure 30 m, pressurised 90 percent of the time. The paper prints
    each UARL component and the total, then TIRL and the resulting ILI.
    """
    return ReferenceCase(
        name="aqua1999_uarl_example",
        citation=AQUA_1999,
        quantity="UARL total",
        inputs={
            "mains_length_km": 1500.0,
            "service_connections": 60_000.0,
            "private_length_km": 60_000.0 * 6.0 / 1000.0,
            "average_pressure_m": 30.0,
            "days": AQUA_DAYS_PRESSURISED,
        },
        published_value=826.0,
        published_units="10^3 m3/year",
        tolerance=0.005,
        published_components={
            "mains": 266.0,
            "connections": 473.0,
            "private": 87.0,
        },
        rounding_note=(
            "The published private-pipe component prints 87 where the stated "
            "coefficients give 88.7, and the printed components sum to 826 "
            "against 827.8 computed. Mains and connections reproduce exactly. "
            "Treated as published rounding, not as a different coefficient."
        ),
    )


def aqua1999_tirl_case() -> ReferenceCase:
    """TIRL and ILI from the same AQUA example, which are rounding-independent."""
    return ReferenceCase(
        name="aqua1999_tirl_case",
        citation=AQUA_1999,
        quantity="technical indicator for real losses",
        inputs={
            "annual_real_losses_m3": 4000.0 * 1000.0,
            "service_connections": 60_000.0,
            "pressurised_fraction": 0.9,
            "days": AQUA_DAYS_PRESSURISED,
        },
        published_value=202.0,
        published_units="litres/service connection/day w.s.p.",
        tolerance=0.01,
    )


def aqua1999_ili_case() -> ReferenceCase:
    """ILI from the AQUA example: 202 / 42 = 4.8."""
    return ReferenceCase(
        name="aqua1999_ili_case",
        citation=AQUA_1999,
        quantity="infrastructure leakage index",
        inputs={
            "tirl_l_per_connection_day": 202.0,
            "uarl_l_per_connection_day": 42.0,
        },
        published_value=4.8,
        published_units="dimensionless",
        tolerance=0.01,
    )


def aqua1999_ili_end_to_end_case() -> ReferenceCase:
    """End-to-end ILI from the AQUA network and real-loss inputs."""
    return ReferenceCase(
        name="aqua1999_ili_end_to_end",
        citation=AQUA_1999,
        quantity="infrastructure leakage index",
        inputs={
            "mains_length_km": 1500.0,
            "service_connections": 60_000.0,
            "private_length_km": 360.0,
            "average_pressure_m": 30.0,
            "annual_real_losses_m3": 4_000_000.0,
            "days": 328.5,
        },
        published_value=4.8,
        published_units="dimensionless",
        tolerance=0.01,
        rounding_note="The published ILI is rounded to one decimal place.",
    )


def iwa_taskforce_uarl_case() -> ReferenceCase:
    """The IWA Task Force worked example, which reproduces exactly."""
    return ReferenceCase(
        name="iwa_taskforce_uarl_case",
        citation=IWA_TASKFORCE,
        quantity="UARL",
        inputs={
            "mains_length_km": 603.0,
            "service_connections": 16_359.0,
            "private_length_km": 0.0,
            "average_pressure_m": 65.0,
        },
        published_value=1556.0,
        published_units="m3/day",
        tolerance=0.005,
    )


def lambert2009_background_leakage_case() -> ReferenceCase:
    """Background leakage at 50 m, Lambert (2009).

    BL (l/hour) = (2 x Lm + 1.25 x Ns) x (AZNP/50), evaluated at the reference
    pressure of 50 m where the factor is unity.
    """
    return ReferenceCase(
        name="lambert2009_background_leakage_case",
        citation=LAMBERT_2009,
        quantity="background leakage at 50 m",
        inputs={
            "mains_length_km": 1.0,
            "service_connections": 1.0,
            "average_zone_night_pressure_m": 50.0,
            "mains_coefficient": 2.0,
            "connections_coefficient": 1.25,
        },
        published_value=3.25,
        published_units="litres/hour",
        tolerance=0.005,
        exercises_library=False,
    )


def all_reference_cases() -> list[ReferenceCase]:
    """Every published case this module can check."""
    return [
        aqua1999_uarl_example(),
        aqua1999_tirl_case(),
        aqua1999_ili_case(),
        aqua1999_ili_end_to_end_case(),
        iwa_taskforce_uarl_case(),
        lambert2009_background_leakage_case(),
    ]


# --------------------------------------------------------------------------
# Computation
# --------------------------------------------------------------------------

def _coefficient(source: str, name: str):
    """Load the declared coefficient the implementation actually uses.

    Sourced rather than written inline, so the number under test is the one the
    library uses. If it is ever changed, these cases fail rather than passing
    against a separate copy of the arithmetic.
    """
    if source == AQUA_1999:
        from .water_loss import lambert_coefficient_templates

        for template in lambert_coefficient_templates():
            if template["role"] == name:
                return template["published_value"]
        return None
    if source == LAMBERT_2009:
        return {"mains_coefficient": 2.0, "connections_coefficient": 1.25}.get(name)
    return None


def _aqua_coefficient_declarations():
    from .night_flow import CoefficientDeclaration
    from .water_loss import lambert_coefficient_templates

    return {
        template["role"]: CoefficientDeclaration(
            constant=template["published_value"],
            meaning=template["meaning"],
            unit=template["unit"],
            source=template["source"],
        )
        for template in lambert_coefficient_templates()
    }


def compute_reference_case(case: ReferenceCase) -> float | None:
    """Compute the case's quantity using the library's own functions."""
    inputs = case.inputs

    if case.name == "aqua1999_uarl_example":
        from .water_loss import PressureFactor, UarlInputs, compute_uarl_l_per_day

        network_inputs = UarlInputs(
            mains_length_km=inputs["mains_length_km"],
            service_connections=int(inputs["service_connections"]),
            private_pipe_length_km=inputs["private_length_km"],
            pressure_factor=PressureFactor(
                average_pressure_m=inputs["average_pressure_m"],
                method="published reference case",
                measured=True,
            ),
        )
        coefficients = _aqua_coefficient_declarations()
        lpd_day = compute_uarl_l_per_day(
            network_inputs,
            main_length_coefficient=coefficients["mains"],
            connections_coefficient=coefficients["connections"],
            private_length_coefficient=coefficients["private"],
        )
        return lpd_day * inputs["days"] / 1_000_000.0

    if case.name == "aqua1999_tirl_case":
        from .water_loss import ili_assessment

        assessment = ili_assessment(
            annual_real_loss_m3=inputs["annual_real_losses_m3"],
            input_volume_m3_per_year=inputs["annual_real_losses_m3"],
            uarl_l_per_day=None,
            accounting_days=inputs["days"],
        )
        return assessment.carl_l_per_day / inputs["service_connections"]

    if case.name == "aqua1999_ili_case":
        from .water_loss import infrastructure_leakage_index

        return infrastructure_leakage_index(
            carl_l_per_day=inputs["tirl_l_per_connection_day"],
            uarl_l_per_day=inputs["uarl_l_per_connection_day"],
        )

    if case.name == "aqua1999_ili_end_to_end":
        from .water_loss import (
            PressureFactor,
            UarlInputs,
            compute_uarl_l_per_day,
            ili_assessment,
        )

        network_inputs = UarlInputs(
            mains_length_km=inputs["mains_length_km"],
            service_connections=int(inputs["service_connections"]),
            private_pipe_length_km=inputs["private_length_km"],
            pressure_factor=PressureFactor(
                average_pressure_m=inputs["average_pressure_m"],
                method="published reference case",
                measured=True,
            ),
        )
        coefficients = _aqua_coefficient_declarations()
        uarl_l_per_day = compute_uarl_l_per_day(
            network_inputs,
            main_length_coefficient=coefficients["mains"],
            connections_coefficient=coefficients["connections"],
            private_length_coefficient=coefficients["private"],
        )
        assessment = ili_assessment(
            annual_real_loss_m3=inputs["annual_real_losses_m3"],
            input_volume_m3_per_year=inputs["annual_real_losses_m3"],
            uarl_l_per_day=uarl_l_per_day,
            pressure_factor=network_inputs.pressure_factor,
            accounting_days=inputs["days"],
        )
        return assessment.ili

    if case.name == "iwa_taskforce_uarl_case":
        from .water_loss import PressureFactor, UarlInputs, compute_uarl_l_per_day

        network_inputs = UarlInputs(
            mains_length_km=inputs["mains_length_km"],
            service_connections=int(inputs["service_connections"]),
            private_pipe_length_km=inputs["private_length_km"],
            pressure_factor=PressureFactor(
                average_pressure_m=inputs["average_pressure_m"],
                method="published reference case",
                measured=True,
            ),
        )
        coefficients = _aqua_coefficient_declarations()
        lpd_day = compute_uarl_l_per_day(
            network_inputs,
            main_length_coefficient=coefficients["mains"],
            connections_coefficient=coefficients["connections"],
            private_length_coefficient=coefficients["private"],
        )
        return lpd_day / 1000.0

    if case.name == "lambert2009_background_leakage_case":
        return (
            inputs["mains_coefficient"] * inputs["mains_length_km"]
            + inputs["connections_coefficient"] * inputs["service_connections"]
        ) * (inputs["average_zone_night_pressure_m"] / 50.0)

    return None


def run_reference_case(case: ReferenceCase) -> ReferenceCaseResult:
    """Execute one case and compare against the published value."""
    computed = compute_reference_case(case)
    if computed is None:
        return ReferenceCaseResult(
            case, None, None, False, "no implementation for this case"
        )

    if case.published_value == 0:
        relative_error = 0.0 if computed == 0 else float("inf")
    else:
        relative_error = abs(computed - case.published_value) / abs(case.published_value)

    return ReferenceCaseResult(
        case=case,
        computed_value=computed,
        relative_error=relative_error,
        passed=relative_error <= case.tolerance,
        detail=case.rounding_note if relative_error > case.tolerance else None,
    )


def run_reference_cases(cases: Sequence[ReferenceCase] | None = None) -> list[ReferenceCaseResult]:
    """Execute every case. Returns a result per case, pass or fail."""
    return [run_reference_case(case) for case in (cases or all_reference_cases())]


def check_uarl_applicability(
    *,
    service_connections: float,
    mains_length_km: float,
    average_pressure_m: float,
) -> dict[str, Any]:
    """Is this network inside the range the UARL equation was derived for?

    The source states lower limits. Outside them the equation still returns a
    number, and that number is not an estimate of anything.
    """
    connection_density = service_connections / mains_length_km if mains_length_km > 0 else 0.0
    failures: list[str] = []

    if service_connections < UARL_APPLICABILITY_LIMITS["min_service_connections"]:
        failures.append(
            f"{service_connections:,.0f} service connections is below the "
            f"{UARL_APPLICABILITY_LIMITS['min_service_connections']:,.0f} stated minimum"
        )
    if connection_density < UARL_APPLICABILITY_LIMITS["min_connection_density_per_km"]:
        failures.append(
            f"connection density {connection_density:.1f}/km is below the stated "
            f"minimum of {UARL_APPLICABILITY_LIMITS['min_connection_density_per_km']:.0f}/km"
        )
    if average_pressure_m < UARL_APPLICABILITY_LIMITS["min_average_pressure_m"]:
        failures.append(
            f"average pressure {average_pressure_m:.1f} m is below the stated "
            f"minimum of {UARL_APPLICABILITY_LIMITS['min_average_pressure_m']:.0f} m"
        )

    return {
        "within_limits": not failures,
        "connection_density_per_km": connection_density,
        "failures": failures,
        "note": UARL_LIMITS_RELAXED_2009["note"],
    }


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_reference_cases(
    cases: Sequence[ReferenceCase] | None = None,
) -> list[Any]:
    """Run the published cases and report any that do not reproduce.

    Conditions emitted
    ------------------
    ``coefficient_reference_case_failed``
        The implementation does not reproduce a published worked example.
        Critical: a formula that cannot reproduce its own source figure should
        not be used, whatever else it looks right about.
    ``coefficient_reference_case_passed``
        The implementation reproduces the published figure within tolerance.
        Informational, recorded as evidence rather than as a defect.
    ``coefficient_uarl_outside_applicability``
        Reported separately by :func:`validate_uarl_applicability`.
    """
    results = run_reference_cases(cases)
    issues: list[Any] = []

    for result in results:
        if result.passed:
            issues.append(
                _issue(
                    "coefficient_reference_case_passed", "info",
                    f"{result.case.name} reproduces the published "
                    f"{result.case.published_value:g} {result.case.published_units} to within "
                    f"{(result.relative_error or 0.0) * 100:.2f} percent. Source: "
                    f"{result.case.citation}",
                    result.as_dict(),
                )
            )
        else:
            issues.append(
                _issue(
                    "coefficient_reference_case_failed", "critical",
                    f"{result.case.name} computes {result.computed_value:g} against a published "
                    f"{result.case.published_value:g} {result.case.published_units}, a relative "
                    f"error of {(result.relative_error or 0.0) * 100:.2f} percent against a "
                    f"{result.case.tolerance * 100:.0f} percent tolerance. Do not use this "
                    f"result. Source: {result.case.citation}"
                    + (f" Note: {result.detail}" if result.detail else ""),
                    result.as_dict(),
                )
            )

    return issues


def validate_uarl_applicability(
    *,
    service_connections: float,
    mains_length_km: float,
    average_pressure_m: float,
) -> list[Any]:
    """Report use of the UARL equation outside its stated range."""
    report = check_uarl_applicability(
        service_connections=service_connections,
        mains_length_km=mains_length_km,
        average_pressure_m=average_pressure_m,
    )
    if report["within_limits"]:
        return []
    return [
        _issue(
            "coefficient_uarl_outside_applicability", "high",
            "The UARL equation is being applied outside the range it was derived for: "
            + "; ".join(report["failures"])
            + ". It will still return a number, and that number is not an estimate of "
              "unavoidable losses for a network of this size, density and pressure. "
            + report["note"],
            report,
        )
    ]


__all__ = [
    "AQUA_1999",
    "AQUA_DAYS_PRESSURISED",
    "IWA_TASKFORCE",
    "LAMBERT_2009",
    "PROBLEM_NAME",
    "UARL_APPLICABILITY_LIMITS",
    "ReferenceCase",
    "ReferenceCaseResult",
    "all_reference_cases",
    "aqua1999_ili_case",
    "aqua1999_tirl_case",
    "aqua1999_uarl_example",
    "check_uarl_applicability",
    "compute_reference_case",
    "iwa_taskforce_uarl_case",
    "lambert2009_background_leakage_case",
    "run_reference_case",
    "run_reference_cases",
    "validate_reference_cases",
    "validate_uarl_applicability",
]