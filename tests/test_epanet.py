"""Tests for EPANET ``.inp`` parsing and structural validation.

The behaviour worth protecting is the diagnostic value: a deck that would make
EPANET fail with a numeric error should instead produce a named condition with
a row number. Every fixture here is a small, realistic deck.
"""

from __future__ import annotations

import pytest

from geoqa.validations.epanet import parse_inp, summarize_inp, validate_inp

VALID_DECK = """
[Test Network]
; a minimal but well-formed deck

[JUNCTIONS]
;ID    Elev   Demand  Pattern
 J10   710    0.0     1
 J11   710    25.0    1
 J12   700    30.0    2

[RESERVOIRS]
;ID   Head  Pattern
 R1   800

[TANKS]
;ID   Elev  InitLvl  MinLvl  MaxLvl  Diam   MinVol  VolCurve
 T1   850   850      100     1200    50     0

[PIPES]
;ID   From  To    Length  Diameter  Roughness  MinorLoss  Status
 P1   J11   J12   1000    300       100        0          Open
 P2   J12   J10   500     250       110        0          Open
 P3   R1    J11   2000    400       95         0          Open
 P4   T1    J12   800     350       105        0          Open

[PUMPS]
;ID   From  To   Parameters
 PU1  J10   J11  HEAD 30

[VALVES]
;ID  From  To  Diameter  Type  Setting
 V1  J12   J10  300       PRV   50

[PATTERNS]
;ID   Multipliers
 1    1.0 1.2 1.4
 2    1.0 0.8 0.6

[REACTIONS]
;Type     Pipe/C Tank  Global
 ORDER    1      0      0

[ENERGY]
 Global Efficiency  75
 Global Price       0
 Demand Charge       0

[OPTIONS]
 Units              SI
 Headloss           H-W
 Specific Gravity   1.0
 Viscosity          1.0
 Flow Units         LPS
"""


def _names(issues) -> list[str]:
    return [i.problem_name for i in issues]


def test_parses_a_clean_deck():
    model = parse_inp(VALID_DECK)
    assert model.section("JUNCTIONS") is not None
    assert len(model.junction_rows) == 3
    assert len(model.pipe_rows) == 4
    assert model.title.startswith("Test Network")


def test_clean_deck_produces_no_high_or_critical_issues():
    issues = validate_inp(parse_inp(VALID_DECK))
    serious = [i for i in issues if str(i.severity) in {"high", "critical"}]
    assert serious == [], [i.description for i in serious]


def test_reads_units():
    model = parse_inp(VALID_DECK)
    assert model.units["UNITS"] == "si"
    assert model.units["FLOW_UNITS"] == "lps"


def test_comments_are_stripped():
    model = parse_inp(VALID_DECK)
    lengths = [r[3].value for r in model.pipe_rows]
    assert "1000" in lengths
    assert not any(";" in v for v in lengths)


def test_column_count_matches_header():
    model = parse_inp(VALID_DECK)
    assert model.section("PIPES").column_count == 8


def test_dangling_endpoint_is_high():
    text = VALID_DECK.replace(" P2   J12   J10 ", " P2   J12   MISSING ")
    issues = validate_inp(parse_inp(text))
    dangling = [i for i in issues if i.problem_name == "epanet_dangling_endpoint"]
    assert len(dangling) == 1
    assert str(dangling[0].severity) == "high"
    assert "MISSING" in dangling[0].description


def test_dangling_endpoint_reports_the_row():
    text = VALID_DECK.replace(" P2   J12   J10 ", " P2   J12   MISSING ")
    issue = next(i for i in validate_inp(parse_inp(text)) if i.problem_name == "epanet_dangling_endpoint")
    assert issue.to_dict()["row"] > 0


def test_duplicate_id_is_flagged():
    text = VALID_DECK.replace(" J12   700    30.0    2", " J11   700    30.0    2")
    issues = validate_inp(parse_inp(text))
    assert "epanet_duplicate_id" in _names(issues)


def test_unknown_units_is_critical():
    text = VALID_DECK.replace(" Units              SI", " Units              furlongs")
    issues = validate_inp(parse_inp(text))
    unit_issue = next(i for i in issues if i.problem_name == "epanet_unknown_units")
    assert str(unit_issue.severity) == "critical"


def test_unit_mismatch_between_diameter_and_flow_is_flagged():
    text = VALID_DECK.replace(" Flow Units         LPS", " Flow Units         GPM")
    issues = validate_inp(parse_inp(text))
    assert "epanet_unit_mismatch" in _names(issues)


def test_missing_options_is_critical():
    text = VALID_DECK.split("[OPTIONS]")[0]
    issues = validate_inp(parse_inp(text))
    assert "epanet_missing_section" in _names(issues)


def test_empty_junctions_is_critical():
    text = VALID_DECK.replace("[JUNCTIONS]\n;ID    Elev   Demand  Pattern\n J10   710    0.0     1\n J11   710    25.0    1\n J12   700    30.0    2", "[JUNCTIONS]")
    issues = validate_inp(parse_inp(text))
    assert "epanet_empty_section" in _names(issues)


def test_zero_length_pipe_is_flagged():
    text = VALID_DECK.replace(" P1   J11   J12   1000", " P1   J11   J12   0")
    assert "epanet_zero_length_pipe" in _names(validate_inp(parse_inp(text)))


def test_non_numeric_length_is_high():
    text = VALID_DECK.replace(" P1   J11   J12   1000", " P1   J11   J12   abc")
    issues = validate_inp(parse_inp(text))
    nonnumeric = [i for i in issues if i.problem_name == "epanet_non_numeric_field"]
    assert nonnumeric and str(nonnumeric[0].severity) == "high"


def test_non_positive_diameter_is_flagged():
    text = VALID_DECK.replace(" P1   J11   J12   1000    300", " P1   J11   J12   1000    0")
    assert "epanet_invalid_diameter" in _names(validate_inp(parse_inp(text)))


def test_stray_section_rows_are_not_treated_as_nodes():
    """An unrecognised section must not inject phantom demand nodes."""
    text = VALID_DECK.replace(
        "[TANKS]", "[EXTRA_JUNCTIONS]\n J99  700  5.0  1\n\n[TANKS]"
    )
    model = parse_inp(text)
    assert "J99" not in model.node_ids
    issues = validate_inp(model)
    assert "epanet_disconnected_component" not in _names(issues)


def test_isolated_node_with_demand_is_an_orphan():
    text = VALID_DECK.replace(" J12   700    30.0    2", " J12   700    30.0    2\n J77   700    5.0     1")
    issues = validate_inp(parse_inp(text))
    orphan = next(i for i in issues if i.problem_name == "epanet_orphaned_node")
    assert "J77" in orphan.description
    assert str(orphan.severity) == "high"


def test_multi_node_component_without_a_source_is_reported():
    """A connected island with real demand still cannot be supplied."""
    text = VALID_DECK.replace(
        "[PATTERNS]",
        "[JUNCTIONS]\n J80  700  4.0  1\n J81  700  6.0  1\n"
        "[PIPES]\n P9  J80  J81  300  100 100 0  Open\n\n[PATTERNS]",
    )
    issues = validate_inp(parse_inp(text))
    stranded = next(i for i in issues if i.problem_name == "epanet_disconnected_component")
    assert stranded.to_dict()["sample"] == ["J80", "J81"]


def test_missing_reactions_is_informational():
    text = VALID_DECK.split("[REACTIONS]")[0] + VALID_DECK.split("[ENERGY]")[1]
    issues = validate_inp(parse_inp(text))
    missing = [i for i in issues if i.problem_name == "epanet_missing_reactions"]
    assert missing and str(missing[0].severity) == "info"


def test_non_default_reaction_order_is_flagged():
    text = VALID_DECK.replace(" ORDER    1      0      0", " ORDER    1.2    0      0")
    assert "epanet_non_default_reaction_order" in _names(validate_inp(parse_inp(text)))


def test_unknown_pattern_reference_is_flagged():
    text = VALID_DECK.replace(" J11   710    25.0    1", " J11   710    25.0    99")
    issues = validate_inp(parse_inp(text))
    assert "epanet_unknown_pattern" in _names(issues)


def test_inline_section_header_is_supported():
    text = "[JUNCTIONS] J10 710 0\n P1 J10 J11 100 100 100\n[PIPES]\n"
    model = parse_inp(text)
    assert model.section("JUNCTIONS") is not None
    assert len(model.section("JUNCTIONS").rows) == 1


def test_pumps_and_valves_count_as_connectivity():
    summary = summarize_inp(parse_inp(VALID_DECK))
    assert summary["pumps"] == 1
    assert summary["valves"] == 1


def test_summarize_reports_structure():
    summary = summarize_inp(parse_inp(VALID_DECK))
    assert summary["junctions"] == 3
    assert summary["pipes"] == 4
    assert summary["reservoirs"] == 1
    assert summary["tanks"] == 1
    assert summary["patterns"] == 2
    assert summary["units"]["UNITS"] == "si"


def test_comments_only_section_yields_no_rows():
    model = parse_inp("[JUNCTIONS]\n; only a comment\n")
    assert model.section("JUNCTIONS").rows == []


def test_empty_deck_is_safe():
    model = parse_inp("")
    assert model.sections == {}
    assert validate_inp(model) is not None


def test_node_and_link_id_sets_are_uppercased():
    model = parse_inp(VALID_DECK)
    assert "J10" in model.node_ids
    assert "P1" in model.link_ids


def test_quoted_token_with_semicolon_is_preserved():
    text = '[JUNCTIONS]\n J1 710 0 ;note\n[TAGS]\n J1 "zone;north"\n'
    model = parse_inp(text)
    tag_rows = model.section("TAGS").rows
    assert any(tok.value == "zone;north" for row in tag_rows for tok in row)


def test_validates_a_realistic_bad_deck_end_to_end():
    """Several faults at once, as a hand-edited deck accumulates them."""
    text = (
        "[JUNCTIONS]\n"
        " J1 710 10\n"
        " J1 710 20\n"
        " J2 700 30\n"
        "[PIPES]\n"
        " P1 J1 J2 0 0 100\n"
        " P2 J2 NOPE 100 100 100\n"
        "[OPTIONS]\n"
        " Units SI\n"
        " Flow Units GPM\n"
    )
    issues = validate_inp(parse_inp(text))
    names = set(_names(issues))
    assert "epanet_dangling_endpoint" in names
    assert "epanet_duplicate_id" in names
    assert "epanet_zero_length_pipe" in names
    assert "epanet_invalid_diameter" in names
    assert "epanet_unit_mismatch" in names
    assert "epanet_missing_reactions" in names