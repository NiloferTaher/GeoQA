"""Archive (ZIP) inspection and pre-extraction validation.

Why this exists
---------------
A directory of downloaded archives is a common way to acquire geospatial data
and an equally common way to acquire something that is not what the filename
claims. The expensive mistakes happen at extraction time: a zip-slip path
overwrites a file outside the target directory, a half a shapefile fails
halfway through a load, and a 4 GB member expands to fill a disk.

This module answers three questions without writing anything to disk:

1. **What is actually inside?** Member names, sizes, and what each one appears
   to be, cross-checked against its magic bytes rather than its extension.
2. **Is it safe to extract?** Path traversal, absolute paths, symlinks,
   encryption, decompression bombs, and duplicate names.
3. **Will it load?** A shapefile missing its ``.shx`` or ``.dbf``, a GeoJSON
   that is actually an HTML error page, a raster with no CRS.

Extraction itself stays an explicit, separate, opt-in step. Nothing here
writes to the filesystem.

Design constraints
------------------
**Extension is a claim, not a fact.** Every recognised geospatial extension is
checked against leading magic bytes. A ``.shp`` containing XML is reported.

**A shapefile is a set, not a file.** Four sidecars are mandatory. An archive
containing ``roads.shp`` and ``roads.dbf`` with no ``roads.shx`` cannot be
opened, and finding that out before extraction is the entire point.

**Decompression ratio is the bomb signal.** A member whose uncompressed size
exceeds a declared multiple of its compressed size is flagged on ratio alone,
before any write.

**Nested archives are reported, not followed.** An archive inside an archive is
listed; descending is the caller's decision.
"""

from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "archive_package"

#: Extensions this module recognises as geospatial, mapped to a coarse kind.
GEOSPATIAL_EXTENSIONS: dict[str, str] = {
    ".shp": "vector",
    ".shx": "vector_sidecar",
    ".dbf": "vector_sidecar",
    ".prj": "crs_sidecar",
    ".cpg": "encoding_sidecar",
    ".qpj": "crs_sidecar",
    ".sbn": "vector_sidecar",
    ".sbx": "vector_sidecar",
    ".shp.xml": "metadata_sidecar",
    ".geojson": "vector",
    ".json": "ambiguous",
    ".gml": "vector",
    ".kml": "vector",
    ".kmz": "archive",
    ".gpx": "vector",
    ".fgb": "vector",
    ".gpkg": "package",
    ".sqlite": "package",
    ".gdb": "package",
    ".tif": "raster",
    ".tiff": "raster",
    ".img": "raster",
    ".vrt": "raster",
    ".asc": "raster",
    ".hdf": "raster",
    ".h5": "raster",
    ".nc": "raster",
    ".las": "pointcloud",
    ".laz": "pointcloud",
    ".gz": "compressed",
    ".zip": "archive",
    ".7z": "archive",
    ".rar": "archive",
    ".tar": "archive",
    ".tgz": "archive",
}

#: Sidecars without which a shapefile cannot be opened.
SHAPEFILE_REQUIRED = (".shp", ".shx", ".dbf")

#: Sidecars a shapefile should carry but which are optional.
SHAPEFILE_RECOMMENDED = (".prj", ".cpg")

#: Sidecars that indicate a CRS was recorded at all.
CRS_SIDECAR_EXTENSIONS = (".prj", ".qpj")

#: Decompressed-to-compressed ratio above which a member is treated as a bomb.
DEFAULT_MAX_RATIO = 120.0

#: Uncompressed size, in bytes, above which a member is reported regardless of ratio.
DEFAULT_MAX_MEMBER_BYTES = 2 * 1024**3

#: Total uncompressed size, in bytes, above which the archive is reported.
DEFAULT_MAX_TOTAL_BYTES = 8 * 1024**3

#: Members with these extensions are inspected for credentials.
TEXTUAL_EXTENSIONS = (
    ".txt", ".csv", ".json", ".geojson", ".xml", ".yml", ".yaml",
    ".md", ".sql", ".ini", ".cfg", ".conf", ".env", ".sh", ".bat", ".ps1",
)

#: Leading magic bytes, longest first so prefixes are not shadowed.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"PK\x03\x04", "zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole2"),
    (b"\x89HDF\r\n\x1a\n", "hdf5"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"7z\xbc\xaf\x27\x1c", "7zip"),
    (b"Rar!\x1a\x07", "rar"),
    (b"SQLite format 3\x00", "sqlite"),
    (b"\x00\x00\x00\x0cjP", "gpkg_1_2_or_later"),
    (b"\x00\x00\x00\x14jP", "gpkg_1_0"),
    (b"\x00\x00\x1cjP", "gpkg_1_2_or_later"),
)


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _normalise(name: str) -> str:
    """Lowercase extension, treating multi-part extensions such as ``.shp.xml``."""
    lowered = name.lower()
    if lowered.endswith(".shp.xml"):
        return ".shp.xml"
    suffix = PurePosixPath(lowered).suffix
    return suffix or ""


def _classify(name: str) -> str:
    """What kind of thing this member claims to be, from its name."""
    extension = _normalise(name)
    if extension in GEOSPATIAL_EXTENSIONS:
        return GEOSPATIAL_EXTENSIONS[extension]
    return "other"


def looks_geospatial(name: str) -> bool:
    """Is this member name one that suggests geospatial content?"""
    return _classify(name) in {"vector", "raster", "package", "pointcloud", "archive"}


def detect_magic(head: bytes) -> str:
    """Identify a file from its leading bytes. ``"unknown"`` when unrecognised."""
    for signature, label in _MAGIC:
        if head.startswith(signature):
            return label
    stripped = head.lstrip()
    if stripped[:1] == b"<":
        return "xml"
    if stripped[:1] in (b"{", b"["):
        return "json_text"
    return "unknown"


def _is_plausible_for(extension: str, kind: str, magic: str | None) -> bool:
    """Does the detected content agree with the extension on the filename?

    Checked per extension rather than per kind, because the kind is too coarse:
    GML is XML and GeoJSON is JSON, so a text detection is correct for those
    but proves that a ``.shp`` is really an HTML error page.
    """
    if magic is None or magic == "unknown":
        return True
    #: Extensions that must be a specific binary container.
    strict: dict[str, tuple[str, ...]] = {
        ".shp": ("unknown",),
        ".shx": ("unknown",),
        ".dbf": ("unknown",),
        ".gpkg": ("sqlite", "gpkg_1_0", "gpkg_1_2_or_later"),
        ".sqlite": ("sqlite",),
        ".tif": ("tiff",),
        ".tiff": ("tiff",),
        ".hdf": ("hdf5",),
        ".h5": ("hdf5",),
        ".kmz": ("zip",),
        ".zip": ("zip",),
        ".7z": ("7zip",),
        ".gz": ("gzip",),
        ".png": ("png",),
        ".jpg": ("jpeg",),
    }
    allowed = strict.get(extension)
    if allowed is not None:
        return magic in allowed
    #: Text formats that legitimately detect as text.
    if extension in {".geojson", ".gml", ".kml", ".xml"}:
        return magic in {"xml", "json_text", "unknown"}
    if kind in {"vector", "raster", "package", "pointcloud"}:
        return magic not in {"zip", "7zip", "rar", "jpeg", "png", "gif"}
    return True


def _traversal_kind(name: str) -> str | None:
    """Classify a member name as unsafe. ``None`` when the name is acceptable."""
    if not name:
        return "empty_name"
    if name.startswith(("/", "\\")) or PureWindowsPath(name).is_absolute():
        return "absolute_path"
    normalised = name.replace("\\", "/")
    if normalised.startswith("/"):
        return "absolute_path"
    parts = [part for part in normalised.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return "path_traversal"
    if PurePosixPath(name).is_absolute():
        return "absolute_path"
    return None


@dataclass
class ArchiveMember:
    """One member of an archive, described without extracting it."""

    name: str
    compressed_size: int
    uncompressed_size: int
    is_dir: bool = False
    #: 0 when stored, otherwise the deflate level; surfaced for diagnosis only.
    compress_type: int = 0
    encrypted: bool = False
    crc: int = 0

    @property
    def extension(self) -> str:
        return _normalise(self.name)

    @property
    def kind(self) -> str:
        """What the name claims this member is."""
        return _classify(self.name)

    @property
    def is_geospatial(self) -> bool:
        return self.kind in {"vector", "raster", "package", "pointcloud"}

    @property
    def is_shapefile_sidecar(self) -> bool:
        return self.kind in {
            "vector_sidecar", "crs_sidecar", "encoding_sidecar", "metadata_sidecar"
        }

    @property
    def ratio(self) -> float:
        """Uncompressed bytes per compressed byte. 0.0 for stored members."""
        if not self.compressed_size:
            return float("inf") if self.uncompressed_size else 0.0
        return self.uncompressed_size / self.compressed_size

    @property
    def megabytes(self) -> float:
        return self.uncompressed_size / 1_048_576.0

    @property
    def stem(self) -> str:
        """Filename without its extension, used to group shapefile sidecars."""
        name = posixpath.basename(self.name.replace("\\", "/"))
        return posixpath.splitext(name)[0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "member": self.name,
            "kind": self.kind,
            "extension": self.extension,
            "geospatial": self.is_geospatial,
            "compressed_bytes": self.compressed_size,
            "uncompressed_bytes": self.uncompressed_size,
            "megabytes": round(self.megabytes, 3),
            "ratio": None if self.ratio == float("inf") else round(self.ratio, 2),
            "encrypted": self.encrypted,
        }


@dataclass
class ArchiveProfile:
    """What an archive contains, and whether it is safe to extract."""

    path: str
    members: list[ArchiveMember] = field(default_factory=list)
    #: Members whose content disagreed with their extension.
    mismatched: list[tuple[str, str]] = field(default_factory=list)
    #: ``(member, reason)`` for each unsafe name.
    unsafe_names: list[tuple[str, str]] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)
    nested_archives: list[str] = field(default_factory=list)
    unreadable: list[tuple[str, str]] = field(default_factory=list)
    shapefile_sets: dict[str, list[str]] = field(default_factory=dict)
    missing_sidecars: dict[str, list[str]] = field(default_factory=dict)
    no_crs_sidecar: list[str] = field(default_factory=list)
    total_uncompressed: int = 0
    total_compressed: int = 0

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def geospatial_members(self) -> list[ArchiveMember]:
        return [m for m in self.members if m.is_geospatial]

    @property
    def max_ratio(self) -> float:
        return max((m.ratio for m in self.members), default=0.0)

    @property
    def safe_to_extract(self) -> bool:
        """No traversal, no absolute paths, no bomb, nothing unreadable."""
        return not (
            self.unsafe_names
            or self.unreadable
            or self.max_ratio > DEFAULT_MAX_RATIO
            or self.total_uncompressed > DEFAULT_MAX_TOTAL_BYTES
        )

    def summary(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "member_count": self.member_count,
            "geospatial_members": [m.as_dict() for m in self.geospatial_members],
            "max_compression_ratio": round(self.max_ratio, 2) if self.max_ratio != float("inf") else None,
            "total_uncompressed_mb": round(self.total_uncompressed / 1_048_576.0, 2),
            "total_compressed_mb": round(self.total_compressed / 1_048_576.0, 2),
            "safe_to_extract": self.safe_to_extract,
            "shapefile_sets": {k: sorted(v) for k, v in self.shapefile_sets.items()},
        }


def _read_magic(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int = 64) -> bytes | None:
    """Leading bytes of a member, or ``None`` when it genuinely cannot be read.

    ``None`` means the archive is broken. An empty result means the member is
    empty. Neither should be conflated with "bytes I do not recognise".
    """
    try:
        with archive.open(info) as handle:
            return handle.read(limit)
    except (RuntimeError, zipfile.BadZipFile, OSError, EOFError, NotImplementedError):
        return None


def _is_encrypted(info: zipfile.ZipInfo) -> bool:
    return bool(info.flag_bits & 0x1)


def scan_archive(path: str | Path, *, check_content: bool = True) -> ArchiveProfile:
    """Inventory an archive without extracting anything.

    ``check_content`` reads at most the first 64 bytes of each member to compare
    its detected type against its extension. It never writes, and it never
    decompresses a member beyond that limit.
    """
    source = Path(path)
    profile = ArchiveProfile(path=str(source))

    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            member = ArchiveMember(
                name=info.filename,
                compressed_size=info.compress_size,
                uncompressed_size=info.file_size,
                is_dir=info.is_dir(),
                compress_type=info.compress_type,
                encrypted=_is_encrypted(info),
                crc=info.CRC,
            )
            profile.members.append(member)
            profile.total_uncompressed += member.uncompressed_size
            profile.total_compressed += member.compressed_size

            reason = _traversal_kind(info.filename)
            if reason:
                profile.unsafe_names.append((info.filename, reason))

            if not member.is_dir and member.kind == "archive":
                profile.nested_archives.append(info.filename)

            if check_content and not member.is_dir and member.uncompressed_size:
                head = _read_magic(archive, info)
                if head is None:
                    profile.unreadable.append((member.name, "member could not be decompressed"))
                    continue
                magic = detect_magic(head)
                if not _is_plausible_for(member.extension, member.kind, magic):
                    profile.mismatched.append((member.name, magic))

    seen: set[str] = set()
    for member in profile.members:
        if member.is_dir or not member.name:
            continue
        if member.name in seen:
            profile.duplicate_names.append(member.name)
        seen.add(member.name)

    _group_shapefiles(profile)
    return profile


def _group_shapefiles(profile: ArchiveProfile) -> None:
    """Group shapefile sidecars by stem and record what is missing."""
    for member in profile.members:
        if member.is_dir:
            continue
        extension = member.extension
        if extension in SHAPEFILE_REQUIRED or member.is_shapefile_sidecar:
            profile.shapefile_sets.setdefault(member.stem, []).append(extension)

    for stem, extensions in profile.shapefile_sets.items():
        present = set(extensions)
        if not present & set(SHAPEFILE_REQUIRED):
            continue
        missing = [ext for ext in SHAPEFILE_REQUIRED if ext not in present]
        if missing:
            profile.missing_sidecars[stem] = missing

    crs_sidecars = {m.stem for m in profile.members if m.extension in CRS_SIDECAR_EXTENSIONS}
    for member in profile.geospatial_members:
        if member.extension in CRS_SIDECAR_EXTENSIONS:
            continue
        if member.kind == "package":
            continue
        if member.stem not in crs_sidecars:
            profile.no_crs_sidecar.append(member.name)


def validate_archive(
    path: str | Path,
    *,
    check_content: bool = True,
    max_ratio: float = DEFAULT_MAX_RATIO,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    require_crs_sidecar: bool = False,
) -> list[Any]:
    """Report archive conditions, before anything is extracted.

    Conditions emitted
    ------------------
    ``archive_path_traversal``
        A member name escapes the extraction directory. Critical: extracting it
        writes outside the target.
    ``archive_absolute_path``
        A member name is absolute. Same consequence, reached differently.
    ``archive_unsafe_member_name``
        Another name that should not be written: empty, or a bare drive spec.
    ``archive_decompression_bomb``
        A member expands by more than ``max_ratio``, or past ``max_member_bytes``.
    ``archive_excessive_total_size``
        The archive as a whole expands past ``max_total_bytes``.
    ``archive_duplicate_member``
        Two members share a name. Most extractors silently keep the last one.
    ``archive_encrypted_member``
        A member is encrypted, so extraction will prompt or fail.
    ``archive_content_mismatch``
        The bytes do not match the extension, such as an HTML error page saved
        as ``.shp``.
    ``archive_member_unreadable``
        A member could not be opened or held no recognisable content.
    ``archive_incomplete_shapefile``
        A shapefile set is missing a required sidecar and will not open.
    ``archive_shapefile_missing_crs``
        A shapefile set has no ``.prj``, so its CRS is unknown.
    ``archive_vector_missing_crs``
        A vector file has no recorded CRS. Reported at ``require_crs_sidecar``.
    ``archive_nested_archive``
        An archive inside an archive, listed rather than descended.
    ``archive_no_geospatial_content``
        Nothing inside looks geospatial, so extracting it for survey work is
        wasted effort.
    """
    profile = scan_archive(path, check_content=check_content)
    issues: list[Any] = []

    for member_name, reason in profile.unsafe_names:
        if reason == "path_traversal":
            issues.append(
                _issue(
                    "archive_path_traversal",
                    "critical",
                    f"Member {member_name!r} traverses out of the extraction directory. "
                    "Extracting it writes outside the intended folder",
                    {"member": member_name, "reason": reason, "archive": profile.path},
                )
            )
        elif reason == "absolute_path":
            issues.append(
                _issue(
                    "archive_absolute_path",
                    "critical",
                    f"Member {member_name!r} is an absolute path. Extracting it writes "
                    "to that absolute location rather than inside the target folder",
                    {"member": member_name, "reason": reason, "archive": profile.path},
                )
            )
        else:
            issues.append(
                _issue(
                    "archive_unsafe_member_name",
                    "medium",
                    f"Member {member_name!r} has an unusable name ({reason})",
                    {"member": member_name, "reason": reason, "archive": profile.path},
                )
            )

    for member in profile.members:
        if member.is_dir:
            continue
        if member.ratio > max_ratio or member.uncompressed_size > max_member_bytes:
            issues.append(
                _issue(
                    "archive_decompression_bomb",
                    "high",
                    f"Member {member.name!r} expands {member.uncompressed_size / 1_048_576.0:.1f} MB "
                    f"from {member.compressed_size / 1_048_576.0:.2f} MB "
                    f"(ratio {member.ratio:.0f}:1). Treat it as untrusted until explained",
                    {
                        "member": member.name,
                        "ratio": round(member.ratio, 2) if member.ratio != float("inf") else None,
                        "uncompressed_bytes": member.uncompressed_size,
                        "compressed_bytes": member.compressed_size,
                    },
                )
            )
        if member.encrypted:
            issues.append(
                _issue(
                    "archive_encrypted_member",
                    "high",
                    f"Member {member.name!r} is encrypted; extraction will prompt for a "
                    "password or fail outright",
                    {"member": member.name},
                )
            )

    if profile.total_uncompressed > max_total_bytes:
        issues.append(
            _issue(
                "archive_excessive_total_size",
                "high",
                f"Archive expands to {profile.total_uncompressed / 1024**3:.2f} GB, above the "
                f"{max_total_bytes / 1024**3:.0f} GB limit for unattended extraction",
                {
                    "total_uncompressed_bytes": profile.total_uncompressed,
                    "limit_bytes": max_total_bytes,
                },
            )
        )

    for name in profile.duplicate_names:
        issues.append(
            _issue(
                "archive_duplicate_member",
                "medium",
                f"Member {name!r} appears more than once. Most extractors keep the last "
                "copy, so which one lands is decided silently",
                {"member": name},
            )
        )

    for member_name, magic in profile.mismatched:
        issues.append(
            _issue(
                "archive_content_mismatch",
                "high",
                f"Member {member_name!r} has a geospatial extension but its content is "
                f"{magic}, so it will not open as that format. A saved error page is the "
                "usual cause",
                {"member": member_name, "detected": magic},
            )
        )

    for member_name, reason in profile.unreadable:
        issues.append(
            _issue(
                "archive_member_unreadable",
                "medium",
                f"Member {member_name!r} could not be read ({reason})",
                {"member": member_name, "reason": reason},
            )
        )

    for stem, missing in profile.missing_sidecars.items():
        issues.append(
            _issue(
                "archive_incomplete_shapefile",
                "high",
                f"Shapefile set {stem!r} is missing {', '.join(missing)}. A shapefile "
                "needs all of .shp, .shx and .dbf before it can be opened",
                {"stem": stem, "missing": missing},
            )
        )

    if require_crs_sidecar:
        for member_name in profile.no_crs_sidecar:
            issues.append(
                _issue(
                    "archive_vector_missing_crs",
                    "medium",
                    f"{member_name!r} has no .prj or .qpj beside it, so the coordinate "
                    "reference system is unknown and coordinates cannot be trusted",
                    {"member": member_name},
                )
            )

    for name in profile.nested_archives:
        issues.append(
            _issue(
                "archive_nested_archive",
                "low",
                f"{name!r} is an archive inside an archive. It is listed but not opened; "
                "inspect it separately if its contents are needed",
                {"member": name},
            )
        )

    if not profile.geospatial_members:
        issues.append(
            _issue(
                "archive_no_geospatial_content",
                "info",
                f"Archive holds {profile.member_count} members and none is recognisably "
                "geospatial, so extracting it for spatial work will not help",
                {"member_count": profile.member_count},
            )
        )

    return issues


def open_member(path: str | Path, member_name: str) -> bytes:
    """Read one member into memory. For small files only.

    This is the bridge from "validated" to "actually checked": a CSV, GeoJSON
    or workbook inside an archive can be parsed without ever being written out.
    """
    with zipfile.ZipFile(Path(path)) as archive:
        with archive.open(member_name) as handle:
            return handle.read()


def member_suffix_candidates(member_name: str) -> tuple[str, ...]:
    """Other members that belong with this one, for set-based formats.

    For ``data/roads.shp`` this is every sibling sharing the stem that a reader
    needs, so a caller can extract a complete set in one call.
    """
    name = posixpath.basename(member_name.replace("\\", "/"))
    stem, _ = posixpath.splitext(name)
    directory = posixpath.dirname(member_name.replace("\\", "/"))
    siblings = [name]
    for extension in SHAPEFILE_REQUIRED + SHAPEFILE_RECOMMENDED + (".shp.xml",):
        siblings.append(f"{stem}{extension}")
    return tuple(f"{directory}/{sibling}" if directory else sibling for sibling in siblings)


def plan_extraction(
    path: str | Path,
    *,
    destination: str | Path,
    kinds: Sequence[str] | None = None,
    check_content: bool = True,
) -> dict[str, Any]:
    """Produce an extraction plan. Writes nothing.

    The plan names exactly which members would be written and where, after
    rejecting unsafe names. It is meant to be shown to a person before
    anything touches the filesystem, because the interesting outcome is
    usually "these three members and nothing else".
    """
    profile = scan_archive(path, check_content=check_content)
    root = Path(destination).resolve()

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for member in profile.members:
        if member.is_dir:
            continue
        reason = _traversal_kind(member.name)
        if reason:
            skipped.append({"member": member.name, "reason": reason})
            continue
        if kinds is not None and member.kind not in kinds:
            skipped.append({"member": member.name, "reason": f"kind {member.kind!r} not requested"})
            continue
        target = (root / member.name.replace("\\", "/")).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            skipped.append({"member": member.name, "reason": "resolves outside destination"})
            continue
        selected.append(
            {
                "member": member.name,
                "kind": member.kind,
                "geospatial": member.is_geospatial,
                "destination": str(target),
                "megabytes": round(member.megabytes, 3),
            }
        )

    return {
        "archive": profile.path,
        "destination": str(root),
        "safe_to_extract": profile.safe_to_extract,
        "selected": selected,
        "skipped": skipped,
        "would_write_bytes": sum(
            m.uncompressed_size for m in profile.members
            if m.name not in {s["member"] for s in skipped}
        ),
        "profile": profile.summary(),
    }


__all__ = [
    "CRS_SIDECAR_EXTENSIONS",
    "DEFAULT_MAX_MEMBER_BYTES",
    "DEFAULT_MAX_RATIO",
    "DEFAULT_MAX_TOTAL_BYTES",
    "GEOSPATIAL_EXTENSIONS",
    "PROBLEM_NAME",
    "SHAPEFILE_REQUIRED",
    "SHAPEFILE_RECOMMENDED",
    "TEXTUAL_EXTENSIONS",
    "ArchiveMember",
    "ArchiveProfile",
    "detect_magic",
    "looks_geospatial",
    "member_suffix_candidates",
    "open_member",
    "plan_extraction",
    "scan_archive",
    "validate_archive",
]