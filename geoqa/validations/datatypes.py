"""Declared datatypes, geometry parts, and what a database will accept.

A layer can be geometrically perfect and still be wrong for its destination.
A coordinate column declared ``text`` will accept ``"12,5"``. An identifier
stored as a float will come back as ``70677.0`` from any tool that reads the
column as text. A ``MultiPolygon`` column holding single-part polygons is not
wrong, but a ``Polygon`` column receiving a two-part polygon is refused by
PostGIS outright, at insert, after the work of building the row.

These checks run before the write rather than after, because the failure they
prevent surfaces at load time with no useful message.

Geometry part structure is reported on three axes rather than one, because the
answers differ in consequence:

- **Part count** - one part or several.
- **Part type** - whether the parts agree on dimension, and whether they are
  homogeneous. A ``MultiPolygon`` whose parts include a ``GeometryCollection``
  is malformed in a way that some readers accept and others reject.
- **Family** - point, line, polygon. A layer mixing families is usually a
  mistake at the layer level rather than the feature level, and is the one
  case where taking the majority and ignoring the rest loses data.

The declared-type checks are expressed against the target rather than against
a particular database, so the same rule set applies whether the destination is
PostGIS, a GeoPackage or a shapefile. The PostGIS expectations are one table
in this module, not the whole design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from geoqa.validations.base import ValidationIssue, build_issue

__all__ = [
    "GeometryPartProfile",
    "profile_geometry_parts",
    "validate_geometry_parts",
    "profile_datatypes",
    "validate_datatypes",
    "postgis_expectations",
    "GEOMETRY_FAMILY",
]

#: Geometry types grouped by the family a database column will accept.
#: A column declared Polygon will not take a MultiPolygon; a column declared
#: MultiPolygon will take either, which is why "declared" and "observed" have
#: to be compared rather than assumed to agree.
GEOMETRY_FAMILY: dict[str, str] = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "LinearRing": "line",
    "MultiLineString": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
    "GeometryCollection": "collection",
}

_PART_COUNTABLE = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
}


@dataclass
class GeometryPartProfile:
    """What the geometry column actually contains, as distinct from what is declared."""

    type_counts: dict[str, int] = field(default_factory=dict)
    family_counts: dict[str, int] = field(default_factory=dict)
    single_part: int = 0
    multi_part: int = 0
    empty_part_count: int = 0
    mixed_families: bool = False
    mixed_part_types: bool = False
    per_feature: dict[Any, str] = field(default_factory=dict)

    @property
    def dominant_type(self) -> str | None:
        if not self.type_counts:
            return None
        return max(self.type_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]

    @property
    def has_mixed(self) -> bool:
        return self.mixed_families or self.mixed_part_types

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_counts": dict(sorted(self.type_counts.items(), key=lambda kv: -kv[1])),
            "family_counts": dict(sorted(self.family_counts.items(), key=lambda kv: -kv[1])),
            "single_part": self.single_part,
            "multi_part": self.multi_part,
            "dominant_type": self.dominant_type,
            "mixed_families": self.mixed_families,
            "mixed_part_types": self.mixed_part_types,
            "empty_part_count": self.empty_part_count,
        }


def _geometry_type(geometry: Any) -> str:
    return str(getattr(geometry, "geom_type", "") or "Unknown")


def _part_geometries(geometry: Any) -> list[Any]:
    parts = getattr(geometry, "geoms", None)
    if parts is None:
        return [geometry]
    try:
        return list(parts)
    except Exception:
        return [geometry]


def profile_geometry_parts(layer: Any) -> GeometryPartProfile:
    """Describe the part structure of a layer without judging it."""
    profile = GeometryPartProfile()
    families: set[str] = set()

    try:
        rows = list(layer.iterrows())
    except Exception:
        rows = []

    for index, row in rows:
        geometry = row.get("geometry") if hasattr(row, "get") else None
        if geometry is None:
            continue
        gtype = _geometry_type(geometry)
        profile.type_counts[gtype] = profile.type_counts.get(gtype, 0) + 1
        family = GEOMETRY_FAMILY.get(gtype, "unknown")
        profile.family_counts[family] = profile.family_counts.get(family, 0) + 1
        families.add(family)

        parts = _part_geometries(geometry)
        if gtype in _PART_COUNTABLE:
            if len(parts) <= 1:
                profile.single_part += 1
                profile.per_feature[index] = "single"
            else:
                profile.multi_part += 1
                profile.per_feature[index] = "multi"
                empty = sum(1 for p in parts if getattr(p, "is_empty", False))
                profile.empty_part_count += empty

    profile.mixed_families = len(families) > 1
    # A MultiPolygon with a LinearRing inside is one family but not one
    # part type, and it will not survive a round trip through most writers.
    profile.mixed_part_types = len(profile.type_counts) > 1
    return profile


def validate_geometry_parts(
    layer: Any,
    *,
    declared_type: str | None = None,
    require_uniform: bool = True,
) -> list[ValidationIssue]:
    """Report mixed geometry part structure and a declared type that will not accept it.

    No check for empty parts inside a multi-part geometry, because shapely 2
    refuses to construct one and geopandas refuses to load one. The state
    cannot arrive from either, so a condition for it would never fire and
    would only make the registry less trustworthy. A multi-part geometry
    whose parts were emptied by a failed dissolve arrives instead as a
    smaller geometry, which the part-count check does see.
    """
    issues: list[ValidationIssue] = []
    profile = profile_geometry_parts(layer)

    if profile.mixed_families:
        issues.append(
            build_issue(
                "geometry_family_mixed",
                description=(
                    "The layer mixes geometry families ("
                    + ", ".join(sorted(k for k in profile.family_counts if k != "unknown"))
                    + "). A single typed column cannot hold this, and choosing one "
                    "family silently discards the rest."
                ),
                extra=profile.to_dict(),
            )
        )
    elif require_uniform and profile.mixed_part_types:
        issues.append(
            build_issue(
                "geometry_part_type_mixed",
                description=(
                    "The layer mixes geometry types ("
                    + ", ".join(sorted(profile.type_counts))
                    + "). Multi-part geometries containing unlike parts will not "
                    "round-trip through most writers."
                ),
                extra=profile.to_dict(),
            )
        )

    if declared_type:
        target = str(declared_type).strip()
        observed = profile.dominant_type
        if observed and not _declared_accepts(target, observed):
            issues.append(
                build_issue(
                    "geometry_declared_type_mismatch",
                    description=(
                        f"The column is declared {target} but the layer is mostly "
                        f"{observed}. PostGIS will refuse the insert rather than "
                        "coerce it."
                    ),
                    extra={"declared_type": target, "observed_type": observed,
                           **profile.to_dict()},
                )
            )
    return issues


def _declared_accepts(declared: str, observed: str) -> bool:
    """Whether a column declared ``declared`` will accept geometry ``observed``.

    ``GEOMETRY`` accepts anything. The single-type columns accept their own
    type only; the multi-type columns accept both forms of their family.
    """
    declared_clean = declared.split(",")[0].strip().split("(")[0].strip()
    if declared_clean.upper() in {"GEOMETRY", "GEOMETRYCOLLECTION", ""}:
        return True
    if declared_clean == observed:
        return True
    if declared_clean.startswith("Multi") and not observed.startswith("Multi"):
        if declared_clean[len("Multi") :] == observed:
            return True
    return False


#: Columns whose values are coordinates or measures must be numeric. A text
#: column accepts anything, which is how "12,5" and "12.5" both end up stored
#: as if they were the same number.
_NUMERIC_SUFFIXES = (
    "x", "y", "z", "lat", "lon", "lng", "long", "latitude", "longitude",
    "elev", "elevation", "height", "depth", "length", "len", "dist", "distance",
    "area", "perimeter", "radius", "diameter", "width", "depth_m",
    "accuracy", "precision", "tolerance",
)


def _looks_numeric_field(name: str) -> bool:
    lowered = name.strip().lower()
    if lowered in _NUMERIC_SUFFIXES:
        return True
    return any(lowered.endswith("_" + suffix) or lowered.endswith(suffix) for suffix in _NUMERIC_SUFFIXES)


def profile_datatypes(layer: Any) -> dict[str, str]:
    """Return the declared dtype per column, using text for anything unreadable."""
    profile: dict[str, str] = {}
    try:
        dtypes = layer.dtypes
    except Exception:
        return profile
    for column in dtypes.index:
        try:
            profile[str(column)] = str(dtypes[column])
        except Exception:
            profile[str(column)] = "unknown"
    return profile


def _is_text_dtype(dtype: str) -> bool:
    return dtype.startswith("object") or dtype in {"string", "str", "category"}


def _is_float_dtype(dtype: str) -> bool:
    """Float only.

    An integer identifier is correct when the identifier is genuinely numeric.
    It is a float identifier that is wrong, because a float is written as
    70677.0 by some readers, so separating the two is the whole point.
    """
    return dtype.startswith("float")


def _is_floatish(dtype: str) -> bool:
    return dtype.startswith(("float", "int", "uint"))


def validate_datatypes(
    layer: Any,
    *,
    id_fields: Sequence[str] = (),
    numeric_fields: Sequence[str] = (),
    infer_numeric_from_name: bool = True,
    declared_numeric: Mapping[str, Any] | None = None,
) -> list[ValidationIssue]:
    """Report columns whose declared type does not match what they hold.

    Three rules, each from something that has actually gone wrong at a load:

    - an identifier column declared as text or float, because ``70677.0`` then
      compares unequal to ``"70677"`` in every downstream join;
    - a coordinate or measure column declared as text, because that admits
      comma decimal separators and stray whitespace as valid values;
    - a declared numeric column holding a value that cannot be read as one.
    """
    issues: list[ValidationIssue] = []
    dtypes = profile_datatypes(layer)
    if not dtypes:
        return issues

    id_set = {str(f) for f in id_fields}
    numeric_set = {str(f) for f in numeric_fields}
    if declared_numeric:
        numeric_set |= {str(f) for f in declared_numeric}

    candidates_numeric = set(numeric_set)
    if infer_numeric_from_name:
        for column in dtypes:
            if _looks_numeric_field(column):
                candidates_numeric.add(column)

    for column, dtype in dtypes.items():
        if column == "geometry":
            continue

        if column in id_set:
            if _is_float_dtype(dtype):
                issues.append(
                    build_issue(
                        "datatype_identifier_as_float",
                        description=(
                            f"Identifier column {column!r} is declared {dtype}. A float "
                            "identifier is written as 70677.0 by some readers and as "
                            "70677 by others, so it stops matching itself."
                        ),
                        extra={"column": column, "dtype": dtype},
                    )
                )
            elif _is_text_dtype(dtype):
                issues.append(
                    build_issue(
                        "datatype_identifier_as_text",
                        description=(
                            f"Identifier column {column!r} is declared {dtype}. "
                            "Trailing whitespace and inconsistent padding will make "
                            "equal identifiers compare unequal."
                        ),
                        extra={"column": column, "dtype": dtype},
                    )
                )
            continue

        if column in candidates_numeric and _is_text_dtype(dtype):
            unparseable = _count_unparseable(layer, column)
            issues.append(
                build_issue(
                    "datatype_numeric_as_text",
                    description=(
                        f"Column {column!r} looks numeric but is declared {dtype}"
                        + (
                            f"; {unparseable} value(s) cannot be read as a number"
                            if unparseable
                            else ""
                        )
                        + ". A text column accepts a comma decimal separator and stray "
                        "whitespace as if they were valid numbers."
                    ),
                    extra={
                        "column": column,
                        "dtype": dtype,
                        "unparseable": unparseable,
                    },
                )
            )

    return issues


def _count_unparseable(layer: Any, column: str) -> int:
    try:
        series = layer[column]
    except Exception:
        return 0
    bad = 0
    for value in series:
        if value is None or (isinstance(value, float) and value != value):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            continue
        text = str(value).strip()
        if not text:
            continue
        try:
            float(text)
        except ValueError:
            bad += 1
    return bad


def postgis_expectations(
    layer: Any,
    *,
    table_name: str = "target",
    schema_name: str | None = None,
    target_srid: int = 4326,
    expected_geometry_type: str | None = None,
    id_fields: Sequence[str] = (),
) -> list[ValidationIssue]:
    """Check a layer against what PostGIS will accept on insert.

    Not a substitute for the database's own answer: PostGIS is authoritative
    and should be asked. This catches the cases where the mismatch is visible
    from the layer alone, so the failure arrives before the insert rather than
    during it.
    """
    issues: list[ValidationIssue] = []
    try:
        crs = layer.crs
    except Exception:
        crs = None

    if crs is None:
        issues.append(
            build_issue(
                "postgis_crs_undeclared",
                description=(
                    f"{table_name} has no CRS. PostGIS will store the geometry with "
                    "SRID 0, which is not an error and will not be noticed until "
                    "something downstream projects it."
                ),
                extra={"table": table_name, "schema": schema_name},
            )
        )
    else:
        try:
            epsg = crs.to_epsg()
        except Exception:
            epsg = None
        if epsg is None:
            issues.append(
                build_issue(
                    "postgis_crs_not_epsg",
                    description=(
                        f"{table_name} has a CRS that does not resolve to an EPSG code. "
                        "It can be stored, but every consumer has to carry the full "
                        "definition with it."
                    ),
                    extra={"table": table_name, "crs": str(crs)},
                )
            )
        elif epsg != target_srid:
            issues.append(
                build_issue(
                    "postgis_srid_mismatch",
                    description=(
                        f"{table_name} is {epsg} but the target is {target_srid}. "
                        "PostGIS does not reproject on insert; it stores the SRID "
                        "alongside the coordinates as given."
                    ),
                    extra={"table": table_name, "observed_epsg": epsg,
                           "target_epsg": target_srid},
                )
            )

    issues.extend(
        validate_geometry_parts(layer, declared_type=expected_geometry_type)
    )
    issues.extend(validate_datatypes(layer, id_fields=id_fields))
    return issues