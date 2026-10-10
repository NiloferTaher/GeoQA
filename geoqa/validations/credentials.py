"""Hardcoded credential detection, for code and configuration.

Why this exists
---------------
A credential in source is a credential in every clone, every build artefact and
every log that echoes the source. It survives password rotation because it is
not a password manager entry; it is a literal. This module finds the literals.

The hard part is not finding secrets, it is not crying wolf. A validator that
reports ``password = os.environ["PW"]`` as a leak trains people to ignore it. So
every rule here has an explicit exemption:

- **Environment references are exempt.** ``os.environ``, ``os.getenv``,
  ``process.env``, ``System.getenv``, ``${VAR}`` and ``{{ var }}`` are the
  correct way to do this.
- **Placeholders are exempt.** ``changeme``, ``your-password-here``, ``REDACTED``,
  ``xxx``, ``***``. These are noise, and reporting them costs the whole report
  its credibility.
- **Short values are exempt.** Under six characters is not a credential, it is
  a flag.
- **Non-literals are exempt.** ``password = self.password`` assigns a name, not
  a secret.

What is still reported
----------------------
Real-looking tokens matched by pattern (AWS, GitHub, Slack, Google, JWT), PEM
private key blocks, connection strings with an inline password, and literal
strings assigned to a secret-named variable.

Provenance
----------
The pattern set follows the published prefix schemes those providers document,
plus the generic name-and-literal rule that catches everything else. Detection
is a strong signal, not proof: a finding says "look here", and the surrounding
code decides.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

PROBLEM_NAME = "hardcoded_credential"

#: Provider-prefixed token formats. Each is a published scheme, not a guess.
TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"), "critical"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "critical"),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "critical"),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "critical"),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "high"),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), "critical"),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "critical"),
    ("mailgun_key", re.compile(r"\bkey-[0-9a-zA-Z]{32}\b"), "high"),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "high"),
    ("json_web_token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"), "high"),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"), "critical"),
    ("putty_private_key", re.compile(r"PuTTY-User-Key-File-\d"), "critical"),
)

#: URIs that carry an inline password.
CONNECTION_URI = re.compile(
    r"\b(?P<scheme>postgres(?:ql)?|mysql|mongodb(?:\+srv)?|amqp|redis|rediss|ftp|sftp|amqp\+ssl)"
    r"://(?P<user>[^:/@\s]+):(?P<password>[^@/\s]+)@",
    re.IGNORECASE,
)

#: ``https://user:password@host`` in a URL.
HTTP_BASIC_AUTH = re.compile(r"\bhttps?://[^:/@\s]+:[^@/\s]{4,}@", re.IGNORECASE)

#: Variable names whose value is a credential.
SECRET_NAME = re.compile(
    r"(?:^|[_.\-\[\]\"'])"
    r"(?:passwd|password|pass|pwd|secret|secrete|token|api[_-]?key|apikey|access[_-]?key"
    r"|secret[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?token|bearer|credential"
    r"|connection[_-]?string|dsn|session[_-]?key)"
    r"(?:$|[_.\-\[\]\"'])",
    re.IGNORECASE,
)

#: ``NAME = "literal"`` or ``"name": "literal"`` in any common language.
ASSIGNMENT = re.compile(
    r"""(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)   # variable or key
        \s*[:=]\s*                             # assignment or mapping
        (?P<quote>['"])                       # opening quote
        (?P<value>[^'"\n]*?)                  # the literal
        (?P=quote)""",
    re.VERBOSE,
)

#: Values that are references, not literals. Deliberately limited to forms that
#: are unambiguous in source: an empty branch here would exempt everything.
ENV_REFERENCE = re.compile(
    r"""^(?:
          os\.environ\b | os\.getenv\b | environ\.get\b | environ\b
        | process\.env\b | System\.getenv\b | System\.environ\b
        | (?:os|process)\.environ(?:\.get)?\b
        | settings\.[A-Za-z_]\w*
        | config\.[A-Za-z_]\w*
        | self\.[A-Za-z_]\w*
        | [A-Za-z_]\w*\([^)]*\)
    )$""",
    re.VERBOSE,
)

#: Literal values that are placeholders, not secrets. Each branch must consume
#: the whole value; an empty branch would exempt every word-only string.
PLACEHOLDER = re.compile(
    r"""^(?:
          x{3,}
        | [*\-.]{3,}
        | (?:change|changed|replace|insert|put|enter|set)[_-]?me
        | (?:placeholder|example|sample|dummy|redacted|removed|deleted
           | todo|fixme|none|null|nil|na|your|here|test|testing|secret
           | password|passwd|token|apikey|api_key|key|value|insert|put|enter
           | set|replace|change|me)(?:[-_. ]+
           (?:placeholder|example|sample|dummy|redacted|removed|deleted
           | todo|fixme|none|null|nil|na|your|here|test|testing|secret
           | password|passwd|token|apikey|api_key|key|value|insert|put|enter
           | set|replace|change|me))*[0-9_]*
        | <[^>]*>
        | \{\{?[^}]*\}?\}
        | %\w+%
        | \$\{[^}]*\} | \$[A-Za-z_]\w*
        | 0{4,} | x{4,}
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

#: Minimum length before a literal is treated as a possible credential.
MIN_LENGTH = 6

#: Characters commonly used in keys and passwords, for the shape test.
_CREDENTIAL_SHAPE = re.compile(r"^[A-Za-z0-9+/=_\-\.\:@!#\$%\^&\*]{6,}$")

#: Extensions scanned by :func:`scan_tree` when no filter is given.
DEFAULT_PATTERNS = ("*.py", "*.env", "*.ini", "*.cfg", "*.conf", "*.yaml", "*.yml", "*.json",
                    "*.toml", "*.properties", "*.xml", "*.sh", "*.ps1", "*.bat", "*.js",
                    "*.ts", "*.sql", "*.tf", "*.txt", "*.md")

#: Directory names never descended into.
SKIP_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build", ".tox",
})

#: Test files carry fake credentials by construction. Scanning them buries the
#: real findings under fixtures that are supposed to look like leaks.
TEST_PATH_PARTS = frozenset({"tests", "test", "fixtures", "testdata"})


def is_test_path(path: Path) -> bool:
    """Is this file a test fixture rather than shipped code?"""
    name = path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return any(part.lower() in TEST_PATH_PARTS for part in path.parts)


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def shannon_entropy(text: str) -> float:
    """Bits per character. Credentials sit high; English words sit low."""
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for character in text:
        counts[character] = counts.get(character, 0) + 1
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


@dataclass(frozen=True)
class SecretFinding:
    """One place a credential appears, with enough context to judge it."""

    kind: str
    severity: str
    line_number: int
    line: str
    #: The matched text, for reporting. Never the redacted value.
    match: str
    variable: str | None = None
    entropy: float | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "line_number": self.line_number,
            "line": self.line.strip()[:200],
            "variable": self.variable,
            "entropy": round(self.entropy, 2) if self.entropy is not None else None,
            "source": self.source,
        }


def redact_match(text: str, *, keep: int = 4) -> str:
    """A safe rendering of a secret: a hint of its shape, none of its value.

    Reports are shared. ``AKIA...MPLE`` tells a reviewer which key is meant
    without giving them the key.
    """
    if len(text) <= keep * 2:
        return "*" * len(text)
    return f"{text[:keep]}...{text[-keep:]}"


def _is_exempt(value: str) -> bool:
    """Is this literal safe to ignore?"""
    stripped = value.strip()
    if len(stripped) < MIN_LENGTH:
        return True
    if ENV_REFERENCE.match(stripped):
        return True
    if PLACEHOLDER.match(stripped):
        return True
    if stripped.startswith(("$", "{{", "<%", "%(")):
        return True
    return False


def _is_placeholder_url(url: str) -> bool:
    """Is this a documentation example rather than a real credential?

    ``https://user:password@host`` is how the pattern gets described. Flagging
    the description is the kind of false positive that teaches people to ignore
    the detector.
    """
    match = HTTP_BASIC_AUTH.search(url)
    if not match:
        return True
    credential = match.group(0).rsplit("://", 1)[-1].split(":", 1)[-1].split("@", 1)[0]
    return bool(PLACEHOLDER.match(credential.strip()))


def scan_text(
    text: str,
    *,
    source: str | None = None,
    min_entropy: float = 3.0,
) -> list[SecretFinding]:
    """Find credentials in one block of text.

    ``min_entropy`` guards the generic name-and-literal rule. Provider tokens
    matched by pattern are reported regardless, because their prefix is proof.
    """
    findings: list[SecretFinding] = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        for kind, pattern, severity in TOKEN_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    SecretFinding(
                        kind=kind,
                        severity=severity,
                        line_number=line_number,
                        line=line,
                        match=redact_match(match.group(0)),
                        source=source,
                    )
                )

        uri = CONNECTION_URI.search(line)
        if uri:
            password = uri.group("password")
            if not PLACEHOLDER.match(password.strip()):
                findings.append(
                    SecretFinding(
                        kind="connection_string_password",
                        severity="critical",
                        line_number=line_number,
                        line=line,
                        match=redact_match(password),
                        variable=f"{uri.group('scheme')}://{uri.group('user')}",
                        source=source,
                    )
                )

        basic = HTTP_BASIC_AUTH.search(line)
        if basic:
            if not _is_placeholder_url(basic.group(0)):
                findings.append(
                    SecretFinding(
                        kind="url_basic_auth",
                        severity="high",
                        line_number=line_number,
                        line=line,
                        match=redact_match(basic.group(0)),
                        source=source,
                    )
                )

        for assignment in ASSIGNMENT.finditer(line):
            name = assignment.group("name")
            value = assignment.group("value")
            if not SECRET_NAME.search(name):
                continue
            if _is_exempt(value):
                continue
            if not _CREDENTIAL_SHAPE.match(value.strip()):
                continue
            entropy = shannon_entropy(value)
            if entropy < min_entropy:
                continue
            findings.append(
                SecretFinding(
                    kind="hardcoded_secret_literal",
                    severity="high",
                    line_number=line_number,
                    line=line,
                    match=redact_match(value.strip()),
                    variable=name,
                    entropy=entropy,
                    source=source,
                )
            )

    return findings


def scan_file(path: str | Path, *, min_entropy: float = 3.0) -> list[SecretFinding]:
    """Scan one file. Binary and oversized files are skipped rather than guessed at."""
    target = Path(path)
    try:
        if target.stat().st_size > 8 * 1024 * 1024:
            return []
        text = target.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(text, source=str(target), min_entropy=min_entropy)


def iter_source_files(root: str | Path, *, patterns: Sequence[str] | None = None) -> Iterator[Path]:
    """Yield files worth scanning under ``root``, skipping caches and VCS."""
    base = Path(root)
    globs = tuple(patterns) if patterns else DEFAULT_PATTERNS
    for path in sorted(base.rglob("*")):
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if path.is_file() and any(path.match(pattern) for pattern in globs):
            yield path


def scan_tree(
    root: str | Path,
    *,
    patterns: Sequence[str] | None = None,
    min_entropy: float = 3.0,
    include_tests: bool = False,
) -> list[SecretFinding]:
    """Scan a directory for hardcoded credentials.

    ``include_tests`` is off by default. Test files hold fake credentials on
    purpose, so scanning them buries the real findings under fixtures that are
    meant to look like leaks. Turn it on when auditing a test suite itself.
    """
    findings: list[SecretFinding] = []
    for path in iter_source_files(root, patterns=patterns):
        if not include_tests and is_test_path(path):
            continue
        findings.extend(scan_file(path, min_entropy=min_entropy))
    return findings


def validate_credentials(
    path: str | Path,
    *,
    patterns: Sequence[str] | None = None,
    min_entropy: float = 3.0,
    include_tests: bool = False,
) -> list[Any]:
    """Report hardcoded credentials in a file or directory.

    Conditions emitted
    ------------------
    ``hardcoded_credential``
        A credential literal in source or configuration. Severity follows the
        kind: critical for provider tokens, private keys and connection
        strings, high for URL basic auth and generic secret literals.
    """
    target = Path(path)
    if target.is_dir():
        findings = scan_tree(
            target, patterns=patterns, min_entropy=min_entropy, include_tests=include_tests
        )
    else:
        findings = scan_file(target, min_entropy=min_entropy)

    issues: list[Any] = []
    for finding in findings:
        issue = _issue(
            PROBLEM_NAME,
            finding.severity,
            f"{finding.kind} in {finding.source or 'text'} line {finding.line_number}"
            + (f" (variable {finding.variable!r})" if finding.variable else "")
            + ". A credential in source survives every password rotation because it "
              "is a literal, not a secret-manager entry. Move it to an environment "
              "variable or a secret manager and rotate the exposed value",
            finding.as_dict(),
        )
        issues.append(issue)
    return issues


__all__ = [
    "CONNECTION_URI",
    "DEFAULT_PATTERNS",
    "MIN_LENGTH",
    "PROBLEM_NAME",
    "SECRET_NAME",
    "SKIP_DIRECTORIES",
    "TEST_PATH_PARTS",
    "TOKEN_PATTERNS",
    "SecretFinding",
    "is_test_path",
    "iter_source_files",
    "redact_match",
    "scan_file",
    "scan_text",
    "scan_tree",
    "shannon_entropy",
    "validate_credentials",
]