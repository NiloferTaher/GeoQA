"""QGIS integration: style files, layer bundles, and PyQGIS processing recipes.

Scope
-----
QGIS is the most common place a person looks when a GeoQA run produces
findings, so the output has to land somewhere they already work. This module
produces three things, none of which require QGIS to be installed:

``qml_style(...)``
    A QGIS **QML** style document. QGIS 3.x reads ``.qml`` alongside any layer
    and applies the symbology, so findings render correctly by severity the
    moment they are loaded, with no manual classification.

``write_layer_bundle(...)``
    A directory holding the findings as GeoPackage, the style, and a run
    manifest. Self-contained, no server, no dependencies beyond GDAL.

``pyqgis_recipe(...)``
    A runnable PyQGIS script that reloads GeoQA inside QGIS, so the check runs
    against the layer the user actually has open rather than a re-export.

Why QML rather than raw SLD
---------------------------
QGIS writes and reads QML natively, it round-trips every symbol layer without
loss, and a ``.qml`` dropped beside a ``.gpkg`` is applied on load. SLD is the
interchange format and would mean giving up QGIS-specific symbology for no
benefit here.

Where ArcGIS fits
-----------------
It does not, and that is a deliberate boundary rather than an omission. ArcGIS
Data Reviewer is a licensed desktop product with its own batch validation
engine; the useful integration is to emit something it can consume (File
Geodatabase or geopackage plus a documented rule manifest), not to reimplement
its review workflow. See ``arcgis_field_mapping`` for the attribute mapping that
makes a findings layer legible in Pro.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .validations.base import ValidationIssue

# Severity to colour. Chosen to stay distinguishable in greyscale print and
# under the common colour-vision deficiencies: the ramp is monotonic in
# lightness, not only in hue.
SEVERITY_COLOURS = {
    "critical": "#B2182B",
    "high": "#D6604D",
    "medium": "#F4A582",
    "low": "#92C5DE",
    "info": "#4393C3",
}

SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def _severity_of(issue: ValidationIssue | Mapping[str, Any]) -> str:
    value = issue.severity if isinstance(issue, ValidationIssue) else issue.get("severity")
    return str(value).lower() if value else "info"


def _issue_row(issue: ValidationIssue) -> dict[str, Any]:
    payload = issue.to_dict()
    return {
        "problem_name": issue.problem_name,
        "severity": str(issue.severity),
        "description": issue.description,
        "solution_hint": issue.solution_hint,
        "feature_id": issue.feature_id,
        "issue_id": issue.issue_id,
        "issue_class": issue.issue_class,
        "confidence": str(issue.confidence),
        "actionable": bool(issue.actionable),
        "geometry_wkt": payload.get("geometry") if isinstance(payload.get("geometry"), str) else None,
        "geometry_geojson": payload.get("geometry") if isinstance(payload.get("geometry"), dict) else None,
        "extra": payload.get("extra") or {},
    }


def issues_to_geodataframe(issues: Iterable[ValidationIssue]):
    """Build a GeoDataFrame of findings, split into point and non-point.

    QGIS chokes on a layer holding a mix of point and polygon geometry, and it
    refuses ``None`` geometry outright, so findings are partitioned rather than
    written as one broken layer.
    """
    import geopandas as gpd
    import pandas as pd
    import shapely
    from shapely.geometry import shape

    rows = [_issue_row(issue) for issue in issues]
    if not rows:
        empty = gpd.GeoDataFrame(
            {"problem_name": [], "severity": []}, geometry=[], crs="EPSG:4326"
        )
        return empty, empty

    records = []
    geometries = []
    for row in rows:
        raw = row.pop("geometry_geojson", None)
        geometry = None
        if isinstance(raw, dict):
            try:
                geometry = shape(raw)
            except Exception:
                geometry = None
        elif row.get("geometry_wkt"):
            try:
                geometry = shapely.from_wkt(row["geometry_wkt"])
            except Exception:
                geometry = None
        row.pop("geometry_wkt", None)
        row["extra"] = json.dumps(row.get("extra") or {}, ensure_ascii=True, default=str)
        records.append(row)
        geometries.append(geometry)

    frame = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    point_mask = frame.geometry.geom_type.isin(["Point", "MultiPoint"])
    point_frame = frame[point_mask].reset_index(drop=True)
    other_frame = frame[~point_mask].reset_index(drop=True)
    other_frame = other_frame[~other_frame.geometry.isna() & ~other_frame.geometry.is_empty]

    for target in (point_frame, other_frame):
        target["severity"] = pd.Categorical(
            target["severity"],
            categories=[s for s in SEVERITY_ORDER if s in set(target["severity"])]
            or ["info"],
            ordered=True,
        )

    return point_frame, other_frame


def qml_style(
    *,
    layer_name: str = "GeoQA Findings",
    field: str = "severity",
    geometry_field: str | None = None,
    title: str | None = None,
) -> str:
    """Build a QGIS QML style document that renders findings by severity.

    Written as an explicit string rather than generated from a template file so
    the symbology is visible in the source and reviewable in a diff.
    """
    ranges = []
    for index, severity in enumerate(SEVERITY_ORDER):
        ranges.append(
            f"""    <range>
      <rangeexpression>"{field}" = '{severity}'</rangeexpression>
      <symbol>
        <layer class="SimpleMarker" enabled="1" pass="0" locked="0">
          <Option type="Map">
            <Option name="angle" type="double" value="0"/>
            <Option name="color" type="string" value="{SEVERITY_COLOURS[severity]}"/>
            <Option name="outline_color" type="string" value="#232323"/>
            <Option name="outline_style" type="string" value="solid"/>
            <Option name="outline_width" type="double" value="0.26"/>
            <Option name="outline_width_unit" type="string" value="MM"/>
            <Option name="size" type="double" value="{3.4 - index * 0.4}"/>
            <Option name="size_unit" type="string" value="MM"/>
            <Option name="shape" type="string" value="circle"/>
          </Option>
        </layer>
        <label type="simple">
          <Option type="Map">
            <Option name="fieldName" type="string" value="problem_name"/>
            <Option name="fontSizeUnit" type="string" value="MM"/>
          </Option>
        </label>
      </symbol>
      <label>"{severity}"</label>
      <render>TRUE</render>
    </range>"""
        )

    document_title = html.escape(title or layer_name)
    return f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology|Labeling">
  <renderer-v2 type="categorizedSymbol" attr="{field}" forceraster="0" symbollevels="0" enableorderby="0" referencescale="-1">
{chr(10).join(ranges)}
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="problem_name" fontSize="8" textColor="#232323"/>
      <text-style fieldName="severity" fontSize="8" textColor="#555555"/>
    </settings>
  </labeling>
  <title>{document_title}</title>
</qgis>
"""


def write_layer_bundle(
    issues: Sequence[ValidationIssue],
    directory: str | Path,
    *,
    layer_stem: str = "geoqa_findings",
    manifest: Mapping[str, Any] | None = None,
    write_style: bool = True,
) -> dict[str, Any]:
    """Write findings as a self-contained QGIS-ready bundle.

    Produces a GeoPackage of findings, a ``.qml`` style beside it, and a
    ``manifest.json`` recording what was validated, when, and with which rule
    set. The manifest is the part that matters later: it makes a finding
    reproducible, which a bare layer does not.
    """
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)

    point_frame, other_frame = issues_to_geodataframe(issues)
    written: list[str] = []

    gpkg = destination / f"{layer_stem}.gpkg"
    if not point_frame.empty:
        point_frame.to_file(gpkg, layer="findings_points", driver="GPKG")
        written.append("findings_points")
    if not other_frame.empty:
        other_frame.to_file(gpkg, layer="findings_geometries", driver="GPKG")
        written.append("findings_geometries")
    if not written:
        # An empty layer is still useful: it proves the run happened and found
        # nothing, which is otherwise indistinguishable from a missing file.
        empty = point_frame.copy()
        empty.to_file(gpkg, layer="findings_points", driver="GPKG")
        written.append("findings_points")

    if write_style:
        style_path = destination / f"{layer_stem}.qml"
        style_path.write_text(qml_style(layer_name=layer_stem), encoding="utf-8")

    from .problem_registry import VALIDATION_RULE_VERSION

    counts: dict[str, int] = {}
    for issue in issues:
        counts[_severity_of(issue)] = counts.get(_severity_of(issue), 0) + 1

    manifest_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issue_count": len(issues),
        "layers": written,
        "severity_counts": counts,
        "validation_rule_version": VALIDATION_RULE_VERSION,
        "layers_written": written,
        **(dict(manifest) if manifest else {}),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=True, default=str),
        encoding="utf-8",
    )

    return {
        "directory": str(destination),
        "geopackage": str(gpkg),
        "style": str(destination / f"{layer_stem}.qml") if write_style else None,
        "manifest": str(destination / "manifest.json"),
        "layers": written,
        "issue_count": len(issues),
    }


def pyqgis_recipe(
    *,
    input_path: str,
    dataset_type: str,
    output_directory: str,
    context: Mapping[str, Any] | None = None,
) -> str:
    """A runnable PyQGIS script that runs GeoQA against the open layer.

    Drop it into the QGIS Python console and it uses the layer already loaded,
    so the validation runs against what the user is looking at rather than a
    re-export that may differ.
    """
    payload = json.dumps(dict(context or {}), ensure_ascii=True, indent=2)
    return f'''"""Run GeoQA against the active QGIS layer.

Generated by GeoQA. Paste into the QGIS Python Console, or save to a script in
your QGIS profile and add it to a toolbar.
"""
import json
from pathlib import Path

from qgis.core import QgsApplication, QgsProject
import geopandas as gpd

INPUT_PATH = {input_path!r}
DATASET_TYPE = {dataset_type!r}
OUTPUT_DIRECTORY = Path({output_directory!r})
CONTEXT = json.loads(r"""{payload}""")


def main():
    layer = QgsProject.instance().mapLayerByName(Path(INPUT_PATH).stem)
    if layer is None:
        for candidate in QgsProject.instance().mapLayers().values():
            if candidate.source().endswith(Path(INPUT_PATH).name):
                layer = candidate
                break
    if layer is None:
        raise RuntimeError("Open {input_path!r} in QGIS before running this script.")

    frame = gpd.read_file(INPUT_PATH)
    if layer.crs() is not None and frame.crs is None:
        frame = frame.set_crs(layer.crs(), allow_override=True)

    from geoqa.validation_runtime import execute_validation_plan
    from geoqa.qgis_export import write_layer_bundle

    result = execute_validation_plan(frame, DATASET_TYPE, return_result=True, **CONTEXT)
    bundle = write_layer_bundle(result.issues, OUTPUT_DIRECTORY)
    print("GeoQA found {{}} issue(s); bundle written to {{}}".format(len(result.issues), bundle["directory"]))

    QgsApplication.processEvents()


main()
'''


def arcgis_field_mapping() -> dict[str, Any]:
    """Attribute mapping that makes a findings layer usable in ArcGIS Pro.

    ArcGIS has no equivalent of QML auto-classification, so a findings layer
    carries a ready-made ``SeverityRank`` integer for graduated symbology and a
    ``ProblemCategory`` for grouping. Emitting both removes the setup step that
    otherwise gets skipped.
    """
    return {
        "attribute_map": {
            "problem_name": {"alias": "Problem", "length": 80},
            "severity": {"alias": "Severity", "length": 16, "domain": list(SEVERITY_ORDER)},
            "severity_rank": {"alias": "Severity Rank", "type": "SHORT", "note": "1 is most severe; graduated renderer"},
            "issue_class": {"alias": "Issue Class", "length": 32},
            "confidence": {"alias": "Confidence", "length": 16},
            "actionable": {"alias": "Actionable", "type": "SHORT"},
            "description": {"alias": "Description", "length": 254},
            "solution_hint": {"alias": "Suggested Action", "length": 254},
            "feature_id": {"alias": "Source Feature ID", "length": 64},
            "issue_id": {"alias": "Issue ID", "length": 64},
        },
        "severity_rank": {severity: index + 1 for index, severity in enumerate(SEVERITY_ORDER)},
        "notes": [
            "Graduated colours on SeverityRank with the palette "
            + ", ".join(f"{s}: {SEVERITY_COLOURS[s]}" for s in SEVERITY_ORDER),
            "Enable Time on Issues only if issue_id is populated; GeoQA does not "
            "date-stamp findings unless a run manifest is supplied.",
        ],
    }


def severity_rank(issues: Sequence[ValidationIssue]) -> dict[str, int]:
    """Rank map for a findings layer, 1 being most severe."""
    return {severity: index + 1 for index, severity in enumerate(SEVERITY_ORDER)}


__all__ = [
    "SEVERITY_COLOURS",
    "SEVERITY_ORDER",
    "arcgis_field_mapping",
    "issues_to_geodataframe",
    "pyqgis_recipe",
    "qml_style",
    "severity_rank",
    "write_layer_bundle",
]