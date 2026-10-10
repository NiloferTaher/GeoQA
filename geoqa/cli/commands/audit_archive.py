from __future__ import annotations

import argparse
import json
from pathlib import Path

from geoqa.audit_archive import run_audit_archive


def _load_expected_crs_config(path: str | None) -> str | None:
    if not path:
        return None
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            value = payload.get("expected_crs")
            return str(value) if value else None
    except Exception:
        pass
    for line in text.splitlines():
        if line.strip().startswith("expected_crs"):
            _, value = line.split(":", 1)
            return value.strip().strip("'\"") or None
    return None


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("audit-archive", help="Run a local audit over a ZIP, folder, or vector layer.")
    parser.add_argument("path", help="Path to ZIP, folder, Shapefile, GeoJSON, or GeoPackage.")
    parser.add_argument("--out", required=True, help="Output directory for JSON, Excel, and summary reports.")
    parser.add_argument("--profiles", default="auto", help="Use auto or an explicit GeoQA profile name.")
    parser.add_argument("--excel", action="store_true", help="Write a combined Excel audit workbook.")
    parser.add_argument("--json", action="store_true", help="Write one JSON report per validated layer.")
    parser.add_argument("--selected-layer", default=None, help="Validate only this layer path, name, or id.")
    parser.add_argument("--all-layers", action="store_true", help="Validate every detected layer.")
    parser.add_argument("--expected-crs", default=None, help="Configured authoritative CRS such as EPSG:32640.")
    parser.add_argument("--expected-crs-config", default=None, help="JSON or simple YAML file with expected_crs.")
    parser.add_argument("--sanitize", action="store_true", help="Avoid detailed local paths in workbook metadata.")
    parser.add_argument("--no-coordinates", action="store_true", help="Suppress row-level issue coordinates in workbook rows.")
    parser.add_argument("--public-demo-mode", action="store_true", help="Use sanitized public-demo metadata.")
    parser.add_argument("--write-fix-plan", action="store_true", help="Write a human-review fix plan note.")
    parser.add_argument("--apply-safe-fixes", action="store_true", help="Reserved for future explicit safe-fix workflows.")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    expected_crs = args.expected_crs or _load_expected_crs_config(args.expected_crs_config)
    write_excel = bool(args.excel or not args.json)
    write_json = bool(args.json or not args.excel)
    command = "geoqa audit-archive"
    result = run_audit_archive(
        args.path,
        output_dir=args.out,
        profiles=args.profiles,
        excel=write_excel,
        json_reports=write_json,
        selected_layer=args.selected_layer,
        all_layers=args.all_layers,
        expected_crs=expected_crs,
        sanitize=args.sanitize,
        no_coordinates=args.no_coordinates,
        public_demo_mode=args.public_demo_mode,
        write_fix_plan=args.write_fix_plan,
        apply_safe_fixes=args.apply_safe_fixes,
        command=command,
    )
    print(f"Detected {len(result.layers)} layer(s)")
    print(f"Validated {len(result.validated_results)} layer(s)")
    if result.excel_report:
        print(f"Excel report written to {result.excel_report}")
    for report_path in result.json_reports:
        print(f"JSON report written to {report_path}")
    print(f"Summary written to {result.summary_report}")
    if result.pdf_report:
        print(f"PDF summary written to {result.pdf_report}")
    return 0


__all__ = ["configure_parser", "run"]
