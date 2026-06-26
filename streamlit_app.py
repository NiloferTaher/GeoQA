from __future__ import annotations

import base64
import tempfile
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from geoqa.conversion import (
    default_vector_layer_name,
    export_vector_layer,
    layer_preview_geojson,
    list_vector_layers,
    load_vector_dataset,
    resolve_uploaded_dataset,
    summarize_vector_layer,
    table_preview_frame,
)
from geoqa.fix import drop_null_geometries, make_geometries_valid, remove_duplicate_vertices
from geoqa.thermal import ThermalGuard, ThermalLimitExceeded


st.set_page_config(page_title="GeoQA", layout="wide")
st.title("GeoQA: Data Converter and Geometry Fixer")
st.caption("Inspect vector data, apply deterministic geometry fixes, and optionally export cleaned outputs.")

with st.sidebar:
    st.header("Options")
    app_mode = st.radio("Page", ["Inspect / Fix", "Convert / Export"])
    if app_mode == "Convert / Export":
        target_format = st.selectbox(
            "Convert to",
            ["keep original", "geojson", "csv", "geoparquet", "gpkg", "kml", "shapefile"],
        )
    else:
        target_format = "keep original"
    run_basic_fixes = st.checkbox("Apply basic geometry fixes", value=True)
    include_make_valid = st.checkbox("Repair invalid/self-intersecting polygons", value=True)
    include_drop_null = st.checkbox("Drop null geometries", value=True)
    include_dedupe = st.checkbox("Remove duplicate vertices", value=True)
    point_label_mode = st.selectbox("Point labels", ["On", "Auto", "Off"], index=0)


def _upload_signature(files: list[object]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((getattr(file, "name", ""), int(getattr(file, "size", 0) or 0)) for file in files))


def _normalize_local_path_input(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


def _local_path_signature(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path), int(stat.st_size), int(stat.st_mtime))


def _fix_signature() -> tuple[bool, bool, bool, bool]:
    return (run_basic_fixes, include_make_valid, include_drop_null, include_dedupe)


def _best_point_label(properties: dict[str, Any]) -> str | None:
    candidates = [
        "name",
        "NAME",
        "namelsad",
        "NAMELSAD",
        "place",
        "PLACE",
        "city",
        "CITY",
        "label",
        "LABEL",
        "geoid",
        "GEOID",
    ]
    for key in candidates:
        value = properties.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _iter_positions(value: object):
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            yield float(value[0]), float(value[1])
        else:
            for item in value:
                yield from _iter_positions(item)


def _geojson_center(payload: dict) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = _geojson_bounds(payload)
    return (min_x + max_x) / 2, (min_y + max_y) / 2


def _geojson_bounds(payload: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for feature in payload.get("features", []):
        geometry = feature.get("geometry") or {}
        for x, y in _iter_positions(geometry.get("coordinates")):
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        return -1.0, 19.0, 1.0, 21.0
    return min(xs), min(ys), max(xs), max(ys)


def _zoom_for_bounds(min_x: float, min_y: float, max_x: float, max_y: float) -> float:
    span = max(max_x - min_x, max_y - min_y)
    if span > 120:
        return 2
    if span > 60:
        return 3
    if span > 30:
        return 4
    if span > 15:
        return 5
    if span > 8:
        return 6
    if span > 4:
        return 7
    if span > 2:
        return 8
    if span > 1:
        return 9
    if span > 0.5:
        return 10
    if span > 0.25:
        return 11
    return 12


def _preview_map(
    geojson_text: str,
    *,
    fill_color: list[int] | None = None,
    line_color: list[int] | None = None,
    theme: dict[str, Any] | None = None,
) -> Any:
    try:
        import json
        import folium
        from streamlit_folium import st_folium
    except Exception:
        st.info("Interactive map preview is unavailable in this environment. Use the preview-data tabs below to inspect the payload.")
        return

    try:
        payload = json.loads(geojson_text)
        min_x, min_y, max_x, max_y = _geojson_bounds(payload)
        longitude, latitude = _geojson_center(payload)
        applied_theme = theme or {}
        base_fill = fill_color or applied_theme.get("fill_color") or [30, 136, 229, 80]
        base_line = line_color or applied_theme.get("line_color") or [30, 136, 229]
        point_color = applied_theme.get("point_color") or base_line
        map_obj = folium.Map(
            location=[latitude, longitude],
            zoom_start=max(2, int(_zoom_for_bounds(min_x, min_y, max_x, max_y))),
            control_scale=True,
            tiles="CartoDB positron",
        )

        def popup_html(feature: dict[str, Any]) -> str:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            rows = [f"<div style='font-weight:700;margin-bottom:0.35rem;'>{escape(applied_theme.get('label', 'Feature'))}</div>"]
            rows.append(f"<div><b>geometry</b>: {escape(str(geometry.get('type', 'Unknown')))}</div>")
            for key, value in props.items():
                safe_value = _json_safe_value(value)
                if safe_value is None or str(safe_value).strip() == "":
                    continue
                rows.append(f"<div><b>{escape(str(key))}</b>: {escape(str(safe_value))}</div>")
            return "".join(rows)

        point_records = []
        for feature in payload.get("features", []):
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            geometry_type = geometry.get("type")
            label = _best_point_label(properties)
            popup = folium.Popup(popup_html(feature), max_width=420)
            if geometry_type == "Point":
                coordinates = geometry.get("coordinates") or []
                if len(coordinates) < 2:
                    continue
                lon, lat = coordinates[0], coordinates[1]
                point_records.append((lat, lon, label, popup))
            elif geometry_type == "MultiPoint":
                for coordinates in geometry.get("coordinates") or []:
                    if len(coordinates) < 2:
                        continue
                    lon, lat = coordinates[0], coordinates[1]
                    point_records.append((lat, lon, label, popup))
            else:
                style = {
                    "color": f"rgb({base_line[0]}, {base_line[1]}, {base_line[2]})",
                    "weight": 2,
                    "fillColor": f"rgba({base_fill[0]}, {base_fill[1]}, {base_fill[2]}, {base_fill[3] / 255:.3f})",
                    "fillOpacity": max(0.10, min(0.45, base_fill[3] / 255)),
                }
                geojson_layer = folium.GeoJson(
                    feature,
                    style_function=lambda _: style,
                    highlight_function=lambda _: {"weight": 3, "fillOpacity": 0.30},
                )
                geojson_layer.add_child(popup)
                geojson_layer.add_to(map_obj)

        show_labels = False
        labels_mode = point_label_mode
        if labels_mode == "On":
            show_labels = True
        elif labels_mode == "Auto" and len([record for record in point_records if record[2]]) <= 15:
            show_labels = True

        for lat, lon, label, popup in point_records:
            marker = folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color=f"rgb({point_color[0]}, {point_color[1]}, {point_color[2]})",
                weight=2,
                fill=True,
                fill_color=f"rgb({point_color[0]}, {point_color[1]}, {point_color[2]})",
                fill_opacity=0.88,
                popup=popup,
            )
            if label and show_labels:
                marker.add_child(
                    folium.Tooltip(
                        label,
                        permanent=True,
                        direction="top",
                        offset=(0, -8),
                        opacity=0.95,
                        style=(
                            "background: rgba(32, 35, 41, 0.86); color: white; border: 1px solid rgba(255,255,255,0.55); "
                            "border-radius: 4px; padding: 2px 6px; font-size: 11px;"
                        ),
                    )
                )
            marker.add_to(map_obj)

        bounds = [[float(min_y), float(min_x)], [float(max_y), float(max_x)]]
        if bounds[0] != bounds[1]:
            map_obj.fit_bounds(bounds, padding=(18, 18))

        st.markdown(
            '<div style="border:1px solid rgba(255,255,255,0.82);border-radius:0.8rem;overflow:hidden;box-shadow:0 0 0 1px rgba(255,255,255,0.10);">',
            unsafe_allow_html=True,
        )
        result = st_folium(
            map_obj,
            height=620,
            use_container_width=True,
            returned_objects=[],
            key="geoqa_preview_map",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return result
    except Exception as exc:
        st.warning(f"Interactive map preview is unavailable: {exc}")
        st.info("Use the preview-data tabs below to inspect the payload.")
        return None


def _folium_bounds(payload: dict) -> list[list[float]] | None:
    min_x, min_y, max_x, max_y = _geojson_bounds(payload)
    bounds = [[float(min_y), float(min_x)], [float(max_y), float(max_x)]]
    if bounds[0] == bounds[1]:
        return None
    return bounds
def _attributes_preview_frame(frame: Any) -> Any:
    columns = list(getattr(frame, "columns", []))
    attribute_columns = [column for column in columns if str(column).lower() != "geometry"]
    if not attribute_columns:
        return frame.iloc[:, 0:0] if hasattr(frame, "iloc") else frame
    return frame[attribute_columns]


def _dominant_geometry(summary: dict[str, Any]) -> str:
    geometry_types = summary.get("geometry_types") or {}
    if not geometry_types:
        return "unknown"
    return max(geometry_types, key=geometry_types.get).lower()


def _infer_preview_theme(layer: Any, summary: dict[str, Any], source_label: str, source_format: str) -> dict[str, Any]:
    columns = {str(column).lower() for column in getattr(layer, "columns", [])}
    dominant_geometry = _dominant_geometry(summary)
    source_text = f"{source_label} {source_format}".lower()

    theme = {
        "label": "Generic",
        "symbol": "●",
        "fill_color": [64, 160, 255, 72],
        "line_color": [86, 171, 255],
        "point_color": [86, 171, 255],
        "legend_title": "Layer styling",
        "legend_text": "Generic vector preview inferred from geometry and schema.",
    }

    if "point" in dominant_geometry:
        theme.update(
            {
                "label": "Points",
                "symbol": "●",
                "fill_color": [255, 183, 77, 110],
                "line_color": [255, 183, 77],
                "point_color": [255, 183, 77],
                "legend_title": "Point features",
                "legend_text": "Point markers are emphasized with a visible symbol overlay for inspection.",
            }
        )
        if {"name", "population", "feature_code", "geonameid"} & columns or "cities" in source_text or "places" in source_text:
            theme.update(
                {
                    "label": "Cities / Places",
                    "symbol": "◎",
                    "fill_color": [255, 125, 80, 120],
                    "line_color": [255, 125, 80],
                    "point_color": [255, 125, 80],
                    "legend_title": "Places",
                    "legend_text": "Point markers represent named places or settlement-like records.",
                }
            )
        elif {"site_no", "agency_cd", "datetime"} & columns:
            theme.update(
                {
                    "label": "Monitoring Sites",
                    "symbol": "▲",
                    "fill_color": [0, 200, 190, 120],
                    "line_color": [0, 200, 190],
                    "point_color": [0, 200, 190],
                    "legend_title": "Monitoring points",
                    "legend_text": "Point markers represent sites or measurement locations.",
                }
            )
        elif {"substance", "waterway", "network_type"} & columns or "water" in source_text:
            theme.update(
                {
                    "label": "Water Network Points",
                    "symbol": "◆",
                    "fill_color": [72, 169, 255, 120],
                    "line_color": [72, 169, 255],
                    "point_color": [72, 169, 255],
                    "legend_title": "Water points",
                    "legend_text": "Point markers represent water-network or hydro-related records.",
                }
            )
    elif "line" in dominant_geometry:
        theme.update(
            {
                "label": "Lines",
                "symbol": "━",
                "fill_color": [255, 183, 77, 40],
                "line_color": [255, 183, 77],
                "point_color": [255, 183, 77],
                "legend_title": "Line features",
                "legend_text": "Linework is emphasized with a bright stroke against the darker basemap.",
            }
        )
        if {"highway", "linearid", "fullname", "rttyp", "road", "roads"} & columns or "roads" in source_text:
            theme.update(
                {
                    "label": "Roads",
                    "symbol": "━",
                    "fill_color": [255, 167, 38, 40],
                    "line_color": [255, 167, 38],
                    "point_color": [255, 167, 38],
                    "legend_title": "Road network",
                    "legend_text": "Orange linework indicates road or transport-style features.",
                }
            )
        elif {"waterway", "substance", "network_type"} & columns or "water" in source_text:
            theme.update(
                {
                    "label": "Water Network",
                    "symbol": "≈",
                    "fill_color": [72, 169, 255, 40],
                    "line_color": [72, 169, 255],
                    "point_color": [72, 169, 255],
                    "legend_title": "Water linework",
                    "legend_text": "Blue linework indicates water or utility-style network features.",
                }
            )
    elif "polygon" in dominant_geometry:
        theme.update(
            {
                "label": "Polygons",
                "symbol": "■",
                "fill_color": [86, 171, 255, 68],
                "line_color": [86, 171, 255],
                "point_color": [86, 171, 255],
                "legend_title": "Area features",
                "legend_text": "Polygon fill is semi-transparent so boundaries remain visible.",
            }
        )
        if {"shapeiso", "boundarytype", "admin_level", "geoid", "tractce"} & columns or "adm" in source_text or "tract" in source_text:
            theme.update(
                {
                    "label": "Boundaries / Areas",
                    "symbol": "■",
                    "fill_color": [96, 165, 250, 62],
                    "line_color": [120, 190, 255],
                    "point_color": [120, 190, 255],
                    "legend_title": "Boundary polygons",
                    "legend_text": "Boundary or census-style area polygons are shown with a light blue fill.",
                }
            )

    return theme


def _render_map_legend(theme: dict[str, Any], summary: dict[str, Any]) -> None:
    geometry_types = summary.get("geometry_types") or {}
    geometry_label = ", ".join(f"{name}: {count}" for name, count in geometry_types.items()) if geometry_types else "Unknown geometry mix"
    st.markdown(
        (
            '<div style="border:1px solid rgba(255,255,255,0.10);border-radius:0.75rem;'
            'padding:0.75rem 0.9rem;background:rgba(255,255,255,0.03);margin-bottom:0.8rem;">'
            f'<div style="font-weight:700;margin-bottom:0.25rem;">Legend: {theme["legend_title"]}</div>'
            f'<div style="margin-bottom:0.35rem;">'
            f'<span style="display:inline-block;min-width:1.6rem;font-weight:700;color:rgb({theme["point_color"][0]}, {theme["point_color"][1]}, {theme["point_color"][2]});">{theme["symbol"]}</span>'
            f'{theme["label"]}</div>'
            f'<div style="font-size:0.95rem;color:rgba(255,255,255,0.78);margin-bottom:0.25rem;">{theme["legend_text"]}</div>'
            f'<div style="font-size:0.9rem;color:rgba(255,255,255,0.65);">Geometry mix: {geometry_label}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def _preview_data_tabs(geojson_text: str) -> None:
    import json

    parsed_tab, text_tab = st.tabs(["Parsed Preview Data", "Raw Preview GeoJSON"])
    with parsed_tab:
        try:
            st.json(json.loads(geojson_text), expanded=False)
        except Exception as exc:
            st.warning(f"Unable to parse preview GeoJSON: {exc}")
    with text_tab:
        st.text_area("Preview GeoJSON", geojson_text, height=360)


def _render_download_link(label: str, payload: bytes, file_name: str, mime: str = "application/octet-stream") -> None:
    encoded = base64.b64encode(payload).decode("ascii")
    st.markdown(
        (
            f'<a href="data:{mime};base64,{encoded}" download="{file_name}" '
            'style="display:inline-block;padding:0.55rem 0.9rem;border-radius:0.5rem;'
            'background:#8f2d2d;color:white;text-decoration:none;font-weight:600;'
            'border:1px solid #a94848;box-shadow:none;">'
            f"{label}</a>"
        ),
        unsafe_allow_html=True,
    )


def _geometry_token(geom: object) -> str | None:
    if geom is None:
        return None
    return getattr(geom, "wkt", str(geom))


def _count_geometry_changes(before_layer: Any, after_layer: Any) -> int:
    if "geometry" not in getattr(before_layer, "columns", []) or "geometry" not in getattr(after_layer, "columns", []):
        return 0
    common_index = before_layer.index.intersection(after_layer.index)
    changed = 0
    for idx in common_index:
        if _geometry_token(before_layer.at[idx, "geometry"]) != _geometry_token(after_layer.at[idx, "geometry"]):
            changed += 1
    return changed


def _best_identifier_column(layer: Any) -> str | None:
    columns = [column for column in getattr(layer, "columns", []) if column != "geometry"]
    preferred = [
        "id",
        "ID",
        "fid",
        "FID",
        "objectid",
        "OBJECTID",
        "name",
        "NAME",
        "adm1_code",
        "adm1_cod_1",
        "iso_3166_2",
    ]
    for candidate in preferred:
        if candidate in columns:
            return candidate
    return columns[0] if columns else None


def _shorten_text(value: str | None, limit: int = 220) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def _describe_step_details(before_layer: Any, after_layer: Any, label: str, *, max_rows: int = 25) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    identifier_column = _best_identifier_column(before_layer)

    removed_indexes = before_layer.index.difference(after_layer.index)
    for idx in removed_indexes[:max_rows]:
        row = before_layer.loc[idx]
        details.append(
            {
                "row_index": int(idx) if isinstance(idx, int) else str(idx),
                "feature_id": row.get(identifier_column) if identifier_column else None,
                "column": "geometry",
                "step": label,
                "change_type": "row removed",
                "why": "Feature had null geometry, so it was removed.",
                "before": _shorten_text(_geometry_token(row.get("geometry"))),
                "after": None,
                "before_full": _geometry_token(row.get("geometry")),
                "after_full": None,
            }
        )

    common_index = before_layer.index.intersection(after_layer.index)
    for idx in common_index:
        before_geom = before_layer.at[idx, "geometry"] if "geometry" in before_layer.columns else None
        after_geom = after_layer.at[idx, "geometry"] if "geometry" in after_layer.columns else None
        before_token = _geometry_token(before_geom)
        after_token = _geometry_token(after_geom)
        if before_token == after_token:
            continue
        before_row = before_layer.loc[idx]
        why = {
            "Remove duplicate vertices": "Duplicate consecutive coordinates were removed from the geometry.",
            "Repair invalid/self-intersecting polygons": "GeoQA rewrote the geometry to make it valid where possible.",
        }.get(label, "GeoQA changed the geometry during the selected fix step.")
        details.append(
            {
                "row_index": int(idx) if isinstance(idx, int) else str(idx),
                "feature_id": before_row.get(identifier_column) if identifier_column else None,
                "column": "geometry",
                "step": label,
                "change_type": "geometry changed",
                "why": why,
                "before": _shorten_text(before_token),
                "after": _shorten_text(after_token),
                "before_full": before_token,
                "after_full": after_token,
            }
        )
        if len(details) >= max_rows:
            break

    return details


def _enabled_fix_steps() -> list[dict[str, Any]]:
    return [
        {
            "id": "drop_null_geometries",
            "label": "Drop null geometries",
            "enabled": include_drop_null,
            "fn": drop_null_geometries,
        },
        {
            "id": "remove_duplicate_vertices",
            "label": "Remove duplicate vertices",
            "enabled": include_dedupe,
            "fn": remove_duplicate_vertices,
        },
        {
            "id": "make_geometries_valid",
            "label": "Repair invalid/self-intersecting polygons",
            "enabled": include_make_valid,
            "fn": make_geometries_valid,
        },
    ]


def _suggest_chunk_size(row_count: int) -> int:
    if row_count <= 1000:
        return 200
    if row_count <= 5000:
        return 500
    if row_count <= 20000:
        return 1000
    return 2000


def _concat_chunks(chunks: list[Any], source_layer: Any) -> Any:
    if not chunks:
        return source_layer.iloc[0:0].copy()
    import geopandas as gpd
    import pandas as pd

    combined = pd.concat(chunks)
    if source_layer.__class__.__name__ == "GeoDataFrame":
        geometry_column = getattr(source_layer, "geometry", None)
        geometry_name = getattr(geometry_column, "name", "geometry") if geometry_column is not None else "geometry"
        return gpd.GeoDataFrame(combined, geometry=geometry_name, crs=getattr(source_layer, "crs", None))
    return combined


def _base_feedback(layer: Any) -> dict[str, Any]:
    return {
        "automatic": True,
        "run_basic_fixes": run_basic_fixes,
        "requested_steps": [step["label"] for step in _enabled_fix_steps() if step["enabled"]],
        "input_rows": len(layer),
        "output_rows": len(layer),
        "total_rows_removed": 0,
        "total_geometry_changes": 0,
        "steps": [],
        "summary": "",
    }


def _record_step_result(
    feedback: dict[str, Any],
    label: str,
    rows_removed: int,
    geometry_changes: int,
    details: list[dict[str, Any]] | None = None,
) -> None:
    status = "applied" if rows_removed > 0 or geometry_changes > 0 else "no applicable changes found"
    reason = (
        f"Removed {rows_removed} row(s) and changed {geometry_changes} geometry value(s)."
        if status == "applied"
        else "Step completed, but GeoQA did not find anything to change for this layer."
    )
    feedback["steps"].append(
        {
            "step": label,
            "status": status,
            "reason": reason,
            "rows_removed": rows_removed,
            "geometry_changes": geometry_changes,
            "details": details or [],
        }
    )
    feedback["total_rows_removed"] += max(rows_removed, 0)
    feedback["total_geometry_changes"] += geometry_changes


def _record_skipped_step(feedback: dict[str, Any], label: str) -> None:
    feedback["steps"].append(
        {
            "step": label,
            "status": "skipped",
            "reason": "Option not selected.",
            "rows_removed": 0,
            "geometry_changes": 0,
            "details": [],
        }
    )


def _direct_fix_pipeline(layer: Any, guard: ThermalGuard) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    feedback = _base_feedback(layer)
    if not run_basic_fixes:
        feedback["summary"] = "Automatic geometry fixes are turned off. The preview and export use the loaded dataset as-is."
        return layer, feedback, None

    current = layer
    steps = _enabled_fix_steps()
    for index, step in enumerate(steps):
        if not step["enabled"]:
            _record_skipped_step(feedback, step["label"])
            continue
        try:
            guard.wait_until_safe(stage=f"streamlit_fix_{step['id']}")
        except ThermalLimitExceeded as exc:
            feedback["summary"] = (
                f"Fix workflow stopped for thermal safety before '{step['label']}'. "
                f"Alternative available: resume with chunking from the last completed step."
            )
            feedback["output_rows"] = len(current)
            return current, feedback, {
                "status": "awaiting_chunk_choice",
                "message": str(exc),
                "suggested_chunk_size": _suggest_chunk_size(len(current)),
                "step_index": index,
                "current_layer": current,
                "feedback": feedback,
                "fix_signature": _fix_signature(),
            }

        before = current
        after = step["fn"](current)
        rows_removed = len(before) - len(after)
        geometry_changes = _count_geometry_changes(before, after)
        details = _describe_step_details(before, after, step["label"])
        _record_step_result(feedback, step["label"], rows_removed, geometry_changes, details)
        current = after

        try:
            guard.check_or_raise(stage=f"streamlit_fix_{step['id']}_post")
        except ThermalLimitExceeded as exc:
            next_enabled = any(later_step["enabled"] for later_step in steps[index + 1 :])
            if not next_enabled:
                feedback["output_rows"] = len(current)
                feedback["summary"] = (
                    f"Automatic geometry fixes finished. Rows removed: {feedback['total_rows_removed']}. "
                    f"Geometry values changed: {feedback['total_geometry_changes']}."
                )
                return current, feedback, None
            feedback["summary"] = (
                f"Fix workflow paused for thermal safety after '{step['label']}'. "
                f"Alternative available: resume remaining work with chunking."
            )
            feedback["output_rows"] = len(current)
            return current, feedback, {
                "status": "awaiting_chunk_choice",
                "message": str(exc),
                "suggested_chunk_size": _suggest_chunk_size(len(current)),
                "step_index": index + 1,
                "current_layer": current,
                "feedback": feedback,
                "fix_signature": _fix_signature(),
            }

    feedback["output_rows"] = len(current)
    feedback["summary"] = (
        f"Automatic geometry fixes ran on upload. Rows removed: {feedback['total_rows_removed']}. "
        f"Geometry values changed: {feedback['total_geometry_changes']}."
    )
    return current, feedback, None


def _chunked_fix_resume(resume_state: dict[str, Any], guard: ThermalGuard) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    feedback = resume_state["feedback"]
    steps = _enabled_fix_steps()
    current = resume_state["current_layer"]
    step_index = int(resume_state["step_index"])
    chunk_size = int(resume_state["suggested_chunk_size"])

    while step_index < len(steps):
        step = steps[step_index]
        if not step["enabled"]:
            _record_skipped_step(feedback, step["label"])
            step_index += 1
            continue

        source_layer = resume_state.get("step_source_layer", current)
        chunk_start = int(resume_state.get("chunk_start", 0))
        completed_parts = list(resume_state.get("completed_parts", []))

        try:
            while chunk_start < len(source_layer):
                guard.wait_until_safe(stage=f"streamlit_chunk_{step['id']}_{chunk_start}")
                chunk = source_layer.iloc[chunk_start : chunk_start + chunk_size].copy()
                completed_parts.append(step["fn"](chunk))
                chunk_start += chunk_size
                guard.check_or_raise(stage=f"streamlit_chunk_{step['id']}_{chunk_start}_post")
        except ThermalLimitExceeded as exc:
            feedback["summary"] = (
                f"Chunked fix workflow paused for thermal safety during '{step['label']}'. "
                "You can continue from the last completed chunk."
            )
            feedback["output_rows"] = len(current)
            return current, feedback, {
                "status": "chunked_paused",
                "message": str(exc),
                "suggested_chunk_size": chunk_size,
                "step_index": step_index,
                "current_layer": current,
                "step_source_layer": source_layer,
                "completed_parts": completed_parts,
                "chunk_start": chunk_start,
                "feedback": feedback,
                "fix_signature": _fix_signature(),
            }

        after = _concat_chunks(completed_parts, source_layer)
        rows_removed = len(source_layer) - len(after)
        geometry_changes = _count_geometry_changes(source_layer, after)
        details = _describe_step_details(source_layer, after, step["label"])
        _record_step_result(feedback, step["label"], rows_removed, geometry_changes, details)
        current = after
        step_index += 1

        resume_state.pop("step_source_layer", None)
        resume_state.pop("completed_parts", None)
        resume_state.pop("chunk_start", None)

    feedback["output_rows"] = len(current)
    feedback["summary"] = (
        f"Chunked fix workflow completed. Rows removed: {feedback['total_rows_removed']}. "
        f"Geometry values changed: {feedback['total_geometry_changes']}."
    )
    return current, feedback, None


def _refresh_processed_views(layer: Any) -> None:
    st.session_state["geoqa_working_layer"] = layer
    st.session_state["geoqa_preview_geojson"] = layer_preview_geojson(layer, limit=50)
    st.session_state["geoqa_table_preview"] = table_preview_frame(layer, limit=50)


def _infer_source_format(uploaded_files: list[Any], resolved_path: Path) -> str:
    suffix = resolved_path.suffix.lower()
    if len(uploaded_files) > 1 and suffix == ".shp":
        return "shapefile"
    return {
        ".geojson": "geojson",
        ".json": "geojson",
        ".csv": "csv",
        ".gpkg": "gpkg",
        ".kml": "kml",
        ".parquet": "geoparquet",
        ".shp": "shapefile",
        ".zip": "shapefile",
        ".pbf": "osm_pbf",
        ".osm": "osm_pbf",
    }.get(suffix, "geojson")


def _effective_output_format(source_format: str) -> str:
    return source_format if target_format == "keep original" else target_format


def _supports_direct_export(format_name: str) -> bool:
    return format_name in {"geojson", "csv", "geoparquet", "gpkg", "kml", "shapefile"}


def _set_processing_stage(stage_key: str, detail: str = "") -> None:
    st.session_state["geoqa_processing_stage"] = stage_key
    st.session_state["geoqa_processing_detail"] = detail


def _render_processing_status() -> None:
    stage = st.session_state.get("geoqa_processing_stage", "idle")
    detail = st.session_state.get("geoqa_processing_detail", "")
    stage_meta = {
        "idle": (0, "Idle"),
        "resolving": (15, "Resolving upload"),
        "inspecting_layers": (30, "Inspecting source layers"),
        "opening_layer": (50, "Opening selected layer"),
        "applying_fixes": (75, "Applying selected fixes"),
        "rendering_preview": (90, "Preparing preview"),
        "ready": (100, "Ready"),
    }
    percent, label = stage_meta.get(stage, (0, "Working"))
    status_cols = st.columns([5, 2])
    with status_cols[0]:
        st.progress(percent, text=f"{label}{': ' + detail if detail else ''}")
    with status_cols[1]:
        st.metric("Status", label)


def _details_preview_table(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in details:
        rows.append(
            {
                "row_index": entry.get("row_index"),
                "feature_id": entry.get("feature_id"),
                "column": entry.get("column"),
                "change_type": entry.get("change_type"),
                "why": entry.get("why"),
                "before": entry.get("before"),
                "after": entry.get("after"),
            }
        )
    return rows


def _json_safe_scalar(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _json_safe_value(value: Any) -> Any:
    value = _json_safe_scalar(value)
    if isinstance(value, dict):
        return {str(_json_safe_scalar(key)): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return value


def _change_details_geojson(details: list[dict[str, Any]], geometry_key: str) -> str | None:
    import json
    from shapely import wkt

    features = []
    for entry in details:
        geometry_text = entry.get(geometry_key)
        if not geometry_text:
            continue
        try:
            geometry = wkt.loads(geometry_text)
        except Exception:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "row_index": _json_safe_scalar(entry.get("row_index")),
                    "feature_id": _json_safe_scalar(entry.get("feature_id")),
                    "step": _json_safe_scalar(entry.get("step")),
                    "change_type": _json_safe_scalar(entry.get("change_type")),
                },
                "geometry": _json_safe_value(geometry.__geo_interface__),
            }
        )
    if not features:
        return None
    return json.dumps(_json_safe_value({"type": "FeatureCollection", "features": features}))


source_mode = st.radio(
    "Source input",
    ["Upload file(s)", "Use local file path"],
    horizontal=True,
    help="Use a local path for larger datasets that are already on disk and do not need browser upload.",
)

uploaded_files: list[Any] = []
resolved_path: Path | None = None
source_label = ""
source_format = None

if source_mode == "Upload file(s)":
    uploaded_files = st.file_uploader(
        "Upload a vector dataset",
        type=["geojson", "json", "zip", "gpkg", "kml", "csv", "parquet", "shp", "dbf", "shx", "prj", "cpg", "pbf", "osm"],
        accept_multiple_files=True,
        help=(
            "Upload a single GeoJSON/GPKG/KML/CSV/GeoParquet/OSM PBF/ZIP file, "
            "or upload the full Shapefile set together (.shp, .dbf, .shx, and optional .prj/.cpg)."
        ),
    )
    if uploaded_files:
        source_label = "uploaded"
elif source_mode == "Use local file path":
    local_source_text = st.text_input(
        "Local dataset path",
        value=st.session_state.get("geoqa_local_source_input", ""),
        placeholder="path/to/your/dataset.geojson",
        help="Point GeoQA at a dataset already on disk. This avoids browser upload failures for larger local files.",
    )
    st.session_state["geoqa_local_source_input"] = local_source_text
    normalized_local_source = _normalize_local_path_input(local_source_text)
    if normalized_local_source:
        candidate = Path(normalized_local_source)
        if candidate.exists():
            resolved_path = candidate
            source_label = str(candidate)
        else:
            st.error(f"Local dataset path does not exist: {candidate}")
            st.stop()

if uploaded_files or resolved_path is not None:
    guard = ThermalGuard.strict()
    upload_signature = (
        _upload_signature(uploaded_files)
        if uploaded_files
        else _local_path_signature(resolved_path)
    )
    try:
        if st.session_state.get("geoqa_upload_signature") != upload_signature:
            with st.spinner("Loading dataset..."):
                _set_processing_stage(
                    "resolving",
                    "Saving uploaded files" if uploaded_files else "Resolving local dataset path",
                )
                local_path = resolve_uploaded_dataset(uploaded_files) if uploaded_files else resolved_path
                guard.wait_until_safe(stage="streamlit_load")
                _set_processing_stage("inspecting_layers", "Discovering available layers")
                available_layers = list_vector_layers(local_path)
                st.session_state["geoqa_upload_signature"] = upload_signature
                st.session_state["geoqa_local_path"] = str(local_path)
                st.session_state["geoqa_available_layers"] = available_layers
                st.session_state["geoqa_selected_layer"] = default_vector_layer_name(available_layers)
                st.session_state["geoqa_loaded_layer"] = None
                st.session_state["geoqa_loaded_summary"] = None
                st.session_state["geoqa_source_format"] = (
                    _infer_source_format(uploaded_files, local_path) if uploaded_files else _infer_source_format([], local_path)
                )
                st.session_state["geoqa_source_label"] = source_label
                st.session_state["geoqa_fix_signature"] = None
                st.session_state["geoqa_resume_state"] = None
                st.session_state["geoqa_feedback"] = None
                st.session_state["geoqa_working_layer"] = None
                st.session_state["geoqa_preview_geojson"] = None
                st.session_state["geoqa_table_preview"] = None
                guard.check_or_raise(stage="streamlit_load_post")
                _set_processing_stage("ready", "Upload inspection complete")
    except ThermalLimitExceeded as exc:
        _set_processing_stage("idle")
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        _set_processing_stage("idle")
        st.error(f"Unable to load dataset: {exc}")
        st.stop()

    local_path = Path(st.session_state["geoqa_local_path"])
    available_layers = st.session_state.get("geoqa_available_layers") or []
    source_format = st.session_state["geoqa_source_format"]

    if available_layers:
        selected_layer = st.selectbox(
            "Source layer",
            available_layers,
            index=max(0, available_layers.index(st.session_state.get("geoqa_selected_layer")))
            if st.session_state.get("geoqa_selected_layer") in available_layers
            else 0,
            help="OSM/PBF and other multi-layer sources can expose multiple geometry layers. Choose which one to inspect.",
        )
        if st.session_state.get("geoqa_selected_layer") != selected_layer:
            st.session_state["geoqa_selected_layer"] = selected_layer
            st.session_state["geoqa_loaded_layer"] = None
            st.session_state["geoqa_loaded_summary"] = None
            st.session_state["geoqa_fix_signature"] = None
            st.session_state["geoqa_resume_state"] = None
            st.session_state["geoqa_feedback"] = None
            st.session_state["geoqa_working_layer"] = None
            st.session_state["geoqa_preview_geojson"] = None
            st.session_state["geoqa_table_preview"] = None
            _set_processing_stage("opening_layer", f"Layer changed to {selected_layer}")
    else:
        selected_layer = None

    _render_processing_status()

    try:
        if st.session_state.get("geoqa_loaded_layer") is None:
            with st.spinner("Opening selected layer..."):
                _set_processing_stage("opening_layer", selected_layer or "Opening dataset")
                guard.wait_until_safe(stage="streamlit_layer_open")
                layer = load_vector_dataset(local_path, ogr_layer=selected_layer)
                guard.check_or_raise(stage="streamlit_layer_open_post")
                st.session_state["geoqa_loaded_layer"] = layer
                st.session_state["geoqa_loaded_summary"] = summarize_vector_layer(layer)
                _set_processing_stage("ready", "Layer opened")
    except ThermalLimitExceeded as exc:
        _set_processing_stage("idle")
        st.error(str(exc))
        st.stop()
    except Exception as exc:
        _set_processing_stage("idle")
        st.error(f"Unable to open layer: {exc}")
        st.stop()

    layer = st.session_state["geoqa_loaded_layer"]
    summary = st.session_state["geoqa_loaded_summary"]
    fix_signature = _fix_signature()

    if st.session_state.get("geoqa_fix_signature") != fix_signature or st.session_state.get("geoqa_working_layer") is None:
        _set_processing_stage("applying_fixes", "Running deterministic fix workflow")
        working_layer, feedback, resume_state = _direct_fix_pipeline(layer, guard)
        st.session_state["geoqa_fix_signature"] = fix_signature
        st.session_state["geoqa_feedback"] = feedback
        st.session_state["geoqa_resume_state"] = resume_state
        _set_processing_stage("rendering_preview", "Refreshing preview and table")
        _refresh_processed_views(working_layer)
        _set_processing_stage("ready", "Preview ready")

    feedback = st.session_state.get("geoqa_feedback") or {}
    resume_state = st.session_state.get("geoqa_resume_state")
    working_layer = st.session_state["geoqa_working_layer"]
    preview_theme = _infer_preview_theme(
        working_layer,
        summary,
        st.session_state.get("geoqa_source_label", ""),
        source_format,
    )
    st.subheader("Processing Feedback")
    feedback_tab, summary_tab = st.tabs(["Feedback", "Dataset Summary"])
    with feedback_tab:
        st.write(feedback.get("summary", "No processing feedback is available yet."))
        if feedback:
            st.json(
                {
                    "automatic": feedback.get("automatic"),
                    "run_basic_fixes": feedback.get("run_basic_fixes"),
                    "requested_steps": feedback.get("requested_steps"),
                    "input_rows": feedback.get("input_rows"),
                    "output_rows": feedback.get("output_rows"),
                    "total_rows_removed": feedback.get("total_rows_removed"),
                    "total_geometry_changes": feedback.get("total_geometry_changes"),
                }
            )

        if resume_state:
            st.warning(f"Thermal stop reason: {resume_state['message']}")
            st.info(
                "Alternative available: use chunking to continue from the last completed step or chunk. "
                f"Suggested chunk size: {resume_state['suggested_chunk_size']} features."
            )
            action_columns = st.columns(2)
            continue_label = (
                "Use chunking and continue"
                if resume_state["status"] == "awaiting_chunk_choice"
                else "Continue from last place with chunking"
            )
            if action_columns[0].button(continue_label, key="geoqa_chunk_resume"):
                with st.spinner("Continuing fix workflow with chunking..."):
                    _set_processing_stage("applying_fixes", "Continuing with chunked fix workflow")
                    resumed_layer, resumed_feedback, new_resume = _chunked_fix_resume(resume_state, guard)
                    st.session_state["geoqa_feedback"] = resumed_feedback
                    st.session_state["geoqa_resume_state"] = new_resume
                    _set_processing_stage("rendering_preview", "Refreshing preview and table")
                    _refresh_processed_views(resumed_layer)
                    _set_processing_stage("ready", "Preview ready")
                st.rerun()
            if action_columns[1].button("Keep current result without chunking", key="geoqa_chunk_skip"):
                st.session_state["geoqa_resume_state"] = None
                feedback["summary"] = (
                    f"{feedback.get('summary', '').rstrip()} Current result kept without chunked continuation."
                ).strip()
                st.session_state["geoqa_feedback"] = feedback
                st.rerun()

        if feedback.get("steps"):
            st.subheader("Fix Step Results")
            st.table(
                [
                    {
                        "step": entry["step"],
                        "status": entry["status"],
                        "reason": entry["reason"],
                        "rows_removed": entry["rows_removed"],
                        "geometry_changes": entry["geometry_changes"],
                    }
                    for entry in feedback["steps"]
                ]
            )
            for step_result in feedback["steps"]:
                details = step_result.get("details") or []
                if not details:
                    continue
                with st.expander(f"Changed Features: {step_result['step']} ({len(details)})"):
                    st.caption(
                        "These are the first changed rows GeoQA detected for this step. "
                        "The affected column is `geometry`; feature IDs come from the first useful identifier column GeoQA could find."
                    )
                    st.dataframe(_details_preview_table(details), width="stretch")
                    before_geojson = _change_details_geojson(details, "before_full")
                    after_geojson = _change_details_geojson(details, "after_full")
                    if before_geojson or after_geojson:
                        before_tab, after_tab = st.tabs(["Before", "After"])
                        with before_tab:
                            if before_geojson:
                                _preview_map(
                                    before_geojson,
                                    fill_color=[180, 90, 90, 70],
                                    line_color=[180, 90, 90],
                                    theme=preview_theme,
                                )
                            else:
                                st.info("No before-geometry preview is available for this change set.")
                        with after_tab:
                            if after_geojson:
                                _preview_map(
                                    after_geojson,
                                    fill_color=[30, 136, 229, 80],
                                    line_color=[30, 136, 229],
                                    theme=preview_theme,
                                )
                            else:
                                st.info("No after-geometry preview is available for this change set.")
        st.caption(
            "Checked fix options run automatically on upload. “No applicable changes found” means the step executed but did not modify this dataset."
        )
    with summary_tab:
        st.json(
            {
                "source": st.session_state.get("geoqa_source_label"),
                "source_format": source_format,
                **summary,
            }
        )

    st.subheader(f"Preview - {preview_theme['label']}")
    st.caption("The map and preview-data tabs are inspection views only. They do not control the export format.")
    preview_geojson = st.session_state["geoqa_preview_geojson"]
    st.caption(
        f"Inferred preview theme: `{preview_theme['label']}`. "
        "This is a UI hint based on geometry and schema, not a formal validation result."
    )
    map_tab, preview_tab = st.tabs(["Map", "Preview Data"])
    with map_tab:
        _render_map_legend(preview_theme, summary)
        _preview_map(preview_geojson, theme=preview_theme)
        st.info("Click a marker or feature to open its popup. Point labels can be forced on from the sidebar when you need them.")
        st.info(
            "If a polygon looks wrong against the basemap, do not assume AI should redraw it. "
            "The map is showing the dataset geometry as provided. A mismatch usually means one of these: "
            "the source boundary is generalized, disputed, semantically wrong, or needs comparison against an authoritative reference layer."
        )
        st.caption(
            "The map now zooms to the layer bounds. For actual fix inspection, use the per-step before/after map previews in the feedback panel when they are available."
        )
    with preview_tab:
        _preview_data_tabs(preview_geojson)

    st.subheader("Attribute / Geometry Table")
    st.caption("This is the single table view for the current layer. It includes attributes plus geometry in WKT form.")
    st.dataframe(st.session_state["geoqa_table_preview"], width="stretch")

    if app_mode == "Convert / Export":
        st.subheader("Export")
        chosen_format = _effective_output_format(source_format)
        st.write(
            f"Source format: `{source_format}`. "
            f"Export target: `{chosen_format}`."
        )
        if target_format == "keep original" and not _supports_direct_export(chosen_format):
            st.warning(
                "Keeping the original format is not supported for this source type. "
                "Choose a supported export format such as GeoJSON, CSV, GeoParquet, GPKG, KML, or Shapefile."
            )
        else:
            try:
                with tempfile.TemporaryDirectory(prefix="geoqa_streamlit_export_") as tmpdir:
                    suffix_map = {
                        "geojson": ".geojson",
                        "csv": ".csv",
                        "geoparquet": ".parquet",
                        "gpkg": ".gpkg",
                        "kml": ".kml",
                        "shapefile": ".zip",
                    }
                    export_path = Path(tmpdir) / f"converted{suffix_map[chosen_format]}"
                    exported = export_vector_layer(working_layer, export_path, output_format=chosen_format)
                    export_bytes = exported.read_bytes()
                    _render_download_link(f"Download {chosen_format.upper()}", export_bytes, exported.name)
            except Exception as exc:
                st.warning(f"Export failed: {exc}")

st.markdown(
    """
Notes:
- `Use local file path` is useful for larger datasets already on disk because it bypasses browser upload failures.
- `Inspect / Fix` lets you preview and clean data without forcing conversion.
- `Convert / Export` is optional and separate from inspection.
- Shapefiles should be uploaded as either one `.zip` bundle or one complete multi-file set.
- OSM `.pbf` / `.osm` sources can expose multiple internal layers such as `points`, `lines`, or `multipolygons`.
- Basic geometry fixes are deterministic and local.
- If thermal safety stops a fix pass, the app can offer chunked continuation from the last completed step or chunk.
"""
)
