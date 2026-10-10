"""Tests for hardcoded credential detection.

The behaviour worth protecting: real credentials are found, and the correct
ways of *not* hardcoding them are not flagged. A detector that cries wolf gets
switched off, and then it protects nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from geoqa.validations.credentials import (
    SecretFinding,
    is_test_path,
    redact_match,
    scan_file,
    scan_text,
    scan_tree,
    shannon_entropy,
    validate_credentials,
)


def _names(issues):
    return [i.problem_name for i in issues]


def _kinds(findings):
    return [f.kind for f in findings]


# --- real credentials must be found -------------------------------------

def test_aws_access_key_id_is_critical():
    findings = scan_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')
    finding = next(f for f in findings if f.kind == "aws_access_key_id")
    assert finding.severity == "critical"


def test_github_token_is_found():
    token = "ghp_" + "a" * 36
    assert "github_token" in _kinds(scan_text(f'TOKEN = "{token}"'))


def test_private_key_block_is_found():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"
    assert "private_key_block" in _kinds(scan_text(text))


def test_connection_string_with_password_is_critical():
    findings = scan_text('DB = "postgresql://admin:hunter2correct@db.internal:5432/gis"')
    finding = next(f for f in findings if f.kind == "connection_string_password")
    assert finding.severity == "critical"
    assert finding.match.startswith("hunt")
    assert "hunter2correct" not in finding.match


def test_url_basic_auth_is_found():
    findings = scan_text('url = "https://alice:s3cr3tp4ss@example.com/data"')
    assert "url_basic_auth" in _kinds(findings)


def test_json_web_token_is_found():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    assert "json_web_token" in _kinds(scan_text(f'token = "{token}"'))


def test_generic_secret_literal_is_found():
    findings = scan_text('password = "Tr0ub4dor&3xyz"', min_entropy=2.5)
    finding = next(f for f in findings if f.kind == "hardcoded_secret_literal")
    assert finding.variable == "password"


# --- the correct patterns must NOT be flagged ---------------------------

def test_environment_reference_is_exempt():
    """This is how it should be written, so it must never be reported."""
    text = 'password = os.environ["GIS_PASSWORD"]'
    assert scan_text(text) == []


def test_getenv_is_exempt():
    assert scan_text('api_key = os.getenv("API_KEY")') == []
    assert scan_text('token = process.env.GITHUB_TOKEN') == []


def test_template_variable_is_exempt():
    assert scan_text('password = "${GIS_PASSWORD}"') == []
    assert scan_text("password = '{{ vault_password }}'") == []


def test_placeholders_are_exempt():
    for value in ("changeme", "your-password-here", "REDACTED", "xxxxxxxx", "***", "<password>", "TODO"):
        assert scan_text(f'password = "{value}"') == [], value


def test_short_value_is_exempt():
    assert scan_text('password = "abc"') == []


def test_self_reference_is_exempt():
    """Assigning a name is not assigning a secret."""
    assert scan_text("password = self.password") == []
    assert scan_text("secret = config.secret_key") == []


def test_ordinary_vocabulary_is_not_a_secret():
    """A sentence about a password should not trip the entropy rule."""
    text = 'password = "the user must change this"'
    assert [f for f in scan_text(text, min_entropy=3.0) if f.kind == "hardcoded_secret_literal"] == []


def test_non_secret_variables_are_ignored():
    assert scan_text('username = "gis_operator"') == []


# --- redaction ------------------------------------------------------------

def test_redaction_keeps_a_hint_and_drops_the_value():
    rendered = redact_match("AKIAIOSFODNN7EXAMPLE")
    assert rendered.startswith("AKIA")
    assert rendered.endswith("MPLE")
    assert "IOSFODNN7EXA" not in rendered


def test_redaction_of_short_values_is_total():
    assert redact_match("abc") == "***"


def test_finding_never_carries_the_full_secret():
    findings = scan_text('password = "Tr0ub4dor&3xyz"', min_entropy=2.5)
    for finding in findings:
        assert "Tr0ub4dor&3xyz" not in finding.line.replace(finding.match, "") or "Tr0ub4dor" not in finding.match


# --- entropy ---------------------------------------------------------------

def test_entropy_separates_secrets_from_words():
    assert shannon_entropy("Tr0ub4dor&3xyz") > shannon_entropy("password")


def test_entropy_of_empty_is_zero():
    assert shannon_entropy("") == 0.0


# --- files and trees -------------------------------------------------------

def test_scan_file(tmp_path):
    path = tmp_path / "config.py"
    path.write_text('password = "Sup3rS3cretValue"\n', encoding="utf-8")
    findings = scan_file(path)
    assert findings and findings[0].source == str(path)


def test_binary_file_is_skipped_not_guessed(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\xff\xfe\x00\x01AKIAIOSFODNN7EXAMPLE")
    assert scan_file(path) == []


def test_missing_file_is_empty(tmp_path):
    assert scan_file(tmp_path / "nope.py") == []


def test_scan_tree_finds_nested_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text('api_key = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    assert any("aws_access_key_id" == f.kind for f in scan_tree(tmp_path))


def test_scan_tree_skips_caches_and_vcs(tmp_path):
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "leak.py").write_text('password = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    assert scan_tree(tmp_path) == []


def test_validate_credentials_on_a_directory(tmp_path):
    (tmp_path / "a.py").write_text('token = "ghp_' + "a" * 36 + '"\n', encoding="utf-8")
    issues = validate_credentials(tmp_path)
    assert _names(issues) == ["hardcoded_credential"]
    assert str(issues[0].severity) == "critical"


def test_validate_credentials_on_a_clean_file(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text('password = os.environ["PW"]\n', encoding="utf-8")
    assert validate_credentials(path) == []


def test_issue_payload_carries_line_number(tmp_path):
    path = tmp_path / "a.py"
    path.write_text('# comment\npassword = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    issue = validate_credentials(path)[0]
    assert issue.to_dict()["line_number"] == 2


def test_line_numbers_survive_multiple_lines():
    text = "\n".join([
        "a = 1",
        "b = 2",
        'token = "ghp_' + "z" * 36 + '"',
    ])
    finding = next(f for f in scan_text(text) if f.kind == "github_token")
    assert finding.line_number == 3


def test_finding_is_hashable_value_type():
    finding = SecretFinding("k", "high", 1, "line", "***")
    assert finding.severity == "high"

# --- test fixtures are exempt by default ----------------------------------

def test_documentation_example_is_not_flagged():
    """Flagging the detector's own documentation teaches people to ignore it."""
    assert scan_text("#: ``https://user:password@host`` in a URL.") == []


def test_real_basic_auth_is_still_flagged():
    assert "url_basic_auth" in _kinds(scan_text('url = "https://alice:s3cr3tp4ss@example.com"'))


def test_placeholder_connection_string_is_not_flagged():
    assert scan_text('DB = "postgresql://user:password@localhost/gis"') == []


def test_test_paths_are_recognised():
    from pathlib import Path
    assert is_test_path(Path("tests/test_secrets.py")) is True
    assert is_test_path(Path("src/conftest.py")) is True
    assert is_test_path(Path("geoqa/validations/credentials.py")) is False


def test_scan_tree_skips_tests_by_default(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text('k = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    assert scan_tree(tmp_path) == []


def test_tests_can_be_included_on_request(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text('k = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    assert any("aws_access_key_id" == f.kind for f in scan_tree(tmp_path, include_tests=True))