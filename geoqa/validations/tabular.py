"""Tabular validation for CSV and Excel, before anything spatial touches them.

Why this exists
---------------
A CSV or workbook is where a spatial dataset acquires its coordinates, and it is
where they quietly go wrong in ways that survive every downstream check because
the values still parse as numbers.

The specific failures this module exists to catch:

**Excel eats leading zeros.** An account, meter or licence number ``007123``
arrives as the number ``7123``. It still reads as a number, still joins, still
matches nothing at the other end. Nothing fails; the data is simply wrong.

**Excel eats long identifiers.** A 16-digit meter number pasted into a cell
becomes ``9.999999999999999E+14`` or rounds. Same cause, worse outcome.

**Dates are ambiguous.** ``03/04/2025`` is 3 April in most of the world and
4 March in the United States. Nothing in the file says which. A date column
read with the wrong convention is silently wrong on every row.

**A number and its text both parse.** ``00123`` as text is a valid identifier;
as an integer it is a different identifier. The reader decides, not the file.

Scope
-----
Deliberately not a general spreadsheet linter. Merged cells and hidden sheets
are reported only where they break machine reading, because a presentation
choice is not a data defect.

Design constraints
------------------
**Report what will be lost, not only what is wrong.** Leading-zero loss is the
headline condition, and it is reported per column with the sample values.

**Never silently fix.** A converter that repairs ``7123`` back to ``007123``
cannot know whether the original was ``7123`` or ``007123``. So this module
reports and leaves the decision alone.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "tabular_dataset"

#: Extensions treated as comma-separated text.
CSV_EXTENSIONS = (".csv", ".tsv", ".txt", ".psv")

#: Extensions treated as Excel workbooks.
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xltx", ".xltm")

#: Spreadsheet tokens that mean "no value". Comparing a column to zero because
#: some rows hold ``-9999`` is how a real reading gets erased. Stored lowercase;
#: compare with :func:`_is_null`.
NULL_TOKENS = frozenset({
    "", "-", "--", "---", "n/a", "na", "n.a.", "nan", "null", "none", "nil",
    "?", "unknown", "undefined", "#n/a", "#null!", "#value!",
})


def _is_null(value: Any) -> bool:
    """Is this cell value one of the many ways a spreadsheet says "nothing"?

    Case-insensitive and whitespace-tolerant, because ``N/A``, ``n/a`` and
    `` N/A `` are the same absence and a case-sensitive check misses two of
    the three.
    """
    if value is None:
        return True
    return str(value).strip().casefold() in NULL_TOKENS

#: Sentinel values used by instrument exports to mean "not measured".
SENTINEL_NEGATIVE = (-9999.0, -999.0, -99.0, -99999.0, -1.0e9)

#: Sheet-state flags that hide content from a default read.
HIDDEN_SHEET_STATES = frozenset({"hidden", "veryHidden"})


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _is_excel(path: str | Path) -> bool:
    return Path(path).suffix.lower() in EXCEL_EXTENSIONS


def _is_csv(path: str | Path) -> bool:
    return Path(path).suffix.lower() in CSV_EXTENSIONS


def _import_openpyxl():
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "openpyxl is required for Excel validation. Install with: pip install openpyxl"
        ) from exc
    return openpyxl


def _looks_like_identifier(name: str) -> bool:
    label = str(name).strip().lower()
    return any(
        token in label
        for token in (
            "id", "code", "account", "acct", "meter", "serial", "licence", "license",
            "ref", "number", "no.", "no", "pin", "tag", "asset", "customer",
        )
    )


def _looks_like_date(name: str) -> bool:
    label = str(name).strip().lower()
    return any(token in label for token in ("date", "day", "month", "year", "time", "period", "dt"))


def _looks_like_numeric_id(values: Sequence[str]) -> tuple[bool, list[str]]:
    """Do these all-numeric-looking values have a leading zero or unusual length?"""
    samples = [v for v in values if v and v not in NULL_TOKENS][:200]
    if len(samples) < 2:
        return False, []
    numeric = [v for v in samples if re.fullmatch(r"[+-]?\d+(\.\d+)?", v)]
    if len(numeric) < len(samples) * 0.9:
        return False, []
    leading_zero = [v for v in numeric if v.startswith("0") and len(v) > 1 and not v.startswith("0.")]
    lengths = {len(v) for v in numeric}
    over_15 = [v for v in numeric if len(v.replace(".", "")) > 15]
    return bool(leading_zero or over_15), (leading_zero + over_15)[:5]


def _parse_dates(values: Sequence[str]) -> tuple[bool, list[str]]:
    """Find slash or dash dates that are ambiguous between day-first and month-first."""
    ambiguous: list[str] = []
    pattern = re.compile(r"^(\d{1,4})[-/](\d{1,2})[-/](\d{1,4})$")
    for value in values:
        if _is_null(value):
            continue
        match = pattern.match(value.strip())
        if not match:
            continue
        groups = match.groups()
        # A four-digit leading component means the value is already year-first
        # and unambiguous. Check the text, not the parsed int.
        if len(groups[0]) == 4:
            continue
        first, second = int(groups[0]), int(groups[1])
        if first <= 12 and second <= 12 and first != second:
            ambiguous.append(value)
        if len(ambiguous) >= 5:
            break
    return bool(ambiguous), ambiguous


@dataclass
class ColumnProfile:
    """One column, described without judging it."""

    name: str
    row_count: int
    null_count: int
    unique_count: int
    sample_values: tuple[str, ...] = ()
    max_length: int = 0
    all_numeric: bool = False
    inferred_kind: str = "text"

    @property
    def null_fraction(self) -> float:
        return self.null_count / self.row_count if self.row_count else 0.0

    @property
    def is_identifier_like(self) -> bool:
        return _looks_like_identifier(self.name)

    @property
    def is_date_like(self) -> bool:
        return _looks_like_date(self.name)

    def as_dict(self) -> dict[str, Any]:
        return {
            "column": self.name,
            "rows": self.row_count,
            "nulls": self.null_count,
            "null_fraction": round(self.null_fraction, 4),
            "unique": self.unique_count,
            "max_length": self.max_length,
            "all_numeric": self.all_numeric,
            "inferred_kind": self.inferred_kind,
        }


@dataclass
class TabularProfile:
    """What a table is, before any condition is decided."""

    path: str
    kind: str
    sheets: tuple[str, ...] = ()
    rows: int = 0
    columns: tuple[ColumnProfile, ...] = ()
    delimiter: str | None = None
    encoding: str | None = None
    has_header: bool = True
    ragged_rows: int = 0
    merged_cells: int = 0
    hidden_sheets: tuple[str, ...] = ()
    hidden_rows: int = 0
    formula_cells: int = 0
    #: Images embedded in the workbook, with the row they are anchored to.
    embedded_images: int = 0

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "sheets": list(self.sheets),
            "rows": self.rows,
            "columns": [column.as_dict() for column in self.columns],
            "delimiter": self.delimiter,
            "encoding": self.encoding,
            "ragged_rows": self.ragged_rows,
            "merged_cells": self.merged_cells,
            "hidden_sheets": list(self.hidden_sheets),
            "hidden_rows": self.hidden_rows,
            "formula_cells": self.formula_cells,
            "embedded_images": self.embedded_images,
        }


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def _read_csv_text(path: Path) -> tuple[str, str | None, str]:
    raw = path.read_bytes()
    encoding: str | None = None
    for candidate in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(candidate), candidate, "bom" if raw[:3] == b"\xef\xbb\xbf" else "none"
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1", "undecodable"


def _sniff_delimiter(sample: str, suffix: str) -> str:
    if suffix == ".tsv":
        return "\t"
    if suffix == ".psv":
        return "|"
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        return ","


def _profile_columns(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> tuple[ColumnProfile, ...]:
    profiles: list[ColumnProfile] = []
    for index, name in enumerate(headers):
        values = [str(row[index]) if index < len(row) else "" for row in rows]
        populated = [v for v in values if not _is_null(v)]
        profiles.append(
            ColumnProfile(
                name=name,
                row_count=len(values),
                null_count=len(values) - len(populated),
                unique_count=len(set(populated)),
                sample_values=tuple(populated[:3]),
                max_length=max((len(v) for v in populated), default=0),
                all_numeric=bool(populated) and all(
                    re.fullmatch(r"[+-]?\d+(\.\d+)?", v) for v in populated
                ),
                inferred_kind="numeric" if populated and all(
                    re.fullmatch(r"[+-]?\d+(\.\d+)?", v) for v in populated
                ) else "text",
            )
        )
    return tuple(profiles)


def profile_tabular(path: str | Path, *, sheet: str | None = None, max_rows: int | None = 50_000) -> TabularProfile:
    """Describe a CSV or workbook. Reads structure, not data."""
    target = Path(path)

    if _is_excel(target):
        return _profile_excel(target, sheet=sheet)
    if _is_csv(target):
        return _profile_csv(target, max_rows=max_rows)
    raise ValueError(
        f"{target.name!r} is not a recognised tabular file. Expected one of "
        f"{', '.join(CSV_EXTENSIONS + EXCEL_EXTENSIONS)}"
    )


def _profile_csv(path: Path, *, max_rows: int | None = None) -> TabularProfile:
    text, encoding, _bom = _read_csv_text(path)
    delimiter = _sniff_delimiter(text[:8192], path.suffix.lower())
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    try:
        headers = [str(cell).strip() for cell in next(reader)]
    except StopIteration:
        return TabularProfile(path=str(path), kind="csv", rows=0, columns=(), delimiter=delimiter, encoding=encoding)

    rows: list[list[str]] = []
    ragged = 0
    width = len(headers)
    for record in reader:
        if not record or all(not cell.strip() for cell in record):
            continue
        if len(record) != width:
            ragged += 1
        rows.append(record)
        if max_rows is not None and len(rows) >= max_rows:
            break

    return TabularProfile(
        path=str(path),
        kind="csv",
        rows=len(rows),
        columns=_profile_columns(headers, rows),
        delimiter=delimiter,
        encoding=encoding,
        ragged_rows=ragged,
    )


def _profile_excel(path: Path, *, sheet: str | None = None) -> TabularProfile:
    openpyxl = _import_openpyxl()
    book = openpyxl.load_workbook(path, data_only=False, read_only=False)

    hidden = tuple(
        name for name in book.sheetnames
        if str(book[name].sheet_state).lower() in HIDDEN_SHEET_STATES
    )
    target_name = sheet or book.sheetnames[0]
    worksheet = book[target_name]

    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in next(worksheet.iter_rows(max_row=1))]

    rows: list[list[str]] = []
    ragged = 0
    formulas = 0
    width = len(headers)
    for record in worksheet.iter_rows(min_row=2, values_only=True):
        if record is None or all(value is None for value in record):
            continue
        rendered = ["" if value is None else str(value) for value in record]
        if len(rendered) != width:
            ragged += 1
        formulas += sum(1 for value in record if isinstance(value, str) and value.startswith("="))
        rows.append(rendered)

    hidden_rows = sum(
        1 for index, dimension in worksheet.row_dimensions.items() if dimension.hidden
    )

    return TabularProfile(
        path=str(path),
        kind="excel",
        sheets=tuple(book.sheetnames),
        rows=len(rows),
        columns=_profile_columns(headers, rows),
        merged_cells=len(worksheet.merged_cells.ranges),
        hidden_sheets=hidden,
        hidden_rows=hidden_rows,
        formula_cells=formulas,
        embedded_images=len(getattr(worksheet, "_images", [])),
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_tabular(
    path: str | Path,
    *,
    sheet: str | None = None,
    expected_columns: Sequence[str] | None = None,
    key_column: str | None = None,
    require_key: bool = False,
    max_rows: int | None = 50_000,
) -> list[Any]:
    """Report conditions that will corrupt or hide data downstream.

    Conditions emitted
    ------------------
    ``tabular_missing_header``
        The file has no header row, so columns will be named positionally.
    ``tabular_duplicate_header``
        Two columns share a name, so a lookup returns an arbitrary one.
    ``tabular_blank_header``
        A column has no name and will be imported as ``Unnamed: 3``.
    ``tabular_ragged_rows``
        Some rows have a different column count. High: the extra or missing
        values land in the wrong column without an error.
    ``tabular_identifier_leading_zero``
        An identifier-like column holds all-numeric values with a leading zero.
        Critical: reading it as a number destroys the identifier.
    ``tabular_identifier_numeric``
        An identifier-like column is numeric and long enough to lose precision.
        High: Excel renders these in scientific notation.
    ``tabular_ambiguous_date``
        A date column holds a value that means different days under day-first
        and month-first conventions. High, because it is wrong on every row.
    ``tabular_sentinel_values``
        Instrument sentinel values such as ``-9999`` are present. High: they
        are numeric and will silently enter a mean.
    ``tabular_empty_column``
        A column is entirely null.
    ``tabular_merged_cells``
        Merged cells make a column have a value only on its first row. High
        for any column a reader will group or filter on.
    ``tabular_hidden_sheet``
        A sheet is hidden and will not appear in a default read.
    ``tabular_hidden_rows``
        Rows are hidden and will not appear in a default read.
    ``tabular_formula_cells``
        Cells hold formulas. Their cached value is what a plain reader sees.
    ``tabular_missing_expected_column``
        A column the caller expected is absent.
    ``tabular_duplicate_key``
        A key column repeats a value, so a one-to-one join will fan out.
    ``tabular_missing_key``
        The declared key column is absent while ``require_key`` is set.
    """
    profile = profile_tabular(path, sheet=sheet, max_rows=max_rows)
    issues: list[Any] = []
    names = profile.column_names

    if not names:
        issues.append(
            _issue(
                "tabular_missing_header", "high",
                f"{Path(profile.path).name} has no readable header row, so columns will be "
                "named positionally and every downstream reference to a column name fails",
                {"path": profile.path},
            )
        )

    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    for name in duplicates:
        issues.append(
            _issue(
                "tabular_duplicate_header", "high",
                f"Column {name!r} appears {names.count(name)} times. A lookup by that name "
                "returns an arbitrary one of them",
                {"column": name, "occurrences": names.count(name)},
            )
        )

    for index, name in enumerate(names):
        if name:
            continue
        issues.append(
            _issue(
                "tabular_blank_header", "medium",
                f"Column {index} has no name and will be imported as an unnamed column. "
                "Any value in it has nothing to be referred to by",
                {"position": index},
            )
        )

    if profile.ragged_rows:
        issues.append(
            _issue(
                "tabular_ragged_rows", "high",
                f"{profile.ragged_rows} rows have a different column count from the header. "
                "The surplus or missing values shift into the neighbouring columns without "
                "raising an error",
                {"rows_affected": profile.ragged_rows, "columns": len(names)},
            )
        )

    for column in profile.columns:
        values = [str(v) for v in column.sample_values]
        if column.is_identifier_like and column.all_numeric:
            risky, samples = _looks_like_identifier_values(column)
            if risky and any(sample.startswith("0") for sample in samples):
                issues.append(
                    _issue(
                        "tabular_identifier_leading_zero", "critical",
                        f"Column {column.name!r} holds all-numeric identifier values with a "
                        f"leading zero (for example {', '.join(samples[:3])}). Reading this "
                        "column as a number destroys the identifier and the records will "
                        "never match the source system",
                        {"column": column.name, "samples": samples},
                    )
                )
            elif risky:
                issues.append(
                    _issue(
                        "tabular_identifier_numeric", "high",
                        f"Column {column.name!r} is an identifier held as a number with up to "
                        f"{column.max_length} digits. Spreadsheet software renders these in "
                        "scientific notation and rounds the low digits",
                        {"column": column.name, "max_length": column.max_length},
                    )
                )

        if column.is_date_like:
            ambiguous, samples = _parse_dates([str(v) for v in values])
            if not ambiguous and column.all_numeric:
                ambiguous, samples = _parse_dates(
                    [str(v) for v in column.sample_values]
                )
            if ambiguous:
                issues.append(
                    _issue(
                        "tabular_ambiguous_date", "high",
                        f"Column {column.name!r} holds dates such as {', '.join(samples)} that "
                        "mean a different day depending on whether they are read day-first or "
                        "month-first. Nothing in the file states which, so every such row is "
                        "silently wrong under one convention",
                        {"column": column.name, "samples": samples},
                    )
                )

        if column.all_numeric:
            sentinels = [
                str(v) for v in column.sample_values
                if float(v) in SENTINEL_NEGATIVE
            ]
            if sentinels:
                issues.append(
                    _issue(
                        "tabular_sentinel_values", "high",
                        f"Column {column.name!r} contains instrument sentinel values such as "
                        f"{', '.join(sentinels)}. They are ordinary numbers and will enter a "
                        "mean or a total unless they are excluded explicitly",
                        {"column": column.name, "samples": sentinels},
                    )
                )

        if column.row_count and column.null_count == column.row_count:
            issues.append(
                _issue(
                    "tabular_empty_column", "low",
                    f"Column {column.name!r} is empty in all {column.row_count} rows",
                    {"column": column.name},
                )
            )

    if profile.merged_cells:
        issues.append(
            _issue(
                "tabular_merged_cells", "high",
                f"The sheet has {profile.merged_cells} merged range(s). A merged cell stores "
                "its value only on the top-left cell, so every other row reads as empty and "
                "any group-by or filter over that column drops them",
                {"merged_ranges": profile.merged_cells},
            )
        )

    for name in profile.hidden_sheets:
        issues.append(
            _issue(
                "tabular_hidden_sheet", "high",
                f"Sheet {name!r} is hidden and will not appear in a default read. Whatever "
                "corrections it holds will look as though they were never made",
                {"sheet": name, "all_sheets": list(profile.sheets)},
            )
        )

    if profile.hidden_rows:
        issues.append(
            _issue(
                "tabular_hidden_rows", "medium",
                f"{profile.hidden_rows} row(s) are hidden and will not appear in a default read",
                {"hidden_rows": profile.hidden_rows},
            )
        )

    if profile.formula_cells:
        issues.append(
            _issue(
                "tabular_formula_cells", "medium",
                f"{profile.formula_cells} cell(s) hold formulas. A reader that does not "
                "evaluate them sees the last cached value, which may be out of date",
                {"formula_cells": profile.formula_cells},
            )
        )

    for expected in expected_columns or ():
        if expected not in names:
            issues.append(
                _issue(
                    "tabular_missing_expected_column", "high",
                    f"Expected column {expected!r} is absent. Columns present: "
                    f"{', '.join(n for n in names if n) or 'none'}",
                    {"column": expected, "present": [n for n in names if n]},
                )
            )

    if key_column:
        if key_column not in names:
            if require_key:
                issues.append(
                    _issue(
                        "tabular_missing_key", "critical",
                        f"Key column {key_column!r} is absent, so records cannot be matched "
                        "to anything. Nothing downstream can be reconciled",
                        {"column": key_column},
                    )
                )
        else:
            column = next(c for c in profile.columns if c.name == key_column)
            if column.unique_count < column.row_count - column.null_count:
                issues.append(
                    _issue(
                        "tabular_duplicate_key", "high",
                        f"Key column {key_column!r} has {column.unique_count} distinct values "
                        f"across {column.row_count - column.null_count} populated rows. A "
                        "one-to-one join against it will fan out and multiply records",
                        {"column": key_column, "unique": column.unique_count,
                         "populated": column.row_count - column.null_count},
                    )
                )

    return issues


def _looks_like_identifier_values(column: ColumnProfile) -> tuple[bool, list[str]]:
    """Re-check an identifier column for leading zeros or excessive length.

    ``ColumnProfile`` only keeps samples, so this re-reads the column values it
    holds and decides from those.
    """
    samples = [str(v) for v in column.sample_values]
    if not samples:
        return False, []
    numeric = [v for v in samples if re.fullmatch(r"[+-]?\d+(\.\d+)?", v)]
    if len(numeric) != len(samples):
        return False, []
    leading_zero = [v for v in numeric if v.startswith("0") and len(v) > 1 and not v.startswith("0.")]
    over_15 = [v for v in numeric if len(v.replace(".", "")) > 15]
    return bool(leading_zero or over_15), (leading_zero + over_15)[:5]


def read_csv_rows(path: str | Path, *, max_rows: int | None = None) -> list[dict[str, str]]:
    """Read a CSV as plain strings.

    Every value stays a string on purpose. Coercion is where leading zeros and
    long identifiers die, so the caller has to ask for it.
    """
    target = Path(path)
    text, _encoding, _bom = _read_csv_text(target)
    delimiter = _sniff_delimiter(text[:8192], target.suffix.lower())
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for record in reader:
        rows.append({str(k): ("" if v is None else str(v)) for k, v in record.items()})
        if max_rows is not None and len(rows) >= max_rows:
            break
    return rows


__all__ = [
    "CSV_EXTENSIONS",
    "EXCEL_EXTENSIONS",
    "HIDDEN_SHEET_STATES",
    "NULL_TOKENS",
    "PROBLEM_NAME",
    "SENTINEL_NEGATIVE",
    "ColumnProfile",
    "TabularProfile",
    "profile_tabular",
    "read_csv_rows",
    "validate_tabular",
]