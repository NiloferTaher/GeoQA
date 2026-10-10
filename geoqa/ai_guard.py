"""Guardrails for anything sent to a language model.

The problem
-----------
Sending data to an AI service is a disclosure. Most of that disclosure is
intended and nobody notices it; the part that is *not* intended is the
credential, the personal identifier or the client name that rode along inside a
configuration file, a stack trace or a column header.

This module is the preflight. It runs on the payload **before** the call, and
it does two things:

* **Redact** what it recognises, replacing it with a stable placeholder so the
  model still sees that a field exists.
* **Refuse** when a redacted payload would still disclose something the policy
  does not permit, returning findings rather than silently passing.

What it does not do
-------------------
It does not guarantee nothing sensitive leaves. Redaction is a control, not a
proof. It does not understand what your data *means*: a coordinate that is
sensitive because it is a private household is not detectable by pattern. Where
that is the risk, the answer is a declared allowlist of columns, which this
module supports and prefers over redaction.

Policy over hardcoding
----------------------
Column names, terms and paths that must never be sent are supplied by the
caller. Nothing about a particular organisation is written into this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .validations.credentials import TOKEN_PATTERNS, shannon_entropy

PROBLEM_NAME = "ai_disclosure_risk"

#: Column names that usually carry personal or sensitive data.
SENSITIVE_COLUMN_NAMES: frozenset[str] = frozenset({
    "email", "e_mail", "mail", "phone", "mobile", "telephone", "tel", "fax",
    "national_id", "nationalid", "national_number", "civil_id", "cnic",
    "id_card", "idcard", "identity_no", "identity_number", "ssn", "sin",
    "passport", "passport_no", "passport_number", "visa_no", "licence_number",
    "dob", "date_of_birth", "birth_date", "birthdate", "birth_year",
    "address", "home_address", "street_address", "residential_address",
    "postcode", "zip", "zip_code", "full_name", "first_name", "last_name",
    "surname", "father_name", "mother_name", "employer_name",
    "salary", "wage", "income", "bank_account", "account_number", "iban",
    "card_number", "credit_card", "medical", "diagnosis", "health_condition",
    "religion", "ethnicity", "political_affiliation", "password", "passwd",
    "secret", "token", "api_key", "apikey", "private_key", "credential",
    "latitude_of_home", "home_location", "gps_of_home",
})

#: Free-text patterns for personal data. Ordered most specific first.
PERSONAL_DATA_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "high"),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"), "medium"),
    ("phone", re.compile(r"(?<![\w.])(?:\+|00)\d[\d\s().-]{7,17}\d"), "medium"),
    ("credit_card", re.compile(r"(?<![\d.])(?:\d[ -]?){13,19}(?![\d.])"), "high"),
    ("national_id", re.compile(r"(?<![\w])(?:\d{1,4}[- ])?\d{6,12}[- ]?\d{0,4}(?![\w])"), "low"),
)


@dataclass
class RedactionPolicy:
    """What may leave, and what must be replaced.

    ``blocked_terms`` is the caller's own list: client names, project code
    names, internal identifiers. This module ships none, deliberately.
    """

    #: Terms that must never appear in a payload. Compared case-insensitively.
    blocked_terms: frozenset[str] = frozenset()
    #: Column names to drop entirely rather than redact.
    drop_columns: frozenset[str] = frozenset()
    #: Redact personal-data patterns. Off by default: it is noisy on plain text.
    redact_personal_data: bool = True
    #: Redact filesystem paths, which leak usernames and directory structure.
    redact_paths: bool = True
    #: Redact credentials of any recognised provider format.
    redact_credentials: bool = True
    #: Characters kept at each end of a redacted value, for identifiability.
    keep_chars: int = 0
    #: Refuse rather than redact when a blocked term is present.
    strict: bool = True

    def placeholder_for(self, kind: str) -> str:
        return f"[REDACTED:{kind}]"


@dataclass
class RedactionFinding:
    """One redaction or refusal, with the location and nothing of the value."""

    kind: str
    category: str
    location: str
    severity: str = "medium"
    action: str = "redacted"

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "category": self.category,
            "location": self.location,
            "severity": self.severity,
            "action": self.action,
        }


@dataclass
class RedactionResult:
    """The safe payload, plus an account of what was taken out of it."""

    payload: Any
    findings: list[RedactionFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.action == "blocked" for f in self.findings)

    @property
    def clean(self) -> bool:
        """Nothing was redacted and nothing blocked."""
        return not self.findings

    @property
    def redacted_count(self) -> int:
        return sum(1 for f in self.findings if f.action == "redacted")

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return {
            "blocked": self.blocked,
            "redacted": self.redacted_count,
            "by_category": counts,
            "findings": [f.as_dict() for f in self.findings],
        }


def _is_sensitive_column(name: Any) -> str | None:
    """Which sensitive class a column name belongs to, if any."""
    label = str(name).strip().lower().replace(" ", "_")
    if label in SENSITIVE_COLUMN_NAMES:
        return label
    for candidate in SENSITIVE_COLUMN_NAMES:
        if candidate in label:
            return candidate
    return None


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .validations.base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _redact_literal(value: str, policy: RedactionPolicy) -> str:
    keep = max(0, policy.keep_chars)
    if keep and len(value) > keep * 2:
        return f"{value[:keep]}{policy.placeholder_for('value')}{value[-keep:]}"
    return policy.placeholder_for("value")


def keep_hint(value: Any, policy: RedactionPolicy) -> bool:
    """Should a leading/trailing hint be kept for this value?

    Only when the caller asked for it *and* the value is long enough that a
    hint identifies without disclosing. Short identifiers get a full redaction.
    """
    keep = max(0, policy.keep_chars)
    return bool(keep) and isinstance(value, str) and len(value) > keep * 2


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

def redact_text(text: str, policy: RedactionPolicy | None = None, *, location: str = "text") -> RedactionResult:
    """Make a block of text safe to send.

    Credentials first, then personal data, then paths, then the caller's own
    blocked terms. Order matters: a credential inside a connection string is
    caught by the credential rule before the path rule touches the URI.
    """
    active = policy or RedactionPolicy()
    result = RedactionResult(payload=text)
    working = text

    if active.redact_credentials:
        for kind, pattern, severity in TOKEN_PATTERNS:
            working, count = pattern.subn(active.placeholder_for(kind), working)
            if count:
                result.findings.append(
                    RedactionFinding(kind, "credential", location, severity, "redacted")
                )

    if active.redact_personal_data:
        for kind, pattern, severity in PERSONAL_DATA_PATTERNS:
            if kind == "national_id" and len(working) > 2000:
                # Far too many false positives to be useful in prose.
                continue
            working, count = pattern.subn(active.placeholder_for(kind), working)
            if count:
                result.findings.append(
                    RedactionFinding(kind, "personal_data", location, severity, "redacted")
                )

    if active.redact_paths:
        working, count = re.subn(
            r"(?<![\w])(?:[A-Za-z]:)?[\\/](?:[\w.\- ]+[\\/])+[\w.\- ]*",
            active.placeholder_for("path"),
            working,
        )
        if count:
            result.findings.append(RedactionFinding("path", "filesystem_path", location, "low", "redacted"))

    for term in sorted(active.blocked_terms, key=len, reverse=True):
        if not term:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        working, count = pattern.subn(active.placeholder_for("term"), working)
        if count:
            result.findings.append(
                RedactionFinding(
                    kind=term,
                    category="blocked_term",
                    location=location,
                    severity="high",
                    action="blocked" if active.strict else "redacted",
                )
            )

    result.payload = working
    return result


# --------------------------------------------------------------------------
# Mappings and tables
# --------------------------------------------------------------------------

def redact_mapping(
    mapping: Mapping[str, Any],
    policy: RedactionPolicy | None = None,
    *,
    location: str = "payload",
) -> RedactionResult:
    """Redact a mapping, dropping columns the policy names.

    ``drop_columns`` beats redaction: a column that must not be sent is removed,
    because a redacted column still reveals that the entity had one.
    """
    active = policy or RedactionPolicy()
    result = RedactionResult(payload={})
    safe: dict[str, Any] = {}

    for key, value in mapping.items():
        column_label = str(key).strip().lower().replace(" ", "_")

        if key in active.drop_columns or column_label in active.drop_columns:
            result.findings.append(
                RedactionFinding(str(key), "dropped_column", f"{location}.{key}", "high", "dropped")
            )
            continue

        sensitive = _is_sensitive_column(key)
        if sensitive:
            result.findings.append(
                RedactionFinding(sensitive, "sensitive_column", f"{location}.{key}", "high", "redacted")
            )
            safe[key] = _redact_literal(str(value), active) if keep_hint(value, active) else active.placeholder_for("sensitive")
            continue

        if isinstance(value, str):
            nested = redact_text(value, active, location=f"{location}.{key}")
            safe[key] = nested.payload
            result.findings.extend(nested.findings)
        elif isinstance(value, Mapping):
            nested = redact_mapping(value, active, location=f"{location}.{key}")
            safe[key] = nested.payload
            result.findings.extend(nested.findings)
        elif isinstance(value, (list, tuple)):
            safe[key] = [
                redact_text(item, active, location=f"{location}.{key}[{i}]").payload
                if isinstance(item, str) else item
                for i, item in enumerate(value)
            ]
        else:
            safe[key] = value

    result.payload = safe
    return result


def redact_frame(
    frame: Any,
    policy: RedactionPolicy | None = None,
    *,
    allowed_columns: Sequence[str] | None = None,
    max_rows: int | None = 1000,
) -> RedactionResult:
    """Redact a tabular dataset before it leaves the process.

    ``allowed_columns`` is preferred over redaction when the caller knows what
    is needed. Anything not on the list is dropped, which makes the disclosure
    a decision rather than an accident.
    """
    active = policy or RedactionPolicy()
    result = RedactionResult(payload=None)

    columns = list(getattr(frame, "columns", []))
    if not columns:
        return result

    keep: list[str] = []
    for column in columns:
        label = str(column)
        if allowed_columns is not None:
            if label not in allowed_columns:
                result.findings.append(
                    RedactionFinding(label, "not_allowed", f"column:{label}", "low", "dropped")
                )
                continue
        elif label in active.drop_columns or str(column).lower() in active.drop_columns:
            result.findings.append(
                RedactionFinding(label, "dropped_column", f"column:{label}", "high", "dropped")
            )
            continue

        sensitive = _is_sensitive_column(column)
        if sensitive:
            result.findings.append(
                RedactionFinding(sensitive, "sensitive_column", f"column:{label}", "high", "redacted")
            )
        keep.append(column)

    rows = frame if max_rows is None else frame.head(max_rows)
    safe = rows[keep].copy()
    for column in keep:
        if any(f.category == "sensitive_column" and f.location == f"column:{column}" for f in result.findings):
            safe[column] = active.placeholder_for("sensitive")
        elif safe[column].dtype == object:
            safe[column] = safe[column].map(
                lambda v: redact_text(v, active, location=f"column:{column}").payload
                if isinstance(v, str) else v
            )

    if max_rows is not None and len(frame) > max_rows:
        result.findings.append(
            RedactionFinding("truncated", "row_limit", "frame", "low", "truncated")
        )

    result.payload = safe
    return result


def redact_issues(
    issues: Iterable[Any],
    policy: RedactionPolicy | None = None,
    *,
    location: str = "issues",
) -> RedactionResult:
    """Redact validation issues before they are summarised by a model.

    Descriptions often quote the offending value, which is exactly how a
    credential ends up in a prompt.
    """
    active = policy or RedactionPolicy()
    result = RedactionResult(payload=[])

    for index, issue in enumerate(issues):
        as_dict = issue.to_dict() if hasattr(issue, "to_dict") else dict(issue)
        nested = redact_mapping(as_dict, active, location=f"{location}[{index}]")
        result.payload.append(nested.payload)
        result.findings.extend(nested.findings)

    return result


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def validate_ai_disclosure(
    payload: Any,
    policy: RedactionPolicy | None = None,
    *,
    location: str = "payload",
) -> list[Any]:
    """Report what would be disclosed by sending ``payload`` unchanged.

    This is the diagnostic you run *before* redacting, to decide whether to
    redact at all.

    Conditions emitted
    ------------------
    ``ai_disclosure_credential``
        A credential is present in the payload. Critical.
    ``ai_disclosure_blocked_term``
        A term the caller declared as blocked appears. High, and refused under
        a strict policy.
    ``ai_disclosure_personal_data``
        An email, phone, card or similar pattern is present. Medium.
    ``ai_disclosure_sensitive_column``
        A column name indicates personal data. High.
    ``ai_disclosure_filesystem_path``
        A local path is present, disclosing a username or directory structure.
        Low.
    """
    active = policy or RedactionPolicy()
    issues: list[Any] = []

    if isinstance(payload, str):
        result = redact_text(payload, active, location=location)
    elif hasattr(payload, "columns"):
        result = redact_frame(payload, active)
    elif isinstance(payload, Mapping):
        result = redact_mapping(payload, active, location=location)
    else:
        result = redact_text(str(payload), active, location=location)

    grouped: dict[str, list[RedactionFinding]] = {}
    for finding in result.findings:
        grouped.setdefault(finding.category, []).append(finding)

    if grouped.get("credential"):
        issues.append(
            _issue(
                "ai_disclosure_credential",
                "critical",
                f"{len(grouped['credential'])} credential(s) would be sent to the model "
                "verbatim. Rotate the exposed value, then redact before sending",
                {"locations": [f.location for f in grouped["credential"]][:20]},
            )
        )

    if grouped.get("blocked_term"):
        issues.append(
            _issue(
                "ai_disclosure_blocked_term",
                "high",
                f"{len(grouped['blocked_term'])} occurrence(s) of a declared blocked "
                "term would be sent. Under a strict policy this payload is refused",
                {
                    "terms": sorted({f.kind for f in grouped["blocked_term"]}),
                    "refused": active.strict,
                },
            )
        )

    if grouped.get("sensitive_column"):
        issues.append(
            _issue(
                "ai_disclosure_sensitive_column",
                "high",
                f"{len(grouped['sensitive_column'])} column(s) are named like personal "
                "data. Drop them or pass an explicit allowlist; a redacted column still "
                "discloses that the entity had one",
                {"columns": [f.location for f in grouped["sensitive_column"]][:20]},
            )
        )

    if grouped.get("personal_data"):
        issues.append(
            _issue(
                "ai_disclosure_personal_data",
                "medium",
                f"{len(grouped['personal_data'])} personal-data pattern(s) would be sent. "
                "Confirm the recipient is permitted to hold this data",
                {"kinds": sorted({f.kind for f in grouped["personal_data"]})},
            )
        )

    if grouped.get("filesystem_path"):
        issues.append(
            _issue(
                "ai_disclosure_filesystem_path",
                "low",
                f"{len(grouped['filesystem_path'])} local path(s) would be sent, disclosing "
                "a username and directory structure",
                {"locations": [f.location for f in grouped["filesystem_path"]][:20]},
            )
        )

    return issues


class AiSubmissionGuard:
    """Context manager that redacts on the way in and reports on the way out.

    ::

        with AiSubmissionGuard(blocked_terms={"acme"}) as guard:
            client.chat(messages=guard(payload))

    ``guard.safe`` is false if anything was blocked, and ``guard.summary()``
    records exactly what was removed. The original payload is never mutated.
    """

    def __init__(self, policy: RedactionPolicy | None = None, *, location: str = "payload") -> None:
        self.policy = policy or RedactionPolicy()
        self.location = location
        self.last_result: RedactionResult | None = None

    def __enter__(self) -> "AiSubmissionGuard":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def __call__(self, payload: Any) -> Any:
        if isinstance(payload, str):
            self.last_result = redact_text(payload, self.policy, location=self.location)
        elif hasattr(payload, "columns"):
            self.last_result = redact_frame(payload, self.policy)
        elif isinstance(payload, Mapping):
            self.last_result = redact_mapping(payload, self.policy, location=self.location)
        else:
            self.last_result = redact_text(str(payload), self.policy, location=self.location)

        if self.last_result.blocked and self.policy.strict:
            raise PermissionError(
                "payload refused: it contains a term declared blocked "
                f"({', '.join(sorted({f.kind for f in self.last_result.findings if f.action == 'blocked'}))}). "
                "Redact it explicitly or relax the policy"
            )
        return self.last_result.payload

    @property
    def safe(self) -> bool:
        return self.last_result is None or not self.last_result.blocked

    def summary(self) -> dict[str, Any]:
        return self.last_result.summary() if self.last_result else {"blocked": False, "redacted": 0}


__all__ = [
    "PERSONAL_DATA_PATTERNS",
    "PROBLEM_NAME",
    "SENSITIVE_COLUMN_NAMES",
    "AiSubmissionGuard",
    "RedactionFinding",
    "RedactionPolicy",
    "RedactionResult",
    "redact_frame",
    "redact_issues",
    "redact_mapping",
    "redact_text",
    "validate_ai_disclosure",
]