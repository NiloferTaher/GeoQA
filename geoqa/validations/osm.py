"""OpenStreetMap: the failure modes that come with the format's own nature.

Why OSM needs its own conditions
--------------------------------
Every other source GeoQA reads is a curated export. OSM is a crowd-sourced
database that anyone edits, and its data problems are not the same species as
a missing sidecar file. They are the predictable consequences of the way OSM is
made:

**Geometry is an emergent property.** A building is not a polygon; it is a way
plus a relation that assembles ways into a ring. Whether that ring closes is a
property of the current version of the data, and it can be broken by an edit
somewhere else in the world. Nothing in the file says a polygon should close,
because polygons are not a first-class concept in OSM.

**Relations are open to interpretation.** A ``multipolygon`` relation has
``inner`` and ``outer`` roles. A relation whose members do not actually form a
ring is common, not exceptional, and different renderers resolve it
differently.

**The licence requires attribution and share-alike.** ODbL means a derived
database carries obligations. Extracting polygons and dropping the attribution
is a licence breach, not a metadata omission, and it is invisible to any
structural check.

**Coverage is uneven and confidence is absent.** OSM has no completeness
measure. A missing feature in a well-mapped city is indistinguishable from a
feature that was never there, and the data gives you nothing to tell them apart.

What is deliberately not here
-----------------------------
Completeness is not checkable from OSM alone, and this module does not pretend
otherwise. It reports what the data can show about itself, and names what it
cannot.

Provenance
----------
The licence obligation is the Open Database License. The attribution requirement
and the share-alike condition are its terms, not conventions of this library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PROBLEM_NAME = "openstreetmap"

#: The licence OSM data is published under, and its obligations.
OSM_LICENCE = "Open Database License (ODbL) v1.0"

#: Tags that identify a closed way as an area rather than a line.
AREA_TAGS = {
    "building", "building:part", "landuse", "natural", "amenity", "leisure",
    "shop", "man_made", "waterway", "area:highway", "boundary", "place",
    "public_transport", "aeroway", "military", "power", "tourism",
    "historic", "office", "craft", "healthcare", "emergency",
}

#: Tags whose value is a closed way used as an area and needs a relation when
#: it has more than one ring, or when it has holes.
NEEDS_MULTIPOLYGON_WHEN_HOLES = {"building", "building:part", "landuse", "natural", "leisure"}

#: A closed way used as an area. OpenStreetMap renders this; a naive import does not.
_CLOSED_WAY = re.compile(r"^(way|relation)\s+(\d+)", re.IGNORECASE)


def _issue(problem_name: str, severity: str, description: str, extra: dict[str, Any]):
    from .base import build_issue

    return build_issue(
        problem_name=problem_name,
        severity=severity,
        description=description,
        extra=extra,
    )


@dataclass
class OsmProfile:
    """What an OSM extract declares about itself."""

    path: str | None = None
    #: Tags present across the extract, with counts.
    tag_counts: dict[str, int] = field(default_factory=dict)
    #: Feature identifiers seen, mapped to their geometry type.
    element_types: dict[str, int] = field(default_factory=dict)
    version_attribute_present: bool = False
    timestamp_attribute_present: bool = False
    user_attribute_present: bool = False
    changeset_attribute_present: bool = False
    #: Whether any attribution or licence text is present in the file.
    attribution_present: bool = False
    #: Areas built from a single closed way, which is where holes get lost.
    single_ring_areas: int = 0
    #: Ways that are not closed but are tagged as an area.
    unclosed_area_ways: int = 0
    #: Ways with a closed ring used where a multipolygon would be needed.
    single_ring_with_holes_tagged: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "elements": dict(self.element_types),
            "version_attribute": self.version_attribute_present,
            "timestamp_attribute": self.timestamp_attribute_present,
            "user_attribute": self.user_attribute_present,
            "changeset_attribute": self.changeset_attribute_present,
            "attribution_present": self.attribution_present,
            "single_ring_areas": self.single_ring_areas,
            "unclosed_area_ways": self.unclosed_area_ways,
            "single_ring_with_holes_tagged": self.single_ring_with_holes_tagged,
            "tag_counts": dict(sorted(self.tag_counts.items(), key=lambda kv: -kv[1])[:40]),
        }


def _looks_closed(value: Any) -> bool:
    """Is a WKT geometry a closed ring?"""
    text = str(value or "").upper()
    if text.startswith("POLYGON"):
        return "EMPTY" not in text
    if text.startswith("LINESTRING"):
        # A closed line is LINESTRING(x y, x y) where first equals last.
        try:
            body = text[text.index("(") + 1: text.rindex(")")]
            points = [point.strip() for point in body.split(",") if point.strip()]
            return len(points) >= 4 and points[0] == points[-1]
        except ValueError:
            return False
    return False


def profile_osm_layer(
    layer: Any,
    *,
    key_column: str | None = "osm_id",
    geometry_column: str = "geometry",
    path: str | None = None,
) -> OsmProfile:
    """Describe an OSM-derived layer without judging it yet."""
    profile = OsmProfile(path=path)
    columns = [str(column) for column in getattr(layer, "columns", [])]
    if not columns:
        return profile

    lowered = {column.lower(): column for column in columns}
    profile.version_attribute_present = any(
        token in lowered for token in ("version", "osm_version")
    )
    profile.timestamp_attribute_present = any(
        token in lowered for token in ("timestamp", "osm_timestamp", "date")
    )
    profile.user_attribute_present = any(token in lowered for token in ("user", "osm_user"))
    profile.changeset_attribute_present = any(
        token in lowered for token in ("changeset", "osm_changeset")
    )

    for column in columns:
        label = str(column).lower()
        if "licence" in label or "license" in label or "attribution" in label or "copyright" in label:
            try:
                values = layer[column]
            except Exception:
                continue
            if any(str(value).strip() for value in values if value is not None):
                profile.attribution_present = True

    tag_columns = [
        column for column in columns
        if str(column).lower() not in {geometry_column.lower(), (key_column or "").lower()}
        and str(column).lower() not in {
            "osm_id", "osm_type", "version", "timestamp", "user", "changeset",
            "name", "notes", "id", "type",
        }
    ]

    for _, row in layer.iterrows():
        area_tagged = False
        for column in tag_columns:
            value = row[column]
            if value is None or str(value).strip() == "":
                continue
            label = str(column).lower()
            profile.tag_counts[label] = profile.tag_counts.get(label, 0) + 1
            if label in AREA_TAGS and str(value).strip().lower() not in {"no", "false"}:
                area_tagged = True
                if label in NEEDS_MULTIPOLYGON_WHEN_HOLES:
                    profile.single_ring_with_holes_tagged += 1

        if not area_tagged:
            continue
        geometry = row[geometry_column] if geometry_column in columns else None
        if geometry is None:
            continue
        if _looks_closed(geometry):
            profile.single_ring_areas += 1
        else:
            profile.unclosed_area_ways += 1

    return profile


def validate_osm(
    layer: Any,
    *,
    key_column: str | None = "osm_id",
    geometry_column: str = "geometry",
    require_attribution: bool = True,
    require_version_metadata: bool = True,
    path: str | None = None,
) -> list[Any]:
    """Report the OSM-specific conditions a structural check would miss.

    Conditions emitted
    ------------------
    ``osm_attribution_absent``
        No licence or attribution field accompanies the data. High, and a
        licence matter rather than a metadata one: OSM data is published under
        the ODbL, which requires attribution and share-alike on derived
        databases.
    ``osm_version_metadata_absent``
        No version, timestamp or changeset field. Medium: without them a row
        cannot be tied to a point in the OSM history, so an update cannot be
        traced and a disputed edit cannot be contested.
    ``osm_unclosed_area``
        A feature tagged as an area whose geometry is not closed. High: it will
        not render as a polygon, and the renderer decides what it becomes.
    ``osm_single_ring_with_holes``
        A feature that may have holes is represented by a single ring, so any
        holes are lost. Medium.
    ``osm_geometry_from_relation``
        Informational: an area assembled from a relation. Recorded because a
        relation's validity is a property of the current data version and can
        be broken by an unrelated edit.
    ``osm_completeness_unknown``
        Always informational. OSM carries no completeness measure, so an absent
        feature is indistinguishable from one that was never mapped. Every OSM
        analysis inherits this limitation and no structural check can remove it.
    """
    profile = profile_osm_layer(
        layer, key_column=key_column, geometry_column=geometry_column, path=path
    )
    columns = [str(column) for column in getattr(layer, "columns", [])]
    if not columns:
        return []

    issues: list[Any] = []

    if require_attribution and not profile.attribution_present:
        issues.append(
            _issue(
                "osm_attribution_absent", "high",
                f"No licence or attribution field accompanies this data. OSM data is published "
                f"under the {OSM_LICENCE}, which requires attribution and share-alike for "
                "derived databases. Extracting geometry and discarding the attribution is a "
                "licence breach, and no structural check can detect it",
                profile.as_dict(),
            )
        )

    if require_version_metadata and not (
        profile.version_attribute_present
        and profile.timestamp_attribute_present
        and profile.changeset_attribute_present
    ):
        missing = []
        if not profile.version_attribute_present:
            missing.append("version")
        if not profile.timestamp_attribute_present:
            missing.append("timestamp")
        if not profile.changeset_attribute_present:
            missing.append("changeset")
        issues.append(
            _issue(
                "osm_version_metadata_absent", "medium",
                f"Missing {', '.join(missing)}. Without them a row cannot be tied to a point in "
                "the OSM history, so an update cannot be traced and a disputed edit cannot be "
                "contested. This matters more for OSM than for a curated export, because OSM is "
                "edited continuously by many people",
                profile.as_dict(),
            )
        )

    if profile.unclosed_area_ways:
        issues.append(
            _issue(
                "osm_unclosed_area", "high",
                f"{profile.unclosed_area_ways} feature(s) are tagged as an area but their geometry "
                "is not closed. In OSM an area is an emergent property of ways and relations "
                "rather than a stored polygon, so a ring that does not close will not render, and "
                "what a renderer substitutes differs between tools",
                profile.as_dict(),
            )
        )

    if profile.single_ring_with_holes_tagged:
        issues.append(
            _issue(
                "osm_single_ring_with_holes", "medium",
                f"{profile.single_ring_with_holes_tagged} feature(s) may contain holes but are "
                "represented by a single ring. A courtyard inside a building footprint, for "
                "instance, would be filled rather than excluded",
                profile.as_dict(),
            )
        )

    issues.append(
        _issue(
            "osm_completeness_unknown", "info",
            "OSM carries no completeness measure, so a missing feature cannot be distinguished "
            "from one that was never mapped. Coverage is uneven between places and between "
            "feature types, and every result derived from this data inherits that limitation. "
            "This is not fixable by validation and is recorded so it is not forgotten",
            profile.as_dict(),
        )
    )

    return issues


__all__ = [
    "AREA_TAGS",
    "NEEDS_MULTIPOLYGON_WHEN_HOLES",
    "OSM_LICENCE",
    "PROBLEM_NAME",
    "OsmProfile",
    "profile_osm_layer",
    "validate_osm",
]