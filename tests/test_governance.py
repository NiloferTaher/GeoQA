"""Tests for governance metadata.

The behaviour worth protecting: a missing licence is reported as a distinct,
serious condition rather than folded into "metadata incomplete", because the two
have different consequences and different remedies.
"""

from __future__ import annotations

from datetime import date

import pytest

from geoqa.validations.governance import (
    ACCOUNTABILITY_ELEMENTS,
    INSPIRE_ELEMENTS,
    RIGHTS_ELEMENTS,
    governance_report,
    licence_looks_open,
    parse_metadata_date,
    validate_governance_metadata,
)


COMPLETE = {
    "title": "Distribution network boundaries",
    "abstract": "Service area boundaries for the distribution network.",
    "resource_type": "dataset",
    "unique_identifier": "urn:example:boundaries:2026",
    "topic_category": ["boundaries"],
    "keyword": ["network", "boundaries"],
    "geographic_extent": "52.0,16.0,60.0,26.5",
    "temporal_reference": "2026-09-30",
    "lineage": "Digitised from survey; reconciled against field records 2026-09.",
    "conformity": "Validated against the internal QA profile 2026.03.",
    "conditions_for_access_and_use": "Licensed under CC BY 4.0.",
    "limitations_on_public_access": "None. Open for reuse.",
    "responsible_organisation": "Example utility, GIS unit",
    "metadata_point_of_contact": "gis@example.org",
    "metadata_date": date(2026, 9, 30),
    "metadata_language": "en",
}


def _names(issues):
    return [i.problem_name for i in issues]


def _without(key):
    metadata = dict(COMPLETE)
    metadata.pop(key, None)
    return metadata


# --- the element that matters ---------------------------------------------

def test_missing_licence_is_its_own_condition():
    """A dataset with no recorded terms cannot lawfully be reused."""
    issues = validate_governance_metadata(_without("conditions_for_access_and_use"))
    assert "governance_licence_not_declared" in _names(issues)


def test_missing_licence_is_high():
    issue = next(
        i for i in validate_governance_metadata(_without("conditions_for_access_and_use"))
        if i.problem_name == "governance_licence_not_declared"
    )
    assert str(issue.severity) == "high"
    assert "1205/2008" in issue.description or "INSPIRE" in issue.description


def test_missing_access_limitation_is_also_a_rights_gap():
    issues = validate_governance_metadata(_without("limitations_on_public_access"))
    assert "governance_licence_not_declared" in _names(issues)


def test_restricted_licence_is_not_reported_by_default():
    """A restricted licence is a legitimate choice, not a defect."""
    metadata = dict(COMPLETE, conditions_for_access_and_use="Internal use only.")
    assert "governance_licence_not_open" not in _names(validate_governance_metadata(metadata))


def test_restricted_licence_is_raised_when_openness_is_required():
    metadata = dict(COMPLETE, conditions_for_access_and_use="Internal use only.")
    issues = validate_governance_metadata(metadata, require_open_licence=True)
    issue = next(i for i in issues if i.problem_name == "governance_licence_not_open")
    assert str(issue.severity) == "medium"
    assert "2019/1024" in issue.description


# --- accountability ---------------------------------------------------------

def test_missing_responsible_organisation_is_high():
    issues = validate_governance_metadata(_without("responsible_organisation"))
    issue = next(i for i in issues if i.problem_name == "governance_accountability_unassigned")
    assert str(issue.severity) == "high"


def test_missing_contact_is_high():
    assert "governance_accountability_unassigned" in _names(
        validate_governance_metadata(_without("metadata_point_of_contact"))
    )


def test_accountability_elements_are_identified():
    assert set(ACCOUNTABILITY_ELEMENTS) == {"responsible_organisation", "metadata_point_of_contact"}


# --- lineage, conformity, identity -----------------------------------------

def test_missing_lineage_is_high():
    """Without processing history, a declared accuracy cannot be interpreted."""
    issues = validate_governance_metadata(_without("lineage"))
    issue = next(i for i in issues if i.problem_name == "governance_lineage_undeclared")
    assert str(issue.severity) == "high"


def test_missing_conformity_is_medium():
    issues = validate_governance_metadata(_without("conformity"))
    issue = next(i for i in issues if i.problem_name == "governance_conformity_undeclared")
    assert str(issue.severity) == "medium"


def test_missing_unique_identifier_is_medium():
    assert "governance_unique_identifier_missing" in _names(
        validate_governance_metadata(_without("unique_identifier"))
    )


def test_missing_temporal_reference_is_medium():
    assert "governance_temporal_reference_missing" in _names(
        validate_governance_metadata(_without("temporal_reference"))
    )


def test_ordinary_missing_element_is_medium():
    assert "governance_metadata_element_missing" in _names(
        validate_governance_metadata(_without("topic_category"))
    )


# --- placeholders -------------------------------------------------------------

def test_placeholder_is_not_a_value():
    issues = validate_governance_metadata(dict(COMPLETE, abstract="TBD"))
    assert "governance_metadata_element_placeholder" in _names(issues)


def test_absent_and_placeholder_are_different_findings():
    """A blank field and a field reading TBD need different remedies."""
    absent = _names(validate_governance_metadata(_without("abstract")))
    placeholder = _names(validate_governance_metadata(dict(COMPLETE, abstract="TBD")))
    assert "governance_metadata_element_missing" in absent
    assert "governance_metadata_element_placeholder" not in absent
    assert "governance_metadata_element_placeholder" in placeholder
    assert "governance_metadata_element_missing" not in placeholder


def test_tbd_licence_counts_as_missing():
    metadata = dict(COMPLETE, conditions_for_access_and_use="TBD")
    assert "governance_licence_not_declared" in _names(validate_governance_metadata(metadata))


# --- currency -------------------------------------------------------------------

def test_stale_metadata_is_reported():
    issues = validate_governance_metadata(dict(COMPLETE, metadata_date=date(2015, 1, 1)))
    issue = next(i for i in issues if i.problem_name == "governance_metadata_stale")
    assert issue.to_dict()["age_days"] > 700


def test_recent_metadata_is_not_stale():
    issues = validate_governance_metadata(
        dict(COMPLETE, metadata_date=date(2026, 9, 30)), today=date(2026, 10, 1)
    )
    assert "governance_metadata_stale" not in _names(issues)


def test_staleness_can_be_switched_off():
    metadata = dict(COMPLETE, metadata_date=date(2015, 1, 1))
    assert "governance_metadata_stale" not in _names(
        validate_governance_metadata(metadata, stale_after_days=None)
    )


# --- dates -------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    ["2026-09-30", "2026/09/30", "30/09/2026", "2026-09-30T12:00:00", date(2026, 9, 30)],
)
def test_metadata_date_formats(value):
    assert parse_metadata_date(value) == date(2026, 9, 30)


def test_unparseable_date_is_none():
    assert parse_metadata_date("sometime last year") is None


# --- licence detection -----------------------------------------------------------

def test_open_licences_are_detected():
    for text in ("CC0 1.0", "CC BY 4.0", "Open Data Commons ODbL", "Apache 2.0", "Public domain"):
        assert licence_looks_open(text) is True, text


def test_restricted_licences_are_not_open():
    for text in ("Internal use only", "All rights reserved", "Named users only"):
        assert licence_looks_open(text) is False, text


def test_empty_is_not_open():
    assert licence_looks_open(None) is False
    assert licence_looks_open("") is False


# --- completeness ----------------------------------------------------------------

def test_complete_metadata_is_clean():
    issues = validate_governance_metadata(COMPLETE, today=date(2026, 10, 1))
    assert [i for i in issues if str(i.severity) in {"critical", "high"}] == []


def test_report_states_publishability():
    report = governance_report(_without("conditions_for_access_and_use"))
    assert report["licence_recorded"] is False
    assert report["publishable"] is False


def test_report_on_complete_metadata():
    report = governance_report(COMPLETE)
    assert report["publishable"] is True
    assert report["missing"] == []
    assert report["licence_appears_open"] is True


def test_required_elements_can_be_narrowed():
    issues = validate_governance_metadata(
        _without("lineage"), required_elements=["title", "lineage"]
    )
    assert _names(issues) == ["governance_lineage_undeclared"]


def test_empty_metadata_reports_everything():
    issues = validate_governance_metadata({})
    assert len(issues) == len(INSPIRE_ELEMENTS)


def test_metadata_is_required():
    with pytest.raises(ValueError, match="metadata is required"):
        validate_governance_metadata(None)


def test_nested_metadata_is_read():
    """INSPIRE records nest identification under a container."""
    metadata = dict(COMPLETE)
    metadata["metadata"] = {"title": "A title from a nested container"}
    assert "governance_metadata_element_missing" not in _names(
        validate_governance_metadata(metadata)
    )


def test_keys_are_matched_case_insensitively():
    metadata = {"Title": "Case varied", "Conditions_For_Access_And_Use": "CC BY 4.0"}
    issues = validate_governance_metadata(metadata)
    # The other rights element is genuinely absent, so only check the one we set.
    assert not any(
        i.to_dict().get("element") == "conditions_for_access_and_use" for i in issues
    )


def test_rights_elements_are_the_licence_pair():
    assert set(RIGHTS_ELEMENTS) == {
        "conditions_for_access_and_use", "limitations_on_public_access"
    }