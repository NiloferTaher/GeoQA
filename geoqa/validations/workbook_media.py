"""Embedded and referenced media in a spreadsheet.

The general problem
-------------------
A spreadsheet is often used as more than a table: each row is a record and each
record carries an attached artefact that supports it. A photograph of the thing
being recorded. A scan of a document. A screenshot of a system state. A
signature. A field sketch.

The artefacts live in the workbook as embedded images, or as references to files
on disk, and in both cases the association between the artefact and the row it
belongs to is maintained by whatever last saved the file. Nothing enforces it.
So the same four questions apply regardless of what the artefact is:

1. Does every row that needs an artefact actually have one?
2. Is each artefact attached to the right row?
3. Is it legible enough to support the claim the row makes?
4. Is anything attached to nothing, or pointing at a file that is gone?

Design constraints
------------------
**No domain vocabulary.** Nothing here assumes any particular industry,
asset class or evidence type. Call the thing a *record* and its artefact an
*attachment*, and the same module serves a photographic survey, a document
register, a defect log or an inspection sheet.

**Legibility is measured in pixels, not opinion.** An attachment too small to
read cannot support a claim about what it shows. The threshold is a parameter
because what counts as legible depends on what is being claimed.

**Broken references are the common case.** A path to a file on a colleague's
machine does not survive being emailed. That is reported as missing, not
silently skipped.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "workbook_media"

#: Media parts inside the OOXML package that hold an image.
MEDIA_PREFIX = "xl/media/"

#: Drawing parts that anchor media to a cell.
DRAWING_PREFIX = "xl/drawings/"

#: Sheet relationships that point at a drawing.
SHEET_RELS = "xl/worksheets/_rels/"

#: Image formats OOXML can embed that no validator here can read pixels from.
UNREADABLE_FORMATS = frozenset({".emf", ".wmf"})

#: Formats the media probe cannot decode.
OPAQUE_FORMATS = frozenset({".emf", ".wmf", ".bin"})

#: Below this on its longest side an attachment cannot show detail.
DEFAULT_MIN_DIMENSION_PX = 120

#: Formula forms that reference an external file.
_FORMULA_REFERENCE = re.compile(
    r"""=\s*(?:IMAGE|HYPERLINK)\s*\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

#: Plain-text cell content that looks like a file path.
_PATH_REFERENCE = re.compile(
    r"""^(?:[A-Za-z]:)?[\\/][^\s"']+|^[A-Za-z]:\\[^;]+|\.{1,2}[\\/][^\s"']+""",
)

#: Image magic bytes, for the fallback that reads the package directly.
_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
)


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _import_openpyxl():
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "openpyxl is required for workbook media validation. "
            "Install with: pip install 'geoqa[excel]'"
        ) from exc
    return openpyxl


def detect_image_format(head: bytes) -> str | None:
    """Identify an image from its leading bytes, or ``None``."""
    for signature, name in _IMAGE_MAGIC:
        if head.startswith(signature):
            return name
    return None


@dataclass
class Attachment:
    """One artefact attached to, or referenced by, a worksheet row."""

    source: str
    #: 1-based worksheet row the artefact is anchored to, when it is embedded.
    row: int | None
    #: 1-based worksheet column, when known.
    column: int | None
    media_name: str | None
    image_format: str | None
    width_px: int | None = None
    height_px: int | None = None
    sha1: str | None = None
    byte_size: int | None = None
    #: Set when the attachment is a reference to a file rather than an embed.
    is_reference: bool = False
    reference_path: str | None = None
    reference_resolves: bool | None = None

    @property
    def longest_side(self) -> int:
        return max(self.width_px or 0, self.height_px or 0)

    @property
    def is_embedded(self) -> bool:
        return not self.is_reference

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "row": self.row,
            "column": self.column,
            "media": self.media_name,
            "format": self.image_format,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "bytes": self.byte_size,
            "sha1": self.sha1,
            "is_reference": self.is_reference,
            "reference_path": self.reference_path,
            "reference_resolves": self.reference_resolves,
        }


@dataclass
class MediaProfile:
    """What media a workbook holds, and how it attaches to rows."""

    path: str
    sheets: tuple[str, ...] = ()
    embedded: list[Attachment] = field(default_factory=list)
    referenced: list[Attachment] = field(default_factory=list)
    orphaned: list[Attachment] = field(default_factory=list)
    duplicates: list[tuple[str, str]] = field(default_factory=list)
    undecodable: list[str] = field(default_factory=list)
    #: Rows that carry an attachment.
    attached_rows: tuple[int, ...] = ()
    #: Number of data rows, excluding the header.
    total_rows: int = 0
    #: Highest worksheet row carrying data.
    last_row: int = 0

    @property
    def attachments(self) -> list[Attachment]:
        return self.embedded + self.referenced

    @property
    def attachment_count(self) -> int:
        return len(self.attachments)

    def rows_without_attachment(self) -> tuple[int, ...]:
        """Data rows carrying no attachment. Row 1 is the header, not a record."""
        attached = set(self.attached_rows)
        return tuple(
            row for row in range(2, self.last_row + 1) if row not in attached
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sheets": list(self.sheets),
            "embedded": len(self.embedded),
            "referenced": len(self.referenced),
            "orphaned": len(self.orphaned),
            "duplicates": len(self.duplicates),
            "undecodable": len(self.undecodable),
            "attachment_rows": list(self.attached_rows),
            "rows_without_attachment": list(self.rows_without_attachment()),
        }


def _media_parts(archive: zipfile.ZipFile) -> dict[str, tuple[int, bytes]]:
    """Media inside the package, with leading bytes and a content hash."""
    import hashlib

    parts: dict[str, tuple[int, bytes]] = {}
    for info in archive.infolist():
        if not info.filename.startswith(MEDIA_PREFIX) or info.is_dir():
            continue
        with archive.open(info) as handle:
            head = handle.read(32)
        parts[info.filename] = (info.file_size, head)
        parts[f"{info.filename}#sha1"] = (0, hashlib.sha1(
            archive.read(info.filename)
        ).hexdigest().encode("ascii"))
    return parts


def _anchor_position(anchor: Any) -> tuple[int | None, int | None]:
    """Row and column, 1-based, that a drawing anchor points at."""
    origin = getattr(anchor, "_from", None)
    if origin is None:
        return None, None
    row = getattr(origin, "row", None)
    column = getattr(origin, "col", None)
    return (
        int(row) + 1 if row is not None else None,
        int(column) + 1 if column is not None else None,
    )


def profile_workbook_media(
    path: str | Path,
    *,
    sheet: str | None = None,
    reference_root: str | Path | None = None,
) -> MediaProfile:
    """Inventory media in a workbook, embedded and referenced.

    Reads the OOXML package directly for the media parts, and openpyxl for the
    anchors, because openpyxl does not expose media it cannot decode and those
    are exactly the ones worth reporting.
    """
    openpyxl = _import_openpyxl()
    target = Path(path)
    profile = MediaProfile(path=str(target))

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        parts = _media_parts(archive)

    for name, (size, head) in parts.items():
        if name.endswith("#sha1"):
            continue
        suffix = PurePosixPath(name).suffix.lower()
        image_format = detect_image_format(head)
        if suffix in UNREADABLE_FORMATS or (image_format is None and suffix in OPAQUE_FORMATS):
            profile.undecodable.append(name)
        if name not in names:
            continue

    book = openpyxl.load_workbook(target, data_only=False, read_only=False)
    profile.sheets = tuple(book.sheetnames)
    worksheet = book[sheet] if sheet else book[book.sheetnames[0]]

    import hashlib

    seen: dict[str, str] = {}
    for image in getattr(worksheet, "_images", []):
        row, column = _anchor_position(getattr(image, "anchor", None))
        payload = b""
        try:
            ref = getattr(image, "ref", None)
            if isinstance(ref, str) and ref in parts:
                payload = parts[ref][0].to_bytes(8, "little")  # size only
        except Exception:
            payload = b""
        digest = None
        try:
            if hasattr(image, "_data"):
                digest = hashlib.sha1(image._data()).hexdigest()
        except Exception:
            digest = None

        attachment = Attachment(
            source=str(target),
            row=row,
            column=column,
            media_name=getattr(image, "path", None) or getattr(image, "ref", None),
            image_format=(getattr(image, "format", None) or "").lower() or None,
            width_px=getattr(image, "width", None),
            height_px=getattr(image, "height", None),
            sha1=digest,
        )
        profile.embedded.append(attachment)
        if digest:
            if digest in seen:
                profile.duplicates.append((digest, attachment.media_name or "?"))
            else:
                seen[digest] = attachment.media_name or "?"

    profile.orphaned.extend(a for a in profile.embedded if a.row is None)

    profile.referenced = _scan_references(worksheet, reference_root=reference_root)

    rows = worksheet.max_row or 0
    #: Number of data rows, excluding the header.
    profile.total_rows = max(0, rows - 1)
    #: Highest worksheet row carrying data.
    profile.last_row = max(0, rows)
    profile.attached_rows = tuple(
        sorted({a.row for a in profile.attachments if a.row is not None})
    )
    return profile


def _scan_references(worksheet: Any, *, reference_root: str | Path | None) -> list[Attachment]:
    """Find attachments referenced by path rather than embedded."""
    found: list[Attachment] = []

    for row in worksheet.iter_rows():
        for cell in row:
            value = cell.value
            if not isinstance(value, str):
                continue
            match = _FORMULA_REFERENCE.search(value)
            candidate = match.group(1) if match else None
            if candidate is None and _PATH_REFERENCE.match(value.strip()):
                candidate = value.strip()

            if not candidate:
                continue

            root = Path(reference_root) if reference_root else Path.cwd()
            resolved = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate)
            found.append(
                Attachment(
                    source=str(worksheet.parent.path) if hasattr(worksheet.parent, "path") else "",
                    row=cell.row,
                    column=cell.column,
                    media_name=Path(candidate).name,
                    image_format=Path(candidate).suffix.lower().lstrip(".") or None,
                    is_reference=True,
                    reference_path=candidate,
                    reference_resolves=resolved.exists(),
                )
            )
    return found


def validate_workbook_media(
    path: str | Path,
    *,
    sheet: str | None = None,
    key_column: str | None = None,
    expect_attachment_every_row: bool = False,
    min_dimension_px: int = DEFAULT_MIN_DIMENSION_PX,
    reference_root: str | Path | None = None,
) -> list[Any]:
    """Check that the artefacts a workbook's rows depend on are actually there.

    Conditions emitted
    ------------------
    ``workbook_media_missing_reference``
        A row references an attachment by path and that file does not exist.
        High: this is what happens when a workbook outlives the folder it was
        written against.
    ``workbook_media_orphaned``
        An attachment is embedded but anchored to no row, so it documents
        nothing. Medium.
    ``workbook_media_duplicate``
        The same image bytes appear more than once. Usually a copy-paste
        artefact, and usually two records pointing at one piece of evidence.
    ``workbook_media_below_legibility_threshold``
        An attachment is too small on its longest side to show the detail its
        row claims. High, because the row looks evidenced and is not.
    ``workbook_media_undecodable``
        An attachment is in a format no validator here can inspect, so it is
        unverified rather than checked.
    ``workbook_row_missing_attachment``
        A row carries no attachment. Only reported when the caller says one is
        expected, because plenty of spreadsheets need none.
    ``workbook_attachment_without_key``
        An attachment is anchored to a row with no value in the key column, so
        it cannot be traced back to a record. High.
    ``workbook_no_attachments``
        The workbook holds no media at all, which is worth knowing before
        concluding that evidence is missing.
    """
    profile = profile_workbook_media(path, sheet=sheet, reference_root=reference_root)
    issues: list[Any] = []

    for attachment in profile.referenced:
        if attachment.reference_resolves is False:
            issues.append(
                _issue(
                    "workbook_media_missing_reference", "high",
                    f"Row {attachment.row} references {attachment.reference_path!r}, which does "
                    "not exist. A path to a file on someone else's machine does not survive "
                    "the workbook being sent anywhere",
                    attachment.as_dict(),
                )
            )

    for attachment in profile.orphaned:
        issues.append(
            _issue(
                "workbook_media_orphaned", "medium",
                f"An attachment ({attachment.media_name}) is embedded but anchored to no row, "
                "so it does not support any record",
                attachment.as_dict(),
            )
        )

    for digest, media_name in profile.duplicates:
        issues.append(
            _issue(
                "workbook_media_duplicate", "medium",
                f"Identical image content appears more than once (first at {digest[:8]}, then "
                f"{media_name}). Two records may be pointing at one piece of evidence",
                {"sha1": digest, "media": media_name},
            )
        )

    for attachment in profile.attachments:
        if attachment.is_reference:
            continue
        if attachment.longest_side and attachment.longest_side < min_dimension_px:
            issues.append(
                _issue(
                    "workbook_media_below_legibility_threshold", "high",
                    f"Row {attachment.row} carries an attachment {attachment.width_px}x"
                    f"{attachment.height_px} px, under the {min_dimension_px} px threshold. "
                    "The row looks evidenced and is not readable",
                    attachment.as_dict(),
                )
            )

    for name in profile.undecodable:
        issues.append(
            _issue(
                "workbook_media_undecodable", "medium",
                f"Attachment {name} is in a format that cannot be inspected here, so it is "
                "unverified rather than checked",
                {"media": name},
            )
        )

    if key_column:
        openpyxl = _import_openpyxl()
        book = openpyxl.load_workbook(path, data_only=False, read_only=False)
        worksheet = book[sheet] if sheet else book[book.sheetnames[0]]
        headers = [str(c.value).strip() if c.value is not None else "" for c in next(worksheet.iter_rows(max_row=1))]
        if key_column not in headers:
            issues.append(
                _issue(
                    "workbook_media_unverifiable", "high",
                    f"Key column {key_column!r} is absent, so no attachment can be traced "
                    f"back to a record. Columns present: {', '.join(h for h in headers if h) or 'none'}",
                    {"column": key_column},
                )
            )
        else:
            key_index = headers.index(key_column)
            for attachment in profile.attachments:
                if attachment.row is None:
                    continue
                value = worksheet.cell(row=attachment.row, column=key_index + 1).value
                if value is None or str(value).strip() == "":
                    issues.append(
                        _issue(
                            "workbook_attachment_without_key", "high",
                            f"Row {attachment.row} carries an attachment but no value in "
                            f"{key_column!r}, so the evidence cannot be attributed to a record",
                            {**attachment.as_dict(), "key_column": key_column},
                        )
                    )

    if expect_attachment_every_row and profile.attachment_count:
        for row in profile.rows_without_attachment():
            if row <= 1:
                continue
            issues.append(
                _issue(
                    "workbook_row_missing_attachment", "high",
                    f"Row {row} carries no attachment, though attachments are declared "
                    "expected on every row. Either the evidence was never captured or it "
                    "was lost",
                    {"row": row},
                )
            )

    if not profile.attachments:
        issues.append(
            _issue(
                "workbook_no_attachments", "info",
                "The workbook holds no attachments at all. Worth establishing before "
                "concluding that supporting evidence is missing",
                {"path": profile.path},
            )
        )

    return issues


__all__ = [
    "DEFAULT_MIN_DIMENSION_PX",
    "DRAWING_PREFIX",
    "MEDIA_PREFIX",
    "OPAQUE_FORMATS",
    "PROBLEM_NAME",
    "SHEET_RELS",
    "UNREADABLE_FORMATS",
    "Attachment",
    "MediaProfile",
    "detect_image_format",
    "profile_workbook_media",
    "validate_workbook_media",
]