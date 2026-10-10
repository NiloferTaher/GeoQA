"""IWA water balance and non-revenue water analysis.

What this computes
------------------
The IWA / AWWA water balance is arithmetic on stated inputs. That matters: it
can be implemented without embedding a single empirical coefficient, and every
coefficient it does accept must be supplied by the caller.

The balance, in the form implemented here::

    System Input Volume (SIV)
      = Water Imported + Water Exported + Other Sources + Supplier Water

    System Output Volume (SOV)
      = Authorised Consumption + Real Losses + Apparent Losses

    Non-Revenue Water (NRW)
      = SIV - SOV
      = Real Losses + Apparent Losses

    Authorised Consumption
      = Billed Consumption + Unbilled Consumption
      = Supplied - Unbilled Consumed

    Revenue Water
      = Billed Consumption + Unbilled Billed

with Real Losses decomposed into the standard service/plumbing split, and
Apparent Losses into the four IWA categories.

The design decision that matters
--------------------------------
**Losses are derived, never entered.** If a caller supplies both a real-loss
figure and the components that should sum to it, the module reports the
disagreement rather than silently preferring one. A water balance where losses
are typed in is not a balance; it is a set of numbers.

On ILI
------
The Infrastructure Leakage Index is computed when a UARL is supplied, but it is
never returned as a verdict. The IWA Water Loss Specialist Group is explicit
that ILI should not be used in isolation for target setting, and this module
emits that as a condition rather than a footnote. Anyone wanting a single
verdict will have to read the warning, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

PROBLEM_NAME = "water_balance"

# Default tolerance for the balance-closure check, as a fraction of SIV.
CLOSURE_TOLERANCE = 0.005

REAL_LOSS_COMPONENTS = (
    "transmission_main_leakage",
    "distribution_main_leakage",
    "service_connection_leakage",
    "customer_mains_leakage",
    "storage_losses",
    "exported_water_loss",
)

APPARENT_LOSS_COMPONENTS = (
    "unbilled_consumption",
    "unauthorized_consumption",
    "metering_inaccuracies",
    "data_handling_inaccuracies",
)


@dataclass
class WaterBalanceInputs:
    """Volumes for a reporting period, in m3. Only supply is required."""

    system_input_volume: float

    supplier_water: float = 0.0
    imported_water: float = 0.0
    exported_water: float = 0.0
    other_sources: float = 0.0

    billed_consumption: float = 0.0
    unbilled_billed: float = 0.0
    unbilled_consumption: float = 0.0

    real_loss_components: dict[str, float] = field(default_factory=dict)
    apparent_loss_components: dict[str, float] = field(default_factory=dict)

    #: Optional declared real losses. Used only to cross-check, never as truth.
    declared_real_losses: float | None = None
    declared_apparent_losses: float | None = None
    declared_nrw: float | None = None

    #: Optional apparent losses derived from night flow rather than itemised.
    night_flow_apparent_losses: float | None = None

    #: When an apparent loss is derived rather than itemised, report it as a
    #: balance error too: an unexplained residual is not a measurement.
    closure_tolerance: float = CLOSURE_TOLERANCE

    def __post_init__(self) -> None:
        for name in REAL_LOSS_COMPONENTS:
            self.real_loss_components.setdefault(name, 0.0)
        for name in APPARENT_LOSS_COMPONENTS:
            self.apparent_loss_components.setdefault(name, 0.0)


@dataclass
class WaterBalanceResult:
    """Computed balance, with every intermediate value retained."""

    system_input_volume: float
    supply_total: float
    authorised_consumption: float
    revenue_water: float
    real_losses: float
    real_loss_components: dict[str, float]
    apparent_losses: float
    apparent_loss_components: dict[str, float]
    non_revenue_water: float
    system_output_volume: float
    nrw_percentage: float
    ili: float | None = None
    uarl: float | None = None
    cawl: float | None = None
    derived_apparent_losses: bool = False
    closure_error: float = 0.0
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "system_input_volume_m3": self.system_input_volume,
            "supply_total_m3": self.supply_total,
            "authorised_consumption_m3": self.authorised_consumption,
            "revenue_water_m3": self.revenue_water,
            "real_losses_m3": self.real_losses,
            "real_loss_components_m3": dict(self.real_loss_components),
            "apparent_losses_m3": self.apparent_losses,
            "apparent_loss_components_m3": dict(self.apparent_loss_components),
            "non_revenue_water_m3": self.non_revenue_water,
            "system_output_volume_m3": self.system_output_volume,
            "nrw_percent": self.nrw_percentage,
            "ili": self.ili,
            "uarl_l_per_day": self.uarl,
            "carl_l_per_day": self.cawl,
            "derived_apparent_losses": self.derived_apparent_losses,
            "closure_error_m3": self.closure_error,
            "notes": list(self.notes),
        }


def compute_water_balance(
    inputs: WaterBalanceInputs,
    *,
    days_in_period: float | None = None,
    uarl: float | None = None,
    cawl: float | None = None,
) -> WaterBalanceResult:
    """Compute the IWA water balance.

    ``uarl`` and ``cawl`` are caller-supplied in L/day. The module does not
    compute a UARL, because that requires service-connection counts, main
    lengths and pressure that only the network owner holds, and because the
    Lambert coefficients are empirical. Supply them, or ILI is not reported.
    """
    notes: list[str] = []

    supply_total = (
        inputs.supplier_water
        + inputs.imported_water
        + inputs.exported_water
        + inputs.other_sources
    )

    real_losses = float(sum(inputs.real_loss_components.values()))
    real_components = {
        name: float(inputs.real_loss_components.get(name, 0.0))
        for name in REAL_LOSS_COMPONENTS
    }

    itemised_apparent = float(sum(inputs.apparent_loss_components.values()))
    apparent_components = {
        name: float(inputs.apparent_loss_components.get(name, 0.0))
        for name in APPARENT_LOSS_COMPONENTS
    }

    derived = False
    apparent_losses = itemised_apparent
    if inputs.night_flow_apparent_losses is not None:
        apparent_losses = float(inputs.night_flow_apparent_losses)
        derived = True
        residual = apparent_losses - itemised_apparent
        notes.append(
            f"Night flow implies apparent losses of {apparent_losses:,.0f} m3; "
            f"itemised components total {itemised_apparent:,.0f} m3 "
            f"(difference {residual:,.0f} m3)"
        )
        apparent_components["night_flow_residual"] = residual

    authorised = inputs.billed_consumption + inputs.unbilled_consumption
    revenue_water = inputs.billed_consumption + inputs.unbilled_billed
    nrw = real_losses + apparent_losses
    sov = authorised + nrw

    siv = inputs.system_input_volume
    nrw_pct = (100.0 * nrw / siv) if siv else 0.0
    closure_error = supply_total - siv

    ili = None
    resolved_carl: float | None = None
    if uarl is not None:
        resolved_carl = cawl
        if resolved_carl is None and days_in_period:
            resolved_carl = 1_000_000.0 * real_losses / days_in_period
        if resolved_carl is not None and uarl:
            ili = resolved_carl / uarl
            notes.append(
                "ILI is reported with its value only. The IWA Water Loss Specialist "
                "Group advises against using it in isolation for target setting."
            )

    return WaterBalanceResult(
        system_input_volume=siv,
        supply_total=supply_total,
        authorised_consumption=authorised,
        revenue_water=revenue_water,
        real_losses=real_losses,
        real_loss_components=real_components,
        apparent_losses=apparent_losses,
        apparent_loss_components=apparent_components,
        non_revenue_water=nrw,
        system_output_volume=sov,
        nrw_percentage=nrw_pct,
        ili=ili,
        uarl=uarl,
        cawl=resolved_carl,
        derived_apparent_losses=derived,
        closure_error=closure_error,
        notes=tuple(notes),
    )


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_water_balance(
    inputs: WaterBalanceInputs,
    result: WaterBalanceResult | None = None,
) -> list[Any]:
    """Check that a balance is internally consistent.

    The interesting checks are the ones a water balance is usually quietly wrong
    about: supply that does not match the components, losses typed in alongside
    the components that should produce them, and a real loss total that is
    negative because two large errors cancelled.
    """
    if result is None:
        result = compute_water_balance(inputs)

    issues: list[Any] = []
    siv = inputs.system_input_volume
    tolerance = max(inputs.closure_tolerance, 0.0) * abs(siv) if siv else 0.0

    # --- supply closure ------------------------------------------------
    if abs(result.closure_error) > max(tolerance, 1.0):
        issues.append(
            _issue(
                "water_balance_supply_mismatch",
                "high",
                f"Supply components total {result.supply_total:,.0f} m3 but declared "
                f"system input volume is {siv:,.0f} m3, a difference of "
                f"{result.closure_error:,.0f} m3; the balance cannot close",
                {
                    "supply_total": result.supply_total,
                    "system_input_volume": siv,
                    "difference": result.closure_error,
                },
            )
        )

    # --- losses must be derived, not declared ---------------------------
    if inputs.declared_real_losses is not None:
        difference = inputs.declared_real_losses - result.real_losses
        if abs(difference) > max(tolerance, 1.0):
            issues.append(
                _issue(
                    "water_balance_loss_mismatch",
                    "high",
                    f"Declared real losses ({inputs.declared_real_losses:,.0f} m3) do not "
                    f"equal the sum of loss components ({result.real_losses:,.0f} m3); "
                    "losses must be derived, not entered",
                    {
                        "declared_real_losses": inputs.declared_real_losses,
                        "derived_real_losses": result.real_losses,
                        "difference": difference,
                    },
                )
            )

    if inputs.declared_apparent_losses is not None:
        difference = inputs.declared_apparent_losses - result.apparent_losses
        if abs(difference) > max(tolerance, 1.0):
            issues.append(
                _issue(
                    "water_balance_loss_mismatch",
                    "high",
                    f"Declared apparent losses ({inputs.declared_apparent_losses:,.0f} m3) do "
                    f"not equal the itemised apparent loss total "
                    f"({result.apparent_losses:,.0f} m3)",
                    {
                        "declared_apparent_losses": inputs.declared_apparent_losses,
                        "derived_apparent_losses": result.apparent_losses,
                        "difference": difference,
                    },
                )
            )

    if inputs.declared_nrw is not None:
        difference = inputs.declared_nrw - result.non_revenue_water
        if abs(difference) > max(tolerance, 1.0):
            issues.append(
                _issue(
                    "water_balance_nrw_mismatch",
                    "high",
                    f"Declared NRW ({inputs.declared_nrw:,.0f} m3) does not equal real plus "
                    f"apparent losses ({result.non_revenue_water:,.0f} m3)",
                    {
                        "declared_nrw": inputs.declared_nrw,
                        "derived_nrw": result.non_revenue_water,
                        "difference": difference,
                    },
                )
            )

    # --- impossible values ------------------------------------------------
    for name, value in result.real_loss_components.items():
        if value < 0:
            issues.append(
                _issue(
                    "water_balance_negative_component",
                    "high",
                    f"Real loss component '{name}' is negative ({value:,.0f} m3); a loss "
                    "cannot be negative, so the component has been mis-signed",
                    {"component": name, "value": value},
                )
            )
    for name, value in result.apparent_loss_components.items():
        if value < 0 and name != "night_flow_residual":
            issues.append(
                _issue(
                    "water_balance_negative_component",
                    "high",
                    f"Apparent loss component '{name}' is negative ({value:,.0f} m3)",
                    {"component": name, "value": value},
                )
            )

    # --- NRW share ---------------------------------------------------------
    if siv and result.nrw_percentage > 100.0:
        issues.append(
            _issue(
                "water_balance_nrw_exceeds_input",
                "critical",
                f"NRW is {result.nrw_percentage:.1f}% of system input volume, which is not "
                "possible; losses exceed the water that entered the system",
                {"nrw_percent": result.nrw_percentage, "system_input_volume": siv},
            )
        )

    # --- ILI must never stand alone -----------------------------------------
    if result.ili is not None:
        issues.append(
            _issue(
                "ili_requires_context",
                "medium",
                f"ILI is {result.ili:.2f}. The IWA Water Loss Specialist Group advises that "
                "ILI must not be used in isolation for target setting; it is reported here "
                "as a value only",
                {"ili": result.ili, "uarl": result.uarl, "carl": result.cawl},
            )
        )
    else:
        issues.append(
            _issue(
                "ili_not_computable",
                "info",
                "ILI was not computed because a UARL was not supplied. A UARL requires "
                "service-connection counts, main lengths and average pressure, and the "
                "Lambert coefficients are empirical, so it is not derived here",
                {"uarl_supplied": result.uarl is not None},
            )
        )

    # --- night-flow residual -------------------------------------------------
    if result.derived_apparent_losses:
        residual = result.apparent_loss_components.get("night_flow_residual", 0.0)
        if abs(residual) > max(tolerance, 1.0):
            issues.append(
                _issue(
                    "water_balance_night_flow_residual",
                    "medium",
                    f"Night-flow apparent losses differ from the itemised total by "
                    f"{residual:,.0f} m3. A residual is expected, because night flow "
                    "captures a combined signal, but a large one should be explained "
                    "rather than absorbed",
                    {"residual": residual, "tolerance": tolerance},
                )
            )

    return issues


def nrw_from_components(
    *,
    system_input_volume: float,
    real_losses: Mapping[str, float] | None = None,
    apparent_losses: Mapping[str, float] | None = None,
    **supply: float,
) -> WaterBalanceResult:
    """Convenience constructor from component dictionaries.

    Supply keyword arguments are forwarded to :class:`WaterBalanceInputs`, so
    ``supplier_water``, ``imported_water``, ``exported_water`` and
    ``other_sources`` are the expected names.
    """
    inputs = WaterBalanceInputs(
        system_input_volume=system_input_volume,
        real_loss_components=dict(real_losses or {}),
        apparent_loss_components=dict(apparent_losses or {}),
        **supply,
    )
    return compute_water_balance(inputs)


__all__ = [
    "APPARENT_LOSS_COMPONENTS",
    "CLOSURE_TOLERANCE",
    "PROBLEM_NAME",
    "REAL_LOSS_COMPONENTS",
    "WaterBalanceInputs",
    "WaterBalanceResult",
    "compute_water_balance",
    "nrw_from_components",
    "validate_water_balance",
]