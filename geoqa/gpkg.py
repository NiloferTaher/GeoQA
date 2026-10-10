"""GeoPackage structure, inspection and writing.

Why this exists
---------------
A GeoPackage is a SQLite database with a specification laid over it, and most of
the specification lives in tables that nothing checks at read time. A file
missing ``gpkg_geometry_columns`` opens fine in QGIS and fails in the next tool
that reads the standard. A layer whose SRS is not in ``gpkg_spatial_ref_sys``
opens with an assumed CRS and nobody notices.

So the useful question is not "does it open here" but "is it conformant",
because conformance is what makes it portable to the tool you have not met yet.

Scope
-----
Structural conformance and inventory. Feature-level geometry, attribute and
topology checks are the existing validators; this module hands them a layer once
it knows the file is sound.

Design constraints
------------------
**Read-only.** The database is opened through a ``mode=ro`` URI. Inspecting a
GeoPackage must never be able to modify it, because the inspection is
automated and the file is someone's work.

**No GDAL required.** Conformance is checked against the specification's own
tables, so this works where GDAL is absent and cannot be fooled by a driver
being lenient.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "geopackage_structure"

#: ``application_id`` every conformant GeoPackage carries, as an integer.
GPKG_APPLICATION_ID = 0x47504B47

#: Human-readable form of the same value.
GPKG_APPLICATION_ID_TEXT = "GPKG"

#: Minimum ``user_version`` for the 1.2 specification.
GPKG_MIN_USER_VERSION = 10200

#: Specification versions this module recognises.
GPKG_KNOWN_VERSIONS = {
    10200: "1.0/1.1",
    10300: "1.2",
    10400: "1.3",
}

#: Tables the specification requires in every GeoPackage.
REQUIRED_TABLES = ("gpkg_spatial_ref_sys", "gpkg_contents")

#: Tables required once the file carries vector or tile content.
VECTOR_TABLES = ("gpkg_geometry_columns",)

#: Optional but expected tables.
OPTIONAL_TABLES = (
    "gpkg_tile_matrix_set",
    "gpkg_tile_matrix",
    "gpkg_extensions",
    "gpkg_data_columns",
    "gpkg_ogr_contents",
)

#: SRS identifiers the specification requires to be present.
REQUIRED_SRS = (
    (0, "Undefined cartesian"),
    (0, "Undefined geographic"),
    (4326, "WGS 84"),
    (3857, "Pseudo-Mercator"),
)

#: Geometry type to storage column expectations.
GEOMETRY_STORAGE = {
    "POINT": "POINT",
    "LINESTRING": "LINESTRING",
    "POLYGON": "POLYGON",
    "MULTIPOINT": "MULTIPOINT",
    "MULTILINESTRING": "MULTILINESTRING",
    "MULTIPOLYGON": "MULTIPOLYGON",
    "GEOMETRYCOLLECTION": "GEOMETRYCOLLECTION",
}


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .validations.base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open a GeoPackage without any possibility of writing to it."""
    uri = f"file:{path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


@dataclass
class GpkgLayer:
    """One feature table registered in ``gpkg_contents``."""

    name: str
    table: str
    data_type: str
    identifier: str
    srs_id: int | None
    min_x: float | None
    min_y: float | None
    max_x: float | None
    max_y: float | None
    geometry_column: str | None = None
    geometry_type: str | None = None
    z: int | None = None
    m: int | None = None
    srs_name: str | None = None
    srs_organization: str | None = None
    feature_count: int | None = None
    columns: tuple[str, ...] = ()
    has_spatial_index: bool = False
    declared_extent: bool = True

    @property
    def is_vector(self) -> bool:
        return self.data_type.lower() == "features"

    @property
    def is_tiled(self) -> bool:
        return self.data_type.lower() in {"tiles", "tiledgriddedcoverage"}

    @property
    def extent(self) -> tuple[float, float, float, float] | None:
        if None in (self.min_x, self.min_y, self.max_x, self.max_y):
            return None
        return (self.min_x, self.min_y, self.max_x, self.max_y)

    def as_dict(self) -> dict[str, Any]:
        return {
            "layer": self.name,
            "table": self.table,
            "data_type": self.data_type,
            "identifier": self.identifier,
            "srs_id": self.srs_id,
            "srs_name": self.srs_name,
            "geometry_column": self.geometry_column,
            "geometry_type": self.geometry_type,
            "features": self.feature_count,
            "columns": list(self.columns),
            "has_spatial_index": self.has_spatial_index,
            "declared_extent": self.declared_extent,
        }


@dataclass
class GpkgProfile:
    """What a GeoPackage is, structurally."""

    path: str
    application_id: int | None = None
    user_version: int | None = None
    tables: tuple[str, ...] = ()
    layers: list[GpkgLayer] = field(default_factory=list)
    srs_ids: tuple[int, ...] = ()
    file_bytes: int = 0

    @property
    def is_geopackage(self) -> bool:
        return self.application_id == GPKG_APPLICATION_ID

    @property
    def specification(self) -> str | None:
        return GPKG_KNOWN_VERSIONS.get(self.user_version or -1)

    @property
    def vector_layers(self) -> tuple[GpkgLayer, ...]:
        return tuple(layer for layer in self.layers if layer.is_vector)

    @property
    def layer_names(self) -> tuple[str, ...]:
        return tuple(layer.name for layer in self.layers)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "application_id": self.application_id,
            "is_geopackage": self.is_geopackage,
            "user_version": self.user_version,
            "specification": self.specification,
            "tables": list(self.tables),
            "layers": [layer.as_dict() for layer in self.layers],
            "megabytes": round(self.file_bytes / 1_048_576.0, 3),
        }


def _table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _srs_lookup(connection: sqlite3.Connection) -> dict[int, tuple[str | None, str | None]]:
    try:
        rows = connection.execute(
            "SELECT srs_id, srs_name, organization FROM gpkg_spatial_ref_sys"
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {int(row[0]): (row[1], row[2]) for row in rows}


def _has_spatial_index(connection: sqlite3.Connection, table: str, column: str | None) -> bool:
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rtree%'"
        ).fetchall()
    except sqlite3.Error:
        return False
    names = {str(row[0]) for row in rows}
    if not column:
        return any(name.startswith(f"rtree_{table}_") for name in names)
    return f"rtree_{table}_{column}" in names


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    try:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error:
        return ()
    return tuple(str(row[1]) for row in rows)


def _count_rows(connection: sqlite3.Connection, table: str) -> int | None:
    try:
        return int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
    except sqlite3.Error:
        return None


def profile_gpkg(path: str | Path) -> GpkgProfile:
    """Inspect a GeoPackage structurally. Never writes.

    Raises ``ValueError`` if the file is not a SQLite database at all, because
    there is nothing further to inspect and guessing would be misleading.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(target)

    profile = GpkgProfile(path=str(target), file_bytes=target.stat().st_size)

    try:
        connection = _connect_readonly(target)
    except sqlite3.Error as exc:
        raise ValueError(f"{target.name!r} is not a readable SQLite database") from exc

    with connection:
        try:
            profile.user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            raw_id = connection.execute("PRAGMA application_id").fetchone()[0]
            profile.application_id = int(raw_id) & 0xFFFFFFFF if raw_id else 0
        except sqlite3.Error:
            return profile

        profile.tables = _table_names(connection)
        if not profile.is_geopackage:
            return profile

        srs = _srs_lookup(connection)
        profile.srs_ids = tuple(sorted(srs))

        geometry_columns: dict[str, tuple[str, str | None, int | None, int | None]] = {}
        if "gpkg_geometry_columns" in profile.tables:
            try:
                for row in connection.execute(
                    "SELECT table_name, column_name, geometry_type_name, z, m "
                    "FROM gpkg_geometry_columns"
                ):
                    geometry_columns[str(row[0])] = (
                        str(row[1]), row[2], row[3], row[4]
                    )
            except sqlite3.Error:
                pass

        if "gpkg_contents" in profile.tables:
            try:
                for row in connection.execute(
                    "SELECT table_name, data_type, identifier, srs_id, "
                    "min_x, min_y, max_x, max_y "
                    "FROM gpkg_contents"
                ):
                    table = str(row[0])
                    geometry = geometry_columns.get(table)
                    srs_id = int(row[3]) if row[3] is not None else None
                    srs_name, srs_org = srs.get(srs_id, (None, None)) if srs_id is not None else (None, None)
                    extent_values = tuple(row[4:8])
                    profile.layers.append(
                        GpkgLayer(
                            name=table,
                            table=table,
                            data_type=str(row[1]),
                            identifier=str(row[2]),
                            srs_id=srs_id,
                            min_x=extent_values[0],
                            min_y=extent_values[1],
                            max_x=extent_values[2],
                            max_y=extent_values[3],
                            geometry_column=geometry[0] if geometry else None,
                            geometry_type=geometry[1] if geometry else None,
                            z=geometry[2] if geometry else None,
                            m=geometry[3] if geometry else None,
                            srs_name=srs_name,
                            srs_organization=srs_org,
                            feature_count=_count_rows(connection, table),
                            columns=_table_columns(connection, table),
                            has_spatial_index=_has_spatial_index(
                                connection, table, geometry[0] if geometry else None
                            ),
                            declared_extent=all(v is not None for v in extent_values),
                        )
                    )
            except sqlite3.Error:
                pass

    return profile


def list_gpkg_layers(path: str | Path) -> tuple[str, ...]:
    """Names of the layers a GeoPackage declares."""
    return profile_gpkg(path).layer_names


def validate_gpkg(path: str | Path, *, require_spatial_index: bool = False) -> list[Any]:
    """Report structural nonconformance in a GeoPackage.

    Conditions emitted
    ------------------
    ``geopackage_not_conformant``
        The file lacks the GeoPackage ``application_id``. Critical: it is a
        SQLite database, but not one anything can recognise as spatial.
    ``geopackage_unsupported_version``
        ``user_version`` is below the specification minimum or unrecognised.
    ``geopackage_missing_required_table``
        A table the specification requires is absent.
    ``geopackage_missing_required_srs``
        A spatial reference system the specification requires is not defined.
    ``geopackage_layer_missing_geometry_record``
        A feature layer has no row in ``gpkg_geometry_columns``. High: readers
        that follow the standard cannot find its geometry.
    ``geopackage_layer_srs_undeclared``
        A layer's SRS is not defined in ``gpkg_spatial_ref_sys``, so its
        coordinates will be interpreted against an assumption.
    ``geopackage_layer_no_crs``
        A feature layer declares SRS 0 or none. Critical: coordinates have no
        known reference system.
    ``geopackage_layer_without_primary_key``
        A feature table has no primary key. The specification requires one.
    ``geopackage_layer_extent_undeclared``
        A layer's extent is not declared, so the file does not say what it covers.
    ``geopackage_layer_missing_spatial_index``
        A feature layer has no RTree index. Reported on request, because its
        absence is a performance matter rather than a correctness one.
    ``geopackage_empty``
        The file declares no layers at all.
    """
    profile = profile_gpkg(path)
    issues: list[Any] = []

    if not profile.is_geopackage:
        return [
            _issue(
                "geopackage_not_conformant", "critical",
                f"{Path(profile.path).name!r} is a SQLite database but its application_id "
                f"is {profile.application_id:#x}, not {GPKG_APPLICATION_ID_TEXT}. It is not "
                "a GeoPackage, so any tool reading it as one is guessing",
                {
                    "application_id": profile.application_id,
                    "expected": GPKG_APPLICATION_ID_TEXT,
                    "tables": list(profile.tables)[:20],
                },
            )
        ]

    if profile.user_version is None or profile.user_version < GPKG_MIN_USER_VERSION:
        issues.append(
            _issue(
                "geopackage_unsupported_version", "high",
                f"user_version is {profile.user_version}, below the GeoPackage minimum of "
                f"{GPKG_MIN_USER_VERSION}. Tools may refuse the file or read only part of it",
                {"user_version": profile.user_version, "minimum": GPKG_MIN_USER_VERSION},
            )
        )
    elif profile.user_version not in GPKG_KNOWN_VERSIONS:
        issues.append(
            _issue(
                "geopackage_unsupported_version", "low",
                f"user_version {profile.user_version} is newer than any specification this "
                "module knows. It is probably fine, but conformance has not been checked "
                "against a published definition",
                {"user_version": profile.user_version},
            )
        )

    for required in REQUIRED_TABLES:
        if required not in profile.tables:
            issues.append(
                _issue(
                    "geopackage_missing_required_table", "critical",
                    f"Required table {required!r} is absent, so this file is not a "
                    "conformant GeoPackage however it opens",
                    {"table": required, "present": list(profile.tables)[:30]},
                )
            )

    for srs_id, description in REQUIRED_SRS:
        if srs_id not in profile.srs_ids and srs_id != 0:
            issues.append(
                _issue(
                    "geopackage_missing_required_srs", "medium",
                    f"Required spatial reference system {srs_id} ({description}) is not "
                    "defined in gpkg_spatial_ref_sys",
                    {"srs_id": srs_id, "description": description},
                )
            )

    if not profile.layers:
        issues.append(
            _issue(
                "geopackage_empty", "medium",
                "The GeoPackage declares no layers in gpkg_contents. An empty package is "
                "valid but carries no data, and is indistinguishable from a failed export",
                {"path": profile.path},
            )
        )

    for layer in profile.layers:
        if not layer.is_vector:
            continue

        if layer.geometry_column is None:
            issues.append(
                _issue(
                    "geopackage_layer_missing_geometry_record", "high",
                    f"Feature layer {layer.name!r} has no row in gpkg_geometry_columns, so a "
                    "standards-compliant reader cannot locate its geometry column. It opens in "
                    "QGIS because QGIS tolerates this; it does not open everywhere",
                    {"layer": layer.name, "table": layer.table},
                )
            )

        if layer.srs_id is None or layer.srs_id == 0:
            issues.append(
                _issue(
                    "geopackage_layer_no_crs", "critical",
                    f"Feature layer {layer.name!r} declares no coordinate reference system "
                    f"(srs_id {layer.srs_id}). Its coordinates have no known meaning and any "
                    "measurement taken from them is wrong",
                    {"layer": layer.name, "srs_id": layer.srs_id},
                )
            )
        elif layer.srs_id not in profile.srs_ids:
            issues.append(
                _issue(
                    "geopackage_layer_srs_undeclared", "high",
                    f"Feature layer {layer.name!r} uses SRS {layer.srs_id} but that system is "
                    "not defined in gpkg_spatial_ref_sys, so readers must assume rather than "
                    "look up",
                    {"layer": layer.name, "srs_id": layer.srs_id},
                )
            )

        columns = layer.columns
        if columns:
            primary_keys = _primary_keys(path, layer.table)
            if not primary_keys:
                issues.append(
                    _issue(
                        "geopackage_layer_without_primary_key", "high",
                        f"Feature table {layer.table!r} has no primary key. The GeoPackage "
                        "specification requires one, and without it rows cannot be "
                        "identified across updates",
                        {"layer": layer.name, "table": layer.table},
                    )
                )

        if not layer.declared_extent:
            issues.append(
                _issue(
                    "geopackage_layer_extent_undeclared", "medium",
                    f"Layer {layer.name!r} has no declared extent, so the file does not state "
                    "what area it covers. Consumers cannot check a layer against an area of "
                    "interest without reading every row",
                    {"layer": layer.name},
                )
            )

        if require_spatial_index and not layer.has_spatial_index:
            issues.append(
                _issue(
                    "geopackage_layer_missing_spatial_index", "low",
                    f"Feature layer {layer.name!r} has no RTree spatial index. Correct, but "
                    "spatial predicates will scan the whole table",
                    {"layer": layer.name},
                )
            )

    return issues


def _primary_keys(path: str | Path, table: str) -> tuple[str, ...]:
    try:
        connection = _connect_readonly(Path(path))
    except sqlite3.Error:
        return ()
    with connection:
        try:
            rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        except sqlite3.Error:
            return ()
    return tuple(str(row[1]) for row in rows if int(row[5]) > 0)


def read_gpkg_layer(path: str | Path, layer: str) -> Any:
    """Read one layer out of a GeoPackage as a GeoDataFrame."""
    import geopandas as gpd

    return gpd.read_file(path, layer=layer)


def write_gpkg_bundle(
    layers: Mapping[str, Any],
    directory: str | Path,
    *,
    filename: str = "bundle.gpkg",
    manifest: Mapping[str, Any] | None = None,
    create_spatial_index: bool = True,
) -> dict[str, Any]:
    """Write several layers into one GeoPackage with a manifest beside it.

    Used to deliver validation findings plus the context needed to read them:
    the findings, the layers that produced them, and the run manifest. One file
    means one thing to hand over.
    """
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    gpkg = destination / filename

    written: list[str] = []
    counts: dict[str, int] = {}

    for layer_name, frame in layers.items():
        if frame is None or getattr(frame, "empty", False):
            continue
        frame.to_file(
            gpkg,
            layer=layer_name,
            driver="GPKG",
            index=create_spatial_index,
        )
        written.append(layer_name)
        counts[layer_name] = int(len(frame))

    from .problem_registry import VALIDATION_RULE_VERSION

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "geopackage": str(gpkg),
        "layers": written,
        "feature_counts": counts,
        "spatial_index": create_spatial_index,
        "validation_rule_version": VALIDATION_RULE_VERSION,
        **(dict(manifest) if manifest else {}),
    }
    manifest_path = destination / f"{Path(filename).stem}_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )

    return {
        "geopackage": str(gpkg),
        "manifest": str(manifest_path),
        "layers": written,
        "feature_counts": counts,
    }


__all__ = [
    "GPKG_APPLICATION_ID",
    "GPKG_APPLICATION_ID_TEXT",
    "GPKG_KNOWN_VERSIONS",
    "GPKG_MIN_USER_VERSION",
    "GEOMETRY_STORAGE",
    "OPTIONAL_TABLES",
    "PROBLEM_NAME",
    "REQUIRED_SRS",
    "REQUIRED_TABLES",
    "VECTOR_TABLES",
    "GpkgLayer",
    "GpkgProfile",
    "list_gpkg_layers",
    "profile_gpkg",
    "read_gpkg_layer",
    "validate_gpkg",
    "write_gpkg_bundle",
]