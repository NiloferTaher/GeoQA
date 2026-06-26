from __future__ import annotations

import argparse
import json
from pathlib import Path

from geoqa.execution import validate_dataset_with_profile

from ._common import apply_low_resource_defaults, build_cache, build_limits, progress_printer_with_interval


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("validate", help="Validate a dataset with a named profile.")
    parser.add_argument("path", help="Dataset path.")
    parser.add_argument("--profile", default="generic_quick", help="GeoQA validation profile name.")
    parser.add_argument("--expected-crs", default=None, help="Configured authoritative CRS such as EPSG:32640.")
    parser.add_argument("--output-format", choices=("json", "csv"), default="json")
    parser.add_argument("--report-path", help="Output path without extension.")
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
    parser.add_argument("--fail-on-error", action="store_true")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    apply_low_resource_defaults(args, command_name="validate")
    result = validate_dataset_with_profile(
        args.path,
        profile=args.profile,
        expected_crs=args.expected_crs,
        output_format=args.output_format if args.report_path else None,
        report_path=args.report_path,
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
    print(f"Loaded {result.feature_count} features")
    print(f"Detected {len(result.issues)} issues")
    print(f"Execution status: {result.execution_status}")
    if result.execution_reason:
        print(f"Execution reason: {result.execution_reason}")
    if result.report_path:
        print(f"Report written to {result.report_path}")
    print(json.dumps(result.summary, indent=2, ensure_ascii=False))
    if args.fail_on_error and result.issues:
        return 2
    return 0


__all__ = ["configure_parser", "run"]
