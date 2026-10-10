"""Tests for archive inspection before extraction.

The behaviour worth protecting: nothing is written, and an archive that would
damage the target directory or produce unreadable spatial data is reported
without being unpacked.
"""

from __future__ import annotations

import zipfile

import pytest

from geoqa.validations.archive import (
    ArchiveMember,
    detect_magic,
    looks_geospatial,
    member_suffix_candidates,
    open_member,
    plan_extraction,
    scan_archive,
    validate_archive,
)


def _names(issues):
    return [i.problem_name for i in issues]


def _zip(path, entries, *, compression=zipfile.ZIP_STORED, compresslevel=None):
    """Write a zip.

    ``writestr`` with a plain string name does not inherit ``compresslevel``, so
    compression is set on the archive itself and passed per member.
    """
    with zipfile.ZipFile(path, "w", compression=compression, compresslevel=compresslevel) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload, compresslevel=compresslevel)
    return path


def _text(path, entries):
    return _zip(path, {k: v.encode("utf-8") if isinstance(v, str) else v for k, v in entries.items()})


SHAPEFILE_MAGIC = b"\x00\x00\x27\x0a" + b"\x00" * 64
SQLITE_MAGIC = b"SQLite format 3\x00" + b"\x00" * 32


# --- what is inside ------------------------------------------------------------

def test_geospatial_members_are_identified(tmp_path):
    path = _text(
        tmp_path / "a.zip",
        {"roads.shp": SHAPEFILE_MAGIC, "roads.dbf": b"\x03", "notes.txt": b"hello"},
    )
    profile = scan_archive(path)
    assert [m.name for m in profile.geospatial_members] == ["roads.shp"]
    assert profile.member_count == 3


def test_looks_geospatial_by_extension():
    assert looks_geospatial("roads.shp")
    assert looks_geospatial("dem.tif")
    assert looks_geospatial("network.gpkg")
    assert not looks_geospatial("readme.txt")
    assert not looks_geospatial("photo.jpg")


def test_extension_is_a_claim_not_a_fact(tmp_path):
    """An HTML error page saved as .shp is the common Downloads failure."""
    path = _text(tmp_path / "bad.zip", {"roads.shp": b"<html>404 not found</html>"})
    issues = validate_archive(path)
    mismatch = next(i for i in issues if i.problem_name == "archive_content_mismatch")
    assert mismatch.to_dict()["detected"] == "xml"


def test_matching_content_is_not_reported(tmp_path):
    path = _text(tmp_path / "ok.zip", {"roads.shp": SHAPEFILE_MAGIC})
    assert "archive_content_mismatch" not in _names(validate_archive(path))


def test_magic_detection():
    assert detect_magic(SQLITE_MAGIC) == "sqlite"
    assert detect_magic(b"II*\x00") == "tiff"
    assert detect_magic(b"\x89HDF\r\n\x1a\n") == "hdf5"
    assert detect_magic(b"<xml/>") == "xml"
    assert detect_magic(b"random") == "unknown"


# --- extraction safety ---------------------------------------------------------

def test_path_traversal_is_critical(tmp_path):
    path = _text(tmp_path / "evil.zip", {"../../windows/system32/evil.dll": b"MZ"})
    issues = validate_archive(path)
    assert "archive_path_traversal" in _names(issues)
    issue = next(i for i in issues if i.problem_name == "archive_path_traversal")
    assert str(issue.severity) == "critical"


def test_absolute_path_is_critical(tmp_path):
    path = _text(tmp_path / "abs.zip", {"/etc/passwd": b"root"})
    assert "archive_absolute_path" in _names(validate_archive(path))


def test_windows_style_traversal_is_caught(tmp_path):
    """Backslashes are separators on Windows, so they traverse too."""
    path = _text(tmp_path / "win.zip", {"..\\..\\evil.txt": b"x"})
    assert "archive_path_traversal" in _names(validate_archive(path))


def test_decompression_bomb_is_flagged_on_ratio(tmp_path):
    path = _zip(
        tmp_path / "bomb.zip",
        {"big.txt": b"0" * (4 * 1024 * 1024)},
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    )
    issues = validate_archive(path, max_ratio=10.0)
    bomb = next(i for i in issues if i.problem_name == "archive_decompression_bomb")
    assert bomb.to_dict()["ratio"] > 10.0


def test_stored_member_is_not_a_bomb(tmp_path):
    path = _zip(tmp_path / "stored.zip", {"plain.txt": b"hello"})
    assert "archive_decompression_bomb" not in _names(validate_archive(path, max_ratio=5.0))


def test_total_size_limit(tmp_path):
    path = _zip(
        tmp_path / "big.zip",
        {"a.txt": b"0" * (2 * 1024 * 1024)},
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    )
    issues = validate_archive(path, max_total_bytes=1024, max_ratio=1e9)
    assert "archive_excessive_total_size" in _names(issues)


def test_duplicate_names_are_reported(tmp_path):
    with zipfile.ZipFile(tmp_path / "dup.zip", "w") as archive:
        archive.writestr("roads.shp", SHAPEFILE_MAGIC)
        archive.writestr("roads.shp", b"\x00" * 32)
    issues = validate_archive(tmp_path / "dup.zip")
    assert "archive_duplicate_member" in _names(issues)


def test_nested_archive_is_listed_not_opened(tmp_path):
    inner = _text(tmp_path / "inner.zip", {"roads.shp": SHAPEFILE_MAGIC})
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as target:
        target.writestr("bundle.zip", source.read("inner.zip") if False else open(inner, "rb").read())
    issues = validate_archive(outer)
    assert "archive_nested_archive" in _names(issues)


# --- will it load ----------------------------------------------------------------

def test_incomplete_shapefile_is_high(tmp_path):
    """A .shp with no .shx and .dbf cannot be opened at all."""
    path = _text(tmp_path / "half.zip", {"roads.shp": SHAPEFILE_MAGIC})
    issues = validate_archive(path)
    issue = next(i for i in issues if i.problem_name == "archive_incomplete_shapefile")
    assert str(issue.severity) == "high"
    assert set(issue.to_dict()["missing"]) == {".shx", ".dbf"}


def test_complete_shapefile_is_not_flagged(tmp_path):
    path = _text(
        tmp_path / "full.zip",
        {
            "roads.shp": SHAPEFILE_MAGIC,
            "roads.shx": b"\x00",
            "roads.dbf": b"\x03",
            "roads.prj": b"GEOGCS",
        },
    )
    assert "archive_incomplete_shapefile" not in _names(validate_archive(path))


def test_missing_crs_sidecar_is_opt_in(tmp_path):
    path = _text(
        tmp_path / "nocrs.zip",
        {"roads.shp": SHAPEFILE_MAGIC, "roads.shx": b"", "roads.dbf": b"\x03"},
    )
    assert "archive_vector_missing_crs" not in _names(validate_archive(path))
    assert "archive_vector_missing_crs" in _names(validate_archive(path, require_crs_sidecar=True))


def test_geopackage_is_not_demanded_a_prj(tmp_path):
    """A GeoPackage carries its CRS internally; demanding a .prj would be wrong."""
    path = _text(tmp_path / "g.zip", {"network.gpkg": SQLITE_MAGIC})
    assert "archive_vector_missing_crs" not in _names(validate_archive(path, require_crs_sidecar=True))


def test_archive_with_no_geospatial_content_is_informational(tmp_path):
    path = _text(tmp_path / "docs.zip", {"readme.txt": b"hello"})
    issue = next(i for i in validate_archive(path) if i.problem_name == "archive_no_geospatial_content")
    assert str(issue.severity) == "info"


def test_clean_archive_reports_no_serious_issues(tmp_path):
    path = _text(
        tmp_path / "clean.zip",
        {
            "roads.shp": SHAPEFILE_MAGIC,
            "roads.shx": b"\x00",
            "roads.dbf": b"\x03",
            "roads.prj": b"GEOGCS",
        },
    )
    serious = [i for i in validate_archive(path) if str(i.severity) in {"critical", "high"}]
    assert serious == []


# --- profile ----------------------------------------------------------------------

def test_safe_to_extract_is_false_for_traversal(tmp_path):
    path = _text(tmp_path / "evil.zip", {"../x.txt": b"x"})
    assert scan_archive(path).safe_to_extract is False


def test_safe_to_extract_is_true_for_clean(tmp_path):
    path = _text(tmp_path / "ok.zip", {"roads.shp": SHAPEFILE_MAGIC, "roads.dbf": b"\x03"})
    assert scan_archive(path).safe_to_extract is True


def test_summary_shape(tmp_path):
    path = _text(tmp_path / "a.zip", {"roads.shp": SHAPEFILE_MAGIC, "readme.txt": b"x"})
    summary = scan_archive(path).summary()
    assert summary["member_count"] == 2
    assert summary["safe_to_extract"] is True
    assert len(summary["geospatial_members"]) == 1


# --- plan ---------------------------------------------------------------------------

def test_plan_writes_nothing(tmp_path):
    destination = tmp_path / "out"
    path = _text(tmp_path / "a.zip", {"roads.shp": SHAPEFILE_MAGIC, "readme.txt": b"x"})
    plan_extraction(path, destination=destination)
    assert not destination.exists()


def test_plan_excludes_unsafe_members(tmp_path):
    path = _text(tmp_path / "a.zip", {"../evil.txt": b"x", "roads.shp": SHAPEFILE_MAGIC})
    plan = plan_extraction(path, destination=tmp_path / "out")
    assert [s["member"] for s in plan["selected"]] == ["roads.shp"]
    assert any(s["reason"] == "path_traversal" for s in plan["skipped"])


def test_plan_can_filter_by_kind(tmp_path):
    path = _text(tmp_path / "a.zip", {"roads.shp": SHAPEFILE_MAGIC, "readme.txt": b"x"})
    plan = plan_extraction(path, destination=tmp_path / "out", kinds=("vector",))
    assert [s["member"] for s in plan["selected"]] == ["roads.shp"]


def test_plan_destinations_stay_inside_the_root(tmp_path):
    destination = tmp_path / "out"
    path = _text(tmp_path / "a.zip", {"sub/roads.shp": SHAPEFILE_MAGIC})
    plan = plan_extraction(path, destination=destination)
    for entry in plan["selected"]:
        assert entry["destination"].startswith(str(destination.resolve()))


# --- reading without extraction -------------------------------------------------------

def test_member_can_be_read_without_extraction(tmp_path):
    payload = "id,name\n1,Muscat\n"
    path = _text(tmp_path / "a.zip", {"data.csv": payload})
    assert open_member(path, "data.csv").decode("utf-8") == payload


def test_sidecar_candidates_for_a_shapefile(tmp_path):
    names = member_suffix_candidates("data/roads.shp")
    assert "data/roads.shx" in names
    assert "data/roads.dbf" in names
    assert "data/roads.prj" in names


def test_member_ratio_is_infinite_for_empty_compressed(tmp_path):
    member = ArchiveMember("x.txt", compressed_size=0, uncompressed_size=100)
    assert member.ratio == float("inf")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_archive(tmp_path / "nope.zip")