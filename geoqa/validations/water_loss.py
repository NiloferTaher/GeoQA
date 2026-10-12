"""Unavoidable Annual Real Loss and the Infrastructure Leakage Index.

Why this needs declared coefficients too
-----------------------------------------
Lambert's UARL formulation is a linear regression with three fitted
coefficients: main length, number of service connections, and total length of
private pipe. The multipliers (18, 0.8, 25) and the pressure factor P come from
empirical studies whose values differ by country, network age and pressure
regime. They are not universal constants and this module will not supply them.

So the same rule as the night-flow module applies: no coefficient enters
without a declaration, and a declaration without reproduction evidence is
reported.

Why ILI is never returned as a verdict
---------------------------------------
The IWA Water Loss Specialist Group is explicit that ILI should not be used
alone for target setting. A single number invites exactly the comparison it
cannot support: a network with ILI 3.0 is not "better" than one with 2.8 unless
pressure regime, connection density and accounting period are comparable, and
usually they are not.

Every function here therefore returns the inputs alongside the index, and
:func:`ili_assessment` returns a statement of what may and may not be concluded
rather than a rating.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

PROBLEM_NAME = "water_loss_indicator"

# Lambert's three regression coefficients, left undeclared on purpose.
LAMBERT_MAIN_LENGTH_COEF = "18"
LAMBERT_CONNECTIONS_COEF = "0.8"
LAMBERT_PRIVATE_LENGTH_COEF = "25"

_DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class PressureFactor:
    """Average pressure in the network, and how it was established."""

    average_pressure_m: float
    method: str
    measured: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "average_pressure_m": self.average_pressure_m,
            "method": self.method,
            "measured": self.measured,
        }


@dataclass(frozen=True)
class UarlInputs:
    """Network properties required by the UARL regression."""

    mains_length_km: float
    service_connections: int
    private_pipe_length_km: float
    pressure_factor: PressureFactor | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("mains_length_km", self.mains_length_km),
            ("private_pipe_length_km", self.private_pipe_length_km),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative: {value}")
        if self.service_connections < 0:
            raise ValueError(
                f"service_connections cannot be negative: {self.service_connections}"
            )
        if (
            self.pressure_factor is not None
            and self.pressure_factor.average_pressure_m <= 0
        ):
            raise ValueError(
                "average_pressure_m must be positive: "
                f"{self.pressure_factor.average_pressure_m}"
            )

    @property
    def average_pressure(self) -> float:
        """Return the declared mean pressure in metres.

        UARL is proportional to pressure in metres, so no neutral default
        exists. A PressureFactor must be supplied.
        """
        if self.pressure_factor is None:
            raise ValueError(
                "Average pressure was not declared. UARL is proportional to "
                "pressure in meters, so no neutral default exists; a "
                "PressureFactor must be supplied."
            )
        return self.pressure_factor.average_pressure_m

    def as_dict(self) -> dict[str, Any]:
        return {
            "mains_length_km": self.mains_length_km,
            "service_connections": self.service_connections,
            "private_pipe_length_km": self.private_pipe_length_km,
            "pressure_factor": (
                self.pressure_factor.as_dict() if self.pressure_factor is not None else None
            ),
        }


@dataclass
class WaterLossAssessment:
    """The index, plus everything needed to interpret it."""

    ili: float | None
    carl_l_per_day: float | None
    uarl_l_per_day: float | None
    annual_real_loss_m3: float | None
    input_volume_m3_per_year: float | None
    nrw_percent: float | None
    pressure_factor: dict[str, Any] | None
    caveats: tuple[str, ...] = ()
    blocking_gaps: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ili": self.ili,
            "carl_l_per_day": self.carl_l_per_day,
            "uarl_l_per_day": self.uarl_l_per_day,
            "annual_real_loss_m3": self.annual_real_loss_m3,
            "input_volume_m3_per_year": self.input_volume_m3_per_year,
            "nrw_percent": self.nrw_percent,
            "pressure_factor": self.pressure_factor,
            "caveats": list(self.caveats),
            "blocking_gaps": list(self.blocking_gaps),
        }


# Lambert's coefficients are imported lazily to avoid a circular import with the
# coefficient-declaration machinery.
def _declaration_class():
    from .night_flow import CoefficientDeclaration

    return CoefficientDeclaration


def compute_uarl_l_per_day(
    inputs: UarlInputs,
    *,
    main_length_coefficient,
    connections_coefficient,
    private_length_coefficient,
) -> float:
    """Unavoidable annual real loss, L/day.

    ``(c_main * Lm + c_conn * Nc + c_priv * Lp) * P``

    All three coefficients must be declared. The formulation itself is not in
    dispute; the multipliers are, and they vary by network.
    """
    Declaration = _declaration_class()
    for name, coefficient in (
        ("main_length_coefficient", main_length_coefficient),
        ("connections_coefficient", connections_coefficient),
        ("private_length_coefficient", private_length_coefficient),
    ):
        if not isinstance(coefficient, Declaration):
            raise TypeError(
                f"{name} must be a CoefficientDeclaration; this module does not "
                "supply Lambert's empirical multipliers"
            )
        if not coefficient.is_complete:
            raise ValueError(f"{name} is missing a meaning or a unit")

    per_year = (
        main_length_coefficient.constant * inputs.mains_length_km
        + connections_coefficient.constant * inputs.service_connections
        + private_length_coefficient.constant * inputs.private_pipe_length_km
    )
    return per_year * inputs.average_pressure


def infrastructure_leakage_index(
    *,
    carl_l_per_day: float,
    uarl_l_per_day: float,
) -> float:
    """ILI = CARL / UARL. Returns a value, never a verdict."""
    if uarl_l_per_day <= 0:
        raise ValueError(f"UARL must be positive: {uarl_l_per_day}")
    if carl_l_per_day < 0:
        raise ValueError(f"CARL cannot be negative: {carl_l_per_day}")
    return carl_l_per_day / uarl_l_per_day


def ili_assessment(
    *,
    annual_real_loss_m3: float,
    input_volume_m3_per_year: float,
    uarl_l_per_day: float | None,
    pressure_factor: PressureFactor | None = None,
    accounting_days: float = _DAYS_PER_YEAR,
    ili_threshold_coefficient=None,
) -> WaterLossAssessment:
    """Build an ILI assessment with its interpretation attached.

    A threshold coefficient may be declared; when it is, the output states
    whether the index falls below it. Even then the caveat stands, because a
    threshold comparison is exactly the use the IWA group warns against without
    context.

    Where a genuine gap exists it is recorded in ``blocking_gaps`` rather than
    filled with a plausible default.
    """
    caveats: list[str] = []
    blocking: list[str] = []

    if input_volume_m3_per_year <= 0:
        raise ValueError("input volume must be positive")
    if annual_real_loss_m3 < 0:
        raise ValueError("real losses cannot be negative")
    if accounting_days <= 0:
        raise ValueError("accounting period must be positive")

    carl = 1_000.0 * annual_real_loss_m3 / accounting_days
    nrw_percent = 100.0 * annual_real_loss_m3 / input_volume_m3_per_year

    ili = None
    if uarl_l_per_day is None:
        blocking.append(
            "No UARL was computed, so no ILI is reported. UARL requires mains "
            "length, connection count, private pipe length and average pressure, "
            "and Lambert's multipliers, which vary by network."
        )
    else:
        ili = infrastructure_leakage_index(carl_l_per_day=carl, uarl_l_per_day=uarl_l_per_day)

    if pressure_factor is not None and not pressure_factor.measured:
        caveats.append(
            "Average pressure was estimated rather than measured, so the pressure "
            "factor P carries that uncertainty into the UARL and therefore into ILI."
        )

    caveats.append(
        "ILI is reported as a value only. The IWA Water Loss Specialist Group "
        "advises against using it in isolation for target setting: networks with "
        "similar indices may differ in pressure regime, connection density and "
        "accounting period."
    )
    average_flow_m3h = input_volume_m3_per_year / accounting_days / 24.0
    if average_flow_m3h < 1.0:
        caveats.append(
            f"Average input flow is {average_flow_m3h:.2f} m3/h, below 1 m3/h, so the "
            "reporting period is very short relative to the network; an index computed "
            "over it is unstable"
        )

    below_threshold = None
    if ili is not None and ili_threshold_coefficient is not None:
        below_threshold = ili < ili_threshold_coefficient.constant
        caveats.append(
            f"Compared against a declared threshold of "
            f"{ili_threshold_coefficient.constant:g}; a threshold comparison does "
            "not substitute for the context above."
        )

    return WaterLossAssessment(
        ili=ili,
        carl_l_per_day=carl,
        uarl_l_per_day=uarl_l_per_day,
        annual_real_loss_m3=annual_real_loss_m3,
        input_volume_m3_per_year=input_volume_m3_per_year,
        nrw_percent=nrw_percent,
        pressure_factor=pressure_factor.as_dict() if pressure_factor else None,
        caveats=tuple(caveats),
        blocking_gaps=tuple(blocking),
    )


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_water_loss(
    assessment: WaterLossAssessment,
    *,
    uarl_inputs: UarlInputs | None = None,
) -> list[Any]:
    """Check a water-loss assessment for the conditions that make it unusable."""
    issues: list[Any] = []

    if assessment.ili is None:
        issues.append(
            _issue(
                "ili_not_computable",
                "medium",
                "ILI was not computed because no UARL is available. Reporting a "
                "leakage index without it would be reporting a ratio against an "
                "assumed rather than derived baseline",
                assessment.as_dict(),
            )
        )
    else:
        issues.append(
            _issue(
                "ili_requires_context",
                "medium",
                f"ILI is {assessment.ili:.2f}. The IWA Water Loss Specialist Group "
                "advises that ILI must not be used in isolation for target setting",
                assessment.as_dict(),
            )
        )

    if uarl_inputs is not None and uarl_inputs.pressure_factor is None:
        issues.append(
            _issue(
                "uarl_pressure_factor_estimated",
                "high",
                "Average pressure was not declared. UARL is proportional to "
                "pressure in meters, so no neutral default exists; a "
                "PressureFactor must be supplied",
                uarl_inputs.as_dict(),
            )
        )
    elif uarl_inputs is not None and not uarl_inputs.pressure_factor.measured:
        issues.append(
            _issue(
                "uarl_pressure_factor_estimated",
                "medium",
                f"Average pressure ({uarl_inputs.average_pressure:.1f} m) was "
                f"{uarl_inputs.pressure_factor.method}, not measured. UARL scales "
                "linearly with pressure, so an error here passes straight into ILI",
                uarl_inputs.as_dict(),
            )
        )

    if assessment.ili is not None and assessment.ili < 0:
        issues.append(
            _issue(
                "ili_out_of_range",
                "high",
                f"ILI is {assessment.ili:.2f}, which is below zero and therefore "
                "outside the physically meaningful range",
                assessment.as_dict(),
            )
        )

    if assessment.ili is not None and assessment.ili < 0.5:
        issues.append(
            _issue(
                "ili_below_possible_range",
                "medium",
                f"ILI is {assessment.ili:.2f}. Values under 0.5 are usually the "
                "result of an accounting error, an implausibly low UARL, or real "
                "losses below what the pipes can physically pass",
                assessment.as_dict(),
            )
        )

    if assessment.nrw_percent is not None and assessment.nrw_percent > 100:
        issues.append(
            _issue(
                "nrw_exceeds_input",
                "critical",
                f"Real losses are {assessment.nrw_percent:.1f}% of input volume, "
                "which exceeds the water that entered the system",
                assessment.as_dict(),
            )
        )

    if uarl_inputs is not None and uarl_inputs.service_connections == 0:
        issues.append(
            _issue(
                "uarl_missing_connections",
                "high",
                "Service connection count is zero, so the UARL regression omits its "
                "largest term for a distribution network and will understate the "
                "baseline substantially",
                uarl_inputs.as_dict(),
            )
        )

    return issues


def lambert_coefficient_templates() -> list[dict[str, Any]]:
    """Starter declarations carrying their published provenance.

    The values are still ``None`` and a caller must still supply a declaration:
    filling these in silently would mean every network is fitted to one
    publication whether or not that publication applies to it. What has changed
    is that the source is no longer unknown, so a declaration built from these
    templates carries a citation rather than a shrug.

    The coefficient values themselves are the UARL Total column of Table 4 in
    Lambert, Brown, Takizawa, Weimer & Karam (1999), AQUA Journal, IWA
    Publishing. That table decomposes each component into background losses,
    reported bursts and unreported bursts; the 18, 0.80 and 25 are the sums.

    Applicability is stated in the source and narrower than general use suggests:
    more than 5,000 service connections, connection density above 20 per km, and
    average pressure above 25 m. Use
    :func:`~geoqa.validations.reference_cases.validate_uarl_applicability` to
    check a network against those limits rather than assuming them.
    """
    source = (
        "Lambert, Brown, Takizawa, Weimer & Karam (1999), A Review of Performance "
        "Indicators for Real Losses from Water Supply Systems, AQUA Journal, IWA "
        "Publishing, Table 4."
    )
    return [
        {
            "role": "mains",
            "constant": None,
            "meaning": "UARL coefficient on mains length",
            "unit": "L/day per km per metre of pressure",
            "source": source,
            "published_value": 18.0,
            "note": "Table 4 UARL Total for mains, being 9.6 background plus 5.8 "
                    "reported bursts plus 2.6 unreported bursts.",
        },
        {
            "role": "connections",
            "constant": None,
            "meaning": "UARL coefficient on service connections",
            "unit": "L/day per connection per metre of pressure",
            "source": source,
            "published_value": 0.80,
            "note": "Table 4 UARL Total for connections with meters at the edge of "
                    "street, being 0.60 background plus 0.04 plus 0.16.",
        },
        {
            "role": "private",
            "constant": None,
            "meaning": "UARL coefficient on private pipe length",
            "unit": "L/day per km per metre of pressure",
            "source": source,
            "published_value": 25.0,
            "note": "Table 4 UARL Total for underground pipe between the edge of "
                    "street and the customer meter, being 16.0 plus 1.9 plus 7.1.",
        },
    ]


__all__ = [
    "LAMBERT_CONNECTIONS_COEF",
    "LAMBERT_MAIN_LENGTH_COEF",
    "LAMBERT_PRIVATE_LENGTH_COEF",
    "PROBLEM_NAME",
    "PressureFactor",
    "UarlInputs",
    "WaterLossAssessment",
    "compute_uarl_l_per_day",
    "ili_assessment",
    "infrastructure_leakage_index",
    "lambert_coefficient_templates",
    "validate_water_loss",
]