"""Tests for undeclared constants in metric chains.

The behaviour that matters: a real KPI listing containing 3.31, 1.52, 0.3 and
6.5 must report exactly those four and nothing else. Unit conversions and
structural literals must stay silent, or the signal is unusable.
"""

from __future__ import annotations

import pytest

from geoqa.validations.metric_constants import (
    ConstantDeclaration,
    audit_constants,
    audit_table,
    parse_metric_expressions,
    validate_metric_constants,
)

EWA_SOURCE = """
Total Investigated Length
sum("ewa_hps"."investigated_pipe_len")/1000

Leak per KM
"ewa_card_kpis"."Total Leaks"/"ewa_hps"."Total Investigated Length"

Unreportable Main Line Water Volume
sum("ewa_card_kpis"."unreportable_main")*(3.31*24*180)/1000000

Unreportable Main Line Water Savings
"ewa_card_kpis"."Unreportable Main Line Water Volume"*0.3*1000000

Unreportable Service Line Water Volume
sum("ewa_card_kpis"."unreportable_service")*(1.52*24*180)/1000000

Crewdays
sum("ewa_crewmath"."owner_hours")/6.5
"""


def _declared() -> list[ConstantDeclaration]:
    return [
        ConstantDeclaration("3.31", "night flow rate, main line", "L/day", "fitted from vendor outputs"),
        ConstantDeclaration("1.52", "night flow rate, service line", "L/day", "fitted from vendor outputs"),
        ConstantDeclaration("0.3", "share of unrecovered volume counted as saving", "ratio", None),
        ConstantDeclaration("6.5", "paid hours per crewday", "hours", None),
    ]


def test_parses_name_expression_pairs():
    audits = parse_metric_expressions("Leak per KM = TotalLeaks / Length")
    assert len(audits) == 1
    assert audits[0].name == "Leak per KM"


def test_real_listing_yields_four_undeclared_constants():
    audits = audit_constants(EWA_SOURCE)
    undeclared = sorted({c for a in audits for c in a.undeclared})
    assert undeclared == ["0.3", "1.52", "3.31", "6.5"]


def test_unit_conversions_are_not_flagged():
    audits = audit_constants(EWA_SOURCE)
    for audit in audits:
        assert "24" not in audit.undeclared
        assert "180" not in audit.undeclared
        assert "1000000" not in audit.undeclared
        assert "1000" not in audit.undeclared


def test_declaring_constants_clears_the_findings():
    audits = audit_constants(EWA_SOURCE, _declared())
    assert all(a.is_declared_fully for a in audits)


def test_mapping_form_of_declarations_also_works():
    mapping = {d.constant: d for d in _declared()}
    audits = audit_constants(EWA_SOURCE, mapping)
    assert all(a.is_declared_fully for a in audits)


def test_thousands_separators_do_not_silently_collide():
    audits = audit_constants("Big = count * 3310", {"3310": ConstantDeclaration("3310", "x")})
    assert audits[0].is_declared_fully


def test_validate_reports_one_issue_per_undeclared_constant():
    issues = validate_metric_constants(source=EWA_SOURCE)
    assert len(issues) == 4
    assert {i.problem_name for i in issues} == {"unlabelled_physical_constant"}
    assert all(str(i.severity) == "medium" for i in issues)


def test_issue_records_metric_and_expression():
    issues = validate_metric_constants(source=EWA_SOURCE)
    issue = next(i for i in issues if "3.31" in i.description)
    payload = issue.to_dict()
    assert payload["metric"] == "Unreportable Main Line Water Volume"
    assert payload["constant"] == "3.31"
    assert "3.31" in payload["expression"]


def test_scope_boundary_is_flagged_by_default():
    issues = validate_metric_constants(source="Report = rows WHERE date >= 2025-06-01")
    names = {i.problem_name for i in issues}
    assert "hardcoded_scope_boundary" in names


def test_scope_boundary_can_be_excluded():
    issues = validate_metric_constants(
        source="Report = rows WHERE date >= 2025-06-01", skip_scope_boundaries=True
    )
    assert issues == []


def test_scope_boundary_asks_the_actual_question():
    issues = validate_metric_constants(source="Report = rows WHERE date >= 2025-06-01")
    issue = next(i for i in issues if i.problem_name == "hardcoded_scope_boundary")
    assert "client requirement" in issue.to_dict()["question"]


def test_declaration_metadata_is_retained():
    audits = audit_constants(EWA_SOURCE, _declared())
    matched = [d for a in audits for d in a.declared if d.constant == "3.31"][0]
    assert matched.unit == "L/day"
    assert matched.source == "fitted from vendor outputs"
    assert matched.verified is False


def test_verified_flag_round_trips():
    d = ConstantDeclaration("3.31", "x", "L/day", "src", verified=True)
    assert d.as_dict()["verified"] is True


def test_comments_and_blank_lines_are_ignored():
    audits = audit_constants("# note: uses 3.31\n\n  \nReal = count * 2")
    assert [a.name for a in audits] == ["Real"]


def test_structural_literals_stay_silent():
    audits = audit_constants("Ratio = volume * 1 / 1000")
    assert audits[0].undeclared == ()


def test_audit_table_reads_literal_formula_cells():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"formula": ["Volume = count * 3.31 * 24 * 180", "Save = Volume * 0.3"]})
    audits = audit_table(frame)
    undeclared = sorted({c for a in audits for c in a.undeclared})
    assert undeclared == ["0.3", "3.31"]


def test_audit_table_honours_column_restriction():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame({"formula": ["Volume = count * 3.31"], "note": ["Volume = count * 9.99"]})
    audits = audit_table(frame, metric_columns=["formula"])
    assert sorted({c for a in audits for c in a.undeclared}) == ["3.31"]


def test_empty_source_is_safe():
    assert validate_metric_constants(source="") == []
    assert audit_constants("") == []


def test_no_source_returns_no_issues():
    assert validate_metric_constants() == []


def test_name_with_slash_does_not_confuse_the_parser():
    """Metric names in the real file contain slashes and spaces."""
    audits = parse_metric_expressions('Leak per KM/x = "a"/"b"')
    assert audits[0].name == "Leak per KM/x"
    assert audits[0].expression == '"a"/"b"'