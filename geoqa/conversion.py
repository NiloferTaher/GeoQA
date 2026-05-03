from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZipInfo


@dataclass(slots=True, frozen=True)
class ArchiveSafetyLimits:
    max_member_count: int = 200
    max_uncompressed_size_mb: float = 512.0
    max_compression_ratio: float = 200.0


def _load_geopandas():
    try:
        import geopandas as gpd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Vector conversion requires GeoPandas.") from exc
    return gpd


def _guess_coordinate_columns(columns: list[str]) -> tuple[str, str]:
    lowered = {column.lower(): column for column in columns}
    x_candidates = [
        "longitude",
        "lon",
        "x",
        "lng",
        "intptlong",
        "intptlong_num",
        "centroid_lon",
        "long",
    ]
    y_candidates = [
        "latitude",
        "lat",
        "y",
        "intptlat",
        "intptlat_num",
        "centroid_lat",
    ]
    x_field = next((lowered[name] for name in x_candidates if name in lowered), None)
    y_field = next((lowered[name] for name in y_candidates if name in lowered), None)
    if x_field is None or y_field is None:
        raise ValueError("CSV input requires recognizable longitude/latitude columns.")
    return x_field, y_field


def _guess_geometry_column(columns: list[str]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in ("geometry", "geom", "wkt"):
        if candidate in lowered:
            return lowered[candidate]
    return None


def _validate_zip_member_name(info: ZipInfo) -> None:
    parts = Path(info.filename).parts
    if info.filename.startswith(("/", "\\")) or ".." in parts:
        raise ValueError(f"Unsafe archive member path detected: {info.filename!r}.")


def _scan_zip_archive(archive_path: Path, limits: ArchiveSafetyLimits) -> list[ZipInfo]:
    with ZipFile(archive_path) as archive:
        infos = archive.infolist()
    if len(infos) > limits.max_member_count:
        raise ValueError(
            f"Archive contains {len(infos)} members, above the configured safety limit of "
            f"{limits.max_member_count}."
        )
    total_size = 0
    for info in infos:
        _validate_zip_member_name(info)
        if info.flag_bits & 0x1:
            raise ValueError(f"Encrypted archive entries are not supported: {info.filename!r}.")
        total_size += info.file_size
        compressed_size = max(info.compress_size, 1)
        compression_ratio = info.file_size / compressed_size
        if compression_ratio > limits.max_compression_ratio:
            raise ValueError(
                f"Archive member {info.filename!r} exceeds the configured compression-ratio limit of "
                f"{limits.max_compression_ratio:.1f}."
            )
    total_size_mb = total_size / (1024 * 1024)
    if total_size_mb > limits.max_uncompressed_size_mb:
        raise ValueError(
            f"Archive expands to {total_size_mb:.2f} MB, above the configured safety limit of "
            f"{limits.max_uncompressed_size_mb:.2f} MB."
        )
    return infos


def _extract_zip_archive(archive_path: Path, *, limits: ArchiveSafetyLimits) -> Path:
    _scan_zip_archive(archive_path, limits)
    target_dir = Path(tempfile.mkdtemp(prefix="geoqa_archive_"))
    with ZipFile(archive_path) as archive:
        archive.extractall(target_dir)
    return target_dir


def _resolve_extracted_dataset(root_dir: Path) -> Path:
    shapefiles = sorted(root_dir.rglob("*.shp"))
    if len(shapefiles) == 1:
        return shapefiles[0]
    if len(shapefiles) > 1:
        raise ValueError("Archive contains multiple Shapefile datasets. Supply one dataset per archive.")

    kml_files = sorted(root_dir.rglob("*.kml"))
    if kml_files:
        return kml_files[0]

    geojson_files = sorted(root_dir.rglob("*.geojson"))
    if geojson_files:
        return geojson_files[0]

    json_files = sorted(root_dir.rglob("*.json"))
    if json_files:
        return json_files[0]

    gpkg_files = sorted(root_dir.rglob("*.gpkg"))
    if gpkg_files:
        return gpkg_files[0]

    csv_files = sorted(root_dir.rglob("*.csv"))
    if csv_files:
        return csv_files[0]

    raise ValueError("Archive did not contain a supported vector dataset.")


def _load_las_like_dataset(path: Path, *, csv_crs: str) -> Any:
    gpd = _load_geopandas()
    try:
        import laspy
    except ImportError as exc:
        raise RuntimeError("LAS/LAZ loading requires laspy.") from exc

    las = laspy.read(path)
    payload: dict[str, Any] = {
        "x": list(las.x),
        "y": list(las.y),
        "z": list(las.z),
    }
    for field_name in ("classification", "intensity", "return_number", "number_of_returns"):
        if hasattr(las, field_name):
            try:
                payload[field_name] = list(getattr(las, field_name))
            except Exception:
                continue
    return gpd.GeoDataFrame(payload, geometry=gpd.points_from_xy(payload["x"], payload["y"], crs=csv_crs), crs=csv_crs)


def list_vector_layers(path: str | Path) -> list[str]:
    dataset_path = Path(path)
    try:
        import pyogrio

        layers = pyogrio.list_layers(dataset_path)
        if hasattr(layers, "tolist"):
            values = layers.tolist()
        else:
            values = layers
        result = []
        for item in values:
            if isinstance(item, (list, tuple)) and item:
                result.append(str(item[0]))
            else:
                result.append(str(item))
        return result
    except Exception:
        try:
            import fiona

            return [str(name) for name in fiona.listlayers(dataset_path)]
        except Exception:
            return []


def default_vector_layer_name(layers: list[str]) -> str | None:
    preferred = ["multipolygons", "lines", "multilinestrings", "points", "other_relations"]
    lowered = {layer.lower(): layer for layer in layers}
    for candidate in preferred:
        if candidate in lowered:
            return lowered[candidate]
    return layers[0] if layers else None


def load_vector_dataset(
    path: str | Path,
    *,
    csv_x_field: str | None = None,
    csv_y_field: str | None = None,
    csv_crs: str = "EPSG:4326",
    ogr_layer: str | None = None,
    archive_limits: ArchiveSafetyLimits | None = None,
) -> Any:
    """Load a vector dataset from common local formats."""
    gpd = _load_geopandas()
    dataset_path = Path(path)
    suffix = dataset_path.suffix.lower()
    resolved_archive_limits = archive_limits or ArchiveSafetyLimits()

    if suffix == ".zip":
        extracted_dir = _extract_zip_archive(dataset_path, limits=resolved_archive_limits)
        resolved = _resolve_extracted_dataset(extracted_dir)
        return load_vector_dataset(
            resolved,
            csv_x_field=csv_x_field,
            csv_y_field=csv_y_field,
            csv_crs=csv_crs,
            ogr_layer=ogr_layer,
            archive_limits=resolved_archive_limits,
        )

    if suffix == ".kmz":
        extracted_dir = _extract_zip_archive(dataset_path, limits=resolved_archive_limits)
        kml_files = sorted(extracted_dir.rglob("*.kml"))
        if not kml_files:
            raise ValueError("KMZ input did not contain a KML payload.")
        return gpd.read_file(kml_files[0])

    if suffix == ".csv":
        from shapely.geometry import Point
        from shapely import wkt

        try:
            csv.field_size_limit(sys.maxsize)
        except OverflowError:
            csv.field_size_limit(2**31 - 1)

        rows: list[dict[str, Any]] = []
        with dataset_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows.extend(reader)
        if not rows:
            raise ValueError("CSV input is empty.")
        columns = list(rows[0].keys())
        geometry_column = _guess_geometry_column(columns)
        if geometry_column is not None:
            geometries = []
            parsed_rows: list[dict[str, Any]] = []
            for row in rows:
                parsed_row = dict(row)
                geometry_text = (parsed_row.pop(geometry_column, None) or "").strip()
                geometries.append(wkt.loads(geometry_text) if geometry_text else None)
                parsed_rows.append(parsed_row)
            return gpd.GeoDataFrame(parsed_rows, geometry=geometries, crs=csv_crs)

        x_field = csv_x_field
        y_field = csv_y_field
        if x_field is None or y_field is None:
            guessed_x, guessed_y = _guess_coordinate_columns(columns)
            x_field = x_field or guessed_x
            y_field = y_field or guessed_y
        geometries = []
        for row in rows:
            raw_x = row.get(x_field)
            raw_y = row.get(y_field)
            if raw_x in (None, "") or raw_y in (None, ""):
                geometries.append(None)
                continue
            try:
                geometries.append(Point(float(raw_x), float(raw_y)))
            except (TypeError, ValueError):
                geometries.append(None)
        return gpd.GeoDataFrame(
            rows,
            geometry=geometries,
            crs=csv_crs,
        )

    if suffix == ".parquet":
        return gpd.read_parquet(dataset_path)

    if suffix in {".las", ".laz"}:
        return _load_las_like_dataset(dataset_path, csv_crs=csv_crs)

    if suffix in {".pbf", ".osm"}:
        layer_name = ogr_layer
        if layer_name is None:
            layer_name = default_vector_layer_name(list_vector_layers(dataset_path))
        if layer_name is not None:
            return gpd.read_file(dataset_path, layer=layer_name)
        return gpd.read_file(dataset_path)

    if suffix in {".dxf", ".gdb", ".fgdb"}:
        if ogr_layer is not None:
            return gpd.read_file(dataset_path, layer=ogr_layer)
        return gpd.read_file(dataset_path)

    return gpd.read_file(dataset_path)


def convert_vector_dataset(
    input_path: str | Path,
    output_path: str | Path,
    *,
    output_format: str,
    csv_x_field: str | None = None,
    csv_y_field: str | None = None,
    csv_crs: str = "EPSG:4326",
    ogr_layer: str | None = None,
    archive_limits: ArchiveSafetyLimits | None = None,
) -> Path:
    """Convert a local vector dataset into another supported output format."""
    layer = load_vector_dataset(
        input_path,
        csv_x_field=csv_x_field,
        csv_y_field=csv_y_field,
        csv_crs=csv_crs,
        ogr_layer=ogr_layer,
        archive_limits=archive_limits,
    )
    return export_vector_layer(layer, output_path, output_format=output_format)


def export_vector_layer(layer: Any, output_path: str | Path, *, output_format: str) -> Path:
    """Export a loaded vector layer to a supported output format."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.lower()

    if fmt == "geojson":
        output.write_text(layer.to_json(), encoding="utf-8")
        return output

    if fmt == "csv":
        if layer.__class__.__name__ == "GeoDataFrame":
            import pandas as pd

            frame = pd.DataFrame(layer.copy())
        elif hasattr(layer, "to_pandas"):
            frame = layer.to_pandas()
        else:
            frame = layer.copy()
        if "geometry" in getattr(frame, "columns", []):
            frame["geometry"] = frame["geometry"].apply(lambda geom: getattr(geom, "wkt", str(geom)) if geom is not None else None)
        with output.open("w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
        return output

    if fmt == "geoparquet":
        layer.to_parquet(output, index=False, compression=None)
        return output

    if fmt == "gpkg":
        layer.to_file(output, driver="GPKG")
        return output

    if fmt == "kml":
        layer.to_file(output, driver="KML")
        return output

    if fmt == "shapefile":
        target_dir = output.with_suffix("")
        target_dir.mkdir(parents=True, exist_ok=True)
        shp_path = target_dir / f"{target_dir.name}.shp"
        layer.to_file(shp_path, driver="ESRI Shapefile")
        archive_path = output if output.suffix.lower() == ".zip" else output.with_suffix(".zip")
        with ZipFile(archive_path, "w") as archive:
            for file in target_dir.iterdir():
                archive.write(file, arcname=file.name)
        shutil.rmtree(target_dir)
        return archive_path

    raise ValueError(f"Unsupported output format: {output_format!r}")


def save_uploaded_file(uploaded_file: Any, suffix: str | None = None) -> Path:
    """Persist a Streamlit-uploaded file to a temporary local path."""
    name = getattr(uploaded_file, "name", "uploaded_dataset")
    final_suffix = suffix or Path(name).suffix
    temp_dir = Path(tempfile.mkdtemp(prefix="geoqa_upload_"))
    target = temp_dir / f"uploaded{final_suffix}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def save_uploaded_files(uploaded_files: list[Any]) -> Path:
    """Persist multiple uploaded files into one temporary directory."""
    if not uploaded_files:
        raise ValueError("No uploaded files were provided.")
    temp_dir = Path(tempfile.mkdtemp(prefix="geoqa_upload_bundle_"))
    for uploaded_file in uploaded_files:
        name = Path(getattr(uploaded_file, "name", "uploaded_part"))
        target = temp_dir / name.name
        target.write_bytes(uploaded_file.getbuffer())
    return temp_dir


def resolve_uploaded_dataset(uploaded_files: list[Any]) -> Path:
    """Resolve one or more uploaded files into a local dataset path."""
    if not uploaded_files:
        raise ValueError("No uploaded files were provided.")

    if len(uploaded_files) == 1:
        uploaded = uploaded_files[0]
        name = Path(getattr(uploaded, "name", "uploaded_dataset"))
        suffix = name.suffix.lower()
        if suffix == ".shp":
            raise ValueError(
                "A Shapefile requires its sidecar files too. Upload a .zip bundle or upload the .shp, .dbf, and .shx files together."
            )
        return save_uploaded_file(uploaded)

    bundle_dir = save_uploaded_files(uploaded_files)
    shapefiles = sorted(bundle_dir.glob("*.shp"))
    if not shapefiles:
        raise ValueError("Multi-file upload did not include a .shp file.")
    if len(shapefiles) > 1:
        raise ValueError("Multi-file upload included multiple .shp files. Upload only one Shapefile dataset at a time.")

    shapefile = shapefiles[0]
    required_sidecars = [
        shapefile.with_suffix(".dbf"),
        shapefile.with_suffix(".shx"),
    ]
    missing = [path.name for path in required_sidecars if not path.exists()]
    if missing:
        raise ValueError(
            f"Uploaded Shapefile is incomplete. Missing required sidecar file(s): {', '.join(missing)}."
        )
    return shapefile


def layer_preview_geojson(layer: Any, *, limit: int = 50) -> str:
    """Return a small GeoJSON preview string for map display."""
    if hasattr(layer, "head"):
        preview = layer.head(limit)
    else:
        preview = layer
    return preview.to_json()


def table_preview_frame(layer: Any, *, limit: int = 50) -> Any:
    """Return a Streamlit-friendly preview frame with geometry converted to WKT."""
    if hasattr(layer, "head"):
        preview = layer.head(limit).copy()
    else:
        preview = layer.copy()
    if hasattr(preview, "to_pandas"):
        preview = preview.to_pandas()
    elif preview.__class__.__name__ == "GeoDataFrame":
        import pandas as pd

        preview = pd.DataFrame(preview.copy())
    columns = getattr(preview, "columns", [])
    if "geometry" in columns:
        preview["geometry"] = preview["geometry"].apply(
            lambda geom: getattr(geom, "wkt", str(geom)) if geom is not None else None
        )
    return preview


def summarize_vector_layer(layer: Any) -> dict[str, Any]:
    """Return a small metadata summary for UI display."""
    geometry_types = None
    try:
        geometry_types = {str(key): int(value) for key, value in layer.geometry.geom_type.value_counts().to_dict().items()}
    except Exception:
        pass
    return {
        "row_count": len(layer) if hasattr(layer, "__len__") else None,
        "column_count": len(getattr(layer, "columns", [])),
        "crs": str(getattr(layer, "crs", None)) if getattr(layer, "crs", None) is not None else None,
        "geometry_types": geometry_types,
    }


__all__ = [
    "ArchiveSafetyLimits",
    "convert_vector_dataset",
    "export_vector_layer",
    "layer_preview_geojson",
    "load_vector_dataset",
    "list_vector_layers",
    "default_vector_layer_name",
    "resolve_uploaded_dataset",
    "save_uploaded_file",
    "save_uploaded_files",
    "summarize_vector_layer",
    "table_preview_frame",
]
