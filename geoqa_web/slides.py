"""Generate a presentation-ready slide deck from GeoQA findings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#38bdf8",
    "info": "#64748b",
}


def _collection(source: Any) -> dict[str, Any]:
    if isinstance(source, dict) and source.get("type") == "FeatureCollection":
        return source
    if hasattr(source, "to_geojson"):
        return source.to_geojson()
    if isinstance(source, (str, Path)):
        return json.loads(Path(source).read_text(encoding="utf-8"))
    if hasattr(source, "issues"):
        from geoqa.reports.geojson import issues_to_geojson

        return issues_to_geojson(source.issues)
    raise TypeError(f"Unsupported slides source: {type(source)!r}")


def slide_deck_from_report(
    source: Any,
    *,
    title: str = "GeoQA Findings",
    subtitle: str = "Spatial data quality report",
    presenter: str = "",
) -> dict[str, Any]:
    """Build a declarative deck: title, headline numbers, rules, actions."""
    collection = _collection(source)
    features = collection.get("features", [])
    props = [f.get("properties", {}) or {} for f in features]

    severities = ["critical", "high", "medium", "low"]
    counts = {s: sum(1 for p in props if p.get("severity") == s) for s in severities}

    problems: dict[str, int] = {}
    severity_of: dict[str, str] = {}
    for p in props:
        name = str(p.get("problem_name", "unknown"))
        problems[name] = problems.get(name, 0) + 1
        severity_of.setdefault(name, str(p.get("severity", "info")))

    unmapped = int((collection.get("geoqa") or {}).get("unmapped_count", 0))
    mappable = len(features)
    total = mappable + unmapped

    def color_for(severity: str) -> str:
        return SEVERITY_COLORS.get(severity, "#64748b")

    top_rules = sorted(problems.items(), key=lambda kv: kv[1], reverse=True)[:8]
    rule_bars = [
        {
            "label": name.replace("_", " "),
            "value": count,
            "color": color_for(severity_of.get(name, "info")),
        }
        for name, count in top_rules
    ]

    severity_bars = [
        {"label": s.title(), "value": counts[s], "color": color_for(s)} for s in severities if counts[s]
    ]

    actions: list[str] = []
    for p in props:
        hint = p.get("recommended_action") or p.get("solution_hint")
        if hint and hint not in actions:
            actions.append(str(hint))
    actions = actions[:6]

    findings_without_reason = sum(
        1 for p in props if not (p.get("why_it_matters") or p.get("description"))
    )

    slides: list[dict[str, Any]] = [
        {
            "kicker": "Spatial data quality",
            "title": title,
            "lede": subtitle,
            "note": f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            + (f" — {presenter}" if presenter else ""),
        },
        {
            "kicker": "Headline",
            "title_level": 2,
            "title": "What the check found",
            "tiles": [
                {"value": str(total), "label": "Total findings", "color": "#e6ecf7"},
                {"value": str(mappable), "label": "Mapped on the web map", "color": "#60a5fa"},
                {"value": str(counts["critical"] + counts["high"]), "label": "Critical or high", "color": "#ef4444"},
                {"value": str(len(problems)), "label": "Distinct rules", "color": "#a855f7"},
                {"value": str(unmapped), "label": "Attribute-only findings", "color": "#8b9bb4"},
            ],
        },
    ]

    if severity_bars:
        slides.append({
            "kicker": "Severity profile",
            "title_level": 2,
            "title": "Severity distribution",
            "bars": severity_bars,
        })

    if rule_bars:
        slides.append({
            "kicker": "Rule breakdown",
            "title_level": 2,
            "title": "Findings by rule",
            "bars": rule_bars,
        })

    if actions:
        slides.append({
            "kicker": "Remediation",
            "title_level": 2,
            "title": "Recommended actions",
            "bullets": actions,
        })

    slides.append({
        "kicker": "Next step",
        "title_level": 2,
        "title": "Open the map",
        "bullets": [
            "Every mapped finding carries a popup with the rule, severity, confidence and fix.",
            "Toggle severities in the legend to isolate what matters to you.",
            "Filter by text to trace one feature across every rule that fired on it.",
            "Export the findings to CSV or XLSX for spreadsheet and database analysis.",
        ],
        "note": "Findings without geometry are listed in the exported table with blank coordinates.",
    })

    if findings_without_reason:
        slides[-1]["note"] = (
            f"{findings_without_reason} finding(s) lacked an explanation field and fall back to the raw description."
        )

    return {"slides": slides, "footer": "Generated by GeoQA"}


def build_slides(
    source: Any,
    output_dir: str | Path,
    *,
    title: str = "GeoQA Findings",
    subtitle: str = "Spatial data quality report",
    presenter: str = "",
) -> Path:
    """Write a self-contained ``index.html`` slide deck."""
    from . import _read_template

    deck = slide_deck_from_report(source, title=title, subtitle=subtitle, presenter=presenter)
    page = _read_template("slides.html")
    page = page.replace("__TITLE__", _escape(title))
    page = page.replace("__DECK__", _json_for_script(deck))

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    index = target / "index.html"
    index.write_text(page, encoding="utf-8")

    (target / "deck.json").write_text(json.dumps(deck, indent=2), encoding="utf-8")
    return index


def _escape(value: Any) -> str:
    import html

    return html.escape(str(value if value is not None else ""))


def _json_for_script(payload: Any) -> str:
    """Serialise JSON for an inline <script> block, neutralising ``</script>``."""
    return (
        json.dumps(payload, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


__all__ = ["build_slides", "slide_deck_from_report"]