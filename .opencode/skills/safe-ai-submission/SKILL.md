---
name: safe-ai-submission
description: Use before sending ANY data, file, code, log, stack trace, config, query result, or dataframe to an LLM or AI service. Detects credentials, personal data, blocked terms and filesystem paths in the payload, redacts them, and refuses when policy forbids it. Also use when auditing a repo for hardcoded credentials, or when building anything that calls an AI API with real data.
---

# Safe AI submission

## The rule

**Never send a payload to a model without running it through the guard first.**

This is not a style preference. A credential in a config file, a client name in
a column header, or a username in a path will ride along silently, and the
disclosure is irreversible: the data is now in someone else's retention system.

## Do this

```python
from geoqa.ai_guard import RedactionPolicy, redact_frame, validate_ai_disclosure

policy = RedactionPolicy(blocked_terms=frozenset({"<client name>", "<project codename>"}))

# 1. Look before you leap. This is the diagnostic step.
for issue in validate_ai_disclosure(payload, policy):
    print(issue.problem_name, issue.description)

# 2. Redact on the way in.
safe = redact_frame(df, policy, allowed_columns=["geometry", "region"])  # allowlist wins
```

Prefer `allowed_columns=` over redaction. A redacted column still discloses
that the entity had one. An allowlist makes the disclosure a decision.

## Or use the guard

```python
from geoqa.ai_guard import AiSubmissionGuard

with AiSubmissionGuard(policy) as guard:
    client.chat(model="...", messages=[{"role": "user", "content": guard(payload)}])

guard.summary()   # exactly what was removed, and from where
```

The guard **raises `PermissionError`** if the payload contains a blocked term
and the policy is strict. That is the intended behaviour, not a bug to catch.

## What gets caught

| Category | Examples |
|---|---|
| `credential` | AWS `AKIA…`, GitHub `ghp_…`, Slack `xox…`, PEM private key blocks, JWTs |
| `personal_data` | email, phone, IBAN, card number |
| `sensitive_column` | `national_id`, `passport`, `dob`, `salary`, `address`, `phone`, `email` |
| `blocked_term` | whatever the caller declared: client names, project names, internal codes |
| `filesystem_path` | `C:\Users\<you>\…` — leaks a username and directory structure |

## What it cannot catch

Redaction is a control, not a proof. These need a human decision:

- A coordinate that is sensitive because it is **a private household's location**
- A screenshot or image containing anything
- Free text whose meaning a regex cannot see
- The fact that a dataset exists at all

When those are in scope, use an allowlist and say so in the output.

## Auditing a repo for hardcoded credentials

```python
from geoqa.validations.credentials import validate_credentials, scan_tree

for finding in scan_tree("."):
    print(finding.kind, finding.source, finding.line_number)

for issue in validate_credentials("."):
    print(issue.description)
```

This has explicit exemptions on purpose, because a detector that cries wolf
gets switched off and then protects nothing:

- `os.environ[...]`, `os.getenv(...)`, `process.env.X`, `${VAR}`, `{{ var }}` — exempt
- `changeme`, `your-password-here`, `REDACTED`, `xxxxxxxx` — exempt
- values under 6 characters — exempt
- `password = self.password` — exempt

**If it flags something that is not a secret, that is a bug.** Fix the pattern in
`geoqa/validations/credentials.py`, do not suppress the report.

## Rotating an exposed credential

Finding a hardcoded secret is step one. Step two is **rotating the value** —
a literal in source survives every password rotation because it is not a
password-manager entry. Report it as `critical` and say so plainly.