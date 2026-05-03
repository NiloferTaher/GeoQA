from __future__ import annotations

import argparse

from geoqa.cli.commands import benchmark, convert, profiles, report, validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geoqa", description="Deterministic geospatial QA engine.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate.configure_parser(subparsers)
    profiles.configure_parser(subparsers)
    convert.configure_parser(subparsers)
    report.configure_parser(subparsers)
    benchmark.configure_parser(subparsers)
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return int(handler(args) or 0)


main = run


__all__ = ["build_parser", "main", "run"]
