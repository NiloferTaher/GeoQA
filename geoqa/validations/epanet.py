"""EPANET ``.inp`` input-file parsing and structural validation.

Scope, deliberately
-------------------
This module writes the **parser**. It does not implement a hydraulic solver,
and it should not. EPANET and WNTR already do that, and reimplementing one
would be the single worst use of effort in this codebase.

What belongs here is everything that can be checked *before* a simulation runs
and *after* one completes:

- structural validity of the input deck
- unit consistency between sections
- internal referential integrity (links/jumps against nodes)
- topological preconditions the solver will otherwise reject opaquely
- loss accounting against the IWA water balance

A malformed deck that reaches EPANET produces a cryptic numeric failure. The
value of parsing it ourselves is turning that into a named condition with a
severity and a repair hint.

Section handling
----------------
EPANET input is section-delimited::

    [JUNCTIONS]
    ;ID  Elev  Demand  Pattern
    10   100   0.0     1

Two layouts are supported: the bracketed form above, and the older
``[TITLE]``-on-its-own-line form used by some generators. Comments begin with
``;`` and are stripped, except where a quoted title legitimately contains one.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

PROBLEM_NAME = "epanet_input"

_SECTION_RE = re.compile(r"^\s*\[([A-Za-z][A-Za-z0-9 _\-]*)\]\s*$")
_INLINE_HEADER_RE = re.compile(r"^\s*\[([A-Za-z][A-Za-z0-9 _\-]*)\]\s+(.*)$")

# Pipe diameter units as EPANET interprets them in [OPTIONS].
_KNOWN_SECTIONS = {
    "TITLE", "JUNCTIONS", "RESERVOIRS", "TANKS", "PIPES", "PUMPS", "VALVES",
    "EMITTERS", "CURVES", "PATTERNS", "ENERGY", "REACTIONS", "TIMES",
    "REPORT", "OPTIONS", "TAGS", "COORDINATES", "VERTICES", "LABELS",
    "BACKDROP", "MAP", "PROFILES", "BACKDROP-DIMENSIONS",
}

# EPANET [OPTIONS] UNITS names a unit *system* for pipe diameters. The value
# maps to metres, so a mismatch between UNITS and FLOW_UNITS can be detected.
_UNITS_TO_METRES = {
    "fps": 0.3048,    # feet
    "mgd": 0.3048,    # million gallons per day, US survey feet
    "si": 1.0,        # metres
    "lpm": 1.0,       # litres per minute, metres
}

# Direct diameter units, also accepted in place of a system.
_DIAMETER_UNITS = {"feet": 0.3048, "inches": 0.0254, "mm": 0.001, "cm": 0.01, "m": 1.0}

# EPANET [OPTIONS] FLOW_UNITS, mapped to cubic metres per second.
_FLOW_UNITS = {
    "cfs": 0.0283168466,
    "gpm": 6.30901964e-5,
    "mgd": 0.0438126364,
    "imgd": 0.0526168,
    "afd": 0.0142764,
    "lps": 0.001,
    "lpm": 0.001 / 60.0,
    "cmh": 1.0 / 3600.0,
    "cmd": 1.0 / 86400.0,
    "si": 1.0,
}

# A flow unit is metric for this check when it is litres, cubic metres, or a
# derived SI rate.
_METRIC_FLOW_UNITS = {"lps", "lpm", "cmh", "cmd", "si"}

# Demand multipliers that should be unit-consistent with FLOW_UNITS.
_NODE_CLASSES = {"JUNCTIONS", "RESERVOIRS", "TANKS", "EMITTERS"}
_LINK_CLASSES = {"PIPES", "PUMPS", "VALVES", "EMITTERS"}


@dataclass
class Token:
    """One whitespace-delimited field on one line."""

    value: str
    row: int
    column: int
    line: str


@dataclass
class Section:
    name: str
    rows: list[list[Token]] = field(default_factory=list)
    header: str = ""

    @property
    def column_count(self) -> int:
        return max((len(r) for r in self.rows), default=0)

    def values(self, index: int) -> Iterator[Token]:
        for row in self.rows:
            if len(row) > index:
                yield row[index]

    def ids(self) -> list[str]:
        return [row[0].value.upper() for row in self.rows if row]


@dataclass
class EpanetModel:
    """A parsed ``.inp`` deck, section-keyed."""

    sections: dict[str, Section] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    title: str = ""
    units: dict[str, str] = field(default_factory=dict)
    source_name: str | None = None

    def section(self, name: str) -> Section | None:
        return self.sections.get(name.upper())

    @property
    def node_ids(self) -> set[str]:
        ids: set[str] = set()
        for name in ("JUNCTIONS", "RESERVOIRS", "TANKS"):
            section = self.section(name)
            if section:
                ids.update(section.ids())
        return ids

    @property
    def link_ids(self) -> set[str]:
        ids: set[str] = set()
        for name in ("PIPES", "PUMPS", "VALVES"):
            section = self.section(name)
            if section:
                ids.update(section.ids())
        return ids

    @property
    def pipe_rows(self) -> list[list[Token]]:
        section = self.section("PIPES")
        return section.rows if section else []

    @property
    def junction_rows(self) -> list[list[Token]]:
        section = self.section("JUNCTIONS")
        return section.rows if section else []


def _strip_comment(line: str) -> str:
    """Remove a trailing ``;`` comment, honouring quoted strings."""
    in_quotes = False
    for index, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == ";" and not in_quotes:
            return line[:index]
    return line


def _tokenize(line: str, row: int) -> list[Token]:
    body = _strip_comment(line).strip()
    if not body:
        return []
    tokens: list[Token] = []
    for match in re.finditer(r'"([^"]*)"|(\S+)', body):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        tokens.append(Token(value=value, row=row, column=len(tokens), line=line.rstrip()))
    return tokens


def parse_inp(text: str | Path, *, source_name: str | None = None) -> EpanetModel:
    """Parse EPANET input text into an :class:`EpanetModel`.

    Does not validate. Use :func:`validate_inp` for that, so parsing stays cheap
    and usable on a deck that fails.
    """
    if isinstance(text, Path):
        source_name = source_name or text.name
        text = text.read_text(encoding="utf-8", errors="replace")

    model = EpanetModel(source_name=source_name)
    current: Section | None = None
    title_lines: list[str] = []
    seen_known_section = False

    for row_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n").rstrip("\r")
        stripped = line.strip()

        inline = _INLINE_HEADER_RE.match(stripped)
        if inline:
            name = inline.group(1).strip().upper()
            if name == "TITLE":
                title_lines.append(inline.group(2).strip())
                continue
            current = Section(name=name, header=inline.group(2).strip())
            model.sections[name] = current
            if name not in model.order:
                model.order.append(name)
            continue

        header = _SECTION_RE.match(stripped)
        if header:
            name = header.group(1).strip().upper()
            if name == "TITLE":
                current = None
                continue
            # Hand-edited decks sometimes carry the network name in brackets
            # at the top. Treat a bracketed line before any real section as a
            # title rather than inventing a section for it.
            if not seen_known_section and name not in _KNOWN_SECTIONS:
                title_lines.append(name.title())
                continue
            seen_known_section = True
            current = Section(name=name)
            model.sections[name] = current
            if name not in model.order:
                model.order.append(name)
            continue

        if current is None:
            # A bracketed line before any real section is a title, not a
            # section. Hand-edited decks carry the network name this way.
            # Comments are stripped so the title stays usable as a label.
            candidate = _strip_comment(stripped).strip()
            if candidate:
                title_lines.append(candidate)
            continue

        tokens = _tokenize(line, row_number)
        if tokens:
            current.rows.append(tokens)

    model.title = " ".join(title_lines).strip()

    options = model.section("OPTIONS")
    if options:
        model.units = _parse_options(options)

    return model


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def validate_inp(model: EpanetModel) -> list[Any]:
    """Structural and referential validation of a parsed deck.

    Checks in order of how badly they break a run:
    structure, referential integrity, units, topology, loss accounting.
    """
    issues: list[Any] = []

    # --- 1. structure ------------------------------------------------
    required = ["JUNCTIONS", "PIPES", "[OPTIONS]"]
    options = model.section("OPTIONS")
    if options is None:
        issues.append(
            _issue(
                "epanet_missing_section",
                "critical",
                "Deck has no [OPTIONS] section; EPANET cannot resolve units or defaults",
                {"section": "OPTIONS"},
            )
        )
    if not model.junction_rows:
        issues.append(
            _issue(
                "epanet_empty_section",
                "critical",
                "[JUNCTIONS] is absent or empty; the model has no demand nodes",
                {"section": "JUNCTIONS"},
            )
        )
    if not model.pipe_rows:
        issues.append(
            _issue(
                "epanet_empty_section",
                "critical",
                "[PIPES] is absent or empty; the model has no conveyance",
                {"section": "PIPES"},
            )
        )

    # --- 2. referential integrity ------------------------------------
    nodes = model.node_ids
    missing_nodes: list[dict[str, Any]] = []
    missing_links: list[dict[str, Any]] = []

    for row in model.pipe_rows:
        link_id = row[0].value.upper()
        for position, label in ((1, "from"), (2, "to")):
            if len(row) <= position:
                continue
            ref = row[position].value.upper()
            if ref not in nodes:
                missing_nodes.append({"link": link_id, "endpoint": label, "node": ref, "row": row[position].row})
    for row in model.junction_rows:
        if not row:
            continue
        node_id = row[0].value.upper()
        # A pattern reference appears after elevation and demand. EPANET allows
        # numeric pattern IDs, so digits are not a reason to skip the check.
        if len(row) >= 4:
            pattern = row[3].value.strip().upper()
            patterns = model.section("PATTERNS")
            if patterns and patterns.rows and pattern:
                if pattern not in {p[0].value.upper() for p in patterns.rows}:
                    missing_links.append({"node": node_id, "pattern": pattern, "row": row[3].row})

    for entry in missing_nodes:
        issues.append(
            _issue(
                "epanet_dangling_endpoint",
                "high",
                f"Pipe '{entry['link']}' references unknown {entry['endpoint']} node "
                f"'{entry['node']}' (line {entry['row']})",
                entry,
            )
        )
    for entry in missing_links:
        issues.append(
            _issue(
                "epanet_unknown_pattern",
                "medium",
                f"Node '{entry['node']}' references undefined demand pattern "
                f"'{entry['pattern']}' (line {entry['row']})",
                entry,
            )
        )

    # --- 3. duplicate identifiers -------------------------------------
    for name in ("JUNCTIONS", "PIPES", "RESERVOIRS", "TANKS", "PUMPS", "VALVES"):
        section = model.section(name)
        if section is None:
            continue
        seen: Counter[str] = Counter(row[0].value.upper() for row in section.rows if row)
        for identifier, count in seen.items():
            if count > 1:
                issues.append(
                    _issue(
                        "epanet_duplicate_id",
                        "high",
                        f"[{name}] declares '{identifier}' {count} times; EPANET will use the last",
                        {"section": name, "id": identifier, "count": count},
                    )
                )

    # --- 4. units ------------------------------------------------------
    issues.extend(_validate_units(model))

    # --- 5. topology ----------------------------------------------------
    issues.extend(_validate_topology(model))

    # --- 6. loss accounting ---------------------------------------------
    issues.extend(_validate_losses(model))

    return issues


# Multi-word [OPTIONS] keys. EPANET writes them space-separated, so a naive
# key/value split reads "Flow Units   LPS" as key "Flow", value "Units".

_OPTIONS_MULTIWORD = {
    "FLOW UNITS": "FLOW_UNITS",
    "SPECIFIC GRAVITY": "SPECIFIC_GRAVITY",
    "VISCOSITY": "VISCOSITY",
    "HYDRAULIC MODULUS": "HYDRAULIC_MODULUS",
    "RELATIVE ROUGHNESS": "RELATIVE_ROUGHNESS",
    "MAXIMUM TRIALS": "MAXIMUM_TRIALS",
    "ACCURACY": "ACCURACY",
    "UNBALANCED": "UNBALANCED",
    "DEMAND MULTIPLIER": "DEMAND_MULTIPLIER",
    "MINIMUM PRESSURE": "MINIMUM_PRESSURE",
    "REQUIRED PRESSURE": "REQUIRED_PRESSURE",
    "PRESSURE EXPONENT": "PRESSURE_EXPONENT",
    "GLOBAL EFFICIENCY": "GLOBAL_EFFICIENCY",
    "GLOBAL PRICE": "GLOBAL_PRICE",
    "DEMAND CHARGE": "DEMAND_CHARGE",
    "HEADLOSS": "HEADLOSS",
    "UNITS": "UNITS",
    "PATTERN": "PATTERN",
    "QUALITY": "QUALITY",
    "DIFFUSIVITY": "DIFFUSIVITY",
    "TOLERANCE": "TOLERANCE",
}


def _normalize_option_key(key: str) -> str:
    stripped = key.strip().upper()
    if stripped in _OPTIONS_MULTIWORD:
        return _OPTIONS_MULTIWORD[stripped]
    return stripped.replace(" ", "_")


def _parse_options(section: Section) -> dict[str, str]:
    """Read [OPTIONS], tolerating keys that span several tokens.

    EPANET writes options space-separated with no delimiter, so a key may
    occupy two or three tokens on one line::

        Specific Gravity   1.0
        Flow Units         LPS
        Demand Multiplier  1.0

    The section is therefore read as a token stream: the longest known key is
    matched greedily from the left and everything after it is the value.
    """
    stream: list[str] = []
    for row in section.rows:
        stream.extend(token.value for token in row)

    units: dict[str, str] = {}
    longest = max((len(key.split()) for key in _OPTIONS_MULTIWORD), default=1)
    longest = max(longest, 1)

    index = 0
    while index < len(stream):
        matched: str | None = None
        value_start = index
        for width in range(min(longest, len(stream) - index), 0, -1):
            candidate = " ".join(stream[index:index + width]).strip().upper()
            if candidate in _OPTIONS_MULTIWORD:
                matched = _OPTIONS_MULTIWORD[candidate]
                value_start = index + width
                break

        if matched is None:
            matched = _normalize_option_key(stream[index])
            value_start = index + 1

        remainder = stream[value_start:]
        if not remainder:
            units[matched] = ""
            index = value_start
            continue

        units[matched] = remainder[0].strip().lower()
        index = value_start + 1

    return units


def _validate_units(model: EpanetModel) -> list[Any]:
    issues: list[Any] = []
    units = model.units

    diameter_unit = units.get("UNITS")
    metres_per_unit = None
    if diameter_unit:
        metres_per_unit = _UNITS_TO_METRES.get(diameter_unit) or _DIAMETER_UNITS.get(diameter_unit)
        if metres_per_unit is None:
            issues.append(
                _issue(
                    "epanet_unknown_units",
                    "critical",
                    f"[OPTIONS] UNITS '{diameter_unit}' is not an EPANET unit system "
                    "or diameter unit",
                    {
                        "option": "UNITS",
                        "value": diameter_unit,
                        "accepted": sorted(set(_UNITS_TO_METRES) | set(_DIAMETER_UNITS)),
                    },
                )
            )
    flow_unit = units.get("FLOW_UNITS")
    if flow_unit and flow_unit not in _FLOW_UNITS:
        issues.append(
            _issue(
                "epanet_unknown_units",
                "critical",
                f"[OPTIONS] FLOW_UNITS '{flow_unit}' is not an EPANET flow unit",
                {"option": "FLOW_UNITS", "value": flow_unit, "accepted": sorted(_FLOW_UNITS)},
            )
        )
    if metres_per_unit is not None and flow_unit in _FLOW_UNITS:
        diameter_is_metric = metres_per_unit >= 0.9
        flow_is_metric = flow_unit in _METRIC_FLOW_UNITS
        if diameter_is_metric and not flow_is_metric:
            issues.append(
                _issue(
                    "epanet_unit_mismatch",
                    "medium",
                    f"Pipe diameters are metric ('{diameter_unit}') but demands are in "
                    f"'{flow_unit}'; a metric model with an imperial flow unit is "
                    "usually unintended and will silently scale results",
                    {"diameter_units": diameter_unit, "flow_units": flow_unit},
                )
            )
    return issues


def _validate_topology(model: EpanetModel) -> list[Any]:
    issues: list[Any] = []
    adjacency: dict[str, set[str]] = defaultdict(set)
    zero_length = 0

    for row in model.pipe_rows:
        if len(row) < 3:
            continue
        a, b = row[1].value.upper(), row[2].value.upper()
        adjacency[a].add(b)
        adjacency[b].add(a)

    for row in model.pipe_rows:
        link_id = row[0].value.upper()
        # [PIPES] order: ID FROM TO LENGTH DIAMETER ROUGHNESS
        if len(row) >= 4:
            try:
                if float(row[3].value) <= 0:
                    zero_length += 1
            except ValueError:
                issues.append(
                    _issue(
                        "epanet_non_numeric_field",
                        "high",
                        f"Pipe '{link_id}' has non-numeric length '{row[3].value}'",
                        {"link": link_id, "field": "LENGTH", "value": row[3].value, "row": row[0].row},
                    )
                )
        if len(row) >= 5:
            try:
                if float(row[4].value) <= 0:
                    issues.append(
                        _issue(
                            "epanet_invalid_diameter",
                            "high",
                            f"Pipe '{link_id}' has non-positive diameter '{row[4].value}'; "
                            "EPANET cannot compute headloss",
                            {"link": link_id, "value": row[4].value},
                        )
                    )
            except ValueError:
                issues.append(
                    _issue(
                        "epanet_non_numeric_field",
                        "high",
                        f"Pipe '{link_id}' has non-numeric diameter '{row[4].value}'",
                        {"link": link_id, "field": "DIAMETER", "value": row[4].value},
                    )
                )

    if zero_length:
        issues.append(
            _issue(
                "epanet_zero_length_pipe",
                "high",
                f"{zero_length} pipe(s) declare zero or negative length, which makes "
                "computed velocities meaningless",
                {"count": zero_length},
            )
        )

    groups = _disconnected_groups(model, adjacency)
    demand_nodes = set()
    for row in model.junction_rows:
        if not row:
            continue
        node_id = row[0].value.upper()
        demand = row[2].value if len(row) >= 3 else ""
        try:
            if float(demand) != 0.0:
                demand_nodes.add(node_id)
        except ValueError:
            # Non-numeric or pattern-driven demand counts as real demand.
            demand_nodes.add(node_id)

    source_nodes: set[str] = set()
    for name in ("RESERVOIRS", "TANKS"):
        section = model.section(name)
        if section:
            source_nodes.update(section.ids())

    multi = [g for g in groups if len(g) > 1]
    unconnected = [g for g in groups if len(g) == 1]

    # A component is stranded only when it holds demand and no source. The
    # main component containing every source is correctly supplied.
    for group in multi:
        if group & source_nodes:
            continue
        stranded = sorted(group & demand_nodes)
        if not stranded:
            continue
        issues.append(
            _issue(
                "epanet_disconnected_component",
                "medium",
                f"{len(stranded)} demand node(s) form a component with no path to any "
                "reservoir or tank; these demands cannot be supplied",
                {"size": len(stranded), "sample": stranded[:12]},
            )
        )

    for group in unconnected:
        node_id = next(iter(group))
        if node_id not in demand_nodes:
            continue
        issues.append(
            _issue(
                "epanet_orphaned_node",
                "high",
                f"Node '{node_id}' carries demand but has no pipe, pump or valve "
                "connecting it to the network",
                {"node": node_id},
            )
        )
    return issues


def _disconnected_groups(model: EpanetModel, adjacency: dict[str, set[str]]) -> list[set[str]]:
    nodes = model.node_ids
    if not nodes:
        return []
    neighbours: dict[str, set[str]] = {node: set(adjacency.get(node, ())) for node in nodes}

    for name in ("PUMPS", "VALVES"):
        section = model.section(name)
        if section is None:
            continue
        for row in section.rows:
            if len(row) >= 3:
                a, b = row[1].value.upper(), row[2].value.upper()
                neighbours.setdefault(a, set()).add(b)
                neighbours.setdefault(b, set()).add(a)

    unseen = set(nodes)
    groups: list[set[str]] = []
    while unseen:
        seed = min(unseen)
        stack = [seed]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            unseen.discard(current)
            stack.extend(neighbours.get(current, set()) - component)
        groups.append(component)
    return groups


def _validate_losses(model: EpanetModel) -> list[Any]:
    """Check [REACTIONS] consistency before a run.

    This does not compute a water balance. It checks the inputs such a balance
    would need, and flags the configuration error that most often makes one
    impossible to interpret: a reaction setting left at a value that silently
    dominates results.
    """
    issues: list[Any] = []
    reactions = model.section("REACTIONS")
    if reactions is None:
        issues.append(
            _issue(
                "epanet_missing_reactions",
                "info",
                "[REACTIONS] is absent, so global order and wall reaction are both zero; "
                "any computed loss figure will exclude reaction losses",
                {"section": "REACTIONS"},
            )
        )
        return issues

    order = None
    for row in reactions.rows:
        if row and row[0].value.upper() == "ORDER" and len(row) >= 2:
            try:
                order = float(row[1].value)
            except ValueError:
                issues.append(
                    _issue(
                        "epanet_non_numeric_field",
                        "medium",
                        f"[REACTIONS] ORDER '{row[1].value}' is not numeric",
                        {"field": "ORDER", "value": row[1].value},
                    )
                )
    if order is not None and order > 1.0:
        issues.append(
            _issue(
                "epanet_non_default_reaction_order",
                "medium",
                f"Global reaction order is {order}; above 1.0 mass transfer becomes "
                "nonlinear and a simple leakage split is no longer defensible",
                {"order": order},
            )
        )
    return issues


def _storage_count(model: EpanetModel) -> int:
    total = 0
    for name in ("RESERVOIRS", "TANKS"):
        section = model.section(name)
        if section:
            total += len(section.rows)
    return total


def summarize_inp(model: EpanetModel) -> dict[str, Any]:
    """Counts and unit context, for a manifest or report header."""
    def count(name: str) -> int:
        section = model.section(name)
        return len(section.rows) if section else 0

    return {
        "source_name": model.source_name,
        "title": model.title,
        "sections": len(model.sections),
        "junctions": len(model.junction_rows),
        "pipes": len(model.pipe_rows),
        "reservoirs": count("RESERVOIRS"),
        "tanks": count("TANKS"),
        "pumps": count("PUMPS"),
        "valves": count("VALVES"),
        "patterns": count("PATTERNS"),
        "curves": count("CURVES"),
        "energy": count("ENERGY"),
        "reactions": count("REACTIONS"),
        "storage_nodes": _storage_count(model),
        "units": dict(model.units),
    }


__all__ = [
    "PROBLEM_NAME",
    "EpanetModel",
    "Section",
    "Token",
    "parse_inp",
    "summarize_inp",
    "validate_inp",
]
