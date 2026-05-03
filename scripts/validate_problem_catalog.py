from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ALLOWED_CATEGORIES = {
    "accuracy",
    "anomalies",
    "attributes",
    "crs",
    "geometry",
    "integrity",
    "metadata",
    "spatial_logic",
    "topology",
}

ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}

REQUIRED_FIELDS = {
    "problem_name",
    "description",
    "category",
    "severity",
    "example",
    "repair_hint",
    "source_name",
    "source_link",
}


def validate_catalog(path: Path) -> list[str]:
    errors: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        return ["Catalog root must be a JSON array."]

    name_counts = Counter()
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append(f"Entry {index} is not an object.")
            continue

        missing = sorted(REQUIRED_FIELDS - set(item))
        if missing:
            errors.append(f"Entry {index} missing fields: {', '.join(missing)}")
            continue

        problem_name = item.get("problem_name")
        if not isinstance(problem_name, str) or not problem_name.strip():
            errors.append(f"Entry {index} has an invalid problem_name.")
        else:
            name_counts[problem_name] += 1

        category = item.get("category")
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"Entry {index} has invalid category: {category!r}")

        severity = item.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            errors.append(f"Entry {index} has invalid severity: {severity!r}")

        for field in ("description", "example", "repair_hint", "source_name", "source_link"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"Entry {index} has an invalid {field}.")

    duplicates = sorted(name for name, count in name_counts.items() if count > 1)
    if duplicates:
        errors.append(f"Duplicate problem_name values found: {', '.join(duplicates)}")

    return errors


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "raw_problems_with_sources.json"
    errors = validate_catalog(path)
    if errors:
        print("Catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Catalog validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
