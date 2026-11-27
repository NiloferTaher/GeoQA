from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd

from geoqa.conversion import (
    ArchiveSafetyLimits,
    default_vector_layer_name,
    export_vector_layer,
    layer_preview_geojson,
    list_vector_layers,
    load_vector_dataset,
    resolve_uploaded_dataset,
    summarize_vector_layer,
    table_preview_frame,
)


class _FakeUpload:
    def __init__(self, path: Path) -> None:
        self.name = path.name
        self._payload = path.read_bytes()

    def getbuffer(self) -> bytes:
        return self._payload


class TestConversionHelpers(unittest.TestCase):
    def test_default_vector_layer_name_prefers_multipolygons(self) -> None:
        self.assertEqual(
            default_vector_layer_name(["points", "lines", "multipolygons"]),
            "multipolygons",
        )

    def test_default_vector_layer_name_returns_none_for_empty_list(self) -> None:
        self.assertIsNone(default_vector_layer_name([]))

    def test_list_vector_layers_unknown_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "not_a_vector_dataset.bin"
            fake_path.write_bytes(b"nope")
            self.assertEqual(list_vector_layers(fake_path), [])

    def test_export_vector_layer_geojson(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_vector_layer(layer, Path(tmpdir) / "out.geojson", output_format="geojson")
            payload = json.loads(Path(output).read_text(encoding="utf-8"))
        self.assertEqual(payload["type"], "FeatureCollection")

    def test_load_vector_dataset_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "points.csv"
            csv_path.write_text("ID,longitude,latitude\n1,1.0,2.0\n", encoding="utf-8")
            layer = load_vector_dataset(csv_path)
        self.assertEqual(len(layer), 1)
        self.assertEqual(str(layer.crs), "EPSG:4326")

    def test_load_vector_dataset_csv_census_style_coordinate_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "places.csv"
            csv_path.write_text(
                "NAME,INTPTLAT_num,INTPTLONG_num\nAbanda,33.091627,-85.527029\n",
                encoding="utf-8",
            )
            layer = load_vector_dataset(csv_path)
        self.assertEqual(len(layer), 1)
        self.assertEqual(layer.geometry.iloc[0].geom_type, "Point")
        self.assertEqual(str(layer.crs), "EPSG:4326")

    def test_load_vector_dataset_csv_missing_coordinate_rows_become_null_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "places.csv"
            csv_path.write_text(
                "NAME,INTPTLAT_num,INTPTLONG_num\nAbanda,33.091627,-85.527029\nBroken,,\n",
                encoding="utf-8",
            )
            layer = load_vector_dataset(csv_path)
        self.assertEqual(len(layer), 2)
        self.assertEqual(layer.geometry.iloc[0].geom_type, "Point")
        self.assertIsNone(layer.geometry.iloc[1])

    def test_load_vector_dataset_csv_wkt_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "polygons.csv"
            csv_path.write_text(
                'ID,name,geometry\n1,a,"POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"\n',
                encoding="utf-8",
            )
            layer = load_vector_dataset(csv_path)
        self.assertEqual(len(layer), 1)
        self.assertEqual(layer.geometry.iloc[0].geom_type, "Polygon")
        self.assertEqual(str(layer.crs), "EPSG:4326")

    def test_preview_and_summary(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        preview = layer_preview_geojson(layer)
        table_preview = table_preview_frame(layer)
        summary = summarize_vector_layer(layer)
        self.assertIn('"FeatureCollection"', preview)
        self.assertIsInstance(table_preview.loc[0, "geometry"], str)
        self.assertEqual(summary["row_count"], 1)

    def test_load_vector_dataset_geoparquet(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = Path(tmpdir) / "points.parquet"
            layer.to_parquet(parquet_path, index=False)
            loaded = load_vector_dataset(parquet_path)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded.crs.equals(layer.crs))

    def test_export_vector_layer_geoparquet_roundtrip(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = export_vector_layer(layer, Path(tmpdir) / "out.parquet", output_format="geoparquet")
            loaded = load_vector_dataset(parquet_path)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded.crs.equals(layer.crs))

    def test_export_geoparquet_to_csv_roundtrip(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1], "name": ["a"]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = Path(tmpdir) / "source.parquet"
            csv_path = Path(tmpdir) / "converted.csv"
            layer.to_parquet(parquet_path, index=False)
            loaded = load_vector_dataset(parquet_path)
            export_vector_layer(loaded, csv_path, output_format="csv")
            roundtrip = load_vector_dataset(csv_path)
        self.assertEqual(len(roundtrip), 1)
        self.assertEqual(roundtrip.geometry.iloc[0].geom_type, "Point")

    def test_resolve_uploaded_dataset_single_shp_requires_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            shp_path = Path(tmpdir) / "sample.shp"
            shp_path.write_bytes(b"placeholder")
            with self.assertRaisesRegex(ValueError, "requires its sidecar files"):
                resolve_uploaded_dataset([_FakeUpload(shp_path)])

    def test_resolve_uploaded_dataset_shapefile_bundle(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "shape"
            dataset_dir.mkdir()
            shp_path = dataset_dir / "sample.shp"
            layer.to_file(shp_path, driver="ESRI Shapefile")
            uploads = [_FakeUpload(path) for path in dataset_dir.iterdir() if path.suffix.lower() in {".shp", ".dbf", ".shx", ".prj", ".cpg"}]
            resolved = resolve_uploaded_dataset(uploads)
            loaded = load_vector_dataset(resolved)
            self.assertEqual(resolved.suffix.lower(), ".shp")
            self.assertEqual(len(loaded), 1)

    def test_resolve_uploaded_dataset_missing_required_sidecar(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "shape"
            dataset_dir.mkdir()
            shp_path = dataset_dir / "sample.shp"
            layer.to_file(shp_path, driver="ESRI Shapefile")
            shx_path = shp_path.with_suffix(".shx")
            if shx_path.exists():
                shx_path.unlink()
            uploads = [_FakeUpload(path) for path in dataset_dir.iterdir() if path.suffix.lower() in {".shp", ".dbf", ".prj", ".cpg"}]
            with self.assertRaisesRegex(ValueError, "Missing required sidecar"):
                resolve_uploaded_dataset(uploads)

    def test_load_vector_dataset_zip_geojson(self) -> None:
        layer = gpd.GeoDataFrame(
            {"ID": [1]},
            geometry=gpd.points_from_xy([1.0], [2.0]),
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "sample.geojson"
            zip_path = Path(tmpdir) / "sample.zip"
            layer.to_file(geojson_path, driver="GeoJSON")
            import zipfile

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.write(geojson_path, arcname="sample.geojson")
            loaded = load_vector_dataset(zip_path)
        self.assertEqual(len(loaded), 1)

    def test_load_vector_dataset_zip_rejects_unsafe_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "bad.zip"
            import zipfile

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../evil.geojson", "{}")
            with self.assertRaisesRegex(ValueError, "Unsafe archive member path"):
                load_vector_dataset(zip_path)

    def test_load_vector_dataset_zip_respects_archive_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "big.zip"
            import zipfile

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("sample.geojson", "x" * 2048)
            with self.assertRaisesRegex(ValueError, "above the configured safety limit"):
                load_vector_dataset(zip_path, archive_limits=ArchiveSafetyLimits(max_uncompressed_size_mb=0.001))


if __name__ == "__main__":
    unittest.main()
