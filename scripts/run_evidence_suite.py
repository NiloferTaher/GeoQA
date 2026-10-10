#!/usr/bin/env python3
"""Run a declared suite of validation cases, verify each, and log the results.

Purpose
-------
Reproducibility harnesses tend to accumulate hardcoded paths and hardcoded
headline numbers, which makes them valid for exactly one submission and
invalid for the next. This tool generalises the pattern: you declare the cases
in a manifest, and the harness does the mechanical part - run, verify, log,
and optionally diff against a recorded baseline.

What it verifies per case
-------------------------
- the process exited zero
- a report file was produced
- the report is non-empty and parses as JSON
- ``execution_status`` is ``full`` (a partial run is NOT accepted as a pass;
  this is the check that most often catches a truncated scan being reported as
  a clean result)
- an expected issue count, when the manifest states one

Usage
-----
    python scripts/run_evidence_suite.py suite.json --out reports/my_suite
    python scripts/run_evidence_suite.py suite.json --baseline reports/my_suite/run_log.json

Manifest format
---------------
    {
      "name": "my_suite",
      "cases": [
        {"name": "case_a", "path": "data/x.geojson",
         "profile": "generic_quick", "low_resource": true,
         "expect_issues": 2, "expect_status": "full"},
        {"name": "case_b", "path": "data/y.geojson",
         "profile": "spectral", "python_callable": "my_module:generate"}
      ]
    }

``python_callable`` cases are for validators that are not reachable through the
CLI - for example the ``spectral`` dataset type, which has no CLI flag. The
callable receives the report directory and must write ``<report_dir>/<name>.json``.

Exit codes
----------
0  every declared case passed
1  at least one case failed, or the run log could not be written
2  the manifest was unreadable or invalid
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


def load_json(path: pathlib.Path) -> dict[str, Any]:
    """Read JSON tolerating a UTF-8 BOM.

    Windows editors and PowerShell's Out-File/Set-Content emit a BOM by
    default, so a manifest or report written on Windows frequently carries one.
    Python's utf-8 codec raises on it, which would make the harness fail only on
    Windows for a file that is perfectly valid everywhere else. utf-8-sig
    decodes BOM and BOM-less files identically, so this is safe to use
    unconditionally.
    """
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(raw)


def extract_status(data: dict[str, Any]) -> str | None:
    """Pull execution_status from wherever this report version put it."""
    status = data.get("execution_status")
    if status:
        return status
    summary = data.get("summary")
    if isinstance(summary, dict):
        return summary.get("execution_status")
    return None


def extract_issue_count(data: dict[str, Any]) -> int | None:
    for key in ("issue_count", "total_issues"):
        if isinstance(data.get(key), int):
            return data[key]
    if isinstance(data.get("issues"), list):
        return len(data["issues"])
    summary = data.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("issue_count"), int):
        return summary["issue_count"]
    return None


def run_cli_case(case: dict[str, Any], root: pathlib.Path, report_dir: pathlib.Path) -> dict[str, Any]:
    out_dir = report_dir / case["name"]
    cmd = [
        sys.executable, "-m", "geoqa", "validate",
        str((root / case["path"]).resolve()),
        "--profile", case.get("profile", "generic_quick"),
        "--report-path", str(out_dir),
    ]
    if case.get("low_resource"):
        cmd.append("--low-resource")
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    record: dict[str, Any] = {
        "name": case["name"],
        "command": " ".join(cmd),
        "returncode": proc.returncode,
    }
    report = report_dir / f"{case['name']}.json"
    problems: list[str] = []

    if proc.returncode != 0:
        problems.append(f"exit code {proc.returncode}: {proc.stderr.strip()[:300]}")
    if not report.exists() or report.stat().st_size == 0:
        problems.append("report missing or empty")
        record.update(status="FAIL", problems=problems)
        return record

    try:
        data = load_json(report)
    except json.JSONDecodeError as exc:
        problems.append(f"report is not valid JSON: {exc}")
        record.update(status="FAIL", problems=problems)
        return record

    status = extract_status(data)
    count = extract_issue_count(data)
    record.update(report=str(report), execution_status=status, issue_count=count)

    expected_status = case.get("expect_status", "full")
    if status != expected_status:
        problems.append(
            f"execution_status {status!r} != expected {expected_status!r}"
        )
    if "expect_issues" in case and count != case["expect_issues"]:
        problems.append(f"issue_count {count} != expected {case['expect_issues']}")

    record.update(status="PASS" if not problems else "FAIL", problems=problems)
    return record


def run_callable_case(case: dict[str, Any], root: pathlib.Path, report_dir: pathlib.Path) -> dict[str, Any]:
    """For validators with no CLI surface, e.g. the spectral dataset type."""
    target = case["python_callable"]
    if ":" not in target:
        raise ValueError(f"python_callable must be 'module:function', got {target!r}")
    module_name, _, func_name = target.partition(":")
    try:
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
    except Exception as exc:
        return {"name": case["name"], "status": "FAIL",
                "problems": [f"cannot load {target}: {exc}"]}
    try:
        func(report_dir)
    except Exception as exc:  # surface the failure rather than hiding it
        return {"name": case["name"], "status": "FAIL",
                "problems": [f"{type(exc).__name__}: {exc}"]}

    report = report_dir / f"{case['name']}.json"
    if not report.exists() or report.stat().st_size == 0:
        return {"name": case["name"], "status": "FAIL",
                "problems": ["callable did not write a report"]}
    try:
        data = load_json(report)
    except json.JSONDecodeError as exc:
        return {"name": case["name"], "status": "FAIL",
                "problems": [f"report is not valid JSON: {exc}"]}

    problems = []
    status = extract_status(data)
    count = extract_issue_count(data)
    if status != case.get("expect_status", "full"):
        problems.append(f"execution_status {status!r}")
    if "expect_issues" in case and count != case["expect_issues"]:
        problems.append(f"issue_count {count} != expected {case['expect_issues']}")
    return {"name": case["name"], "report": str(report), "execution_status": status,
            "issue_count": count, "status": "PASS" if not problems else "FAIL",
            "problems": problems}


def write_log(records: list[dict[str, Any]], report_dir: pathlib.Path, suite_name: str) -> None:
    csv_path = report_dir / "run_log.csv"
    fields = ["case", "status", "execution_status", "issue_count", "problems"]
    with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow({
                "case": rec.get("name", ""),
                "status": rec.get("status", ""),
                "execution_status": rec.get("execution_status", ""),
                "issue_count": rec.get("issue_count", ""),
                "problems": "; ".join(rec.get("problems", []) or []),
            })
    json_path = report_dir / "run_log.json"
    json_path.write_text(
        json.dumps(
            {
                "suite": suite_name,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "cases": records,
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )


def compare_baseline(records: list[dict[str, Any]], baseline: pathlib.Path) -> list[str]:
    base = load_json(baseline)
    base_cases = {c.get("name"): c for c in base.get("cases", [])}
    diffs = []
    for rec in records:
        ref = base_cases.get(rec.get("name"))
        if ref is None:
            diffs.append(f"{rec['name']}: not present in baseline")
            continue
        for field in ("status", "execution_status", "issue_count"):
            if ref.get(field) != rec.get(field):
                diffs.append(
                    f"{rec['name']}.{field}: baseline {ref.get(field)!r} "
                    f"!= current {rec.get(field)!r}"
                )
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("manifest", help="path to the suite manifest JSON")
    parser.add_argument("--out", default=None, help="report directory (default reports/<suite name>)")
    parser.add_argument("--baseline", default=None, help="run_log.json to compare against")
    parser.add_argument("--root", default=None, help="repository root (default: parent of scripts/)")
    args = parser.parse_args(argv)

    manifest_path = pathlib.Path(args.manifest).resolve()
    try:
        manifest = load_json(manifest_path)
    except FileNotFoundError:
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"manifest is not valid JSON: {exc}", file=sys.stderr)
        return 2

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        print("manifest must contain a non-empty 'cases' list", file=sys.stderr)
        return 2

    root = pathlib.Path(args.root).resolve() if args.root else \
        pathlib.Path(__file__).resolve().parents[1]
    suite_name = manifest.get("name") or manifest_path.stem
    report_dir = pathlib.Path(args.out).resolve() if args.out else root / "reports" / suite_name
    report_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for case in cases:
        if "python_callable" in case:
            record = run_callable_case(case, root, report_dir)
        else:
            record = run_cli_case(case, root, report_dir)
        records.append(record)
        mark = "PASS" if record["status"] == "PASS" else "FAIL"
        print(f"  [{mark}] {record['name']:<24} "
              f"status={record.get('execution_status')} "
              f"issues={record.get('issue_count')}")
        for problem in record.get("problems", []) or []:
            print(f"         - {problem}")

    write_log(records, report_dir, suite_name)
    failed = [r for r in records if r["status"] != "PASS"]

    print(f"\n{len(records) - len(failed)}/{len(records)} passed; log -> {report_dir}")

    if args.baseline:
        diffs = compare_baseline(records, pathlib.Path(args.baseline).resolve())
        if diffs:
            print("\nDISCREPANCY against baseline:")
            for d in diffs:
                print(f"  ! {d}")
            return 1
        print("\nbaseline MATCH")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())