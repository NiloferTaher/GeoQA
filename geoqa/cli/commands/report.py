from __future__ import annotations

import argparse
import json

from geoqa.reports.report_generator import format_summary_text, load_report, summarize_report


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("report", help="Summarize existing GeoQA reports.")
    report_subparsers = parser.add_subparsers(dest="report_command", required=True)

    summarize_parser = report_subparsers.add_parser("summarize", help="Summarize a report.")
    summarize_parser.add_argument("report_path")
    summarize_parser.add_argument("--json", action="store_true", dest="as_json")
    summarize_parser.set_defaults(handler=run_summarize)

    stats_parser = report_subparsers.add_parser("stats", help="Show report row count and summary.")
    stats_parser.add_argument("report_path")
    stats_parser.add_argument("--json", action="store_true", dest="as_json")
    stats_parser.set_defaults(handler=run_stats)


def run_summarize(args: argparse.Namespace) -> int:
    summary = summarize_report(args.report_path)
    if args.as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(format_summary_text(summary))
    return 0


def run_stats(args: argparse.Namespace) -> int:
    rows = load_report(args.report_path)
    payload = summarize_report(args.report_path)
    payload["row_count"] = len(rows)
    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_summary_text(payload))
        print(f"\nRow count: {payload['row_count']}")
    return 0


__all__ = ["configure_parser"]
