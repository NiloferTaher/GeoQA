from __future__ import annotations

import argparse
import json

from geoqa.execution import validate_dataset_with_profile
from geoqa.reports.report_generator import format_summary_text

from ._common import apply_low_resource_defaults, build_cache, build_limits, progress_printer_with_interval


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("benchmark", help="Run a validation benchmark summary.")
    parser.add_argument("path")
    parser.add_argument("--profile", default="generic_quick")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--thermal-profile", choices=("balanced", "cool", "strict"), default="balanced")
    parser.add_argument("--max-features", type=int, default=None)
    parser.add_argument("--max-size-mb", type=float, default=None)
    parser.add_argument("--cache", help="Persistent cache directory.")
    parser.add_argument("--cache-tag", default=None)
    parser.add_argument("--max-runtime-seconds", type=float, default=None)
    parser.add_argument("--max-issues", type=int, default=None)
    parser.add_argument("--stop-after-actionable", type=int, default=None)
    parser.add_argument("--progress-interval-seconds", type=float, default=None)
    parser.add_argument("--low-resource", action="store_true")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    apply_low_resource_defaults(args, command_name="benchmark")
    result = validate_dataset_with_profile(
        args.path,
        profile=args.profile,
        max_workers=args.max_workers,
        validation_chunk_size=args.chunk_size,
        sleep_between_validation_chunks_seconds=args.sleep,
        thermal_profile=args.thermal_profile,
        limits=build_limits(args),
        cache=build_cache(args),
        cache_tag=args.cache_tag,
        progress_callback=progress_printer_with_interval(args.progress, args.progress_interval_seconds),
        max_runtime_seconds=args.max_runtime_seconds,
        max_issues=args.max_issues,
        stop_after_actionable=args.stop_after_actionable,
        prefer_high_priority=bool(args.low_resource),
    )
    payload = {
        "dataset_path": result.dataset_path,
        "profile_name": result.profile_name,
        "duration_seconds": round(result.duration_seconds, 4),
        "feature_count": result.feature_count,
        "issue_count": len(result.issues),
        "suppressed_issue_count": len(result.suppressed_issues),
        "execution_status": result.execution_status,
        "execution_reason": result.execution_reason,
        "thermal_summary": result.thermal_summary,
        "summary": result.summary,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"Dataset: {result.dataset_path}")
    print(f"Profile: {result.profile_name}")
    print(f"Duration: {round(result.duration_seconds, 4)}s")
    print(f"Features: {result.feature_count}")
    print(f"Issues: {len(result.issues)}")
    print(f"Execution status: {result.execution_status}")
    print("")
    print(format_summary_text(result.summary))
    return 0


__all__ = ["configure_parser"]
