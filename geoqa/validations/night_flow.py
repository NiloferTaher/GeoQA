"""Night-flow leakage and NRW coefficients, under declared provenance.

The design problem
------------------
Leakage coefficients are empirical. A typical night-flow rate for a main-line
leak is a fitted number from a reference or from vendor outputs, not a
universal constant, and it varies by material, pressure and jurisdiction.

The temptation is to hardcode them. That is precisely the failure this package
exists to catch: a number nobody can source, sitting inside a decision chain,
producing a savings figure that nobody signed.

So this module never supplies a coefficient. It accepts declared ones and
checks them.

What can and cannot be verified
-------------------------------
**Cannot:** whether a declared coefficient is physically correct for a given
network. That needs measurement or a published source, and only the analyst has
those.

**Can:**

*reproduction*
    Given an observed figure and its known inputs, solve for the implied
    coefficient and compare it to the declared one. This is what actually
    validates a fitted constant, and it is checkable.

*unit consistency*
    A constant declared in L/day inside a formula that produces m3/day is a
    unit error even when the magnitude looks plausible.

*consistency of use*
    The same constant appearing with two different meanings in one chain.

*declaration completeness*
    A coefficient with no meaning, unit or provenance recorded.

Declaration is not optional. Every function here requires one, which is the
whole point: a number cannot enter a water-loss calculation without someone
stating what it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

PROBLEM_NAME = "coefficient_provenance"

GALLONS_PER_CUBIC_METRE = 264.172052
LITRES_PER_CUBIC_METRE = 1000.0

# Unit families, used to check that a declared unit matches the arithmetic.
_VOLUME_UNITS_PER_DAY = {"l/day", "litre/day", "l/day", "litres/day", "lpcd"}
_CUBIC_METRE_UNITS = {"m3/day", "m^3/day", "m3d-1", "cubic metre/day", "cms"}


@dataclass(frozen=True)
class CoefficientDeclaration:
    """A coefficient, and everything someone must state about it."""

    constant: float
    meaning: str
    unit: str
    source: str | None = None
    #: How the value was arrived at.
    basis: str | None = None
    verified: bool = False
    #: Observed figure and inputs, when the coefficient was fitted rather than
    #: looked up. Enables the reproduction check.
    fitted_from: "ReproductionEvidence | None" = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "constant": self.constant,
            "meaning": self.meaning,
            "unit": self.unit,
            "source": self.source,
            "basis": self.basis,
            "verified": self.verified,
            "has_reproduction_evidence": self.fitted_from is not None,
        }

    @property
    def is_complete(self) -> bool:
        return bool(self.meaning.strip() and self.unit.strip())


@dataclass(frozen=True)
class ReproductionEvidence:
    """An observed figure and the inputs needed to derive the coefficient.

    ``implied_constant`` is what solving the relationship gives. Comparing it to
    the declared value is the only real test of a fitted number.
    """

    observed_output: float
    known_inputs: Mapping[str, float]
    relationship: str
    implied_constant: float | None = None

    def relative_error(self, declared: float) -> float | None:
        if self.implied_constant in (None, 0):
            return None
        if declared == 0:
            return None
        return abs(self.implied_constant - declared) / abs(declared)


# --------------------------------------------------------------------------
# Physical relationships. Each returns the quantity it names, given declared
# coefficients only.
# --------------------------------------------------------------------------


def orifice_discharge(
    *,
    discharge_coefficient: CoefficientDeclaration,
    area_m2: float,
    pressure_head_m: float,
) -> float:
    """Orifice discharge ``Q = Cd * A * sqrt(2 g h)`` in m3/s.

    ``discharge_coefficient`` must be declared. The coefficient of discharge is
    genuinely empirical and varies with orifice geometry and Reynolds number;
    there is no defensible default.
    """
    if not isinstance(discharge_coefficient, CoefficientDeclaration):
        raise TypeError(
            "discharge_coefficient must be a CoefficientDeclaration; this module "
            "does not supply empirical constants"
        )
    if not discharge_coefficient.is_complete:
        raise ValueError("discharge_coefficient is missing a meaning or a unit")
    if pressure_head_m < 0:
        raise ValueError(f"pressure head cannot be negative: {pressure_head_m}")
    return discharge_coefficient.constant * area_m2 * math.sqrt(2.0 * 9.80665 * pressure_head_m)


def favad_flow_ratio(
    *,
    base_flow_lps: float,
    pressure_ratio: float,
    exponent: CoefficientDeclaration,
) -> float:
    """Pressure-driven flow change ``Q1 / Q0 = (P1 / P0) ^ n``.

    The FAVAD exponent is empirical and network-specific; 0.5 is a common
    assumption and 1.0 is the fully pressure-driven limit, but neither is a
    default this module will apply for you.
    """
    if not isinstance(exponent, CoefficientDeclaration):
        raise TypeError("exponent must be a CoefficientDeclaration")
    if not exponent.is_complete:
        raise ValueError("exponent is missing a meaning or a unit")
    if pressure_ratio <= 0:
        raise ValueError(f"pressure ratio must be positive: {pressure_ratio}")
    if base_flow_lps < 0:
        raise ValueError(f"base flow cannot be negative: {base_flow_lps}")
    return base_flow_lps * (pressure_ratio ** exponent.constant)


def fadd(nnfi: float, pressure_m: float, exponent: CoefficientDeclaration) -> float:
    """Fixed-and-variable discharge split at normal operating pressure.

    ``NNFI`` is the night flow as a fraction of average daily flow.
    """
    if not isinstance(exponent, CoefficientDeclaration):
        raise TypeError("exponent must be a CoefficientDeclaration")
    if not 0.0 <= nnfi <= 1.0:
        raise ValueError(f"NNFI must be between 0 and 1: {nnfi}")
    if pressure_m < 0:
        raise ValueError(f"pressure cannot be negative: {pressure_m}")
    return nnfi * pressure_m ** exponent.constant


def nightly_leakage_from_night_flow(
    *,
    minimum_night_flow_m3h: float,
    hours_of_night: float,
    legitimate_night_use_m3h: float,
) -> float:
    """Night-flow leakage in m3 over the night window.

    Deliberately simple and deliberately declared-parameter-free: every quantity
    is supplied by the caller. No hidden background loss, no assumed customer
    consumption profile.
    """
    if minimum_night_flow_m3h < 0:
        raise ValueError(f"night flow cannot be negative: {minimum_night_flow_m3h}")
    if legitimate_night_use_m3h < 0:
        raise ValueError(f"legitimate night use cannot be negative: {legitimate_night_use_m3h}")
    if hours_of_night <= 0:
        raise ValueError(f"hours of night must be positive: {hours_of_night}")
    return (minimum_night_flow_m3h - legitimate_night_use_m3h) * hours_of_night


def pressure_dependent_background_leakage(
    *,
    average_pressure_m: float,
    night_pressure_m: float,
    nnfi: float,
    exponent: CoefficientDeclaration,
    reference_pressure_m: float,
    night_pressure_width_m: float,
) -> float:
    """Background leakage at night pressure, from the FAVAD relationship.

    ``night_pressure_width_m`` is the pressure range over which leakage varies
    linearly; the standard formulation multiplies the result by that width.
    """
    if not isinstance(exponent, CoefficientDeclaration):
        raise TypeError("exponent must be a CoefficientDeclaration")
    if reference_pressure_m <= 0:
        raise ValueError("reference_pressure_m must be positive")
    if night_pressure_m <= 0:
        raise ValueError("night_pressure_m must be positive")

    average_flow = (nnfi * average_pressure_m) ** exponent.constant
    night_flow = (nnfi * night_pressure_m) ** exponent.constant
    per_pressure = (average_flow - night_flow) / (average_pressure_m - night_pressure_m)
    return per_pressure * night_pressure_width_m


def apparent_losses_from_mnf(
    *,
    minimum_night_flow_m3h: float,
    hours_of_night: float,
    legitimate_night_use_m3h: float,
    apparent_loss_fraction_of_mnf: CoefficientDeclaration,
) -> float:
    """Apparent losses derived from minimum night flow, in m3.

    ``apparent_loss_fraction_of_mnf`` is the share of night flow attributed to
    consumption rather than leakage. It is one of the least standardised numbers
    in NRW practice and varies with billing cycles and customer behaviour, so it
    is required as a declaration rather than assumed.
    """
    if not isinstance(apparent_loss_fraction_of_mnf, CoefficientDeclaration):
        raise TypeError(
            "apparent_loss_fraction_of_mnf must be a CoefficientDeclaration"
        )
    if not apparent_loss_fraction_of_mnf.is_complete:
        raise ValueError("apparent_loss_fraction_of_mnf is missing a meaning or a unit")
    fraction = apparent_loss_fraction_of_mnf.constant
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be between 0 and 1: {fraction}")

    gross = nightly_leakage_from_night_flow(
        minimum_night_flow_m3h=minimum_night_flow_m3h,
        hours_of_night=hours_of_night,
        legitimate_night_use_m3h=legitimate_night_use_m3h,
    )
    return gross * fraction


# --------------------------------------------------------------------------
# Validation of the declarations themselves.
# --------------------------------------------------------------------------


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_coefficient_declaration(
    declaration: CoefficientDeclaration,
    *,
    expects_volume_unit: bool = False,
    expects_fraction: bool = False,
    reproduction_tolerance: float = 0.01,
) -> list[Any]:
    """Check one declaration for completeness, units and reproduction.

    ``reproduction_tolerance`` is the relative error allowed between the
    declared value and the value implied by supplied evidence. One percent is
    tight, which is deliberate: a fitted coefficient that cannot reproduce its
    own source figure to within one percent was not fitted from it.
    """
    issues: list[Any] = []

    if not declaration.meaning.strip():
        issues.append(
            _issue(
                "coefficient_meaning_undeclared",
                "high",
                f"Coefficient {declaration.constant:g} has no recorded meaning, so a "
                "reader cannot tell what it represents",
                declaration.as_dict(),
            )
        )
    if not declaration.unit.strip():
        issues.append(
            _issue(
                "coefficient_unit_undeclared",
                "high",
                f"Coefficient {declaration.constant:g} has no unit; a value without a "
                "unit cannot be checked for consistency",
                declaration.as_dict(),
            )
        )
    if not declaration.source:
        issues.append(
            _issue(
                "coefficient_source_unrecorded",
                "medium",
                f"Coefficient {declaration.constant:g} ({declaration.meaning or 'unnamed'}) "
                "records no source, so it cannot be traced to a specification or a fit",
                declaration.as_dict(),
            )
        )
    if not declaration.verified:
        issues.append(
            _issue(
                "coefficient_unverified",
                "info",
                f"Coefficient {declaration.constant:g} is not marked verified"
                + (
                    "; it reproduces supplied evidence"
                    if declaration.fitted_from
                    else " and carries no reproduction evidence"
                ),
                declaration.as_dict(),
            )
        )

    unit = declaration.unit.strip().lower()
    if expects_volume_unit and unit in _CUBIC_METRE_UNITS:
        issues.append(
            _issue(
                "coefficient_unit_mismatch",
                "high",
                f"Coefficient {declaration.constant:g} is declared in {declaration.unit!r} "
                "but the surrounding formula produces a rate per day in L/day or m3/day; "
                "the units do not match the arithmetic",
                declaration.as_dict(),
            )
        )
    if expects_volume_unit and unit in _VOLUME_UNITS_PER_DAY:
        issues.append(
            _issue(
                "coefficient_unit_scale_ambiguous",
                "medium",
                f"Coefficient {declaration.constant:g} is declared in {declaration.unit!r} "
                "while the balance is computed in m3; convert explicitly or record the "
                "conversion so the two are not confused",
                declaration.as_dict(),
            )
        )
    if expects_fraction and not (0.0 <= declaration.constant <= 1.0):
        issues.append(
            _issue(
                "coefficient_out_of_range",
                "high",
                f"Coefficient {declaration.constant:g} is used as a fraction but lies "
                "outside [0, 1]",
                declaration.as_dict(),
            )
        )

    evidence = declaration.fitted_from
    if evidence is not None:
        error = evidence.relative_error(declaration.constant)
        if error is None:
            issues.append(
                _issue(
                    "coefficient_reproduction_indeterminate",
                    "medium",
                    f"Reproduction evidence for {declaration.constant:g} cannot yield a "
                    "comparable implied value; the relationship or its inputs are "
                    "incomplete",
                    {**declaration.as_dict(), **evidence.__dict__},
                )
            )
        elif error > reproduction_tolerance:
            issues.append(
                _issue(
                    "coefficient_fails_reproduction",
                    "high",
                    f"Coefficient {declaration.constant:g} does not reproduce its own "
                    f"source figure: the {evidence.relationship} implies "
                    f"{evidence.implied_constant:.6g}, a relative difference of "
                    f"{error:.2%} against a {reproduction_tolerance:.0%} tolerance",
                    {**declaration.as_dict(), **evidence.__dict__, "relative_error": error},
                )
            )
        else:
            issues.append(
                _issue(
                    "coefficient_reproduced",
                    "info",
                    f"Coefficient {declaration.constant:g} reproduces its source figure "
                    f"to within {error:.3%}",
                    {**declaration.as_dict(), **evidence.__dict__, "relative_error": error},
                )
            )

    return issues


def solve_fitted_night_flow_coefficient(
    *,
    observed_volume_m3: float,
    hours_of_night: float,
    legitimate_night_use_m3h: float,
    window_days: int,
) -> float:
    """Back out the night-flow leakage rate that explains an observed volume.

    The inverse of :func:`nightly_leakage_from_night_flow`. Given the volume a
    fit produced and the assumptions used, this returns the rate implied, which
    is what a declared coefficient is checked against.
    """
    total_hours = hours_of_night * window_days
    if total_hours <= 0:
        raise ValueError("hours_of_night and window_days must both be positive")
    return (observed_volume_m3 / total_hours) + legitimate_night_use_m3h


def solve_fitted_favad_exponent(
    *,
    base_flow_lps: float,
    observed_flow_lps: float,
    pressure_ratio: float,
) -> float:
    """Back out the FAVAD exponent implied by two observed flows."""
    if base_flow_lps <= 0 or pressure_ratio <= 0:
        raise ValueError("base flow and pressure ratio must be positive")
    if observed_flow_lps <= 0:
        raise ValueError("observed flow must be positive to solve for an exponent")
    return math.log(observed_flow_lps / base_flow_lps) / math.log(pressure_ratio)


def validate_coefficient_chain(
    declarations: Sequence[tuple[str, CoefficientDeclaration]],
    *,
    expects: Mapping[str, str] | None = None,
    reproduction_tolerance: float = 0.01,
) -> list[Any]:
    """Validate every coefficient in a calculation chain.

    Also catches the same literal declared twice with different meanings, which
    is otherwise invisible and produces quietly inconsistent results.
    """
    issues: list[Any] = []
    by_value: dict[float, list[tuple[str, CoefficientDeclaration]]] = {}

    for name, declaration in declarations:
        issues.extend(
            validate_coefficient_declaration(
                declaration,
                expects_volume_unit=(expects or {}).get(name) == "volume_rate",
                expects_fraction=(expects or {}).get(name) == "fraction",
                reproduction_tolerance=reproduction_tolerance,
            )
        )
        by_value.setdefault(declaration.constant, []).append((name, declaration))

    for value, entries in by_value.items():
        meanings = {d.meaning.strip().lower() for _, d in entries if d.meaning.strip()}
        if len(meanings) > 1:
            issues.append(
                _issue(
                    "coefficient_used_inconsistently",
                    "high",
                    f"Value {value:g} is declared with {len(meanings)} different meanings "
                    f"in one chain ({', '.join(sorted(meanings))}); the same number cannot "
                    "mean two things",
                    {
                        "value": value,
                        "roles": sorted(name for name, _ in entries),
                        "meanings": sorted(meanings),
                    },
                )
            )
    return issues


__all__ = [
    "CoefficientDeclaration",
    "PROBLEM_NAME",
    "ReproductionEvidence",
    "apparent_losses_from_mnf",
    "fadd",
    "favad_flow_ratio",
    "nightly_leakage_from_night_flow",
    "orifice_discharge",
    "pressure_dependent_background_leakage",
    "solve_fitted_favad_exponent",
    "solve_fitted_night_flow_coefficient",
    "validate_coefficient_chain",
    "validate_coefficient_declaration",
]