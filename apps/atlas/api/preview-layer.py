import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler
from _common import (
    _parse_vercel_request,
    _write_vercel_response,
    _make_vercel_handler,
    _error_response,
    _json_response,
    _options_response,
    _preview_geojson,
    _preview_shapefile_zip,
)


def handle(request):
    if request.method == "OPTIONS":
        return _options_response()
    if request.method != "POST":
        return _json_response({"detail": "Method not allowed."}, status=405)

    try:
        filename = request.query.get("filename", "upload")
        layer = request.query.get("layer")
        data = request.body or b""
        if not data:
            return _error_response("Upload a GeoJSON FeatureCollection, CSV, OSM/PBF, or zipped Shapefile.")
        lower = filename.lower()
        if lower.endswith(".zip"):
            result = _preview_shapefile_zip(data, filename, layer)
        elif lower.endswith(".csv") or lower.endswith(".osm") or lower.endswith(".pbf") or lower.endswith(".osm.pbf"):
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory(prefix="geoqa_atlas_preview_") as temp_dir:
                target = Path(temp_dir) / filename
                target.write_bytes(data)
                from geoqa.conversion import load_vector_dataset
                gdf = load_vector_dataset(target, ogr_layer=layer)
                features = []
                for _, row in gdf.iterrows():
                    geom = row.get("geometry")
                    if geom is None:
                        continue
                    try:
                        gj = geom.__geo_interface__
                    except Exception:
                        continue
                    props = {k: v for k, v in row.items() if k != "geometry"}
                    features.append({"type": "Feature", "geometry": gj, "properties": props})
                result = {
                    "collection": {"type": "FeatureCollection", "features": features[:500]},
                    "label": f"{len(features)} features loaded from {filename}.",
                    "note": "",
                    "layers": [{"name": layer or filename, "path": layer or filename, "feature_count": len(gdf), "geometry_type": None, "is_valid": True}],
                    "detected_layer_count": 1,
                    "selected_layer": layer or filename,
                    "can_run_all_layers": False,
                }
        else:
            result = _preview_geojson(data)
        return _json_response(result)
    except ValueError as exc:
        return _error_response(str(exc))
    except Exception as exc:  # pragma: no cover
        return _error_response(f"Unable to read layer preview: {exc}", status=500)

class handler(BaseHTTPRequestHandler):
    def _dispatch(self):
        try:
            request = _parse_vercel_request(self)
            result = handle(request)
            _write_vercel_response(self, result)
        except Exception as exc:
            import traceback
            body = traceback.format_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body.encode())))
            self.end_headers()
            self.wfile.write(body.encode())

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()

    def log_message(self, *args, **kwargs):
        return
