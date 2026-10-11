"""Chart payloads for GeoQA findings.

Charts are described as plain data so the caller chooses the renderer: a D3 or
Plotly spec for an interactive web page, a matplotlib call for a static figure
for a paper. Keeping the *description* separate from the *renderer* means one
chart definition can serve both the slide deck and a journal figure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#38bdf8",
    "info": "#64748b",
}
PALETTE = ["#60a5fa", "#22c55e", "#f97316", "#a855f7", "#14b8a6", "#ec4899", "#eab308"]


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
    raise TypeError(f"Unsupported chart source: {type(source)!r}")


def _counts(values: list[str], order: list[str] | None = None) -> list[dict[str, Any]]:
    tally: dict[str, int] = {}
    for value in values:
        tally[value] = tally.get(value, 0) + 1
    keys = [key for key in (order or []) if key in tally]
    keys += sorted((key for key in tally if key not in keys), key=lambda k: -tally[k])
    return [
        {"label": key, "value": tally[key], "color": SEVERITY_COLORS.get(key, PALETTE[i % len(PALETTE)])}
        for i, key in enumerate(keys)
    ]


def chart_bundle(source: Any, *, top: int = 15) -> dict[str, Any]:
    """Describe the standard set of charts for a findings collection."""
    collection = _collection(source)
    props = [f.get("properties", {}) or {} for f in collection.get("features", [])]

    problems = _counts([str(p.get("problem_name", "unknown")) for p in props])
    severities = _counts([str(p.get("severity", "info")) for p in props], SEVERITY_ORDER)
    validators = _counts([str(p.get("validator_name", "unknown")) for p in props])

    return {
        "by_problem": {"type": "bar", "orientation": "horizontal", "data": problems[:top]},
        "by_severity": {"type": "donut", "data": severities},
        "by_validator": {"type": "bar", "orientation": "vertical", "data": validators[:top]},
    }


def to_plotly(spec: dict[str, Any], *, title: str = "") -> Any:
    """Render a chart spec with Plotly (interactive HTML)."""
    import plotly.graph_objects as go

    data = spec.get("data", [])
    labels = [item["label"] for item in data]
    values = [item["value"] for item in data]
    colors = [item.get("color", PALETTE[i % len(PALETTE)]) for i, item in enumerate(data)]

    if spec.get("type") == "donut":
        figure = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors)))
    else:
        figure = go.Figure(go.Bar(
            x=values, y=labels, orientation="h" if spec.get("orientation") == "horizontal" else "v",
            marker=dict(color=colors), text=values, textposition="outside",
        ))
        figure.update_layout(yaxis=dict(automargin=True))
    figure.update_layout(
        template="plotly_dark",
        title=title,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        paper_bgcolor="#121826",
        plot_bgcolor="#121826",
        font=dict(color="#e6ecf7"),
    )
    return figure


def to_d3(spec: dict[str, Any], *, width: int = 720, height: int = 380) -> str:
    """Render a chart spec as a self-contained D3 + SVG fragment."""
    import html as _html

    data = spec.get("data", [])
    if not data:
        return "<p>No data to chart.</p>"

    if spec.get("type") == "donut":
        return _d3_donut(data, width, height)
    return _d3_bar(data, width, height, horizontal=spec.get("orientation") == "horizontal")


def _d3_bar(data: list[dict[str, Any]], width: int, height: int, *, horizontal: bool) -> str:
    import html as _html

    rows = "".join(
        f'<tr><td style="padding:2px 10px 2px 0">{_html.escape(str(d["label"]))}</td>'
        f'<td style="padding:2px"><div style="width:{max(2, int(d["value"] * 6))}px;height:12px;'
        f'background:{d.get("color", "#60a5fa")};border-radius:3px"></div></td>'
        f'<td style="padding:2px 0 2px 8px;color:#8b9bb4">{d["value"]}</td></tr>'
        for d in data
    )
    return (
        f'<svg role="img" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<text x="0" y="16" fill="#e6ecf7" font-size="14">{_html.escape("Findings")}</text></svg>'
        f'<table style="border-collapse:collapse;font:13px system-ui">{rows}</table>'
    )


def _d3_donut(data: list[dict[str, Any]], width: int, height: int) -> str:
    import math

    import html as _html

    total = sum(d["value"] for d in data) or 1
    radius = min(width, height) / 2 - 12
    inner = radius * 0.6
    cx = cy = min(width, height) / 2

    angle = -math.pi / 2
    parts = []
    for d in data:
        sweep = 2 * math.pi * d["value"] / total
        x1 = cx + radius * math.cos(angle)
        y1 = cy + radius * math.sin(angle)
        x2 = cx + radius * math.cos(angle + sweep)
        y2 = cy + radius * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        dpath = f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {radius} {radius} 0 {large} 1 {x2:.2f} {y2:.2f} Z"
        parts.append(f'<path d="{dpath}" fill="{d.get("color", "#60a5fa")}" fill-opacity="0.85"><title>{_html.escape(str(d["label"]))}: {d["value"]}</title></path>')
        angle += sweep

    legend = "".join(
        f'<div style="display:flex;gap:8px;align-items:center;margin:3px 0">'
        f'<span style="width:11px;height:11px;border-radius:3px;background:{d.get("color", "#60a5fa")}"></span>'
        f'<span style="font-size:12px">{_html.escape(str(d["label"]))}</span>'
        f'<span style="font-size:12px;color:#8b9bb4;margin-left:auto">{d["value"]}</span></div>'
        for d in data
    )
    inner_circle = f'<circle cx="{cx}" cy="{cy}" r="{inner}" fill="#0b0f19"/>'
    return (
        f'<div style="display:flex;gap:20px;align-items:center">'
        f'<svg width="{min(width, height)}" height="{min(width, height)}">{"".join(parts)}{inner_circle}</svg>'
        f'<div style="min-width:150px">{legend}</div></div>'
    )


def render_chart_html(source: Any, *, top: int = 12) -> str:
    """Render every chart in the bundle as one HTML fragment."""
    bundle = chart_bundle(source, top=top)
    parts = []
    for name, spec in bundle.items():
        body = _d3_donut(spec["data"], 300, 300) if spec.get("type") == "donut" else _d3_bar(
            spec["data"], 700, 40, horizontal=spec.get("orientation") == "horizontal"
        )
        parts.append(
            f'<section style="margin:0 0 26px"><h3 style="font:600 12px system-ui;letter-spacing:.12em;'
            f'text-transform:uppercase;color:#8b9bb4;margin:0 0 10px">{name.replace("_", " ")}</h3>{body}</section>'
        )
    return "".join(parts)


def render_plotly_html(source: Any, *, top: int = 12) -> str:
    """Render the bundle as Plotly figures (returns the HTML of a div per chart)."""
    bundle = chart_bundle(source, top=top)
    fragments = []
    for index, (name, spec) in enumerate(bundle.items()):
        figure = to_plotly(spec, title=name.replace("_", " ").title())
        fragments.append(figure.to_html(full_html=False, include_plotlyjs="cdn" if index == 0 else False,
                                        config={"displayModeBar": False}))
    return "".join(fragments)


def save_chart_assets(source: Any, output_dir: str | Path, *, top: int = 15) -> dict[str, Path]:
    """Write ``charts.json`` plus D3 and Plotly HTML fragments."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    written = {"json": target / "charts.json"}
    written["json"].write_text(json.dumps(chart_bundle(source, top=top), indent=2), encoding="utf-8")

    try:
        written["d3"] = target / "charts_d3.html"
        written["d3"].write_text(render_chart_html(source, top=top), encoding="utf-8")
    except Exception:
        pass

    try:
        written["plotly"] = target / "charts_plotly.html"
        written["plotly"].write_text(render_plotly_html(source, top=top), encoding="utf-8")
    except Exception:
        pass

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        bundle = chart_bundle(source, top=top)
        figure, axes = plt.subplots(1, len(bundle), figsize=(4.5 * len(bundle), 3.6))
        if len(bundle) == 1:
            axes = [axes]
        for axis, (name, spec) in zip(axes, bundle.items()):
            labels = [str(item["label"]) for item in spec["data"]]
            values = [item["value"] for item in spec["data"]]
            colors = [item.get("color", PALETTE[i % len(PALETTE)]) for i, item in enumerate(spec["data"])]
            if spec.get("type") == "donut":
                axis.pie(values, labels=labels, colors=colors, autopct="%1.0f%%", startangle=90)
            else:
                axis.barh(labels[::-1], values[::-1], color=colors[::-1])
            axis.set_title(name.replace("_", " ").title(), fontsize=11)
            axis.tick_params(labelsize=8)
        figure.tight_layout()
        written["matplotlib"] = target / "charts.png"
        figure.savefig(written["matplotlib"], dpi=160)
        plt.close(figure)
    except Exception:
        pass

    return written


__all__ = [
    "chart_bundle",
    "render_chart_html",
    "render_plotly_html",
    "save_chart_assets",
    "to_d3",
    "to_plotly",
]