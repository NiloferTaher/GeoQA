"""Turn GeoQA findings into a browsable web-GIS site, slides, and charts.

The workflow is deliberately no-code: hand ``build_site`` a validation report
(or raw GeoJSON) and receive a self-contained static site whose findings are
map features with detail popups. No QGIS, Folium, server, or build step.

    import geoqa, geoqa_web
    report = geoqa.validate("mains.osm.pbf")
    geoqa_web.build_site(report, "out/site")

Templates are original GeoQA assets: a dark, map-first presentation in the style
of interactive geospatial explorers, carrying no third-party branding or copy.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .charts import chart_bundle, render_chart_html
from .site import build_site
from .slides import build_slides, slide_deck_from_report

_TEMPLATES = Path(__file__).resolve().parent / "templates"

__all__ = [
    "build_site",
    "build_slides",
    "chart_bundle",
    "render_chart_html",
    "slide_deck_from_report",
    "storyboard_from_report",
]


def storyboard_from_report(
    report: Any,
    *,
    hold_ms: int = 2600,
) -> list[dict[str, Any]]:
    """Derive a camera/filter storyboard from a report.

    The map template plays this as a guided tour: it opens on the whole extent,
    then narrows to each severity band in turn. The storyboard is plain data,
    so a caller can replace it entirely.
    """
    collection = _findings(report)
    severities = ["critical", "high", "medium", "low"]
    present = [s for s in severities if any(f["properties"].get("severity") == s for f in collection["features"])]

    steps: list[dict[str, Any]] = [{"severity": None, "fit": True, "hold": hold_ms, "label": "All findings"}]
    for severity in present:
        steps.append({
            "severity": [severity],
            "fit": True,
            "hold": hold_ms,
            "label": f"{severity.title()} findings",
        })
    return steps


def _findings(report: Any) -> dict[str, Any]:
    """Normalise a report / GeoQAReport / FeatureCollection into a collection."""
    if isinstance(report, dict) and report.get("type") == "FeatureCollection":
        return report
    if hasattr(report, "to_geojson"):
        return report.to_geojson()
    if isinstance(report, (str, Path)):
        return json.loads(Path(report).read_text(encoding="utf-8"))
    if hasattr(report, "issues"):
        from geoqa.reports.geojson import issues_to_geojson

        return issues_to_geojson(report.issues)
    raise TypeError(f"Unsupported report source for geoqa_web: {type(report)!r}")


def _summary_payload(collection: dict[str, Any]) -> dict[str, Any]:
    from geoqa.reports.geojson import errors_summary

    payload = errors_summary(collection)
    payload["unmapped"] = (collection.get("geoqa") or {}).get("unmapped_count", 0)
    return payload


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _read_template(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")