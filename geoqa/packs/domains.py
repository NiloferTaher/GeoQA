"""Domain packs: which conditions apply to which kind of data.

Why packs and not more validators
---------------------------------
A library that hard-codes flood checks is a flood library. GeoQA keeps the
generic conditions in ``validations/`` and puts domain knowledge here, where it
is opt-in, named, and replaceable by whoever owns the domain.

Each pack is a declaration, not a reimplementation. It says which existing
validator to run, which declared reference is required, and which conditions
should halt a run. Nothing in a pack duplicates arithmetic that lives elsewhere.

The domains
-----------
``coastal`` / ``flood``
    Elevation against a named tidal reference. The datum question dominates.
``mangrove``
    The same datum question, plus canopy height that is measured from the
    ground and not from sea level.
``seismic``
    Ground motion with units and a site class. PGA in g and in m/s2 differ by a
    factor of about 9.8, which is a plausible-looking wrong number.
``wildfire``
    Fuel model version and perimeter snapshot date, neither of which is ever in
    the layer.
``power``
    Voltage level and phase, which are not inferable from geometry.
``mining`` / ``oil``
    Horizontal datum, where legacy data is frequently on a different one from
    the surrounding country.

None of these packs assert a threshold of their own. Where a domain genuinely
has a standard limit, it is declared in the pack rather than hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ..hitl import Gate, GateSpec, PROCEED_WITH_WARNINGS, any_of, at_least, count_at_least


@dataclass(frozen=True)
class Pack:
    """A named set of requirements for one kind of data."""

    name: str
    #: One-line statement of what this pack is for.
    summary: str
    #: Runtime dataset types this pack expects to run.
    dataset_types: tuple[str, ...] = ()
    #: Conditions whose absence should stop a run.
    required_conditions: tuple[str, ...] = ()
    #: Conditions worth reporting but not worth stopping for.
    advisory_conditions: tuple[str, ...] = ()
    #: Context keys the pack wants passed to the validators.
    context_keys: tuple[str, ...] = ()
    #: Anything a caller must decide, stated rather than assumed.
    declarations_required: tuple[str, ...] = ()
    notes: str = ""

    def gate(self) -> Gate:
        """A governance gate for this pack.

        Built from the declared conditions, so the gate and the documentation
        cannot drift apart: they come from the same fields.
        """
        return Gate(
            name=f"{self.name}_pack",
            gates=[
                GateSpec(
                    name=f"{self.name}_required",
                    requirement=f"{self.summary}; required: {', '.join(self.required_conditions)}",
                    predicate=any_of(*self.required_conditions) if self.required_conditions else (lambda issues: []),
                ),
                GateSpec(
                    name=f"{self.name}_critical",
                    requirement="no critical finding in this domain",
                    predicate=at_least("critical"),
                ),
                GateSpec(
                    name=f"{self.name}_advisory_repeats",
                    requirement="a repeated advisory condition is a pattern worth reviewing",
                    predicate=count_at_least(3),
                    outcome=PROCEED_WITH_WARNINGS,
                ),
            ],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "dataset_types": list(self.dataset_types),
            "required_conditions": list(self.required_conditions),
            "advisory_conditions": list(self.advisory_conditions),
            "context_keys": list(self.context_keys),
            "declarations_required": list(self.declarations_required),
            "notes": self.notes,
        }


#: Conditions that mean "you do not know what these numbers mean yet".
_UNINTERPRETABLE = (
    "vertical_reference_undeclared",
    "vertical_reference_ambiguous",
    "vertical_crs_undeclared",
    "horizontal_axis_order_undeclared",
    "coordinate_axis_order_undeclared",
)

COASTAL = Pack(
    name="coastal",
    summary="Coastal and tidal data, where a level is meaningless without its reference surface",
    dataset_types=("crs", "crs_units", "geometry", "topology"),
    required_conditions=("vertical_reference_undeclared", "vertical_reference_ambiguous"),
    advisory_conditions=("vertical_unit_ambiguous", "vertical_range_implausible"),
    context_keys=("declared_reference", "expected_range", "expected_unit"),
    declarations_required=(
        "the vertical reference surface (MSL, MHHW, LAT, chart datum, geoid)",
        "the vertical unit",
        "the epoch the tidal reference was computed for",
    ),
    notes=(
        "Mean sea level, mean higher high water and lowest astronomical tide are different "
        "surfaces, locally by more than a metre. Nothing in a typical coastal layer says which "
        "one applies, and a consumer will assume."
    ),
)

FLOOD = Pack(
    name="flood",
    summary="Flood extent and depth, which are datum-critical and return-period-dependent",
    dataset_types=("crs", "crs_units", "geometry"),
    required_conditions=("vertical_reference_undeclared",),
    advisory_conditions=("vertical_unit_ambiguous", "vertical_range_implausible"),
    context_keys=("declared_reference", "expected_range", "declared_crs"),
    declarations_required=(
        "the vertical datum the depths are measured from",
        "the return period the extent represents, for example 1-in-100-year",
        "the climate scenario, where a projection rather than a historic event",
    ),
    notes=(
        "A flood extent with no return period is not a hazard statement. Two extents for the "
        "same location can differ by an order of magnitude purely because of the return period, "
        "and neither file records it."
    ),
)

MANGROVE = Pack(
    name="mangrove",
    summary="Mangrove extent and condition, where zonation depends entirely on the tidal reference",
    dataset_types=("crs", "crs_units", "geometry", "raster", "hyperspectral"),
    required_conditions=("vertical_reference_undeclared",),
    advisory_conditions=("vertical_unit_ambiguous", "vertical_range_implausible"),
    context_keys=("declared_reference", "expected_range"),
    declarations_required=(
        "the tidal datum used for canopy height or inundation",
        "whether height is measured from the ground or from sea level",
        "the survey date, where phenology affects canopy cover",
    ),
    notes=(
        "Mangrove zonation is conventionally expressed relative to mean higher high water. "
        "Canopy height measured from the ground and from sea level are different quantities "
        "that are routinely confused, and the confusion moves features between zones."
    ),
)

SEISMIC = Pack(
    name="seismic",
    summary="Seismic hazard and ground motion, where units and site class are never in the layer",
    dataset_types=("crs", "crs_units", "geometry", "raster"),
    required_conditions=("horizontal_axis_order_undeclared",),
    advisory_conditions=("coordinate_axis_order_swapped", "vertical_range_implausible"),
    context_keys=("declared_crs", "expected_extent"),
    declarations_required=(
        "whether ground motion is in g, m/s2 or Gal",
        "the site class or Vs30 the values assume",
        "whether the layer is hazard (probability of exceedance) or risk",
    ),
    notes=(
        "Peak ground acceleration is quoted in g, m/s2 and Gal. The values differ by a factor "
        "of about 9.8, so a unit error is plausible-looking and materially wrong. Separately, "
        "a hazard layer and a risk layer answer different questions and are routinely swapped."
    ),
)

WILDFIRE = Pack(
    name="wildfire",
    summary="Wildfire perimeter and fuel data, which are snapshots of a moving process",
    dataset_types=("crs", "crs_units", "geometry", "topology", "raster"),
    required_conditions=("missing_metadata_completeness_report",),
    advisory_conditions=("temporal_reference_missing", "governance_metadata_stale"),
    context_keys=("declared_crs", "expected_periods"),
    declarations_required=(
        "the date the perimeter was produced",
        "the fuel model and its version",
        "the source of the perimeter, since automated detection and manual mapping differ",
    ),
    notes=(
        "A wildfire perimeter is a snapshot, not a property. Without the date it is a polygon "
        "with no meaning, and perimeters from different sources for the same fire do not "
        "agree."
    ),
)

POWER = Pack(
    name="power",
    summary="Electricity network assets, where voltage level and topology carry the meaning",
    dataset_types=("topology", "geometry", "crs", "epanet"),
    required_conditions=("isolated_network_segment",),
    advisory_conditions=("unsnapped_endpoints_within_tolerance", "line_dangle"),
    context_keys=("expected_crs", "role_field", "domain_field"),
    declarations_required=(
        "the nominal voltage level of each asset",
        "whether the network model is radial, looped or meshed",
        "the phase conductor count, where three-phase assets are represented",
    ),
    notes=(
        "A network segment with no declared voltage cannot be checked for a plausible rating, "
        "and a radial network containing a loop is usually a topology error rather than a design "
        "choice. Neither is inferable from geometry."
    ),
)

MINING = Pack(
    name="mining",
    summary="Mining and petroleum leases and infrastructure, where the horizontal datum varies by vintage",
    dataset_types=("crs", "crs_units", "geometry", "boundary_conformance"),
    required_conditions=("missing_spatial_reference",),
    advisory_conditions=("length_unit_inconsistent_with_crs", "web_mercator_area_unusable"),
    context_keys=("declared_crs", "expected_extent"),
    declarations_required=(
        "the horizontal datum, which for legacy mineral data is often not the modern one",
        "the coordinate epoch where a dynamic datum is used",
        "the licence or permit boundary authority",
    ),
    notes=(
        "Mineral and petroleum datasets are frequently digitised on a national or historical "
        "datum rather than WGS 84, and a few hundred metres of offset is invisible on a map "
        "but decisive for a boundary determination."
    ),
)

OIL = Pack(
    name="oil",
    summary="Petroleum infrastructure and licensing, sharing the mineral datum problem",
    dataset_types=("crs", "crs_units", "geometry", "boundary_conformance"),
    required_conditions=("missing_spatial_reference",),
    advisory_conditions=("length_unit_inconsistent_with_crs",),
    context_keys=("declared_crs", "expected_extent"),
    declarations_required=(
        "the horizontal datum for any legacy well record",
        "the licence boundary authority and vintage",
    ),
    notes="Same datum exposure as mining, with well records going back far enough to predate modern datums.",
)

PUBLIC_REFERENCE = Pack(
    name="public_reference",
    summary="Crowd-sourced and open reference data such as OSM, where the licence and completeness are the real risks",
    dataset_types=("geometry", "topology", "osm", "governance"),
    required_conditions=("osm_attribution_absent",),
    advisory_conditions=("osm_version_metadata_absent", "osm_unclosed_area"),
    context_keys=("key_column", "geometry_column"),
    declarations_required=(
        "the licence of the source data",
        "the extract date, since the data is edited continuously",
        "the spatial extent actually covered",
    ),
    notes=(
        "Two risks are invisible to structural validation: the licence obligation, which is a "
        "legal matter rather than a data matter, and completeness, which the source does not "
        "measure at all."
    ),
)

ALL_PACKS: tuple[Pack, ...] = (
    COASTAL, FLOOD, MANGROVE, SEISMIC, WILDFIRE, POWER, MINING, OIL, PUBLIC_REFERENCE,
)

PACKS_BY_NAME: dict[str, Pack] = {pack.name: pack for pack in ALL_PACKS}


def list_packs() -> list[str]:
    return sorted(PACKS_BY_NAME)


def get_pack(name: str) -> Pack:
    """Fetch a pack by name."""
    key = str(name).strip().lower()
    if key not in PACKS_BY_NAME:
        raise KeyError(
            f"unknown pack {name!r}; available: {', '.join(list_packs())}"
        )
    return PACKS_BY_NAME[key]


def pack_gate(name: str) -> Gate:
    """The governance gate for a named pack."""
    return get_pack(name).gate()


def pack_report() -> list[dict[str, Any]]:
    """Every pack, for the capability workbook and for documentation."""
    return [pack.as_dict() for pack in ALL_PACKS]


__all__ = [
    "ALL_PACKS",
    "COASTAL",
    "FLOOD",
    "MANGROVE",
    "MINING",
    "OIL",
    "PACKS_BY_NAME",
    "POWER",
    "PUBLIC_REFERENCE",
    "SEISMIC",
    "WILDFIRE",
    "Pack",
    "get_pack",
    "list_packs",
    "pack_gate",
    "pack_report",
]