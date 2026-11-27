"""Tests for the AI disclosure guard.

The behaviour worth protecting: the guard refuses on a blocked term rather than
quietly passing, and a clean payload is reported as clean. A guard that always
says "redacted" is as useless as no guard at all.
"""

from __future__ import annotations

import pandas as pd
import pytest

from geoqa.ai_guard import (
    AiSubmissionGuard,
    RedactionPolicy,
    redact_frame,
    redact_issues,
    redact_mapping,
    redact_text,
    validate_ai_disclosure,
)
from geoqa.validations.base import build_issue


def _names(issues):
    return [i.problem_name for i in issues]


POLICY = RedactionPolicy(blocked_terms=frozenset({"acme water", "project falcon"}), strict=True)


# --- credentials ----------------------------------------------------------

def test_credential_is_redacted_from_text():
    result = redact_text('token = "ghp_' + "a" * 36 + '"')
    assert "ghp_" not in result.payload
    assert result.redacted_count == 1


def test_credential_in_payload_is_critical():
    issues = validate_ai_disclosure('key: "AKIAIOSFODNN7EXAMPLE"')
    assert "ai_disclosure_credential" in _names(issues)


# --- blocked terms -------------------------------------------------------

def test_blocked_term_is_replaced():
    result = redact_text("Built for Acme Water in 2024", POLICY)
    assert "Acme" not in result.payload
    assert "[REDACTED:term]" in result.payload


def test_blocked_term_blocks_under_strict_policy():
    result = redact_text("Acme Water data", POLICY)
    assert result.blocked is True


def test_guard_refuses_a_blocked_payload():
    with AiSubmissionGuard(POLICY) as guard:
        with pytest.raises(PermissionError, match="refused"):
            guard("Acme Water network")


def test_guard_allows_a_clean_payload():
    with AiSubmissionGuard(POLICY) as guard:
        payload = guard("A network with 12 boundary polygons.")
    assert "12" in payload
    assert guard.safe is True


def test_non_strict_policy_redacts_without_blocking():
    lenient = RedactionPolicy(blocked_terms=frozenset({"acme"}), strict=False)
    result = redact_text("Acme Water", lenient)
    assert result.blocked is False
    assert "Acme" not in result.payload


def test_partial_word_is_not_blocked():
    """'acme' must not match inside 'academic'."""
    result = redact_text("academic research", POLICY)
    assert result.clean is True


def test_guard_does_not_mutate_the_original():
    lenient = RedactionPolicy(blocked_terms=frozenset({"acme water"}), strict=False)
    original = {"note": "Acme Water"}
    with AiSubmissionGuard(lenient) as guard:
        guard(original)
    assert original["note"] == "Acme Water"


# --- sensitive columns ----------------------------------------------------

def test_sensitive_column_is_redacted():
    result = redact_mapping({"national_id": "123456789", "region": "north"})
    assert result.payload["national_id"] == "[REDACTED:sensitive]"
    assert result.payload["region"] == "north"


def test_sensitive_column_name_matching_is_flexible():
    result = redact_mapping({"Customer Email Address": "a@b.com"})
    assert result.payload["Customer Email Address"] == "[REDACTED:sensitive]"


def test_dropped_column_is_removed_entirely():
    """A redacted column still reveals the entity had one."""
    policy = RedactionPolicy(drop_columns=frozenset({"salary"}))
    result = redact_mapping({"salary": 50000, "region": "north"}, policy)
    assert "salary" not in result.payload
    assert any(f.action == "dropped" for f in result.findings)


def test_sensitive_column_in_payload_is_high():
    issues = validate_ai_disclosure({"national_id": "123", "region": "n"})
    assert "ai_disclosure_sensitive_column" in _names(issues)


# --- personal data --------------------------------------------------------

def test_email_is_redacted():
    result = redact_text("Contact alice@example.com for access")
    assert "alice@example.com" not in result.payload


def test_iban_is_redacted():
    result = redact_text("Account GB82WEST12345698765432")
    assert "GB82WEST" not in result.payload


def test_personal_data_in_payload_is_reported():
    issues = validate_ai_disclosure("Reach alice@example.com")
    assert "ai_disclosure_personal_data" in _names(issues)


def test_personal_data_redaction_can_be_disabled():
    policy = RedactionPolicy(redact_personal_data=False)
    result = redact_text("alice@example.com", policy)
    assert "alice@example.com" in result.payload


# --- filesystem paths ------------------------------------------------------

def test_windows_path_is_redacted():
    result = redact_text("Saved to C:\\Users\\admin\\Projects\\secret\\data.gpkg")
    assert "admin" not in result.payload
    assert "[REDACTED:path]" in result.payload


def test_path_in_payload_is_low():
    issues = validate_ai_disclosure("See C:\\Users\\admin\\data\\roads.gpkg")
    assert _names(issues) == ["ai_disclosure_filesystem_path"]


# --- frames ------------------------------------------------------------------

def test_frame_drops_unallowed_columns():
    frame = pd.DataFrame({"region": ["north"], "secret_column": ["x"]})
    result = redact_frame(frame, allowed_columns=["region"])
    assert list(result.payload.columns) == ["region"]


def test_frame_redacts_sensitive_columns():
    frame = pd.DataFrame({"region": ["north"], "phone": ["+968 1234 5678"]})
    result = redact_frame(frame)
    assert result.payload["phone"].iloc[0] == "[REDACTED:sensitive]"
    assert result.payload["region"].iloc[0] == "north"


def test_frame_redacts_text_cells():
    frame = pd.DataFrame({"note": ["built for Acme Water"]})
    result = redact_frame(frame, POLICY)
    assert "Acme" not in result.payload["note"].iloc[0]


def test_frame_row_limit_is_reported():
    frame = pd.DataFrame({"a": range(50)})
    result = redact_frame(frame, max_rows=10)
    assert len(result.payload) == 10
    assert any(f.action == "truncated" for f in result.findings)


def test_empty_frame_is_safe():
    assert redact_frame(pd.DataFrame()).payload is None


# --- validation issues ---------------------------------------------------------

def test_issue_descriptions_are_redacted():
    issue = build_issue(
        problem_name="test_problem",
        description="Value Acme Water is invalid",
        feature_id=1,
    )
    result = redact_issues([issue], POLICY)
    assert "Acme" not in result.payload[0]["description"]


def test_clean_payload_reports_nothing():
    issues = validate_ai_disclosure("A polygon layer with 4 features.")
    assert issues == []


def test_guard_summary_reports_what_was_removed():
    lenient = RedactionPolicy(blocked_terms=frozenset({"acme water"}), strict=False)
    with AiSubmissionGuard(lenient) as guard:
        guard("token = AKIAIOSFODNN7EXAMPLE for Acme Water")
    summary = guard.summary()
    assert summary["redacted"] >= 2
    assert summary["by_category"]["credential"] == 1


def test_guard_before_use_is_safe():
    with AiSubmissionGuard() as guard:
        assert guard.safe is True


# --- policy defaults -----------------------------------------------------------

def test_default_policy_blocks_nothing():
    """Nothing organisation-specific is baked in, deliberately."""
    assert RedactionPolicy().blocked_terms == frozenset()
    result = redact_text("any ordinary text")
    assert result.payload == "any ordinary text"


def test_keep_chars_retains_a_hint():
    policy = RedactionPolicy(keep_chars=4)
    result = redact_mapping({"password": "AKIAIOSFODNN7EXAMPLE"}, policy)
    assert "AKIA" in str(result.payload["password"])
    assert "IOSFODNN7EXAMPLE" not in str(result.payload["password"])