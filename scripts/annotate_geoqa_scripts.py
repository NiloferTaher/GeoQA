from __future__ import annotations

import argparse
import ast
from pathlib import Path


COMMENT_BLOCK = (
    "# GeoQA Script\n"
    "# Base class: GeoQAScriptBase\n"
    "# ThermalGuard & optional startup diagnostic enabled.\n"
    "# Implement load_items() and process_item() only.\n\n"
)


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return None


def _uses_geoqa_script_base(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if _base_name(base) == "GeoQAScriptBase":
                return True
    return False


def _already_annotated(source: str) -> bool:
    lines = source.lstrip().splitlines()
    head = "\n".join(lines[:4])
    return "# GeoQA Script" in head and "GeoQAScriptBase" in head


def annotate_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if _already_annotated(source):
        return False
    if not _uses_geoqa_script_base(source):
        return False

    path.write_text(COMMENT_BLOCK + source, encoding="utf-8")
    return True


def scan_directory(root: Path) -> list[Path]:
    updated: list[Path] = []
    for path in root.rglob("*.py"):
        if path.is_file() and annotate_file(path):
            updated.append(path)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Annotate Python files that subclass GeoQAScriptBase."
    )
    parser.add_argument("directory", type=Path, help="Directory to scan recursively.")
    args = parser.parse_args()

    root = args.directory.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Directory not found: {root}")
        return 1

    updated = scan_directory(root)
    print(f"Annotated {len(updated)} file(s).")
    for path in updated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
