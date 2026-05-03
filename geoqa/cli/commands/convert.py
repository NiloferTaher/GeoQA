from __future__ import annotations

import argparse

from geoqa.conversion import convert_vector_dataset


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("convert", help="Convert a vector dataset to another format.")
    parser.add_argument("input_path")
    parser.add_argument("output_path")
    parser.add_argument("--format", required=True, dest="output_format")
    parser.add_argument("--layer", default=None)
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    out = convert_vector_dataset(
        args.input_path,
        args.output_path,
        output_format=args.output_format,
        ogr_layer=args.layer,
    )
    print(f"Wrote {out}")
    return 0


__all__ = ["configure_parser"]
