#!/usr/bin/env python3
"""Generate one Markdown page per validation module from the live registry.

Why this is generated rather than written
-----------------------------------------
Hand-written module documentation drifts. Someone renames a condition, or
changes a severity, and the prose quietly becomes wrong while still reading
authoritatively. A document that disagrees with the code is worse than no
document, because it is trusted.

This reads the actual registry and the actual module source, so a condition's
severity, description and repair hint in the documentation are the same strings
the validator emits at runtime.

Usage
-----
    python tools/generate_module_docs.py            # write docs/modules/*.md
    python tools/generate_module_docs.py --check    # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geoqa.problem_registry import list_problem_definitions  # noqa: E402

OUTPUT_DIR = ROOT / "docs" / "modules"

#: Where each module's prose lives in the generated page.
MODULE_ORDER_HINT = (
    "geometry", "topology", "attributes", "integrity", "crs", "crs_units",
    "dimension", "endpoint_triage", "raster", "hyperspectral", "cog",
    "archive", "tabular", "workbook_media", "axis_order", "osm",
    "vertical_datum", "boundary_conformance", "clip", "repeat_incident",
    "epanet", "water_balance", "night_flow", "water_loss", "reference_cases",
    "governance", "metric_constants", "payload_columns", "credentials",
)

_ISSUE_CALL = re.compile(
    r"""(?:_issue|build_issue)\s*\(\s*\n?\s*["']([a-z][a-z0-9_]+)["']"""
)


def _first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    text = inspect.cleandoc(doc).strip()
    for block in text.split("\n\n"):
        candidate = block.strip()
        if candidate and not candidate.startswith(("---", "===", "#")):
            return " ".join(candidate.split())
    return " ".join(text.split("\n\n")[0].split()) if text else ""


def _sections(doc: str | None) -> list[str]:
    """Section headings from a module docstring, for the generated page."""
    if not doc:
        return []
    headings: list[str] = []
    lines = inspect.cleandoc(doc).splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or index + 1 >= len(lines):
            continue
        underline = lines[index + 1].strip()
        if underline and set(underline) <= {"-", "="} and len(underline) >= max(3, len(stripped) - 2):
            headings.append(stripped.rstrip(":"))
    return headings


def module_conditions(module: Any) -> list[str]:
    """Problem names this module can emit, read from its source.

    Two classes of string are deliberately excluded, because mistaking them for
    conditions produces a page asserting a defect that does not exist:

    ``PROBLEM_NAME``
        A headline label for the module, often just the module's own name.

    Anything exported in ``__all__``
        Public function names and cause constants. The source regex matches a
        quoted string following an issue constructor across newlines, so a
        bare entry in an ``__all__`` list can be picked up.
    """
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return []
    found = set(_ISSUE_CALL.findall(source))
    found.discard("problem_name")
    for exported in getattr(module, "__all__", ()) or ():
        found.discard(str(exported))
    for name, value in vars(module).items():
        if callable(value) or isinstance(value, (str, tuple, frozenset)) and name.isupper():
            found.discard(name)
    return sorted(found)


def public_validators(module: Any) -> list[tuple[str, str]]:
    """Public validate_* functions and their first docstring line."""
    items: list[tuple[str, str]] = []
    for name in sorted(dir(module)):
        if not name.startswith("validate_"):
            continue
        function = getattr(module, name)
        if not callable(function):
            continue
        summary = (inspect.getdoc(function) or "").strip().split("\n")[0]
        items.append((name, summary))
    return items


def build_pages() -> dict[str, str]:
    registry = {definition.problem_name: definition for definition in list_problem_definitions()}
    validations_dir = ROOT / "geoqa" / "validations"
    pages: dict[str, str] = {}

    for path in sorted(validations_dir.glob("*.py")):
        if path.stem in {"__init__", "base"}:
            continue
        try:
            module = importlib.import_module(f"geoqa.validations.{path.stem}")
        except Exception as error:  # pragma: no cover - optional dependency
            pages[path.stem] = (
                f"# `{path.stem}`\n\n"
                f"Not importable in this environment: `{error}`.\n"
                "Its optional dependency is not installed.\n"
            )
            continue

        doc = module.__doc__
        summary = _first_paragraph(doc)
        headings = _sections(doc)
        conditions = module_conditions(module)
        validators = public_validators(module)

        lines: list[str] = [f"# `{path.stem}`", ""]
        if summary:
            lines += [summary, ""]

        if validators:
            lines += ["## Entry points", "", "| Function | Purpose |", "| --- | --- |"]
            lines += [f"| `{name}` | {text} |" for name, text in validators]
            lines.append("")

        if conditions:
            lines += ["## Conditions emitted", ""]
            for name in conditions:
                definition = registry.get(name)
                if definition is None:
                    lines += [
                        f"### `{name}`", "",
                        "Not present in the registry. This is a defect: every emitted "
                        "condition should be registered so it carries a severity and a "
                        "repair hint.", "",
                    ]
                    continue
                lines += [
                    f"### `{name}`", "",
                    f"**Severity** {definition.default_severity} &nbsp;|&nbsp; "
                    f"**Class** `{definition.issue_class}` &nbsp;|&nbsp; "
                    f"**Confidence** {definition.default_confidence}",
                    "",
                    definition.description,
                    "",
                    f"**Repair.** {definition.repair_hint}",
                    "",
                ]
        else:
            lines += [
                "## Conditions emitted", "",
                "None directly. This module implements the underlying checks; the "
                "conditions it participates in are registered under the names used by "
                "the validation runtime.", "",
            ]

        if headings:
            lines += ["## Design notes", ""]
            lines += [f"- **{heading}**" for heading in headings]
            lines.append("")

        lines += [
            "---", "",
            "Generated from the live registry by `tools/generate_module_docs.py`. "
            "Do not edit by hand; the severity and wording here are the strings the "
            "validator actually emits.", "",
        ]
        pages[path.stem] = "\n".join(lines)

    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if any page is out of date")
    arguments = parser.parse_args(argv)

    pages = build_pages()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Validation modules", "", "One page per module, generated from the registry.", ""]

    def sort_key(name: str) -> tuple[int, str]:
        return (MODULE_ORDER_HINT.index(name), name) if name in MODULE_ORDER_HINT else (len(MODULE_ORDER_HINT), name)

    stale: list[str] = []
    for name in sorted(pages, key=sort_key):
        target = OUTPUT_DIR / f"{name}.md"
        content = pages[name]
        heading = re.search(r"^# .+?$", content, re.M)
        index_lines.append(f"- [`{name}`]({name}.md) — {(heading.group(0)[2:] if heading else name)}")
        if arguments.check:
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                stale.append(name)
        else:
            target.write_text(content, encoding="utf-8")

    index = "\n".join(index_lines) + "\n"
    index_path = OUTPUT_DIR / "README.md"
    if arguments.check:
        if not index_path.exists() or index_path.read_text(encoding="utf-8") != index:
            stale.append("README")
        if stale:
            print("Out of date: " + ", ".join(sorted(stale)), file=sys.stderr)
            return 1
        print(f"module docs up to date ({len(pages)} modules)")
        return 0

    index_path.write_text(index, encoding="utf-8")
    print(f"wrote {len(pages)} module pages + index to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())